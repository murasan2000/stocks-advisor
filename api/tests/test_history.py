"""銘柄詳細チャート（OHLCV 合成）のテスト。"""

from __future__ import annotations

from app.services.screener.history import synth_candles


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
