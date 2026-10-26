"""Agent 状态定义。"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    question: Annotated[str, "用户原始问题"]
    role: Annotated[str, "调用者角色 buyer/seller/admin"]
    intent: Annotated[str, "意图：standards/market/find_products/seller_advice/other"]
    entities: Annotated[dict, "意图附带的实体（品种/等级/产区等）"]
    tool_results: Annotated[list[dict], "工具执行结果 [{tool, ok, summary, data}]"]
    citations: Annotated[list[dict], "引用来源 [{no, title, text}]"]
    answer: Annotated[str, "最终回答"]
    steps: Annotated[list[str], "思考轨迹：每一步做了什么（排查/解释用）"]
    degraded: Annotated[bool, "是否走了降级路径"]
    error: Annotated[str, "错误信息"]
