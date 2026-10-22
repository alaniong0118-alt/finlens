"""Synthetic memory-only tests. Load with the guarded stdin harness in the ExecPlan.

These tests do not instantiate WindowsAPI or access real evidence/destinations.
They do not certify native Windows ACL, sharing, reparse or namespace semantics.
"""

import base64
import copy
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
import ntpath
import sys
import types
import unittest
import uuid

import preserve_showcase_evidence as p


SID = "S-1-5-21-1-2-3-1001"
PARENT = r"C:\Fixture\Local"
PRIVATE_ACES = tuple((s, 0x1F01FF, 0x13, 0) for s in (SID, "S-1-5-18", "S-1-5-32-544"))
PINNED_MANIFEST = globals().get("PINNED_MANIFEST")


class Handle:
    def __init__(self, node, writable=False):
        self.node, self.writable, self.position, self.closed = node, writable, 0, False


class MemoryAPI:
    """A deterministic memory filesystem, with deliberately adversarial fault hooks."""

    def __init__(self):
        self.nodes, self.events, self.handles = {}, [], []
        self.fault, self.observe_counts, self.write_counts = None, {}, {}
        pngs = [("desktop-chromium", b"\x89PNG\r\n\x1a\ndesktop"),
                ("mobile-width-chromium", b"\x89PNG\r\n\x1a\nmobile")]
        self.png_expectations = tuple((name, len(b), p.sha(b)) for name, b in pngs)
        report = {"suites": [{"specs": [{"title": p.PNG_TITLE, "tests": [
            {"projectName": name, "results": [{"status": "passed", "attachments": [
                {"name": "cc01-layout", "contentType": "image/png", "body": base64.b64encode(b).decode("ascii")}
            ]}]} for name, b in pngs]}]}]}
        self.specs = []
        self.add_path(PARENT, True)
        for index, row in enumerate(p.FIXED):
            artifact_id, _, _, _, _, destination = row
            root = r"D:\Fixture\Risk" if index == 0 else r"C:\Fixture\Temp"
            source = ntpath.join(root, artifact_id + ".source")
            data = json.dumps(report).encode() if index == 0 else (artifact_id + " synthetic historical bytes").encode()
            self.add_path(source, False, data)
            self.specs.append(p.Spec(artifact_id, source, len(data), p.sha(data), destination))
        self.specs = tuple(self.specs)
        self.approval = self.approval_for_current_nodes()

    def add_path(self, path, directory, data=b"", created=False):
        chain = p.path_chain(path)
        for part in chain[:-1]:
            if part not in self.nodes:
                self.add_path(part, True)
        volume = 1 if path.startswith("C:") else 2
        guid = "11111111-1111-1111-1111-111111111111" if volume == 1 else "22222222-2222-2222-2222-222222222222"
        aces = PRIVATE_ACES if directory else tuple((s, m, 0x10, t) for s, m, _, t in PRIVATE_ACES)
        o = {"volume_serial": volume, "file_id": p.sha(path.encode())[:32],
             "final_path": "\\\\?\\Volume{" + guid + "}\\" + path[3:],
             "security_sha256": p.sha((path + " security").encode()), "directory": directory,
             "filesystem": "NTFS", "attributes": 16 if directory else 0,
             "reparse_tag": 0, "links": 1, "delete_pending": False,
             "owner_sid": SID, "aces": aces}
        self.nodes[path] = {"path": path, "observation": o, "data": bytearray(data), "created": created}
        return self.nodes[path]

    def approval_for_current_nodes(self):
        return {"schema_version": 1, "execution_authorized": True, "reviewed_tool_sha256": "0" * 64,
                "independent_review_sha256": "1" * 64, "approved_revision": p.REVISION,
                "operator_sid": SID, "operator_name": "SyntheticOperator", "local_app_data": PARENT,
                "operator_temp": r"C:\Fixture\Temp",
                "bindings": {path: p.identity(node["observation"]) for path, node in self.nodes.items()}}

    def operator(self):
        return SID, "SyntheticOperator"

    def known_folder(self):
        return PARENT

    def hold(self, node, writable=False):
        h = Handle(node, writable)
        self.handles.append(h)
        self.events.append(("open_write" if writable else "open_read", node["path"]))
        return h

    def open_volume(self, final_path):
        for path, node in self.nodes.items():
            if len(path) == 3 and node["observation"]["final_path"] == final_path:
                return self.hold(node)
        raise p.Stop("unknown_volume")

    def open_child(self, parent, name, directory):
        assert not parent.closed
        p.component(name)
        path = ntpath.join(parent.node["path"], name)
        if path not in self.nodes:
            raise p.Missing("missing")
        node = self.nodes[path]
        if node["created"] and not directory:
            if self.fault == "reread" and name != p.RECEIPT:
                raise p.Stop("synthetic_reread_failure")
            if self.fault == "reread_identity" and name != p.RECEIPT:
                node["observation"]["file_id"] = "f" * 32
            if self.fault == "reread_corrupt" and name != p.RECEIPT:
                node["data"][0] ^= 1
            if self.fault == "receipt_reread" and name == p.RECEIPT:
                raise p.Stop("synthetic_receipt_reread_failure")
            if self.fault == "receipt_identity" and name == p.RECEIPT:
                node["observation"]["file_id"] = "b" * 32
        return self.hold(node)

    def create_child(self, parent, name, directory):
        assert not parent.closed
        p.component(name)
        path = ntpath.join(parent.node["path"], name)
        self.events.append(("create_attempt", path))
        if self.fault == "collision" and directory:
            self.add_path(path, True, created=True)
        p.require(path not in self.nodes, "collision")
        node = self.add_path(path, directory, created=True)
        if self.fault == "escape" and directory:
            node["observation"]["final_path"] += "\\redirected"
        if self.fault == "created_acl" and not directory:
            node["observation"]["aces"] += (("S-1-1-0", 0x1F01FF, 0, 0),)
        return self.hold(node, not directory)

    def absent(self, parent, name):
        return ntpath.join(parent.node["path"], name) not in self.nodes

    def observe(self, h):
        assert not h.closed
        path = h.node["path"]
        self.observe_counts[path] = self.observe_counts.get(path, 0) + 1
        o = copy.deepcopy(h.node["observation"])
        if self.fault == "ancestor_changed" and path == "D:\\" and self.observe_counts[path] >= 2:
            o["file_id"] = "e" * 32
        return o

    def rewind(self, h):
        assert not h.closed
        h.position = 0

    def read(self, h, count):
        assert not h.closed and not h.writable
        p.require(count > 0, "read_count")
        data = bytes(h.node["data"][h.position:h.position + count])
        h.position += len(data)
        if self.fault == "receipt_corrupt" and ntpath.basename(h.node["path"]) == p.RECEIPT and data:
            return b"!" + data[1:]
        return data

    def write(self, h, data):
        assert not h.closed and h.writable and h.node["created"]
        path = h.node["path"]
        self.write_counts[path] = self.write_counts.get(path, 0) + 1
        self.events.append(("write", path))
        if self.fault == "partial_copy" and ntpath.basename(path) == self.specs[2].destination:
            raise p.Stop("synthetic_partial_failure")
        count = len(data) - 1 if self.fault == "short_write" else len(data)
        if self.fault == "receipt_short_write" and ntpath.basename(path) == p.RECEIPT:
            count -= 1
        h.node["data"].extend(data[:count])
        h.position += count
        return count

    def flush(self, h):
        self.events.append(("flush", h.node["path"]))

    def close(self, h):
        assert not h.closed
        h.closed = True
        self.events.append(("close", h.node["path"]))

    def utc_now(self):
        return "2026-10-23T00:00:00+00:00"

    def run(self):
        return p.preserve(self, self.approval, self.specs, self.png_expectations)

    def created_paths(self):
        return {path for path, node in self.nodes.items() if node["created"]}


