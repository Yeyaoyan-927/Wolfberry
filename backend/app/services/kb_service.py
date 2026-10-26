"""知识库服务：上传 -> 解析 -> 切分 -> 向量化 -> 入库。

整条链路是同步的：单篇标准文档通常几百 KB，秒级完成；
后续文档量上来后可把 ingest 移到后台队列，接口不变。
"""
from __future__ import annotations

import datetime as dt
import logging
import random
import string

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError, Err
from app.models.kb import DOC_PARSING, KbChunk, KbDocument
from app.rag.embedding import embed_with_fallback
from app.rag.parser import parse
from app.rag.splitter import split
from app.repositories.kb import KbRepo
from app.services.upload_service import save_document

logger = logging.getLogger(__name__)


def _new_doc_no() -> str:
    token = "".join(random.choices(string.digits, k=4))
    return f"KB{dt.date.today():%Y%m%d}{token}"


def create_document(
    session: Session,
    *,
    filename: str,
    data: bytes,
    content_type: str,
    title: str | None = None,
    doc_type: str = "other",
    chunk_strategy: str = "auto",
    user_id: int | None = None,
) -> KbDocument:
    parsed = parse(filename, data)  # 解析失败直接抛错，不产生垃圾文件
    stored = save_document(data, filename, content_type)

    repo = KbRepo(session)
    doc = KbDocument(
        doc_no=_new_doc_no(),
        title=(title or filename).strip()[:255],
        doc_type=doc_type,
        source_type="upload",
        object_key=stored.key,
        url=stored.url,
        file_name=filename,
        content_type=stored.content_type,
        size=stored.size,
        status=DOC_PARSING,
        chunk_strategy=chunk_strategy,
        created_by=user_id,
    )
    repo.add(doc)

    try:
        ingest(session, doc, parsed.text)
    except Exception as exc:  # 入库失败要留痕，不能静默
        logger.exception("文档入库失败 doc=%s", doc.doc_no)
        repo.mark_failed(doc, str(exc))
    return doc


def ingest(session: Session, doc: KbDocument, text: str) -> dict:
    repo = KbRepo(session)

    chunks, strategy = split(
        text,
        strategy=doc.chunk_strategy,
        size=settings.RAG_CHUNK_SIZE,
        overlap=settings.RAG_CHUNK_OVERLAP,
        doc_type=doc.doc_type,
    )
    if not chunks:
        raise BizError(Err.DOC_PARSE_FAILED, "切分后没有有效内容")

    vectors, provider = embed_with_fallback([c.text for c in chunks])
    if len(vectors) != len(chunks):
        raise BizError(Err.RAG_DEGRADED, "向量化结果数量与切片不匹配")

    repo.clear_chunks(doc.id)
    repo.bulk_add_chunks(
        [
            KbChunk(
                doc_id=doc.id,
                chunk_no=chunk.index,
                section_path=chunk.section_path[:255],
                content=chunk.text,
                char_count=len(chunk.text),
                embedding=_dumps(vectors[i]),
                embedding_provider=provider,
                embedding_dim=len(vectors[i]),
                meta={"strategy": strategy},
            )
            for i, chunk in enumerate(chunks)
        ]
    )
    repo.mark_indexed(doc, chunk_count=len(chunks), char_count=len(text))

    logger.info(
        "文档入库完成 doc=%s strategy=%s chunks=%d provider=%s",
        doc.doc_no,
        strategy,
        len(chunks),
        provider,
    )
    return {"strategy": strategy, "chunks": len(chunks), "provider": provider}


def _dumps(vector: list[float]) -> str:
    # 向量保留 6 位小数足以区分，同时把体积压到原来的 1/3
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


def reindex(session: Session, doc: KbDocument, text: str) -> dict:
    doc.status = DOC_PARSING
    doc.error_msg = ""
    session.flush()
    result = ingest(session, doc, text)
    return result
