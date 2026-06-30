"""スクリーニング指標（純粋関数）のテスト。"""

from __future__ import annotations

from app.services.screener.metrics import (
    compute_score,
    drop_from_high_pct,
    is_oversold_rebound,
    rebound_from_low_pct,
    rsi,
)


def test_rsi_all_gains_is_100() -> None:
    closes = [float(i) for i in range(1, 30)]
    assert rsi(closes) == 100.0


def test_rsi_needs_enough_data() -> None:
    assert rsi([1.0, 2.0, 3.0]) is None


def test_drop_and_rebound() -> None:
    assert drop_from_high_pct(50.0, 100.0) == 50.0
    assert rebound_from_low_pct(55.0, 50.0) == 10.0
    assert drop_from_high_pct(10.0, 0.0) is None


def test_is_oversold_rebound() -> None:
    assert is_oversold_rebound(60.0, 15.0, min_drop=50, min_rebound=10) is True
    assert is_oversold_rebound(40.0, 15.0, min_drop=50, min_rebound=10) is False
    assert is_oversold_rebound(60.0, 5.0, min_drop=50, min_rebound=10) is False
    assert is_oversold_rebound(None, 15.0, min_drop=50, min_rebound=10) is False


def test_compute_score_range_and_ordering() -> None:
    cheap = compute_score(
        per=8, pbr=0.8, dividend_yield=4.0, roe=18, rsi_value=45, rebound_pct=20
    )
    pricey = compute_score(
        per=40, pbr=5, dividend_yield=0.0, roe=2, rsi_value=85, rebound_pct=0
    )
    assert 0 <= pricey < cheap <= 100


def test_compute_score_no_data_is_zero() -> None:
    assert compute_score(
        per=None,
        pbr=None,
        dividend_yield=None,
        roe=None,
        rsi_value=None,
        rebound_pct=None,
    ) == 0
