"""1銘柄分の日足チャート（OHLCV）取得。

全銘柄スキャン（fetcher.py）とは異なり、都度1銘柄のみのオンデマンド取得のため
レートリミットの影響は軽微。live は yfinance、mock は銘柄コードを種に
した決定論的なランダムウォークで合成する（テスト・オフライン動作のため）。
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta
from typing import Any

from app.services.screener.fetcher import with_retry
from app.types.api import Candle, HistoryPeriod

# 期間ごとのおおよその営業日数（合成データの本数決定に使用）
_PERIOD_TRADING_DAYS: dict[HistoryPeriod, int] = {
    "3mo": 63,
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
    "10y": 2520,
}


def fetch_candles_live(symbol: str, period: HistoryPeriod) -> list[Candle]:
    """yfinance から1銘柄分の日足 OHLCV を取得する。取得失敗時は空リスト。"""
    import yfinance as yf

    try:
        df = with_retry(
            lambda: yf.Ticker(symbol).history(period=period, interval="1d"),
            what=f"history {symbol}",
        )
    except Exception:
        return []
    if df is None or df.empty:
        return []
    return _rows_to_candles(df)


def _rows_to_candles(df: Any) -> list[Candle]:
    candles: list[Candle] = []
    for idx, row in df.iterrows():
        try:
            o, h, low, c, v = (
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                int(row["Volume"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if o != o or c != c:  # NaN
            continue
        candles.append(
            Candle(
                date=idx.strftime("%Y-%m-%d"),
                open=round(o, 2),
                high=round(h, 2),
                low=round(low, 2),
                close=round(c, 2),
                volume=v,
            )
        )
    return candles


def synth_candles(code: str, period: HistoryPeriod) -> list[Candle]:
    """証券コードを種にした決定論的なランダムウォークで OHLCV を合成する。"""
    seed = int.from_bytes(hashlib.sha256(code.encode()).digest()[:4], "big")
    days = _PERIOD_TRADING_DAYS.get(period, 252)
    price = 500 + seed % 9500 + (seed % 100) / 100

    candles: list[Candle] = []
    d = date.today() - timedelta(days=int(days * 1.45))  # 週末を考慮した逆算
    step = 0
    while len(candles) < days and d <= date.today():
        if d.weekday() < 5:  # 平日のみ
            # sin波 + 疑似乱数で緩やかなトレンド・ノイズを付与
            noise = math.sin((seed + step) * 0.37) * 0.015 + (
                ((seed >> (step % 20)) % 21 - 10) / 1000
            )
            price = max(price * (1 + noise), 1.0)
            open_p = price * (1 + ((seed >> (step % 13)) % 11 - 5) / 1000)
            high = max(open_p, price) * (1 + ((seed >> (step % 7)) % 6) / 1000)
            low = min(open_p, price) * (1 - ((seed >> (step % 11)) % 6) / 1000)
            volume = 10_000 + ((seed >> (step % 17)) % 50_000) * 10
            candles.append(
                Candle(
                    date=d.isoformat(),
                    open=round(open_p, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(price, 2),
                    volume=volume,
                )
            )
            step += 1
        d += timedelta(days=1)
    return candles
