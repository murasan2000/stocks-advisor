"""ウォッチ銘柄の価格・スコア変化アラート検出（detect_alerts, issue #81）のテスト。

副作用のない純粋関数のため、DB・ネットワーク非依存でテストできる。
"""

from __future__ import annotations

from app.services.watchlist.alerts import detect_alerts
from app.types.api import StockRow


def _row(code: str, price: float | None, score: int) -> StockRow:
    return StockRow(
        code=code,
        symbol=f"{code}.T",
        name=f"銘柄{code}",
        market="プライム",
        price=price,
        score=score,
    )


def test_price_change_over_threshold_is_detected() -> None:
    old_rows = [_row("7203", 1000.0, 50)]
    new_rows = [_row("7203", 1060.0, 50)]  # +6% > 5%
    alerts = detect_alerts(old_rows, new_rows)
    assert len(alerts) == 1
    assert alerts[0].kind == "price"
    assert alerts[0].code == "7203"
    assert alerts[0].old_value == 1000.0
    assert alerts[0].new_value == 1060.0
    assert alerts[0].change_pct is not None
    assert alerts[0].change_pct == 6.0


def test_price_change_under_threshold_is_not_detected() -> None:
    old_rows = [_row("7203", 1000.0, 50)]
    new_rows = [_row("7203", 1040.0, 50)]  # +4% <= 5%
    assert detect_alerts(old_rows, new_rows) == []


def test_price_drop_over_threshold_is_detected() -> None:
    """下落方向（負の変化率）も絶対値で判定する。"""
    old_rows = [_row("7203", 1000.0, 50)]
    new_rows = [_row("7203", 900.0, 50)]  # -10%
    alerts = detect_alerts(old_rows, new_rows)
    assert len(alerts) == 1
    assert alerts[0].kind == "price"
    assert alerts[0].change_pct == -10.0


def test_score_change_over_threshold_is_detected() -> None:
    old_rows = [_row("7203", 1000.0, 50)]
    new_rows = [_row("7203", 1000.0, 65)]  # +15 > 10
    alerts = detect_alerts(old_rows, new_rows)
    assert len(alerts) == 1
    assert alerts[0].kind == "score"
    assert alerts[0].old_value == 50.0
    assert alerts[0].new_value == 65.0
    assert alerts[0].change_pct is None


def test_score_change_under_threshold_is_not_detected() -> None:
    old_rows = [_row("7203", 1000.0, 50)]
    new_rows = [_row("7203", 1000.0, 58)]  # +8 <= 10
    assert detect_alerts(old_rows, new_rows) == []


def test_both_price_and_score_change_produce_two_alerts() -> None:
    old_rows = [_row("7203", 1000.0, 50)]
    new_rows = [_row("7203", 1200.0, 70)]  # +20% と +20 の両方
    alerts = detect_alerts(old_rows, new_rows)
    kinds = {a.kind for a in alerts}
    assert kinds == {"price", "score"}
    assert len(alerts) == 2


def test_code_not_in_old_snapshot_is_skipped() -> None:
    """新規ウォッチ等、旧スナップショットに存在しない銘柄は比較不能としてスキップ。"""
    old_rows: list[StockRow] = []
    new_rows = [_row("7203", 1000.0, 50)]
    assert detect_alerts(old_rows, new_rows) == []


def test_none_price_is_skipped() -> None:
    old_rows = [_row("7203", None, 50)]
    new_rows = [_row("7203", 1000.0, 50)]
    assert detect_alerts(old_rows, new_rows) == []

    old_rows2 = [_row("7203", 1000.0, 50)]
    new_rows2 = [_row("7203", None, 50)]
    assert detect_alerts(old_rows2, new_rows2) == []


def test_multiple_codes_are_evaluated_independently() -> None:
    old_rows = [_row("7203", 1000.0, 50), _row("6758", 500.0, 30)]
    new_rows = [_row("7203", 1000.0, 50), _row("6758", 600.0, 30)]  # 6758 のみ +20%
    alerts = detect_alerts(old_rows, new_rows)
    assert len(alerts) == 1
    assert alerts[0].code == "6758"
