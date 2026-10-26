"""存储抽象：上层只依赖该接口，不感知 COS / 本地磁盘差异。"""
from __future__ import annotations

import mimetypes
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def guess_content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"


def build_key(prefix: str, filename: str, *, keep_name: bool = True) -> str:
    """生成对象键：prefix/YYYYMM/uuid-name.ext

    保留原文件名便于排查，但做字符清洗，避免路径穿越与中文编码问题。
    """
    safe = _SAFE.sub("_", PurePosixPath(filename).name).strip("._") or "file"
    if not keep_name:
        safe = "object"
    month = datetime.now(timezone.utc).strftime("%Y%m")
    token = uuid.uuid4().hex[:12]
    return f"{prefix.strip('/')}/{month}/{token}-{safe}"[:512]


@dataclass(frozen=True)
class StoredObject:
    key: str
    url: str
    size: int
    content_type: str
    provider: str
    expires_at: int | None = None  # 签名 URL 的过期时间戳，公开读时为 None


class StorageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def put(self, data: bytes, key: str, content_type: str | None = None) -> StoredObject: ...

    @abstractmethod
    def url_for(self, key: str, ttl: int | None = None) -> str: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...
