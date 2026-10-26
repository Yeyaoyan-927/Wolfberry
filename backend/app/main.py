"""应用入口：python -m app.main"""
from __future__ import annotations

import uvicorn

from app.bootstrap.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.DEBUG and not settings.is_prod,
    )