class PreservationTests(unittest.TestCase):
    def failed(self, api, code=None, before_creation=False):
        with self.assertRaises(p.Stop) as caught:
            api.run()
        if code:
            self.assertEqual(str(caught.exception), code)
        self.assertTrue(all(h.closed for h in api.handles))
        if before_creation:
            self.assertFalse(api.created_paths())
        self.assertTrue(all(count == 1 for count in api.write_counts.values()))

    def test_success_exact_outputs_source_immutability_and_receipt(self):
        api = MemoryAPI()
        originals = {s.source: bytes(api.nodes[s.source]["data"]) for s in api.specs}
        result = api.run()
        self.assertEqual(result["preservation"], "PASS")
        expected = {ntpath.join(PARENT, p.CHILD, row[5]) for row in p.FIXED}
        expected.add(ntpath.join(PARENT, p.CHILD, p.RECEIPT))
        self.assertEqual(api.created_paths(), expected | {ntpath.join(PARENT, p.CHILD)})
        for s in api.specs:
            self.assertEqual(bytes(api.nodes[s.source]["data"]), originals[s.source])
            self.assertEqual(bytes(api.nodes[ntpath.join(PARENT, p.CHILD, s.destination)]["data"]), originals[s.source])
        receipt_data = bytes(api.nodes[ntpath.join(PARENT, p.CHILD, p.RECEIPT)]["data"])
        receipt = json.loads(receipt_data)
        self.assertEqual(result["receipt_sha256"], p.sha(receipt_data))
        self.assertEqual(receipt["historical_states"], p.HISTORY)
        self.assertTrue(receipt["custody_completion"].startswith("NOT SELF-ATTESTED"))
        self.assertIs(receipt["new_browser_financial_model_or_runtime_acceptance"], False)
        self.assertTrue(all(h.closed for h in api.handles))
        for s in api.specs:
            path = ntpath.join(PARENT, p.CHILD, s.destination)
            close_index = api.events.index(("close", path))
            reread_index = api.events.index(("open_read", path))
            self.assertLess(close_index, reread_index)

    def test_wrong_source_digest(self):
        api = MemoryAPI()
        api.nodes[api.specs[1].source]["data"][0] ^= 1
        self.failed(api, "bytes_or_digest", True)

    def test_multiple_chunks_use_one_source_handle_and_fresh_destination_reader(self):
        api = MemoryAPI()
        s = api.specs[1]
        data = b"synthetic" * (p.CHUNK // 3)
        api.nodes[s.source]["data"] = bytearray(data)
        api.specs = (api.specs[0], replace(s, size=len(data), digest=p.sha(data))) + api.specs[2:]
        self.assertEqual(api.run()["preservation"], "PASS")
        target = ntpath.join(PARENT, p.CHILD, s.destination)
        self.assertGreater(api.write_counts[target], 1)
        self.assertEqual(sum(event == "open_read" and path == s.source for event, path in api.events), 1)
        self.assertEqual(sum(event == "open_read" and path == target for event, path in api.events), 1)

    def test_core_also_requires_explicit_execution_authorization(self):
        api = MemoryAPI()
        api.approval["execution_authorized"] = False
        self.failed(api, "execution_not_authorized", True)
        self.assertFalse(api.handles)

    def test_wrong_source_sizes(self):
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                api = MemoryAPI()
                api.specs = (replace(api.specs[0], size=api.specs[0].size + delta),) + api.specs[1:]
                self.failed(api, before_creation=True)

    def test_missing_source(self):
        api = MemoryAPI()
        del api.nodes[api.specs[4].source]
        self.failed(api, before_creation=True)

    def test_unexpected_source_identity(self):
        api = MemoryAPI()
        api.nodes[api.specs[3].source]["observation"]["file_id"] = "a" * 32
        self.failed(api, "handle_identity", True)

    def test_changed_ancestor_identity_before_mutation(self):
        api = MemoryAPI()
        api.fault = "ancestor_changed"
        self.failed(api, "handle_identity", True)

    def test_reparse_junction_and_cloud_recall(self):
        for attrs, tag in ((0x400, 0xA0000003), (0x400, 0xA000000C), (0x400000, 0)):
            with self.subTest(attrs=attrs, tag=tag):
                api = MemoryAPI()
                api.nodes[api.specs[0].source]["observation"].update(attributes=attrs, reparse_tag=tag)
                self.failed(api, "reparse_or_offline", True)

    def test_acl_additional_principal_even_with_approved_descriptor(self):
        api = MemoryAPI()
        api.nodes[PARENT]["observation"]["aces"] += (("S-1-1-0", 0x1F01FF, 0x13, 0),)
        self.failed(api, "private_principals", True)

    def test_new_file_acl_checked_before_writing_bytes(self):
        api = MemoryAPI()
        api.fault = "created_acl"
        self.failed(api, "private_principals")
        self.assertFalse(api.write_counts)

    def test_private_acl_cannot_have_weaker_rights_or_inherit_only_rules(self):
        for rule in ((SID, 0x1301BF, 0x13, 0), (SID, 0x1F01FF, 0x1B, 0)):
            with self.subTest(rule=rule):
                api = MemoryAPI()
                o = api.nodes[PARENT]["observation"]
                o["aces"] = (rule,) + o["aces"][1:]
                self.failed(api, before_creation=True)

    def test_existing_destination_no_overwrite(self):
        api = MemoryAPI()
        node = api.add_path(ntpath.join(PARENT, p.CHILD), True)
        self.failed(api, "destination_exists", True)
        self.assertIs(api.nodes[node["path"]], node)

    def test_destination_collision_after_absence_check_no_retry(self):
        api = MemoryAPI()
        api.fault = "collision"
        self.failed(api, "collision")
        self.assertEqual(sum(event == "create_attempt" for event, _ in api.events), 1)
        self.assertFalse(api.write_counts)

    def test_duplicate_destination_name(self):
        api = MemoryAPI()
        api.specs = (replace(api.specs[0], destination=api.specs[1].destination),) + api.specs[1:]
        self.failed(api, "duplicate_destination", True)

    def test_handle_relative_creation_cannot_escape(self):
        api = MemoryAPI()
        api.fault = "escape"
        self.failed(api, "new_handle_containment")
        self.assertFalse(api.write_counts)

    def test_reopened_handle_identity_is_checked(self):
        api = MemoryAPI()
        api.fault = "reread_identity"
        self.failed(api, "handle_identity")

    def test_embedded_mismatch_before_destination_creation(self):
        api = MemoryAPI()
        api.png_expectations = ((api.png_expectations[0][0], 1, "f" * 64), api.png_expectations[1])
        self.failed(api, "embedded_digest", True)

    def test_duplicate_embedded_selector(self):
        api = MemoryAPI()
        s = api.specs[0]
        report = json.loads(api.nodes[s.source]["data"])
        tests = report["suites"][0]["specs"][0]["tests"]
        tests.append(copy.deepcopy(tests[0]))
        data = json.dumps(report).encode()
        api.nodes[s.source]["data"] = bytearray(data)
        api.specs = (replace(s, size=len(data), digest=p.sha(data)),) + api.specs[1:]
        self.failed(api, "embedded_selector_count", True)

    def test_short_write_no_retry_or_success_receipt(self):
        api = MemoryAPI()
        api.fault = "short_write"
        self.failed(api, "short_write")
        self.assertEqual(sum(api.write_counts.values()), 1)
        self.assertNotIn(ntpath.join(PARENT, p.CHILD, p.RECEIPT), api.nodes)

    def test_partial_copy_retained_no_cleanup(self):
        api = MemoryAPI()
        api.fault = "partial_copy"
        self.failed(api, "synthetic_partial_failure")
        self.assertTrue(api.created_paths())
        self.assertNotIn(ntpath.join(PARENT, p.CHILD, p.RECEIPT), api.nodes)

    def test_failed_independent_reread(self):
        api = MemoryAPI()
        api.fault = "reread"
        self.failed(api, "synthetic_reread_failure")
        self.assertNotIn(ntpath.join(PARENT, p.CHILD, p.RECEIPT), api.nodes)

    def test_independent_reread_detects_content_change(self):
        api = MemoryAPI()
        api.fault = "reread_corrupt"
        self.failed(api, "bytes_or_digest")

    def test_rerun_after_partial_failure_stops_at_existing_child(self):
        api = MemoryAPI()
        api.fault = "partial_copy"
        self.failed(api)
        writes = dict(api.write_counts)
        api.fault = None
        self.failed(api, "destination_exists")
        self.assertEqual(api.write_counts, writes)

    def test_failed_custody_verification_never_returns_success(self):
        for fault in ("receipt_reread", "receipt_corrupt", "receipt_short_write", "receipt_identity"):
            with self.subTest(fault=fault):
                api = MemoryAPI()
                api.fault = fault
                self.failed(api)
                if fault != "receipt_short_write":
                    data = bytes(api.nodes[ntpath.join(PARENT, p.CHILD, p.RECEIPT)]["data"])
                    self.assertTrue(json.loads(data)["custody_completion"].startswith("NOT SELF-ATTESTED"))

    def test_close_failure_prevents_success_even_after_verification(self):
        api = MemoryAPI()
        close = api.close

        def fail_one_close(h):
            close(h)
            if h.node["path"] == PARENT:
                raise p.Stop("synthetic_close_failure")

        api.close = fail_one_close
        self.failed(api, "synthetic_close_failure")

    def test_missing_or_extra_identity_binding(self):
        for extra in (False, True):
            with self.subTest(extra=extra):
                api = MemoryAPI()
                if extra:
                    api.approval["bindings"][r"C:\Unexpected"] = api.approval["bindings"][PARENT]
                else:
                    del api.approval["bindings"][api.specs[1].source]
                self.failed(api, "incomplete_or_extra_bindings", True)

    def test_wrong_operator_and_known_folder(self):
        for fault in ("operator", "known_folder"):
            with self.subTest(fault=fault):
                api = MemoryAPI()
                if fault == "operator":
                    api.approval["operator_name"] = "OtherOperator"
                else:
                    api.known_folder = lambda: r"C:\Redirected"
                self.failed(api, before_creation=True)

    def test_source_recheck_detects_changed_bytes_before_receipt(self):
        api = MemoryAPI()
        original = api.flush

        def flush(h):
            original(h)
            if ntpath.basename(h.node["path"]) == api.specs[-1].destination:
                api.nodes[api.specs[1].source]["data"][0] ^= 1

        api.flush = flush
        self.failed(api, "bytes_or_digest")
        self.assertNotIn(ntpath.join(PARENT, p.CHILD, p.RECEIPT), api.nodes)

    def test_non_ntfs_hardlink_delete_pending(self):
        for change in ({"filesystem": "FAT32"}, {"links": 2}, {"delete_pending": True}):
            with self.subTest(change=change):
                api = MemoryAPI()
                api.nodes[api.specs[1].source]["observation"].update(change)
                self.failed(api, before_creation=True)


class EntryAndContractTests(unittest.TestCase):
    def test_execution_refuses_nonisolated_interpreter_before_any_input_or_native_call(self):
        original = p.sys
        p.sys = types.SimpleNamespace(flags=types.SimpleNamespace(isolated=0, no_site=0, dont_write_bytecode=0))
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(["--execute-approved"]), 1)
        finally:
            p.sys = original

    @unittest.skipUnless(PINNED_MANIFEST is not None, "guarded harness supplies committed manifest bytes")
    def test_git_reader_disables_trace_outputs_and_lazy_network_fetch(self):
        saved_os, saved_subprocess = sys.modules.get("os"), sys.modules.get("subprocess")
        fake_os = types.ModuleType("os")
        fake_os.environ = {"GIT_TRACE": "synthetic-log", "GIT_CONFIG_COUNT": "1", "SystemRoot": "synthetic-system"}
        fake_os.devnull = "NUL"
        fake_subprocess = types.ModuleType("subprocess")
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            return types.SimpleNamespace(returncode=0, stdout=PINNED_MANIFEST)

        fake_subprocess.run = run
        sys.modules["os"], sys.modules["subprocess"] = fake_os, fake_subprocess
        try:
            self.assertEqual(p.committed_manifest(), PINNED_MANIFEST)
        finally:
            for name, previous in (("os", saved_os), ("subprocess", saved_subprocess)):
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous
        args, kwargs = calls[0]
        self.assertEqual(kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")
        self.assertNotIn("GIT_TRACE", kwargs["env"])
        self.assertNotIn("GIT_CONFIG_COUNT", kwargs["env"])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], "NUL")
        self.assertTrue(all(value in args for value in ("trace2.eventTarget=0", "trace2.perfTarget=0", "trace2.normalTarget=0")))

    def test_default_and_help_do_not_load_native_or_manifest(self):
        native, manifest = p.WindowsAPI, p.committed_manifest

        def forbidden():
            raise AssertionError("default performed I/O")

        p.WindowsAPI = p.committed_manifest = forbidden
        try:
            for args in ([], ["--help"], ["--execute"], ["--execute-approved", "--retry"]):
                with redirect_stdout(io.StringIO()):
                    self.assertIn(p.main(args), (0, 2))
        finally:
            p.WindowsAPI, p.committed_manifest = native, manifest

    def test_approval_requires_review_authorization_and_exact_schema(self):
        a = MemoryAPI().approval
        p.validate_approval(a, "0" * 64)
        for key, value in (("execution_authorized", False), ("reviewed_tool_sha256", "f" * 64),
                           ("approved_revision", "f" * 40), ("independent_review_sha256", ""),
                           ("schema_version", True)):
            with self.subTest(key=key):
                bad = copy.deepcopy(a)
                bad[key] = value
                with self.assertRaises(p.Stop):
                    p.validate_approval(bad, "0" * 64)
        bad = dict(a, allow_overwrite=True)
        with self.assertRaises(p.Stop):
            p.validate_approval(bad, "0" * 64)

    def test_reject_ambiguous_paths_and_device_names(self):
        for path in (r"C:\Fixture\..\secret", r"C:\Fixture\file:stream", r"C:\Fixture\NUL.txt",
                     "C:\\Fixture\\trailing. ", r"\\server\share\file", r"\\?\C:\Fixture", "C:/Fixture"):
            with self.subTest(path=path), self.assertRaises(p.Stop):
                p.path_chain(path)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(p.Stop):
            p.parse_json('{"execution_authorized":false,"execution_authorized":true}')

    def test_known_folder_guid_layout(self):
        self.assertEqual(p.LOCAL_APPDATA_GUID_BYTES,
                         uuid.UUID("F1B32785-6FBA-4FCF-9D55-7B8E7F157091").bytes_le)

    @unittest.skipUnless(PINNED_MANIFEST is not None, "guarded harness supplies committed manifest bytes")
    def test_actual_committed_manifest_contract_without_opening_sources(self):
        specs = p.make_specs(PINNED_MANIFEST, r"C:\Fixture\Temp")
        self.assertEqual(len(specs), 7)
        self.assertEqual(sum(s.size for s in specs), 1341222)
        self.assertEqual(specs[0].source_revision, "UNKNOWN")
        self.assertEqual(specs[-2].recorded_acceptance, "FAIL")
        self.assertEqual(specs[-1].recorded_acceptance, "FAIL")
        self.assertIn("static", specs[1].recorded_scope)
        p.validate_specs(specs)
        with self.assertRaises(p.Stop):
            p.make_specs(PINNED_MANIFEST + b" ", r"C:\Fixture\Temp")


