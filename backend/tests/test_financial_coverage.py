"""Guarded offline stored-coverage tests; no physical database/provider."""
from datetime import date, timedelta
from unittest.mock import Mock
import json
from types import MappingProxyType

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from app import financial_coverage as coverage, main, freshness_service
from app.financial_insights_contract import Budget, InsightsFailure
from app.financial_insights_service import registry_guard
from test_financial_insights import COMPANY, Rows, row_stats, session_for, fact
from test_quarter_window_comparison import source


def build(monkeypatch, rows, kind="quarter", budget=None):
    monkeypatch.setattr(coverage, "bounded_load", lambda *_: (COMPANY, (0, 0, 0), rows, registry_guard()))
    body, _ = coverage.build_coverage(None, "TEST", 0, kind, budget or Budget())
    return json.loads(body)


@pytest.mark.parametrize("kind", ["annual", "quarter"])
def test_union_includes_income_and_cashflow_without_revenue(monkeypatch, kind):
    rows = ([fact("NetIncomeLoss", id=1, year=2024), fact("NetCashProvidedByUsedInOperatingActivities", id=2, year=2025)]
        if kind == "annual" else [source(date(2025, 1, 1), 90, "NetIncomeLoss", 1),
                                 source(date(2025, 4, 1), 91, "NetCashProvidedByUsedInOperatingActivities", 2)])
    body = build(monkeypatch, rows, kind)
    assert body["window_count"] == 2 and body["cell_count"] == 22
    assert body["coverage_scope"] == "stored_reported_windows"
    assert all(len(c["metrics"]) == 11 for c in body["columns"])
    assert all(c["metrics"]["revenue"]["status"] == "unavailable" for c in body["columns"])
    assert body["data_version"] == body["facts_version"] == body["evidence_version"] == 0


@pytest.mark.parametrize("kind", ["annual", "quarter"])
def test_overlapping_same_end_windows_retained(monkeypatch, kind):
    end = date(2025, 12, 31) if kind == "annual" else date(2025, 3, 31)
    rows = [fact(id=1, period_start=date(2025, 1, 1), period_end=end),
            fact("NetIncomeLoss", id=2, period_start=date(2025, 1, 2), period_end=end)]
    body = build(monkeypatch, rows, kind)
    assert body["window_count"] == 2
    assert len({c["window"]["start"] for c in body["columns"]}) == 2


def test_conflict_and_missing_sources_preserve_reasons_and_alternatives(monkeypatch):
    rows = [source(date(2025, 1, 1), 90, "SalesRevenueNet", 1, "10"),
            source(date(2025, 1, 1), 90, "RevenueFromContractWithCustomerExcludingAssessedTax", 2, "11")]
    body = build(monkeypatch, rows)
    revenue = body["columns"][0]["metrics"]["revenue"]
    assert revenue["status"] == "unavailable" and revenue["reason"]
    assert {s["fact_id"] for s in revenue["alternatives"]} == {1, 2}
    assert body["columns"][0]["metrics"]["operating_cash_flow"]["status"] == "unavailable"


def test_company_wide_bank_exception_and_negative_capex(monkeypatch):
    rows = [fact("RevenuesNetOfInterestExpense", id=1, year=2024),
            source(date(2025, 1, 1), 90, "Revenues", 2),
            source(date(2025, 1, 1), 90, "NetCashProvidedByUsedInOperatingActivities", 3, "-2"),
            source(date(2025, 1, 1), 90, "PaymentsToAcquirePropertyPlantAndEquipment", 4, "-3")]
    points = build(monkeypatch, rows)["columns"][0]["metrics"]
    assert points["gross_margin"]["status"] == "not_applicable"
    assert points["operating_cash_flow"]["value"] == "-2"
    assert points["free_cash_flow"]["status"] == "unavailable"
    assert "Negative" in points["capital_expenditures"]["reason"]


def test_yoy_uses_unselected_inventory_and_original_source_dates(monkeypatch):
    rows = [source(date(2024, 1, 1), 91, identifier=1, value="100"), source(date(2025, 1, 1), 90, identifier=2, value="120")]
    body = build(monkeypatch, rows)
    point = body["columns"][0]["metrics"]["revenue_growth_yoy"]
    assert point["value"] == "0.2" and point["period"]["fiscal_year"] is None
    assert point["inputs"][1]["period"]["start"] == "2024-01-01"
    assert point["provenance"][1]["fact_id"] == 1


