"""Agent 端到端验证：三类意图（标准/行情/找货）+ 卖家工具权限 + 降级路径。

用法：python scripts/test_agent.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap.app_factory import create_app  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

ok_count = 0


def check(name: str, cond: bool, detail: str = ""):
    global ok_count
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok_count += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main():
    setup_logging("WARNING")
    client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(create_app())

    def login(u, p):
        r = client.post("/api/v1/auth/login", json={"username": u, "password": p})
        return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

    buyer = login("buyer1", "buyer123")
    seller = login("seller1", "seller123")

    print("== 意图① standards（标准问答） ==")
    r = client.post("/api/v1/kb/ask", json={"question": "特优和特级差在哪？"}, headers=buyer)
    d = r.json()["data"]
    print(f"    mode={d.get('mode')} intent={d.get('intent')} tools={d.get('tools_used')}")
    check("Agent 模式生效", d.get("mode") == "agent", str(d.get("mode")))
    check("意图=standards", d.get("intent") == "standards", str(d.get("intent")))
    check("调用了标准检索工具", "search_standards" in (d.get("tools_used") or []))
    check("回答带引用编号", "[1]" in d["answer"] or "[2]" in d["answer"], d["answer"][:60])
    check("引用来源非空", len(d.get("citations") or []) >= 1)

    print("== 意图② market（行情问答，含实体抽取） ==")
    r = client.post("/api/v1/kb/ask",
                    json={"question": "中宁宁杞5号特级现在什么价？"}, headers=buyer)
    d = r.json()["data"]
    print(f"    intent={d.get('intent')} tools={d.get('tools_used')}")
    print(f"    {d['answer'][:100]}")
    check("意图=market", d.get("intent") == "market", str(d.get("intent")))
    check("调用了行情工具", "get_market_price" in (d.get("tools_used") or []))

    print("== 意图③ find_products（找货） ==")
    r = client.post("/api/v1/kb/ask",
                    json={"question": "帮我找缺陷率低的宁杞7号货源"}, headers=buyer)
    d = r.json()["data"]
    print(f"    intent={d.get('intent')} tools={d.get('tools_used')}")
    check("意图=find_products", d.get("intent") == "find_products", str(d.get("intent")))
    check("调用了商品检索工具", "search_products" in (d.get("tools_used") or []))

    print("== 权限：买家问定价建议 → 降级为标准检索 ==")
    r = client.post("/api/v1/kb/ask",
                    json={"question": "我的枸杞应该怎么定价？"}, headers=buyer)
    d = r.json()["data"]
    check("买家不含 price_suggest", "price_suggest" not in (d.get("tools_used") or []),
          str(d.get("tools_used")))

    print("== 卖家定价建议（seller_advice） ==")
    r = client.post("/api/v1/kb/ask",
                    json={"question": "宁杞5号特级 中宁 280粒 定多少合适？"}, headers=seller)
    d = r.json()["data"]
    print(f"    intent={d.get('intent')} tools={d.get('tools_used')}")
    print(f"    {d['answer'][:100]}")
    check("卖家可调用 price_suggest", "price_suggest" in (d.get("tools_used") or []),
          str(d.get("tools_used")))

    print("== 思考轨迹（steps） ==")
    d = client.post("/api/v1/kb/ask", json={"question": "特优和特级差在哪？"}, headers=buyer).json()["data"]
    for s in (d.get("steps") or []):
        print(f"    · {s}")
    check("steps 落在响应中", len(d.get("steps") or []) >= 3)

    print(f"\n通过 {ok_count} 项")


if __name__ == "__main__":
    main()
