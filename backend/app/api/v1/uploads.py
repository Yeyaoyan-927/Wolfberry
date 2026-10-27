"""通用上传：售后举证、头像等非商品图场景。

与商品图上传分开：
    - 商品图会触发 L1 门禁 + 异步 AI 评估 + 审核链路
    - 通用上传只做格式/大小校验，落独立目录，不进入商品评估
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.encoders import jsonable_encoder

from app.api.deps import AnyUser
from app.core.errors import BizError, Err
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.services import upload_service

router = APIRouter(tags=["upload"])

ALLOWED_SCENES = {"after-sale/evidence", "user/avatar", "product/images"}
MAX_MB = 10


@router.post("/uploads")
async def upload_file(
    user: AnyUser,
    file: UploadFile = File(...),
    scene: str = Query("after-sale/evidence"),
):
    """通用图片上传（仅登录用户）。返回相对 URL，可直接用于举证/展示。"""
    trace = new_trace_id()
    if scene not in ALLOWED_SCENES:
        raise BizError(Err.PARAM_INVALID, f"scene 必须是 {sorted(ALLOWED_SCENES)} 之一")

    data = await file.read()
    if not data:
        raise BizError(Err.PARAM_INVALID, "上传内容为空")
    if len(data) > MAX_MB * 1024 * 1024:
        raise BizError(Err.PARAM_INVALID, f"图片超过 {MAX_MB}MB")

    stored, status, detail = upload_service.save_image(
        data, file.filename or "upload.jpg", file.content_type or "image/jpeg", scene=scene
    )
    return ok({
        "key": stored.key,
        "url": stored.url,
        "size": stored.size,
        "provider": stored.provider,
        "l1_status": status,
    }, trace_id=trace)
