"""Dormant single-CIK transport. No callable live acquisition is commissioned.

Injected descriptors/callbacks are trusted offline test machinery, not an in-process
security boundary. All receipts permanently say offline_injected. Handoff records a
logical commit, never proof that a caller received or processed a result.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import json
import re
import threading
import time
import uuid

from app import sec_identity_source as source
from app import sec_submissions_custody as custody


ACQUISITION_REVISION = "fl-ucr-01c1.acquisition.v1"
POLICY_REVISION = "fl-ucr-01c1.policy.v1"
SCHEMA = "fl-ucr-01c1.receipt.v1"
HOST = "data.sec.gov"
MAX_BODY = 4_194_304
BLOCK = 65_536
MAX_HEADERS = 64
MAX_HEADER_BYTES = MAX_RECEIPT = 16_384
WORK_NS = 28_000_000_000
TOTAL_NS = 30_000_000_000
PHASES = ("operation_start", "headers_complete", "body_complete", "receipt_created")
RETAINED = frozenset(("content-length", "content-type", "content-encoding",
                      "date", "etag", "last-modified"))
FORBIDDEN = frozenset(("transfer-encoding", "trailer", "content-range", "location"))
CRITICAL = RETAINED | FORBIDDEN
TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_HANDOFF = object()


def require(condition, code):
    if not condition:
        raise custody.CustodyError(code)


def canonical_cik(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{10}", value) is not None
            and value != "0000000000", "expected_cik")
    return value


def capture_id(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        value) is not None, "capture_id")
    return value


def url_for(cik):
    return f"https://{HOST}/submissions/CIK{canonical_cik(cik)}.json"


class Cancellation:
    """Replaces Event: non-clearable, one operation, same lock as final handoff.

    cancel() returns 'accepted', 'already_cancelled', or 'too_late'. No external
    independently writable Event is accepted. Reusing this token is rejected.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._decision = {}
        self._claimed = False

    @property
    def _cancelled(self):
        decision = self._decision.get("terminal")
        return decision is not None and decision is not _HANDOFF

    @property
    def _handed_off(self):
        return self._decision.get("terminal") is _HANDOFF

    def cancel(self):
        request = object()
        with self._lock:
            # The builtin dict operation on an exact string key is the shared
            # linearization point, including same-thread RLock reentry. The
            # winning decision is never overwritten. No callbacks run here.
            decision = self._decision.setdefault("terminal", request)
            if decision is _HANDOFF:
                return "too_late"
            return "accepted" if decision is request else "already_cancelled"


@dataclass(frozen=True)
class Outcome:
    publication: str
    stored_integrity: str
    cleanup: str
    delivery: str


class CaptureFailure(RuntimeError):
    """Sanitized state and optional recovery selector; no publication/authority proof."""

    def __init__(self, codes, outcome, *, capture_id=None):
        self.codes, self.code, self.outcome = tuple(codes), codes[0], outcome
        self.capture_id = capture_id
        super().__init__(self.code)


