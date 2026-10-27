"""售后工单接口：买家申请、卖家响应、平台仲裁。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from app.api.deps import AdminUser, AnyUser, DbSession
from app.core.logging import new_trace_id
from app.schemas.after_sale import (
    AfterSaleCreateIn,
    AfterSaleReplyIn,
    AfterSaleResolveIn,
)
from app.schemas.common import ok
from app.services import after_sale_service

router = APIRouter(tags=["after-sale"])


@router.post("/orders/{order_id}/after-sale")
def apply_after_sale(order_id: int, payload: AfterSaleCreateIn, session: DbSession, user: AnyUser):
    """买家对已发货/已完成的订单申请售后（同一订单不能重复提未结案工单）。"""
    trace = new_trace_id()
    out = after_sale_service.apply(session, user=user, order_id=order_id, payload=payload)
    return ok(jsonable_encoder(out), trace_id=trace)


@router.get("/after-sales")
def list_after_sales(
    session: DbSession,
    user: AnyUser,
    status: int | None = Query(None, ge=1, le=6),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """按角色隔离：买家看自己买的、卖家看自己卖的、管理员看全部。"""
    trace = new_trace_id()
    items, total = after_sale_service.list_tickets(
        session, user=user, status=status, page=page, size=size
    )
    return ok(
        {"items": jsonable_encoder(items), "total": total, "page": page, "size": size},
        trace_id=trace,
    )


@router.get("/after-sales/{ticket_id}")
def after_sale_detail(ticket_id: int, session: DbSession, user: AnyUser):
    trace = new_trace_id()
    return ok(jsonable_encoder(after_sale_service.get_ticket(session, user=user, ticket_id=ticket_id)),
              trace_id=trace)


@router.post("/after-sales/{ticket_id}/respond")
def respond_after_sale(ticket_id: int, payload: AfterSaleReplyIn, session: DbSession, user: AnyUser):
    """卖家响应：同意（直接结案，线下退款）或拒绝。"""
    trace = new_trace_id()
    out = after_sale_service.respond(
        session, user=user, ticket_id=ticket_id, agree=payload.agree, note=payload.note
    )
    return ok(jsonable_encoder(out), trace_id=trace)


@router.post("/after-sales/{ticket_id}/escalate")
def escalate_after_sale(ticket_id: int, session: DbSession, user: AnyUser,
                        note: str = Query("", max_length=500)):
    """买家申请平台介入。"""
    trace = new_trace_id()
    out = after_sale_service.escalate(session, user=user, ticket_id=ticket_id, note=note)
    return ok(jsonable_encoder(out), trace_id=trace)


@router.post("/admin/after-sales/{ticket_id}/resolve")
def resolve_after_sale(ticket_id: int, payload: AfterSaleResolveIn, session: DbSession, admin: AdminUser):
    """平台裁决：支持买家全额退款 / 部分退款 / 支持卖家 / 证据不足关闭。"""
    trace = new_trace_id()
    out = after_sale_service.resolve(
        session, admin=admin, ticket_id=ticket_id,
        outcome=payload.outcome, note=payload.note,
        refund_amount=payload.refund_amount if payload.refund_amount else None,
    )
    return ok(jsonable_encoder(out), trace_id=trace)


@router.get("/admin/after-sales/stats")
def after_sale_stats(session: DbSession, admin: AdminUser):
    trace = new_trace_id()
    return ok(after_sale_service.stats(session), trace_id=trace)
