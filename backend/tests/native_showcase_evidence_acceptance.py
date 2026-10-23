"""REL-DEMO-03D review candidate. Inert on import; native execution is default-off.

Preparation does not authorize invocation. No historical inputs, preservation
orchestration, output receipts, cleanup, retries, or fixture relocation exist.
Only a separately approved, externally supervised foreground run may opt in.
"""

FIXTURE = "FinLens-NativeValidation-REL-DEMO-03D-v1"
ADAPTER_SHA256 = "ce215717bebd1ad2b74d820293d927e7e0fe2ae2dd0e03b32fc0b30fd9718e34"
SUPERVISION = "foreground:120s-total:30s-call:5s-interrupt:retain-on-abort"
FILE_READ_DATA = 0x00000001
FILE_WRITE_DATA = 0x00000002
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
SYNCHRONIZE = 0x00100000
FILE_GENERIC_READ = 0x00120089
SHARE_ALL = 0x00000007
FILE_OPEN = 1
FILE_CREATE = 2
STATUS_SHARING_VIOLATION = 0xC0000043
STATUS_OBJECT_NAME_COLLISION = 0xC0000035
USERS_SID = "S-1-5-32-545"


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


class Handles:
    """Register before validation; close each owned handle once, even after error."""

    def __init__(self, api):
        self.api = api
        self.owned = []
        self.close_errors = []

    def own(self, handle):
        require(handle not in self.owned, "duplicate_owned_handle")
        # Append first: even a subsequent validation failure owns this handle.
        self.owned.append(handle)
        require(bool(handle) and self.owned.count(handle) == 1, "invalid_owned_handle")
        require(len(self.owned) <= 128, "owned_handle_bound")
        return handle

    def close_one(self, handle):
        self.owned.remove(handle)  # No retry, including after CloseHandle failure.
        try:
            self.api.close(handle)
        except BaseException as exc:
            self.close_errors.append(exc)
            raise

    def close_all(self):
        for handle in tuple(reversed(self.owned)):
            try:
                self.close_one(handle)
            except BaseException:
                continue  # Original failure and every close error remain retained.


def raw_open(api, handles, parent, name, access, directory=False, collision=False):
    """Test-only native-status probe. No absolute path or replacement disposition."""
    require(name in (FIXTURE, "payload.bin", "unexpected-acl.bin"), "probe_name")
    require(not directory or (collision and name == FIXTURE), "probe_directory")
    if collision:
        require(access == (0x1200A1 if directory else 0xC0120000), "collision_access")
    else:
        require(access in (FILE_GENERIC_READ,
                           FILE_WRITE_DATA | SYNCHRONIZE,
                           DELETE | SYNCHRONIZE,
                           READ_CONTROL | WRITE_DAC | SYNCHRONIZE), "probe_access")
    c = api.c
    buf = c.create_unicode_buffer(name)
    length = len(name.encode("utf-16-le"))
    us = api.US(length, length + 2, c.cast(buf, c.c_void_p))
    oa = api.OA(c.sizeof(api.OA), parent, c.pointer(us), 0x1040, None, None)
    out, ios = c.c_void_p(), api.IOS()
    # OPEN_REPARSE_POINT | SYNCHRONOUS_IO_NONALERT | DIRECTORY/NON_DIRECTORY.
    # No DELETE_ON_CLOSE; FILE_CREATE is restricted to exclusive collision cases.
    options = 0x200000 | 0x20 | (1 if directory else 0x40)
    status = api.NtCreateFile(c.byref(out), access, c.byref(oa), c.byref(ios),
                              None, 0, SHARE_ALL,
                              FILE_CREATE if collision else FILE_OPEN,
                              options, None, 0)
    handle = handles.own(out.value) if out.value else None
    status &= 0xFFFFFFFF
    # Information has no universal value contract on failure. Only return it
    # on STATUS_SUCCESS; FILE_OPEN callers then require FILE_OPENED (1).
    return status, handle, ios.Information if status == 0 else None


