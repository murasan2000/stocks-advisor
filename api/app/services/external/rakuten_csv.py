"""楽天証券 保有株式CSV（Shift-JIS）のパーサー。

フォーマット（data/mock/rakten_securities_jp_info.csv 参照）:
- 冒頭にサマリー行（■現在の評価額合計 など）と口座区分行（■NISA成長投資枠 など）
- 「銘柄コード」で始まるヘッダー行の後に銘柄明細行が続く
- 末尾に口座合計行（銘柄コード列が空）がある
- 数値はダブルクォート + カンマ区切り（例: "8,888.50"）
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.types.external.rakuten_securities import RakutenHolding


class RakutenCsvFormatError(Exception):
    """CSVフォーマットが想定と異なる場合に送出される。"""


def _to_float(value: str) -> float:
    cleaned = value.strip().replace(",", "")
    if cleaned in ("", "-"):
        return 0.0
    return float(cleaned)


def parse_rakuten_csv(path: str | Path) -> list[RakutenHolding]:
    """楽天証券の保有株式CSVをパースして保有銘柄一覧を返す。

    Raises:
        RakutenCsvFormatError: ヘッダー行が見つからない・明細が空の場合。
        FileNotFoundError: ファイルが存在しない場合。
    """
    path = Path(path)
    # 楽天証券のエクスポートは Shift-JIS（cp932）
    with path.open(encoding="cp932") as f:
        rows = list(csv.reader(f))

    header_idx: int | None = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "銘柄コード":
            header_idx = i
            break
    if header_idx is None:
        raise RakutenCsvFormatError(
            "ヘッダー行（銘柄コード,銘柄名,...）が見つかりません"
        )

    header = [c.strip() for c in rows[header_idx]]
    col = {name: idx for idx, name in enumerate(header)}
    required = (
        "銘柄コード",
        "銘柄名",
        "保有数量［株］",
        "平均取得価額［円］",
        "取得総額［円］",
        "現在値［円］",
        "時価評価額［円］",
        "評価損益［円］",
    )
    missing = [name for name in required if name not in col]
    if missing:
        raise RakutenCsvFormatError(f"必須カラムがありません: {missing}")

    holdings: list[RakutenHolding] = []
    for row in rows[header_idx + 1 :]:
        if len(row) < len(required):
            continue
        ticker = row[col["銘柄コード"]].strip()
        if not ticker.isdigit():  # 口座合計行などをスキップ
            continue
        acquisition = _to_float(row[col["取得総額［円］"]])
        pnl = _to_float(row[col["評価損益［円］"]])
        holdings.append(
            RakutenHolding(
                ticker=ticker,
                company_name=row[col["銘柄名"]].strip(),
                quantity=int(_to_float(row[col["保有数量［株］"]])),
                average_cost=_to_float(row[col["平均取得価額［円］"]]),
                acquisition_value=acquisition,
                current_price=_to_float(row[col["現在値［円］"]]),
                market_value=_to_float(row[col["時価評価額［円］"]]),
                unrealized_pnl=pnl,
                unrealized_pnl_pct=(
                    round(pnl / acquisition * 100, 2) if acquisition else 0.0
                ),
            )
        )

    if not holdings:
        raise RakutenCsvFormatError("銘柄明細が1件もありません")
    return holdings
