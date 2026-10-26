"""文档解析：统一把 pdf / docx / md / txt 转成纯文本 + 页码信息。"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.core.errors import BizError, Err

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {".pdf", ".docx", ".md", ".txt", ".markdown"}


@dataclass
class ParsedDoc:
    text: str
    page_count: int = 0
    meta: dict = field(default_factory=dict)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _parse_pdf(data: bytes) -> ParsedDoc:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise BizError(Err.DOC_PARSE_FAILED, "PDF 解析失败，文件可能已损坏", detail=str(exc)) from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # 单页异常不影响整篇
            pages.append("")

    text = "\n".join(pages).strip()
    if len(text) < 20:
        raise BizError(
            Err.DOC_PARSE_FAILED,
            "未提取到文本，疑似扫描件。请先 OCR 转换为可复制文本后重新上传",
        )
    return ParsedDoc(text=text, page_count=len(pages), meta={"pages": len(pages)})


def _parse_docx(data: bytes) -> ParsedDoc:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise BizError(Err.DOC_PARSE_FAILED, "Word 解析失败", detail=str(exc)) from exc

    blocks: list[str] = []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading"):
            blocks.append(f"\n{text}\n")
        else:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))

    text = "\n".join(blocks).strip()
    if not text:
        raise BizError(Err.DOC_PARSE_FAILED, "Word 文档内容为空")
    return ParsedDoc(text=text, page_count=0, meta={"blocks": len(blocks)})


def _parse_text(data: bytes) -> ParsedDoc:
    text = _decode(data).strip()
    if not text:
        raise BizError(Err.DOC_PARSE_FAILED, "文件内容为空")
    return ParsedDoc(text=text, page_count=0, meta={})


def parse(filename: str, data: bytes) -> ParsedDoc:
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise BizError(
            Err.DOC_UNSUPPORTED,
            f"暂不支持 {ext or '未知'} 格式，请上传 pdf / docx / md / txt",
        )
    if ext == ".pdf":
        return _parse_pdf(data)
    if ext == ".docx":
        return _parse_docx(data)
    return _parse_text(data)
