"""BaseAgent（核クラス）の共通動作テスト。"""

from __future__ import annotations

from typing import Any, ClassVar, TypedDict

import pytest

from app.services.agents import base
from app.services.agents.base import BaseAgent
from app.types.agents.multi_agent import empty_state


class _DummyData(TypedDict):
    value: int
    summary: str


class _DummyAgent(BaseAgent[_DummyData]):
    key: ClassVar[str] = "dummy"
    label: ClassVar[str] = "ダミー"
    state_key: ClassVar[str] = "market"
    system_prompt: ClassVar[str] = "test"

    def __init__(self, data: _DummyData | None) -> None:
        self._data = data

    async def collect(self, state: Any) -> _DummyData | None:
        return self._data

    def to_context(self, data: _DummyData) -> str:
        return str(data["value"])

    def to_summary(self, data: _DummyData) -> str:
        return f"rule:{data['value']}"

    def with_summary(self, data: _DummyData, summary: str) -> _DummyData:
        return {**data, "summary": summary}


async def test_as_node_success_uses_llm_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_summary(*args: Any, **kwargs: Any) -> str:
        return "llm-summary"

    monkeypatch.setattr(base, "generate_summary", fake_summary)

    agent = _DummyAgent({"value": 42, "summary": ""})
    node = agent.as_node()
    update = await node(empty_state(), {})

    assert update["market"]["summary"] == "llm-summary"
    assert update["market"]["value"] == 42
    assert "errors" not in update


async def test_as_node_falls_back_to_rule_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # generate_summary は LLM 失敗時に fallback を返す契約。ここではそれを再現。
    async def fake_summary(
        system_prompt: str, context: str, *, fallback: str, **kwargs: Any
    ) -> str:
        return fallback

    monkeypatch.setattr(base, "generate_summary", fake_summary)

    agent = _DummyAgent({"value": 7, "summary": ""})
    update = await agent.as_node()(empty_state(), {})
    assert update["market"]["summary"] == "rule:7"


async def test_as_node_collect_none_emits_error() -> None:
    agent = _DummyAgent(None)
    update = await agent.as_node()(empty_state(), {})

    assert update["market"] is None
    assert update["errors"][0]["agent"] == "dummy"


def test_state_update_helpers() -> None:
    agent = _DummyAgent(None)
    assert agent.empty_update() == {"market": None}
    assert agent.to_state_update({"value": 1, "summary": "s"}) == {
        "market": {"value": 1, "summary": "s"}
    }
    err = agent.error_update("boom")
    assert err["market"] is None
    assert err["errors"] == [{"agent": "dummy", "message": "boom"}]
