"""检索效果评估：Recall@K 与 MRR。

评测集格式（JSON）：
    [{"question": "...", "expected": ["GB/T 18672", "分级"]}]
expected 为文档标题的匹配片段，命中任意一个即算该问题检索正确。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.rag.retriever import search


def _match(title: str, expected: list[str]) -> bool:
    return any(token and token in title for token in expected)


def evaluate(
    session: Session,
    cases: list[dict],
    *,
    k: int = 5,
    doc_type: str | None = None,
    min_score: float = 0.0,
) -> dict:
    details: list[dict] = []
    hits = 0
    rr_sum = 0.0
    provider = ""

    for case in cases:
        question = case["question"]
        expected = case.get("expected", [])
        results, provider, _ = search(
            session, question, top_k=k, doc_type=doc_type, min_score=min_score
        )
        rank: int | None = None
        for i, hit in enumerate(results, start=1):
            if _match(hit.doc_title, expected):
                rank = i
                break

        if rank:
            hits += 1
            rr_sum += 1.0 / rank

        details.append(
            {
                "question": question,
                "expected_docs": expected,
                "hit": rank is not None,
                "first_hit_rank": rank,
                "top_score": round(results[0].score, 4) if results else 0.0,
            }
        )

    total = len(cases) or 1
    return {
        "total": len(cases),
        "recall_at_k": round(hits / total, 4),
        "mrr": round(rr_sum / total, 4),
        "k": k,
        "provider": provider,
        "cases": details,
    }
