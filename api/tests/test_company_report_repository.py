"""CompanyReportRepository（AI企業分析レポートの日次永続化・issue #72）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.company.report_repository import CompanyReportRepository


@pytest.fixture
async def repo(tmp_path: Path) -> CompanyReportRepository:
    r = CompanyReportRepository(str(tmp_path / "company_reports.db"))
    await r.initialize()
    return r


async def test_upsert_then_get(repo: CompanyReportRepository) -> None:
    saved = await repo.upsert("7203", "2026-07-23", "# トヨタ自動車\n本文")
    assert saved.code == "7203"
    assert saved.report_date == "2026-07-23"
    assert saved.content == "# トヨタ自動車\n本文"

    fetched = await repo.get("7203", "2026-07-23")
    assert fetched is not None
    assert fetched.content == "# トヨタ自動車\n本文"


async def test_get_missing_returns_none(repo: CompanyReportRepository) -> None:
    assert await repo.get("7203", "2026-01-01") is None


async def test_upsert_same_day_overwrites(repo: CompanyReportRepository) -> None:
    """同一銘柄・同一日付での再実行はDBの内容を上書きする（issue #72 の仕様）。"""
    await repo.upsert("7203", "2026-07-23", "本文1")
    updated = await repo.upsert("7203", "2026-07-23", "本文2")
    assert updated.content == "本文2"

    fetched = await repo.get("7203", "2026-07-23")
    assert fetched is not None
    assert fetched.content == "本文2"

    dates = await repo.list_dates("7203")
    assert dates == ["2026-07-23"]  # 上書きなので行は増えない


async def test_different_codes_are_independent(
    repo: CompanyReportRepository,
) -> None:
    await repo.upsert("7203", "2026-07-23", "トヨタ自動車レポート")
    await repo.upsert("6758", "2026-07-23", "ソニーグループレポート")

    toyota = await repo.get("7203", "2026-07-23")
    sony = await repo.get("6758", "2026-07-23")
    assert toyota is not None and toyota.content == "トヨタ自動車レポート"
    assert sony is not None and sony.content == "ソニーグループレポート"


async def test_list_dates_is_newest_first_and_per_code(
    repo: CompanyReportRepository,
) -> None:
    await repo.upsert("7203", "2026-07-20", "0720")
    await repo.upsert("7203", "2026-07-22", "0722")
    await repo.upsert("7203", "2026-07-21", "0721")
    await repo.upsert("6758", "2026-07-25", "sony")

    assert await repo.list_dates("7203") == [
        "2026-07-22",
        "2026-07-21",
        "2026-07-20",
    ]
    assert await repo.list_dates("6758") == ["2026-07-25"]
    assert await repo.list_dates("9999") == []
