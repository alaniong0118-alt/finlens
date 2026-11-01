"""Guarded offline reported-window comparison tests; synthetic facts only."""
from datetime import date, timedelta
import json
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import quarter_window_comparison as quarter
from app.financial_insights_contract import Budget, InsightsFailure
from app.financial_insights_service import registry_guard
from test_financial_insights import COMPANY, Rows, fact, row_stats, session_for


def row(identifier, concept, start, end, value="10"):
    return fact(concept, value, year=end.year, id=identifier, period_start=start, period_end=end,
                period_type="quarter", filed=end + timedelta(days=30))


def source(start, days, concept="Revenues", identifier=1, value="10"):
    return row(identifier, concept, start, start + timedelta(days=days - 1), value)


def build(monkeypatch, rows, selected=(), budget=None):
    monkeypatch.setattr(quarter, "bounded_load", lambda *_args: (COMPANY, (0, 0, 0), rows, registry_guard()))
    body, _ = quarter.build_quarter_comparison(None, "TEST", 0, tuple(selected), budget or Budget())
    return json.loads(body)


def request(query="", pin="0"):
    headers = [] if pin is None else [(b"x-finlens-data-version", pin.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": query.encode(), "headers": headers})


@pytest.mark.parametrize("days,expected", [(74, False), (75, True), (105, True), (106, False)])
def test_direct_duration_boundaries(monkeypatch, days, expected):
    start = date(2025, 1, 1)
    result = build(monkeypatch, [source(start, days)])
    assert bool(result["available_windows"]) is expected


def test_union_discovers_cashflow_and_income_without_revenue(monkeypatch):
    one, two = date(2025, 1, 1), date(2025, 4, 1)
    rows = [source(one, 90, "NetIncomeLoss", 1),
            source(two, 91, "NetCashProvidedByUsedInOperatingActivities", 2)]
    result = build(monkeypatch, rows)
    assert {(x["start"], x["end"]) for x in result["available_windows"]} == {
        ("2025-01-01", "2025-03-31"), ("2025-04-01", "2025-06-30")}
    assert result["columns"] == []


def test_same_end_and_overlapping_windows_remain_distinct(monkeypatch):
    end = date(2025, 3, 31)
    rows = [row(1, "Revenues", date(2025, 1, 1), end), row(2, "NetIncomeLoss", date(2025, 1, 2), end)]
    result = build(monkeypatch, rows, [(x.period_start, x.period_end) for x in rows])
    assert len(result["available_windows"]) == len(result["columns"]) == 2
    assert result["columns"][0]["metrics"]["net_income"]["status"] == "unavailable"
    assert result["columns"][1]["metrics"]["revenue"]["status"] == "unavailable"


def test_bank_exclusions_and_missing_direct_cashflow_are_retained(monkeypatch):
    starts = [date(2025, 1, 1), date(2025, 4, 1)]
    rows = [source(start, 90, "RevenuesNetOfInterestExpense", i+1) for i, start in enumerate(starts)]
    result = build(monkeypatch, rows, [(r.period_start, r.period_end) for r in rows])
    for column in result["columns"]:
        assert column["metrics"]["gross_margin"]["status"] == "not_applicable"
        assert column["metrics"]["operating_cash_flow"]["status"] == "unavailable"
        assert column["metrics"]["operating_cash_flow"]["reason"]


def test_yoy_uses_prior_complete_inventory_and_hides_inferred_labels(monkeypatch):
    rows = [source(date(2024, 1, 1), 91, identifier=1, value="100"),
            source(date(2025, 1, 1), 90, identifier=2, value="120"),
            source(date(2025, 4, 1), 91, identifier=3, value="130")]
    result = build(monkeypatch, rows, [(r.period_start, r.period_end) for r in rows[1:]])
    yoy = result["columns"][0]["metrics"]["revenue_growth_yoy"]
    assert yoy["status"] == "available" and yoy["value"] == "0.2"
    assert {x["role"] for x in yoy["inputs"]} == {"current", "prior"}
    assert yoy["period"]["fiscal_year"] is None and yoy["period"]["fiscal_period"] is None
    assert all(item["period"]["fiscal_year"] is None for item in yoy["inputs"])


def test_53_week_shift_uses_existing_prior_window_rules(monkeypatch):
    rows = [source(date(2024, 1, 1), 91, identifier=1, value="100"),
            source(date(2025, 1, 6), 91, identifier=2, value="120"),
            source(date(2025, 4, 7), 91, identifier=3, value="130")]
    result = build(monkeypatch, rows, [(r.period_start, r.period_end) for r in rows[1:]])
    growth = result["columns"][0]["metrics"]["revenue_growth_yoy"]
    assert growth["status"] == "available" and growth["value"] == "0.2"
    assert growth["inputs"][1]["period"]["start"] == "2024-01-01"


@pytest.mark.parametrize("query,pin", [("", None), ("", "00"), ("", "-1"), ("", "9007199254740992"),
    ("period=2025-01-01,2025-03-31", "0"), ("mode=discover", "0"),
    ("period=2025-01-01,2025-03-31&period=2025-01-01,2025-03-31", "0"),
    ("period=2025-02-30,2025-04-30&period=2025-04-01,2025-06-30", "0")])
def test_malformed_selectors_and_pin_reject(query, pin):
    with pytest.raises(HTTPException) as caught: quarter.parse_quarter_request(request(query, pin))
    assert caught.value.status_code == 422


def test_zero_pin_and_exact_two_windows():
    pin, selected = quarter.parse_quarter_request(request("period=2025-01-01,2025-03-31&period=2025-04-01,2025-06-30"))
    assert pin == 0 and selected == ((date(2025, 1, 1), date(2025, 3, 31)), (date(2025, 4, 1), date(2025, 6, 30)))


def test_unknown_window_rejects_without_partial_result(monkeypatch):
    start = date(2025, 1, 1)
    with pytest.raises(HTTPException) as caught:
        build(monkeypatch, [source(start, 90)], [(start, date(2025, 3, 31)), (date(2024, 1, 1), date(2024, 3, 31))])
    assert caught.value.status_code == 422


def test_changed_registry_rejected_before_publication(monkeypatch):
    from app import revenue_scope_authorizations as auth
    calls = 0
    def changed(*_args):
        nonlocal calls
        calls += 1
        if calls == 2: monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
        return registry_guard()
    monkeypatch.setattr(quarter, "registry_guard", changed)
    with pytest.raises(InsightsFailure) as caught:
        build(monkeypatch, [source(date(2025, 1, 1), 90)])
    assert caught.value.code == "INSIGHTS_CONFIGURATION_UNSUPPORTED"


def test_work_budget_exhaustion_rejects_without_result(monkeypatch):
    budget = Budget(); budget.counts["work"] = 2_000_000
    with pytest.raises(InsightsFailure) as caught:
        build(monkeypatch, [source(date(2025, 1, 1), 90)], budget=budget)
    assert caught.value.code == "INSIGHTS_RESOURCE_LIMIT"


def test_candidate_group_limit_is_enforced(monkeypatch):
    rows = [source(date(2025, 1, 1), 90, identifier=i) for i in range(1, 258)]
    with pytest.raises(InsightsFailure) as caught:
        build(monkeypatch, rows)
    assert caught.value.code == "INSIGHTS_RESOURCE_LIMIT"


def test_discovered_window_limit_is_enforced(monkeypatch):
    rows = [source(date(2024, 1, 1) + timedelta(days=i), 90, identifier=i + 1) for i in range(257)]
    with pytest.raises(InsightsFailure) as caught:
        build(monkeypatch, rows)
    assert caught.value.code == "INSIGHTS_RESOURCE_LIMIT"


def test_output_limit_is_enforced():
    from app.financial_insights_contract import bounded_json
    with pytest.raises(InsightsFailure) as caught:
        bounded_json({"reason": ["x" * 1024 for _ in range(4097)]}, Budget())
    assert caught.value.code == "INSIGHTS_RESOURCE_LIMIT"


def test_real_route_reads_complete_inventory_and_preserves_publication(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, freshness_service
    rows = [source(date(2024, 1, 1), 91, identifier=1, value="100"),
            source(date(2025, 1, 1), 90, identifier=2, value="120"),
            source(date(2025, 4, 1), 91, identifier=3, value="130")]
    session, result = session_for(rows)
    session.execute.side_effect = [Mock(), *list(session.execute.side_effect)]
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = 7
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda: session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/quarters?period=2025-01-01,2025-03-31&period=2025-04-01,2025-06-30",
                              headers={"X-FinLens-Data-Version": "7"})
    assert response.status_code == 200, response.text
    assert response.headers["X-FinLens-Data-Version"] == "7"
    assert response.json()["columns"][0]["metrics"]["revenue_growth_yoy"]["value"] == "0.2"
    assert result.closed and session.close.called


def test_active_authorization_configuration_fails_before_session(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, revenue_scope_authorizations as auth
    session = Mock(side_effect=AssertionError("must not load a session"))
    monkeypatch.setattr(main, "InsightsSessionLocal", session)
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/quarters", headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 503
    assert response.headers["X-FinLens-Error-Code"] == "INSIGHTS_CONFIGURATION_UNSUPPORTED"
    assert "source-authorization configuration" in response.json()["detail"]
    assert not session.called


def test_publication_zero_and_registry_change_during_cleanup(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, freshness_service, revenue_scope_authorizations as auth
    rows = [source(date(2025, 1, 1), 90)]
    def setup():
        session, _ = session_for(rows)
        company = dict(vars(COMPANY), data_version=0, facts_version=0, evidence_version=0)
        session.execute.side_effect = [Mock(), Rows([company]), Rows([{"count": len(rows),
            "bytes": sum(row_stats(f) for f in rows), "invalid": 0}]), Rows([vars(f) for f in rows])]
        session.get_bind.return_value.dialect.name = "postgresql"; session.scalar.return_value = 0
        monkeypatch.setattr(main, "InsightsSessionLocal", lambda: session)
        monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
        return session
    setup()
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/quarters", headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 200 and response.headers["X-FinLens-Data-Version"] == "0"
    session = setup()
    session.close.side_effect = lambda: monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
    with TestClient(main.app) as client:
        rejected = client.get("/companies/TEST/financials/quarters", headers={"X-FinLens-Data-Version": "0"})
    assert rejected.status_code == 503 and rejected.headers["X-FinLens-Error-Code"] == "INSIGHTS_CONFIGURATION_UNSUPPORTED"
    assert "available_windows" not in rejected.json()
