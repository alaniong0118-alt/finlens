"""Offline only: guarded runner, fake PostgreSQL and disposable SQLite fixtures."""
import builtins
from copy import deepcopy
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import assess_aapl_facts as assess


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", "development")
    monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", "0")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    for name in tuple(os.environ):
        if name.startswith("PG") or name.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
            monkeypatch.delenv(name)
    def forbidden(*a, **k):
        raise AssertionError("No subprocess/model/network in worker tests")
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    # Never query the actual Windows registry/platform proxy configuration.
    monkeypatch.setattr(assess.urllib_request, "getproxies", lambda: {})
    for module in (builtins, io):
        original = module.open
        def guarded(path, *args, _original=original, **kwargs):
            if isinstance(path, (str, Path)) and Path(path).name.startswith(".env"):
                raise AssertionError("Private dotenv read forbidden")
            return _original(path, *args, **kwargs)
        monkeypatch.setattr(module, "open", guarded)


@pytest.mark.parametrize("args", [[], ["--ticker", "AAPL"], ["--allow-network", "--stream", "both"],
    ["--allow-network", "--all"], ["--allow-network", "--report", "anything.json"]])
def test_default_and_unknown_arguments_reject_before_app_import(monkeypatch, capsys, args):
    original = builtins.__import__
    def guarded(name, *a, **k):
        assert not name.startswith("app"), "Operational import before opt-in"
        return original(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", guarded)
    assert assess.main(args) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "EXPLICIT_NETWORK_CONSENT_REQUIRED"


@pytest.mark.parametrize("profile,flag", [(None, "0"), ("", "0"), ("sec_readonly", "0"),
    ("sec_reader", "0"), ("development", "1"), ("development", "false")])
def test_process_guard_precedes_dotenv(monkeypatch, capsys, profile, flag):
    if profile is None: monkeypatch.delenv("FINLENS_SERVER_PROFILE")
    else: monkeypatch.setenv("FINLENS_SERVER_PROFILE", profile)
    monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", flag)
    original = builtins.__import__
    def guarded(name, *a, **k):
        assert not name.startswith("app")
        return original(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", guarded)
    assert assess.main(["--allow-network"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "EXPLICIT_DEVELOPMENT_REQUIRED"


def test_frozen_release_guard_cannot_be_changed_by_process_env(monkeypatch):
    from app import config
    from app.release_policy import ReleaseModeBlocked
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    with pytest.raises(ReleaseModeBlocked):
        assess._assess()


def test_local_options_keep_finite_bounds_and_add_read_only_without_mutation():
    from app.config import ServerProfile
    from app.database import http_engine_options
    url = "postgresql+psycopg://fixture:synthetic@127.0.0.1/fixture"
    before = http_engine_options(url, ServerProfile("development"), {})[1]
    _, options = assess._connection_options(url, ServerProfile("development"), {})
    assert options["connect_args"] == {**before["connect_args"], "options":
        "-c statement_timeout=30000 -c lock_timeout=5000 -c default_transaction_read_only=on"
        " -c idle_in_transaction_session_timeout=30000"}
    assert options["connect_args"]["connect_timeout"] == options["pool_timeout"] == 5
    assert options["pool_size"] == 2 and options["max_overflow"] == 0
    assert http_engine_options(url, ServerProfile("development"), {})[1] == before


@pytest.mark.parametrize("url", ["sqlite://", "postgresql+psycopg://f:s@203.0.113.1/db",
    "postgresql+psycopg://f:s@[2001:db8::1]/db", "postgresql+psycopg://f:s@localhost/db",
    "postgresql+psycopg://f:s@127.0.0.1/db?options=-c%20default_transaction_read_only=off",
    "postgresql+psycopg://f:s@127.0.0.1/db?service=other"])
def test_unsafe_targets_or_overrides_refused(url):
    from app.config import ServerProfile
    from app.database import HttpDatabaseConfigurationError
    error = assess.AssessmentRejected if "203.0.113.1" in url or "2001:db8::1" in url else HttpDatabaseConfigurationError
    with pytest.raises(error):
        assess._connection_options(url, ServerProfile("development"), {})


@pytest.mark.parametrize("name,value", [("PGOPTIONS", "-c default_transaction_read_only=off"),
    ("PGSERVICE", "fixture"), ("PGHOSTADDR", "203.0.113.1"), ("PGCONNECT_TIMEOUT", "0")])
def test_inherited_overrides_refused(name, value):
    from app.config import ServerProfile
    with pytest.raises(ValueError):
        assess._connection_options("postgresql+psycopg://f:s@127.0.0.1/db", ServerProfile("development"), {name: value})


def test_read_only_each_transaction_and_verification_failure():
    connection = Mock()
    connection.exec_driver_sql.return_value.scalar_one.return_value = "on"
    for _ in range(2): assess._begin_read_only(connection)
    assert [c.args[0] for c in connection.exec_driver_sql.call_args_list] == [
        assess.READ_ONLY, "SHOW transaction_read_only"] * 2
    connection.exec_driver_sql.return_value.scalar_one.return_value = "off"
    with pytest.raises(assess.AssessmentRejected, match="READ_ONLY_UNVERIFIED"):
        assess._begin_read_only(connection)


@pytest.mark.parametrize("sql,many", [("INSERT INTO x VALUES(1)", False), ("UPDATE x SET a=1", False),
    ("DELETE FROM x", False), ("CREATE TABLE x(a int)", False), ("COPY x TO STDOUT", False),
    ("SET TRANSACTION READ WRITE", False), ("SELECT 1", True)])
def test_sql_guard_refuses_writes_and_batch(sql, many):
    with pytest.raises(assess.AssessmentRejected): assess._sql_guard(None, None, sql, None, None, many)


def test_factory_retains_engine_and_revalidates_connect(monkeypatch):
    import sqlalchemy
    from app.config import ServerProfile
    handlers = {}
    engine = Mock()
    create = Mock(return_value=engine)
    monkeypatch.setattr(sqlalchemy, "create_engine", create)
    monkeypatch.setattr(sqlalchemy.event, "listens_for", lambda e, name: lambda fn: handlers.setdefault(name, fn))
    monkeypatch.setattr(sqlalchemy.event, "listen", lambda e, name, fn: handlers.setdefault(name, fn))
    factory = assess._make_factory("postgresql+psycopg://f:s@127.0.0.1/db", ServerProfile("development"))
    assert factory.kw["bind"] is engine
    assert handlers["begin"] is assess._begin_read_only
    assert handlers["before_cursor_execute"] is assess._sql_guard
    params = deepcopy(create.call_args.kwargs["connect_args"])
    dialect = Mock()
    handlers["do_connect"](dialect, None, [], params)
    assert dialect.connect.call_args.kwargs == params
    monkeypatch.setenv("PGSERVICE", "unexpected")
    with pytest.raises(ValueError): handlers["do_connect"](dialect, None, [], params)
    assert dialect.connect.call_count == 1
    monkeypatch.delenv("PGSERVICE")
    params["options"] = "-c default_transaction_read_only=off"
    with pytest.raises(assess.AssessmentRejected): handlers["do_connect"](dialect, None, [], params)
    assert dialect.connect.call_count == 1


def test_canonical_coordinator_uses_real_lock_and_new_transaction_read_only():
    from app.refresh_service import coordinator, COORDINATOR_LOCK
    class Connection:
        invalidated = closed = False
        active = False
        def __init__(self): self.calls = []
        def exec_driver_sql(self, sql):
            self.calls.append(sql)
            return SimpleNamespace(scalar_one=lambda: "on")
        def start(self):
            if not self.active:
                assess._begin_read_only(self)
                self.active = True
        def scalar(self, sql, params):
            self.start(); self.calls.append((str(sql), params)); return True
        def execute(self, sql): self.start(); self.calls.append(str(sql))
        def commit(self): self.calls.append("COMMIT"); self.active = False
        def in_transaction(self): return self.active
        def invalidate(self): self.invalidated = True
        def close(self): self.closed = True
    c = Connection()
    factory = SimpleNamespace(kw={"bind": SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=lambda: c)})
    with coordinator(factory) as owned: owned()
    assert c.calls == [assess.READ_ONLY, "SHOW transaction_read_only",
        ("SELECT pg_try_advisory_lock(:key)", {"key": COORDINATOR_LOCK}), "COMMIT",
        assess.READ_ONLY, "SHOW transaction_read_only", "SELECT 1", "COMMIT"]
    assert c.closed and c.invalidated


@pytest.mark.parametrize("name", ["HTTP_PROXY", "https_proxy", "ALL_PROXY"])
def test_proxy_refusal_before_contact_or_source(monkeypatch, name):
    monkeypatch.setenv(name, "SYNTHETIC_SECRET")
    with pytest.raises(assess.AssessmentRejected, match="PROXY_CONFIGURATION_UNSUPPORTED"):
        assess._network_admission()


@pytest.mark.parametrize("scheme", ["http", "https", "all"])
def test_platform_proxy_with_empty_env_matches_httpx_and_blocks_before_contact(monkeypatch, scheme):
    import httpx
    import httpx._utils
    from app import sec_client
    discovered = {scheme: "http://synthetic-proxy.invalid:8080"}
    discover = Mock(return_value=discovered)
    monkeypatch.setattr(assess.urllib_request, "getproxies", discover)
    # Probe the installed HTTPX mapping only, no client/transport/socket creation.
    # Its internal imported alias is patched independently; production uses only
    # urllib's public API, not this private compatibility probe.
    monkeypatch.setattr(httpx._utils, "getproxies", discover)
    proxy_map = httpx.Client._get_proxy_map(None, proxy=None, allow_env_proxies=True)
    assert str(proxy_map[scheme + "://"].url) == "http://synthetic-proxy.invalid:8080"
    headers, source = Mock(), Mock()
    monkeypatch.setattr(sec_client, "get_sec_headers", headers)
    monkeypatch.setattr(sec_client, "get_company_facts", source)
    assert not any(value for name, value in os.environ.items()
                   if name.lower() in {"http_proxy", "https_proxy", "all_proxy"})
    with pytest.raises(assess.AssessmentRejected, match="PROXY_CONFIGURATION_UNSUPPORTED"):
        assess._aapl_facts(assess.CIK)
    headers.assert_not_called()
    source.assert_not_called()


@pytest.mark.parametrize("discovered", [{}, {"no": "*"}, {"no": "data.sec.gov"},
                                        {"ftp": "http://synthetic-proxy.invalid:8080"}])
def test_direct_and_no_proxy_controls(monkeypatch, discovered):
    from app import sec_client
    monkeypatch.setattr(assess.urllib_request, "getproxies", lambda: discovered)
    headers = Mock(return_value={})
    monkeypatch.setattr(sec_client, "get_sec_headers", headers)
    assess._network_admission()
    headers.assert_called_once()


@pytest.mark.parametrize("discovered", [None, [], {"https": None}, {1: "proxy"}, {"https": 1}])
def test_malformed_proxy_discovery_fails_closed_before_contact(monkeypatch, discovered):
    from app import sec_client
    monkeypatch.setattr(assess.urllib_request, "getproxies", lambda: discovered)
    headers = Mock()
    monkeypatch.setattr(sec_client, "get_sec_headers", headers)
    with pytest.raises(assess.AssessmentRejected, match="PROXY_CONFIGURATION_UNVERIFIED"):
        assess._network_admission()
    headers.assert_not_called()


def test_proxy_discovery_exception_is_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(assess.urllib_request, "getproxies", Mock(side_effect=RuntimeError("SYNTHETIC_SECRET")))
    assert assess.main(["--allow-network"]) == 1
    captured = capsys.readouterr()
    assert "SYNTHETIC_SECRET" not in captured.out + captured.err
    assert json.loads(captured.out)["code"] == "PROXY_CONFIGURATION_UNVERIFIED"


def test_contact_and_cik_checks_before_source(monkeypatch):
    from app import sec_client
    source = Mock(return_value={"cik": 320193})
    monkeypatch.setattr(sec_client, "get_company_facts", source)
    monkeypatch.setattr(sec_client, "get_sec_headers", Mock(side_effect=ValueError("SYNTHETIC_SECRET")))
    with pytest.raises(assess.AssessmentRejected, match="AAPL_IDENTITY_MISMATCH"): assess._aapl_facts("0000000001")
    with pytest.raises(ValueError): assess._aapl_facts(assess.CIK)
    source.assert_not_called()
    monkeypatch.setattr(sec_client, "get_sec_headers", Mock(return_value={"User-Agent": "synthetic"}))
    assert assess._aapl_facts(assess.CIK) == {"cik": 320193}
    source.assert_called_once_with(assess.CIK)


def test_exception_and_dependency_output_never_leak(monkeypatch, capsys):
    def fail():
        print("SYNTHETIC_SECRET")
        raise RuntimeError("SYNTHETIC_SECRET")
    monkeypatch.setattr(assess, "_assess", fail)
    assert assess.main(["--allow-network"]) == 1
    output = capsys.readouterr()
    assert "SYNTHETIC_SECRET" not in output.out + output.err
    assert json.loads(output.out)["code"] == "ASSESSMENT_UNVERIFIED"


def payload(value="100", accession="0000320193-25-000001"):
    return {"cik": 320193, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [{
        "val": Decimal(value), "start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-01",
        "accn": accession, "form": "10-K", "fy": 2024, "fp": "FY", "frame": "CY2024"}]}}}}}


