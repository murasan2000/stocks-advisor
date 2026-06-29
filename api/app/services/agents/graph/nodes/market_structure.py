"""MarketStructureAgent（マーケット構造分析）。

主要指数・為替を収集し、LLM で市場構造を要約する。
「収集 → LLM要約」の専用サブグラフを定義し、外側ノードがそれを呼び出す。
これがエージェント・サブグラフ化（Phase 3.7）のリファレンス実装。
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.graph.agent_runtime import generate_summary
from app.services.external.yahoo_finance_client import YahooFinanceClient
from app.types.agents.multi_agent import MarketStructure, MultiAgentState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "あなたは日本株のマーケットストラテジストです。"
    "主要指数・為替の数値から、当日の市場構造（リスクオン/オフ、為替の影響、"
    "想定されるセクター物色）を2〜3文で簡潔に要約してください。"
    "数値を断定的な投資助言にせず、客観的な状況説明に留めること。"
)


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class _State(TypedDict):
    """market_structure サブグラフのローカル状態。"""

    data: MarketStructure | None
    error: str | None


async def _collect(state: _State) -> dict[str, Any]:
    """主要指数・為替を取得し、ルールベースの構造データを組み立てる。"""
    client = YahooFinanceClient()
    try:
        n225 = await client.get_quote("^N225")
        topix = await client.get_quote("^TOPX")
        usd_jpy = await client.get_quote("USDJPY=X")
    except Exception as exc:
        logger.error("market_structure collect failed: %s", exc, exc_info=True)
        return {"data": None, "error": str(exc)}

    avg_change = (
        n225.regular_market_change_percent + topix.regular_market_change_percent
    ) / 2
    macro_score = round(_clamp(avg_change / 2.0), 2)
    if macro_score > 0.2:
        trend = "強気"
    elif macro_score < -0.2:
        trend = "弱気"
    else:
        trend = "中立"

    rule_summary = (
        f"日経平均 {n225.regular_market_price:,.0f}円"
        f"（{n225.regular_market_change_percent:+.2f}%）、"
        f"TOPIX {topix.regular_market_price:,.1f}"
        f"（{topix.regular_market_change_percent:+.2f}%）、"
        f"USD/JPY {usd_jpy.regular_market_price:.2f}円。"
        f"市場トレンドは「{trend}」（スコア {macro_score:+.2f}）。"
    )
    data = MarketStructure(
        usd_jpy=usd_jpy.regular_market_price,
        nikkei225=n225.regular_market_price,
        topix=topix.regular_market_price,
        market_trend=trend,
        macro_score=macro_score,
        summary=rule_summary,
    )
    return {"data": data, "error": None}


async def _summarize(state: _State, config: RunnableConfig) -> dict[str, Any]:
    """収集データを LLM で要約し、summary を更新する。"""
    data = state.get("data")
    if not data:
        return {}
    context = (
        f"日経平均: {data['nikkei225']:,.0f}円\n"
        f"TOPIX: {data['topix']:,.1f}\n"
        f"USD/JPY: {data['usd_jpy']:.2f}円\n"
        f"方向スコア: {data['macro_score']:+.2f}（{data['market_trend']}）"
    )
    summary = await generate_summary(
        _SYSTEM_PROMPT,
        context,
        fallback=data["summary"],
        config=config,
    )
    return {"data": {**data, "summary": summary}}


def _build_subgraph() -> Any:
    builder: StateGraph[_State, Any, _State, _State] = StateGraph(_State)
    builder.add_node("collect", _collect)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


_subgraph = _build_subgraph()


async def market_structure_node(
    state: MultiAgentState, config: RunnableConfig
) -> dict[str, Any]:
    """専用サブグラフを実行し、結果を MultiAgentState にマッピングする。"""
    result: _State = await _subgraph.ainvoke({"data": None, "error": None}, config)
    if result.get("error") or not result.get("data"):
        message = result.get("error") or "取得失敗"
        return {
            "market_structure": None,
            "errors": [{"agent": "market_structure", "message": message}],
        }
    return {"market_structure": result["data"]}
