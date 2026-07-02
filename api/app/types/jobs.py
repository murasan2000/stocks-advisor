from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    """ジョブのライフサイクル（粗いステータス）。

    細かい進捗は progress（AgentStep.status = AgentPhase）で表現する。
    """

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class AgentPhase(StrEnum):
    """エージェント実行ステップの状態・フェーズ。

    Job の progress（各ステップ）に付与し、UI の進捗表示に用いる。
    """

    WAITING = "waiting"
    RUNNING = "running"
    DELEGATING = "delegating"  # 親が子エージェントへ委任
    SEARCHING = "searching"  # データ収集・検索
    GENERATING_REPORT = "generating_report"  # レポート/回答生成
    DONE = "done"
    ERROR = "error"


class AgentStep(BaseModel):
    """ジョブ進捗の 1 ステップ分。

    summary には中間結果の要約が入り、フロントの進捗表示に使われる。
    """

    key: str  # 例: "orchestrator" / "general" / "company"
    label: str  # 例: "意図判定" / "一般質問エージェント"
    status: AgentPhase = AgentPhase.WAITING
    summary: str | None = None
    started_at: float | None = None
    finished_at: float | None = None


class Job(BaseModel):
    job_id: str
    query: str
    status: JobStatus
    result: str | None = None
    error: str | None = None
    progress: list[AgentStep] | None = None
    created_at: float
    updated_at: float
    completed_at: float | None = None  # done/error になった時刻
