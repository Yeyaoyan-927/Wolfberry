"""商品与图片 DTO。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator

GRADES = ("特优", "特级", "甲级", "乙级", "等外")


def _num(value: Decimal | None) -> float | None:
    """数值统一转 float 输出：避免 Decimal 被序列化成 '100.000' 字符串。"""
    return None if value is None else float(value)


class ProductCreateIn(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    variety: str = Field(min_length=1, max_length=32)
    origin: str = Field(min_length=2, max_length=64)
    spec_per_50g: int = Field(280, ge=100, le=1000)
    grade_claim: str = Field(description="卖家自述等级")
    unit_price: Decimal = Field(gt=0, le=100000)
    stock: Decimal = Field(gt=0, le=1_000_000)
    min_order_qty: Decimal = Field(50, gt=0)
    description: str = Field("", max_length=2000)

    @field_validator("grade_claim")
    @classmethod
    def _check_grade(cls, v: str) -> str:
        if v not in GRADES:
            raise ValueError(f"等级必须是 {GRADES} 之一")
        return v


class ImageOut(BaseModel):
    id: int
    url: str
    object_key: str
    file_name: str
    size: int
    l1_status: int
    l1_detail: dict | None = None

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: int
    product_no: str
    seller_id: int
    title: str
    variety: str
    origin: str
    spec_per_50g: int
    grade_claim: str
    grade_platform: str | None
    grade_diff: int | None = None
    unit_price: Decimal
    stock: Decimal
    min_order_qty: Decimal
    status: int
    description: str
    ai_grade: str | None
    rating_avg: float = 0
    review_count: int = 0
    reject_reason: str = ""
    ai_confidence: float | None
    defect_ratio: float | None
    moldy_ratio: float | None
    grain_count: int | None
    cover_url: str
    images: list[ImageOut] = []

    model_config = {"from_attributes": True}

    @field_serializer("unit_price", "stock", "min_order_qty")
    def _decimal_to_float(self, value: Decimal | None) -> float | None:
        return _num(value)


class UploadOut(BaseModel):
    key: str
    url: str
    size: int
    content_type: str
    provider: str
    expires_at: int | None = None
