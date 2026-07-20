"""銘柄コードの市場（JP/US）判定。

日本株コードは4桁（先頭3桁が数字、末尾1桁は数字または英字。例: 7203, 167A）。
それ以外（英字のみのティッカー等）は米国株として扱う。判定結果は
ウォッチリスト・企業分析エージェントの委任先振り分けで共有する。

保有銘柄CSVインポート（services/portfolio/csv_import.py）はコード形式では
なく、CSVのセクションヘッダー（銘柄コード列/ティッカー列）で通貨を判定する
（ファイル自体に明示された、より確実な情報源のため）。
"""

from __future__ import annotations

import re

_JP_CODE_RE = re.compile(r"^\d{3}[0-9A-Z]$")


def is_jp_code(code: str) -> bool:
    """証券コードが日本株の形式（4桁、先頭3桁が数字）かどうかを判定する。"""
    return bool(_JP_CODE_RE.match(code.strip().upper()))
