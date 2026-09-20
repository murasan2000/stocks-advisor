"""エージェント（意図判定・子グラフ・親オーケストレーター・ジョブ）のテスト。

LLM 非依存にするため、一般質問エージェントの invoke_llm はモックに差し替える。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.agents import company, company_us, general, orchestrator, runtime
from app.services.agents.resolver import resolve_tickers
from app.services.agents.runner import run_agent_job
from app.services.agents.runtime import (
    classify_intent,
    classify_intent_llm,
    extract_tickers,
)
from app.services.agents.state import CompanyFacts, new_state
from app.services.jobs.repository import JobRepository
from app.services.portfolio.repository import HoldingsRepository
from app.services.watchlist.repository import WatchlistRepository
from app.types.jobs import AgentPhase, JobStatus
from app.utils.settings import settings


async def _fake_llm(
    system: str, user: str, *, fallback: str, config: Any = None
) -> str:
    return f"[LLM] {user}"


async def _fake_intent_llm(
    system: str, user: str, *, fallback: str, config: Any = None
) -> str:
    return fallback


@pytest.fixture
def fast_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 呼び出しを即時フォールバックにし、Web検索を無効化する（テスト高速化）。

    オフラインでは実接続リトライ（数秒）を待ってしまうため、オフライン経路
    そのものを検証するテスト以外はこのフィクスチャを使う。
    """
    monkeypatch.setattr(runtime, "invoke_llm", _fake_intent_llm)
    monkeypatch.setattr(general, "search_web", _no_search)
    monkeypatch.setattr(company, "search_web", _no_search)
    monkeypatch.setattr(company, "invoke_llm", _fake_intent_llm)
    monkeypatch.setattr(company_us, "search_web", _no_search)
    monkeypatch.setattr(company_us, "invoke_llm", _fake_intent_llm)


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


async def test_classify_intent_llm_offline_falls_back() -> None:
    # LLM 未接続時はルールベースにフォールバックする
    assert await classify_intent_llm("7203を分析", ["7203"]) == "company"
    assert await classify_intent_llm("PERとは", []) == "general"


def test_resolve_tickers_by_code_and_name() -> None:
    # コード直接指定
    assert resolve_tickers("7203を分析して") == ["7203"]
    # 正式名称（ユニバースの銘柄名）
    assert resolve_tickers("トヨタ自動車を分析して") == ["7203"]
    # 名称プレフィックス（「トヨタ」→ トヨタ自動車）
    assert resolve_tickers("トヨタを分析して") == ["7203"]
    # コード + 名称の混在（重複排除・出現順）
    assert resolve_tickers("7203とソニーグループを比較") == ["7203", "6758"]
    # 該当なし
    assert resolve_tickers("PERとは何ですか") == []


# ---------------------------------------------------------------------------
# 子エージェント
# ---------------------------------------------------------------------------


async def _no_search(query: str, **kwargs: Any) -> list[Any]:
    return []


async def test_general_agent_uses_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(general, "invoke_llm", _fake_llm)
    monkeypatch.setattr(general, "search_web", _no_search)
    answer = await general.run("PERとは？")
    # 検索結果なし → プロンプトは質問のみ・出典セクションなし
    assert answer == "[LLM] PERとは？"


async def test_general_agent_appends_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_search(query: str, **kwargs: Any) -> list[dict[str, str]]:
        return [
            {"title": "PER入門", "url": "https://e.com/1", "snippet": "解説"},
            {"title": "指標の見方", "url": "https://e.com/2", "snippet": ""},
        ]

    monkeypatch.setattr(general, "search_web", _fake_search)
    monkeypatch.setattr(general, "invoke_llm", _fake_llm)

    answer = await general.run("PERとは？")
    # LLM 入力に参考情報が含まれ（_fake_llm はユーザープロンプトを反射）、
    # 回答末尾に出典（Markdownリンク）が付く
    assert "参考情報（Web検索結果）" in answer
    assert "#### 出典" in answer
    assert "[PER入門](https://e.com/1)" in answer
    assert "[指標の見方](https://e.com/2)" in answer


