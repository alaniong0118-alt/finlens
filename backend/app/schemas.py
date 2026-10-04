from datetime import date

from pydantic import BaseModel
from typing import Literal


class FilingAnswerClaimResponse(BaseModel):
    text: str
    citation_ids: list[str]


class FilingCitationResponse(BaseModel):
    citation_id: str
    chunk_id: str
    accession_number: str
    form: str
    filed: date | None
    filename: str
    start_char: int
    end_char: int
    sec_url: str
    similarity: float
    semantic_similarity: float
    lexical_score: float
    hybrid_score: float
    evidence_reason: str


class FilingAnswerResponse(BaseModel):
    ticker: str
    company_name: str
    accession_number: str
    question: str
    answer: str
    claims: list[FilingAnswerClaimResponse]
    citations: list[FilingCitationResponse]
    evidence_status: Literal["sufficient", "insufficient"]
    insufficient_evidence: bool
    model: str


class CompanyResponse(BaseModel):
    id: int
    ticker: str
    name: str
    cik: str
    exchange: str
    has_indexed_filing: bool
    indexed_filing_count: int


class MetricPeriodResponse(BaseModel):
    value: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    period_start: date
    period_end: date
    fiscal_year: int | None
    fiscal_period: str | None
    filed: date | None
    form: str | None


class FinancialSourceResponse(BaseModel):
    accession_number: str
    form: str | None
    filed: date | None
    sec_url: str


class FinancialMetricResponse(BaseModel):
    metric: str
    value: float
    unit: str
    current: MetricPeriodResponse
    previous: MetricPeriodResponse | None = None
    source: FinancialSourceResponse | None = None


class FinancialSummaryResponse(BaseModel):
    company_cik: str
    metrics: dict[str, FinancialMetricResponse]


class FinancialSnapshotPeriodResponse(BaseModel):
    period_start: date
    period_end: date
    fiscal_year: int | None
    fiscal_period: str | None
    filed: date | None
    form: str | None


class FinancialSnapshotValuesResponse(BaseModel):
    revenue: float
    net_income: float
    diluted_eps: float | None = None


class FinancialSnapshotResponse(BaseModel):
    company_cik: str
    period: FinancialSnapshotPeriodResponse
    values: FinancialSnapshotValuesResponse
    analysis: FinancialSummaryResponse


class FinancialHistoryItemResponse(BaseModel):
    period_start: date
    period_end: date
    fiscal_year: int | None
    fiscal_period: str | None
    filed: date | None
    form: str | None
    revenue: float | None
    net_income: float | None
    diluted_eps: float | None


class FinancialHistoryResponse(BaseModel):
    company_cik: str
    history: list[FinancialHistoryItemResponse]
class FinancialSourceResponse(BaseModel):
    accession_number: str
    form: str | None
    filed: date | None
    period_start: date | None
    period_end: date | None
    metrics: list[str]
    sec_url: str
    has_filing_chunks: bool = False
