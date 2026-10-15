"""DEP-01A1 offline acceptance. Run with DATABASE_URL=sqlite:// and dotenv disabled.

No real database, server startup, source/provider requests or model downloads.
"""
import asyncio
import importlib
import inspect
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, main
from app.release_policy import (
    READONLY_ROUTES, ReleaseAdmissionMiddleware, ReleaseModeBlocked, development_only,
)


def bomb(*args, **kwargs):
    raise AssertionError("Forbidden external network, database, provider or callback")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    if not getattr(socket.socket.connect, "_finlens_offline_guard", False):
        original_connect = socket.socket.connect
        socketpair_code = getattr(getattr(socket, "_fallback_socketpair", None), "__code__", None)

        def guarded_connect(self, address):
            if (socketpair_code is not None and sys._getframe(1).f_code is socketpair_code
                    and isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}):
                return original_connect(self, address)
            bomb()

        monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", bomb)
    monkeypatch.setattr(socket, "create_connection", bomb)
    monkeypatch.setattr("app.database.engine.connect", bomb)
    monkeypatch.setattr(main, "HttpSessionLocal", bomb)
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))


def child(code, profile=None):
    env = dict(os.environ, DATABASE_URL="sqlite://", PYTHON_DOTENV_DISABLED="1")
    env.pop("FINLENS_SERVER_PROFILE", None)
    if profile is not None:
        env["FINLENS_SERVER_PROFILE"] = profile
    return subprocess.run([sys.executable, "-B", "-c", code], env=env,
                          capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("value", ["", " ", "SEC_READONLY", "readonly", "sec_readonly ", "unknown"])
@pytest.mark.parametrize("entry", ["app.main", "app.sec_importer", "app.embedding_service", "app.answer_service", "seed_companies"])
def test_invalid_profile_rejects_before_initialization(value, entry):
    result = child(f'''
import socket, sqlalchemy, importlib, sys
def bomb(*a, **k): raise AssertionError("initialization executed")
socket.socket.connect = bomb
sqlalchemy.create_engine = bomb
try:
    importlib.import_module({entry!r})
except ValueError as exc:
    assert "FINLENS_SERVER_PROFILE" in str(exc)
    assert "app.database" not in sys.modules
    assert "sentence_transformers" not in sys.modules
    assert "openai" not in sys.modules
else:
    raise AssertionError("invalid profile accepted")
''', value)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value,expected", [(None, "development"), ("development", "development"), ("sec_readonly", "sec_readonly")])
def test_profile_is_resolved_once_and_frozen(value, expected):
    result = child(f'''
import os
from dataclasses import FrozenInstanceError
from app.config import server_profile
profile = server_profile()
assert profile.name == {expected!r}
os.environ["FINLENS_SERVER_PROFILE"] = "unknown"
assert server_profile() is profile
try: profile.name = "development"
except FrozenInstanceError: pass
else: raise AssertionError("mutable profile")
''', value)
    assert result.returncode == 0, result.stderr


def test_profile_resolves_after_dotenv_and_does_not_revalidate_on_reload():
    result = child('''
import os, dotenv
def load(*a, **k): os.environ.setdefault("FINLENS_SERVER_PROFILE", "sec_readonly")
dotenv.load_dotenv = load
from app.config import server_profile, load_backend_env
assert server_profile().name == "sec_readonly"
os.environ["FINLENS_SERVER_PROFILE"] = "development"
load_backend_env()
assert server_profile().name == "sec_readonly"
''')
    assert result.returncode == 0, result.stderr


BLOCKED = [
    ("POST", "/companies/AAPL/filings/0000320193-25-000079/answer"),
    ("GET", "/companies/AAPL/filings/0000320193-25-000079/answer"),
    ("POST", "/companies/AAPL/refresh"), ("GET", "/unknown"),
    ("GET", "/companies/"), ("GET", "/docs"), ("GET", "/openapi.json"),
    ("HEAD", "/companies"), ("DELETE", "/companies"), ("PATCH", "/companies"),
    ("PUT", "/capabilities"), ("POST", "/capabilities"),
    ("GET", "/companies/AAPL/research-answer"), ("OPTIONS", "/companies"),
]


@pytest.mark.parametrize("method,path", BLOCKED)
def test_real_backend_denies_before_sessions_and_body_parsing(monkeypatch, method, path):
    monkeypatch.setattr(main, "read_session", bomb)
    monkeypatch.setattr(main, "answer_filing_question", bomb)
    response = TestClient(main.app).request(method, path, content=b"malformed JSON",
        headers={"Content-Type": "application/json", "Origin": "http://localhost:3000",
                 "Access-Control-Request-Method": "GET", "X-FinLens-Server-Profile": "development"})
    assert response.status_code == 403
    assert response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"
    assert response.headers["Cache-Control"] == "no-store"


def install_policy(app):
    app.add_middleware(ReleaseAdmissionMiddleware, router=app.router,
        admitted_routes=tuple(r for r in app.router.routes if any(
            (m, getattr(r, "path", None)) in READONLY_ROUTES for m in getattr(r, "methods", ()))))


def test_forbidden_routes_execute_zero_fastapi_dependencies():
    app = FastAPI()
    calls = []

    def dependency():
        calls.append("dependency")
        bomb()

    def handler(_=Depends(dependency)):
        calls.append("handler")
        bomb()

    app.post("/companies/{ticker}/filings/{accession_number}/answer")(handler)
    app.get("/new-read")(handler)
    install_policy(app)
    for path in ["/companies/AAPL/filings/fixture/answer", "/new-read"]:
        assert TestClient(app).request("POST" if "answer" in path else "GET", path).status_code == 403
    assert calls == []


@pytest.mark.parametrize("method,template", sorted(READONLY_ROUTES))
def test_every_reviewed_route_identity_is_admitted(method, template):
    app = FastAPI()
    app.add_api_route(template, lambda: {"synthetic_read": True}, methods=[method])
    install_policy(app)
    path = template.replace("{ticker}", "TEST").replace("{metric}", "revenue").replace("{accession_number}", "fixture")
    response = TestClient(app).request(method, path)
    assert response.status_code == 200 and response.json() == {"synthetic_read": True}


def test_actual_route_inventory_matches_explicit_policy():
    actual = {(m, r.path) for r in main.app.router.routes if hasattr(r, "methods") for m in r.methods}
    assert READONLY_ROUTES <= actual
    assert ("POST", "/companies/{ticker}/filings/{accession_number}/answer") not in READONLY_ROUTES


def test_added_alias_and_replaced_route_cannot_inherit_admission():
    app = FastAPI()
    app.get("/capabilities")(lambda: {"original": True})
    install_policy(app)
    app.get("/alias")(bomb)
    assert TestClient(app).get("/alias").status_code == 403
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/capabilities"]
    app.get("/capabilities")(bomb)
    assert TestClient(app).get("/capabilities").status_code == 403


def test_structurally_equal_replacement_requires_registered_object_identity():
    app = FastAPI()
    def original():
        return {"original": True}
    app.get("/capabilities")(original)
    admitted = next(r for r in app.router.routes if getattr(r, "path", None) == "/capabilities")
    install_policy(app)
    app.router.routes.remove(admitted)
    app.get("/capabilities")(original)
    replacement = next(r for r in app.router.routes if getattr(r, "path", None) == "/capabilities")
    assert replacement is not admitted
    assert TestClient(app).get("/capabilities").status_code == 403


def test_websocket_is_denied_without_handler_execution():
    app = FastAPI()
    app.websocket("/socket")(bomb)
    install_policy(app)
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/socket"):
            bomb()
    assert exc.value.code == 1008


def test_proxy_rewrite_preserves_backend_denial():
    # Match the existing Next catch-all rewrite, with an in-process transport.
    # No Next/server startup; both origin and forwarding paths reach the same app.
    source = (config.BACKEND_ROOT.parent / "frontend/next.config.ts").read_text()
    assert 'source: "/api/finlens/:path*"' in source
    assert 'destination: `${backendUrl}/:path*`' in source

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://synthetic.test") as backend:
            async def forward(request):
                path = request.url.path.removeprefix("/api/finlens")
                return await backend.request(request.method, path, content=request.content, headers=request.headers)
            async with httpx.AsyncClient(transport=httpx.MockTransport(forward), base_url="http://proxy.test") as proxy:
                for client, prefix in [(backend, ""), (proxy, "/api/finlens")]:
                    for method, path in BLOCKED:
                        response = await client.request(method, prefix + path, content=b"{}")
                        assert response.status_code == 403
                        assert response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"
                    response = await client.get(prefix + "/capabilities")
                    assert response.json()["ai_analysis_enabled"] is False
    asyncio.run(exercise())


def test_dummy_key_does_not_enable_ai_or_disclose_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-private-key")
    response = TestClient(main.app).get("/capabilities")
    assert response.json() == {"research_mode": True, "ai_analysis_configured": False,
                               "ai_analysis_enabled": False, "server_profile": "sec_readonly"}
    assert "dummy-private-key" not in response.text


def test_deterministic_research_uses_existing_resolver_and_synthetic_observations(monkeypatch):
    from contextlib import contextmanager
    from datetime import date, datetime, timezone
    from decimal import Decimal
    from app.models import Company, FinancialFact
    company = Company(ticker="TEST", name="Fixture", cik="0000000001")
    fact = FinancialFact(id=1, company_cik=company.cik, metric="Revenues", value=Decimal("100"), unit="USD",
        period_start=date(2025, 1, 1), period_end=date(2025, 3, 31), period_type="quarter", form="10-Q",
        filed=date(2025, 5, 1), accession_number="0000000001-25-000001", source="SEC Company Facts API: Revenues",
        created_at=datetime(2025, 5, 1, tzinfo=timezone.utc))
    session = SimpleNamespace(scalars=lambda statement: [company] if
        statement.column_descriptions[0]["entity"] is Company else [fact])

    @contextmanager
    def synthetic_read(factory):
        yield session

    monkeypatch.setattr(main, "read_session", synthetic_read)
    for question in ["latest quarterly revenue", "latest quarterly gross margin"]:
        response = TestClient(main.app).post("/companies/TEST/research-answer", json={"question": question})
        assert response.status_code == 200
        data = response.json()
        if "revenue" in question:
            assert data["status"] == "available" and data["observation"]["value"] == "100"
            assert data["observation"]["provenance"][0]["fact_id"] == 1
        else:
            assert data["status"] == "unavailable" and data["observation"]["value"] is None


OPERATIONS = {
    "app.sec_client": ["_sec_get"],
    "app.answer_service": ["answer_filing_question", "_get_openai_client"],
    "app.embedding_service": ["embed_filing_chunks", "_embed_filing_chunks"],
    "app.sec_importer": ["merge_company_facts", "import_metric", "import_company", "import_all_companies"],
    "app.sec_filing_service": ["ingest_filing_chunks", "_ingest_filing_chunks"],
    "app.catalog_indexing_service": ["index_company", "index_catalog", "_index_catalog"],
    "app.financial_sync_service": ["sync_catalog", "_sync_catalog"],
    "app.refresh_scope": ["pin_sources"],
    "app.refresh_service": ["pin_sources", "publication_session", "reconcile_publication", "coordinator", "state_row", "record_fact_change",
        "register_complete_filings", "manifest", "bootstrap_publications", "stage_filing", "persist_staged", "refresh", "refresh_stream"],
    "seed_companies": ["seed_companies"],
    "scripts.setup_demo": ["setup_demo", "_setup_demo", "ensure_filing_metadata", "main"],
    "scripts.index_catalog": ["main"], "scripts.refresh_data": ["main"],
    "scripts.sync_financial_facts": ["main", "write_report"],
    "scripts.evaluate_rag": ["main", "evaluate_query"],
    "scripts.verify_collation": ["main", "audit", "command"],
    "scripts.verify_catalog_indexing": ["main_cli", "verify"],
    "scripts.verify_financial_metrics": ["verify"],
    "scripts.verify_financial_sync": ["main", "verify"],
    "scripts.verify_historical_answers": ["run"], "scripts.verify_research_answers": ["run"],
    "app.aapl_net_margin_activation": ["activate_aapl_net_margin"],
    "app.aapl_net_margin_launcher": ["launch", "main", "_load_application", "_run_server"],
}


class BombObject:
    def __getattr__(self, name):
        bomb()

    def __call__(self, *args, **kwargs):
        bomb()


@pytest.mark.parametrize("module,name", [(m, n) for m, names in OPERATIONS.items() for n in names])
def test_direct_operational_entry_rejects_before_arguments_or_side_effects(module, name):
    function = getattr(importlib.import_module(module), name)
    signature = inspect.signature(function)
    args = [BombObject() for p in signature.parameters.values() if p.kind in
            (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty]
    kwargs = {p.name: BombObject() for p in signature.parameters.values() if p.kind is p.KEYWORD_ONLY and p.default is p.empty}
    with pytest.raises(ReleaseModeBlocked, match="SEC-only"):
        function(*args, **kwargs)


@pytest.mark.parametrize("dry_run", [False, True])
def test_injected_callbacks_sources_and_dry_runs_cannot_bypass(monkeypatch, dry_run):
    from app.refresh_service import refresh
    from app.refresh_contracts import RefreshRequest
    from app.answer_service import answer_filing_question
    from app.catalog_indexing_service import index_catalog
    from app.sec_importer import merge_company_facts
    for call in [
        lambda: refresh(bomb, RefreshRequest(tickers=["AAPL"], dry_run=dry_run), facts_loader=bomb,
                        inventory_loader=bomb, raw_loader=bomb, encoder=bomb, on_progress=bomb),
        lambda: answer_filing_question("revenue", "", [], client=BombObject()),
        lambda: index_catalog(BombObject(), ["AAPL"], dry_run=dry_run, on_result=bomb),
        lambda: merge_company_facts(BombObject(), "0000320193", BombObject(), dry_run=dry_run, publish=False),
    ]:
        with pytest.raises(ReleaseModeBlocked):
            call()


@pytest.mark.parametrize("argv", [[], ["--all", "--allow-network"], ["--all", "--bootstrap"],
                                  ["--ticker", "AAPL", "--dry-run", "--allow-network"]])
def test_operator_flags_cannot_bypass(argv):
    from scripts.refresh_data import main as refresh_main
    with pytest.raises(ReleaseModeBlocked):
        refresh_main(argv)


def test_disabled_activation_stays_disabled_and_registry_is_unchanged():
    from app import aapl_net_margin_activation as activation, revenue_scope_authorizations as authorization
    before = authorization.DENOMINATOR_AUTHORIZATIONS
    assert activation._ACTIVATION_ENABLED is False
    with pytest.raises(ReleaseModeBlocked):
        activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=BombObject())
    assert authorization.DENOMINATOR_AUTHORIZATIONS is before


def test_release_guards_precede_refresh_admission_and_launcher_claim(monkeypatch):
    from app.refresh_service import RefreshAdmission
    from app.aapl_net_margin_launcher import launch
    from app import activation_lifecycle
    monkeypatch.setattr(activation_lifecycle, "_claim_launch", bomb)
    with pytest.raises(ReleaseModeBlocked):
        RefreshAdmission(BombObject())()
    with pytest.raises(ReleaseModeBlocked):
        launch(BombObject())


@pytest.mark.parametrize("cached", [None, object(), "missing-model/modules.json"])
def test_missing_encoder_cache_never_constructs_or_downloads(monkeypatch, cached):
    from app import embedding_service as embedding
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a: cached)
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=bomb))
    embedding._get_model.cache_clear()
    with pytest.raises(RuntimeError, match="local cache"):
        embedding.embed_texts(["query"])
    embedding._get_model.cache_clear()


