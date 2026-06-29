"""Yahoo Finance API クライアント。

EXTERNAL_API_MODE=mock のとき data/mock/yahoo_finance/ の JSON を返す。
モックに存在しないシンボルはシンボル文字列をシードとした決定論的な
ダミーデータを生成する（同じシンボルなら常に同じ値）。

live モードは RapidAPI キー取得後に実装予定（Phase 5）。
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.services.external.symbols import sanitize_symbol
from app.types.external.yahoo_finance import (
    OHLCV,
    AssetProfile,
    ChartData,
    NewsItem,
    Quote,
)
from app.utils.settings import settings

_TRADING_DAYS = 252


def _seed(symbol: str) -> int:
    return int.from_bytes(hashlib.sha256(symbol.encode()).digest()[:4], "big")


class YahooFinanceClient:
    def __init__(
        self,
        mode: str | None = None,
        mock_dir: str | Path | None = None,
    ) -> None:
        self._mode = mode or settings.external_api_mode
        self._mock_dir = Path(mock_dir or settings.mock_data_dir) / "yahoo_finance"
        self._cache: dict[str, Any] = {}

    def _ensure_mock(self) -> None:
        if self._mode != "mock":
            raise NotImplementedError(
                "Yahoo Finance の live モードは未実装です（Phase 5 で対応予定）。"
                " EXTERNAL_API_MODE=mock を使用してください。"
            )

    def _load(self, filename: str) -> Any:
        if filename not in self._cache:
            path = self._mock_dir / filename
            with path.open(encoding="utf-8") as f:
                self._cache[filename] = json.load(f)
        return self._cache[filename]

    def _load_optional(self, filename: str) -> dict[str, Any]:
        """モックJSONを読み込む。ファイルが無い場合は空辞書を返す。

        data/mock/ は別管理コンポーネントで未配置のことがあるため、
        欠損時はクラッシュさせず決定論的合成データへフォールバックさせる。
        """
        try:
            data: dict[str, Any] = self._load(filename)
            return data
        except FileNotFoundError:
            self._cache[filename] = {}
            return {}

    async def get_quote(self, symbol: str) -> Quote:
        """リアルタイム株価を取得する。"""
        self._ensure_mock()
        quotes = self._load_optional("quotes.json")
        if symbol in quotes:
            return Quote.model_validate(quotes[symbol])
        return self._synthesize_quote(symbol)

    async def get_chart(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> ChartData:
        """過去株価データ（日足 OHLCV）を取得する。"""
        self._ensure_mock()
        path = self._mock_dir / "charts" / f"{sanitize_symbol(symbol)}.json"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                return ChartData.model_validate(json.load(f))
        quote = await self.get_quote(symbol)
        return self._synthesize_chart(symbol, quote.regular_market_price)

    async def get_asset_profile(self, symbol: str) -> AssetProfile:
        """企業基本情報を取得する。"""
        self._ensure_mock()
        profiles = self._load_optional("profiles.json")
        if symbol in profiles:
            return AssetProfile.model_validate({"symbol": symbol, **profiles[symbol]})
        return AssetProfile(
            symbol=symbol,
            longName=symbol,
            sector="不明",
            industry="不明",
            longBusinessSummary=f"{symbol} の企業情報はモックデータに存在しません。",
        )

    async def get_news(self, symbol: str) -> list[NewsItem]:
        """銘柄関連ニュースを取得する。モックにない銘柄は汎用ニュースを返す。"""
        self._ensure_mock()
        news = self._load_optional("news.json")
        items = news.get(symbol, news.get("default", []))
        return [NewsItem.model_validate(item) for item in items]

    # ------------------------------------------------------------------
    # モック未収録シンボル向けの決定論的ダミーデータ生成
    # ------------------------------------------------------------------

    def _synthesize_quote(self, symbol: str) -> Quote:
        seed = _seed(symbol)
        base = 500.0 + (seed % 9500)  # 500〜9,999円
        change_pct = ((seed >> 8) % 600 - 300) / 100  # -3.0〜+3.0%
        price = round(base * (1 + change_pct / 100), 1)
        prev = round(base, 1)
        return Quote(
            symbol=symbol,
            shortName=symbol,
            regularMarketPrice=price,
            regularMarketChange=round(price - prev, 1),
            regularMarketChangePercent=round(change_pct, 2),
            regularMarketPreviousClose=prev,
            regularMarketVolume=(seed % 5000) * 1000,
            regularMarketTime=int(time.time()),
            fiftyTwoWeekHigh=round(base * 1.25, 1),
            fiftyTwoWeekLow=round(base * 0.75, 1),
        )

    def _synthesize_chart(self, symbol: str, end_price: float) -> ChartData:
        seed = _seed(symbol)
        prices: list[OHLCV] = []
        # end_price に向かう単純なランダムウォーク（決定論的）
        value = end_price * 0.85
        day = date.today() - timedelta(days=int(_TRADING_DAYS * 1.45))
        rng = seed
        for i in range(_TRADING_DAYS):
            while day.weekday() >= 5:
                day += timedelta(days=1)
            rng = (rng * 1103515245 + 12345) % (2**31)
            drift = (end_price - value) / max(_TRADING_DAYS - i, 1)
            noise = ((rng % 200) - 100) / 100 * end_price * 0.012
            value = max(value + drift + noise, end_price * 0.3)
            close = round(value, 1)
            spread = end_price * 0.008
            prices.append(
                OHLCV(
                    date=day.isoformat(),
                    open=round(close - spread / 2, 1),
                    high=round(close + spread, 1),
                    low=round(close - spread, 1),
                    close=close,
                    volume=(rng % 4000) * 1000,
                )
            )
            day += timedelta(days=1)
        return ChartData(symbol=symbol, prices=prices)
