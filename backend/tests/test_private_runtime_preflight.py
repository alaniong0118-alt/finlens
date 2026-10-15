"""Synthetic Option B checks; no application imports or real environment changes."""

import builtins
from email.parser import Parser
import importlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import preflight_private_runtime as preflight


PRIVATE = {"FINLENS_SERVER_PROFILE": "sec_readonly"}
SECRET = "private-path credential database-url synthetic-sensitive-value"
REAL_MARKER_ENVIRONMENT = preflight.default_environment
MARKERS = REAL_MARKER_ENVIRONMENT()
MARKERS.update(python_version="3.14", python_full_version="3.14.7",
               sys_platform="win32", os_name="nt", platform_system="Windows")


def distribution(name="synthetic", version="1.0", python=">=3.10", requires=(),
                 extras=(), raw=None):
    if raw is None:
        fields = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
        if python is not None:
            fields.append(f"Requires-Python: {python}")
        fields.extend(f"Requires-Dist: {item}" for item in requires)
        fields.extend(f"Provides-Extra: {extra}" for extra in extras)
        raw = "\n".join(fields) + "\n\n"
    return SimpleNamespace(metadata=Parser().parsestr(raw),
                           read_text=lambda filename: raw if filename == "METADATA" else None)


@pytest.fixture(autouse=True)
def no_external_operations(monkeypatch):
    def bomb(*args, **kwargs):
        raise AssertionError("Forbidden external operation: " + SECRET)

    for attribute in ("socket", "create_connection", "getaddrinfo", "socketpair"):
        monkeypatch.setattr(socket, attribute, bomb)
    for attribute in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, attribute, bomb)
    for attribute in ("system", "popen", "startfile", "spawnv", "spawnve"):
        if hasattr(os, attribute):
            monkeypatch.setattr(os, attribute, bomb)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app", "sqlalchemy", "psycopg", "psycopg2", "sqlite3", "torch",
            "sentence_transformers", "transformers", "huggingface_hub", "httpx", "requests",
        }:
            return bomb()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(preflight, "default_environment", lambda: MARKERS.copy())


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    path = tmp_path / "requirements.txt"
    path.write_text("synthetic>=1,<2\n", encoding="utf-8")
    packages = [distribution()]
    monkeypatch.setattr(preflight.metadata, "distributions", lambda: iter(packages))

    def inspect(text=None, installed=None, environment=PRIVATE):
        if text is not None:
            path.write_text(text, encoding="utf-8")
        if installed is not None:
            packages[:] = installed
        return preflight.inspect_runtime(requirements_path=path, environ=environment)

    return inspect, path, packages


def codes(report):
    return {item["code"] for item in report["diagnostics"]}


def assert_blocked(report):
    assert report["status"] == "BLOCKED"
    assert report["exit_code"] == 1
    assert "Model artifacts and numerical compatibility are not assessed." in report["limitations"]
    assert "not authorized" in report["limitations"][-1]
    assert SECRET not in json.dumps(report)


def test_valid_metadata_is_always_blocked(runtime):
    inspect, _, _ = runtime
    report = inspect()
    assert report["checks"] == {"explicit_profile": "PASS", "python_dependency_metadata": "PASS"}
    assert codes(report) == set()
    assert_blocked(report)


@pytest.mark.parametrize("profile", [None, "", "development", "unknown", "SEC_READONLY",
                                     " sec_readonly", "sec_readonly ", SECRET])
def test_explicit_profile_required(runtime, profile):
    inspect, _, _ = runtime
    environment = {} if profile is None else {"FINLENS_SERVER_PROFILE": profile}
    report = inspect(environment=environment)
    assert codes(report) == {"PROFILE_REQUIRED"}
    assert report["checks"]["explicit_profile"] == "FAIL"
    assert report["checks"]["python_dependency_metadata"] == "PASS"
    assert_blocked(report)


