"""向量化：DashScope（质量优先）/ 本地哈希（离线兜底）。

两种实现的向量不在同一空间，检索时按 embedding_dim 过滤，避免混算。
"""
from __future__ import annotations

import logging
import math
import re
import zlib
from abc import ABC, abstractmethod

import httpx
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class Embedder(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str], *, text_type: str = "document") -> list[list[float]]: ...


class DashScopeEmbedder(Embedder):
    name = "dashscope"

    def __init__(self) -> None:
        self.dim = settings.EMBEDDING_DIM
        self.model = settings.EMBEDDING_MODEL
        self.url = f"{settings.DASHSCOPE_BASE_URL}/services/embeddings/text-embedding/text-embedding"

    def embed(self, texts: list[str], *, text_type: str = "document") -> list[list[float]]:
        vectors: list[list[float]] = []
        batch_size = settings.EMBEDDING_BATCH
        with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                payload = {
                    "model": self.model,
                    "input": {"texts": batch},
                    "parameters": {"dimension": self.dim, "text_type": text_type},
                }
                resp = client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                items = sorted(data["output"]["embeddings"], key=lambda x: x["text_index"])
                vectors.extend([item["embedding"] for item in items])
        return vectors


class LocalHashEmbedder(Embedder):
    """字符 n-gram 哈希向量：无外网也能跑，适合中文关键词型检索。

    不是语义模型，但做条款类检索的兜底足够，且完全确定、可复现。
    """

    name = "local-hash"

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    @staticmethod
    def _grams(text: str) -> list[str]:
        clean = re.sub(r"\s+", "", text)
        grams: list[str] = []
        for n in (2, 3):
            grams.extend(clean[i : i + n] for i in range(len(clean) - n + 1))
        return grams or [clean]

    def embed(self, texts: list[str], *, text_type: str = "document") -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            counts: dict[str, int] = {}
            for gram in self._grams(text):
                counts[gram] = counts.get(gram, 0) + 1
            for gram, count in counts.items():
                idx = zlib.crc32(gram.encode("utf-8")) % self.dim
                vec[idx] += 1.0 + math.log(count)
            norm = float(np.linalg.norm(vec))
            out.append((vec / norm).tolist() if norm else vec.tolist())
        return out


def get_embedder() -> Embedder:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "local":
        return LocalHashEmbedder()
    if provider == "dashscope":
        return DashScopeEmbedder()
    return DashScopeEmbedder() if settings.llm_ready else LocalHashEmbedder()


def embed_with_fallback(texts: list[str], *, text_type: str = "document") -> tuple[list[list[float]], str]:
    """返回 (向量, 实际使用的 provider)。远程失败自动降级本地，保证入库不中断。"""
    primary = get_embedder()
    try:
        return primary.embed(texts, text_type=text_type), primary.name
    except Exception as exc:
        if primary.name == "local-hash":
            raise
        logger.warning("向量化服务不可用，降级本地哈希：%s", exc)
        fallback = LocalHashEmbedder()
        return fallback.embed(texts, text_type=text_type), fallback.name
