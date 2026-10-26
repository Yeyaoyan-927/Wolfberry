"""认证接口。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

from app.api.deps import CurrentUser, DbSession
from app.core.logging import new_trace_id
from app.schemas.auth import LoginIn, UserOut
from app.schemas.common import ok
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(payload: LoginIn, session: DbSession):
    trace = new_trace_id()
    result = auth_service.login(session, payload.username, payload.password)
    return ok(jsonable_encoder(result), trace_id=trace)


@router.get("/auth/me")
def me(user: CurrentUser):
    return ok(jsonable_encoder(UserOut.model_validate(user)), trace_id=new_trace_id())