async def test_general_agent_falls_back_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # LLM 未接続でも例外を投げず、フォールバック文言を返す
    # （検索は無効化: .env にキーがあっても実ネットワークへ出ないように）
    monkeypatch.setattr(general, "search_web", _no_search)
    answer = await general.run("PERとは？")
    assert "PERとは？" in answer
    assert answer  # 空でない


async def test_company_agent_reports_per_ticker(fast_intent: None) -> None:
    answer = await company.run("分析して", tickers=["7203", "6758"])
    # 銘柄名はユニバースから解決される
    assert "トヨタ自動車（7203）企業分析レポート" in answer
    assert "ソニーグループ（6758）企業分析レポート" in answer
    for section in ("## サマリー", "## 財務分析", "## AI評価", "## 総評"):
        assert section in answer
    assert "投資判断はご自身の責任で" in answer  # 免責


async def test_company_agent_requires_ticker(fast_intent: None) -> None:
    answer = await company.run("分析して", tickers=[])
    assert "銘柄コード" in answer


# ---------------------------------------------------------------------------
# 企業分析（子）: ポートフォリオ/ウォッチリストの保有文脈（Issue #78）
# ---------------------------------------------------------------------------


def _make_company_facts(
    *,
    holding_quantity: float | None = None,
    holding_avg_cost: float | None = None,
    watched: bool = False,
    price: float | None = 3000.0,
) -> CompanyFacts:
    """保有文脈のテスト用に最小限の CompanyFacts を組み立てる。"""
    return CompanyFacts(
        code="7203",
        name="トヨタ自動車",
        market="プライム",
        metrics={"price": price},
        business_summary="",
        news=[],
        filings=[],
        holding_quantity=holding_quantity,
        holding_avg_cost=holding_avg_cost,
        watched=watched,
    )


def test_facts_to_prompt_includes_holding_pnl() -> None:
    facts = _make_company_facts(holding_quantity=100, holding_avg_cost=2500.0)
    prompt = company._facts_to_prompt(facts)
    assert "保有中: 100株（取得単価 2,500.00円）" in prompt
    assert "含み損益: +50,000円（+20.00%）" in prompt


def test_facts_to_prompt_includes_watched() -> None:
    facts = _make_company_facts(watched=True)
    prompt = company._facts_to_prompt(facts)
    assert "ウォッチリスト登録済み" in prompt


def test_facts_to_prompt_omits_holding_context_when_neither() -> None:
    facts = _make_company_facts()
    prompt = company._facts_to_prompt(facts)
    assert "保有中" not in prompt
    assert "ウォッチリスト登録済み" not in prompt


def test_build_report_includes_holding_loss() -> None:
    # 含み損（現在値 < 取得単価）の場合も符号付きで表示される
    facts = _make_company_facts(
        holding_quantity=10, holding_avg_cost=2000.0, price=1800.0
    )
    report = company.build_report(facts, "分析")
    assert "保有中: 10株（取得単価 2,000.00円）" in report
    assert "含み損益: -2,000円（-10.00%）" in report


def test_facts_to_prompt_skips_pnl_when_price_unavailable() -> None:
    # 現在値未取得（None）でも保有数量・取得単価のみ表示し、含み損益は算出しない
    facts = _make_company_facts(
        holding_quantity=100, holding_avg_cost=2500.0, price=None
    )
    prompt = company._facts_to_prompt(facts)
    assert "保有中: 100株（取得単価 2,500.00円）" in prompt
    assert "含み損益" not in prompt


