"""统一响应与分页。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Resp(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    trace_id: str = ""


class PageMeta(BaseModel):
    total: int = 0
    page: int = 1
    size: int = 20


class PageQuery(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PageData(BaseModel, Generic[T]):
    items: list[T] = []
    total: int = 0
    page: int = 1
    size: int = 20


def ok(data: Any = None, message: str = "ok", trace_id: str = "") -> dict:
    return {"code": 0, "message": message, "data": data, "trace_id": trace_id}
