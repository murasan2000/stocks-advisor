"""一般質問エージェント（子）。

投資一般・日本株・用語などの質問に回答する。グラフは「Web検索（search）→
回答生成（answer）」の 2 ノード。検索は共通ツール（services/search/web）を
使い、結果は出典（引用リンク）として回答末尾に付与する。

検索キー未設定・検索失敗時は検索なしで LLM 知識のみの回答に自動フォールバック。
LLM 失敗時はフォールバック文言を返す（オフラインでも動作）。
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.runtime import invoke_llm
from app.services.agents.state import AgentState, new_state
from app.services.search.web import SearchResult, search_web

_SYSTEM_PROMPT = (
    "あなたは日本株投資の初心者にもわかりやすく答えるアシスタントです。"
    "投資の一般知識・用語・日本株の基礎について、Markdown で簡潔に回答してください。"
    "特定銘柄の売買推奨は避け、一般的な説明に留めること。\n"
    "参考情報が与えられた場合は、事実の裏付けとして活用し、"
    "参照した情報には文中で [1] のように番号で言及すること。"
)


def _build_user_prompt(query: str, results: list[SearchResult]) -> str:
    """質問と検索結果（あれば）を LLM 入力に整形する。"""
    if not results:
        return query
    lines = [query, "", "## 参考情報（Web検索結果）"]
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] {r['title']}")
        if r["snippet"]:
            lines.append(f"    {r['snippet'][:300]}")
    return "\n".join(lines)


def _sources_section(results: list[SearchResult]) -> str:
    """出典セクション（Markdown リンク）を組み立てる。"""
    if not results:
        return ""
    lines = ["", "---", "#### 出典"]
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. [{r['title']}]({r['url']})")
    return "\n".join(lines)


def _fallback(query: str) -> str:
    return (
        f"「{query}」についてお答えする準備をしています。\n\n"
        "現在 LLM に接続できないため、一般質問エージェントの本回答は生成できません"
        "（LLM プロバイダ設定後に利用可能になります）。"
    )


async def _search(state: AgentState) -> dict[str, Any]:
    """質問に関連する Web 情報を収集する（キー未設定なら空のまま継続）。"""
    results = await search_web(state["query"], max_results=5)
    return {"search_results": results}


async def _answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """検索結果を参考情報として LLM で回答を生成し、出典を付与する。"""
    results = state["search_results"]
    answer = await invoke_llm(
        _SYSTEM_PROMPT,
        _build_user_prompt(state["query"], results),
        fallback=_fallback(state["query"]),
        config=config,
    )
    return {"answer": answer + _sources_section(results)}


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("search", _search)
    builder.add_node("answer", _answer)
    builder.add_edge(START, "search")
    builder.add_edge("search", "answer")
    builder.add_edge("answer", END)
    return builder.compile()


graph = build_graph()


async def run(query: str, config: RunnableConfig | None = None) -> str:
    """一般質問エージェントを単体実行し、回答を返す。"""
    result = await graph.ainvoke(new_state(query), config or {})
    return str(result["answer"])
