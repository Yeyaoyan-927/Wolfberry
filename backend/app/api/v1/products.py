"""商品接口：创建、图片上传、列表、详情。"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder

from app.api.deps import DbSession, OptionalUser, SellerUser
from app.core.config import settings
from app.core.errors import BizError, Err
from app.core.logging import new_trace_id
from app.repositories.product import ProductRepo
from app.schemas.common import ok
from app.schemas.product import ImageOut, ProductCreateIn
from app.services import assessment_service, product_service

router = APIRouter(tags=["products"])


@router.post("/products")
def create_product(payload: ProductCreateIn, seller: SellerUser, session: DbSession):
    """发布货源。图片在创建后通过 /products/{id}/images 上传。"""
    trace = new_trace_id()
    product = product_service.create_product(session, seller=seller, payload=payload)
    return ok(jsonable_encoder(product_service.to_out(product, [])), trace_id=trace)


@router.post("/products/{product_id}/images")
async def upload_product_image(
    product_id: int,
    seller: SellerUser,
    session: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """上传商品实拍图，执行 L1 前置校验（格式 / 大小 / 分辨率）。

    上传成功后异步触发图像评估（失败不阻塞，字段留空显示"评估中"）。
    """
    trace = new_trace_id()
    data = await file.read()
    if not data:
        raise BizError(Err.PARAM_INVALID, "上传内容为空")

    product = ProductRepo(session).detail(product_id)
    if product is None:
        raise BizError(Err.NOT_FOUND, "商品不存在")
    if product.seller_id != seller.id and seller.role != "admin":
        raise BizError(Err.FORBIDDEN, "只能操作自己的商品")

    image = product_service.add_product_image(
        session,
        product=product,
        data=data,
        filename=file.filename or "upload.jpg",
        content_type=file.content_type or "image/jpeg",
    )

    if settings.ASSESS_ENABLED:
        # 评估在独立 session 中执行，不影响当前请求事务
        background_tasks.add_task(assessment_service.run_assessment, product_id)

    return ok(jsonable_encoder(ImageOut.model_validate(image)), trace_id=trace)


@router.get("/products")
def list_products(
    session: DbSession,
    user: OptionalUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    variety: str | None = None,
    grade: str | None = None,
    origin: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    order_by: str = Query(
        "newest", pattern="^(newest|price_asc|price_desc|defect_asc|rating_desc)$"
    ),
    only_on_shelf: bool = Query(True, description="false 仅管理员可用"),
):
    trace = new_trace_id()
    # 数据权限：只有管理员可以查看非上架商品
    show_all = only_on_shelf is False and user is not None and user.role == "admin"
    items, total = product_service.list_products(
        session,
        page=page,
        size=size,
        keyword=keyword,
        variety=variety,
        grade=grade,
        origin=origin,
        min_price=min_price,
        max_price=max_price,
        only_on_shelf=not show_all,
        order_by=order_by,
    )
    return ok(
        {"items": jsonable_encoder(items), "total": total, "page": page, "size": size},
        trace_id=trace,
    )


@router.get("/products/mine")
def list_my_products(
    session: DbSession,
    seller: SellerUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """卖家：我发布的商品（全部状态，含待审/驳回/下架）。"""
    trace = new_trace_id()
    items, total = product_service.list_mine(session, seller_id=seller.id, page=page, size=size)
    return ok({"items": jsonable_encoder(items), "total": total, "page": page, "size": size},
              trace_id=trace)


@router.patch("/products/{product_id}/shelf")
def set_product_shelf(
    product_id: int,
    seller: SellerUser,
    session: DbSession,
    on_shelf: bool = Query(..., description="false 下架 / true 重新提交审核"),
):
    trace = new_trace_id()
    product = product_service.set_shelf(
        session, product_id=product_id, seller_id=seller.id, on_shelf=on_shelf
    )
    return ok({"id": product.id, "status": product.status}, trace_id=trace)


@router.get("/products/{product_id}")
def product_detail(product_id: int, session: DbSession):
    trace = new_trace_id()
    return ok(jsonable_encoder(product_service.get_detail(session, product_id)), trace_id=trace)
