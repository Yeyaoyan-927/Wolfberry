"""认证服务。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError, Err
from app.core.security import create_access_token, verify_password
from app.repositories.user import UserRepo
from app.schemas.auth import TokenOut, UserOut


def login(session: Session, username: str, password: str) -> TokenOut:
    repo = UserRepo(session)
    user = repo.by_username(username)

    # 统一提示，避免暴露"用户是否存在"
    if user is None or not verify_password(password, user.password_hash):
        raise BizError(Err.UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise BizError(Err.FORBIDDEN, "账号已停用，请联系管理员")

    token = create_access_token(str(user.id), role=user.role, extra={"name": user.display_name})
    return TokenOut(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )
