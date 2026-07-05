"""共通ユーティリティ（TTLキャッシュ・同期リトライ）のテスト。"""

from __future__ import annotations

import pytest

from app.utils.cache import async_ttl_cache
from app.utils.retry import invoke_with_retry_sync


async def test_ttl_cache_hits_within_ttl() -> None:
    calls = 0

    @async_ttl_cache(ttl_seconds=60)
    async def fetch(code: str) -> str:
        nonlocal calls
        calls += 1
        return f"data-{code}"

    assert await fetch("7203") == "data-7203"
    assert await fetch("7203") == "data-7203"  # キャッシュヒット
    assert calls == 1
    assert await fetch("6758") == "data-6758"  # 別キーはミス
    assert calls == 2

    fetch.cache_clear()
    assert await fetch("7203") == "data-7203"
    assert calls == 3


async def test_ttl_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.utils.cache as cache_mod

    now = 1000.0
    monkeypatch.setattr(cache_mod.time, "monotonic", lambda: now)
    calls = 0

    @async_ttl_cache(ttl_seconds=10)
    async def fetch() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert await fetch() == 1
    now += 5
    assert await fetch() == 1  # TTL内
    now += 6
    assert await fetch() == 2  # TTL切れで再取得


def test_retry_sync_retries_only_matching_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.utils.retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda _: None)
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("429 Too Many Requests")
        return "ok"

    result = invoke_with_retry_sync(
        flaky, should_retry=lambda e: "429" in str(e), max_retries=5
    )
    assert result == "ok"
    assert attempts == 3


def test_retry_sync_raises_non_retryable_immediately() -> None:
    attempts = 0

    def fail() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        invoke_with_retry_sync(
            fail, should_retry=lambda e: "429" in str(e), max_retries=5
        )
    assert attempts == 1
