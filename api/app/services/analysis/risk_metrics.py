"""リスク指標の計算（純Python実装・外部ライブラリ不使用）。

入力の closes は古い順（昇順）の終値リストを想定する。
"""

from __future__ import annotations

import math
import statistics

_TRADING_DAYS = 252


def daily_returns(closes: list[float]) -> list[float]:
    """日次リターン系列を返す。"""
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1] != 0
    ]


def annual_volatility(closes: list[float]) -> float:
    """年率ボラティリティ（%）。"""
    returns = daily_returns(closes)
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(_TRADING_DAYS) * 100


def max_drawdown(closes: list[float]) -> float:
    """最大ドローダウン（%、負値）。"""
    if not closes:
        return 0.0
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        worst = min(worst, (price - peak) / peak)
    return worst * 100


def sharpe_ratio(closes: list[float]) -> float:
    """シャープレシオ（無リスク金利は0と仮定）。"""
    returns = daily_returns(closes)
    if len(returns) < 2:
        return 0.0
    std = statistics.stdev(returns)
    if std == 0:
        return 0.0
    return statistics.mean(returns) / std * math.sqrt(_TRADING_DAYS)


def beta(closes: list[float], benchmark_closes: list[float]) -> float | None:
    """β値（ベンチマークに対する感応度）。データ長が一致しない場合は末尾を揃える。"""
    n = min(len(closes), len(benchmark_closes))
    if n < 30:
        return None
    r_stock = daily_returns(closes[-n:])
    r_bench = daily_returns(benchmark_closes[-n:])
    if len(r_stock) != len(r_bench) or len(r_bench) < 2:
        return None
    var_bench = statistics.variance(r_bench)
    if var_bench == 0:
        return None
    cov = statistics.covariance(r_stock, r_bench)
    return cov / var_bench


def correlation(closes_a: list[float], closes_b: list[float]) -> float | None:
    """2銘柄の日次リターンの相関係数。"""
    n = min(len(closes_a), len(closes_b))
    if n < 30:
        return None
    r_a = daily_returns(closes_a[-n:])
    r_b = daily_returns(closes_b[-n:])
    if len(r_a) != len(r_b) or len(r_a) < 2:
        return None
    try:
        return statistics.correlation(r_a, r_b)
    except statistics.StatisticsError:
        return None
