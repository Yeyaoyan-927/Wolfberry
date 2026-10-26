"""切分策略。

三种策略，按文档类型选择，避免"一律定长切"把条款切碎：
    clause    标准/法规：按「第X章 / 5.2 / 一、」等编号切，保留条款路径
    recursive 通用长文：按段落聚合到目标长度，带重叠
    qa        问答集：按 Q/A 对切

auto 会先探测编号密度，再决定用 clause 还是 recursive。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 条款编号：第X章/节/条、5.2.1、一、、（一）
_HEADING = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百零]+[章节条]|附录[A-Z一二三四五六七八九十]|"
    r"\d+(?:\.\d+){0,3}[\.、\s]|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）)\S*",
    re.MULTILINE,
)


@dataclass
class Chunk:
    index: int
    text: str
    section_path: str = ""


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    """超长段落按句号/分号回退切分，尽量不截断句子。"""
    if len(text) <= size:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("。"), window.rfind("；"), window.rfind("\n"))
            if cut > size * 0.5:
                end = start + cut + 1
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]


def split_recursive(text: str, size: int = 500, overlap: int = 80) -> list[Chunk]:
    text = _normalize(text)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if not blocks:
        return []

    chunks: list[Chunk] = []
    buffer = ""
    for block in blocks:
        if len(block) > size:
            if buffer:
                chunks.append(Chunk(len(chunks), buffer))
                buffer = ""
            for piece in _split_long(block, size, overlap):
                chunks.append(Chunk(len(chunks), piece))
            continue

        if len(buffer) + len(block) + 1 <= size:
            buffer = f"{buffer}\n{block}" if buffer else block
        else:
            if buffer:
                chunks.append(Chunk(len(chunks), buffer))
            buffer = block

    if buffer:
        chunks.append(Chunk(len(chunks), buffer))
    return chunks


def split_clause(text: str, size: int = 500, overlap: int = 80) -> list[Chunk]:
    """按条款切分：每块带 section_path，便于回答时标注"依据第几条"。"""
    text = _normalize(text)
    matches = list(_HEADING.finditer(text))
    if len(matches) < 3:  # 编号太少，退回通用策略
        return split_recursive(text, size, overlap)

    chunks: list[Chunk] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        heading = match.group(0).strip()[:60]
        if len(body) <= size * 1.6:
            chunks.append(Chunk(len(chunks), body, heading))
        else:
            for j, piece in enumerate(_split_long(body, size, overlap)):
                chunks.append(Chunk(len(chunks), piece, f"{heading}{(f' (续{j + 1})' if j else '')}"))
    return chunks


def split_qa(text: str) -> list[Chunk]:
    text = _normalize(text)
    blocks = re.split(r"\n(?=(?:问[:：]|Q[:：]|\d+[\.、]\s*问))", text)
    chunks: list[Chunk] = []
    for block in blocks:
        block = block.strip()
        if len(block) < 8:
            continue
        question = block.split("\n", 1)[0][:60]
        chunks.append(Chunk(len(chunks), block, question))
    return chunks or split_recursive(text)


def detect_strategy(text: str, doc_type: str = "") -> str:
    if doc_type in {"faq"}:
        return "qa"
    if doc_type in {"standard", "rule"}:
        return "clause"
    headings = len(_HEADING.findall(text[:8000]))
    return "clause" if headings >= 3 else "recursive"


def split(
    text: str,
    *,
    strategy: str = "auto",
    size: int = 500,
    overlap: int = 80,
    doc_type: str = "",
) -> tuple[list[Chunk], str]:
    """返回 (切片列表, 实际使用的策略名)。"""
    resolved = detect_strategy(text, doc_type) if strategy == "auto" else strategy

    if resolved == "qa":
        chunks = split_qa(text)
    elif resolved == "clause":
        chunks = split_clause(text, size, overlap)
    else:
        chunks = split_recursive(text, size, overlap)

    # 兜底：清洗空块并重排索引
    cleaned = [c for c in chunks if len(c.text.strip()) >= 8]
    for idx, chunk in enumerate(cleaned):
        chunk.index = idx
    return cleaned, resolved
