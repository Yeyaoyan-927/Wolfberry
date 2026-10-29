"""商品评价接口。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from app.api.deps import AnyUser, DbSession
from app.core.logging import new_trace_id
from app.schemas.common import ok
from app.schemas.review import ReviewIn
from app.services import review_service

router = APIRouter(tags=["review"])


@router.post("/orders/{order_id}/review")
def create_review(order_id: int, payload: ReviewIn, session: DbSession, user: AnyUser):
    """买家对已完成订单评分（同一订单仅一次；有未结案售后时暂不可评）。"""
    trace = new_trace_id()
    out = review_service.create(session, user=user, order_id=order_id, payload=payload)
    return ok(jsonable_encoder(out), trace_id=trace)


@router.get("/products/{product_id}/reviews")
def product_reviews(
    product_id: int,
    session: DbSession,
    rating: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
):
    """商品评价列表 + 评分汇总（公开，影响购买决策）。"""
    trace = new_trace_id()
    items, total, summary = review_service.list_by_product(
        session, product_id, rating=rating, page=page, size=size
    )
    return ok({
        "items": jsonable_encoder(items), "total": total,
        "page": page, "size": size,
        "summary": jsonable_encoder(summary),
    }, trace_id=trace)


@router.get("/reviews/pending")
def pending_reviews(session: DbSession, user: AnyUser):
    """待评价订单（已完成且未评价），用于买家中心提醒。"""
    trace = new_trace_id()
    return ok(jsonable_encoder(review_service.pending_orders(session, user=user)), trace_id=trace)


@router.get("/reviews/mine")
def my_reviews(session: DbSession, user: AnyUser,
               page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    trace = new_trace_id()
    items, total = review_service.mine(session, user=user, page=page, size=size)
    return ok({"items": jsonable_encoder(items), "total": total}, trace_id=trace)


@router.get("/seller/reviews")
def seller_reviews(session: DbSession, user: AnyUser,
                   page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """卖家收到的评价。"""
    trace = new_trace_id()
    items, total = review_service.for_seller(session, user=user, page=page, size=size)
    return ok({"items": jsonable_encoder(items), "total": total}, trace_id=trace)


@router.post("/seller/reviews/{review_id}/reply")
def reply_review(review_id: int, session: DbSession, user: AnyUser,
                 content: str = Query(..., min_length=2, max_length=500)):
    """卖家回复评价（只一条，可覆盖）。"""
    trace = new_trace_id()
    out = review_service.reply(session, user=user, review_id=review_id, content=content)
    return ok(jsonable_encoder(out), trace_id=trace)
