"""本地磁盘实现：无 COS 凭据时的降级方案，接口与 COS 完全一致。"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.errors import BizError, Err
from app.infra.storage.base import StorageProvider, StoredObject, guess_content_type


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: str | Path | None = None, public_base: str = "") -> None:
        self.root = Path(root or settings.STORAGE_LOCAL_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base = public_base.rstrip("/")

    def _path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if not str(target).startswith(str(self.root)):
            raise BizError(Err.PARAM_INVALID, "非法的文件路径")
        return target

    def put(self, data: bytes, key: str, content_type: str | None = None) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            key=key,
            url=self.url_for(key),
            size=len(data),
            content_type=content_type or guess_content_type(key),
            provider=self.name,
        )

    def url_for(self, key: str, ttl: int | None = None) -> str:
        return f"{self.public_base}/files/{key}"

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise BizError(Err.NOT_FOUND, "文件不存在")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()
