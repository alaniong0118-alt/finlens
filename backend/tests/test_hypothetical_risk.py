"""Synthetic-only adapter/HTTP tests; use tests/run_financial_insights.py."""
from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, hypothetical_risk as adapter
from app.hypothetical_risk_route import router
from app.portfolio_risk import PortfolioRiskError
from app.release_policy import ReleaseAdmissionMiddleware, READONLY_ROUTES


def fixture(confidence="0.8", horizon=1):
    losses = [-4, -2, 0, 1, 1, 2, 3, 4, 4, 10]
    from decimal import Decimal
    start = date(2026, 1, 1)
    return {"reporting_currency": "USD", "exposure_date": "2026-02-01", "confidence": confidence,
        "horizon": horizon, "portfolio_value": "100", "exposures": [{"asset_id": "long", "amount": "100"}],
        "sessions": [{"session_id": f"s{i}", "start": (start + timedelta(days=i)).isoformat(),
            "end": (start + timedelta(days=i+1)).isoformat(), "factors": {"long": str(1 - Decimal(loss) / 100)}}
            for i, loss in enumerate(losses)]}


def result(value=None):
    return adapter.calculate_request(value or fixture())["result"]


@pytest.mark.parametrize("confidence,var,es,mass", [("0.8", "4", "7", "2"), ("0.85", "4", "8", "1.5"), ("0.95", "10", None, "0.5")])
def test_references(confidence, var, es, mass):
    r = result(fixture(confidence))
    assert r["var"]["exact"]["display"] == f"{var}.000000000000000000"
    assert (r["es"]["exact"] is None) == (es is None)
    if es:
        assert r["es"]["exact"]["display"] == f"{es}.000000000000000000"
    else:
        assert r["es"]["reason"] == "insufficient_tail_mass"
    from decimal import Decimal
    assert Decimal(r["tail_mass"]["display"]) == Decimal(mass)
    assert len(r["scenarios"]) == 10
    assert r["data_authority"] == "unverified_synthetic_inputs"


def test_signs_overlap_and_full_receipt():
    value = fixture("0.5", 2)
    value["exposures"].append({"asset_id": "short", "amount": "-25"})
    value["sessions"] = value["sessions"][:4]
    for i, session in enumerate(value["sessions"]):
        session["factors"] = {"long": "1.1" if i % 2 == 0 else "0.9", "short": "1"}
    original = deepcopy(value)
    response = adapter.calculate_request(value)
    assert value == original and response["inputs"] == original
    r = response["result"]
    assert r["var"]["exact"]["numerator"] == r["es"]["exact"]["numerator"] == "1"
    assert r["overlapping"] is True and r["scenario_count"] == 3
    assert all(s["tail_mass"]["numerator"] == "1" and s["tail_mass"]["denominator"] == "2" for s in r["scenarios"])
    assert r["net_exposure"]["numerator"] == "75" and r["gross_exposure"]["numerator"] == "125"
    assert len(r["panel"]["sessions"]) == 4
    value["exposures"] = [{"asset_id": "long", "amount": "-100"}]
    for session in value["sessions"]:
        session["factors"] = {"long": "1.1"}
    assert result(value)["var"]["exact"]["numerator"] == "21"


@pytest.mark.parametrize("count", [0, 1])
def test_insufficiency(count):
    value = fixture(); value["sessions"] = value["sessions"][:count]
    assert result(value)["var"]["reason"] == "insufficient_scenarios"


@pytest.mark.parametrize("amount,reason", [(None, "portfolio_value_not_declared"), ("0", "nonpositive_portfolio_value"), ("-10", "nonpositive_portfolio_value")])
def test_denominator(amount, reason):
    value = fixture(); value["portfolio_value"] = amount
    assert result(value)["var_percent"]["reason"] == reason
    assert result(value)["var"]["exact"]["numerator"] == "4"


