"""模型统一导出：确保 Base.metadata 收齐所有表。"""
from app.models.assessment import ProductAssessment
from app.models.audit import AuditLog
from app.models.base import TimestampMixin
from app.models.kb import KbChunk, KbDocument
from app.models.order import Order
from app.models.product import MarketQuote, Product, ProductImage
from app.models.sys import ROLE_ADMIN, ROLE_BUYER, ROLE_SELLER, SysUser

__all__ = [
    "TimestampMixin",
    "SysUser",
    "ROLE_ADMIN",
    "ROLE_BUYER",
    "ROLE_SELLER",
    "Product",
    "ProductImage",
    "MarketQuote",
    "KbDocument",
    "KbChunk",
    "ProductAssessment",
    "Order",
    "AuditLog",
]