def test_empty_inventory_is_not_a_fabricated_window(monkeypatch):
    body = build(monkeypatch, [])
    assert body["columns"] == [] and body["window_count"] == body["cell_count"] == body["source_reference_count"] == 0


@pytest.mark.parametrize("kind", ["annual", "quarter"])
def test_all_derived_values_reuse_canonical_engine_and_complete_source_inputs(monkeypatch, kind):
    from app.financial_metrics_service import FinancialMetrics
    rows = []
    definitions = [("Revenues", "100", "120"), ("GrossProfit", "50", "60"), ("OperatingIncomeLoss", "20", "30"),
        ("NetIncomeLoss", "10", "24"), ("NetCashProvidedByUsedInOperatingActivities", "14", "20"),
        ("PaymentsToAcquirePropertyPlantAndEquipment", "4", "5")]
    for year in [2024, 2025]:
        for concept, earlier, later in definitions:
            rows.append(fact(concept, earlier if year == 2024 else later, year=year, id=len(rows)+1) if kind == "annual"
                else source(date(year, 1, 1), 91 if year == 2024 else 90, concept, len(rows)+1, earlier if year == 2024 else later))
    body = build(monkeypatch, rows, kind)
    model = FinancialMetrics(COMPANY, rows)
    latest = body["columns"][0]
    for metric in latest["metrics"]:
        period = next(p for p in model.metric_periods(metric, kind) if p.end.year == 2025)
        expected = model.observation(metric, period).model_dump(mode="json")
        coverage.date_only(expected["period"])
        for operand in expected["inputs"]: coverage.date_only(operand["period"])
        assert latest["metrics"][metric] == expected
    assert latest["metrics"]["free_cash_flow"]["value"] == "15"
    assert latest["metrics"]["revenue_growth_yoy"]["value"] == "0.2"
    assert all(latest["metrics"][m]["status"] == "available" for m in ["gross_margin", "operating_margin", "net_margin"])


def test_actual_64_window_map_returns_all_704_cells(monkeypatch):
    rows = [source(date(2025, 1, 1) + timedelta(days=i), 90, identifier=i + 1) for i in range(64)]
    body = build(monkeypatch, rows)
    assert body["window_count"] == 64 and body["cell_count"] == 704
    assert len(body["columns"]) == 64


@pytest.mark.parametrize("name,limit", [("windows", 64), ("cells", 704), ("source_references", 4096)])
def test_explicit_limit_boundaries(name, limit):
    assert coverage.COVERAGE_LIMITS[name] == limit
    coverage.coverage_limit(name, limit)
    with pytest.raises(InsightsFailure): coverage.coverage_limit(name, limit + 1)


def test_window_overflow_rejects_before_serialization(monkeypatch):
    rows = [source(date(2025, 1, 1) + timedelta(days=i), 90, identifier=i + 1) for i in range(65)]
    forbidden = Mock(side_effect=AssertionError("partial serialization forbidden"))
    monkeypatch.setattr(coverage, "bounded_json", forbidden)
    with pytest.raises(InsightsFailure): build(monkeypatch, rows)
    assert not forbidden.called


def test_reference_count_guard_is_in_result_path(monkeypatch):
    monkeypatch.setattr(coverage, "COVERAGE_LIMITS", MappingProxyType(dict(windows=64, cells=704, source_references=0)))
    with pytest.raises(InsightsFailure): build(monkeypatch, [source(date(2025, 1, 1), 90)])


def test_work_and_cooperative_deadline_reject(monkeypatch):
    exhausted = Budget(); exhausted.counts["work"] = 2_000_000
    with pytest.raises(InsightsFailure): build(monkeypatch, [source(date(2025, 1, 1), 90)], budget=exhausted)
    expired = Budget(lambda: 0); expired.clock = lambda: 20
    with pytest.raises(InsightsFailure): build(monkeypatch, [], budget=expired)


def request(query="period=annual", pins=("0",), extra=()):
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": query.encode(),
        "headers": [(b"x-finlens-data-version", v.encode()) for v in pins] + list(extra)})


