"""Local CLI acceptance without writing temporary data or contacting providers."""
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import inspect_market_history as cli


BACKEND = Path(__file__).resolve().parents[1]
PAYLOAD = BACKEND / "tests/fixtures/tiingo_eod/ordinary.json"
CONTEXT = BACKEND / "tests/fixtures/market_history/synthetic-context.json"


def args(fmt="json"):
    return ["--payload", str(PAYLOAD), "--context", str(CONTEXT), "--format", fmt]


def test_cli_json_and_table_actual_local_files(capsys):
    assert cli.main(args()) == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert captured.err == ""
    assert [row["unadjusted_close"] for row in output["rows"]] == ["100", "105"]
    assert output["input_kind"] == "synthetic" and output["trusted_custody"] is False
    assert cli.main(args("table")) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Session date | Unadjusted close | Declared currency | Observation state" in captured.out
    assert "2026-01-05 | 100 | USD | present" in captured.out
    assert "returns: unavailable" in captured.out and "available (declared): null" in captured.out
    assert "Declared symbol: FICT" in captured.out and "timezone: America/New_York" in captured.out
    assert "Response SHA256:" in captured.out and "Publication manifest SHA256:" in captured.out


@pytest.mark.parametrize("path", ["https://secret.invalid/private", "//secret-server/share/file.json",
    "\\\\secret-server\\share\\file.json", "nonexistent-secret-name.json", "."])
def test_bad_local_paths_are_rejected_without_echo_or_stdout(path, capsys):
    supplied = args()
    supplied[1] = path
    assert cli.main(supplied) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ")
    assert path not in captured.err and "secret" not in captured.err and "Traceback" not in captured.err


@pytest.mark.parametrize("argv", [[], ["--payload", "sensitive-path"], ["--token", "sensitive-token"],
                                 args() + ["--format", "sensitive-value"]])
def test_argument_errors_do_not_echo_input(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: invalid_arguments\n"


def test_malformed_context_error_is_sanitized_without_partial_output(monkeypatch, capsys):
    original = cli._read_local
    monkeypatch.setattr(cli, "_read_local", lambda path, limit: b'{"secret-token":' if str(path) == str(CONTEXT)
                        else original(path, limit))
    assert cli.main(args()) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: invalid_context\n"


@pytest.mark.parametrize("limit", [cli.MAX_RESPONSE_BYTES, cli.MAX_CONTEXT_BYTES])
def test_regular_file_reader_reads_only_limit_plus_one_and_rejects_overflow(monkeypatch, limit):
    reads = []
    class Stream(io.BytesIO):
        def fileno(self):
            return 12345
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)
    monkeypatch.setattr(Path, "open", lambda *a, **k: Stream(b"x" * (limit + 100)))
    before = PAYLOAD.stat()
    monkeypatch.setattr(cli.os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG,
                        st_dev=before.st_dev, st_ino=before.st_ino))
    with pytest.raises(cli.MarketContractError, match="invalid_local_file_bound"):
        cli._read_local(PAYLOAD, limit)
    assert reads == [limit + 1]


def test_cli_oversized_context_is_sanitized(monkeypatch, capsys):
    original = cli._read_local
    monkeypatch.setattr(cli, "_read_local", lambda path, limit: b"x" * (cli.MAX_CONTEXT_BYTES + 1)
                        if str(path) == str(CONTEXT) else original(path, limit))
    assert cli.main(args()) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: invalid_context_bound\n"


def test_symlink_or_reparse_file_is_rejected_before_open(monkeypatch):
    monkeypatch.setattr(Path, "lstat", lambda path: SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0))
    with pytest.raises(cli.MarketContractError, match="invalid_local_path"):
        cli._read_local(PAYLOAD, cli.MAX_RESPONSE_BYTES)


def test_file_replacement_rejected_before_read(monkeypatch):
    class Stream(io.BytesIO):
        def fileno(self):
            return 12345
        def read(self, size=-1):
            raise AssertionError("replacement must not be read")
    before = PAYLOAD.stat()
    monkeypatch.setattr(Path, "open", lambda *a, **k: Stream(b"unexpected replacement"))
    monkeypatch.setattr(cli.os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG,
                        st_dev=before.st_dev, st_ino=before.st_ino + 1))
    with pytest.raises(cli.MarketContractError, match="invalid_local_file"):
        cli._read_local(PAYLOAD, cli.MAX_RESPONSE_BYTES)


