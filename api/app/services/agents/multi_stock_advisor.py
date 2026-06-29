"""マルチエージェント版アドバイザー（Phase 3 / Phase 3.5）。

ジョブランナー向けに、各エージェントの開始・完了（中間サマリー付き）と
最終回答をイベントとしてストリームする。

Phase 3.5: 任意のエージェントを複数選択してサブパイプラインを実行できる。
選択集合は依存解決（agent_selection.resolve_agents）で前提が補完され、
選択分だけの動的サブグラフを実行する。suggestion を含まない選択では、
各エージェントのサマリーから回答を合成して answer を発行する。

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
from app.types.agents.multi_agent import MultiAgentState

__all__ = ["AGENT_SEQUENCE", "MultiStockAdvisor"]

_MAX_SUMMARY_LEN = 500

_DISCLAIMER = (
    "※本情報はAIによる分析であり、投資勧誘を目的としたものではありません。"
    "投資判断はご自身の責任で行ってください。"
)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_SUMMARY_LEN:
        return text
    return text[: _MAX_SUMMARY_LEN - 1] + "…"


def _summarize(node: str, update: dict[str, Any]) -> str:
    """各ノードの出力から進捗表示用の中間サマリーを作る。"""
    if node == "portfolio":
        data = update.get("portfolio_data")
        if not data:
            return "ポートフォリオCSVが未連携のためスキップしました"
        return (
            f"保有 {len(data['holdings'])}銘柄 / "
            f"評価額 {data['total_market_value']:,.0f}円 / "
            f"評価損益 {data['total_unrealized_pnl']:+,.0f}円"
            f"（{data['total_unrealized_pnl_pct']:+.1f}%）"
        )
    if node == "market_structure":
        analysis = update.get("market_structure")
        return analysis["summary"] if analysis else "マーケット構造の取得に失敗しました"
    if node == "screening":
        result = update.get("screening_result")
        return result["summary"] if result else "スクリーニングに失敗しました"
    if node == "market_data":
        data = update.get("market_data") or {}
        names = ", ".join(d["company_name"] for d in data.values())
        return f"{len(data)}銘柄の株価・チャート・企業情報を取得（{names}）"
    if node == "technical":
        analysis = update.get("technical_analysis") or {}
        if not analysis:
            return "テクニカル分析対象がありません"
        lines = [f"{t}: {a['summary']}" for t, a in analysis.items()]
        return _truncate("\n".join(lines))
    if node == "fundamental":
        analysis = update.get("fundamental_analysis") or {}
        if not analysis:
            return "財務分析対象がありません（指数・開示なし銘柄）"
        lines = [f"{t}: {a['summary']}" for t, a in analysis.items()]
        return _truncate("\n".join(lines))
    if node == "risk":
        assessment = update.get("risk_assessment")
        if not assessment:
            return "リスク評価に失敗しました"
        return _truncate(
            "\n".join([assessment["summary"], *assessment["suggestions"]])
        )
    if node == "suggestion":
        result = update.get("final_suggestion")
        if not result or not result["suggestions"]:
            return "回答レポートを生成しました"
        lines = [
            f"{s['company_name']}: {s['action']}（信頼度 {s['confidence']:.0%}）"
            for s in result["suggestions"]
        ]
        return _truncate("\n".join(lines))
    return "完了"


def _compose_partial_answer(collected: dict[str, str]) -> str:
    """suggestion を含まない選択時、各エージェントのサマリーから回答を合成する。"""
    lines = ["## 選択エージェントの分析結果", ""]
    for key in AGENT_ORDER:
        if key in collected:
            lines.append(f"### {AGENT_LABELS[key]}")
            lines.append(collected[key])
            lines.append("")
    lines.append("---")
    lines.append(_DISCLAIMER)
    return "\n".join(lines)


class MultiStockAdvisor:
    """マルチエージェントパイプラインを実行し、進捗イベントをストリームする。

    Args:
        agents: 実行するエージェントキーの選択。None または空でフルパイプライン。
                前提エージェントは依存解決で自動補完される。
    """

    def __init__(self, agents: list[str] | None = None) -> None:
        self._graph, self.resolved = build_graph(agents)

    async def astream_advice(
        self, query: str
    ) -> AsyncGenerator[dict[str, str]]:
        callback = get_langfuse_callback()
        config: RunnableConfig = {"callbacks": [callback]} if callback else {}

        resolved = self.resolved
        resolved_set = set(resolved)
        parents, children, roots, _terminals = build_topology(resolved)

        initial_state: MultiAgentState = {
            "query": query,
            "portfolio_data": None,
            "market_structure": None,
            "screening_result": None,
            "market_data": None,
            "technical_analysis": None,
            "fundamental_analysis": None,
            "risk_assessment": None,
            "final_suggestion": None,
            "final_answer": None,
            "errors": [],
        }

        started: set[str] = set()
        done: set[str] = set()
        collected: dict[str, str] = {}
        answer: str | None = None

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

                if node == "suggestion":
                    answer = str(update.get("final_answer") or "")

                # 全前提が完了した後続エージェントの開始を通知
                for child in children.get(node, []):
                    if child in started:
                        continue
                    if all(p in done for p in parents[child]):
                        started.add(child)
                        yield {"type": "agent_start", "agent": child}

        # suggestion を含まない選択ではサマリーから回答を合成
        if answer is None:
            answer = _compose_partial_answer(collected)
        yield {"type": "answer", "content": answer}
