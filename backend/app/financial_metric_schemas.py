"""Decimal values serialize as strings, preserving source and calculation precision."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_serializer, model_validator

PeriodKind = Literal["quarter", "half_year", "nine_months", "annual", "instant"]
Availability = Literal["available", "unavailable", "not_applicable"]
RevenueBasis = Literal["total_revenue", "customer_contract", "net_sales", "net_interest"]


class MetricMetadataModel(BaseModel):
    """Omit absent additive metadata, including on supported Pydantic 2.10."""

    @model_serializer(mode="wrap")
    def serialize_metadata(self, handler):
        result = handler(self)
        for key in ("revenue_basis", "comparability", "scope_authorization"):
            if key in result and result[key] is None:
                del result[key]
        return result


class FinancialPeriod(BaseModel):
    kind: PeriodKind
    start: date | None
    end: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    fiscal_label_basis: str = "unknown"


class FactProvenance(BaseModel):
    fact_id: int
    canonical_metric: str
    company_cik: str
    stored_metric: str
    original_concept: str
    value: Decimal
    unit: str
    period_start: date | None
    period_end: date
    stored_period_type: str | None
    source_fiscal_year: int | None
    source_fiscal_period: str | None
    frame: str | None
    filed: date
    form: str
    accession_number: str
    source: str
    sec_url: str
    stored_at: datetime


class MetricInput(MetricMetadataModel):
    role: str
    metric: str
    value: Decimal
    unit: str
    period: FinancialPeriod
    fact_ids: list[int]
    revenue_basis: RevenueBasis | None = None


class ScopeAuthorizationProvenance(BaseModel):
    permission: Literal["select:revenue", "denominator:net_margin"]
    approval_id: str
    version: int


class NormalizedMetric(MetricMetadataModel):
    metric: str
    unit: str
    status: Availability
    value: Decimal | None = None
    reason: str | None = None
    period: FinancialPeriod | None = None
    formula: str | None = None
    provenance: list[FactProvenance] = Field(default_factory=list)
    alternatives: list[FactProvenance] = Field(default_factory=list)
    inputs: list[MetricInput] = Field(default_factory=list)
    revenue_basis: RevenueBasis | None = None
    scope_authorization: ScopeAuthorizationProvenance | None = None


class NormalizedFinancialSummary(BaseModel):
    ticker: str
    company_name: str
    company_cik: str
    period: FinancialPeriod | None
    requested_period: PeriodKind
    selection_policy: str
    metrics: dict[str, NormalizedMetric]


class AnnualFinancialComparison(NormalizedFinancialSummary):
    requested_period: Literal["annual"] = "annual"
    requested_fiscal_year: int | None = Field(default=None, ge=1900, le=2099)
    fiscal_years: list[int]
    period_reason: str | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        if self.requested_fiscal_year is None:
            if self.period is not None or self.metrics:
                raise ValueError("Annual discovery must not select financial observations.")
        elif self.period is not None:
            p = self.period
            if (p.kind != "annual" or p.start is None or p.start > p.end
                    or p.fiscal_year != self.requested_fiscal_year or p.fiscal_period != "FY"
                    or p.end.year != self.requested_fiscal_year):
                raise ValueError("Annual reporting window does not match the requested fiscal end-year.")
        for name, point in self.metrics.items():
            if point.metric != name or point.period != self.period:
                raise ValueError("Metric reporting window does not match the selected annual window.")
            if self.period is None and point.status == "available":
                raise ValueError("An unresolved annual window cannot have an available metric.")
            if any(source.company_cik != self.company_cik
                   for source in (*point.provenance, *point.alternatives)):
                raise ValueError("Financial provenance does not belong to the requested company.")
        return self


class FiscalPeriodRequest(BaseModel):
    fiscal_year: int = Field(ge=1900, le=2099)
    quarter: int | None = Field(default=None, ge=1, le=4)

    @property
    def label(self):
        return f"Q{self.quarter} FY{self.fiscal_year}" if self.quarter else f"FY{self.fiscal_year}"


class MetricComparison(BaseModel):
    status: Availability
    reason: str | None = None
    earlier_period: FiscalPeriodRequest
    later_period: FiscalPeriodRequest
    earlier: NormalizedMetric
    later: NormalizedMetric
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    percentage_status: Literal["available", "unavailable", "not_applicable"] = "unavailable"
    percentage_reason: str | None = None
    direction: Literal["increase", "decrease", "no_change"] | None = None
    formula: str = "absolute_change = later - earlier; percentage_change = (later - earlier) / earlier"


class HistoryComparability(BaseModel):
    value_basis: Literal["reported_as_filed"] = "reported_as_filed"
    status: Literal["unverified"] = "unverified"
    reason: str = "SEC source values are preserved; cross-period stock-split/restatement share-basis comparability is not established."


class NormalizedMetricHistory(MetricMetadataModel):
    ticker: str
    company_cik: str
    metric: str
    unit: str
    requested_period: PeriodKind
    status: Availability
    reason: str | None
    selection_policy: str
    history: list[NormalizedMetric]
    comparability: HistoryComparability | None = None
