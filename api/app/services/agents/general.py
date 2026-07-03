"""一般質問エージェント（子）。

投資一般・日本株・用語などの質問に回答する。単一ノードのシンプルなグラフ。
本実装（Web検索・引用）は Phase 6。ここでは LLM 回答＋フォールバックの雛形。
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.runtime import invoke_llm
from app.services.agents.state import AgentState, new_state

_SYSTEM_PROMPT = (
    "あなたは日本株投資の初心者にもわかりやすく答えるアシスタントです。"
    "投資の一般知識・用語・日本株の基礎について、Markdown で簡潔に回答してください。"
    "特定銘柄の売買推奨は避け、一般的な説明に留めること。"
)


def _fallback(query: str) -> str:
    return (
        f"「{query}」についてお答えする準備をしています。\n\n"
        "現在 LLM に接続できないため、一般質問エージェントの本回答は生成できません"
        "（LLM プロバイダ設定後に利用可能になります）。"
    )


async def _answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    answer = await invoke_llm(
        _SYSTEM_PROMPT,
        state["query"],
        fallback=_fallback(state["query"]),
        config=config,
    )
    return {"answer": answer}


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("answer", _answer)
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    return builder.compile()


graph = build_graph()


async def run(query: str, config: RunnableConfig | None = None) -> str:
    """一般質問エージェントを単体実行し、回答を返す。"""
    result = await graph.ainvoke(new_state(query), config or {})
    return str(result["answer"])
