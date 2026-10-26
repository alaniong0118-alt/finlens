from ipaddress import ip_address
from threading import Lock

import psycopg
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, DBAPIError, TimeoutError as PoolTimeoutError
from sqlalchemy.orm import DeclarativeBase, sessionmaker


import os

from app.config import load_backend_env, server_profile

load_backend_env()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("Set DATABASE_URL privately in backend/.env or the process environment.")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class HttpDatabaseConfigurationError(ValueError):
    """Unsupported HTTP connection configuration, without private diagnostics."""


class HttpDatabaseConnectionError(DBAPIError):
    """A typed DBAPI failure specifically during HTTP connection establishment."""


def http_engine_options(database_url, profile, environ=None):
    """Validate one libpq destination; never read/probe the DB or change the env.

    A hostname needs one explicit hostaddr, retaining host for verify-full TLS.
    An allowlist prevents service, multi-host, async/alternate driver and startup
    overrides from changing the approved bounds. Operational configuration is
    intentionally independent.
    """
    environ = os.environ if environ is None else environ
    bounds = profile.http_database_bounds

    def reject():
        raise HttpDatabaseConfigurationError("Unsupported HTTP database configuration.") from None

    try:
        url = make_url(database_url)
        if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
            reject()
        if any(char in url.host for char in (",", "/", "\\", " ", "\t", "\n")):
            reject()
        allowed = {"sslmode", "sslcert", "sslkey", "sslrootcert", "sslcrl", "sslcrldir",
                   "sslpassword", "sslsni", "ssl_min_protocol_version", "ssl_max_protocol_version",
                   "sslnegotiation", "sslcompression", "application_name", "hostaddr", "connect_timeout", "options"}
        if set(url.query) - allowed or any(not isinstance(v, str) for v in url.query.values()):
            reject()
        tls_values = {
            "sslmode": {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"},
            "sslsni": {"0", "1"}, "sslcompression": {"0", "1"},
            "sslnegotiation": {"postgres", "direct"},
            "ssl_min_protocol_version": {"TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"},
            "ssl_max_protocol_version": {"", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"},
        }
        if any(key in url.query and url.query[key] not in values for key, values in tls_values.items()):
            reject()
        if (url.query.get("connect_timeout", str(bounds.connect_timeout)) != str(bounds.connect_timeout)
                or url.query.get("options", bounds.startup_options) != bounds.startup_options):
            reject()
        # Explicit startup options override libpq defaults, but conflicting
        # inherited settings fail early instead of silently weakening policy.
        if environ.get("PGOPTIONS", "") not in {"", bounds.startup_options}:
            reject()
        if environ.get("PGCONNECT_TIMEOUT", "") not in {"", str(bounds.connect_timeout)}:
            reject()
        if any(environ.get(name) for name in ("PGSERVICE", "PGSERVICEFILE")):
            reject()
        if environ.get("PGTARGETSESSIONATTRS", "") not in {"", "any"}:
            reject()
        if environ.get("PGLOADBALANCEHOSTS", "") not in {"", "disable"}:
            reject()
        if any("," in environ.get(name, "") for name in ("PGHOST", "PGHOSTADDR", "PGPORT")):
            reject()
        address = url.query.get("hostaddr", url.host)
        ip_address(address)
        if environ.get("PGHOSTADDR", "") not in {"", address}:
            reject()
        port = url.port if url.port is not None else 5432
        if not 1 <= port <= 65535:
            reject()
    except (ArgumentError, ValueError, TypeError):
        reject()
    return url, {
        "connect_args": {"host": url.host, "hostaddr": address, "port": port,
                         "connect_timeout": bounds.connect_timeout,
                         "options": bounds.startup_options,
                         "target_session_attrs": "any", "load_balance_hosts": "disable"},
        "pool_size": bounds.pool_size, "max_overflow": bounds.max_overflow,
        "pool_timeout": bounds.pool_timeout,
        # Built-in pre-ping reconnects on failure. Our checkout event surfaces
        # the first failure instead, with the startup SQL limits already active.
        "pool_pre_ping": False,
    }


def _checkout_probe(http_engine, dbapi_connection, record, proxy):
    try:
        if not http_engine.dialect.do_ping(dbapi_connection):
            raise psycopg.OperationalError("HTTP checkout probe failed.")
    except psycopg.Error as exc:
        record.invalidate(exc)
        raise DBAPIError(None, None, exc, connection_invalidated=True) from None
    except BaseException:
        record.invalidate()
        raise


_http_factory = None
_http_factory_lock = Lock()


def http_session_factory():
    """Construct one isolated HTTP engine on first use; construction does no I/O."""
    global _http_factory
    with _http_factory_lock:
        if _http_factory is None:
            profile = server_profile()
            url, options = http_engine_options(DATABASE_URL, profile)
            http_engine = create_engine(url, **options)

            @event.listens_for(http_engine, "do_connect")
            def connect(dialect, record, args, params):
                # Recheck inherited options immediately before a physical
                # connection, including after an idle pool has been created.
                http_engine_options(url, profile)
                try:
                    return dialect.connect(*args, **params)
                except psycopg.Error as exc:
                    raise HttpDatabaseConnectionError(None, None, exc) from None

            @event.listens_for(http_engine, "checkout")
            def checkout(dbapi_connection, record, proxy):
                _checkout_probe(http_engine, dbapi_connection, record, proxy)

            _http_factory = sessionmaker(bind=http_engine, autoflush=False, autocommit=False,
                                        close_resets_only=False)
        return _http_factory


def HttpSessionLocal():
    return http_session_factory()()


_insights_factory = None
_insights_factory_lock = Lock()


def _insights_cursor_execution(query, connection=None):
    from app.financial_insights_contract import current_budget, require
    owner = current_budget.get()
    require(owner is not None)
    sql = query if isinstance(query, str) else query.as_string(connection)
    statement = sql.lstrip().upper()
    # psycopg dialect's checkout ping is the empty query ";".
    transaction = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    require(statement.strip() in {";", transaction} or statement.startswith(("SELECT", "SHOW")))
    owner.cursor(research=bool(getattr(owner, "research_transaction", False)
                              and statement.startswith("SELECT")))
    if statement.strip() == transaction:
        owner.research_transaction = True


class InsightsCursor(psycopg.Cursor):
    """Count client-cursor SQL, including raw checkout and initialization SQL."""
    def execute(self, query, params=None, **kwargs):
        _insights_cursor_execution(query, self.connection)
        return super().execute(query, params, **kwargs)

    def executemany(self, *args, **kwargs):
        from app.financial_insights_contract import require
        require(False)

    def copy(self, *args, **kwargs):
        from app.financial_insights_contract import require
        require(False)

    def stream(self, *args, **kwargs):
        from app.financial_insights_contract import require
        require(False)


def insights_session_factory():
    """One separate bounded pool; existing HTTP/operational options unchanged."""
    global _insights_factory
    from app.financial_insights_contract import current_budget, require

    budget = current_budget.get()
    require(budget is not None)
    budget.deadline(1)
    require(_insights_factory_lock.acquire(timeout=1), "INSIGHTS_DEADLINE_EXCEEDED")
    try:
        if _insights_factory is None:
            profile = server_profile()
            url, options = http_engine_options(DATABASE_URL, profile)
            # TypeInfo.fetch explicitly constructs psycopg.Cursor, bypassing
            # cursor_factory. Financial projections use no HSTORE; disable this
            # otherwise unaccounted initialization probe on this pool only.
            options.update(pool_size=1, max_overflow=0, pool_timeout=1, use_native_hstore=False)
            options["connect_args"].update(connect_timeout=2,
                options="-c statement_timeout=1500 -c lock_timeout=250", cursor_factory=InsightsCursor)
            bounded_engine = create_engine(url, **options)

            @event.listens_for(bounded_engine, "do_connect")
            def bounded_connect(dialect, record, args, params):
                owner = current_budget.get()
                require(owner is not None)
                owner.deadline(2)
                http_engine_options(url, profile)
                require(params.get("connect_timeout") == 2
                        and params.get("options") == "-c statement_timeout=1500 -c lock_timeout=250"
                        and params.get("cursor_factory") is InsightsCursor)
                try:
                    result = dialect.connect(*args, **params)
                    try:
                        owner.deadline()
                    except BaseException:
                        result.close()
                        raise
                    return result
                except psycopg.Error as exc:
                    raise HttpDatabaseConnectionError(None, None, exc) from None

            @event.listens_for(bounded_engine, "do_execute")
            def bounded_execute(cursor, sql, parameters, context):
                owner = current_budget.get()
                require(owner is not None)
                # Client-side Cursor fetchmany performs no additional FETCH SQL.
                # Named/server cursors would bypass this execution accounting.
                require(not isinstance(cursor, psycopg.ServerCursor))
                # Actual counting is in InsightsCursor.execute. The explicit
                # native-HSTORE cursor bypass is disabled above.

            @event.listens_for(bounded_engine, "do_executemany")
            def forbid_many(*args):
                require(False)

            @event.listens_for(bounded_engine, "checkout")
            def bounded_checkout(dbapi_connection, record, proxy):
                owner = current_budget.get()
                require(owner is not None)
                # do_ping's raw cursor is the same InsightsCursor factory.
                _checkout_probe(bounded_engine, dbapi_connection, record, proxy)
                owner.deadline()

            _insights_factory = sessionmaker(bind=bounded_engine, autoflush=False,
                autocommit=False, close_resets_only=False)
        return _insights_factory
    finally:
        _insights_factory_lock.release()


def InsightsSessionLocal():
    return insights_session_factory()()


def database_failure(exc):
    """Typed dependency classification only; never inspect diagnostic messages."""
    if isinstance(exc, PoolTimeoutError):
        return 503, "DATABASE_BUSY", "The research database is busy. Try again later."
    if not isinstance(exc, DBAPIError):
        return None
    original = exc.orig
    state = original.sqlstate if isinstance(original, psycopg.Error) else None
    if state in {"55P03", "53300"}:
        return 503, "DATABASE_BUSY", "The research database is busy. Try again later."
    if state == "57014":
        return 504, "DATABASE_TIMEOUT", "The research database request could not complete in time."
    unavailable_state = bool(state and state.startswith("08")) or state in {"57P01", "57P02", "57P03"}
    # Discarding a connection after a failed probe does not turn an unknown SQL
    # or programming error into a diagnosed dependency outage.
    if state and not unavailable_state:
        return None
    if (exc.connection_invalidated or unavailable_state
            or (state is None and isinstance(exc, HttpDatabaseConnectionError)
                and isinstance(original, psycopg.OperationalError))):
        return 503, "DATABASE_UNAVAILABLE", "The research database is unavailable. Try again later."
    return None
