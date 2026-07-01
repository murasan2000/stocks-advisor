"""スクリーニング指標の計算（純粋関数）。

RSI・下がりすぎ反発の各指標・総合スコアを算出する。テスト容易性のため、
外部 I/O を持たない純粋関数として切り出す。
"""

from __future__ import annotations


def rsi(closes: list[float], period: int = 14) -> float | None:
    """終値系列から RSI（Wilder の平滑化）を算出する。"""
    if len(closes) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def drop_from_high_pct(price: float, high: float) -> float | None:
    """高値からの下落率（%, 正値＝下落）。"""
    if high <= 0:
        return None
    return round((high - price) / high * 100, 1)


def rebound_from_low_pct(price: float, low: float) -> float | None:
    """安値からの反発率（%, 正値＝反発）。"""
    if low <= 0:
        return None
    return round((price - low) / low * 100, 1)


def is_oversold_rebound(
    drop_pct: float | None,
    rebound_pct: float | None,
    *,
    min_drop: float,
    min_rebound: float,
) -> bool:
    """「下がりすぎ反発」条件を満たすか。

    5年高値から min_drop% 以上下落し、かつ1年安値から min_rebound% 以上
    反発している銘柄（＝落ちたナイフが底を打って反発し始めた兆し）。
    """
    if drop_pct is None or rebound_pct is None:
        return False
    return drop_pct >= min_drop and rebound_pct >= min_rebound


def _scale(value: float, lo: float, hi: float) -> float:
    """value を [lo, hi] で 0〜1 にクランプ正規化する。"""
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def compute_score(
    *,
    per: float | None,
    pbr: float | None,
    dividend_yield: float | None,
    roe: float | None,
    rsi_value: float | None,
    rebound_pct: float | None,
) -> int:
    """総合スコア（0〜100）を算出する。

    割安（低PER/低PBR）・配当・収益性（ROE）を主軸に、反発の兆し（rebound）を
    加点、過熱（高RSI）を減点する透明な加重平均。指標欠損時はその要素を中立扱い。
    """
    parts: list[tuple[float, float]] = []  # (score0_1, weight)

    if per is not None and per > 0:
        # PER 5→1.0, 25→0.0（低いほど割安）
        parts.append((1.0 - _scale(per, 5, 25), 0.25))
    if pbr is not None and pbr > 0:
        # PBR 0.5→1.0, 3.0→0.0
        parts.append((1.0 - _scale(pbr, 0.5, 3.0), 0.20))
    if dividend_yield is not None:
        # 配当 0%→0.0, 5%→1.0
        parts.append((_scale(dividend_yield, 0, 5), 0.20))
    if roe is not None:
        # ROE 0%→0.0, 20%→1.0
        parts.append((_scale(roe, 0, 20), 0.20))
    if rebound_pct is not None:
        # 反発 0%→0.0, 30%→1.0（底打ち反発の兆し）
        parts.append((_scale(rebound_pct, 0, 30), 0.10))
    if rsi_value is not None:
        # RSI 50→1.0, 80→0.0（過熱を減点、売られすぎ〜中立を加点）
        parts.append((1.0 - _scale(rsi_value, 50, 80), 0.05))

    if not parts:
        return 0
    total_weight = sum(w for _, w in parts)
    score = sum(s * w for s, w in parts) / total_weight
    return round(score * 100)
