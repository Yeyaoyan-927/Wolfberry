"""Skill 1：卖家定价建议。

数据来源：平台近 30 天成交（不足则放宽到 90 天 / 全国）。
规则实现：app/domain/pricing.py（纯函数，可单测）。
"""
from __future__ import annotations

from app.schemas.skill import PriceSuggestIn
from app.services import skill_service
from app.tools.base import ToolContext, ToolSpec, registry


def _handle(ctx: ToolContext, args: PriceSuggestIn) -> dict:
    advice = skill_service.price_suggest(ctx.session, args)
    return advice.model_dump()


price_suggest_tool = ToolSpec(
    name="price_suggest",
    description=(
        "卖家定价建议：输入品种、等级、产区、规格与拟售数量，返回走量/适中/溢价三档参考价、"
        "市场均价与分位区间、当前定价的偏离度。仅给建议，不修改商品价格。"
    ),
    args_model=PriceSuggestIn,
    handler=_handle,
    scope={"seller", "admin"},
    timeout_ms=3000,
)

registry.register(price_suggest_tool)
