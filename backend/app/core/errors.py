"""统一错误码与业务异常。

错误码规则：模块(2位) + 序号(3位)
    10 通用 / 20 鉴权 / 30 存储与文档 / 40 商品 / 50 智能体
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any


class Err(IntEnum):
    OK = 0

    PARAM_INVALID = 40001
    UNAUTHORIZED = 40101
    TOKEN_EXPIRED = 40102
    FORBIDDEN = 40301
    NOT_FOUND = 40401
    CONFLICT = 40901
    RATE_LIMITED = 42901

    INTERNAL = 50001
    STORAGE_ERROR = 50201
    LLM_UNAVAILABLE = 50301
    RAG_DEGRADED = 50302

    SELLER_NOT_VERIFIED = 60001
    PRODUCT_OFF_SHELF = 61001
    OUT_OF_STOCK = 61002

    ORDER_NOT_ALLOWED = 63001      # 当前状态不允许该操作
    PAY_REGISTERED = 63002         # 凭证已登记，勿重复提交

    DOC_PARSE_FAILED = 62001
    DOC_TOO_LARGE = 62002
    DOC_UNSUPPORTED = 62003


_HTTP_STATUS: dict[Err, int] = {
    Err.OK: 200,
    Err.PARAM_INVALID: 400,
    Err.UNAUTHORIZED: 401,
    Err.TOKEN_EXPIRED: 401,
    Err.FORBIDDEN: 403,
    Err.NOT_FOUND: 404,
    Err.CONFLICT: 409,
    Err.RATE_LIMITED: 429,
    Err.INTERNAL: 500,
    Err.STORAGE_ERROR: 502,
    Err.LLM_UNAVAILABLE: 503,
    Err.RAG_DEGRADED: 503,
    Err.SELLER_NOT_VERIFIED: 400,
    Err.PRODUCT_OFF_SHELF: 400,
    Err.OUT_OF_STOCK: 400,
    Err.ORDER_NOT_ALLOWED: 409,
    Err.PAY_REGISTERED: 409,
    Err.DOC_PARSE_FAILED: 422,
    Err.DOC_TOO_LARGE: 413,
    Err.DOC_UNSUPPORTED: 415,
}


class BizError(Exception):
    """业务异常。message 面向用户，可安全展示。"""

    def __init__(
        self,
        code: Err,
        message: str,
        *,
        detail: Any = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.http_status = http_status or _HTTP_STATUS.get(code, 400)

    def to_dict(self, trace_id: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": int(self.code),
            "message": self.message,
            "data": None,
            "trace_id": trace_id,
        }
        if self.detail is not None:
            body["detail"] = self.detail
        return body
