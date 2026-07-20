"""ウォッチリスト（追加/削除/一覧・スナップショット結合）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.screener import us_quote
from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import ScreenerFilters, ScreenerService
from app.services.watchlist.repository import WatchlistRepository
from app.services.watchlist.service import WatchlistService
from app.types.api import StockRow
from app.utils.settings import settings


@pytest.fixture
async def watchlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[WatchlistService, ScreenerService]:
    monkeypatch.setattr(settings, "external_api_mode", "mock")
    db_path = str(tmp_path / "app.db")
    screener_repo = ScreenerRepository(db_path)
    await screener_repo.initialize()
    screener = ScreenerService(screener_repo)
    await screener.refresh()  # mock 合成でスナップショットをシード

    wl_repo = WatchlistRepository(db_path)
    await wl_repo.initialize()
    return WatchlistService(wl_repo, screener_repo), screener


async def _first_code(screener: ScreenerService) -> str:
    res = await screener.query(ScreenerFilters(), 1)
    return res.stocks[0].code


async def test_add_and_list_codes(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, screener = watchlist
    code = await _first_code(screener)
    await wl.add(code)
    assert await wl.list_codes() == [code]


async def test_add_is_idempotent(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, screener = watchlist
    code = await _first_code(screener)
    await wl.add(code)
    await wl.add(code)
    assert await wl.list_codes() == [code]


async def test_remove_is_safe_when_not_present(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, _ = watchlist
    await wl.remove("9999")  # 未登録でも例外にならない
    assert await wl.list_codes() == []


async def test_list_rows_joins_snapshot(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, screener = watchlist
    code = await _first_code(screener)
    await wl.add(code)
    rows = await wl.list_rows()
    assert len(rows) == 1
    assert rows[0].code == code
    assert rows[0].price is not None  # スナップショットの値が結合されている


async def test_list_rows_falls_back_when_missing_from_snapshot(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, _ = watchlist
    await wl.add("0000")  # スナップショットに存在しないコード
    rows = await wl.list_rows()
    assert len(rows) == 1
    assert rows[0].code == "0000"
    assert rows[0].price is None


async def test_list_rows_mock_mode_synthesizes_us_quote(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, _ = watchlist
    await wl.add("AAPL")  # mockモード（fixtureのデフォルト）・スナップショット対象外
    rows = await wl.list_rows()
    assert len(rows) == 1
    assert rows[0].code == "AAPL"
    assert rows[0].price is not None  # 決定論的合成データが入る


async def test_list_rows_fetches_us_quote_when_live(
    watchlist: tuple[WatchlistService, ScreenerService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    us_quote._fetch_us_quote_live.cache_clear()  # TTLキャッシュを分離
    wl, _ = watchlist
    monkeypatch.setattr(settings, "external_api_mode", "live")

    def fake_fetch_live_quote(code: str) -> StockRow:
        return StockRow(
            code=code, symbol=code, name="Apple Inc.", market="NMS", price=200.0
        )

    monkeypatch.setattr(us_quote, "fetch_live_quote", fake_fetch_live_quote)

    await wl.add("AAPL")
    rows = await wl.list_rows()
    assert len(rows) == 1
    assert rows[0].code == "AAPL"
    assert rows[0].name == "Apple Inc."
    assert rows[0].price == 200.0


async def test_list_rows_us_quote_falls_back_on_failure(
    watchlist: tuple[WatchlistService, ScreenerService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    us_quote._fetch_us_quote_live.cache_clear()
    wl, _ = watchlist
    monkeypatch.setattr(settings, "external_api_mode", "live")

    def raising_fetch_live_quote(code: str) -> StockRow:
        raise RuntimeError("network error")

    monkeypatch.setattr(us_quote, "fetch_live_quote", raising_fetch_live_quote)

    await wl.add("MSFT")
    rows = await wl.list_rows()
    assert rows[0].code == "MSFT"
    assert rows[0].price is None  # 取得失敗 → プレースホルダーへ縮退


async def test_list_rows_us_quote_failure_is_not_cached(
    watchlist: tuple[WatchlistService, ScreenerService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 失敗はキャッシュされないため、次回呼び出しで再取得され成功できる
    us_quote._fetch_us_quote_live.cache_clear()
    wl, _ = watchlist
    monkeypatch.setattr(settings, "external_api_mode", "live")
    attempt = 0

    def flaky_fetch_live_quote(code: str) -> StockRow:
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise RuntimeError("transient error")
        return StockRow(
            code=code, symbol=code, name="Apple Inc.", market="", price=201.0
        )

    monkeypatch.setattr(us_quote, "fetch_live_quote", flaky_fetch_live_quote)

    await wl.add("AAPL")
    first = await wl.list_rows()
    assert first[0].price is None  # 1回目は失敗 → プレースホルダー

    second = await wl.list_rows()
    assert second[0].price == 201.0  # 失敗はキャッシュされず、2回目は再取得して成功


async def test_list_rows_jp_code_missing_from_snapshot_skips_us_fetch(
    watchlist: tuple[WatchlistService, ScreenerService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    us_quote._fetch_us_quote_live.cache_clear()
    wl, _ = watchlist
    monkeypatch.setattr(settings, "external_api_mode", "live")

    called = False

    def fail_if_called(code: str) -> StockRow | None:
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(us_quote, "fetch_live_quote", fail_if_called)

    await wl.add("0000")  # JPコード形式・スナップショット無し（上場廃止等）
    rows = await wl.list_rows()
    assert rows[0].price is None
    assert called is False  # JPコードは米国株quote取得を試みない


async def test_list_codes_ordered_newest_first(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, _ = watchlist
    await wl.add("1111")
    await wl.add("2222")
    assert await wl.list_codes() == ["2222", "1111"]

    await wl.remove("2222")
    assert await wl.list_codes() == ["1111"]
