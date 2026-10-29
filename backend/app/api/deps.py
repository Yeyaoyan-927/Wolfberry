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


# 卖家专属：管理员不参与买卖（后台有独立的代操作接口），
# 否则会出现「管理员账号发布商品、出现在审核队列里」的荒谬路径
SellerUser = Annotated[SysUser, Depends(require_role("seller"))]
AdminUser = Annotated[SysUser, Depends(require_role("admin"))]
AnyUser = Annotated[SysUser, Depends(get_current_user)]


def get_optional_user(
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> SysUser | None:
    """可选鉴权：有 token 且有效返回用户，否则 None（公开接口用）。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = decode_token(authorization.split(" ", 1)[1].strip())
        user_id = payload.get("sub")
        if not user_id:
            return None
        return UserRepo(session).active_by_id(int(user_id))
    except Exception:
        return None


OptionalUser = Annotated[SysUser | None, Depends(get_optional_user)]
