"""行情数据访问：定价建议的数据来源。"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select

from app.models.product import MarketQuote
from app.repositories.base import BaseRepo


class MarketRepo(BaseRepo[MarketQuote]):
    model = MarketQuote

    def add_many(self, quotes: list[MarketQuote]) -> None:
        self.session.add_all(quotes)
        self.session.flush()

    def recent_prices(
        self,
        *,
        variety: str,
        grade: str,
        origin: str | None = None,
        spec_per_50g: int | None = None,
        days: int = 30,
        quote_type: str = "deal",
    ) -> Sequence[MarketQuote]:
        """按维度取近 N 天样本。维度条件全部下推 SQL。"""
        since = dt.date.today() - dt.timedelta(days=days)
        conds = [
            MarketQuote.variety == variety,
            MarketQuote.grade == grade,
            MarketQuote.quote_type == quote_type,
            MarketQuote.stat_date >= since,
        ]
        if origin:
            conds.append(MarketQuote.origin == origin)
        if spec_per_50g:
            conds.append(MarketQuote.spec_per_50g == spec_per_50g)
        return self.session.scalars(
            select(MarketQuote).where(*conds).order_by(MarketQuote.stat_date)
        ).all()

    def latest_date(self) -> dt.date | None:
        return self.session.scalar(select(MarketQuote.stat_date).order_by(MarketQuote.stat_date.desc()).limit(1))

    def avg_price(
        self, *, variety: str, grade: str, days: int = 30
    ) -> Decimal | None:
        rows = self.recent_prices(variety=variety, grade=grade, days=days)
        if not rows:
            return None
        return sum((r.price for r in rows), Decimal("0")) / len(rows)

    def availability(self, *, days: int = 30) -> list[dict]:
        """有成交数据的维度组合 + 样本量，供前端渲染下拉与空数据兜底。

        按样本量降序：样本越多的组合代表性越强，作为默认推荐。
        """
        since = dt.date.today() - dt.timedelta(days=days)
        rows = self.session.execute(
            select(
                MarketQuote.variety,
                MarketQuote.grade,
                func.count(MarketQuote.id).label("n"),
                func.avg(MarketQuote.price).label("avg_price"),
            )
            .where(MarketQuote.quote_type == "deal", MarketQuote.stat_date >= since)
            .group_by(MarketQuote.variety, MarketQuote.grade)
            .order_by(func.count(MarketQuote.id).desc())
        ).all()
        return [
            {
                "variety": v,
                "grade": g,
                "samples": int(n),
                "avg_price": round(float(p), 2),
            }
            for v, g, n, p in rows
        ]
