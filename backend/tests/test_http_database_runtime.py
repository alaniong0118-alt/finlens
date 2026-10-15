"""Synthetic HTTP runtime contracts; run through the guarded Increment 2 runner."""
import ast
from json import JSONDecodeError
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
import psycopg
import pytest
from sqlalchemy import event, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app import config, database, embedding_service as embedding, freshness_service as freshness, main
from app.refresh_contracts import Freshness
from app.models import Company, CompanyRefreshState, FilingPublication
from app.release_policy import READONLY_ROUTES, ReleaseModeBlocked, development_only

URL = "postgresql+psycopg://fixture:private@127.0.0.1/fixture"
SENSITIVE = "password=private SQL SELECT secret params host diagnostics C:/models/private"
OPERATIONAL_FACTORY = database.SessionLocal


def bomb(*args, **kwargs):
    raise AssertionError("Out-of-scope database/model/provider work")


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    monkeypatch.setattr(database.engine, "connect", bomb)
    monkeypatch.setattr(database, "SessionLocal", bomb)
    monkeypatch.setattr(database, "_http_factory", None)
    monkeypatch.setattr(main, "HttpSessionLocal", bomb)
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    cached_model = embedding._get_model
    cached_model.cache_clear()
    yield
    cached_model.cache_clear()


@pytest.mark.parametrize("profile,expected", [
    ("development", (5, 5, 30000, 5000, 5, 5)),
    ("sec_readonly", (3, 2, 10000, 2000, 5, 0)),
])
def test_profile_limits_and_startup_options(profile, expected):
    bounds = config.ServerProfile(profile).http_database_bounds
    assert (bounds.connect_timeout, bounds.pool_timeout, bounds.statement_timeout_ms,
            bounds.lock_timeout_ms, bounds.pool_size, bounds.max_overflow) == expected
    _, options = database.http_engine_options(URL, config.ServerProfile(profile), {})
    assert options["connect_args"]["options"] == f"-c statement_timeout={expected[2]} -c lock_timeout={expected[3]}"
    assert options["connect_args"]["connect_timeout"] == expected[0]
    assert options["pool_timeout"] == expected[1]
    assert options["pool_size"] == 5 and options["max_overflow"] == expected[5]
    assert options["pool_pre_ping"] is False


