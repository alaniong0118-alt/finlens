"""Internal worker for Assess-FinLens-AaplFacts.ps1; inert on import.

Only the PowerShell entry has an independent whole-worker deadline. This module
does not authorize a live run; --allow-network requires separate operator consent.
"""
import contextlib
from contextvars import ContextVar
from ipaddress import ip_address
import json
import os
import sys
from urllib import request as urllib_request

CIK = "0000320193"
SCOPE = "aapl-facts-dry-run"
READ_ONLY = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
MAX_RECEIPT = 64 * 1024
STAGES = ("not_started", "process_admitted", "development_verified", "network_admitted",
          "database_configured", "schema_verified", "source_admitted", "source_returned",
          "assessment_completed")
REFUSAL_CODES = {"EXPLICIT_NETWORK_CONSENT_REQUIRED", "EXPLICIT_DEVELOPMENT_REQUIRED",
                 "DEVELOPMENT_REQUIRED", "LOCAL_DATABASE_REQUIRED", "READ_ONLY_UNVERIFIED",
                 "UNEXPECTED_DATABASE_OPERATION", "CONNECTION_OPTIONS_CHANGED",
                 "PROXY_CONFIGURATION_UNSUPPORTED", "PROXY_CONFIGURATION_UNVERIFIED",
                 "AAPL_IDENTITY_MISMATCH", "CANONICAL_ASSESSMENT_FAILED",
                 "INVALID_CANONICAL_RESULT", "ASSESSMENT_UNVERIFIED", "OUTPUT_LIMIT"}
_progress = ContextVar("aapl_assessment_progress", default=None)
_cleanup_active = ContextVar("aapl_assessment_cleanup", default=False)
SQLSTATE_CATEGORIES = {
    "28P01": "DATABASE_AUTH_REJECTED", "28000": "DATABASE_AUTH_REJECTED",
    "3D000": "DATABASE_TARGET_MISSING", "08000": "DATABASE_CONNECTION_FAILED",
    "08001": "DATABASE_CONNECTION_FAILED", "08003": "DATABASE_CONNECTION_FAILED",
    "08004": "DATABASE_CONNECTION_FAILED", "08006": "DATABASE_CONNECTION_FAILED",
    "08007": "DATABASE_CONNECTION_FAILED", "08P01": "DATABASE_CONNECTION_FAILED",
    "53300": "DATABASE_CAPACITY", "25006": "READ_ONLY_REJECTED_OPERATION",
    "42501": "DATABASE_PERMISSION", "42P01": "SCHEMA_OBJECT_MISSING",
    "42703": "SCHEMA_OBJECT_MISSING", "3F000": "SCHEMA_OBJECT_MISSING",
    "57014": "QUERY_CANCELED_OR_TIMEOUT", "55P03": "LOCK_NOT_AVAILABLE",
}


def _classify_failure(error):
    # Inspect only known types/modules already loaded. Early admission failures
    # must not import app/config/DB merely to classify an error. Never stringify.
    category, kind, state = "UNCLASSIFIED", "other", None
    setup = sys.modules.get("scripts.setup_demo")
    sa = sys.modules.get("sqlalchemy.exc")
    pg = sys.modules.get("psycopg")
    if isinstance(error, AssessmentRejected):
        category, kind = "LOCAL_GUARD_REFUSAL", "AssessmentRejected"
    elif setup is not None and isinstance(error, setup.DemoSetupError):
        category, kind = "SCHEMA_REQUIREMENT_UNSATISFIED", "DemoSetupError"
    elif sa is not None and isinstance(error, sa.TimeoutError):
        category, kind = "POOL_TIMEOUT", "SQLAlchemyTimeoutError"
    else:
        original = error.orig if sa is not None and isinstance(error, sa.DBAPIError) else error
        if pg is not None and isinstance(original, pg.Error):
            operational = isinstance(original, pg.OperationalError)
            kind = "PsycopgOperationalError" if operational else "PsycopgError"
            raw_state = original.sqlstate
            if type(raw_state) is str and raw_state in SQLSTATE_CATEGORIES:
                state, category = raw_state, SQLSTATE_CATEGORIES[raw_state]
            else:
                category = "DATABASE_CONNECTION_UNVERIFIED" if operational and raw_state is None else "DATABASE_ERROR_UNCLASSIFIED"
        elif sa is not None and isinstance(error, sa.DBAPIError):
            category, kind = "DATABASE_ERROR_UNCLASSIFIED", "SQLAlchemyDBAPIError"
        elif sa is not None and isinstance(error, sa.ArgumentError):
            category, kind = "CONFIGURATION_INVALID", "SQLAlchemyArgumentError"
        elif sa is not None and isinstance(error, sa.InvalidRequestError):
            category, kind = "API_STATE_ERROR", "SQLAlchemyInvalidRequestError"
        elif isinstance(error, ImportError):
            category, kind = "DEPENDENCY_UNAVAILABLE", "ImportError"
        elif isinstance(error, TypeError):
            category, kind = "PROGRAMMING_ERROR", "TypeError"
        elif isinstance(error, ValueError):
            category, kind = "VALUE_ERROR", "ValueError"
    return {"category": category, "exception_type": kind, "sqlstate": state}


