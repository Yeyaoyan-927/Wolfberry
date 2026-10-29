"""轻量数据库结构迁移（幂等）。

项目未引入 Alembic 迁移目录（演示环境用 create_all 建表），
但 create_all 只建新表、不会给已有表加列。本脚本补这个缺口：
    - 检查列是否存在，不存在则 ALTER TABLE 添加
    - 可重复执行，已存在则跳过

用法：python scripts/migrate_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import engine  # noqa: E402

# (表, 列, DDL 片段)
COLUMNS: list[tuple[str, str, str]] = [
    ("kb_document", "chunk_size", "INT NOT NULL DEFAULT 500"),
    ("kb_document", "chunk_overlap", "INT NOT NULL DEFAULT 80"),
    ("sys_user", "seller_status", "INT NOT NULL DEFAULT 0"),
    ("product", "rating_avg", "DECIMAL(3,2) NOT NULL DEFAULT 0"),
    ("product", "review_count", "INT NOT NULL DEFAULT 0"),
]


def main() -> None:
    setup_logging("WARNING")
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    added = 0

    with engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if table not in existing_tables:
                print(f"  跳过 {table}.{column}（表不存在，create_all 会建）")
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if column in cols:
                print(f"  已存在 {table}.{column}")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            print(f"  新增 {table}.{column} {ddl}")
            added += 1

    # 存量卖家视为已认证（历史数据无资质记录，不应因新规则失去发布能力）
    with engine.begin() as conn:
        n = conn.execute(
            text("UPDATE sys_user SET seller_status = 2 WHERE role = 'seller' AND seller_status = 0")
        ).rowcount
        if n:
            print(f"  存量卖家标记为已认证：{n} 个")

    print(f"\n迁移完成，新增 {added} 列")


if __name__ == "__main__":
    main()
