"""Yahoo Finance API のレスポンス型定義。

実API（RapidAPI 経由の Yahoo Finance）のレスポンス形状を調査した結果に基づく。
フィールド名は実APIの camelCase を alias として保持し、Python 側は snake_case
でアクセスする。モックデータ（data/mock/yahoo_finance/）も camelCase で記述
されており、live モード実装時にそのまま実APIレスポンスをパースできる。

- Quote:        GET /v6/finance/quote の quoteResponse.result[] 要素
- ChartData:    GET /v8/finance/chart/{symbol} を OHLCV 配列に正規化した形
- AssetProfile: GET /v11/finance/quoteSummary/{symbol}?modules=assetProfile
- NewsItem:     GET /v2/finance/news の要素
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Quote(BaseModel):
    """リアルタイム株価（/v6/finance/quote）。"""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    short_name: str = Field(alias="shortName")
    currency: str = "JPY"
    regular_market_price: float = Field(alias="regularMarketPrice")
    regular_market_change: float = Field(alias="regularMarketChange")
    regular_market_change_percent: float = Field(alias="regularMarketChangePercent")
    regular_market_previous_close: float = Field(alias="regularMarketPreviousClose")
    regular_market_volume: int = Field(alias="regularMarketVolume", default=0)
    regular_market_time: int = Field(alias="regularMarketTime", default=0)
    market_cap: float | None = Field(alias="marketCap", default=None)
    fifty_two_week_high: float = Field(alias="fiftyTwoWeekHigh")
    fifty_two_week_low: float = Field(alias="fiftyTwoWeekLow")


class OHLCV(BaseModel):
    """日足の OHLCV データ1件。

    実APIの /v8/finance/chart は timestamp[] と indicators.quote[0].{open,...}
    の列指向構造のため、live モード実装時にこの行指向の形に正規化する。
    """

    date: str  # ISO 形式 (YYYY-MM-DD)
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartData(BaseModel):
    """過去株価データ（/v8/finance/chart を正規化したもの）。"""

    symbol: str
    currency: str = "JPY"
    period: str = "1y"
    interval: str = "1d"
    prices: list[OHLCV]


class AssetProfile(BaseModel):
    """企業基本情報（/v11/finance/quoteSummary ?modules=assetProfile）。"""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    long_name: str = Field(alias="longName")
    sector: str
    industry: str
    long_business_summary: str = Field(alias="longBusinessSummary")
    website: str | None = None
    full_time_employees: int | None = Field(alias="fullTimeEmployees", default=None)
    country: str = "Japan"


class NewsItem(BaseModel):
    """ニュース1件（/v2/finance/news）。"""

    model_config = ConfigDict(populate_by_name=True)

    uuid: str
    title: str
    publisher: str
    link: str
    provider_publish_time: int = Field(alias="providerPublishTime")
    summary: str | None = None
    related_tickers: list[str] = Field(alias="relatedTickers", default_factory=list)
