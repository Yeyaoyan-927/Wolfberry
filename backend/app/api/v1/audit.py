"""审核工作台接口（仅管理员）：队列、详情、通过/驳回、手动重评。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from app.api.deps import AdminUser, DbSession
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.services import audit_service

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


@router.get("/queue")
def audit_queue(
    session: DbSession,
    auditor: AdminUser,
    flag: str | None = Query(None, description="按差异标记过滤：绿/黄/红/蓝/灰"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """待审核队列：红标（自述高报≥2级）优先展示。"""
    trace = new_trace_id()
    items, total = audit_service.audit_queue(session, flag=flag, page=page, size=size)
    return ok({
        "items": items, "total": total, "page": page, "size": size,
        "reject_reasons": audit_service.REJECT_REASONS,
    }, trace_id=trace)


@router.get("/products/{product_id}")
def audit_detail(product_id: int, session: DbSession, auditor: AdminUser):
    """审核详情：商品 + 图片 + AI 评估明细 + 卖家风险画像 + 历史记录。"""
    trace = new_trace_id()
    return ok(jsonable_encoder(audit_service.audit_detail(session, product_id)), trace_id=trace)


@router.post("/products/{product_id}/approve")
def approve(product_id: int, session: DbSession, auditor: AdminUser,
            grade_platform: str | None = Query(None, description="审核员修正后的认定等级，不传则采用 AI 建议")):
    """通过上架（架构底线：等级由审核员确认，AI 只建议）。"""
    trace = new_trace_id()
    result = audit_service.approve(session, auditor=auditor, product_id=product_id,
                                   grade_platform=grade_platform)
    return ok(result, trace_id=trace)


@router.post("/products/{product_id}/reject")
def reject(product_id: int, session: DbSession, auditor: AdminUser,
           reason_code: str = Query(..., description="驳回原因代码"),
           note: str = Query("", max_length=150, description="补充说明")):
    """驳回，原因必须来自枚举（见 /queue 返回的 reject_reasons）。"""
    trace = new_trace_id()
    return ok(audit_service.reject(session, auditor=auditor, product_id=product_id,
                                   reason_code=reason_code, note=note), trace_id=trace)


@router.post("/products/{product_id}/reassess")
def reassess(product_id: int, session: DbSession, auditor: AdminUser):
    """手动触发重新评估（改图后），同步执行并返回最新 AI 摘要。"""
    trace = new_trace_id()
    return ok(jsonable_encoder(audit_service.force_reassess(session, auditor=auditor,
                                                            product_id=product_id)), trace_id=trace)
