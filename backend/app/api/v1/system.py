"""健康检查：部署探针用。"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.infra.storage import storage_status
from app.rag.embedding import get_embedder
from app.schemas.common import ok

router = APIRouter(tags=["system"])


@router.get("/health")
def health(session: DbSession):
    db_ok = True
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    embedder = get_embedder()
    return ok(
        {
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
            "db": "up" if db_ok else "down",
            "storage": storage_status(),
            "llm": "ready" if settings.llm_ready else "not-configured",
            "embedding": {"provider": embedder.name, "dim": embedder.dim},
        }
    )
