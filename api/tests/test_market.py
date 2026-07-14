"""is_jp_code の市場判定テスト。"""

from __future__ import annotations

from app.utils.market import is_jp_code


def test_jp_four_digit_code() -> None:
    assert is_jp_code("7203") is True


def test_jp_alphanumeric_code() -> None:
    # 末尾に英字1文字を含むコード（例: 167A）もJP扱い
    assert is_jp_code("167a") is True


def test_us_ticker_is_not_jp() -> None:
    assert is_jp_code("AAPL") is False


def test_index_and_fx_are_not_jp() -> None:
    assert is_jp_code("^N225") is False
    assert is_jp_code("USDJPY=X") is False


def test_empty_string_is_not_jp() -> None:
    assert is_jp_code("") is False
