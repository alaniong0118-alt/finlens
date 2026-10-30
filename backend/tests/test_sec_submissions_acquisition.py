"""Bounded offline acceptance; no DNS, sockets, DB, services or native fixtures.

Run: backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_submissions_acquisition.py
Native fixtures require a separately approved provisioned disposable RootSpec:
  same command --native-approved-root-spec ABSOLUTE_JSON_PATH
That option is never used in default acceptance. Artifacts are intentionally kept.
"""

import ctypes
from datetime import datetime, timezone
import hashlib
import http.client
import inspect
import io
import json
from pathlib import Path
import socket
import ssl
import sys
import threading
import unittest
from unittest.mock import patch


DENIED = []


def deny_network(*args, **kwargs):
    DENIED.append("denied")
    raise AssertionError("offline_network_denied")


# Install before application import. Stdlib SSL is already initialized so its
# class definitions do not need the replaced socket constructor.
socket.socket = socket.create_connection = socket.getaddrinfo = deny_network
socket.gethostbyname = socket.gethostbyname_ex = socket.gethostbyaddr = deny_network
def audit_network(event, args):
    if event.startswith("socket."):
        deny_network()
sys.addaudithook(audit_network)
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import sec_submissions_acquisition as a
from app import sec_submissions_custody as k


CIK = "0000123456"
ID = "12345678-1234-4234-8234-123456789abc"
BODY = b'{"cik":"123456","name":"Offline Fixture"}'
UTC = datetime(2026, 10, 30, tzinfo=timezone.utc)
VOLUME = "\\\\?\\Volume{12345678-1234-1234-1234-123456789abc}\\"
SID = "S-1-5-21-123-456-789-1001"
ACES = tuple((sid, 0x1F01FF, 3, 0) for sid in (SID, "S-1-5-18", "S-1-5-32-544"))
SPEC = k.RootSpec(VOLUME, ("fixture",), 123, "2" * 32, "a" * 64, SID)
NATIVE_SPEC = None


def wire(body=BODY, fields=None, status=b"HTTP/1.1 200 OK\r\n", tail=b""):
    if fields is None:
        fields = [(b"Content-Length", str(len(body)).encode()),
                  (b"Content-Type", b"application/json")]
    return status + b"".join(n + b":" + v + b"\r\n" for n, v in fields) + b"\r\n" + body + tail


class Clock:
    def __init__(self):
        self.ns = self.calls = 0
        self.hook = lambda n: None

    def __call__(self):
        self.calls += 1
        self.hook(self.calls)
        return self.ns


class TraceFP(io.BytesIO):
    def __init__(self, data, harness):
        super().__init__(data)
        self.h = harness
        self.body_reads = 0
        self.requests = []

    def readline(self, count=-1):
        self.requests.append(count)
        self.h.event("before:header")
        result = super().readline(count)
        self.h.event("after:header")
        return result

    def read(self, count=-1):
        self.body_reads += 1
        self.h.event("before:body")
        result = super().read(count)
        self.h.event("after:body")
        return self.h.transform_body(result, count)

    def close(self):
        if not self.closed:
            super().close()
            self.h.event("close:response")


class FakeSocket:
    def __init__(self, h):
        self.h, self.fp = h, TraceFP(h.raw, h)
        self.timeouts = []

    def makefile(self, mode):
        assert mode == "rb"
        return self.fp

    def settimeout(self, timeout):
        self.timeouts.append(timeout)


class FakeConnection:
    def __init__(self, h, op):
        self.h, self.op, self.closed, self.requests = h, op, False, []
        self.physical_attempts = []
        self.sock = FakeSocket(h)

    def request(self, method, path, body, headers):
        self.h.event("before:request")
        # Scripted connector behavior, never actual DNS/TCP. One application
        # request may involve several address attempts in stdlib transport.
        self.physical_attempts.extend(("fixture-v6", "fixture-v4a", "fixture-v4b"))
        self.requests.append((method, path, body, headers))
        self.h.event("after:request")

    def getresponse(self):
        response = a.StrictHTTPResponse(self.sock, operation=self.op, method="GET")
        self._response_token = self.op.own(response, lambda r: r.close())
        try:
            response.begin()
            return response
        except BaseException:
            response.close()
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            self.sock.fp.close()
            self.h.event("close:connection")


class FakeAPI:
    """In-memory native seam preserving node identity across directory rename."""

    def __init__(self, harness):
        self.h, self.nodes, self.handles, self.next = harness, {}, {}, 100
        self.opens, self.closes, self.rename_calls = [], [], []
        self.status, self.rename_error = 0, None
        self.add(VOLUME, True, "1" * 32)
        self.add(SPEC.final_path, True, SPEC.file_id)

    def add(self, path, directory, identity=None):
        self.nodes[path] = dict(path=path, directory=directory, data=b"", position=0,
                                id=identity or f"{len(self.nodes) + 30:032x}", links=1,
                                attributes=0, tag=0, owner=SID, aces=ACES,
                                security="a" * 64)
        return self.nodes[path]

    def open(self, parent, name, access, share, directory, create, op):
        self.h.event("before:open:" + name)
        if parent is None:
            path = VOLUME
            assert name == "\\??\\" + VOLUME[4:]
        else:
            path = self.handles[parent]["node"]["path"].rstrip("\\") + "\\" + name
        if create:
            if path in self.nodes:
                raise k.CustodyError("native_open_or_collision")
            node = self.add(path, directory)
        else:
            if path not in self.nodes:
                raise k.CustodyError("native_open_or_collision")
            node = self.nodes[path]
        self.next += 1
        handle = self.next
        self.handles[handle] = dict(node=node, closed=False, position=0)
        token = op.own(handle, self.close, native=True)
        self.opens.append((handle, path, access, share, directory, create))
        self.h.event("after:open:" + name)
        return handle, token

    def observe(self, handle):
        self.h.event("before:observe")
        node = self.handles[handle]["node"]
        result = dict(volume_serial=SPEC.volume_serial, file_id=node["id"],
                      final_path=node["path"], security_sha256=node["security"],
                      directory=node["directory"], length=len(node["data"]),
                      filesystem="NTFS", attributes=node["attributes"], reparse_tag=node["tag"],
                      links=node["links"], delete_pending=False,
                      owner_sid=node["owner"], aces=node["aces"])
        result = self.h.transform_observation(result)
        self.h.event("after:observe")
        return result

    def names(self, handle, op):
        self.h.event("before:names")
        prefix = self.handles[handle]["node"]["path"] + "\\"
        result = tuple(sorted(path[len(prefix):] for path in self.nodes
                              if path.startswith(prefix) and "\\" not in path[len(prefix):]))
        self.h.event("after:names")
        return result

    def rewind(self, handle):
        self.h.event("before:rewind")
        self.handles[handle]["position"] = 0
        self.h.event("after:rewind")

    def read(self, handle, count):
        self.h.event("before:read")
        entry = self.handles[handle]
        position = entry["position"]
        result = entry["node"]["data"][position:position + count]
        entry["position"] += len(result)
        self.h.event("after:read")
        return result

    def write(self, handle, data):
        self.h.event("before:write")
        entry = self.handles[handle]
        assert entry["position"] == len(entry["node"]["data"])
        entry["node"]["data"] += data
        entry["position"] += len(data)
        self.h.event("after:write")
        return len(data)

    def flush(self, handle):
        self.h.event("before:flush")
        self.h.event("after:flush")

    def rename(self, handle, root, name, op):
        self.h.event("before:rename")
        self.rename_calls.append((handle, root, name))
        if self.rename_error:
            raise self.rename_error
        if self.status == 0:
            source = self.handles[handle]["node"]["path"]
            destination = self.handles[root]["node"]["path"] + "\\" + name
            if destination in self.nodes:
                return k.STATUS_COLLISION
            for path in tuple(self.nodes):
                if path == source or path.startswith(source + "\\"):
                    node = self.nodes.pop(path)
                    node["path"] = destination + path[len(source):]
                    self.nodes[node["path"]] = node
        self.h.event("after:rename")
        return self.status

    def close(self, handle):
        entry = self.handles[handle]
        assert not entry["closed"], "double close"
        entry["closed"] = True
        self.closes.append(handle)
        self.h.event("close:handle")


