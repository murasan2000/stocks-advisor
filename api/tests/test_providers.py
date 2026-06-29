"""MarketDataProvider（汎用ツール）のテスト。"""

from __future__ import annotations

from app.services.external.providers import get_market_data_provider
from app.services.external.yahoo_finance_client import YahooFinanceClient


def test_factory_returns_mock_in_mock_mode() -> None:
    # デフォルト設定（EXTERNAL_API_MODE=mock）では合成クライアントを返す。
    provider = get_market_data_provider()
    assert isinstance(provider, YahooFinanceClient)


async def test_mock_client_synthesizes_when_files_missing() -> None:
    # mock データファイルが無くてもクラッシュせず決定論的合成を返す。
    client = YahooFinanceClient(mode="mock", mock_dir="/nonexistent")
    quote = await client.get_quote("^N225")
    assert quote.symbol == "^N225"
    assert quote.regular_market_price > 0

    # 同一シンボルは常に同じ値（決定論的）。
    again = await client.get_quote("^N225")
    assert again.regular_market_price == quote.regular_market_price

    chart = await client.get_chart("^N225")
    assert len(chart.prices) > 0
