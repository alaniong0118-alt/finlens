"""Fixed REL-DEMO-03 preservation candidate; real execution needs separate review.

Default invocation does not inspect evidence or load Windows APIs. The explicit
execution entry point requires private approval JSON on stdin, including the hash
of this reviewed tool and identity/security bindings for EVERY existing component.
Approval is a trusted operator attestation, not cryptographic authentication.
Only the private receipt may contain resolved personal paths. Never print them.
"""

import sys

# Also protect ordinary default invocation before importing any non-builtin module.
sys.dont_write_bytecode = True

import base64
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import ntpath
import re


REVISION = "cfa4521379bfde92331ba988b6b60a5887a39706"
REPOSITORY = r"D:\Projects\finlens-foundation"
MANIFEST = "docs/showcase/evidence-manifest.json"
MANIFEST_SHA256 = "457bb3acfed5eab81bd7249bee5453241190d254776b644a9468aaf761a87458"
CHILD = "FinLens-ShowcaseEvidence-REL-DEMO-03-v1"
RECEIPT = "custody-receipt.json"
CHUNK = 65536
FORBIDDEN_ATTRIBUTES = 0x400 | 0x1000 | 0x40000 | 0x400000
IDENTITY_KEYS = ("volume_serial", "file_id", "final_path", "security_sha256", "directory")
HISTORY = {
    "REL-DEMO-02 execution scope": "FAIL",
    "documentation review (coordinator-attested)": "PASS WITH CONDITIONS",
    "QA-RISK original": "FAIL",
    "QA-RISK teardown": "FAIL",
    "REL-SHOW-01D": "PASS: static historical scope only",
    "keyword browser/live": "NOT TESTED",
    "portable showcase": "BLOCKED",
    "live execution": "NO-GO",
    "keyword-astra-coordinator original report": "MISSING",
}
# id, source root, exact locator, bytes, SHA-256, destination basename
FIXED = (
    ("risk-browser-report", "repository", "frontend/test-results/sec-risk-cc01-final-721cd8d233a8416f87b902bee14b64bb/results.json", 228816, "57acde3ac0cbd10a4349b8b8dc45076496cdc1cba2bdb8144377449cc2262d25", "risk-browser-report.json"),
    ("ml-static-report", "temporary", "finlens-rel-show-01d-ddab2002b8554dc2a2cb973ae2f9ad40/acceptance-report.md", 12505, "bf8d3e6a28d6c5f3b0e530cedbe1bdfce435c3612696465f0222f1169f336f9e", "ml-static-report.md"),
    ("ml-static-summary", "temporary", "finlens-rel-show-01d-ddab2002b8554dc2a2cb973ae2f9ad40/acceptance-summary.json", 867, "0ee01b296fcdb777f6d1404061f9e206c71547b6fbb81079a75d2131c0abeb8d", "ml-static-summary.json"),
    ("ml-desktop-capture", "temporary", "finlens-rel-show-01d-ddab2002b8554dc2a2cb973ae2f9ad40/evidence/desktop-expanded-full.png", 576289, "2efb4ca0ddf79f28a00cb4ba8824ce5491923859e502585d2b32232482b570d9", "ml-desktop-capture.png"),
    ("ml-mobile-capture", "temporary", "finlens-rel-show-01d-ddab2002b8554dc2a2cb973ae2f9ad40/evidence/mobile-expanded-full.png", 518808, "dd42f5d7793093948f71a9a575252de497bf2682f4342dccffdaaf234e4f7a1d", "ml-mobile-capture.png"),
    ("qa-risk-original-fail", "temporary", "finlens-qa-risk-01-97131629aa11428ea42bbc1c1fb888a0/acceptance-summary.json", 1327, "706b0ac3f83db002f4636bbebe5f446c58fe31846207a460873686525ef34848", "qa-risk-original-fail.json"),
    ("qa-risk-teardown-fail", "temporary", "finlens-qa-risk-01t-phase2-1de978dfac6c404595bcb2c075c17c13/diagnostic-conclusion.json", 2610, "88684ae69f447aaf073600d71091f304fb9e14c369e88a1549976dcf6ec7ba2c", "qa-risk-teardown-fail.json"),
)
PNG_TITLE = "SEC-RISK-CC01 independent evidence, three disclosure targets, layout and keyboard focus"
LOCAL_APPDATA_GUID_BYTES = bytes.fromhex("8527b3f1ba6fcf4f9d557b8e7f157091")
PNG_EXPECTATIONS = (
    ("desktop-chromium", 96355, "b6f39ebab8b11b63ff8d6ca2ac690df4d9d6e49dd34dce41d234ecf6d2fe5ab8"),
    ("mobile-width-chromium", 58000, "56af9812536ac5e54c430e7f0a49ae5f4ceb211dc42a7ba5a4fa04576bd35f46"),
)


