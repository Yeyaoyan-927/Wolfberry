"""工具层基类与注册表。

约定：
    - 每个工具声明 name / description / 入参模型 / 可用角色
    - 工具体只做参数校验与结果封装，规则在 domain，数据在 service
    - 调用统一经过 registry.invoke()，便于日志、限权、后续接 LangChain
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import BizError, Err

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    session: Session
    user_id: int | None
    role: str


@dataclass
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, Any], Any]
    scope: set[str] = field(default_factory=lambda: {"public"})
    timeout_ms: int = 3000

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具重复注册：{spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        spec = self._tools.get(name)
        if spec is None:
            raise BizError(Err.NOT_FOUND, f"工具不存在：{name}")
        return spec

    def list_for(self, role: str) -> list[dict]:
        return [
            spec.to_schema()
            for spec in self._tools.values()
            if role in spec.scope or "public" in spec.scope
        ]

    def invoke(self, name: str, args: dict, ctx: ToolContext) -> dict:
        spec = self.get(name)
        if ctx.role not in spec.scope and "public" not in spec.scope:
            raise BizError(Err.FORBIDDEN, f"当前角色无权调用 {name}")

        payload = spec.args_model.model_validate(args)
        started = time.perf_counter()
        result = spec.handler(ctx, payload)
        elapsed = int((time.perf_counter() - started) * 1000)

        logger.info(
            "工具调用 tool=%s role=%s user=%s elapsed_ms=%d",
            name,
            ctx.role,
            ctx.user_id,
            elapsed,
            extra={"event": "tool_invoke", "latency_ms": elapsed},
        )

        if isinstance(result, BaseModel):
            result = result.model_dump()
        return {"tool": name, "elapsed_ms": elapsed, "data": result}


registry = ToolRegistry()
