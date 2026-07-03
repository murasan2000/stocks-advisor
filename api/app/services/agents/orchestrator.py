"""親エージェント（オーケストレーター）。

責務は「意図判定 → 子エージェントへの委任」のみ。実処理は子グラフに閉じ込める。
グラフは classify → (general | company) の分岐。

意図判定の詳細ロジック（LLM 化）は Phase 5、子エージェントの本実装は Phase 6/7。
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents import company, general
from app.services.agents.runtime import classify_intent, extract_tickers
from app.services.agents.state import AgentState, new_state


async def _classify(state: AgentState) -> dict[str, Any]:
    """意図と対象銘柄を判定する。"""
    tickers = state["tickers"] or extract_tickers(state["query"])
    return {"tickers": tickers, "intent": classify_intent(state["query"], tickers)}


def _route(state: AgentState) -> str:
    """意図に応じて委任先の子エージェントを選ぶ。"""
    return "company" if state["intent"] == "company" else "general"


async def _delegate_general(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """一般質問エージェントへ委任する（子 run は親 run にネストする）。"""
    result = await general.graph.ainvoke(state, config)
    return {"answer": result["answer"]}


async def _delegate_company(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """企業分析エージェントへ委任する。"""
    result = await company.graph.ainvoke(state, config)
    return {"answer": result["answer"], "reports": result.get("reports", {})}


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("classify", _classify)
    builder.add_node("general", _delegate_general)
    builder.add_node("company", _delegate_company)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify", _route, {"general": "general", "company": "company"}
    )
    builder.add_edge("general", END)
    builder.add_edge("company", END)
    return builder.compile()


graph = build_graph()


async def run(
    query: str,
    tickers: list[str] | None = None,
    config: RunnableConfig | None = None,
) -> str:
    """親エージェントを実行し、意図判定 → 委任 の結果（回答）を返す。"""
    result = await graph.ainvoke(new_state(query, tickers), config or {})
    return str(result["answer"])
