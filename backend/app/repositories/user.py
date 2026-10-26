"""用户数据访问。"""
from __future__ import annotations

from sqlalchemy import select

from app.models.sys import SysUser
from app.repositories.base import BaseRepo


class UserRepo(BaseRepo[SysUser]):
    model = SysUser

    def by_username(self, username: str) -> SysUser | None:
        return self.session.scalar(select(SysUser).where(SysUser.username == username))

    def active_by_id(self, user_id: int) -> SysUser | None:
        return self.session.scalar(
            select(SysUser).where(SysUser.id == user_id, SysUser.is_active.is_(True))
        )
