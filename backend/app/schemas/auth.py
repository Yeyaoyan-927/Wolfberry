"""鉴权相关 DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    org_name: str = ""

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