class Harness:
    def __init__(self, raw=None):
        self.raw = wire() if raw is None else raw
        self.clock, self.cancel = Clock(), a.Cancellation()
        self.events, self.hook = [], lambda label, index: None
        self.transform_body = lambda data, count: data
        self.transform_observation = lambda value: value
        self.api, self.connection = FakeAPI(self), None
        self.exchange = a.InertDescriptor(self.open_exchange)
        self.store = a.InertDescriptor(lambda op: k.WindowsStore(op, SPEC, self.api))

    def event(self, label):
        self.events.append(label)
        self.hook(label, len(self.events))

    def open_exchange(self, op):
        def factory(operation):
            self.connection = FakeConnection(self, operation)
            return self.connection
        return a.HTTPSExchange(op, CIK, "FinLens offline fixture", factory)

    def capture(self):
        with patch.object(a.uuid, "uuid4", return_value=ID):
            return a.capture_injected(CIK, exchange=self.exchange, store=self.store,
                                      cancellation=self.cancel, monotonic_ns=self.clock,
                                      utc_now=lambda: UTC)

    def receipt(self):
        return self.api.nodes[SPEC.final_path + "\\" + k.bundle_name(ID, "complete")
                              + "\\receipt.json"]["data"]

    def released(self):
        return all(e["closed"] for e in self.api.handles.values())