@pytest.mark.parametrize("incomplete", [False, True])
def test_cached_encoder_is_local_only_and_incomplete_cache_fails_safely(monkeypatch, tmp_path, incomplete):
    from app import embedding_service as embedding
    import huggingface_hub
    cached = tmp_path / "modules.json"
    cached.write_text("[]")
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a: str(cached))
    calls = []

    def constructor(path, **kwargs):
        calls.append((path, kwargs))
        if incomplete:
            raise OSError("synthetic missing weights")
        return SimpleNamespace(get_sentence_embedding_dimension=lambda: 384,
            encode=lambda texts, **kw: SimpleNamespace(tolist=lambda: [[1.0] * 384 for _ in texts]))

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=constructor))
    embedding._get_model.cache_clear()
    try:
        if incomplete:
            with pytest.raises(RuntimeError, match="local cache"):
                embedding.embed_texts(["query"])
        else:
            assert len(embedding.embed_texts(["query"])[0]) == 384
        assert calls == [(str(tmp_path), {"local_files_only": True})]
    finally:
        embedding._get_model.cache_clear()


def test_development_preserves_routes_generation_encoder_and_disabled_activation(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    app = FastAPI()
    app.get("/unreviewed")(lambda: {"development": True})
    install_policy(app)
    assert TestClient(app).get("/unreviewed").status_code == 200
    assert TestClient(app).get("/missing").status_code == 404
    assert development_only(lambda: "workflow")() == "workflow"
    from app.answer_service import answer_filing_question
    assert answer_filing_question("revenue", "", [], client=BombObject())["insufficient_evidence"] is True
    from app.aapl_net_margin_activation import activate_aapl_net_margin
    assert activate_aapl_net_margin() is False
    from app import embedding_service as embedding
    calls = []
    def constructor(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(get_sentence_embedding_dimension=lambda: 384)
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=constructor))
    embedding._get_model.cache_clear()
    try:
        embedding._get_model()
        assert calls == [((embedding.MODEL_NAME,), {})]
    finally:
        embedding._get_model.cache_clear()


