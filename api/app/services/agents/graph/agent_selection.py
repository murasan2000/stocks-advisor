"""エージェントの登録・選択・LangGraph 構築。

MVP では Market Agent（市場概況）の 1 エージェントのみを登録する。
将来エージェントを追加する場合は AGENT_SEQUENCE / HARD_PREREQS / _NODES に
追記すれば、依存解決（resolve_agents）と動的グラフ構築（build_graph）が
そのまま機能する設計にしてある。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.services.agents.market_agent_jp import market_node
from app.types.agents.multi_agent import MultiAgentState

# 実行順（トポロジカルソートの基準順序）と表示ラベル。
AGENT_SEQUENCE: list[tuple[str, str]] = [
    ("market", "市場分析"),
]

AGENT_ORDER: list[str] = [key for key, _ in AGENT_SEQUENCE]
AGENT_LABELS: dict[str, str] = dict(AGENT_SEQUENCE)
AGENT_KEYS: frozenset[str] = frozenset(AGENT_ORDER)

# 各エージェントの実行に必須となる先行エージェント（データ依存）。
HARD_PREREQS: dict[str, tuple[str, ...]] = {
    "market": (),
}

_NODES: dict[str, Any] = {
    "market": market_node,
}

_Graph = CompiledStateGraph[
    MultiAgentState, Any, MultiAgentState, MultiAgentState
]


def resolve_agents(selected: list[str] | None) -> list[str]:
    """選択集合にハード前提を補完し、実行順（AGENT_ORDER 準拠）で返す。

    None / 空 / 不正キーのみ → 全エージェント（既定パイプライン）。
    """
    valid = [k for k in (selected or []) if k in AGENT_KEYS]
    if not valid:
        return list(AGENT_ORDER)

    chosen: set[str] = set()

    def _add(key: str) -> None:
        if key in chosen:
            return
        for prereq in HARD_PREREQS[key]:
            _add(prereq)
        chosen.add(key)

    for key in valid:
        _add(key)

    return [k for k in AGENT_ORDER if k in chosen]


def build_topology(
    resolved: list[str],
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str], list[str]]:
    """解決済み集合の DAG（parents / children / roots / terminals）を返す。"""
    rset = set(resolved)
    parents: dict[str, list[str]] = {
        k: [p for p in HARD_PREREQS[k] if p in rset] for k in resolved
    }
    children: dict[str, list[str]] = {k: [] for k in resolved}
    for node in resolved:
        for parent in parents[node]:
            children[parent].append(node)

    roots = [k for k in resolved if not parents.get(k)]
    terminals = [k for k in resolved if not children.get(k)]
    return parents, children, roots, terminals


@lru_cache(maxsize=8)
def _compile_graph(resolved: tuple[str, ...]) -> _Graph:
    """解決済みエージェントのタプルからグラフをコンパイル（結果をキャッシュ）。"""
    nodes = list(resolved)
    builder = StateGraph(MultiAgentState)
    for key in nodes:
        builder.add_node(key, _NODES[key])

    parents, _children, _roots, terminals = build_topology(nodes)
    for key in nodes:
        ps = parents.get(key, [])
        if not ps:
            builder.add_edge(START, key)
        elif len(ps) == 1:
            builder.add_edge(ps[0], key)
        else:
            builder.add_edge(ps, key)
    for key in terminals:
        builder.add_edge(key, END)

    return builder.compile()


def build_graph(selected: list[str] | None) -> tuple[_Graph, list[str]]:
    """選択に対応するコンパイル済みグラフと解決済みエージェント順を返す。"""
    resolved = resolve_agents(selected)
    return _compile_graph(tuple(resolved)), resolved
