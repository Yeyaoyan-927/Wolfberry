"""根级文件路由：本地存储的文件服务；COS 私有桶时 302 到签名 URL。

注意：该路由挂在应用根路径（/files/**），不走 /api/v1 前缀，
这样 LocalStorage.url_for() 生成的链接无需感知 API 前缀。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

from app.core.errors import BizError, Err
from app.infra.storage import get_storage

router = APIRouter(tags=["files"])


@router.get("/files/{key:path}")
def serve_file(key: str):
    provider = get_storage()
    if not provider.exists(key):
        raise BizError(Err.NOT_FOUND, "文件不存在")

    if provider.name == "cos":
        return RedirectResponse(provider.url_for(key), status_code=302)

    root = Path(get_storage().root)  # type: ignore[attr-defined]
    target = (root / key).resolve()
    if not str(target).startswith(str(root)):
        raise BizError(Err.PARAM_INVALID, "非法路径")
    return FileResponse(target)
