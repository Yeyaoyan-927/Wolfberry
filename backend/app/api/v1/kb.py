"""知识库接口：文档上传入库、切片查看、检索、问答、评测。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from app.api.deps import DbSession
from app.core.errors import BizError, Err
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.schemas.kb import AskIn, SearchIn
from app.services import kb_service, rag_service

router = APIRouter(tags=["kb"])


def _eval_cases() -> list[dict]:
    """评测集：scripts/eval_cases.json，格式 [{"question":..., "expected":[...]}]。"""
    path = Path(__file__).resolve().parents[3] / "scripts" / "eval_cases.json"
    if not path.exists():
        raise BizError(Err.NOT_FOUND, f"评测集不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/kb/documents")
async def upload_document(
    session: DbSession,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form("other"),
    chunk_strategy: str = Form("auto"),
    user_id: int = Query(0, description="演示环境无登录时的操作人，可选"),
):
    """上传文档并立即完成 解析 → 切分 → 向量化 → 入库。"""
    trace = new_trace_id()
    data = await file.read()
    if not data:
        raise BizError(Err.PARAM_INVALID, "上传内容为空")

    doc = kb_service.create_document(
        session,
        filename=file.filename or "doc.txt",
        data=data,
        content_type=file.content_type or "application/octet-stream",
        title=title or None,
        doc_type=doc_type,
        chunk_strategy=chunk_strategy,
        user_id=user_id or None,
    )

    body = jsonable_encoder(doc)
    body.pop("url", None)  # 签名 URL 不回显，前端按需用 /kb/documents/{id}/file 获取
    return ok(body, trace_id=trace)


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
def list_chunks(doc_id: int, session: DbSession, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    trace = new_trace_id()
    from app.repositories.kb import KbRepo

    repo = KbRepo(session)
    doc = repo.get(doc_id)
    if doc is None:
        raise BizError(Err.NOT_FOUND, "文档不存在")

    chunks = repo.chunks_of(doc_id, offset=(page - 1) * size, limit=size)
    return ok(
        {
            "doc": {"id": doc.id, "title": doc.title, "chunk_count": doc.chunk_count},
            "items": jsonable_encoder(chunks),
            "page": page,
            "size": size,
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


@router.post("/kb/ask")
def kb_ask(payload: AskIn, session: DbSession):
    trace = new_trace_id()
    result = rag_service.ask(
        session,
        payload.question,
        top_k=payload.top_k,
        with_llm=payload.with_llm,
    )
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
