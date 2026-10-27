"""RAG 对外服务：检索、问答、评测。"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.rag import generator, retriever
from app.schemas.kb import AskOut, Citation, SearchHit, SearchOut


def search(session: Session, query: str, *, top_k: int | None = None, doc_type: str | None = None) -> SearchOut:
    hits, provider, elapsed = retriever.search(
        session, query, top_k=top_k, doc_type=doc_type
    )
    return SearchOut(
        query=query,
        provider=provider,
        elapsed_ms=elapsed,
        hits=[
            SearchHit(
                chunk_id=h.chunk_id,
                doc_id=h.doc_id,
                doc_title=h.doc_title,
                section_path=h.section_path,
                context=h.context,
                content=h.content,
                score=round(h.score, 4),
            )
            for h in hits
        ],
    )


def ask(
    session: Session,
    question: str,
    *,
    top_k: int | None = None,
    with_llm: bool = True,
) -> AskOut:
    started = time.perf_counter()
    hits, _provider, _ = retriever.search(session, question, top_k=top_k)

    answer_text, mode, note = generator.answer(question, hits, with_llm=with_llm)

    citations = [
        Citation(
            index=i,
            doc_title=hit.doc_title,
            section_path=hit.section_path,
            snippet=hit.content.strip().replace("\n", " ")[:200],
            score=round(hit.score, 4),
        )
        for i, hit in enumerate(hits, start=1)
    ]

    return AskOut(
        question=question,
        answer=answer_text,
        citations=citations,
        mode=mode,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        note=note,
    )


def evaluate(
    session: Session,
    cases: list[dict],
    *,
    k: int | None = None,
    doc_type: str | None = None,
) -> dict:
    from app.rag.evaluator import evaluate as run_eval

    return run_eval(
        session,
        cases,
        k=k or settings.RAG_TOP_K,
        doc_type=doc_type,
        min_score=0.0,
    )
