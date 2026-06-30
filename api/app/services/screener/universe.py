"""銘柄ユニバース（スクリーニング対象の証券コード集合）の読み込み。

yfinance には「全上場銘柄一覧」を返す API が無いため、対象コードの集合は
リポジトリ同梱の JSON（data/tse_prime_tickers.json）から読み込む。
同梱データは主要銘柄のシード。全銘柄（約1,595）へは scripts/update_tickers.py で
JPX 公開リストから再生成する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.external.symbols import to_yahoo_symbol

_DATA_FILE = Path(__file__).parent / "data" / "tse_prime_tickers.json"


@dataclass(frozen=True)
class Ticker:
    """ユニバースの 1 銘柄。"""

    code: str
    name: str
    market: str

    @property
    def symbol(self) -> str:
        return to_yahoo_symbol(self.code)


@lru_cache(maxsize=1)
def load_universe() -> list[Ticker]:
    """同梱 JSON からユニバースを読み込む（プロセス内でキャッシュ）。"""
    with _DATA_FILE.open(encoding="utf-8") as f:
        payload = json.load(f)
    tickers = [
        Ticker(code=str(t["code"]), name=str(t["name"]), market=str(t["market"]))
        for t in payload.get("tickers", [])
    ]
    return tickers


def universe_source() -> str:
    """ユニバースの出所（"seed" / "jpx" など）を返す。"""
    with _DATA_FILE.open(encoding="utf-8") as f:
        return str(json.load(f).get("source", "unknown"))
