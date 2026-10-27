"""知识库文档与切片。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin

DOC_PENDING = 0
DOC_PARSING = 1
DOC_INDEXED = 2
DOC_FAILED = 3


class KbDocument(Base, TimestampMixin):
    __tablename__ = "kb_document"
    __table_args__ = (Index("idx_doc_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(16), default="other", nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), default="upload", nullable=False)

    # 原始文件在对象存储中的位置
    object_key: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(800), default="", nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[int] = mapped_column(Integer, default=DOC_PENDING, nullable=False)
    chunk_strategy: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    # 切分参数随文档持久化：重切/复现问题时要能知道当初用的什么参数
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_msg: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class KbChunk(Base, TimestampMixin):
    __tablename__ = "kb_chunk"
    __table_args__ = (
        Index("idx_chunk_doc", "doc_id", "chunk_no"),
        Index("idx_chunk_provider", "embedding_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("kb_document.id"), nullable=False)
    chunk_no: Mapped[int] = mapped_column(Integer, nullable=False)

    section_path: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 向量以 JSON 数组存储，便于跨库迁移；规模上来后可平滑换 faiss / 向量库
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    meta: Mapped[dict | None] = mapped_column("meta_json", JSON, nullable=True)