@pytest.mark.parametrize("url", [
    "malformed private URL", "sqlite://", "postgresql://u:p@127.0.0.1/db", "postgresql+psycopg2://u:p@127.0.0.1/db",
    "postgresql+asyncpg://u:p@127.0.0.1/db", "postgresql+psycopg://u:p@/db",
    "postgresql+psycopg://u:p@127.0.0.1", "postgresql+psycopg://u:p@one,two/db",
    "postgresql+psycopg://u:p@localhost/db", "postgresql+psycopg://u:p@127.0.0.1:0/db",
    "postgresql+psycopg://u:p@127.0.0.1:65536/db",
    *[URL + "?" + query for query in [
        "host=other", "host=one&host=two", "hostaddr=127.0.0.1,127.0.0.2",
        "hostaddr=localhost", "port=5432,5433", "service=private", "servicefile=private",
        "connect_timeout=0", "connect_timeout=5&connect_timeout=5", "options=-c+statement_timeout=0",
        "sslmode=require&sslmode=disable", "target_session_attrs=prefer-standby", "async_fallback=true",
        "load_balance_hosts=random", "dbname=host%3Dother", "client_encoding=SQL_ASCII",
        "sslmode=unknown", "sslsni=off", "sslnegotiation=unknown", "ssl_min_protocol_version=unknown",
    ]],
])
def test_hostile_url_rejected_without_engine_or_connect(url, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_URL", url)
    monkeypatch.setattr(database, "create_engine", bomb)
    with pytest.raises(database.HttpDatabaseConfigurationError) as exc:
        database.HttpSessionLocal()
    assert str(exc.value) == "Unsupported HTTP database configuration."


@pytest.mark.parametrize("name,value", [
    ("PGOPTIONS", "-c statement_timeout=0"), ("PGOPTIONS", "-c lock_timeout=1 -c statement_timeout=0"),
    ("PGCONNECT_TIMEOUT", "0"), ("PGSERVICE", "private"), ("PGSERVICEFILE", "private"),
    ("PGHOST", "one,two"), ("PGHOSTADDR", "127.0.0.1,127.0.0.2"), ("PGHOSTADDR", "127.0.0.2"),
    ("PGPORT", "5432,5433"), ("PGTARGETSESSIONATTRS", "prefer-standby"), ("PGLOADBALANCEHOSTS", "random"),
])
def test_hostile_environment_rejected_without_mutation(name, value):
    env = {name: value}
    with pytest.raises(database.HttpDatabaseConfigurationError):
        database.http_engine_options(URL, config.ServerProfile("development"), env)
    assert env == {name: value}


def test_tls_preserved_hostname_single_address_and_canonical_options():
    url = "postgresql+psycopg://u:p@db.example/db?hostaddr=192.0.2.1&sslmode=verify-full&sslrootcert=C%3A%2Fprivate%2Fca.pem"
    parsed, options = database.http_engine_options(url, config.ServerProfile("development"), {})
    assert parsed.query["sslmode"] == "verify-full" and parsed.query["sslrootcert"] == "C:/private/ca.pem"
    assert options["connect_args"]["host"] == "db.example"
    assert options["connect_args"]["hostaddr"] == "192.0.2.1"
    args, params = postgresql.psycopg.dialect().create_connect_args(parsed)
    params.update(options["connect_args"])
    assert params["sslmode"] == "verify-full" and params["sslrootcert"] == "C:/private/ca.pem"
    assert args == [] and params["options"] == "-c statement_timeout=30000 -c lock_timeout=5000"
    bounds = config.ServerProfile("development").http_database_bounds
    env = {"PGOPTIONS": bounds.startup_options, "PGCONNECT_TIMEOUT": "5", "PGSSLMODE": "verify-full"}
    database.http_engine_options(URL, config.ServerProfile("development"), env)
    assert env["PGOPTIONS"] == bounds.startup_options


@pytest.mark.parametrize("profile", ["development", "sec_readonly"])
def test_lazy_factory_isolated_and_connection_startup_precedes_probe(monkeypatch, profile):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile(profile))
    monkeypatch.setattr(database, "DATABASE_URL", URL)
    assert database._http_factory is None
    factory = database.http_session_factory()
    http_engine = factory.kw["bind"]
    assert http_engine is not database.engine
    assert database.http_session_factory() is factory
    assert http_engine.pool.size() == 5
    assert http_engine.pool.timeout() == config.ServerProfile(profile).http_database_bounds.pool_timeout
    assert http_engine.pool._max_overflow == (5 if profile == "development" else 0)
    assert http_engine.pool.checkedin() == 0 and http_engine.pool.checkedout() == 0
    session = database.HttpSessionLocal()
    assert session.get_bind() is http_engine and session.autoflush is False
    session.close()
    # The actual registered do_connect event passes startup limits into DBAPI,
    # before SQLAlchemy can initialize or call the registered checkout probe.
    calls = []
    fake = object()
    dialect = SimpleNamespace(connect=lambda *a, **k: calls.append(k) or fake)
    params = {"sslmode": "verify-full"}
    _, options = database.http_engine_options(URL, config.ServerProfile(profile), {})
    params.update(options["connect_args"])
    hook = next(iter(http_engine.dialect.dispatch.do_connect))
    assert hook(dialect, Mock(), [], params) is fake
    assert calls == [params]
    assert calls[0]["options"] == config.ServerProfile(profile).http_database_bounds.startup_options
    monkeypatch.setenv("PGOPTIONS", "-c statement_timeout=0")
    with pytest.raises(database.HttpDatabaseConfigurationError):
        hook(dialect, Mock(), [], params)
    assert len(calls) == 1
    http_engine.dispose()


@pytest.mark.parametrize("failure", [psycopg.errors.QueryCanceled(SENSITIVE), psycopg.OperationalError(SENSITIVE),
                                    psycopg.errors.SyntaxError(SENSITIVE), False, TypeError(SENSITIVE)])
def test_checkout_probe_invalidates_once_without_retry(failure):
    ping = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    engine = SimpleNamespace(dialect=SimpleNamespace(do_ping=ping))
    record = Mock()
    with pytest.raises(TypeError if isinstance(failure, TypeError) else DBAPIError) as exc:
        database._checkout_probe(engine, object(), record, object())
    ping.assert_called_once()
    record.invalidate.assert_called_once()
    if isinstance(failure, psycopg.errors.SyntaxError):
        assert database.database_failure(exc.value) is None


