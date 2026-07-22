"""為替クオート取得（マーケット画面・為替パネル向け）。

screener/us_quote.py と同様のパターン: mock時は決定論的合成、live時は
yfinance のファンダメンタルズ(.info)から直接取得し、失敗時はNoneへ縮退する
（「失敗＝機能縮退」方針。fetch_fundamentals(retry=False) 自体もリトライしない）。
FX_SYMBOLS のキーは Yahoo Finance 形式（例: "USDJPY=X"）。to_yahoo_symbol()の
`=X` サフィックス素通し分岐により、既存の記号変換ロジックへそのまま渡せる。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from app.services.external.symbols import to_yahoo_symbol
from app.services.screener.fetcher import fetch_fundamentals
from app.types.api import FxQuote
from app.utils.cache import async_ttl_cache
from app.utils.settings import settings

logger = logging.getLogger(__name__)

# symbol（Yahoo Finance形式、=Xサフィックス） -> 表示名。MVPは2種（反応を見て拡張）。
FX_SYMBOLS: dict[str, str] = {
    "USDJPY=X": "米ドル/円",
    "EURJPY=X": "ユーロ/円",
}


def _synth_fx_quote(symbol: str, label: str) -> FxQuote:
    """決定論的な合成クオート（mock用。screener.fetcher.synth_row と同じ考え方）。"""
    seed = int.from_bytes(hashlib.sha256(symbol.encode()).digest()[:4], "big")
    price = round(50 + seed % 200 + (seed % 100) / 100, 2)
    change_pct = round(((seed >> 8) % 400 - 200) / 100, 2)
    return FxQuote(symbol=symbol, label=label, price=price, change_pct=change_pct)


@async_ttl_cache(ttl_seconds=300)
async def _fetch_fx_info_live(symbol: str) -> dict[str, Any]:
    """為替のファンダメンタルズ(.info)を取得する（5分キャッシュ）。

    取得失敗時（ネットワーク不可・レートリミット等）は例外を送出する
    （async_ttl_cacheは例外をキャッシュしないため、失敗がキャッシュに残らない）。
    """
    yahoo_symbol = to_yahoo_symbol(symbol)
    info = await asyncio.to_thread(fetch_fundamentals, yahoo_symbol, retry=False)
    if not info:
        raise ValueError(f"no fx data for {symbol}")
    return info


async def fetch_fx_quote(symbol: str, label: str) -> FxQuote | None:
    """1通貨ペアのクオートを取得する（mockは決定論的合成、liveは失敗時Noneへ縮退）。"""
    if settings.external_api_mode != "live":
        return _synth_fx_quote(symbol, label)
    try:
        info = await _fetch_fx_info_live(symbol)
    except Exception as exc:  # noqa: BLE001 - ベストエフォート（機能縮退）
        logger.info("fx quote unavailable for %s: %s", symbol, exc)
        return None
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    if price is None:  # 価格が無ければ行を残す意味が無い（build_live_rowと同方針）
        logger.info("fx quote unavailable for %s: no price field", symbol)
        return None
    change_pct = info.get("regularMarketChangePercent")
    return FxQuote(
        symbol=symbol,
        label=label,
        price=round(float(price), 4),
        change_pct=round(float(change_pct), 2) if change_pct is not None else None,
    )


async def fetch_fx_quotes() -> list[FxQuote]:
    """登録済み通貨ペアのクオートを並行取得する（取得失敗は結果から除外）。"""
    rows = await asyncio.gather(
        *(fetch_fx_quote(symbol, label) for symbol, label in FX_SYMBOLS.items())
    )
    return [r for r in rows if r is not None]