def test_fresh_process_forbids_network_writes_database_models_and_promotion():
    code = '''
import os, sys
def guard(event, values):
    if event.startswith("socket.") or event in {"os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.truncate"}:
        raise AssertionError("forbidden side effect")
    if event == "open":
        mode, flags = values[1], values[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise AssertionError("forbidden write")
    if event == "import" and values[0].split(".")[0] in {"sqlalchemy", "psycopg", "psycopg2", "sqlite3", "torch", "sentence_transformers", "requests", "httpx"}:
        raise AssertionError("forbidden dependency")
sys.addaudithook(guard)
from scripts.inspect_market_history import main
result = main(sys.argv[1:])
assert not any(name in sys.modules for name in ("app.main", "app.config", "app.database", "app.models", "app.market_returns", "app.embedding_service"))
raise SystemExit(result)
'''
    result = subprocess.run([sys.executable, "-B", "-c", code, *args()], cwd=BACKEND,
                            capture_output=True, text=True, timeout=20,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert result.stderr == "" and output["trusted_custody"] is False
    assert output["publication_state"] == "unsupported" and output["return_state"] == "unavailable"


def _metadata(mode=stat.S_IFDIR, attributes=0):
    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes, st_dev=1, st_ino=2)


def _forbidden(*args, **kwargs):
    raise AssertionError("unexpected filesystem lookup/open/read")


@pytest.mark.parametrize("spelling", [
    "", "//host/share/file", r"\\host\share\file", r"\\?\D:\file", r"\\.\NUL", r"\??\D:\file",
    "https://secret.invalid/file", "file:///D:/file", "D:file", r"\file", "/file",
    "../file", r"D:\safe\..\file", "D:/link/../file", "D:/safe/file:stream", "D:/safe/file::$DATA",
    "D:/safe/NUL", "D:/safe/CON.txt", "D:/safe/COM1", "D:/safe/LPT9.log", "D:/safe/COM¹.txt",
    "D:/safe/CON .txt", "D:/safe/CONIN$", "D:/safe/file.", "D:/safe/file ", "D:/safe./file",
    "D:/safe/file?", "D:/safe/file*", "D:/safe/a\x00b", "D:/safe/a\nb",
])
def test_lexical_rejection_precedes_root_and_filesystem_calls(monkeypatch, spelling):
    monkeypatch.setattr(cli, "_check_windows_root", _forbidden)
    monkeypatch.setattr(Path, "lstat", _forbidden)
    monkeypatch.setattr(Path, "open", _forbidden)
    with pytest.raises(cli.MarketContractError, match="invalid_local_path"):
        cli._local_target(spelling)


@pytest.mark.parametrize("spelling", ["fixtures/input.json", "./fixtures/input.json", r"D:\base\fixtures\input.json"])
def test_relative_and_absolute_paths_are_lexical_only(monkeypatch, spelling):
    roots = []
    monkeypatch.setattr(cli.os, "getcwd", lambda: r"D:\base")
    monkeypatch.setattr(cli, "_check_windows_root", roots.append)
    monkeypatch.setattr(Path, "lstat", _forbidden)
    monkeypatch.setattr(Path, "resolve", _forbidden)
    monkeypatch.setattr(Path, "absolute", _forbidden)
    monkeypatch.setattr(cli.os.path, "realpath", _forbidden)
    assert cli._local_target(spelling) == Path(r"D:\base\fixtures\input.json")
    assert roots == ["D:\\"]


@pytest.mark.parametrize("cwd", [r"\\host\share\cwd", r"D:cwd", r"D:\unsafe.\cwd", "D:/unsafe/../cwd"])
def test_unsafe_cwd_is_not_used_to_classify_relative_input(monkeypatch, cwd):
    monkeypatch.setattr(cli.os, "getcwd", lambda: cwd)
    monkeypatch.setattr(cli, "_check_windows_root", _forbidden)
    monkeypatch.setattr(Path, "lstat", _forbidden)
    with pytest.raises(cli.MarketContractError):
        cli._local_target("input.json")