def expect_native_failure(api, handles, parent, name, access, expected,
                          directory=False, collision=False):
    status, handle, _ = raw_open(
        api, handles, parent, name, access, directory, collision)
    if handle is not None:
        # Even unexpected success is registered, closed, and terminal. If close
        # itself fails, outer closure still attempts every other owned handle.
        handles.close_one(handle)
        raise RuntimeError("unexpected_probe_handle")
    require(status == expected, "wrong_native_status")


def sharing_checks(p, api, handles, directory, source, expected, spec):
    # The production source handle remains open with FILE_SHARE_READ only.
    status, control, information = raw_open(
        api, handles, directory, "payload.bin", FILE_GENERIC_READ)
    require(status == 0 and control is not None and information == 1,
            "compatible_read_open")
    p.check_observation(api.observe(control), expected)
    p.read_checked(api, control, spec)
    p.compare_streams(api, source, control, spec.size)
    handles.close_one(control)
    expect_native_failure(api, handles, directory, "payload.bin",
                          FILE_WRITE_DATA | SYNCHRONIZE, STATUS_SHARING_VIOLATION)
    expect_native_failure(api, handles, directory, "payload.bin",
                          DELETE | SYNCHRONIZE, STATUS_SHARING_VIOLATION)


def release_local(api, pointer, code):
    """Free a query allocation without masking an already active failure."""
    import sys

    primary = sys.exc_info()[1]
    try:
        require(not api.LocalFree(pointer), code)
    except BaseException:
        if primary is None:
            raise
        print("Additional native allocation-release failure:", code)


def security_snapshot(api, handle):
    """Copy owner/group, descriptor controls and exact ACE bytes; never query SACL."""
    c = api.c
    security = c.WinDLL("advapi32", use_last_error=True)
    control_fn = security.GetSecurityDescriptorControl
    control_fn.restype = c.c_int
    control_fn.argtypes = [c.c_void_p, c.POINTER(c.c_uint16), c.POINTER(c.c_uint32)]
    owner, group, dacl, sd = (c.c_void_p() for _ in range(4))
    try:
        result = api.GetSecurityInfo(handle, 1, 7, c.byref(owner), c.byref(group),
                                     c.byref(dacl), None, c.byref(sd))
        require(result == 0 and sd.value and owner.value and group.value,
                "acl_snapshot_api")
        require(bool(dacl.value), "null_dacl")
        control, revision = c.c_uint16(), c.c_uint32()
        require(control_fn(sd, c.byref(control), c.byref(revision)), "sd_control_api")
        info = api.ACLINFO()
        require(api.GetAclInformation(dacl, c.byref(info), c.sizeof(info), 2),
                "acl_information_api")
        require(0 < info.AceCount <= 16 and info.AclBytesInUse <= 65535, "acl_bound")
        aces = []
        for index in range(info.AceCount):
            ace = c.c_void_p()
            require(api.GetAce(dacl, index, c.byref(ace)) and ace.value, "get_ace_api")
            header = c.string_at(ace.value, 4)
            size = int.from_bytes(header[2:4], "little")
            require(8 <= size <= info.AclBytesInUse, "acl_ace_bound")
            aces.append(c.string_at(ace.value, size))
        return {"owner": api.sid(owner), "group": api.sid(group),
                "control": control.value, "sd_revision": revision.value,
                "acl_revision": c.string_at(dacl.value, 1)[0], "aces": tuple(aces)}
    finally:
        if sd.value:
            release_local(api, sd, "security_local_free")


