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
import struct
import sys

from app.activation_lifecycle import LaunchRejected


@dataclass(frozen=True)
class DeploymentPolicy:
    deployment_id: str
    operator_sids: tuple[str, ...]
    original_store: Path
    protected_files: tuple[tuple[Path, str], ...]
    import_roots: tuple[Path, ...]
    code_root: Path
    runtime_roots: tuple[Path, ...]
    configuration_files: tuple[Path, ...]
    custodian_sids: tuple[str, ...]


# Well-known Windows platform principals, not an installed operator allowlist.
# Delegated/user custodians are deliberately outside this initial supported subset.
_CUSTODIANS = frozenset({"S-1-5-18", "S-1-5-32-544"})
_MODIFY = 0x000D0156  # write/append/EA/attributes/delete-child/DELETE/WRITE_DAC/OWNER
_FILE_ALL = 0x001F01FF


@dataclass(frozen=True)
class SecurityDescriptor:
    owner: str
    aces: tuple[tuple[str, int, int], ...]  # SID, mapped file rights, ACE flags
    token_access: int
    token_is_custodian: bool
    dacl_protected: bool


def _file_mask(mask):
    if type(mask) is not int or not 0 <= mask <= 0xFFFFFFFF:
        raise LaunchRejected("unsupported_security_descriptor")
    mapped = mask & 0x0FFFFFFF
    for generic, rights in ((0x80000000, 0x120089), (0x40000000, 0x120116),
                            (0x20000000, 0x1200A0), (0x10000000, _FILE_ALL)):
        if mask & generic:
            mapped |= rights
    if mapped & ~_FILE_ALL:
        raise LaunchRejected("unsupported_security_descriptor")
    return mapped


def _decode_acl(raw):
    """Support ordinary allow ACEs only; no optimistic deny/conditional evaluation."""
    if len(raw) < 8:
        raise LaunchRejected("unsupported_security_descriptor")
    revision, reserved, size, count, reserved2 = struct.unpack_from("<BBHHH", raw)
    if revision != 2 or reserved or reserved2 or size != len(raw) or count > 4096:
        raise LaunchRejected("unsupported_security_descriptor")
    offset, aces = 8, []
    for _ in range(count):
        if offset + 16 > size:
            raise LaunchRejected("unsupported_security_descriptor")
        kind, flags, length, mask = struct.unpack_from("<BBHI", raw, offset)
        sid_revision, subs = raw[offset + 8:offset + 10]
        if (kind != 0 or flags & ~0x1F or sid_revision != 1 or subs > 15
                or length != 16 + 4 * subs or offset + length > size):
            raise LaunchRejected("unsupported_security_descriptor")
        authority = int.from_bytes(raw[offset + 10:offset + 16], "big")
        values = struct.unpack_from("<" + "I" * subs, raw, offset + 16)
        sid = f"S-1-{authority}" + "".join(f"-{value}" for value in values)
        aces.append((sid, _file_mask(mask), flags))
        offset += length
    if any(raw[offset:]):
        raise LaunchRejected("unsupported_security_descriptor")
    return tuple(aces)