class Operation:
    def __init__(self, cancellation, *, monotonic_ns=time.monotonic_ns,
                 utc_now=lambda: datetime.now(timezone.utc), deferred=False):
        require(type(cancellation) is Cancellation, "cancellation_type")
        self.cancel = cancellation
        self.clock, self.utc_now = monotonic_ns, utc_now
        self.start = self.last = self.start_utc = None
        self.ledger, self.codes = [], []
        self.publication, self.integrity = "not_published", "unverified"
        self.cleanup, self.delivery = "pending", "withheld"
        self.quarantined = False
        self.claimed = False
        self.capture_id = None
        if not deferred:
            self.begin()

    def begin(self):
        self.start = self.last = self.clock()
        require(type(self.start) is int, "monotonic_clock")
        self.start_utc = self.utc_now()
        require(type(self.start_utc) is datetime and self.start_utc.tzinfo is timezone.utc,
                "utc_clock")

    def claim(self):
        with self.cancel._lock:
            require(not self.cancel._claimed, "cancellation_consumed")
            self.cancel._claimed = self.claimed = True

    def elapsed(self):
        require(self.start is not None, "monotonic_clock")
        now = self.clock()
        require(type(now) is int and now >= self.last, "monotonic_regression")
        self.last = now
        return now - self.start

    def checkpoint(self, *, closing=False):
        elapsed = self.elapsed()
        expired = elapsed > TOTAL_NS if closing else elapsed >= WORK_NS
        if expired:
            self.note(custody.CustodyError("deadline"))
        with self.cancel._lock:
            require(not self.cancel._cancelled, "cancelled")
        require(not expired, "deadline")

    def call(self, function, *args):
        self.checkpoint()
        result = function(*args)
        self.checkpoint()
        return result

    def own(self, resource, closer, *, native=False):
        """Register immediately, before any checkpoint; token is closed once only."""
        token = [resource, closer, False, native]
        self.ledger.append(token)
        return token

    def note(self, error):
        code = error.code if isinstance(error, (custody.CustodyError,
                                                 source.SecIdentitySourceError)) else "io_failure"
        if code not in self.codes:
            self.codes.append(code)

    def close_one(self, token):
        if token[2]:
            return
        if self.quarantined and token[3]:
            self.note(custody.CustodyError("cleanup_unverified"))
            return
        # Mark before calling: a failed close may already have released a handle.
        token[2] = True
        for is_close, action in ((False, lambda: self.checkpoint(closing=True)),
                                 (True, lambda: token[1](token[0])),
                                 (False, lambda: self.checkpoint(closing=True))):
            try:
                action()
            except BaseException as error:
                self.note(error)
                if is_close:
                    self.note(custody.CustodyError("cleanup_unverified"))

    def close_all(self):
        if self.quarantined:
            self.note(custody.CustodyError("cleanup_unverified"))
        for token in reversed(self.ledger):
            self.close_one(token)
        self.cleanup = ("unverified_pending_io" if self.quarantined else
                        "unverified" if "cleanup_unverified" in self.codes else "closed")

    def outcome(self):
        return Outcome(self.publication, self.integrity, self.cleanup, self.delivery)

    def handoff(self, result):
        # Sample the cooperative deadline before taking the terminal transition
        # lock: injected clocks/callbacks must not execute inside that transition.
        try:
            require(self.elapsed() <= TOTAL_NS, "deadline")
        except BaseException as error:
            self.note(error)
        with self.cancel._lock:
            if self.cancel._cancelled:
                self.note(custody.CustodyError("cancelled"))
            if not self.codes:
                require(self.cleanup == "closed" and self.claimed, "handoff_state")
                decision = self.cancel._decision.setdefault("terminal", _HANDOFF)
                if decision is _HANDOFF:
                    self.delivery = "logical_handoff"
                    return result
                self.note(custody.CustodyError("cancelled"))
            priority = {"publication_indeterminate": 0, "integrity_failure": 0,
                        "cleanup_unverified": 1, "cancelled": 2, "deadline": 3}
            ordered = sorted(self.codes, key=lambda c: priority.get(c, 4))
            raise CaptureFailure(ordered, self.outcome(), capture_id=self.capture_id) from None


class InertDescriptor:
    """Single-use ownership transfer, replacing an already-open store interface.

    An opener receives Operation and must register every partial resource there
    immediately. The returned resource is then owned by this descriptor. Opening
    occurs inside the budget. Rejected already-open inputs are still closed.
    Trusted injected openers must never perform real network or production writes.
    """

    def __init__(self, opener):
        self.opener = opener
        self.state, self.resource = "inert", None

    def open(self, op):
        require(self.state == "inert" and self.resource is None, "descriptor_not_inert")
        self.state = "opening"
        self.resource = self.opener(op)
        self.state = "opened"
        return self.resource

    def close(self):
        resource, self.resource = self.resource, None
        self.state = "consumed"
        if resource is not None:
            resource.close()


