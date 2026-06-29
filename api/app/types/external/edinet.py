"""EDINET API v2 のレスポンス型定義。

実API（https://api.edinet-fsa.go.jp/api/v2/）のレスポンス形状に基づく。

- DocumentListResponse: GET /api/v2/documents.json のレスポンス
- DocumentResult:       書類一覧の results[] 要素（主要フィールドのみ）
- FinancialSummary:     書類（XBRL）から抽出した財務サマリーの正規化型。
                        実APIは ZIP(XBRL) を返すため、live モード実装時に
                        XBRL パース後この型へ変換する。金額の単位は百万円。

docTypeCode（主要なもの）:
  120: 有価証券報告書 / 130: 訂正有価証券報告書
  160: 半期報告書     / 180: 臨時報告書
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResultSet(BaseModel):
    count: int


class DocumentListMetadata(BaseModel):
    title: str = ""
    status: str = "200"
    message: str = "OK"
    resultset: ResultSet


class DocumentResult(BaseModel):
    """書類一覧の results[] 要素。"""

    model_config = ConfigDict(populate_by_name=True)

    doc_id: str = Field(alias="docID")
    edinet_code: str = Field(alias="edinetCode")
    sec_code: str | None = Field(alias="secCode", default=None)  # 例: "72030"
    filer_name: str = Field(alias="filerName")
    doc_type_code: str = Field(alias="docTypeCode")
    doc_description: str = Field(alias="docDescription")
    period_start: str | None = Field(alias="periodStart", default=None)
    period_end: str | None = Field(alias="periodEnd", default=None)
    submit_date_time: str = Field(alias="submitDateTime")
    xbrl_flag: str = Field(alias="xbrlFlag", default="1")


class DocumentListResponse(BaseModel):
    """GET /api/v2/documents.json のレスポンス。"""

    metadata: DocumentListMetadata
    results: list[DocumentResult]


class FinancialSummary(BaseModel):
    """XBRL から抽出した財務サマリー（正規化型）。金額は百万円。

    PER / PBR / 配当利回りは株価が必要なため、この型には含めず
    FundamentalAgent（Phase 3）で市場データと組み合わせて算出する。
    """

    doc_id: str
    sec_code: str  # 4桁の証券コード（例: "7203"）
    filer_name: str
    fiscal_year: str  # 例: "2026年3月期"
    fiscal_period: str  # "FY"（通期） | "H1"（半期）
    net_sales: float  # 売上高
    operating_income: float  # 営業利益
    ordinary_income: float  # 経常利益
    net_income: float  # 当期純利益
    total_assets: float  # 総資産
    equity: float  # 自己資本
    equity_ratio: float  # 自己資本比率（%）
    eps: float  # 1株当たり利益（円）
    bps: float  # 1株当たり純資産（円）
    dividend_per_share: float  # 1株当たり配当（円）
