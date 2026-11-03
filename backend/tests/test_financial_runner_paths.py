"""Offline path controls; Linux paths are simulated, never a Linux execution."""
import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest


RUNNER = Path(__file__).with_name("run_financial_insights.py")


def runner_tree():
    return ast.parse(RUNNER.read_text(encoding="utf-8"), filename=str(RUNNER))


def selector():
    function, = [node for node in runner_tree().body
                 if isinstance(node, ast.FunctionDef) and node.name == "fixed_venv_site_packages"]
    scope = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(RUNNER), "exec"), scope)
    return scope[function.name]


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize("version", [(3, 13), (3, 14)])
def test_fixed_layout_uses_supplied_interpreter_version(tmp_path, platform, version):
    expected = (tmp_path / ".venv/Lib/site-packages" if platform == "win32" else
                tmp_path / f".venv/lib/python{version[0]}.{version[1]}/site-packages")
    expected.mkdir(parents=True)
    assert selector()(tmp_path, platform, version, "cpython", False) == expected


@pytest.mark.parametrize("platform,implementation,free_threaded", [
    ("darwin", "cpython", False), ("linux", "pypy", False),
    ("win32", "cpython", True), ("linux", "cpython", True)])
def test_unsupported_layout_rejects_before_dependency_lookup(tmp_path, platform, implementation, free_threaded):
    with pytest.raises(RuntimeError, match="normal CPython on Windows or Linux"):
        selector()(tmp_path, platform, (3, 14), implementation, free_threaded)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_missing_fixed_packages_never_fall_back(tmp_path, platform):
    with pytest.raises(RuntimeError, match="Missing fixed virtualenv dependencies"):
        selector()(tmp_path, platform, (3, 14), "cpython", False)


def test_other_linux_version_or_lib64_is_not_a_fallback(tmp_path):
    (tmp_path / ".venv/lib/python3.13/site-packages").mkdir(parents=True)
    (tmp_path / ".venv/lib64/python3.14/site-packages").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="Missing fixed virtualenv dependencies"):
        selector()(tmp_path, "linux", (3, 14), "cpython", False)


def test_isolated_child_does_not_process_pth_or_ambient_pythonpath(tmp_path):
    # Execute the actual runner bootstrap through sys.path setup only. No app,
    # driver, model or third-party dependency is imported in this child.
    prefix = []
    for node in runner_tree().body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "update":
            break
        prefix.append(node)
    bootstrap = ast.unparse(ast.Module(body=prefix, type_ignores=[]))
    (tmp_path / "tests").mkdir()
    packages = (tmp_path / ".venv/Lib/site-packages" if sys.platform == "win32" else
                tmp_path / f".venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
    packages.mkdir(parents=True)
    marker = tmp_path / "pth-executed"
    (packages / "poison.pth").write_text(f"import pathlib; pathlib.Path({str(marker)!r}).write_text('bad')\n", encoding="utf-8")
    ambient = tmp_path / "ambient"
    ambient.mkdir()
    (ambient / "finlens_ambient_probe.py").write_text("raise AssertionError('ambient import')\n", encoding="utf-8")
    code = f'''import importlib.util, socket, sys
def denied(*args, **kwargs):
    raise AssertionError("No network IO in bootstrap control")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = denied
__file__ = {str(tmp_path / 'tests/run_financial_insights.py')!r}
exec({bootstrap!r})
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert "site" not in sys.modules
assert importlib.util.find_spec("finlens_ambient_probe") is None
assert not Path({str(marker)!r}).exists()
assert sys.path[:3] == [str(PACKAGES), str(ROOT), str(ROOT / "tests")]
'''
    env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if name in os.environ}
    env["PYTHONPATH"] = str(ambient)
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr or result.stdout
    assert not marker.exists()
