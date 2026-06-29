"""エージェント共通のランタイムヘルパー（Phase 3.7）。

各分析エージェントのサブグラフ（collect → summarize）の summarize ステップが
共通で使う LLM 要約処理を提供する。LLM 失敗時はルールベースの fallback を返す。
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.services.llm.provider import LLMProviderFactory
from app.utils.retry import ainvoke_with_retry

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 120.0


async def generate_summary(
    system_prompt: str,
    context: str,
    *,
    fallback: str,
    config: RunnableConfig | None = None,
) -> str:
    """収集済みデータを LLM で要約する。失敗時は fallback を返す。

    Args:
        system_prompt: エージェントの役割・出力指示
        context: 収集済みデータを整形したテキスト
        fallback: LLM 失敗時に返すルールベースの要約
        config: LangGraph から伝播する RunnableConfig（トレース等）
    """
    llm = LLMProviderFactory.get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ]
    try:
        response = await ainvoke_with_retry(
            lambda: asyncio.wait_for(llm.ainvoke(messages, config), _LLM_TIMEOUT)
        )
        text = str(response.content).strip()
        return text or fallback
    except Exception as exc:
        logger.error("generate_summary failed: %s", exc, exc_info=True)
        return fallback
