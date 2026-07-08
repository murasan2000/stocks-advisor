"""リトライの共通ユーティリティ（エラーハンドリング方針の集約先）。

方針:
- LLM 呼び出し・重要な外部 I/O は指数バックオフでリトライする。
- リトライすべきでない失敗（バリデーション等）は should_retry で除外できる。
- 「失敗＝機能縮退」で続行する箇所（Web検索・EDINET 等）はリトライせず、
  呼び出し側で空結果にフォールバックする（過剰リトライでの遅延を避ける）。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


def is_rate_limit_error(exc: BaseException) -> bool:
    """レートリミット（429等）を示す例外か判定する（yfinance 等の should_retry 用）。"""
    msg = str(exc).lower()
    return (
        "too many requests" in msg
        or "rate limit" in msg
        or "rate-limit" in msg
        or "429" in msg
    )


async def ainvoke_with_retry[T](
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """非同期関数を指数バックオフでリトライする。"""
    if max_retries < 1:
        raise ValueError(f"max_retries must be >= 1, got {max_retries}")
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


def invoke_with_retry_sync[T](
    fn: Callable[[], T],
    *,
    should_retry: Callable[[BaseException], bool],
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    what: str = "call",
) -> T:
    """同期関数を条件付き指数バックオフでリトライする。

    should_retry が False を返す例外（回復不能な失敗）は即座に送出する。
    yfinance のレートリミット（429）対策など、to_thread 内の同期処理で使う。
    """
    if max_retries < 1:
        raise ValueError(f"max_retries must be >= 1, got {max_retries}")
    delay = base_delay
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not should_retry(exc):
                raise
            if attempt < max_retries - 1:
                logger.info(
                    "%s rate limited/retryable (attempt %d/%d), retry in %.0fs",
                    what,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, max_delay)
    assert last_exc is not None
    raise last_exc