def test_process_environment_profile_without_dotenv(runtime, monkeypatch):
    inspect, _, _ = runtime
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", "sec_readonly")
    assert inspect(environment=None)["checks"]["explicit_profile"] == "PASS"
    monkeypatch.delenv("FINLENS_SERVER_PROFILE")
    assert "PROFILE_REQUIRED" in codes(inspect(environment=None))


@pytest.mark.parametrize("version", ["0.9", "2.0", "1.1rc1"])
def test_incompatible_dependency(runtime, version):
    inspect, _, _ = runtime
    assert codes(inspect(installed=[distribution(version=version)])) == {"DEPENDENCY_INCOMPATIBLE"}


def test_missing_dependency(runtime):
    inspect, _, _ = runtime
    assert codes(inspect(installed=[])) == {"DEPENDENCY_MISSING"}


def test_explicit_prerelease_requirement_is_supported(runtime):
    inspect, _, _ = runtime
    assert codes(inspect("synthetic>=1.1rc1,<2", [distribution(version="1.1rc2")])) == set()


@pytest.mark.parametrize("version,expected", [("6.1.0", {"SENTENCE_TRANSFORMERS_INCOMPATIBLE"}),
                                             ("3.3.9", {"SENTENCE_TRANSFORMERS_INCOMPATIBLE"}),
                                             ("5.9", set())])
def test_sentence_transformers_declared_range(runtime, version, expected):
    inspect, _, _ = runtime
    report = inspect("sentence-transformers>=3.4,<6.0\n",
                     [distribution("sentence-transformers", version)])
    assert codes(report) == expected
    assert_blocked(report)  # Synthetic in-range metadata establishes no model compatibility.


@pytest.mark.parametrize("python,expected", [("<3.14", "PYTHON_INCOMPATIBLE"),
                                            (None, "METADATA_INVALID"),
                                            ("", "METADATA_INVALID"),
                                            ("broken", "METADATA_INVALID")])
def test_python_declaration(runtime, python, expected):
    inspect, _, _ = runtime
    assert codes(inspect(installed=[distribution(python=python)])) == {expected}


@pytest.mark.parametrize("raw", [
    "",
    "Metadata-Version: 2.1\nName: synthetic\n\n",
    "Metadata-Version: 2.1\nName: synthetic\nVersion: nonsense\nRequires-Python: >=3\n\n",
    "Metadata-Version: 9.9\nName: synthetic\nVersion: 1\nRequires-Python: >=3\n\n",
    "Metadata-Version: 2.1\nName: synthetic\nVersion: 1\nVersion: 2\nRequires-Python: >=3\n\n",
    "Metadata-Version: 2.1\nName: synthetic\nName: synthetic\nVersion: 1\n\n",
    "Metadata-Version: 2.1\nName: synthetic\nVersion: 1\nRequires-Python: >=3\nRequires-Dist: ???\n\n",
    "Metadata-Version: 2.1\nVersion: 1\nRequires-Python: >=3\n\n",
    "Metadata-Version: 2.1\nName: ???\nVersion: 1\nRequires-Python: >=3\n\n",
    "Name: synthetic\nVersion: 1\nRequires-Python: >=3\n\n",
    "Metadata-Version: 2.1\nName: synthetic\nVersion: 1\nRequires-Python: >=3\nRequires-Python: <3\n\n",
])
def test_malformed_or_incomplete_metadata(runtime, raw):
    inspect, _, _ = runtime
    report = inspect(installed=[distribution(raw=raw)])
    assert codes(report) == {"METADATA_INVALID"}
    assert_blocked(report)


def test_ambiguous_normalized_distribution_identity(runtime):
    inspect, _, _ = runtime
    report = inspect("some-package>=1", [distribution("some-package"), distribution("some_package")])
    assert codes(report) == {"METADATA_AMBIGUOUS"}


def test_inconsistent_metadata_identity(runtime):
    inspect, _, _ = runtime
    package = distribution("other")
    package.metadata.replace_header("Name", "synthetic")
    assert codes(inspect(installed=[package])) == {"METADATA_INVALID"}


