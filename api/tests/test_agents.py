"""エージェント（意図判定・子グラフ・親オーケストレーター・ジョブ）のテスト。

LLM 非依存にするため、一般質問エージェントの invoke_llm はモックに差し替える。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.agents import company, general, orchestrator
from app.services.agents.runner import run_agent_job
from app.services.agents.runtime import classify_intent, extract_tickers
from app.services.jobs.repository import JobRepository
from app.types.jobs import JobStatus


async def _fake_llm(
    system: str, user: str, *, fallback: str, config: Any = None
) -> str:
    return f"[LLM] {user}"


# ---------------------------------------------------------------------------
# 純粋ロジック
# ---------------------------------------------------------------------------


def test_extract_tickers() -> None:
    assert extract_tickers("7203 と 6758 を比較") == ["7203", "6758"]
    assert extract_tickers("167Aはどう？") == ["167A"]
    assert extract_tickers("7203.T の株価") == ["7203"]
    assert extract_tickers("こんにちは") == []
    assert extract_tickers("12345 は5桁で対象外") == []


def test_classify_intent() -> None:
    # 銘柄コードが特定できた場合のみ company（曖昧なキーワード推定はしない）
    assert classify_intent("7203の株価", ["7203"]) == "company"
    assert classify_intent("トヨタの業績を分析して", []) == "general"
    assert classify_intent("PERとは何ですか", []) == "general"


# ---------------------------------------------------------------------------
# 子エージェント
# ---------------------------------------------------------------------------


async def test_general_agent_uses_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(general, "invoke_llm", _fake_llm)
    answer = await general.run("PERとは？")
    assert answer == "[LLM] PERとは？"


async def test_general_agent_falls_back_offline() -> None:
    # LLM 未接続でも例外を投げず、フォールバック文言を返す
    answer = await general.run("PERとは？")
    assert "PERとは？" in answer
    assert answer  # 空でない


async def test_company_agent_reports_per_ticker() -> None:
    answer = await company.run("分析して", tickers=["7203", "6758"])
    assert "7203 企業分析レポート" in answer
    assert "6758 企業分析レポート" in answer
    assert "サマリー" in answer


async def test_company_agent_requires_ticker() -> None:
    answer = await company.run("分析して", tickers=[])
    assert "銘柄コード" in answer


# ---------------------------------------------------------------------------
# 親オーケストレーター（意図判定 → 委任）
# ---------------------------------------------------------------------------


async def test_orchestrator_routes_to_company() -> None:
    answer = await orchestrator.run("7203を分析して")
    assert "7203 企業分析レポート" in answer


async def test_orchestrator_routes_to_general(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(general, "invoke_llm", _fake_llm)
    answer = await orchestrator.run("PERとは何ですか")
    assert answer == "[LLM] PERとは何ですか"


# ---------------------------------------------------------------------------
# ジョブ実行
# ---------------------------------------------------------------------------


async def test_run_agent_job_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(general, "invoke_llm", _fake_llm)
    repo = JobRepository(str(tmp_path / "jobs.db"))
    await repo.initialize()
    await repo.create("j1", "PERとは")

    await run_agent_job("j1", repo, "auto", "PERとは何ですか")

    job = await repo.get("j1")
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.result == "[LLM] PERとは何ですか"
    assert job.completed_at is not None
    # 進捗ステップが記録されている（classify → general）
    assert job.progress is not None
    assert [s.key for s in job.progress] == ["classify", "general"]


async def test_run_agent_job_company_kind(tmp_path: Path) -> None:
    repo = JobRepository(str(tmp_path / "jobs.db"))
    await repo.initialize()
    await repo.create("j2", "企業分析")

    await run_agent_job("j2", repo, "company", "分析", tickers=["7203"])

    job = await repo.get("j2")
    assert job is not None
    assert job.status == JobStatus.DONE
    assert "7203 企業分析レポート" in (job.result or "")
