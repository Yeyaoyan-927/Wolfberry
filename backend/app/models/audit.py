"""审核记录：不可删除，只增（质检/审核类业务强留痕）。

每次审核动作落一行快照：当时的自述等级、AI 等级、差异标记、
审核员动作与理由 —— 事后可完整还原「为什么这个商品能上架」。
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

ACT_APPROVE = "approve"   # 通过上架
ACT_REJECT = "reject"     # 驳回
ACT_GRADE = "grade"       # 改级（审核员修正平台认定等级，通常伴随通过）


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_product", "product_id"),
        Index("idx_audit_auditor", "auditor_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    auditor_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False)

    action: Mapped[str] = mapped_column(String(16), nullable=False)

    # 快照：审核时的差异标记上下文
    grade_claim: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    ai_grade: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    grade_platform_before: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    grade_platform_after: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    diff_flag: Mapped[str] = mapped_column(String(8), default="", nullable=False)  # 绿黄红蓝灰

    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    acted_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
