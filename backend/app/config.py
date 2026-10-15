"""Load backend-local environment configuration without overriding process env."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_backend_env(path: Path | None = None) -> None:
    load_dotenv(path or BACKEND_ROOT / ".env", override=False)


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
    name: Literal["development", "sec_readonly"]

    def __post_init__(self):
        if self.name not in {"development", "sec_readonly"}:
            raise ValueError("Invalid FINLENS_SERVER_PROFILE; use development or sec_readonly.")

    @property
    def generation_allowed(self) -> bool:
        return self.name == "development"

    @property
    def http_database_bounds(self) -> HttpDatabaseBounds:
        if self.name == "development":
            return HttpDatabaseBounds(5, 5, 30000, 5000, max_overflow=5)
        return HttpDatabaseBounds(3, 2, 10000, 2000)


# Resolve exactly once after dotenv, before importers initialize engines/models.
# An explicitly empty value is a configuration error, not a development fallback.
_SERVER_PROFILE = ServerProfile(os.environ.get("FINLENS_SERVER_PROFILE", "development"))


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