@pytest.mark.parametrize("failure,code", [
    (psycopg.OperationalError(SENSITIVE), "DATABASE_UNAVAILABLE"),
    (psycopg.errors.TooManyConnections(SENSITIVE), "DATABASE_BUSY"),
    (psycopg.errors.QueryCanceled(SENSITIVE), "DATABASE_TIMEOUT"),
    (psycopg.errors.SyntaxError(SENSITIVE), None),
    (TypeError(SENSITIVE), None),
])
def test_registered_connect_boundary_types_failures_without_retry(monkeypatch, failure, code):
    monkeypatch.setattr(database, "DATABASE_URL", URL)
    factory = database.http_session_factory()
    engine = factory.kw["bind"]
    hook = next(iter(engine.dialect.dispatch.do_connect))
    connect = Mock(side_effect=failure)
    with pytest.raises(database.HttpDatabaseConnectionError if isinstance(failure, psycopg.Error) else TypeError) as exc:
        hook(SimpleNamespace(connect=connect), Mock(), [], {})
    connect.assert_called_once()
    classified = database.database_failure(exc.value)
    assert (classified[1] if classified else None) == code
    engine.dispose()


def wrapped(error, invalidated=False, cls=DBAPIError):
    return cls("SELECT secret", {"password": "private"}, error, connection_invalidated=invalidated)


ERRORS = [
    (TimeoutError(SENSITIVE), 503, "DATABASE_BUSY"),
    (wrapped(psycopg.errors.LockNotAvailable(SENSITIVE)), 503, "DATABASE_BUSY"),
    (wrapped(psycopg.errors.TooManyConnections(SENSITIVE)), 503, "DATABASE_BUSY"),
    (wrapped(psycopg.errors.QueryCanceled(SENSITIVE)), 504, "DATABASE_TIMEOUT"),
    *[(wrapped(psycopg.errors.lookup(state)(SENSITIVE)), 503, "DATABASE_UNAVAILABLE")
      for state in ["08000", "08001", "08003", "08004", "08006", "08007", "08P01", "57P01", "57P02", "57P03"]],
    (wrapped(psycopg.OperationalError(SENSITIVE), cls=database.HttpDatabaseConnectionError), 503, "DATABASE_UNAVAILABLE"),
    (wrapped(psycopg.errors.ConnectionTimeout(SENSITIVE), cls=database.HttpDatabaseConnectionError), 503, "DATABASE_UNAVAILABLE"),
    (wrapped(Exception(SENSITIVE), invalidated=True), 503, "DATABASE_UNAVAILABLE"),
    (embedding.EncoderDependencyError(SENSITIVE), 503, "RETRIEVAL_UNAVAILABLE"),
    (wrapped(psycopg.errors.SyntaxError(SENSITIVE)), 500, None),
    (wrapped(psycopg.errors.SyntaxError(SENSITIVE), invalidated=True), 500, None),
    (wrapped(psycopg.errors.UndefinedTable(SENSITIVE)), 500, None),
    (wrapped(psycopg.errors.SerializationFailure(SENSITIVE)), 500, None),
    (wrapped(psycopg.OperationalError("timeout 57014 connection refused")), 500, None),
    (wrapped(SimpleNamespace(sqlstate="57014")), 500, None),
    (OperationalError("secret", {}, Exception("timeout connection refused")), 500, None),
    (TypeError(SENSITIVE), 500, None), (AttributeError(SENSITIVE), 500, None),
    (AssertionError(SENSITIVE), 500, None), (RuntimeError("57014 pool timeout"), 500, None),
]


@pytest.mark.parametrize("exc,status,code", ERRORS)
@pytest.mark.parametrize("version", [None, 0, 8])
def test_typed_errors_fixed_body_headers_and_pin_provenance(monkeypatch, exc, status, code, version):
    def factory():
        main.request_scope.get()["version"] = version
        raise exc
    monkeypatch.setattr(main, "HttpSessionLocal", factory)
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == status
    assert response.headers.get("X-FinLens-Error-Code") == code
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("X-FinLens-Data-Version") == (str(version) if version is not None else None)
    messages = {
        "DATABASE_BUSY": "The research database is busy. Try again later.",
        "DATABASE_TIMEOUT": "The research database request could not complete in time.",
        "DATABASE_UNAVAILABLE": "The research database is unavailable. Try again later.",
        "RETRIEVAL_UNAVAILABLE": "Filing evidence search is unavailable. Try again later.",
        None: "Internal server error.",
    }
    assert response.json() == {"detail": messages[code]}
    assert all(secret not in response.text for secret in ["private", "SELECT", "params", "diagnostics", "C:/models"])
    assert main.request_scope.get() is None


