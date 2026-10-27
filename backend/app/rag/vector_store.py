"""Chroma 向量库（嵌入式持久化模式）。

定位：kb_chunk 向量检索的主存储；MySQL 中的 embedding JSON 列保留，
作为 Chroma 不可用时的降级数据源与重建来源。

- 持久化目录：backend/var/chroma（配置 CHROMA_DIR 可改）
- 距离度量：cosine（collection 级声明）；对外统一输出「相似度 = 1 - distance」
- 线程安全：PersistentClient 写操作用进程内锁串行
- 不可用时上层自动降级，不阻塞业务
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_COLLECTION = "kb_chunks"
_lock = threading.Lock()
_client = None
_collection = None
_init_error: str | None = None


def _get_collection():
    """懒加载单例；失败返回 None（上层降级）。"""
    global _client, _collection, _init_error
    if _collection is not None:
        return _collection
    if _init_error is not None:
        return None
    try:
        import chromadb

        path = Path(settings.CHROMA_DIR)
        path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(path))
        _collection = _client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Chroma 就绪 path=%s count=%d", path, _collection.count())
        return _collection
    except Exception as exc:  # noqa: BLE001
        _init_error = str(exc)
        logger.warning("Chroma 初始化失败，检索将降级 MySQL：%.120s", exc)
        return None


def available() -> bool:
    return _get_collection() is not None


def count() -> int:
    col = _get_collection()
    return col.count() if col else 0


def upsert(items: list[dict]) -> int:
    """写入/更新切片向量。

    items: [{chunk_id, doc_id, doc_type, doc_title, section_path, content, embedding}]
    """
    col = _get_collection()
    if not col or not items:
        return 0
    with _lock:
        col.upsert(
            ids=[str(it["chunk_id"]) for it in items],
            embeddings=[it["embedding"] for it in items],
            documents=[it["content"] for it in items],
            metadatas=[
                {
                    "doc_id": it["doc_id"],
                    "doc_type": it.get("doc_type") or "",
                    "doc_title": it.get("doc_title") or "",
                    "section_path": it.get("section_path") or "",
                    "context": it.get("context") or "",
                }
                for it in items
            ],
        )
    return len(items)


def delete_doc(doc_id: int) -> None:
    col = _get_collection()
    if col:
        with _lock:
            col.delete(where={"doc_id": doc_id})


def query(embedding: list[float], *, top_k: int = 5, doc_type: str | None = None) -> list[dict]:
    """向量检索，返回 [{chunk_id, doc_id, doc_title, section_path, content, score}]。

    score = 1 - cosine_distance（越高越相似）。
    """
    col = _get_collection()
    if not col or col.count() == 0:
        return []
    where = {"doc_type": doc_type} if doc_type else None
    res = col.query(
        query_embeddings=[embedding],
        n_results=min(top_k, col.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    ids = res["ids"][0]
    for i, cid in enumerate(ids):
        out.append(
            {
                "chunk_id": int(cid),
                "doc_id": res["metadatas"][0][i].get("doc_id"),
                "doc_title": res["metadatas"][0][i].get("doc_title", ""),
                "section_path": res["metadatas"][0][i].get("section_path", ""),
                "context": res["metadatas"][0][i].get("context", ""),
                "content": res["documents"][0][i],
                "score": 1.0 - float(res["distances"][0][i]),
            }
        )
    return out


def rebuild_from_rows(rows: list[dict]) -> int:
    """全量重建（从 MySQL kb_chunk 行）：删集合重建，规避 chromadb 空 where 限制。"""
    global _collection
    col = _get_collection()
    if not col:
        return 0
    with _lock:
        _client.delete_collection(_COLLECTION)
        _collection = _client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"}
        )
    # 分批写入，单批 ≤ 2k（Chroma 单批上限）
    step = 2000
    total = 0
    for i in range(0, len(rows), step):
        total += upsert(rows[i : i + step])
    return total