@pytest.mark.parametrize("text", ["", "# comment only", "???", "-r private.txt", "--index-url " + SECRET,
                                 "synthetic @ https://invalid.example/model"])
def test_invalid_requirements_are_sanitized(runtime, text):
    inspect, _, _ = runtime
    report = inspect(text)
    assert codes(report) == {"REQUIREMENTS_INVALID"}
    assert_blocked(report)


def test_missing_requirements_file(runtime):
    _, path, _ = runtime
    report = preflight.inspect_runtime(requirements_path=path.parent / "absent", environ=PRIVATE)
    assert codes(report) == {"REQUIREMENTS_INVALID"}


def test_root_and_transitive_environment_markers(runtime):
    inspect, _, _ = runtime
    package = distribution(requires=("child>=1; sys_platform == 'win32'",
                                     "absent; sys_platform == 'linux'"))
    text = "synthetic>=1; python_version >= '3.14'\nabsent; python_version < '3'\n"
    report = inspect(text, [package, distribution("child")])
    assert codes(report) == set()
    assert codes(inspect(installed=[package])) == {"DEPENDENCY_MISSING"}


def test_active_extras_and_late_extra_propagation(runtime):
    inspect, _, _ = runtime
    packages = [distribution("base", requires=("late", "child; extra == 'fast'"), extras=("fast",)),
                distribution("late", requires=("base[fast]",)), distribution("child")]
    assert codes(inspect("base>=1", packages)) == set()
    assert codes(inspect(installed=packages[:2])) == {"DEPENDENCY_MISSING"}


def test_inactive_extras_not_required(runtime):
    inspect, _, _ = runtime
    package = distribution(requires=("absent; extra == 'fast'",), extras=("fast",))
    assert codes(inspect(installed=[package])) == set()
    assert codes(inspect("synthetic[fast]", [package])) == {"DEPENDENCY_MISSING"}


def test_base_and_extra_requirements_both_apply(runtime):
    inspect, _, _ = runtime
    package = distribution(requires=("absent; extra != 'fast'",), extras=("fast",))
    assert codes(inspect("synthetic[fast]", [package])) == {"DEPENDENCY_MISSING"}


def test_unknown_active_extra_rejected(runtime):
    inspect, _, _ = runtime
    assert codes(inspect("synthetic[unknown]")) == {"METADATA_INVALID"}


def test_constraints_rechecked_after_node_expansion(runtime):
    inspect, _, _ = runtime
    packages = [distribution(requires=("child>=1", "late")),
                distribution("child"), distribution("late", requires=("child>=2",))]
    assert codes(inspect(installed=packages)) == {"DEPENDENCY_INCOMPATIBLE"}


def test_active_direct_url_metadata_is_indeterminate(runtime):
    inspect, _, _ = runtime
    package = distribution(requires=("child @ https://invalid.example/private",))
    assert codes(inspect(installed=[package])) == {"METADATA_INVALID"}


def test_parser_unavailable_is_sanitized(runtime, monkeypatch):
    inspect, _, _ = runtime
    monkeypatch.setattr(preflight, "_PARSER_AVAILABLE", False)
    assert codes(inspect()) == {"PARSER_UNAVAILABLE"}


def test_real_marker_environment_needs_no_external_operations(runtime, monkeypatch):
    inspect, _, _ = runtime
    monkeypatch.setattr(preflight, "default_environment", REAL_MARKER_ENVIRONMENT)
    assert codes(inspect()) == set()


def test_diagnostics_independent_of_inventory_and_requirement_order(runtime):
    inspect, _, _ = runtime
    packages = [distribution(version="0.1"), distribution("child", version="3")]
    first = inspect("synthetic>=1\nchild<2\nabsent", packages)
    second = inspect("absent\nchild<2\nsynthetic>=1", list(reversed(packages)))
    assert first == second
    assert codes(first) == {"DEPENDENCY_INCOMPATIBLE", "DEPENDENCY_MISSING"}


