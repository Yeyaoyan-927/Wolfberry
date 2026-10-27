"""知识库接口：文档上传入库、切片查看、检索、问答、评测。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from app.api.deps import AdminUser, DbSession, OptionalUser
from app.core.errors import BizError, Err
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.models.kb import KbDocument
from app.schemas.kb import AskIn, SearchIn
from app.services import kb_service, rag_service

router = APIRouter(tags=["kb"])

ALLOWED_STRATEGIES = {"auto", "clause", "md", "recursive", "qa"}


def _eval_cases() -> list[dict]:
    """评测集：scripts/eval_cases.json，格式 [{"question":..., "expected":[...]}]。"""
    path = Path(__file__).resolve().parents[3] / "scripts" / "eval_cases.json"
    if not path.exists():
        raise BizError(Err.NOT_FOUND, f"评测集不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/kb/preview")
async def preview_chunks(
    admin: AdminUser,
    file: UploadFile = File(...),
    doc_type: str = Form("other"),
    chunk_strategy: str = Form("auto"),
    chunk_size: int = Form(0, description="0 表示用配置默认值"),
    chunk_overlap: int = Form(-1, description="-1 表示用配置默认值"),
):
    """试切分：只看切片效果与质量报告，不入库。

    典型用法：先按默认参数试一次 → 看 report.advice → 调 size/策略再试 →
    满意后用 /kb/documents 带同样的参数正式入库。
    """
    trace = new_trace_id()
    if chunk_strategy not in ALLOWED_STRATEGIES:
        raise BizError(Err.PARAM_INVALID, f"切分策略必须是 {sorted(ALLOWED_STRATEGIES)} 之一")
    data = await file.read()
    if not data:
        raise BizError(Err.PARAM_INVALID, "上传内容为空")

    result = kb_service.preview_chunks(
        filename=file.filename or "doc.txt",
        data=data,
        doc_type=doc_type,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size or None,
        chunk_overlap=None if chunk_overlap < 0 else chunk_overlap,
    )
    return ok(result, trace_id=trace)


@router.post("/kb/documents")
async def upload_document(
    session: DbSession,
    admin: AdminUser,
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form("other"),
    chunk_strategy: str = Form("auto"),
    chunk_size: int = Form(0),
    chunk_overlap: int = Form(-1),
):
    """上传文档并立即完成 解析 → 切分 → 向量化 → 入库。"""
    trace = new_trace_id()
    data = await file.read()
    if not data:
        raise BizError(Err.PARAM_INVALID, "上传内容为空")
    if chunk_strategy not in ALLOWED_STRATEGIES:
        raise BizError(Err.PARAM_INVALID, f"切分策略必须是 {sorted(ALLOWED_STRATEGIES)} 之一")

    doc = kb_service.create_document(
        session,
        filename=file.filename or "doc.txt",
        data=data,
        content_type=file.content_type or "application/octet-stream",
        title=title or None,
        doc_type=doc_type,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size or None,
        chunk_overlap=None if chunk_overlap < 0 else chunk_overlap,
        user_id=admin.id,
    )

    body = jsonable_encoder(doc)
    body.pop("url", None)  # 签名 URL 不回显，前端按需用 /kb/documents/{id}/file 获取
    return ok(body, trace_id=trace)


@router.post("/kb/documents/{doc_id}/rechunk")
def rechunk_document(
    doc_id: int,
    session: DbSession,
    admin: AdminUser,
    chunk_strategy: str = Query("", description="留空则沿用原策略"),
    chunk_size: int = Query(0, description="0 表示沿用原参数"),
    chunk_overlap: int = Query(-1, description="-1 表示沿用原参数"),
):
    """按新参数重切文档（重新解析原文件 → 重切 → 重新向量化）。"""
    trace = new_trace_id()
    doc = session.get(KbDocument, doc_id)
    if doc is None:
        raise BizError(Err.NOT_FOUND, "文档不存在")
    if chunk_strategy and chunk_strategy not in ALLOWED_STRATEGIES:
        raise BizError(Err.PARAM_INVALID, f"切分策略必须是 {sorted(ALLOWED_STRATEGIES)} 之一")

    result = kb_service.rechunk(
        session,
        doc,
        strategy=chunk_strategy or None,
        chunk_size=chunk_size or None,
        chunk_overlap=None if chunk_overlap < 0 else chunk_overlap,
    )
    return ok({"doc_id": doc_id, "chunk_type": doc.doc_type, **result}, trace_id=trace)


@router.delete("/kb/documents/{doc_id}")
def delete_document(doc_id: int, session: DbSession, admin: AdminUser):
    """删除文档及其切片、向量、原始文件。"""
    trace = new_trace_id()
    doc = session.get(KbDocument, doc_id)
    if doc is None:
        raise BizError(Err.NOT_FOUND, "文档不存在")
    kb_service.delete_document(session, doc)
    return ok({"deleted": doc_id}, trace_id=trace)


@router.get("/kb/documents")
def list_documents(
    session: DbSession,
    doc_type: str | None = None,
    status: int | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    trace = new_trace_id()
    rows, total = _list_docs(session, doc_type, status, keyword, page, size)
    items = [jsonable_encoder(doc) for doc in rows]
    return ok({"items": items, "total": total, "page": page, "size": size}, trace_id=trace)


def _list_docs(session, doc_type, status, keyword, page, size):
    from app.repositories.kb import KbRepo

    return KbRepo(session).list_docs(
        doc_type=doc_type,
        status=status,
        keyword=keyword,
        offset=(page - 1) * size,
        limit=size,
    )


@router.get("/kb/documents/{doc_id}/chunks")
def list_chunks(
    doc_id: int,
    session: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    keyword: str | None = Query(None, description="按切片正文/章节路径过滤"),
):
    """切片详情：供运营核对"切得对不对、引得到不到"。

    返回每条切片的完整元信息（章节路径、上下文、字数、向量模型/维度），
    正文不截断——排查召回问题时需要看原文。
    """
    trace = new_trace_id()
    from sqlalchemy import func, or_, select

    from app.models.kb import KbChunk
    from app.repositories.kb import KbRepo

    repo = KbRepo(session)
    doc = repo.get(doc_id)
    if doc is None:
        raise BizError(Err.NOT_FOUND, "文档不存在")

    conds = [KbChunk.doc_id == doc_id]
    if keyword:
        like = f"%{keyword}%"
        conds.append(or_(KbChunk.content.like(like), KbChunk.section_path.like(like)))

    total = int(session.scalar(select(func.count(KbChunk.id)).where(*conds)) or 0)
    rows = session.scalars(
        select(KbChunk)
        .where(*conds)
        .order_by(KbChunk.chunk_no)
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    # 整体长度分布，一眼判断切分质量
    lens = [c.char_count for c in repo.chunks_of(doc_id, offset=0, limit=1000)]
    stats = {
        "count": len(lens),
        "avg_len": round(sum(lens) / len(lens), 1) if lens else 0,
        "min_len": min(lens) if lens else 0,
        "max_len": max(lens) if lens else 0,
    }

    items = [
        {
            "id": c.id,
            "chunk_no": c.chunk_no,
            "section_path": c.section_path,
            "context": (c.meta or {}).get("context", ""),
            "content": c.content,
            "char_count": c.char_count,
            "embedding_provider": c.embedding_provider,
            "embedding_dim": c.embedding_dim,
            "level": (c.meta or {}).get("level", 0),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]

    return ok(
        {
            "doc": {
                "id": doc.id,
                "title": doc.title,
                "chunk_count": doc.chunk_count,
                "chunk_strategy": doc.chunk_strategy,
                "chunk_size": doc.chunk_size,
                "chunk_overlap": doc.chunk_overlap,
                "char_count": doc.char_count,
            },
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "stats": stats,
        },
        trace_id=trace,
    )


@router.get("/kb/documents/{doc_id}/file")
def download_document(doc_id: int, session: DbSession):
    """获取文档原始文件。COS 私有桶会 302 到签名 URL。"""
    from app.repositories.kb import KbRepo

    doc = KbRepo(session).get(doc_id)
    if doc is None or not doc.object_key:
        raise BizError(Err.NOT_FOUND, "文档不存在或缺少原始文件")
    return RedirectResponse(get_storage().url_for(doc.object_key), status_code=302)


@router.post("/kb/search")
def kb_search(payload: SearchIn, session: DbSession):
    trace = new_trace_id()
    result = rag_service.search(session, payload.query, top_k=payload.top_k, doc_type=payload.doc_type)
    return ok(jsonable_encoder(result), trace_id=trace)


@router.post("/kb/ask/stream")
async def kb_ask_stream(payload: AskIn, session: DbSession, user: OptionalUser):
    """流式问答：逐个节点推送执行过程（意图识别 → 工具调用 → 汇总生成）。

    事件类型：
        start  问答开始
        step   节点状态（running / done，含耗时与结果摘要）
        done   最终回答 + 引用 + 完整思考轨迹
        error  中途失败
    """
    from fastapi.responses import StreamingResponse

    from app.agent.runner import stream_agent

    role = user.role if user else "buyer"

    def encode(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

    async def gen():
        async for item in stream_agent(session, payload.question, role=role):
            yield encode(item["event"], item["data"])

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # 防止反向代理缓冲导致前端收不到增量
        },
    )


@router.post("/kb/ask")
def kb_ask(payload: AskIn, session: DbSession, user: OptionalUser):
    """智能问答：LangGraph Agent 编排（意图→工具→生成）优先，失败自动降级 RAG 管线。"""
    trace = new_trace_id()

    if payload.with_llm:
        from app.agent import run_agent

        agent = run_agent(session, payload.question,
                          role=user.role if user else "buyer")
        if agent is not None:
            agent["mode"] = "agent"
            return ok(jsonable_encoder(agent), trace_id=trace)

    result = rag_service.ask(
        session,
        payload.question,
        top_k=payload.top_k,
        with_llm=payload.with_llm,
    )
    result["mode"] = "pipeline"
    return ok(jsonable_encoder(result), trace_id=trace)


@router.get("/kb/eval")
def kb_eval(
    session: DbSession,
    k: int = Query(5, ge=1, le=10),
    doc_type: str | None = None,
):
    """检索效果评估：Recall@K 与 MRR。评测集在 scripts/eval_cases.json。"""
    trace = new_trace_id()
    report = rag_service.evaluate(session, _eval_cases(), k=k, doc_type=doc_type)
    return ok(report, trace_id=trace)
