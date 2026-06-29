"""エージェント選択・依存解決・動的サブグラフ構築（Phase 3.5）。

ユーザーが任意のエージェントを複数選択して実行できるようにするための中核。

- 各エージェントの実行順・表示ラベル・データ依存（前提エージェント）を一元管理する。
- 選択集合に対して前提を芋づる式に補完し（resolve_agents）、
  選択分だけの LangGraph サブグラフを動的に構築する（build_graph）。
- 進捗ストリーミング（multi_stock_advisor）も同じトポロジー情報を共有する。

依存関係（データ依存・ハード前提）::

    portfolio   ← なし
    macro       ← なし
    screening   ← なし（query から銘柄を確定。portfolio があれば利用）
    market_data ← screening
    technical   ← market_data
    fundamental ← market_data
    risk        ← market_data
    suggestion  ← 選択された他エージェントすべて（LLM 統合・特別扱い）
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.services.agents.graph.nodes.fundamental import fundamental_multi_node
from app.services.agents.graph.nodes.market_data import market_data_node
from app.services.agents.graph.nodes.market_structure import market_structure_node
from app.services.agents.graph.nodes.portfolio import portfolio_node
from app.services.agents.graph.nodes.risk import risk_node
from app.services.agents.graph.nodes.screening import screening_node
from app.services.agents.graph.nodes.suggestion import suggestion_node
from app.services.agents.graph.nodes.technical import technical_multi_node
from app.types.agents.multi_agent import MultiAgentState

# 実行順（トポロジカルソートの基準順序）と表示ラベル
AGENT_SEQUENCE: list[tuple[str, str]] = [
    ("portfolio", "ポートフォリオ分析"),
    ("market_structure", "マーケット構造分析"),
    ("screening", "銘柄スクリーニング"),
    ("market_data", "市場データ収集"),
    ("technical", "テクニカル分析"),
    ("fundamental", "財務分析"),
    ("risk", "リスク評価"),
    ("suggestion", "投資判断・提案"),
]

AGENT_ORDER: list[str] = [key for key, _ in AGENT_SEQUENCE]
AGENT_LABELS: dict[str, str] = dict(AGENT_SEQUENCE)
AGENT_KEYS: frozenset[str] = frozenset(AGENT_ORDER)

# suggestion は全エージェントの出力を統合するため、エッジ構築時に特別扱いする。
_SUGGESTION = "suggestion"

# 各エージェントの実行に必須となる先行エージェント（データ依存）。
# suggestion は「選択された他エージェントすべて」に依存するため空にしておき、
# build_topology でリーフノードから動的にエッジを張る。
HARD_PREREQS: dict[str, tuple[str, ...]] = {
    "portfolio": (),
    "market_structure": (),
    "screening": (),
    "market_data": ("screening",),
    "technical": ("market_data",),
    "fundamental": ("market_data",),
    "risk": ("market_data",),
    "suggestion": (),
}

_NODES: dict[str, Any] = {
    "portfolio": portfolio_node,
    "market_structure": market_structure_node,
    "screening": screening_node,
    "market_data": market_data_node,
    "technical": technical_multi_node,
    "fundamental": fundamental_multi_node,
    "risk": risk_node,
    "suggestion": suggestion_node,
}

_Graph = CompiledStateGraph[
    MultiAgentState, Any, MultiAgentState, MultiAgentState
]


def resolve_agents(selected: list[str] | None) -> list[str]:
    """選択集合にハード前提を補完し、実行順（AGENT_ORDER 準拠）で返す。

    - None / 空 / 不正キーのみ → 全エージェント（従来のフルパイプライン）。
    - 例: ["technical"] → ["screening", "market_data", "technical"]
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
) -> tuple[
    dict[str, list[str]], dict[str, list[str]], list[str], list[str]
]:
    """解決済みエージェント集合の DAG（parents / children / roots / terminals）を返す。

    suggestion が含まれる場合は、それ以外のリーフノード（後続を持たないノード）から
    suggestion へ fan-in する（全分析の完了を待って統合）。
    """
    rset = set(resolved)
    has_suggestion = _SUGGESTION in rset
    core = [k for k in resolved if k != _SUGGESTION]

    parents: dict[str, list[str]] = {
        k: [p for p in HARD_PREREQS[k] if p in rset] for k in core
    }
    children: dict[str, list[str]] = {k: [] for k in core}
    for node in core:
        for parent in parents[node]:
            children[parent].append(node)

    if has_suggestion:
        leaves = [k for k in core if not children[k]]
        parents[_SUGGESTION] = leaves
        children[_SUGGESTION] = []
        for leaf in leaves:
            children[leaf].append(_SUGGESTION)

    roots = [k for k in resolved if not parents.get(k)]
    terminals = [k for k in resolved if not children.get(k)]
    return parents, children, roots, terminals


@lru_cache(maxsize=64)
def _compile_graph(resolved: tuple[str, ...]) -> _Graph:
    """解決済みエージェントのタプルからサブグラフをコンパイル（結果をキャッシュ）。"""
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
            # 複数前提は join（全前提の完了を待つ）
            builder.add_edge(ps, key)
    for key in terminals:
        builder.add_edge(key, END)

    return builder.compile()


def build_graph(selected: list[str] | None) -> tuple[_Graph, list[str]]:
    """選択に対応するコンパイル済みサブグラフと解決済みエージェント順を返す。"""
    resolved = resolve_agents(selected)
    return _compile_graph(tuple(resolved)), resolved
