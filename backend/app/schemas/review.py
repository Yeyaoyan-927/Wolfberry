"""商品评价 DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    content: str = Field("", max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=6)
    images: list[str] = Field(default_factory=list, max_length=6)
    anonymous: bool = False


class ReviewOut(BaseModel):
    id: int
    order_id: int
    order_no: str = ""
    product_id: int
    product_title: str = ""
    buyer_id: int
    buyer_name: str = ""
    seller_id: int = 0
    rating: int
    content: str = ""
    tags: list[str] = []
    images: list[str] = []
    anonymous: bool = False
    reply: str = ""
    replied_at: str = ""
    created_at: str = ""


class ReviewSummary(BaseModel):
    product_id: int
    rating_avg: float = 0
    review_count: int = 0
    dist: dict[int, int] = {}          # {5: 3, 4: 1, ...}
    with_images: int = 0
    good_rate: float = 0               # 4~5 星占比


class PendingOrder(BaseModel):
    order_id: int
    order_no: str
    product_id: int
    product_title: str
    total_amount: float = 0
    completed_at: str = ""
    has_open_after_sale: bool = False
