"""清理无图 / 图片不可显示的商品记录。

判定"图片不可显示"（三条任一命中）：
    1. 没有任何 product_image
    2. 所有图的原始文件在本地存储中缺失或 0 字节
    3. 所有图都被 L1 门禁拦截（l1_status != 1）
另外封面为空但库里其实有可用图的，顺手回填封面（不删）。

删除规则（遵守架构底线）：
    - 有订单的商品**不删**（订单是交易凭证，删了没法对账），改为下架 + 报告
    - 无订单：删评估明细 → 删图片 → 删商品；
      **audit_log 保留**（审核留痕不可删除，后台日志页显示"（商品已删除）"）

用法：
    python scripts/clean_image_products.py            # 只扫描报告
    python scripts/clean_image_products.py --fix      # 执行清理
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.models.assessment import ProductAssessment  # noqa: E402
from app.models.order import Order  # noqa: E402
from app.models.product import STATUS_OFF_SHELF, Product, ProductImage  # noqa: E402

UPLOADS = Path(__file__).resolve().parents[1] / "var" / "uploads"


def _file_of(url: str, key: str) -> Path:
    k = (key or "").strip() or (url.split("/files/")[-1] if "/files/" in url else "")
    return UPLOADS / k.lstrip("/")


def inspect(session, product: Product) -> dict:
    imgs = session.scalars(
        select(ProductImage).where(ProductImage.product_id == product.id).order_by(ProductImage.id)
    ).all()
    usable = []
    reasons = []
    for im in imgs:
        fp = _file_of(im.url or "", im.object_key or "")
        exists = fp.exists() and fp.stat().st_size > 0
        if not exists:
            reasons.append(f"图#{im.id} 文件缺失")
        elif im.l1_status != 1:
            reasons.append(f"图#{im.id} 被 L1 拦截")
        else:
            usable.append(im)
    bad = not usable
    n_order = session.scalar(
        select(func.count(Order.id)).where(Order.product_id == product.id)
    ) or 0
    return {
        "product": product,
        "images_total": len(imgs),
        "usable": usable,
        "reasons": reasons,
        "orders": int(n_order),
        "bad": bad,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="执行清理")
    args = parser.parse_args()
    setup_logging("WARNING")

    session = SessionLocal()
    try:
        products = session.scalars(select(Product).order_by(Product.id)).all()
        to_delete, to_archive, fixable = [], [], []

        print(f"扫描 {len(products)} 件商品…")
        print("-" * 88)
        for p in products:
            info = inspect(session, p)
            if not info["bad"]:
                # 有可用图但封面为空 → 回填，不删
                if not p.cover_url and info["usable"]:
                    fixable.append((p, info["usable"][0]))
                continue
            tag = f"订单{info['orders']}"
            print(f"  #{p.id:>2} [{p.status}] {p.title[:26]:28} 图{info['images_total']} "
                  f"{tag:6} {' / '.join(info['reasons'][:2]) or '无图'}")
            (to_archive if info["orders"] > 0 else to_delete).append(info)

        print("-" * 88)
        print(f"可物理删除 {len(to_delete)} 件 | 有订单需下架 {len(to_archive)} 件 | 可回填封面 {len(fixable)} 件")

        if not args.fix:
            print("\n加 --fix 执行")
            return

        for info in to_delete:
            p = info["product"]
            session.query(ProductAssessment).filter(
                ProductAssessment.product_id == p.id
            ).delete(synchronize_session=False)
            session.query(ProductImage).filter(
                ProductImage.product_id == p.id
            ).delete(synchronize_session=False)
            print(f"  删除 #{p.id} {p.title[:24]}")
            session.delete(p)

        for info in to_archive:
            p = info["product"]
            p.status = STATUS_OFF_SHELF
            p.stock = 0
            print(f"  下架 #{p.id} {p.title[:24]}（有 {info['orders']} 笔订单，保留交易凭证）")

        for p, im in fixable:
            p.cover_url = im.url
            print(f"  回填封面 #{p.id} ← 图#{im.id}")

        session.commit()
        print(f"\n完成：删除 {len(to_delete)} / 下架 {len(to_archive)} / 回填封面 {len(fixable)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
