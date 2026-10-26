"""订单：线下支付、平台只登记状态与凭证。

状态机：
    1 待卖家确认 → 2 待发货 → 3 已发货 → 4 已完成
         ↓
        5 已取消（买家取消 / 卖家拒单，均回滚冻结库存）

库存语义：product.stock 即「可售库存」，下单原子扣减（冻结），
取消归还；发货后不再归还。
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

# 订单状态
ST_CONFIRMING = 1   # 待卖家确认
ST_TO_SHIP = 2      # 待发货
ST_SHIPPED = 3      # 已发货
ST_DONE = 4         # 已完成
ST_CANCELLED = 5    # 已取消

STATUS_LABELS = {
    ST_CONFIRMING: "待卖家确认",
    ST_TO_SHIP: "待发货",
    ST_SHIPPED: "已发货",
    ST_DONE: "已完成",
    ST_CANCELLED: "已取消",
}

# 支付登记状态（线下支付，平台只记状态与凭证）
PAY_UNPAID = 0
PAY_REGISTERED = 1


class Order(Base, TimestampMixin):
    __tablename__ = "order"
    __table_args__ = (
        Index("idx_order_buyer", "buyer_id", "status"),
        Index("idx_order_seller", "seller_id", "status"),
        Index("idx_order_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    buyer_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)

    # 下单时快照，商品改价不影响历史订单
    product_title: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    status: Mapped[int] = mapped_column(Integer, default=ST_CONFIRMING, nullable=False)
    pay_status: Mapped[int] = mapped_column(Integer, default=PAY_UNPAID, nullable=False)
    pay_voucher_key: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    ship_company: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    ship_no: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    cancel_reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    ordered_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    shipped_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
