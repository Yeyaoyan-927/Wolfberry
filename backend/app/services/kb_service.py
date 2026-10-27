"""知识库服务：上传 -> 解析 -> 试切分 -> 向量化 -> 入库 -> 重切 -> 删除。

链路默认同步（单篇标准文档秒级完成）。切分参数（策略 / 块长 / 重叠）
随文档持久化，便于复现问题与按需重切。
"""
from __future__ import annotations

import datetime as dt
import logging
import random
import string

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError, Err
from app.models.kb import DOC_FAILED, DOC_INDEXED, DOC_PARSING, KbChunk, KbDocument
from app.rag.embedding import embed_with_fallback
from app.rag.parser import parse
from app.rag.splitter import Chunk, chunk_report, split
from app.repositories.kb import KbRepo
from app.services.upload_service import save_document

logger = logging.getLogger(__name__)


def _new_doc_no() -> str:
    token = "".join(random.choices(string.digits, k=4))
    return f"KB{dt.date.today():%Y%m%d}{token}"


def preview_chunks(
    *,
    filename: str,
    data: bytes,
    doc_type: str = "other",
    chunk_strategy: str = "auto",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    max_chunks: int = 200,
) -> dict:
    """试切分：只解析+切分+统计，不落库、不向量化。

    运营在入库前用这个看参数效果（切片长度分布、章节路径是否保留），
    确认后再真正上传，避免切坏了要删除重建。
    """
    if len(data) > settings.RAG_MAX_DOC_MB * 1024 * 1024:
        raise BizError(Err.PARAM_INVALID, f"文件超过 {settings.RAG_MAX_DOC_MB}MB 限制")

    parsed = parse(filename, data)
    size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = chunk_size and chunk_overlap if chunk_overlap is not None else settings.RAG_CHUNK_OVERLAP

    chunks, strategy = split(
        parsed.text,
        strategy=chunk_strategy,
        size=size,
        overlap=overlap,
        doc_type=doc_type,
    )
    report = chunk_report(chunks, size)

    return {
        "file_name": filename,
        "strategy": strategy,
        "requested_strategy": chunk_strategy,
        "chunk_size": size,
        "chunk_overlap": overlap,
        "parser": parsed.meta.get("parser", "") if hasattr(parsed, "meta") else "",
        "total_chars": len(parsed.text),
        "chunk_count": len(chunks),
        "report": report,
        "chunks": [
            {
                "no": c.index,
                "section_path": c.section_path,
                "context": c.context,
                "char_count": c.char_count,
                "text": c.text[:800] + ("…" if c.char_count > 800 else ""),
            }
            for c in chunks[:max_chunks]
        ],
        "truncated": len(chunks) > max_chunks,
    }


