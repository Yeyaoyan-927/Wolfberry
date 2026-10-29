"""商品评价服务。

与售后的边界（重要）：
    订单「已完成」才可评价；
    若该订单存在**未结案**的售后工单，暂不允许评价（等纠纷处理完再评，避免刷分/报复）；
    售后结案后仍可评价——两者互不替代，一个是纠纷处理，一个是体验反馈。
"""
from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, Err
from app.models.after_sale import AS_OPEN_STATUSES, AfterSale
from app.models.order import Order
from app.models.product import Product
from app.models.review import ProductReview
from app.models.sys import SysUser
from app.schemas.review import PendingOrder, ReviewIn, ReviewOut, ReviewSummary

logger = logging.getLogger(__name__)

GOOD_RATING = 4  # 4~5 星记为好评


def _to_out(r: ProductReview, *, hide_name: bool = False) -> ReviewOut:
    name = r.buyer_name or f"用户{r.buyer_id}"
    if r.anonymous or hide_name:
        name = name[0] + "**" if name else "匿名"
    return ReviewOut(
        id=r.id, order_id=r.order_id, order_no=r.order_no,
        product_id=r.product_id, product_title=r.product_title,
        buyer_id=r.buyer_id, buyer_name=name, seller_id=r.seller_id,
        rating=r.rating, content=r.content,
        tags=list(r.tags or []), images=list(r.images or []),
        anonymous=bool(r.anonymous), reply=r.reply,
        replied_at=str(r.replied_at or ""), created_at=str(r.created_at or ""),
    )


def _refresh_product_score(session: Session, product_id: int) -> None:
    """重算商品评分冗余字段（列表排序与详情展示都读它）。"""
    row = session.execute(
        select(func.count(ProductReview.id), func.avg(ProductReview.rating))
        .where(ProductReview.product_id == product_id)
    ).one()
    count, avg = int(row[0] or 0), row[1]
    product = session.get(Product, product_id)
    if product is not None:
        product.review_count = count
        product.rating_avg = Decimal(str(round(float(avg or 0), 2)))


def has_open_after_sale(session: Session, order_id: int) -> bool:
    n = session.scalar(
        select(func.count(AfterSale.id)).where(
            AfterSale.order_id == order_id, AfterSale.status.in_(tuple(AS_OPEN_STATUSES))
        )
    )
    return bool(n)


def create(session: Session, *, user: SysUser, order_id: int, payload: ReviewIn) -> ReviewOut:
    order = session.get(Order, order_id)
    if order is None:
        raise BizError(Err.NOT_FOUND, "订单不存在")
    if order.buyer_id != user.id:
        raise BizError(Err.FORBIDDEN, "只能评价自己购买的订单")
    if order.status != 4:
        raise BizError(Err.PARAM_INVALID, "仅已完成订单可评价，请先确认收货")
    if session.scalar(select(func.count(ProductReview.id)).where(ProductReview.order_id == order_id)):
        raise BizError(Err.PARAM_INVALID, "该订单已评价，不能重复评分")
    if has_open_after_sale(session, order_id):
        raise BizError(Err.PARAM_INVALID, "该订单有进行中的售后工单，请等待处理完成后再评价")

    r = ProductReview(
        order_id=order.id, order_no=order.order_no,
        product_id=order.product_id, product_title=order.product_title,
        buyer_id=user.id, seller_id=order.seller_id,
        buyer_name=user.display_name or user.username,
        rating=payload.rating, content=payload.content.strip(),
        tags=payload.tags or [], images=payload.images or [],
        anonymous=1 if payload.anonymous else 0,
    )
    session.add(r)
    session.flush()
    _refresh_product_score(session, order.product_id)
    logger.info("新增评价 order=%s product=%s rating=%s", order.order_no, order.product_id, payload.rating)
    return _to_out(r)


