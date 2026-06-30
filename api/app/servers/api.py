from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response

from app.services.agents.graph.agent_selection import AGENT_KEYS
from app.services.agents.market_agent_jp import JapanMarketAgent
from app.services.jobs.repository import JobRepository
from app.services.jobs.runner import run_advisor_job
from app.types.agents.multi_agent import empty_state
from app.types.api import (
    CreateJobResponse,
    HealthResponse,
    MarketOverviewResponse,
    StockQuery,
)
from app.types.jobs import Job, JobStatus
from app.utils.logging_config import setup_logging
from app.utils.settings import settings

_job_repo = JobRepository(settings.db_path)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    await _job_repo.initialize()
    yield


app = FastAPI(title="Stock Advisor API", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# ジョブキュー（バッチ・信頼性優先）
# ---------------------------------------------------------------------------


@app.post("/api/v1/jobs", response_model=CreateJobResponse, status_code=202)
async def create_job(request: StockQuery) -> CreateJobResponse:
    """調査ジョブを作成し job_id を即時返却する（HTTP 202 Accepted）。

    処理はバックグラウンドで実行される。
    GET /api/v1/jobs/{job_id} でステータスと結果をポーリングする。
    """
    if request.agents is not None:
        unknown = [a for a in request.agents if a not in AGENT_KEYS]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"unknown agents: {unknown}",
            )

    job_id = str(uuid.uuid4())
    await _job_repo.create(job_id, request.query)
    asyncio.create_task(
        run_advisor_job(
            job_id,
            request.query,
            _job_repo,
            agents=request.agents,
        )
    )
    return CreateJobResponse(job_id=job_id, status=JobStatus.PENDING)


@app.get("/api/v1/jobs", response_model=list[Job])
async def list_jobs(limit: int = Query(default=10, ge=1, le=50)) -> list[Job]:
    """最近のジョブ一覧を返す（最近のチャット表示用）。"""
    return await _job_repo.list(limit=limit)


@app.get("/api/v1/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    """ジョブのステータスと結果を返す（ポーリング用）。

    status が "done" になると result に最終回答が格納される。
    status が "error" になると error にエラー詳細が格納される。
    """
    job = await _job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job


# ---------------------------------------------------------------------------
# 市場サマリー（Market Agent / ダッシュボード上部の市場概況）
# ---------------------------------------------------------------------------


@app.get("/api/v1/market/overview", response_model=MarketOverviewResponse)
async def market_overview() -> MarketOverviewResponse:
    """Market Agent を単体実行し、市場全体の概況（★評価付き）を返す。

    ジョブを介さず即時に取得する軽量エンドポイント。
    取得には MarketDataProvider（EXTERNAL_API_MODE で live/mock 切替）を用いる。
    """
    overview = await JapanMarketAgent().collect(empty_state())
    if overview is None:
        raise HTTPException(status_code=503, detail="市場データを取得できませんでした")
    return MarketOverviewResponse.model_validate(overview)


# ---------------------------------------------------------------------------
# ヘルスチェック
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health_check(response: Response) -> HealthResponse:
    db_ok = await _job_repo.ping()
    db_status = "ok" if db_ok else "error"
    overall = "ok" if db_ok else "error"

    if not db_ok:
        response.status_code = 503

    return HealthResponse(
        status=overall,
        db=db_status,
        llm_provider=settings.llm_provider,
        version=app.version,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
