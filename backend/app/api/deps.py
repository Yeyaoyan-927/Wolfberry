"""接口层依赖：数据库会话、当前用户、角色校验。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.core.security import decode_token
from app.infra.db import get_session
from app.models.sys import SysUser
from app.repositories.user import UserRepo

DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> SysUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise BizError(Err.UNAUTHORIZED, "未登录或缺少凭证")
    token = authorization.split(" ", 1)[1].strip()

    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise BizError(Err.UNAUTHORIZED, "登录状态无效")

    user = UserRepo(session).active_by_id(int(user_id))
    if user is None:
        raise BizError(Err.UNAUTHORIZED, "账号不存在或已停用")
    return user


CurrentUser = Annotated[SysUser, Depends(get_current_user)]


def require_role(*roles: str):
    """角色校验依赖工厂。"""

    def dependency(user: CurrentUser) -> SysUser:
        if user.role not in roles:
            raise BizError(Err.FORBIDDEN, f"需要以下角色之一：{'/'.join(roles)}")
        return user

    return dependency


SellerUser = Annotated[SysUser, Depends(require_role("seller", "admin"))]
AdminUser = Annotated[SysUser, Depends(require_role("admin"))]
AnyUser = Annotated[SysUser, Depends(get_current_user)]
