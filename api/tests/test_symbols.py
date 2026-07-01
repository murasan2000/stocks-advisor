"""to_yahoo_symbol の変換テスト。"""

from __future__ import annotations

from app.services.external.symbols import to_yahoo_symbol


def test_four_digit_code() -> None:
    assert to_yahoo_symbol("7203") == "7203.T"


def test_alphanumeric_code() -> None:
    # 英字を含むコード（例: 167A）にも対応する
    assert to_yahoo_symbol("167a") == "167A.T"


def test_already_suffixed_or_special() -> None:
    assert to_yahoo_symbol("7203.T") == "7203.T"
    assert to_yahoo_symbol("^N225") == "^N225"
    assert to_yahoo_symbol("USDJPY=X") == "USDJPY=X"
    assert to_yahoo_symbol("") == ""
