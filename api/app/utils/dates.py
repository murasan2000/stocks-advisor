"""日付関連のユーティリティ。

本アプリは日本株市場を主対象とするため、「今日」の判定は常に JST
（Asia/Tokyo）基準に統一する。サーバのホストタイムゾーンに依存すると、
UTC等でホストされた場合にクライアント（ブラウザ、通常JST想定）の「今日」と
サーバの「今日」がずれ、マーケットレポートの日付キーが食い違う原因になる。
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

_JST = ZoneInfo("Asia/Tokyo")


def today_jst() -> date:
    """JST基準の今日の日付を返す。"""
    return datetime.now(_JST).date()
