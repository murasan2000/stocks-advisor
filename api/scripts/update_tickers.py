"""東証上場銘柄ユニバース（tse_prime_tickers.json）を JPX 公開リストから更新する。

JPX が公開する「東証上場銘柄一覧」(data_j.xls) を取得し、市場区分ごとに
コード・銘柄名を抽出して、スクリーナーが読み込む JSON を再生成する。

使い方:
    # .xls 読み込みに xlrd が必要
    uv run --with xlrd python scripts/update_tickers.py            # プライムのみ
    uv run --with xlrd python scripts/update_tickers.py --all      # 全市場

ネットワークから JPX へ到達できる環境で実行すること（egress 制限環境では不可）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

_JPX_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/"
    "tvdivq0000001vg2-att/data_j.xls"
)
_OUT = Path(__file__).resolve().parents[1] / (
    "app/services/screener/data/tse_prime_tickers.json"
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all",
        action="store_true",
        help="プライム以外（スタンダード・グロース）も含める",
    )
    args = parser.parse_args()

    df = pd.read_excel(_JPX_URL, dtype={"コード": str})
    df = df[df["市場・商品区分"].isin(_MARKET_MAP)]
    if not args.all:
        df = df[df["市場・商品区分"].str.startswith("プライム")]

    tickers = [
        {
            "code": str(row["コード"]).strip(),
            "name": str(row["銘柄名"]).strip(),
            "market": _MARKET_MAP[str(row["市場・商品区分"])],
        }
        for _, row in df.iterrows()
    ]
    tickers.sort(key=lambda t: t["code"])

    payload = {
        "source": "jpx",
        "note": "JPX『東証上場銘柄一覧』(data_j.xls) から生成。",
        "market_label": "プライム" if not args.all else "全市場",
        "tickers": tickers,
    }
    _OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(tickers)} tickers -> {_OUT}")


if __name__ == "__main__":
    main()
