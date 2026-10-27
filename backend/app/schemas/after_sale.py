"""售后工单 DTO。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer


class AfterSaleCreateIn(BaseModel):
    type: int = Field(ge=1, le=5, description="1质量 2数量 3与描述不符 4物流 5其他")
    reason: str = Field(min_length=5, max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=9, description="举证图 URL")
    refund_amount: Decimal = Field(Decimal("0"), ge=0, le=1_000_000)


class AfterSaleReplyIn(BaseModel):
    agree: bool
    note: str = Field("", max_length=500)


class AfterSaleResolveIn(BaseModel):
    outcome: str = Field(pattern="^(refund_buyer|support_seller|partial|closed)$")
    note: str = Field(default="", max_length=500)
    refund_amount: Decimal = Field(Decimal("0"), ge=0)


class AfterSaleLogOut(BaseModel):
    id: int
    action: str
    actor_id: int | None = None
    actor_role: str = ""
    note: str = ""
    status_after: int
    created_at: str = ""


class AfterSaleOut(BaseModel):
    id: int
    ticket_no: str
    order_id: int
    order_no: str
    product_id: int
    product_title: str
    buyer_id: int
    seller_id: int
    type: int
    type_label: str = ""
    reason: str
    evidence: list[str] = []
    refund_amount: Decimal = Decimal("0")
    status: int
    status_label: str = ""
    seller_reply: str = ""
    resolution: str = ""
    created_at: str = ""
    responded_at: str = ""
    resolved_at: str = ""
    logs: list[AfterSaleLogOut] = []

    @field_serializer("refund_amount")
    def _amount(self, v: Decimal | None) -> float:
        return float(v or 0)
