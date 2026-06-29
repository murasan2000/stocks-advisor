"""楽天証券 保有株式CSV（Shift-JIS）の型定義。

フォーマットは data/mock/rakten_securities_jp_info.csv を参照。
冒頭にサマリー行（評価額合計など）と口座区分行があり、その後に
ヘッダー行 + 銘柄明細行が続く。
"""

from __future__ import annotations

from typing import TypedDict


class RakutenHolding(TypedDict):
    """保有銘柄1件。"""

    ticker: str  # 証券コード（例: "7203"）
    company_name: str  # 銘柄名
    quantity: int  # 保有株数
    average_cost: float  # 平均取得価額（円）
    acquisition_value: float  # 取得総額（円）
    current_price: float  # 現在値（円）
    market_value: float  # 時価評価額（円）
    unrealized_pnl: float  # 評価損益（円）
    unrealized_pnl_pct: float  # 評価損益率（%）
