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


def test_us_ticker_passthrough() -> None:
    # 米国株ティッカーはサフィックスを付けずそのまま返す（yfinanceがそのまま受け付ける）
    assert to_yahoo_symbol("AAPL") == "AAPL"
    assert to_yahoo_symbol("aapl") == "AAPL"
    assert to_yahoo_symbol("BRK.B") == "BRK.B"  # 既に"."を含むため素通し