class OfflineTests(unittest.TestCase):
    def failure(self, h, code=None):
        with self.assertRaises(a.CaptureFailure) as caught:
            h.capture()
        if code:
            self.assertIn(code, caught.exception.codes)
        selector = caught.exception.capture_id
        if selector is not None:
            self.assertEqual(a.capture_id(selector), selector)
        self.assertEqual(str(caught.exception), caught.exception.code)
        self.assertTrue(h.released())
        if h.connection:
            self.assertTrue(h.connection.closed)
        return caught.exception

    def test_success_exact_bytes_closed_and_single_get(self):
        h = Harness()
        result = h.capture()
        self.assertEqual(result.storage_state, "PUBLISHED_VERIFIED")
        self.assertEqual(result.origin, "offline_injected")
        self.assertEqual(result.verification_status, "unverified")
        self.assertEqual(result.body_sha256, hashlib.sha256(BODY).hexdigest())
        self.assertTrue(h.released())
        self.assertTrue(h.connection.closed)
        self.assertEqual(len(h.connection.requests), 1)
        self.assertEqual(h.connection.requests[0][:3],
                         ("GET", "/submissions/CIK0000123456.json", None))
        self.assertEqual(len(h.api.rename_calls), 1)
        self.assertEqual(h.cancel.cancel(), "too_late")
        self.assertEqual(result.receipt_sha256, hashlib.sha256(h.receipt()).hexdigest())

    def test_pure_imports_no_configuration_database_or_provider(self):
        for name in ("app.config", "app.database", "dotenv", "sqlalchemy", "openai"):
            self.assertNotIn(name, sys.modules)

    def test_cik_binding_and_expected_cik_validation(self):
        for body in (BODY.replace(b"123456", b"123457"), b"not JSON"):
            h = Harness(wire(body))
            self.failure(h)
            self.assertFalse(h.api.rename_calls)
        for cik in (True, "123456", "0000000000", "0000123456/evil", "１２３４５６７８９０"):
            h = Harness()
            with self.assertRaises(a.CaptureFailure):
                a.capture_injected(cik, exchange=h.exchange, store=h.store,
                                   cancellation=h.cancel, monotonic_ns=h.clock, utc_now=lambda: UTC)
            self.assertFalse(h.api.opens)
            self.assertEqual(h.exchange.state, "consumed")

    def test_clock_start_failure_still_consumes_owned_descriptors(self):
        for field in ("monotonic_ns", "utc_now"):
            h = Harness()
            clocks = dict(monotonic_ns=h.clock, utc_now=lambda: UTC)
            clocks[field] = lambda: (_ for _ in ()).throw(OSError("clock"))
            with self.assertRaises(a.CaptureFailure):
                a.capture_injected(CIK, exchange=h.exchange, store=h.store,
                                   cancellation=h.cancel, **clocks)
            self.assertEqual(h.exchange.state, "consumed")
            self.assertEqual(h.store.state, "consumed")

    def test_raw_header_rejections_deliver_zero_body(self):
        bad_blocks = [
            b"HTTP/1.0 200 OK\r\nContent-Length:40\r\n\r\n",
            b"HTTP/1.1\t200 OK\r\nContent-Length:40\r\n\r\n",
            b"HTTP/1.1 100 Continue\r\n\r\n",
            b"HTTP/1.1 301 Moved\r\nLocation:https://example.test\r\n\r\n",
            b"HTTP/1.1 200 OK\nContent-Length:40\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Length:40\r\n",  # premature EOF
        ]
        fields = [b" bad:field", b"Bad :field", b"NoColon", b"Bad\x00:field",
                  b"Bad:\xff", b"Bad:\tfield", b"Bad:field\rhidden",
                  b"Content-Length:040", b"Content-Length:+40", b"Content-Length:0",
                  b"Content-Length:4194305", b"Transfer-Encoding:identity", b"Transfer-Encoding:chunked",
                  b"Content-Encoding:gzip", b"Content-Range:bytes 0-1/2", b"Trailer:Digest",
                  b"Location:https://data.sec.gov", b"Content-Type:text/html"]
        for field in fields:
            bad_blocks.append(b"HTTP/1.1 200 OK\r\nContent-Length:" + str(len(BODY)).encode()
                              + b"\r\n" + field + b"\r\n\r\n")
        for block in bad_blocks:
            with self.subTest(block=block[:100]):
                h = Harness(block + BODY)
                self.failure(h)
                self.assertEqual(h.connection.sock.fp.body_reads, 0)
                self.assertFalse(h.api.rename_calls)

    def test_duplicate_critical_headers_even_equal(self):
        # Forbidden headers have no accepted singleton; their rejection is covered
        # separately. Every permitted critical singleton below must first succeed.
        values = {"content-length": str(len(BODY)).encode(),
                  "content-type": b"application/json", "content-encoding": b"identity",
                  "date": b"Fri, 30 Oct 2026 00:00:00 GMT", "etag": b'"offline-v1"',
                  "last-modified": b"Thu, 29 Oct 2026 00:00:00 GMT"}
        self.assertEqual(set(values), a.RETAINED)
        for name, value in values.items():
            fields = [] if name == "content-length" else [(b"Content-Length", str(len(BODY)).encode())]
            fields.append((name.encode(), value))
            with self.subTest(name=name):
                Harness(wire(fields=fields)).capture()
                h = Harness(wire(fields=fields + [(name.upper().encode(), value)]))
                failure = self.failure(h, "duplicate_critical_header")
                self.assertEqual(failure.code, "duplicate_critical_header")
                self.assertEqual(h.connection.sock.fp.body_reads, 0)

    def test_parser_defect_and_disagreement_rejected(self):
        for mode in ("defect", "disagreement"):
            original = http.client.parse_headers
            def parse(fp, _mode=mode):
                headers = original(fp)
                if _mode == "defect":
                    headers.defects.append(ValueError("fixture"))
                else:
                    headers["Hidden"] = "field"
                return headers
            h = Harness()
            with patch.object(http.client, "parse_headers", parse):
                self.failure(h)
            self.assertEqual(h.connection.sock.fp.body_reads, 0)

    def test_header_name_value_field_limits(self):
        for name_size in (128, 129):
            h = Harness(wire(fields=[(b"Content-Length", str(len(BODY)).encode()),
                                     (b"X" * name_size, b"value")]))
            if name_size == 128:
                h.capture()
            else:
                self.failure(h, "header_name")
        for value_size in (2048, 2049):
            h = Harness(wire(fields=[(b"Content-Length", str(len(BODY)).encode()),
                                     (b"X", b"a" * value_size)]))
            if value_size == 2048:
                h.capture()
            else:
                self.failure(h)
        for fields in (64, 65):
            h = Harness(wire(fields=[(b"Content-Length", str(len(BODY)).encode())]
                                    + [(b"X", b"a")] * (fields - 1)))
            if fields == 64:
                h.capture()
            else:
                self.failure(h, "header_count")

    def test_exact_aggregate_and_status_limit(self):
        for total in (a.MAX_HEADER_BYTES, a.MAX_HEADER_BYTES + 1):
            base = b"HTTP/1.1 200 OK\r\nContent-Length:" + str(len(BODY)).encode() + b"\r\n"
            fields = b"X:" + b"a" * 2048 + b"\r\n"
            remainder = total - len(base) - 2 - len(fields) * 7
            block = base + fields * 7 + b"Y:" + b"b" * (remainder - 4) + b"\r\n\r\n"
            self.assertEqual(len(block), total)
            h = Harness(block + BODY)
            if total == a.MAX_HEADER_BYTES:
                h.capture()
            else:
                self.failure(h, "header_bytes_limit")
            self.assertTrue(all(0 < request <= 2180 for request in h.connection.sock.fp.requests))
        for size in (1024, 1025):
            prefix = b"HTTP/1.1 200 "
            line = prefix + b"A" * (size - len(prefix) - 2) + b"\r\n"
            h = Harness(wire(status=line))
            if size == 1024:
                h.capture()
            else:
                self.failure(h, "header_bytes_limit")

    def test_body_strict_boundaries_and_short_reads(self):
        # Whitespace preserves parser validity while reaching the exact cap.
        for size in (1, a.MAX_BODY, a.MAX_BODY + 1):
            raw_body = BODY + b" " * max(0, size - len(BODY)) if size > 1 else b"{"
            h = Harness(wire(raw_body))
            if size == a.MAX_BODY:
                h.capture()
            else:
                self.failure(h)
        h = Harness(wire(BODY[:-1], fields=[(b"Content-Length", str(len(BODY)).encode())]))
        self.failure(h, "body_read")
        for transform in (lambda d, n: "text", lambda d, n: d + b"x"):
            h = Harness()
            h.transform_body = transform
            self.failure(h, "body_read")

    def test_no_read_past_declared_representation(self):
        h = Harness(wire(tail=b"arbitrary trailing connection bytes"))
        h.capture()
        self.assertEqual(h.connection.sock.fp.body_reads, 1)
        body = h.api.nodes[SPEC.final_path + "\\" + k.bundle_name(ID, "complete") + "\\body.bin"]
        self.assertEqual(body["data"], BODY)

    def test_buffered_read_ahead_is_preserved(self):
        class Raw(io.RawIOBase):
            def __init__(self):
                self.stream, self.delivered = io.BytesIO(wire()), 0
            def readable(self):
                return True
            def readinto(self, target):
                data = self.stream.read(len(target))
                target[:len(data)] = data
                self.delivered += len(data)
                return len(data)
        raw = Raw()
        class Sock:
            def makefile(self, mode):
                return io.BufferedReader(raw)
            def settimeout(self, value):
                pass
        op = a.Operation(a.Cancellation(), monotonic_ns=lambda: 0, utc_now=lambda: UTC)
        response = a.StrictHTTPResponse(Sock(), operation=op)
        for action in (lambda: response.read(1), lambda: response.readinto(bytearray(1)),
                       lambda: response.read1(1), lambda: response.readline(1), lambda: response.peek(1)):
            with self.assertRaises(k.CustodyError):
                action()
        response.begin()
        self.assertEqual(raw.delivered, len(wire()))
        self.assertEqual(response.read(len(BODY)), BODY)
        response.close()

    def test_socket_timeout_capped_by_remaining_work(self):
        h = Harness()
        h.hook = lambda label, i: setattr(h.clock, "ns", 27_500_000_000)
        h.capture()
        self.assertTrue(all(0 < n <= 0.5 for n in h.connection.sock.timeouts))

    def test_work_reserve_and_late_cleanup_deadline_withhold_delivery(self):
        h = Harness()
        h.hook = lambda label, i: setattr(h.clock, "ns", a.WORK_NS) if label == "after:header" else None
        self.failure(h, "deadline")
        self.assertEqual(h.connection.sock.fp.body_reads, 0)
        h = Harness()
        def late(label, i):
            if label == "close:handle" and h.api.rename_calls:
                h.clock.ns = a.TOTAL_NS + 1
        h.hook = late
        result = self.failure(h, "deadline")
        self.assertEqual(result.outcome.publication, "PUBLISHED_VERIFIED")
        self.assertEqual(result.outcome.cleanup, "closed")

    def test_preopened_native_store_resources_close_on_rejection(self):
        h = Harness()
        old = a.Operation(a.Cancellation(), monotonic_ns=h.clock, utc_now=lambda: UTC)
        old.claim()
        h.store.resource = k.WindowsStore(old, SPEC, h.api)
        h.store.state = "opened"
        self.failure(h, "descriptor_not_inert")
        self.assertEqual(len(h.api.closes), 2)

    def test_consumption_started_rejects_and_closes_without_store_open(self):
        h = Harness()
        def opener(op):
            ex = h.open_exchange(op)
            ex.started = True
            return ex
        h.exchange = a.InertDescriptor(opener)
        self.failure(h, "exchange_not_inert")
        self.assertFalse(h.api.opens)

    def test_unknown_native_io_retains_handles_but_closes_http(self):
        h = Harness()
        def pending(handle, root, name, op):
            op.quarantined = True
            raise k.CustodyError("publication_indeterminate")
        h.api.rename = pending
        with self.assertRaises(a.CaptureFailure) as caught:
            h.capture()
        self.assertEqual(caught.exception.outcome.publication, "indeterminate")
        self.assertEqual(caught.exception.outcome.cleanup, "unverified_pending_io")
        self.assertTrue(h.connection.closed)
        self.assertFalse(h.released())

    def test_no_physical_tcp_attempt_count_asserted(self):
        h = Harness()
        h.capture()
        self.assertEqual(len(h.connection.requests), 1)
        self.assertEqual(len(h.connection.physical_attempts), 3)

    def test_every_external_event_cancel_deadline_and_io(self):
        baseline = Harness()
        baseline.capture()
        for event_index in range(1, len(baseline.events) + 1):
            for mode in ("cancel", "deadline", "io"):
                h = Harness()
                def hook(label, index, *, target=event_index, mode=mode):
                    if index == target:
                        if mode == "cancel":
                            h.cancel.cancel()
                        elif mode == "deadline":
                            h.clock.ns = a.TOTAL_NS + 1
                        else:
                            raise OSError("private fixture detail must never escape")
                h.hook = hook
                with self.subTest(event=baseline.events[event_index - 1], index=event_index, mode=mode):
                    failure = self.failure(h)
                    self.assertNotIn("private", str(failure))
                    self.assertNotEqual(failure.outcome.delivery, "logical_handoff")

    def test_every_clock_checkpoint_cancellation_and_deadline(self):
        baseline = Harness()
        baseline.capture()
        # Exclude the initial timestamp read, which precedes token ownership.
        for call in range(2, baseline.clock.calls + 1):
            for mode in ("cancel", "deadline"):
                h = Harness()
                def hook(n, target=call, mode=mode):
                    if n == target:
                        if mode == "cancel":
                            h.cancel.cancel()
                        else:
                            h.clock.ns = a.TOTAL_NS + 1
                h.clock.hook = hook
                with self.subTest(clock_call=call, mode=mode):
                    self.failure(h, "cancelled" if mode == "cancel" else "deadline")

    def test_cancellation_on_entry_consumes_descriptors(self):
        h = Harness()
        self.assertEqual(h.cancel.cancel(), "accepted")
        self.assertEqual(h.cancel.cancel(), "already_cancelled")
        failure = self.failure(h, "cancelled")
        self.assertIsNone(failure.capture_id)
        self.assertEqual(h.exchange.state, "consumed")
        self.assertEqual(h.store.state, "consumed")
        self.assertFalse(h.api.opens)

    def test_preopened_and_consumed_inputs_rejected_and_closed(self):
        for state in ("opened", "consumed"):
            h = Harness()
            class Resource:
                closed = False
                def close(self):
                    self.closed = True
            resource = Resource()
            h.exchange.state, h.exchange.resource = state, resource
            self.failure(h, "descriptor_not_inert")
            self.assertTrue(resource.closed)
        h = Harness()
        h.capture()
        h.cancel = a.Cancellation()
        self.failure(h, "descriptor_not_inert")

    def test_event_is_not_accepted_as_cancellation(self):
        h = Harness()
        h.cancel = threading.Event()
        self.failure(h, "cancellation_type")
        self.assertEqual(h.store.state, "consumed")

    def test_duplicate_descriptors_and_reused_token_rejected(self):
        h = Harness()
        h.store = h.exchange
        self.failure(h, "descriptor_reused")
        h = Harness()
        h.capture()
        h.exchange = a.InertDescriptor(h.open_exchange)
        self.failure(h, "cancellation_consumed")

    def test_partial_open_failure_all_registered_handles_closed(self):
        h = Harness()
        h.hook = lambda label, i: (_ for _ in ()).throw(OSError()) if label == "after:open:fixture" else None
        self.failure(h)
        self.assertEqual(len(h.api.opens), 2)
        self.assertEqual(h.api.closes, [row[0] for row in reversed(h.api.opens)])

    def test_after_rename_cancel_preserves_published_unverified(self):
        h = Harness()
        h.hook = lambda label, i: h.cancel.cancel() if label == "after:rename" else None
        failure = self.failure(h, "cancelled")
        self.assertEqual(failure.outcome.publication, "PUBLISHED_UNVERIFIED")
        self.assertEqual(len(h.api.rename_calls), 1)

    def test_failed_capture_selector_selects_explicit_recovery(self):
        h = Harness()
        h.hook = lambda label, i: h.cancel.cancel() if label == "after:rename" else None
        # Bypass Harness.capture's fixed-UUID fixture: only the actual failure
        # object may supply the selector for this acceptance test.
        with self.assertRaises(a.CaptureFailure) as caught:
            a.capture_injected(CIK, exchange=h.exchange, store=h.store, cancellation=h.cancel,
                               monotonic_ns=h.clock, utc_now=lambda: UTC)
        failure = caught.exception
        self.assertEqual(failure.outcome.publication, "PUBLISHED_UNVERIFIED")
        identifier = failure.capture_id
        self.assertEqual(a.capture_id(identifier), identifier)
        self.assertTrue(h.released())
        descriptor = a.InertDescriptor(lambda op: k.WindowsStore(op, SPEC, h.api))
        recovered = a.recover_injected(CIK, identifier, store=descriptor,
                                       cancellation=a.Cancellation(), monotonic_ns=lambda: 0,
                                       utc_now=lambda: UTC)
        self.assertEqual(recovered.capture_id, identifier)
        self.assertEqual(recovered.storage_state, "RECOVERED_VERIFIED_LOCAL")
        self.assertEqual(recovered.origin, "offline_injected")
        self.assertEqual(recovered.verification_status, "unverified")
        self.assertEqual(len(h.connection.requests), 1)
        self.assertEqual(len(h.api.rename_calls), 1)
        self.assertTrue(h.released())

    def replaced_file_identity(self, filename):
        h = Harness()
        observations = []
        def replace(label, index):
            if label == "after:rename":
                path = SPEC.final_path + "\\" + k.bundle_name(ID, "complete")
                node = h.api.nodes[path + "\\" + filename]
                observations.append((h.api.nodes[path]["id"], node["data"]))
                node["id"] = "f" * 32
                self.assertEqual((h.api.nodes[path]["id"], node["data"]), observations[0])
        h.hook = replace
        failure = self.failure(h, "integrity_failure")
        self.assertEqual(failure.code, "integrity_failure")
        self.assertEqual(failure.outcome.publication, "PUBLISHED_UNVERIFIED")
        self.assertEqual(failure.outcome.stored_integrity, "failed")
        self.assertEqual(len(observations), 1)
        return h, failure

    def test_replaced_body_id_with_identical_bytes_is_rejected(self):
        self.replaced_file_identity("body.bin")

    def test_replaced_receipt_id_with_identical_bytes_is_rejected(self):
        self.replaced_file_identity("receipt.json")

    def test_recovery_remains_current_integrity_only_after_file_id_change(self):
        for filename in ("body.bin", "receipt.json"):
            with self.subTest(filename=filename):
                h, failure = self.replaced_file_identity(filename)
                recovered = a.recover_injected(CIK, failure.capture_id,
                    store=a.InertDescriptor(lambda op: k.WindowsStore(op, SPEC, h.api)),
                    cancellation=a.Cancellation(), monotonic_ns=lambda: 0, utc_now=lambda: UTC)
                self.assertEqual(recovered.capture_id, failure.capture_id)
                self.assertEqual(recovered.storage_state, "RECOVERED_VERIFIED_LOCAL")
                self.assertEqual(recovered.origin, "offline_injected")
                self.assertEqual(recovered.verification_status, "unverified")
                self.assertTrue(h.released())

    def test_failure_before_id_allocation_has_no_recovery_selector(self):
        h = Harness()
        with patch.object(a.uuid, "uuid4", side_effect=OSError("private allocation failure")):
            with self.assertRaises(a.CaptureFailure) as caught:
                a.capture_injected(CIK, exchange=h.exchange, store=h.store, cancellation=h.cancel,
                                   monotonic_ns=h.clock, utc_now=lambda: UTC)
        self.assertIsNone(caught.exception.capture_id)
        self.assertEqual(str(caught.exception), "io_failure")
        self.assertEqual(h.exchange.state, "consumed")
        self.assertEqual(h.store.state, "consumed")
        self.assertFalse(h.api.opens)

    def test_close_failure_after_verification_withholds_delivery(self):
        h = Harness()
        def hook(label, i):
            if label == "close:handle" and h.api.rename_calls:
                raise OSError()
        h.hook = hook
        failure = self.failure(h, "cleanup_unverified")
        self.assertEqual(failure.outcome.publication, "PUBLISHED_VERIFIED")
        self.assertEqual(failure.outcome.cleanup, "unverified")

    def test_unknown_failed_and_collision_publication_no_retry(self):
        for status, code in ((1, "publication_indeterminate"), (k.STATUS_PENDING, "publication_indeterminate"),
                             (-1073741790, "publication_failed"), (k.STATUS_COLLISION, "publication_collision")):
            h = Harness()
            h.api.status = status
            failure = self.failure(h, code)
            self.assertEqual(failure.capture_id, ID)
            self.assertEqual(len(h.api.rename_calls), 1)
        h = Harness()
        h.api.rename_error = KeyboardInterrupt()
        self.failure(h, "publication_indeterminate")

    def test_existing_collision_target_is_unchanged(self):
        h = Harness()
        path = SPEC.final_path + "\\" + k.bundle_name(ID, "complete")
        existing = h.api.add(path, True)
        h.api.add(path + "\\body.bin", False)["data"] = b"existing"
        self.failure(h, "publication_collision")
        self.assertIs(h.api.nodes[path], existing)
        self.assertEqual(h.api.nodes[path + "\\body.bin"]["data"], b"existing")

    def test_access_sharing_and_closure_order(self):
        h = Harness()
        h.capture()
        directory_reads = []
        for handle, path, access, share, directory, create in h.api.opens:
            if path.endswith(".staging"):
                self.assertEqual((access, share), (k.SOURCE_ACCESS, k.SHARE_RW))
                source_handle = handle
            elif path.endswith(".complete"):
                self.assertEqual((access, share), (k.READER_ACCESS, k.SHARE_RWD))
                directory_reads.append(handle)
            elif not directory:
                self.assertEqual((access, share), (k.WRITER_ACCESS if create else k.FILE_READER_ACCESS, k.SHARE_R))
            else:
                self.assertEqual(share, k.SHARE_RW)
        self.assertLess(h.api.closes.index(directory_reads[0]), h.api.closes.index(source_handle))
        self.assertEqual(h.api.closes[-2:], [h.api.opens[1][0], h.api.opens[0][0]])
        # Writers are closed before the rename hook executes.
        before_rename = h.events.index("before:rename")
        self.assertEqual(h.events[:before_rename].count("close:handle"), 2)

    def test_reparse_hardlink_acl_owner_identity_filesystem_rejections(self):
        changes = [dict(reparse_tag=1), dict(attributes=0x400), dict(filesystem="FAT32"),
                   dict(owner_sid="S-1-5-21-999"), dict(aces=()), dict(file_id="f" * 32),
                   dict(delete_pending=True)]
        for change in changes:
            h = Harness()
            h.transform_observation = lambda value, change=change: dict(value, **change)
            with self.subTest(change=change):
                self.failure(h)
        h = Harness()
        h.transform_observation = lambda value: dict(value, links=2) if not value["directory"] else value
        self.failure(h, "custody_hardlink")

    def test_post_publication_identity_and_content_integrity_failures(self):
        for mode in ("id", "body", "extra", "receipt_valid_change"):
            h = Harness()
            def hook(label, i, mode=mode):
                if label == "after:rename":
                    path = SPEC.final_path + "\\" + k.bundle_name(ID, "complete")
                    if mode == "id":
                        h.api.nodes[path]["id"] = "f" * 32
                    elif mode == "body":
                        h.api.nodes[path + "\\body.bin"]["data"] = b"x" * len(BODY)
                    elif mode == "extra":
                        h.api.add(path + "\\extra", False)
                    else:
                        node = h.api.nodes[path + "\\receipt.json"]
                        receipt = json.loads(node["data"])
                        receipt["timestamps"] = {p: "2026-10-31T00:00:00.000000Z" for p in a.PHASES}
                        node["data"] = a._canonical(receipt)
            h.hook = hook
            failure = self.failure(h, "integrity_failure")
            self.assertEqual(failure.code, "integrity_failure")
            self.assertEqual(failure.outcome.publication, "PUBLISHED_UNVERIFIED")

    def test_receipt_canonical_roundtrip_and_closed_schema(self):
        h = Harness()
        h.capture()
        raw = h.receipt()
        value = a.verify_receipt(raw, BODY, expected_id=ID, expected_cik=CIK)
        self.assertEqual(raw, a._canonical(value))
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertFalse(raw.endswith(b"\n"))
        for key in value:
            for modified in ({k: v for k, v in value.items() if k != key}, dict(value, unknown=1)):
                with self.subTest(key=key):
                    with self.assertRaises(k.CustodyError):
                        a.verify_receipt(a._canonical(modified), BODY, expected_id=ID, expected_cik=CIK)

    def test_receipt_binding_types_revisions_and_time_rejections(self):
        h = Harness()
        h.capture()
        value = json.loads(h.receipt())
        changes = [("schema", "unknown"), ("capture_id", ID.upper()), ("cik", "123456"),
                   ("url", "https://example.test/"), ("origin", "sec_live"),
                   ("source_identity", "other"), ("http_status", True), ("byte_count", True),
                   ("byte_count", len(BODY) + 1), ("body_sha256", "0" * 64),
                   ("versions", dict(a.versions(), parser="old")),
                   ("versions", dict(a.versions(), extra="v1")),
                   ("timestamps", dict(value["timestamps"], receipt_created="2026-02-30T00:00:00.000000Z")),
                   ("timestamps", dict(value["timestamps"], receipt_created="2026-10-29T00:00:00.000000Z")),
                   ("offsets_ns", dict(value["offsets_ns"], operation_start=True)),
                   ("offsets_ns", dict(value["offsets_ns"], receipt_created=a.WORK_NS + 1)),
                   ("offsets_ns", dict(value["offsets_ns"], extra=0)),
                   ("response_headers", [["content-length", str(len(BODY))], ["content-length", str(len(BODY))]]),
                   ("response_headers", [["location", "x"]])]
        for field, content in changes:
            with self.subTest(field=field, content=content):
                with self.assertRaises(k.CustodyError):
                    a.verify_receipt(a._canonical(dict(value, **{field: content})), BODY,
                                     expected_id=ID, expected_cik=CIK)

    def test_receipt_duplicate_noncanonical_nonfinite_and_escaping(self):
        h = Harness()
        h.capture()
        raw = h.receipt()
        for changed in (raw + b"\n", b"\xef\xbb\xbf" + raw,
                        raw.replace(b'"http_status":200', b'"http_status":200,"http_status":200'),
                        raw.replace(b'"http_status":200', b'"http_status":NaN'),
                        raw.replace(b'"http_status":200', b'"http_status":1e309'),
                        raw.replace(b'"http_status":200', b'"http_status":200.0'),
                        json.dumps(json.loads(raw), indent=2).encode(), b"[]", b"{" * 1000):
            with self.assertRaises(k.CustodyError):
                a.verify_receipt(changed, BODY, expected_id=ID, expected_cik=CIK)
        self.assertEqual(a._canonical({"z": "é", "a": "\n"}), b'{"a":"\\n","z":"\\u00e9"}')
        with self.assertRaises(ValueError):
            a._canonical({"n": float("nan")})

    def test_wall_clock_regression_prevents_publication(self):
        h = Harness()
        times = iter([UTC, UTC.replace(day=29), UTC, UTC])
        with self.assertRaises(a.CaptureFailure) as caught:
            a.capture_injected(CIK, exchange=h.exchange, store=h.store, cancellation=h.cancel,
                               monotonic_ns=h.clock, utc_now=lambda: next(times))
        self.assertIn("wall_clock_regression", caught.exception.codes)
        self.assertFalse(h.api.rename_calls)

    def test_recovery_is_separate_local_verification_without_refetch(self):
        h = Harness()
        h.capture()
        count = len(h.connection.requests)
        descriptor = a.InertDescriptor(lambda op: k.WindowsStore(op, SPEC, h.api))
        result = a.recover_injected(CIK, ID, store=descriptor, cancellation=a.Cancellation(),
                                    monotonic_ns=lambda: 0, utc_now=lambda: UTC)
        self.assertEqual(result.storage_state, "RECOVERED_VERIFIED_LOCAL")
        self.assertEqual(result.origin, "offline_injected")
        self.assertEqual(result.verification_status, "unverified")
        self.assertEqual(len(h.connection.requests), count)
        self.assertEqual(len(h.api.rename_calls), 1)
        self.assertTrue(h.released())

    def test_recovery_wrong_selector_and_noncanonical_receipt_reject(self):
        for mode in ("selector", "receipt"):
            h = Harness()
            h.capture()
            if mode == "receipt":
                path = SPEC.final_path + "\\" + k.bundle_name(ID, "complete") + "\\receipt.json"
                h.api.nodes[path]["data"] += b"\n"
            descriptor = a.InertDescriptor(lambda op: k.WindowsStore(op, SPEC, h.api))
            with self.assertRaises(a.CaptureFailure):
                a.recover_injected(CIK, "87654321-1234-4234-8234-123456789abc" if mode == "selector" else ID,
                                   store=descriptor, cancellation=a.Cancellation(),
                                   monotonic_ns=lambda: 0, utc_now=lambda: UTC)
            self.assertTrue(h.released())

    def test_failure_precedence_and_cleanup_keeps_secondary_codes(self):
        h = Harness()
        def hook(label, i):
            if label == "after:rename":
                h.cancel.cancel()
                h.clock.ns = a.TOTAL_NS + 1
                raise OSError()
            if label == "close:handle" and h.api.rename_calls:
                raise OSError()
        h.hook = hook
        failure = self.failure(h)
        self.assertEqual(failure.code, "publication_indeterminate")
        self.assertIn("cleanup_unverified", failure.codes)
        self.assertIn("cancelled", failure.codes)

    def test_same_lock_cancel_handoff_races(self):
        for _ in range(50):
            cancel = a.Cancellation()
            op = a.Operation(cancel, monotonic_ns=lambda: 0, utc_now=lambda: UTC)
            op.claim()
            op.cleanup = "closed"
            barrier, results = threading.Barrier(2), []
            def request_cancel():
                barrier.wait()
                results.append(cancel.cancel())
            worker = threading.Thread(target=request_cancel)
            worker.start()
            barrier.wait()
            try:
                result = op.handoff("detached")
            except a.CaptureFailure:
                result = None
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual((result, results[0]),
                             ("detached", "too_late") if result else (None, "accepted"))

    def trace_cancellation(self, marker):
        cancel = a.Cancellation()
        op = a.Operation(cancel, monotonic_ns=lambda: 0, utc_now=lambda: UTC)
        op.claim()
        op.cleanup = "closed"
        lines, start = inspect.getsourcelines(a.Operation.handoff)
        target = [start + n for n, line in enumerate(lines) if marker in line]
        self.assertEqual(len(target), 1)
        responses = []
        def trace(frame, event, arg):
            if (event == "line" and frame.f_code is a.Operation.handoff.__code__
                    and frame.f_lineno == target[0] and not responses):
                responses.append(cancel.cancel())
            return trace
        previous = sys.gettrace()
        try:
            sys.settrace(trace)
            try:
                result, failure = op.handoff("detached"), None
            except a.CaptureFailure as error:
                result, failure = None, error
        finally:
            sys.settrace(previous)
        self.assertEqual(len(responses), 1)
        return op, result, failure, responses[0]

    def test_reentrant_cancel_after_final_check_prevents_handoff(self):
        op, result, failure, response = self.trace_cancellation('require(self.cleanup ==')
        self.assertEqual(response, "accepted")
        self.assertIsNone(result)
        self.assertIsNotNone(failure)
        self.assertIn("cancelled", failure.codes)
        self.assertEqual(op.delivery, "withheld")

    def test_reentrant_cancel_immediately_before_commit_prevents_handoff(self):
        op, result, failure, response = self.trace_cancellation('decision = self.cancel._decision.setdefault')
        self.assertEqual(response, "accepted")
        self.assertIsNone(result)
        self.assertIsNotNone(failure)
        self.assertIn("cancelled", failure.codes)
        self.assertFalse(op.cancel._handed_off)

    def test_reentrant_cancel_immediately_after_commit_is_too_late(self):
        op, result, failure, response = self.trace_cancellation('if decision is _HANDOFF:')
        self.assertEqual(response, "too_late")
        self.assertEqual(result, "detached")
        self.assertIsNone(failure)
        self.assertFalse(op.cancel._cancelled)
        self.assertTrue(op.cancel._handed_off)
        self.assertEqual(op.delivery, "logical_handoff")

    def test_handoff_samples_injected_clock_outside_terminal_lock(self):
        cancel = a.Cancellation()
        def clock():
            self.assertFalse(cancel._lock._is_owned())
            return 0
        op = a.Operation(cancel, monotonic_ns=clock, utc_now=lambda: UTC)
        op.claim()
        op.cleanup = "closed"
        self.assertEqual(op.handoff("detached"), "detached")

    def test_disabled_entrypoint_ignores_factories_environment_and_network(self):
        class Bomb:
            def __getattribute__(self, name):
                raise AssertionError("side_effect")
        import os
        before = len(DENIED)
        with patch.dict(os.environ, {"SEC_ACQUISITION_ENABLED": "1", "FINLENS_SEC_LIVE": "true"}):
            with self.assertRaises(k.CustodyError) as caught:
                a.acquire_submissions(Bomb(), exchange=Bomb(), store=Bomb(), enabled=True)
        self.assertEqual(caught.exception.code, "live_acquisition_disabled")
        self.assertEqual(len(DENIED), before)
        for function in (socket.socket, socket.getaddrinfo, socket.create_connection):
            with self.assertRaises(AssertionError):
                function()


