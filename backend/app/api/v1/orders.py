"""订单接口：买家下单/取消/收货/支付登记，卖家确认/发货，双方查询。"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from app.api.deps import AnyUser, DbSession
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.schemas.order import CancelIn, OrderCreateIn, PayRegisterIn, ShipIn
from app.services import order_service

router = APIRouter(tags=["orders"])


@router.post("/orders")
def create_order(payload: OrderCreateIn, user: AnyUser, session: DbSession):
    """买家下单：冻结库存，进入「待卖家确认」。"""
    trace = new_trace_id()
    order = order_service.create_order(session, buyer=user, product_id=payload.product_id,
                                       quantity=Decimal(payload.quantity))
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order.id)),
              trace_id=trace)


@router.get("/orders")
def list_orders(
    session: DbSession,
    user: AnyUser,
    status: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """我的订单：买家看自己买的，卖家看自己卖的，管理员看全部。"""
    trace = new_trace_id()
    items, total = order_service.list_orders(session, user=user, status=status,
                                             page=page, size=size)
    return ok({"items": jsonable_encoder(items), "total": total, "page": page, "size": size},
              trace_id=trace)


@router.get("/orders/{order_id}")
def order_detail(order_id: int, user: AnyUser, session: DbSession):
    trace = new_trace_id()
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order_id)),
              trace_id=trace)


@router.post("/orders/{order_id}/confirm")
def confirm_order(order_id: int, user: AnyUser, session: DbSession):
    """卖家确认订单：待确认 → 待发货。"""
    trace = new_trace_id()
    order = order_service.transit(session, user=user, order_id=order_id, to_status=2)
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order.id)),
              trace_id=trace)


@router.post("/orders/{order_id}/ship")
def ship_order(order_id: int, payload: ShipIn, user: AnyUser, session: DbSession):
    """卖家发货：登记物流公司与单号（平台只记录，不做物流对接）。"""
    trace = new_trace_id()
    order = order_service.transit(session, user=user, order_id=order_id, to_status=3,
                                  ship_company=payload.ship_company, ship_no=payload.ship_no)
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order.id)),
              trace_id=trace)


@router.post("/orders/{order_id}/receive")
def receive_order(order_id: int, user: AnyUser, session: DbSession):
    """买家确认收货：已发货 → 已完成。"""
    trace = new_trace_id()
    order = order_service.transit(session, user=user, order_id=order_id, to_status=4)
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order.id)),
              trace_id=trace)


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, payload: CancelIn, user: AnyUser, session: DbSession):
    """取消订单（待确认/待发货可取消），冻结库存全额归还。"""
    trace = new_trace_id()
    order = order_service.transit(session, user=user, order_id=order_id, to_status=5,
                                  cancel_reason=payload.reason)
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order.id)),
              trace_id=trace)


@router.post("/orders/{order_id}/pay")
def register_pay(order_id: int, payload: PayRegisterIn, user: AnyUser, session: DbSession):
    """买家登记线下支付凭证（平台不接支付通道，只记状态与凭证键）。"""
    trace = new_trace_id()
    order = order_service.register_pay(session, user=user, order_id=order_id,
                                       voucher_key=payload.voucher_key)
    return ok(jsonable_encoder(order_service.get_order(session, user=user, order_id=order.id)),
              trace_id=trace)
