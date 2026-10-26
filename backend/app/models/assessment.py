"""图像评估明细：逐图检测记录，永久保留作纠纷举证。

产品冗余字段（ai_grade 等）只是摘要，明细与原始输出在这里，
带 model_version + threshold_version，保证判定可复现。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin


class ProductAssessment(Base, TimestampMixin):
    __tablename__ = "product_assessment"
    __table_args__ = (Index("idx_asmt_product", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    image_id: Mapped[int] = mapped_column(Integer, nullable=False)

    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_version: Mapped[str] = mapped_column(String(32), nullable=False)

    grain_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    moldy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bad: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    oily: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impurity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=0, nullable=False)

    valid: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 有效 0 剔除
    exclude_reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    raw_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 本轮评估完成时间（供前端显示"评估中/完成于 xx"）
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
