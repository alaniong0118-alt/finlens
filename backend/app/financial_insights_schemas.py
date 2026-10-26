"""Insights-only wire types; canonical financial schemas remain unchanged."""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from app.financial_metric_schemas import FinancialPeriod, MetricComparison


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReferenceIdentity(ClosedModel):
    scope: str
    kind: Literal["observation", "comparison", "operand", "source", "candidate", "window", "rejection"]
    key: str
    metric: str | None = None
    side: Literal["earlier", "later"] | None = None
    role: str | None = None
    window: str | None = None


class FinancialReference(ReferenceIdentity):
    category: Literal["F"] = "F"
    kind: Literal["observation", "comparison", "operand", "source"]


class DiagnosticReference(ReferenceIdentity):
    category: Literal["D"] = "D"


EvidenceReference = Annotated[FinancialReference | DiagnosticReference, Field(discriminator="category")]


class EvidenceNode(ClosedModel):
    ref: EvidenceReference
    edges: list[EvidenceReference]
    data: dict[str, Any]


class InsightStatement(ClosedModel):
    ruleset: Literal["fin-depth-01-v1"] = "fin-depth-01-v1"
    key: str
    rule: Literal["VALUE", "CHANGE", "PERCENT_CHANGE", "PERCENT_UNAVAILABLE", "PRECISION_NOTICE", "UNAVAILABLE", "OVERALL", "LIMITATION"]
    metric: str | None = None
    side: Literal["earlier", "later"] | None = None
    outcome: Literal["all_increased", "mixed", "revenue_not_increased", "not_assessable"] | None = None
    text: str
    financial: list[FinancialReference]
    diagnostic: list[DiagnosticReference]


class InsightsResponse(ClosedModel):
    mode: Literal["discover", "compare"]
    ticker: str
    company_cik: str
    company_name: str
    data_version: int
    facts_version: int
    evidence_version: int
    scope: str
    fiscal_years: list[int]
    earlier_fiscal_year: int | None
    later_fiscal_year: int | None
    periods: dict[str, FinancialPeriod | None]
    selection_policy: str
    completeness: Literal["complete", "partial", "unavailable"] | None
    comparisons: dict[str, MetricComparison]
    evidence: list[EvidenceNode]
    statements: list[InsightStatement]
