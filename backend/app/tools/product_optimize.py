"""Skill 2：商品优化建议。

输入商品 ID，输出按严重程度排序的改进项：
    图片质量 / 等级高报 / 缺陷率 / 置信度 / 描述完整度
规则实现：app/domain/optimize.py。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.services import skill_service
from app.tools.base import ToolContext, ToolSpec, registry


class OptimizeArgs(BaseModel):
    product_id: int = Field(..., ge=1, description="商品 ID")


def _handle(ctx: ToolContext, args: OptimizeArgs) -> dict:
    advice = skill_service.product_optimize(ctx.session, args.product_id)
    return advice.model_dump()


product_optimize_tool = ToolSpec(
    name="product_optimize",
    description=(
        "商品优化建议：根据实拍图校验结果与 AI 外观评估，指出等级高报、缺陷率偏高、"
        "图片质量不足等问题，并给出可执行的改进动作与预期效果。只给建议，不修改商品。"
    ),
    args_model=OptimizeArgs,
    handler=_handle,
    scope={"seller", "admin"},
    timeout_ms=2000,
)

registry.register(product_optimize_tool)
