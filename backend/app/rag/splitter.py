"""切分策略。

四种策略，按文档类型选择，避免"一律定长切"把条款或标题切碎：
    clause    标准/法规：按「第X章 / 5.2 / 一、」等编号切，保留条款路径
    md        Markdown/带标题层级：按 # / ## 切，section_path 记录层级路径
    recursive 通用长文：按段落聚合到目标长度，带重叠
    qa        问答集：按 Q/A 对切

auto 会先探测结构（markdown 标题密度 → 条款编号密度 → 退化到 recursive）。

每个切片除正文外还带两样东西，供检索侧使用：
    section_path  条款/章节路径，回答时用于标注"依据第几条"
    context       所属章节标题链 + 首句，检索命中后作为上下文回填（small-to-big）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 条款编号：第X章/节/条、5.2.1、一、、（一）
_HEADING = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百零]+[章节条]|附录[A-Z一二三四五六七八九十]|"
    r"\d+(?:\.\d+){0,3}[\.、\s]|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）)\S*",
    re.MULTILINE,
)

# Markdown 标题：# ~ ######
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


@dataclass
class Chunk:
    index: int
    text: str
    section_path: str = ""
    context: str = ""
    level: int = 0                      # markdown 标题层级，0 表示无

    @property
    def char_count(self) -> int:
        return len(self.text)


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


def _first_sentence(text: str, limit: int = 60) -> str:
    body = text.strip()
    for sep in ("。", "\n", "；"):
        idx = body.find(sep)
        if 0 < idx < limit:
            return body[: idx + 1]
    return body[:limit]


def _parent_path(path: str) -> str:
    """取 section_path 的父级（去掉最后一段）。"""
    return path.rsplit(" > ", 1)[0] if " > " in path else ""


def _group_key(chunk: Chunk) -> str:
    """判断"是否同一父级"的键。

    优先用 context（章节链）：clause 的 section_path 是「第三条」这种平铺条款号，
    真正的层级在 context「第二章 > 第三条」里；md 的 context 与 section_path 同构。
    qa 的 context 是问题本身，因此每个问答各自成组（不合并，保持一问一答完整）。

    阿拉伯数字编号（1. / 1.1）的文档没有「第X章」层级，逐条也是同级，
    此时统一归到 __root__：同文档的短条款可以互相合并到块长上限，
    合并后 section_path 仍记录「起 ~ 止」，引用不会失真。
    """
    base = chunk.context or chunk.section_path
    if " > " in base:
        return _parent_path(base)
    return "__flat__"      # 无层级信息：同文档同级条款，允许合并到块长上限


def _merge_siblings(chunks: list[Chunk], size: int, ratio: float = 0.6) -> list[Chunk]:
    """合并同一父级下的过短相邻切片。

    为什么需要：条款式/标题式文档每个小节往往只有一两句话，
    逐节切会产出大量 20~40 字的碎片——embedding 信息量不足，
    检索时容易命中但没有可回答的内容。合并到同一父级的合理长度后，
    语义完整度明显提升，同时保留父路径供引用溯源。
    """
    if not chunks:
        return chunks

    merged: list[Chunk] = []
    for chunk in chunks:
        prev = merged[-1] if merged else None
        g_chunk, g_prev = _group_key(chunk), (_group_key(prev) if prev else "")
        # 同组可合并；顶层/无层级块（__flat__ 或只有一行的标题块）允许被相邻内容吸收
        related = bool(
            prev
            and chunk.section_path
            and prev.section_path
            and (g_chunk == g_prev or g_prev == "__flat__" or g_chunk == "__flat__")
        )
        can_merge = bool(
            related
            and prev.char_count < size * ratio
            and prev.char_count + chunk.char_count + 2 <= size
        )
        if can_merge:
            prev.text = f"{prev.text}\n{chunk.text}"
            # 只保留"首段 ~ 末段"，避免路径越并越长
            first = prev.section_path.split(" ~ ")[0]
            last = chunk.section_path.split(" ~ ")[-1][:30]
            # 末段若只是首段的子级，只保留子级部分，避免"标题 ~ 标题 > 子标题"
            if last.startswith(first + " > "):
                last = last[len(first) + 3:]
            prev.section_path = (first if first == last else f"{first} ~ {last}")[:250]
            # context 只保留真实章节链，绝不写入内部分组键（__flat__ 是判断用的）
            if not prev.context or prev.context == "__flat__":
                prev.context = "" if chunk.context == "__flat__" else chunk.context
            continue
        merged.append(chunk)

    for idx, c in enumerate(merged):
        c.index = idx
    return merged

    for idx, c in enumerate(merged):
        c.index = idx
    return merged


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

    # 段落式切分没有显式标题，用各自首句作为检索上下文
    for c in chunks:
        if not c.context:
            c.context = _first_sentence(c.text)
    return chunks


def split_markdown(text: str, size: int = 500, overlap: int = 80) -> list[Chunk]:
    """按 Markdown 标题层级切分，section_path 形如「三级 分级要求 > 4.2 特级」。"""
    text = _normalize(text)
    matches = list(_MD_HEADING.finditer(text))
    if len(matches) < 2:                       # 没有标题结构，退回通用策略
        return split_recursive(text, size, overlap)

    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []          # (level, title)

    # 第一个标题之前的前言
    preface = text[: matches[0].start()].strip()
    if len(preface) >= 20:
        for piece in _split_long(preface, size, overlap):
            chunks.append(Chunk(len(chunks), piece, "前言", context="前言"))

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # 维护标题栈，得到完整层级路径
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        path = " > ".join(t for _, t in stack)[:240]
        context = path

        if not body:
            continue
        if len(body) <= size * 1.6:
            chunks.append(Chunk(len(chunks), body, path, context=context, level=level))
        else:
            for j, piece in enumerate(_split_long(body, size, overlap)):
                suffix = f" (续{j + 1})" if j else ""
                chunks.append(Chunk(len(chunks), piece, path + suffix,
                                    context=context, level=level))
    return _merge_siblings(chunks, size)


def split_clause(text: str, size: int = 500, overlap: int = 80) -> list[Chunk]:
    """按条款切分：每块带 section_path，便于回答时标注"依据第几条"。"""
    text = _normalize(text)
    matches = list(_HEADING.finditer(text))
    if len(matches) < 3:  # 编号太少，退回通用策略
        return split_recursive(text, size, overlap)

    chunks: list[Chunk] = []
    last_clause = ""                     # 最近一个「第X章/节」级标题，作为上下文
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        heading = match.group(0).strip()[:60]
        if re.match(r"^\s*(第[一二三四五六七八九十百零]+[章节]|附录)", heading):
            last_clause = heading
        # 只有存在上级章节时才给 context；否则留空（section_path 已够用，
        # 填个"1."当上下文反而干扰阅读）
        context = f"{last_clause} > {heading}" if last_clause and last_clause != heading else ""

        if len(body) <= size * 1.6:
            chunks.append(Chunk(len(chunks), body, heading, context=context))
        else:
            for j, piece in enumerate(_split_long(body, size, overlap)):
                suffix = f" (续{j + 1})" if j else ""
                chunks.append(Chunk(len(chunks), piece, f"{heading}{suffix}",
                                    context=context))
    return _merge_siblings(chunks, size)


def split_qa(text: str, size: int = 500, overlap: int = 80) -> list[Chunk]:
    text = _normalize(text)
    blocks = re.split(r"\n(?=(?:问[:：]|Q[:：]|\d+[\.、]\s*问))", text)
    chunks: list[Chunk] = []
    carry = ""                                   # 文档标题等前言，并入首个问答
    for block in blocks:
        block = block.strip()
        if len(block) < 8:
            continue
        # 只含 markdown 标题、没有正文的块：作为前言吞掉
        if block.lstrip().startswith("#") and "\n" not in block:
            carry = f"{carry}\n{block}".strip()
            continue
        if carry:
            block = f"{carry}\n{block}"
            carry = ""
        question = block.split("\n", 1)[0][:60]
        # 单个问答过长时再按长度切，但保留问题作为上下文
        if len(block) > size * 1.6:
            for j, piece in enumerate(_split_long(block, size, overlap)):
                chunks.append(Chunk(len(chunks), piece,
                                    f"{question}{f' (续{j + 1})' if j else ''}",
                                    context=question))
        else:
            chunks.append(Chunk(len(chunks), block, question, context=question))
    return chunks or split_recursive(text, size, overlap)


def detect_strategy(text: str, doc_type: str = "") -> str:
    if doc_type in {"faq"}:
        return "qa"
    if doc_type in {"standard", "rule"}:
        # 有 markdown 标题结构时优先按标题切，层级信息更完整
        return "md" if len(_MD_HEADING.findall(text[:8000])) >= 2 else "clause"
    head = text[:8000]
    if len(_MD_HEADING.findall(head)) >= 2:
        return "md"
    if len(_HEADING.findall(head)) >= 3:
        return "clause"
    return "recursive"


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
    size = max(120, min(size, 4000))
    overlap = max(0, min(overlap, size // 2))     # 重叠不得超过块长一半

    if resolved == "qa":
        chunks = split_qa(text, size, overlap)
    elif resolved == "md":
        chunks = split_markdown(text, size, overlap)
    elif resolved == "clause":
        chunks = split_clause(text, size, overlap)
    else:
        chunks = split_recursive(text, size, overlap)

    # 兜底：清洗空块并重排索引
    cleaned = [c for c in chunks if len(c.text.strip()) >= 8]
    for idx, chunk in enumerate(cleaned):
        chunk.index = idx
    return cleaned, resolved


# ---------- 切分质量评估 ----------
SHORT_THRESHOLD = 60          # 少于 60 字视为过短碎块（检索噪音的主要来源）


def chunk_report(chunks: list[Chunk], size: int = 500) -> dict:
    """切分质量指标：给运营在"试切分"阶段判断参数是否合适。

    关注三件事：
        过短块多 → 语义不完整，答案会缺上下文 → 调小 overlap / 换 clause 策略
        超长块多 → 超出 embedding 有效区间，召回变差 → 调小 size
        无章节路径 → 引用溯源信息不足 → 换 md / clause 策略
    """
    n = len(chunks)
    if n == 0:
        return {"count": 0, "avg_len": 0, "min_len": 0, "max_len": 0,
                "short_ratio": 0.0, "long_ratio": 0.0, "with_section_ratio": 0.0,
                "total_chars": 0, "advice": ["没有切出任何内容，请检查文档是否为空白或扫描件（需 OCR）"]}

    lens = [c.char_count for c in chunks]
    short = sum(1 for x in lens if x < SHORT_THRESHOLD)
    long_ = sum(1 for x in lens if x > size * 1.6)
    with_section = sum(1 for c in chunks if c.section_path.strip())

    advice: list[str] = []
    if short / n > 0.3:
        advice.append(f"过短块占 {short / n:.0%}，建议调大 size 或换 clause/md 策略，减少碎块")
    if long_ / n > 0.2:
        advice.append(f"超长块占 {long_ / n:.0%}，建议调小 size 到 {max(200, size // 2)} 左右")
    if with_section / n < 0.5:
        advice.append("多数切片没有章节路径，引用溯源会偏弱；标准类文档建议用 clause 或 md 策略")
    if not advice:
        advice.append("长度分布合理，可直接入库")

    return {
        "count": n,
        "avg_len": round(sum(lens) / n, 1),
        "min_len": min(lens),
        "max_len": max(lens),
        "short_ratio": round(short / n, 3),
        "long_ratio": round(long_ / n, 3),
        "with_section_ratio": round(with_section / n, 3),
        "total_chars": sum(lens),
        "advice": advice,
    }
