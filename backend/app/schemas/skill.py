"""Skill（工具）DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PriceSuggestIn(BaseModel):
    variety: str
    grade: str
    origin: str
    spec_per_50g: int = 280
    quantity_kg: float = Field(500, gt=0, le=1_000_000)
    current_price: float | None = Field(None, gt=0, description="卖家当前拟定价，用于偏离度测算")


class PriceTier(BaseModel):
    name: str          # 走量 / 适中 / 溢价
    price_low: float
    price_high: float
    strategy: str


class PriceSuggestOut(BaseModel):
    variety: str
    grade: str
    origin: str
    sample_size: int
    market_avg: float
    market_p25: float
    market_p75: float
    tiers: list[PriceTier]
    deviation_pct: float | None = None
    deviation_level: str | None = None   # 正常 / 偏高 / 明显偏高 / 偏低
    basis: list[str]
    disclaimer: str


class OptimizeIssue(BaseModel):
    code: str
    severity: str        # high / medium / low
    title: str
    detail: str
    action: str
    expected_effect: str


class OptimizeOut(BaseModel):
    product_id: int
    risk_level: str
    summary: str
    issues: list[OptimizeIssue]
    disclaimer: str
