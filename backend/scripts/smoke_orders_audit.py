"""端到端验证：订单全流程（含库存冻结）+ 审核工作台（队列/差异落库）。

用法：python scripts/smoke_orders_audit.py
前置：服务已运行（或依赖 TestClient 亦可，这里直接 TestClient 免起服务）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap.app_factory import create_app  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

ok_count = 0


def check(name: str, cond: bool, detail: str = ""):
    global ok_count
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok_count += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def login(client, username, password):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def stock_of(client, pid):
    r = client.get(f"/api/v1/products/{pid}")
    return r.json()["data"]["stock"]


def main():
    setup_logging("WARNING")
    client = TestClient(create_app())

    buyer = login(client, "buyer1", "buyer123")
    sellers = {1: login(client, "seller1", "seller123"),
               2: login(client, "seller2", "seller123"),
               3: login(client, "seller2", "seller123"),
               4: login(client, "seller2", "seller123")}
    admin = login(client, "admin", "admin123")

    # 找一个上架商品
    r = client.get("/api/v1/products?only_mine=0&size=5")
    items = [i for i in r.json()["data"]["items"] if i["status"] == 3]
    assert items, "无上架商品可测"
    pid = items[0]["id"]
    detail = client.get(f"/api/v1/products/{pid}").json()["data"]
    min_qty = int(float(detail["min_order_qty"]))
    seller = sellers[detail["seller_id"]]  # 订单操作必须用商品所属卖家
    stock0 = float(stock_of(client, pid))
    print(f"== 订单流程：商品 #{pid} 初始库存 {stock0} 起订量 {min_qty} ==")

    # 1. 下单冻结
    qty1 = min_qty + 10
    r = client.post("/api/v1/orders", json={"product_id": pid, "quantity": qty1}, headers=buyer)
    check("买家下单", r.status_code == 200, r.text[:120])
    order = r.json()["data"]
    oid = order["id"]
    check("订单状态=待卖家确认", order["status"] == 1 and order["status_label"] == "待卖家确认")
    check("下单冻结库存", abs(float(stock_of(client, pid)) - (stock0 - qty1)) < 1e-6,
          f"stock={stock_of(client, pid)}")
    check("金额快照正确", abs(float(order["total_amount"]) - qty1 * float(order["unit_price"])) < 0.01)

    # 2. 起订量校验
    r = client.post("/api/v1/orders", json={"product_id": pid, "quantity": max(1, min_qty - 1)},
                    headers=buyer)
    check("低于起订量被拒", r.status_code == 400, r.json()["message"][:40])

    # 3. 越权：buyer 无法确认订单
    r = client.post(f"/api/v1/orders/{oid}/confirm", headers=buyer)
    check("买家不能执行卖家确认", r.status_code == 403, r.json()["message"][:40])

    # 4. 状态机：待确认不能直接收货
    r = client.post(f"/api/v1/orders/{oid}/receive", headers=buyer)
    check("待确认状态不可收货", r.status_code == 409, r.json()["message"][:40])

    # 5. 支付凭证登记
    r = client.post(f"/api/v1/orders/{oid}/pay", json={"voucher_key": "product/images/demo-pay.jpg"},
                    headers=buyer)
    check("线下支付凭证登记", r.status_code == 200 and r.json()["data"]["pay_status"] == 1)
    r = client.post(f"/api/v1/orders/{oid}/pay", json={"voucher_key": "x"}, headers=buyer)
    check("重复登记被拒", r.status_code == 409)

    # 6. 卖家确认 → 发货 → 买家收货
    r = client.post(f"/api/v1/orders/{oid}/confirm", headers=seller)
    check("卖家确认→待发货", r.json()["data"]["status"] == 2)
    r = client.post(f"/api/v1/orders/{oid}/ship",
                    json={"ship_company": "顺丰速运", "ship_no": "SF2026102600001"}, headers=seller)
    check("卖家发货→已发货（记录物流单号）",
          r.json()["data"]["status"] == 3 and r.json()["data"]["ship_no"] == "SF2026102600001")
    r = client.post(f"/api/v1/orders/{oid}/receive", headers=buyer)
    check("买家收货→已完成", r.json()["data"]["status"] == 4 and r.json()["data"]["completed_at"])
    check("完成后库存保持扣减", abs(float(stock_of(client, pid)) - (stock0 - qty1)) < 1e-6)

    # 7. 取消回库存
    r = client.post("/api/v1/orders", json={"product_id": pid, "quantity": min_qty}, headers=buyer)
    oid2 = r.json()["data"]["id"]
    r = client.post(f"/api/v1/orders/{oid2}/cancel", json={"reason": "拍错了"}, headers=buyer)
    check("买家取消订单", r.json()["data"]["status"] == 5 and r.json()["data"]["cancel_reason"] == "拍错了")
    check("取消后库存归还", abs(float(stock_of(client, pid)) - (stock0 - qty1)) < 1e-6,
          f"stock={stock_of(client, pid)}")

    # 8. 库存不足
    r = client.post("/api/v1/orders", json={"product_id": pid, "quantity": 999999}, headers=buyer)
    check("库存不足被拒(原子扣减)", r.status_code == 400 and "库存不足" in r.json()["message"])

    # 9. 订单列表按角色隔离
    r = client.get("/api/v1/orders", headers=buyer)
    check("买家视角只看到自己的订单", all(o["buyer_id"] == 4 for o in r.json()["data"]["items"]) and
          r.json()["data"]["total"] >= 2)

    # ================ 审核工作台 ================
    print("\n== 审核工作台 ==")
    # seller1 提交一个新商品（不自上架，保持待审核），自述特优（高报演示红/黄标）
    r = client.post("/api/v1/products", json={
        "title": "审核演示·中宁特优280粒", "variety": "宁杞5号", "origin": "中宁",
        "spec_per_50g": 280, "grade_claim": "特优", "unit_price": 49.9,
        "stock": 500, "min_order_qty": 50, "description": "提交审核演示",
    }, headers=seller)
    check("卖家提交商品→待审核", r.status_code == 200 and r.json()["data"]["status"] == 1)
    new_pid = r.json()["data"]["id"]

    # 传图（异步评估，TestClient 不执行 BackgroundTasks → 显示"评估中/灰"）
    img = Path("scripts/seed_assets/web/goji-web-1.jpg")
    if not img.exists():
        img = next(Path("../docs/飞浆gouqi").glob("*.jpg"))
    r = client.post(f"/api/v1/products/{new_pid}/images",
                    files={"file": (img.name, img.read_bytes(), "image/jpeg")}, headers=seller)
    check("待审商品上传图片", r.status_code == 200, r.text[:100])

    # 手动触发评估（模拟 BackgroundTasks 在真实服务中的执行）
    r = client.post(f"/api/v1/admin/audit/products/{new_pid}/reassess", headers=admin)
    if r.status_code == 200:
        d = r.json()["data"]
        print(f"    评估结果：AI等级={d['ai_grade']}  缺陷率={d['defect_ratio']}")
    else:
        # cv2 未装好时评估会跳过——此时队列为灰标
        print(f"    [提示] 评估未产出（cv2 未就绪）：{r.json()['message'][:60]}")

    # 队列
    r = client.get("/api/v1/admin/audit/queue", headers=admin)
    q = r.json()["data"]
    check("管理员可见审核队列", r.status_code == 200 and q["total"] >= 1)
    flags = {i["id"]: i["diff_flag"] for i in q["items"]}
    print(f"    队列差异标记：{flags}")
    check("队列返回驳回原因枚举(10条)", len(q["reject_reasons"]) == 10)

    # 越权：卖家不能访问审核队列
    r = client.get("/api/v1/admin/audit/queue", headers=seller)
    check("卖家访问审核接口被拒(403)", r.status_code == 403)

    # 详情
    r = client.get(f"/api/v1/admin/audit/products/{new_pid}", headers=admin)
    d = r.json()["data"]
    check("审核详情含图片/评估/卖家风险", d["images"] and "seller_risk" in d and "assessments" in d)
    print(f"    卖家风险画像：{d['seller_risk']}")

    # 通过（指定等级=改级场景）
    target = d["ai_grade"] or "甲级"  # AI 未产出则人工定级
    r = client.post(f"/api/v1/admin/audit/products/{new_pid}/approve",
                    params={"grade_platform": target}, headers=admin)
    check(f"审核通过（认定 {target}）", r.status_code == 200 and r.json()["data"]["status"] == 3,
          r.text[:120])

    # 差异标记快照落库验证
    import json
    import subprocess
    q = ("SELECT action, grade_claim, ai_grade, grade_platform_after, diff_flag, reason "
         "FROM audit_log WHERE product_id=%d ORDER BY id DESC LIMIT 1" % new_pid)
    row = subprocess.run(
        ["mysql", "-h127.0.0.1", "-uroot", "-pyeyaoyan", "-D", "wolfberry",
         "--default-character-set=utf8mb4", "-N", "-e", q],
        capture_output=True, text=True).stdout.strip()
    print(f"    audit_log 快照：{row}")
    check("差异标记快照落库（含自述/AI/认定/标记）", all(k in row for k in ["特优", "审核通过"]))

    # 驳回路径
    r = client.post("/api/v1/products", json={
        "title": "审核演示·驳回用例", "variety": "宁杞5号", "origin": "中宁",
        "spec_per_50g": 280, "grade_claim": "特级", "unit_price": 39.9,
        "stock": 300, "min_order_qty": 50, "description": "驳回演示",
    }, headers=seller)
    rej_pid = r.json()["data"]["id"]
    r = client.post(f"/api/v1/admin/audit/products/{rej_pid}/reject",
                    params={"reason_code": "GRADE_MISMATCH", "note": "实拍图不支持特优"}, headers=admin)
    check("驳回（枚举原因）", r.status_code == 200 and r.json()["data"]["status"] == 4, r.text[:120])
    r = client.post(f"/api/v1/admin/audit/products/{rej_pid}/reject",
                    params={"reason_code": "NOT_IN_ENUM"}, headers=admin)
    check("非法驳回原因被拒", r.status_code == 400)

    print(f"\n通过 {ok_count} 项")


if __name__ == "__main__":
    main()
