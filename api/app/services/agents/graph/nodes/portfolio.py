from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from app.services.external.rakuten_csv import parse_rakuten_csv
from app.types.agents.multi_agent import MultiAgentState, PortfolioData
from app.utils.settings import settings

logger = logging.getLogger(__name__)

_CSV_FILENAME = "rakten_securities_jp_info.csv"


async def portfolio_node(state: MultiAgentState) -> dict[str, Any]:
    """楽天証券CSV（モック）からポートフォリオ状況を集計する。

    Phase 4.5 でユーザーアップロードに対応予定。現状は data/mock/ の
    固定CSVを参照し、存在しない場合はポートフォリオなしとして続行する。
    """
    csv_path = Path(settings.mock_data_dir) / _CSV_FILENAME
    try:
        holdings = parse_rakuten_csv(csv_path)
    except FileNotFoundError:
        logger.info("Portfolio CSV not found: %s", csv_path)
        return {
            "portfolio_data": None,
            "errors": [
                {
                    "agent": "portfolio",
                    "message": "ポートフォリオCSVが未連携のためスキップしました",
                }
            ],
        }
    except Exception as exc:
        logger.error("portfolio_node failed: %s", exc, exc_info=True)
        return {
            "portfolio_data": None,
            "errors": [{"agent": "portfolio", "message": str(exc)}],
        }

    total_value = sum(h["market_value"] for h in holdings)
    total_pnl = sum(h["unrealized_pnl"] for h in holdings)
    total_cost = sum(h["acquisition_value"] for h in holdings)
    data = PortfolioData(
        holdings=holdings,
        total_market_value=total_value,
        total_unrealized_pnl=total_pnl,
        total_unrealized_pnl_pct=(
            round(total_pnl / total_cost * 100, 2) if total_cost else 0.0
        ),
        as_of_date=date.today().isoformat(),
    )
    return {"portfolio_data": data}