@pytest.mark.parametrize("mapping,drive_type,accepted", [
    ("\\Device\\HarddiskVolume4", 3, True),
    ("\\Device\\HarddiskVolume4", 4, False),
    ("\\Device\\HarddiskVolume4", 0, False),
    ("\\Device\\HarddiskVolume4", 1, False),
    ("\\Device\\HarddiskVolume4", 2, False),
    ("\\Device\\HarddiskVolume4", 5, False),
    ("\\Device\\HarddiskVolume4", 6, False),
    ("\\Device\\Mup\\server\\share", None, False),
    ("\\Device\\LanmanRedirector\\server\\share", None, False),
    ("\\??\\D:\\substituted", None, False),
    ("\\Device\\UnknownVolume", None, False),
    ("\\Device\\HarddiskVolume4\x00\\??\\D:\\alias", None, False),
    ("", None, False),
])
def test_windows_root_mapping_is_classified_before_drive_query(monkeypatch, mapping, drive_type, accepted):
    import ctypes
    calls = []
    def query(drive, buffer, size):
        calls.append(("mapping", drive))
        buffer.value = mapping
        return len(mapping) + 2 if mapping else 0
    def classify(anchor):
        calls.append(("drive_type", anchor))
        assert drive_type is not None, "rejected mapping must not be queried as a filesystem root"
        return drive_type
    kernel = SimpleNamespace(QueryDosDeviceW=Mock(side_effect=query), GetDriveTypeW=Mock(side_effect=classify))
    monkeypatch.setattr(ctypes, "WinDLL", Mock(return_value=kernel))
    monkeypatch.setattr(Path, "lstat", _forbidden)
    if accepted:
        cli._check_windows_root("D:\\")
    else:
        with pytest.raises(cli.MarketContractError, match="unsupported_local_root"):
            cli._check_windows_root("D:\\")
    assert calls[0] == ("mapping", "D:")
    assert calls[1:] == ([] if drive_type is None else [("drive_type", "D:\\")])


def test_unavailable_root_classifier_has_no_fallback(monkeypatch):
    import ctypes
    monkeypatch.setattr(ctypes, "WinDLL", Mock(side_effect=OSError("private system details")))
    monkeypatch.setattr(Path, "lstat", _forbidden)
    with pytest.raises(cli.MarketContractError, match="unsupported_local_root"):
        cli._check_windows_root("D:\\")


def test_missing_windows_api_has_no_fallback(monkeypatch):
    import ctypes
    monkeypatch.setattr(ctypes, "WinDLL", Mock(return_value=SimpleNamespace()))
    monkeypatch.setattr(Path, "lstat", _forbidden)
    with pytest.raises(cli.MarketContractError, match="unsupported_local_root"):
        cli._check_windows_root("D:\\")


def test_platform_without_root_classifier_is_unsupported(monkeypatch):
    monkeypatch.setattr(cli, "os", SimpleNamespace(name="posix", fspath=os.fspath))
    monkeypatch.setattr(cli, "_check_windows_root", _forbidden)
    monkeypatch.setattr(Path, "lstat", _forbidden)
    with pytest.raises(cli.MarketContractError, match="unsupported_local_root"):
        cli._local_target("input.json")


def test_rejected_root_prevents_any_path_lookup(monkeypatch):
    monkeypatch.setattr(cli, "_check_windows_root", Mock(side_effect=cli.MarketContractError("unsupported_local_root")))
    monkeypatch.setattr(Path, "lstat", _forbidden)
    monkeypatch.setattr(Path, "open", _forbidden)
    with pytest.raises(cli.MarketContractError, match="unsupported_local_root"):
        cli._read_local("D:/synthetic/input.json", 20)


