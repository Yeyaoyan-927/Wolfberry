"""商品服务：创建、上传图片、列表与详情。"""
from __future__ import annotations

import datetime as dt
import random
import string

from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.domain.optimize import grade_gap
from app.models.product import (
    STATUS_OFF_SHELF,
    STATUS_ON_SHELF,
    STATUS_PENDING,
    STATUS_REJECTED,
    Product,
    ProductImage,
)
from app.models.sys import ROLE_SELLER, SQ_LABELS, SQ_VERIFIED, SysUser
from app.repositories.product import ProductRepo
from app.schemas.product import ImageOut, ProductCreateIn, ProductOut
from app.services import upload_service


def _new_product_no() -> str:
    token = "".join(random.choices(string.digits, k=4))
    return f"GQ{dt.date.today():%Y%m%d}{token}"


def create_product(session: Session, *, seller: SysUser, payload: ProductCreateIn) -> Product:
    """发布商品：卖家必须已完成资质认证。

    为什么卡在这里而不是注册时：注册只是开账号，资质是平台对"谁能供货"的审核，
    未认证卖家可以先浏览、可以提交资质，但不能把商品送进审核队列。
    """
    if seller.role != ROLE_SELLER:
        raise BizError(Err.FORBIDDEN, "仅卖家可发布商品")
    if seller.seller_status != SQ_VERIFIED:
        raise BizError(
            Err.FORBIDDEN,
            f"请先完成卖家资质认证（当前：{SQ_LABELS.get(seller.seller_status, '未认证')}）",
        )

    repo = ProductRepo(session)

    product_no = _new_product_no()
    for _ in range(3):
        if repo.by_no(product_no) is None:
            break
        product_no = _new_product_no()
    else:
        raise BizError(Err.CONFLICT, "商品编号生成冲突，请重试")

    product = Product(
        product_no=product_no,
        seller_id=seller.id,
        title=payload.title,
        variety=payload.variety,
        origin=payload.origin,
        spec_per_50g=payload.spec_per_50g,
        grade_claim=payload.grade_claim,
        unit_price=payload.unit_price,
        stock=payload.stock,
        min_order_qty=payload.min_order_qty,
        description=payload.description,
        status=STATUS_PENDING,  # 提交即进入待审核；AI 评估异步补写
    )
    return repo.add(product)


def add_product_image(
    session: Session,
    *,
    product: Product,
    data: bytes,
    filename: str,
    content_type: str,
) -> ProductImage:
    stored, l1_status, l1_detail = upload_service.save_image(data, filename, content_type)

    repo = ProductRepo(session)
    existing = repo.images(product.id)
    image = ProductImage(
        product_id=product.id,
        object_key=stored.key,
        # COS：完整签名 URL；本地：相对路径 /files/{key}（前端经代理同源访问，不绑定域名端口）
        url=stored.url,
        file_name=filename,
        content_type=stored.content_type,
        size=stored.size,
        width=int(l1_detail.get("width") or 0),
        height=int(l1_detail.get("height") or 0),
        sort=len(existing),
        l1_status=l1_status,
        l1_detail=l1_detail,
    )
    repo.add_image(image)

    # 首图自动作为封面
    if not product.cover_key:
        product.cover_key = stored.key
        product.cover_url = image.url

    return image


def to_out(product: Product, images: list[ProductImage]) -> ProductOut:
    data = ProductOut.model_validate(product)
    data.images = [ImageOut.model_validate(img) for img in images]
    data.grade_diff = grade_gap(product.grade_claim, product.ai_grade)
    return data


def get_detail(session: Session, product_id: int) -> ProductOut:
    repo = ProductRepo(session)
    product = repo.detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    out = to_out(product, list(repo.images(product_id)))
    # 驳回原因（卖家在"我的商品"可见；只取最新一条，审核记录本身不可删）
    if product.status == STATUS_REJECTED:
        from sqlalchemy import select

        from app.models.audit import ACT_REJECT, AuditLog

        out.reject_reason = session.scalar(
            select(AuditLog.reason)
            .where(AuditLog.product_id == product_id, AuditLog.action == ACT_REJECT)
            .order_by(AuditLog.id.desc())
            .limit(1)
        ) or ""
    return out


def list_mine(session: Session, *, seller_id: int, page: int = 1, size: int = 20) -> tuple[list[ProductOut], int]:
    """卖家：我发布的商品（全部状态）。"""
    repo = ProductRepo(session)
    rows, total = repo.search(seller_id=seller_id, offset=(page - 1) * size, limit=size)
    return [to_out(r, list(repo.images(r.id))) for r in rows], total


def set_shelf(session: Session, *, product_id: int, seller_id: int, on_shelf: bool) -> Product:
    """上下架：下架（3→5）/ 重新提交（5→1 待审核）。

    已上架商品改图改级必须重新审核（架构底线），重新提交走待审核。
    """
    repo = ProductRepo(session)
    product = repo.detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    if product.seller_id != seller_id:
        raise BizError(Err.FORBIDDEN, "只能操作自己的商品")

    if on_shelf:
        if product.status != STATUS_OFF_SHELF:
            raise BizError(Err.PARAM_INVALID, "仅已下架商品可重新提交")
        product.status = STATUS_PENDING
    else:
        if product.status != STATUS_ON_SHELF:
            raise BizError(Err.PARAM_INVALID, "仅在售商品可下架")
        product.status = STATUS_OFF_SHELF
    session.flush()
    return product


def list_products(
    session: Session,
    *,
    page: int = 1,
    size: int = 20,
    keyword: str | None = None,
    variety: str | None = None,
    grade: str | None = None,
    origin: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    only_on_shelf: bool = True,
    order_by: str = "newest",
) -> tuple[list[ProductOut], int]:
    repo = ProductRepo(session)
    rows, total = repo.search(
        status=STATUS_ON_SHELF if only_on_shelf else None,
        keyword=keyword,
        variety=variety,
        grade=grade,
        origin=origin,
        min_price=min_price,
        max_price=max_price,
        offset=(page - 1) * size,
        limit=size,
        order_by=order_by,
    )
    items = [to_out(row, list(repo.images(row.id))) for row in rows]
    return items, total
