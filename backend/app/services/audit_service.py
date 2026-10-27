"""审核工作台服务：队列、详情、通过/驳回/改级，差异标记快照落库。"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.domain.grading import DIFF_GRAY, diff_flag
from app.domain.optimize import grade_gap
from app.models.audit import ACT_APPROVE, ACT_GRADE, ACT_REJECT, AuditLog
from app.models.product import STATUS_ON_SHELF, STATUS_PENDING, STATUS_REJECTED, Product
from app.models.sys import SysUser
from app.repositories.product import ProductRepo

logger = logging.getLogger(__name__)

# 队列排序权重：红（高报≥2级）最优先，其次黄、灰，蓝绿最后
_FLAG_ORDER = {"红": 0, "黄": 1, "灰": 2, "蓝": 3, "绿": 4}


def _snapshot(product: Product) -> dict:
    """审核时的差异上下文快照。"""
    conf = float(product.ai_confidence) if product.ai_confidence is not None else None
    flag = diff_flag(product.grade_claim, product.ai_grade, conf)
    return {
        "grade_claim": product.grade_claim or "",
        "ai_grade": product.ai_grade or "",
        "grade_platform_before": product.grade_platform or "",
        "diff_flag": flag,
        "gap": grade_gap(product.grade_claim, product.ai_grade),
    }


def _flag_of(product: Product) -> str:
    conf = float(product.ai_confidence) if product.ai_confidence is not None else None
    return diff_flag(product.grade_claim, product.ai_grade, conf)


def seller_risk_stats(session: Session, seller_id: int) -> dict:
    """卖家近 30 天审核风险画像：红标次数 / 驳回次数 / 提交数。"""
    since = dt.datetime.now() - dt.timedelta(days=30)
    red = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .join(Product, Product.id == AuditLog.product_id)
        .where(Product.seller_id == seller_id, AuditLog.diff_flag == "红",
               AuditLog.acted_at >= since)
    ) or 0
    rejected = session.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.seller_id == seller_id, Product.status == STATUS_REJECTED)
    ) or 0
    total = session.scalar(
        select(func.count()).select_from(Product).where(Product.seller_id == seller_id)
    ) or 0
    return {"red_flags_30d": int(red), "rejected_total": int(rejected), "products_total": int(total),
            "risk_warn": int(red) >= 3}


def audit_queue(session: Session, *, flag: str | None = None,
                page: int = 1, size: int = 20) -> tuple[list[dict], int]:
    """待审核队列：按差异严重度排序（红优先）。"""
    conds = [Product.status == STATUS_PENDING]
    rows = session.scalars(
        select(Product).where(*conds).order_by(Product.id.desc()).limit(500)
    ).all()

    items = []
    for p in rows:
        flag_now = _flag_of(p)
        if flag and flag_now != flag:
            continue
        items.append({
            "id": p.id,
            "product_no": p.product_no,
            "title": p.title,
            "seller_id": p.seller_id,
            "cover_url": p.cover_url or "",
            "grade_claim": p.grade_claim,
            "ai_grade": p.ai_grade,
            "ai_confidence": float(p.ai_confidence) if p.ai_confidence is not None else None,
            "defect_ratio": float(p.defect_ratio) if p.defect_ratio is not None else None,
            "diff_flag": flag_now,
            "assessing": p.ai_grade is None and p.grain_count is None,
        })
    # 红黄优先：无 AI 结果（灰）排中，蓝绿最后
    items.sort(key=lambda x: _FLAG_ORDER.get(x["diff_flag"], 9))
    total = len(items)
    return items[(page - 1) * size: page * size], total


def audit_detail(session: Session, product_id: int) -> dict:
    """审核详情：商品字段 + 图片 + AI 评估明细 + 卖家风险画像 + 历史审核记录。"""
    repo = ProductRepo(session)
    product = repo.detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")

    images = [
        {"id": im.id, "url": im.url, "file_name": im.file_name, "l1_status": im.l1_status,
         "width": im.width, "height": im.height}
        for im in repo.images(product_id)
    ]

    from app.models.assessment import ProductAssessment
    assessments = session.scalars(
        select(ProductAssessment)
        .where(ProductAssessment.product_id == product_id)
        .order_by(ProductAssessment.image_id)
    ).all()
    assessment_rows = [
        {"image_id": a.image_id, "model_version": a.model_version,
         "threshold_version": a.threshold_version, "grain_count": a.grain_count,
         "moldy": a.moldy, "bad": a.bad, "oily": a.oily, "impurity": a.impurity,
         "image_confidence": float(a.image_confidence), "valid": bool(a.valid),
         "exclude_reason": a.exclude_reason, "raw": a.raw_result or {}}
        for a in assessments
    ]

    logs = session.scalars(
        select(AuditLog).where(AuditLog.product_id == product_id).order_by(AuditLog.id.desc())
    ).all()
    log_rows = [
        {"id": lg.id, "action": lg.action, "auditor_id": lg.auditor_id,
         "grade_claim": lg.grade_claim, "ai_grade": lg.ai_grade,
         "grade_platform_after": lg.grade_platform_after, "diff_flag": lg.diff_flag,
         "reason": lg.reason, "acted_at": lg.acted_at}
        for lg in logs
    ]

    snap = _snapshot(product)
    snap = _snapshot(product)

    # 行情参考（近 30 天同品种/等级成交）
    from app.repositories.market import MarketRepo

    market = None
    try:
        m_rows = MarketRepo(session).recent_prices(
            variety=product.variety, grade=product.grade_claim,
            origin=product.origin if product.origin in ("中宁", "诺木洪", "靖远") else None, days=30,
        )
        if m_rows:
            prices = [float(r.price) for r in m_rows]
            avg = sum(prices) / len(prices)
            market = {
                "samples": len(prices),
                "avg_30d": round(avg, 2),
                "deviation_pct": round((float(product.unit_price) - avg) / avg * 100, 1),
                "low": min(prices), "high": max(prices),
            }
    except Exception:
        logger.warning("行情参考查询失败 product=%s", product.product_no)

    # 命中规则（阈值判定依据）
    rules = None
    if product.defect_ratio is not None:
        from app.domain.grading import rule_hits

        # 杂质率：从评估明细汇总（product 冗余字段未存 impurity）
        asmt_rows = session.scalars(
            select(ProductAssessment).where(ProductAssessment.product_id == product_id)
        ).all()
        total_grains = sum(a.grain_count for a in asmt_rows) or 1
        impurity_ratio = sum(a.impurity for a in asmt_rows) / total_grains
        rules = rule_hits(
            defect_ratio=float(product.defect_ratio),
            moldy_ratio=float(product.moldy_ratio or 0),
            impurity_ratio=impurity_ratio,
        )

    return {
        "id": product.id,
        "product_no": product.product_no,
        "title": product.title,
        "seller_id": product.seller_id,
        "variety": product.variety,
        "origin": product.origin,
        "spec_per_50g": product.spec_per_50g,
        "grade_claim": product.grade_claim,
        "grade_platform": product.grade_platform,
        "ai_grade": product.ai_grade,
        "ai_confidence": float(product.ai_confidence) if product.ai_confidence is not None else None,
        "defect_ratio": float(product.defect_ratio) if product.defect_ratio is not None else None,
        "moldy_ratio": float(product.moldy_ratio) if product.moldy_ratio is not None else None,
        "grain_count": product.grain_count,
        "unit_price": float(product.unit_price),
        "stock": float(product.stock),
        "min_order_qty": float(product.min_order_qty),
        "status": product.status,
        "description": product.description,
        "created_at": str(product.created_at) if product.created_at else None,
        "images": images,
        "assessments": assessment_rows,
        "assessing": product.ai_grade is None and product.grain_count is None,
        "diff_flag": snap["diff_flag"],
        "grade_gap": snap["gap"],
        "market": market,
        "rules": rules,
        "seller_risk": seller_risk_stats(session, product.seller_id),
        "audit_logs": log_rows,
    }


def queue_stats(session: Session) -> dict:
    """队列条统计：待审核数 / 今日已审 / 30 天内驳回（超时暂无数据，置 0）。"""
    today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    pending = session.scalar(
        select(func.count()).select_from(Product).where(Product.status == STATUS_PENDING)
    ) or 0
    audited_today = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.acted_at >= today)
    ) or 0
    return {"pending": int(pending), "audited_today": int(audited_today), "overtime": 0}


def approve(session: Session, *, auditor: SysUser, product_id: int,
            grade_platform: str | None = None) -> dict:
    """通过上架。可携带修正后的平台认定等级（= 审核员改级）。

    等级最终由审核员确认（架构底线第 1 条），AI 建议只作依据；
    无 AI 结果时必须显式指定等级。
    """
    repo = ProductRepo(session)
    product = repo.detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    if product.status not in (STATUS_PENDING, STATUS_REJECTED):
        raise BizError(Err.ORDER_NOT_ALLOWED, "商品不在待审核状态")

    final_grade = grade_platform or product.ai_grade
    if not final_grade:
        raise BizError(Err.PARAM_INVALID, "AI 未产出建议等级，请显式指定平台认定等级")

    snap = _snapshot(product)
    product.grade_platform = final_grade
    product.status = STATUS_ON_SHELF
    product.published_at = dt.datetime.now()
    session.add(AuditLog(
        product_id=product_id, auditor_id=auditor.id,
        action=ACT_GRADE if grade_platform and grade_platform != product.ai_grade else ACT_APPROVE,
        grade_claim=snap["grade_claim"], ai_grade=snap["ai_grade"],
        grade_platform_before=snap["grade_platform_before"],
        grade_platform_after=final_grade, diff_flag=snap["diff_flag"],
        reason=f"审核通过，认定等级 {final_grade}", acted_at=dt.datetime.now(),
    ))
    session.flush()
    logger.info("商品 %s 审核通过 认定=%s 差异=%s", product.product_no, final_grade, snap["diff_flag"])
    return {"product_id": product_id, "status": product.status,
            "grade_platform": final_grade, "diff_flag": snap["diff_flag"]}


REJECT_REASONS = {
    "GRADE_MISMATCH": "自述等级与实拍图明显不符",
    "IMAGE_POOR": "图片模糊/光照差，无法核实品质",
    "IMAGE_STOLEN": "疑似盗图",
    "PRICE_ABNORMAL": "价格异常偏离行情",
    "TITLE_VIOLATION": "标题含违规词",
    "FAKE_ORIGIN": "产地造假嫌疑",
    "MOLDY_RISK": "可见霉变风险，禁止上架",
    "SPEC_CONFLICT": "规格参数自相矛盾",
    "DUPLICATE": "与已下架/已驳回商品重复",
    "OTHER": "其他（需补充说明）",
}


def reject(session: Session, *, auditor: SysUser, product_id: int,
           reason_code: str, note: str = "") -> dict:
    """驳回：status → 已驳回，原因必须来自枚举。"""
    if reason_code not in REJECT_REASONS:
        raise BizError(Err.PARAM_INVALID, f"驳回原因必须是以下之一：{', '.join(REJECT_REASONS)}")
    repo = ProductRepo(session)
    product = repo.detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    if product.status != STATUS_PENDING:
        raise BizError(Err.ORDER_NOT_ALLOWED, "商品不在待审核状态")

    snap = _snapshot(product)
    product.status = STATUS_REJECTED
    reason = REJECT_REASONS[reason_code] + (f"：{note}" if note else "")
    session.add(AuditLog(
        product_id=product_id, auditor_id=auditor.id, action=ACT_REJECT,
        grade_claim=snap["grade_claim"], ai_grade=snap["ai_grade"],
        grade_platform_before=snap["grade_platform_before"], grade_platform_after="",
        diff_flag=snap["diff_flag"], reason=reason, acted_at=dt.datetime.now(),
    ))
    session.flush()
    logger.info("商品 %s 驳回 原因=%s", product.product_no, reason_code)
    return {"product_id": product_id, "status": product.status, "reason": reason}


def force_reassess(session: Session, *, auditor: SysUser, product_id: int) -> dict:
    """手动触发重新评估（改图后可用）。同步执行，返回最新摘要。"""
    from app.services import assessment_service

    product = ProductRepo(session).detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    assessment_service.run_assessment(product_id)
    session.expire_all()
    return {"product_id": product_id, "ai_grade": product.ai_grade,
            "defect_ratio": float(product.defect_ratio) if product.defect_ratio is not None else None}