@pytest.mark.parametrize("variant,expected", [("same", 0), ("new", 1), ("conflict", None), ("empty", None)])
def test_worker_through_canonical_refresh_merge_no_recovery_or_publication(monkeypatch, variant, expected):
    from sqlalchemy import create_engine, event, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app import refresh_service, sec_client
    from app.models import Company, FinancialFact, CompanyRefreshState, RefreshAttempt
    from app.sec_importer import merge_company_facts
    from scripts import setup_demo
    engine = create_engine("sqlite://", poolclass=StaticPool)
    for model in (Company, FinancialFact, CompanyRefreshState, RefreshAttempt): model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session, session.begin():
        session.add(Company(cik=assess.CIK, ticker="AAPL", name="Synthetic", exchange="NASDAQ"))
        session.flush()
        merge_company_facts(session, assess.CIK, payload(), publish=False)
        # Abandoned metadata must not be recovered even for another company.
        from app.refresh_contracts import utcnow
        session.add(RefreshAttempt(id="old", run_id="old", company_cik=assess.CIK,
                                  stream="facts", status="running", started_at=utcnow(), details={}))
    with engine.connect() as c: c.exec_driver_sql("PRAGMA query_only=ON")
    original_dispose = engine.dispose
    dispose = Mock()
    monkeypatch.setattr(engine, "dispose", dispose)
    monkeypatch.setattr(assess, "_make_factory", lambda *a: factory)
    monkeypatch.setattr(setup_demo, "check_schema", Mock())
    monkeypatch.setattr(sec_client, "get_sec_headers", lambda: {})
    data = payload() if variant == "same" else payload("200", "0000320193-26-000001" if variant == "new" else "0000320193-25-000001")
    if variant == "empty": data = {"cik": 320193, "facts": {"us-gaap": {}}}
    source = Mock(return_value=data)
    monkeypatch.setattr(sec_client, "get_company_facts", source)
    def no_evidence(*a, **k): raise AssertionError("Evidence/model path forbidden")
    monkeypatch.setattr(sec_client, "discover_refresh_filings", no_evidence)
    sql = []
    event.listen(engine, "before_cursor_execute", lambda c, cur, statement, *a: sql.append(statement))
    try:
        if expected is None:
            with pytest.raises(assess.AssessmentRejected, match="CANONICAL_ASSESSMENT_FAILED"): assess._assess()
        else:
            result = assess._assess()
            assert result["would_insert"] == expected and result["version_before"] == result["version_after"] == 0
        source.assert_called_once_with(assess.CIK)
        dispose.assert_called_once()
        with factory() as s:
            assert len(list(s.scalars(select(FinancialFact)))) == 1
            assert s.get(RefreshAttempt, "old").status == "running"
            assert not list(s.scalars(select(CompanyRefreshState)))
        assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")) for s in sql)
    finally: original_dispose()


@pytest.mark.parametrize("change", [{"facts_inserted": 1}, {"version_after": 1}, {"would_insert": True},
    {"would_insert": -1}, {"stream": "evidence"}, {"pending_targets": ["anything"]}, {"status": "updated"}])
def test_untrusted_result_fields_fail_closed(change):
    from app.refresh_contracts import RefreshResult
    row = RefreshResult(ticker="AAPL", stream="facts", status="no_change").model_dump(mode="json")
    row.update(change)
    with pytest.raises(assess.AssessmentRejected): assess._sanitized_result({"dry_run": True, "error": None, "companies": [row]})
