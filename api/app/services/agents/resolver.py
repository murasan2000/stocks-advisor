"""クエリから分析対象銘柄（証券コード）を解決する。

証券コードの直接指定（7203 / 167A）に加えて、銘柄ユニバースの企業名との
マッチングで「トヨタ自動車を分析して」のような自然文からもコードを引く。

マッチは誤検知を抑えるため段階的に行う:
  1. 正式名称がクエリに完全に含まれる（例: "トヨタ自動車" → 7203）
  2. 名称の先頭4文字が含まれる（例: "ソフトバンクグループ" → "ソフトバンクG"表記等）
  3. 名称の先頭3文字が含まれる（例: "トヨタ" → トヨタ自動車）
上の段階でヒットがあればそこで打ち切る。TODO(Phase 6/7): LLM による名称正規化。
"""

from __future__ import annotations

from app.services.agents.runtime import extract_tickers
from app.services.screener.universe import Ticker, load_universe

_MAX_TICKERS = 5  # 1 リクエストで分析する銘柄数の上限（暴走防止）


def _match_by_name(query: str, universe: list[Ticker]) -> list[str]:
    """企業名マッチ（段階的プレフィックス）でコードを返す。"""
    full: list[str] = []
    prefix4: list[str] = []
    prefix3: list[str] = []
    for t in universe:
        name = t.name
        if len(name) >= 2 and name in query:
            full.append(t.code)
        elif len(name) > 4 and name[:4] in query:
            prefix4.append(t.code)
        elif len(name) > 3 and name[:3] in query:
            prefix3.append(t.code)
    return full or prefix4 or prefix3


def resolve_tickers(query: str) -> list[str]:
    """クエリから対象銘柄コードを解決する（コード指定 + 企業名マッチ）。"""
    codes = extract_tickers(query)
    names = _match_by_name(query, load_universe())
    merged: dict[str, None] = {}
    for code in [*codes, *names]:
        merged.setdefault(code, None)
    return list(merged)[:_MAX_TICKERS]