@pytest.mark.parametrize("query,pins,extra", [("", ("0",), ()), ("period=instant", ("0",), ()),
    ("period=annual&period=annual", ("0",), ()), ("period=quarter&extra=1", ("0",), ()),
    ("period=annual", (), ()), ("period=annual", ("0", "0"), ()), ("period=annual", ("-0",), ()),
    ("period=annual", ("9007199254740992",), ()), ("period=quarter", ("0",), ((b"content-length", b"4"),))])
def test_request_validation(query, pins, extra):
    with pytest.raises(HTTPException): coverage.parse_coverage_request(request(query, pins, extra))


def test_oversized_raw_query_rejects_before_parsing_or_headers():
    class Unparsed:
        scope = {"query_string": b"period=" + b"a" * 58}
        @property
        def query_params(self):
            raise AssertionError("Oversized query must not be parsed")
        @property
        def headers(self):
            raise AssertionError("Oversized query must reject first")
    with pytest.raises(HTTPException) as error:
        coverage.parse_coverage_request(Unparsed())
    assert error.value.status_code == 422


def test_publication_zero_real_route_and_stale_pin(monkeypatch):
    rows = [source(date(2025, 1, 1), 90)]
    session, _ = session_for(rows)
    company = dict(vars(COMPANY), data_version=0, facts_version=0, evidence_version=0)
    session.execute.side_effect = [Mock(), Rows([company]), Rows([{"count": 1, "bytes": row_stats(rows[0]), "invalid": 0}]), Rows([vars(rows[0])])]
    session.get_bind.return_value.dialect.name = "postgresql"; session.scalar.return_value = 0
    stale_session = Mock(); stale_session.get_bind.return_value.dialect.name = "postgresql"; stale_session.scalar.return_value = 0
    monkeypatch.setattr(main, "InsightsSessionLocal", Mock(side_effect=[session, stale_session]))
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    with TestClient(main.app) as client:
        good = client.get("/companies/TEST/financials/coverage?period=quarter", headers={"X-FinLens-Data-Version": "0"})
        stale = client.get("/companies/TEST/financials/coverage?period=quarter", headers={"X-FinLens-Data-Version": "1"})
    assert good.status_code == 200 and good.headers["X-FinLens-Data-Version"] == "0"
    assert good.json()["data_version"] == 0 and session.close.called
    assert stale.status_code == 409 and stale.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    assert stale_session.close.called


def test_active_configuration_denies_before_session(monkeypatch):
    from app import revenue_scope_authorizations as auth
    factory = Mock(side_effect=AssertionError("no database session"))
    monkeypatch.setattr(main, "InsightsSessionLocal", factory)
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/coverage?period=annual", headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 503 and "source-authorization" in response.json()["detail"]
    assert not factory.called


def test_configuration_change_during_composition_denies(monkeypatch):
    from app import revenue_scope_authorizations as auth
    original = coverage.bounded_json
    def changed(result, budget):
        body = original(result, budget)
        monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
        return body
    monkeypatch.setattr(coverage, "bounded_json", changed)
    with pytest.raises(InsightsFailure): build(monkeypatch, [source(date(2025, 1, 1), 90)])


@pytest.mark.parametrize("stats", [{"count": 10001, "bytes": 0, "invalid": 0},
    {"count": 1, "bytes": 8*1024*1024+1, "invalid": 0}, {"count": 1, "bytes": 1, "invalid": 1}])
def test_real_inventory_preflight_rejects_before_fact_transfer(stats):
    session, result = session_for([source(date(2025, 1, 1), 90)], stats=stats)
    with pytest.raises(InsightsFailure): coverage.build_coverage(session, "TEST", 7, "quarter", Budget())
    assert session.execute.call_count == 2 and result.offset == 0


def test_configuration_change_during_session_cleanup_cannot_publish(monkeypatch):
    from app import revenue_scope_authorizations as auth
    rows = [source(date(2025, 1, 1), 90)]
    session, _ = session_for(rows)
    session.execute.side_effect = [Mock(), *list(session.execute.side_effect)]
    session.get_bind.return_value.dialect.name = "postgresql"; session.scalar.return_value = 7
    session.close.side_effect = lambda: monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda: session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/coverage?period=quarter", headers={"X-FinLens-Data-Version": "7"})
    assert response.status_code == 503 and response.headers["X-FinLens-Error-Code"] == "INSIGHTS_CONFIGURATION_UNSUPPORTED"
    assert "columns" not in response.json()
