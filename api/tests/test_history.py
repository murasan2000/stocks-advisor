"""銘柄詳細チャート（OHLCV 合成・短期キャッシュ）のテスト。"""

from __future__ import annotations

import pytest

from app.services.screener import history
from app.services.screener.history import fetch_candles_live_cached, synth_candles
from app.types.api import Candle


def test_synth_candles_is_deterministic() -> None:
    a = synth_candles("7203", "1y")
    b = synth_candles("7203", "1y")
    assert a == b
    assert len(a) > 0


def test_synth_candles_length_matches_period() -> None:
    short = synth_candles("7203", "3mo")
    long = synth_candles("7203", "5y")
    assert len(short) < len(long)


def test_synth_candles_ohlc_consistency() -> None:
    candles = synth_candles("7203", "6mo")
    for c in candles:
        assert c.low <= c.open <= c.high
        assert c.low <= c.close <= c.high
        assert c.volume >= 0


def test_synth_candles_dates_are_chronological() -> None:
    candles = synth_candles("7203", "3mo")
    dates = [c.date for c in candles]
    assert dates == sorted(dates)


async def test_fetch_candles_live_cached_hits_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_candles_live_cached.cache_clear()  # TTLキャッシュをテスト間で分離
    calls = 0
    sample = [Candle(date="2026-01-01", open=1, high=2, low=0.5, close=1.5, volume=100)]

    def fake_fetch(symbol: str, period: str) -> list[Candle]:
        nonlocal calls
        calls += 1
        return sample

    monkeypatch.setattr(history, "fetch_candles_live", fake_fetch)
    assert await fetch_candles_live_cached("7203.T", "1y") == sample
    assert await fetch_candles_live_cached("7203.T", "1y") == sample  # キャッシュヒット
    assert calls == 1
    assert await fetch_candles_live_cached("7203.T", "6mo") == sample  # 期間違いはミス
    assert calls == 2


async def test_fetch_candles_live_cached_separates_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_candles_live_cached.cache_clear()
    calls: list[str] = []

    def fake_fetch(symbol: str, period: str) -> list[Candle]:
        calls.append(symbol)
        return []

    monkeypatch.setattr(history, "fetch_candles_live", fake_fetch)
    await fetch_candles_live_cached("7203.T", "1y")
    await fetch_candles_live_cached("6758.T", "1y")
    assert calls == ["7203.T", "6758.T"]