@pytest.mark.parametrize("bad", [True, 1, 0.8, "NaN", "Infinity", "1e-1", " 0.8", "+0.8", "00.8", "0.1234567890123", "1" * 25, "0", "1"])
def test_confidence_rejects_coercion(bad):
    value = fixture(); value["confidence"] = bad
    with pytest.raises(PortfolioRiskError): result(value)


@pytest.mark.parametrize("case", ["missing", "unknown", "duplicate", "gap", "overlap", "reversed", "zero", "negative", "date", "field", "horizon", "bool", "assets", "sessions"])
def test_invalid_panels(case):
    value = fixture()
    if case == "missing": value["sessions"][-1]["factors"] = {}
    if case == "unknown": value["sessions"][-1]["factors"]["other"] = "1"
    if case == "duplicate": value["exposures"] *= 2
    if case == "gap": value["sessions"][1]["start"] = "2026-01-03"
    if case == "overlap": value["sessions"][1]["start"] = "2026-01-01"
    if case == "reversed": value["sessions"].reverse()
    if case == "zero": value["sessions"][-1]["factors"]["long"] = "0"
    if case == "negative": value["sessions"][-1]["factors"]["long"] = "-1"
    if case == "date": value["exposure_date"] = "2026-02-30"
    if case == "field": value["extra"] = "ignored?"
    if case == "horizon": value["horizon"] = 21
    if case == "bool": value["horizon"] = True
    if case == "assets": value["exposures"] *= 9
    if case == "sessions": value["sessions"] *= 13
    with pytest.raises(PortfolioRiskError): result(value)


@pytest.mark.parametrize("body", [b'{"a":1,"a":2}', b'NaN', b'\xff', b'{', b'[' * 2000, b' ' * (adapter.MAX_REQUEST_BYTES + 1)], ids=['duplicate', 'constant', 'utf8', 'broken', 'deep', 'oversize'])
def test_json_rejections(body):
    with pytest.raises(PortfolioRiskError): adapter.calculate_request(adapter.parse_body(body))


def test_inclusive_bounds_and_output_limit(monkeypatch):
    value = fixture("0.5", 20)
    value["exposures"] = [{"asset_id": f"a{i}", "amount": "999999999999.123456789012"} for i in range(8)]
    start = date(2026, 1, 1)
    value["sessions"] = [{"session_id": f"s{i}", "start": (start + timedelta(days=i)).isoformat(), "end": (start + timedelta(days=i+1)).isoformat(), "factors": {f"a{j}": "1.000000000001" for j in range(8)}} for i in range(120)]
    assert len(adapter.response_bytes(value)) < adapter.MAX_RESPONSE_BYTES
    monkeypatch.setattr(adapter, "MAX_RESPONSE_BYTES", 1)
    with pytest.raises(PortfolioRiskError, match="response_resource_limit"): adapter.response_bytes(value)


def client(monkeypatch, profile="development", enabled="1", admission=False):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile(profile))
    monkeypatch.setenv("FINLENS_HYPOTHETICAL_RISK", enabled)
    app = FastAPI(); app.include_router(router)
    if admission:
        app.add_middleware(ReleaseAdmissionMiddleware, router=app.router, admitted_routes=())
    return TestClient(app)


@pytest.mark.parametrize("profile,enabled,status", [("development", "0", 404), ("development", "", 404), ("sec_readonly", "1", 403), ("sec_reader", "1", 403)])
def test_disabled_and_restricted(monkeypatch, profile, enabled, status):
    with client(monkeypatch, profile, enabled, True) as c:
        assert c.post("/hypothetical-risk", json=fixture()).status_code == status
    assert ("POST", "/hypothetical-risk") not in READONLY_ROUTES


