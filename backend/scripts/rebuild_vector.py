"""从 MySQL kb_chunk 全量重建 Chroma 向量库。

用法：python scripts/rebuild_vector.py
场景：首次启用 Chroma / 更换嵌入模型 / 数据修复。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.models.kb import KbChunk, KbDocument  # noqa: E402
from app.rag import vector_store  # noqa: E402


def main() -> None:
    setup_logging("WARNING")
    if not vector_store.available():
        print("Chroma 不可用，请先 pip install chromadb")
        sys.exit(1)

    session = SessionLocal()
    rows = session.execute(
        select(KbChunk, KbDocument.title, KbDocument.doc_type)
        .join(KbDocument, KbDocument.id == KbChunk.doc_id)
        .order_by(KbChunk.id)
    ).all()
    session.close()

    items = []
    for chunk, title, doc_type in rows:
        try:
            vec = json.loads(chunk.embedding)
        except (TypeError, ValueError):
            continue
        if not isinstance(vec, list) or not vec:
            continue
        items.append(
            {
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "doc_type": doc_type,
                "doc_title": title,
                "section_path": chunk.section_path or "",
                "content": chunk.content,
                "embedding": vec,
            }
        )

    total = vector_store.rebuild_from_rows(items)
    print(f"Chroma 重建完成：MySQL 切片 {len(rows)} 条，写入 {total} 条，库内 {vector_store.count()} 条")


if __name__ == "__main__":
    main()