def test_metadata_failure_preserves_other_detected_incompatibilities(runtime):
    inspect, _, _ = runtime
    packages = [distribution("sentence-transformers", "6.1.0"), distribution(python=None)]
    report = inspect("sentence-transformers>=3.4,<6.0\nsynthetic", packages)
    assert codes(report) == {"SENTENCE_TRANSFORMERS_INCOMPATIBLE", "METADATA_INVALID"}


@pytest.mark.parametrize("target", ["requirements", "discovery", "metadata_read", "metadata_access"])
def test_unexpected_failures_never_leak(runtime, monkeypatch, target):
    inspect, _, packages = runtime

    def failed(*args, **kwargs):
        raise PermissionError(SECRET)

    if target == "requirements":
        monkeypatch.setattr(Path, "read_text", failed)
        expected = "REQUIREMENTS_INVALID"
    elif target == "discovery":
        monkeypatch.setattr(preflight.metadata, "distributions", failed)
        expected = "INSPECTION_FAILED"
    elif target == "metadata_read":
        packages[0].read_text = failed
        expected = "INSPECTION_FAILED"
    else:
        class Broken:
            @property
            def metadata(self):
                return failed()
        packages[:] = [Broken()]
        expected = "INSPECTION_FAILED"
    report = inspect()
    assert codes(report) == {expected}
    assert_blocked(report)


def test_cli_always_nonzero_and_deterministic(runtime, monkeypatch, capsys):
    inspect, _, _ = runtime
    report = inspect()
    monkeypatch.setattr(preflight, "inspect_runtime", lambda: report)
    assert preflight.main([]) == 1
    first = capsys.readouterr()
    assert first.err == ""
    assert preflight.main([]) == 1
    assert capsys.readouterr().out == first.out
    assert json.loads(first.out) == report
    assert preflight.main([SECRET]) == 1
    assert SECRET not in capsys.readouterr().out
    assert "ARGUMENTS_UNSUPPORTED" in codes(report)


def test_no_model_artifact_reads_or_filesystem_mutations(runtime, monkeypatch):
    inspect, path, packages = runtime
    before = path.read_bytes()
    real_open, real_io_open, real_os_open = builtins.open, io.open, os.open
    reads = []

    def guarded_open(file, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), SECRET
        assert Path(file) == path, SECRET
        reads.append(path)
        return real_open(file, mode, *args, **kwargs)

    def guarded_io_open(file, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), SECRET
        assert Path(file) == path, SECRET
        reads.append(path)
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(file, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND), SECRET
        assert Path(file) == path, SECRET
        return real_os_open(file, flags, *args, **kwargs)

    def bomb(*args, **kwargs):
        raise AssertionError(SECRET)

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", guarded_open)
        guard.setattr(io, "open", guarded_io_open)
        guard.setattr(os, "open", guarded_os_open)
        for attribute in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace", "rmdir",
                          "chmod", "utime", "link", "symlink"):
            guard.setattr(os, attribute, bomb)
        guard.setattr(Path, "iterdir", bomb)
        guard.setattr(Path, "glob", bomb)
        guard.setattr(Path, "rglob", bomb)
        report = inspect()
    assert codes(report) == set()  # A caught side-effect sentinel must also fail this assertion.
    assert report["checks"]["python_dependency_metadata"] == "PASS"
    assert reads == [path]
    assert path.read_bytes() == before
    assert len(packages) == 1


def test_module_import_does_not_start_inspection(runtime, monkeypatch):
    _, _, _ = runtime
    calls = []

    def bomb(*args, **kwargs):
        calls.append(True)
        raise AssertionError(SECRET)

    monkeypatch.setattr(preflight.metadata, "distributions", bomb)
    monkeypatch.setattr(Path, "read_text", bomb)
    importlib.reload(preflight)
    assert calls == []
    assert "app.embedding_service" not in sys.modules
