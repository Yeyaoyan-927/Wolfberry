"""文件上传：图片与文档。

职责边界：
    - 只负责校验、生成对象键、写入存储、返回公开信息
    - 不写商品/文档表（那是 service 的事）
"""
from __future__ import annotations

import io
import logging
import struct
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.config import settings
from app.core.errors import BizError, Err
from app.infra.storage import build_key, get_storage

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOC_EXT = {".pdf", ".docx", ".md", ".txt", ".markdown"}
MAX_IMAGE_MB = 10
MIN_SHORT_SIDE = 800


@dataclass
class ImageMeta:
    width: int
    height: int
    fmt: str


def _png_size(data: bytes) -> ImageMeta | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
        return None
    width, height = struct.unpack(">II", data[16:24])
    return ImageMeta(width=width, height=height, fmt="png")


def _jpeg_size(data: bytes) -> ImageMeta | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    stream = io.BytesIO(data)
    stream.seek(2)
    while True:
        marker = stream.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            return None
        code = marker[1]
        if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            stream.read(3)  # 长度 + 精度
            height, width = struct.unpack(">HH", stream.read(4))
            return ImageMeta(width=width, height=height, fmt="jpeg")
        if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
            continue
        raw_len = stream.read(2)
        if len(raw_len) < 2:
            return None
        length = struct.unpack(">H", raw_len)[0]
        stream.seek(length - 2, io.SEEK_CUR)


def image_meta(data: bytes) -> ImageMeta | None:
    return _png_size(data) or _jpeg_size(data)


def l1_check(data: bytes, filename: str) -> tuple[int, dict]:
    """上传前置校验。返回 (1 通过 / 2 不通过, 明细)。

    只做能确定性判断的检查：格式、大小、分辨率。
    模糊度与遮挡需要模型，放到后续环节。
    """
    ext = PurePosixPath(filename).suffix.lower()
    detail: dict = {"ext": ext, "size": len(data)}

    if ext not in ALLOWED_IMAGE_EXT:
        detail["reason"] = f"不支持的格式 {ext}，请上传 jpg / png / webp"
        return 2, detail

    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        detail["reason"] = f"图片超过 {MAX_IMAGE_MB}MB，请压缩后上传"
        return 2, detail

    meta = image_meta(data)
    if meta is None:
        detail["reason"] = "无法识别图片尺寸，文件可能损坏"
        return 2, detail

    short_side = min(meta.width, meta.height)
    detail.update({"width": meta.width, "height": meta.height, "short_side": short_side})

    if short_side < MIN_SHORT_SIDE:
        detail["reason"] = f"短边 {short_side}px 低于 {MIN_SHORT_SIDE}px，请用原图上传"
        return 2, detail

    return 1, detail


def save_image(data: bytes, filename: str, content_type: str = "",
               scene: str = "product/images") -> tuple[object, int, dict]:
    """保存图片，返回 (StoredObject, l1_status, l1_detail)。

    scene 决定存储前缀：商品图 product/images、售后举证 after-sale/evidence 等，
    便于按场景做生命周期管理与权限控制。
    """
    status, detail = l1_check(data, filename)
    if status != 1:
        # 校验不通过直接拦截，不落盘，避免占存储
        raise BizError(Err.PARAM_INVALID, detail.get("reason", "图片校验未通过"), detail=detail)

    key = build_key(scene, filename)
    stored = get_storage().put(data, key, content_type or None)
    logger.info("图片已上传 key=%s provider=%s size=%d scene=%s", stored.key, stored.provider, stored.size, scene)
    return stored, status, detail


def save_document(data: bytes, filename: str, content_type: str = "") -> object:
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXT:
        raise BizError(
            Err.DOC_UNSUPPORTED,
            f"暂不支持 {ext or '未知'} 格式，请上传 pdf / docx / md / txt",
        )
    if len(data) > settings.RAG_MAX_DOC_MB * 1024 * 1024:
        raise BizError(Err.DOC_TOO_LARGE, f"文档超过 {settings.RAG_MAX_DOC_MB}MB")

    key = build_key("kb/docs", filename)
    stored = get_storage().put(data, key, content_type or None)
    logger.info("文档已上传 key=%s provider=%s size=%d", stored.key, stored.provider, stored.size)
    return stored


def absolutize(url: str, base_url: str) -> str:
    """本地存储返回相对路径，对外输出时补全域名。"""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{base_url.rstrip('/')}{url}"
