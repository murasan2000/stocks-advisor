"""親エージェント（オーケストレーター）。

責務は「意図判定 → 子エージェントへの委任」のみ。実処理は子グラフに閉じ込める。
グラフは classify → (general | company) の分岐。company 委任時は対象銘柄の
市場（JP/US）に応じて company / company_us のどちらか、または両方に振り分ける。

意図判定の詳細ロジック（LLM 化）は Phase 5、子エージェントの本実装は Phase 6/7。
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents import company, company_us, general
from app.services.agents.resolver import resolve_tickers
from app.services.agents.runtime import classify_intent_llm
from app.services.agents.state import AgentState, new_state
from app.utils.market import is_jp_code


async def _classify(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """意図と対象銘柄を判定する（銘柄解決 → LLM 意図判定）。"""
    tickers = state["tickers"] or resolve_tickers(state["query"])
    intent = await classify_intent_llm(state["query"], tickers, config)
    return {"tickers": tickers, "intent": intent}


def _route(state: AgentState) -> str:
    """意図に応じて委任先の子エージェントを選ぶ。"""
    return "company" if state["intent"] == "company" else "general"


async def _delegate_general(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """一般質問エージェントへ委任する（子 run は親 run にネストする）。"""
    result = await general.graph.ainvoke(state, config)
    return {"answer": result["answer"]}


def _split_by_market(tickers: list[str]) -> tuple[list[str], list[str]]:
    """対象ティッカーを日本株/米国株に振り分ける（company/company_usへの委任先決定）。"""
    jp = [t for t in tickers if is_jp_code(t)]
    us = [t for t in tickers if not is_jp_code(t)]
    return jp, us


async def _invoke_child(
    child_graph: Any, tickers: list[str], state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """子グラフへ委任する（対象銘柄が無ければ何もしない）。"""
    if not tickers:
        return {}
    result: dict[str, Any] = await child_graph.ainvoke(
        {**state, "tickers": tickers}, config
    )
    return result


async def _delegate_company(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    """企業分析エージェントへ委任する（対象銘柄の市場に応じてJP/US別エージェントへ振り分け）。"""
    jp_tickers, us_tickers = _split_by_market(state["tickers"])

    if not jp_tickers and not us_tickers:
        # 銘柄が1つも解決できなかった場合は company 側の案内メッセージに委ねる
        # （company_us も同内容のメッセージを持つが、どちらか一方で十分）
        result = await company.graph.ainvoke(state, config)
        return {"answer": result["answer"], "reports": result.get("reports", {})}

    jp_result, us_result = await asyncio.gather(
        _invoke_child(company.graph, jp_tickers, state, config),
        _invoke_child(company_us.graph, us_tickers, state, config),
    )
    reports: dict[str, str] = {}
    answers: list[str] = []
    for result in (jp_result, us_result):
        reports.update(result.get("reports", {}))
        if result.get("answer"):
            answers.append(str(result["answer"]))
    return {"answer": "\n\n---\n\n".join(answers), "reports": reports}


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
