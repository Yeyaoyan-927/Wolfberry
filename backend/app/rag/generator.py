"""答案生成：有 LLM 走生成，无 LLM 走抽取式兜底。

两条路径都强制带引用，不允许无据作答。
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.rag.index import Candidate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是枸杞交易平台的知识助手。规则：\n"
    "1. 只能依据「资料」回答，不得使用资料之外的知识补充具体数值或条款；\n"
    "2. 每条结论后面必须标注引用编号，如 [1]、[2]；\n"
    "3. 资料没有覆盖的内容，直接回答「知识库中未收录」，并建议咨询平台客服或送第三方检测；\n"
    "4. 不要输出「合格/不合格/达标」等法定判定用语，只能给参考性表述；\n"
    "5. 回答控制在 300 字以内，先给结论，再给依据。"
)


def build_context(hits: list[Candidate]) -> str:
    blocks = []
    for i, hit in enumerate(hits, start=1):
        section = f" · {hit.section_path}" if hit.section_path else ""
        blocks.append(f"[{i}]《{hit.doc_title}》{section}\n{hit.content.strip()}")
    return "\n\n".join(blocks)


def _call_llm(question: str, hits: list[Candidate]) -> str:
    url = f"{settings.DASHSCOPE_BASE_URL}/services/aigc/text-generation/generation"
    payload = {
        "model": settings.LLM_MODEL,
        "input": {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"资料：\n{build_context(hits)}\n\n问题：{question}",
                },
            ]
        },
        "parameters": {
            "result_format": "message",
            "max_tokens": settings.LLM_MAX_TOKENS,
            "temperature": 0.2,
        },
    }
    with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["output"]["choices"][0]["message"]["content"].strip()


def _extractive(question: str, hits: list[Candidate]) -> str:
    if not hits:
        return (
            "知识库中未收录与这个问题相关的内容。"
            "建议换一种问法，或联系平台客服确认。"
        )
    lines = ["知识库中检索到的相关原文如下（未配置大模型，直接返回片段）："]
    for i, hit in enumerate(hits[:3], start=1):
        section = f"·{hit.section_path}" if hit.section_path else ""
        snippet = hit.content.strip().replace("\n", " ")[:220]
        lines.append(f"[{i}]《{hit.doc_title}》{section}：{snippet}")
    return "\n".join(lines)


def answer(
    question: str,
    hits: list[Candidate],
    *,
    with_llm: bool = True,
) -> tuple[str, str, str]:
    """返回 (答案, 模式, 附加说明)。"""
    if not hits:
        return _extractive(question, hits), "extractive", "未检索到相关资料"

    if with_llm and settings.llm_ready:
        try:
            return _call_llm(question, hits), "llm", ""
        except Exception as exc:
            logger.warning("LLM 调用失败，降级抽取式：%s", exc)
            return (
                _extractive(question, hits),
                "extractive",
                "大模型服务暂不可用，已返回检索到的原文片段",
            )

    note = "" if settings.llm_ready else "未配置大模型 API Key，使用抽取式回答"
    return _extractive(question, hits), "extractive", note
