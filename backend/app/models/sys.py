"""用户与角色。"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

ROLE_BUYER = "buyer"
ROLE_SELLER = "seller"
ROLE_ADMIN = "admin"

ROLES = (ROLE_BUYER, ROLE_SELLER, ROLE_ADMIN)

# 卖家入驻认证状态（买家恒为 0，不参与该流程）
SQ_NONE = 0        # 未提交
SQ_PENDING = 1     # 待审核
SQ_VERIFIED = 2    # 已认证（唯一允许发布商品的状态）
SQ_REJECTED = 3    # 已驳回

SQ_LABELS = {
    SQ_NONE: "未认证",
    SQ_PENDING: "待审核",
    SQ_VERIFIED: "已认证",
    SQ_REJECTED: "已驳回",
}


class SysUser(Base, TimestampMixin):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default=ROLE_BUYER, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    phone_mask: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    org_name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 冗余字段：鉴权时免 join 资质表；真实资料见 seller_qualification
    seller_status: Mapped[int] = mapped_column(Integer, default=SQ_NONE, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SysUser {self.username} {self.role}>"
