"""JobRepository.find_active（多重起動防止・issue #73）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.jobs.repository import JobRepository
from app.types.jobs import JobStatus


@pytest.fixture
async def repo(tmp_path: Path) -> JobRepository:
    r = JobRepository(str(tmp_path / "jobs.db"))
    await r.initialize()
    return r


async def test_find_active_returns_none_when_no_job(repo: JobRepository) -> None:
    assert await repo.find_active("screener_refresh") is None


async def test_find_active_returns_pending_job(repo: JobRepository) -> None:
    job = await repo.create("job-1", "screener_refresh")
    found = await repo.find_active("screener_refresh")
    assert found is not None
    assert found.job_id == job.job_id


async def test_find_active_returns_running_job(repo: JobRepository) -> None:
    await repo.create("job-1", "screener_refresh")
    await repo.update_status("job-1", JobStatus.RUNNING)
    found = await repo.find_active("screener_refresh")
    assert found is not None
    assert found.job_id == "job-1"


async def test_find_active_ignores_completed_jobs(repo: JobRepository) -> None:
    await repo.create("job-1", "screener_refresh")
    await repo.update_status("job-1", JobStatus.DONE, result="ok")
    assert await repo.find_active("screener_refresh") is None


async def test_find_active_ignores_other_queries(repo: JobRepository) -> None:
    await repo.create("job-1", "何かの一般質問")
    assert await repo.find_active("screener_refresh") is None


async def test_find_active_returns_latest_when_multiple(repo: JobRepository) -> None:
    await repo.create("job-1", "screener_refresh")
    await repo.create("job-2", "screener_refresh")
    found = await repo.find_active("screener_refresh")
    assert found is not None
    assert found.job_id == "job-2"
