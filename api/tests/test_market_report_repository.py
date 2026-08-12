"""MarketReportRepository（レポートの日次永続化・issue #66）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.market.report_repository import MarketReportRepository


@pytest.fixture
async def repo(tmp_path: Path) -> MarketReportRepository:
    r = MarketReportRepository(str(tmp_path / "market_reports.db"))
    await r.initialize()
    return r


async def test_upsert_then_get(repo: MarketReportRepository) -> None:
    saved = await repo.upsert("jp_stocks", "2026-07-23", "# 日本株市況\n本文")
    assert saved.category_id == "jp_stocks"
    assert saved.report_date == "2026-07-23"
    assert saved.content == "# 日本株市況\n本文"

    fetched = await repo.get("jp_stocks", "2026-07-23")
    assert fetched is not None
    assert fetched.content == "# 日本株市況\n本文"


async def test_get_missing_returns_none(repo: MarketReportRepository) -> None:
    assert await repo.get("jp_stocks", "2026-01-01") is None


async def test_upsert_same_day_overwrites(repo: MarketReportRepository) -> None:
    """同一カテゴリ・同一日付での再実行はDBの内容を上書きする（issue #66 の仕様）。"""
    await repo.upsert("jp_stocks", "2026-07-23", "本文1")
    updated = await repo.upsert("jp_stocks", "2026-07-23", "本文2")
    assert updated.content == "本文2"

    fetched = await repo.get("jp_stocks", "2026-07-23")
    assert fetched is not None
    assert fetched.content == "本文2"

    dates = await repo.list_dates("jp_stocks")
    assert dates == ["2026-07-23"]  # 上書きなので行は増えない


async def test_different_categories_are_independent(
    repo: MarketReportRepository,
) -> None:
    await repo.upsert("jp_stocks", "2026-07-23", "日本株レポート")
    await repo.upsert("us_stocks", "2026-07-23", "米国株レポート")

    jp = await repo.get("jp_stocks", "2026-07-23")
    us = await repo.get("us_stocks", "2026-07-23")
    assert jp is not None and jp.content == "日本株レポート"
    assert us is not None and us.content == "米国株レポート"


async def test_list_dates_is_newest_first_and_per_category(
    repo: MarketReportRepository,
) -> None:
    await repo.upsert("jp_stocks", "2026-07-20", "0720")
    await repo.upsert("jp_stocks", "2026-07-22", "0722")
    await repo.upsert("jp_stocks", "2026-07-21", "0721")
    await repo.upsert("us_stocks", "2026-07-25", "us")

    assert await repo.list_dates("jp_stocks") == [
        "2026-07-22",
        "2026-07-21",
        "2026-07-20",
    ]
    assert await repo.list_dates("us_stocks") == ["2026-07-25"]
    assert await repo.list_dates("unknown_category") == []
