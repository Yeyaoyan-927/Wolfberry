"""商品服务：创建、上传图片、列表与详情。"""
from __future__ import annotations

import datetime as dt
import random
import string

from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.domain.optimize import grade_gap
from app.models.product import (
    STATUS_ON_SHELF,
    STATUS_PENDING,
    Product,
    ProductImage,
)
from app.repositories.product import ProductRepo
from app.schemas.product import ImageOut, ProductCreateIn, ProductOut
from app.services import upload_service


def _new_product_no() -> str:
    token = "".join(random.choices(string.digits, k=4))
    return f"GQ{dt.date.today():%Y%m%d}{token}"


def create_product(session: Session, *, seller_id: int, payload: ProductCreateIn) -> Product:
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
        seller_id=seller_id,
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
    base_url: str,
) -> ProductImage:
    stored, l1_status, l1_detail = upload_service.save_image(data, filename, content_type)

    repo = ProductRepo(session)
    existing = repo.images(product.id)
    image = ProductImage(
        product_id=product.id,
        object_key=stored.key,
        url=upload_service.absolutize(stored.url, base_url),
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
    return to_out(product, list(repo.images(product_id)))


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