def _remember_failure(error, *, cleanup=False):
    progress = _progress.get()
    key = "cleanup_failure" if cleanup else "failure"
    if progress is not None and progress[key] is None:
        try:
            progress[key] = _classify_failure(error)
        except BaseException:
            progress[key] = {"category": "UNCLASSIFIED", "exception_type": "other", "sqlstate": None}


def _cleanup_call(callback):
    token = _cleanup_active.set(True)
    try:
        return callback()
    finally:
        _cleanup_active.reset(token)


def _confirmed(stage):
    progress = _progress.get()
    if progress is not None:
        if stage not in STAGES or STAGES.index(stage) < STAGES.index(progress["stage"]):
            raise RuntimeError("Invalid assessment progress")
        progress["stage"] = stage


class AssessmentRejected(Exception):
    def __init__(self, code):
        super().__init__(code)
        # Canonical refresh catches source/DB exceptions. Retain only the first
        # local allowlisted refusal, so its generic failure cannot erase it.
        progress = _progress.get()
        if _cleanup_active.get():
            _remember_failure(self, cleanup=True)
            return
        if progress is not None and progress.get("refusal") is None and code in REFUSAL_CODES:
            progress["refusal"] = code
        _remember_failure(self)


class _Discard:
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def _process_admission():
    # Reject before config/dotenv or operational imports. Never set a profile.
    if (os.environ.get("FINLENS_SERVER_PROFILE") != "development"
            or os.environ.get("FINLENS_FINANCIAL_ONLY", "0") != "0"):
        raise AssessmentRejected("EXPLICIT_DEVELOPMENT_REQUIRED")


def _connection_options(database_url, profile, environ=None):
    from app.database import http_engine_options
    if profile.name != "development" or profile.financial_only:
        raise AssessmentRejected("DEVELOPMENT_REQUIRED")
    url, options = http_engine_options(database_url, profile, environ)
    if not ip_address(options["connect_args"]["hostaddr"]).is_loopback:
        raise AssessmentRejected("LOCAL_DATABASE_REQUIRED")
    options["connect_args"]["options"] += (
        " -c default_transaction_read_only=on"
        " -c idle_in_transaction_session_timeout=30000")
    options.update(pool_size=2, max_overflow=0)
    return url, options


def _begin_read_only(connection):
    try:
        connection.exec_driver_sql(READ_ONLY)
        if connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() != "on":
            raise AssessmentRejected("READ_ONLY_UNVERIFIED")
    except BaseException as error:
        _remember_failure(error)
        raise


def _sql_guard(connection, cursor, statement, parameters, context, executemany):
    # Fixed canonical queries only; this is additional fail-closed protection,
    # not a SQL parser or a substitute for server-enforced read-only mode.
    sql = statement.strip().upper()
    if executemany or not (sql == READ_ONLY or sql.startswith(("SELECT ", "SHOW "))):
        raise AssessmentRejected("UNEXPECTED_DATABASE_OPERATION")


