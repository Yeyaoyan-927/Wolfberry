"""卖家资质 DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class QualificationIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=128)
    credit_code: str = Field("", max_length=32, description="统一社会信用代码")
    legal_person: str = Field("", max_length=64)
    origin: str = Field("", max_length=64)
    contact_phone: str = Field("", max_length=24)
    intro: str = Field("", max_length=1000)
    licenses: list[str] = Field(default_factory=list, max_length=6, description="证件图 URL")


class QualAuditIn(BaseModel):
    approve: bool
    reason: str = Field("", max_length=300)


class QualificationOut(BaseModel):
    id: int | None = None
    user_id: int
    username: str = ""
    company_name: str = ""
    credit_code: str = ""
    legal_person: str = ""
    origin: str = ""
    contact_phone: str = ""
    intro: str = ""
    licenses: list[str] = []
    status: int = 0
    status_label: str = ""
    reject_reason: str = ""
    created_at: str = ""
    audited_at: str = ""
    # 卖家经营概况（后台审核时参考）
    products_total: int = 0
    products_on_shelf: int = 0
