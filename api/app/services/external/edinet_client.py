"""EDINET API v2 クライアント。

EXTERNAL_API_MODE=mock のとき data/mock/edinet/ の JSON を返す。
モックに存在しない証券コードは EdinetDataNotFoundError を送出する
（実APIでも開示書類が存在しないケースがあるため、呼び出し側で処理する）。

live モードは EDINET API キー取得後に実装予定（Phase 5）。
実APIは書類本体を ZIP(XBRL) で返すため、live 実装時は XBRL をパースして
FinancialSummary へ正規化する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.types.external.edinet import (
    DocumentListMetadata,
    DocumentListResponse,
    DocumentResult,
    FinancialSummary,
    ResultSet,
)
from app.utils.settings import settings


class EdinetDataNotFoundError(Exception):
    """指定した証券コードの開示情報が見つからない場合に送出される。"""


class EdinetClient:
    def __init__(
        self,
        mode: str | None = None,
        mock_dir: str | Path | None = None,
    ) -> None:
        self._mode = mode or settings.external_api_mode
        self._mock_dir = Path(mock_dir or settings.mock_data_dir) / "edinet"
        self._cache: dict[str, Any] = {}

    def _ensure_mock(self) -> None:
        if self._mode != "mock":
            raise NotImplementedError(
                "EDINET の live モードは未実装です（Phase 5 で対応予定）。"
                " EXTERNAL_API_MODE=mock を使用してください。"
            )

    def _load(self, filename: str) -> Any:
        if filename not in self._cache:
            path = self._mock_dir / filename
            with path.open(encoding="utf-8") as f:
                self._cache[filename] = json.load(f)
        return self._cache[filename]

    async def get_documents(self, sec_code: str) -> DocumentListResponse:
        """証券コード（4桁）に紐づく開示書類一覧を返す。"""
        self._ensure_mock()
        documents: dict[str, Any] = self._load("documents.json")
        results = [
            DocumentResult.model_validate(doc) for doc in documents.get(sec_code, [])
        ]
        return DocumentListResponse(
            metadata=DocumentListMetadata(resultset=ResultSet(count=len(results))),
            results=results,
        )

    async def get_financial_summaries(self, sec_code: str) -> list[FinancialSummary]:
        """証券コード（4桁）の財務サマリー一覧（新しい順）を返す。

        Raises:
            EdinetDataNotFoundError: 開示情報が存在しない場合。
        """
        self._ensure_mock()
        financials: dict[str, Any] = self._load("financials.json")
        if sec_code not in financials:
            raise EdinetDataNotFoundError(
                f"証券コード {sec_code} の開示情報が見つかりませんでした"
            )
        return [FinancialSummary.model_validate(f) for f in financials[sec_code]]
