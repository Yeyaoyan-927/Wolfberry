"""售后工单：交易闭环的最后一段。

真实场景：买家收到枸杞后发现霉变、数量不符或与描述不一致，需要一条
可留痕的处理路径，而不是只在聊天里吵。工单天然关联订单与**上架时的
AI 评估快照**——这是平台判定"上架时是否就与描述不符"的客观依据。

状态机（单向，不可回退）：
    1 待卖家响应 → 2 卖家同意退货/退款 → 5 已解决
                 → 3 卖家拒绝 → 4 平台介入中（买家申请）→ 5 已解决 / 6 已关闭
    1 → 4  买家直接申请平台介入（卖家超时未响应）
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

# 售后类型
AS_QUALITY = 1      # 质量问题（霉变/坏果/油果）
AS_QUANTITY = 2     # 数量/重量不符
AS_NOT_AS_DESC = 3  # 与描述不符（等级、规格）
AS_LOGISTICS = 4    # 物流破损/未收到
AS_OTHER = 5

TYPE_LABELS = {
    AS_QUALITY: "质量问题",
    AS_QUANTITY: "数量不符",
    AS_NOT_AS_DESC: "与描述不符",
    AS_LOGISTICS: "物流问题",
    AS_OTHER: "其他",
}

# 工单状态
AS_PENDING = 1       # 待卖家响应
AS_AGREED = 2        # 卖家同意
AS_REJECTED = 3      # 卖家拒绝
AS_ESCALATED = 4     # 平台介入中
AS_RESOLVED = 5      # 已解决
AS_CLOSED = 6        # 已关闭

STATUS_LABELS = {
    AS_PENDING: "待卖家响应",
    AS_AGREED: "卖家已同意",
    AS_REJECTED: "卖家已拒绝",
    AS_ESCALATED: "平台介入中",
    AS_RESOLVED: "已解决",
    AS_CLOSED: "已关闭",
}

# 未结案状态：同一订单不允许重复提工单
AS_OPEN_STATUSES = (AS_PENDING, AS_AGREED, AS_REJECTED, AS_ESCALATED)

ACT_APPLY = "apply"        # 买家申请
ACT_AGREE = "agree"        # 卖家同意
ACT_REJECT = "reject"      # 卖家拒绝
ACT_ESCALATE = "escalate"  # 买家申请平台介入
ACT_RESOLVE = "resolve"    # 平台裁决


class AfterSale(Base, TimestampMixin):
    __tablename__ = "after_sale"
    __table_args__ = (
        Index("idx_as_order", "order_id"),
        Index("idx_as_status", "status", "created_at"),
        Index("idx_as_buyer", "buyer_id"),
        Index("idx_as_seller", "seller_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), nullable=False)
    order_no: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_title: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    buyer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)

    type: Mapped[int] = mapped_column(Integer, default=AS_OTHER, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 举证图 URL 列表
    refund_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    status: Mapped[int] = mapped_column(Integer, default=AS_PENDING, nullable=False)
    seller_reply: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    resolution: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    resolved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    responded_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AfterSaleLog(Base, TimestampMixin):
    """工单处理轨迹：只增不改，纠纷复盘时按时间线还原。"""

    __tablename__ = "after_sale_log"
    __table_args__ = (Index("idx_aslog_ticket", "ticket_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("after_sale.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_role: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status_after: Mapped[int] = mapped_column(Integer, nullable=False)
