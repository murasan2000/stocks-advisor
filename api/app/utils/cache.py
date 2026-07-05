"""シンプルな TTL 付き非同期キャッシュ（企業情報などの短期キャッシュ用）。

外部 API（yfinance 企業概要・EDINET 開示など）の同一引数の再取得を抑える。
プロセス内メモリのみ・小規模用途向け。テストからは cache_clear() でリセットする。
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Protocol, TypeVar, cast

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class AsyncCached(Protocol[T_co]):
    """async_ttl_cache が返すラッパの型（cache_clear 付き）。"""

    def __call__(self, *args: Any, **kwargs: Any) -> Awaitable[T_co]: ...

    def cache_clear(self) -> None: ...


def async_ttl_cache(
    ttl_seconds: float, maxsize: int = 256
) -> Callable[[Callable[..., Awaitable[T]]], AsyncCached[T]]:
    """非同期関数の戻り値を TTL 付きでキャッシュするデコレータ。

    キーは位置・キーワード引数（hashable 前提）。maxsize 超過時は最も古い
    エントリから捨てる。None などの falsy な結果もキャッシュされる点に注意
    （「取得失敗を空で返す」関数へは適用しないか、TTL を短くすること）。
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> AsyncCached[T]:
        store: dict[tuple[Any, ...], tuple[float, T]] = {}

        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            hit = store.get(key)
            if hit is not None and now - hit[0] < ttl_seconds:
                return hit[1]
            value = await fn(*args, **kwargs)
            if len(store) >= maxsize:
                oldest = min(store, key=lambda k: store[k][0])
                del store[oldest]
            store[key] = (now, value)
            return value

        def cache_clear() -> None:
            store.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return cast(AsyncCached[T], wrapper)

    return decorator