def test_development_sec_acquisition_keeps_fake_transport_compatible(monkeypatch):
    from contextlib import contextmanager
    from app import sec_client
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    calls = []
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        @contextmanager
        def stream(self, method, url):
            calls.append((method, url))
            yield httpx.Response(200, content=b'{"synthetic":true}', request=httpx.Request(method, url))

    monkeypatch.setattr(sec_client.httpx, "Client", FakeClient)
    monkeypatch.setattr(sec_client, "get_sec_headers", lambda: {})
    monkeypatch.setattr(sec_client.time, "sleep", lambda *a: None)
    url = "https://data.sec.gov/submissions/CIK0000000001.json"
    assert sec_client._sec_get(url).json() == {"synthetic": True}
    assert calls == [("GET", url)]


def test_cached_provider_api_is_preserved_and_release_guard_precedes_cache_hits(monkeypatch):
    from app import answer_service
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    calls, provider = [], object()
    def constructor(**kwargs):
        calls.append("constructed")
        return provider
    monkeypatch.setattr(answer_service, "OpenAI", constructor)
    answer_service._get_openai_client.cache_clear()
    try:
        assert answer_service._get_openai_client() is provider
        assert answer_service._get_openai_client() is provider
        assert answer_service._get_openai_client.cache_info().hits == 1
        monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
        with pytest.raises(ReleaseModeBlocked):
            answer_service._get_openai_client()
        assert calls == ["constructed"]
    finally:
        answer_service._get_openai_client.cache_clear()


