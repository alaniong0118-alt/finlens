"""Read-only native probes and isolated synthetic custody/profile checks.

No ACL installation, real profile, external store, database or activation.
Synthetic descriptor successes never demonstrate real deployment/bootstrap trust.
"""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

from app import aapl_operator_policy as p
from app import aapl_net_margin_activation as activation, aapl_net_margin_proposal as proposal
from app import revenue_scope_authorizations as auth, sec_evidence_adapter as evidence
from app import financial_metric_registry as registry


SYSTEM, ADMIN = "S-1-5-18", "S-1-5-32-544"
USER, GROUP = "S-1-5-21-111-222-333-444", "S-1-5-11"


def inactive():
    assert activation._ACTIVATION_ENABLED is False
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == auth.DENOMINATOR_AUTHORIZATIONS == ()
    assert auth.AUTHORIZATION_WITHDRAWALS == evidence.PRODUCTION_EVIDENCE_POLICIES == ()
    assert registry.REVENUE_EQUIVALENCES == frozenset()


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    inactive()  # BEFORE any substitution; never patch the gate or registries.
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network forbidden"))
    yield
    inactive()


def descriptor(**kwargs):
    return replace(p.SecurityDescriptor(SYSTEM, ((SYSTEM, p._FILE_ALL, 0),
                   (ADMIN, p._FILE_ALL, 0), (GROUP, 0x120089, 0)), 0x120089, False, True), **kwargs)


def acl_bytes(aces):
    result = b""
    for sid, mask, flags, kind in aces:
        parts = [int(x) for x in sid.split("-")[1:]]
        sid_bytes = bytes((parts[0], len(parts) - 2)) + parts[1].to_bytes(6, "big")
        sid_bytes += b"".join(x.to_bytes(4, "little") for x in parts[2:])
        result += struct.pack("<BBHI", kind, flags, 8 + len(sid_bytes), mask) + sid_bytes
    return struct.pack("<BBHHH", 2, 0, len(result) + 8, len(aces), 0) + result


@pytest.mark.parametrize("protected", [False, True])
def test_supported_synthetic_custody_allows_readers_and_trusted_custodians(protected):
    p._check_security(descriptor(dacl_protected=protected))
    p._check_security(descriptor(token_access=p._FILE_ALL, token_is_custodian=True))


@pytest.mark.parametrize("mask", [2, 4, 16, 64, 256, 0x10000, 0x40000, 0x80000,
                                  0x40000000, 0x10000000])
@pytest.mark.parametrize("flags", [0, 0x10, 0x1B])
def test_group_inherited_and_inherit_only_modification_fails(mask, flags):
    with pytest.raises(p.LaunchRejected, match="unauthorized_modification"):
        p._check_security(descriptor(aces=((GROUP, mask, flags),)))


def test_owner_and_actual_token_effective_modification_reject():
    with pytest.raises(p.LaunchRejected, match="untrusted_owner"):
        p._check_security(descriptor(owner=USER))
    with pytest.raises(p.LaunchRejected, match="effective_modification"):
        p._check_security(descriptor(token_access=0x40000))


@pytest.mark.parametrize("bad", [None, object(), ("bad",), True, -1, 0x02000000])
def test_unsupported_descriptor_or_rights_reject(bad):
    with pytest.raises(p.LaunchRejected):
        if bad is None or type(bad) is object or type(bad) is tuple:
            p._check_security(bad)
        else:
            p._check_security(descriptor(token_access=bad))


def test_binary_acl_keeps_group_and_inherited_grants():
    aces = p._decode_acl(acl_bytes([(SYSTEM, p._FILE_ALL, 0, 0), (GROUP, 0x40000000, 0x10, 0)]))
    assert aces[1] == (GROUP, 0x120116, 0x10)
    with pytest.raises(p.LaunchRejected, match="unauthorized_modification"):
        p._check_security(descriptor(aces=aces))


@pytest.mark.parametrize("kind", [1, 5, 6, 9, 10, 17, 18])
def test_deny_object_callback_and_other_ace_types_are_unsupported(kind):
    with pytest.raises(p.LaunchRejected, match="unsupported_security_descriptor"):
        p._decode_acl(acl_bytes([(GROUP, p._FILE_ALL, 0, kind)]))