class Stop(RuntimeError):
    """Sanitized failure category; never include an exception's private pathname."""


class Missing(Stop):
    pass


def require(condition, code):
    if not condition:
        raise Stop(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "duplicate_json_key")
        obj[key] = value
    return obj


def parse_json(data):
    return json.loads(data, object_pairs_hook=unique_object)


def component(name):
    require(isinstance(name, str) and 0 < len(name) <= 255, "invalid_component")
    require(not any(c in name for c in '\\/:*?"<>|\x00'), "invalid_component")
    require(not any(ord(c) < 32 for c in name), "invalid_component")
    require(name not in (".", "..") and name[-1] not in " .", "invalid_component")
    require(name.split(".")[0].upper() not in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }, "device_component")
    return name


def path_chain(path):
    require(isinstance(path, str) and re.fullmatch(r"[A-Z]:\\[^/]*", path), "invalid_path")
    require(len(path) <= 4096, "invalid_path")
    root = path[:3]
    tail = path[3:]
    parts = [] if not tail else tail.split("\\")
    result = [root]
    for part in parts:
        result.append(ntpath.join(result[-1], component(part)))
    return result


@dataclass(frozen=True)
class Spec:
    artifact_id: str
    source: str
    size: int
    digest: str
    destination: str
    source_revision: str = "SYNTHETIC TEST ONLY"
    recorded_acceptance: str = "SYNTHETIC TEST ONLY"
    recorded_scope: str = "SYNTHETIC TEST ONLY"
    revision_provenance: str = "SYNTHETIC TEST ONLY"


def make_specs(manifest_bytes, temporary_root):
    require(sha(manifest_bytes) == MANIFEST_SHA256, "committed_manifest_digest")
    manifest = parse_json(manifest_bytes)
    entries = manifest["artifacts"]
    require(len({a["id"] for a in entries}) == len(entries), "duplicate_artifact")
    by_id = {a["id"]: a for a in entries}
    path_chain(temporary_root)
    specs = []
    for artifact_id, root, locator, size, digest, destination in FIXED:
        a = by_id[artifact_id]
        actual = a["repository_relative_path"] if root == "repository" else a["external_locator"]["relative_path"]
        if root != "repository":
            require(a["external_locator"]["root"] == "OPERATOR_TEMP", "source_root")
        require((actual, a["size_bytes"], a["sha256"]) == (locator, size, digest), "manifest_entry")
        source_root = REPOSITORY if root == "repository" else temporary_root
        source = ntpath.join(source_root, *locator.split("/"))
        path_chain(source)
        specs.append(Spec(artifact_id, source, size, digest, destination,
                          a["source_revision"], a["original_recorded_acceptance_classification"],
                          a["original_recorded_scope"], a["revision_provenance"]))
    require(sum(s.size for s in specs) == 1341222, "source_total")
    return tuple(specs)


def validate_specs(specs):
    require(tuple(s.artifact_id for s in specs) == tuple(f[0] for f in FIXED), "source_allowlist")
    names = [s.destination for s in specs] + [RECEIPT]
    require(len(set(n.casefold() for n in names)) == 8, "duplicate_destination")
    require(tuple(names[:-1]) == tuple(f[5] for f in FIXED), "destination_allowlist")
    require(len({s.source.casefold() for s in specs}) == 7, "duplicate_source")
    for s in specs:
        path_chain(s.source)
        component(s.destination)
        require(type(s.size) is int and 0 < s.size <= 1048576, "source_size_contract")
        require(re.fullmatch(r"[0-9a-f]{64}", s.digest), "source_digest_contract")