def _windows_security(path):
    """Read native owner/DACL and AccessCheck the actual process impersonation token.

    No grants, token adjustment or impersonation of the running thread occurs.
    LocalFree/CloseHandle release only API allocations/handles, never filesystem data.
    """
    if os.name != "nt":
        raise LaunchRejected("windows_security_required")
    import ctypes as c
    from ctypes import wintypes as w
    kernel, api = c.WinDLL("kernel32", use_last_error=True), c.WinDLL("advapi32", use_last_error=True)
    ptr = c.c_void_p
    signatures = {
        "GetNamedSecurityInfoW": ([w.LPWSTR, w.DWORD, w.DWORD, c.POINTER(ptr), ptr, c.POINTER(ptr), ptr, c.POINTER(ptr)], w.DWORD),
        "IsValidSecurityDescriptor": ([ptr], w.BOOL),
        "GetSecurityDescriptorControl": ([ptr, c.POINTER(w.WORD), c.POINTER(w.DWORD)], w.BOOL),
        "IsValidAcl": ([ptr], w.BOOL),
        "ConvertSidToStringSidW": ([ptr, c.POINTER(w.LPWSTR)], w.BOOL),
        "ConvertStringSidToSidW": ([w.LPCWSTR, c.POINTER(ptr)], w.BOOL),
        "OpenProcessToken": ([w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL),
        "DuplicateToken": ([w.HANDLE, c.c_int, c.POINTER(w.HANDLE)], w.BOOL),
        "CheckTokenMembership": ([w.HANDLE, ptr, c.POINTER(w.BOOL)], w.BOOL),
        "AccessCheck": ([ptr, w.HANDLE, w.DWORD, ptr, ptr, c.POINTER(w.DWORD), c.POINTER(w.DWORD), c.POINTER(w.BOOL)], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ptr], ptr
    owner, dacl, descriptor, admin = ptr(), ptr(), ptr(), ptr()
    sid_text, process, token = w.LPWSTR(), w.HANDLE(), w.HANDLE()
    try:
        if (api.GetNamedSecurityInfoW(str(path), 1, 0x7, c.byref(owner), None,
                                     c.byref(dacl), None, c.byref(descriptor)) != 0
                or not descriptor or not owner or not dacl
                or not api.IsValidSecurityDescriptor(descriptor) or not api.IsValidAcl(dacl)):
            raise LaunchRejected("security_descriptor_unverifiable")
        control, revision = w.WORD(), w.DWORD()
        if (not api.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision))
                or revision.value != 1 or not control.value & 4 or control.value & 0x9):
            raise LaunchRejected("unsupported_security_descriptor")
        if not api.ConvertSidToStringSidW(owner, c.byref(sid_text)):
            raise LaunchRejected("security_descriptor_unverifiable")
        size = struct.unpack_from("<H", c.string_at(dacl, 8), 2)[0]
        if not 8 <= size <= 65535:
            raise LaunchRejected("unsupported_security_descriptor")
        aces = _decode_acl(c.string_at(dacl, size))
        if (not api.OpenProcessToken(kernel.GetCurrentProcess(), 0xA, c.byref(process))
                or not api.DuplicateToken(process, 2, c.byref(token))
                or not api.ConvertStringSidToSidW("S-1-5-32-544", c.byref(admin))):
            raise LaunchRejected("security_token_unverifiable")
        member = w.BOOL()
        if not api.CheckTokenMembership(token, admin, c.byref(member)):
            raise LaunchRejected("security_token_unverifiable")
        # GENERIC_MAPPING has four DWORDs. AccessCheck accounts for token groups,
        # disabled/deny-only groups, ownership and the supported DACL's ACE order.
        mapping = (w.DWORD * 4)(0x120089, 0x120116, 0x1200A0, _FILE_ALL)
        length, granted, status = w.DWORD(65536), w.DWORD(), w.BOOL()
        privileges = c.create_string_buffer(length.value)
        if not api.AccessCheck(descriptor, token, 0x02000000, mapping, privileges,
                               c.byref(length), c.byref(granted), c.byref(status)) or length.value > 65536:
            raise LaunchRejected("effective_access_unverifiable")
        # A successful API call may report no granted access. That is not an API
        # failure; group grants for every principal are still checked separately.
        if not status.value and granted.value:
            raise LaunchRejected("effective_access_unverifiable")
        return SecurityDescriptor(sid_text.value, aces, _file_mask(granted.value),
                                  bool(member.value) or _process_token_sid() == "S-1-5-18",
                                  bool(control.value & 0x1000))
    finally:
        for allocation in (c.cast(sid_text, ptr), admin, descriptor):
            if allocation:
                kernel.LocalFree(allocation)
        for handle in (token, process):
            if handle:
                kernel.CloseHandle(handle)


