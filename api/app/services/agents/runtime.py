"""エージェント共通のランタイムヘルパー。

- LLM アクセスは invoke_llm に一本化（失敗時は必ず fallback を返す）。
- 実行設定（Langfuse callback 付き RunnableConfig）はトップで 1 度組み立て、
  親 → 子へそのまま伝播させることで、子 run が親 run にネストする。
- 意図判定・銘柄抽出のような純粋ロジックはここに切り出してテスト可能にする。
"""

from __future__ import annotations

import asyncio
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.services.llm.provider import LLMProviderFactory
from app.services.tracing.langfuse import get_langfuse_callback
from app.utils.retry import ainvoke_with_retry

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 120.0

# 日本株の証券コード（4文字。1・3文字目は数字、2・4文字目は英数字）。
# 例: "7203"（全数字）、"167A"（新形式の英数字コード）。
_CODE_RE = re.compile(
    r"(?<![0-9A-Za-z])[0-9][0-9A-Za-z][0-9][0-9A-Za-z](?![0-9A-Za-z])"
)


async def invoke_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    fallback: str,
    config: RunnableConfig | None = None,
) -> str:
    """LLM を呼び出す。失敗時（未接続・タイムアウト等）は fallback を返す。

    これによりオフライン/テストでもエージェントは動作する。
    """
    llm = LLMProviderFactory.get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    try:
        response = await ainvoke_with_retry(
            lambda: asyncio.wait_for(llm.ainvoke(messages, config), _LLM_TIMEOUT)
        )
        return str(response.content).strip() or fallback
    except Exception as exc:
        logger.warning("LLM invocation failed, using fallback: %s", exc)
        return fallback


def build_run_config(run_name: str) -> RunnableConfig:
    """Langfuse callback 付きの RunnableConfig を組み立てる（トレースのルート）。

    これを graph.ainvoke / astream に渡すと、以降の子グラフ・LLM 呼び出しは
    同じトレースにネストされる。
    """
    config: RunnableConfig = {"run_name": run_name}
    callback = get_langfuse_callback()
    if callback is not None:
        config["callbacks"] = [callback]
    return config


def extract_tickers(text: str) -> list[str]:
    """テキストから証券コードを抽出する（重複排除・出現順）。"""
    seen: dict[str, None] = {}
    for m in _CODE_RE.findall(text):
        seen.setdefault(m.upper(), None)
    return list(seen)


def classify_intent(query: str, tickers: list[str]) -> str:
    """ルールベースの意図判定（"general" | "company"）。LLM 失敗時のフォールバック。

    分析対象の銘柄が特定できた場合のみ company。キーワードによる曖昧な推定は
    誤ルーティングを招くため行わない。
    """
    return "company" if tickers else "general"


_INTENT_SYSTEM_PROMPT = (
    "あなたは投資アシスタントのルーターです。ユーザーの質問を次の2種類に分類し、"
    "分類名だけを小文字1単語で出力してください。\n"
    "- company: 特定の企業・銘柄についての分析/評価/売買判断を求めている\n"
    "- general: 投資の一般知識・用語・市場全般など、特定銘柄に依らない質問\n"
    "出力は company または general のみ。説明は不要。"
)


async def classify_intent_llm(
    query: str,
    tickers: list[str],
    config: RunnableConfig | None = None,
) -> str:
    """LLM による意図判定。銘柄が特定済みなら company 確定、LLM 失敗時はルールへ。"""
    if tickers:
        return "company"
    fallback = classify_intent(query, tickers)
    output = await invoke_llm(
        _INTENT_SYSTEM_PROMPT, query, fallback=fallback, config=config
    )
    return "company" if "company" in output.lower() else "general"