def create_document(
    session: Session,
    *,
    filename: str,
    data: bytes,
    content_type: str,
    title: str | None = None,
    doc_type: str = "other",
    chunk_strategy: str = "auto",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
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
        chunk_size=chunk_size or settings.RAG_CHUNK_SIZE,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.RAG_CHUNK_OVERLAP,
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
        size=doc.chunk_size or settings.RAG_CHUNK_SIZE,
        overlap=doc.chunk_overlap if doc.chunk_overlap is not None else settings.RAG_CHUNK_OVERLAP,
        doc_type=doc.doc_type,
    )
    if not chunks:
        raise BizError(Err.DOC_PARSE_FAILED, "切分后没有有效内容")

    vectors, provider = embed_with_fallback([c.text for c in chunks])
    if len(vectors) != len(chunks):
        raise BizError(Err.RAG_DEGRADED, "向量化结果数量与切片不匹配")

    # 重切/重入库要先清掉旧切片及其向量，否则会残留旧版本内容
    from app.rag import vector_store

    vector_store.delete_doc(doc.id)
    repo.clear_chunks(doc.id)

    chunk_rows = [
        KbChunk(
            doc_id=doc.id,
            chunk_no=chunk.index,
            section_path=chunk.section_path[:255],
            content=chunk.text,
            char_count=len(chunk.text),
            embedding=_dumps(vectors[i]),
            embedding_provider=provider,
            embedding_dim=len(vectors[i]),
            meta={
                "strategy": strategy,
                "context": chunk.context[:500],
                "level": chunk.level,
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    repo.bulk_add_chunks(chunk_rows)
    # 实际使用的策略回写（auto 会被解析成具体策略），同时记录切分质量
    report = chunk_report(chunks, doc.chunk_size or settings.RAG_CHUNK_SIZE)
    repo.mark_indexed(doc, chunk_count=len(chunks), char_count=len(text), strategy=strategy)
    session.flush()  # 拿到 chunk 主键，供 Chroma 以 chunk_id 作为唯一 ID

    # Chroma 主检索库（失败不阻塞入库，MySQL 向量列始终是降级数据源）
    vector_store.upsert(
        [
            {
                "chunk_id": row.id,
                "doc_id": doc.id,
                "doc_type": doc.doc_type,
                "doc_title": doc.title,
                "section_path": row.section_path,
                "context": (chunk_rows[i].meta or {}).get("context", ""),
                "content": row.content,
                "embedding": vectors[i],
            }
            for i, row in enumerate(chunk_rows)
        ]
    )

    logger.info(
        "文档入库完成 doc=%s strategy=%s size=%s overlap=%s chunks=%d provider=%s chroma=%s",
        doc.doc_no,
        strategy,
        doc.chunk_size,
        doc.chunk_overlap,
        len(chunks),
        provider,
        vector_store.available(),
    )
    return {"strategy": strategy, "chunks": len(chunks), "provider": provider, "report": report}


def _dumps(vector: list[float]) -> str:
    # 向量保留 6 位小数足以区分，同时把体积压到原来的 1/3
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


def reindex(session: Session, doc: KbDocument, text: str) -> dict:
    doc.status = DOC_PARSING
    doc.error_msg = ""
    session.flush()
    result = ingest(session, doc, text)
    return result


def rechunk(
    session: Session,
    doc: KbDocument,
    *,
    strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict:
    """用新参数重切已有文档：重新解析原始文件 → 重新切分 → 重新向量化入库。

    适用场景：发现召回效果差、切片长短不一、引用溯源信息缺失。
    原始文件从对象存储读回，保证与首次入库的输入完全一致。
    """
    from app.infra.storage import get_storage

    if not doc.object_key:
        raise BizError(Err.NOT_FOUND, "该文档没有原始文件，无法重切")

    try:
        data = get_storage().get_bytes(doc.object_key)
    except Exception as exc:  # noqa: BLE001
        raise BizError(Err.NOT_FOUND, f"读取原始文件失败：{exc}") from exc

    parsed = parse(doc.file_name or "document.txt", data)

    if strategy:
        doc.chunk_strategy = strategy
    if chunk_size:
        doc.chunk_size = chunk_size
    if chunk_overlap is not None:
        doc.chunk_overlap = chunk_overlap

    doc.status = DOC_PARSING
    doc.error_msg = ""
    session.flush()

    try:
        result = ingest(session, doc, parsed.text)
    except Exception as exc:
        logger.exception("重切失败 doc=%s", doc.doc_no)
        KbRepo(session).mark_failed(doc, str(exc))
        raise BizError(Err.DOC_PARSE_FAILED, f"重切失败：{exc}") from exc
    return result


def delete_document(session: Session, doc: KbDocument) -> None:
    """删除文档：切片、向量、原始文件一并清理。

    注意：审核/检测类记录不可删除，但知识库文档属于可运营内容，
    允许删除（否则传错一份标准就会一直污染召回结果）。
    """
    from app.infra.storage import get_storage
    from app.rag import vector_store

    vector_store.delete_doc(doc.id)
    KbRepo(session).clear_chunks(doc.id)
    if doc.object_key:
        try:
            get_storage().delete(doc.object_key)
        except Exception as exc:  # noqa: BLE001  文件缺失不应阻断删除
            logger.warning("删除原始文件失败 doc=%s: %s", doc.doc_no, exc)
    session.delete(doc)
    logger.info("文档已删除 doc=%s", doc.doc_no)
