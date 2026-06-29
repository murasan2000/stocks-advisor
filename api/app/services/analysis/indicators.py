"""テクニカル指標の計算（純Python実装・外部ライブラリ不使用）。

入力の values は古い順（昇順）の終値リストを想定する。
データ不足で計算できない場合は None を返す。
"""

from __future__ import annotations

import statistics


def sma(values: list[float], window: int) -> float | None:
    """単純移動平均（直近 window 件）。"""
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def rsi(values: list[float], period: int = 14) -> float | None:
    """RSI（Wilder 方式）。"""
    if len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _ema_series(values: list[float], period: int) -> list[float]:
    alpha = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def macd(
    values: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[float, float, float] | None:
    """MACD・シグナル・ヒストグラムを返す。"""
    if len(values) < slow + signal:
        return None
    fast_ema = _ema_series(values, fast)
    slow_ema = _ema_series(values, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema, strict=True)]
    signal_line = _ema_series(macd_line[slow - 1 :], signal)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return macd_val, signal_val, macd_val - signal_val


def bollinger(
    values: list[float],
    window: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float] | None:
    """ボリンジャーバンド（上限・中央・下限）を返す。"""
    if len(values) < window:
        return None
    recent = values[-window:]
    middle = sum(recent) / window
    std = statistics.pstdev(recent)
    return middle + num_std * std, middle, middle - num_std * std


def detect_cross(values: list[float], short_w: int, long_w: int) -> str | None:
    """直近5営業日内のゴールデンクロス/デッドクロスを検出する。

    Returns:
        "golden" | "dead" | None
    """
    if len(values) < long_w + 5:
        return None
    for offset in range(5):
        end = len(values) - offset
        s_now = sum(values[end - short_w : end]) / short_w
        l_now = sum(values[end - long_w : end]) / long_w
        s_prev = sum(values[end - 1 - short_w : end - 1]) / short_w
        l_prev = sum(values[end - 1 - long_w : end - 1]) / long_w
        if s_prev <= l_prev and s_now > l_now:
            return "golden"
        if s_prev >= l_prev and s_now < l_now:
            return "dead"
    return None
