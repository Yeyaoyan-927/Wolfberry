"""订单服务：下单（冻结库存）、确认、发货、收货、取消、支付登记。

职责：
- 状态流转全部经 domain/order_state.py 校验，这里不写状态规则
- 库存冻结 / 回滚走原子 UPDATE
- 买家 / 卖家 / 管理员三种视角的数据权限在这里收口
"""
from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.domain.order_state import action_of, can_transit, role_allowed
from app.models.order import (
    PAY_REGISTERED,
    PAY_UNPAID,
    ST_CANCELLED,
    ST_CONFIRMING,
    ST_DONE,
    ST_SHIPPED,
    ST_TO_SHIP,
    STATUS_LABELS,
    Order,
)
from app.models.product import STATUS_ON_SHELF, Product
from app.models.sys import SysUser
from app.repositories.order import OrderRepo
from app.schemas.order import OrderOut

logger = logging.getLogger(__name__)


def _to_out(order: Order) -> OrderOut:
    data = OrderOut.model_validate(order)
    data.status_label = STATUS_LABELS.get(order.status, "未知")
    return data


def _load_owned(session: Session, user: SysUser, order_id: int) -> Order:
    order = OrderRepo(session).by_id(order_id)
    if order is None:
        raise BizError(Err.NOT_FOUND, "订单不存在")
    if user.role == "buyer" and order.buyer_id != user.id:
        raise BizError(Err.FORBIDDEN, "无权查看该订单")
    if user.role == "seller" and order.seller_id != user.id:
        raise BizError(Err.FORBIDDEN, "无权操作该订单")
    return order


# ---------- 买家：下单 ----------
def create_order(session: Session, *, buyer: SysUser, product_id: int, quantity: Decimal) -> Order:
    if buyer.role != "buyer":
        raise BizError(Err.FORBIDDEN, "仅买家可下单")

    product = session.get(Product, product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    if product.status != STATUS_ON_SHELF:
        raise BizError(Err.PRODUCT_OFF_SHELF, "商品已下架或未上架，无法下单")
    if quantity < product.min_order_qty:
        raise BizError(Err.PARAM_INVALID, f"低于最小起订量 {product.min_order_qty}")

    repo = OrderRepo(session)
    # 原子冻结库存：不足即失败，无竞态
    if not repo.freeze_stock(session, product_id, quantity):
        raise BizError(Err.OUT_OF_STOCK, "库存不足或已被其他订单冻结")

    order = Order(
        buyer_id=buyer.id,
        seller_id=product.seller_id,
        product_id=product.id,
        product_title=product.title,
        unit_price=product.unit_price,
        quantity=quantity,
        total_amount=(product.unit_price * quantity).quantize(Decimal("0.01")),
        status=ST_CONFIRMING,
        ordered_at=dt.datetime.now(),
    )
    try:
        repo.add(order)
        session.flush()
    except Exception:
        # 下单失败归还冻结库存
        repo.restore_stock(session, product_id, quantity)
        raise
    logger.info("订单创建 %s product=%s qty=%s", order.order_no, product.product_no, quantity)
    return order


# ---------- 通用：流转 ----------
ACTION_ROLE_LABELS = {
    "confirm": "卖家",
    "cancel": "买家或卖家",
    "ship": "卖家",
    "receive": "买家",
}


def transit(
    session: Session,
    *,
    user: SysUser,
    order_id: int,
    to_status: int,
    ship_company: str = "",
    ship_no: str = "",
    cancel_reason: str = "",
) -> Order:
    order = _load_owned(session, user, order_id)
    action = action_of(order.status, to_status)
    if not can_transit(order.status, to_status):
        raise BizError(Err.ORDER_NOT_ALLOWED, f"当前状态「{STATUS_LABELS.get(order.status)}」不允许该操作")
    if not role_allowed(action, user.role):
        raise BizError(Err.FORBIDDEN, f"「{ACTION_ROLE_LABELS.get(action, action)}」才可执行该操作")

    now = dt.datetime.now()
    if to_status == ST_TO_SHIP:
        order.confirmed_at = now
    elif to_status == ST_SHIPPED:
        order.ship_company, order.ship_no = ship_company, ship_no
        order.shipped_at = now
    elif to_status == ST_DONE:
        order.completed_at = now
    elif to_status == ST_CANCELLED:
        order.cancelled_at = now
        order.cancel_reason = cancel_reason
        # 已发货后取消不再归还（实际是收货前取消才回库存；发货后不允许 cancel，见状态机）
        OrderRepo.restore_stock(session, order.product_id, order.quantity)

    order.status = to_status
    session.flush()
    logger.info("订单流转 %s ->%s by=%s", order.order_no, to_status, user.username)
    return order


# ---------- 买家：支付凭证登记（线下支付） ----------
def register_pay(session: Session, *, user: SysUser, order_id: int, voucher_key: str) -> Order:
    order = _load_owned(session, user, order_id)
    if order.buyer_id != user.id:
        raise BizError(Err.FORBIDDEN, "仅买家本人可登记支付")
    if order.pay_status == PAY_REGISTERED:
        raise BizError(Err.PAY_REGISTERED, "支付凭证已登记，请勿重复提交")
    if order.status not in (ST_CONFIRMING, ST_TO_SHIP):
        raise BizError(Err.ORDER_NOT_ALLOWED, "当前状态不可登记支付")
    order.pay_status = PAY_REGISTERED
    order.pay_voucher_key = voucher_key
    session.flush()
    return order


# ---------- 查询 ----------
def get_order(session: Session, *, user: SysUser, order_id: int) -> OrderOut:
    return _to_out(_load_owned(session, user, order_id))


def list_orders(
    session: Session,
    *,
    user: SysUser,
    status: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[OrderOut], int]:
    repo = OrderRepo(session)
    kwargs: dict = {}
    if user.role == "buyer":
        kwargs["buyer_id"] = user.id
    elif user.role == "seller":
        kwargs["seller_id"] = user.id
    rows, total = repo.search(status=status, offset=(page - 1) * size, limit=size, **kwargs)
    return [_to_out(r) for r in rows], total