class FakeSession:
    def __init__(self, stage=None, error=None, version=0):
        self.stage, self.error, self.version = stage, error, version
        self.events = []
        self.conn = SimpleNamespace(invalidate=Mock())
        self.invalidated = False

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def connection(self):
        self.events.append("connection")
        if self.stage in {"connect", "pre-ping"}:
            raise self.error
        return self.conn

    def execute(self, stmt):
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        self.events.append(sql)
        if self.stage == "transaction" and sql.startswith("SET TRANSACTION"):
            raise self.error
        if self.stage == "query" and sql == "SELECT 42":
            raise self.error

    def scalar(self, stmt):
        compiled = stmt.compile(dialect=postgresql.dialect())
        assert compiled.params == {"ticker_1": "TEST"}
        assert "company_refresh_state.data_version" in str(compiled)
        self.events.append("pin")
        if self.stage == "pin":
            raise self.error
        return self.version

    def close(self):
        self.events.append("close")
        if self.stage == "cleanup":
            raise self.error

    def invalidate(self):
        self.events.append("invalidate")
        self.invalidated = True


class ProductionFreshnessSession(FakeSession):
    """Synthetic ORM data for the real freshness function, with compiled SQL."""
    def __init__(self, version=0, **kwargs):
        super().__init__(version=version, **kwargs)
        self.company = Company(ticker="TEST", cik="0000000001", name="Fixture")
        self.metadata = None if version is None else CompanyRefreshState(
            company_cik=self.company.cik, data_version=version,
            facts_version=version, evidence_version=version, facts={}, evidence={})

    def scalar(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is CompanyRefreshState:
            return super().scalar(stmt)
        compiled = stmt.compile(dialect=postgresql.dialect())
        if entity is Company:
            assert compiled.params == {"ticker_1": self.company.ticker}
            self.events.append("company")
            return self.company
        assert entity is FilingPublication
        assert compiled.params["company_cik_1"] == self.company.cik
        self.events.append("latest")
        return None

    def get(self, model, key):
        assert model is CompanyRefreshState and key == self.company.cik
        self.events.append("metadata")
        return self.metadata

    def execute(self, stmt):
        if getattr(stmt, "is_select", False):
            assert stmt.column_descriptions[0]["entity"] is FilingPublication
            compiled = stmt.compile(dialect=postgresql.dialect())
            assert compiled.params["company_cik_1"] == self.company.cik
            assert "cleaned_text" not in str(compiled)
            self.events.append("latest")
            return SimpleNamespace(first=lambda: None)
        return super().execute(stmt)


def install_production_freshness(monkeypatch, session, schema=True):
    monkeypatch.setattr(main, "HttpSessionLocal", lambda: session)
    monkeypatch.setattr(freshness, "schema_ready", lambda conn: schema)
    assert main.freshness is freshness.freshness


@pytest.mark.parametrize("missing", ["row", "schema"])
def test_production_freshness_unverified_is_unavailable(monkeypatch, missing):
    session = ProductionFreshnessSession(version=None)
    install_production_freshness(monkeypatch, session, schema=missing != "schema")
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Publication freshness is unavailable. Try again later."}
    assert response.headers["X-FinLens-Error-Code"] == "FRESHNESS_UNAVAILABLE"
    assert response.headers["Cache-Control"] == "no-store"
    assert "data_version" not in response.json()
    assert "X-FinLens-Data-Version" not in response.headers
    assert session.events.count("close") == 1 and "latest" not in session.events
    if missing == "schema":
        assert "pin" not in session.events and "metadata" not in session.events
    assert main.request_scope.get() is None


@pytest.mark.parametrize("missing", ["row", "schema"])
@pytest.mark.parametrize("version", [0, 9])
def test_production_freshness_recovers_on_later_independent_request(monkeypatch, missing, version):
    unavailable = ProductionFreshnessSession(version=None)
    install_production_freshness(monkeypatch, unavailable, schema=missing != "schema")
    client = TestClient(main.app)
    first = client.get("/companies/TEST/freshness")
    assert first.status_code == 503 and "X-FinLens-Data-Version" not in first.headers
    recovered = ProductionFreshnessSession(version=version)
    install_production_freshness(monkeypatch, recovered)
    later = client.get("/companies/TEST/freshness", headers={"X-FinLens-Data-Version": str(version)})
    assert later.status_code == 200
    assert later.json()["data_version"] == version and type(later.json()["data_version"]) is int
    assert later.json()["facts_version"] == version and later.json()["evidence_version"] == version
    assert later.headers["X-FinLens-Data-Version"] == str(version)
    assert later.headers["Cache-Control"] == "no-store" and "X-FinLens-Error-Code" not in later.headers
    assert recovered.events[:2] == ["connection", "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"]
    assert recovered.events.count("pin") == 1
    assert recovered.events.count("metadata") == 1 and recovered.events.count("latest") == 1
    assert recovered.events[-1] == "close" and unavailable.events.count("close") == 1
    assert recovered.conn is not unavailable.conn and main.request_scope.get() is None


@pytest.mark.parametrize("version", [0, 9])
def test_production_freshness_stale_pin_is_409_before_body_reads(monkeypatch, version):
    session = ProductionFreshnessSession(version=version)
    install_production_freshness(monkeypatch, session)
    response = TestClient(main.app).get("/companies/TEST/freshness", headers={"X-FinLens-Data-Version": str(version + 1)})
    assert response.status_code == 409
    assert response.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    assert response.headers["X-FinLens-Data-Version"] == str(version)
    assert response.headers["Cache-Control"] == "no-store"
    assert "company" not in session.events and "metadata" not in session.events
    assert session.events.count("pin") == 1 and session.events[-1] == "close"


@pytest.mark.parametrize("missing", ["row", "schema"])
def test_production_freshness_unverified_cleanup_failure_preserves_unavailable(monkeypatch, missing):
    session = ProductionFreshnessSession(version=None, stage="cleanup",
        error=wrapped(psycopg.errors.QueryCanceled(SENSITIVE)))
    install_production_freshness(monkeypatch, session, schema=missing != "schema")
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 503 and response.headers["X-FinLens-Error-Code"] == "FRESHNESS_UNAVAILABLE"
    assert response.json() == {"detail": "Publication freshness is unavailable. Try again later."}
    assert "X-FinLens-Data-Version" not in response.headers
    session.conn.invalidate.assert_called_once()
    assert session.invalidated and session.events.count("close") == 1


@pytest.mark.parametrize("failure", [TypeError(SENSITIVE), AttributeError(SENSITIVE), AssertionError(SENSITIVE)])
def test_production_freshness_programming_failure_remains_sanitized_generic(monkeypatch, failure):
    session = ProductionFreshnessSession(version=9)
    install_production_freshness(monkeypatch, session)
    session.get = Mock(side_effect=failure)
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 500 and response.json() == {"detail": "Internal server error."}
    assert "X-FinLens-Error-Code" not in response.headers
    assert response.headers["X-FinLens-Data-Version"] == "9"
    assert response.headers["Cache-Control"] == "no-store"
    assert all(secret not in response.text for secret in ["private", "SELECT", "params", "diagnostics", "C:/models"])
    assert session.events.count("close") == 1 and main.request_scope.get() is None


def install_session(monkeypatch, session):
    monkeypatch.setattr(main, "HttpSessionLocal", lambda: session)
    monkeypatch.setattr(freshness, "schema_ready", lambda conn: True)
    def result(s, ticker):
        assert s is session
        s.execute(text("SELECT 42"))
        # Boundary-only stub: publication availability cases below exercise the
        # production function instead. Never turn an unknown pin into zero.
        return Freshness(ticker=ticker, data_version=session.version)
    monkeypatch.setattr(main, "freshness", result)


@pytest.mark.parametrize("stage", ["connect", "pre-ping", "transaction", "pin", "query", "cleanup"])
@pytest.mark.parametrize("version", [0, 9])
def test_failure_stages_snapshot_cleanup_and_later_request_recovery(monkeypatch, stage, version):
    error = wrapped(psycopg.errors.QueryCanceled(SENSITIVE))
    failed = FakeSession(stage, error, version)
    install_session(monkeypatch, failed)
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 504
    verified = stage in {"query", "cleanup"}
    assert response.headers.get("X-FinLens-Data-Version") == (str(version) if verified else None)
    assert failed.events.count("close") == 1 and "SELECT 42" not in response.text
    if stage == "cleanup":
        failed.conn.invalidate.assert_called_once()
        assert failed.invalidated
    if verified:
        assert failed.events[:3] == ["connection", "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", "connection"]
        assert failed.events.count("pin") == 1
    recovered = FakeSession(version=version + 1)
    install_session(monkeypatch, recovered)
    later = TestClient(main.app).get("/companies/TEST/freshness")
    assert later.status_code == 200 and later.headers["X-FinLens-Data-Version"] == str(version + 1)
    assert recovered.events.count("pin") == 1 and recovered.events[-1] == "close"
    assert failed.events.count("close") == 1


@pytest.mark.parametrize("version", [None, 0, 7])
def test_zero_positive_missing_metadata_and_409_headers(monkeypatch, version):
    session = ProductionFreshnessSession(version=version)
    install_production_freshness(monkeypatch, session)
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == (200 if version is not None else 503)
    if version is not None:
        assert response.json()["data_version"] == version
    assert response.headers.get("X-FinLens-Data-Version") == (str(version) if version is not None else None)
    for expected in ["0", "7"]:
        session.events.clear()
        response = TestClient(main.app).get("/companies/TEST/freshness", headers={"X-FinLens-Data-Version": expected})
        assert response.status_code == (200 if version is not None and str(version) == expected else 409)
        assert response.headers.get("X-FinLens-Data-Version") == (str(version) if version is not None else None)
        if response.status_code == 409:
            assert response.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
            assert "company" not in session.events and "metadata" not in session.events
        assert session.events.count("pin") == 1


def test_unmigrated_scope_never_fabricates_pin(monkeypatch):
    session = ProductionFreshnessSession()
    install_production_freshness(monkeypatch, session, schema=False)
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 503 and "X-FinLens-Data-Version" not in response.headers
    assert response.headers["X-FinLens-Error-Code"] == "FRESHNESS_UNAVAILABLE"
    assert "pin" not in session.events
    response = TestClient(main.app).get("/companies/TEST/freshness", headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 409 and response.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    assert "X-FinLens-Data-Version" not in response.headers


@pytest.mark.parametrize("version", [-1, True, "0"])
def test_invalid_pin_metadata_stays_generic_and_unverified(monkeypatch, version):
    install_session(monkeypatch, FakeSession(version=version))
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 500 and "X-FinLens-Data-Version" not in response.headers


def test_schema_probe_failure_is_unverified_and_sanitized(monkeypatch):
    session = FakeSession(version=0)
    install_session(monkeypatch, session)
    monkeypatch.setattr(freshness, "schema_ready", Mock(side_effect=wrapped(psycopg.errors.LockNotAvailable(SENSITIVE))))
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 503 and response.headers["X-FinLens-Error-Code"] == "DATABASE_BUSY"
    assert "X-FinLens-Data-Version" not in response.headers
    assert "pin" not in session.events and session.events[-1] == "close"


def test_cleanup_failure_preserves_primary_programming_error_and_discards_connection(monkeypatch):
    session = FakeSession("cleanup", wrapped(psycopg.errors.QueryCanceled(SENSITIVE)))
    install_session(monkeypatch, session)
    monkeypatch.setattr(main, "freshness", Mock(side_effect=TypeError(SENSITIVE)))
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == 500 and response.headers["X-FinLens-Data-Version"] == "0"
    assert "X-FinLens-Error-Code" not in response.headers
    session.conn.invalidate.assert_called_once()
    assert session.invalidated


@pytest.mark.parametrize("status,code", [(400, None), (404, None), (409, "EVIDENCE_PENDING"), (422, None)])
def test_meaningful_research_contracts_preserved(monkeypatch, status, code):
    session = FakeSession(version=5)
    install_session(monkeypatch, session)
    headers = {"X-FinLens-Error-Code": code} if code else None
    monkeypatch.setattr(main, "freshness", Mock(side_effect=HTTPException(status, {"reason": "fixture"}, headers)))
    response = TestClient(main.app).get("/companies/TEST/freshness")
    assert response.status_code == status and response.json() == {"detail": {"reason": "fixture"}}
    assert response.headers.get("X-FinLens-Error-Code") == code
    assert response.headers["X-FinLens-Data-Version"] == "5"


def test_fastapi_validation_does_not_open_session_or_fabricate_pin():
    response = TestClient(main.app).get("/companies/TEST/financials/annual?fiscal_year=1899")
    assert response.status_code == 422 and "X-FinLens-Data-Version" not in response.headers


HTTP_DB_ROUTES = sorted(READONLY_ROUTES - {("GET", "/healthz"), ("GET", "/capabilities")}) + [
    ("POST", "/companies/{ticker}/filings/{accession_number}/answer")]


@pytest.mark.parametrize("method,path", HTTP_DB_ROUTES)
@pytest.mark.parametrize("profile", ["development", "sec_readonly"])
def test_every_http_database_path_uses_bounded_factory(monkeypatch, method, path, profile):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile(profile))
    factory = Mock(side_effect=TimeoutError(SENSITIVE))
    monkeypatch.setattr(main, "HttpSessionLocal", factory)
    monkeypatch.setattr(embedding, "_get_model", bomb)
    monkeypatch.setattr(main, "answer_filing_question", bomb)
    actual = path.replace("{ticker}", "TEST").replace("{accession_number}", "fixture").replace("{metric}", "revenue")
    response = TestClient(main.app).request(method, actual, params={"q": "revenue"}, json={"question": "revenue"})
    if profile == "sec_readonly" and path.endswith("/answer"):
        assert response.status_code == 403 and response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"
        factory.assert_not_called()
    else:
        assert response.status_code == 503 and response.headers["X-FinLens-Error-Code"] == "DATABASE_BUSY"
        factory.assert_called_once()
    assert "X-FinLens-Data-Version" not in response.headers


def test_no_operational_engine_http_callsite_and_dbz_read_only(monkeypatch):
    source = Path(main.__file__).read_text()
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.Name) and node.id in {"engine", "SessionLocal"} for node in ast.walk(tree))
    session = FakeSession()
    monkeypatch.setattr(main, "HttpSessionLocal", lambda: session)
    response = TestClient(main.app).get("/dbz")
    assert response.json() == {"status": "ok", "database": "postgresql"}
    assert session.events == ["connection", "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", "SELECT 1", "close"]


