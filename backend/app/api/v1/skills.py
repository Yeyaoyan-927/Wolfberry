"""Skill 接口：工具清单、统一调用入口、场景化快捷端点。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

from app.api.deps import AnyUser, DbSession, SellerUser
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.schemas.skill import PriceSuggestIn
from app.services import skill_service
from app.tools import registry
from app.tools.base import ToolContext

router = APIRouter(tags=["skills"])


@router.get("/tools")
def list_tools(user: AnyUser):
    """当前角色可用的工具清单（含入参 schema，前端可直接渲染表单）。"""
    return ok(jsonable_encoder(registry.list_for(user.role)), trace_id=new_trace_id())


@router.post("/tools/{name}/invoke")
def invoke_tool(name: str, payload: dict, user: AnyUser, session: DbSession):
    """统一调用入口：Agent 与前端页面共用同一套工具。"""
    trace = new_trace_id()
    ctx = ToolContext(session=session, user_id=user.id, role=user.role)
    result = registry.invoke(name, payload, ctx)
    return ok(result, trace_id=trace)


# ---------------- 场景化快捷端点（不改工具语义，只是更省事） ----------------


@router.post("/skills/price-suggest")
def price_suggest(payload: PriceSuggestIn, seller: SellerUser, session: DbSession):
    trace = new_trace_id()
    ctx = ToolContext(session=session, user_id=seller.id, role=seller.role)
    result = registry.invoke("price_suggest", payload.model_dump(), ctx)
    return ok(result, trace_id=trace)


@router.get("/skills/products/{product_id}/optimize")
def product_optimize(product_id: int, seller: SellerUser, session: DbSession):
    trace = new_trace_id()
    ctx = ToolContext(session=session, user_id=seller.id, role=seller.role)
    result = registry.invoke(
        "product_optimize", {"product_id": product_id}, ctx
    )
    return ok(result, trace_id=trace)


# 供冒烟脚本/无登录场景复用
def _invoke_direct(session, *, name: str, args: dict, role: str = "seller"):
    ctx = ToolContext(session=session, user_id=None, role=role)
    return registry.invoke(name, args, ctx)
