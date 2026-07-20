"""楽天証券「現在保有商品一覧」CSVのパース。

単純な矩形CSVではなく、口座区分（特定口座・NISA成長投資枠 等）ごとの
セクション（ヘッダー行＋データ行＋「○○口座合計」集計行）が複数回繰り返される
構造。セクションの数・順序に依存せず、ファイル全体から「ヘッダー行（銘柄コード列
または米国株のティッカー列から始まる行）」を検出し、先頭列が空になるまでを
データ行として読む方式で対応する。

日本株セクション（`銘柄コード` 始まり・円建て）と米国株セクション（`ティッカー`
始まり・USドル建て）の両方に対応する。金額は換算せず、CSVに記載された値の
まま（日本株は円、米国株はドル）保持する。通貨の解釈は呼び出し側が
銘柄コードの形式（`utils/market.is_jp_code`）から判定する。

副作用（DB反映）は含まない。パースと集計はテスト容易な純粋関数として分離する。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

_CODE_COL = "銘柄コード"
_US_CODE_COL = "ティッカー"
_NAME_COL = "銘柄名"
_QUANTITY_COL = "保有数量［株］"
_AVG_COST_COL = "平均取得価額［円］"
_US_AVG_COST_COL = "平均取得価額［USドル］"

# 楽天証券のCSVは通常 Shift-JIS(CP932) だが、UTF-8 で保存され直している
# 可能性もあるため、決め打ちせず順に試す。"utf-8-sig" はBOMの有無に関わらず
# 有効なUTF-8をすべて受け付けるため、単体の "utf-8" は別途試す必要がない。
_ENCODINGS = ("utf-8-sig", "cp932")


@dataclass(frozen=True)
class _ColumnMap:
    """セクションのヘッダー形式ごとの列名マップ（JP/US で切り替える）。"""

    code_col: str
    name_col: str
    qty_col: str
    cost_col: str


_JP_FORMAT = _ColumnMap(_CODE_COL, _NAME_COL, _QUANTITY_COL, _AVG_COST_COL)
_US_FORMAT = _ColumnMap(_US_CODE_COL, _NAME_COL, _QUANTITY_COL, _US_AVG_COST_COL)
_FORMATS = (_JP_FORMAT, _US_FORMAT)


@dataclass(frozen=True)
class ParsedHolding:
    code: str
    name: str
    quantity: float
    avg_cost: float


def decode_csv_bytes(data: bytes) -> str:
    """文字コードを判定してデコードする（全滅時は置換文字でフォールバック）。"""
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_number(raw: str) -> float | None:
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _parse_row(line: str) -> list[str]:
    return next(csv.reader([line]), [])


def parse_rakuten_holdings_csv(text: str) -> list[ParsedHolding]:
    """楽天証券の保有商品一覧CSVから銘柄行を抽出する（セクション横断・重複統合前）。"""
    lines = text.splitlines()
    holdings: list[ParsedHolding] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        fmt = next((f for f in _FORMATS if line.startswith(f.code_col)), None)
        if fmt is None:
            i += 1
            continue

        header = _parse_row(line)
        index = {name: idx for idx, name in enumerate(header)}
        code_i = index.get(fmt.code_col)
        name_i = index.get(fmt.name_col)
        qty_i = index.get(fmt.qty_col)
        cost_i = index.get(fmt.cost_col)
        i += 1
        if code_i is None or name_i is None or qty_i is None or cost_i is None:
            continue  # 想定外のヘッダー形式はスキップ（このセクションは無視）

        while i < len(lines):
            row_line = lines[i]
            if not row_line.strip():
                break
            row = _parse_row(row_line)
            if len(row) <= code_i or not row[code_i].strip():
                break  # 「○○口座合計」集計行、またはセクション終端
            code = row[code_i].strip().upper()
            name = row[name_i].strip() if len(row) > name_i else code
            quantity = _parse_number(row[qty_i]) if len(row) > qty_i else None
            avg_cost = _parse_number(row[cost_i]) if len(row) > cost_i else None
            # 手動登録（HoldingRequest）と同じ gt=0 の制約に揃える
            # （数量0の行は「全株売却済み」等の過渡データとして扱い、取り込まない）。
            if (
                quantity is not None
                and avg_cost is not None
                and quantity > 0
                and avg_cost > 0
            ):
                holdings.append(ParsedHolding(code, name, quantity, avg_cost))
            i += 1
    return holdings


def merge_duplicate_codes(holdings: list[ParsedHolding]) -> list[ParsedHolding]:
    """同一銘柄コードが複数セクションに出現した場合、数量合算＋加重平均で統合する。"""
    merged: dict[str, ParsedHolding] = {}
    for h in holdings:
        existing = merged.get(h.code)
        if existing is None:
            merged[h.code] = h
            continue
        total_qty = existing.quantity + h.quantity
        weighted_cost = (
            existing.quantity * existing.avg_cost + h.quantity * h.avg_cost
        ) / total_qty
        merged[h.code] = ParsedHolding(h.code, h.name, total_qty, weighted_cost)
    return list(merged.values())
