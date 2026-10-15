"""Guarded Increment 2 tests; no private dotenv, physical DB or external sockets."""
import os
from pathlib import Path
import socket
import sys

os.environ["DATABASE_URL"] = "postgresql+psycopg://fixture:private@127.0.0.1/fixture"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["FINLENS_SERVER_PROFILE"] = "development"
# Hostile env cases are injected explicitly by tests, not inherited from a
# developer's shell. These changes are confined to this test process.
for name in tuple(os.environ):
    if name.startswith("PG"):
        os.environ.pop(name)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def bomb(*args, **kwargs):
    raise AssertionError("Physical DB and external sockets forbidden in Increment 2 tests")


original_connect = socket.socket.connect
socketpair_code = getattr(getattr(socket, "_fallback_socketpair", None), "__code__", None)


def guarded_connect(self, address):
    if (socketpair_code is not None and sys._getframe(1).f_code is socketpair_code
            and isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}):
        return original_connect(self, address)
    bomb()


socket.socket.connect = guarded_connect
socket.socket.connect_ex = bomb
socket.create_connection = bomb
import psycopg
psycopg.connect = bomb
psycopg.Connection.connect = bomb

if __name__ == "__main__":
    import pytest
    targets = sys.argv[1:] or ["tests/test_http_database_runtime.py"]
    raise SystemExit(pytest.main(["-q", "--tb=short", "-p", "no:cacheprovider", *targets]))