def validate_approval(a, tool_digest):
    keys = {"schema_version", "execution_authorized", "reviewed_tool_sha256",
            "independent_review_sha256", "approved_revision", "operator_sid",
            "operator_name", "local_app_data", "operator_temp", "bindings"}
    require(isinstance(a, dict) and set(a) == keys, "approval_fields")
    require(type(a["schema_version"]) is int and a["schema_version"] == 1, "approval_version")
    require(a["execution_authorized"] is True, "execution_not_authorized")
    require(a["approved_revision"] == REVISION, "approval_revision")
    require(isinstance(tool_digest, str) and re.fullmatch(r"[0-9a-f]{64}", tool_digest) and
            a["reviewed_tool_sha256"] == tool_digest, "unreviewed_tool")
    require(isinstance(a["independent_review_sha256"], str) and
            re.fullmatch(r"[0-9a-f]{64}", a["independent_review_sha256"]), "review_binding")
    require(isinstance(a["operator_sid"], str) and
            re.fullmatch(r"S-1-(?:[0-9]+-)+[0-9]+", a["operator_sid"]), "operator_sid")
    require(isinstance(a["operator_name"], str) and bool(a["operator_name"]), "operator_name")
    path_chain(a["local_app_data"])
    path_chain(a["operator_temp"])
    require(isinstance(a["bindings"], dict) and len(a["bindings"]) <= 128, "approval_bindings")
    for path, identity in a["bindings"].items():
        path_chain(path)
        require(isinstance(identity, dict) and set(identity) == set(IDENTITY_KEYS), "identity_fields")
        require(type(identity["volume_serial"]) is int and identity["volume_serial"] >= 0, "volume_identity")
        require(isinstance(identity["file_id"], str) and re.fullmatch(r"[0-9a-f]{32}", identity["file_id"]), "file_identity")
        require(isinstance(identity["security_sha256"], str) and
                re.fullmatch(r"[0-9a-f]{64}", identity["security_sha256"]), "security_identity")
        require(type(identity["directory"]) is bool, "directory_identity")
        require(isinstance(identity["final_path"], str) and
                re.fullmatch(r"\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\[^\x00]*", identity["final_path"]), "resolved_identity")


def identity(observation):
    return {k: observation[k] for k in IDENTITY_KEYS}


def check_observation(o, expected):
    require(identity(o) == expected, "handle_identity")
    require(o["filesystem"] == "NTFS", "filesystem")
    require(not o["attributes"] & FORBIDDEN_ATTRIBUTES and o["reparse_tag"] == 0, "reparse_or_offline")
    require(not o["delete_pending"], "delete_pending")
    require(o["directory"] or o["links"] == 1, "hardlink_count")


def check_private(o, operator_sid):
    require(o["owner_sid"] == operator_sid, "private_owner")
    allowed = {operator_sid, "S-1-5-18", "S-1-5-32-544"}
    aces = o["aces"]
    require(len(aces) == 3 and {a[0] for a in aces} == allowed, "private_principals")
    for sid, mask, flags, ace_type in aces:
        require(ace_type == 0 and mask == 0x1F01FF and not flags & ~0x13,
                "private_acl_rights")
        require(not flags & 8, "inherit_only_private_acl")
        require(not o["directory"] or flags & 3 == 3, "private_inheritance")


def embedded_check(data, expectations=PNG_EXPECTATIONS):
    document = parse_json(data)
    found = {project: [] for project, _, _ in expectations}

    def visit(suites, depth=0):
        require(depth < 32, "report_depth")
        for suite in suites:
            for spec in suite.get("specs", []):
                if spec.get("title") != PNG_TITLE:
                    continue
                for test in spec.get("tests", []):
                    project = test.get("projectName")
                    if project not in found:
                        continue
                    for result in test.get("results", []):
                        for attachment in result.get("attachments", []):
                            if attachment.get("name") == "cc01-layout":
                                require(result.get("status") == "passed" and
                                        attachment.get("contentType") == "image/png" and
                                        not attachment.get("path"), "embedded_type_or_scope")
                                found[project].append(base64.b64decode(attachment["body"], validate=True))
            visit(suite.get("suites", []), depth + 1)

    visit(document["suites"])
    for project, size, digest in expectations:
        require(len(found[project]) == 1, "embedded_selector_count")
        b = found[project][0]
        require(b.startswith(b"\x89PNG\r\n\x1a\n") and len(b) == size and sha(b) == digest,
                "embedded_digest")