@pytest.mark.parametrize("failure", [ImportError(SENSITIVE), ModuleNotFoundError(SENSITIVE),
                                    FileNotFoundError(SENSITIVE), PermissionError(SENSITIVE),
                                    JSONDecodeError("private", "{", 0)])
@pytest.mark.parametrize("profile", ["development", "sec_readonly"])
def test_narrow_encoder_dependency_failures(monkeypatch, tmp_path, failure, profile):
    install_encoder(monkeypatch, tmp_path, profile, Mock(side_effect=failure))
    with pytest.raises(embedding.EncoderDependencyError) as exc:
        embedding.embed_texts(["query"])
    assert str(exc.value) == "The query encoder dependency is unavailable."


def install_encoder(monkeypatch, tmp_path, profile, constructor):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile(profile))
    cached = tmp_path / "modules.json"
    cached.write_text("[]")
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(try_to_load_from_cache=lambda *a: str(cached)))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=constructor))


@pytest.mark.parametrize("failure", [TypeError(SENSITIVE), AttributeError(SENSITIVE), AssertionError(SENSITIVE), ValueError(SENSITIVE)])
def test_encoder_programming_errors_are_not_outages(monkeypatch, tmp_path, failure):
    install_encoder(monkeypatch, tmp_path, "sec_readonly", Mock(side_effect=failure))
    with pytest.raises(type(failure)) as exc:
        embedding.embed_texts(["query"])
    assert not isinstance(exc.value, embedding.EncoderDependencyError)


