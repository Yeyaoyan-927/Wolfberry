"""LangChain 工具层：Agent 访问业务的唯一通道。

实现说明：
- 工具以「工厂闭包」构建：session 由 runner 注入闭包，不进 LLM 参数 schema，
  @tool 的入参只保留业务参数（str/int/float），pydantic 可安全推断
- 只读查询；写操作类能力一律走业务 API，不在 Agent 内落库
- 每个工具返回 dict：{ok, summary, data}，异常不抛出（记入 summary）
"""
from __future__ import annotations

import logging

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_tools(session: Session, role: str) -> dict[str, BaseTool]:
    """构建本轮可用的工具集。卖家工具按角色过滤（买家不可见）。"""

    @tool
    def search_standards(query: str) -> dict:
        """检索平台知识库：枸杞分级标准、收购规范、平台规则条款。返回原文片段与来源标题。"""
        from app.services import rag_service

        try:
            out = rag_service.search(session, query, top_k=4)
            hits = out.hits
            return {
                "ok": True,
                "summary": f"命中 {len(hits)} 条（{out.provider}，{out.elapsed_ms}ms）",
                "data": [
                    {
                        "no": i + 1,
                        "title": h.doc_title,
                        "section": h.section_path,
                        "text": h.content,
                        "score": h.score,
                    }
                    for i, h in enumerate(hits)
                ],
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_standards 失败: %s", exc)
            return {"ok": False, "summary": f"知识库检索失败：{exc}", "data": []}

    @tool
    def get_market_price(variety: str, grade: str, origin: str = "") -> dict:
        """查询某品种/等级/产区的近 30 天成交行情：样本数、均价、最低、最高、逐日样本。"""
        from app.repositories.market import MarketRepo

        try:
            rows = MarketRepo(session).recent_prices(
                variety=variety, grade=grade, origin=origin or None, days=30
            )
            if not rows:
                return {"ok": True, "summary": "近 30 天无成交样本", "data": []}
            prices = [float(r.price) for r in rows]
            return {
                "ok": True,
                "summary": f"样本 {len(prices)} 条，均价 {sum(prices) / len(prices):.2f} 元/kg",
                "data": {
                    "variety": variety, "grade": grade, "origin": origin or "全部产区",
                    "days": 30, "samples": len(prices),
                    "avg": round(sum(prices) / len(prices), 2),
                    "low": min(prices), "high": max(prices),
                    "recent": [
                        {"date": str(r.stat_date), "price": float(r.price)} for r in rows[-10:]
                    ],
                },
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_market_price 失败: %s", exc)
            return {"ok": False, "summary": f"行情查询失败：{exc}", "data": []}

    @tool
    def search_products(
        variety: str = "", origin: str = "", grade: str = "", max_price: float = 0
    ) -> dict:
        """按品种/产区/等级/价格上限检索在架货源（按 AI 缺陷率升序），返回商品摘要。"""
        from app.services import product_service

        try:
            items, total = product_service.list_products(
                session,
                size=5,
                variety=variety or None,
                origin=origin or None,
                grade=grade or None,
                max_price=max_price or None,
                order_by="defect_asc",
            )
            return {
                "ok": True,
                "summary": f"命中 {total} 条，展示前 {len(items)} 条",
                "data": [
                    {
                        "id": p.id, "title": p.title,
                        "grade_platform": p.grade_platform, "ai_grade": p.ai_grade,
                        "defect_ratio": float(p.defect_ratio) if p.defect_ratio is not None else None,
                        "unit_price": float(p.unit_price), "origin": p.origin,
                    }
                    for p in items
                ],
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_products 失败: %s", exc)
            return {"ok": False, "summary": f"商品检索失败：{exc}", "data": []}

    @tool
    def price_suggest(variety: str, grade: str, origin: str, spec_per_50g: int = 280) -> dict:
        """【卖家】按品种/等级/产区给出三档定价建议（走量/适中/溢价）与行情分位。纯规则计算。"""
        from app.schemas.skill import PriceSuggestIn
        from app.services import skill_service

        try:
            out = skill_service.price_suggest(
                session,
                PriceSuggestIn(
                    variety=variety, grade=grade, origin=origin, spec_per_50g=spec_per_50g
                ),
            )
            return {
                "ok": True,
                "summary": f"样本 {out.sample_size} 条，行情均价 {out.market_avg} 元/kg",
                "data": {
                    "samples": out.sample_size,
                    "market_avg": out.market_avg,
                    "market_p25": out.market_p25,
                    "market_p75": out.market_p75,
                    "tiers": [
                        {"name": t.name, "range": [t.price_low, t.price_high], "strategy": t.strategy}
                        for t in out.tiers
                    ],
                    "disclaimer": out.disclaimer,
                },
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("price_suggest 失败: %s", exc)
            return {"ok": False, "summary": f"定价建议失败：{exc}", "data": []}

    tools: dict[str, BaseTool] = {
        "search_standards": search_standards,
        "get_market_price": get_market_price,
        "search_products": search_products,
    }
    if role in ("seller", "admin"):
        tools["price_suggest"] = price_suggest
    return tools
