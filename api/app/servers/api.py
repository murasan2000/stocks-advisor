from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile

from app.services.agents.runner import run_agent_job
from app.services.chat.repository import ChatRepository
from app.services.chat.service import accept_message, run_chat_agent_job
from app.services.jobs.repository import JobRepository
from app.services.jobs.runner import run_refresh_job
from app.services.portfolio.repository import HoldingsRepository
from app.services.portfolio.service import PortfolioService
from app.services.screener.history import fetch_candles_live_cached, synth_candles
from app.services.screener.repository import ScreenerRepository
from app.services.screener.service import ScreenerFilters, ScreenerService
from app.services.watchlist.repository import WatchlistRepository
from app.services.watchlist.service import WatchlistService
from app.types.api import (
    AgentJobRequest,
    CreateJobResponse,
    HealthResponse,
    HistoryPeriod,
    Holding,
    HoldingRequest,
    ImportResult,
    ScreenerMeta,
    StockHistory,
    StockRow,
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
_watchlist_repo = WatchlistRepository(settings.db_path)
_watchlist = WatchlistService(_watchlist_repo, _screener_repo)
_holdings_repo = HoldingsRepository(settings.db_path)
_portfolio = PortfolioService(_holdings_repo, _screener_repo)

# イベントループはタスクへ弱参照しか持たないため、参照を保持しないと
# 実行中のバックグラウンドタスクが GC で消え得る（Python 公式ドキュメントの注意）。
_background_tasks: set[asyncio.Task[None]] = set()


def _spawn(coro: Coroutine[Any, Any, None]) -> None:
    """バックグラウンドタスクを起動し、完了まで参照を保持する。"""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    await _job_repo.initialize()
    await _screener_repo.initialize()
    await _chat_repo.initialize()
    await _watchlist_repo.initialize()
    await _holdings_repo.initialize()
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
    _spawn(run_refresh_job(job_id, _job_repo, _screener))
    return CreateJobResponse(job_id=job_id, status=JobStatus.PENDING)


# ---------------------------------------------------------------------------
# ウォッチリスト
# ---------------------------------------------------------------------------


@app.get("/api/v1/watchlist", response_model=list[StockRow])
async def watchlist_list() -> list[StockRow]:
    """登録銘柄を追加日時の新しい順で返す（スナップショット結合済み）。"""
    return await _watchlist.list_rows()


@app.get("/api/v1/watchlist/codes", response_model=list[str])
async def watchlist_codes() -> list[str]:
    """登録済みコードのみを返す（スクリーナー画面の★状態判定用の軽量取得）。"""
    return await _watchlist.list_codes()


@app.post("/api/v1/watchlist/{code}", status_code=200)
async def watchlist_add(code: str) -> Response:
    """登録する（冪等）。"""
    await _watchlist.add(code)
    return Response(status_code=200)


@app.delete("/api/v1/watchlist/{code}", status_code=204)
async def watchlist_remove(code: str) -> Response:
    """解除する（未登録でもエラーにしない）。"""
    await _watchlist.remove(code)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# 保有銘柄（ポートフォリオ）
# ---------------------------------------------------------------------------


@app.get("/api/v1/portfolio/holdings", response_model=list[Holding])
async def portfolio_holdings() -> list[Holding]:
    """保有銘柄一覧を返す（スナップショット結合済み、評価損益算出済み）。"""
    return await _portfolio.list_holdings()


# 注意: /holdings/import は /holdings/{code} より前に登録する。
# Starlette のルーティングは登録順で最初にマッチしたものを使うため、
# 後ろに置くと "import" が {code} にマッチして誤ってアップサート処理に届いてしまう。
@app.post("/api/v1/portfolio/holdings/import", response_model=ImportResult)
async def portfolio_import(
    file: UploadFile = File(...),  # noqa: B008  (FastAPI 既定値の慣用)
) -> ImportResult:
    """楽天証券の保有商品一覧CSVをインポートする（アップサート、既存は削除しない）。"""
    data = await file.read()
    return await _portfolio.import_csv(data)


@app.post("/api/v1/portfolio/holdings/{code}", status_code=200)
async def portfolio_upsert(code: str, request: HoldingRequest) -> Response:
    """保有銘柄を追加/更新する（既存なら数量・平均取得単価を上書き）。"""
    await _portfolio.upsert(code, request.quantity, request.avg_cost)
    return Response(status_code=200)


@app.delete("/api/v1/portfolio/holdings/{code}", status_code=204)
async def portfolio_remove(code: str) -> Response:
    """保有銘柄を削除する（未登録でもエラーにしない）。"""
    await _portfolio.remove(code)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# 銘柄詳細チャート
# ---------------------------------------------------------------------------


@app.get("/api/v1/stocks/{code}/history", response_model=StockHistory)
async def stock_history(
    code: str,
    period: HistoryPeriod = Query(default="1y"),  # noqa: B008  (FastAPI 既定値の慣用)
) -> StockHistory:
    """1銘柄分の日足 OHLCV を返す（都度オンデマンド取得、全銘柄一括とは別経路）。

    短期キャッシュ（#37）により、同一銘柄・同一期間の再取得は高速に返る。
    """
    if settings.external_api_mode == "live":
        from app.services.external.symbols import to_yahoo_symbol

        candles = await fetch_candles_live_cached(to_yahoo_symbol(code), period)
    else:
        candles = synth_candles(code, period)
    return StockHistory(code=code, period=period, candles=candles)


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
    status_code=202,
)
async def post_message(
    conversation_id: str, request: SendMessageRequest
) -> SendMessageResponse:
    """ユーザー発言を保存し、AI 応答をエージェントジョブとして実行する。

    進捗は GET /api/v1/jobs/{job_id} でポーリングする。完了時の回答は
    Job.result に加えて会話（assistant メッセージ）にも保存される。
    """
    result = await accept_message(
        _chat_repo, _job_repo, conversation_id, request.content
    )
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    _spawn(
        run_chat_agent_job(
            result.job_id,
            _job_repo,
            _chat_repo,
            conversation_id,
            request.content,
            request.tickers,
        )
    )
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
    _spawn(
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