def _make_factory(database_url, profile):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    url, options = _connection_options(database_url, profile)
    engine = create_engine(url, **options)

    @event.listens_for(engine, "do_connect")
    def connect(dialect, record, args, params):
        # Revalidate inherited libpq settings immediately before every connect.
        _, checked = _connection_options(database_url, profile)
        if any(params.get(key) != value for key, value in checked["connect_args"].items()):
            raise AssessmentRejected("CONNECTION_OPTIONS_CHANGED")
        try:
            return dialect.connect(*args, **params)
        except BaseException as error:
            _remember_failure(error)
            raise

    event.listen(engine, "begin", _begin_read_only)
    event.listen(engine, "before_cursor_execute", _sql_guard)
    # Keep .kw['bind']: canonical coordinator must take its PostgreSQL lock.
    return sessionmaker(bind=engine, autoflush=False, autocommit=False,
                        close_resets_only=False)


def _network_admission():
    # HTTPX uses urllib.request.getproxies(), including Windows/macOS platform
    # fallback when proxy env is empty. Use that public discovery path too.
    # Conservatively reject configured HTTP proxies even if NO_PROXY could bypass
    # them; never remove settings or force a different route. No values are logged.
    if any(value for name, value in os.environ.items()
           if name.lower() in {"http_proxy", "https_proxy", "all_proxy"}):
        raise AssessmentRejected("PROXY_CONFIGURATION_UNSUPPORTED")
    try:
        proxies = urllib_request.getproxies()
        if (type(proxies) is not dict or any(type(key) is not str or type(value) is not str
                                            for key, value in proxies.items())):
            raise ValueError()
    except Exception:
        raise AssessmentRejected("PROXY_CONFIGURATION_UNVERIFIED") from None
    if any(value for key, value in proxies.items() if key.lower() in {"http", "https", "all"}):
        raise AssessmentRejected("PROXY_CONFIGURATION_UNSUPPORTED")
    from app.sec_client import get_sec_headers
    get_sec_headers()  # Validate contact without printing or returning it.


def _aapl_facts(cik):
    if cik != CIK:
        raise AssessmentRejected("AAPL_IDENTITY_MISMATCH")
    # Recheck both process provenance and frozen guard at the source boundary.
    _process_admission()
    _network_admission()
    _confirmed("source_admitted")  # Permission verified; NOT an HTTP-attempt count.
    from app.sec_client import get_company_facts
    result = get_company_facts(CIK)
    _confirmed("source_returned")  # Parsed payload returned, not financial admission.
    return result


def _sanitized_result(report):
    # Do not serialize arbitrary canonical errors, source bodies or DB text.
    if (report.get("error") is not None or report.get("dry_run") is not True
            or len(report.get("companies", [])) != 1):
        raise AssessmentRejected("CANONICAL_ASSESSMENT_FAILED")
    row = report["companies"][0]
    if (row.get("ticker") != "AAPL" or row.get("stream") != "facts"
            or row.get("status") not in {"no_change", "would_update"}
            or row.get("commit_outcome") != "not_attempted"
            or row.get("error") is not None or row.get("pending_targets")
            or row.get("facts_inserted") != 0 or row.get("filings_published") != 0):
        raise AssessmentRejected("CANONICAL_ASSESSMENT_FAILED")
    for key in ("would_insert", "version_before", "version_after"):
        if type(row.get(key)) is not int or not 0 <= row[key] <= 2**63 - 1:
            raise AssessmentRejected("INVALID_CANONICAL_RESULT")
    if (row["version_before"] != row["version_after"]
            or (row["status"] == "would_update") != (row["would_insert"] > 0)):
        raise AssessmentRejected("INVALID_CANONICAL_RESULT")
    return {"status": "ASSESSED", "scope": SCOPE, "ticker": "AAPL", "company_cik": CIK,
            "dry_run": True, "outcome": row["status"], "would_insert": row["would_insert"],
            "version_before": row["version_before"], "version_after": row["version_after"],
            "facts_inserted": 0, "filings_published": 0}


