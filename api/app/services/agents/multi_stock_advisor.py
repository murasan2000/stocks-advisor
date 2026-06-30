"""エージェントパイプラインのオーケストレーター。

ジョブランナー向けに、各エージェントの開始・完了（中間サマリー付き）と
最終回答をイベントとしてストリームする。MVP では Market Agent のみだが、
エージェント追加時もこの仕組み（依存解決 → 動的グラフ → 進捗ストリーム）を
そのまま利用できる。

Yields:
    {"type": "agent_start", "agent": str}
    {"type": "agent_end",   "agent": str, "summary": str}
    {"type": "answer",      "content": str}
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from app.services.agents.graph.agent_selection import (
    AGENT_LABELS,
    AGENT_ORDER,
    AGENT_SEQUENCE,
    build_graph,
    build_topology,
)
from app.services.tracing.langfuse import get_langfuse_callback
from app.types.agents.multi_agent import MultiAgentState, empty_state

__all__ = ["AGENT_SEQUENCE", "MultiStockAdvisor"]

_DISCLAIMER = (
    "※本情報はAIによる分析であり、投資勧誘を目的としたものではありません。"
    "投資判断はご自身の責任で行ってください。"
)


def _summarize(node: str, update: dict[str, Any]) -> str:
    """各ノードの出力から進捗表示用の中間サマリーを作る。"""
    if node == "market":
        analysis = update.get("market")
        return analysis["summary"] if analysis else "市場概況の取得に失敗しました"
    return "完了"


def _compose_answer(collected: dict[str, str]) -> str:
    """各エージェントのサマリーから回答 Markdown を合成する。"""
    lines: list[str] = []
    for key in AGENT_ORDER:
        if key in collected:
            lines.append(f"## {AGENT_LABELS[key]}")
            lines.append(collected[key])
            lines.append("")
    lines.append("---")
    lines.append(_DISCLAIMER)
    return "\n".join(lines)


class MultiStockAdvisor:
    """エージェントパイプラインを実行し、進捗イベントをストリームする。

    Args:
        agents: 実行するエージェントキーの選択。None または空で既定パイプライン。
                前提エージェントは依存解決で自動補完される。
    """

    def __init__(self, agents: list[str] | None = None) -> None:
        self._graph, self.resolved = build_graph(agents)

    async def astream_advice(self, query: str) -> AsyncGenerator[dict[str, str]]:
        callback = get_langfuse_callback()
        config: RunnableConfig = {"callbacks": [callback]} if callback else {}

        resolved = self.resolved
        resolved_set = set(resolved)
        parents, children, roots, _terminals = build_topology(resolved)

        initial_state: MultiAgentState = empty_state(query)

        started: set[str] = set()
        done: set[str] = set()
        collected: dict[str, str] = {}

        # 前提を持たないルートエージェントの開始を通知
        for root in roots:
            started.add(root)
            yield {"type": "agent_start", "agent": root}

        async for chunk in self._graph.astream(initial_state, config=config):
            for node_name, node_update in chunk.items():
                node = str(node_name)
                if node not in resolved_set:
                    continue
                update = cast(dict[str, Any], node_update or {})
                done.add(node)

                summary = _summarize(node, update)
                collected[node] = summary
                yield {"type": "agent_end", "agent": node, "summary": summary}

                # 全前提が完了した後続エージェントの開始を通知
                for child in children.get(node, []):
                    if child in started:
                        continue
                    if all(p in done for p in parents[child]):
                        started.add(child)
                        yield {"type": "agent_start", "agent": child}

        yield {"type": "answer", "content": _compose_answer(collected)}
