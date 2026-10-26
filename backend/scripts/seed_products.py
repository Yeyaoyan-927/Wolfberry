"""创建演示商品并上传真实图片（AI 生成的枸杞商品图）。

用法：python scripts/seed_products.py
说明：商品上的 ai_grade / defect_ratio 等字段是演示用预置评估值，
     真实环境由图像评估流水线写入，此处仅用于演示「等级差异标记」功能。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap.app_factory import create_app  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.infra.db import SessionLocal  # noqa: E402
from app.models.product import STATUS_ON_SHELF  # noqa: E402
from app.repositories.product import ProductRepo  # noqa: E402

# 图片来源：用户自备素材（docs/飞浆gouqi，185 张）；备选 Wikimedia CC 图见 seed_assets/web
ASSETS_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "docs" / "飞浆gouqi",
    Path(__file__).resolve().parent / "seed_assets" / "web",
]
ASSETS = next((p for p in ASSETS_CANDIDATES if p.exists()), ASSETS_CANDIDATES[-1])

PRODUCTS = [
    {
        "seller": "seller1",
        "payload": {
            "title": "中宁宁杞5号 特级 280粒/50g 2026 新货 产地直发",
            "variety": "宁杞5号",
            "origin": "中宁",
            "spec_per_50g": 280,
            "grade_claim": "特级",
            "unit_price": 46.2,
            "stock": 1200,
            "min_order_qty": 50,
            "description": "2026 年 7 月采摘，自然晾晒后人工挑选，果形偏长色泽深红，含水率 12.4%，支持寄样。",
        },
        # 真实图片：Wikimedia Commons（CC BY-SA），来源见 seed_assets/web/SOURCES.json
        "images": ["cgcjyfyj (7).jpg", "cgcjyfyj (37).jpg"],
        "ai": {"ai_grade": "特级", "ai_confidence": 0.78,
               "defect_ratio": 0.021, "moldy_ratio": 0.001, "grain_count": 742},
    },
    {
        "seller": "seller2",
        "payload": {
            "title": "诺木洪宁杞7号 特优 220粒 大颗粒礼盒装",
            "variety": "宁杞7号",
            "origin": "诺木洪",
            "spec_per_50g": 220,
            "grade_claim": "特优",
            "unit_price": 52.0,
            "stock": 800,
            "min_order_qty": 100,
            "description": "青海柴达木产区，日照充足果肉厚实，适合礼盒与直接食用，含水率 11.8%。",
        },
        "images": ["cgcjyfyj (69).jpg"],
        # 演示：自述特优，评估甲级（高报 1 级）——用于展示黄色差异标记
        "ai": {"ai_grade": "甲级", "ai_confidence": 0.66,
               "defect_ratio": 0.032, "moldy_ratio": 0.002, "grain_count": 528},
    },
]


def main() -> None:
    setup_logging("WARNING")
    app = create_app()
    client = TestClient(app)

    # 登录卖家
    tokens = {}
    for name in ("seller1", "seller2"):
        r = client.post("/api/v1/auth/login", json={"username": name, "password": "seller123"})
        tokens[name] = r.json()["data"]["access_token"]

    for spec in PRODUCTS:
        headers = {"Authorization": f"Bearer {tokens[spec['seller']]}"}

        # 同标题已存在则跳过（幂等）
        r = client.get(
            "/api/v1/products",
            params={"keyword": spec["payload"]["title"][:20], "size": 5},
        )
        if any(item["title"] == spec["payload"]["title"] for item in r.json()["data"]["items"]):
            print(f"  跳过（已存在）：{spec['payload']['title'][:24]}")
            continue

        r = client.post("/api/v1/products", json=spec["payload"], headers=headers)
        r.raise_for_status()
        product = r.json()["data"]
        pid = product["id"]

        for img_name in spec["images"]:
            path = ASSETS / img_name
            if not path.exists():
                print(f"  [警告] 演示图缺失：{img_name}")
                continue
            r = client.post(
                f"/api/v1/products/{pid}/images",
                files={"file": (img_name, path.read_bytes(), "image/png")},
                headers=headers,
            )
            r.raise_for_status()

        # 预置评估值（演示用）
        session = SessionLocal()
        product_row = ProductRepo(session).detail(pid)
        for key, value in spec["ai"].items():
            setattr(product_row, key, value)
        product_row.status = STATUS_ON_SHELF
        session.commit()
        session.close()

        print(f"  商品 {product_row.product_no}：{product_row.title[:22]}  自述 {product_row.grade_claim} / AI {product_row.ai_grade}")

    print("完成")


if __name__ == "__main__":
    main()
