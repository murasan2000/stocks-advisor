"""マーケット情報収集エージェント（market.py）のテスト。

LLM 非依存にするため invoke_llm はモックに差し替える（他エージェントのテストと
同じ方針）。search_web はカテゴリごとの固定結果を返すフェイクに差し替える。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.agents import market
from app.services.agents.runner import run_agent_job
from app.services.agents.state import MarketFacts
from app.services.jobs.repository import JobRepository
from app.types.jobs import AgentPhase, JobStatus


async def _fake_llm(
    system: str, user: str, *, fallback: str, config: Any = None
) -> str:
    return f"[LLM] {user}"


async def _no_search(query: str, **kwargs: Any) -> list[Any]:
    return []


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """テスト間でカテゴリニュースのTTLキャッシュを分離する。"""
    market._fetch_category_news.cache_clear()


def test_market_categories_catalog_has_expected_ids() -> None:
    known = {c["id"] for c in market.MARKET_CATEGORIES}
    assert known == {"jp_stocks", "us_stocks"}


async def test_market_agent_reports_requested_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(market, "invoke_llm", _fake_llm)
    monkeypatch.setattr(market, "search_web", _no_search)

    answer = await market.run(categories=["jp_stocks"])
    assert "# 日本株市況" in answer
    assert "米国株市況" not in answer  # 未指定カテゴリは含めない


async def test_market_agent_defaults_to_all_categories_when_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(market, "invoke_llm", _fake_llm)
    monkeypatch.setattr(market, "search_web", _no_search)

    # 未知のカテゴリIDのみ指定した場合は全カテゴリにフォールバックする
    answer = await market.run(categories=["unknown"])
    assert "# 日本株市況" in answer
    assert "# 米国株市況" in answer


async def test_market_agent_appends_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_search(query: str, **kwargs: Any) -> list[dict[str, str]]:
        return [
            {"title": "日経平均が反発", "url": "https://e.com/1", "snippet": "概況"},
        ]

    monkeypatch.setattr(market, "invoke_llm", _fake_llm)
    monkeypatch.setattr(market, "search_web", _fake_search)

    answer = await market.run(categories=["jp_stocks"])
    assert "[LLM]" in answer  # LLM要約が呼ばれている
    assert "#### 出典" in answer
    assert "[日経平均が反発](https://e.com/1)" in answer
    assert "投資判断はご自身の責任で" in answer  # 免責


async def test_market_agent_falls_back_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # LLM 未接続でも例外を投げず、ルールベース要約にフォールバックする（ニュース有り）
    async def _fake_search(query: str, **kwargs: Any) -> list[dict[str, str]]:
        return [{"title": "日経平均が反発", "url": "https://e.com/1", "snippet": ""}]

    monkeypatch.setattr(market, "search_web", _fake_search)
    answer = await market.run(categories=["jp_stocks"])
    assert "ルールベース簡易要約" in answer
    assert "日経平均が反発" in answer


def test_rule_based_analysis_without_news() -> None:
    facts = MarketFacts(category="jp_stocks", label="日本株市況", news=[])
    result = market.rule_based_analysis(facts)
    assert "関連ニュースを取得できませんでした" in result


def test_rule_based_analysis_with_news() -> None:
    facts = MarketFacts(
        category="jp_stocks",
        label="日本株市況",
        news=[{"title": "日経平均反発", "url": "https://e.com/1", "snippet": ""}],
    )
    result = market.rule_based_analysis(facts)
    assert "日経平均反発" in result
    assert "### 注目トピック" in result


async def test_fetch_category_news_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def _counting_search(query: str, **kwargs: Any) -> list[Any]:
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(market, "search_web", _counting_search)
    await market._fetch_category_news("jp_stocks")
    await market._fetch_category_news("jp_stocks")
    assert calls == 1  # 同一カテゴリはTTL内で再取得しない
    await market._fetch_category_news("us_stocks")
    assert calls == 2  # 別カテゴリはキャッシュキーが異なる


async def test_run_agent_job_market_kind(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(market, "invoke_llm", _fake_llm)
    monkeypatch.setattr(market, "search_web", _no_search)

    repo = JobRepository(str(tmp_path / "jobs.db"))
    await repo.initialize()
    await repo.create("j3", "マーケット情報")

    await run_agent_job(
        "j3", repo, "market", "マーケット情報", categories=["jp_stocks"]
    )

    job = await repo.get("j3")
    assert job is not None
    assert job.status == JobStatus.DONE
    assert "# 日本株市況" in (job.result or "")
    assert job.progress is not None
    assert [s.key for s in job.progress] == [
        "select_categories",
        "collect",
        "analyze",
        "report",
    ]
    assert all(s.status == AgentPhase.DONE for s in job.progress)
