"""yfinance を用いた実データ版 MarketDataProvider。

設計書の Provider パターンにおける ``YahooFinanceProvider`` の実装。
無料かつ Python で最も普及している yfinance で指数・ETF・為替・個別銘柄を取得する。

yfinance は同期 I/O のため ``asyncio.to_thread`` でオフロードする。
ネットワーク到達不可や API 変更で取得に失敗した場合は、決定論的な合成データ
（``YahooFinanceClient`` の mock/synth）へ自動フォールバックし、アプリ全体が
落ちないようにする。これにより live/mock いずれの環境でも動作する。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.services.external.yahoo_finance_client import YahooFinanceClient
from app.types.external.yahoo_finance import (
    OHLCV,
    AssetProfile,
    ChartData,
    NewsItem,
    Quote,
)

logger = logging.getLogger(__name__)


def _first(source: Any, *keys: str) -> Any:
    """dict / 属性アクセスのどちらでも値を引けるよう順に試す。"""
    for key in keys:
        try:
            value = source[key]
        except (KeyError, TypeError, IndexError):
            value = getattr(source, key, None)
        if value is not None:
            return value
    return None


class YahooFinanceProvider:
    """yfinance による実データ取得。失敗時は決定論的合成へフォールバックする。"""

    def __init__(self) -> None:
        # フォールバック用の決定論的合成クライアント（常に有効な値を返す）。
        self._fallback = YahooFinanceClient(mode="mock")

    # ------------------------------------------------------------------
    # 公開 API（MarketDataProvider 準拠）
    # ------------------------------------------------------------------

    async def get_quote(self, symbol: str) -> Quote:
        try:
            return await asyncio.to_thread(self._quote_sync, symbol)
        except Exception as exc:
            logger.warning("yfinance get_quote(%s) failed, fallback: %s", symbol, exc)
            return await self._fallback.get_quote(symbol)

    async def get_chart(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> ChartData:
        try:
            return await asyncio.to_thread(self._chart_sync, symbol, period, interval)
        except Exception as exc:
            logger.warning("yfinance get_chart(%s) failed, fallback: %s", symbol, exc)
            return await self._fallback.get_chart(symbol, period, interval)

    async def get_asset_profile(self, symbol: str) -> AssetProfile:
        try:
            return await asyncio.to_thread(self._profile_sync, symbol)
        except Exception as exc:
            logger.warning(
                "yfinance get_asset_profile(%s) failed, fallback: %s", symbol, exc
            )
            return await self._fallback.get_asset_profile(symbol)

    async def get_news(self, symbol: str) -> list[NewsItem]:
        try:
            return await asyncio.to_thread(self._news_sync, symbol)
        except Exception as exc:
            logger.warning("yfinance get_news(%s) failed, fallback: %s", symbol, exc)
            return await self._fallback.get_news(symbol)

    # ------------------------------------------------------------------
    # 同期実装（to_thread で実行）
    # ------------------------------------------------------------------

    def _quote_sync(self, symbol: str) -> Quote:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        hist = ticker.history(period="5d", auto_adjust=False)
        if hist.empty:
            raise ValueError(f"no history for {symbol}")

        closes = [float(c) for c in hist["Close"].tolist() if c == c]  # NaN 除外
        price = float(_first(fast, "last_price", "lastPrice") or closes[-1])
        prev = float(
            _first(fast, "previous_close", "previousClose")
            or (closes[-2] if len(closes) >= 2 else price)
        )
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0.0

        year_high = _first(fast, "year_high", "yearHigh")
        year_low = _first(fast, "year_low", "yearLow")
        return Quote(
            symbol=symbol,
            shortName=str(_first(fast, "shortName") or symbol),
            currency=str(_first(fast, "currency") or "JPY"),
            regularMarketPrice=round(price, 4),
            regularMarketChange=round(change, 4),
            regularMarketChangePercent=round(change_pct, 4),
            regularMarketPreviousClose=round(prev, 4),
            regularMarketVolume=int(_first(fast, "last_volume", "lastVolume") or 0),
            regularMarketTime=int(datetime.now().timestamp()),
            marketCap=_first(fast, "market_cap", "marketCap"),
            fiftyTwoWeekHigh=round(float(year_high or max(closes)), 4),
            fiftyTwoWeekLow=round(float(year_low or min(closes)), 4),
        )

    def _chart_sync(self, symbol: str, period: str, interval: str) -> ChartData:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval, auto_adjust=False)
        if hist.empty:
            raise ValueError(f"no history for {symbol}")

        prices: list[OHLCV] = []
        for index, row in hist.iterrows():
            close = row["Close"]
            if close != close:  # NaN
                continue
            prices.append(
                OHLCV(
                    date=index.date().isoformat(),
                    open=round(float(row["Open"]), 4),
                    high=round(float(row["High"]), 4),
                    low=round(float(row["Low"]), 4),
                    close=round(float(close), 4),
                    volume=int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                )
            )
        if not prices:
            raise ValueError(f"no valid rows for {symbol}")
        return ChartData(symbol=symbol, period=period, interval=interval, prices=prices)

    def _profile_sync(self, symbol: str) -> AssetProfile:
        import yfinance as yf

        info: dict[str, Any] = yf.Ticker(symbol).info or {}
        return AssetProfile(
            symbol=symbol,
            longName=str(info.get("longName") or info.get("shortName") or symbol),
            sector=str(info.get("sector") or "不明"),
            industry=str(info.get("industry") or "不明"),
            longBusinessSummary=str(info.get("longBusinessSummary") or ""),
            website=info.get("website"),
            fullTimeEmployees=info.get("fullTimeEmployees"),
            country=str(info.get("country") or "Japan"),
        )

    def _news_sync(self, symbol: str) -> list[NewsItem]:
        import yfinance as yf

        raw = yf.Ticker(symbol).news or []
        items: list[NewsItem] = []
        for entry in raw:
            content = entry.get("content", entry)
            title = content.get("title")
            if not title:
                continue
            provider = content.get("provider") or {}
            link = content.get("canonicalUrl") or content.get("link") or {}
            items.append(
                NewsItem(
                    uuid=str(content.get("id") or entry.get("uuid") or title),
                    title=str(title),
                    publisher=str(provider.get("displayName") or "Yahoo Finance"),
                    link=str(link.get("url") if isinstance(link, dict) else link or ""),
                    providerPublishTime=int(datetime.now().timestamp()),
                    summary=content.get("summary"),
                    relatedTickers=[symbol],
                )
            )
        return items
