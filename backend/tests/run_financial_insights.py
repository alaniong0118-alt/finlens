"""Run only explicitly selected offline tests with isolation BEFORE app imports.

Usage from backend: .venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py
"""
import builtins
import importlib.abc
import io
import os
from pathlib import Path
import socket
import sys
from threading import local

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / ".venv" / "Lib" / "site-packages"), str(ROOT), str(ROOT / "tests")]
os.environ.update(DATABASE_URL="postgresql+psycopg://fixture:fixture@127.0.0.1/fixture",
                  FINLENS_SERVER_PROFILE="development", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                  PYTHON_DOTENV_DISABLED="1")


def forbidden(*args, **kwargs):
    raise AssertionError("Prohibited live dependency")


def protected_open(original):
    def guarded(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(path)).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                forbidden()
        return original(path, *args, **kwargs)
    return guarded


builtins.open = protected_open(builtins.open)
io.open = protected_open(io.open)
os.open = protected_open(os.open)


class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"torch", "sentence_transformers", "transformers", "tensorflow"}:
            forbidden()


sys.meta_path.insert(0, NoModels())
signal_pair = local()
original_connect, original_pair = socket.socket.connect, socket.socketpair


def connect(sock, address):
    if not getattr(signal_pair, "active", False):
        forbidden()
    return original_connect(sock, address)


def socketpair(*args, **kwargs):
    # Windows' stdlib builds asyncio's owned wakeup socket pair with connect.
    # This exception is confined to the stdlib call, never application network I/O.
    signal_pair.active = True
    try:
        return original_pair(*args, **kwargs)
    finally:
        signal_pair.active = False


socket.socket.connect = connect
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden
socket.socketpair = socketpair

import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
dotenv.find_dotenv = forbidden
import psycopg
psycopg.connect = forbidden
psycopg.Connection.connect = classmethod(forbidden)
psycopg.AsyncConnection.connect = classmethod(forbidden)


from app import answer_service, embedding_service, sec_client, sec_evidence_adapter
answer_service._get_openai_client = forbidden
embedding_service._get_model = forbidden
embedding_service._get_model.cache_clear = lambda: None
embedding_service._load_model = forbidden
sec_client._sec_get = forbidden
sec_evidence_adapter._read = forbidden
sec_evidence_adapter.load_production_evidence = forbidden

import pytest
raise SystemExit(pytest.main([*(sys.argv[1:] or ["tests/test_financial_insights.py"]),
                              "-q", "-p", "no:cacheprovider"]))
