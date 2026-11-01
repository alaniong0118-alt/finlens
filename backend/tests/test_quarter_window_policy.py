"""Quarter route/profile consistency; run through the guarded offline runner."""
from datetime import date
from pathlib import Path
from types import MappingProxyType
from unittest.mock import Mock
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, main, freshness_service, quarter_window_comparison as quarter
from app.financial_insights_contract import Budget
from app.release_policy import READONLY_ROUTES, READER_ROUTES, ReleaseAdmissionMiddleware
from test_financial_insights import COMPANY, Rows, row_stats, session_for
from test_quarter_window_comparison import source


TEMPLATE = "/companies/{ticker}/financials/quarters"
PATH = "/companies/TEST/financials/quarters"
SELECTION = "?period=2025-01-01,2025-03-31&period=2025-04-01,2025-06-30"


def forbidden(*args, **kwargs):
    raise AssertionError("No denied request may reach a handler, physical database or session")


@pytest.fixture(autouse=True)
def browser_advertised_profile(monkeypatch):
    # A deliberately narrow source tripwire connects this real backend probe to
    # the fixture's existing inline capabilities reply. Refactoring that reply
    # requires updating this proof, rather than silently testing another profile.
    fixture = (Path(__file__).resolve().parents[2] / "frontend/e2e/fixtures/browser.ts").read_text(encoding="utf-8")
    replies = [line for line in fixture.splitlines() if "if (path === '/capabilities')" in line]
    assert len(replies) == 1
    profiles = re.findall(r"server_profile:\s*'([^']+)'", replies[0])
    assert profiles == ["sec_readonly"]
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile(profiles[0]))
    monkeypatch.setattr(main, "InsightsSessionLocal", forbidden)
    monkeypatch.setattr(main, "HttpSessionLocal", forbidden)
    return profiles[0]


def fake_read(monkeypatch, pin=0, stats=None):
    rows = [source(date(2024, 1, 1), 91, identifier=1, value="100"),
            source(date(2025, 1, 1), 90, identifier=2, value="120"),
            source(date(2025, 4, 1), 91, identifier=3, value="130")]
    session, result = session_for(rows)
    company = dict(vars(COMPANY), data_version=pin, facts_version=pin, evidence_version=pin)
    summary = stats if stats is not None else {"count": len(rows), "bytes": sum(row_stats(row) for row in rows), "invalid": 0}
    session.execute.side_effect = [Mock(), Rows([company]), Rows([summary]), result]
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = pin
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda: session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    return session, result


@pytest.mark.parametrize("pin", [0, 7])
@pytest.mark.parametrize("query", ["", SELECTION])
def test_browser_advertised_profile_actually_admits_discovery_and_comparison(monkeypatch, browser_advertised_profile, pin, query):
    assert ("GET", TEMPLATE) in READONLY_ROUTES
    session, result = fake_read(monkeypatch, pin)
    client = TestClient(main.app)
    capabilities = client.get("/capabilities").json()
    assert capabilities["server_profile"] == browser_advertised_profile and capabilities["research_mode"] is True
    response = client.get(PATH + query, headers={"X-FinLens-Data-Version": str(pin)})
    assert response.status_code == 200, response.text
    assert response.headers["X-FinLens-Data-Version"] == str(pin) and response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert len(body["available_windows"]) == 3 and len(body["columns"]) == (2 if query else 0)
    if query:
        assert body["columns"][0]["metrics"]["revenue_growth_yoy"]["value"] == "0.2"
        assert all(len(column["metrics"]) == 11 for column in body["columns"])
    assert "REPEATABLE READ, READ ONLY" in str(session.execute.call_args_list[0].args[0])
    assert result.closed and session.close.called and not session.commit.called


@pytest.mark.parametrize("query,headers", [("", {}), ("", {"X-FinLens-Data-Version": "00"}),
    ("?mode=discover", {"X-FinLens-Data-Version": "0"}),
    ("?period=2025-01-01,2025-03-31", {"X-FinLens-Data-Version": "0"}),
    ("?period=2025-01-01,2025-03-31&period=2025-01-01,2025-03-31", {"X-FinLens-Data-Version": "0"}),
    ("", [("X-FinLens-Data-Version", "0"), ("X-FinLens-Data-Version", "0")])])
def test_required_pins_and_selectors_reject_before_session(query, headers):
    assert TestClient(main.app).get(PATH + query, headers=headers).status_code == 422


def test_stale_pin_closes_readonly_session_without_composition(monkeypatch):
    session, result = fake_read(monkeypatch)
    response = TestClient(main.app).get(PATH, headers={"X-FinLens-Data-Version": "7"})
    assert response.status_code == 409 and response.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    assert session.close.called and result.offset == 0 and session.execute.call_count == 1


