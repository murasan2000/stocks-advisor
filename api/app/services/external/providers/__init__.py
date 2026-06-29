"""市場データ Provider のファクトリ。

``EXTERNAL_API_MODE`` で実装を切り替える::

    live → YahooFinanceProvider（yfinance 実データ、失敗時は合成へフォールバック）
    mock → YahooFinanceClient （決定論的合成 / data/mock 配置時は固定モック）

エージェント側は ``get_market_data_provider()`` だけを呼べばよく、
取得元（無料 API / 有料 API）の差し替えはこの 1 箇所に閉じる。
"""

from __future__ import annotations

from functools import lru_cache

from app.services.external.providers.base import MarketDataProvider
from app.services.external.yahoo_finance_client import YahooFinanceClient
from app.utils.settings import settings

__all__ = ["MarketDataProvider", "get_market_data_provider"]


@lru_cache(maxsize=1)
def get_market_data_provider() -> MarketDataProvider:
    """設定に応じた市場データ Provider を返す（プロセス内でキャッシュ）。"""
    if settings.external_api_mode == "live":
        from app.services.external.providers.yfinance_provider import (
            YahooFinanceProvider,
        )

        return YahooFinanceProvider()
    return YahooFinanceClient(mode="mock")
