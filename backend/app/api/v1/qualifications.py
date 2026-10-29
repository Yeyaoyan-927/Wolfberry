"""卖家资质接口：卖家提交/查看，平台审核。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from app.api.deps import AdminUser, AnyUser, DbSession
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.schemas.qualification import QualAuditIn, QualificationIn
from app.services import qualification_service

router = APIRouter(tags=["qualification"])


@router.post("/seller/qualification")
def submit_qualification(payload: QualificationIn, session: DbSession, user: AnyUser):
    """卖家提交入驻资质（驳回后可重新提交）。"""
    trace = new_trace_id()
    out = qualification_service.submit(session, user=user, payload=payload)
    return ok(jsonable_encoder(out), trace_id=trace)


@router.get("/seller/qualification")
def my_qualification(session: DbSession, user: AnyUser):
    """我的资质状态；未提交返回 status=0 的空壳。"""
    trace = new_trace_id()
    return ok(jsonable_encoder(qualification_service.mine(session, user=user)), trace_id=trace)


@router.get("/admin/seller-qualifications")
def list_qualifications(
    session: DbSession,
    admin: AdminUser,
    status: int | None = Query(None, ge=0, le=3),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """后台审核列表：每个卖家只显示最新一次提交。"""
    trace = new_trace_id()
    items, total = qualification_service.list_for_admin(
        session, status=status, page=page, size=size
    )
    return ok({"items": jsonable_encoder(items), "total": total, "page": page, "size": size},
              trace_id=trace)


@router.post("/admin/seller-qualifications/{qid}/audit")
def audit_qualification(qid: int, payload: QualAuditIn, session: DbSession, admin: AdminUser):
    """审核：通过即解锁发布权限；驳回必须写原因。"""
    trace = new_trace_id()
    out = qualification_service.audit(
        session, admin=admin, qid=qid, approve=payload.approve, reason=payload.reason
    )
    return ok(jsonable_encoder(out), trace_id=trace)


@router.get("/admin/seller-qualifications/stats")
def qualification_stats(session: DbSession, admin: AdminUser):
    trace = new_trace_id()
    return ok(qualification_service.stats(session), trace_id=trace)