@pytest.mark.parametrize("raw", [b"", b"123", b"\x02\x00\x08\x00\x01\x00\x00\x00",
    b"\x04\x00\x08\x00\x00\x00\x00\x00", b"\x02\x01\x08\x00\x00\x00\x00\x00"])
def test_malformed_or_unsupported_acl_reject(raw):
    with pytest.raises(p.LaunchRejected): p._decode_acl(raw)


def test_parent_delete_child_cannot_be_hidden_by_safe_file(tmp_path, monkeypatch):
    file = tmp_path / "synthetic.txt"
    file.write_text("fixture", encoding="utf-8")
    def security(path):
        return descriptor(aces=((GROUP, 64, 0),)) if path == tmp_path else descriptor()
    monkeypatch.setattr(p, "_windows_security", security)
    with pytest.raises(p.LaunchRejected, match="unauthorized_modification"):
        p._verify_protected_profile(file)


def test_custody_checks_every_ancestor_and_descriptor_api_failure(tmp_path, monkeypatch):
    seen = []
    def read(path):
        seen.append(path)
        return descriptor()
    monkeypatch.setattr(p, "_windows_security", read)
    p._verify_custody(tmp_path)
    assert seen == [*reversed(tmp_path.parents), tmp_path]
    monkeypatch.setattr(p, "_windows_security", lambda path: (_ for _ in ()).throw(OSError("synthetic API fault")))
    with pytest.raises(p.LaunchRejected, match="security_descriptor_unverifiable"):
        p._verify_custody(tmp_path)


@pytest.mark.parametrize("value", ["relative", "", "\\\\server\\share\\file", "D:\\file:stream", "D:\\trailing."])
def test_unsafe_path_shapes_reject(value):
    with pytest.raises(p.LaunchRejected): p._absolute(value)


