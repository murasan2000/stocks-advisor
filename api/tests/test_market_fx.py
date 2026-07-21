"""為替クオート取得（services/market/fx.py）のテスト。

screener/us_quote.py のテストと同じ方針: mockは決定論的合成、liveは
fetch_fundamentals をフェイクに差し替えて検証する。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.market import fx
from app.utils.settings import settings


@pytest.fixture(autouse=True)
def _isolate_cache() -> None:
    fx._fetch_fx_info_live.cache_clear()


async def test_mock_mode_returns_synthetic_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_api_mode", "mock")
    quotes = await fx.fetch_fx_quotes()
    assert {q.symbol for q in quotes} == set(fx.FX_SYMBOLS)
    for q in quotes:
        assert q.label == fx.FX_SYMBOLS[q.symbol]
        assert q.price is not None

    # 決定論的（同一シンボルは常に同じ値）
    again = await fx.fetch_fx_quotes()
    assert [q.price for q in quotes] == [q.price for q in again]


async def test_live_mode_maps_fundamentals_to_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_api_mode", "live")

    def fake_fetch_fundamentals(symbol: str, *, retry: bool = True) -> dict[str, Any]:
        assert symbol == "USDJPY=X"
        return {"regularMarketPrice": 156.789, "regularMarketChangePercent": 0.321}

    monkeypatch.setattr(fx, "fetch_fundamentals", fake_fetch_fundamentals)
    quote = await fx.fetch_fx_quote("USDJPY=X", "米ドル/円")
    assert quote is not None
    assert quote.price == 156.789
    assert quote.change_pct == 0.32


async def test_live_mode_falls_back_to_none_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_api_mode", "live")

    def raising_fetch_fundamentals(
        symbol: str, *, retry: bool = True
    ) -> dict[str, Any]:
        raise RuntimeError("network error")

    monkeypatch.setattr(fx, "fetch_fundamentals", raising_fetch_fundamentals)
    assert await fx.fetch_fx_quote("USDJPY=X", "米ドル/円") is None


async def test_live_mode_empty_info_falls_back_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_api_mode", "live")
    monkeypatch.setattr(fx, "fetch_fundamentals", lambda symbol, **kw: {})
    assert await fx.fetch_fx_quote("USDJPY=X", "米ドル/円") is None


async def test_live_mode_missing_price_falls_back_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # infoは非空だが価格フィールドが無い（データ不備）ケース
    monkeypatch.setattr(settings, "external_api_mode", "live")
    monkeypatch.setattr(
        fx, "fetch_fundamentals", lambda symbol, **kw: {"exchange": "CCY"}
    )
    assert await fx.fetch_fx_quote("USDJPY=X", "米ドル/円") is None
