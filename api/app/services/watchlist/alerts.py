"""ウォッチ銘柄の価格・スコア変化アラート検出（issue #81・候補A: アプリ内通知）。

サーバ側（スクリーナーのスナップショット更新ジョブ完了時）でウォッチ銘柄の
「更新前 → 更新後」を比較し、閾値超えを検出する。副作用（DB・ネットワーク）を
持たない純粋関数として切り出し、run_refresh_job() から呼び出しやすく・かつ
ユニットテストしやすくする（backend-workflow 方針）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.types.api import StockRow

# 価格変化率のアラート閾値（%）。this を超えたら（絶対値で）アラート対象。
PRICE_CHANGE_THRESHOLD_PCT = 5.0
# スコア変化量のアラート閾値。これを超えたら（絶対値で）アラート対象。
SCORE_CHANGE_THRESHOLD = 10.0


@dataclass
class DetectedAlert:
    """検出されたアラート1件（永続化前の中間表現）。

    alert_id・created_at はDB保存時に AlertsRepository 側で付与するため、
    ここでは検出内容のみを持つ。
    """

    code: str
    kind: Literal["price", "score"]
    old_value: float
    new_value: float
    change_pct: float | None = None  # 価格アラートのみ設定


def detect_alerts(
    old_rows: list[StockRow], new_rows: list[StockRow]
) -> list[DetectedAlert]:
    """更新前後のスナップショットを比較し、閾値を超えたアラートを返す。

    - 価格変化率 abs((new.price - old.price) / old.price) * 100 が
      PRICE_CHANGE_THRESHOLD_PCT を超える
    - スコア変化 abs(new.score - old.score) が SCORE_CHANGE_THRESHOLD を超える
    どちらか一方でも該当すれば対象（両方該当する場合は price/score それぞれ
    独立したアラートとして最大2件返す）。

    旧スナップショットに存在しない銘柄（新規ウォッチ等）や price が None の
    場合は比較不能としてスキップする。
    """
    old_by_code = {r.code: r for r in old_rows}
    alerts: list[DetectedAlert] = []
    for new in new_rows:
        old = old_by_code.get(new.code)
        if old is None:
            continue

        if old.price is not None and new.price is not None and old.price != 0:
            change_pct = (new.price - old.price) / old.price * 100
            if abs(change_pct) > PRICE_CHANGE_THRESHOLD_PCT:
                alerts.append(
                    DetectedAlert(
                        code=new.code,
                        kind="price",
                        old_value=old.price,
                        new_value=new.price,
                        change_pct=change_pct,
                    )
                )

        score_diff = new.score - old.score
        if abs(score_diff) > SCORE_CHANGE_THRESHOLD:
            alerts.append(
                DetectedAlert(
                    code=new.code,
                    kind="score",
                    old_value=float(old.score),
                    new_value=float(new.score),
                )
            )
    return alerts
