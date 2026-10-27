"""售后工单服务：申请 → 卖家响应 → 平台介入 → 裁决，全程留痕。"""
from __future__ import annotations

import datetime as dt
import logging
import random
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.domain import after_sale_state as fsm
from app.models.after_sale import (
    ACT_AGREE,
    ACT_APPLY,
    ACT_ESCALATE,
    ACT_REJECT,
    ACT_RESOLVE,
    AS_AGREED,
    AS_CLOSED,
    AS_ESCALATED,
    AS_OPEN_STATUSES,
    AS_PENDING,
    AS_REJECTED,
    AS_RESOLVED,
    STATUS_LABELS,
    TYPE_LABELS,
    AfterSale,
    AfterSaleLog,
)
from app.models.order import Order
from app.models.sys import SysUser
from app.schemas.after_sale import AfterSaleCreateIn, AfterSaleOut

logger = logging.getLogger(__name__)


def _ticket_no() -> str:
    return f"AS{dt.date.today():%Y%m%d}{''.join(random.choices(string.digits, k=5))}"


def _log(session: Session, ticket: AfterSale, *, action: str, actor: SysUser | None,
         note: str = "") -> None:
    session.add(
        AfterSaleLog(
            ticket_id=ticket.id,
            action=action,
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else "",
            note=note[:500],
            status_after=ticket.status,
        )
    )


def to_out(session: Session, ticket: AfterSale, *, with_logs: bool = False) -> AfterSaleOut:
    out = AfterSaleOut(
        id=ticket.id,
        ticket_no=ticket.ticket_no,
        order_id=ticket.order_id,
        order_no=ticket.order_no,
        product_id=ticket.product_id,
        product_title=ticket.product_title,
        buyer_id=ticket.buyer_id,
        seller_id=ticket.seller_id,
        type=ticket.type,
        type_label=TYPE_LABELS.get(ticket.type, "其他"),
        reason=ticket.reason,
        evidence=list(ticket.evidence or []),
        refund_amount=ticket.refund_amount or 0,
        status=ticket.status,
        status_label=STATUS_LABELS.get(ticket.status, ""),
        seller_reply=ticket.seller_reply,
        resolution=ticket.resolution,
        created_at=str(ticket.created_at or ""),
        responded_at=str(ticket.responded_at or ""),
        resolved_at=str(ticket.resolved_at or ""),
    )
    if with_logs:
        rows = session.scalars(
            select(AfterSaleLog).where(AfterSaleLog.ticket_id == ticket.id).order_by(AfterSaleLog.id)
        ).all()
        out.logs = [
            {
                "id": r.id, "action": r.action, "actor_id": r.actor_id,
                "actor_role": r.actor_role, "note": r.note,
                "status_after": r.status_after, "created_at": str(r.created_at or ""),
            }
            for r in rows
        ]
    return out


def apply(session: Session, *, user: SysUser, order_id: int, payload: AfterSaleCreateIn) -> AfterSaleOut:
    order = session.get(Order, order_id)
    if order is None:
        raise BizError(Err.NOT_FOUND, "订单不存在")
    if order.buyer_id != user.id:
        raise BizError(Err.FORBIDDEN, "只能对自己的订单申请售后")
    if not fsm.can_apply_order(order.status):
        raise BizError(Err.PARAM_INVALID, "仅已发货或已完成的订单可申请售后")
    dup = session.scalar(
        select(func.count(AfterSale.id)).where(
            AfterSale.order_id == order_id, AfterSale.status.in_(tuple(AS_OPEN_STATUSES))
        )
    )
    if dup:
        raise BizError(Err.PARAM_INVALID, "该订单已有处理中的售后工单，请勿重复提交")

    ticket = AfterSale(
        ticket_no=_ticket_no(),
        order_id=order.id,
        order_no=order.order_no,
        product_id=order.product_id,
        product_title=order.product_title,
        buyer_id=order.buyer_id,
        seller_id=order.seller_id,
        type=payload.type,
        reason=payload.reason,
        evidence=payload.evidence or [],
        refund_amount=payload.refund_amount,
        status=AS_PENDING,
    )
    session.add(ticket)
    session.flush()
    _log(session, ticket, action=ACT_APPLY, actor=user, note=f"申请售后：{TYPE_LABELS.get(payload.type)}")
    logger.info("售后申请 %s order=%s buyer=%s", ticket.ticket_no, order.order_no, user.username)
    return to_out(session, ticket, with_logs=True)


