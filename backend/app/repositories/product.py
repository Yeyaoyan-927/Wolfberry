"""商品与图片数据访问。

过滤条件全部下推到 SQL，不在应用层做全表遍历。
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select

from app.models.product import Product, ProductImage
from app.repositories.base import BaseRepo


class ProductRepo(BaseRepo[Product]):
    model = Product

    def by_no(self, product_no: str) -> Product | None:
        return self.session.scalar(select(Product).where(Product.product_no == product_no))

    def detail(self, product_id: int) -> Product | None:
        return self.session.scalar(select(Product).where(Product.id == product_id))

    def images(self, product_id: int) -> Sequence[ProductImage]:
        return self.session.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.sort, ProductImage.id)
        ).all()

    def add_image(self, image: ProductImage) -> ProductImage:
        self.session.add(image)
        self.session.flush()
        return image

    def search(
        self,
        *,
        status: int | None = None,
        seller_id: int | None = None,
        variety: str | None = None,
        grade: str | None = None,
        origin: str | None = None,
        keyword: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        offset: int = 0,
        limit: int = 20,
        order_by: str = "newest",
    ) -> tuple[Sequence[Product], int]:
        conds = []
        if status is not None:
            conds.append(Product.status == status)
        if seller_id is not None:
            conds.append(Product.seller_id == seller_id)
        if variety:
            conds.append(Product.variety == variety)
        if grade:
            conds.append(func.coalesce(Product.grade_platform, Product.grade_claim) == grade)
        if origin:
            conds.append(Product.origin.like(f"{origin}%"))
        if keyword:
            conds.append(Product.title.like(f"%{keyword}%"))
        if min_price is not None:
            conds.append(Product.unit_price >= min_price)
        if max_price is not None:
            conds.append(Product.unit_price <= max_price)

        total = int(self.session.scalar(select(func.count()).select_from(Product).where(*conds)) or 0)

        # MySQL 8 不支持 NULLS LAST，用「IS NULL 先排序」等效实现
        order_map: dict[str, list] = {
            "price_asc": [Product.unit_price.asc()],
            "price_desc": [Product.unit_price.desc()],
            "defect_asc": [Product.defect_ratio.is_(None), Product.defect_ratio.asc()],
            # 按评分：无评价的排在后面（NULL 先排序），再看评价数
            "rating_desc": [Product.review_count == 0, Product.rating_avg.desc(),
                            Product.review_count.desc()],
        }
        order_clauses = order_map.get(order_by, [Product.id.desc()])

        rows = self.session.scalars(
            select(Product).where(*conds).order_by(*order_clauses).offset(offset).limit(limit)
        ).all()
        return rows, total
