from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    PENDING = "pending"
    # シングルエージェント（mode=single）のフェーズ別ステータス
    RESEARCHING_WEB = "researching_web"
    RESEARCHING_EDINET = "researching_edinet"
    SYNTHESIZING = "synthesizing"
    RESPONDING = "responding"
    # マルチエージェント（mode=multi）は粗いステータス + progress で詳細を持つ
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class AgentStepStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class AgentStep(BaseModel):
    """マルチエージェント実行の1ステップ分の進捗。

    summary には各エージェントの中間結果の要約が入り、
    フロントエンドのホバー/クリックで表示される。
    """

    key: str  # 例: "portfolio"
    label: str  # 例: "ポートフォリオ分析"
    status: AgentStepStatus = AgentStepStatus.WAITING
    summary: str | None = None
    started_at: float | None = None
    finished_at: float | None = None


class Job(BaseModel):
    job_id: str
    query: str
    status: JobStatus
    result: str | None = None
    error: str | None = None
    progress: list[AgentStep] | None = None  # mode=multi のときのみ設定
    created_at: float
    updated_at: float
