"""JobRepository（completed_at・進捗保存）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.jobs.repository import JobRepository
from app.types.jobs import AgentPhase, AgentStep, JobStatus


@pytest.fixture
async def repo(tmp_path: Path) -> JobRepository:
    r = JobRepository(str(tmp_path / "jobs.db"))
    await r.initialize()
    return r


async def test_create_is_pending_without_completed_at(repo: JobRepository) -> None:
    job = await repo.create("j1", "質問")
    assert job.status == JobStatus.PENDING
    fetched = await repo.get("j1")
    assert fetched is not None
    assert fetched.completed_at is None


async def test_running_does_not_set_completed_at(repo: JobRepository) -> None:
    await repo.create("j1", "q")
    await repo.update_status("j1", JobStatus.RUNNING)
    job = await repo.get("j1")
    assert job is not None
    assert job.status == JobStatus.RUNNING
    assert job.completed_at is None


async def test_done_sets_completed_at_and_result(repo: JobRepository) -> None:
    await repo.create("j1", "q")
    await repo.update_status("j1", JobStatus.DONE, result="回答")
    job = await repo.get("j1")
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.result == "回答"
    assert job.completed_at is not None


async def test_error_sets_completed_at(repo: JobRepository) -> None:
    await repo.create("j1", "q")
    await repo.update_status("j1", JobStatus.ERROR, error="失敗")
    job = await repo.get("j1")
    assert job is not None
    assert job.completed_at is not None


async def test_progress_persists_phases(repo: JobRepository) -> None:
    await repo.create("j1", "q")
    steps = [
        AgentStep(key="classify", label="意図判定", status=AgentPhase.DELEGATING),
        AgentStep(key="general", label="一般質問", status=AgentPhase.DONE),
    ]
    await repo.update_progress("j1", steps)
    job = await repo.get("j1")
    assert job is not None and job.progress is not None
    assert [s.status for s in job.progress] == [
        AgentPhase.DELEGATING,
        AgentPhase.DONE,
    ]
