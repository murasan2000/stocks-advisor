"""エージェントの核となる基底クラス（BaseAgent）。

エージェントの乱立を防ぐため、全エージェントが共有する「収集 → 要約」の
スケルトンをここに集約する。各エージェントはこのクラスを継承し、
データ収集（collect）と整形（to_context / to_summary / with_summary）だけを
実装すればよい。

LangGraph 構成は維持する。``as_node()`` が「collect → summarize」を行う
1 つの LangGraph ノードを返し、外側のパイプライングラフ（agent_selection）に
登録される。（従来 nodes/ に散在していた「収集 → LLM要約」パターンの一般化。）

要約は LLM（generate_summary）で行い、失敗時は to_summary のルールベース
要約へフォールバックする。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from langchain_core.runnables import RunnableConfig

from app.services.agents.graph.agent_runtime import generate_summary
from app.types.agents.multi_agent import AgentError, MultiAgentState

logger = logging.getLogger(__name__)

NodeFn = Callable[[MultiAgentState, RunnableConfig], Awaitable[dict[str, Any]]]


class BaseAgent[TData](ABC):
    """全エージェントの基底クラス。

    サブクラスは ``key`` / ``label`` / ``state_key`` / ``system_prompt`` を定義し、
    ``collect`` ・ ``to_context`` ・ ``to_summary`` ・ ``with_summary`` を実装する。

    Attributes:
        key: エージェント識別子（例: "market"）。グラフ/選択 UI のキー。
        label: 表示ラベル（例: "市場分析"）。
        state_key: 結果を書き込む MultiAgentState のキー（例: "market"）。
        system_prompt: LLM 要約時のシステムプロンプト。
    """

    key: ClassVar[str]
    label: ClassVar[str]
    state_key: ClassVar[str]
    system_prompt: ClassVar[str]

    # ------------------------------------------------------------------
    # サブクラスが実装する抽象メソッド
    # ------------------------------------------------------------------

    @abstractmethod
    async def collect(self, state: MultiAgentState) -> TData | None:
        """データを収集し、ルールベースの結果（要約込み）を組み立てる。

        取得対象が無い・失敗した場合は None を返す（エラー扱いになる）。
        """

    @abstractmethod
    def to_context(self, data: TData) -> str:
        """LLM 要約に渡す入力テキストを組み立てる。"""

    @abstractmethod
    def to_summary(self, data: TData) -> str:
        """ルールベースの要約（LLM 失敗時の fallback）を返す。"""

    @abstractmethod
    def with_summary(self, data: TData, summary: str) -> TData:
        """data の要約フィールドを差し替えた新しい data を返す。"""

    # ------------------------------------------------------------------
    # 既定実装（必要に応じてオーバーライド可）
    # ------------------------------------------------------------------

    def to_state_update(self, data: TData) -> dict[str, Any]:
        """収集結果を MultiAgentState への更新に変換する。"""
        return {self.state_key: data}

    def empty_update(self) -> dict[str, Any]:
        """収集失敗時の MultiAgentState への更新（結果は None）。"""
        return {self.state_key: None}

    def error_update(self, message: str) -> dict[str, Any]:
        """エラー時の MultiAgentState 更新（結果 None + errors 追記）。"""
        return {
            **self.empty_update(),
            "errors": [AgentError(agent=self.key, message=message)],
        }

    # ------------------------------------------------------------------
    # 実行（collect → summarize）
    # ------------------------------------------------------------------

    async def _summarize(
        self, data: TData, config: RunnableConfig | None
    ) -> TData:
        """収集済みデータを LLM で要約し、要約を反映した data を返す。

        LLM 失敗時は to_summary のルールベース要約へフォールバックする。
        """
        summary = await generate_summary(
            self.system_prompt,
            self.to_context(data),
            fallback=self.to_summary(data),
            config=config,
        )
        return self.with_summary(data, summary)

    async def analyze(
        self, state: MultiAgentState, config: RunnableConfig | None = None
    ) -> TData | None:
        """collect → LLM 要約 を実行し、要約済みデータを返す。

        グラフ外（例: 市場サマリー API）からエージェントを単体利用する入口。
        """
        data = await self.collect(state)
        if data is None:
            return None
        return await self._summarize(data, config)

    def as_node(self) -> NodeFn:
        """collect → summarize を行う LangGraph ノード（外側グラフに登録）を返す。

        前段でエラーが起きても他エージェントの実行を止めないよう、例外は
        errors に載せて握りつぶす（部分的な結果でレポートを生成できる）。
        """

        async def node(
            state: MultiAgentState, config: RunnableConfig
        ) -> dict[str, Any]:
            try:
                data = await self.collect(state)
            except Exception as exc:  # noqa: BLE001 - エラーは state に載せて続行
                logger.error("%s collect failed: %s", self.key, exc, exc_info=True)
                return self.error_update(str(exc))
            if data is None:
                return self.error_update("取得に失敗しました")
            return self.to_state_update(await self._summarize(data, config))

        return node
