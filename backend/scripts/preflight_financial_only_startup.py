"""Explicit local financial-only configuration check, not runtime authorization.

The module is inert on import. The explicit CLI check normally loads private
backend configuration; run it only as part of a separately approved native run.
It opens no connection, starts no service and never loads an encoder. The full
private-runtime diagnostic and its fixed BLOCKED result remain unchanged.
"""
import contextlib
from ipaddress import ip_address
import json
import os
import sys


class ConfigurationRejected(Exception):
    def __init__(self, code):
        self.code = code


class _Discard:
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def _check_configuration():
    # Check actual process provenance before dotenv/config or operational imports.
    if (os.environ.get("FINLENS_SERVER_PROFILE") != "sec_readonly"
            or os.environ.get("FINLENS_FINANCIAL_ONLY") != "1"):
        raise ConfigurationRejected("EXPLICIT_FINANCIAL_ONLY_REQUIRED")

    from app.config import server_profile
    profile = server_profile()
    if (profile.name != "sec_readonly" or profile.financial_only is not True
            or profile.filing_research_enabled or profile.generation_allowed):
        raise ConfigurationRejected("FROZEN_PROFILE_MISMATCH")

    from app.release_policy import ReleaseModeBlocked, require_encoder
    try:
        require_encoder()
    except ReleaseModeBlocked:
        pass
    else:
        raise ConfigurationRejected("ENCODER_GUARD_MISMATCH")

    # Reuse existing connection-option validation; do not open a session or DB.
    from app.database import DATABASE_URL, http_engine_options
    _, options = http_engine_options(DATABASE_URL, profile)
    if not ip_address(options["connect_args"]["hostaddr"]).is_loopback:
        raise ConfigurationRejected("LOCAL_DATABASE_REQUIRED")

    # Cold import exercises the actual core dependency graph, without ASGI boot,
    # requests, schema inspection or model warmup. SQLAlchemy engines are lazy.
    from app.main import capabilities
    from starlette.responses import Response
    expected = {"research_mode": True, "ai_analysis_configured": False,
                "ai_analysis_enabled": False, "server_profile": "sec_readonly",
                "filing_research_enabled": False}
    response = Response()
    if capabilities(response).model_dump() != expected or response.headers.get("cache-control") != "no-store":
        raise ConfigurationRejected("CAPABILITY_MISMATCH")
    if any(name in sys.modules for name in (
            "sentence_transformers", "transformers", "torch", "huggingface_hub")):
        raise ConfigurationRejected("MODEL_IMPORT_DETECTED")
    return {"status": "CONFIGURATION_READY", "scope": "financial-only-local",
            "server_profile": "sec_readonly", "financial_only": True,
            "filing_research_enabled": False, "ai_analysis_enabled": False,
            "database_loopback": True, "encoder_imported": False}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args != ["--check-configuration"]:
        report = {"status": "BLOCKED", "scope": "financial-only-local",
                  "code": "EXPLICIT_CHECK_REQUIRED"}
    else:
        try:
            # Never echo dependency/configuration diagnostics or credentials.
            with contextlib.redirect_stdout(_Discard()), contextlib.redirect_stderr(_Discard()):
                report = _check_configuration()
        except ConfigurationRejected as exc:
            report = {"status": "BLOCKED", "scope": "financial-only-local", "code": exc.code}
        except Exception:
            report = {"status": "BLOCKED", "scope": "financial-only-local",
                      "code": "CONFIGURATION_UNVERIFIED"}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "CONFIGURATION_READY" else 1


def create_app():
    """Recheck inside the actual server process, before Uvicorn binds a socket.

    A successful earlier checker cannot attest a later process's configuration.
    This factory retains the existing app/router and all its admission guards.
    """
    try:
        with contextlib.redirect_stdout(_Discard()), contextlib.redirect_stderr(_Discard()):
            _check_configuration()
            from app.main import app
        return app
    except Exception:
        raise RuntimeError("Financial-only startup guard did not pass; private diagnostics suppressed.") from None


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
