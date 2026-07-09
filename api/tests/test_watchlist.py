"""ウォッチリスト（追加/削除/一覧・スナップショット結合）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import ScreenerFilters, ScreenerService
from app.services.watchlist.repository import WatchlistRepository
from app.services.watchlist.service import WatchlistService
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


async def test_list_codes_ordered_newest_first(
    watchlist: tuple[WatchlistService, ScreenerService],
) -> None:
    wl, _ = watchlist
    await wl.add("1111")
    await wl.add("2222")
    assert await wl.list_codes() == ["2222", "1111"]

    await wl.remove("2222")
    assert await wl.list_codes() == ["1111"]
