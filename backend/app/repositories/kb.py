"""知识库数据访问。"""
from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import delete, func, select

from app.models.kb import KbChunk, KbDocument
from app.repositories.base import BaseRepo


class KbRepo(BaseRepo[KbDocument]):
    model = KbDocument

    # ---------------- 文档 ----------------
    def by_no(self, doc_no: str) -> KbDocument | None:
        return self.session.scalar(select(KbDocument).where(KbDocument.doc_no == doc_no))

    def list_docs(
        self,
        *,
        doc_type: str | None = None,
        status: int | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[KbDocument], int]:
        conds = []
        if doc_type:
            conds.append(KbDocument.doc_type == doc_type)
        if status is not None:
            conds.append(KbDocument.status == status)
        if keyword:
            conds.append(KbDocument.title.like(f"%{keyword}%"))

        total = int(
            self.session.scalar(select(func.count()).select_from(KbDocument).where(*conds)) or 0
        )
        rows = self.session.scalars(
            select(KbDocument)
            .where(*conds)
            .order_by(KbDocument.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return rows, total

    def mark_indexed(
        self, doc: KbDocument, *, chunk_count: int, char_count: int, strategy: str | None = None
    ) -> None:
        doc.status = 2
        doc.chunk_count = chunk_count
        doc.char_count = char_count
        # auto 策略会被解析成具体策略（md/clause/qa/recursive），回写便于运营判断
        if strategy:
            doc.chunk_strategy = strategy
        doc.error_msg = ""
        doc.indexed_at = dt.datetime.now()
        self.session.flush()

    def mark_failed(self, doc: KbDocument, reason: str) -> None:
        doc.status = 3
        doc.error_msg = reason[:500]
        self.session.flush()

    # ---------------- 切片 ----------------
    def clear_chunks(self, doc_id: int) -> None:
        self.session.execute(delete(KbChunk).where(KbChunk.doc_id == doc_id))

    def bulk_add_chunks(self, rows: list[KbChunk]) -> None:
        self.session.add_all(rows)
        self.session.flush()

    def chunks_of(self, doc_id: int, *, offset: int = 0, limit: int = 50) -> Sequence[KbChunk]:
        return self.session.scalars(
            select(KbChunk)
            .where(KbChunk.doc_id == doc_id)
            .order_by(KbChunk.chunk_no)
            .offset(offset)
            .limit(limit)
        ).all()

    def count_chunks(self, doc_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(KbChunk).where(KbChunk.doc_id == doc_id)
            )
            or 0
        )

    def vector_rows(self, *, doc_type: str | None = None) -> list[tuple]:
        """取召回所需的最小列集，避免 SELECT * 把大字段全捞出来。"""
        stmt = (
            select(
                KbChunk.id,
                KbChunk.doc_id,
                KbChunk.section_path,
                KbChunk.content,
                KbChunk.embedding,
                KbDocument.title,
                KbDocument.doc_type,
            )
            .join(KbDocument, KbDocument.id == KbChunk.doc_id)
            .where(KbDocument.status == 2)
        )
        if doc_type:
            stmt = stmt.where(KbDocument.doc_type == doc_type)
        return list(self.session.execute(stmt).all())
