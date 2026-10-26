"""商品与商品图片。"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

STATUS_DRAFT = 0
STATUS_PENDING = 1
STATUS_ON_SHELF = 3
STATUS_REJECTED = 4
STATUS_OFF_SHELF = 5

GRADES = ("特优", "特级", "甲级", "乙级", "等外")


class Product(Base, TimestampMixin):
    __tablename__ = "product"
    __table_args__ = (
        Index("idx_product_status", "status"),
        Index("idx_product_seller", "seller_id", "status"),
        Index("idx_product_dim", "variety", "grade_platform", "origin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    variety: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_per_50g: Mapped[int] = mapped_column(Integer, default=280, nullable=False)

    # 卖家自述等级 / 平台认定等级 —— 差异标记的依据
    grade_claim: Mapped[str] = mapped_column(String(16), nullable=False)
    grade_platform: Mapped[str | None] = mapped_column(String(16), nullable=True)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    min_order_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=50, nullable=False)

    status: Mapped[int] = mapped_column(Integer, default=STATUS_DRAFT, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # AI 评估摘要（明细见评估表，此处冗余便于列表排序）
    ai_grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    defect_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    moldy_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    grain_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cover_key: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    cover_url: Mapped[str] = mapped_column(String(800), default="", nullable=False)

    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class ProductImage(Base, TimestampMixin):
    __tablename__ = "product_image"
    __table_args__ = (Index("idx_image_product", "product_id", "sort"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)

    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(800), default="", nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), default="image/jpeg", nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # L1 门禁：1 通过 / 2 不通过
    l1_status: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    l1_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MarketQuote(Base, TimestampMixin):
    """行情样本（成交/挂牌），定价建议的数据来源。"""

    __tablename__ = "market_quote"
    __table_args__ = (
        Index("idx_quote_dim", "variety", "grade", "origin", "spec_per_50g", "stat_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    variety: Mapped[str] = mapped_column(String(32), nullable=False)
    grade: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_per_50g: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    stat_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    quote_type: Mapped[str] = mapped_column(String(16), default="deal", nullable=False)  # deal|listing
    source: Mapped[str] = mapped_column(String(128), default="平台成交", nullable=False)
