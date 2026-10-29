"""商品评价。

设计要点（与售后互补，不重叠）：
    售后 = 出问题后的**纠纷处理**，可退款，有工单与平台裁决
    评价 = 交易完成后的**体验打分**，不可退款，公开影响其他买家决策
    所以评价只在订单「已完成」且无进行中售后时允许提交，避免"一边打一星一边要退款"。

同一订单只允许一条评价（order_id 唯一），保证评分不被刷。
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin


class ProductReview(Base, TimestampMixin):
    __tablename__ = "product_review"
    __table_args__ = (
        Index("idx_review_product", "product_id", "created_at"),
        Index("idx_review_buyer", "buyer_id"),
        Index("idx_review_order", "order_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), nullable=False)
    order_no: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    buyer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    rating: Mapped[int] = mapped_column(Integer, nullable=False)          # 1~5
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)        # 快捷标签
    images: Mapped[list | None] = mapped_column(JSON, nullable=True)      # 实拍图
    anonymous: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)

    # 卖家回复（一条，可覆盖）
    reply: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    replied_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
