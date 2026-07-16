"""銘柄スナップショットの取得。

live: yfinance から取得。yfinance のレートリミット(429)対策として
      - 株価ヒストリカルは yf.download で一括取得（リクエスト数を削減）
      - ファンダメンタルズ(.info)は低並列 + 指数バックオフ再試行
  を用いる。株価が取れた銘柄は、ファンダ取得に失敗しても行を残す（件数を安定化）。
mock: 証券コードをシードに決定論的な合成データを返す（オフライン/テスト用）。
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import Any

from app.services.external.symbols import to_yahoo_symbol
from app.services.screener.metrics import (
    compute_score,
    drop_from_high_pct,
    rebound_from_low_pct,
    rsi,
)
from app.services.screener.universe import Ticker
from app.types.api import StockRow
from app.utils.retry import invoke_with_retry_sync, is_rate_limit_error
from app.utils.settings import settings

logger = logging.getLogger(__name__)

# ヒストリカル取得期間。下がりすぎ反発検出に5年・1年が必要。
_HISTORY_PERIOD = "5y"
_ONE_YEAR_TRADING_DAYS = 248


class NoDataError(Exception):
    """価格データが取得できない（上場廃止・未上場など）銘柄を表す。"""


def _seed(code: str) -> int:
    return int.from_bytes(hashlib.sha256(code.encode()).digest()[:4], "big")


def with_retry[T](fn: Callable[[], T], *, what: str) -> T:
    """レートリミット時のみ指数バックオフで再試行する（共通リトライを利用）。"""
    return invoke_with_retry_sync(
        fn,
        should_retry=is_rate_limit_error,
        max_retries=settings.screener_max_retries,
        what=what,
    )


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


def _norm_pct_fraction(value: Any) -> float | None:
    """0.025 のような比率を 2.5(%) に正規化する（既に%表記ならそのまま）。"""
    if value is None:
        return None
    v = float(value)
    return round(v * 100, 2) if abs(v) < 1 else round(v, 2)


# ---------------------------------------------------------------------------
# mock（決定論的合成）
# ---------------------------------------------------------------------------


def synth_row(ticker: Ticker) -> StockRow:
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


def fetch_history_batch(symbols: list[str]) -> dict[str, list[float]]:
    """複数銘柄の終値系列を yf.download で一括取得する（リクエスト数削減）。

    取得できなかった銘柄は結果に含めない。
    """
    import yfinance as yf

    if not symbols:
        return {}

    df = with_retry(
        lambda: yf.download(
            symbols,
            period=_HISTORY_PERIOD,
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=False,
            progress=False,
        ),
        what="history batch",
    )
    out: dict[str, list[float]] = {}
    if df is None or df.empty:
        return out
    multi = len(symbols) > 1
    for sym in symbols:
        try:
            sub = df[sym] if multi else df
            closes = [float(c) for c in sub["Close"].tolist() if c == c]
        except Exception:
            closes = []
        if closes:
            out[sym] = closes
    return out


def fetch_fundamentals(symbol: str, *, retry: bool = True) -> dict[str, Any]:
    """1銘柄のファンダメンタルズ(.info)を取得する（ベストエフォート）。

    retry=True（既定・スクリーナーの一括取得向け）: レートリミットは再試行する。
    retry=False（単発の「失敗＝機能縮退」呼び出し向け）: リトライせず、
    失敗を即座に許容する（CLAUDE.md の「機能縮退」方針に従い、過剰リトライで
    応答を遅くしない）。
    最終的に失敗しても {} を返し、株価情報だけで行を残す。
    """
    import yfinance as yf

    try:
        if retry:
            info = with_retry(lambda: yf.Ticker(symbol).info, what=f"info {symbol}")
        else:
            info = yf.Ticker(symbol).info
        return info or {}
    except Exception as exc:  # noqa: BLE001 - ベストエフォート
        logger.info("fundamentals unavailable for %s: %s", symbol, exc)
        return {}


def build_live_row(
    ticker: Ticker, closes: list[float], info: dict[str, Any]
) -> StockRow | None:
    """一括取得した終値系列＋ファンダから StockRow を組み立てる。

    価格データが全く無い（上場廃止等）場合は None を返す。
    """
    info_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not closes and not info_price:
        return None

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


def fetch_live_quote(code: str) -> StockRow | None:
    """1銘柄のライブ相場を取得する（ウォッチリスト等、単発の米国株quote向け）。

    スクリーナーの一括取得と異なり、ヒストリカル取得は行わない（RSI・5年高値・
    1年安値は None のまま）。現在値・前日比・主要ファンダメンタルズのみを返す。
    単発の「失敗＝機能縮退」呼び出しのため、レートリミット時もリトライしない
    （呼び出し側でプレースホルダーへフォールバックする）。
    """
    symbol = to_yahoo_symbol(code)
    info = fetch_fundamentals(symbol, retry=False)
    ticker = Ticker(code=code, name=code, market=str(info.get("exchange") or ""))
    return build_live_row(ticker, [], info)
