"""数据库引擎与会话管理。"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：请求级会话，异常回滚。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all() -> None:
    """开发期建表。生产用 alembic 迁移。"""
    from app import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(bind=engine)