def read_checked(api, handle, spec, collect=False):
    api.rewind(handle)
    count, digest, parts = 0, hashlib.sha256(), []
    while True:
        requested = min(CHUNK, spec.size + 1 - count)
        b = api.read(handle, requested)
        require(isinstance(b, bytes) and len(b) <= requested, "invalid_read")
        if not b:
            break
        count += len(b)
        require(count <= spec.size, "source_length")
        digest.update(b)
        if collect:
            parts.append(b)
    require(count == spec.size and digest.hexdigest() == spec.digest, "bytes_or_digest")
    return b"".join(parts) if collect else None


def copy_exact(api, source, output, spec):
    api.rewind(source)
    count, digest = 0, hashlib.sha256()
    while True:
        requested = min(CHUNK, spec.size + 1 - count)
        b = api.read(source, requested)
        require(isinstance(b, bytes) and len(b) <= requested, "invalid_read")
        if not b:
            break
        count += len(b)
        require(count <= spec.size, "copy_length")
        require(api.write(output, b) == len(b), "short_write")
        digest.update(b)
    require(count == spec.size and digest.hexdigest() == spec.digest, "copy_digest")
    api.flush(output)


def compare_streams(api, source, destination, size):
    api.rewind(source)
    api.rewind(destination)
    remaining = size
    while remaining:
        n = min(CHUNK, remaining)
        a, b = api.read(source, n), api.read(destination, n)
        require(isinstance(a, bytes) and 0 < len(a) <= n and a == b, "byte_comparison")
        remaining -= len(a)
    require(api.read(source, 1) == api.read(destination, 1) == b"", "comparison_length")