@pytest.mark.parametrize("cache", [None, object(), "missing-cache/modules.json"])
def test_missing_cache_does_not_construct_or_download(monkeypatch, cache):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(try_to_load_from_cache=lambda *a: cache))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=bomb))
    with pytest.raises(embedding.EncoderDependencyError):
        embedding.embed_texts(["query"])


@pytest.mark.parametrize("profile", ["development", "sec_readonly"])
def test_encoder_local_only_and_development_constructor_compatibility(monkeypatch, tmp_path, profile):
    model = SimpleNamespace(get_sentence_embedding_dimension=lambda: 384,
        encode=Mock(return_value=SimpleNamespace(tolist=lambda: [[1.0] * 384])))
    constructor = Mock(return_value=model)
    install_encoder(monkeypatch, tmp_path, profile, constructor)
    assert len(embedding.embed_texts(["query"])[0]) == 384
    if profile == "sec_readonly":
        constructor.assert_called_once_with(str(tmp_path), local_files_only=True)
    else:
        constructor.assert_called_once_with(embedding.MODEL_NAME)
    model.encode.assert_called_once_with(["query"], batch_size=32, normalize_embeddings=True, show_progress_bar=False)


def test_incompatible_model_is_explicit_dependency_failure(monkeypatch, tmp_path):
    install_encoder(monkeypatch, tmp_path, "sec_readonly", lambda *a, **k: SimpleNamespace(get_sentence_embedding_dimension=lambda: 768))
    with pytest.raises(embedding.EncoderDependencyError):
        embedding.embed_texts(["query"])


