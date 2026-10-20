"""Synthetic only. Run with dotenv disabled and an explicit fixture-only URL.

No listener, PostgreSQL connection, real encoder import, approval or extraction
channel is used. Gate injection below is intentionally test-owned and private.
"""
import asyncio
from contextlib import contextmanager
from datetime import date
import importlib.util
import os
from pathlib import Path
import sys
from threading import Barrier, Event, Lock
from types import SimpleNamespace as NS

import httpx
import pytest

assert os.environ.get("PYTHON_DOTENV_DISABLED") == "1", "Disable dotenv before collecting offline tests."
assert os.environ.get("DATABASE_URL") in {
    "sqlite://", "postgresql+psycopg://fixture:private@127.0.0.1/fixture",
}, "Use a synthetic offline database URL and the real-connection guard."

from app import config, evidence_latency as lat, embedding_service as embedding
from app import filing_search_service as search, freshness_service as fresh, main
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.sec_client import build_filing_url


SECRET = "PRIVATE-CANARY-DO-NOT-RETAIN-4815162342"
QUERY = "supply chain " + SECRET
VECTOR = [1.0] + [0.0] * 383
ISSUERS = {"AAPL": "0000320193", "COST": "0000909832"}


def bomb(*args, **kwargs):
    raise AssertionError("Forbidden real dependency or external operation")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(lat.CONFIG_KEY):
            monkeypatch.delenv(name)
    monkeypatch.setattr(lat, "_collector", None)
    monkeypatch.setattr(lat, "_permit", None)
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    monkeypatch.setattr(main, "HttpSessionLocal", bomb)
    monkeypatch.setattr("app.database.engine.connect", bomb)
    monkeypatch.setitem(sys.modules, "sentence_transformers", NS(SentenceTransformer=bomb))
    embedding._get_model.cache_clear()
    record_token, parent_token = lat._current.set(None), lat._parent.set(0)
    yield
    embedding._get_model.cache_clear()
    lat._parent.reset(parent_token)
    lat._current.reset(record_token)


def enable(monkeypatch, *, proof=True):
    """Fake admission state, never an actual local-run approval or socket."""
    monkeypatch.setenv(lat.CONFIG_KEY, lat.CONFIG_VALUE)
    monkeypatch.setenv(lat.LOCAL_KEY, lat.LOCAL_VALUE)
    monkeypatch.setattr(lat, "_permit", (os.getpid(), None, None, lat.perf_counter_ns()))
    monkeypatch.setattr(lat, "_verified_local_run", lambda scope, now: proof)


@contextmanager
def holding(record):
    token, parent_token = lat._current.set(record), lat._parent.set(0)
    try:
        yield record
    finally:
        lat._parent.reset(parent_token)
        lat._current.reset(token)


def record():
    now = lat.perf_counter_ns()
    return lat._Record(1, 1, now, now + lat.REQUEST_NS)


def summaries(item):
    return [lat._SUMMARY.unpack_from(item.summary, i * lat._SUMMARY.size)
            for i in range(item.summary_count)]


def phases(item):
    return [row[2] for row in summaries(item)]


def raw(item):
    return [lat._EVENT.unpack_from(item.events, i * lat._EVENT.size) for i in range(item.count)]


class Rows(list):
    def __init__(self, values, store, kind):
        super().__init__(values)
        self.store, self.kind = store, kind

    def __iter__(self):
        self.store.op("consume_" + self.kind)
        # Verify that lazy consumption is INSIDE the read span, without changing
        # the semantic SQL ledger compared between enabled/disabled requests.
        item = lat._current.get()
        if item is not None:
            starts = {r[1]: r[3] for r in raw(item) if r[4] == lat.START}
            self.store.consumption.append((self.kind, starts.get(lat._parent.get())))
        return super().__iter__()

    def first(self):
        self.store.op("consume_" + self.kind)
        return self[0] if self else None


