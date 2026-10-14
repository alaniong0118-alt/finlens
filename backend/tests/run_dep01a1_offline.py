"""Run only DEP-01A1 synthetic acceptance with private dotenv/network disabled."""
import os
from pathlib import Path
import socket
import sys

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["FINLENS_SERVER_PROFILE"] = "development"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_connect = socket.socket.connect
_socketpair_code = getattr(getattr(socket, "_fallback_socketpair", None), "__code__", None)


def guarded_connect(self, address):
    # Windows asyncio's internal wakeup pair uses loopback TCP. Admit only the
    # stdlib socketpair callsite, never general loopback/DB/provider connections.
    if (_socketpair_code is not None and sys._getframe(1).f_code is _socketpair_code
            and isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}):
        return _connect(self, address)
    raise AssertionError("External sockets are forbidden in DEP-01A1 acceptance")


guarded_connect._finlens_offline_guard = True
socket.socket.connect = guarded_connect
socket.socket.connect_ex = lambda *a, **k: (_ for _ in ()).throw(AssertionError("External sockets forbidden"))
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(AssertionError("External sockets forbidden"))

if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main(["-q", "--tb=short", "-p", "no:cacheprovider",
                                 "tests/test_release_profile.py", "tests/test_capabilities.py"]))
