"""卖家资质服务：提交 → 平台审核 → 回写用户认证状态。"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.models.product import STATUS_ON_SHELF, Product
from app.models.qualification import SellerQualification
from app.models.sys import (
    ROLE_SELLER,
    SQ_LABELS,
    SQ_NONE,
    SQ_PENDING,
    SQ_REJECTED,
    SQ_VERIFIED,
    SysUser,
)
from app.schemas.qualification import QualificationIn, QualificationOut

logger = logging.getLogger(__name__)


def _to_out(session: Session, q: SellerQualification, *, user: SysUser | None = None) -> QualificationOut:
    u = user or session.get(SysUser, q.user_id)
    total = session.scalar(
        select(func.count(Product.id)).where(Product.seller_id == q.user_id)
    ) or 0
    on_shelf = session.scalar(
        select(func.count(Product.id)).where(
            Product.seller_id == q.user_id, Product.status == STATUS_ON_SHELF
        )
    ) or 0
    return QualificationOut(
        id=q.id,
        user_id=q.user_id,
        username=u.username if u else "",
        company_name=q.company_name,
        credit_code=q.credit_code,
        legal_person=q.legal_person,
        origin=q.origin,
        contact_phone=q.contact_phone,
        intro=q.intro,
        licenses=list(q.licenses or []),
        status=q.status,
        status_label=SQ_LABELS.get(q.status, ""),
        reject_reason=q.reject_reason,
        created_at=str(q.created_at or ""),
        audited_at=str(q.audited_at or ""),
        products_total=int(total),
        products_on_shelf=int(on_shelf),
    )


def submit(session: Session, *, user: SysUser, payload: QualificationIn) -> QualificationOut:
    """卖家提交/重新提交资质。已认证状态下不允许重复提交。"""
    if user.role != ROLE_SELLER:
        raise BizError(Err.FORBIDDEN, "仅卖家账号需要提交资质")
    if user.seller_status == SQ_VERIFIED:
        raise BizError(Err.PARAM_INVALID, "已通过认证，无需重复提交")
    if user.seller_status == SQ_PENDING:
        raise BizError(Err.PARAM_INVALID, "资质正在审核中，请等待结果")

    # 用最新一条记录承载本次提交（保留历史记录便于追溯）
    q = SellerQualification(
        user_id=user.id,
        company_name=payload.company_name.strip(),
        credit_code=payload.credit_code.strip(),
        legal_person=payload.legal_person.strip(),
        origin=payload.origin.strip(),
        contact_phone=payload.contact_phone.strip(),
        intro=payload.intro.strip(),
        licenses=payload.licenses or [],
        status=SQ_PENDING,
    )
    session.add(q)
    user.seller_status = SQ_PENDING
    session.flush()
    logger.info("卖家资质提交 user=%s company=%s", user.username, q.company_name)
    return _to_out(session, q, user=user)


def mine(session: Session, *, user: SysUser) -> QualificationOut:
    """我的资质：返回最新一条；从未提交则返回空壳（status=未认证）。"""
    q = session.scalar(
        select(SellerQualification)
        .where(SellerQualification.user_id == user.id)
        .order_by(SellerQualification.id.desc())
        .limit(1)
    )
    if q is None:
        # 存量卖家由迁移脚本标记为已认证（历史数据没有资质记录），
        # 这里以用户表状态位为准，避免"后端放行、前端显示未认证"的不一致
        status = user.seller_status or SQ_NONE
        # 兜底分支同样要带上经营概况，否则页面会显示"0 件商品"
        total = session.scalar(
            select(func.count(Product.id)).where(Product.seller_id == user.id)
        ) or 0
        on_shelf = session.scalar(
            select(func.count(Product.id)).where(
                Product.seller_id == user.id, Product.status == STATUS_ON_SHELF
            )
        ) or 0
        return QualificationOut(
            user_id=user.id, username=user.username,
            company_name=user.org_name, contact_phone=user.phone_mask,
            status=status, status_label=SQ_LABELS.get(status, ""),
            products_total=int(total), products_on_shelf=int(on_shelf),
        )
    return _to_out(session, q, user=user)


def list_for_admin(session: Session, *, status: int | None = None,
                   page: int = 1, size: int = 20) -> tuple[list[QualificationOut], int]:
    """后台审核列表：每个卖家只取最新一条，避免同一人多次提交刷屏。"""
    latest_ids = (
        select(func.max(SellerQualification.id))
        .group_by(SellerQualification.user_id)
    ).scalar_subquery()
    conds = [SellerQualification.id.in_(latest_ids)]
    if status is not None:
        conds.append(SellerQualification.status == status)

    total = session.scalar(select(func.count()).select_from(SellerQualification).where(*conds)) or 0
    rows = session.scalars(
        select(SellerQualification).where(*conds)
        .order_by(SellerQualification.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return [_to_out(session, q) for q in rows], int(total)


def audit(session: Session, *, admin: SysUser, qid: int, approve: bool, reason: str) -> QualificationOut:
    q = session.get(SellerQualification, qid)
    if q is None:
        raise BizError(Err.NOT_FOUND, "资质记录不存在")
    if q.status != SQ_PENDING:
        raise BizError(Err.PARAM_INVALID, f"当前状态「{SQ_LABELS.get(q.status)}」不可审核")

    user = session.get(SysUser, q.user_id)
    if user is None:
        raise BizError(Err.NOT_FOUND, "卖家账号不存在")
    if not approve and len(reason.strip()) < 4:
        raise BizError(Err.PARAM_INVALID, "驳回需填写原因（至少 4 字），卖家据此补充材料")

    q.status = SQ_VERIFIED if approve else SQ_REJECTED
    q.reject_reason = "" if approve else reason.strip()[:300]
    q.audited_by = admin.id
    q.audited_at = dt.datetime.now()
    # 冗余状态回写用户表，鉴权时免 join
    user.seller_status = q.status
    session.flush()
    logger.info("资质审核 %s by=%s approve=%s", q.company_name, admin.username, approve)
    return _to_out(session, q, user=user)


def stats(session: Session) -> dict:
    rows = session.execute(
        select(SellerQualification.status, func.count(SellerQualification.id))
        .group_by(SellerQualification.status)
    ).all()
    by_status = {int(s): int(n) for s, n in rows}
    return {
        "pending": by_status.get(SQ_PENDING, 0),
        "verified": by_status.get(SQ_VERIFIED, 0),
        "rejected": by_status.get(SQ_REJECTED, 0),
        "by_status": by_status,
    }
