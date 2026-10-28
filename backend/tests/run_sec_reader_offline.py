"""Guarded synthetic tests only; invoke with .venv/Scripts/python.exe -I -S -B.

Also loaded by fresh-process probes before importing application code. No server
or lifespan is started. Only stdlib-owned Windows asyncio wakeup pairs may connect.
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
for name in tuple(os.environ):
    if name.startswith(("FINLENS_", "OPENAI_", "PG")):
        os.environ.pop(name)
os.environ.update(DATABASE_URL="postgresql+psycopg://fixture:private@127.0.0.1/fixture",
                  FINLENS_SERVER_PROFILE="development", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                  PYTHON_DOTENV_DISABLED="1")


def forbidden(*args, **kwargs):
    raise AssertionError("Forbidden live dependency in SEC reader offline tests")


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
    signal_pair.active = True
    try:
        return original_pair(*args, **kwargs)
    finally:
        signal_pair.active = False


socket.socket.connect = connect
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden
socket.socketpair = socketpair
socket.getaddrinfo = forbidden

import dotenv
dotenv_calls = []


def synthetic_legacy_dotenv(path, *, override=False):
    """Record legacy calls; a reader call is always a test failure, never a no-op."""
    if os.environ.get("FINLENS_SERVER_PROFILE") == "sec_reader":
        forbidden()
    dotenv_calls.append((path, override))
    return False


dotenv.load_dotenv = synthetic_legacy_dotenv
dotenv.find_dotenv = forbidden
import psycopg
psycopg.connect = forbidden
psycopg.Connection.connect = classmethod(forbidden)
psycopg.AsyncConnection.connect = classmethod(forbidden)
# Permit SQLAlchemy's explicitly fake DBAPI fixtures, while both real drivers
# used by these suites remain blocked (including in-memory SQLite).
import sqlite3
import sqlite3.dbapi2
sqlite3.connect = forbidden
sqlite3.dbapi2.connect = forbidden
import openai
openai.OpenAI = forbidden
openai.AsyncOpenAI = forbidden

if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([*(sys.argv[1:] or ["tests/test_sec_reader.py"]),
                                  "-q", "--tb=short", "-p", "no:cacheprovider"]))
