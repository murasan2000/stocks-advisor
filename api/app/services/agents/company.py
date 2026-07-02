"""企業分析エージェント（子）。

ダッシュボードで選択した銘柄について、銘柄ごとに個別レポートを生成する。
グラフは「対象銘柄の特定（resolve）→ レポート生成（report）」の 2 ノード。

本実装（yfinance/EDINET 収集・Web検索・SWOT等の AI 分析）は Phase 7。
ここでは対象銘柄ごとに構成済みのスケルトンレポートを返す雛形。
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.runtime import extract_tickers
from app.services.agents.state import AgentState, new_state

# レポートの節構成（Phase 7 で各節を実データ＋AI分析で埋める）。
_REPORT_SECTIONS = (
    "サマリー",
    "財務分析",
    "ニュース要約",
    "AI評価",
    "リスク",
    "総評",
)


def _skeleton_report(ticker: str) -> str:
    """1 銘柄分のスケルトンレポート（Markdown）。"""
    lines = [f"# {ticker} 企業分析レポート", ""]
    for section in _REPORT_SECTIONS:
        lines.append(f"## {section}")
        lines.append("（Phase 7 で実装予定）")
        lines.append("")
    return "\n".join(lines).rstrip()


async def _resolve(state: AgentState) -> dict[str, Any]:
    """分析対象の銘柄を確定する（未指定なら query から抽出）。"""
    tickers = state["tickers"] or extract_tickers(state["query"])
    return {"tickers": tickers}


async def _report(state: AgentState) -> dict[str, Any]:
    """銘柄ごとにレポートを生成する。"""
    tickers = state["tickers"]
    if not tickers:
        return {
            "answer": "分析対象の銘柄コードを指定してください（例: 7203）。",
            "reports": {},
        }
    reports = {ticker: _skeleton_report(ticker) for ticker in tickers}
    answer = "\n\n---\n\n".join(reports[t] for t in tickers)
    return {"reports": reports, "answer": answer}


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("resolve", _resolve)
    builder.add_node("report", _report)
    builder.add_edge(START, "resolve")
    builder.add_edge("resolve", "report")
    builder.add_edge("report", END)
    return builder.compile()


graph = build_graph()


async def run(
    query: str,
    tickers: list[str] | None = None,
    config: RunnableConfig | None = None,
) -> str:
    """企業分析エージェントを単体実行し、レポート（Markdown）を返す。"""
    result = await graph.ainvoke(new_state(query, tickers), config or {})
    return str(result["answer"])
