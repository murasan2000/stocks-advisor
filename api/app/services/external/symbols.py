"""証券コード → Yahoo Finance シンボル変換。"""

from __future__ import annotations


def to_yahoo_symbol(code: str) -> str:
    """日本株の証券コードを Yahoo Finance シンボルに変換する。

    日本株コードは基本4桁数字だが、一部に英字を含むものがある（例: 167A）。
    Yahoo Finance では ``.T`` サフィックスを付ける（例: 7203 → 7203.T）。
    既に ``.T`` 付き・指数（^始まり）・為替（=X）の場合はそのまま返す。
    """
    code = code.strip().upper()
    if not code or code.startswith("^") or code.endswith("=X") or "." in code:
        return code
    return f"{code}.T"
