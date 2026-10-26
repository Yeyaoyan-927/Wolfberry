"""行情数据访问：定价建议的数据来源。"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select

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
