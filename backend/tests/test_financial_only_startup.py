"""Synthetic startup checks; use run_dep01a2_increment2_offline.py, no real DB/config."""
import builtins
import io
import json
from pathlib import Path
import socket
import sys

import pytest

from scripts import preflight_financial_only_startup as check


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", "sec_readonly")
    monkeypatch.setenv("FINLENS_FINANCIAL_ONLY", "1")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://fixture:synthetic@127.0.0.1/fixture")
    for name in tuple(__import__('os').environ):
        if name.startswith("PG"):
            monkeypatch.delenv(name)

    def forbidden(*args, **kwargs):
        raise AssertionError("Physical DB/network forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    for module, name in ((builtins, "open"), (io, "open")):
        original = getattr(module, name)
        def guarded(path, *args, _original=original, **kwargs):
            if isinstance(path, (str, Path)) and Path(path).name.startswith('.env'):
                raise AssertionError("Private dotenv read forbidden")
            return _original(path, *args, **kwargs)
        monkeypatch.setattr(module, name, guarded)


def test_actual_cold_core_import_no_private_file_database_or_model(capsys):
    # Run this file alone: no earlier app/config import can impersonate cold boot.
    assert "app.config" not in sys.modules
    assert check.main(["--check-configuration"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"status": "CONFIGURATION_READY", "scope": "financial-only-local",
        "server_profile": "sec_readonly", "financial_only": True,
        "filing_research_enabled": False, "ai_analysis_enabled": False,
        "database_loopback": True, "encoder_imported": False}
    assert not any(name in sys.modules for name in ("torch", "transformers", "sentence_transformers", "huggingface_hub"))
    from app.main import app
    assert check.create_app() is app  # Same app/router; no server/socket startup.


@pytest.mark.parametrize("profile,flag", [(None, "1"), ("development", "1"), ("sec_reader", "1"),
    ("sec_readonly", None), ("sec_readonly", "0"), ("sec_readonly", "true"), ("sec_readonly", " 1")])
def test_process_opt_in_denied_before_any_app_import(monkeypatch, profile, flag):
    for name, value in (("FINLENS_SERVER_PROFILE", profile), ("FINLENS_FINANCIAL_ONLY", flag)):
        if value is None: monkeypatch.delenv(name, raising=False)
        else: monkeypatch.setenv(name, value)
    real = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith("app"), "No app/dotenv import before admission"
        return real(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    with pytest.raises(check.ConfigurationRejected) as failure:
        check._check_configuration()
    assert failure.value.code == "EXPLICIT_FINANCIAL_ONLY_REQUIRED"


@pytest.mark.parametrize("profile,flag", [("development", False), ("sec_readonly", False)])
def test_frozen_profile_must_match_process(monkeypatch, profile, flag):
    from app import config
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile(profile, flag))
    with pytest.raises(check.ConfigurationRejected) as failure:
        check._check_configuration()
    assert failure.value.code == "FROZEN_PROFILE_MISMATCH"


@pytest.mark.parametrize("url", ["postgresql+psycopg://fixture:synthetic@203.0.113.1/fixture",
    "postgresql+psycopg://fixture:synthetic@[2001:db8::1]/fixture"])
def test_remote_database_refused_without_connecting(monkeypatch, url):
    from app import database
    monkeypatch.setattr(database, "DATABASE_URL", url)
    with pytest.raises(check.ConfigurationRejected) as failure:
        check._check_configuration()
    assert failure.value.code == "LOCAL_DATABASE_REQUIRED"


@pytest.mark.parametrize("url", ["", "sqlite://", "postgresql+psycopg://fixture:secret@127.0.0.1/fixture?service=secret"])
def test_invalid_database_configuration_is_sanitized(monkeypatch, capsys, url):
    from app import database
    monkeypatch.setattr(database, "DATABASE_URL", url)
    assert check.main(["--check-configuration"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "CONFIGURATION_UNVERIFIED"


def test_encoder_guard_cannot_silently_allow(monkeypatch):
    from app import release_policy
    monkeypatch.setattr(release_policy, "require_encoder", lambda: None)
    with pytest.raises(check.ConfigurationRejected) as failure:
        check._check_configuration()
    assert failure.value.code == "ENCODER_GUARD_MISMATCH"


@pytest.mark.parametrize("name", ["torch", "transformers", "sentence_transformers", "huggingface_hub"])
def test_model_import_is_not_configuration_ready(monkeypatch, name):
    monkeypatch.setitem(sys.modules, name, object())
    with pytest.raises(check.ConfigurationRejected) as failure:
        check._check_configuration()
    assert failure.value.code == "MODEL_IMPORT_DETECTED"


def test_capabilities_must_match_and_be_uncached(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "capabilities", lambda response: type('Reply', (), {'model_dump': lambda self: {}})())
    with pytest.raises(check.ConfigurationRejected) as failure:
        check._check_configuration()
    assert failure.value.code == "CAPABILITY_MISMATCH"


@pytest.mark.parametrize("args", [[], ["--help"], ["--check-configuration", "--skip-checks"]])
def test_cli_requires_exact_explicit_check_before_loading(monkeypatch, capsys, args):
    monkeypatch.setattr(check, "_check_configuration", lambda: pytest.fail("Unexpected config read"))
    assert check.main(args) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "EXPLICIT_CHECK_REQUIRED"


def test_import_diagnostics_and_exception_are_never_exposed(monkeypatch, capsys):
    def broken():
        print("SYNTHETIC_SECRET")
        print("SYNTHETIC_SECRET", file=sys.stderr)
        raise ValueError("SYNTHETIC_SECRET")
    monkeypatch.setattr(check, "_check_configuration", broken)
    assert check.main(["--check-configuration"]) == 1
    result = capsys.readouterr()
    assert "SYNTHETIC_SECRET" not in result.out + result.err
    assert result.err == ""
    assert json.loads(result.out)["status"] == "BLOCKED"


def test_actual_server_factory_rechecks_and_suppresses_failure(monkeypatch):
    calls = []
    def refused():
        calls.append(True)
        raise ValueError("SYNTHETIC_SECRET")
    monkeypatch.setattr(check, "_check_configuration", refused)
    with pytest.raises(RuntimeError) as failure:
        check.create_app()
    assert calls == [True]
    assert "SYNTHETIC_SECRET" not in str(failure.value)
    assert failure.value.__suppress_context__ is True
