"""Bounded existing-observation coverage, never expected-filing discovery."""
import re
from datetime import date
from types import MappingProxyType

from fastapi import HTTPException
from app.activation_lifecycle import financial_reader
from app.financial_insights_contract import Budget, InsightsFailure, bounded_json, require
from app.financial_insights_service import admit_input, bounded_load, registry_guard
from app.financial_metric_engine import ANNUAL_COMPARISON_METRICS
from app.financial_metric_registry import SELECTION_POLICY
from app.financial_metric_schemas import StoredCoverageColumn, StoredCoverageWindow, StoredFinancialCoverage
from app.financial_metrics_service import FinancialMetrics
from app.quarter_window_comparison import date_only

COVERAGE_LIMITS = MappingProxyType(dict(windows=64, cells=704, source_references=4096))


class CoverageLimitFailure(InsightsFailure):
    def __init__(self, category):
        super().__init__("INSIGHTS_RESOURCE_LIMIT")
        self.limit_category = category


class CoverageBudget(Budget):
    """Same limits/accounting; annotate only a check that actually failed."""
    def check(self, name, value):
        try:
            super().check(name, value)
        except InsightsFailure as error:
            if error.code == "INSIGHTS_RESOURCE_LIMIT":
                # Inherited windows count complete-company input, before any
                # display filter; the map's own 64-window check is separate.
                raise CoverageLimitFailure("company_input_windows" if name == "windows" else name) from error
            raise


def coverage_limit(name, count):
    if type(count) is not int or not 0 <= count <= COVERAGE_LIMITS[name]:
        raise CoverageLimitFailure(name)


def parse_coverage_request(request):
    def invalid():
        raise HTTPException(422, detail="Choose one stored annual or quarter period kind, a verified publication pin, and an optional ordered pair of end_from/end_to dates (YYYY-MM-DD, inclusive).")
    if len(request.scope.get("query_string", b"")) > 64:
        invalid()
    pins = request.headers.getlist("X-FinLens-Data-Version")
    pairs = list(request.query_params.multi_items())
    if (len(pins) != 1 or not re.fullmatch(r"(?:0|[1-9][0-9]{0,15})", pins[0])
            or int(pins[0]) > 9007199254740991
            or len(pairs) not in {1, 3} or len({k for k, _ in pairs}) != len(pairs)
            or any(k not in {"period", "end_from", "end_to"} for k, _ in pairs)
            or dict(pairs).get("period") not in {"annual", "quarter"}
            or len(request.headers.getlist("content-length")) > 1
            or request.headers.get("content-length", "0") != "0" or "transfer-encoding" in request.headers):
        invalid()
    params = dict(pairs)
    end_from = end_to = None
    if len(pairs) == 3:
        raw = [params.get(key, "") for key in ("end_from", "end_to")]
        if any(not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) for value in raw):
            invalid()
        try:
            end_from, end_to = map(date.fromisoformat, raw)
        except ValueError:
            invalid()
        if end_from > end_to:
            invalid()
    return int(pins[0]), params["period"], end_from, end_to


@financial_reader
def build_coverage(session, ticker, pin, kind, budget, end_from=None, end_to=None):
    require(kind in {"annual", "quarter"})
    require((end_from is None and end_to is None) or
            (type(end_from) is date and type(end_to) is date and end_from <= end_to))
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
            if end_from is not None and not end_from <= period.end <= end_to:
                continue
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
        source_reference_count=references, columns=columns,
        end_date_range=None if end_from is None else {"from_date": end_from, "to_date": end_to}).model_dump(mode="json")
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
