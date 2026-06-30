"""Market Agent（日本株版 / 市場全体の概況）。

設計書の ① Market Agent に対応する MVP の中核エージェント。
まずは日本株にフォーカスし、日経平均・TOPIX・ドル円から市場全体の状況を
評価する。リスクオン/オフのスコアと ★1〜5 の総合評価を付けて要約する。

※米国株（S&P500・NASDAQ・NYダウ・VIX・米金利）への拡張は、日本株版が
  安定したのち別 Issue で対応する。

BaseAgent を継承し、データ収集（collect）と整形のみを実装する。
「収集 → LLM 要約」の実行・LangGraph ノード化は BaseAgent が担う。
データ取得は MarketDataProvider 経由（EXTERNAL_API_MODE で live/mock 切替）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import ClassVar

from app.services.agents.base import BaseAgent
from app.services.external.providers import (
    MarketDataProvider,
    get_market_data_provider,
)
from app.types.agents.multi_agent import IndexQuote, MarketOverview, MultiAgentState

logger = logging.getLogger(__name__)

# 取得対象（日本株版）: 主要指数と為替。
_TARGETS: list[tuple[str, str, str]] = [
    ("^N225", "日経平均", "index"),
    ("^TOPX", "TOPIX", "index"),
    ("USDJPY=X", "ドル円", "fx"),
]


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _score_to_trend(score: float) -> str:
    if score > 0.2:
        return "強気"
    if score < -0.2:
        return "弱気"
    return "中立"


def _score_to_rating(score: float) -> int:
    """マクロスコア(-1〜1)を ★1〜5 に写像する（0→★3）。"""
    return max(1, min(5, round((score + 1) / 2 * 4) + 1))


def _fmt(q: IndexQuote) -> str:
    if q["category"] == "fx":
        return f"{q['name']} {q['price']:.2f}円（{q['change_pct']:+.2f}%）"
    return f"{q['name']} {q['price']:,.2f}（{q['change_pct']:+.2f}%）"


class JapanMarketAgent(BaseAgent[MarketOverview]):
    """日経平均・TOPIX・ドル円から日本市場の概況を評価するエージェント。"""

    key: ClassVar[str] = "market"
    label: ClassVar[str] = "市場分析"
    state_key: ClassVar[str] = "market"
    system_prompt: ClassVar[str] = (
        "あなたは日本株のマーケットストラテジストです。"
        "日経平均・TOPIX・ドル円の数値から、当日の日本市場全体の状況"
        "（リスクオン/オフ、為替の影響、想定されるセクター物色）を"
        "2〜3文で簡潔に要約してください。"
        "数値を断定的な投資助言にせず、客観的な状況説明に留めること。"
    )

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self._provider = provider or get_market_data_provider()

    async def collect(self, state: MultiAgentState) -> MarketOverview | None:
        results = await asyncio.gather(
            *(self._provider.get_quote(sym) for sym, _, _ in _TARGETS),
            return_exceptions=True,
        )

        indices: list[IndexQuote] = []
        for (symbol, name, category), result in zip(_TARGETS, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("market quote failed for %s: %s", symbol, result)
                continue
            indices.append(
                IndexQuote(
                    symbol=symbol,
                    name=name,
                    category=category,
                    price=round(result.regular_market_price, 4),
                    change_pct=round(result.regular_market_change_percent, 2),
                )
            )

        equity = [q for q in indices if q["category"] == "index"]
        if not equity:
            return None  # 株式指数が 1 つも取れなければ概況を出さない

        equity_avg = sum(q["change_pct"] for q in equity) / len(equity)
        # ±2% を ±1.0 に正規化。
        score = round(_clamp(equity_avg / 2.0), 2)
        overview = MarketOverview(
            indices=indices,
            market_trend=_score_to_trend(score),
            macro_score=score,
            rating=_score_to_rating(score),
            as_of=date.today().isoformat(),
            summary="",
        )
        return self.with_summary(overview, self.to_summary(overview))

    def to_context(self, data: MarketOverview) -> str:
        lines = [_fmt(q) for q in data["indices"]]
        return (
            "\n".join(lines)
            + f"\n方向スコア: {data['macro_score']:+.2f}（{data['market_trend']}）"
        )

    def to_summary(self, data: MarketOverview) -> str:
        stars = "★" * data["rating"] + "☆" * (5 - data["rating"])
        head = (
            f"市場総合評価 {stars}（{data['market_trend']}・"
            f"スコア {data['macro_score']:+.2f}）"
        )
        body = "、".join(_fmt(q) for q in data["indices"])
        return f"{head}。{body}。"

    def with_summary(self, data: MarketOverview, summary: str) -> MarketOverview:
        return {**data, "summary": summary}


# グラフ登録用ノード（agent_selection から参照）。
market_node = JapanMarketAgent().as_node()
