"""JapanMarketAgent（Market Agent 日本株版 / 市場概況）のテスト。

EXTERNAL_API_MODE のデフォルト（mock）では YahooFinanceClient が
決定論的合成データを返すため、ネットワーク・LLM 非依存で検証できる。
"""

from __future__ import annotations

from app.services.agents.market_agent_jp import (
    JapanMarketAgent,
    _score_to_rating,
    _score_to_trend,
)
from app.types.agents.multi_agent import empty_state


async def test_collect_returns_valid_overview() -> None:
    overview = await JapanMarketAgent().collect(empty_state())

    assert overview is not None
    # 日本株版の対象（日経・TOPIX・ドル円）= 3 項目。
    assert len(overview["indices"]) == 3
    assert 1 <= overview["rating"] <= 5
    assert -1.0 <= overview["macro_score"] <= 1.0
    assert overview["market_trend"] in {"強気", "中立", "弱気"}
    assert overview["summary"].startswith("市場総合評価")
    symbols = {q["symbol"] for q in overview["indices"]}
    assert symbols == {"^N225", "1306.T", "USDJPY=X"}

    topix = next(q for q in overview["indices"] if q["symbol"] == "1306.T")
    assert topix["note"] is not None
    others = [q for q in overview["indices"] if q["symbol"] != "1306.T"]
    assert all(q["note"] is None for q in others)


async def test_collect_is_deterministic() -> None:
    a = await JapanMarketAgent().collect(empty_state())
    b = await JapanMarketAgent().collect(empty_state())
    assert a is not None and b is not None
    assert a["macro_score"] == b["macro_score"]
    assert a["rating"] == b["rating"]


def test_score_to_rating_mapping() -> None:
    assert _score_to_rating(-1.0) == 1
    assert _score_to_rating(-0.5) == 2
    assert _score_to_rating(0.0) == 3
    assert _score_to_rating(0.5) == 4
    assert _score_to_rating(1.0) == 5


def test_score_to_trend_thresholds() -> None:
    assert _score_to_trend(0.5) == "強気"
    assert _score_to_trend(0.0) == "中立"
    assert _score_to_trend(-0.5) == "弱気"
