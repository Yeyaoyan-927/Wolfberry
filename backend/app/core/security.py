"""密码哈希与访问令牌。"""
from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.errors import BizError, Err


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, *, role: str, extra: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except jwt.ExpiredSignatureError as exc:
        raise BizError(Err.TOKEN_EXPIRED, "登录已过期，请重新登录") from exc
    except jwt.PyJWTError as exc:
        raise BizError(Err.UNAUTHORIZED, "登录状态无效") from exc
