from __future__ import annotations

import logging
import re
from typing import Any

from app.services.external.edinet_client import (
    EdinetClient,
    EdinetDataNotFoundError,
)
from app.types.agents.multi_agent import (
    AgentError,
    FundamentalAnalysis,
    MultiAgentState,
)
from app.types.external.edinet import FinancialSummary

logger = logging.getLogger(__name__)


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _valuation_score(
    per: float | None, pbr: float | None, dividend_yield: float | None
) -> float:
    score = 0.0
    if per is not None:
        if per < 10:
            score += 0.4
        elif per < 15:
            score += 0.2
        elif per > 25:
            score -= 0.3
    if pbr is not None:
        if pbr < 1:
            score += 0.3
        elif pbr > 3:
            score -= 0.2
    if dividend_yield is not None and dividend_yield > 3:
        score += 0.2
    return round(_clamp(score), 2)


def _analyze(
    ticker: str,
    price: float | None,
    latest: FinancialSummary,
    previous: FinancialSummary | None,
) -> FundamentalAnalysis:
    growth = (
        round((latest.net_sales / previous.net_sales - 1) * 100, 1)
        if previous and previous.net_sales
        else None
    )
    operating_margin = round(latest.operating_income / latest.net_sales * 100, 1)
    roe = round(latest.net_income / latest.equity * 100, 1)
    per = round(price / latest.eps, 1) if price and latest.eps else None
    pbr = round(price / latest.bps, 2) if price and latest.bps else None
    dividend_yield = (
        round(latest.dividend_per_share / price * 100, 2) if price else None
    )
    score = _valuation_score(per, pbr, dividend_yield)

    parts = [f"{latest.fiscal_year}: 営業利益率 {operating_margin:.1f}%、ROE {roe:.1f}%"]
    if growth is not None:
        parts.append(f"売上成長率 {growth:+.1f}%")
    if per is not None:
        parts.append(f"PER {per:.1f}倍")
    if pbr is not None:
        parts.append(f"PBR {pbr:.2f}倍")
    if dividend_yield is not None:
        parts.append(f"配当利回り {dividend_yield:.2f}%")
    valuation = "割安" if score > 0.2 else "割高" if score < -0.2 else "妥当"
    parts.append(f"バリュエーション: {valuation}（スコア {score:+.2f}）")

    return FundamentalAnalysis(
        ticker=ticker,
        company_name=latest.filer_name,
        fiscal_year=latest.fiscal_year,
        revenue_growth_yoy=growth,
        operating_margin=operating_margin,
        roe=roe,
        per=per,
        pbr=pbr,
        dividend_yield=dividend_yield,
        equity_ratio=latest.equity_ratio,
        valuation_score=score,
        summary="、".join(parts),
    )


async def fundamental_multi_node(state: MultiAgentState) -> dict[str, Any]:
    """EDINET の財務データと株価からバリュエーションを評価する。

    証券コードを持たない銘柄（指数等）や開示情報がない銘柄はスキップする。
    """
    market_data = state.get("market_data") or {}
    client = EdinetClient()
    analysis: dict[str, FundamentalAnalysis] = {}
    errors: list[AgentError] = []

    for ticker, data in market_data.items():
        m = re.match(r"^(\d{4})\.T$", ticker)
        if not m:
            continue  # 指数・為替などはスキップ
        try:
            summaries = await client.get_financial_summaries(m.group(1))
        except EdinetDataNotFoundError:
            errors.append(
                AgentError(
                    agent="fundamental",
                    message=f"{ticker} の開示情報が見つかりませんでした",
                )
            )
            continue
        except Exception as exc:
            logger.error("fundamental fetch failed for %s: %s", ticker, exc)
            errors.append(
                AgentError(agent="fundamental", message=f"{ticker}: {exc}")
            )
            continue

        annual = [s for s in summaries if s.fiscal_period == "FY"]
        if not annual:
            continue
        previous = annual[1] if len(annual) > 1 else None
        analysis[ticker] = _analyze(
            ticker, data["current_price"], annual[0], previous
        )

    update: dict[str, Any] = {"fundamental_analysis": analysis}
    if errors:
        update["errors"] = errors
    return update
