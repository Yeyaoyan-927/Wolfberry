"""存储工厂：按配置选择实现，并在 COS 不可用时自动降级本地。

上层通过 get_storage() 获取单例，不直接 import cos/local。
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings
from app.core.errors import BizError, Err
from app.infra.storage.base import StorageProvider, StoredObject, build_key, guess_content_type
from app.infra.storage.local import LocalStorage

logger = logging.getLogger(__name__)

__all__ = [
    "StorageProvider",
    "StoredObject",
    "build_key",
    "guess_content_type",
    "get_storage",
    "storage_status",
]


@lru_cache
def get_storage() -> StorageProvider:
    driver = settings.STORAGE_DRIVER.lower()

    if driver == "local":
        logger.info("存储驱动：local（显式指定）")
        return LocalStorage()

    if driver in {"cos", "auto"} and settings.cos_ready:
        try:
            from app.infra.storage.cos import CosStorage

            provider = CosStorage()
            logger.info("存储驱动：cos bucket=%s region=%s", settings.COS_BUCKET, settings.COS_REGION)
            return provider
        except BizError as exc:
            if driver == "cos":
                raise
            logger.warning("COS 初始化失败，降级本地存储：%s", exc.message)
        except Exception as exc:  # 凭据错误等
            if driver == "cos":
                raise BizError(Err.STORAGE_ERROR, "对象存储初始化失败", detail=str(exc)) from exc
            logger.warning("COS 初始化异常，降级本地存储：%s", exc)

    logger.info("存储驱动：local（未配置 COS 凭据）")
    return LocalStorage()


def storage_status() -> dict:
    provider = get_storage()
    return {
        "driver": provider.name,
        "bucket": settings.COS_BUCKET if provider.name == "cos" else None,
        "region": settings.COS_REGION if provider.name == "cos" else None,
        "domain": settings.COS_DOMAIN if provider.name == "cos" else None,
        "public_read": settings.COS_PUBLIC_READ if provider.name == "cos" else False,
    }