def test_development_operational_engine_configuration_unchanged_and_release_guard(monkeypatch):
    assert database.engine.pool._pre_ping is True
    assert database.engine.pool.timeout() == 30
    assert database.engine.pool.size() == 5 and database.engine.pool._max_overflow == 10
    assert OPERATIONAL_FACTORY.kw["bind"] is database.engine
    assert OPERATIONAL_FACTORY.kw["autoflush"] is False and OPERATIONAL_FACTORY.kw["autocommit"] is False
    assert database.SessionLocal is bomb  # operational workflows never execute here
    assert development_only(lambda: "maintenance")() == "maintenance"
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    with pytest.raises(ReleaseModeBlocked):
        embedding.embed_filing_chunks(SimpleNamespace(get_bind=bomb))


def test_implementation_import_has_no_http_connection_or_schema_probe():
    assert database._http_factory is None
    assert database.engine.pool.checkedin() == 0 and database.engine.pool.checkedout() == 0


def synthetic_pool():
    """Real SQLAlchemy pool/ORM lifecycle over an entirely fake DBAPI."""
    connections = []

    class Cursor:
        description = None
        rowcount = -1
        def execute(self, sql, params=None):
            self.connection.statements.append(sql)
        def close(self):
            pass

    class Connection:
        def __init__(self):
            self.statements, self.closed, self.fail_rollback = [], False, False
        def cursor(self):
            cursor = Cursor()
            cursor.connection = self
            return cursor
        def rollback(self):
            if self.fail_rollback:
                raise psycopg.errors.QueryCanceled(SENSITIVE)
        def commit(self):
            bomb()
        def close(self):
            self.closed = True

    def creator():
        conn = Connection()
        connections.append(conn)
        return conn
    dialect = DefaultDialect(dbapi=SimpleNamespace(Error=psycopg.Error, paramstyle="named"))
    dialect.name = "postgresql"
    dialect.supports_statement_cache = False
    pool = QueuePool(creator, pool_size=1, max_overflow=0, timeout=0.01, dialect=dialect)
    engine = Engine(pool, dialect, make_url(URL))
    return engine, connections


