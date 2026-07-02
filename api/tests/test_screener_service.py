"""スクリーナーのキャッシュ・絞り込み・段階取得のテスト（mock/合成データ）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import PAGE_SIZE, ScreenerFilters, ScreenerService
from app.utils.settings import settings


@pytest.fixture
async def service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ScreenerService:
    # .env の既定が live でもテストはネットワーク非依存の mock で実行する
    monkeypatch.setattr(settings, "external_api_mode", "mock")
    repo = ScreenerRepository(str(tmp_path / "screener.db"))
    await repo.initialize()
    svc = ScreenerService(repo)
    await svc.refresh()  # mock 合成でシード
    return svc


async def test_refresh_populates_snapshot(service: ScreenerService) -> None:
    res = await service.query(ScreenerFilters(), 1)
    assert res.total > 0
    assert res.meta.source == "mock"
    assert res.meta.snapshot_count == res.total
    assert res.summary.count == res.total


async def test_default_sort_by_score_desc(service: ScreenerService) -> None:
    res = await service.query(ScreenerFilters(), 1)
    scores = [s.score for s in res.stocks]
    assert scores == sorted(scores, reverse=True)


async def test_value_filter_reduces_results(service: ScreenerService) -> None:
    base = await service.query(ScreenerFilters(), 1)
    filtered = await service.query(ScreenerFilters(per_max=15, pbr_max=1.5), 1)
    assert filtered.total <= base.total
    for s in filtered.stocks:
        assert s.per is not None and s.per <= 15
        assert s.pbr is not None and s.pbr <= 1.5


async def test_oversold_filter(service: ScreenerService) -> None:
    res = await service.query(
        ScreenerFilters(
            oversold_enabled=True, drop_from_high_pct=50, rebound_from_low_pct=10
        ),
        1,
    )
    for s in res.stocks:
        assert s.drop_from_high_pct is not None and s.drop_from_high_pct >= 50
        assert s.rebound_from_low_pct is not None and s.rebound_from_low_pct >= 10


async def test_staged_pagination(service: ScreenerService) -> None:
    page1 = await service.query(ScreenerFilters(), 1)
    if page1.total > PAGE_SIZE:
        assert page1.next_stage == 2
        assert len(page1.stocks) == PAGE_SIZE
    else:
        assert page1.next_stage is None
        assert len(page1.stocks) == page1.total
