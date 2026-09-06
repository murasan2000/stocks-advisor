"""run_refresh_job（スナップショット更新ジョブ・ウォッチ銘柄アラート検出連携）のテスト。

issue #81: 更新前後のウォッチ銘柄スナップショットを比較し、閾値超えのアラートを
alerts_repo へ保存する。screener の実際の取得ロジックには依存させたくないため、
refresh() の中身を「指定した行でスナップショットを置き換えるだけ」のフェイクに
差し替える。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from app.services.jobs.repository import JobRepository
from app.services.jobs.runner import run_refresh_job
from app.services.screener.repository import ScreenerRepository
from app.services.watchlist.alerts_repository import AlertsRepository
from app.services.watchlist.repository import WatchlistRepository
from app.types.api import StockRow
from app.types.jobs import JobStatus


class _FakeScreener:
    """screener.refresh() の代わりに、指定行でスナップショットを置き換えるだけの
    フェイク（外部I/O非依存でアラート検出の配線だけを検証したいため）。"""

    def __init__(self, repo: ScreenerRepository, new_rows: list[StockRow]) -> None:
        self._repo = repo
        self._new_rows = new_rows

    async def refresh(
        self, progress: Callable[[int, int], Awaitable[None]] | None = None
    ) -> int:
        await self._repo.replace_all(
            self._new_rows, source="mock", universe_count=len(self._new_rows)
        )
        return len(self._new_rows)


def _row(code: str, price: float | None, score: int) -> StockRow:
    return StockRow(
        code=code, symbol=f"{code}.T", name=f"銘柄{code}", market="プライム",
        price=price, score=score,
    )


@pytest.fixture
async def screener_repo(tmp_path: Path) -> ScreenerRepository:
    r = ScreenerRepository(str(tmp_path / "screener.db"))
    await r.initialize()
    return r


@pytest.fixture
async def watchlist_repo(tmp_path: Path) -> WatchlistRepository:
    r = WatchlistRepository(str(tmp_path / "watchlist.db"))
    await r.initialize()
    return r


@pytest.fixture
async def alerts_repo(tmp_path: Path) -> AlertsRepository:
    r = AlertsRepository(str(tmp_path / "alerts.db"))
    await r.initialize()
    return r


@pytest.fixture
async def job_repo(tmp_path: Path) -> JobRepository:
    r = JobRepository(str(tmp_path / "jobs.db"))
    await r.initialize()
    return r


async def test_run_refresh_job_detects_and_persists_alerts(
    job_repo: JobRepository,
    screener_repo: ScreenerRepository,
    watchlist_repo: WatchlistRepository,
    alerts_repo: AlertsRepository,
) -> None:
    # 事前状態（更新前）
    await screener_repo.replace_all(
        [_row("7203", 1000.0, 50), _row("6758", 500.0, 30)],
        source="mock",
        universe_count=2,
    )
    await watchlist_repo.add("7203")
    await watchlist_repo.add("6758")
    await job_repo.create("j1", "screener_refresh")

    fake_screener = _FakeScreener(
        screener_repo,
        [_row("7203", 1200.0, 50), _row("6758", 500.0, 30)],  # 7203 のみ +20%
    )

    await run_refresh_job(
        "j1",
        job_repo,
        fake_screener,  # type: ignore[arg-type]
        screener_repo=screener_repo,
        watchlist_repo=watchlist_repo,
        alerts_repo=alerts_repo,
    )

    job = await job_repo.get("j1")
    assert job is not None
    assert job.status == JobStatus.DONE

    alerts = await alerts_repo.list_all()
    assert len(alerts) == 1
    assert alerts[0].code == "7203"
    assert alerts[0].kind == "price"


async def test_run_refresh_job_skips_detection_when_repos_not_given(
    job_repo: JobRepository, screener_repo: ScreenerRepository
) -> None:
    """watchlist_repo/alerts_repo が未指定なら検出処理をスキップし、既存動作を保つ。"""
    await screener_repo.replace_all(
        [_row("7203", 1000.0, 50)], source="mock", universe_count=1
    )
    await job_repo.create("j2", "screener_refresh")
    fake_screener = _FakeScreener(screener_repo, [_row("7203", 5000.0, 90)])

    await run_refresh_job("j2", job_repo, fake_screener)  # type: ignore[arg-type]

    job = await job_repo.get("j2")
    assert job is not None
    assert job.status == JobStatus.DONE


async def test_run_refresh_job_no_alerts_when_no_watchlist_codes(
    job_repo: JobRepository,
    screener_repo: ScreenerRepository,
    watchlist_repo: WatchlistRepository,
    alerts_repo: AlertsRepository,
) -> None:
    await screener_repo.replace_all(
        [_row("7203", 1000.0, 50)], source="mock", universe_count=1
    )
    await job_repo.create("j3", "screener_refresh")
    fake_screener = _FakeScreener(screener_repo, [_row("7203", 5000.0, 90)])

    await run_refresh_job(
        "j3",
        job_repo,
        fake_screener,  # type: ignore[arg-type]
        screener_repo=screener_repo,
        watchlist_repo=watchlist_repo,
        alerts_repo=alerts_repo,
    )

    assert await alerts_repo.list_all() == []
