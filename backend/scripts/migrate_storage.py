"""存量迁移：COS 对象 → 本地磁盘，并更新 DB 里的 url 为本地相对路径。

用法：python scripts/migrate_storage.py
前提：COS 凭据仍在 .env.dev（迁移一次性读取），STORAGE_DRIVER 已切 local。
范围：product_image / product.cover_url / kb_document。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.infra.storage.local import LocalStorage  # noqa: E402
from app.models.kb import KbDocument  # noqa: E402
from app.models.product import Product, ProductImage  # noqa: E402


def fetch_cos():
    """直接构造 COS 客户端（迁移期一次性使用，不受当前 driver 配置影响）。"""
    from app.infra.storage.cos import CosStorage

    return CosStorage()


def migrate(session) -> None:
    cos = fetch_cos()
    local = LocalStorage()
    moved = skipped = failed = 0

    def move(object_key: str) -> str | None:
        """COS 取回 → 本地落盘 → 返回新 url；失败返回 None。"""
        nonlocal moved, skipped, failed
        if not object_key or local.exists(object_key):
            skipped += 1
            return f"/files/{object_key}" if object_key else None
        try:
            data = cos.get_bytes(object_key)
        except Exception as exc:  # noqa: BLE001
            print(f"  [失败] {object_key}: {exc}")
            failed += 1
            return None
        stored = local.put(data, object_key)
        moved += 1
        return stored.url

    # 商品图
    for img in session.scalars(select(ProductImage)).all():
        new_url = move(img.object_key)
        if new_url:
            img.url = new_url
    # 封面
    for p in session.scalars(select(Product)).all():
        if p.cover_key:
            new_url = move(p.cover_key)
            if new_url:
                p.cover_url = new_url
    # 知识库文档
    for doc in session.scalars(select(KbDocument)).all():
        new_url = move(doc.object_key)
        if new_url:
            doc.url = new_url

    session.commit()
    print(f"迁移完成：下载 {moved} 个对象，跳过(已存在/空) {skipped}，失败 {failed}")


if __name__ == "__main__":
    setup_logging("WARNING")
    s = SessionLocal()
    migrate(s)
    s.close()
