"""保有銘柄（追加/更新/削除/一覧・スナップショット結合・CSVインポート）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.portfolio.repository import HoldingsRepository
from app.services.portfolio.service import PortfolioService
from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import ScreenerFilters, ScreenerService
from app.utils.settings import settings


@pytest.fixture
async def portfolio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[PortfolioService, ScreenerService]:
    monkeypatch.setattr(settings, "external_api_mode", "mock")
    db_path = str(tmp_path / "app.db")
    screener_repo = ScreenerRepository(db_path)
    await screener_repo.initialize()
    screener = ScreenerService(screener_repo)
    await screener.refresh()  # mock 合成でスナップショットをシード

    repo = HoldingsRepository(db_path)
    await repo.initialize()
    return PortfolioService(repo, screener_repo), screener


async def _first_code(screener: ScreenerService) -> str:
    res = await screener.query(ScreenerFilters(), 1)
    return res.stocks[0].code


async def test_upsert_and_list(
    portfolio: tuple[PortfolioService, ScreenerService],
) -> None:
    pf, screener = portfolio
    code = await _first_code(screener)
    await pf.upsert(code, 100, 1000.0)
    holdings = await pf.list_holdings()
    assert len(holdings) == 1
    assert holdings[0].code == code
    assert holdings[0].quantity == 100
    assert holdings[0].avg_cost == 1000.0
    assert holdings[0].cost_value == 100_000.0
    assert holdings[0].price is not None  # スナップショットの値が結合されている
    assert holdings[0].market_value == holdings[0].quantity * holdings[0].price


async def test_upsert_overwrites_existing(
    portfolio: tuple[PortfolioService, ScreenerService],
) -> None:
    pf, screener = portfolio
    code = await _first_code(screener)
    await pf.upsert(code, 100, 1000.0)
    await pf.upsert(code, 50, 2000.0)
    holdings = await pf.list_holdings()
    assert len(holdings) == 1
    assert holdings[0].quantity == 50
    assert holdings[0].avg_cost == 2000.0


async def test_remove_is_safe_when_not_present(
    portfolio: tuple[PortfolioService, ScreenerService],
) -> None:
    pf, _ = portfolio
    await pf.remove("9999")  # 未登録でも例外にならない
    assert await pf.list_holdings() == []


async def test_pnl_calculation(
    portfolio: tuple[PortfolioService, ScreenerService],
) -> None:
    pf, screener = portfolio
    code = await _first_code(screener)
    await pf.upsert(code, 10, 1.0)  # 極端に低い取得単価で含み益を確定させる
    holdings = await pf.list_holdings()
    h = holdings[0]
    assert h.pnl is not None
    assert h.pnl == h.market_value - h.cost_value  # type: ignore[operator]
    assert h.pnl_pct is not None
    assert h.pnl_pct == pytest.approx(h.pnl / h.cost_value * 100)


async def test_list_holdings_falls_back_when_missing_from_snapshot(
    portfolio: tuple[PortfolioService, ScreenerService],
) -> None:
    pf, _ = portfolio
    await pf.upsert("0000", 5, 100.0)  # スナップショットに存在しないコード
    holdings = await pf.list_holdings()
    assert len(holdings) == 1
    assert holdings[0].code == "0000"
    assert holdings[0].price is None
    assert holdings[0].market_value is None
    assert holdings[0].pnl is None
    assert holdings[0].cost_value == 500.0


async def test_import_csv_upserts_without_deleting_existing(
    portfolio: tuple[PortfolioService, ScreenerService],
) -> None:
    pf, screener = portfolio
    manual_code = await _first_code(screener)
    await pf.upsert(manual_code, 1, 1.0)  # 手動登録した既存銘柄

    csv_text = (
        "銘柄コード,銘柄名,保有数量［株］,平均取得価額［円］\n"
        '"1111","XXX鉱山","20","8,888.50"\n'
    )
    result = await pf.import_csv(csv_text.encode("utf-8"))
    assert result.imported == 1

    holdings = await pf.list_holdings()
    codes = {h.code for h in holdings}
    assert manual_code in codes  # CSVに無い既存銘柄は消えない
    assert "1111" in codes
