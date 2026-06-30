"""東証上場銘柄ユニバースの同梱シード(tse_prime_tickers.json)を JPX から再生成する。

通常は live 更新時にサーバが自動で JPX から取得・キャッシュするため必須ではないが、
リポジトリに全銘柄リストを同梱しておきたい場合に使う。

使い方（.xls 読み込みに xlrd が必要。本体依存に含まれる）:
    uv run python scripts/update_tickers.py            # プライムのみ
    uv run python scripts/update_tickers.py --all      # 全市場

JPX へ到達できる環境で実行すること。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.screener.universe import fetch_jpx_universe

_OUT = Path(__file__).resolve().parents[1] / (
    "app/services/screener/data/tse_prime_tickers.json"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="プライム以外も含める")
    args = parser.parse_args()

    tickers = fetch_jpx_universe(prime_only=not args.all)
    payload = {
        "source": "jpx",
        "note": "JPX『東証上場銘柄一覧』(data_j.xls) から生成。",
        "market_label": "全市場" if args.all else "プライム",
        "tickers": [
            {"code": t.code, "name": t.name, "market": t.market} for t in tickers
        ],
    }
    _OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(tickers)} tickers -> {_OUT}")


if __name__ == "__main__":
    main()
