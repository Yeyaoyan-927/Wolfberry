"""结构化日志与 trace_id 贯穿。"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    tid = uuid.uuid4().hex[:16]
    trace_id_var.set(tid)
    return tid


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": trace_id_var.get(),
            "msg": record.getMessage(),
        }
        for key in ("event", "module", "latency_ms", "code", "user_id", "extra"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 访问日志交给应用自己输出，避免 uvicorn 默认格式与 JSON 混杂
    for noisy in ("uvicorn.access", "sqlalchemy.engine.Engine", "qcloud_cos", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(event: str, **fields) -> None:
    logging.getLogger("app").info(event, extra={"event": event, **fields})
