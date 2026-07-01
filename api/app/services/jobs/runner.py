"""ジョブ実行ランナー。

ジョブ機能（バックグラウンド実行 + 進捗保存）は将来のエージェント実行でも
利用する汎用基盤。現状はスクリーナーのスナップショット更新を実行する。
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.services.jobs.repository import JobRepository
from app.services.screener.service import ScreenerService
from app.types.jobs import AgentStep, AgentStepStatus, JobStatus

logger = logging.getLogger(__name__)

_JOB_TIMEOUT = 1800.0  # 全銘柄ライブ取得は時間がかかるため余裕を持たせる


async def run_refresh_job(
    job_id: str,
    repo: JobRepository,
    screener: ScreenerService,
) -> None:
    """スクリーナーのスナップショット更新をバックグラウンドで実行する。"""
    log = logging.LoggerAdapter(logger, {"job_id": job_id})
    step = AgentStep(key="refresh", label="スナップショット更新")
    step.status = AgentStepStatus.RUNNING
    step.started_at = time.time()
    await repo.update_status(job_id, JobStatus.RUNNING)
    await repo.update_progress(job_id, [step])

    async def _progress(done: int, total: int) -> None:
        step.summary = f"{done}/{total} 銘柄を取得"
        await repo.update_progress(job_id, [step])

    try:
        count = await asyncio.wait_for(
            screener.refresh(progress=_progress), timeout=_JOB_TIMEOUT
        )
        step.status = AgentStepStatus.DONE
        step.summary = f"{count} 銘柄を更新しました"
        step.finished_at = time.time()
        await repo.update_progress(job_id, [step])
        await repo.update_status(job_id, JobStatus.DONE, result=f"{count}")
        log.info("refresh job completed: %d stocks", count)
    except TimeoutError:
        log.error("refresh job timed out")
        step.status = AgentStepStatus.ERROR
        step.finished_at = time.time()
        await repo.update_progress(job_id, [step])
        await repo.update_status(job_id, JobStatus.ERROR, error="タイムアウトしました")
    except Exception as exc:
        log.exception("refresh job failed: %s", exc)
        step.status = AgentStepStatus.ERROR
        step.finished_at = time.time()
        await repo.update_progress(job_id, [step])
        await repo.update_status(job_id, JobStatus.ERROR, error=str(exc))
