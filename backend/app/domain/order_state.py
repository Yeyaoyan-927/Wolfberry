"""订单状态机：纯函数定义合法流转，Service 只调用不自行判断。"""
from __future__ import annotations

from app.models.order import ST_CANCELLED, ST_CONFIRMING, ST_DONE, ST_SHIPPED, ST_TO_SHIP

# 合法流转表：from -> (to, 动作, 允许角色)
TRANSITIONS = {
    (ST_CONFIRMING, ST_TO_SHIP): "confirm",   # 卖家确认
    (ST_CONFIRMING, ST_CANCELLED): "cancel",  # 买家取消 / 卖家拒单
    (ST_TO_SHIP, ST_CANCELLED): "cancel",     # 发货前仍可取消
    (ST_TO_SHIP, ST_SHIPPED): "ship",         # 卖家发货
    (ST_SHIPPED, ST_DONE): "receive",         # 买家确认收货
}

ACTION_ROLE = {
    "confirm": ("seller",),
    "cancel": ("buyer", "seller"),
    "ship": ("seller",),
    "receive": ("buyer",),
}


def can_transit(from_status: int, to_status: int) -> bool:
    return (from_status, to_status) in TRANSITIONS


def action_of(from_status: int, to_status: int) -> str | None:
    return TRANSITIONS.get((from_status, to_status))


def role_allowed(action: str, role: str) -> bool:
    return role in ACTION_ROLE.get(action, ())
