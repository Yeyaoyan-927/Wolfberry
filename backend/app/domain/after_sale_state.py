"""售后状态机（纯函数，可单测）。

只允许这些流转，其余一律拒绝——售后涉及退款与纠纷定责，
状态不能靠"想改就改"，必须闭环。
"""
from __future__ import annotations

from app.models.after_sale import (
    ACT_AGREE,
    ACT_APPLY,
    ACT_ESCALATE,
    ACT_REJECT,
    ACT_RESOLVE,
    AS_AGREED,
    AS_CLOSED,
    AS_ESCALATED,
    AS_PENDING,
    AS_REJECTED,
    AS_RESOLVED,
)

# (当前状态, 动作) → 目标状态
# 注意：resolve 的目标状态由裁决结果（outcome）决定，这里只登记"允许裁决"，
# 实际落地状态由 RESOLVE_OUTCOMES 覆盖。
TRANSITIONS: dict[tuple[int, str], int] = {
    (AS_PENDING, ACT_AGREE): AS_AGREED,
    (AS_PENDING, ACT_REJECT): AS_REJECTED,
    (AS_PENDING, ACT_ESCALATE): AS_ESCALATED,
    (AS_PENDING, ACT_RESOLVE): AS_RESOLVED,
    (AS_REJECTED, ACT_ESCALATE): AS_ESCALATED,
    (AS_ESCALATED, ACT_RESOLVE): AS_RESOLVED,
}

# 动作 → 允许的角色
ACTION_ROLE: dict[str, str] = {
    ACT_APPLY: "buyer",
    ACT_AGREE: "seller",
    ACT_REJECT: "seller",
    ACT_ESCALATE: "buyer",
    ACT_RESOLVE: "admin",
}

# 平台裁决可选结果
RESOLVE_OUTCOMES = {
    "refund_buyer": (AS_RESOLVED, "平台判定：支持买家，全额退款"),
    "support_seller": (AS_CLOSED, "平台判定：支持卖家，工单关闭"),
    "partial": (AS_RESOLVED, "平台判定：部分退款，双方协商一致"),
    "closed": (AS_CLOSED, "平台判定：证据不足，工单关闭"),
}

# 已发货/已完成的订单才允许申请售后
APPLICABLE_ORDER_STATUS = (3, 4)


def can_transit(status: int, action: str) -> bool:
    return (status, action) in TRANSITIONS


def next_status(status: int, action: str) -> int | None:
    return TRANSITIONS.get((status, action))


def role_allowed(action: str, role: str) -> bool:
    return ACTION_ROLE.get(action) == role


def can_apply_order(order_status: int) -> bool:
    return order_status in APPLICABLE_ORDER_STATUS
