from __future__ import annotations

import asyncio
import logging
import time

from app.services.agents.graph.agent_selection import AGENT_LABELS
from app.services.agents.multi_stock_advisor import MultiStockAdvisor
from app.services.jobs.repository import JobRepository
from app.types.jobs import AgentStep, AgentStepStatus, JobStatus

logger = logging.getLogger(__name__)

_JOB_TIMEOUT = 300.0


def _initial_steps(agent_keys: list[str]) -> list[AgentStep]:
    return [AgentStep(key=key, label=AGENT_LABELS[key]) for key in agent_keys]


async def _execute_multi_job(
    job_id: str,
    query: str,
    repo: JobRepository,
    agents: list[str] | None = None,
) -> None:
    """マルチエージェントでジョブを実行し、ステップ毎に進捗を保存する。

    agents で指定したエージェントのみを実行する（前提は自動補完）。
    None でフルパイプライン。
    """
    advisor = MultiStockAdvisor(agents)
    steps = _initial_steps(advisor.resolved)
    step_by_key = {s.key: s for s in steps}
    await repo.update_status(job_id, JobStatus.RUNNING)
    await repo.update_progress(job_id, steps)

    async for event in advisor.astream_advice(query):
        if event["type"] == "agent_start":
            step = step_by_key.get(event["agent"])
            if step and step.status == AgentStepStatus.WAITING:
                step.status = AgentStepStatus.RUNNING
                step.started_at = time.time()
                await repo.update_progress(job_id, steps)
        elif event["type"] == "agent_end":
            step = step_by_key.get(event["agent"])
            if step:
                step.status = AgentStepStatus.DONE
                step.summary = event.get("summary")
                step.finished_at = time.time()
                await repo.update_progress(job_id, steps)
        elif event["type"] == "answer":
            await repo.update_status(
                job_id,
                JobStatus.DONE,
                result=event.get("content", ""),
            )


async def _mark_running_steps_error(job_id: str, repo: JobRepository) -> None:
    """異常終了時、実行中だったステップを error にして保存する。"""
    job = await repo.get(job_id)
    if not job or not job.progress:
        return
    changed = False
    for step in job.progress:
        if step.status == AgentStepStatus.RUNNING:
            step.status = AgentStepStatus.ERROR
            step.finished_at = time.time()
            changed = True
    if changed:
        await repo.update_progress(job_id, job.progress)


async def run_advisor_job(
    job_id: str,
    query: str,
    repo: JobRepository,
    agents: list[str] | None = None,
) -> None:
    """ジョブをバックグラウンドで実行し、進捗を DB に反映する。

    マルチエージェント（Phase 3）で実行する。
    agents 指定時は Phase 3.5 の選択サブパイプライン（前提は自動補完）。
    """
    log = logging.LoggerAdapter(logger, {"job_id": job_id})
    log.info("Job started (agents=%s)", agents)
    try:
        await asyncio.wait_for(
            _execute_multi_job(job_id, query, repo, agents),
            timeout=_JOB_TIMEOUT,
        )
        log.info("Job completed")
    except TimeoutError:
        log.error("Job timed out after %.0fs", _JOB_TIMEOUT)
        await _mark_running_steps_error(job_id, repo)
        await repo.update_status(
            job_id,
            JobStatus.ERROR,
            error=f"タイムアウト: {_JOB_TIMEOUT:.0f}秒以内に完了しませんでした",
        )
    except Exception as exc:
        log.exception("Job failed: %s", exc)
        await _mark_running_steps_error(job_id, repo)
        await repo.update_status(job_id, JobStatus.ERROR, error=str(exc))
