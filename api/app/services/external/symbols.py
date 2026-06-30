"""銘柄名・証券コードから Yahoo Finance シンボルへの解決。"""

from __future__ import annotations

import re

# 銘柄名（部分一致）→ シンボルのマッピング。モックデータに存在する銘柄を網羅する。
_NAME_TO_SYMBOL: dict[str, str] = {
    "トヨタ": "7203.T",
    "ソニー": "6758.T",
    "ソフトバンクグループ": "9984.T",
    "ソフトバンク": "9984.T",
    "キーエンス": "6861.T",
    "三菱UFJ": "8306.T",
    "三菱ＵＦＪ": "8306.T",
    "NTT": "9432.T",
    "日本電信電話": "9432.T",
    "日経平均": "^N225",
    "日経225": "^N225",
    # ^TOPX は Yahoo Finance 側で 2019 年以降ヒストリカルデータの配信が
    # 停止しているため、TOPIX 連動 ETF（1306.T）をプロキシとして使う。
    "TOPIX": "1306.T",
    "トピックス": "1306.T",
    "S&P500": "^GSPC",
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "ナスダック": "^IXIC",
    "ドル円": "USDJPY=X",
    "USD/JPY": "USDJPY=X",
    "為替": "USDJPY=X",
}

_JP_TICKER_RE = re.compile(r"^\d{4}$")
_SYMBOL_RE = re.compile(r"^[\^A-Z0-9.=-]+$")


def resolve_symbol(target: str) -> str:
    """銘柄名・証券コード・シンボルを Yahoo Finance シンボルに解決する。

    解決できない場合は入力をそのまま返す（クライアント側で
    決定論的なダミーデータにフォールバックする）。
    """
    target = target.strip()

    for name, symbol in _NAME_TO_SYMBOL.items():
        if name in target:
            return symbol

    if _JP_TICKER_RE.match(target):
        return f"{target}.T"

    if _SYMBOL_RE.match(target):
        return target

    return target


def to_sec_code(target: str) -> str | None:
    """銘柄名・シンボルから EDINET 用の4桁証券コードを返す。"""
    symbol = resolve_symbol(target)
    m = re.match(r"^(\d{4})\.T$", symbol)
    return m.group(1) if m else None


def sanitize_symbol(symbol: str) -> str:
    """シンボルをモックファイル名に使える形式に変換する（例: 7203.T → 7203_T）。"""
    return re.sub(r"[^A-Za-z0-9_-]", "_", symbol)


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
