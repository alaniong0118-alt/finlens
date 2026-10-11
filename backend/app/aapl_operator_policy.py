"""Windows identity and an explicitly uncommissioned deployment trust boundary.

No supplied policy is trusted until ACL/ownership, executable/import closure and
maintenance exclusion have separately reviewed implementations. No credentials,
allowlists or protected profiles are shipped. Test substitutions are private and
reversible; there is no synthetic/skip-verification mode in production.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from app.activation_lifecycle import LaunchRejected


@dataclass(frozen=True)
class DeploymentPolicy:
    deployment_id: str
    operator_sids: tuple[str, ...]
    original_store: Path
    protected_files: tuple[tuple[Path, str], ...]
    import_roots: tuple[Path, ...]


def _process_token_sid():
    """Read TokenUser from this process, never USERNAME, a caller SID or a claim."""
    if os.name != "nt":
        raise LaunchRejected("windows_process_token_required")
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel.LocalFree.restype = wintypes.HLOCAL
    advapi.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR))
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    handle = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(handle)):
        raise LaunchRejected("process_token_unverifiable")
    text_sid = wintypes.LPWSTR()
    try:
        size = wintypes.DWORD()
        # TokenUser consists of SID_AND_ATTRIBUTES; its first field is PSID.
        if advapi.GetTokenInformation(handle, 1, None, 0, ctypes.byref(size)) or ctypes.get_last_error() != 122:
            raise LaunchRejected("process_token_unverifiable")
        if not 0 < size.value <= 65536:
            raise LaunchRejected("process_token_unverifiable")
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(handle, 1, buffer, size, ctypes.byref(size)):
            raise LaunchRejected("process_token_unverifiable")
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        if not sid or not advapi.ConvertSidToStringSidW(sid, ctypes.byref(text_sid)):
            raise LaunchRejected("process_token_unverifiable")
        return text_sid.value
    finally:
        if text_sid:
            kernel.LocalFree(ctypes.cast(text_sid, wintypes.HLOCAL))
        kernel.CloseHandle(handle)


def _verify_protected_profile(path):
    # Path shape/hash cannot establish Windows owner/DACL or directory custody.
    # Intentionally unavailable until independently reviewed deployment controls.
    raise LaunchRejected("protected_profile_acl_verification_unavailable")


def _verify_deployment_integrity(policy):
    # Must establish the complete interpreter/DLL/stdlib/dependency/import closure,
    # its protected ownership and absence of untrusted import hooks/search paths.
    # A caller's file list or digest is insufficient evidence of that closure.
    raise LaunchRejected("deployment_integrity_verification_unavailable")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LaunchRejected("ambiguous_launch_profile")
        result[key] = value
    return result


def _absolute(value):
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise LaunchRejected("unsafe_deployment_path")
    path = Path(value)
    if path.is_symlink() or path.absolute() != path.resolve(strict=True):
        raise LaunchRejected("unsafe_deployment_path")
    return path


def authenticate_operator(profile_path):
    from app import aapl_net_margin_proposal as proposal, sec_evidence_adapter as evidence
    sid = _process_token_sid()
    if not isinstance(sid, str) or not re.fullmatch(r"S-1-[0-9]+(?:-[0-9]+)+", sid):
        raise LaunchRejected("process_token_unverifiable")
    path = _absolute(str(profile_path))
    repository = Path(__file__).resolve().parents[2]
    if path.is_relative_to(repository):
        raise LaunchRejected("launch_profile_must_be_outside_repository")
    _verify_protected_profile(path)  # Before reading an untrusted policy.
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise LaunchRejected("launch_profile_size_limit")
    data = json.loads(raw, object_pairs_hook=_unique)
    fields = {"version", "deployment_id", "operator_sids", "approval", "approval_sha256",
              "evidence_policy_sha256", "python_executable", "import_roots", "original_store", "protected_files"}
    if not isinstance(data, dict) or set(data) != fields or type(data["version"]) is not int or data["version"] != 1:
        raise LaunchRejected("invalid_launch_profile")
    if data["approval"] != {"permission": proposal.REF.permission, "id": proposal.REF.approval_id,
                            "version": proposal.REF.version} or type(data["approval"].get("version")) is not int:
        raise LaunchRejected("wrong_authorization_scope")
    if (data["approval_sha256"] != evidence.approval_digest(proposal.PROPOSED_DENOMINATOR_AUTHORIZATION)
            or data["evidence_policy_sha256"] != evidence._policy_digest(proposal.PROPOSED_EVIDENCE_POLICY)):
        raise LaunchRejected("changed_approved_scope")
    sids = data["operator_sids"]
    if (not isinstance(sids, list) or not sids or any(not isinstance(s, str) or
            not re.fullmatch(r"S-1-[0-9]+(?:-[0-9]+)+", s) for s in sids) or sid not in sids):
        raise LaunchRejected("operator_not_authorized")
    if not isinstance(data["deployment_id"], str) or not data["deployment_id"].strip():
        raise LaunchRejected("invalid_deployment_identity")
    if _absolute(data["python_executable"]) != Path(sys.executable).resolve(strict=True):
        raise LaunchRejected("wrong_interpreter")
    if not isinstance(data["import_roots"], list) or not data["import_roots"]:
        raise LaunchRejected("missing_import_roots")
    roots = tuple(_absolute(p) for p in data["import_roots"])
    store = _absolute(data["original_store"])
    if not store.is_dir() or store.is_relative_to(repository) or any(not p.is_dir() for p in roots):
        raise LaunchRejected("unsafe_original_store_or_import_root")
    if store != _absolute(os.environ.get("FINLENS_SEC_ORIGINAL_STORE", "")):
        raise LaunchRejected("original_store_configuration_mismatch")
    items = data["protected_files"]
    if not isinstance(items, list) or not items:
        raise LaunchRejected("missing_deployment_inventory")
    pins = []
    for item in items:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise LaunchRejected("invalid_deployment_inventory")
        file = _absolute(item["path"])
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]:
            raise LaunchRejected("deployment_file_changed")
        pins.append((file, item["sha256"]))
    if len({p for p, _ in pins}) != len(pins):
        raise LaunchRejected("ambiguous_deployment_inventory")
    policy = DeploymentPolicy(data["deployment_id"], tuple(sids), store, tuple(pins), roots)
    _verify_deployment_integrity(policy)
    _verify_protected_profile(path)  # Custody must remain valid across the read.
    return policy


@contextmanager
def maintenance_exclusion(policy):
    # No current lock proves exclusion of all raw import/bootstrap/publication
    # writers AND original-store mutation. Existing advisory locks alone do not.
    # A future lease must hold both protections, with ownership/loss checks, from
    # fresh validation through server shutdown. No bool bypass. Contract:
    # assert_held() -> None performs a fresh authoritative check of identity,
    # scope, expiry and renewal; unknown/lost ownership raises BaseException.
    # subscribe_loss(callback) -> None atomically installs loss monitoring and
    # reports already-lost ownership. Publish invalidity before callback(error),
    # outside provider locks. Notify expiry/revocation/renewal/monitor failure
    # promptly even while consumers are idle. Never silently renew/revive a lost
    # lease. Deliberate context release after shutdown is not loss notification.
    raise LaunchRejected("maintenance_exclusion_unavailable")
    yield  # Context-manager shape; unreachable until a separately reviewed change.