def preserve(api, approval, specs, png_expectations=PNG_EXPECTATIONS):
    """Only called after explicit approval validation; tests supply an in-memory API."""
    # The CLI additionally compares this value to the actual reviewed tool bytes.
    validate_approval(approval, approval.get("reviewed_tool_sha256"))
    validate_specs(specs)
    parent_path = approval["local_app_data"]
    required = set(path_chain(parent_path))
    for s in specs:
        required.update(path_chain(s.source))
    require(set(approval["bindings"]) == required, "incomplete_or_extra_bindings")
    require(api.operator() == (approval["operator_sid"], approval["operator_name"]), "operator_mismatch")
    require(api.known_folder() == parent_path, "known_folder_mismatch")
    bindings, opened = approval["bindings"], {}
    with ExitStack() as stack:
        def retain(h):
            stack.callback(api.close, h)
            return h

        def existing(path):
            if path in opened:
                return opened[path]
            chain = path_chain(path)
            expected = bindings[path]
            if len(chain) == 1:
                h = api.open_volume(expected["final_path"])
            else:
                parent = existing(chain[-2])
                require(bindings[chain[-2]]["directory"], "ancestor_not_directory")
                h = api.open_child(parent, ntpath.basename(path), expected["directory"])
            retain(h)
            check_observation(api.observe(h), expected)
            opened[path] = h
            return h

        parent = existing(parent_path)
        check_private(api.observe(parent), approval["operator_sid"])
        require(bindings[parent_path]["directory"], "parent_not_directory")
        sources = {}
        for spec in specs:
            require(not bindings[spec.source]["directory"], "source_not_file")
            h = existing(spec.source)
            data = read_checked(api, h, spec, spec.artifact_id == "risk-browser-report")
            if data is not None:
                embedded_check(data, png_expectations)
            sources[spec.artifact_id] = h
        require(api.absent(parent, CHILD), "destination_exists")
        for path, h in opened.items():
            check_observation(api.observe(h), bindings[path])
        check_private(api.observe(parent), approval["operator_sid"])

        def new_identity(h, parent_observation, name, directory):
            o = api.observe(h)
            require(o["volume_serial"] == parent_observation["volume_serial"] and
                    o["final_path"] == parent_observation["final_path"].rstrip("\\") + "\\" + name and
                    o["directory"] is directory, "new_handle_containment")
            check_observation(o, identity(o))
            check_private(o, approval["operator_sid"])
            return identity(o)

        child = retain(api.create_child(parent, CHILD, True))
        child_identity = new_identity(child, api.observe(parent), CHILD, True)
        destinations, copied = {}, []
        for spec in specs:
            output = api.create_child(child, spec.destination, False)
            try:
                output_identity = new_identity(output, api.observe(child), spec.destination, False)
                copy_exact(api, sources[spec.artifact_id], output, spec)
            finally:
                api.close(output)
            # A new read-only handle, opened relative to the retained private child.
            reread = retain(api.open_child(child, spec.destination, False))
            check_observation(api.observe(reread), output_identity)
            data = read_checked(api, reread, spec, spec.artifact_id == "risk-browser-report")
            compare_streams(api, sources[spec.artifact_id], reread, spec.size)
            if data is not None:
                embedded_check(data, png_expectations)
            destinations[spec.artifact_id] = (reread, output_identity)
            copied.append({"artifact_id": spec.artifact_id, "source_path": spec.source,
                           "source_identity": bindings[spec.source],
                           "destination_identity": output_identity, "size_bytes": spec.size,
                           "sha256": spec.digest, "destination_name": spec.destination,
                           "source_revision": spec.source_revision,
                           "recorded_acceptance": spec.recorded_acceptance,
                           "recorded_scope": spec.recorded_scope,
                           "revision_provenance": spec.revision_provenance})

        def recheck():
            for path, h in opened.items():
                check_observation(api.observe(h), bindings[path])
            check_observation(api.observe(child), child_identity)
            check_private(api.observe(child), approval["operator_sid"])
            for spec in specs:
                read_checked(api, sources[spec.artifact_id], spec)
                h, expected = destinations[spec.artifact_id]
                check_observation(api.observe(h), expected)

        recheck()
        receipt = {
            "schema_version": 1, "operation": "REL-DEMO-03 historical evidence preservation",
            "manifest_revision": REVISION, "manifest_blob_sha256": MANIFEST_SHA256,
            "operator_sid": approval["operator_sid"], "operator_name": approval["operator_name"],
            "reviewed_tool_sha256": approval["reviewed_tool_sha256"],
            "independent_review_sha256": approval["independent_review_sha256"],
            "approval_sha256": sha(json.dumps(approval, sort_keys=True).encode("utf-8")),
            "completed_utc": api.utc_now(), "destination_parent": parent_path,
            "destination_identity": child_identity, "sources": copied,
            "evidence_byte_verification": "PASS", "historical_states": dict(HISTORY),
            "custody_completion": "NOT SELF-ATTESTED: requires independent verification of this receipt",
            "new_browser_financial_model_or_runtime_acceptance": False,
            "privacy": "Operator-private custody; no public redistribution authorization",
            "source_namespace_trust": "Trusted operator/administrators; ordinary-user races require retained handle containment",
        }
        payload = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
        writer = api.create_child(child, RECEIPT, False)
        try:
            receipt_identity = new_identity(writer, api.observe(child), RECEIPT, False)
            require(api.write(writer, payload) == len(payload), "receipt_short_write")
            api.flush(writer)
        finally:
            api.close(writer)
        reader = retain(api.open_child(child, RECEIPT, False))
        check_observation(api.observe(reader), receipt_identity)
        receipt_spec = Spec("private-receipt", "", len(payload), sha(payload), RECEIPT)
        require(read_checked(api, reader, receipt_spec, True) == payload, "receipt_verification")
        recheck()
        # The file deliberately makes no circular claim about its own verification.
        result = {"preservation": "PASS", "receipt_sha256": sha(payload),
                  "evidence_files": 7, "evidence_bytes": sum(s.size for s in specs)}
    # A close failure also prevents a successful return.
    return result


