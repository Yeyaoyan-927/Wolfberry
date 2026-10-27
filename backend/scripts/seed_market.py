"""行情数据种子：给行情中心 / 首页行情 / 审核行情参考提供真实可用样本。

为什么单独一个脚本：
    market_quote 是全网行情的底座，被 4 处消费（行情中心、首页速览、产区聚合、
    审核工作台的"同类行情参考"）。表一旦空，这 4 处全部显示"暂无数据"，
    但不会报错，很容易被忽略。所以做成可重复执行的独立脚本。

用法：
    python scripts/seed_market.py          # 补缺失维度（有数据的维度跳过）
    python scripts/seed_market.py --reset  # 清空后重建
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.models.product import MarketQuote  # noqa: E402

# (品种, 等级, 产区, 基准价低, 基准价高, 规格粒数)
# 价位参考 2026 年中宁/诺木洪产地价：特优 > 特级 > 甲级，大麻叶整体偏低
DIMENSIONS: list[tuple[str, str, str, float, float, int]] = [
    ("宁杞5号", "特优", "中宁", 52.0, 58.0, 220),
    ("宁杞5号", "特级", "中宁", 44.0, 49.0, 280),
    ("宁杞5号", "甲级", "中宁", 35.0, 39.5, 320),
    ("宁杞7号", "特优", "诺木洪", 49.0, 55.0, 220),
    ("宁杞7号", "特级", "诺木洪", 41.0, 46.5, 280),
    ("宁杞7号", "甲级", "诺木洪", 33.0, 37.5, 320),
    ("大麻叶", "特级", "靖远", 38.0, 43.0, 300),
    ("大麻叶", "甲级", "靖远", 30.0, 34.0, 340),
]

DAYS = 90


def _series(low: float, high: float) -> list[float]:
    """生成 90 天价格：温和上行 + 周期性波动 + 噪声，避免直线显得假。"""
    import math

    out = []
    for i in range(DAYS):          # i=0 最早
        pct = i / (DAYS - 1)
        trend = low + (high - low) * (0.35 + 0.65 * pct)   # 起点约 35% 分位
        wave = math.sin(i / 6.5) * (high - low) * 0.06      # 周级波动
        noise = random.uniform(-0.35, 0.35)
        out.append(round(trend + wave + noise, 2))
    return out


def seed(reset: bool = False) -> None:
    setup_logging("WARNING")
    session = SessionLocal()
    try:
        if reset:
            deleted = session.query(MarketQuote).delete()
            session.commit()
            print(f"  已清空行情 {deleted} 条")

        today = dt.date.today()
        total_new = 0
        for variety, grade, origin, low, high, spec in DIMENSIONS:
            exists = (
                session.query(MarketQuote)
                .filter(
                    MarketQuote.variety == variety,
                    MarketQuote.grade == grade,
                    MarketQuote.origin == origin,
                )
                .count()
            )
            if exists:
                print(f"  跳过 {variety}/{grade}/{origin}（已有 {exists} 条）")
                continue

            prices = _series(low, high)
            rows = []
            for i, price in enumerate(prices):
                stat_date = today - dt.timedelta(days=DAYS - 1 - i)
                rows.append(
                    MarketQuote(
                        variety=variety,
                        grade=grade,
                        origin=origin,
                        spec_per_50g=spec,
                        price=price,
                        volume=round(random.uniform(120, 860), 1),
                        stat_date=stat_date,
                        quote_type="deal",
                        source="平台成交（演示数据）",
                    )
                )
            session.add_all(rows)
            session.commit()
            total_new += len(rows)
            print(f"  新增 {variety}/{grade}/{origin}：{len(rows)} 天，"
                  f"{prices[0]} → {prices[-1]} 元/kg")

        print(f"\n完成，本次写入 {total_new} 条")
        _report(session)
    finally:
        session.close()


def _report(session) -> None:
    from sqlalchemy import func, select

    rows = session.execute(
        select(
            MarketQuote.variety,
            MarketQuote.grade,
            func.count(MarketQuote.id),
            func.min(MarketQuote.price),
            func.max(MarketQuote.price),
        )
        .group_by(MarketQuote.variety, MarketQuote.grade)
        .order_by(MarketQuote.variety, MarketQuote.grade)
    ).all()
    print("当前行情覆盖：")
    for variety, grade, n, lo, hi in rows:
        print(f"  {variety:8} {grade:4} {n:3} 天  ¥{lo} ~ ¥{hi}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="清空后重建")
    seed(reset=parser.parse_args().reset)