def _check_security(descriptor):
    if (type(descriptor) is not SecurityDescriptor or descriptor.owner not in _CUSTODIANS
            or type(descriptor.token_is_custodian) is not bool
            or type(descriptor.dacl_protected) is not bool or type(descriptor.aces) is not tuple):
        raise LaunchRejected("protected_profile_acl_untrusted_owner")
    for ace in descriptor.aces:
        if type(ace) is not tuple or len(ace) != 3:
            raise LaunchRejected("unsupported_security_descriptor")
        sid, mask, flags = ace
        if (not isinstance(sid, str) or not re.fullmatch(r"S-1-[0-9]+(?:-[0-9]+)+", sid)
                or type(flags) is not int or flags & ~0x1F):
            raise LaunchRejected("unsupported_security_descriptor")
        # All inherited/group grants are inspected; inherit-only grants are also
        # rejected conservatively when they could give unsafe descendant custody.
        if _file_mask(mask) & _MODIFY and sid not in _CUSTODIANS:
            raise LaunchRejected("protected_profile_acl_unauthorized_modification")
    if _file_mask(descriptor.token_access) & _MODIFY and not descriptor.token_is_custodian:
        raise LaunchRejected("protected_profile_acl_effective_modification")


def _verify_custody(path):
    try:
        path = _absolute(str(path))
        for node in (*reversed(path.parents), path):
            _absolute(str(node))
            _check_security(_windows_security(node))
    except (OSError, ValueError, TypeError, struct.error):
        raise LaunchRejected("security_descriptor_unverifiable") from None


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
    _verify_custody(path)  # Includes ancestor write/delete/replacement permissions.


def _verify_external_bootstrap(policy):
    # No assertion inside Python can authenticate its already executed startup
    # hooks/native loader/code. A separately reviewed protected launch mechanism
    # must establish that trust BEFORE Python runs. No profile/boolean/env bypass.
    raise LaunchRejected("deployment_integrity_external_bootstrap_unavailable")