def test_http_and_transport(monkeypatch):
    with client(monkeypatch) as c:
        response = c.post("/hypothetical-risk", json=fixture())
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json() == adapter.calculate_request(fixture())
        assert c.post("/hypothetical-risk", content="{}", headers={"Content-Type": "text/plain"}).status_code == 415
        assert c.post("/hypothetical-risk", content=b' ' * 131073, headers={"Content-Type": "application/json"}).status_code == 413
        assert c.post("/hypothetical-risk", content=b'{"x":1,"x":2}', headers={"Content-Type": "application/json"}).status_code == 422
        assert c.post("/hypothetical-risk", json=fixture(), headers={"Content-Encoding": "gzip"}).status_code == 415
        from app.hypothetical_risk_route import _slot
        assert _slot.acquire(False)
        try:
            assert c.post("/hypothetical-risk", json=fixture()).status_code == 429
        finally:
            _slot.release()
        assert c.post("/hypothetical-risk", json={}).status_code == 422
        assert c.post("/hypothetical-risk", json=fixture()).status_code == 200


def test_main_registration(monkeypatch):
    from app.main import app
    with TestClient(app) as c:
        monkeypatch.setenv("FINLENS_HYPOTHETICAL_RISK", "1")
        assert c.post("/hypothetical-risk", json=fixture()).status_code == 200
        monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
        assert c.post("/hypothetical-risk", json=fixture()).status_code == 403


def test_contract_export():
    # Fresh actual adapter output for the client contract; export only on request.
    target = os.environ.get("FINLENS_RISK_CONTRACT_OUTPUT")
    if target:
        variants = [fixture(), fixture("0.85"), fixture("0.95"), fixture("0.5", 2)]
        for count in [0, 1]:
            value = fixture(); value["sessions"] = value["sessions"][:count]; variants.append(value)
        for amount in [None, "0", "-10"]:
            value = fixture(); value["portfolio_value"] = amount; variants.append(value)
        for sign in ["100", "-100"]:
            value = fixture(); value["exposures"][0]["amount"] = sign; variants.append(value)
        Path(target).write_text(json.dumps([adapter.calculate_request(v) for v in variants]), encoding="utf-8")


def test_absent_flag_rejects_before_body_parsing(monkeypatch):
    with client(monkeypatch) as c:
        monkeypatch.delenv("FINLENS_HYPOTHETICAL_RISK", raising=False)
        assert c.post("/hypothetical-risk", content=b'{', headers={"Content-Type": "application/json"}).status_code == 404


def test_request_byte_boundary_is_inclusive():
    body = b'{}' + b' ' * (adapter.MAX_REQUEST_BYTES - 2)
    assert adapter.parse_body(body) == {}
    with pytest.raises(PortfolioRiskError, match="request_resource_limit"):
        adapter.parse_body(body + b' ')


# These tests use the real ASGI route, Starlette dispatcher, AnyIO capacity
# limiter and worker threads. Events/limiter statistics, never timing sleeps,
# establish the phase in which cancellation or an exception is injected.
class _ObservedSlot:
    def __init__(self):
        from threading import BoundedSemaphore, Lock, Event
        self._semaphore = BoundedSemaphore(1)
        self._lock = Lock()
        self.released = Event()
        self._acquisitions = self._releases = 0

    def acquire(self, blocking=False):
        acquired = self._semaphore.acquire(blocking=blocking)
        if acquired:
            with self._lock:
                self._acquisitions += 1
        return acquired

    def release(self):
        with self._lock:
            self._semaphore.release()  # Actual bounded semaphore detects doubles.
            self._releases += 1
            self.released.set()

    @property
    def counts(self):
        with self._lock:
            return self._acquisitions, self._releases


def _dispatch_setup(monkeypatch):
    from app import hypothetical_risk_route as route
    slot = _ObservedSlot()
    monkeypatch.setattr(route, "_slot", slot)
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    monkeypatch.setenv("FINLENS_HYPOTHETICAL_RISK", "1")
    app = FastAPI(); app.include_router(route.router)
    return route, slot, app


async def _eventually(predicate):
    import asyncio
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0)


async def _cancel(task, times=1):
    import asyncio
    for _ in range(times):
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
    assert not task.cancel()  # A later repeated cancel cannot repeat cleanup.