@pytest.mark.parametrize("owner,name", [("revenue_scope_authorizations", "REVENUE_SELECTION_AUTHORIZATIONS"),
    ("revenue_scope_authorizations", "DENOMINATOR_AUTHORIZATIONS"), ("revenue_scope_authorizations", "AUTHORIZATION_WITHDRAWALS"),
    ("sec_evidence_adapter", "PRODUCTION_EVIDENCE_POLICIES")])
def test_each_active_registry_still_denies_before_session(monkeypatch, owner, name):
    import importlib
    monkeypatch.setattr(importlib.import_module("app." + owner), name, (object(),))
    response = TestClient(main.app).get(PATH, headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 503 and response.headers["X-FinLens-Error-Code"] == "INSIGHTS_CONFIGURATION_UNSUPPORTED"


@pytest.mark.parametrize("stage", ["serialization", "session_cleanup"])
def test_registry_change_cannot_publish_a_partial_response(monkeypatch, stage):
    from app import revenue_scope_authorizations as auth
    session, _ = fake_read(monkeypatch)
    def change():
        monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
    if stage == "session_cleanup":
        session.close.side_effect = change
    else:
        original = quarter.bounded_json
        def changed(*args):
            body = original(*args)
            change()
            return body
        monkeypatch.setattr(quarter, "bounded_json", changed)
    response = TestClient(main.app).get(PATH + SELECTION, headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 503 and response.headers["X-FinLens-Error-Code"] == "INSIGHTS_CONFIGURATION_UNSUPPORTED"
    assert "columns" not in response.json() and session.close.called


@pytest.mark.parametrize("kind", ["facts", "work", "output", "deadline"])
def test_route_budgets_still_refuse_without_partial_results_and_close_session(monkeypatch, kind):
    session, result = fake_read(monkeypatch, stats={"count": 10001, "bytes": 1, "invalid": 0} if kind == "facts" else None)
    budget = Budget()
    if kind == "work":
        budget.counts["work"] = 2_000_000
    if kind == "deadline":
        budget = Budget(lambda: 0)
        budget.clock = lambda: 20
    if kind == "output":
        from app import financial_insights_contract as contract
        monkeypatch.setattr(contract, "LIMITS", MappingProxyType(dict(contract.LIMITS, output_bytes=1)))
    monkeypatch.setattr(main, "Budget", lambda: budget)
    response = TestClient(main.app).get(PATH + SELECTION, headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == (504 if kind == "deadline" else 503)
    assert response.headers["X-FinLens-Error-Code"] == ("INSIGHTS_DEADLINE_EXCEEDED" if kind == "deadline" else "INSIGHTS_RESOURCE_LIMIT")
    assert "columns" not in response.json() and session.close.called
    if kind == "facts":
        assert result.offset == 0


@pytest.mark.parametrize("method,path", [(method, PATH) for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")]
    + [("GET", PATH + "/"), ("GET", PATH + "/detail"), ("GET", PATH + "-export"),
       ("POST", PATH + "/acquire"), ("POST", "/companies/TEST/refresh")])
def test_exact_admission_does_not_expand_prefix_methods_or_acquisition(method, path):
    response = TestClient(main.app).request(method, path, content=b"malformed JSON",
        headers={"X-FinLens-Server-Profile": "development"})
    assert response.status_code == 403 and response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"


def test_sec_reader_still_denies_even_captured_quarter_route(monkeypatch):
    assert ("GET", TEMPLATE) not in READER_ROUTES
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_reader"))
    app = FastAPI()
    app.get(TEMPLATE)(forbidden)
    app.get("/capabilities")(lambda: {"reader": True})
    app.add_middleware(ReleaseAdmissionMiddleware, router=app.router, admitted_routes=tuple(app.router.routes), expected_profile="sec_reader")
    client = TestClient(app)
    assert client.get("/capabilities").status_code == 200
    assert client.get(PATH, headers={"X-FinLens-Data-Version": "0"}).status_code == 403


def test_replaced_quarter_route_does_not_inherit_captured_admission():
    app = FastAPI()
    app.get(TEMPLATE)(lambda ticker: {"original": ticker})
    original = next(route for route in app.router.routes if getattr(route, "path", None) == TEMPLATE)
    app.add_middleware(ReleaseAdmissionMiddleware, router=app.router, admitted_routes=(original,))
    app.router.routes.remove(original)
    app.get(TEMPLATE)(forbidden)
    assert TestClient(app).get(PATH).status_code == 403
