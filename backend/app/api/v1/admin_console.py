"""管理端：用户管理、阈值与审计日志查询。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.core.config import settings
from app.core.errors import BizError, Err
from app.core.logging import new_trace_id
from app.models.audit import AuditLog
from app.models.product import Product
from app.models.sys import SysUser
from app.schemas.common import ok

router = APIRouter(prefix="/admin", tags=["admin-console"])


# ---------------- 用户管理 ----------------
@router.get("/users")
def list_users(
    session: DbSession,
    admin: AdminUser,
    role: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    conds = []
    if role:
        conds.append(SysUser.role == role)
    if keyword:
        conds.append(
            SysUser.username.like(f"%{keyword}%") | SysUser.display_name.like(f"%{keyword}%")
        )
    total = session.scalar(select(func.count()).select_from(SysUser).where(*conds)) or 0
    rows = session.scalars(
        select(SysUser).where(*conds).order_by(SysUser.id).offset((page - 1) * size).limit(size)
    ).all()

    # 卖家附带经营统计（商品数 / 驳回 / 红标）
    items = []
    for u in rows:
        stats = None
        if u.role == "seller":
            published = session.scalar(
                select(func.count()).select_from(Product).where(Product.seller_id == u.id)
            ) or 0
            rejected = session.scalar(
                select(func.count())
                .select_from(Product)
                .where(Product.seller_id == u.id, Product.status == 4)
            ) or 0
            since = dt.datetime.now() - dt.timedelta(days=30)
            red = session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .join(Product, Product.id == AuditLog.product_id)
                .where(Product.seller_id == u.id, AuditLog.diff_flag == "红",
                       AuditLog.acted_at >= since)
            ) or 0
            stats = {"published": int(published), "rejected": int(rejected), "red_30d": int(red)}
        items.append({
            "id": u.id, "username": u.username, "display_name": u.display_name,
            "role": u.role, "org_name": u.org_name, "is_active": bool(u.is_active),
            "created_at": str(u.created_at) if getattr(u, "created_at", None) else None,
            "seller_stats": stats,
        })
    return ok({"items": items, "total": total, "page": page, "size": size},
              trace_id=new_trace_id())


@router.patch("/users/{user_id}/status")
def set_user_status(user_id: int, session: DbSession, admin: AdminUser,
                    is_active: bool = Query(..., description="true 启用 / false 停用")):
    user = session.get(SysUser, user_id)
    if user is None:
        raise BizError(Err.NOT_FOUND, "用户不存在")
    if user.id == admin.id and not is_active:
        raise BizError(Err.PARAM_INVALID, "不能停用自己的账号")
    user.is_active = is_active
    session.flush()
    return ok({"id": user.id, "is_active": bool(user.is_active)}, trace_id=new_trace_id())


# ---------------- 模型与阈值（只读展示） ----------------
@router.get("/thresholds")
def get_thresholds(session: DbSession, admin: AdminUser):
    from app.domain.grading import DEFAULT_THRESHOLDS

    return ok({
        "model_version": settings.ASSESS_MODEL_VERSION,
        "threshold_version": settings.ASSESS_THRESHOLD_VERSION,
        "detector": settings.ASSESS_DETECTOR,
        "gray_conf": settings.ASSESS_GRAY_CONF,
        "min_image_conf": settings.ASSESS_MIN_IMAGE_CONF,
        "min_grains": settings.ASSESS_MIN_GRAINS,
        "thresholds": DEFAULT_THRESHOLDS,
        "grade_lines": [
            {"grade": "特优", "defect": "≤1.0%", "moldy": "=0"},
            {"grade": "特级", "defect": "≤2.0%", "moldy": "≤0.2%"},
            {"grade": "甲级", "defect": "≤5.0%", "moldy": "≤0.5%"},
            {"grade": "乙级", "defect": "≤10.0%", "moldy": "—"},
            {"grade": "等外", "defect": ">10% 或霉变>1.5%", "moldy": "一票否决"},
        ],
    }, trace_id=new_trace_id())


# ---------------- 审计日志（审核动作全量） ----------------
@router.get("/audit/logs")
def audit_logs(
    session: DbSession,
    admin: AdminUser,
    action: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    conds = []
    if action:
        conds.append(AuditLog.action == action)
    total = session.scalar(select(func.count()).select_from(AuditLog).where(*conds)) or 0
    rows = session.execute(
        select(AuditLog, Product.title, SysUser.display_name)
        .join(Product, Product.id == AuditLog.product_id)
        .join(SysUser, SysUser.id == AuditLog.auditor_id)
        .where(*conds)
        .order_by(AuditLog.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    items = [
        {
            "id": lg.id, "product_id": lg.product_id, "product_title": title,
            "auditor": name, "action": lg.action, "diff_flag": lg.diff_flag,
            "grade_claim": lg.grade_claim, "ai_grade": lg.ai_grade,
            "grade_platform_after": lg.grade_platform_after,
            "reason": lg.reason, "acted_at": str(lg.acted_at),
        }
        for lg, title, name in rows
    ]
    return ok({"items": items, "total": total, "page": page, "size": size},
              trace_id=new_trace_id())