def add_users_read_ace(api, handle, before):
    """One handle-based DACL-only operation, preserving original raw ACE sequence."""
    c = api.c
    security = c.WinDLL("advapi32", use_last_error=True)
    convert = security.ConvertStringSidToSidW
    convert.restype, convert.argtypes = c.c_int, [c.c_wchar_p, c.POINTER(c.c_void_p)]
    length_fn = security.GetLengthSid
    length_fn.restype, length_fn.argtypes = c.c_uint32, [c.c_void_p]
    initialize = security.InitializeAcl
    initialize.restype, initialize.argtypes = c.c_int, [c.c_void_p, c.c_uint32, c.c_uint32]
    append = security.AddAce
    append.restype, append.argtypes = c.c_int, [c.c_void_p, c.c_uint32, c.c_uint32,
                                              c.c_void_p, c.c_uint32]
    set_security = security.SetSecurityInfo
    set_security.restype = c.c_uint32
    set_security.argtypes = [c.c_void_p, c.c_int, c.c_uint32] + [c.c_void_p] * 4
    sid = c.c_void_p()
    try:
        require(convert(USERS_SID, c.byref(sid)) and sid.value, "users_sid_api")
        length = length_fn(sid)
        require(8 <= length <= 68 and api.sid(sid) == USERS_SID, "users_sid_exact")
        # ACCESS_ALLOWED_ACE_TYPE=0; AceFlags=0: explicit and non-inheritable.
        ace = (bytes((0, 0)) + (8 + length).to_bytes(2, "little")
               + FILE_GENERIC_READ.to_bytes(4, "little") + c.string_at(sid.value, length))
        sequence = (ace,) + before["aces"]
        size = 8 + sum(map(len, sequence))
        require(size <= 65535, "new_acl_bound")
        acl = c.create_string_buffer(size)
        require(initialize(acl, size, before["acl_revision"]), "initialize_acl_api")
        for raw in sequence:
            buf = c.create_string_buffer(raw)
            require(append(acl, before["acl_revision"], 0xFFFFFFFF, buf, len(raw)),
                    "add_ace_api")
        # SE_FILE_OBJECT=1; DACL_SECURITY_INFORMATION=4 ONLY. No owner/group/SACL
        # pointers, protected/unprotected toggles, or path-based security setter.
        require(set_security(handle, 1, 4, None, None, acl, None) == 0,
                "set_dacl_api")
        return dict(before, aces=sequence)
    finally:
        if sid.value:
            release_local(api, sid, "sid_local_free")


def acl_negative(p, api, handles, directory, reader, expected, spec, operator, guard):
    status, handle, information = raw_open(
        api, handles, directory, "unexpected-acl.bin",
        READ_CONTROL | WRITE_DAC | SYNCHRONIZE)
    require(status == 0 and handle is not None and information == 1, "dacl_handle_open")
    guard()
    observation = api.observe(handle)
    p.check_observation(observation, expected)  # Includes links=1 and non-reparse.
    p.check_private(observation, operator)
    p.read_checked(api, reader, spec)
    before = security_snapshot(api, handle)
    # Fresh identity/policy checks immediately before the only security mutation.
    guard()
    p.check_observation(api.observe(handle), expected)
    wanted = add_users_read_ace(api, handle, before)
    after = security_snapshot(api, handle)
    require(after == wanted, "acl_delta_not_exact")
    changed = api.observe(handle)
    post_identity = dict(expected, security_sha256=changed["security_sha256"])
    p.check_observation(changed, post_identity)
    require(changed["owner_sid"] == observation["owner_sid"] == operator,
            "acl_owner_changed")
    require(changed["aces"] == ((USERS_SID, FILE_GENERIC_READ, 0, 0),)
            + observation["aces"], "acl_semantic_delta")
    p.read_checked(api, reader, spec)
    try:
        p.check_private(changed, operator)
    except p.Stop as exc:
        require(str(exc) == "private_principals", "unrelated_private_policy_failure")
    else:
        raise RuntimeError("private_principals_not_rejected")
    # Deliberately retain the changed fixture; do not restore the DACL.
    handles.close_one(handle)