class NativeProtocolMockTests(unittest.TestCase):
    def test_x64_layout_and_status_classification(self):
        k.assert_layout()
        self.assertEqual(ctypes.alignment(k.FILE_RENAME_INFORMATION), 8)
        for status, expected in ((0, "success"), (0x103, "pending"),
                                  (k.STATUS_COLLISION, "collision"), (-1073741790, "failure"),
                                  (0x80000005, "failure"), (1, "indeterminate")):
            self.assertEqual(k.classify_status(status), expected)

    def test_bindings_without_loading_native_libraries(self):
        calls = {}
        class Function:
            pass
        class Library:
            def __getattr__(self, name):
                calls[name] = Function()
                return calls[name]
        with patch.object(k.sys, "platform", "win32"), patch.object(
                k.c, "WinDLL", lambda *args, **kwargs: Library(), create=True):
            k.WindowsAPI()
        rename = calls["NtSetInformationFile"]
        self.assertIs(rename.restype, ctypes.c_int32)
        self.assertEqual(rename.argtypes, [ctypes.c_void_p, ctypes.POINTER(k.IO_STATUS_BLOCK),
                                         ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32])

    def protocol(self):
        api = object.__new__(k.WindowsAPI)
        op = a.Operation(a.Cancellation(), monotonic_ns=lambda: 0, utc_now=lambda: UTC)
        op.claim()
        return api, op

    def test_no_replace_buffer_offsets_alignment_and_byte_length(self):
        api, op = self.protocol()
        def rename(handle, ios, data, size, information_class):
            info = ctypes.cast(data, ctypes.POINTER(k.FILE_RENAME_INFORMATION)).contents
            self.assertEqual((handle, info.RootDirectory, info.ReplaceIfExists, information_class),
                             (100, 200, 0, 10))
            self.assertEqual(ctypes.addressof(data) % 8, 0)
            name = k.bundle_name(ID, "complete").encode("utf-16-le")
            self.assertEqual(size, 20 + len(name))
            self.assertEqual(info.FileNameLength, len(name))
            self.assertEqual(ctypes.string_at(ctypes.addressof(data) + 20, len(name)), name)
            self.assertEqual(ctypes.string_at(ctypes.addressof(data) + 1, 7), b"\x00" * 7)
            return 0
        api.NtSetInformationFile = rename
        self.assertEqual(api.rename(100, 200, k.bundle_name(ID, "complete"), op), 0)

    def test_native_open_flags_partial_ownership_and_no_close_retry(self):
        for create in (False, True):
            for status in (0, -1073741790):
                api, op = self.protocol()
                closed = []
                api.CloseHandle = lambda handle: closed.append(handle) or 1
                def open_file(out, access, oa, ios, allocation, attributes, share,
                              disposition, options, ea, ea_length):
                    self.assertEqual(oa._obj.RootDirectory, 90)
                    self.assertEqual(oa._obj.Attributes, 0x1040)
                    self.assertEqual((access, share, disposition, options),
                                     (k.SOURCE_ACCESS, k.SHARE_RW, 2 if create else 1,
                                      0x200000 | 0x20 | 1))
                    self.assertEqual(len(op.ledger), 0)
                    out._obj.value = 100
                    ios._obj.Information = 2 if create else 1
                    return status
                api.NtCreateFile = open_file
                if status == 0:
                    api.open(90, "fixture", k.SOURCE_ACCESS, k.SHARE_RW, True, create, op)
                else:
                    with self.assertRaises(k.CustodyError):
                        api.open(90, "fixture", k.SOURCE_ACCESS, k.SHARE_RW, True, create, op)
                self.assertEqual(len(op.ledger), 1)
                op.close_all()
                op.close_all()
                self.assertEqual(closed, [100])

    def test_pending_waits_for_terminal_iosb_even_after_cancellation_deadline(self):
        api, op = self.protocol()
        calls, state = [], {}
        def rename(handle, ios, data, size, information_class):
            state["ios"], state["data"] = ios._obj, data
            return k.STATUS_PENDING
        def wait(handle, timeout):
            calls.append((handle, timeout))
            if len(calls) == 1:
                op.cancel.cancel()
                op.clock = lambda: a.TOTAL_NS + 1
                return 0x102
            state["ios"].Status = 0
            self.assertIsNotNone(state["data"])
            return 0
        api.NtSetInformationFile, api.WaitForSingleObject = rename, wait
        self.assertEqual(api.rename(100, 200, k.bundle_name(ID, "complete"), op), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("cancelled", op.codes)
        self.assertIn("deadline", op.codes)

    def test_interrupted_pending_observation_keeps_waiting_until_terminal(self):
        api, op = self.protocol()
        ios, calls = k.IO_STATUS_BLOCK(), []
        ios.Status = k.STATUS_PENDING
        def wait(handle, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise KeyboardInterrupt()
            ios.Status = 0
            return 0
        api.WaitForSingleObject = wait
        self.assertEqual(api._terminal(k.STATUS_PENDING, 100, ios, object(), op), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("publication_indeterminate", op.codes)
        self.assertFalse(op.quarantined)  # completion known, resources can close

    def test_pending_terminal_failure_and_unknown_wait_retention(self):
        api, op = self.protocol()
        ios = k.IO_STATUS_BLOCK()
        ios.Status = -1073741790
        api.WaitForSingleObject = lambda handle, timeout: 0
        self.assertEqual(k.classify_status(api._terminal(k.STATUS_PENDING, 100, ios, object(), op)), "failure")
        api, op = self.protocol()
        api.WaitForSingleObject = lambda handle, timeout: 0xFFFFFFFF
        closed = []
        op.own(100, lambda h: closed.append(h), native=True)
        before = len(k._PENDING)
        with self.assertRaises(k.CustodyError):
            api._terminal(k.STATUS_PENDING, 100, k.IO_STATUS_BLOCK(), object(), op)
        self.assertTrue(op.quarantined)
        self.assertEqual(len(k._PENDING), before + 1)
        op.close_all()
        self.assertEqual(op.cleanup, "unverified_pending_io")
        self.assertEqual(closed, [])

    def test_interrupted_call_retains_iosb_buffer_and_operation(self):
        api, op = self.protocol()
        api.NtSetInformationFile = lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(k.CustodyError):
            api.rename(100, 200, k.bundle_name(ID, "complete"), op)
        self.assertTrue(op.quarantined)
        self.assertIs(k._PENDING[-1][-1], op)


class NativeAcceptanceTests(unittest.TestCase):
    """Opt-in authored fixtures. Never provision ACLs or remove ambiguous bundles."""

    def setUp(self):
        if NATIVE_SPEC is None:
            self.skipTest("native Windows disposable-fixture execution requires separate approval")

    def test_native_publish_reopen_recover_and_collision(self):
        h = Harness()
        spec = k.RootSpec(**NATIVE_SPEC)
        h.store = a.InertDescriptor(lambda op: k.WindowsStore(op, spec))
        # A fresh UUID avoids reusing a prior fixture selector. No cleanup/deletion.
        result = a.capture_injected(CIK, exchange=h.exchange, store=h.store,
                                    cancellation=h.cancel)
        def recover():
            return a.recover_injected(CIK, result.capture_id,
                store=a.InertDescriptor(lambda op: k.WindowsStore(op, spec)),
                cancellation=a.Cancellation())
        before = recover()
        # Force the same target in a second operation; existing bytes must survive.
        h2 = Harness()
        h2.store = a.InertDescriptor(lambda op: k.WindowsStore(op, spec))
        with patch.object(a.uuid, "uuid4", return_value=result.capture_id):
            with self.assertRaises(a.CaptureFailure):
                a.capture_injected(CIK, exchange=h2.exchange, store=h2.store,
                                   cancellation=h2.cancel)
        after = recover()
        self.assertEqual(before, after)


class CountingResult(unittest.TextTestResult):
    subtests = 0

    def addSubTest(self, test, subtest, error):
        self.subtests += 1
        super().addSubTest(test, subtest, error)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CountingResult)
    if "--native-approved-root-spec" in sys.argv:
        index = sys.argv.index("--native-approved-root-spec")
        path = Path(sys.argv[index + 1])
        if not path.is_absolute():
            raise SystemExit("native fixture spec must have an explicitly approved absolute path")
        NATIVE_SPEC = json.loads(path.read_text(encoding="utf-8"))
        NATIVE_SPEC["components"] = tuple(NATIVE_SPEC["components"])
        del sys.argv[index:index + 2]
        # Only this explicit invocation runs the native acceptance class.
        program = unittest.main(defaultTest="NativeAcceptanceTests", testRunner=runner, exit=False)
    else:
        program = unittest.main(testRunner=runner, exit=False)
    print(f"Offline subtests executed: {program.result.subtests}")
    raise SystemExit(not program.result.wasSuccessful())
