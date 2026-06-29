from __future__ import annotations

from pydantic import BaseModel

from app.types.jobs import JobStatus


class StockQuery(BaseModel):
    query: str
    # Phase 3.5: 実行するエージェントの選択。
    # None / 空でフルパイプライン。前提エージェントは自動補完される。
    agents: list[str] | None = None


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class HealthResponse(BaseModel):
    status: str
    db: str
    llm_provider: str
    version: str

