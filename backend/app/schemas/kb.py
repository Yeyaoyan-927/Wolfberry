"""知识库与 RAG DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DocOut(BaseModel):
    id: int
    doc_no: str
    title: str
    doc_type: str
    file_name: str
    url: str
    size: int
    status: int
    chunk_strategy: str
    chunk_count: int
    char_count: int
    error_msg: str = ""

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: int
    chunk_no: int
    section_path: str
    content: str
    char_count: int
    embedding_provider: str
    embedding_dim: int

    model_config = {"from_attributes": True}


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    top_k: int = Field(5, ge=1, le=20)
    doc_type: str | None = None


class SearchHit(BaseModel):
    chunk_id: int
    doc_id: int
    doc_title: str
    section_path: str
    content: str
    score: float


class SearchOut(BaseModel):
    query: str
    hits: list[SearchHit]
    provider: str
    elapsed_ms: int


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    top_k: int = Field(5, ge=1, le=20)
    with_llm: bool = True


class Citation(BaseModel):
    index: int
    doc_title: str
    section_path: str
    snippet: str
    score: float


class AskOut(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    mode: str  # llm | extractive
    elapsed_ms: int
    note: str = ""


class EvalCaseOut(BaseModel):
    question: str
    expected_docs: list[str]
    hit: bool
    first_hit_rank: int | None
    top_score: float


class EvalReport(BaseModel):
    total: int
    recall_at_k: float
    mrr: float
    k: int
    provider: str
    cases: list[EvalCaseOut]
