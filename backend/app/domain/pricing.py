"""定价规则（纯函数，无 IO、无框架依赖，可独立单测）。

输入行情样本，输出三档建议价与偏离度。LLM 不参与计算。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PriceTier:
    name: str
    price_low: float
    price_high: float
    strategy: str


@dataclass
class PriceAdvice:
    sample_size: int
    market_avg: float
    market_p25: float
    market_p75: float
    tiers: list[PriceTier] = field(default_factory=list)
    deviation_pct: float | None = None
    deviation_level: str | None = None
    basis: list[str] = field(default_factory=list)


def _r(value: float) -> float:
    return round(float(value), 2)


def deviation_level(pct: float) -> str:
    if pct > 10:
        return "明显偏高"
    if pct > 3:
        return "偏高"
    if pct < -10:
        return "明显偏低"
    if pct < -3:
        return "偏低"
    return "正常"


def build_advice(
    prices: list[float],
    *,
    current_price: float | None = None,
    source_note: str = "平台近 30 天成交",
) -> PriceAdvice | None:
    """prices 为空表示样本不足，返回 None 由上层给兜底话术。"""
    if not prices:
        return None

    arr = np.asarray(prices, dtype=float)
    avg = float(arr.mean())
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))

    # 三档：走量（低于市场）/ 适中（主流成交区间）/ 溢价（高于市场但有品质支撑）
    tier_low = PriceTier(
        name="走量",
        price_low=_r(max(p25 * 0.95, avg * 0.88)),
        price_high=_r(p25),
        strategy="低于主流区间，适合大批量快速出货",
    )
    tier_mid = PriceTier(
        name="适中",
        price_low=_r(p25),
        price_high=_r(p75),
        strategy="落在主流成交区间，审核与成交概率最高",
    )
    tier_high = PriceTier(
        name="溢价",
        price_low=_r(p75),
        price_high=_r(p75 * 1.10),
        strategy="高于主流区间，需要有更低的缺陷率或更好的卖相支撑",
    )

    advice = PriceAdvice(
        sample_size=int(arr.size),
        market_avg=_r(avg),
        market_p25=_r(p25),
        market_p75=_r(p75),
        tiers=[tier_low, tier_mid, tier_high],
    )

    if current_price:
        pct = (current_price - avg) / avg * 100
        advice.deviation_pct = _r(pct)
        advice.deviation_level = deviation_level(pct)

    advice.basis = [
        f"样本量 {arr.size} 条，均价 {_r(avg)} 元/kg，主流区间 {_r(p25)}~{_r(p75)} 元/kg",
        f"数据来源：{source_note}，已剔除偏离中位数 3 倍以上的异常值",
    ]
    if advice.deviation_pct is not None:
        advice.basis.append(
            f"当前拟定价偏离均价 {advice.deviation_pct:+.1f}%（{advice.deviation_level}）"
        )
    return advice


def filter_outliers(prices: list[float], factor: float = 3.0) -> list[float]:
    """剔除 extreme 值，避免个别异常高价把均价拉偏。"""
    if len(prices) < 4:
        return prices
    arr = np.asarray(prices, dtype=float)
    median = float(np.median(arr))
    if median <= 0:
        return prices
    lower, upper = median / factor, median * factor
    return [p for p in prices if lower <= p <= upper]