class WindowsAPI:
    """Native adapter, never instantiated by default invocation or synthetic tests.

    NtCreateFile: RootDirectory-relative, FILE_OPEN/FILE_CREATE only; share READ
    only; OBJ_DONT_REPARSE and FILE_OPEN_REPARSE_POINT. Every existing directory
    handle remains open through verification. No SetSecurity*, rename or delete API.
    """

    def __init__(self):
        import ctypes as c
        require(sys.platform == "win32", "windows_only")
        self.c = c
        U32, U16, U8, PTR = c.c_uint32, c.c_uint16, c.c_ubyte, c.c_void_p

        class US(c.Structure):
            _fields_ = [("Length", U16), ("MaximumLength", U16), ("Buffer", PTR)]

        class OA(c.Structure):
            _fields_ = [("Length", U32), ("RootDirectory", PTR), ("ObjectName", c.POINTER(US)),
                        ("Attributes", U32), ("SecurityDescriptor", PTR), ("SecurityQualityOfService", PTR)]

        class IOS(c.Structure):
            _fields_ = [("StatusOrPointer", PTR), ("Information", c.c_size_t)]

        class ID(c.Structure):
            _fields_ = [("VolumeSerialNumber", c.c_uint64), ("FileId", U8 * 16)]

        class TAG(c.Structure):
            _fields_ = [("FileAttributes", U32), ("ReparseTag", U32)]

        class STANDARD(c.Structure):
            _fields_ = [("AllocationSize", c.c_int64), ("EndOfFile", c.c_int64),
                        ("NumberOfLinks", U32), ("DeletePending", U8), ("Directory", U8)]

        class ACLINFO(c.Structure):
            _fields_ = [("AceCount", U32), ("AclBytesInUse", U32), ("AclBytesFree", U32)]

        self.US, self.OA, self.IOS = US, OA, IOS
        self.ID, self.TAG, self.STANDARD, self.ACLINFO = ID, TAG, STANDARD, ACLINFO
        kernel = c.WinDLL("kernel32", use_last_error=True)
        security = c.WinDLL("advapi32", use_last_error=True)
        shell = c.WinDLL("shell32", use_last_error=True)
        native = c.WinDLL("ntdll", use_last_error=True)
        ole = c.WinDLL("ole32", use_last_error=True)

        def bind(lib, name, restype, args):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = restype, args
            setattr(self, name, fn)

        P = c.POINTER
        bind(native, "NtCreateFile", c.c_int32, [P(PTR), U32, P(OA), P(IOS), PTR, U32, U32, U32, U32, PTR, U32])
        bind(kernel, "CloseHandle", c.c_int, [PTR])
        bind(kernel, "GetCurrentProcess", PTR, [])
        bind(kernel, "GetFileInformationByHandleEx", c.c_int, [PTR, c.c_int, PTR, U32])
        bind(kernel, "GetFinalPathNameByHandleW", U32, [PTR, c.c_wchar_p, U32, U32])
        bind(kernel, "GetVolumeInformationByHandleW", c.c_int,
             [PTR, c.c_wchar_p, U32, P(U32), P(U32), P(U32), c.c_wchar_p, U32])
        bind(kernel, "SetFilePointerEx", c.c_int, [PTR, c.c_int64, P(c.c_int64), U32])
        bind(kernel, "ReadFile", c.c_int, [PTR, PTR, U32, P(U32), PTR])
        bind(kernel, "WriteFile", c.c_int, [PTR, PTR, U32, P(U32), PTR])
        bind(kernel, "FlushFileBuffers", c.c_int, [PTR])
        bind(kernel, "LocalFree", PTR, [PTR])
        bind(security, "OpenProcessToken", c.c_int, [PTR, U32, P(PTR)])
        bind(security, "GetTokenInformation", c.c_int, [PTR, c.c_int, PTR, U32, P(U32)])
        bind(security, "GetUserNameW", c.c_int, [c.c_wchar_p, P(U32)])
        bind(security, "ConvertSidToStringSidW", c.c_int, [PTR, P(PTR)])
        bind(security, "GetSecurityInfo", U32, [PTR, c.c_int, U32, P(PTR), P(PTR), P(PTR), P(PTR), P(PTR)])
        bind(security, "GetSecurityDescriptorLength", U32, [PTR])
        bind(security, "GetAclInformation", c.c_int, [PTR, PTR, U32, c.c_int])
        bind(security, "GetAce", c.c_int, [PTR, U32, P(PTR)])
        bind(shell, "SHGetKnownFolderPath", c.c_int32, [PTR, U32, PTR, P(PTR)])
        bind(ole, "CoTaskMemFree", None, [PTR])

    def close(self, h):
        require(self.CloseHandle(h), "close_handle")

    def sid(self, pointer):
        c = self.c
        out = c.c_void_p()
        require(self.ConvertSidToStringSidW(pointer, c.byref(out)), "sid_query")
        try:
            return c.wstring_at(out.value)
        finally:
            self.LocalFree(out)

    def operator(self):
        c = self.c
        token, size = c.c_void_p(), c.c_uint32()
        require(self.OpenProcessToken(self.GetCurrentProcess(), 8, c.byref(token)), "operator_token")
        try:
            self.GetTokenInformation(token, 1, None, 0, c.byref(size))
            require(0 < size.value < 65536, "operator_token_size")
            buf = c.create_string_buffer(size.value)
            require(self.GetTokenInformation(token, 1, buf, size, c.byref(size)), "operator_token_query")
            sid = self.sid(c.cast(buf, c.POINTER(c.c_void_p))[0])
        finally:
            self.close(token)
        name, count = c.create_unicode_buffer(1024), c.c_uint32(1024)
        require(self.GetUserNameW(name, c.byref(count)), "operator_name_query")
        return sid, name.value

    def known_folder(self):
        c = self.c
        # FOLDERID_LocalAppData, GUID in native little-endian structure layout.
        guid = (c.c_ubyte * 16).from_buffer_copy(LOCAL_APPDATA_GUID_BYTES)
        out = c.c_void_p()
        # KF_FLAG_DONT_VERIFY; importantly, never KF_FLAG_CREATE.
        try:
            require(self.SHGetKnownFolderPath(c.byref(guid), 0x4000, None, c.byref(out)) == 0 and
                    bool(out.value), "known_folder")
            path = c.wstring_at(out.value)
            path_chain(path)
            return path
        finally:
            if out.value:
                self.CoTaskMemFree(out)

    def _open(self, parent, name, directory, create):
        c = self.c
        if parent is not None:
            component(name)
        buf = c.create_unicode_buffer(name)
        length = len(name.encode("utf-16-le"))
        require(length < 65534, "native_name_length")
        us = self.US(length, length + 2, c.cast(buf, c.c_void_p))
        oa = self.OA(c.sizeof(self.OA), parent, c.pointer(us), 0x1040, None, None)
        handle, ios = c.c_void_p(), self.IOS()
        access = 0x1200A1 if directory else (0xC0120000 if create else 0x80120000)
        options = 0x200000 | 0x20 | (1 if directory else 0x40)
        status = self.NtCreateFile(c.byref(handle), access, c.byref(oa), c.byref(ios),
                                   None, 0, 1, 2 if create else 1, options, None, 0)
        if status & 0xFFFFFFFF == 0xC0000034:
            if handle.value:
                self.close(handle.value)
            raise Missing("missing_source_or_child")
        if status != 0 or handle.value is None:
            if handle.value:
                self.close(handle.value)
            raise Stop("native_open_or_collision")
        if ios.Information != (2 if create else 1):
            self.close(handle.value)
            raise Stop("unexpected_creation_disposition")
        return handle.value

    def open_volume(self, final_path):
        require(re.fullmatch(r"\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\", final_path), "volume_root_binding")
        return self._open(None, "\\??\\" + final_path[4:], True, False)

    def open_child(self, parent, name, directory):
        return self._open(parent, name, directory, False)

    def create_child(self, parent, name, directory):
        return self._open(parent, name, directory, True)

    def absent(self, parent, name):
        try:
            # A non-directory open of an existing directory also fails closed.
            h = self.open_child(parent, name, False)
        except Missing:
            return True
        self.close(h)
        return False

    def observe(self, h):
        c = self.c
        fid, tag, standard = self.ID(), self.TAG(), self.STANDARD()
        for cls, value in ((18, fid), (9, tag), (1, standard)):
            require(self.GetFileInformationByHandleEx(h, cls, c.byref(value), c.sizeof(value)), "file_information")
        path = c.create_unicode_buffer(32768)
        n = self.GetFinalPathNameByHandleW(h, path, len(path), 1)
        require(0 < n < len(path), "resolved_path")
        fs, serial, maximum, flags = c.create_unicode_buffer(32), c.c_uint32(), c.c_uint32(), c.c_uint32()
        require(self.GetVolumeInformationByHandleW(h, None, 0, c.byref(serial), c.byref(maximum), c.byref(flags), fs, len(fs)), "volume_information")
        owner, dacl, sd = c.c_void_p(), c.c_void_p(), c.c_void_p()
        require(self.GetSecurityInfo(h, 1, 5, c.byref(owner), None, c.byref(dacl), None, c.byref(sd)) == 0, "security_query")
        try:
            require(bool(dacl.value), "null_dacl")
            size = self.GetSecurityDescriptorLength(sd)
            require(0 < size < 1048576, "security_size")
            security_digest = sha(c.string_at(sd.value, size))
            info, aces = self.ACLINFO(), []
            require(self.GetAclInformation(dacl, c.byref(info), c.sizeof(info), 2), "acl_information")
            for index in range(info.AceCount):
                ace = c.c_void_p()
                require(self.GetAce(dacl, index, c.byref(ace)), "ace_query")
                header = c.string_at(ace.value, 4)
                ace_type, ace_flags = header[0], header[1]
                require(int.from_bytes(header[2:4], "little") >= 8, "ace_size")
                mask = c.c_uint32.from_address(ace.value + 4).value
                sid = self.sid(ace.value + 8) if ace_type == 0 else "UNPARSED_NON_ALLOW_ACE"
                aces.append((sid, mask, ace_flags, ace_type))
            return {"volume_serial": fid.VolumeSerialNumber, "file_id": bytes(fid.FileId).hex(),
                    "final_path": path.value, "security_sha256": security_digest,
                    "directory": bool(standard.Directory), "filesystem": fs.value,
                    "attributes": tag.FileAttributes, "reparse_tag": tag.ReparseTag,
                    "links": standard.NumberOfLinks, "delete_pending": bool(standard.DeletePending),
                    "owner_sid": self.sid(owner), "aces": tuple(aces)}
        finally:
            self.LocalFree(sd)

    def rewind(self, h):
        require(self.SetFilePointerEx(h, 0, None, 0), "rewind")

    def read(self, h, count):
        c = self.c
        require(0 < count <= CHUNK, "read_bound")
        buf, actual = c.create_string_buffer(count), c.c_uint32()
        require(self.ReadFile(h, buf, count, c.byref(actual), None), "read_failure")
        return buf.raw[:actual.value]

    def write(self, h, data):
        c = self.c
        buf, actual = c.create_string_buffer(data), c.c_uint32()
        require(self.WriteFile(h, buf, len(data), c.byref(actual), None), "write_failure")
        return actual.value

    def flush(self, h):
        require(self.FlushFileBuffers(h), "flush_failure")

    def utc_now(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


def committed_manifest():
    import os
    import subprocess
    # A read-only Git command must not inherit file tracing or lazy-fetch settings.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1")
    result = subprocess.run(
        ["git", "--no-optional-locks", "--no-replace-objects", "-c", "core.fsmonitor=false",
         "-c", "trace2.eventTarget=0", "-c", "trace2.perfTarget=0", "-c", "trace2.normalTarget=0",
         "-C", REPOSITORY, "show", REVISION + ":" + MANIFEST],
        capture_output=True, check=False, timeout=15, env=env,
    )
    require(result.returncode == 0 and sha(result.stdout) == MANIFEST_SHA256, "committed_manifest")
    return result.stdout


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args in ([], ["--help"]):
        print("Review candidate only. No preservation requested; no filesystem mutation.")
        return 0
    if args != ["--execute-approved"]:
        print("NO-GO: explicit reviewed execution mechanism required.")
        return 2
    try:
        require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,
                "isolated_no_site_no_bytecode_required")
        raw = sys.stdin.buffer.read(65537)
        require(len(raw) <= 65536, "approval_size")
        approval = parse_json(raw)
        # Read only the tool itself; this is not a historical evidence access.
        with open(__file__, "rb") as stream:
            tool_digest = sha(stream.read())
        validate_approval(approval, tool_digest)
        specs = make_specs(committed_manifest(), approval["operator_temp"])
        result = preserve(WindowsAPI(), approval, specs)
    except Exception:
        # Native/Python exceptions can contain private paths. Do not print them.
        print("NO-GO: preservation stopped; partial outputs may remain. No cleanup or retry.")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
