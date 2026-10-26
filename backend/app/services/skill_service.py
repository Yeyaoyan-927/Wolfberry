"""Skill 服务：把规则封装成可复用的业务能力。

两个 Skill：
    1. price_suggest     卖家定价建议（复用行情数据）
    2. product_optimize  商品优化建议（复用图片校验与评估摘要）

两者都是只读能力，不改任何业务数据。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.domain import optimize as optimize_domain
from app.domain import pricing as pricing_domain
from app.models.product import Product
from app.repositories.market import MarketRepo
from app.repositories.product import ProductRepo
from app.schemas.skill import (
    OptimizeIssue,
    OptimizeOut,
    PriceSuggestIn,
    PriceSuggestOut,
    PriceTier,
)

PRICE_DISCLAIMER = "以上为基于平台历史成交的参考区间，不构成定价建议，最终价格由卖家自行决定。"
OPTIMIZE_DISCLAIMER = "优化建议基于当前图片与评估数据生成，按建议调整不保证一定通过审核。"


def price_suggest(session: Session, payload: PriceSuggestIn) -> PriceSuggestOut:
    repo = MarketRepo(session)

    # 先按完整维度取样本，样本不足再逐步放宽（产区 -> 全国），并在依据里说明
    rows = repo.recent_prices(
        variety=payload.variety,
        grade=payload.grade,
        origin=payload.origin,
        spec_per_50g=payload.spec_per_50g,
        days=30,
    )
    scope_note = f"平台近 30 天成交（{payload.origin}）"

    if len(rows) < 5:
        rows = repo.recent_prices(
            variety=payload.variety,
            grade=payload.grade,
            spec_per_50g=payload.spec_per_50g,
            days=90,
        )
        scope_note = "平台近 90 天成交（全国，已放宽产区）"

    prices = pricing_domain.filter_outliers([float(r.price) for r in rows])

    advice = pricing_domain.build_advice(
        prices,
        current_price=payload.current_price,
        source_note=scope_note,
    )

    if advice is None:
        return PriceSuggestOut(
            variety=payload.variety,
            grade=payload.grade,
            origin=payload.origin,
            sample_size=0,
            market_avg=0,
            market_p25=0,
            market_p75=0,
            tiers=[],
            deviation_pct=None,
            deviation_level=None,
            basis=[f"该品类暂无成交样本：{payload.variety} / {payload.grade} / {payload.origin}"],
            disclaimer="样本不足，无法给出定价建议。建议参考当地收购点报价或咨询平台客服。",
        )

    return PriceSuggestOut(
        variety=payload.variety,
        grade=payload.grade,
        origin=payload.origin,
        sample_size=advice.sample_size,
        market_avg=advice.market_avg,
        market_p25=advice.market_p25,
        market_p75=advice.market_p75,
        tiers=[
            PriceTier(
                name=t.name,
                price_low=t.price_low,
                price_high=t.price_high,
                strategy=t.strategy,
            )
            for t in advice.tiers
        ],
        deviation_pct=advice.deviation_pct,
        deviation_level=advice.deviation_level,
        basis=advice.basis,
        disclaimer=PRICE_DISCLAIMER,
    )


def product_optimize(session: Session, product_id: int) -> OptimizeOut:
    repo = ProductRepo(session)
    product: Product | None = repo.detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")

    images = list(repo.images(product_id))
    invalid = [
        {
            "file_name": img.file_name,
            "reason": (img.l1_detail or {}).get("reason", "未通过校验"),
        }
        for img in images
        if img.l1_status == 2
    ]

    advice = optimize_domain.build_advice(
        image_count=len(images),
        invalid_images=invalid,
        max_occlusion=float((images[0].l1_detail or {}).get("occlusion", 0)) if images else 0.0,
        grade_claim=product.grade_claim,
        ai_grade=product.ai_grade,
        ai_confidence=float(product.ai_confidence) if product.ai_confidence is not None else None,
        defect_ratio=float(product.defect_ratio) if product.defect_ratio is not None else None,
        moldy_ratio=float(product.moldy_ratio) if product.moldy_ratio is not None else None,
        description_len=len(product.description or ""),
    )

    return OptimizeOut(
        product_id=product.id,
        risk_level=advice.risk_level,
        summary=advice.summary,
        issues=[
            OptimizeIssue(
                code=i.code,
                severity=i.severity,
                title=i.title,
                detail=i.detail,
                action=i.action,
                expected_effect=i.expected_effect,
            )
            for i in advice.issues
        ],
        disclaimer=OPTIMIZE_DISCLAIMER,
    )
