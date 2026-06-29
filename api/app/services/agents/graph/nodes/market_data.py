from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.external.providers import (
    MarketDataProvider,
    get_market_data_provider,
)
from app.types.agents.multi_agent import (
    AgentError,
    MarketData,
    MultiAgentState,
    ScreeningCandidate,
)

logger = logging.getLogger(__name__)

_MAX_TICKERS = 5


async def _fetch_one(
    client: MarketDataProvider, candidate: ScreeningCandidate
) -> MarketData:
    symbol = candidate["ticker"]
    quote = await client.get_quote(symbol)
    chart = await client.get_chart(symbol)
    profile = await client.get_asset_profile(symbol)
    return MarketData(
        ticker=symbol,
        company_name=quote.short_name,
        current_price=quote.regular_market_price,
        price_change_1d_pct=quote.regular_market_change_percent,
        volume=quote.regular_market_volume,
        market_cap=quote.market_cap,
        fifty_two_week_high=quote.fifty_two_week_high,
        fifty_two_week_low=quote.fifty_two_week_low,
        sector=profile.sector,
        historical_prices=chart.prices,
    )


async def market_data_node(state: MultiAgentState) -> dict[str, Any]:
    """スクリーニング結果の各銘柄について市場データを並列取得する。

    一部銘柄の取得失敗は errors に記録し、他銘柄の処理は続行する。
    """
    screening = state.get("screening_result")
    if not screening or not screening["candidates"]:
        return {
            "market_data": {},
            "errors": [
                AgentError(agent="market_data", message="分析対象銘柄がありません")
            ],
        }

    client = get_market_data_provider()
    candidates = screening["candidates"][:_MAX_TICKERS]
    results = await asyncio.gather(
        *(_fetch_one(client, c) for c in candidates),
        return_exceptions=True,
    )

    market_data: dict[str, MarketData] = {}
    errors: list[AgentError] = []
    for candidate, result in zip(candidates, results, strict=True):
        if isinstance(result, BaseException):
            logger.error(
                "market data fetch failed for %s: %s", candidate["ticker"], result
            )
            errors.append(
                AgentError(
                    agent="market_data",
                    message=f"{candidate['ticker']} の取得に失敗: {result}",
                )
            )
        else:
            market_data[candidate["ticker"]] = result

    update: dict[str, Any] = {"market_data": market_data}
    if errors:
        update["errors"] = errors
    return update
