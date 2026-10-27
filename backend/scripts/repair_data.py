"""数据一致性体检与修复（可重复执行）。

覆盖三类"不报错但业务上说不通"的脏数据：
    1. 在售商品缺平台认定等级（grade_platform 为空）——买家会看到「认定 —」
    2. 商品有图但封面为空（cover_url 空）——列表页显示破图
    3. 订单金额与「单价 × 数量」不符——对账必错

用法：
    python scripts/repair_data.py          # 只体检，报告问题
    python scripts/repair_data.py --fix    # 体检并修复
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.models.order import Order  # noqa: E402
from app.models.product import STATUS_ON_SHELF, Product, ProductImage  # noqa: E402


def check_grade_platform(session, fix: bool) -> int:
    rows = session.scalars(
        select(Product).where(Product.status == STATUS_ON_SHELF, Product.grade_platform.is_(None))
    ).all()
    print(f"[认定等级] 在售但无平台认定：{len(rows)} 件")
    for p in rows:
        fallback = p.ai_grade or p.grade_claim
        print(f"   #{p.id} {p.title[:24]} → 回填「{fallback}」")
        if fix:
            p.grade_platform = fallback
    return len(rows)


def check_cover(session, fix: bool) -> int:
    rows = session.scalars(
        select(Product).where((Product.cover_url == "") | (Product.cover_url.is_(None)))
    ).all()
    fixed = 0
    print(f"[封面] 封面为空的商品：{len(rows)} 件")
    for p in rows:
        img = session.scalar(
            select(ProductImage).where(ProductImage.product_id == p.id, ProductImage.l1_status == 1)
            .order_by(ProductImage.id).limit(1)
        )
        if img is None:
            print(f"   #{p.id} {p.title[:24]} → 无可用图，跳过")
            continue
        print(f"   #{p.id} {p.title[:24]} → 用图 #{img.id} {img.url[-28:]}")
        if fix:
            p.cover_url = img.url
        fixed += 1
    return len(rows) - (0 if fix else 0) if rows else 0


def check_order_amount(session, fix: bool) -> int:
    rows = session.scalars(select(Order)).all()
    bad = [o for o in rows if Decimal(str(o.total_amount)) != (Decimal(str(o.unit_price)) * Decimal(str(o.quantity))).quantize(Decimal("0.01"))]
    print(f"[订单金额] 金额与「单价×数量」不符：{len(bad)} 单（共 {len(rows)} 单）")
    for o in bad:
        expect = (Decimal(str(o.unit_price)) * Decimal(str(o.quantity))).quantize(Decimal("0.01"))
        print(f"   {o.order_no} 记录 {o.total_amount} → 应为 {expect}")
        if fix:
            o.total_amount = expect
    return len(bad)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="执行修复（默认只报告）")
    fix = parser.parse_args().fix
    setup_logging("WARNING")

    session = SessionLocal()
    try:
        print("=" * 60)
        print("数据体检" + ("（含修复）" if fix else "（只读）"))
        print("=" * 60)
        n1 = check_grade_platform(session, fix)
        n2 = check_cover(session, fix)
        n3 = check_order_amount(session, fix)
        if fix:
            session.commit()
            print("\n已提交修复")
        total = n1 + n2 + n3
        print(f"\n问题合计 {total} 处" + ("，已修复" if fix else "，加 --fix 执行修复"))
    finally:
        session.close()


if __name__ == "__main__":
    main()