def approved_run(p, api, approval, clock):
    import ntpath
    import hashlib

    handles = Handles(api)
    existing, synthetic = [], []
    primary, result = None, None
    deadline = clock.monotonic() + 120

    def check_time():
        require(clock.monotonic() < deadline, "supervision_deadline")

    def guard():
        check_time()
        for handle, expected in existing:
            p.check_observation(api.observe(handle), expected)
        p.check_private(api.observe(existing[-1][0]), approval["operator_sid"])
        for handle, expected in synthetic:
            observation = api.observe(handle)
            p.check_observation(observation, expected)
            p.check_private(observation, approval["operator_sid"])
        check_time()

    def create(parent, name, directory):
        # Last authorization-relevant observations before EACH exclusive create.
        guard()
        handle = handles.own(api.create_child(parent, name, directory))
        observation, parent_observation = api.observe(handle), api.observe(parent)
        require(observation["volume_serial"] == parent_observation["volume_serial"]
                and observation["final_path"] == parent_observation["final_path"].rstrip("\\")
                + "\\" + name and observation["directory"] is directory,
                "fixture_containment")
        expected = p.identity(observation)
        p.check_observation(observation, expected)
        p.check_private(observation, approval["operator_sid"])
        synthetic.append((handle, expected))
        return handle, expected

    def finish_writer(parent, name, writer, expected):
        handles.close_one(writer)
        synthetic.remove((writer, expected))
        reader = handles.own(api.open_child(parent, name, False))
        p.check_observation(api.observe(reader), expected)
        synthetic.append((reader, expected))
        return reader

    def spec(name, data):
        return p.Spec("synthetic-" + name, "", len(data), hashlib.sha256(data).hexdigest(), name)

    def seed(parent, name, data):
        writer, expected = create(parent, name, False)
        require(api.write(writer, data) == len(data), "fixture_short_write")
        api.flush(writer)
        reader = finish_writer(parent, name, writer, expected)
        expected_spec = spec(name, data)
        require(p.read_checked(api, reader, expected_spec, True) == data, "fixture_bytes")
        return reader, expected, expected_spec

    try:
        require(api.operator() == (approval["operator_sid"], approval["operator_name"]),
                "operator_mismatch")
        require(api.known_folder() == approval["local_app_data"], "known_folder_mismatch")
        chain = p.path_chain(approval["local_app_data"])
        parent = None
        # EVERY existing component is reopened, from approved volume root onward.
        for path in chain:
            expected = approval["bindings"][path]
            handle = handles.own(api.open_volume(expected["final_path"]) if parent is None
                                  else api.open_child(parent, ntpath.basename(path), True))
            p.check_observation(api.observe(handle), expected)
            existing.append((handle, expected))
            parent = handle
        root, root_id = create(parent, FIXTURE, True)
        source_dir, _ = create(root, "source", True)
        destination_dir, _ = create(root, "destination", True)
        decoy_dir, _ = create(root, "decoy", True)
        payload = bytes(i % 251 for i in range(131089))
        source, source_id, source_spec = seed(source_dir, "payload.bin", payload)
        decoy, decoy_id, _ = seed(decoy_dir, "payload.bin", b"not-source\n")
        require(source_id["file_id"] != decoy_id["file_id"], "source_decoy_identity")
        # Opening the same basename must resolve against the retained parent.
        relative = handles.own(api.open_child(source_dir, "payload.bin", False))
        p.check_observation(api.observe(relative), source_id)
        require(p.read_checked(api, relative, source_spec, True) == payload, "relative_bytes")
        handles.close_one(relative)
        output, output_id = create(destination_dir, "payload.bin", False)
        p.copy_exact(api, source, output, source_spec)
        destination = finish_writer(destination_dir, "payload.bin", output, output_id)
        require(source_id["file_id"] != output_id["file_id"], "copy_identity")
        p.read_checked(api, destination, source_spec)
        p.compare_streams(api, source, destination, source_spec.size)
        acl_reader, acl_id, acl_spec = seed(
            source_dir, "unexpected-acl.bin", b"synthetic ACL probe\n")
        guard()
        sharing_checks(p, api, handles, source_dir, source, source_id, source_spec)
        expect_native_failure(api, handles, parent, FIXTURE, 0x1200A1,
                              STATUS_OBJECT_NAME_COLLISION, directory=True, collision=True)
        # Close the destination reader before collision testing so share denial
        # cannot masquerade as an exclusive-creation collision.
        handles.close_one(destination)
        synthetic.remove((destination, output_id))
        expect_native_failure(api, handles, destination_dir, "payload.bin", 0xC0120000,
                              STATUS_OBJECT_NAME_COLLISION, collision=True)
        destination = handles.own(api.open_child(destination_dir, "payload.bin", False))
        p.check_observation(api.observe(destination), output_id)
        synthetic.append((destination, output_id))
        p.read_checked(api, destination, source_spec)
        guard()
        acl_negative(p, api, handles, source_dir, acl_reader, acl_id, acl_spec,
                     approval["operator_sid"], guard)
        check_time()
        result = {"native_synthetic": "PASS", "directories": 4, "files": 4,
                  "fixture_bytes": 2 * len(payload) + 11 + 20,
                  "sharing_write": "STATUS_SHARING_VIOLATION",
                  "sharing_delete": "STATUS_SHARING_VIOLATION",
                  "acl_negative": "private_principals_after_exact_delta",
                  "reparse_creation": "NOT TESTED", "historical_evidence": "NOT ACCESSED"}
    except BaseException as exc:
        primary = exc
    finally:
        handles.close_all()
    if primary is not None:
        if handles.close_errors:
            print("Additional owned-handle close failures:", len(handles.close_errors))
        raise primary
    if handles.close_errors:
        raise handles.close_errors[0]
    require(not handles.owned, "owned_handles_remaining")
    check_time()
    return result