@pytest.mark.parametrize("cancellations", [1, 3])
def test_actual_dispatch_queued_cancellation_releases_and_retry(monkeypatch, cancellations):
    import asyncio
    import httpx
    from anyio.to_thread import current_default_thread_limiter
    route, slot, app = _dispatch_setup(monkeypatch)
    calls = []
    original = route.response_bytes
    def record(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(route, "response_bytes", record)

    async def scenario():
        limiter = current_default_thread_limiter()
        previous = limiter.total_tokens; limiter.total_tokens = 1
        borrower = object()
        await limiter.acquire_on_behalf_of(borrower)
        borrowed = True
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
                request = asyncio.create_task(c.post("/hypothetical-risk", json=fixture()))
                await _eventually(lambda: limiter.statistics().tasks_waiting == 1)
                assert slot.counts == (1, 0) and calls == []
                await _cancel(request, cancellations)
                assert slot.counts == (1, 1) and calls == []
                assert limiter.statistics().tasks_waiting == 0
                limiter.release_on_behalf_of(borrower); borrowed = False
                response = await c.post("/hypothetical-risk", json=fixture())
                assert response.status_code == 200
                assert response.json() == adapter.calculate_request(fixture())
                assert slot.counts == (2, 2) and len(calls) == 1
        finally:
            if borrowed: limiter.release_on_behalf_of(borrower)
            limiter.total_tokens = previous
    asyncio.run(scenario())


@pytest.mark.parametrize("cancellations", [1, 3])
def test_actual_dispatch_running_cancellation_retains_until_exit(monkeypatch, cancellations):
    import asyncio
    import httpx
    from threading import Event, get_ident
    route, slot, app = _dispatch_setup(monkeypatch)
    entered, finish = Event(), Event()
    original = route.response_bytes
    main_thread = get_ident()
    def blocked(value):
        assert get_ident() != main_thread
        entered.set()
        assert finish.wait(5), "Worker finish gate was not released"
        return original(value)
    monkeypatch.setattr(route, "response_bytes", blocked)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
            request = asyncio.create_task(c.post("/hypothetical-risk", json=fixture()))
            try:
                await _eventually(entered.is_set)
                await _cancel(request, cancellations)
                assert slot.counts == (1, 0)
                assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 429
                assert slot.counts == (1, 0)
            finally:
                finish.set()
            await _eventually(slot.released.is_set)
            assert slot.counts == (1, 1)
            assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 200
            assert slot.counts == (2, 2)
    asyncio.run(scenario())


def test_actual_dispatch_cancel_before_owner_entry_revokes_late_callback(monkeypatch):
    import asyncio
    import httpx
    from threading import Event, Lock
    route, slot, app = _dispatch_setup(monkeypatch)
    entered, finish, exited = Event(), Event(), Event()
    guard = Lock(); first = True; calls = []
    original_compute, original_response = route._SlotOwner.compute, route.response_bytes
    def delayed_entry(owner, value):
        nonlocal first
        with guard:
            delay = first; first = False
        if not delay:
            return original_compute(owner, value)
        entered.set()
        try:
            assert finish.wait(5), "Late entry gate was not released"
            return original_compute(owner, value)
        finally:
            exited.set()
    def record(value):
        calls.append(value)
        return original_response(value)
    monkeypatch.setattr(route._SlotOwner, "compute", delayed_entry)
    monkeypatch.setattr(route, "response_bytes", record)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
            request = asyncio.create_task(c.post("/hypothetical-risk", json=fixture()))
            try:
                await _eventually(entered.is_set)  # Real thread, before owner claim.
                await _cancel(request, 3)
                assert slot.counts == (1, 1) and calls == []
                # Reuse while the old callback still exists: it must not compute
                # later or release this new request's slot.
                assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 200
                assert slot.counts == (2, 2) and len(calls) == 1
            finally:
                finish.set()
            await _eventually(exited.is_set)
            assert slot.counts == (2, 2) and len(calls) == 1
    asyncio.run(scenario())


def test_actual_dispatch_start_failure_releases_and_retry(monkeypatch):
    import asyncio
    import httpx
    from anyio._backends._asyncio import WorkerThread
    route, slot, app = _dispatch_setup(monkeypatch)
    original_start = WorkerThread.start
    first = True
    def fail_once(worker):
        nonlocal first
        if first:
            first = False
            raise RuntimeError("Synthetic actual worker-start failure")
        return original_start(worker)
    monkeypatch.setattr(WorkerThread, "start", fail_once)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
            with pytest.raises(RuntimeError, match="actual worker-start failure"):
                await c.post("/hypothetical-risk", json=fixture())
            assert slot.counts == (1, 1)
            assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 200
            assert slot.counts == (2, 2)
    asyncio.run(scenario())


def test_actual_dispatch_failure_after_start_preserves_running_owner(monkeypatch):
    import asyncio
    import httpx
    from threading import Event
    route, slot, app = _dispatch_setup(monkeypatch)
    entered, finish = Event(), Event()
    original_response, actual_dispatch = route.response_bytes, route.run_in_threadpool
    def blocked(value):
        entered.set()
        assert finish.wait(5), "Worker finish gate was not released"
        return original_response(value)
    async def fail_after_start(function, *args):
        dispatch = asyncio.create_task(actual_dispatch(function, *args))
        await _eventually(entered.is_set)
        await _cancel(dispatch, 3)
        raise RuntimeError("Synthetic failure after actual dispatch")
    monkeypatch.setattr(route, "response_bytes", blocked)
    monkeypatch.setattr(route, "run_in_threadpool", fail_after_start)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
            try:
                with pytest.raises(RuntimeError, match="after actual dispatch"):
                    await c.post("/hypothetical-risk", json=fixture())
                assert slot.counts == (1, 0)
                assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 429
            finally:
                finish.set()
            await _eventually(slot.released.is_set)
            assert slot.counts == (1, 1)
            monkeypatch.setattr(route, "run_in_threadpool", actual_dispatch)
            assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 200
            assert slot.counts == (2, 2)
    asyncio.run(scenario())


def test_actual_dispatch_completed_before_cancel_does_not_double_release(monkeypatch):
    import asyncio
    import httpx
    route, slot, app = _dispatch_setup(monkeypatch)
    actual_dispatch = route.run_in_threadpool

    async def scenario():
        completed, return_result = asyncio.Event(), asyncio.Event()
        async def pause_after_compute(function, *args):
            result = await actual_dispatch(function, *args)
            completed.set()
            await return_result.wait()
            return result
        monkeypatch.setattr(route, "run_in_threadpool", pause_after_compute)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
            request = asyncio.create_task(c.post("/hypothetical-risk", json=fixture()))
            await asyncio.wait_for(completed.wait(), 5)
            assert slot.counts == (1, 1)
            await _cancel(request, 3)
            assert slot.counts == (1, 1)
            monkeypatch.setattr(route, "run_in_threadpool", actual_dispatch)
            assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 200
            assert slot.counts == (2, 2)
    asyncio.run(scenario())


@pytest.mark.parametrize("error_type", [PortfolioRiskError, RuntimeError])
def test_actual_dispatch_worker_exception_releases_and_retry(monkeypatch, error_type):
    import asyncio
    import httpx
    from threading import get_ident
    route, slot, app = _dispatch_setup(monkeypatch)
    original = route.response_bytes
    first = True; main_thread = get_ident()
    def fail_once(value):
        nonlocal first
        assert get_ident() != main_thread
        if first:
            first = False
            raise error_type("Synthetic worker exception")
        return original(value)
    monkeypatch.setattr(route, "response_bytes", fail_once)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as c:
            if error_type is PortfolioRiskError:
                assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 422
            else:
                with pytest.raises(RuntimeError, match="Synthetic worker exception"):
                    await c.post("/hypothetical-risk", json=fixture())
            assert slot.counts == (1, 1)
            assert (await c.post("/hypothetical-risk", json=fixture())).status_code == 200
            assert slot.counts == (2, 2)
    asyncio.run(scenario())
