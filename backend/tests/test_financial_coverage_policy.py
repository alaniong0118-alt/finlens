"""Exact coverage admission; guarded in-process HTTP, never a live database."""
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, main, freshness_service
from app.release_policy import READONLY_ROUTES, READER_ROUTES, ReleaseAdmissionMiddleware
from test_financial_insights import COMPANY, Rows, row_stats, session_for
from test_quarter_window_comparison import source


PATH = "/companies/TEST/financials/coverage"
TEMPLATE = "/companies/{ticker}/financials/coverage"


def forbidden(*args, **kwargs):
    raise AssertionError("A denied request must execute no handler or session")


@pytest.fixture(autouse=True)
def readonly(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    monkeypatch.setattr(main, "InsightsSessionLocal", forbidden)
    monkeypatch.setattr(main, "HttpSessionLocal", forbidden)


def test_exact_coverage_get_policy_does_not_admit_other_methods_or_reader():
    assert ("GET", TEMPLATE) in READONLY_ROUTES
    assert not any((method, TEMPLATE) in READONLY_ROUTES for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"))
    assert ("GET", TEMPLATE) not in READER_ROUTES
    assert READER_ROUTES == frozenset({("GET", "/healthz"), ("GET", "/capabilities")})


@pytest.mark.parametrize("pin", [0, 7])
def test_sec_readonly_real_route_keeps_zero_pin_engine_and_readonly_transaction(monkeypatch, pin):
    rows = [source(date(2025, 1, 1), 90)]
    session, _ = session_for(rows)
    company = dict(vars(COMPANY), data_version=pin, facts_version=pin, evidence_version=pin)
    session.execute.side_effect = [Mock(), Rows([company]),
        Rows([{"count": 1, "bytes": row_stats(rows[0]), "invalid": 0}]), Rows([vars(rows[0])])]
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = pin
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda: session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    response = TestClient(main.app).get(PATH + "?period=quarter&end_from=2025-03-31&end_to=2025-03-31", headers={"X-FinLens-Data-Version": str(pin)})
    assert response.status_code == 200
    assert response.headers["X-FinLens-Data-Version"] == str(pin) and response.headers["Cache-Control"] == "no-store"
    assert response.json()["data_version"] == pin and response.json()["cell_count"] == 11
    assert response.json()["end_date_range"] == {"from_date": "2025-03-31", "to_date": "2025-03-31"}
    assert "READ ONLY" in str(session.execute.call_args_list[0].args[0])
    assert session.close.called


@pytest.mark.parametrize("method,path", [(method, PATH) for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")]
    + [("GET", PATH + "/"), ("GET", PATH + "/detail"), ("GET", PATH + "-export"),
       ("POST", PATH + "/acquire"), ("POST", "/companies/TEST/refresh")])
def test_coverage_admission_never_becomes_prefix_write_or_acquisition_permission(method, path):
    response = TestClient(main.app).request(method, path, content=b"malformed JSON",
        headers={"X-FinLens-Server-Profile": "development"})
    assert response.status_code == 403 and response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"


@pytest.mark.parametrize("query,headers", [("period=quarter", {}),
    ("period=instant", {"X-FinLens-Data-Version": "0"}),
    ("period=annual&period=annual", {"X-FinLens-Data-Version": "0"})])
def test_sec_readonly_coverage_still_requires_exact_period_and_pin_before_session(query, headers):
    assert TestClient(main.app).get(PATH + "?" + query, headers=headers).status_code == 422


def test_sec_readonly_coverage_still_denies_active_registry_before_session(monkeypatch):
    from app import revenue_scope_authorizations as auth
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (object(),))
    response = TestClient(main.app).get(PATH + "?period=annual", headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 503
    assert response.headers["X-FinLens-Error-Code"] == "INSIGHTS_CONFIGURATION_UNSUPPORTED"


def test_sec_reader_still_denies_coverage_even_if_the_route_object_was_captured(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_reader"))
    app = FastAPI()
    app.get(TEMPLATE)(forbidden)
    app.get("/capabilities")(lambda: {"reader": True})
    captured = tuple(app.router.routes)
    app.add_middleware(ReleaseAdmissionMiddleware, router=app.router, admitted_routes=captured, expected_profile="sec_reader")
    client = TestClient(app)
    assert client.get("/capabilities").status_code == 200
    response = client.get(PATH + "?period=quarter", headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 403 and response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"


def test_replacement_coverage_route_cannot_inherit_captured_admission():
    app = FastAPI()
    app.get(TEMPLATE)(lambda ticker: {"original": ticker})
    original = next(route for route in app.router.routes if getattr(route, "path", None) == TEMPLATE)
    app.add_middleware(ReleaseAdmissionMiddleware, router=app.router, admitted_routes=(original,))
    app.router.routes.remove(original)
    app.get(TEMPLATE)(forbidden)
    assert TestClient(app).get(PATH).status_code == 403
