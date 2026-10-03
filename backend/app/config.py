"""Load backend-local environment configuration without overriding process env."""

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_backend_env(path: Path | None = None) -> None:
    load_dotenv(path or BACKEND_ROOT / ".env", override=False)


load_backend_env()


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
