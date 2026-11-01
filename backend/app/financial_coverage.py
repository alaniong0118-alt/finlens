"""Bounded existing-observation coverage, never expected-filing discovery."""
import re
from types import MappingProxyType

from fastapi import HTTPException
from app.activation_lifecycle import financial_reader
from app.financial_insights_contract import bounded_json, require
from app.financial_insights_service import admit_input, bounded_load, registry_guard
from app.financial_metric_engine import ANNUAL_COMPARISON_METRICS
from app.financial_metric_registry import SELECTION_POLICY
from app.financial_metric_schemas import StoredCoverageColumn, StoredCoverageWindow, StoredFinancialCoverage
from app.financial_metrics_service import FinancialMetrics
from app.quarter_window_comparison import date_only

COVERAGE_LIMITS = MappingProxyType(dict(windows=64, cells=704, source_references=4096))


def coverage_limit(name, count):
    require(type(count) is int and 0 <= count <= COVERAGE_LIMITS[name], "INSIGHTS_RESOURCE_LIMIT")


def parse_coverage_request(request):
    if len(request.scope.get("query_string", b"")) > 64:
        raise HTTPException(422, detail="Choose one stored annual or quarter period kind and a verified publication pin.")
    pins = request.headers.getlist("X-FinLens-Data-Version")
    pairs = list(request.query_params.multi_items())
    if (len(pins) != 1 or not re.fullmatch(r"(?:0|[1-9][0-9]{0,15})", pins[0])
            or int(pins[0]) > 9007199254740991
            or len(pairs) != 1 or pairs[0][0] != "period" or pairs[0][1] not in {"annual", "quarter"}
            or len(request.headers.getlist("content-length")) > 1
            or request.headers.get("content-length", "0") != "0" or "transfer-encoding" in request.headers):
        raise HTTPException(422, detail="Choose one stored annual or quarter period kind and a verified publication pin.")
    return int(pins[0]), pairs[0][1]


@financial_reader
def build_coverage(session, ticker, pin, kind, budget):
    require(kind in {"annual", "quarter"})
    budget.deadline()
    company, versions, facts, configuration = bounded_load(session, ticker, pin, budget)
    admit_input(facts, (), budget)
    registry_guard(configuration)
    model = FinancialMetrics(company, facts, authorization_evidence=(), budget=budget)
    windows = {}
    low, high = (75, 105) if kind == "quarter" else (330, 390)
    for metric in budget.walk(ANNUAL_COMPARISON_METRICS):
        for period in budget.walk(model.metric_periods(metric, kind)):
            require(period.kind == kind and period.start is not None and low <= (period.end - period.start).days + 1 <= high)
            key = period.start, period.end
            windows.setdefault(key, {}).setdefault(metric, period)
            coverage_limit("windows", len(windows))
            coverage_limit("cells", len(windows) * len(ANNUAL_COMPARISON_METRICS))
    columns, references = [], 0
    for key in budget.walk(sorted(windows, key=lambda w: (w[1], w[0]), reverse=True)):
        anchors = windows[key]
        fallback = next(iter(anchors.values()))
        points = {}
        for metric in budget.walk(ANNUAL_COMPARISON_METRICS):
            point = model.observation(metric, anchors.get(metric, fallback))
            require(point.period is not None and point.period.kind == kind
                    and (point.period.start, point.period.end) == key)
            references += len(point.provenance) + len(point.alternatives)
            for operand in budget.walk(point.inputs):
                references += len(operand.fact_ids)
            coverage_limit("source_references", references)
            points[metric] = point
        columns.append(StoredCoverageColumn(window=StoredCoverageWindow(start=key[0], end=key[1]), metrics=points))
    result = StoredFinancialCoverage(ticker=company.ticker, company_name=company.name, company_cik=company.cik,
        requested_period=kind, selection_policy=SELECTION_POLICY, data_version=versions[0], facts_version=versions[1],
        evidence_version=versions[2], window_count=len(columns), cell_count=len(columns) * len(ANNUAL_COMPARISON_METRICS),
        source_reference_count=references, columns=columns).model_dump(mode="json")
    for column in budget.walk(result["columns"]):
        for point in budget.walk(column["metrics"].values()):
            date_only(point.get("period"))
            for operand in budget.walk(point.get("inputs", ())):
                date_only(operand.get("period"))
    registry_guard(configuration)
    budget.deadline()
    body = bounded_json(result, budget)
    registry_guard(configuration)
    budget.deadline()
    return body, configuration