def list_tickets(session: Session, *, user: SysUser, status: int | None = None,
                 page: int = 1, size: int = 20) -> tuple[list[AfterSaleOut], int]:
    conds = []
    if user.role == "buyer":
        conds.append(AfterSale.buyer_id == user.id)
    elif user.role == "seller":
        conds.append(AfterSale.seller_id == user.id)
    if status:
        conds.append(AfterSale.status == status)

    total = session.scalar(select(func.count(AfterSale.id)).where(*conds)) or 0
    rows = session.scalars(
        select(AfterSale).where(*conds).order_by(AfterSale.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return [to_out(session, t) for t in rows], int(total)


def get_ticket(session: Session, *, user: SysUser, ticket_id: int) -> AfterSaleOut:
    ticket = session.get(AfterSale, ticket_id)
    if ticket is None:
        raise BizError(Err.NOT_FOUND, "工单不存在")
    if user.role != "admin" and user.id not in (ticket.buyer_id, ticket.seller_id):
        raise BizError(Err.FORBIDDEN, "无权查看该工单")
    return to_out(session, ticket, with_logs=True)


def _load_for_action(session: Session, user: SysUser, ticket_id: int, action: str) -> AfterSale:
    ticket = session.get(AfterSale, ticket_id)
    if ticket is None:
        raise BizError(Err.NOT_FOUND, "工单不存在")
    if not fsm.role_allowed(action, user.role):
        raise BizError(Err.FORBIDDEN, f"该操作仅 {fsm.ACTION_ROLE[action]} 可执行")
    if user.role == "seller" and ticket.seller_id != user.id:
        raise BizError(Err.FORBIDDEN, "只能处理自己店铺的工单")
    if user.role == "buyer" and ticket.buyer_id != user.id:
        raise BizError(Err.FORBIDDEN, "只能操作自己的工单")
    if not fsm.can_transit(ticket.status, action):
        raise BizError(
            Err.PARAM_INVALID,
            f"当前状态「{STATUS_LABELS.get(ticket.status)}」不支持该操作",
        )
    return ticket


def respond(session: Session, *, user: SysUser, ticket_id: int, agree: bool, note: str) -> AfterSaleOut:
    action = ACT_AGREE if agree else ACT_REJECT
    ticket = _load_for_action(session, user, ticket_id, action)

    ticket.seller_reply = note or ("同意买家的售后申请" if agree else "不同意，理由未填写")
    ticket.responded_at = dt.datetime.now()
    if agree:
        # 卖家同意即结案：平台不接支付通道，退款线下执行，这里只记录金额与结论
        ticket.status = AS_RESOLVED
        ticket.resolution = f"卖家同意，退款 ¥{ticket.refund_amount}（线下执行）"
        ticket.resolved_at = dt.datetime.now()
    else:
        ticket.status = AS_REJECTED
    _log(session, ticket, action=action, actor=user, note=ticket.seller_reply)
    return to_out(session, ticket, with_logs=True)


def escalate(session: Session, *, user: SysUser, ticket_id: int, note: str = "") -> AfterSaleOut:
    ticket = _load_for_action(session, user, ticket_id, ACT_ESCALATE)
    ticket.status = fsm.next_status(ticket.status, ACT_ESCALATE)
    _log(session, ticket, action=ACT_ESCALATE, actor=user, note=note or "买家申请平台介入")
    return to_out(session, ticket, with_logs=True)


def resolve(session: Session, *, admin: SysUser, ticket_id: int, outcome: str,
            note: str, refund_amount=None) -> AfterSaleOut:
    ticket = _load_for_action(session, admin, ticket_id, ACT_RESOLVE)
    target, default_note = fsm.RESOLVE_OUTCOMES[outcome]
    ticket.status = target
    ticket.resolution = note or default_note
    ticket.resolved_by = admin.id
    ticket.resolved_at = dt.datetime.now()
    if refund_amount is not None:
        ticket.refund_amount = refund_amount
    _log(session, ticket, action=ACT_RESOLVE, actor=admin, note=ticket.resolution)
    return to_out(session, ticket, with_logs=True)


def stats(session: Session) -> dict:
    """后台概览：各状态工单数 + 待处理数。"""
    rows = session.execute(
        select(AfterSale.status, func.count(AfterSale.id)).group_by(AfterSale.status)
    ).all()
    by_status = {int(s): int(n) for s, n in rows}
    return {
        "total": sum(by_status.values()),
        "pending": by_status.get(AS_PENDING, 0),
        "escalated": by_status.get(AS_ESCALATED, 0),
        "resolved": by_status.get(AS_RESOLVED, 0),
        "closed": by_status.get(AS_CLOSED, 0),
        "by_status": by_status,
    }
