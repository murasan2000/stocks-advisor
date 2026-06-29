from __future__ import annotations

import logging
from typing import Any

from app.services.analysis.risk_metrics import (
    annual_volatility,
    beta,
    max_drawdown,
    sharpe_ratio,
)
from app.services.external.providers import get_market_data_provider
from app.types.agents.multi_agent import (
    MultiAgentState,
    RiskAssessment,
    RiskMetrics,
)

logger = logging.getLogger(__name__)


def _concentration(state: MultiAgentState) -> tuple[str, float]:
    """ポートフォリオの銘柄集中度を評価する。

    Returns:
        (集中リスク区分, 最大保有比率%)
    """
    portfolio = state.get("portfolio_data")
    if not portfolio or not portfolio["holdings"]:
        return "低", 0.0
    total = portfolio["total_market_value"]
    if total <= 0:
        return "低", 0.0
    top_share = max(h["market_value"] for h in portfolio["holdings"]) / total * 100
    if top_share > 50:
        return "高", top_share
    if top_share > 30:
        return "中", top_share
    return "低", top_share


async def risk_node(state: MultiAgentState) -> dict[str, Any]:
    """銘柄リスク指標とポートフォリオ集中リスクを評価する。"""
    market_data = state.get("market_data") or {}

    benchmark_closes: list[float] = []
    try:
        bench_chart = await get_market_data_provider().get_chart("^N225")
        benchmark_closes = [p.close for p in bench_chart.prices]
    except Exception as exc:
        logger.warning("benchmark chart fetch failed: %s", exc)

    individual: dict[str, RiskMetrics] = {}
    sector_values: dict[str, float] = {}
    for ticker, data in market_data.items():
        closes = [p.close for p in data["historical_prices"]]
        if len(closes) < 30:
            continue
        individual[ticker] = RiskMetrics(
            ticker=ticker,
            volatility_annual=round(annual_volatility(closes), 1),
            beta=(
                round(b, 2)
                if benchmark_closes and (b := beta(closes, benchmark_closes))
                else None
            ),
            max_drawdown=round(max_drawdown(closes), 1),
            sharpe_ratio=round(sharpe_ratio(closes), 2),
        )
        sector_values[data["sector"]] = sector_values.get(data["sector"], 0.0) + 1

    total_sectors = sum(sector_values.values())
    sector_concentration = {
        sector: round(count / total_sectors * 100, 1)
        for sector, count in sector_values.items()
    }

    concentration, top_share = _concentration(state)
    avg_vol = (
        sum(m["volatility_annual"] for m in individual.values()) / len(individual)
        if individual
        else 0.0
    )
    # ボラティリティ（0〜60%を0〜1に正規化）60% + 集中度 40% の加重
    vol_score = min(avg_vol / 60, 1.0)
    conc_score = {"高": 1.0, "中": 0.5, "低": 0.2}[concentration]
    risk_score = round(vol_score * 0.6 + conc_score * 0.4, 2)

    suggestions: list[str] = []
    if concentration != "低":
        suggestions.append(
            f"特定銘柄への集中度が高め（最大 {top_share:.0f}%）。分散投資を検討してください。"
        )
    if avg_vol > 30:
        suggestions.append("対象銘柄の平均ボラティリティが高く、価格変動リスクに注意が必要です。")
    if not suggestions:
        suggestions.append("現時点で顕著な集中リスク・変動リスクは見られません。")

    assessment = RiskAssessment(
        portfolio_risk_score=risk_score,
        concentration_risk=concentration,
        sector_concentration=sector_concentration,
        individual_risks=individual,
        suggestions=suggestions,
        summary=(
            f"リスクスコア {risk_score:.2f}（集中リスク: {concentration}、"
            f"平均ボラティリティ {avg_vol:.1f}%）"
        ),
    )
    return {"risk_assessment": assessment}
