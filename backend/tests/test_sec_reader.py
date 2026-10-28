"""02A synthetic contracts; run via run_sec_reader_offline.py, never live services."""
import importlib
import inspect
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app import config
from app.release_policy import (
    READONLY_ROUTES, READER_ROUTES, ReleaseAdmissionMiddleware, ReleaseModeBlocked,
    development_only,
)


def bomb(*args, **kwargs):
    raise AssertionError("Forbidden dependency, body, provider or operation executed")


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", "sec_reader")
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_reader"))
    return importlib.import_module("app.sec_reader")


def child(code, profile="sec_reader", *, forbid_dotenv=True):
    # -I -S excludes site startup hooks; install all guards before app imports.
    runner = str(Path(__file__).with_name("run_sec_reader_offline.py").resolve())
    setup = f"import runpy, os\nrunpy.run_path({runner!r}, run_name='offline_probe')\n"
    setup += ("os.environ.pop('FINLENS_SERVER_PROFILE', None)\n" if profile is None else
              f"os.environ['FINLENS_SERVER_PROFILE'] = {profile!r}\n")
    if forbid_dotenv:
        setup += """
import dotenv
def dotenv_sentinel(*args, **kwargs):
    raise AssertionError('reader admission invoked dotenv')
dotenv.load_dotenv = dotenv_sentinel
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", setup + code],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.parametrize("profile", [None, "development", "sec_readonly", "", " ",
                                     "SEC_READER", "sec_reader ", " sec_reader", "unknown"])
def test_reader_requires_explicit_exact_profile_before_initialization(profile):
    child('''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name in {'app.config', 'fastapi', 'app.database', 'app.embedding_service', 'openai'}:
        raise AssertionError('initialization preceded profile rejection')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
try:
    import app.sec_reader
except ValueError as exc:
    assert 'FINLENS_SERVER_PROFILE' in str(exc)
else:
    raise AssertionError('inconsistent profile accepted')
assert 'app.database' not in sys.modules
assert 'app.config' not in sys.modules
''', profile)


@pytest.mark.parametrize("profile", ["", "SEC_READER", "sec_reader ", "unknown"])
@pytest.mark.parametrize("entry", ["app.main", "app.embedding_service", "app.answer_service",
                                  "app.sec_importer"])
def test_invalid_profile_rejects_existing_entrypoints_before_initialization(profile, entry):
    child(f'''
import importlib, sys, sqlalchemy
def forbidden(*args, **kwargs): raise AssertionError('engine initialization')
sqlalchemy.create_engine = forbidden
try:
    importlib.import_module({entry!r})
except ValueError as exc:
    assert 'FINLENS_SERVER_PROFILE' in str(exc)
else:
    raise AssertionError('invalid profile accepted')
assert 'app.database' not in sys.modules
assert 'sentence_transformers' not in sys.modules
''', profile, forbid_dotenv=False)


def test_reader_cannot_use_legacy_entrypoint_or_database_bounds():
    child('''
import sys
from app.config import server_profile
profile = server_profile()
assert profile.name == 'sec_reader' and not profile.generation_allowed
try: profile.http_database_bounds
except ValueError: pass
else: raise AssertionError('database configuration admitted')
try: import app.main
except ValueError as exc: assert 'app.sec_reader' in str(exc)
else: raise AssertionError('legacy entrypoint admitted')
assert 'app.database' not in sys.modules
assert 'app.evidence_latency' not in sys.modules
''')


def test_reader_import_and_requests_are_independent_of_data_and_provider_stack():
    child('''
import builtins, sys
original = builtins.__import__
blocked = {'app.database', 'app.models', 'app.embedding_service', 'app.answer_service',
           'app.sec_client', 'app.sec_importer', 'app.refresh_service',
           'app.revenue_scope_authorizations', 'app.activation_lifecycle',
           'app.financial_insights_service', 'sqlalchemy', 'psycopg', 'openai',
           'sentence_transformers', 'huggingface_hub', 'torch'}
def guarded(name, *args, **kwargs):
    if any(name == item or name.startswith(item + '.') for item in blocked):
        raise AssertionError('forbidden reader import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
os.environ.pop('DATABASE_URL', None)
os.environ['OPENAI_API_KEY'] = 'synthetic-private-key'
from app import sec_reader
from fastapi.testclient import TestClient
client = TestClient(sec_reader.app)
assert client.get('/healthz').json() == {'status': 'ok', 'service': 'finlens-sec-reader'}
response = client.get('/capabilities')
assert response.json() == {'research_mode': False, 'ai_analysis_configured': False,
                          'ai_analysis_enabled': False, 'server_profile': 'sec_reader'}
assert 'synthetic-private-key' not in response.text
assert client.get('/dbz').status_code == 403
assert not any(name in sys.modules for name in blocked if name.startswith('app.'))
''')


def test_profile_is_frozen_and_environment_changes_cannot_enable_reader():
    child('''
from dataclasses import FrozenInstanceError
from app.config import server_profile
from app import sec_reader
from fastapi.testclient import TestClient
profile = server_profile()
os.environ['FINLENS_SERVER_PROFILE'] = 'development'
os.environ['OPENAI_API_KEY'] = 'synthetic-key'
try: profile.name = 'development'
except FrozenInstanceError: pass
else: raise AssertionError('mutable profile')
assert server_profile() is profile
client = TestClient(sec_reader.app)
assert client.get('/capabilities').json()['research_mode'] is False
assert client.get('/companies').status_code == 403
''')


@pytest.mark.parametrize("profile,expected", [(None, "development"), ("development", "development"),
                                             ("sec_readonly", "sec_readonly")])
def test_existing_profile_resolution_unchanged(profile, expected):
    child(f"from app.config import server_profile\nassert server_profile().name == {expected!r}\n",
          profile, forbid_dotenv=False)


@pytest.mark.parametrize("profile", [None, "", "unknown", "development", "sec_readonly"])
def test_dotenv_cannot_inject_reader_or_override_entrypoint_admission(profile):
    child('''
import dotenv, sys
calls = []
def inject_reader(*args, **kwargs):
    calls.append('dotenv')
    os.environ['FINLENS_SERVER_PROFILE'] = 'sec_reader'
dotenv.load_dotenv = inject_reader
try:
    import app.sec_reader
except ValueError as exc:
    assert 'FINLENS_SERVER_PROFILE' in str(exc)
else:
    raise AssertionError('dotenv injected the reader profile')
assert calls == []
assert 'app.config' not in sys.modules
''', profile)


@pytest.mark.parametrize("entry", ["app.sec_reader", "app.config"])
@pytest.mark.parametrize("later_profile", ["sec_reader", "development", "sec_readonly", None])
def test_explicit_reader_never_loads_dotenv_and_rejects_subsequent_loads(entry, later_profile):
    child(f'''
import importlib, dotenv
calls = []
def conflicting_dotenv(*args, **kwargs):
    calls.append('dotenv')
    os.environ['FINLENS_SERVER_PROFILE'] = 'development'
    raise AssertionError('reader reached conflicting dotenv')
dotenv.load_dotenv = conflicting_dotenv
importlib.import_module({entry!r})
from app import config
assert config.server_profile().name == 'sec_reader'
later = {later_profile!r}
if later is None: os.environ.pop('FINLENS_SERVER_PROFILE', None)
else: os.environ['FINLENS_SERVER_PROFILE'] = later
for args in ((), (config.BACKEND_ROOT / 'synthetic.env',)):
    try: config.load_backend_env(*args)
    except ValueError as exc: assert 'sec_reader' in str(exc)
    else: raise AssertionError('subsequent dotenv loading silently admitted')
assert calls == []
assert config.server_profile().name == 'sec_reader'
''')


@pytest.mark.parametrize("process,dotenv_value,expected", [
    (None, "development", "development"), (None, "sec_readonly", "sec_readonly"),
    ("development", "sec_readonly", "development"),
    ("sec_readonly", "development", "sec_readonly"),
    ("development", "sec_reader", "development"),
    ("sec_readonly", "sec_reader", "sec_readonly"),
])
def test_legacy_dotenv_loading_and_process_precedence_are_preserved(process, dotenv_value, expected):
    child(f'''
import dotenv
from pathlib import Path
calls = []
def legacy_loader(path, *, override):
    assert override is False
    calls.append((path, override))
    os.environ.setdefault('FINLENS_SERVER_PROFILE', {dotenv_value!r})
dotenv.load_dotenv = legacy_loader
from app import config
assert config.server_profile().name == {expected!r}
assert calls == [(config.BACKEND_ROOT / '.env', False)]
config.load_backend_env(Path('synthetic.env'))
assert calls[-1] == (Path('synthetic.env'), False) and len(calls) == 2
assert config.server_profile().name == {expected!r}
''', process)


@pytest.mark.parametrize("process", [None, "development", "sec_readonly"])
def test_shared_config_rejects_reader_profile_injected_by_dotenv(process):
    child('''
import dotenv
def inject_reader(*args, **kwargs):
    os.environ['FINLENS_SERVER_PROFILE'] = 'sec_reader'
dotenv.load_dotenv = inject_reader
try:
    import app.config
except ValueError as exc:
    assert 'FINLENS_SERVER_PROFILE' in str(exc)
else:
    raise AssertionError('shared config accepted dotenv-only reader profile')
''', process)


def test_process_reader_blocks_shared_loader_after_legacy_config_was_initialized():
    child('''
from app import config
import dotenv
def forbidden(*args, **kwargs): raise AssertionError('late reader dotenv call')
dotenv.load_dotenv = forbidden
os.environ['FINLENS_SERVER_PROFILE'] = 'sec_reader'
try: config.load_backend_env()
except ValueError: pass
else: raise AssertionError('late process reader profile admitted dotenv')
assert config.server_profile().name == 'development'
try: import app.sec_reader
except ValueError: pass
else: raise AssertionError('conflicting frozen configuration accepted')
''', 'development', forbid_dotenv=False)


@pytest.mark.parametrize("profile", [None, "", "unknown"])
def test_independent_fresh_process_rejects_before_shared_config_or_dotenv(profile):
    # Independent of the runner and its dotenv substitutions: only stdlib and a
    # synthetic dotenv module. No site hooks, third-party imports or file reads.
    backend = str(Path(__file__).resolve().parents[1])
    code = f'''
import os, sys, types
sys.path.insert(0, {backend!r})
os.environ.pop('FINLENS_SERVER_PROFILE', None)
profile = {profile!r}
if profile is not None: os.environ['FINLENS_SERVER_PROFILE'] = profile
dotenv = types.ModuleType('dotenv')
def forbidden(*args, **kwargs): raise AssertionError('pre-admission dotenv reached')
dotenv.load_dotenv = forbidden
sys.modules['dotenv'] = dotenv
try: import app.sec_reader
except ValueError as exc: assert 'FINLENS_SERVER_PROFILE' in str(exc)
else: raise AssertionError('reader profile accepted')
assert 'app.config' not in sys.modules
assert 'fastapi' not in sys.modules
'''
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr or result.stdout


def concrete(template):
    return (template.replace("{ticker}", "TEST").replace("{metric}", "revenue")
            .replace("{accession_number}", "fixture").replace("{chunk_id}", "1"))


BLOCKED = sorted({(method, concrete(path)) for method, path in READONLY_ROUTES - READER_ROUTES} | {
    ("POST", "/companies/TEST/filings/fixture/answer"),
    ("POST", "/companies/TEST/refresh"), ("POST", "/ingest"), ("POST", "/activate"),
    ("GET", "/docs"), ("GET", "/redoc"), ("GET", "/openapi.json"),
    ("GET", "/unknown"), ("GET", "/capabilities/"), ("GET", "/healthz/"),
    ("GET", "/CAPABILITIES"), ("GET", "/%63apabilities"),
    ("GET", "/api/finlens/capabilities"), ("GET", "/maintenance"),
    *{(method, path) for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT")
      for path in ("/healthz", "/capabilities")},
})


@pytest.mark.parametrize("method,path", BLOCKED)
def test_reader_denies_unapproved_methods_routes_and_spoofed_configuration(reader, method, path):
    response = TestClient(reader.app).request(method, path, content=b"malformed JSON",
        headers={"Content-Type": "application/json", "X-FinLens-Server-Profile": "development",
                 "Authorization": "Bearer synthetic", "Origin": "http://localhost:3000",
                 "Access-Control-Request-Method": "GET"},
        params={"server_profile": "development", "enabled": "true"})
    assert response.status_code == 403
    assert response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"
    assert response.headers["Cache-Control"] == "no-store"


def install_policy(app, expected_profile="sec_reader"):
    # Even erroneously supplied data route objects cannot broaden reader policy.
    app.add_middleware(ReleaseAdmissionMiddleware, router=app.router,
                       admitted_routes=tuple(app.router.routes), expected_profile=expected_profile)


def test_policy_rejects_before_body_dependencies_and_injected_data_handler(reader):
    app = FastAPI()
    calls = []
    def dependency():
        calls.append("dependency")
        bomb()
    def handler(_=Depends(dependency)):
        calls.append("handler")
        bomb()
    app.post("/companies/{ticker}/research-answer")(handler)
    app.get("/companies")(handler)
    install_policy(app)
    client = TestClient(app)
    for method, path in [("POST", "/companies/TEST/research-answer"), ("GET", "/companies")]:
        assert client.request(method, path, content=b"malformed").status_code == 403
    assert calls == []


def test_reader_route_inventory_and_capabilities_fail_closed(reader, monkeypatch):
    assert {(method, route.path) for route in reader.app.routes for method in route.methods} == READER_ROUTES
    for key in (None, "", "synthetic-private-key"):
        if key is None:
            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        else:
            monkeypatch.setenv("OPENAI_API_KEY", key)
        response = TestClient(reader.app).get("/capabilities")
        assert response.json() == {"research_mode": False, "ai_analysis_configured": False,
                                   "ai_analysis_enabled": False, "server_profile": "sec_reader"}
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("replacement", [False, True])
def test_route_alias_or_equal_replacement_cannot_inherit_admission(reader, replacement):
    app = FastAPI()
    def original():
        return {"original": True}
    app.get("/capabilities")(original)
    install_policy(app)
    if replacement:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/capabilities"]
    app.get("/capabilities" if replacement else "/alias")(original)
    assert TestClient(app).get("/capabilities" if replacement else "/alias").status_code == 403


@pytest.mark.parametrize("profile", ["development", "sec_readonly", "unknown", ""])
def test_reader_profile_inconsistency_cannot_inherit_other_policy(reader, monkeypatch, profile):
    monkeypatch.setattr(config, "_SERVER_PROFILE", SimpleNamespace(name=profile))
    assert TestClient(reader.app).get("/capabilities").status_code == 403
    assert TestClient(reader.app).get("/companies").status_code == 403


def test_unknown_profile_cannot_fall_through_to_readonly_routes(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", SimpleNamespace(name="unknown"))
    app = FastAPI()
    app.get("/companies")(bomb)
    install_policy(app, expected_profile=None)
    assert TestClient(app).get("/companies").status_code == 403


def test_reader_cannot_reuse_legacy_app_diagnostics(reader):
    from app import main
    client = TestClient(main.app)
    assert client.get("/healthz").status_code == 403
    assert client.get("/capabilities").status_code == 403


def test_reader_denies_websocket_before_handler(reader):
    from starlette.websockets import WebSocketDisconnect
    app = FastAPI()
    app.websocket("/capabilities")(bomb)
    install_policy(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/capabilities"):
            bomb()
    assert exc.value.code == 1008


@pytest.mark.parametrize("entry", ["embed_texts", "_get_model", "_load_model"])
def test_encoder_entries_reject_before_arguments_cache_lookup_or_import(reader, monkeypatch, entry):
    from app import embedding_service as embedding
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=bomb))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(try_to_load_from_cache=bomb))
    embedding._get_model.cache_clear()
    try:
        with pytest.raises(ReleaseModeBlocked):
            getattr(embedding, entry)(*([[]] if entry == "embed_texts" else []))
    finally:
        embedding._get_model.cache_clear()


def test_warm_encoder_and_provider_caches_do_not_bypass_reader(reader, monkeypatch):
    from app import embedding_service as embedding, answer_service
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    model = SimpleNamespace(encode=bomb)
    constructor = Mock(return_value=model)
    monkeypatch.setattr(embedding, "_load_model", constructor)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    provider = Mock(return_value=object())
    monkeypatch.setattr(answer_service, "OpenAI", provider)
    embedding._get_model.cache_clear()
    answer_service._get_openai_client.cache_clear()
    try:
        assert embedding._get_model() is model
        answer_service._get_openai_client()
        monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_reader"))
        for call in (embedding._get_model, lambda: embedding.embed_texts(["query"]),
                     answer_service._get_openai_client,
                     lambda: answer_service.answer_filing_question("", "", [], client=bomb)):
            with pytest.raises(ReleaseModeBlocked):
                call()
        constructor.assert_called_once_with()
        provider.assert_called_once()
    finally:
        embedding._get_model.cache_clear()
        answer_service._get_openai_client.cache_clear()


# Reuse the maintained operational inventory: the new profile must guard every
# existing acquisition/maintenance/activation entry, including injected callbacks.
from test_release_profile import OPERATIONS, BombObject


@pytest.mark.parametrize("module,name", [(m, n) for m, names in OPERATIONS.items() for n in names])
def test_reader_blocks_all_existing_operational_entries(reader, module, name):
    function = getattr(importlib.import_module(module), name)
    signature = inspect.signature(function)
    args = [BombObject() for p in signature.parameters.values() if p.kind in
            (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty]
    kwargs = {p.name: BombObject() for p in signature.parameters.values()
              if p.kind is p.KEYWORD_ONLY and p.default is p.empty}
    with pytest.raises(ReleaseModeBlocked):
        function(*args, **kwargs)


@pytest.mark.parametrize("dry_run", [False, True])
def test_dry_run_and_injected_sources_cannot_bypass_release_policy(reader, dry_run):
    from app.refresh_service import refresh
    from app.refresh_contracts import RefreshRequest
    from app.sec_importer import merge_company_facts
    for call in (
        lambda: refresh(bomb, RefreshRequest(tickers=["AAPL"], dry_run=dry_run),
                        facts_loader=bomb, inventory_loader=bomb, raw_loader=bomb,
                        encoder=bomb, on_progress=bomb),
        lambda: merge_company_facts(BombObject(), "0000320193", BombObject(),
                                   dry_run=dry_run, publish=False),
        development_only(bomb),
    ):
        with pytest.raises(ReleaseModeBlocked):
            call()


def test_financial_authorizations_remain_inactive(reader):
    from app import revenue_scope_authorizations as auth, aapl_net_margin_activation as activation
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == ()
    assert auth.DENOMINATOR_AUTHORIZATIONS == ()
    assert activation._ACTIVATION_ENABLED is False
    with pytest.raises(ReleaseModeBlocked):
        activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=BombObject())
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == ()
    assert auth.DENOMINATOR_AUTHORIZATIONS == ()
