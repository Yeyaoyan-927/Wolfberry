"""检索：查询向量化 -> Chroma 向量召回（主）-> MySQL 余弦（降级）-> 关键词重排。"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.rag import vector_store
from app.rag.embedding import embed_with_fallback
from app.rag.index import Candidate, VectorIndex, _bigrams
from app.repositories.kb import KbRepo


def _rerank(cands: list[Candidate], query_text: str, top_k: int) -> list[Candidate]:
    """bigram 关键词加权重排（与原 MySQL 路径一致的 bonus 逻辑）。"""
    query_grams = _bigrams(query_text)
    if not query_grams:
        return cands[:top_k]
    for c in cands:
        overlap = len(query_grams & _bigrams(c.content))
        if overlap:
            c.score += min(0.12, 0.02 * overlap)
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:top_k]


def _search_chroma(query_vec: list[float], query_text: str, *, top_k: int,
                   min_score: float, doc_type: str | None) -> list[Candidate] | None:
    """Chroma 主路；返回 None 表示不可用（调用方降级）。"""
    if not vector_store.available():
        return None
    try:
        # 多召回一倍再重排，给关键词 bonus 留空间
        raw = vector_store.query(query_vec, top_k=top_k * 2, doc_type=doc_type)
        cands = [
            Candidate(
                chunk_id=r["chunk_id"], doc_id=r["doc_id"] or 0,
                doc_title=r["doc_title"], section_path=r["section_path"],
                content=r["content"], score=r["score"], context=r.get("context", ""),
            )
            for r in raw
        ]
        cands = [c for c in cands if c.score >= min_score]
        return _rerank(cands, query_text, top_k)
    except Exception:  # noqa: BLE001
        return None


def _search_mysql(session: Session, query_vec: list[float], query_text: str, *,
                  top_k: int, min_score: float, doc_type: str | None) -> list[Candidate]:
    rows = KbRepo(session).vector_rows(doc_type=doc_type)
    index = VectorIndex(rows, len(query_vec))
    return index.search(query_vec, query_text, top_k=top_k, min_score=min_score)


def search(
    session: Session,
    query: str,
    *,
    top_k: int | None = None,
    doc_type: str | None = None,
    min_score: float | None = None,
) -> tuple[list[Candidate], str, int]:
    """返回 (命中列表, 通道说明, 耗时毫秒)。通道：chroma | chroma+rerank | mysql-fallback。"""
    started = time.perf_counter()
    top_k = top_k or settings.RAG_TOP_K
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score

    vectors, provider = embed_with_fallback([query], text_type="query")
    query_vec = vectors[0]

    hits = _search_chroma(query_vec, query, top_k=top_k, min_score=min_score, doc_type=doc_type)
    channel = "chroma"
    if hits is None:
        hits = _search_mysql(session, query_vec, query, top_k=top_k,
                             min_score=min_score, doc_type=doc_type)
        channel = "mysql-fallback"

    elapsed = int((time.perf_counter() - started) * 1000)
    return hits, f"{channel}({provider})", elapsed