def _schema_readiness(factory):
    from scripts.setup_demo import check_schema
    session = factory()
    primary = None
    try:
        check_schema(session)  # Same complete schema requirements; no migrations.
    except BaseException as error:
        primary = error
        _remember_failure(error)
        raise
    finally:
        try:
            _cleanup_call(session.close)
        except BaseException as cleanup:
            _remember_failure(cleanup, cleanup=True)
            try:
                _cleanup_call(session.invalidate)
            except BaseException:
                pass  # First bounded cleanup failure retained; worker exits.
            if primary is None:
                _remember_failure(cleanup)
                raise


def _assess():
    _process_admission()
    _confirmed("process_admitted")
    from app.config import server_profile
    from app.release_policy import require_development
    require_development()  # Same frozen development-only guard as canonical CLI.
    profile = server_profile()
    _confirmed("development_verified")
    _network_admission()
    _confirmed("network_admitted")
    from app.database import DATABASE_URL
    factory = _make_factory(DATABASE_URL, profile)
    _confirmed("database_configured")  # Engine constructed, no native-readiness claim.
    primary = None
    try:
        _schema_readiness(factory)
        _confirmed("schema_verified")
        from app.refresh_contracts import RefreshRequest
        from app.refresh_service import refresh
        request = RefreshRequest(tickers=["AAPL"], stream="facts", dry_run=True,
                                 max_seconds=300, max_run_seconds=600)
        return _sanitized_result(refresh(factory, request, facts_loader=_aapl_facts))
    except BaseException as error:
        primary = error
        _remember_failure(error)
        raise
    finally:
        try:
            _cleanup_call(factory.kw["bind"].dispose)
        except BaseException as cleanup:
            _remember_failure(cleanup, cleanup=True)
            if primary is None:
                _remember_failure(cleanup)
                raise


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    progress = {"stage": "not_started", "refusal": None, "failure": None, "cleanup_failure": None}
    token = _progress.set(progress)
    report = {"protocol": 2, "status": "BLOCKED", "scope": SCOPE,
              "code": "EXPLICIT_NETWORK_CONSENT_REQUIRED", "result": None,
              "last_confirmed_stage": "not_started", "sec_http_attempts": None,
              "failure": None, "cleanup_failure": None}
    try:
        if args == ["--allow-network"]:
            try:
                with contextlib.redirect_stdout(_Discard()), contextlib.redirect_stderr(_Discard()):
                    result = _assess()
                if progress["refusal"] is not None:
                    raise AssessmentRejected(progress["refusal"])
                if progress["failure"] is not None or progress["cleanup_failure"] is not None:
                    raise AssessmentRejected("ASSESSMENT_UNVERIFIED")
                _confirmed("assessment_completed")
                report.update(status="ASSESSED", code=None, result=result)
            except AssessmentRejected as exc:
                _remember_failure(exc)
                safe_code = exc.args[0] if len(exc.args) == 1 and type(exc.args[0]) is str and exc.args[0] in REFUSAL_CODES else "ASSESSMENT_UNVERIFIED"
                report["code"] = progress["refusal"] or safe_code
            except (Exception, KeyboardInterrupt) as error:
                _remember_failure(error)
                report["code"] = progress["refusal"] or "ASSESSMENT_UNVERIFIED"
        report["last_confirmed_stage"] = progress["stage"]
        report.update(failure=progress["failure"], cleanup_failure=progress["cleanup_failure"])
        # The canonical HTTP client is not instrumented. Null stays unknown even
        # after source_returned; do not count loader calls or infer from duration.
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_RECEIPT:
            report.update(status="BLOCKED", code="OUTPUT_LIMIT", result=None,
                          failure={"category": "LOCAL_GUARD_REFUSAL", "exception_type": "AssessmentRejected", "sqlstate": None})
            encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
    finally:
        _progress.reset(token)
    print(encoded)
    return 0 if report["status"] == "ASSESSED" else 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    # The supported supervisor uses -I: admit only this checkout's backend path,
    # not PYTHONPATH, user site packages or a caller-selected working directory.
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
