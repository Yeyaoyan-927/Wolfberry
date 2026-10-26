"""用户与角色。"""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

ROLE_BUYER = "buyer"
ROLE_SELLER = "seller"
ROLE_ADMIN = "admin"


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

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SysUser {self.username} {self.role}>"
