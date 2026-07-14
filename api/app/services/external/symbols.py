"""証券コード → Yahoo Finance シンボル変換。"""

from __future__ import annotations

from app.utils.market import is_jp_code


def to_yahoo_symbol(code: str) -> str:
    """証券コードを Yahoo Finance シンボルに変換する。

    日本株コード（4桁数字＋末尾英字1文字まで、例: 7203, 167A）は Yahoo Finance の
    ``.T`` サフィックスを付ける（例: 7203 → 7203.T）。米国株ティッカー（例: AAPL）は
    yfinance がそのまま受け付けるためサフィックスを付けずに返す。
    既に ``.T`` 等が付いている・指数（^始まり）・為替（=X）の場合はそのまま返す。
    """
    code = code.strip().upper()
    if not code or code.startswith("^") or code.endswith("=X") or "." in code:
        return code
    if is_jp_code(code):
        return f"{code}.T"
    return code
