"""订单与库存数据访问。"""
from __future__ import annotations

import datetime as dt
import random
import string

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.product import Product


def _new_order_no() -> str:
    token = "".join(random.choices(string.digits, k=6))
    return f"OD{dt.datetime.now():%Y%m%d%H%M}{token}"


class OrderRepo:
    def __init__(self, session: Session):
        self.session = session

    # ---------- 基础 ----------
    def add(self, order: Order) -> Order:
        for _ in range(3):
            order.order_no = _new_order_no()
            if self.by_no(order.order_no) is None:
                self.session.add(order)
                self.session.flush()
                return order
        raise RuntimeError("订单号生成冲突")

    def by_id(self, order_id: int) -> Order | None:
        return self.session.get(Order, order_id)

    def by_no(self, order_no: str) -> Order | None:
        return self.session.scalar(select(Order).where(Order.order_no == order_no))

    # ---------- 库存冻结（原子操作，防超卖） ----------
    @staticmethod
    def freeze_stock(session: Session, product_id: int, quantity) -> bool:
        """可售库存足量则原子扣减，返回是否成功。

        条件更新：stock >= quantity 才扣，避免读-改-写竞态。
        """
        res = session.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)
            .values(stock=Product.stock - quantity)
        )
        return res.rowcount > 0

    @staticmethod
    def restore_stock(session: Session, product_id: int, quantity) -> None:
        session.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(stock=Product.stock + quantity)
        )

    # ---------- 查询 ----------
    def search(
        self,
        *,
        buyer_id: int | None = None,
        seller_id: int | None = None,
        status: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        conds = []
        if buyer_id is not None:
            conds.append(Order.buyer_id == buyer_id)
        if seller_id is not None:
            conds.append(Order.seller_id == seller_id)
        if status is not None:
            conds.append(Order.status == status)

        total = self.session.scalar(select(func.count()).select_from(Order).where(*conds)) or 0
        rows = self.session.scalars(
            select(Order).where(*conds).order_by(Order.id.desc()).offset(offset).limit(limit)
        ).all()
        return list(rows), int(total)

    # ---------- 更新 ----------
    def save(self, order: Order) -> Order:
        self.session.add(order)
        self.session.flush()
        return order
