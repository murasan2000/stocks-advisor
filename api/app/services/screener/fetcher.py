"""銘柄スナップショットの取得。

live: yfinance から株価・ファンダメンタルズ・ヒストリカルを取得する。
mock: 証券コードをシードに決定論的な合成データを返す（オフライン/テスト用）。

EXTERNAL_API_MODE で切替。yfinance は同期 I/O のため to_thread でオフロードする。
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.services.screener.metrics import (
    compute_score,
    drop_from_high_pct,
    rebound_from_low_pct,
    rsi,
)
from app.services.screener.universe import Ticker
from app.types.api import StockRow
from app.utils.settings import settings

logger = logging.getLogger(__name__)

# ヒストリカル取得期間。下がりすぎ反発検出に5年・1年が必要。
_HISTORY_PERIOD = "5y"
_ONE_YEAR_TRADING_DAYS = 248


class NoDataError(Exception):
    """価格データが取得できない（上場廃止・未上場など）銘柄を表す。"""


def _seed(code: str) -> int:
    return int.from_bytes(hashlib.sha256(code.encode()).digest()[:4], "big")


def _finalize(
    ticker: Ticker,
    *,
    price: float | None,
    change_pct: float | None,
    volume: int | None,
    market_cap: float | None,
    per: float | None,
    pbr: float | None,
    dividend_yield: float | None,
    roe: float | None,
    rsi_value: float | None,
    high_5y: float | None,
    low_1y: float | None,
) -> StockRow:
    """共通の派生指標（下落/反発率・スコア）を埋めて StockRow を組み立てる。"""
    drop = (
        drop_from_high_pct(price, high_5y)
        if price is not None and high_5y is not None
        else None
    )
    rebound = (
        rebound_from_low_pct(price, low_1y)
        if price is not None and low_1y is not None
        else None
    )
    score = compute_score(
        per=per,
        pbr=pbr,
        dividend_yield=dividend_yield,
        roe=roe,
        rsi_value=rsi_value,
        rebound_pct=rebound,
    )
    return StockRow(
        code=ticker.code,
        symbol=ticker.symbol,
        name=ticker.name,
        market=ticker.market,
        price=price,
        change_pct=change_pct,
        volume=volume,
        market_cap=market_cap,
        per=per,
        pbr=pbr,
        dividend_yield=dividend_yield,
        roe=roe,
        rsi=rsi_value,
        high_5y=high_5y,
        low_1y=low_1y,
        drop_from_high_pct=drop,
        rebound_from_low_pct=rebound,
        score=score,
    )


# ---------------------------------------------------------------------------
# mock（決定論的合成）
# ---------------------------------------------------------------------------


def _synth_row(ticker: Ticker) -> StockRow:
    s = _seed(ticker.code)
    price = round(500 + s % 9500 + (s % 100) / 100, 1)
    change_pct = round(((s >> 8) % 600 - 300) / 100, 2)
    volume = (s % 50000) * 100
    market_cap = float(s % 9000 + 100) * 1e9  # 1000億〜9.1兆
    per = round(5 + (s >> 3) % 3500 / 100, 1)  # 5〜40
    pbr = round(0.3 + (s >> 5) % 370 / 100, 2)  # 0.3〜4.0
    dividend_yield = round((s >> 7) % 500 / 100, 2)  # 0〜5%
    roe = round((s >> 9) % 2500 / 100, 1)  # 0〜25%
    rsi_value = round(20 + (s >> 11) % 60, 1)  # 20〜80
    high_5y = round(price * (1 + ((s >> 13) % 150) / 100), 1)  # 高値: +0〜150%
    low_1y = round(price * (0.4 + ((s >> 15) % 55) / 100), 1)  # 安値: -60〜-5%
    return _finalize(
        ticker,
        price=price,
        change_pct=change_pct,
        volume=volume,
        market_cap=market_cap,
        per=per,
        pbr=pbr,
        dividend_yield=dividend_yield,
        roe=roe,
        rsi_value=rsi_value,
        high_5y=high_5y,
        low_1y=low_1y,
    )


# ---------------------------------------------------------------------------
# live（yfinance）
# ---------------------------------------------------------------------------


def _norm_pct_fraction(value: Any) -> float | None:
    """0.025 のような比率を 2.5(%) に正規化する（既に%表記ならそのまま）。"""
    if value is None:
        return None
    v = float(value)
    return round(v * 100, 2) if abs(v) < 1 else round(v, 2)


def _fetch_live_sync(ticker: Ticker) -> StockRow:
    import yfinance as yf

    t = yf.Ticker(ticker.symbol)
    info: dict[str, Any] = t.info or {}
    hist = t.history(period=_HISTORY_PERIOD, auto_adjust=False)

    closes: list[float] = []
    if not hist.empty:
        closes = [float(c) for c in hist["Close"].tolist() if c == c]  # NaN 除外
    info_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not closes and not info_price:
        # 価格もヒストリカルも無い = 上場廃止/未上場。スキップ対象として通知。
        raise NoDataError(ticker.symbol)
    price = float(info_price or 0) or (closes[-1] if closes else None)
    change_pct = info.get("regularMarketChangePercent")
    if change_pct is None and len(closes) >= 2 and closes[-2]:
        change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100
    high_5y = max(closes) if closes else None
    low_1y = min(closes[-_ONE_YEAR_TRADING_DAYS:]) if closes else None

    name = str(info.get("shortName") or info.get("longName") or ticker.name)
    return _finalize(
        Ticker(code=ticker.code, name=name, market=ticker.market),
        price=round(price, 2) if price else None,
        change_pct=round(float(change_pct), 2) if change_pct is not None else None,
        volume=(
            int(info["regularMarketVolume"])
            if info.get("regularMarketVolume")
            else None
        ),
        market_cap=float(info["marketCap"]) if info.get("marketCap") else None,
        per=round(float(info["trailingPE"]), 1) if info.get("trailingPE") else None,
        pbr=round(float(info["priceToBook"]), 2) if info.get("priceToBook") else None,
        dividend_yield=_norm_pct_fraction(info.get("dividendYield")),
        roe=_norm_pct_fraction(info.get("returnOnEquity")),
        rsi_value=rsi(closes),
        high_5y=round(high_5y, 2) if high_5y else None,
        low_1y=round(low_1y, 2) if low_1y else None,
    )


async def fetch_row(ticker: Ticker) -> StockRow | None:
    """1 銘柄のスナップショットを取得する。

    mock: 決定論的合成を返す。
    live: yfinance から取得。価格データが無い（上場廃止等）銘柄や取得失敗は
          None を返してスキップする（偽の合成データを入れない）。
    """
    if settings.external_api_mode != "live":
        return _synth_row(ticker)
    import asyncio

    try:
        return await asyncio.to_thread(_fetch_live_sync, ticker)
    except NoDataError:
        logger.info("skip %s: no price data (delisted?)", ticker.symbol)
        return None
    except Exception as exc:
        logger.warning("skip %s: live fetch failed: %s", ticker.symbol, exc)
        return None