def summary(session: Session, product_id: int) -> ReviewSummary:
    rows = session.execute(
        select(ProductReview.rating, func.count(ProductReview.id))
        .where(ProductReview.product_id == product_id)
        .group_by(ProductReview.rating)
    ).all()
    dist = {i: 0 for i in range(1, 6)}
    for rating, n in rows:
        dist[int(rating)] = int(n)
    total = sum(dist.values())
    avg = round(sum(k * v for k, v in dist.items()) / total, 2) if total else 0
    # 注意：images 存 [] 时 isnot(None) 也为真，必须按 JSON 长度判断，
    # 否则"没传图的评价"会被算成带图评价
    with_images = session.scalar(
        select(func.count(ProductReview.id)).where(
            ProductReview.product_id == product_id,
            func.json_length(ProductReview.images) > 0,
        )
    ) or 0
    good = sum(v for k, v in dist.items() if k >= GOOD_RATING)
    return ReviewSummary(
        product_id=product_id, rating_avg=avg, review_count=total, dist=dist,
        with_images=int(with_images),
        good_rate=round(good / total * 100, 1) if total else 0,
    )


def list_by_product(session: Session, product_id: int, *, rating: int | None = None,
                    page: int = 1, size: int = 10) -> tuple[list[ReviewOut], int, ReviewSummary]:
    conds = [ProductReview.product_id == product_id]
    if rating:
        conds.append(ProductReview.rating == rating)
    total = session.scalar(select(func.count(ProductReview.id)).where(*conds)) or 0
    rows = session.scalars(
        select(ProductReview).where(*conds)
        .order_by(ProductReview.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return [_to_out(r) for r in rows], int(total), summary(session, product_id)


def pending_orders(session: Session, *, user: SysUser, size: int = 20) -> list[PendingOrder]:
    """待评价：已完成且未评价的订单。"""
    reviewed = select(ProductReview.order_id).scalar_subquery()
    rows = session.scalars(
        select(Order).where(
            Order.buyer_id == user.id, Order.status == 4,
            Order.id.notin_(reviewed),
        ).order_by(Order.id.desc()).limit(size)
    ).all()
    return [
        PendingOrder(
            order_id=o.id, order_no=o.order_no, product_id=o.product_id,
            product_title=o.product_title, total_amount=float(o.total_amount or 0),
            completed_at=str(o.completed_at or ""),
            has_open_after_sale=has_open_after_sale(session, o.id),
        )
        for o in rows
    ]


def mine(session: Session, *, user: SysUser, page: int = 1, size: int = 20) -> tuple[list[ReviewOut], int]:
    conds = [ProductReview.buyer_id == user.id]
    total = session.scalar(select(func.count(ProductReview.id)).where(*conds)) or 0
    rows = session.scalars(
        select(ProductReview).where(*conds)
        .order_by(ProductReview.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return [_to_out(r) for r in rows], int(total)


def for_seller(session: Session, *, user: SysUser, page: int = 1, size: int = 20) -> tuple[list[ReviewOut], int]:
    """卖家收到的评价（可按评分筛选由前端处理）。"""
    conds = [ProductReview.seller_id == user.id]
    total = session.scalar(select(func.count(ProductReview.id)).where(*conds)) or 0
    rows = session.scalars(
        select(ProductReview).where(*conds)
        .order_by(ProductReview.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return [_to_out(r) for r in rows], int(total)


def reply(session: Session, *, user: SysUser, review_id: int, content: str) -> ReviewOut:
    r = session.get(ProductReview, review_id)
    if r is None:
        raise BizError(Err.NOT_FOUND, "评价不存在")
    if r.seller_id != user.id:
        raise BizError(Err.FORBIDDEN, "只能回复自己店铺的评价")
    if len(content.strip()) < 2:
        raise BizError(Err.PARAM_INVALID, "回复内容过短")
    r.reply = content.strip()[:500]
    r.replied_at = dt.datetime.now()
    session.flush()
    return _to_out(r)
