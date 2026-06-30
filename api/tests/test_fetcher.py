"""fetcher のモード別挙動テスト（live の no-data スキップ）。"""

from __future__ import annotations

import pytest

from app.services.screener import fetcher
from app.services.screener.universe import Ticker

_T = Ticker(code="6502", name="東芝", market="プライム")


async def test_mock_always_returns_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetcher.settings, "external_api_mode", "mock")
    row = await fetcher.fetch_row(Ticker("7203", "トヨタ自動車", "プライム"))
    assert row is not None
    assert row.code == "7203"
    assert row.symbol == "7203.T"


async def test_live_skips_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetcher.settings, "external_api_mode", "live")

    def _boom(ticker: Ticker) -> fetcher.StockRow:
        raise fetcher.NoDataError(ticker.symbol)

    monkeypatch.setattr(fetcher, "_fetch_live_sync", _boom)
    # 上場廃止などで価格データが無い銘柄は合成せずスキップ（None）。
    assert await fetcher.fetch_row(_T) is None


async def test_live_skips_on_unexpected_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetcher.settings, "external_api_mode", "live")

    def _boom(ticker: Ticker) -> fetcher.StockRow:
        raise RuntimeError("network blip")

    monkeypatch.setattr(fetcher, "_fetch_live_sync", _boom)
    assert await fetcher.fetch_row(_T) is None
