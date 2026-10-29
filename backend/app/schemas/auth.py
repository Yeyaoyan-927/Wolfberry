"""鉴权相关 DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=64)


class RegisterIn(BaseModel):
    """注册：买家/卖家分流。管理员不接受自助注册。"""

    username: str = Field(min_length=4, max_length=32, pattern="^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)
    role: str = Field(description="buyer | seller")
    display_name: str = Field("", max_length=64)
    org_name: str = Field("", max_length=128, description="卖家必填：企业/合作社名称")
    contact_phone: str = Field("", max_length=24)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    org_name: str = ""
    seller_status: int = 0
    seller_status_label: str = ""

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
