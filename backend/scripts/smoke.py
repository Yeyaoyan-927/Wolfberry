"""端到端冒烟：健康检查 / 鉴权 / 商品 / 存储 / 两个 Skill / RAG 全链路。

用法：python scripts/smoke.py
"""
from __future__ import annotations

import io
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap.app_factory import create_app  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def make_png(width: int = 1200, height: int = 900) -> bytes:
    """无依赖生成一张合法 PNG（纯色），用于验证上传与分辨率门禁。"""

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes([188, 58, 46]) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    setup_logging("WARNING")
    app = create_app()
    client = TestClient(app)

    print("\n== 1. 健康检查 ==")
    r = client.get("/api/v1/health")
    check("健康检查 200", r.status_code == 200, r.text)
    health = r.json()["data"]
    print("  ", json.dumps(health, ensure_ascii=False))
    check("数据库可用", health["db"] == "up")
    print(f"    存储驱动: {health['storage']['driver']}")

    print("\n== 2. 登录 ==")
    r = client.post("/api/v1/auth/login", json={"username": "seller1", "password": "seller123"})
    check("卖家登录", r.status_code == 200, r.text)
    seller_token = r.json()["data"]["access_token"]
    seller_headers = {"Authorization": f"Bearer {seller_token}"}

    r = client.post("/api/v1/auth/login", json={"username": "buyer1", "password": "buyer123"})
    buyer_token = r.json()["data"]["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    r = client.post("/api/v1/auth/login", json={"username": "seller1", "password": "wrongpwd"})
    check("错误密码被拒绝", r.status_code == 401, r.text)

    print("\n== 3. 商品创建 ==")
    product_payload = {
        "title": "中宁宁杞5号 特级 280粒/50g 2026 新货 产地直发",
        "variety": "宁杞5号",
        "origin": "中宁",
        "spec_per_50g": 280,
        "grade_claim": "特级",
        "unit_price": 46.2,
        "stock": 1200,
        "min_order_qty": 50,
        "description": "2026 年 7 月采摘，自然晾晒后人工挑选，含水率 12.4%。",
    }
    r = client.post("/api/v1/products", json=product_payload, headers=seller_headers)
    check("创建商品", r.status_code == 200, r.text)
    product = r.json()["data"]
    pid = product["id"]
    print(f"    商品编号 {product['product_no']} 等级 {product['grade_claim']}")

    r = client.post("/api/v1/products", json=product_payload, headers=buyer_headers)
    check("买家不能发布货源", r.status_code == 403, r.text)

    print("\n== 4. 图片上传（对象存储） ==")
    r = client.post(
        f"/api/v1/products/{pid}/images",
        files={"file": ("goji-01.png", io.BytesIO(make_png()), "image/png")},
        headers=seller_headers,
    )
    check("上传商品图", r.status_code == 200, r.text)
    uploaded = r.json()["data"]
    print(f"    url={uploaded['url'][:86]}...")
    print(f"    key={uploaded['object_key']}")
    check("图片 URL 可访问", uploaded["url"].startswith("http") or uploaded["url"].startswith("/"))

    import httpx as _httpx

    ext = _httpx.get(uploaded["url"], timeout=20)
    check("上传后可读取（对象存储）", ext.status_code == 200, f"status={ext.status_code}")

    r = client.post(
        f"/api/v1/products/{pid}/images",
        files={"file": ("small.png", io.BytesIO(make_png(400, 300)), "image/png")},
        headers=seller_headers,
    )
    check("低分辨率图被拦截", r.status_code == 400, r.text)

    print("\n== 5. Skill：定价建议 ==")
    r = client.post(
        "/api/v1/skills/price-suggest",
        json={
            "variety": "宁杞5号",
            "grade": "特级",
            "origin": "中宁",
            "spec_per_50g": 280,
            "quantity_kg": 500,
            "current_price": 46.2,
        },
        headers=seller_headers,
    )
    check("定价建议", r.status_code == 200, r.text)
    price = r.json()["data"]["data"]
    print(
        f"    样本 {price['sample_size']} 均价 {price['market_avg']} "
        f"三档 {[t['name'] for t in price['tiers']]} 偏离 {price['deviation_pct']}%"
    )
    check("三档建议生成", len(price["tiers"]) == 3)
    check("偏离度已计算", price["deviation_pct"] is not None)

    r = client.post(
        "/api/v1/skills/price-suggest",
        json={"variety": "不存在品种", "grade": "特级", "origin": "中宁"},
        headers=buyer_headers,
    )
    check("买家无权调用定价 Skill", r.status_code == 403, r.text)

    print("\n== 6. Skill：商品优化建议 ==")
    r = client.get(f"/api/v1/skills/products/{pid}/optimize", headers=seller_headers)
    check("优化建议（新商品，仅图片项）", r.status_code == 200, r.text)
    print("    issues:", [i["code"] for i in r.json()["data"]["data"]["issues"]])

    print("\n== 7. RAG：文档上传入库 ==")
    doc_md = (
        "# 宁杞5号品种说明\n\n"
        "宁杞5号果实呈长椭圆形，鲜果千粒重约 560 克，干果多糖含量 3.2% 以上。\n\n"
        "## 适种区域\n\n适种于宁夏中宁、甘肃靖远等地，青海诺木洪产区种植时果径偏大、油果比例上升。\n\n"
        "## 与宁杞7号的差异\n\n宁杞7号果型更大但油果率偏高，宁杞5号风味更均衡，鲜食与干果两用。\n"
    )
    r = client.post(
        "/api/v1/kb/documents",
        files={"file": ("ningqi5.md", io.BytesIO(doc_md.encode("utf-8")), "text/markdown")},
        data={"title": "宁杞5号品种说明", "doc_type": "other"},
        headers=seller_headers,
    )
    check("文档上传入库", r.status_code == 200, r.text)
    doc = r.json()["data"]
    print(f"    文档 {doc['doc_no']} 切片 {doc['chunk_count']} 策略 {doc['chunk_strategy']}")
    check("切片数大于 0", doc["chunk_count"] > 0)

    print("\n== 8. RAG：检索 ==")
    r = client.post(
        "/api/v1/kb/search", json={"query": "宁杞5号和宁杞7号有什么区别", "top_k": 3}, headers=seller_headers
    )
    check("语义检索", r.status_code == 200, r.text)
    hits = r.json()["data"]["hits"]
    print(f"    命中 {len(hits)} 条，最高分 {hits[0]['score'] if hits else 0}")
    check("检索有结果", len(hits) > 0)

    print("\n== 9. RAG：问答 ==")
    r = client.post(
        "/api/v1/kb/ask",
        json={"question": "特级的判定标准是什么？", "top_k": 4},
        headers=seller_headers,
    )
    check("RAG 问答", r.status_code == 200, r.text)
    ask = r.json()["data"]
    print(f"    模式 {ask['mode']} 引用 {len(ask['citations'])} 条")
    print(f"    回答：{ask['answer'][:120]}")
    check("回答带引用", len(ask["citations"]) > 0)

    print("\n== 10. RAG：效果评估 ==")
    r = client.get("/api/v1/kb/eval?k=5", headers=seller_headers)
    check("评测接口", r.status_code == 200, r.text)
    report = r.json()["data"]
    print(f"    Recall@{report['k']} = {report['recall_at_k']}  MRR = {report['mrr']}  provider = {report['provider']}")
    check("Recall@5 >= 0.75", report["recall_at_k"] >= 0.75, f"实际 {report['recall_at_k']}")

    print("\n" + "=" * 46)
    print(f"通过 {PASS} / 失败 {FAIL}")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