def approval_path_chain(path):
    """Validate the complete DOS chain without executing any adapter code."""
    import ntpath
    import re

    require(isinstance(path, str) and re.fullmatch(r"[A-Z]:\\[^/]*", path)
            and len(path) <= 4096, "approved_parent_path")
    chain = [path[:3]]
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(10))
    for part in path[3:].split("\\") if path[3:] else ():
        require(0 < len(part) <= 255
                and not any(ch in '\\/:*?"<>|' or ord(ch) < 32 for ch in part)
                and part not in (".", "..") and part[-1] not in " ."
                and part.split(".")[0].upper() not in reserved, "approved_parent_component")
        chain.append(ntpath.join(chain[-1], part))
    return chain


def load_approval(raw, driver_digest):
    import json
    import re

    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate_approval_key")
            value[key] = item
        return value

    approval = json.loads(raw, object_pairs_hook=unique)
    require(isinstance(approval, dict) and set(approval) == {
        "task", "operator_sid", "operator_name", "local_app_data", "bindings",
        "reviewed_driver_sha256", "reviewed_adapter_sha256", "independent_review_sha256",
        "supervision"}, "approval_keys")
    require(approval["task"] == "REL-DEMO-03D" and approval["supervision"] == SUPERVISION,
            "approval_task_or_supervision")
    for name in ("reviewed_driver_sha256", "reviewed_adapter_sha256", "independent_review_sha256"):
        require(isinstance(approval[name], str) and re.fullmatch("[0-9a-f]{64}", approval[name]),
                "approval_hash")
    require(approval["reviewed_driver_sha256"] == driver_digest
            and approval["reviewed_adapter_sha256"] == ADAPTER_SHA256, "reviewed_source_hash")
    require(isinstance(approval["operator_sid"], str)
            and re.fullmatch(r"S-1-5-21-\d+-\d+-\d+-\d+", approval["operator_sid"])
            and isinstance(approval["operator_name"], str)
            and 0 < len(approval["operator_name"]) <= 256, "approved_operator")
    require(isinstance(approval["local_app_data"], str), "approved_parent")
    chain = approval_path_chain(approval["local_app_data"])
    require(1 < len(chain) <= 64 and isinstance(approval["bindings"], dict)
            and set(approval["bindings"]) == set(chain), "complete_existing_chain")
    previous = None
    volume_serial = None
    for index, path in enumerate(chain):
        expected = approval["bindings"][path]
        require(isinstance(expected, dict) and set(expected) == {
            "volume_serial", "file_id", "final_path", "security_sha256", "directory"},
                "identity_keys")
        require(expected["directory"] is True
                and type(expected["volume_serial"]) is int
                and 0 <= expected["volume_serial"] < 2 ** 64, "identity_directory_volume")
        for key, size in (("file_id", 32), ("security_sha256", 64)):
            require(isinstance(expected[key], str)
                    and re.fullmatch("[0-9a-f]{" + str(size) + "}", expected[key]), "identity_hash")
        final = expected["final_path"]
        require(isinstance(final, str), "identity_final_path")
        if index == 0:
            require(re.fullmatch(r"\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\", final), "approved_volume_root")
            volume_serial = expected["volume_serial"]
        else:
            require(final == previous.rstrip("\\") + "\\" + path.rsplit("\\", 1)[-1],
                    "approved_relative_chain")
        require(expected["volume_serial"] == volume_serial, "approved_same_volume")
        previous = final
    return approval


def main(argv=None):
    import sys

    args = sys.argv[1:] if argv is None else argv
    if args in ([], ["--help"]):
        print("Source review candidate; default OFF. No native operation requested.")
        return 0
    if args != ["--run-approved-native-synthetic"]:
        print("NO-GO: explicit separately approved native synthetic mode required.")
        return 2
    try:
        require(sys.platform == "win32" and sys.flags.isolated and sys.flags.no_site
                and sys.flags.dont_write_bytecode, "isolated_windows_python_required")
        import hashlib
        import pathlib
        import time
        import types

        # Reading source for hash binding is not historical evidence access.
        driver = pathlib.Path(__file__).resolve(strict=True)
        require(driver.name == "native_showcase_evidence_acceptance.py"
                and driver.parent.name == "tests" and driver.parent.parent.name == "backend",
                "driver_location")
        adapter = driver.parent.parent / "scripts" / "preserve_showcase_evidence.py"
        # This self-hash is an approval check, not proof of trusted driver launch.
        driver_digest = hashlib.sha256(driver.read_bytes()).hexdigest()
        raw = sys.stdin.buffer.read(65537)
        require(0 < len(raw) <= 65536, "approval_input_bound")
        approval = load_approval(raw, driver_digest)  # Full validation BEFORE adapter execution.
        adapter_source = adapter.read_bytes()  # Exactly one read; immutable bytes.
        require(hashlib.sha256(adapter_source).hexdigest()
                == approval["reviewed_adapter_sha256"], "adapter_source_hash")
        p = types.ModuleType("_rel_demo_03d_reviewed_adapter")
        p.__file__ = str(adapter)
        require(p.__name__ not in sys.modules, "adapter_namespace_exists")
        sys.modules[p.__name__] = p  # Required by dataclasses; separate module globals.
        adapter_code = compile(adapter_source, "<reviewed-rel-demo-03d-adapter>",
                               "exec", dont_inherit=True)
        exec(adapter_code, p.__dict__, p.__dict__)  # No pathname/cache loader or reread.
        api = p.WindowsAPI()  # First native binding, after all source/approval gates.
        result = approved_run(p, api, approval, time)
        import json
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print("ABORTED; retain fixture and partial state. No cleanup or retry.")
        return 130
    except Exception as exc:
        # Keep the primary category; never echo arbitrary exceptions/private paths.
        code = str(exc) if isinstance(exc, RuntimeError) else "unexpected_exception"
        if not code or len(code) > 80 or any(ch not in "abcdefghijklmnopqrstuvwxyz_" for ch in code):
            code = "unexpected_exception"
        print("FAIL:", code, "; retain partial state. No cleanup or retry.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
