"""数据访问基类：只做查询与持久化，不含业务规则。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.db import Base

M = TypeVar("M", bound=Base)


class BaseRepo(Generic[M]):
    model: type[M]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, pk: int) -> M | None:
        return self.session.get(self.model, pk)

    def add(self, obj: M) -> M:
        self.session.add(obj)
        self.session.flush()
        return obj

    def delete(self, obj: M) -> None:
        self.session.delete(obj)

    def count(self, *where: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if where:
            stmt = stmt.where(*where)
        return int(self.session.scalar(stmt) or 0)
