from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response

from app.services.agents.runner import run_agent_job
from app.services.chat.repository import ChatRepository
from app.services.chat.service import send_message
from app.services.jobs.repository import JobRepository
from app.services.jobs.runner import run_refresh_job
from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import ScreenerFilters, ScreenerService
from app.types.api import (
    AgentJobRequest,
    CreateJobResponse,
    HealthResponse,
    ScreenerMeta,
    StocksResponse,
)
from app.types.chat import (
    Conversation,
    Message,
    SendMessageRequest,
    SendMessageResponse,
)
from app.types.jobs import Job, JobStatus
from app.utils.logging_config import setup_logging
from app.utils.settings import settings

logger = logging.getLogger(__name__)

_job_repo = JobRepository(settings.db_path)
_screener_repo = ScreenerRepository(settings.db_path)
_screener = ScreenerService(_screener_repo)
_chat_repo = ChatRepository(settings.db_path)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    await _job_repo.initialize()
    await _screener_repo.initialize()
    await _chat_repo.initialize()
    # mock モードかつキャッシュが空なら、合成データで即時シードする（開発用）。
    if settings.external_api_mode != "live" and await _screener_repo.count() == 0:
        logger.info("seeding screener snapshot with mock data")
        await _screener.refresh()
    yield


app = FastAPI(title="Stocks Advisor API", version="0.2.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# スクリーナー（株式スクリーニング）
# ---------------------------------------------------------------------------


@app.get("/api/v1/screener/stocks", response_model=StocksResponse)
async def screener_stocks(
    stage: int = Query(default=1, ge=1),
    markets: list[str] | None = Query(default=None),  # noqa: B008  (FastAPI 既定値の慣用)
    q: str | None = Query(default=None),
    per_min: float | None = Query(default=None),
    per_max: float | None = Query(default=None),
    pbr_max: float | None = Query(default=None),
    dividend_yield_min: float | None = Query(default=None),
    roe_min: float | None = Query(default=None),
    market_cap_min: float | None = Query(default=None),
    market_cap_max: float | None = Query(default=None),
    rsi_min: float | None = Query(default=None),
    rsi_max: float | None = Query(default=None),
    oversold: bool = Query(default=False),
    drop_from_high_pct: float = Query(default=50.0),
    rebound_from_low_pct: float = Query(default=10.0),
    sort_by: str = Query(default="score"),
    sort_desc: bool = Query(default=True),
) -> StocksResponse:
    """条件で絞り込んだ銘柄を段階（stage）ごとに返す。

    クライアントは next_stage が null になるまで stage を増やして取得する。
    """
    filters = ScreenerFilters(
        markets=markets or [],
        query=q,
        per_min=per_min,
        per_max=per_max,
        pbr_max=pbr_max,
        dividend_yield_min=dividend_yield_min,
        roe_min=roe_min,
        market_cap_min=market_cap_min,
        market_cap_max=market_cap_max,
        rsi_min=rsi_min,
        rsi_max=rsi_max,
        oversold_enabled=oversold,
        drop_from_high_pct=drop_from_high_pct,
        rebound_from_low_pct=rebound_from_low_pct,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    return await _screener.query(filters, stage)


@app.get("/api/v1/screener/meta", response_model=ScreenerMeta)
async def screener_meta() -> ScreenerMeta:
    """スナップショットのメタ情報（最終更新・件数・取得元）を返す。"""
    last_refresh, source, universe_count = await _screener_repo.get_meta()
    from app.services.screener.universe import load_universe, universe_source

    return ScreenerMeta(
        last_refresh=last_refresh,
        universe_count=universe_count or len(load_universe()),
        snapshot_count=await _screener_repo.count(),
        source=source or universe_source(),
    )


@app.post("/api/v1/screener/refresh", response_model=CreateJobResponse, status_code=202)
async def screener_refresh() -> CreateJobResponse:
    """スナップショット更新ジョブを作成し、バックグラウンドで実行する。

    進捗は GET /api/v1/jobs/{job_id} でポーリングできる。
    """
    job_id = str(uuid.uuid4())
    await _job_repo.create(job_id, "screener_refresh")
    asyncio.create_task(run_refresh_job(job_id, _job_repo, _screener))
    return CreateJobResponse(job_id=job_id, status=JobStatus.PENDING)


# ---------------------------------------------------------------------------
# チャット（会話・メッセージ履歴）
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/chat/conversations", response_model=Conversation, status_code=201
)
async def create_conversation() -> Conversation:
    """新しい会話を作成する。タイトルは初回メッセージから自動生成される。"""
    return await _chat_repo.create_conversation()


@app.get("/api/v1/chat/conversations", response_model=list[Conversation])
async def list_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    q: str | None = Query(default=None),
) -> list[Conversation]:
    """会話一覧を更新日時の新しい順で返す。q でタイトル部分一致検索。"""
    return await _chat_repo.list_conversations(limit=limit, query=q)


@app.delete("/api/v1/chat/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str) -> Response:
    """会話と配下のメッセージを削除する。"""
    deleted = await _chat_repo.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="conversation not found")
    return Response(status_code=204)


@app.get(
    "/api/v1/chat/conversations/{conversation_id}/messages",
    response_model=list[Message],
)
async def list_messages(conversation_id: str) -> list[Message]:
    """会話の過去メッセージを時系列で返す。"""
    if await _chat_repo.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return await _chat_repo.list_messages(conversation_id)


@app.post(
    "/api/v1/chat/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
async def post_message(
    conversation_id: str, request: SendMessageRequest
) -> SendMessageResponse:
    """ユーザー発言を保存し、AI 応答（現状モック）を生成・保存して返す。

    TODO(Phase 4/5): 応答生成を親エージェント（Job 実行）に差し替える。
    """
    result = await send_message(_chat_repo, conversation_id, request.content)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


# ---------------------------------------------------------------------------
# エージェント（親オーケストレーター / 子エージェントの単体実行）
# ---------------------------------------------------------------------------


@app.post("/api/v1/jobs", response_model=CreateJobResponse, status_code=202)
async def create_agent_job(request: AgentJobRequest) -> CreateJobResponse:
    """エージェントジョブを作成し、バックグラウンドで実行する。

    進捗・結果は GET /api/v1/jobs/{job_id} でポーリングする（Job 非同期方式）。
    kind=general/company は各子エージェントの独立実行に相当する。
    """
    job_id = str(uuid.uuid4())
    await _job_repo.create(job_id, request.query)
    asyncio.create_task(
        run_agent_job(
            job_id, _job_repo, request.kind, request.query, request.tickers
        )
    )
    return CreateJobResponse(job_id=job_id, status=JobStatus.PENDING)


# ---------------------------------------------------------------------------
# ジョブ（汎用バックグラウンド実行基盤 / 状態取得）
# ---------------------------------------------------------------------------


@app.get("/api/v1/jobs", response_model=list[Job])
async def list_jobs(limit: int = Query(default=10, ge=1, le=50)) -> list[Job]:
    return await _job_repo.list(limit=limit)


@app.get("/api/v1/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job = await _job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job


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