def _validate_pairs(pairs):
    require(len(pairs) <= MAX_HEADERS, "header_count")
    seen = set()
    for name, value in pairs:
        require(type(name) is str and type(value) is str, "header_type")
        require(1 <= len(name) <= 128 and TOKEN.fullmatch(name.encode("ascii"))
                is not None, "header_name")
        require(len(value) <= 2048 and all(32 <= ord(c) <= 126 for c in value),
                "header_value")
        lower = name.lower()
        require(lower not in seen or lower not in CRITICAL, "duplicate_critical_header")
        seen.add(lower)
        require(lower not in FORBIDDEN, "forbidden_header")
    headers = {name.lower(): value for name, value in pairs}
    length = headers.get("content-length", "")
    require(re.fullmatch(r"[1-9][0-9]{0,6}", length) is not None
            and int(length) <= MAX_BODY, "content_length")
    require(headers.get("content-encoding", "identity") == "identity", "content_encoding")
    require(headers.get("content-type", "application/json") in
            ("application/json", "application/json; charset=utf-8"), "content_type")
    return int(length)


class _RawGate:
    """Bound allocations before readline; preserve the original buffered fp."""

    def __init__(self, fp, op):
        self.fp, self.op = fp, op
        self.total, self.pairs = 0, []
        self.status_seen = self.complete = False

    def readline(self, limit=-1):
        require(not self.complete, "header_after_terminator")
        require(MAX_HEADER_BYTES - self.total >= 2, "header_bytes_limit")
        def piece(cap, used=0, *, detect=True):
            cap = min(cap, MAX_HEADER_BYTES - self.total - used)
            require(cap >= 0, "header_bytes_limit")
            request = min(cap + int(detect), limit) if limit >= 0 else cap + int(detect)
            self.before_read()
            data = self.op.call(self.fp.readline, request)
            require(type(data) is bytes and len(data) <= cap, "header_bytes_limit")
            return data
        if not self.status_seen:
            line = piece(1024)
        else:
            # Discover the name/colon before allocating space for its value. The
            # prefix is at most 128 name bytes, ':' and one detecting byte.
            line = piece(130, detect=False)
            if not line.endswith(b"\n"):
                require(b":" in line, "header_name")
                name = line.split(b":", 1)[0]
                require(1 <= len(name) <= 128 and TOKEN.fullmatch(name) is not None,
                        "header_name")
                line += piece(len(name) + 1 + 2048 + 2 - len(line), len(line))
        self.total += len(line)
        require(line.endswith(b"\r\n"), "header_crlf")
        text = line[:-2]
        require(all(32 <= c <= 126 for c in text), "header_character")
        if not self.status_seen:
            require(re.fullmatch(rb"HTTP/1\.1 200 [\x20-\x7e]*", text) is not None,
                    "http_status_line")
            self.status_seen = True
        elif not text:
            self.complete = True
        else:
            require(len(self.pairs) < MAX_HEADERS, "header_count")
            require(b":" in text, "header_separator")
            name, value = text.split(b":", 1)
            require(1 <= len(name) <= 128 and TOKEN.fullmatch(name) is not None,
                    "header_name")
            require(len(value) <= 2048, "header_value")
            self.pairs.append((name.decode("ascii"), value.strip(b" ").decode("ascii")))
        return line

    def close(self):
        self.fp.close()

    def flush(self):
        self.fp.flush()


