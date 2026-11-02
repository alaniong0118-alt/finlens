"""Dormant restriction: run with the guarded offline runner; no real DB/model."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import runpy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, main, embedding_service
from app.release_policy import (FINANCIAL_ONLY_ROUTES, READONLY_ROUTES,
    READER_ROUTES, ReleaseAdmissionMiddleware, ReleaseModeBlocked)
from test_quarter_window_policy import fake_read, SELECTION
import test_quarter_window_policy as quarter_policy
import test_financial_coverage_policy as coverage_policy


def forbidden(*args, **kwargs):
    raise AssertionError("No physical DB, model loader or denied handler")


@pytest.fixture(autouse=True)
def restricted(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly", True))
    monkeypatch.setattr(main, "HttpSessionLocal", forbidden)
    monkeypatch.setattr(main, "InsightsSessionLocal", forbidden)
    monkeypatch.setattr(embedding_service, "_load_model", forbidden)


def configuration(monkeypatch, flag, profile="sec_readonly", loader=None):
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", profile)
    if flag is None:
        monkeypatch.delenv("FINLENS_FINANCIAL_ONLY", raising=False)
    else:
        monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", flag)
    monkeypatch.setattr("dotenv.load_dotenv", loader or (lambda *a, **k: False))
    return runpy.run_path(str(Path(config.__file__)))


@pytest.mark.parametrize("flag,expected", [(None, False), ("0", False), ("1", True)])
def test_process_setting_is_frozen_and_defaults_off(monkeypatch, flag, expected):
    result = configuration(monkeypatch, flag)
    profile = result["server_profile"]()
    assert profile.financial_only is expected
    monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", "0" if expected else "1")
    assert result["server_profile"]() is profile and profile.financial_only is expected
    with pytest.raises(FrozenInstanceError):
        profile.financial_only = False


@pytest.mark.parametrize("flag", ["", "true", "false", "01", " 1", "1 ", "unknown"])
def test_invalid_setting_rejects_before_dotenv(monkeypatch, flag):
    with pytest.raises(ValueError, match="FINLENS_FINANCIAL_ONLY"):
        configuration(monkeypatch, flag, loader=forbidden)


@pytest.mark.parametrize("profile", ["development", "sec_reader"])
def test_restriction_cannot_be_attached_to_another_profile(monkeypatch, profile):
    with pytest.raises(ValueError, match="requires sec_readonly"):
        configuration(monkeypatch, "1", profile)


def test_dotenv_cannot_select_or_remove_the_restriction(monkeypatch):
    def dotenv(*a, **k):
        monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", "1")
    assert configuration(monkeypatch, None, loader=dotenv)["server_profile"]().financial_only is False
    def unset(*a, **k):
        monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", "0")
    assert configuration(monkeypatch, "1", loader=unset)["server_profile"]().financial_only is True


def test_explicit_subset_and_truthful_uncached_capabilities(monkeypatch):
    assert FINANCIAL_ONLY_ROUTES < READONLY_ROUTES
    assert len(FINANCIAL_ONLY_ROUTES) == 16
    for flag in (False, True):
        monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly", flag))
        reply = TestClient(main.app).get("/capabilities")
        assert reply.status_code == 200 and reply.headers["Cache-Control"] == "no-store"
        assert reply.json() == {"research_mode": True, "server_profile": "sec_readonly",
            "ai_analysis_configured": False, "ai_analysis_enabled": False,
            "filing_research_enabled": not flag}


@pytest.mark.parametrize("method,template", sorted(READONLY_ROUTES - FINANCIAL_ONLY_ROUTES))
def test_every_filing_route_denied_before_session_or_model(method, template):
    path = template.replace("{ticker}", "AAA").replace("{accession_number}", "0000000001-25-000001").replace("{chunk_id}", "1")
    response = TestClient(main.app).request(method, path, params={"q": "revenue"},
        headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 403
    assert response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"


def test_encoder_guard_rejects_before_an_existing_cache_hit(monkeypatch):
    embedding_service._get_model.cache_clear()
    marker = object()
    monkeypatch.setattr(embedding_service, "_load_model", lambda: marker)
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    assert embedding_service._get_model() is marker
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly", True))
    monkeypatch.setattr(embedding_service, "_load_model", forbidden)
    try:
        with pytest.raises(ReleaseModeBlocked):
            embedding_service._get_model()
        with pytest.raises(ReleaseModeBlocked):
            embedding_service.embed_texts(["revenue"])
    finally:
        embedding_service._get_model.cache_clear()


@pytest.mark.parametrize("method,path", [("POST", "/companies/AAA/refresh"),
    ("POST", "/companies/AAA/filings/a/answer"), ("POST", "/uploads"),
    ("PUT", "/companies/AAA/financials/quarters"), ("GET", "/companies/AAA/financials/quarters/near")])
def test_restriction_never_opens_write_or_near_routes(method, path):
    assert TestClient(main.app).request(method, path).status_code == 403


def test_all_financial_pairs_keep_exact_route_identity_and_reader_denial(monkeypatch):
    for method, template in sorted(FINANCIAL_ONLY_ROUTES):
        app = FastAPI()
        async def ok():
            return {"ok": True}
        app.add_api_route(template, ok, methods=[method])
        original = app.router.routes[-1]
        app.add_middleware(ReleaseAdmissionMiddleware, router=app.router, admitted_routes=(original,))
        path = template.replace("{ticker}", "AAA").replace("{metric}", "revenue")
        assert TestClient(app).request(method, path).status_code == 200
        app.router.routes.remove(original)
        app.add_api_route(template, forbidden, methods=[method])
        assert TestClient(app).request(method, path).status_code == 403
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_reader"))
    assert READER_ROUTES == frozenset({("GET", "/healthz"), ("GET", "/capabilities")})
    assert TestClient(main.app).get("/companies/AAA/financials/quarters").status_code == 403


@pytest.mark.parametrize("pin", [0, 7])
@pytest.mark.parametrize("query", ["", SELECTION])
def test_restricted_real_quarter_route_keeps_pins_and_readonly_cleanup(monkeypatch, pin, query):
    session, result = fake_read(monkeypatch, pin)
    reply = TestClient(main.app).get("/companies/TEST/financials/quarters" + query,
        headers={"X-FinLens-Data-Version": str(pin)})
    assert reply.status_code == 200 and reply.headers["X-FinLens-Data-Version"] == str(pin)
    assert "REPEATABLE READ, READ ONLY" in str(session.execute.call_args_list[0].args[0])
    assert result.closed and session.close.called and not session.commit.called


def test_restricted_quarter_stale_pin_closes_without_computation(monkeypatch):
    session, result = fake_read(monkeypatch)
    reply = TestClient(main.app).get("/companies/TEST/financials/quarters",
        headers={"X-FinLens-Data-Version": "7"})
    assert reply.status_code == 409 and result.offset == 0 and session.close.called


def test_restricted_quarter_still_requires_a_pin_before_session():
    assert TestClient(main.app).get("/companies/TEST/financials/quarters").status_code == 422


@pytest.mark.parametrize("pin", [0, 7])
def test_restricted_real_coverage_keeps_pin_and_readonly_transaction(monkeypatch, pin):
    coverage_policy.test_sec_readonly_real_route_keeps_zero_pin_engine_and_readonly_transaction(monkeypatch, pin)


@pytest.mark.parametrize("owner,name", [("revenue_scope_authorizations", "REVENUE_SELECTION_AUTHORIZATIONS"),
    ("revenue_scope_authorizations", "DENOMINATOR_AUTHORIZATIONS"),
    ("revenue_scope_authorizations", "AUTHORIZATION_WITHDRAWALS"),
    ("sec_evidence_adapter", "PRODUCTION_EVIDENCE_POLICIES")])
def test_restricted_quarter_preserves_active_policy_rejection(monkeypatch, owner, name):
    # Reuse the existing real-route assertion under this module's restriction.
    quarter_policy.test_each_active_registry_still_denies_before_session(monkeypatch, owner, name)


@pytest.mark.parametrize("stage", ["serialization", "session_cleanup"])
def test_restricted_quarter_preserves_policy_handoff_recheck(monkeypatch, stage):
    quarter_policy.test_registry_change_cannot_publish_a_partial_response(monkeypatch, stage)


@pytest.mark.parametrize("kind", ["facts", "work", "output", "deadline"])
def test_restricted_quarter_preserves_resource_limits(monkeypatch, kind):
    quarter_policy.test_route_budgets_still_refuse_without_partial_results_and_close_session(monkeypatch, kind)
