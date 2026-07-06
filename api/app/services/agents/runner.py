"""エージェントジョブの実行（非同期 + 進捗保存）。

kind に応じてグラフを選び、実行プラン（想定ステップ列）を事前登録した上で、
astream の更新ごとに「実行中 → 完了」の遷移とサマリーを保存する。
auto（親）の場合は classify の結果を見て委任先ステップを動的に追加する。
応答は Job.result に格納し、クライアントはポーリングで受け取る。
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
_SUMMARY_MAX = 120

# kind -> 実行するグラフ（auto は親オーケストレーター）
_GRAPHS: dict[str, Any] = {
    "auto": orchestrator.graph,
    "general": general.graph,
    "company": company.graph,
}

# kind -> 事前登録する実行プラン（ノードkey列）。auto は classify 後に動的追加。
_PLANS: dict[str, list[str]] = {
    "auto": ["classify"],
    "general": ["search", "answer"],
    "company": ["resolve", "collect", "analyze", "report"],
}

# ノードkey -> (表示ラベル, 実行中フェーズ)
_NODE_META: dict[str, tuple[str, AgentPhase]] = {
    "classify": ("意図判定", AgentPhase.DELEGATING),
    "general": ("一般質問エージェント", AgentPhase.GENERATING_REPORT),
    "company": ("企業分析エージェント", AgentPhase.SEARCHING),
    "resolve": ("対象銘柄の特定", AgentPhase.SEARCHING),
    "collect": ("情報収集", AgentPhase.SEARCHING),
    "analyze": ("AI分析", AgentPhase.GENERATING_REPORT),
    "report": ("レポート生成", AgentPhase.GENERATING_REPORT),
    "search": ("Web検索", AgentPhase.SEARCHING),
    "answer": ("回答生成", AgentPhase.GENERATING_REPORT),
}


def _truncate(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= _SUMMARY_MAX:
        return flat
    return flat[: _SUMMARY_MAX - 1] + "…"


def _summarize(node: str, update: dict[str, Any]) -> str | None:
    """ノード完了時のサマリーを作る。"""
    if node == "classify":
        intent = str(update.get("intent") or "?")
        tickers = update.get("tickers") or []
        target = f" / 対象: {', '.join(tickers)}" if tickers else ""
        return f"意図: {intent}{target}"
    if node == "resolve":
        tickers = update.get("tickers") or []
        return f"対象: {', '.join(tickers)}" if tickers else "対象銘柄なし"
    if node == "search":
        results = update.get("search_results") or []
        return f"参考情報 {len(results)} 件を取得"
    if node == "collect":
        facts = update.get("company_facts") or {}
        return f"{len(facts)} 銘柄の情報を収集"
    if node == "analyze":
        analyses = update.get("company_analyses") or {}
        return f"{len(analyses)} 銘柄のAI分析が完了"
    answer = update.get("answer")
    return _truncate(str(answer)) if answer else None


class _ProgressTracker:
    """実行プランに沿って AgentStep の遷移（待機→実行中→完了）を管理する。"""

    def __init__(self, job_id: str, repo: JobRepository, plan: list[str]) -> None:
        self._job_id = job_id
        self._repo = repo
        self._steps: list[AgentStep] = [self._new_step(key) for key in plan]

    @staticmethod
    def _new_step(key: str) -> AgentStep:
        label, _ = _NODE_META.get(key, (key, AgentPhase.RUNNING))
        return AgentStep(key=key, label=label)

    def _find(self, key: str) -> AgentStep | None:
        return next((s for s in self._steps if s.key == key), None)

    def _start_next_waiting(self) -> None:
        """先頭の waiting ステップを実行中フェーズへ進める。"""
        for step in self._steps:
            if step.status == AgentPhase.WAITING:
                _, phase = _NODE_META.get(step.key, (step.key, AgentPhase.RUNNING))
                step.status = phase
                step.started_at = time.time()
                return

    async def begin(self) -> None:
        self._start_next_waiting()
        await self._save()

    async def extend(self, key: str) -> None:
        """プランにステップを動的追加する（auto の委任先など）。"""
        if self._find(key) is None:
            self._steps.append(self._new_step(key))
        await self._save()

    async def complete(self, key: str, summary: str | None) -> None:
        step = self._find(key)
        if step is None:
            step = self._new_step(key)
            self._steps.append(step)
        step.status = AgentPhase.DONE
        step.summary = summary
        step.finished_at = time.time()
        if step.started_at is None:
            step.started_at = step.finished_at
        self._start_next_waiting()
        await self._save()

    async def fail_running(self) -> None:
        """異常終了時、未完了のステップを error にする。"""
        changed = False
        for step in self._steps:
            if step.status not in (AgentPhase.DONE, AgentPhase.ERROR):
                step.status = AgentPhase.ERROR
                step.finished_at = time.time()
                changed = True
        if changed:
            await self._save()

    async def _save(self) -> None:
        await self._repo.update_progress(self._job_id, self._steps)


async def _stream_graph(
    tracker: _ProgressTracker, kind: str, state: Any, config: Any
) -> str:
    """グラフを astream で実行し、進捗遷移を保存しながら回答を返す。"""
    graph = _GRAPHS.get(kind, orchestrator.graph)
    await tracker.begin()

    answer = ""
    async for chunk in graph.astream(state, config):
        for node_name, node_update in chunk.items():
            node = str(node_name)
            update = node_update if isinstance(node_update, dict) else {}
            # auto: 意図判定の結果を見て委任先ステップをプランに追加
            if kind == "auto" and node == "classify":
                intent = str(update.get("intent") or "general")
                await tracker.extend(intent)
            await tracker.complete(node, _summarize(node, update))
            if update.get("answer"):
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
    state = new_state(query, tickers)
    config = build_run_config(f"agent:{kind}")
    tracker = _ProgressTracker(job_id, repo, list(_PLANS.get(kind, [])))
    started = time.monotonic()
    await repo.update_status(job_id, JobStatus.RUNNING)
    try:
        answer = await asyncio.wait_for(
            _stream_graph(tracker, kind, state, config), _AGENT_TIMEOUT
        )
        await repo.update_status(
            job_id, JobStatus.DONE, result=answer or "(回答が空でした)"
        )
        log.info(
            "agent job completed (kind=%s, %.1fs)", kind, time.monotonic() - started
        )
    except TimeoutError:
        log.error("agent job timed out (kind=%s)", kind)
        await tracker.fail_running()
        await repo.update_status(job_id, JobStatus.ERROR, error="タイムアウトしました")
    except Exception as exc:
        log.exception("agent job failed: %s", exc)
        await tracker.fail_running()
        await repo.update_status(job_id, JobStatus.ERROR, error=str(exc))
