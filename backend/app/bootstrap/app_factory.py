"""应用装配：路由、中间件、异常处理、生命周期。"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import logging as app_logging
from app.core.config import settings
from app.core.errors import BizError, Err
from app.infra.db import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    app_logging.setup_logging("DEBUG" if settings.DEBUG else "INFO")

    from app.infra.db import create_all

    create_all()
    logging.getLogger(__name__).info(
        "应用启动 env=%s storage=%s", settings.APP_ENV, _storage_driver()
    )
    yield
    engine.dispose()


def _storage_driver() -> str:
    from app.infra.storage import get_storage

    return get_storage().name


def _trace(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def trace_and_log(request: Request, call_next):
        trace = app_logging.new_trace_id()
        request.state.trace_id = trace
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logging.getLogger("app").exception(
                "未处理异常 path=%s", request.url.path, extra={"event": "unhandled"}
            )
            raise
        response.headers["X-Trace-Id"] = trace
        app_logging.log_event(
            "http_access",
            path=request.url.path,
            method=request.method,
            status=response.status_code,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def biz_handler(request: Request, exc: BizError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict(_trace(request)))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        detail = [
            {"loc": [str(x) for x in err.get("loc", [])], "msg": err.get("msg", "")}
            for err in exc.errors()
        ]
        body = BizError(Err.PARAM_INVALID, "参数校验失败", detail=detail).to_dict(_trace(request))
        return JSONResponse(status_code=400, content=body)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        if settings.DEBUG:
            raise exc
        body = BizError(Err.INTERNAL, "服务内部错误，请稍后重试").to_dict(_trace(request))
        return JSONResponse(status_code=500, content=body)


def _register_routers(app: FastAPI) -> None:
    from app.api import files
    from app.api.v1 import audit, auth, kb, orders, products, skills, system

    app.include_router(files.router)

    api = APIRouter(prefix=settings.API_PREFIX)
    for item in (auth.router, products.router, orders.router, audit.router,
                 kb.router, skills.router, system.router):
        api.include_router(item)
    app.include_router(api)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_prod else None,
    )

    # 开发环境放开跨域（Vite dev server 5173 等）；生产应由网关/同域收敛
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_prod else [],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    @app.get("/")
    def root():
        return {"app": settings.APP_NAME, "env": settings.APP_ENV, "docs": "/docs"}

    return app
