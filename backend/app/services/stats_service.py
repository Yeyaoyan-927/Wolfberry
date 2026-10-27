"""管理端统计：仪表盘数据源（只读聚合）。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assessment import ProductAssessment
from app.models.kb import KbChunk, KbDocument
from app.models.order import Order
from app.models.product import Product
from app.models.sys import SysUser


def admin_stats(session: Session) -> dict:
    today = dt.date.today()
    week_ago = today - dt.timedelta(days=6)

    # 商品状态分布
    status_rows = session.execute(
        select(Product.status, func.count()).group_by(Product.status)
    ).all()
    status_map = {int(s): int(c) for s, c in status_rows}

    # 订单
    order_rows = session.execute(
        select(Order.status, func.count(), func.coalesce(func.sum(Order.total_amount), 0))
        .group_by(Order.status)
    ).all()
    order_map = {int(s): (int(c), float(v)) for s, c, v in order_rows}
    gmv = sum(v for _, v in order_map.values())

    # 近 7 天上架趋势
    trend_rows = session.execute(
        select(func.date(Product.published_at), func.count())
        .where(Product.published_at >= dt.datetime.combine(week_ago, dt.time.min))
        .group_by(func.date(Product.published_at))
    ).all()
    trend_map = {str(d): int(c) for d, c in trend_rows}
    trend = [
        {"date": str(week_ago + dt.timedelta(days=i)),
         "count": trend_map.get(str(week_ago + dt.timedelta(days=i)), 0)}
        for i in range(7)
    ]

    # 评估
    assessed_today = session.scalar(
        select(func.count())
        .select_from(ProductAssessment)
        .where(func.date(ProductAssessment.created_at) == today)
    ) or 0

    # 知识库
    kb_docs = session.scalar(select(func.count()).select_from(KbDocument)) or 0
    kb_chunks = session.scalar(select(func.count()).select_from(KbChunk)) or 0

    # 用户
    role_rows = session.execute(
        select(SysUser.role, func.count()).group_by(SysUser.role)
    ).all()
    role_map = {r: int(c) for r, c in role_rows}

    return {
        "products": {
            "total": sum(status_map.values()),
            "pending": status_map.get(1, 0),
            "on_shelf": status_map.get(3, 0),
            "rejected": status_map.get(4, 0),
        },
        "orders": {
            "total": sum(c for c, _ in order_map.values()),
            "gmv": round(gmv, 2),
            "by_status": {"1": order_map.get(1, (0, 0))[0], "2": order_map.get(2, (0, 0))[0],
                          "3": order_map.get(3, (0, 0))[0], "4": order_map.get(4, (0, 0))[0],
                          "5": order_map.get(5, (0, 0))[0]},
        },
        "users": {"buyers": role_map.get("buyer", 0), "sellers": role_map.get("seller", 0),
                  "admins": role_map.get("admin", 0)},
        "assessment": {"today": int(assessed_today)},
        "kb": {"docs": int(kb_docs), "chunks": int(kb_chunks)},
        "publish_trend": trend,
    }