class StrictHTTPResponse(http.client.HTTPResponse):
    """Application body methods cannot run until raw and tolerant parsers agree.

    Transport buffering may read ahead. No body bytes reach capture, parser or
    custody before accepted=True. Switching retains the same buffered object.
    """

    def __init__(self, sock, *, operation, **kwargs):
        super().__init__(sock, **kwargs)
        self._transport_socket = sock
        self.operation, self.accepted = operation, False
        self.gate = _RawGate(self.fp, operation)
        self.gate.before_read = self._wait_budget
        self.fp = self.gate

    def _wait_budget(self):
        self.operation.checkpoint()
        remaining = (WORK_NS - self.operation.elapsed()) / 1e9
        require(remaining > 0, "deadline")
        self._transport_socket.settimeout(min(5, remaining))

    def begin(self):
        super().begin()
        require(self.gate.complete and not self.headers.defects, "http_parser_defect")
        parsed = [(n.lower(), v) for n, v in self.headers.raw_items()]
        raw = [(n.lower(), v) for n, v in self.gate.pairs]
        require(parsed == raw, "http_parser_disagreement")
        self.declared_length = _validate_pairs(self.gate.pairs)
        require(self.status == 200 and self.version == 11 and not self.chunked
                and self.length == self.declared_length, "http_framing")
        self.retained = tuple(sorted((n.lower(), v) for n, v in self.gate.pairs
                                     if n.lower() in RETAINED))
        self.fp = self.gate.fp
        self.accepted = True

    def read(self, amt=None):
        require(self.accepted and type(amt) is int and 0 < amt <= BLOCK, "body_read_gate")
        self._wait_budget()
        return super().read(amt)

    def readinto(self, b):
        require(self.accepted and len(b) <= BLOCK, "body_read_gate")
        self._wait_budget()
        return super().readinto(b)

    def read1(self, n=-1):
        require(self.accepted and 0 < n <= BLOCK, "body_read_gate")
        self._wait_budget()
        return super().read1(n)

    def readline(self, limit=-1):
        require(self.accepted and 0 < limit <= BLOCK, "body_read_gate")
        self._wait_budget()
        return super().readline(limit)

    def peek(self, n=-1):
        raise custody.CustodyError("body_read_gate")


class _SecHTTPSConnection(http.client.HTTPSConnection):
    """Uncommissioned stdlib TLS transport; no public/default factory uses this."""

    def __init__(self, operation):
        self.operation = operation
        super().__init__(HOST, timeout=min(5, (WORK_NS - operation.elapsed()) / 1e9))
        self.response_class = self._make_response

    def _make_response(self, sock, **kwargs):
        response = StrictHTTPResponse(sock, operation=self.operation, **kwargs)
        self._response_token = self.operation.own(response, lambda r: r.close())
        return response


class HTTPSExchange:
    """Explicit injected connection factory only. One GET; no retry/fallback.

    A fake factory is required by offline callers. The dormant stdlib connection
    above is never selected implicitly. DNS may try several addresses if transport
    is separately commissioned later; no physical TCP-attempt claim is made.
    """

    def __init__(self, operation, cik, user_agent, connection_factory):
        require(type(user_agent) is str and 1 <= len(user_agent) <= 256
                and all(32 <= ord(c) <= 126 for c in user_agent), "user_agent")
        self.op, self.cik = operation, canonical_cik(cik)
        self.connection = connection_factory(operation)
        self.connection_token = operation.own(self.connection, lambda c: c.close())
        self.user_agent, self.response = user_agent, None
        self.started = False

    def headers(self):
        require(not self.started, "exchange_consumed")
        self.started = True
        self.connection.timeout = min(5, max(0.001, (WORK_NS - self.op.elapsed()) / 1e9))
        self.op.call(self.connection.request, "GET", f"/submissions/CIK{self.cik}.json",
                     None, {"User-Agent": self.user_agent, "Accept": "application/json",
                            "Accept-Encoding": "identity", "Connection": "close"})
        # getresponse may raise inside begin(); stdlib closes that response itself.
        self.op.checkpoint()
        self.response = self.connection.getresponse()
        existing = getattr(self.connection, "_response_token", None)
        self.response_token = existing if existing is not None else self.op.own(
            self.response, lambda r: r.close())
        self.op.checkpoint()
        require(isinstance(self.response, StrictHTTPResponse) and self.response.accepted,
                "raw_response_required")
        return self.response.declared_length, self.response.retained

    def read(self, count):
        return self.response.read(count)

    def close(self):
        # Also closes rejected pre-opened resources using their original ledger.
        for name in ("response_token", "connection_token"):
            token = getattr(self, name, None)
            if token is not None:
                self.op.close_one(token)
        require("cleanup_unverified" not in self.op.codes, "cleanup_unverified")


