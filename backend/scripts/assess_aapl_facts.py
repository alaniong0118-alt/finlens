"""Internal worker for Assess-FinLens-AaplFacts.ps1; inert on import.

Only the PowerShell entry has an independent whole-worker deadline. This module
does not authorize a live run; --allow-network requires separate operator consent.
"""
import contextlib
from ipaddress import ip_address
import json
import os
import sys
from urllib import request as urllib_request

CIK = "0000320193"
SCOPE = "aapl-facts-dry-run"
READ_ONLY = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
MAX_RECEIPT = 64 * 1024


class AssessmentRejected(Exception):
    pass


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
    connection.exec_driver_sql(READ_ONLY)
    if connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() != "on":
        raise AssessmentRejected("READ_ONLY_UNVERIFIED")


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
        return dialect.connect(*args, **params)

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
    from app.sec_client import get_company_facts
    return get_company_facts(CIK)


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


def _assess():
    _process_admission()
    from app.config import server_profile
    from app.release_policy import require_development
    require_development()  # Same frozen development-only guard as canonical CLI.
    profile = server_profile()
    _network_admission()
    from app.database import DATABASE_URL
    factory = _make_factory(DATABASE_URL, profile)
    try:
        from scripts.setup_demo import check_schema
        with factory() as session:
            check_schema(session)  # Same schema inspection, no migrations.
        from app.refresh_contracts import RefreshRequest
        from app.refresh_service import refresh
        request = RefreshRequest(tickers=["AAPL"], stream="facts", dry_run=True,
                                 max_seconds=300, max_run_seconds=600)
        return _sanitized_result(refresh(factory, request, facts_loader=_aapl_facts))
    finally:
        factory.kw["bind"].dispose()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    report = {"status": "BLOCKED", "scope": SCOPE, "code": "EXPLICIT_NETWORK_CONSENT_REQUIRED"}
    if args == ["--allow-network"]:
        try:
            with contextlib.redirect_stdout(_Discard()), contextlib.redirect_stderr(_Discard()):
                report = _assess()
        except AssessmentRejected as exc:
            # Only this module's constant codes may reach the output boundary.
            allowed = {"EXPLICIT_DEVELOPMENT_REQUIRED", "DEVELOPMENT_REQUIRED",
                       "LOCAL_DATABASE_REQUIRED", "READ_ONLY_UNVERIFIED",
                       "UNEXPECTED_DATABASE_OPERATION", "CONNECTION_OPTIONS_CHANGED",
                       "PROXY_CONFIGURATION_UNSUPPORTED", "PROXY_CONFIGURATION_UNVERIFIED",
                       "AAPL_IDENTITY_MISMATCH",
                       "CANONICAL_ASSESSMENT_FAILED", "INVALID_CANONICAL_RESULT"}
            report["code"] = str(exc) if str(exc) in allowed else "ASSESSMENT_UNVERIFIED"
        except (Exception, KeyboardInterrupt):
            report["code"] = "ASSESSMENT_UNVERIFIED"
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_RECEIPT:
        encoded = '{"status":"BLOCKED","scope":"aapl-facts-dry-run","code":"OUTPUT_LIMIT"}'
    print(encoded)
    return 0 if report["status"] == "ASSESSED" else 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    # The supported supervisor uses -I: admit only this checkout's backend path,
    # not PYTHONPATH, user site packages or a caller-selected working directory.
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
