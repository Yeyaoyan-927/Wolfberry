"""检索：查询向量化 -> 向量召回 -> 阈值过滤。"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.rag.embedding import embed_with_fallback
from app.rag.index import Candidate, VectorIndex
from app.repositories.kb import KbRepo


def search(
    session: Session,
    query: str,
    *,
    top_k: int | None = None,
    doc_type: str | None = None,
    min_score: float | None = None,
) -> tuple[list[Candidate], str, int]:
    """返回 (命中列表, 向量提供方, 耗时毫秒)。"""
    started = time.perf_counter()
    top_k = top_k or settings.RAG_TOP_K
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score

    vectors, provider = embed_with_fallback([query], text_type="query")
    query_vec = vectors[0]
    dim = len(query_vec)

    rows = KbRepo(session).vector_rows(doc_type=doc_type)
    index = VectorIndex(rows, dim)  # 只接受同维度向量，避免不同 provider 混算
    hits = index.search(query_vec, query, top_k=top_k, min_score=min_score)

    elapsed = int((time.perf_counter() - started) * 1000)
    return hits, provider, elapsed
