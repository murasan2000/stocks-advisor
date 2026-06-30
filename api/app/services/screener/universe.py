"""銘柄ユニバース（スクリーニング対象の証券コード集合）の管理。

yfinance には「全上場銘柄一覧」を返す API が無いため、対象コードの集合は別途用意する。

- 同梱 JSON（data/tse_prime_tickers.json）: 主要銘柄のシード（フォールバック）。
- JPX 公開リスト（data_j.xls）: 全銘柄（約1,500）。live 更新時に取得し、
  ディスクにキャッシュする。次回以降はキャッシュを読む。

優先順位: ディスクキャッシュ > 同梱シード。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.external.symbols import to_yahoo_symbol
from app.utils.settings import settings

_SEED_FILE = Path(__file__).parent / "data" / "tse_prime_tickers.json"

_JPX_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/"
    "tvdivq0000001vg2-att/data_j.xls"
)

# JPX「市場・商品区分」→ アプリ内ラベル
_MARKET_MAP = {
    "プライム（内国株式）": "プライム",
    "スタンダード（内国株式）": "スタンダード",
    "グロース（内国株式）": "グロース",
    "プライム（外国株式）": "プライム",
    "スタンダード（外国株式）": "スタンダード",
    "グロース（外国株式）": "グロース",
}


@dataclass(frozen=True)
class Ticker:
    """ユニバースの 1 銘柄。"""

    code: str
    name: str
    market: str

    @property
    def symbol(self) -> str:
        return to_yahoo_symbol(self.code)


def _cache_path() -> Path:
    """ディスクキャッシュのパス（DB と同じディレクトリに置く）。"""
    return Path(settings.db_path).parent / "tse_universe_cache.json"


def _parse(payload: dict[str, object]) -> list[Ticker]:
    raw = payload.get("tickers", [])
    items = raw if isinstance(raw, list) else []
    return [
        Ticker(code=str(t["code"]), name=str(t["name"]), market=str(t["market"]))
        for t in items
    ]


@lru_cache(maxsize=1)
def load_universe() -> list[Ticker]:
    """ユニバースを読み込む（キャッシュ優先、無ければ同梱シード）。"""
    cache = _cache_path()
    path = cache if cache.exists() else _SEED_FILE
    with path.open(encoding="utf-8") as f:
        return _parse(json.load(f))


def universe_source() -> str:
    """ユニバースの出所（"jpx" / "seed"）を返す。"""
    return "jpx" if _cache_path().exists() else "seed"


def save_universe(tickers: list[Ticker], source: str = "jpx") -> None:
    """取得したユニバースをディスクキャッシュへ保存し、メモリキャッシュを更新する。"""
    cache = _cache_path()
    cache.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source,
        "tickers": [
            {"code": t.code, "name": t.name, "market": t.market} for t in tickers
        ],
    }
    cache.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    load_universe.cache_clear()


def fetch_jpx_universe(*, prime_only: bool = True) -> list[Ticker]:
    """JPX 公開の『東証上場銘柄一覧』(data_j.xls) を取得して全銘柄を返す。

    ネットワーク到達が必要（JPX 到達不可環境では例外）。
    """
    import pandas as pd

    df = pd.read_excel(_JPX_URL, dtype={"コード": str})
    df = df[df["市場・商品区分"].isin(_MARKET_MAP)]
    if prime_only:
        df = df[df["市場・商品区分"].str.startswith("プライム")]

    tickers = [
        Ticker(
            code=str(row["コード"]).strip(),
            name=str(row["銘柄名"]).strip(),
            market=_MARKET_MAP[str(row["市場・商品区分"])],
        )
        for _, row in df.iterrows()
    ]
    tickers.sort(key=lambda t: t.code)
    return tickers