class KnownFolderCleanupTests(unittest.TestCase):
    """Invoke the actual method without constructing ctypes or loading a DLL."""

    def adapter(self, result=0, allocated=True, path=r"C:\Fixture\Local", call_raises=False):
        class Pointer:
            value = None

        class ByteArray:
            def __mul__(self, count):
                return self

            def from_buffer_copy(self, value):
                return value

        reads, freed = [], []

        def read_string(address):
            self.assertEqual(address, 123)
            reads.append(address)
            return path

        def resolve(guid, flags, token, output):
            self.assertEqual(flags, 0x4000)
            self.assertIsNone(token)
            output.value = 123 if allocated else None
            if call_raises:
                raise p.Stop("synthetic_call_failure")
            return result

        api = p.WindowsAPI.__new__(p.WindowsAPI)
        api.c = types.SimpleNamespace(c_ubyte=ByteArray(), c_void_p=Pointer,
                                      byref=lambda value: value, wstring_at=read_string)
        api.SHGetKnownFolderPath = resolve
        api.CoTaskMemFree = lambda output: freed.append(output.value)
        return api, reads, freed

    def test_success_allocated_buffer_freed_exactly_once(self):
        api, reads, freed = self.adapter()
        self.assertEqual(api.known_folder(), r"C:\Fixture\Local")
        self.assertEqual(reads, [123])
        self.assertEqual(freed, [123])

    def test_failed_hresult_allocated_buffer_freed_then_failure_propagates(self):
        api, reads, freed = self.adapter(result=-2147467259)
        with self.assertRaisesRegex(p.Stop, "^known_folder$"):
            api.known_folder()
        self.assertEqual(reads, [])
        self.assertEqual(freed, [123])

    def test_failed_hresult_null_buffer_safe(self):
        api, reads, freed = self.adapter(result=-2147467259, allocated=False)
        with self.assertRaisesRegex(p.Stop, "^known_folder$"):
            api.known_folder()
        self.assertEqual(reads, [])
        self.assertEqual(freed, [])

    def test_success_hresult_null_buffer_still_fails_closed(self):
        api, reads, freed = self.adapter(allocated=False)
        with self.assertRaisesRegex(p.Stop, "^known_folder$"):
            api.known_folder()
        self.assertEqual(reads, [])
        self.assertEqual(freed, [])

    def test_path_validation_failure_frees_allocated_buffer(self):
        api, reads, freed = self.adapter(path=r"\\unapproved\redirect")
        with self.assertRaises(p.Stop):
            api.known_folder()
        self.assertEqual(reads, [123])
        self.assertEqual(freed, [123])

    def test_call_exception_after_allocation_still_cleans_up(self):
        api, reads, freed = self.adapter(call_raises=True)
        with self.assertRaisesRegex(p.Stop, "^synthetic_call_failure$"):
            api.known_folder()
        self.assertEqual(reads, [])
        self.assertEqual(freed, [123])


if __name__ == "__main__":
    unittest.main()