def test_reparse_attribute_and_resolved_substitution_reject(tmp_path, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", lambda self: SimpleNamespace(st_file_attributes=0x400))
        with pytest.raises(p.LaunchRejected): p._absolute(str(tmp_path))
    with monkeypatch.context() as patch:
        patch.setattr(Path, "resolve", lambda self, **kwargs: self / "substitution")
        with pytest.raises(p.LaunchRejected): p._absolute(str(tmp_path))


@pytest.fixture
def profile(tmp_path, monkeypatch):
    file = tmp_path / "synthetic-code.txt"
    file.write_text("synthetic only", encoding="utf-8")
    path = tmp_path / "synthetic-profile.json"
    data = dict(version=2, deployment_id="synthetic", operator_sids=[USER],
        approval={"permission": proposal.REF.permission, "id": proposal.REF.approval_id, "version": proposal.REF.version},
        approval_sha256=evidence.approval_digest(proposal.PROPOSED_DENOMINATOR_AUTHORIZATION),
        evidence_policy_sha256=evidence._policy_digest(proposal.PROPOSED_EVIDENCE_POLICY),
        python_executable=sys.executable, import_roots=[str(tmp_path)], original_store=str(tmp_path),
        protected_files=[dict(path=str(file), sha256=hashlib.sha256(file.read_bytes()).hexdigest())],
        code_root=str(Path(p.__file__).resolve().parents[1]), runtime_roots=[sys.prefix, sys.base_prefix],
        configuration_files=[], custodian_sids=[SYSTEM, ADMIN], custodian_access="full_control")
    monkeypatch.setattr(p, "_process_token_sid", lambda: USER)
    monkeypatch.setattr(p, "_windows_security", lambda path: descriptor())
    # Parsing-only success; the actual bootstrap anchor is never treated as passed.
    monkeypatch.setattr(p, "_verify_deployment_integrity", lambda policy: None)
    monkeypatch.setenv("FINLENS_SEC_ORIGINAL_STORE", str(tmp_path))  # Process-local synthetic fixture only.
    def write(): path.write_text(json.dumps(data), encoding="utf-8")
    write()
    return SimpleNamespace(path=path, data=data, write=write, file=file)


def test_profile_v2_binds_platform_custody_scope_and_roots(profile):
    policy = p.authenticate_operator(profile.path)
    assert policy.operator_sids == (USER,) and policy.custodian_sids == (SYSTEM, ADMIN)
    assert policy.code_root == Path(p.__file__).resolve().parents[1]


@pytest.mark.parametrize("key,value", [("version", 1), ("version", True), ("custodian_sids", [USER]),
    ("custodian_sids", [SYSTEM, ADMIN, ADMIN]), ("custodian_access", "read"),
    ("runtime_roots", []), ("runtime_roots", ["relative"]), ("configuration_files", ["relative"]),
    ("operator_sids", [GROUP]), ("operator_sids", [USER, USER]), ("approval_sha256", "0"*64),
    ("bootstrap_verified", True)])
def test_modified_conflicting_or_claimed_authority_profile_reject(profile, key, value):
    profile.data[key] = value
    profile.write()
    with pytest.raises((p.LaunchRejected, FileNotFoundError)): p.authenticate_operator(profile.path)


def test_missing_duplicate_and_modified_file_profiles_reject(profile):
    profile.path.unlink()
    with pytest.raises(FileNotFoundError): p.authenticate_operator(profile.path)
    profile.path.write_text('{"version":2,"version":2}', encoding="utf-8")
    with pytest.raises(p.LaunchRejected, match="ambiguous_launch_profile"): p.authenticate_operator(profile.path)
    profile.write()
    profile.file.write_text("changed", encoding="utf-8")
    with pytest.raises(p.LaunchRejected, match="deployment_file_changed"): p.authenticate_operator(profile.path)


@pytest.fixture
def imports(tmp_path, monkeypatch):
    from importlib.machinery import BuiltinImporter, FrozenImporter, PathFinder
    import site
    state = SimpleNamespace(flags=SimpleNamespace(isolated=True, safe_path=True),
        path=[str(tmp_path)], meta_path=[BuiltinImporter, FrozenImporter, PathFinder])
    monkeypatch.setattr(p, "sys", state)
    monkeypatch.setattr(site, "ENABLE_USER_SITE", False)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"): monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(p, "_verify_custody", lambda path: None)
    return SimpleNamespace(import_roots=(tmp_path,), state=state, root=tmp_path)


def test_synthetic_import_paths_pass_only_the_structural_check(imports):
    p._check_import_paths(imports)
    with pytest.raises(p.LaunchRejected, match="external_bootstrap_unavailable"):
        p._verify_external_bootstrap(imports)


@pytest.mark.parametrize("line", ["import malicious", "import\tmalicious", "other-directory"])
def test_executable_pth_and_pth_path_injection_reject(imports, line):
    (imports.root / "fixture.pth").write_text(line, encoding="utf-8")
    with pytest.raises(p.LaunchRejected, match="pth_hook_or_path"): p._check_import_paths(imports)


@pytest.mark.parametrize("case", ["relative", "outside", "missing", "unisolated", "hook", "user_site", "env"])
def test_unverifiable_imports_reject(imports, case, monkeypatch):
    if case == "relative": imports.state.path = [""]
    elif case == "outside": imports.state.path = [str(imports.root.parent)]
    elif case == "missing": imports.state.path = [str(imports.root / "missing-library.zip")]
    elif case == "unisolated": imports.state.flags.isolated = False
    elif case == "hook": imports.state.meta_path.insert(0, object())
    elif case == "user_site":
        import site
        monkeypatch.setattr(site, "ENABLE_USER_SITE", True)
    else: monkeypatch.setenv("PYTHONPATH", str(imports.root))
    with pytest.raises((p.LaunchRejected, FileNotFoundError)): p._check_import_paths(imports)


@pytest.fixture
def deployment(tmp_path, imports, monkeypatch):
    code, runtime = tmp_path / "backend", tmp_path / "runtime"
    (code / "app").mkdir(parents=True)
    runtime.mkdir()
    policy_file, launcher = code / "app" / "aapl_operator_policy.py", code / "app" / "aapl_net_margin_launcher.py"
    executable, configuration = runtime / "python.exe", code / ".env"
    for path in (policy_file, launcher, executable, configuration):
        path.write_text("synthetic fixture only", encoding="utf-8")
    monkeypatch.setattr(p, "__file__", str(policy_file))
    imports.state.prefix = imports.state.base_prefix = str(runtime)
    imports.state.executable = str(executable)
    imports.state.path = [str(code), str(runtime)]
    pins = tuple((path, hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in (policy_file, launcher, executable, configuration))
    return p.DeploymentPolicy("synthetic", (USER,), tmp_path, pins, (code, runtime),
                              code, (runtime,), (configuration,), (SYSTEM, ADMIN))


def test_complete_synthetic_inventory_still_cannot_attest_bootstrap(deployment):
    with pytest.raises(p.LaunchRejected, match="external_bootstrap_unavailable"):
        p._verify_deployment_integrity(deployment)


@pytest.mark.parametrize("case,reason", [("missing_pin", "incomplete_inventory"),
    ("changed_bytes", "file_changed"), ("missing_runtime", "missing_runtime_root"),
    ("wrong_code", "wrong_code_root"), ("outside_import", "unreviewed_import_root"),
    ("custom_custodian", "unsupported_custodians")])
def test_deployment_integrity_rejects_incomplete_or_changed_inventory(deployment, case, reason, tmp_path):
    if case == "missing_pin": deployment = replace(deployment, protected_files=deployment.protected_files[:-1])
    elif case == "changed_bytes": deployment.protected_files[0][0].write_text("changed", encoding="utf-8")
    elif case == "missing_runtime": deployment = replace(deployment, runtime_roots=(tmp_path,))
    elif case == "wrong_code": deployment = replace(deployment, code_root=tmp_path)
    elif case == "outside_import": deployment = replace(deployment, import_roots=(tmp_path,))
    else: deployment = replace(deployment, custodian_sids=(USER,))
    with pytest.raises(p.LaunchRejected, match=reason): p._verify_deployment_integrity(deployment)


def test_deployment_security_probe_rejects_real_writable_environment():
    if os.name != "nt": pytest.skip("Native Windows custody probe")
    code = Path(p.__file__).resolve().parents[1]
    policy = p.DeploymentPolicy("untrusted-development-probe", (), code, (), (), code,
                                (Path(sys.prefix), Path(sys.base_prefix)), (), (SYSTEM, ADMIN))
    with pytest.raises(p.LaunchRejected, match="protected_profile_acl"):
        p._verify_deployment_integrity(policy)


def test_current_windows_deployment_native_checks_and_rejection():
    if os.name != "nt": pytest.skip("Native Windows read-only probe")
    sid = p._process_token_sid()
    assert sid.startswith("S-1-")  # Never log or install the real SID.
    path = Path(p.__file__).absolute()
    native = p._windows_security(path)
    assert isinstance(native, p.SecurityDescriptor) and native.aces
    with pytest.raises(p.LaunchRejected): p._verify_protected_profile(path)
    with pytest.raises(p.LaunchRejected, match="external_bootstrap_unavailable"):
        p._verify_external_bootstrap(None)


@pytest.mark.parametrize("function", ["GetNamedSecurityInfoW", "null_descriptor", "IsValidSecurityDescriptor",
    "GetSecurityDescriptorControl", "IsValidAcl", "OpenProcessToken", "DuplicateToken", "AccessCheck"])
def test_native_api_failures_reject(function, monkeypatch):
    if os.name != "nt": pytest.skip("Windows native API failure injection")
    import ctypes
    original = ctypes.WinDLL
    target_name = "GetNamedSecurityInfoW" if function == "null_descriptor" else function
    class Call:
        def __init__(self, target): object.__setattr__(self, "target", target)
        def __setattr__(self, key, value): setattr(self.target, key, value)
        def __call__(self, *args):
            ctypes.set_last_error(5)
            return 5 if function == "GetNamedSecurityInfoW" else 0
    class Proxy:
        def __init__(self, dll): self.dll = dll
        def __getattr__(self, key):
            return Call(getattr(self.dll, key)) if key == target_name else getattr(self.dll, key)
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: Proxy(original(name, **kw)))
    with pytest.raises(p.LaunchRejected): p._windows_security(Path(p.__file__).absolute())
