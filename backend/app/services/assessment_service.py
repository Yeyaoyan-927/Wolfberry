"""图像评估服务：取图 → 逐图检测 → 汇总 → 等级映射 → 落库。

设计要点（架构底线）：
- 异步执行，失败只记日志，不阻塞商品提交与人工审核（字段留空 = 前端显示"评估中"）
- 每次全量重评：已上架商品改图/改级后再次触发同样走这里
- 明细逐图写 product_assessment（含 raw_result），摘要回填 product 冗余字段
- 自建 Session，不依赖请求级 session（BackgroundTasks 执行时请求已结束）
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select

from app.core.config import settings
from app.domain.grading import map_grade
from app.domain.visual_summary import summarize
from app.infra.db import SessionLocal
from app.infra.storage import get_storage
from app.models.assessment import ProductAssessment
from app.models.product import Product, ProductImage
from app.services import upload_service
from app.vision import get_detector

logger = logging.getLogger(__name__)


def run_assessment(product_id: int) -> None:
    """对外入口：供 BackgroundTasks / 手动重跑调用。内部捕获所有异常。"""
    try:
        _run(product_id)
    except Exception:
        logger.exception("图像评估失败 product_id=%s（不阻塞业务）", product_id)


def _run(product_id: int) -> None:
    session = SessionLocal()
    try:
        product = session.get(Product, product_id)
        if product is None:
            return
        images = session.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product_id, ProductImage.l1_status == 1)
            .order_by(ProductImage.sort)
        ).all()
        if not images:
            logger.info("评估跳过：无有效图片 product_id=%s", product_id)
            return

        detector = get_detector()
        storage = get_storage()
        session.query(ProductAssessment).filter(
            ProductAssessment.product_id == product_id
        ).delete()

        per_image = []
        for img in images:
            try:
                data = storage.get_bytes(img.object_key)
            except Exception:
                logger.exception("读取图片失败 key=%s", img.object_key)
                continue
            res = detector(data, img.id)
            c = res.counts
            session.add(
                ProductAssessment(
                    product_id=product_id,
                    image_id=img.id,
                    model_version=settings.ASSESS_MODEL_VERSION,
                    threshold_version=settings.ASSESS_THRESHOLD_VERSION,
                    grain_count=c.grain_count, moldy=c.moldy, bad=c.bad,
                    oily=c.oily, impurity=c.impurity,
                    image_confidence=c.confidence,
                    valid=1 if c.valid else 0,
                    exclude_reason=c.exclude_reason,
                    raw_result=res.raw,
                    assessed_at=dt.datetime.now(),
                )
            )
            per_image.append(c)

        summary = summarize(per_image, min_grains=settings.ASSESS_MIN_GRAINS)
        _apply_summary(product, summary)
        session.commit()
        logger.info(
            "评估完成 product_id=%s 粒数=%d 缺陷率=%.2f%% 等级=%s",
            product_id, summary.total_grains, summary.defect_ratio * 100,
            product.ai_grade or "灰",
        )
    finally:
        session.close()


def _apply_summary(product: Product, summary) -> None:
    """把样品级汇总回填商品冗余字段。无有效图时保持 None（评估中）。"""
    if summary.valid_images == 0:
        for f in ("ai_grade", "ai_confidence", "defect_ratio", "moldy_ratio", "grain_count"):
            setattr(product, f, None)
        return

    product.defect_ratio = summary.defect_ratio
    product.moldy_ratio = summary.moldy_ratio
    product.grain_count = summary.total_grains
    product.ai_confidence = summary.weighted_confidence

    result = map_grade(
        defect_ratio=summary.defect_ratio,
        moldy_ratio=summary.moldy_ratio,
        confidence=summary.weighted_confidence,
        gray_conf=settings.ASSESS_GRAY_CONF,
    )
    product.ai_grade = result.grade  # 灰线以下为 None，前端显示"AI 不参与判定"
    for reason in result.reasons:
        logger.info("等级判定 product=%s: %s", product.product_no, reason)
