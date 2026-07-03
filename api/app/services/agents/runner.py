"""エージェントジョブの実行（非同期 + 進捗保存）。

kind に応じてグラフを選び、astream で 1 ノードずつ進捗（AgentStep）を保存しながら
実行する。応答は Job.result に格納し、クライアントはポーリングで受け取る。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.services.agents import company, general, orchestrator
from app.services.agents.runtime import build_run_config
from app.services.agents.state import new_state
from app.services.jobs.repository import JobRepository
from app.types.jobs import AgentPhase, AgentStep, JobStatus

logger = logging.getLogger(__name__)

_AGENT_TIMEOUT = 300.0

# kind -> 実行するグラフ（auto は親オーケストレーター）
_GRAPHS: dict[str, Any] = {
    "auto": orchestrator.graph,
    "general": general.graph,
    "company": company.graph,
}

# グラフのノード名 -> (表示ラベル, フェーズ)。進捗表示に用いる。
_NODE_META: dict[str, tuple[str, AgentPhase]] = {
    "classify": ("意図判定", AgentPhase.DELEGATING),
    "general": ("一般質問エージェント", AgentPhase.GENERATING_REPORT),
    "company": ("企業分析エージェント", AgentPhase.GENERATING_REPORT),
    "resolve": ("対象銘柄の特定", AgentPhase.SEARCHING),
    "report": ("レポート生成", AgentPhase.GENERATING_REPORT),
    "answer": ("回答生成", AgentPhase.GENERATING_REPORT),
}


async def _stream_graph(
    job_id: str, repo: JobRepository, graph: Any, state: Any, config: Any
) -> str:
    """グラフを astream で実行し、ノード完了ごとに進捗を保存する。回答を返す。"""
    steps: list[AgentStep] = []
    answer = ""
    async for chunk in graph.astream(state, config):
        for node, update in chunk.items():
            label, phase = _NODE_META.get(str(node), (str(node), AgentPhase.RUNNING))
            now = time.time()
            steps.append(
                AgentStep(
                    key=str(node),
                    label=label,
                    status=AgentPhase.DONE,
                    started_at=now,
                    finished_at=now,
                )
            )
            await repo.update_progress(job_id, steps)
            if isinstance(update, dict) and update.get("answer"):
                answer = str(update["answer"])
    return answer


async def run_agent_job(
    job_id: str,
    repo: JobRepository,
    kind: str,
    query: str,
    tickers: list[str] | None = None,
) -> None:
    """エージェントジョブをバックグラウンドで実行し、進捗・結果を保存する。"""
    log = logging.LoggerAdapter(logger, {"job_id": job_id})
    graph = _GRAPHS.get(kind, orchestrator.graph)
    state = new_state(query, tickers)
    config = build_run_config(f"agent:{kind}")
    await repo.update_status(job_id, JobStatus.RUNNING)
    try:
        answer = await asyncio.wait_for(
            _stream_graph(job_id, repo, graph, state, config), _AGENT_TIMEOUT
        )
        await repo.update_status(
            job_id, JobStatus.DONE, result=answer or "(回答が空でした)"
        )
        log.info("agent job completed (kind=%s)", kind)
    except TimeoutError:
        log.error("agent job timed out (kind=%s)", kind)
        await repo.update_status(job_id, JobStatus.ERROR, error="タイムアウトしました")
    except Exception as exc:
        log.exception("agent job failed: %s", exc)
        await repo.update_status(job_id, JobStatus.ERROR, error=str(exc))
