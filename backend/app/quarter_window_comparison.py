"""Bounded comparison of already-admitted, directly reported duration windows.

This is not fiscal-quarter identification or a second financial calculator.
"""
from datetime import date
import re

from fastapi import HTTPException, Request

from app.activation_lifecycle import financial_reader
from app.financial_insights_contract import bounded_json, require
from app.financial_insights_service import admit_input, bounded_load, registry_guard
from app.financial_metric_engine import ANNUAL_COMPARISON_METRICS
from app.financial_metric_registry import SELECTION_POLICY
from app.financial_metric_schemas import ReportedQuarterColumn, ReportedQuarterComparison, ReportedQuarterWindow
from app.financial_metrics_service import FinancialMetrics


def parse_quarter_request(request: Request):
    """Strictly parse one version pin and zero or 2–4 exact windows."""
    def invalid():
        raise HTTPException(422, detail="Invalid reported-window selector or publication pin.")
    pins = request.headers.getlist("X-FinLens-Data-Version")
    if len(pins) != 1 or not re.fullmatch(r"(?:0|[1-9][0-9]{0,15})", pins[0]) or int(pins[0]) > 9007199254740991:
        invalid()
    if len(request.scope.get("query_string", b"")) > 256:
        invalid()
    pairs = list(request.query_params.multi_items())
    if any(key != "period" for key, _ in pairs) or len(pairs) not in {0, 2, 3, 4}:
        invalid()
    windows = []
    for _, value in pairs:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2},[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            invalid()
        try:
            start, end = (date.fromisoformat(item) for item in value.split(","))
        except ValueError:
            invalid()
        if not 75 <= (end - start).days + 1 <= 105:
            invalid()
        windows.append((start, end))
    if len(set(windows)) != len(windows):
        invalid()
    return int(pins[0]), tuple(windows)


def date_only(period):
    """Project presentation labels only after the engine has selected facts."""
    if period is not None:
        period.update(fiscal_year=None, fiscal_period=None, fiscal_label_basis="unknown")


@financial_reader
def build_quarter_comparison(session, ticker, pin, selected, budget):
    company, _versions, facts, configuration = bounded_load(session, ticker, pin, budget)
    admit_input(facts, (), budget)
    registry_guard(configuration)
    model = FinancialMetrics(company, facts, authorization_evidence=(), budget=budget)
    windows = {}
    for metric in budget.walk(ANNUAL_COMPARISON_METRICS):
        for period in budget.walk(model.metric_periods(metric, "quarter")):
            require(period.start is not None and 75 <= (period.end - period.start).days + 1 <= 105)
            key = (period.start, period.end)
            windows.setdefault(key, {}).setdefault(metric, period)
            budget.check("windows", len(windows))
    require(len(selected) in {0, 2, 3, 4} and len(set(selected)) == len(selected), "INSIGHTS_CONTRACT_INVALID")
    if any(key not in windows for key in budget.walk(selected)):
        raise HTTPException(422, detail="A selected reported window is not in the current publication.")
    ordered = sorted(windows, key=lambda item: (item[1], item[0]), reverse=True)
    columns = []
    for key in budget.walk(selected):
        anchors = windows[key]
        fallback = next(iter(anchors.values()))
        # Each metric retains its own canonical anchor. In particular YoY must
        # use the revenue anchor, not another metric's differing fiscal label.
        points = {metric: model.observation(metric, anchors.get(metric, fallback))
                  for metric in budget.walk(ANNUAL_COMPARISON_METRICS)}
        require(all(point.period is not None and point.period.kind == "quarter"
                    and (point.period.start, point.period.end) == key for point in budget.walk(points.values())))
        columns.append(ReportedQuarterColumn(window=ReportedQuarterWindow(start=key[0], end=key[1]), metrics=points))
    result = ReportedQuarterComparison(ticker=company.ticker, company_name=company.name, company_cik=company.cik,
        selection_policy=SELECTION_POLICY, available_windows=[ReportedQuarterWindow(start=a, end=b) for a, b in budget.walk(ordered)],
        columns=columns).model_dump(mode="json")
    for column in budget.walk(result["columns"]):
        for point in budget.walk(column["metrics"].values()):
            date_only(point.get("period"))
            for operand in budget.walk(point.get("inputs", ())):
                date_only(operand.get("period"))
    registry_guard(configuration)
    body = bounded_json(result, budget)
    registry_guard(configuration)
    return body, configuration
