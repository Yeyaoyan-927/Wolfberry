"""Agent 运行入口：装配 state、执行图、产出统一结构。

对外承诺：
- 任何异常都不向上抛（问答是辅助能力），失败返回 None 由调用方降级
- 返回结构：{answer, citations, intent, tools_used, steps, degraded}

stream_agent 是同一张图的流式版本：逐节点产出事件，供前端展示"思考过程"。
两个入口共用 get_app() 编译好的图，行为完全一致，不会出现"流式和同步结果不一样"。
"""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

# 节点元信息：顺序用于前端时间线排序，title 直接展示给人看
NODE_META: dict[str, tuple[str, int]] = {
    "detect_intent": ("意图识别", 1),
    "call_tools": ("工具调用", 2),
    "generate": ("汇总生成", 3),
}
NEXT_NODE = {"detect_intent": "call_tools", "call_tools": "generate"}


def _initial_state(session: Session, question: str, role: str) -> dict:
    return {
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


def run_agent(session: Session, question: str, *, role: str = "buyer") -> dict | None:
    if not settings.AGENT_ENABLED or not settings.DASHSCOPE_API_KEY:
        return None
    started = time.perf_counter()
    try:
        from app.agent.graph import get_app

        final = get_app().invoke(_initial_state(session, question, role))
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


def _node_event(name: str, out: dict, elapsed_ms: int) -> dict:
    """把节点输出压缩成前端可渲染的事件。"""
    title, order = NODE_META.get(name, (name, 99))
    detail, extra = "", {}
    if name == "detect_intent":
        ent = {k: v for k, v in (out.get("entities") or {}).items() if v}
        detail = f"意图 {out.get('intent', '')}"
        if ent:
            detail += "；实体 " + "、".join(f"{k}={v}" for k, v in ent.items())
        extra = {"intent": out.get("intent", ""), "entities": ent}
    elif name == "call_tools":
        results = out.get("tool_results") or []
        extra = {
            "tools": [
                {"tool": r.get("tool"), "ok": bool(r.get("ok")), "summary": r.get("summary", "")}
                for r in results
            ]
        }
        detail = "；".join(f"{r.get('tool')} → {r.get('summary', '')}" for r in results) or "无可执行工具"
    elif name == "generate":
        detail = f"生成 {len(out.get('answer') or '')} 字，引用 {len(out.get('citations') or [])} 条"
    return {
        "node": name, "title": title, "order": order, "status": "done",
        "elapsed_ms": elapsed_ms, "detail": detail, "extra": extra,
    }


async def stream_agent(session: Session, question: str, *, role: str = "buyer") -> AsyncIterator[dict]:
    """流式执行：产出 start / step(running|done) / done / error 事件。

    不改变图的拓扑（仍是 detect_intent → call_tools → generate 的固定 DAG），
    只是把每个节点的完成时点暴露出来，让用户看到"现在在做什么"。
    """
    if not settings.AGENT_ENABLED or not settings.DASHSCOPE_API_KEY:
        yield {"event": "error", "data": {"message": "Agent 未启用（缺少模型配置）"}}
        return

    from app.agent.graph import get_app

    started = time.perf_counter()
    state = _initial_state(session, question, role)
    yield {"event": "start", "data": {"question": question, "engine": "langgraph"}}
    yield {"event": "step", "data": {
        "node": "detect_intent", "title": "意图识别", "order": 1, "status": "running",
    }}

    last = time.perf_counter()
    final = dict(state)
    try:
        async for update in get_app().astream(state, stream_mode="updates"):
            for name, out in update.items():
                now = time.perf_counter()
                elapsed = int((now - last) * 1000)
                last = now
                if not isinstance(out, dict):
                    continue
                final.update(out)
                yield {"event": "step", "data": _node_event(name, out, elapsed)}
                nxt = NEXT_NODE.get(name)
                if nxt:
                    yield {"event": "step", "data": {
                        "node": nxt, "title": NODE_META[nxt][0],
                        "order": NODE_META[nxt][1], "status": "running",
                    }}

        total = int((time.perf_counter() - started) * 1000)
        logger.info("Agent 流式完成 intent=%s %dms", final.get("intent"), total)
        yield {"event": "done", "data": {
            "answer": final.get("answer", ""),
            "citations": final.get("citations", []),
            "intent": final.get("intent", ""),
            "tools_used": [r["tool"] for r in final.get("tool_results", []) if r.get("ok")],
            "steps": final.get("steps", []),
            "degraded": final.get("degraded", False),
            "elapsed_ms": total,
        }}
    except Exception as exc:  # 流式中途失败要显式告诉前端，不能静默断开
        logger.exception("Agent 流式执行失败")
        yield {"event": "error", "data": {"message": f"{type(exc).__name__}: {exc}"}}
