"""市場データ取得の汎用インターフェース（Provider パターン）。

設計書の方針に従い、市場データ取得を抽象インターフェース化する::

    MarketDataProvider
        ├── YahooFinanceProvider   （yfinance 実データ）
        └── YahooFinanceClient     （mock / 決定論的合成・既存実装）

無料 API → 利用者増加 → 有料 API への差し替え、を容易にするための土台。
各エージェントが頻繁に利用する「株価・チャート・企業情報・ニュース取得」を
この 1 インターフェースに集約し、エージェント側は実装を意識しない。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.types.external.yahoo_finance import (
    AssetProfile,
    ChartData,
    NewsItem,
    Quote,
)


@runtime_checkable
class MarketDataProvider(Protocol):
    """市場データ取得プロバイダの共通インターフェース。

    既存の ``YahooFinanceClient`` はこのインターフェースを構造的に満たす
    （mock プロバイダ）。実データ用 ``YahooFinanceProvider`` も同一シグネチャ。
    """

    async def get_quote(self, symbol: str) -> Quote:
        """リアルタイム株価（指数・為替・個別銘柄）を取得する。"""
        ...

    async def get_chart(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> ChartData:
        """過去株価データ（日足 OHLCV）を取得する。"""
        ...

    async def get_asset_profile(self, symbol: str) -> AssetProfile:
        """企業基本情報を取得する。"""
        ...

    async def get_news(self, symbol: str) -> list[NewsItem]:
        """銘柄関連ニュースを取得する。"""
        ...
