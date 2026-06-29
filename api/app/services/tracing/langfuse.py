from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler

from app.utils.settings import settings

logger = logging.getLogger(__name__)

_langfuse_available: bool = False


def _check_langfuse() -> None:
    """起動時にLangfuse接続を確認し、利用可否をグローバルフラグに記録する。

    接続成功時は LANGFUSE_* 環境変数を設定する。
    Langfuse 4.x の CallbackHandler は環境変数から設定を読み込む仕様のため。
    """
    global _langfuse_available
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse: credentials not configured, tracing disabled")
        return
    try:
        import os

        from langfuse import Langfuse

        client = Langfuse(
            host=settings.langfuse_host,
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
        )
        if not client.auth_check():
            logger.warning("Langfuse: auth check failed, tracing disabled")
            return

        os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key

        _langfuse_available = True
        logger.info("Langfuse: tracing enabled (host=%s)", settings.langfuse_host)
    except Exception as exc:
        logger.warning("Langfuse: initialization failed (%s), tracing disabled", exc)


_check_langfuse()


def get_langfuse_callback() -> BaseCallbackHandler | None:
    """リクエスト単位のLangfuse CallbackHandlerを返す。利用不可の場合はNoneを返す。"""
    if not _langfuse_available:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception as exc:
        logger.warning("Langfuse: callback handler creation failed: %s", exc)
        return None
