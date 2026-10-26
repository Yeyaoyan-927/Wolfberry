"""LangGraph 编排：意图识别 → 路由 → 工具执行 → 汇总生成。

图为固定 DAG（无循环边），天然满足「禁止无限循环」的架构底线；
每个节点的动作都写入 state.steps，作为可解释的思考轨迹。
LLM 只做意图分类与文案组织，不做等级判定与价格计算（架构底线）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_TOOLS_PER_TURN = 3  # 单轮最多调用工具数

_INTENTS = ("standards", "market", "find_products", "seller_advice", "other")

_INTENT_SYSTEM = (
    "你是枸杞交易平台的意图分类器。只输出 JSON，格式："
    '{"intent": "standards|market|find_products|seller_advice|other", '
    '"variety": "", "grade": "", "origin": ""}'
    "\n意图说明：standards=分级/等级/标准/规则/能不能上架；market=行情/价格/走势/多少钱；"
    "find_products=找货/选品/推荐货源/求购；seller_advice=卖家定价建议/商品优化建议；other=其他。"
    "\n从问题中抽取品种(宁杞5号/宁杞7号/大麻叶)、等级(特优/特级/甲级/乙级)、产区(中宁/诺木洪/靖远)，抽不到留空。"
)

# 关键词兜底（LLM 不可用时的规则路由）
_KEYWORD_ROUTES: list[tuple[tuple[str, ...], str]] = [
    (("等级", "标准", "分级", "特级", "特优", "甲级", "规则", "上架", "霉变", "缺陷率"), "standards"),
    (("行情", "价格", "多少钱", "走势", "涨价", "跌价", "均价"), "market"),
    (("找", "推荐", "求购", "选", "货源", "哪家", "购买"), "find_products"),
    (("定价", "卖多少", "报价", "怎么定价", "优化", "建议"), "seller_advice"),
]

# 意图 → 工具执行计划（工具名 + 参数构造器；entities 来自意图抽取）
def _clean(v: str) -> str:
    """清洗 LLM 抽取值：'特优|特级' 之类取第一段。"""
    return (v or "").split("|")[0].strip()


def _plan(intent: str, e: dict, question: str) -> list[tuple[str, dict]]:
    variety = _clean(e.get("variety")) or "宁杞5号"
    grade = _clean(e.get("grade")) or "特级"
    origin = _clean(e.get("origin"))
    if intent == "market":
        return [("get_market_price", {"variety": variety, "grade": grade, "origin": origin}),
                ("search_products", {"variety": variety, "grade": grade, "origin": origin})]
    if intent == "find_products":
        return [("search_products", {"variety": variety, "grade": grade, "origin": origin})]
    if intent == "seller_advice":
        return [("price_suggest", {"variety": variety, "grade": grade,
                                   "origin": origin or "中宁", "spec_per_50g": 280})]
    return [("search_standards", {"query": question})]  # standards / other


class AgentState(TypedDict, total=False):
    question: Annotated[str, "用户问题"]
    role: Annotated[str, "调用者角色"]
    intent: Annotated[str, "意图"]
    entities: Annotated[dict, "抽取的实体"]
    tool_results: Annotated[list[dict], "工具结果"]
    citations: Annotated[list[dict], "引用来源"]
    answer: Annotated[str, "最终回答"]
    steps: Annotated[list[str], "思考轨迹"]
    degraded: Annotated[bool, "是否降级"]
    _session: Annotated[Any, "运行时注入的 DB 会话（非 LLM 参数）"]


def _llm(model: str):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=settings.LLM_TIMEOUT,
        max_retries=1,
    )


# ---------- 节点 1：意图识别 ----------
def detect_intent(state: AgentState) -> AgentState:
    question, steps = state["question"], list(state.get("steps", []))
    entities = {"variety": "", "grade": "", "origin": ""}

    try:
        resp = _llm(settings.AGENT_INTENT_MODEL).invoke(
            [SystemMessage(content=_INTENT_SYSTEM), HumanMessage(content=question)]
        )
        data = json.loads(re.search(r"\{.*\}", resp.content, re.S).group(0))
        intent = data.get("intent") if data.get("intent") in _INTENTS else "other"
        for k in entities:
            entities[k] = (data.get(k) or "").strip()
        steps.append(f"意图识别(LLM)：{intent} 实体={entities}")
    except Exception as exc:  # LLM 失败 → 关键词规则兜底
        intent = "other"
        for keys, route in _KEYWORD_ROUTES:
            if any(k in question for k in keys):
                intent = route
                break
        steps.append(f"意图识别(LLM失败 {type(exc).__name__}) → 关键词兜底：{intent}")

    return {**state, "intent": intent, "entities": entities, "steps": steps}


# ---------- 节点 2：执行工具 ----------
def call_tools(state: AgentState) -> AgentState:
    from app.agent.tools import build_tools

    intent, role = state["intent"], state.get("role", "buyer")
    question = state["question"]
    steps = list(state.get("steps", []))
    results: list[dict] = []
    citations: list[dict] = []

    tools = build_tools(state["_session"], role)
    plan = _plan(intent, state.get("entities", {}), question)[:MAX_TOOLS_PER_TURN]

    # 权限降级：买家问卖家建议 → 替换为标准检索
    if intent == "seller_advice" and "price_suggest" not in tools:
        plan = [("search_standards", {"query": question})]
        steps.append("权限过滤：买家角色，定价建议降级为标准检索")

    steps.append(f"路由计划：{[name for name, _ in plan]}")

    for name, args in plan:
        t = tools.get(name)
        if t is None:  # 角色无权限的工具：只记轨迹，不算执行结果
            steps.append(f"工具 {name}：跳过（权限）")
            continue
        try:
            res = t.invoke(args)
            results.append({"tool": name, **res})
            steps.append(f"工具 {name}：{res['summary']}")
            if name == "search_standards" and res.get("ok"):
                for item in res["data"]:
                    citations.append(
                        {"no": item["no"],
                         "title": f"{item['title']} {item.get('section', '')}".strip(),
                         "text": item["text"]}
                    )
        except Exception as exc:  # 单工具失败不拖垮整轮
            logger.exception("工具执行异常 %s", name)
            results.append({"tool": name, "ok": False, "summary": f"执行异常：{exc}", "data": []})
            steps.append(f"工具 {name} 异常：{exc}")

    degraded = all(not r.get("ok") for r in results) if results else True
    return {**state, "tool_results": results, "citations": citations,
            "steps": steps, "degraded": degraded}


# ---------- 节点 3：汇总生成 ----------
_GENERATE_SYSTEM = (
    "你是枸杞交易平台的智能问答助手。依据工具返回的结构化结果回答用户问题："
    "1) 只依据结果作答，不编造数据；2) 引用标准条款时必须使用数字角标格式 [1] [2]（对应结果里的 no 字段），"
    "不要写成 [文档名 条款号]；"
    "3) 涉及价格时注明样本量与统计口径；4) 结尾一句提醒：结果仅供参考，交易以人工核实为准。"
    "5) 中文，简洁分点，不超过 250 字。"
)


def _fallback_answer(state: AgentState) -> str:
    lines = ["已为您查询到以下信息（生成服务暂不可用，以下为原始结果摘要）："]
    for r in state.get("tool_results", []):
        lines.append(f"- [{r['tool']}] {r['summary']}")
        data = r.get("data")
        rows = data if isinstance(data, list) else (data or {}).get("recent", [])
        for item in rows[:3]:
            if isinstance(item, dict) and item.get("text"):
                lines.append(f"  · {str(item['text'])[:80]}…")
    lines.append("注：结果仅供参考，交易以人工核实为准。")
    return "\n".join(lines)


def generate(state: AgentState) -> AgentState:
    steps = list(state.get("steps", []))
    context = json.dumps(
        [{"tool": r["tool"], "ok": r["ok"], "summary": r["summary"], "data": r["data"]}
         for r in state.get("tool_results", [])],
        ensure_ascii=False, default=str,
    )
    try:
        resp = _llm(settings.AGENT_ANSWER_MODEL).invoke(
            [SystemMessage(content=_GENERATE_SYSTEM),
             HumanMessage(content=f"用户问题：{state['question']}\n\n工具结果：{context}")]
        )
        answer = resp.content.strip()
        steps.append("汇总生成(LLM)完成")
    except Exception as exc:
        logger.warning("生成失败，走模板拼接: %s", exc)
        answer = _fallback_answer(state)
        steps.append(f"汇总生成(LLM失败 {type(exc).__name__}) → 模板拼接")

    return {**state, "answer": answer, "steps": steps}


# ---------- 组图（模块级构建一次，节点无状态可复用） ----------
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("detect_intent", detect_intent)
    g.add_node("call_tools", call_tools)
    g.add_node("generate", generate)
    g.add_edge(START, "detect_intent")
    g.add_edge("detect_intent", "call_tools")
    g.add_edge("call_tools", "generate")
    g.add_edge("generate", END)
    return g.compile()


_app = None


def get_app():
    global _app
    if _app is None:
        _app = build_graph()
    return _app
