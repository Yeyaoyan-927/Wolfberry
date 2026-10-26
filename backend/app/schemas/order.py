"""订单入参/出参模型。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderCreateIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0, description="购买数量（kg）")


class ShipIn(BaseModel):
    ship_company: str = Field(min_length=1, max_length=64)
    ship_no: str = Field(min_length=1, max_length=64)


class CancelIn(BaseModel):
    reason: str = Field(default="", max_length=200)


class PayRegisterIn(BaseModel):
    voucher_key: str = Field(default="", max_length=255, description="支付凭证图片 object_key（可空，线下口头确认）")


class ShipInfo(BaseModel):
    ship_company: str = ""
    ship_no: str = ""


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    buyer_id: int
    seller_id: int
    product_id: int
    product_title: str
    unit_price: Decimal
    quantity: Decimal
    total_amount: Decimal
    status: int
    status_label: str = ""
    pay_status: int
    ship_company: str = ""
    ship_no: str = ""
    cancel_reason: str = ""
    ordered_at: object = None
    confirmed_at: object = None
    shipped_at: object = None
    completed_at: object = None
