"""ジョブ実行ランナー。

ジョブ機能（バックグラウンド実行 + 進捗保存）は将来のエージェント実行でも
利用する汎用基盤。現状はスクリーナーのスナップショット更新を実行する。
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.services.jobs.repository import JobRepository
from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import ScreenerService
from app.services.watchlist.alerts import detect_alerts
from app.services.watchlist.alerts_repository import AlertsRepository
from app.services.watchlist.repository import WatchlistRepository
from app.types.api import StockRow
from app.types.jobs import AgentPhase, AgentStep, JobStatus

logger = logging.getLogger(__name__)

_JOB_TIMEOUT = 1800.0  # 全銘柄ライブ取得は時間がかかるため余裕を持たせる


async def run_refresh_job(
    job_id: str,
    repo: JobRepository,
    screener: ScreenerService,
    screener_repo: ScreenerRepository | None = None,
    watchlist_repo: WatchlistRepository | None = None,
    alerts_repo: AlertsRepository | None = None,
) -> None:
    """スクリーナーのスナップショット更新をバックグラウンドで実行する。

    screener_repo・watchlist_repo・alerts_repo が全て指定されている場合、更新前
    （screener.refresh() 呼び出し前）と更新後のウォッチ銘柄スナップショットを比較し、
    価格・スコアの閾値超え変化を alerts_repo へ保存する（issue #81。候補A:
    アプリ内通知）。いずれか None の場合は検出をスキップし、既存の動作を変えない。
    """
    log = logging.LoggerAdapter(logger, {"job_id": job_id})
    step = AgentStep(key="refresh", label="スナップショット更新")
    step.status = AgentPhase.RUNNING
    step.started_at = time.time()
    await repo.update_status(job_id, JobStatus.RUNNING)
    await repo.update_progress(job_id, [step])

    async def _progress(done: int, total: int) -> None:
        step.summary = f"{done}/{total} 銘柄を取得"
        await repo.update_progress(job_id, [step])

    detect_enabled = (
        screener_repo is not None
        and watchlist_repo is not None
        and alerts_repo is not None
    )
    watch_codes: list[str] = []
    old_rows: list[StockRow] = []
    if detect_enabled:
        assert watchlist_repo is not None and screener_repo is not None
        watch_codes = await watchlist_repo.list_codes()
        old_rows = await screener_repo.get_by_codes(watch_codes)

    try:
        count = await asyncio.wait_for(
            screener.refresh(progress=_progress), timeout=_JOB_TIMEOUT
        )
        step.status = AgentPhase.DONE
        step.summary = f"{count} 銘柄を更新しました"
        step.finished_at = time.time()
        await repo.update_progress(job_id, [step])
        await repo.update_status(job_id, JobStatus.DONE, result=f"{count}")
        log.info("refresh job completed: %d stocks", count)

        if detect_enabled and watch_codes:
            assert screener_repo is not None and alerts_repo is not None
            new_rows = await screener_repo.get_by_codes(watch_codes)
            alerts = detect_alerts(old_rows, new_rows)
            if alerts:
                await alerts_repo.create_many(alerts)
                log.info("detected %d watchlist alerts", len(alerts))
    except TimeoutError:
        log.error("refresh job timed out")
        step.status = AgentPhase.ERROR
        step.finished_at = time.time()
        await repo.update_progress(job_id, [step])
        await repo.update_status(job_id, JobStatus.ERROR, error="タイムアウトしました")
    except Exception as exc:
        log.exception("refresh job failed: %s", exc)
        step.status = AgentPhase.ERROR
        step.finished_at = time.time()
        await repo.update_progress(job_id, [step])
        await repo.update_status(job_id, JobStatus.ERROR, error=str(exc))