def test_actual_orm_close_rollback_failure_discards_detached_connection():
    engine, connections = synthetic_pool()
    factory = sessionmaker(bind=engine, close_resets_only=False)
    with pytest.raises(DBAPIError):
        with freshness.read_session(factory) as session:
            session.execute(text("SELECT 42"))
            connections[0].fail_rollback = True
    assert connections[0].closed is True
    assert engine.pool.checkedout() == 0
    with freshness.read_session(factory) as later:
        later.execute(text("SELECT 42"))
    assert len(connections) == 2
    assert all(conn.statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY" for conn in connections)
    assert engine.pool.checkedout() == 0
    engine.dispose()


def test_actual_orm_cleanup_failure_preserves_primary_and_never_reuses_bad_connection():
    engine, connections = synthetic_pool()
    factory = sessionmaker(bind=engine)
    with pytest.raises(TypeError, match="programming"):
        with freshness.read_session(factory):
            connections[0].fail_rollback = True
            raise TypeError("programming")
    assert connections[0].closed is True and engine.pool.checkedout() == 0
    with freshness.read_session(factory):
        pass
    assert len(connections) == 2
    engine.dispose()


def test_actual_pool_checkout_timeout_has_no_retry_and_later_request_recovers():
    engine, connections = synthetic_pool()
    held = engine.connect()
    with pytest.raises(TimeoutError) as exc:
        with freshness.read_session(sessionmaker(bind=engine)):
            bomb()
    assert database.database_failure(exc.value)[1] == "DATABASE_BUSY"
    assert len(connections) == 1
    held.close()
    with freshness.read_session(sessionmaker(bind=engine)):
        pass
    assert len(connections) == 1 and engine.pool.checkedout() == 0
    engine.dispose()


@pytest.mark.parametrize("failure", [psycopg.OperationalError(SENSITIVE), psycopg.errors.QueryCanceled(SENSITIVE),
                                    psycopg.errors.SyntaxError(SENSITIVE), TypeError(SENSITIVE)])
def test_actual_pool_probe_failure_never_reconnects_same_request(failure):
    engine, connections = synthetic_pool()
    ping = Mock(side_effect=[failure, True])
    engine.dialect.do_ping = ping
    event.listen(engine, "checkout", lambda conn, record, proxy: database._checkout_probe(engine, conn, record, proxy))
    with pytest.raises(TypeError if isinstance(failure, TypeError) else DBAPIError):
        engine.connect()
    assert len(connections) == 1 and connections[0].closed and engine.pool.checkedout() == 0
    ping.assert_called_once()
    with engine.connect():
        pass
    assert len(connections) == 2 and ping.call_count == 2
    engine.dispose()