def _canonical(value):
    """ASCII JSON escaping (including non-ASCII), sorted keys, no BOM/newline."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "receipt_duplicate_key")
        value[key] = item
    return value


def _timestamp(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value)
        is not None, "receipt_timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        raise custody.CustodyError("receipt_timestamp") from None


def _stamp(op):
    now = op.utc_now()
    require(type(now) is datetime and now.tzinfo is timezone.utc, "utc_clock")
    return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def versions():
    return {"acquisition": ACQUISITION_REVISION, "custody": custody.CUSTODY_REVISION,
            "parser": source.PARSER_REVISION, "policy": POLICY_REVISION}


def verify_receipt(data, body, *, expected_id, expected_cik):
    require(type(data) is bytes and 0 < len(data) <= MAX_RECEIPT, "receipt_size")
    require(type(body) is bytes and 1 <= len(body) <= MAX_BODY, "body_size")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique,
                           parse_float=lambda _: require(False, "receipt_number"),
                           parse_constant=lambda _: require(False, "receipt_nonfinite"))
    except (UnicodeError, ValueError, RecursionError):
        raise custody.CustodyError("receipt_json") from None
    require(type(value) is dict and set(value) == {
        "schema", "capture_id", "cik", "url", "origin", "source_identity", "http_status",
        "versions", "timestamps", "offsets_ns", "response_headers", "byte_count",
        "body_sha256"}, "receipt_keys")
    require(data == _canonical(value), "receipt_noncanonical")
    require(value["schema"] == SCHEMA and type(value["schema"]) is str, "receipt_schema")
    require(value["capture_id"] == capture_id(expected_id), "receipt_capture_id")
    require(value["cik"] == canonical_cik(expected_cik), "receipt_cik")
    require(value["url"] == url_for(expected_cik), "receipt_url")
    require(value["origin"] == "offline_injected", "receipt_origin")
    require(value["source_identity"] == source.SOURCE_IDENTITY, "receipt_source")
    require(type(value["http_status"]) is int and value["http_status"] == 200, "receipt_status")
    require(type(value["versions"]) is dict and value["versions"] == versions(),
            "receipt_versions")
    for field in ("timestamps", "offsets_ns"):
        require(type(value[field]) is dict and set(value[field]) == set(PHASES), "receipt_phases")
    times = [_timestamp(value["timestamps"][p]) for p in PHASES]
    require(times == sorted(times), "wall_clock_regression")
    offsets = [value["offsets_ns"][p] for p in PHASES]
    require(all(type(n) is int and 0 <= n <= WORK_NS for n in offsets)
            and offsets[0] == 0 and offsets == sorted(offsets), "receipt_offsets")
    headers = value["response_headers"]
    require(type(headers) is list and len(headers) <= len(RETAINED), "receipt_headers")
    require(all(type(p) is list and len(p) == 2 and all(type(v) is str for v in p)
                and p[0] in RETAINED for p in headers), "receipt_headers")
    require(headers == sorted(headers), "receipt_headers")
    require(_validate_pairs(headers) == len(body), "receipt_length")
    require(type(value["byte_count"]) is int and value["byte_count"] == len(body), "receipt_count")
    digest = value["body_sha256"]
    require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            and digest == hashlib.sha256(body).hexdigest(), "receipt_digest")
    source.parse_sec_submissions(body, expected_cik=expected_cik)
    return value


@dataclass(frozen=True)
class CaptureReference:
    capture_id: str
    cik: str
    body_sha256: str
    receipt_sha256: str
    storage_state: str
    origin: str = "offline_injected"
    verification_status: str = "unverified"


def _run(cik, descriptors, cancellation, action, monotonic_ns, utc_now):
    valid_cancel = type(cancellation) is Cancellation
    op = Operation(cancellation if valid_cancel else Cancellation(),
                   monotonic_ns=monotonic_ns, utc_now=utc_now, deferred=True)
    # Ownership transfers before validation/cancellation checks, even on rejection.
    unique = {id(d): d for d in descriptors}
    for descriptor in unique.values():
        op.own(descriptor, lambda d: d.close())
    result = None
    try:
        op.begin()
        require(valid_cancel, "cancellation_type")
        require(len(unique) == len(descriptors), "descriptor_reused")
        op.claim()
        canonical_cik(cik)
        for descriptor in descriptors:
            require(isinstance(descriptor, InertDescriptor)
                    and descriptor.state == "inert" and descriptor.resource is None,
                    "descriptor_not_inert")
        op.checkpoint()
        result = action(op)
    except BaseException as error:
        op.note(error)
    finally:
        op.close_all()
    return op.handoff(result)


def capture_injected(cik, *, exchange, store, cancellation, monotonic_ns=time.monotonic_ns,
                     utc_now=lambda: datetime.now(timezone.utc)):
    """Own single-use inert descriptors; all open work belongs to this budget.

    Never chooses network/config/storage factories. No automatic recovery follows
    failure. Stored integrity, publication, cleanup and delivery remain independent.
    """
    def action(op):
        identifier = str(uuid.uuid4())
        op.capture_id = capture_id(identifier)
        ex = op.call(exchange.open, op)
        require(type(ex) is HTTPSExchange and not ex.started and ex.op is op and ex.cik == cik,
                "exchange_not_inert")
        target = op.call(store.open, op)
        require(type(target) is custody.WindowsStore and target.op is op, "store_type")
        count, headers = op.call(ex.headers)
        require(type(count) is int and 1 <= count <= MAX_BODY
                and _validate_pairs(headers) == count, "content_length")
        times = {"operation_start": op.start_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                 "headers_complete": _stamp(op)}
        offsets = {"operation_start": 0, "headers_complete": op.elapsed()}
        body = bytearray()
        while len(body) < count:
            requested = min(BLOCK, count - len(body))
            part = op.call(ex.read, requested)
            require(type(part) is bytes and 0 < len(part) <= requested, "body_read")
            body.extend(part)
        body = bytes(body)
        op.checkpoint()
        source.parse_sec_submissions(body, expected_cik=cik)
        op.checkpoint()
        op.integrity = "BODY_VERIFIED"
        times["body_complete"], offsets["body_complete"] = _stamp(op), op.elapsed()
        times["receipt_created"], offsets["receipt_created"] = _stamp(op), op.elapsed()
        receipt = _canonical({"schema": SCHEMA, "capture_id": identifier, "cik": cik,
                              "url": url_for(cik), "origin": "offline_injected",
                              "source_identity": source.SOURCE_IDENTITY, "http_status": 200,
                              "versions": versions(), "timestamps": times, "offsets_ns": offsets,
                              "response_headers": sorted(headers), "byte_count": len(body),
                              "body_sha256": hashlib.sha256(body).hexdigest()})
        def verify(b, r):
            return verify_receipt(r, b, expected_id=identifier, expected_cik=cik)
        op.call(verify, body, receipt)
        target.publish(identifier, body, receipt, verify)
        return CaptureReference(identifier, cik, hashlib.sha256(body).hexdigest(),
                                hashlib.sha256(receipt).hexdigest(), "PUBLISHED_VERIFIED")
    return _run(cik, (exchange, store), cancellation, action, monotonic_ns, utc_now)


def recover_injected(cik, identifier, *, store, cancellation,
                     monotonic_ns=time.monotonic_ns,
                     utc_now=lambda: datetime.now(timezone.utc)):
    """Separate explicitly selected local verification; never refetch or promote."""
    def action(op):
        op.capture_id = capture_id(identifier)
        target = op.call(store.open, op)
        require(type(target) is custody.WindowsStore and target.op is op, "store_type")
        def verify(b, r):
            return verify_receipt(r, b, expected_id=identifier, expected_cik=cik)
        body, receipt = target.recover(identifier, verify)
        op.integrity = "RECOVERED_VERIFIED_LOCAL"
        return CaptureReference(identifier, cik, hashlib.sha256(body).hexdigest(),
                                hashlib.sha256(receipt).hexdigest(), "RECOVERED_VERIFIED_LOCAL")
    return _run(cik, (store,), cancellation, action, monotonic_ns, utc_now)


def acquire_submissions(*args, **kwargs):
    """Permanent C1 live boundary: no configuration/factory evaluation precedes it."""
    raise custody.CustodyError("live_acquisition_disabled")
