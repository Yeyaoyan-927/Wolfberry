"""向量索引与相似度计算。

当前规模（万级切片以内）直接在进程内做矩阵乘法即可；
超过后再换 faiss，调用方接口不变。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import numpy as np


@dataclass
class Candidate:
    chunk_id: int
    doc_id: int
    doc_title: str
    section_path: str
    content: str
    score: float
    context: str = ""      # 所属章节路径链（small-to-big：命中片段时一并给出上下文）


def _bigrams(text: str) -> set[str]:
    clean = re.sub(r"\s+", "", text)
    return {clean[i : i + 2] for i in range(len(clean) - 1)}


class VectorIndex:
    def __init__(self, rows: list[tuple], dim: int) -> None:
        self.dim = dim
        self.matrix, self.valid_rows = self._build(rows, dim)

    @staticmethod
    def _build(rows: list[tuple], dim: int) -> tuple[np.ndarray, list[tuple]]:
        vectors: list[list[float]] = []
        kept: list[tuple] = []
        for row in rows:
            try:
                vec = json.loads(row[4])
            except (TypeError, ValueError):
                continue
            if not isinstance(vec, list) or len(vec) != dim:
                continue
            vectors.append(vec)
            kept.append(row)
        if not vectors:
            return np.zeros((0, dim), dtype=np.float32), []
        return np.asarray(vectors, dtype=np.float32), kept

    def __len__(self) -> int:
        return len(self.valid_rows)

    def search(
        self,
        query_vec: list[float],
        query_text: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[Candidate]:
        if not self.valid_rows:
            return []

        q = np.asarray(query_vec, dtype=np.float32)
        norm = float(np.linalg.norm(q))
        if norm == 0:
            return []
        q = q / norm

        # 向量已归一化，点积即余弦相似度
        base_scores = self.matrix @ q
        query_grams = _bigrams(query_text)

        results: list[Candidate] = []
        for idx, base in enumerate(base_scores):
            row = self.valid_rows[idx]
            content = row[3] or ""
            bonus = 0.0
            if query_grams:
                overlap = len(query_grams & _bigrams(content))
                if overlap:
                    bonus = min(0.12, 0.02 * overlap)
            score = float(base) + bonus
            if score < min_score:
                continue
            results.append(
                Candidate(
                    chunk_id=row[0],
                    doc_id=row[1],
                    doc_title=row[5],
                    section_path=row[2] or "",
                    content=content,
                    score=score,
                )
            )

        results.sort(key=lambda c: c.score, reverse=True)
        return results[:top_k]
