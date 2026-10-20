"""Opt-in local observation only: no endpoint, logging, exporter, or I/O writer.

Private buffers may be inspected with an existing debugger only in a separately
authorized local run. Nothing here authorizes that run or approves model/data
provenance. The trusted bootstrap must supply its actual already-listening socket;
HTTP metadata is never proof of listener binding. No bootstrap is invoked here.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import os
from struct import Struct
from threading import Lock
from time import perf_counter_ns
from types import MappingProxyType


MAX_RECORDS = 8
MAX_ACTIVE = 2
MAX_EVENTS = 128
MAX_RETAINED_BYTES = 131072
CONTROL_RESERVATION = 8192
RECORD_RESERVATION = 15360
COLLECTION_NS = 300_000_000_000
REQUEST_NS = 35_000_000_000
CONFIG_KEY = "FINLENS_EVIDENCE_LATENCY"
LOCAL_KEY = "FINLENS_EVIDENCE_LATENCY_LOCAL_RUN"
CONFIG_VALUE = "bounded-local-v1"
LOCAL_VALUE = "approved-local-v1"

# Closed vocabulary: arbitrary strings/fields never enter a record. IDs fit uint16.
PHASES = MappingProxyType({name: i + 1 for i, name in enumerate((
    "http_request", "route_pipeline", "worker", "session_factory",
    "connection_acquire_composite", "transaction_setup", "version_pin_read",
    "company_read", "publication_state_read", "publication_read",
    "chunk_inventory_read", "chunk_body_read", "chunk_admission",
    "publication_eligibility", "publication_validation", "publication_digest",
    "retrieval_admission", "query_embedding", "model_cache_lookup",
    "encoder_loader_body", "encoder_dependency_import", "encoder_artifact_lookup",
    "model_constructor", "encoder_admission", "encoder_encode",
    "encoder_output_conversion", "query_vector_admission", "python_similarity",
    "python_hybrid_ranking", "context_construction", "session_cleanup",
    "http_final_body_send", "freshness_read", "session_close", "session_invalidation",
))})
START, END = 1, 2
OK, FAILED, CANCELLED, TERMINAL = 1, 2, 3, 4
# Raw event: relative ns, span ID, parent ID, phase ID, edge, outcome.
_EVENT = Struct("<QHHHBB")
# Aggregated span: ID, parent, phase, relative start, inclusive ns, exclusive ns,
# outcome, complete. Buffers are allocated BEFORE any transaction/aggregation.
_SUMMARY = Struct("<HHHQQQBB")
_INTERVAL = Struct("<QQ")
_current = ContextVar("finlens_latency_record", default=None)
_parent = ContextVar("finlens_latency_parent", default=0)
_permit = None
_collector = None
_admission_lock = Lock()
_ROUTES = MappingProxyType({
    ("GET", "/companies/AAPL/context"): (1, 1),
    ("GET", "/companies/COST/context"): (1, 2),
    ("GET", "/companies/AAPL/freshness"): (2, 1),
    ("GET", "/companies/COST/freshness"): (2, 2),
})


def _configured():
    return (os.environ.get(CONFIG_KEY) == CONFIG_VALUE
            and os.environ.get(LOCAL_KEY) == LOCAL_VALUE
            and os.environ.get("FINLENS_SERVER_PROFILE", "development") == "development"
            and not any(k.startswith(CONFIG_KEY) and k not in {CONFIG_KEY, LOCAL_KEY}
                        for k in os.environ))


def _binding(listener):
    """Inspect the actual socket, without opening a listener or connection."""
    import socket
    if not isinstance(listener, socket.socket):
        return None
    if (listener.family not in {socket.AF_INET, socket.AF_INET6}
            or socket.socket.getsockopt(listener, socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM
            or socket.socket.getsockopt(listener, socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1):
        return None
    address = socket.socket.getsockname(listener)
    if address[0] not in {"127.0.0.1", "::1"} or not 1 <= address[1] <= 65535:
        return None
    return address[0], address[1]


def _approve_local_run(*, authorized, listeners):
    """Trusted in-process bootstrap only; never called by startup or HTTP code.

    This implementation does not exercise real approval. A future approved owner
    must also establish the independent dataset/model/resource prerequisites.
    No raw listener address or socket is stored in diagnostic request records.
    """
    global _permit
    try:
        if (authorized is not True or not _configured()
                or type(listeners) is not tuple or len(listeners) != 1):
            return False
        from app.config import server_profile
        import weakref
        if server_profile().name != "development":
            return False
        binding = _binding(listeners[0])
        if binding is None:
            return False
        with _admission_lock:
            # One approval/collection per process; no implicit reset or renewed budget.
            if _permit is not None or _collector is not None:
                return False
            _permit = (os.getpid(), weakref.ref(listeners[0]), binding, perf_counter_ns())
        return True
    except BaseException:
        return False


def _verified_local_run(scope, now):
    if _permit is None:
        return False
    pid, reference, binding, approved_at = _permit
    listener = reference()
    return (pid == os.getpid() and 0 <= now - approved_at < COLLECTION_NS
            and listener is not None and _binding(listener) == binding
            and scope.get("server") == binding)


class _Record:
    __slots__ = ("correlation", "route", "issuer", "origin", "deadline", "lock",
                 "events", "summary", "scratch", "count", "next_span", "summary_count",
                 "sealed", "truncated", "expired", "internal_failure", "worker_done",
                 "body_sent", "status", "outcome", "missing", "coverage_complete",
                 "dispatch_ns", "response_processing_ns", "constructors", "aggregated")

    def __init__(self, route, issuer, origin, deadline):
        if (type(route) is not int or route not in {1, 2}
                or type(issuer) is not int or issuer not in {1, 2}
                or type(origin) is not int or type(deadline) is not int
                or not 0 <= origin < deadline <= (1 << 63) - 1):
            raise ValueError("Invalid diagnostic record admission.")
        self.correlation = os.urandom(8).hex()  # exactly 16 ASCII chars; admission only
        self.route, self.issuer = route, issuer  # closed numeric scope, never raw paths
        self.origin, self.deadline = origin, deadline
        self.lock = Lock()
        self.events = bytearray(MAX_EVENTS * _EVENT.size)
        self.summary = bytearray(MAX_EVENTS * _SUMMARY.size)
        self.scratch = bytearray(MAX_EVENTS * _INTERVAL.size)
        self.count = self.next_span = self.summary_count = 0
        self.sealed = self.truncated = self.expired = self.internal_failure = False
        self.worker_done = self.body_sent = self.coverage_complete = self.aggregated = False
        self.status = self.outcome = self.missing = 0
        self.dispatch_ns = self.response_processing_ns = self.constructors = 0

    def _append(self, timestamp, span_id, parent, phase, edge, outcome):
        # Called under this request's lock. No formatting, callbacks or aggregation.
        if self.sealed or self.truncated or self.internal_failure:
            return False
        if (type(timestamp) is not int or type(span_id) is not int
                or type(parent) is not int or type(phase) is not int
                or not 1 <= span_id <= MAX_EVENTS or not 0 <= parent <= MAX_EVENTS
                or not 1 <= phase <= len(PHASES) or type(edge) is not int or type(outcome) is not int
                or edge not in {START, END}
                or outcome not in {0, OK, FAILED, CANCELLED, TERMINAL}):
            self.internal_failure = True
            return False
        if not self.origin <= timestamp < self.deadline:
            self.expired = self.truncated = True
            return False
        if self.count >= MAX_EVENTS:
            self.truncated = True
            return False
        _EVENT.pack_into(self.events, self.count * _EVENT.size, timestamp - self.origin,
                         span_id, parent, phase, edge, outcome)
        self.count += 1
        return True

    def begin(self, phase, parent):
        with self.lock:
            if self.sealed or self.next_span >= MAX_EVENTS:
                return 0
            span_id = self.next_span + 1
            if not self._append(perf_counter_ns(), span_id, parent, phase, START, 0):
                return 0
            self.next_span = span_id
            return span_id

    def end(self, span_id, parent, phase, outcome):
        with self.lock:
            self._append(perf_counter_ns(), span_id, parent, phase, END, outcome)


def _mask(names):
    result = 0
    for name in names:
        result |= 1 << PHASES[name]
    return result


_COMMON_REQUIRED = _mask(("http_request", "route_pipeline", "worker", "session_factory",
                          "connection_acquire_composite", "transaction_setup",
                          "version_pin_read", "session_cleanup", "session_close", "http_final_body_send"))
_CONTEXT_REQUIRED = _mask(("company_read", "publication_state_read", "publication_read",
                           "chunk_inventory_read", "chunk_body_read", "chunk_admission",
                           "publication_eligibility", "publication_validation", "publication_digest",
                           "retrieval_admission", "query_embedding", "model_cache_lookup",
                           "encoder_encode", "encoder_output_conversion", "query_vector_admission",
                           "python_similarity", "python_hybrid_ranking", "context_construction"))
_LOAD_REQUIRED = _mask(("encoder_loader_body", "encoder_dependency_import",
                        "model_constructor", "encoder_admission"))


def _aggregate(record):
    """Bounded post-cleanup work only, under the record lock after sealing."""
    successful = 0
    pipeline_start = pipeline_end = worker_start = worker_end = None
    for i in range(record.count):
        start, span_id, parent, phase, edge, _ = _EVENT.unpack_from(record.events, i * _EVENT.size)
        if edge != START:
            continue
        end, outcome, complete = start, 0, 0
        if phase == PHASES["model_constructor"]:
            record.constructors += 1
        for j in range(i + 1, record.count):
            stop, other, other_parent, other_phase, other_edge, other_outcome = _EVENT.unpack_from(record.events, j * _EVENT.size)
            if (other, other_parent, other_phase, other_edge) == (span_id, parent, phase, END):
                end, outcome, complete = stop, other_outcome, 1
                break
        duration = max(0, end - start)
        _SUMMARY.pack_into(record.summary, record.summary_count * _SUMMARY.size,
                           span_id, parent, phase, start, duration, duration, outcome, complete)
        record.summary_count += 1
        if complete and outcome == OK:
            successful |= 1 << phase
        if phase == PHASES["route_pipeline"]:
            pipeline_start, pipeline_end = start, end if complete else None
        if phase == PHASES["worker"]:
            worker_start, worker_end = start, end if complete else None

    # Union direct-child intervals, clipped to each parent. Overlap is subtracted
    # once. Fixed scratch storage prevents an allocation burst at aggregation.
    for i in range(record.summary_count):
        span_id, parent, phase, start, duration, _, outcome, complete = _SUMMARY.unpack_from(record.summary, i * _SUMMARY.size)
        if not complete:
            continue
        size = 0
        for j in range(record.summary_count):
            _, child_parent, _, child_start, child_duration, _, _, child_complete = _SUMMARY.unpack_from(record.summary, j * _SUMMARY.size)
            if child_parent != span_id or not child_complete:
                continue
            a, b = max(start, child_start), min(start + duration, child_start + child_duration)
            if b <= a:
                continue
            k = size
            while k and _INTERVAL.unpack_from(record.scratch, (k - 1) * _INTERVAL.size)[0] > a:
                previous = _INTERVAL.unpack_from(record.scratch, (k - 1) * _INTERVAL.size)
                _INTERVAL.pack_into(record.scratch, k * _INTERVAL.size, *previous)
                k -= 1
            _INTERVAL.pack_into(record.scratch, k * _INTERVAL.size, a, b)
            size += 1
        covered, cursor = 0, start
        for j in range(size):
            a, b = _INTERVAL.unpack_from(record.scratch, j * _INTERVAL.size)
            covered += max(0, b - max(cursor, a))
            cursor = max(cursor, b)
        _SUMMARY.pack_into(record.summary, i * _SUMMARY.size, span_id, parent, phase,
                           start, duration, duration - covered, outcome, complete)

    if pipeline_start is not None and worker_start is not None:
        record.dispatch_ns = max(0, worker_start - pipeline_start)
    if pipeline_end is not None and worker_end is not None:
        record.response_processing_ns = max(0, pipeline_end - worker_end)
    required = _COMMON_REQUIRED | (_CONTEXT_REQUIRED if record.route == 1 else _mask(("freshness_read",)))
    if record.constructors or successful & (1 << PHASES["encoder_loader_body"]):
        required |= _LOAD_REQUIRED
    record.missing = required & ~successful
    record.coverage_complete = (record.missing == 0 and record.worker_done and record.body_sent
                                and record.outcome == OK and 200 <= record.status < 300
                                and not (record.truncated or record.expired or record.internal_failure))
    record.aggregated = True


class _Collector:
    __slots__ = ("origin", "deadline", "records", "active", "reserved")

    def __init__(self, origin, deadline):
        self.origin, self.deadline = origin, deadline
        self.records = []  # admission lock; at most eight slotted records, never replaced
        self.active = 0
        self.reserved = CONTROL_RESERVATION

    def admit(self, route, issuer, now):
        if (not self.origin <= now < self.deadline or len(self.records) >= MAX_RECORDS
                or self.active >= MAX_ACTIVE
                or self.reserved + RECORD_RESERVATION > MAX_RETAINED_BYTES):
            return None
        record = _Record(route, issuer, now, min(self.deadline, now + REQUEST_NS))
        # Charge conservative total object reservations, not just payload lengths.
        # Numeric fields may grow to 64 bits. Validate this interpreter's object
        # overhead before retention/aggregation, without traversing arbitrary data.
        from sys import getsizeof
        footprint = getsizeof(record)
        for field in _Record.__slots__:
            value = getattr(record, field)
            footprint += 40 if type(value) in {int, bool} else getsizeof(value)
        if footprint > RECORD_RESERVATION:
            return None
        self.records.append(record)
        self.active += 1
        self.reserved += RECORD_RESERVATION
        return record


def _admit(scope, profile_name):
    global _collector
    try:
        if (profile_name != "development" or scope.get("type") != "http"
                or not _configured()):
            return None
        selected = _ROUTES.get((scope.get("method"), scope.get("path")))
        if selected is None:
            return None
        now = perf_counter_ns()
        with _admission_lock:
            if not _verified_local_run(scope, now):
                return None
            if _collector is None:
                _collector = _Collector(now, min(now + COLLECTION_NS, _permit[3] + COLLECTION_NS))
            return _collector.admit(*selected, now)
    except BaseException:
        return None


def _flag(record, name, value=True):
    try:
        if record is not None:
            with record.lock:
                if not record.sealed:
                    now = perf_counter_ns()
                    if not record.origin <= now < record.deadline:
                        record.expired = record.truncated = True
                        return
                    if name in {"worker_done", "body_sent"} and type(value) is bool:
                        setattr(record, name, value)
                    elif name == "status" and type(value) is int and 100 <= value <= 599:
                        record.status = value
    except BaseException:
        pass


@contextmanager
def span(phase):
    """Record numeric boundaries only. Never consume/suppress a business exception."""
    record = token = None
    span_id = parent = phase_id = 0
    try:
        record = _current.get()
        if record is not None and type(phase) is str and len(phase) <= 48:
            phase_id = PHASES.get(phase, 0)
            parent = _parent.get()
            if phase_id and type(parent) is int and 0 <= parent <= MAX_EVENTS:
                span_id = record.begin(phase_id, parent)
                if span_id:
                    token = _parent.set(span_id)
            else:
                _fail_record(record)
        elif record is not None:
            _fail_record(record)
    except BaseException:
        _fail_record(record)
    outcome = OK
    try:
        yield
    except BaseException:
        outcome = FAILED
        raise
    finally:
        try:
            if span_id:
                record.end(span_id, parent, phase_id, outcome)
        except BaseException:
            _fail_record(record)
        finally:
            if token is not None:
                try:
                    _parent.reset(token)
                except BaseException:
                    _fail_record(record)


def _fail_record(record):
    try:
        if record is not None:
            with record.lock:
                if not record.sealed:
                    record.internal_failure = True
    except BaseException:
        pass


def worker(function):
    @wraps(function)
    def observed(*args, **kwargs):
        record = _current.get()
        try:
            with span("worker"):
                return function(*args, **kwargs)
        finally:
            _flag(record, "worker_done")
    return observed


def route(function):
    @wraps(function)
    async def observed(*args, **kwargs):
        with span("route_pipeline"):
            return await function(*args, **kwargs)
    return observed


def _finish(record, outcome):
    try:
        with _admission_lock:
            with record.lock:
                if record.sealed:
                    return
                record.sealed = True  # late copied contexts cannot mutate this record
                record.outcome = outcome
                if (_collector is not None
                        and any(item is record for item in _collector.records)):
                    _collector.active -= 1
        with record.lock:
            if perf_counter_ns() >= record.deadline:
                record.expired = True
            # No aggregation while an abandoned sync worker may own a transaction.
            if record.worker_done:
                _aggregate(record)
    except BaseException:
        # A failed aggregation must never present partially computed full coverage.
        try:
            record.coverage_complete = False
            record.internal_failure = record.sealed = True
        except BaseException:
            pass


class EvidenceLatencyMiddleware:
    """ASGI observer inside release admission; never modifies messages or receive."""
    def __init__(self, app, profile):
        self.app, self.profile = app, profile

    async def __call__(self, scope, receive, send):
        profile_name = None
        try:
            if _configured():
                profile_name = self.profile().name
        except BaseException:
            pass
        record = _admit(scope, profile_name)
        if record is None:
            return await self.app(scope, receive, send)
        token = parent_token = None
        try:
            token = _current.set(record)
            parent_token = _parent.set(0)
        except BaseException:
            _fail_record(record)
        outcome = OK

        async def observed_send(message):
            if message.get("type") == "http.response.start":
                _flag(record, "status", message.get("status"))
            if message.get("type") == "http.response.body" and not message.get("more_body", False):
                with span("http_final_body_send"):
                    await send(message)
                _flag(record, "body_sent")  # server send completed, NOT client receipt
            else:
                await send(message)

        try:
            with span("http_request"):
                await self.app(scope, receive, observed_send)
        except BaseException as exc:
            from asyncio import CancelledError
            outcome = CANCELLED if isinstance(exc, CancelledError) else FAILED if isinstance(exc, Exception) else TERMINAL
            raise
        finally:
            _finish(record, outcome)
            if parent_token is not None:
                try:
                    _parent.reset(parent_token)
                except BaseException:
                    pass
            if token is not None:
                try:
                    _current.reset(token)
                except BaseException:
                    pass
