"""认证服务。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError, Err
from app.core.security import create_access_token, hash_password, verify_password
from app.models.sys import (
    ROLE_BUYER,
    ROLE_SELLER,
    SQ_LABELS,
    SQ_NONE,
    SysUser,
)
from app.repositories.user import UserRepo
from app.schemas.auth import RegisterIn, TokenOut, UserOut


def login(session: Session, username: str, password: str) -> TokenOut:
    repo = UserRepo(session)
    user = repo.by_username(username)

    # 统一提示，避免暴露"用户是否存在"
    if user is None or not verify_password(password, user.password_hash):
        raise BizError(Err.UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise BizError(Err.FORBIDDEN, "账号已停用，请联系管理员")

    return _token_for(user)


def _token_for(user: SysUser) -> TokenOut:
    token = create_access_token(str(user.id), role=user.role, extra={"name": user.display_name})
    out = UserOut.model_validate(user)
    out.seller_status_label = SQ_LABELS.get(user.seller_status, "")
    return TokenOut(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=out,
    )


def register(session: Session, payload: RegisterIn) -> TokenOut:
    """自助注册：只允许 buyer / seller；卖家进入「未认证」状态。"""
    role = (payload.role or "").strip()
    if role not in (ROLE_BUYER, ROLE_SELLER):
        raise BizError(Err.PARAM_INVALID, "注册身份只能是买家或卖家")
    if role == ROLE_SELLER and len(payload.org_name.strip()) < 2:
        raise BizError(Err.PARAM_INVALID, "卖家注册需填写企业/合作社名称")

    repo = UserRepo(session)
    if repo.by_username(payload.username.strip()):
        raise BizError(Err.PARAM_INVALID, "用户名已被占用，请换一个")

    user = SysUser(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=role,
        display_name=(payload.display_name or payload.username).strip()[:64],
        org_name=payload.org_name.strip()[:128],
        phone_mask=_mask_phone(payload.contact_phone),
        # 卖家注册后需完成资质认证才能发布商品
        seller_status=SQ_NONE,
    )
    session.add(user)
    session.flush()
    return _token_for(user)


def _mask_phone(phone: str) -> str:
    """只存掩码：手机号属于敏感信息，平台侧无需完整号码。"""
    raw = (phone or "").strip()
    if len(raw) >= 7:
        return f"{raw[:3]}****{raw[-4:]}"
    return raw[:20]
