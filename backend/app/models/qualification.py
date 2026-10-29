"""卖家资质认证。

为什么单独一张表而不是塞进 sys_user：
    资质是"可多次提交、有审核历史、带证件图片"的业务对象，
    用户表只保留一个冗余状态位（seller_status）用于鉴权判断。
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin


class SellerQualification(Base, TimestampMixin):
    __tablename__ = "seller_qualification"
    __table_args__ = (
        Index("idx_sq_user", "user_id"),
        Index("idx_sq_status", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False)

    company_name: Mapped[str] = mapped_column(String(128), nullable=False)
    credit_code: Mapped[str] = mapped_column(String(32), default="", nullable=False)   # 统一社会信用代码
    legal_person: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    origin: Mapped[str] = mapped_column(String(64), default="", nullable=False)        # 主要产区
    contact_phone: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    intro: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # 证件图（营业执照 / 产地证明等），存相对 URL
    licenses: Mapped[list | None] = mapped_column(JSON, nullable=True)

    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reject_reason: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    audited_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audited_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