class Session:
    """Fake PostgreSQL-shaped session; no engine or real SQL execution."""
    def __init__(self, ticker, ledger, stage=None, close_error=False):
        self.ledger, self.stage, self.close_error = ledger, stage, close_error
        self.consumption = []
        self.live = False
        self.company = Company(id=1, ticker=ticker, cik=ISSUERS[ticker], name=ticker + " synthetic", exchange="NASDAQ")
        cik = self.company.cik
        accession = cik + "-26-000001"  # explicitly synthetic evidence
        self.state = CompanyRefreshState(company_cik=cik, data_version=7, facts_version=5,
                                        evidence_version=6, evidence={}, facts={})
        self.chunks = [FilingChunk(id=i + 1, company_cik=cik, accession_number=accession,
            form="10-Q", filed=date(2026, 7, 31), filename="synthetic.htm", chunk_index=i,
            chunk_id=f"chunk_{i:04d}", text=text, start_char=i * 2250,
            end_char=i * 2250 + len(text), embedding=VECTOR,
            sec_url=build_filing_url(cik, accession)) for i, text in enumerate((
                "Supply chain disruption " + SECRET, "Supply chain continuity and suppliers."))]
        self.publications = [FilingPublication(company_cik=cik, accession_number=accession,
            form="10-Q", filed=date(2026, 7, 31), filename="synthetic.htm", chunk_count=2,
            data_version=4, content_digest=fresh.chunk_digest(self.chunks))]
        self.conn = NS(invalidate=lambda: self.op("connection_invalidate"))

    def op(self, name):
        self.ledger.append(name)
        if name == self.stage:
            raise RuntimeError(SECRET)

    def get_bind(self):
        self.op("bind")
        return NS(dialect=NS(name="postgresql"))

    def connection(self):
        self.op("connection")
        return self.conn

    def scalar(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is CompanyRefreshState:
            self.op("pin")
            return self.state.data_version
        assert entity is Company
        self.op("company")
        return self.company

    def get(self, model, key):
        assert model is CompanyRefreshState and key == self.company.cik
        self.op("state")
        return self.state

    def execute(self, stmt):
        if not hasattr(stmt, "column_descriptions"):
            assert str(stmt) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            self.op("transaction")
            self.live = True
            return Rows([], self, "transaction")
        entity = stmt.column_descriptions[0]["entity"]
        if entity is FilingPublication:
            self.op("latest")
            p = self.publications[0]
            return Rows([NS(accession_number=p.accession_number, form=p.form, filed=p.filed)], self, "latest")
        assert entity is FilingChunk
        self.op("inventory")
        return Rows([NS(**{field: getattr(c, field) for field in fresh.CHUNK_IDENTITY_FIELDS},
                        text_length=len(c.text)) for c in self.chunks], self, "inventory")

    def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is FilingPublication:
            self.op("publications")
            pending = (self.state.evidence or {}).get("pending_targets", [])
            return Rows([p for p in self.publications if p.accession_number not in pending], self, "publications")
        assert entity is FilingChunk
        self.op("bodies")
        return Rows(self.chunks, self, "bodies")

    def close(self):
        self.live = False
        self.op("close")
        if self.close_error:
            raise OSError(SECRET)

    def invalidate(self):
        self.live = False
        self.op("session_invalidate")


def install(monkeypatch, *, stage=None, close_error=False, encoder_stage=None, barrier=None, mutate=None):
    sessions, ledgers, inputs, constructor_calls = [], [], [], []
    lock = Lock()

    def factory():
        ticker = main.request_scope.get()["ticker"]
        ledger = ["factory"]
        with lock:
            ledgers.append(ledger)
        if stage == "factory":
            raise RuntimeError(SECRET)
        session = Session(ticker, ledger, stage, close_error)
        if mutate is not None:
            mutate(session)
        with lock:
            sessions.append(session)
        return session

    class Model:
        def get_sentence_embedding_dimension(self):
            if encoder_stage == "admission":
                return 1
            return 384

        def encode(self, texts, **kwargs):
            if encoder_stage == "encode":
                raise RuntimeError(SECRET)
            with lock:
                inputs.append((texts.copy(), kwargs.copy(), lat._current.get().issuer if lat._current.get() else None))

            def tolist():
                if encoder_stage == "conversion":
                    raise RuntimeError(SECRET)
                return [VECTOR.copy()]
            return NS(tolist=tolist)

    def constructor(*args, **kwargs):
        with lock:
            constructor_calls.append((args, kwargs))
        if barrier is not None:
            barrier.wait(timeout=5)
        if encoder_stage == "constructor":
            raise OSError(SECRET)
        return Model()

    monkeypatch.setattr(main, "HttpSessionLocal", factory)
    monkeypatch.setattr(fresh, "schema_ready", lambda connection: True)
    monkeypatch.setitem(sys.modules, "sentence_transformers", NS(SentenceTransformer=constructor))
    return NS(sessions=sessions, ledgers=ledgers, inputs=inputs, constructors=constructor_calls)


async def request(ticker="AAPL", *, query=QUERY, suffix="context", headers=None):
    transport = httpx.ASGITransport(app=main.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://synthetic") as client:
        return await client.get(f"/companies/{ticker}/{suffix}", params={"q": query, "limit": "5"},
                                headers=headers or {"X-FinLens-Data-Version": "7"})


def fingerprint(response):
    return response.status_code, tuple(response.headers.multi_items()), response.content


@pytest.mark.parametrize("stage", [None, "factory", "bind", "connection", "transaction", "pin",
                                   "company", "state", "publications", "consume_publications",
                                   "inventory", "consume_inventory", "bodies", "consume_bodies", "close"])
def test_http_enabled_disabled_bytes_headers_and_operation_equivalence(monkeypatch, stage):
    baseline = install(monkeypatch, stage=stage)
    off = asyncio.run(request())
    embedding._get_model.cache_clear()
    enabled = install(monkeypatch, stage=stage)
    enable(monkeypatch)
    on = asyncio.run(request())
    assert fingerprint(off) == fingerprint(on)
    assert baseline.ledgers == enabled.ledgers
    assert [(x[0], x[1]) for x in baseline.inputs] == [(x[0], x[1]) for x in enabled.inputs]
    assert baseline.constructors == enabled.constructors
    assert len(lat._collector.records) == 1 and lat._collector.active == 0
    item = lat._collector.records[0]
    assert item.sealed and main.request_scope.get() is None and lat._current.get() is None
    if stage is None:
        assert item.coverage_complete and item.constructors == 1
        data = on.json()
        assert data["company_cik"] == ISSUERS["AAPL"]
        assert (data["data_version"], data["evidence_version"]) == (7, 6)
        assert [c["chunk_id"] for c in data["citations"]] == ["chunk_0000", "chunk_0001"]
        assert all(c["semantic_similarity"] == 1.0 for c in data["citations"])
        assert enabled.sessions[0].consumption == [("publications", lat.PHASES["publication_read"]),
            ("inventory", lat.PHASES["chunk_inventory_read"]), ("bodies", lat.PHASES["chunk_body_read"])]
        assert enabled.inputs[0][0] == [QUERY]
    else:
        assert not item.coverage_complete
        if stage == "factory":
            assert lat.PHASES["session_cleanup"] not in phases(item)
            assert enabled.ledgers == [["factory"]]


@pytest.mark.parametrize("stage", ["constructor", "admission", "encode", "conversion"])
def test_encoder_failure_equivalence_and_actual_constructor_count(monkeypatch, stage):
    install(monkeypatch, encoder_stage=stage)
    off = asyncio.run(request())
    embedding._get_model.cache_clear()
    run = install(monkeypatch, encoder_stage=stage)
    enable(monkeypatch)
    on = asyncio.run(request())
    assert fingerprint(off) == fingerprint(on)
    assert len(run.constructors) == 1
    item = lat._collector.records[0]
    assert item.constructors == 1 and not item.coverage_complete
    assert all(s.ledger.count("close") == 1 for s in run.sessions)


@pytest.mark.parametrize("suffix,headers,query", [
    ("context", {"X-FinLens-Data-Version": "6"}, QUERY),
    ("context", {"X-FinLens-Data-Version": "7"}, " "),
    ("context", {"X-FinLens-Data-Version": "7"}, "x" * 2001),
    ("freshness", {}, QUERY),
])
def test_pin_input_and_freshness_equivalence(monkeypatch, suffix, headers, query):
    baseline = install(monkeypatch)
    off = asyncio.run(request(suffix=suffix, headers=headers, query=query))
    embedding._get_model.cache_clear()
    run = install(monkeypatch)
    enable(monkeypatch)
    on = asyncio.run(request(suffix=suffix, headers=headers, query=query))
    assert fingerprint(off) == fingerprint(on) and baseline.ledgers == run.ledgers
    assert lat._collector.active == 0


@pytest.mark.parametrize("profile", ["sec_readonly", "unknown", "", "DEVELOPMENT"])
def test_resolved_profile_denies_collection(monkeypatch, profile):
    install(monkeypatch)
    enable(monkeypatch)
    monkeypatch.setattr(config, "_SERVER_PROFILE", NS(name=profile))
    assert asyncio.run(request()).status_code == 200
    assert lat._collector is None


@pytest.mark.parametrize("key,value", [
    (lat.CONFIG_KEY, ""), (lat.CONFIG_KEY, "1"), (lat.CONFIG_KEY, lat.CONFIG_VALUE + " "),
    (lat.LOCAL_KEY, ""), (lat.LOCAL_KEY, "true"), (lat.LOCAL_KEY, lat.LOCAL_VALUE + " "),
    (lat.CONFIG_KEY + "_UNEXPECTED", "1"),
])
def test_configuration_conflicts_fail_closed(monkeypatch, key, value):
    install(monkeypatch)
    enable(monkeypatch)
    monkeypatch.setenv(key, value)
    assert asyncio.run(request()).status_code == 200
    assert lat._collector is None


@pytest.mark.parametrize("value", ["", "sec_readonly", "unknown", "development "])
def test_conflicting_profile_environment_denies_even_with_frozen_development(monkeypatch, value):
    install(monkeypatch)
    enable(monkeypatch)
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", value)
    assert asyncio.run(request()).status_code == 200
    assert lat._collector is None


@pytest.mark.parametrize("missing", [lat.CONFIG_KEY, lat.LOCAL_KEY, "permit", "proof"])
def test_missing_authorization_or_proof_denies(monkeypatch, missing):
    install(monkeypatch)
    enable(monkeypatch, proof=missing != "proof")
    if missing == "permit":
        monkeypatch.setattr(lat, "_permit", None)
    elif missing != "proof":
        monkeypatch.delenv(missing)
    assert asyncio.run(request()).status_code == 200
    assert lat._collector is None


@pytest.mark.parametrize("method,path", [("POST", "/companies/AAPL/context"),
    ("GET", "/companies/JPM/context"), ("GET", "/companies/aapl/context"),
    ("GET", "/companies/AAPL/filings/x/context"), ("GET", "/healthz"),
    ("GET", "/companies/AAPL/context/"), ("GET", "/companies/AAPL/context?activate=1")])
def test_exact_route_method_issuer_allowlist(monkeypatch, method, path):
    enable(monkeypatch)
    assert lat._admit({"type": "http", "method": method, "path": path}, "development") is None
    assert lat._collector is None


@pytest.mark.parametrize("binding,server,pid_delta,age", [
    (None, ("127.0.0.1", 8000), 0, 0),
    (("127.0.0.1", 8000), ("0.0.0.0", 8000), 0, 0),
    (("127.0.0.1", 8000), ("127.0.0.1", 8001), 0, 0),
    (("127.0.0.1", 8000), ("127.0.0.1", 8000), 1, 0),
    (("127.0.0.1", 8000), ("127.0.0.1", 8000), 0, lat.COLLECTION_NS),
])
def test_independent_listener_proof_cannot_be_replaced_by_scope(monkeypatch, binding, server, pid_delta, age):
    now = lat.perf_counter_ns()
    monkeypatch.setattr(lat, "_permit", (os.getpid() + pid_delta, lambda: object(), ("127.0.0.1", 8000), now - age))
    monkeypatch.setattr(lat, "_binding", lambda listener: binding)
    assert not lat._verified_local_run({"server": server}, now)
    assert lat._binding is not None


def test_approval_rejects_missing_config_ambiguous_and_non_socket_without_io(monkeypatch):
    assert not lat._approve_local_run(authorized=False, listeners=())
    monkeypatch.setenv(lat.CONFIG_KEY, lat.CONFIG_VALUE)
    monkeypatch.setenv(lat.LOCAL_KEY, lat.LOCAL_VALUE)
    for listeners in ((), (object(), object()), (object(),), [object()]):
        assert not lat._approve_local_run(authorized=True, listeners=listeners)
    assert lat._permit is None and lat._collector is None


@pytest.mark.parametrize("address,family,sock_type,listening,accepted", [
    (("127.0.0.1", 8000), 2, 1, 1, True),
    (("::1", 8000, 0, 0), 23, 1, 1, True),
    (("0.0.0.0", 8000), 2, 1, 1, False),
    (("::", 8000, 0, 0), 23, 1, 1, False),
    (("::ffff:127.0.0.1", 8000, 0, 0), 23, 1, 1, False),
    (("127.0.0.2", 8000), 2, 1, 1, False),
    (("127.0.0.1", 0), 2, 1, 1, False),
    (("127.0.0.1", 65536), 2, 1, 1, False),
    (("127.0.0.1", 8000), 2, 2, 1, False),
    (("127.0.0.1", 8000), 2, 1, 0, False),
    (("127.0.0.1", 8000), 999, 1, 1, False),
])
def test_actual_binding_inspector_contract_with_synthetic_socket(monkeypatch, address, family, sock_type, listening, accepted):
    import socket

    class FakeSocket:
        def __init__(self):
            self.family = socket.AF_INET6 if family == 23 else family

        def getsockopt(self, level, option):
            assert level == socket.SOL_SOCKET
            return sock_type if option == socket.SO_TYPE else listening

        def getsockname(self):
            return address

    # No real socket is created; call the production inspector against the fake
    # low-level socket interface, including all rejecting binding conditions.
    monkeypatch.setattr(socket, "socket", FakeSocket)
    result = lat._binding(FakeSocket())
    assert (result is not None) is accepted


def test_headers_and_query_parameters_cannot_activate_diagnostics(monkeypatch):
    install(monkeypatch)
    response = asyncio.run(request(query="activate=bounded-local-v1", headers={
        "X-FinLens-Data-Version": "7", "X-FinLens-Evidence-Latency": lat.CONFIG_VALUE,
        lat.LOCAL_KEY: lat.LOCAL_VALUE}))
    assert response.status_code == 200 and lat._collector is None


def test_disabled_has_no_collector_model_initialization_or_approval(monkeypatch):
    monkeypatch.setattr(lat, "_approve_local_run", bomb)
    monkeypatch.setattr(lat, "_verified_local_run", bomb)
    monkeypatch.setattr(lat, "_Collector", bomb)
    monkeypatch.setattr(embedding, "_load_model", bomb)
    with lat.span("query_embedding"):
        assert embedding.embed_texts([]) == []
    assert asyncio.run(request(query=" ")).status_code == 422
    assert lat._collector is None and lat._permit is None
    assert embedding._get_model.cache_info().currsize == 0


def test_helper_import_does_not_import_app_config_or_create_storage(monkeypatch):
    path = Path(lat.__file__)
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("isolated_latency_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._collector is None and module._permit is None
    assert not (set(sys.modules) - before) & {"sentence_transformers", "torch", "psycopg", "app.config"}


def test_concurrent_cold_attempts_then_warm_hit_and_context_ownership(monkeypatch):
    run = install(monkeypatch, barrier=Barrier(2))
    enable(monkeypatch)

    async def comparisons():
        responses = await asyncio.gather(request("AAPL"), request("COST"))
        assert lat._current.get() is None and main.request_scope.get() is None
        return responses

    responses = asyncio.run(comparisons())
    assert all(r.status_code == 200 for r in responses)
    assert len(run.constructors) == 2  # observing, not eliminating, the LRU race
    cold = lat._collector.records.copy()
    assert {r.issuer for r in cold} == {1, 2}
    assert len({r.correlation for r in cold}) == 2
    assert all(r.constructors == 1 and r.coverage_complete for r in cold)
    assert {i[2] for i in run.inputs} == {1, 2}
    warm = asyncio.run(request("AAPL"))
    assert warm.status_code == 200 and len(run.constructors) == 2
    item = lat._collector.records[-1]
    assert item.constructors == 0 and item.coverage_complete
    assert lat.PHASES["model_cache_lookup"] in phases(item)
    assert lat.PHASES["encoder_loader_body"] not in phases(item)
    assert lat._collector.active == 0


def test_exclusive_time_subtracts_union_of_overlapping_children():
    item = lat._Record(1, 1, 100, 1000)
    events = [(100, 1, 0, 1, lat.START, 0), (120, 2, 1, 2, lat.START, 0),
              (150, 3, 1, 3, lat.START, 0), (170, 2, 1, 2, lat.END, lat.OK),
              (190, 3, 1, 3, lat.END, lat.OK), (200, 1, 0, 1, lat.END, lat.OK)]
    for values in events:
        item._append(*values)
    item.sealed = True
    lat._aggregate(item)
    root = summaries(item)[0]
    assert root[4:6] == (100, 30)  # children union=70; sum=90 would be wrong


def test_parent_child_ids_and_missing_coverage_are_explicit():
    item = record()
    with holding(item), lat.span("http_request"):
        with lat.span("worker"):
            with lat.span("python_similarity"):
                pass
    item.worker_done = True
    lat._finish(item, lat.OK)
    rows = summaries(item)
    assert rows[0][1] == 0 and rows[1][1] == rows[0][0] and rows[2][1] == rows[1][0]
    assert not item.coverage_complete and item.missing != 0


def test_hard_request_active_and_total_byte_caps(monkeypatch):
    enable(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/companies/AAPL/context"}
    a, b = lat._admit(scope, "development"), lat._admit(scope, "development")
    assert a is not None and b is not None and lat._admit(scope, "development") is None
    lat._finish(a, lat.OK)
    lat._finish(b, lat.OK)
    for _ in range(6):
        item = lat._admit(scope, "development")
        assert item is not None
        lat._finish(item, lat.OK)
    assert lat._admit(scope, "development") is None
    collector = lat._collector
    assert len(collector.records) == 8 and collector.active == 0
    assert collector.reserved <= lat.MAX_RETAINED_BYTES
    # Conservative accounting includes slotted objects, buffers, locks and each
    # primitive (even shared primitive objects are deliberately over-counted).
    actual = sys.getsizeof(collector) + sys.getsizeof(collector.records)
    for item in collector.records:
        actual += sys.getsizeof(item) + sum(sys.getsizeof(getattr(item, s)) for s in item.__slots__)
    assert actual < collector.reserved
    lat._finish(collector.records[0], lat.FAILED)
    assert collector.active == 0  # finalization is idempotent


def test_byte_cap_denies_before_record_allocation(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(lat, "MAX_RETAINED_BYTES", lat.CONTROL_RESERVATION)
    monkeypatch.setattr(lat, "_Record", bomb)
    assert lat._admit({"type": "http", "method": "GET", "path": "/companies/AAPL/context"}, "development") is None
    assert lat._collector.records == []


def test_interpreter_object_overhead_cannot_exceed_reservation(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(lat, "RECORD_RESERVATION", 1)
    item = lat._admit({"type": "http", "method": "GET", "path": "/companies/AAPL/context"}, "development")
    assert item is None and lat._collector.records == [] and lat._collector.active == 0


def test_event_overflow_stops_recording_without_affecting_work():
    item = record()
    calls = []
    with holding(item):
        for i in range(200):
            with lat.span("python_similarity"):
                calls.append(i)
    assert len(calls) == 200 and item.count == lat.MAX_EVENTS and item.truncated
    item.worker_done = True
    lat._finish(item, lat.OK)
    assert not item.coverage_complete
    assert len(item.events) == lat.MAX_EVENTS * lat._EVENT.size
    assert item.summary_count <= lat.MAX_EVENTS


@pytest.mark.parametrize("boundary", ["request", "collection"])
def test_lifetime_bounds_stop_recording_and_admission(monkeypatch, boundary):
    enable(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/companies/AAPL/context"}
    item = lat._admit(scope, "development")
    now = item.deadline if boundary == "request" else lat._collector.deadline
    monkeypatch.setattr(lat, "perf_counter_ns", lambda: now)
    with holding(item), lat.span("query_embedding"):
        pass
    assert item.expired and item.count == 0
    if boundary == "collection":
        assert lat._admit(scope, "development") is None
    lat._finish(item, lat.OK)
    assert item.sealed and not item.coverage_complete


@pytest.mark.parametrize("phase", [SECRET, "x" * 10000, b"worker", None, 99])
def test_closed_phase_schema_rejects_arbitrary_fields(phase):
    item = record()
    with holding(item), lat.span(phase):
        pass
    assert item.count == 0 and len(item.events) == 2048


def test_private_buffers_never_retain_content_config_queries_sql_vectors_or_exceptions(monkeypatch):
    install(monkeypatch)
    enable(monkeypatch)
    monkeypatch.setenv("UNRELATED_SECRET", SECRET)
    response = asyncio.run(request(query=QUERY + " https://private.invalid/secret SELECT secret"))
    assert response.status_code == 200 and SECRET.encode() in response.content
    item = lat._collector.records[0]
    allowed = (int, bool, str, bytearray, type(Lock()))
    for slot in item.__slots__:
        value = getattr(item, slot)
        assert type(value) in allowed
        if isinstance(value, (str, bytearray)):
            encoded = value.encode() if isinstance(value, str) else bytes(value)
            for canary in (SECRET, "https://private.invalid/secret", "SELECT secret", str(VECTOR), QUERY):
                assert canary.encode() not in encoded
    assert len(item.correlation) == 16 and set(item.correlation) <= set("0123456789abcdef")


@pytest.mark.parametrize("failure", ["begin", "end", "aggregate", "clock"])
def test_internal_failures_preserve_http_bytes_and_cleanup(monkeypatch, failure):
    baseline = install(monkeypatch)
    off = asyncio.run(request())
    embedding._get_model.cache_clear()
    run = install(monkeypatch)
    enable(monkeypatch)
    if failure == "aggregate":
        monkeypatch.setattr(lat, "_aggregate", bomb)
    elif failure == "clock":
        monkeypatch.setattr(lat, "perf_counter_ns", bomb)
    else:
        monkeypatch.setattr(lat._Record, failure, bomb)
    on = asyncio.run(request())
    assert fingerprint(off) == fingerprint(on) and baseline.ledgers == run.ledgers
    if lat._collector and lat._collector.records:
        assert not lat._collector.records[0].coverage_complete


@pytest.mark.parametrize("primary", [RuntimeError(SECRET), KeyboardInterrupt(SECRET), asyncio.CancelledError(SECRET), None])
@pytest.mark.parametrize("close_failure", [False, True])
def test_direct_cleanup_equivalence_and_original_exception_precedence(monkeypatch, primary, close_failure):
    monkeypatch.setattr(fresh, "schema_ready", lambda connection: True)
    outcomes, ledgers, items = [], [], []
    for enabled in (False, True):
        ledger = ["factory"]
        session = Session("AAPL", ledger, close_error=close_failure)
        item = record() if enabled else None
        scope_token = fresh.request_scope.set({"ticker": "AAPL", "expected": "7"})
        try:
            with holding(item):
                try:
                    with fresh.read_session(lambda: session):
                        ledger.append("body")
                        if primary is not None:
                            raise primary
                except BaseException as exc:
                    outcomes.append(exc)
                else:
                    outcomes.append(None)
        finally:
            fresh.request_scope.reset(scope_token)
        ledgers.append(ledger)
        items.append(item)
    assert ledgers[0] == ledgers[1] and ledgers[1].count("close") == 1
    if primary is not None:
        assert outcomes[0] is primary and outcomes[1] is primary
    elif close_failure:
        assert all(type(exc) is OSError for exc in outcomes)
    else:
        assert outcomes == [None, None]
    if close_failure:
        assert ledgers[1][-2:] == ["connection_invalidate", "session_invalidate"]


def test_aggregation_runs_after_request_cleanup(monkeypatch):
    run = install(monkeypatch)
    enable(monkeypatch)
    original = lat._aggregate
    observations = []

    def aggregate(item):
        observations.append(all(not s.live and s.ledger[-1] == "close" for s in run.sessions))
        return original(item)

    monkeypatch.setattr(lat, "_aggregate", aggregate)
    assert asyncio.run(request()).status_code == 200
    assert observations == [True]


def test_late_copied_worker_cannot_mutate_http_finalized_record(monkeypatch):
    enable(monkeypatch)
    started, release, ended = Event(), Event(), Event()

    @lat.worker
    def slow():
        try:
            with lat.span("transaction_setup"):
                started.set()
                assert release.wait(5)
            with lat.span("session_cleanup"):
                pass
        finally:
            ended.set()

    async def app(scope, receive, send):
        await asyncio.to_thread(slow)

    observer = lat.EvidenceLatencyMiddleware(app, lambda: NS(name="development"))
    scope = {"type": "http", "method": "GET", "path": "/companies/AAPL/context"}

    async def exercise():
        task = asyncio.create_task(observer(scope, bomb, bomb))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            item = lat._collector.records[0]
            before = (bytes(item.events), bytes(item.summary), item.count, item.worker_done, item.outcome)
            assert item.sealed and not item.worker_done and item.summary_count == 0 and not item.aggregated
            assert item.outcome == lat.CANCELLED and not item.coverage_complete
            release.set()
            assert await asyncio.to_thread(ended.wait, 5)
            return item, before
        finally:
            release.set()

    item, before = asyncio.run(exercise())  # waits for executor wrapper finalization too
    assert (bytes(item.events), bytes(item.summary), item.count, item.worker_done, item.outcome) == before
    assert lat._current.get() is None and lat._parent.get() == 0


@pytest.mark.parametrize("error", [RuntimeError(SECRET), asyncio.CancelledError(SECRET), KeyboardInterrupt(SECRET)])
def test_send_exception_identity_and_final_send_not_client_receipt(monkeypatch, error):
    enable(monkeypatch)
    sent = []

    @lat.worker
    def finish_worker():
        return None

    async def app(scope, receive, send):
        await asyncio.to_thread(finish_worker)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"unchanged"})

    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.body":
            raise error

    observer = lat.EvidenceLatencyMiddleware(app, lambda: NS(name="development"))
    with pytest.raises(type(error)) as caught:
        asyncio.run(observer({"type": "http", "method": "GET", "path": "/companies/AAPL/context"}, bomb, send))
    assert caught.value is error and sent[-1]["body"] == b"unchanged"
    item = lat._collector.records[0]
    assert item.worker_done and not item.body_sent and not item.coverage_complete


def test_release_admission_order_is_unchanged():
    names = [m.cls.__name__ for m in main.app.user_middleware]
    assert names[:3] == ["ReleaseAdmissionMiddleware", "EvidenceLatencyMiddleware", "CORSMiddleware"]


@pytest.mark.parametrize("damage", ["digest", "count", "source", "vector", "pending", "future", "filename", "insufficient"])
def test_enabled_disabled_publication_and_evidence_policy_equivalence(monkeypatch, damage):
    def mutate(session):
        if damage == "digest":
            session.publications[0].content_digest = "0" * 64
        elif damage == "count":
            session.publications[0].chunk_count = 99
        elif damage == "source":
            session.chunks[0].sec_url = "https://private.invalid/" + SECRET
        elif damage == "vector":
            session.chunks[0].embedding = [0.0] * 384
        elif damage == "pending":
            session.state.evidence = {"pending_targets": [session.publications[0].accession_number]}
        elif damage == "future":
            session.publications[0].data_version = 8
        elif damage == "filename":
            session.publications[0].filename = "../untrusted.htm"
        else:
            for c in session.chunks:
                c.text = "Unrelated clinical observations."
                c.embedding = [0.0, 1.0] + [0.0] * 382
            session.publications[0].content_digest = fresh.chunk_digest(session.chunks)

    baseline = install(monkeypatch, mutate=mutate)
    off = asyncio.run(request())
    embedding._get_model.cache_clear()
    run = install(monkeypatch, mutate=mutate)
    enable(monkeypatch)
    on = asyncio.run(request())
    assert fingerprint(off) == fingerprint(on) and baseline.ledgers == run.ledgers
    if on.status_code == 200:
        assert on.json()["citations"] == [] and on.json()["evidence_status"] == "insufficient"
    assert not lat._collector.records[0].coverage_complete or damage == "insufficient"


def test_exact_encoder_phase_boundaries_and_unchanged_arguments(monkeypatch):
    import builtins
    clock = [1_000_000]
    monkeypatch.setattr(lat, "perf_counter_ns", lambda: clock[0])
    original_import = builtins.__import__
    calls = []

    def importing(name, *args, **kwargs):
        if name == "sentence_transformers":
            clock[0] += 11
        return original_import(name, *args, **kwargs)

    class Model:
        def get_sentence_embedding_dimension(self):
            clock[0] += 23
            return 384

        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs))
            clock[0] += 31

            def tolist():
                clock[0] += 37
                return [VECTOR.copy()]
            return NS(tolist=tolist)

    def constructing(*args, **kwargs):
        calls.append((args, kwargs))
        clock[0] += 17
        return Model()

    monkeypatch.setitem(sys.modules, "sentence_transformers", NS(SentenceTransformer=constructing))
    monkeypatch.setattr(builtins, "__import__", importing)
    item = record()
    with holding(item):
        assert embedding.embed_texts([QUERY]) == [VECTOR]
    item.worker_done = True
    lat._finish(item, lat.OK)
    durations = {r[2]: r[4:6] for r in summaries(item)}
    for phase, expected in [("encoder_dependency_import", 11), ("model_constructor", 17),
                            ("encoder_admission", 23), ("encoder_encode", 31), ("encoder_output_conversion", 37)]:
        assert durations[lat.PHASES[phase]] == (expected, expected)
    assert durations[lat.PHASES["encoder_loader_body"]] == (51, 0)
    assert durations[lat.PHASES["model_cache_lookup"]] == (51, 0)
    assert durations[lat.PHASES["query_embedding"]] == (119, 0)
    assert item.constructors == 1 and calls == [((embedding.MODEL_NAME,), {}),
        ([QUERY], {"batch_size": 32, "normalize_embeddings": True, "show_progress_bar": False})]


def test_missing_real_path_phase_prevents_complete_coverage(monkeypatch):
    from contextlib import nullcontext
    install(monkeypatch)
    enable(monkeypatch)
    original = lat.span
    monkeypatch.setattr(lat, "span", lambda name: nullcontext() if name == "python_similarity" else original(name))
    response = asyncio.run(request())
    item = lat._collector.records[0]
    assert response.status_code == 200 and item.aggregated
    assert item.missing == 1 << lat.PHASES["python_similarity"] and not item.coverage_complete


@pytest.mark.parametrize("field,value", [("span_id", True), ("span_id", 129), ("parent", -1),
    ("phase", 65535), ("edge", True), ("outcome", SECRET), ("timestamp", 1.5)])
def test_raw_event_field_types_and_ranges_are_closed(field, value):
    item = lat._Record(1, 1, 100, 1000)
    fields = dict(timestamp=101, span_id=1, parent=0, phase=1, edge=lat.START, outcome=0)
    fields[field] = value
    assert not item._append(**fields)
    assert item.internal_failure and item.count == 0


def test_expired_flags_cannot_claim_late_completion(monkeypatch):
    item = record()
    monkeypatch.setattr(lat, "perf_counter_ns", lambda: item.deadline)
    lat._flag(item, "worker_done")
    lat._flag(item, "body_sent")
    lat._flag(item, "status", 200)
    assert item.expired and item.truncated
    assert not item.worker_done and not item.body_sent and item.status == 0
