"""智能体包：LangGraph 状态图编排 + LangChain 工具层。

分层约束：
- agent 只通过 tools/ 与 services 的公开函数访问业务，不直接写 SQL
- LLM 不做等级判定与价格计算（架构底线），只负责意图分类与文案组织
- 图为固定 DAG：意图 → 路由 → 工具 → 生成，无循环边，天然防死循环
"""
from app.agent.runner import run_agent

__all__ = ["run_agent"]