def test_development_generation_with_injected_provider_keeps_claim_contract(monkeypatch):
    from app.answer_service import answer_filing_question
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    monkeypatch.setenv("OPENAI_MODEL", "synthetic-model")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "medium")
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status="completed", output_parsed={
            "claims": [{"text": "Synthetic fixture revenue was reported.", "citation_ids": ["source_1"]}],
            "insufficient_evidence": False})
    citation = {"citation_id": "source_1", "semantic_similarity": 1.0, "lexical_score": 1.0,
                "sec_url": "https://www.sec.gov/Archives/fixture"}
    result = answer_filing_question("reported revenue", "[SOURCE source_1]\nSynthetic fixture revenue was reported.\n[END SOURCE source_1]",
        [citation], client=SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    assert len(calls) == 1 and calls[0]["store"] is False
    assert result["evidence_status"] == "sufficient" and result["citations"] == [citation]
    assert result["claims"][0]["citation_ids"] == ["source_1"]


def test_development_writer_guards_keep_injected_sessions_compatible(monkeypatch):
    from contextlib import nullcontext
    from app import sec_importer
    from seed_companies import seed_companies
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    calls = []
    session = SimpleNamespace(begin=lambda: nullcontext(), scalars=lambda *a: SimpleNamespace(all=lambda: []),
        add=lambda row: calls.append("add"), commit=lambda: calls.append("commit"))
    monkeypatch.setattr(sec_importer, "SessionLocal", lambda: nullcontext(session))
    def merge(s, cik, facts, **kwargs):
        assert s is session and cik == "0000000001" and kwargs == {"metrics": ["Revenues"]}
        calls.append("merge")
        return {"facts_inserted": 1}
    monkeypatch.setattr(sec_importer, "merge_company_facts", merge)
    assert sec_importer.import_metric("0000000001", {}, "Revenues") == 1
    seed_companies(session, quiet=True)
    assert calls[0] == "merge" and calls[-1] == "commit" and "add" in calls


def test_development_launcher_validates_profile_before_infrastructure():
    source = (config.BACKEND_ROOT.parent / "Start-FinLens.ps1").read_text()
    assert source.index("from app.release_policy import require_development") < source.index("Get-Command docker")


@pytest.mark.parametrize("module", ["app.refresh_scope", "app.refresh_service"])
@pytest.mark.parametrize("sentinel", ["factory", "scalar", "loaders"])
def test_pin_sources_release_guard_precedes_factory_scalar_and_loaders(module, sentinel):
    from contextlib import nullcontext
    from unittest.mock import Mock
    from app.refresh_scope import CIK, NAME

    scalar = Mock(side_effect=bomb if sentinel == "scalar" else [SimpleNamespace(name=NAME), None])
    factory = Mock(side_effect=bomb) if sentinel == "factory" else Mock(
        return_value=nullcontext(SimpleNamespace(scalar=scalar)))
    loaders = [Mock(side_effect=bomb) for _ in range(4)]
    function = getattr(importlib.import_module(module), "pin_sources")
    with pytest.raises(ReleaseModeBlocked) as exc:
        function(factory, {"AAPL": CIK}, *loaders)
    assert exc.value.code == "RELEASE_MODE_BLOCKED"
    for callback in [factory, scalar, *loaders]:
        callback.assert_not_called()


@pytest.mark.parametrize("module", ["app.refresh_scope", "app.refresh_service"])
def test_pin_sources_development_preserves_pinned_return_and_injected_workflow(monkeypatch, module):
    from contextlib import nullcontext
    from unittest.mock import Mock
    from app import refresh_scope

    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    payload = {"entityName": refresh_scope.NAME, "synthetic": {"values": [1]}}
    inventory = {"complete": True, "filings": [refresh_scope.TARGET, refresh_scope.EXISTING]}
    candidates = [{"synthetic_observation": True}]
    scalar = Mock(side_effect=[SimpleNamespace(name=refresh_scope.NAME), None])
    session = SimpleNamespace(scalar=scalar)
    factory = Mock(side_effect=lambda: nullcontext(session))
    facts_loader = Mock(return_value=payload)
    inventory_loader = Mock(return_value=inventory)
    observations = Mock(return_value=candidates)
    reject_conflicts = Mock()
    merge = Mock(return_value={"would_insert": 0})
    validate_inventory = Mock()
    monkeypatch.setattr(refresh_scope, "merge_company_facts", merge)
    monkeypatch.setattr(refresh_scope, "validate_inventory", validate_inventory)

    result = getattr(importlib.import_module(module), "pin_sources")(
        factory=factory, catalog={"AAPL": refresh_scope.CIK}, facts_loader=facts_loader,
        inventory_loader=inventory_loader, observations=observations, reject_conflicts=reject_conflicts)

    assert type(result) is refresh_scope.PinnedCanarySources
    assert result.facts() == payload and result.filings() == inventory
    assert result.evidence()["status"] == "validated"
    assert result.evidence()["facts_would_insert"] == 0
    assert result.facts_sha256 == refresh_scope.digest(payload)
    assert factory.call_count == 2 and scalar.call_count == 2
    facts_loader.assert_called_once_with(refresh_scope.CIK)
    inventory_loader.assert_called_once_with(refresh_scope.CIK)
    observations.assert_called_once_with(refresh_scope.CIK, payload)
    reject_conflicts.assert_called_once_with(session, refresh_scope.CIK, candidates)
    merge.assert_called_once_with(session, refresh_scope.CIK, payload, dry_run=True)
    validate_inventory.assert_called_once_with(session, tuple(inventory["filings"]))
    payload["synthetic"]["values"].append(2)
    inventory["filings"].clear()
    assert result.facts()["synthetic"]["values"] == [1]
    assert result.filings()["filings"] == [refresh_scope.TARGET, refresh_scope.EXISTING]


@pytest.mark.parametrize("module", ["app.refresh_scope", "app.refresh_service"])
def test_pin_sources_development_preserves_catalog_rejection_before_factory(monkeypatch, module):
    from unittest.mock import Mock
    from app.refresh_scope import SourceScopeError

    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    callbacks = [Mock(side_effect=bomb) for _ in range(5)]
    with pytest.raises(SourceScopeError, match="^canary_catalog_cik_mismatch$"):
        getattr(importlib.import_module(module), "pin_sources")(callbacks[0], {}, *callbacks[1:])
    for callback in callbacks:
        callback.assert_not_called()


def test_pin_sources_import_paths_share_the_preserved_signature():
    from app import refresh_scope, refresh_service

    assert refresh_service.pin_sources is refresh_scope.pin_sources
    assert str(inspect.signature(refresh_scope.pin_sources)) == (
        "(factory, catalog, facts_loader, inventory_loader, observations, reject_conflicts)")