async def test_collect_populates_holding_and_watchlist_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_collect ノードが HoldingsRepository/WatchlistRepository を反映する。"""
    db_path = str(tmp_path / "app.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    monkeypatch.setattr(company, "search_web", _no_search)

    holdings_repo = HoldingsRepository(db_path)
    await holdings_repo.initialize()
    await holdings_repo.upsert("7203", 300, 2500.0)

    watchlist_repo = WatchlistRepository(db_path)
    await watchlist_repo.initialize()
    await watchlist_repo.add("6758")

    result = await company._collect(new_state("分析して", tickers=["7203", "6758"]))
    facts = result["company_facts"]

    # 7203: 保有中（ウォッチ未登録）
    assert facts["7203"]["holding_quantity"] == 300
    assert facts["7203"]["holding_avg_cost"] == 2500.0
    assert facts["7203"]["watched"] is False

    # 6758: ウォッチ登録済み（未保有）
    assert facts["6758"]["holding_quantity"] is None
    assert facts["6758"]["holding_avg_cost"] is None
    assert facts["6758"]["watched"] is True


async def test_collect_falls_back_when_holdings_table_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """holdings/watchlist テーブル未初期化でも企業分析自体は継続する。"""
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "missing.db"))
    monkeypatch.setattr(company, "search_web", _no_search)

    result = await company._collect(new_state("分析して", tickers=["7203"]))
    facts = result["company_facts"]

    assert facts["7203"]["holding_quantity"] is None
    assert facts["7203"]["watched"] is False


async def test_company_us_agent_reports_per_ticker(fast_intent: None) -> None:
    answer = await company_us.run("分析して", tickers=["AAPL", "MSFT"])
    assert "（AAPL）企業分析レポート" in answer
    assert "（MSFT）企業分析レポート" in answer
    for section in ("## サマリー", "## 財務分析", "## AI評価", "## 総評"):
        assert section in answer
    assert "投資判断はご自身の責任で" in answer  # 免責
    # EDINET相当のデータソースは持たないため開示セクションは出ない
    assert "開示" not in answer


async def test_company_us_agent_requires_ticker(fast_intent: None) -> None:
    answer = await company_us.run("分析して", tickers=[])
    assert "米国株ティッカー" in answer


# ---------------------------------------------------------------------------
# 親オーケストレーター（意図判定 → 委任）
# ---------------------------------------------------------------------------


async def test_orchestrator_routes_to_company(fast_intent: None) -> None:
    answer = await orchestrator.run("7203を分析して")
    assert "（7203）企業分析レポート" in answer


async def test_orchestrator_resolves_company_name(fast_intent: None) -> None:
    # 企業名からコードを解決して company にルーティングされる
    answer = await orchestrator.run("トヨタ自動車を分析して")
    assert "（7203）企業分析レポート" in answer


async def test_orchestrator_routes_to_general(
    monkeypatch: pytest.MonkeyPatch, fast_intent: None
) -> None:
    monkeypatch.setattr(general, "invoke_llm", _fake_llm)
    answer = await orchestrator.run("PERとは何ですか")
    assert answer == "[LLM] PERとは何ですか"


async def test_orchestrator_routes_us_ticker_to_company_us(fast_intent: None) -> None:
    # 明示指定のticker（チェックボックス選択→分析のフロー相当）でUS判定される
    answer = await orchestrator.run("分析して", tickers=["AAPL"])
    assert "（AAPL）企業分析レポート" in answer


async def test_orchestrator_routes_mixed_jp_us_tickers(fast_intent: None) -> None:
    # JP/US混在の選択でも両方のレポートが1つの回答にまとまる
    answer = await orchestrator.run("分析して", tickers=["7203", "AAPL"])
    assert "トヨタ自動車（7203）企業分析レポート" in answer
    assert "（AAPL）企業分析レポート" in answer


# ---------------------------------------------------------------------------
# ジョブ実行
# ---------------------------------------------------------------------------


async def test_run_agent_job_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast_intent: None
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
    # 進捗: classify → general が完了状態で、サマリー付きで記録されている
    assert job.progress is not None
    assert [s.key for s in job.progress] == ["classify", "general"]
    assert all(s.status == AgentPhase.DONE for s in job.progress)
    assert job.progress[0].summary == "意図: general"
    assert job.progress[0].started_at is not None


async def test_run_agent_job_company_kind(
    tmp_path: Path, fast_intent: None
) -> None:
    repo = JobRepository(str(tmp_path / "jobs.db"))
    await repo.initialize()
    await repo.create("j2", "企業分析")

    await run_agent_job("j2", repo, "company", "分析", tickers=["7203"])

    job = await repo.get("j2")
    assert job is not None
    assert job.status == JobStatus.DONE
    assert "（7203）企業分析レポート" in (job.result or "")
    # 進捗: resolve → collect → analyze → report が完了状態で記録される
    assert job.progress is not None
    assert [s.key for s in job.progress] == [
        "resolve",
        "collect",
        "analyze",
        "report",
    ]
    assert all(s.status == AgentPhase.DONE for s in job.progress)