def test_exact_ancestor_then_leaf_order_and_no_following_stat(monkeypatch):
    target = Path("D:/synthetic/parent/input.json")
    expected = [*reversed(target.parents), target]
    calls = []
    monkeypatch.setattr(cli, "_check_windows_root", lambda anchor: calls.append(("root", anchor)))
    def lstat(path):
        index = sum(kind == "lstat" for kind, _ in calls)
        assert path == expected[index], "descendant queried before an ancestor passed"
        calls.append(("lstat", path))
        return _metadata(stat.S_IFREG if path == target else stat.S_IFDIR)
    class Stream(io.BytesIO):
        def fileno(self):
            return 123
    def open_file(path, mode):
        assert [p for kind, p in calls if kind == "lstat"] == expected
        assert mode == "rb"
        calls.append(("open", path))
        return Stream(b"ok")
    monkeypatch.setattr(Path, "lstat", lstat)
    original_stat = Path.stat
    monkeypatch.setattr(Path, "stat", lambda path, *a, **k: _forbidden() if path in expected else original_stat(path, *a, **k))
    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(cli.os, "fstat", lambda fd: _metadata(stat.S_IFREG))
    assert cli._read_local(target, 2) == b"ok"
    assert calls[0] == ("root", "D:\\")
    assert calls[-1] == ("open", target)


@pytest.mark.parametrize("failure", ["symlink", "junction", "other_reparse", "missing", "inaccessible", "nondirectory"])
@pytest.mark.parametrize("ancestor_index", [0, 1, 2])
def test_rejected_ancestor_stops_all_descendant_access(monkeypatch, failure, ancestor_index):
    target = Path("D:/synthetic/parent/input.json")
    ancestors = list(reversed(target.parents))
    calls = []
    monkeypatch.setattr(cli, "_check_windows_root", lambda anchor: None)
    def lstat(path):
        assert path == ancestors[len(calls)]
        calls.append(path)
        if path != ancestors[ancestor_index]:
            return _metadata()
        if failure == "missing":
            raise FileNotFoundError()
        if failure == "inaccessible":
            raise PermissionError()
        if failure == "symlink":
            return _metadata(stat.S_IFLNK)
        if failure == "nondirectory":
            return _metadata(stat.S_IFREG)
        return _metadata(attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "open", _forbidden)
    with pytest.raises((cli.MarketContractError, OSError)):
        cli._read_local(target, 20)
    assert calls == ancestors[:ancestor_index + 1]


@pytest.mark.parametrize("mode,attributes", [(stat.S_IFLNK, 0), (stat.S_IFREG, stat.FILE_ATTRIBUTE_REPARSE_POINT),
                                           (stat.S_IFDIR, 0), (stat.S_IFIFO, 0)])
def test_target_is_checked_only_after_ancestors_then_rejected(monkeypatch, mode, attributes):
    target = Path("D:/synthetic/input.json")
    calls = []
    monkeypatch.setattr(cli, "_check_windows_root", lambda anchor: None)
    def lstat(path):
        calls.append(path)
        return _metadata(mode, attributes) if path == target else _metadata()
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "open", _forbidden)
    with pytest.raises(cli.MarketContractError):
        cli._read_local(target, 20)
    assert calls == [*reversed(target.parents), target]


@pytest.mark.parametrize("bad_input", ["payload", "context"])
def test_both_inputs_preflight_before_either_leaf_access(monkeypatch, capsys, bad_input):
    payload, context = Path("D:/payload/input.json"), Path("D:/context/input.json")
    rejected = (payload if bad_input == "payload" else context).parent
    calls = []
    monkeypatch.setattr(cli, "_check_windows_root", lambda anchor: None)
    def lstat(path):
        assert path not in (payload, context), "neither leaf may be queried before both preflights pass"
        calls.append(path)
        return _metadata(attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if path == rejected else 0)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "open", _forbidden)
    assert cli.main(["--payload", str(payload), "--context", str(context)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: invalid_local_path\n"
    assert calls[-1] == rejected


def test_parent_replacement_between_preflight_and_read_is_rechecked(monkeypatch, capsys):
    payload, context = Path("D:/payload/input.json"), Path("D:/context/input.json")
    counts = {}
    monkeypatch.setattr(cli, "_check_windows_root", lambda anchor: None)
    def lstat(path):
        assert path not in (payload, context)
        counts[path] = counts.get(path, 0) + 1
        replaced = path == payload.parent and counts[path] == 2
        return _metadata(attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if replaced else 0)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "open", _forbidden)
    assert cli.main(["--payload", str(payload), "--context", str(context)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: invalid_local_path\n"
    assert counts[payload.parent] == 2 and counts[context.parent] == 1
