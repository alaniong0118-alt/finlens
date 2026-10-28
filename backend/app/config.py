"""Load backend-local environment configuration without overriding process env."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Retain process provenance even if the environment changes after admission.
_PROCESS_PROFILE = os.environ.get("FINLENS_SERVER_PROFILE")


def load_backend_env(path: Path | None = None) -> None:
    if (_PROCESS_PROFILE == "sec_reader"
            or os.environ.get("FINLENS_SERVER_PROFILE") == "sec_reader"
            or getattr(globals().get("_SERVER_PROFILE"), "name", None) == "sec_reader"):
        raise ValueError("Dotenv loading is disabled for sec_reader.")
    load_dotenv(path or BACKEND_ROOT / ".env", override=False)


if _PROCESS_PROFILE != "sec_reader":
    load_backend_env()


@dataclass(frozen=True)
class HttpDatabaseBounds:
    connect_timeout: int
    pool_timeout: int
    statement_timeout_ms: int
    lock_timeout_ms: int
    pool_size: int = 5
    max_overflow: int = 0

    @property
    def startup_options(self) -> str:
        return (f"-c statement_timeout={self.statement_timeout_ms} "
                f"-c lock_timeout={self.lock_timeout_ms}")


@dataclass(frozen=True)
class ServerProfile:
    name: Literal["development", "sec_readonly", "sec_reader"]

    def __post_init__(self):
        if self.name not in {"development", "sec_readonly", "sec_reader"}:
            raise ValueError("Invalid FINLENS_SERVER_PROFILE; use development, sec_readonly or sec_reader.")

    @property
    def generation_allowed(self) -> bool:
        return self.name == "development"

    @property
    def http_database_bounds(self) -> HttpDatabaseBounds:
        if self.name == "sec_reader":
            raise ValueError("HTTP database access is disabled for sec_reader.")
        if self.name == "development":
            return HttpDatabaseBounds(5, 5, 30000, 5000, max_overflow=5)
        return HttpDatabaseBounds(3, 2, 10000, 2000)


# Resolve exactly once after legacy dotenv (reader imports never load dotenv),
# before importers initialize engines/models.
# An explicitly empty value is a configuration error, not a development fallback.
_SERVER_PROFILE = ServerProfile(os.environ.get("FINLENS_SERVER_PROFILE", "development"))
if _SERVER_PROFILE.name == "sec_reader" and _PROCESS_PROFILE != "sec_reader":
    raise ValueError("sec_reader requires explicit process FINLENS_SERVER_PROFILE=sec_reader.")


def server_profile() -> ServerProfile:
    return _SERVER_PROFILE


def openai_model() -> str:
    return (
        os.getenv("OPENAI_MODEL")
        or os.getenv("FINLENS_LLM_MODEL")
        or "gpt-6-astra"
    ).strip()


def openai_reasoning_effort() -> str:
    return (
        os.getenv("OPENAI_REASONING_EFFORT")
        or os.getenv("FINLENS_LLM_REASONING_EFFORT")
        or "medium"
    ).strip()
