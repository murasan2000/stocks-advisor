from __future__ import annotations

import re
from typing import Any

from app.services.external.symbols import resolve_symbol
from app.types.agents.multi_agent import (
    MultiAgentState,
    ScreeningCandidate,
    ScreeningResult,
)

_MAX_PORTFOLIO_CANDIDATES = 3
_SELL_KEYWORDS = ("売り時", "売却", "売るべき", "利確", "損切り")
_BUY_KEYWORDS = ("買い時", "購入", "買うべき", "おすすめ", "新規")


def _detect_focus(query: str) -> str:
    if any(k in query for k in _SELL_KEYWORDS):
        return "sell"
    if any(k in query for k in _BUY_KEYWORDS):
        return "buy"
    return "general"


def _query_candidate(query: str) -> ScreeningCandidate | None:
    """クエリから銘柄を抽出する。解決できなければ None。"""
    symbol = resolve_symbol(query)
    # クエリ全体がそのまま返ってきた場合は銘柄を特定できていない
    if symbol == query and not re.match(r"^[\^A-Z0-9.=-]+$", query):
        return None
    return ScreeningCandidate(
        ticker=symbol,
        company_name=symbol,
        reason="ユーザーの質問に含まれる銘柄",
        priority=1,
        source="query",
    )


async def screening_node(state: MultiAgentState) -> dict[str, Any]:
    """クエリとポートフォリオから分析対象銘柄を抽出する。"""
    candidates: list[ScreeningCandidate] = []

    if qc := _query_candidate(state["query"]):
        candidates.append(qc)

    portfolio = state.get("portfolio_data")
    if portfolio:
        # 評価損益率の絶対値が大きい順 = 判断が必要な銘柄を優先
        holdings = sorted(
            portfolio["holdings"],
            key=lambda h: abs(h["unrealized_pnl_pct"]),
            reverse=True,
        )
        for i, h in enumerate(holdings[:_MAX_PORTFOLIO_CANDIDATES]):
            ticker = f"{h['ticker']}.T"
            if any(c["ticker"] == ticker for c in candidates):
                continue
            candidates.append(
                ScreeningCandidate(
                    ticker=ticker,
                    company_name=h["company_name"],
                    reason=f"保有銘柄（評価損益率 {h['unrealized_pnl_pct']:+.1f}%）",
                    priority=2 + i,
                    source="portfolio",
                )
            )

    if not candidates:
        candidates.append(
            ScreeningCandidate(
                ticker="^N225",
                company_name="日経平均株価",
                reason="個別銘柄を特定できないため市場全体を分析",
                priority=1,
                source="query",
            )
        )

    focus = _detect_focus(state["query"])
    names = ", ".join(f"{c['company_name']}({c['ticker']})" for c in candidates)
    result = ScreeningResult(
        candidates=candidates,
        analysis_focus=focus,
        summary=f"分析対象 {len(candidates)}銘柄: {names}。フォーカス: {focus}。",
    )
    return {"screening_result": result}
