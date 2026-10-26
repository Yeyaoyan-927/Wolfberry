"""腾讯云 COS 实现。

桶：wolfberry-1361042049  地域：ap-shanghai
域名：wolfberry-1361042049.cos.ap-shanghai.myqcloud.com
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.errors import BizError, Err
from app.infra.storage.base import StorageProvider, StoredObject, guess_content_type

logger = logging.getLogger(__name__)

try:  # SDK 未安装时不阻断应用启动（会自动降级本地存储）
    from qcloud_cos import CosConfig, CosS3Client
except ImportError:  # pragma: no cover
    CosConfig = None  # type: ignore[assignment]
    CosS3Client = None  # type: ignore[assignment]


class CosStorage(StorageProvider):
    name = "cos"

    def __init__(self) -> None:
        if CosS3Client is None or CosConfig is None:
            raise BizError(Err.STORAGE_ERROR, "COS SDK 未安装，无法启用对象存储")
        self.bucket = settings.COS_BUCKET
        self.region = settings.COS_REGION
        self.ttl = settings.COS_SIGNED_URL_TTL
        self._client = CosS3Client(
            CosConfig(
                Region=self.region,
                SecretId=settings.COS_SECRET_ID,
                SecretKey=settings.COS_SECRET_KEY,
                Scheme=settings.COS_SCHEME,
            )
        )

    # ---------------- 写 ----------------
    def put(self, data: bytes, key: str, content_type: str | None = None) -> StoredObject:
        ctype = content_type or guess_content_type(key)
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=ctype,
                EnableMD5=False,
            )
        except Exception as exc:  # SDK 异常类型较多，统一转业务错误
            logger.error("COS 上传失败 key=%s err=%s", key, exc)
            raise BizError(Err.STORAGE_ERROR, "文件上传失败，请稍后重试", detail=str(exc)) from exc

        url, expires = self._resolve_url(key)
        return StoredObject(
            key=key,
            url=url,
            size=len(data),
            content_type=ctype,
            provider=self.name,
            expires_at=expires,
        )

    # ---------------- 读 ----------------
    def url_for(self, key: str, ttl: int | None = None) -> str:
        return self._resolve_url(key, ttl)[0]

    def _resolve_url(self, key: str, ttl: int | None = None) -> tuple[str, int | None]:
        if settings.COS_PUBLIC_READ:
            return settings.cos_public_url(key), None
        expire = ttl or self.ttl
        try:
            url = self._client.get_presigned_download_url(
                Bucket=self.bucket, Key=key, Expired=expire
            )
        except Exception as exc:
            logger.error("COS 签名失败 key=%s err=%s", key, exc)
            raise BizError(Err.STORAGE_ERROR, "获取文件地址失败", detail=str(exc)) from exc
        return url, int(datetime.now(timezone.utc).timestamp()) + expire

    def exists(self, key: str) -> bool:
        try:
            return bool(self._client.object_exists(Bucket=self.bucket, Key=key))
        except Exception as exc:
            logger.warning("COS 存在性检查失败 key=%s err=%s", key, exc)
            return False

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].get_raw_stream().read()
        except Exception as exc:
            logger.error("COS 读取失败 key=%s err=%s", key, exc)
            raise BizError(Err.STORAGE_ERROR, "读取文件失败", detail=str(exc)) from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            logger.warning("COS 删除失败 key=%s err=%s", key, exc)