def _check_import_paths(policy):
    if not sys.flags.isolated or not sys.flags.safe_path:
        raise LaunchRejected("deployment_integrity_unisolated_bootstrap")
    import site
    if site.ENABLE_USER_SITE is not False:
        raise LaunchRejected("deployment_integrity_user_site")
    if any(os.environ.get(key) for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")):
        raise LaunchRejected("deployment_integrity_ambient_import_configuration")
    from importlib.machinery import BuiltinImporter, FrozenImporter, PathFinder
    if tuple(sys.meta_path) != (BuiltinImporter, FrozenImporter, PathFinder):
        raise LaunchRejected("deployment_integrity_unreviewed_import_hook")
    directories = set(policy.import_roots)
    for entry in sys.path:
        path = _absolute(entry)
        if not any(path == root or path.is_relative_to(root) for root in policy.import_roots):
            raise LaunchRejected("deployment_integrity_unreviewed_import_path")
        _verify_custody(path)
        if path.is_dir():
            directories.add(path)
    # Never bless a hook merely because its bytes have a hash. Python may have
    # executed .pth before these checks; the external anchor still must reject.
    for root in directories:
        for hook in root.glob("*.pth"):
            _verify_custody(hook)
            with hook.open("rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise LaunchRejected("deployment_integrity_pth_size")
            if any(line.strip() and not line.lstrip().startswith("#")
                   for line in raw.decode("utf-8-sig").splitlines()):
                raise LaunchRejected("deployment_integrity_pth_hook_or_path")


def _verify_deployment_integrity(policy):
    if frozenset(policy.custodian_sids) != _CUSTODIANS:
        raise LaunchRejected("deployment_integrity_unsupported_custodians")
    if policy.code_root != Path(__file__).resolve().parents[1]:
        raise LaunchRejected("deployment_integrity_wrong_code_root")
    for path in (policy.code_root, *policy.runtime_roots, *policy.import_roots,
                 policy.original_store, *policy.configuration_files):
        _verify_custody(path)
    for prefix in (sys.prefix, sys.base_prefix):
        if _absolute(prefix) not in policy.runtime_roots:
            raise LaunchRejected("deployment_integrity_missing_runtime_root")
    if any(not any(root == base or root.is_relative_to(base)
                   for base in (policy.code_root, *policy.runtime_roots))
           for root in policy.import_roots):
        raise LaunchRejected("deployment_integrity_unreviewed_import_root")
    pins = dict(policy.protected_files)
    required = {Path(sys.executable).resolve(strict=True), Path(__file__).resolve(),
                policy.code_root / "app" / "aapl_net_margin_launcher.py",
                *policy.configuration_files}
    backend_env = policy.code_root / ".env"
    if backend_env.exists():
        required.add(backend_env)
    if not required <= pins.keys():
        raise LaunchRejected("deployment_integrity_incomplete_inventory")
    for path, digest in policy.protected_files:
        _verify_custody(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise LaunchRejected("deployment_integrity_file_changed")
    _check_import_paths(policy)
    _verify_external_bootstrap(policy)  # ALWAYS rejects; pins are not closure proof.


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
    if ((os.name == "nt" and not path.drive) or path.drive.startswith("\\\\")
            or any(part.endswith((" ", ".")) or ":" in part for part in path.parts[1:])
            or getattr(path.lstat(), "st_file_attributes", 0) & 0x400
            or (path.is_file() and path.stat().st_nlink != 1)
            or path.is_symlink() or path.absolute() != path.resolve(strict=True)):
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
              "evidence_policy_sha256", "python_executable", "import_roots", "original_store", "protected_files",
              "code_root", "runtime_roots", "configuration_files", "custodian_sids", "custodian_access"}
    if not isinstance(data, dict) or set(data) != fields or type(data["version"]) is not int or data["version"] != 2:
        raise LaunchRejected("invalid_launch_profile")
    if data["approval"] != {"permission": proposal.REF.permission, "id": proposal.REF.approval_id,
                            "version": proposal.REF.version} or type(data["approval"].get("version")) is not int:
        raise LaunchRejected("wrong_authorization_scope")
    if (data["approval_sha256"] != evidence.approval_digest(proposal.PROPOSED_DENOMINATOR_AUTHORIZATION)
            or data["evidence_policy_sha256"] != evidence._policy_digest(proposal.PROPOSED_EVIDENCE_POLICY)):
        raise LaunchRejected("changed_approved_scope")
    sids = data["operator_sids"]
    if (not isinstance(sids, list) or not sids or any(not isinstance(s, str) or
            not re.fullmatch(r"S-1-[0-9]+(?:-[0-9]+)+", s) for s in sids)
            or len(set(sids)) != len(sids) or sid not in sids):
        raise LaunchRejected("operator_not_authorized")
    custodians = data["custodian_sids"]
    if (not isinstance(custodians, list) or any(not isinstance(s, str) for s in custodians)
            or len(set(custodians)) != len(custodians) or frozenset(custodians) != _CUSTODIANS
            or data["custodian_access"] != "full_control"):
        raise LaunchRejected("unsupported_custodian_policy")
    if not isinstance(data["deployment_id"], str) or not data["deployment_id"].strip():
        raise LaunchRejected("invalid_deployment_identity")
    if _absolute(data["python_executable"]) != Path(sys.executable).resolve(strict=True):
        raise LaunchRejected("wrong_interpreter")
    if not isinstance(data["import_roots"], list) or not data["import_roots"]:
        raise LaunchRejected("missing_import_roots")
    roots = tuple(_absolute(p) for p in data["import_roots"])
    code = _absolute(data["code_root"])
    if (not isinstance(data["runtime_roots"], list) or not data["runtime_roots"]
            or not isinstance(data["configuration_files"], list)):
        raise LaunchRejected("invalid_runtime_or_configuration_inventory")
    runtimes = tuple(_absolute(p) for p in data["runtime_roots"])
    configurations = tuple(_absolute(p) for p in data["configuration_files"])
    if (not code.is_dir() or any(not p.is_dir() for p in runtimes)
            or any(not p.is_file() for p in configurations)
            or len(set(roots)) != len(roots) or len(set(runtimes)) != len(runtimes)
            or len(set(configurations)) != len(configurations)):
        raise LaunchRejected("ambiguous_deployment_roots_or_configuration")
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
    policy = DeploymentPolicy(data["deployment_id"], tuple(sids), store, tuple(pins), roots,
                              code, runtimes, configurations, tuple(custodians))
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
