"""行情接口：聚合走势与产区概览（公开只读）。"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.logging import new_trace_id
from app.models.product import STATUS_ON_SHELF, MarketQuote, Product
from app.schemas.common import ok
from app.repositories.market import MarketRepo

router = APIRouter(tags=["market"])

VARIETIES = ("宁杞5号", "宁杞7号", "大麻叶")
GRADES = ("特优", "特级", "甲级", "乙级")
ORIGINS = ("中宁", "诺木洪", "靖远")


@router.get("/market/summary")
def market_summary(
    session: DbSession,
    variety: str = Query("宁杞5号"),
    grade: str = Query("特级"),
    days: int = Query(30, ge=7, le=180),
):
    """按日聚合的成交价序列 + 汇总（趋势图数据源）。"""
    rows = MarketRepo(session).recent_prices(variety=variety, grade=grade, days=days)
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        buckets[str(r.stat_date)].append(float(r.price))

    points = [
        {
            "date": d,
            "avg": round(sum(v) / len(v), 2),
            "low": round(min(v), 2),
            "high": round(max(v), 2),
            "count": len(v),
        }
        for d, v in sorted(buckets.items())
    ]
    prices = [float(r.price) for r in rows]
    summary = None
    if prices:
        avg = sum(prices) / len(prices)
        summary = {
            "avg": round(avg, 2),
            "low": round(min(prices), 2),
            "high": round(max(prices), 2),
            "samples": len(prices),
            # 最近 7 天均值 vs 前 7 天均值 → 涨跌
            "trend_pct": _trend(points),
        }
    return ok({
        "variety": variety, "grade": grade, "days": days,
        "points": points, "summary": summary,
        "options": {"varieties": list(VARIETIES), "grades": list(GRADES), "origins": list(ORIGINS)},
    }, trace_id=new_trace_id())


def _trend(points: list[dict]) -> float | None:
    if len(points) < 4:
        return None
    recent = [p["avg"] for p in points[-3:]]
    earlier = [p["avg"] for p in points[-7:-3]] or [p["avg"] for p in points[:-3]]
    if not earlier:
        return None
    a, b = sum(recent) / len(recent), sum(earlier) / len(earlier)
    return round((a - b) / b * 100, 1)


@router.get("/market/origins")
def market_origins(session: DbSession):
    """按产区聚合在售货源：数量、均价、最低价（首页"按产区找"）。"""
    rows = session.execute(
        select(
            Product.origin,
            Product.variety,
            Product.unit_price,
        ).where(Product.status == STATUS_ON_SHELF)
    ).all()
    agg: dict[str, dict] = {}
    for origin, variety, price in rows:
        item = agg.setdefault(origin, {"origin": origin, "count": 0, "sum": 0.0,
                                        "min": float(price), "varieties": set()})
        item["count"] += 1
        item["sum"] += float(price)
        item["min"] = min(item["min"], float(price))
        item["varieties"].add(variety)
    data = [
        {"origin": v["origin"], "count": v["count"],
         "avg_price": round(v["sum"] / v["count"], 2), "min_price": round(v["min"], 2),
         "varieties": sorted(v["varieties"])}
        for v in agg.values()
    ]
    data.sort(key=lambda x: -x["count"])
    return ok(data, trace_id=new_trace_id())
