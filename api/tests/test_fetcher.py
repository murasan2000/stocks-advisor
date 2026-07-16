"""fetcher の合成データ・行組み立て・スキップ挙動のテスト。"""

from __future__ import annotations

import pytest

from app.services.screener import fetcher
from app.services.screener.fetcher import build_live_row, fetch_live_quote, synth_row
from app.services.screener.universe import Ticker

_T = Ticker(code="7203", name="トヨタ自動車", market="プライム")


def test_synth_row_is_deterministic() -> None:
    a = synth_row(_T)
    b = synth_row(_T)
    assert a.code == "7203"
    assert a.symbol == "7203.T"
    assert a == b
    assert 0 <= a.score <= 100


def test_build_live_row_from_history_and_info() -> None:
    closes = [100.0 + i for i in range(300)]  # 上昇トレンド
    info = {
        "currentPrice": 399.0,
        "trailingPE": 12.0,
        "priceToBook": 1.1,
        "dividendYield": 0.03,  # 比率 → 3%
        "returnOnEquity": 0.15,  # → 15%
        "marketCap": 1.0e12,
        "regularMarketVolume": 1000,
    }
    row = build_live_row(_T, closes, info)
    assert row is not None
    assert row.price == 399.0
    assert row.per == 12.0
    assert row.dividend_yield == 3.0
    assert row.roe == 15.0
    assert row.high_5y == 399.0
    assert row.rsi is not None


def test_build_live_row_skips_when_no_data() -> None:
    # 価格もヒストリカルも無い（上場廃止等）→ None（スキップ）
    assert build_live_row(_T, [], {}) is None


def test_build_live_row_keeps_row_without_fundamentals() -> None:
    # 株価はあるがファンダ無し → 行は残す（PER 等は None）
    closes = [100.0, 101.0, 102.0]
    row = build_live_row(_T, closes, {})
    assert row is not None
    assert row.price == 102.0
    assert row.per is None
    assert row.pbr is None


def test_fetch_live_quote_builds_row_without_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ウォッチリスト単発quote向け: ヒストリカル取得なしでも現在値・名前が入る
    monkeypatch.setattr(
        fetcher,
        "fetch_fundamentals",
        lambda symbol, **kwargs: {
            "currentPrice": 199.5,
            "shortName": "Apple Inc.",
            "exchange": "NMS",
        },
    )
    row = fetch_live_quote("AAPL")
    assert row is not None
    assert row.code == "AAPL"
    assert row.name == "Apple Inc."
    assert row.market == "NMS"
    assert row.price == 199.5
    assert row.high_5y is None  # ヒストリカル未取得のため


def test_fetch_live_quote_returns_none_without_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fetcher, "fetch_fundamentals", lambda symbol, **kwargs: {})
    assert fetch_live_quote("ZZZZ") is None


def test_fetch_live_quote_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    # 単発quoteは「失敗＝機能縮退」方針のためリトライしない（retry=Falseで呼ぶ）
    captured: dict[str, object] = {}

    def fake_fetch_fundamentals(
        symbol: str, *, retry: bool = True
    ) -> dict[str, object]:
        captured["retry"] = retry
        return {}

    monkeypatch.setattr(fetcher, "fetch_fundamentals", fake_fetch_fundamentals)
    fetch_live_quote("AAPL")
    assert captured["retry"] is False
