"""Agent 运行入口：装配 state、执行图、产出统一结构。

对外承诺：
- 任何异常都不向上抛（问答是辅助能力），失败返回 None 由调用方降级
- 返回结构：{answer, citations, intent, tools_used, steps, degraded}
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


def run_agent(session: Session, question: str, *, role: str = "buyer") -> dict | None:
    if not settings.AGENT_ENABLED or not settings.DASHSCOPE_API_KEY:
        return None
    started = time.perf_counter()
    try:
        from app.agent.graph import get_app

        final = get_app().invoke(
            {
                "question": question,
                "role": role,
                "intent": "",
                "entities": {},
                "tool_results": [],
                "citations": [],
                "answer": "",
                "steps": [],
                "degraded": False,
                "_session": session,  # 请求级 session，工具复用以复用事务与缓存
            }
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Agent 完成 intent=%s tools=%s degraded=%s %dms",
            final["intent"],
            [r["tool"] for r in final.get("tool_results", [])],
            final.get("degraded"),
            elapsed,
        )
        return {
            "answer": final["answer"],
            "citations": final.get("citations", []),
            "intent": final["intent"],
            "tools_used": [r["tool"] for r in final.get("tool_results", []) if r.get("ok")],
            "steps": final.get("steps", []),
            "degraded": final.get("degraded", False),
            "elapsed_ms": elapsed,
        }
    except Exception:
        logger.exception("Agent 执行失败，降级管线")
        return None
