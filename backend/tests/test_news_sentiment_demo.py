"""Synthetic/private-native tests only. No original ZIP or live HTTP listener."""
import ctypes
from ctypes import wintypes as w
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import serve_news_sentiment_demo as demo


SCRIPT = Path(demo.__file__).resolve()


def command(code):
    # Windows venv python.exe is a process redirector, incompatible with the
    # required one-process job. Use its exact base interpreter for native probes.
    return [sys._base_executable, "-I", "-B", "-c", code]


def read_bytes(job, minimum=1, seconds=5.):
    end = time.monotonic() + seconds
    output = b""
    while len(output) < minimum and time.monotonic() < end:
        output += job.read_available()
        time.sleep(.01)
    assert len(output) >= minimum
    return output


def owner_line(owner, kernel, seconds=5.):
    """Bound the harness too; never wait indefinitely for controller stdout."""
    import msvcrt
    handle = msvcrt.get_osfhandle(owner.stdout.fileno())
    end, data = time.monotonic() + seconds, b""
    while b"\n" not in data and time.monotonic() < end:
        available = w.DWORD()
        if not kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
            break
        if available.value:
            data += owner.stdout.read(min(available.value, 64))
        else:
            time.sleep(.01)
    assert b"\n" in data
    return data.split(b"\n", 1)[0]


def test_native_atomic_gate_membership_limits_and_noninheritable_owner():
    job = demo.NativeJob()
    code = "import os,time; os.write(1,b'owned'); time.sleep(10)"
    try:
        job.spawn(command(code))
        assert read_bytes(job, 5) == b"owned"
        assert job.alive()
        member, flags = w.BOOL(), w.DWORD()
        assert job.win.k.IsProcessInJob(job.process, job.job, ctypes.byref(member)) and member.value
        assert job.win.k.GetHandleInformation(job.job, ctypes.byref(flags)) and not flags.value & 1
        assert job.limits() == {"flags": 0x2208, "active_processes": 1, "job_memory": 1 << 30}
    finally:
        job.stop()


@pytest.mark.parametrize("phase", ["startup", "inference"])
def test_native_atomic_gate_abrupt_parent_death_leaves_no_owned_child(phase):
    child = ("import os,time;os.write(1,b'startup');time.sleep(15)" if phase == "startup" else
             "import os,time;os.read(0,1);os.write(1,b'inference');time.sleep(15)")
    code = f'''
import sys,time
sys.path.insert(0,{str(SCRIPT.parents[1])!r})
from scripts.serve_news_sentiment_demo import NativeJob
j=NativeJob()
try:
 j.spawn({command(child)!r})
 if {phase!r}=='inference':j.write(b'x')
 end=time.monotonic()+5
 ready=b''
 while not ready and time.monotonic()<end:
  ready=j.read_available();time.sleep(.01)
 assert ready=={phase.encode()!r} and j.alive()
 print(j.pid,flush=True)
 time.sleep(15)
finally:j.stop()
'''
    owner = subprocess.Popen(command(code), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    process = None
    kernel = demo.Windows().k
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    try:
        pid = int(owner_line(owner, kernel))
        process = kernel.OpenProcess(0x100000, False, pid)
        assert process
        assert kernel.WaitForSingleObject(process, 0) == 258
        owner.kill()
        owner.wait(timeout=5)
        assert kernel.WaitForSingleObject(process, 5000) == 0
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.wait(timeout=5)
        if owner.stdout:
            owner.stdout.close()
        if process:
            kernel.CloseHandle(process)


def test_native_atomic_gate_only_allowlisted_handles_inherited():
    job = demo.NativeJob()
    k = job.win.k
    k.CreateEventW.argtypes = [ctypes.POINTER(demo.SecurityAttributes), w.BOOL, w.BOOL, w.LPCWSTR]
    k.CreateEventW.restype = w.HANDLE
    k.GetCurrentProcess.restype = w.HANDLE
    k.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE, ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
    k.DuplicateHandle.restype = w.BOOL
    compare = ctypes.WinDLL("api-ms-win-core-handle-l1-1-0", use_last_error=True).CompareObjectHandles
    compare.argtypes = [w.HANDLE, w.HANDLE]
    compare.restype = w.BOOL
    attributes = demo.SecurityAttributes(ctypes.sizeof(demo.SecurityAttributes), None, True)
    sentinel = k.CreateEventW(ctypes.byref(attributes), True, False, None)
    duplicate = w.HANDLE()
    assert sentinel
    try:
        job.spawn(command("import os,time;os.write(1,b'ready');time.sleep(10)"))
        assert read_bytes(job, 5) == b"ready"
        # Handle values can be reused in the child: compare kernel objects if a
        # coincidentally equal numeric handle exists, rather than assuming none.
        if k.DuplicateHandle(job.process, sentinel, k.GetCurrentProcess(), ctypes.byref(duplicate), 0, False, 2):
            assert not compare(sentinel, duplicate)
        if duplicate.value:
            k.CloseHandle(duplicate)
        duplicate = w.HANDLE()
        if k.DuplicateHandle(job.process, job.job, k.GetCurrentProcess(), ctypes.byref(duplicate), 0, False, 2):
            assert not compare(job.job, duplicate)
    finally:
        if duplicate.value:
            k.CloseHandle(duplicate)
        k.CloseHandle(sentinel)
        job.stop()


def test_native_atomic_gate_memory_and_active_process_limits_enforced():
    code = r'''
import ctypes,subprocess,sys,os,time
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong]
k.VirtualAlloc.restype=ctypes.c_void_p
p=k.VirtualAlloc(None,(1<<30)+65536,0x3000,4)
if p:raise AssertionError('memory limit not enforced')
try:subprocess.Popen([sys.executable,'-I','-B','-c','pass'])
except OSError:pass
else:raise AssertionError('active process limit not enforced')
os.write(1,b'limits');time.sleep(10)
'''
    job = demo.NativeJob()
    try:
        job.spawn(command(code))
        assert read_bytes(job, 6) == b"limits"
    finally:
        job.stop()


def test_native_atomic_gate_spawn_and_atomic_attachment_fail_closed(monkeypatch):
    job = demo.NativeJob()
    with pytest.raises(demo.DemoError, match="atomic_child_creation_failed"):
        job.spawn([r"C:\nonexistent-finlens-native-probe.exe"])
    assert not job.process and not job.job and not job.tx and not job.rx
    other = demo.NativeJob()
    monkeypatch.setattr(other, "_job_attribute", lambda: (w.HANDLE * 1)(0))
    try:
        with pytest.raises(demo.DemoError, match="atomic_(job_attribute|child_creation)_failed"):
            other.spawn(command("pass"))
        assert not other.process and not other.job
    finally:
        other.stop()


def test_native_atomic_gate_blocked_pipe_can_be_interrupted_without_harming_unrelated_process():
    import threading
    job = demo.NativeJob()
    unrelated = subprocess.Popen(command("import time;time.sleep(10)"), stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    errors = []

    def write_blocked():
        try:
            job.write(b"x" * 32772)
        except demo.DemoError as exc:
            errors.append(str(exc))

    try:
        job.spawn(command("import os,time;os.write(1,b'waiting');time.sleep(10)"))
        assert read_bytes(job, 7) == b"waiting"
        writer = threading.Thread(target=write_blocked, daemon=True)
        writer.start()
        time.sleep(.05)
        assert writer.is_alive()
        job.stop()
        writer.join(2)
        assert not writer.is_alive() and errors
        assert unrelated.poll() is None
    finally:
        job.stop()
        unrelated.terminate()
        unrelated.wait(timeout=5)


class FakeJob:
    """No process, file, socket or licensed source. Explicit synthetic protocol."""
    def __init__(self):
        self.rx_data = []
        self.sent = []
        self.process = True
        self._alive = True
        self.stopped = False

    def spawn(self, argv):
        self.argv = argv
        return self

    def write(self, data):
        value = demo.Frames().feed(data)[0]
        self.sent.append(value)
        if value["kind"] == "shutdown":
            self._alive = False

    def read_available(self):
        return self.rx_data.pop(0) if self.rx_data else b""

    def alive(self):
        return bool(self.process) and self._alive

    def stop(self, seconds=5):
        self.stopped = True
        self.process = None
        self._alive = False


async def started_owner(*, clock=time.monotonic):
    job = FakeJob()
    owner = demo.Supervisor("synthetic-no-file", factory=lambda: job, clock=clock, cleanup_seconds=.02)
    await owner.start()
    owner.monitor.cancel()
    try:
        await owner.monitor
    except asyncio.CancelledError:
        pass
    owner.monitor = None
    await owner.writer
    return owner, job


async def ready_owner(*, clock=time.monotonic):
    owner, job = await started_owner(clock=clock)
    for phase in demo.PHASES:
        await owner._receive(demo.message(owner.launch, 0, "phase", {"phase": phase}))
    await owner._receive(demo.message(owner.launch, 0, "ready",
        {"method": demo.METHOD_VERSION, "train_rows": 2071, "features": 6866}))
    return owner, job


@pytest.mark.parametrize("text", ["", " ", "x" * 2001, "x\ny", "x\ry", "x\x00y", "x\u200by", "x\u2028y", "x\ud800y"])
def test_sentence_bounds_and_controls(text):
    with pytest.raises(demo.DemoError, match="INVALID_INPUT"):
        demo.sentence({"text": text})


@pytest.mark.parametrize("payload", [[], None, {"text": 1}, {"text": True}, {"text": "ok", "extra": 1}])
def test_sentence_exact_schema(payload):
    with pytest.raises(demo.DemoError, match="INVALID_INPUT"):
        demo.sentence(payload)


def test_sentence_preserves_text_and_unicode_code_point_boundary():
    assert demo.sentence({"text": "  Authored café grows.  "}) == "  Authored café grows.  "
    assert len(demo.sentence({"text": chr(0x1F600) * 2000})) == 2000


@pytest.mark.parametrize("data", [b'{"text":"a","text":"b"}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'not json'])
def test_strict_json_never_echoes_bad_input(data):
    with pytest.raises(demo.DemoError, match="^INVALID_JSON$"):
        demo.strict_json(data)


def test_frames_incremental_bounds_and_multiple_messages():
    source = demo.message("a" * 32, 1, "result", {"label": "neutral"})
    data = demo.frame(source)
    decoder = demo.Frames()
    values = []
    for byte in data:
        values += decoder.feed(bytes([byte]))
    assert values == [source]
    assert not decoder.buffer and decoder.length is None
    assert demo.Frames().feed(data + data) == [source, source]
    with pytest.raises(demo.DemoError, match="IPC_FRAME_LIMIT"):
        demo.Frames().feed((demo.MAX_FRAME + 1).to_bytes(4, "big"))
    with pytest.raises(demo.DemoError, match="IPC_FRAME_LIMIT"):
        demo.Frames().feed(b"\0\0\0\0")


@pytest.mark.parametrize("change", [{"v": True}, {"v": 2}, {"launch": "other"}, {"request": True},
                                    {"request": -1}, {"payload": []}, {"extra": 1}])
def test_ipc_envelope_ownership_and_exact_schema(change):
    value = {**demo.message("a" * 32, 1, "result", {"label": "neutral"}), **change}
    with pytest.raises(demo.DemoError):
        demo.envelope(value, "a" * 32)


def test_lifecycle_ready_once_request_reuse_and_no_retraining():
    async def check():
        owner, job = await ready_owner()
        try:
            assert owner.state == "ready"
            for label in ("negative", "neutral", "positive"):
                task = asyncio.create_task(owner.classify("An authored synthetic news sentence."))
                await asyncio.sleep(0)
                await owner.writer
                job.rx_data.append(demo.frame(demo.message(owner.launch, owner.request, "result", {"label": label})))
                await owner.tick()
                value = await task
                assert value == {"label": label, "method_version": demo.METHOD_VERSION,
                                 "demo_version": demo.DEMO_VERSION, "model_run_id": owner.launch}
            assert [v["kind"] for v in job.sent] == ["init", "classify", "classify", "classify"]
        finally:
            await owner.shutdown()
        assert owner.state == "stopped" and job.stopped
    asyncio.run(check())


def test_cancelled_http_owner_keeps_slot_until_actual_response():
    async def check():
        owner, job = await ready_owner()
        task = asyncio.create_task(owner.classify("Synthetic pending statement."))
        await asyncio.sleep(0)
        await owner.writer
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(demo.DemoError, match="BUSY"):
            await owner.classify("Another synthetic statement.")
        assert owner.pending is not None
        job.rx_data.append(demo.frame(demo.message(owner.launch, owner.request, "result", {"label": "neutral"})))
        await owner.tick()
        assert owner.pending is None and owner.state == "ready"
        await owner.shutdown()
    asyncio.run(check())


def test_fragmented_result_keeps_ownership_until_complete_valid_batch():
    async def check():
        owner, job = await ready_owner()
        try:
            task = asyncio.create_task(owner.classify("Authored fragmented response."))
            await asyncio.sleep(0)
            await owner.writer
            data = demo.frame(demo.message(owner.launch, owner.request, "result", {"label": "neutral"}))
            job.rx_data.append(data[:5])
            await owner.tick()
            assert owner.pending is not None and not task.done() and owner.state == "ready"
            with pytest.raises(demo.DemoError, match="BUSY"):
                await owner.classify("Concurrent authored statement.")
            job.rx_data.append(data[5:])
            await owner.tick()
            assert (await task)["label"] == "neutral"
            assert owner.pending is None and owner.state == "ready"
        finally:
            await owner.shutdown()
    asyncio.run(check())


@pytest.mark.parametrize("fault", ["launch", "request", "duplicate", "label", "schema", "partial", "disconnect"])
def test_protocol_failure_is_terminal_and_closes_owned_worker(fault):
    async def check():
        now = [10.]
        owner, job = await ready_owner(clock=lambda: now[0])
        task = asyncio.create_task(owner.classify("Synthetic statement."))
        await asyncio.sleep(0)
        await owner.writer
        value = demo.message(owner.launch, owner.request, "result", {"label": "neutral"})
        if fault == "launch":
            value["launch"] = "0" * 32
        elif fault == "request":
            value["request"] += 1
        elif fault == "label":
            value["payload"]["label"] = "buy"
        elif fault == "schema":
            value["payload"]["text"] = "PRIVATE SENTINEL"
        data = demo.frame(value)
        if fault == "duplicate":
            data += data
        elif fault == "partial":
            data = data[:-1]
        elif fault == "disconnect":
            job.process = False
            data = b""
        job.rx_data.append(data)
        await owner.tick()
        if fault == "partial":
            assert owner.pending is not None
            now[0] += 3
            await owner.tick()
        with pytest.raises(demo.DemoError):
            await task
        assert owner.state == "failed" and job.stopped
        with pytest.raises(demo.DemoError, match="MODEL_NOT_READY"):
            await owner.classify("No automatic restart.")
    asyncio.run(check())


def test_late_response_never_becomes_success_and_no_respawn():
    async def check():
        now = [0.]
        owner, job = await ready_owner(clock=lambda: now[0])
        task = asyncio.create_task(owner.classify("Synthetic late statement."))
        await asyncio.sleep(0)
        await owner.writer
        now[0] = 2.
        job.rx_data.append(demo.frame(demo.message(owner.launch, owner.request, "result", {"label": "positive"})))
        await owner.tick()
        with pytest.raises(demo.DemoError, match="INFERENCE_TIMEOUT"):
            await task
        assert owner.state == "failed" and job.stopped
        assert sum(v["kind"] == "init" for v in job.sent) == 1
    asyncio.run(check())


def test_warmup_timeout_from_before_spawn_and_no_false_readiness():
    async def check():
        now = [0.]
        owner, job = await started_owner(clock=lambda: now[0])
        now[0] = 60.
        await owner.tick()
        assert owner.state == "failed" and owner.error == "WARMUP_TIMEOUT" and job.stopped
    asyncio.run(check())


def test_unsupported_features_is_recoverable_without_intercept_prediction():
    async def check():
        owner, job = await ready_owner()
        task = asyncio.create_task(owner.classify("Unfamiliar synthetic tokens."))
        await asyncio.sleep(0)
        await owner.writer
        job.rx_data.append(demo.frame(demo.message(owner.launch, owner.request, "unsupported", {"code": "UNSUPPORTED_FEATURES"})))
        await owner.tick()
        with pytest.raises(demo.DemoError, match="UNSUPPORTED_FEATURES"):
            await task
        assert owner.state == "ready" and owner.pending is None
        await owner.shutdown()
    asyncio.run(check())


def test_start_failure_and_cleanup_failure_do_not_claim_stopped():
    async def check():
        class Broken(FakeJob):
            def spawn(self, argv):
                raise demo.DemoError("PRIVATE NATIVE DIAGNOSTIC")
        owner = demo.Supervisor("synthetic", factory=Broken)
        await owner.start()
        assert owner.error == "STARTUP_FAILED" and owner.state == "failed"
        owner, job = await ready_owner()
        job.stop = lambda seconds: (_ for _ in ()).throw(demo.DemoError("child_exit_unverified"))
        assert not await owner.shutdown()
        assert owner.state == "failed" and owner.error == "CLEANUP_UNVERIFIED"
    asyncio.run(check())


async def http_client(owner, *, peer="127.0.0.1"):
    import httpx
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=demo.create_app(owner),
                              client=(peer, 12345), raise_app_exceptions=False),
                              base_url=f"http://127.0.0.1:{owner.port}")


def headers(owner):
    return {"X-FinLens-Demo-Token": owner.token, "Origin": f"http://127.0.0.1:{owner.port}",
            "Content-Type": "application/json"}


@pytest.mark.parametrize("fault", ["duplicate", "separate_read", "partial_extra", "wrong_request",
                                  "unexpected", "batch_limit", "terminal_before_http"])
def test_http_receive_batch_failure_never_returns_success(fault):
    async def check():
        owner, job = await ready_owner()
        admitted = asyncio.Event()
        original_send = owner._send
        def send(value):
            original_send(value)
            admitted.set()
        owner._send = send
        try:
            async with await http_client(owner) as client:
                response_task = asyncio.create_task(client.post("/api/classify", headers=headers(owner),
                                                                json={"text": "Authored synthetic news."}))
                await asyncio.wait_for(admitted.wait(), 1.)
                await owner.writer
                value = demo.message(owner.launch, owner.request, "result", {"label": "neutral"})
                data = demo.frame(value)
                if fault == "separate_read":
                    job.rx_data.extend([data, data])
                elif fault == "partial_extra":
                    job.rx_data.append(data + data[:5])
                elif fault == "wrong_request":
                    job.rx_data.append(data + demo.frame({**value, "request": owner.request + 1}))
                elif fault == "unexpected":
                    job.rx_data.append(data + demo.frame(demo.message(owner.launch, 0, "phase", {"phase": "fitting"})))
                elif fault == "batch_limit":
                    # Eight nonempty reads exhaust the finite validation budget.
                    job.rx_data.extend([data[index:index + 1] for index in range(7)] + [data[7:]])
                elif fault == "terminal_before_http":
                    job.rx_data.append(data)
                else:
                    job.rx_data.append(data + data)
                await owner.tick()
                if fault == "terminal_before_http":
                    # Fail after future settlement but before the HTTP continuation.
                    await owner.fail("WORKER_PROTOCOL_FAILED")
                response = await asyncio.wait_for(response_task, 1.)
                assert response.status_code == 503
                assert response.json() == {"error": "WORKER_PROTOCOL_FAILED"}
                assert owner.state == "failed" and job.stopped and owner.pending is None
                assert sum(item["kind"] == "init" for item in job.sent) == 1
        finally:
            await owner.shutdown()
    asyncio.run(check())


def test_http_routes_security_headers_and_sanitized_input(capsys):
    async def check():
        owner = demo.Supervisor("synthetic-no-read")
        client = await http_client(owner)
        async with client:
            response = await client.get("/")
            assert response.status_code == 200 and owner.token in response.text
            assert "__NONCE__" not in response.text and "__TOKEN__" not in response.text
            for name in ("cache-control", "content-security-policy", "referrer-policy", "x-frame-options"):
                assert name in response.headers
            assert "access-control-allow-origin" not in response.headers
            assert (await client.get("/api/status", headers=headers(owner))).json()["state"] == "starting"
            bad = await client.post("/api/classify", headers=headers(owner), json={"text": "PRIVATE\nSENTINEL"})
            assert bad.status_code == 400 and bad.json() == {"error": "INVALID_INPUT"}
            assert "PRIVATE" not in bad.text
            unavailable = await client.post("/api/classify", headers=headers(owner), json={"text": "Synthetic valid input."})
            assert unavailable.status_code == 503
            for route in ("/docs", "/redoc", "/openapi.json", "/other", "/?token=secret"):
                assert (await client.get(route, headers=headers(owner))).status_code == 404
    asyncio.run(check())
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("case", ["peer", "host", "origin", "token", "duplicate_host", "duplicate_origin",
                                  "duplicate_token", "duplicate_length", "content_type", "method", "body_limit"])
def test_http_rejects_invalid_authority_origin_token_and_bounds(case):
    async def check():
        owner = demo.Supervisor("synthetic")
        client = await http_client(owner, peer="10.0.0.1" if case == "peer" else "127.0.0.1")
        values = list(headers(owner).items())
        if case == "host":
            values.append(("Host", "localhost:8765"))
        elif case == "origin":
            values = [(k, "http://evil.invalid" if k == "Origin" else v) for k, v in values]
        elif case == "token":
            values = [(k, "wrong" if k == "X-FinLens-Demo-Token" else v) for k, v in values]
        elif case.startswith("duplicate_"):
            key = {"duplicate_host": "Host", "duplicate_origin": "Origin",
                   "duplicate_token": "X-FinLens-Demo-Token", "duplicate_length": "Content-Length"}[case]
            values = [(k, v) for k, v in values if k.lower() != key.lower()]
            values.extend([(key, "same"), (key, "same")])
        elif case == "content_type":
            values = [(k, "text/plain" if k == "Content-Type" else v) for k, v in values]
        elif case == "body_limit":
            values.append(("Content-Length", str(demo.MAX_BODY + 1)))
        async with client:
            response = await client.request("GET" if case == "method" else "POST", "/api/classify",
                                            headers=values, content=b'{"text":"synthetic"}')
            assert response.status_code in {400, 403, 405, 413, 415}
            assert "synthetic" not in response.text and "wrong" not in response.text
    asyncio.run(check())


def test_http_json_schema_errors_and_exception_payloads_are_sanitized():
    async def check():
        owner = demo.Supervisor("synthetic")
        async with await http_client(owner) as client:
            for data in [b'{"text":"PRIVATE","text":"SECOND"}', b'{"text":NaN}', b'[]', b'{}', b'\xff']:
                response = await client.post("/api/classify", headers=headers(owner), content=data)
                assert response.status_code == 400
                assert not any(word in response.text for word in ("PRIVATE", "SECOND", "NaN"))
            async def crash(_text):
                raise RuntimeError("PRIVATE INPUT AND TOKEN")
            owner.classify = crash
            response = await client.post("/api/classify", headers=headers(owner), json={"text": "Authored news sentence."})
            assert response.status_code == 503 and response.json() == {"error": "UNAVAILABLE"}
            from starlette.exceptions import HTTPException
            async def http_crash(_text):
                raise HTTPException(422, detail="PRIVATE HTTP VALIDATION DATA")
            owner.classify = http_crash
            response = await client.post("/api/classify", headers=headers(owner), json={"text": "Authored news sentence."})
            assert response.status_code == 400 and response.json() == {"error": "INVALID_REQUEST"}
    asyncio.run(check())


def test_http_success_returns_no_sentence_or_confidence_and_shutdown_verifies():
    async def check():
        owner, job = await ready_owner()
        async def answer(text):
            assert text == "Authored positive news."
            return {"label": "positive", "method_version": demo.METHOD_VERSION,
                    "demo_version": demo.DEMO_VERSION, "model_run_id": owner.launch}
        owner.classify = answer
        async with await http_client(owner) as client:
            response = await client.post("/api/classify", headers=headers(owner), json={"text": "Authored positive news."})
            assert set(response.json()) == {"label", "method_version", "demo_version", "model_run_id"}
            response = await client.post("/api/shutdown", headers=headers(owner), json={})
            assert response.status_code == 202 and owner.state == "stopped" and job.stopped
    asyncio.run(check())


def test_http_stream_body_deadline_and_no_websocket(monkeypatch):
    async def check():
        owner = demo.Supervisor("synthetic")
        app = demo.create_app(owner)
        replies = []
        async def send(item):
            replies.append(item)
        async def receive():
            await asyncio.sleep(1)
            return {"type": "http.request", "body": b"{}", "more_body": False}
        scope = {"type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
                 "path": "/api/classify", "raw_path": b"/api/classify", "query_string": b"",
                 "headers": [(b"host", b"127.0.0.1:8765"), *[(k.lower().encode(), v.encode()) for k, v in headers(owner).items()]],
                 "client": ("127.0.0.1", 1234), "server": ("127.0.0.1", 8765), "root_path": ""}
        await app(scope, receive, send)
        assert replies[0]["status"] == 408
        assert json.loads(replies[-1]["body"]) == {"error": "BODY_TIMEOUT"}
        replies.clear()
        await app({"type": "websocket"}, receive, send)
        assert replies == [{"type": "websocket.close", "code": 1008}]
    monkeypatch.setattr(demo, "BODY_READ_SECONDS", .01)
    asyncio.run(check())


def test_no_import_time_app_or_worker_and_no_public_host_flag(capsys):
    with patch.object(demo, "Supervisor", side_effect=AssertionError("must not start")):
        assert demo.main(["--zip", "PRIVATE PATH", "--host", "0.0.0.0"]) == 2
    captured = capsys.readouterr()
    assert "PRIVATE" not in captured.out and "0.0.0.0" not in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("fault", [None, "source", "groups", "split", "features"])
def test_preparation_uses_only_original_train_indices_and_fixed_c(monkeypatch, fault):
    from contextlib import nullcontext
    news = demo.news_module()
    rows = tuple(news.Row("invented " + label, label)
                 for label, count in zip(news.LABELS, (420, 2146, 887)) for _ in range(count))
    train = list(range(252)) + list(range(420, 1707)) + list(range(2566, 3098))
    assert len(train) == 2071
    grouping = SimpleNamespace(audit={"groups": 1 if fault == "groups" else 3349,
                        "nonsingleton_groups": 76, "rows_in_nonsingleton_groups": 180})
    vectorizer = SimpleNamespace(vocabulary_=dict.fromkeys(range(1 if fault == "features" else 6866)))
    classifier = object()
    ml = SimpleNamespace(thread_limit=lambda **kwargs: nullcontext(), convergence_warning=Warning)
    calls, phases = [], []
    monkeypatch.setattr(news, "local_zip_bytes", lambda path: b"synthetic")
    monkeypatch.setattr(news, "read_archive", lambda data: rows[:-1] if fault == "source" else rows)
    monkeypatch.setattr(news, "group_rows", lambda source: grouping)
    monkeypatch.setattr(news, "load_ml", lambda: ml)
    monkeypatch.setattr(news, "make_split", lambda *args: ({"train": train}, "wrong" if fault == "split" else news.REFERENCE_SPLIT))
    def fit_features(source, ids, dependencies):
        assert source is rows and ids == train and dependencies is ml
        calls.append("features")
        return vectorizer, "synthetic-matrix", "synthetic-labels"
    def fit_classifier(matrix, labels, dependencies, c):
        assert (matrix, labels, dependencies, c) == ("synthetic-matrix", "synthetic-labels", ml, 10.)
        calls.append("classifier")
        return classifier
    monkeypatch.setattr(news, "fit_training_features", fit_features)
    monkeypatch.setattr(news, "fit_linear_classifier", fit_classifier)
    monkeypatch.setattr(news, "evaluate", lambda *args: pytest.fail("must not tune or evaluate holdouts"))
    if fault:
        with pytest.raises(news.ExperimentError):
            demo.prepare_model("synthetic-only", phases.append)
        assert not calls or fault == "features"
    else:
        assert demo.prepare_model("synthetic-only", phases.append) == (vectorizer, classifier, ml)
        assert calls == ["features", "classifier"] and phases == list(demo.PHASES)


def test_zero_features_never_call_classifier_and_valid_label_is_checked():
    vector = SimpleNamespace(transform=lambda texts: SimpleNamespace(nnz=0))
    classifier = SimpleNamespace(predict=lambda matrix: pytest.fail("intercept-only prediction forbidden"))
    assert demo.predict_label(vector, classifier, "Unfamiliar authored words.") is None
    vector.transform = lambda texts: SimpleNamespace(nnz=1)
    classifier.predict = lambda matrix: ["neutral"]
    assert demo.predict_label(vector, classifier, "Known synthetic words.") == "neutral"
    classifier.predict = lambda matrix: ["investment advice"]
    with pytest.raises(demo.DemoError, match="INVALID_MODEL_RESULT"):
        demo.predict_label(vector, classifier, "Known synthetic words.")


def fake_worker_command(*, block_prediction=False, bootstrap=False):
    code = f'''
import sys,time
from types import SimpleNamespace
from contextlib import nullcontext
sys.path.insert(0,{str(SCRIPT.parents[1])!r})
from scripts import serve_news_sentiment_demo as d
class V:
 def transform(self,texts):return SimpleNamespace(nnz=0 if texts==['unknown'] else 1)
class C:
 def predict(self,matrix):
  if {block_prediction!r}:time.sleep(15)
  return ['neutral']
def prepare(path,progress):
 for phase in d.PHASES:progress(phase)
 ml=d.news_module().load_ml() if {bootstrap!r} else SimpleNamespace(thread_limit=lambda **kwargs:nullcontext())
 return V(),C(),ml
d.prepare_model=prepare
raise SystemExit(d.worker_main({str(Path(sys.prefix)/'Lib'/'site-packages')!r}))
'''
    return command(code)


@pytest.mark.parametrize("mode", ["normal", "bootstrap", "warmup_timeout", "inference_timeout"])
def test_native_supervisor_deadlines_and_synthetic_worker_protocol(mode):
    async def check():
        class SyntheticNative(demo.NativeJob):
            def spawn(self, _argv):
                argv = command("import time;time.sleep(15)") if mode == "warmup_timeout" else fake_worker_command(block_prediction=mode == "inference_timeout", bootstrap=mode == "bootstrap")
                return super().spawn(argv)
        owner = demo.Supervisor("synthetic-no-file", factory=SyntheticNative,
                                warmup_seconds=.1 if mode == "warmup_timeout" else 5.,
                                inference_seconds=.1, cleanup_seconds=2.)
        try:
            await owner.start()
            end = time.monotonic() + 6
            while owner.state == "starting" and time.monotonic() < end:
                await asyncio.sleep(.01)
            if mode == "warmup_timeout":
                assert owner.state == "failed" and owner.error == "WARMUP_TIMEOUT"
                if owner.cleanup:
                    await owner.cleanup
                assert not owner.native.process
                return
            assert owner.state == "ready", owner.status()
            if mode == "inference_timeout":
                with pytest.raises(demo.DemoError, match="INFERENCE_TIMEOUT"):
                    await owner.classify("Authored harmless probe.")
                if owner.cleanup:
                    await owner.cleanup
                assert owner.state == "failed" and not owner.native.process
            else:
                assert (await owner.classify("Authored harmless probe."))["label"] == "neutral"
                with pytest.raises(demo.DemoError, match="UNSUPPORTED_FEATURES"):
                    await owner.classify("unknown")
                assert owner.state == "ready"
        finally:
            await owner.shutdown()
        assert owner.state == "stopped" and not owner.native.process
    asyncio.run(asyncio.wait_for(check(), 10.))


def test_concurrent_shutdown_is_idempotent_and_no_worker_queue():
    async def check():
        owner, job = await ready_owner()
        assert await asyncio.gather(owner.shutdown(), owner.shutdown()) == [True, True]
        assert sum(item["kind"] == "shutdown" for item in job.sent) == 1
    asyncio.run(check())


def test_slot_is_not_released_before_both_ipc_directions_complete():
    async def check():
        owner, job = await ready_owner()
        task = asyncio.create_task(owner.classify("Authored synthetic statement."))
        await asyncio.sleep(0)
        await owner.writer
        owner.writer = asyncio.create_task(asyncio.sleep(.03))
        job.rx_data.append(demo.frame(demo.message(owner.launch, owner.request, "result", {"label": "neutral"})))
        response = asyncio.create_task(owner.tick())
        await asyncio.sleep(.005)
        assert owner.pending is not None and not task.done()
        with pytest.raises(demo.DemoError, match="BUSY"):
            await owner.classify("Another authored statement.")
        await response
        assert (await task)["label"] == "neutral" and owner.pending is None
        await owner.shutdown()
    asyncio.run(check())


def test_guarded_parent_imports_and_async_threads_need_no_server_or_writes():
    code = f'''
import sys,asyncio,logging
sys.path.insert(0,{str(Path(sys.prefix)/'Lib'/'site-packages')!r})
sys.path.insert(0,{str(SCRIPT.parents[1])!r})
from scripts import serve_news_sentiment_demo as d
import uvicorn
owner=d.Supervisor('synthetic-no-file')
app=d.create_app(owner)
loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
sys.addaudithook(d.supervisor_audit(8765))
config=uvicorn.Config(app,access_log=False,log_config=None,proxy_headers=False,ws='none',http='h11')
config.load()
assert loop.run_until_complete(asyncio.to_thread(lambda:42))==42
loop.run_until_complete(loop.shutdown_default_executor(timeout=2));loop.close()
print('guarded_parent_bootstrap_ok')
'''
    result = subprocess.run(command(code), capture_output=True, text=True, timeout=8,
                            creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "guarded_parent_bootstrap_ok" and result.stderr == ""


def test_supervisor_audit_blocks_outbound_and_writes_without_widening_original_hook():
    guard = demo.supervisor_audit(8765)
    guard("socket.bind", (None, ("127.0.0.1", 8765)))
    guard("socket.__new__", ())
    for event, args in [("socket.bind", (None, ("0.0.0.0", 8765))),
                        ("socket.connect", (None, ("127.0.0.1", 5432))),
                        ("socket.getaddrinfo", ("remote.invalid",)),
                        ("open", ("synthetic-output", "wb", os.O_WRONLY)),
                        ("import", ("app.database",)), ("subprocess.Popen", ())]:
        with pytest.raises((demo.DemoError, demo.news_module().ExperimentError)):
            guard(event, args)


@pytest.mark.parametrize("confirm_shutdown", [True, False])
def test_ui_dom_readiness_results_clear_stale_and_verified_shutdown(confirm_shutdown):
    # jsdom is already installed for FinLens. This is an in-memory DOM test,
    # not browser acceptance; fetch is stubbed and no resource loader is enabled.
    ui = SCRIPT.with_name("news_sentiment_demo.html")
    jsdom = SCRIPT.parents[2] / "frontend" / "node_modules" / "jsdom"
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.argv[2]);
const html=fs.readFileSync(process.argv[1],'utf8').replaceAll('__NONCE__','synthetic').replaceAll('__TOKEN__','test-token');
const dom=new JSDOM(html,{runScripts:'outside-only',url:'http://127.0.0.1:8765/'}),win=dom.window;
let remote='starting',pending=null,hold=false;const requests=[],confirmShutdown=process.argv[3]==='yes';
const response=(value,ok=true)=>({ok,json:async()=>value});
win.fetch=async(path,options)=>{requests.push([path,options]);if(path==='/api/status'){if(remote==='stopped'&&!confirmShutdown)throw new TypeError('synthetic disconnect');return response({state:remote,phase:'fitting',elapsed_seconds:1,model_run_id:'run-a',method_version:'news-sentiment-tfidf-svc-v1',demo_version:'private-news-sentiment-demo-v1'});}if(path==='/api/shutdown'){remote='stopped';return response({state:'stopping'});}if(hold)return new Promise(resolve=>pending=resolve);return response({label:'positive',method_version:'news-sentiment-tfidf-svc-v1',model_run_id:'run-a'});};
win.Storage.prototype.setItem=()=>{throw Error('storage forbidden')};
const code=html.match(/<script nonce="synthetic">([\s\S]*?)<\/script>/)[1];
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));const get=id=>win.document.getElementById(id);
(async()=>{win.eval(code+'\nwindow.__testPoll=poll;');await sleep(10);assert.equal(get('sentence').disabled,true);
remote='ready';await win.__testPoll();assert.equal(get('sentence').disabled,false);
get('sentence').value='An invented company improves its results.';get('sentence').dispatchEvent(new win.Event('input'));get('classify').click();await sleep(10);assert.equal(get('label').textContent,'Positive');
get('clear').click();assert.equal(get('sentence').value,'');assert.equal(get('label').textContent,'');assert.equal(get('result').hidden,true);
hold=true;get('sentence').value='Authored pending statement.';get('sentence').dispatchEvent(new win.Event('input'));get('classify').click();await sleep(5);assert.ok(pending);get('clear').click();pending(response({label:'negative',method_version:'news-sentiment-tfidf-svc-v1',model_run_id:'run-a'}));await sleep(10);assert.equal(get('label').textContent,'');
get('sentence').value='Authored stale result.';get('sentence').dispatchEvent(new win.Event('input'));get('classify').click();await sleep(5);remote='failed';await win.__testPoll();pending(response({label:'positive',method_version:'news-sentiment-tfidf-svc-v1',model_run_id:'run-a'}));await sleep(10);assert.equal(get('label').textContent,'');remote='ready';await win.__testPoll();
hold=false;get('sentence').value='Sensitive authored input.';get('sentence').dispatchEvent(new win.Event('input'));get('stop').click();assert.equal(get('sentence').value,'');await sleep(460);assert.match(get('status').textContent,confirmShutdown?/Demo stopped/:/Ctrl\+C/);assert.equal(get('classify').disabled,true);
assert.ok(requests.every(([path,options])=>path.startsWith('/api/')&&options.cache==='no-store'&&options.credentials==='omit'));assert.equal(win.document.cookie,'');console.log('synthetic_dom_ok');win.close();})().catch(error=>{console.error(error);win.close();process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", script, str(ui), str(jsdom), "yes" if confirm_shutdown else "no"],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "synthetic_dom_ok" and result.stderr == ""


@pytest.mark.parametrize("late", ["ready", "rejected"])
@pytest.mark.parametrize("boundary", ["confirmed_stop", "unverified_stop", "navigation", "navigation_ready"])
def test_ui_status_poll_cannot_overwrite_confirmed_stop(late, boundary):
    ui = SCRIPT.with_name("news_sentiment_demo.html")
    jsdom = SCRIPT.parents[2] / "frontend" / "node_modules" / "jsdom"
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.argv[2]);
const html=fs.readFileSync(process.argv[1],'utf8').replaceAll('__NONCE__','synthetic').replaceAll('__TOKEN__','test-token');
const dom=new JSDOM(html,{runScripts:'outside-only',url:'http://127.0.0.1:8765/'}),win=dom.window;
const get=id=>win.document.getElementById(id),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const status=state=>({state,model_run_id:'run-a',method_version:'news-sentiment-tfidf-svc-v1',demo_version:'private-news-sentiment-demo-v1'});
const response=value=>({ok:true,json:async()=>value});
let held=false,resolveOld,rejectOld,oldSignal,stopped=false;
const boundary=process.argv[4];
const navigating=boundary.startsWith('navigation');
win.fetch=async(path,options)=>{
 if(path==='/api/shutdown'){stopped=true;return response({state:'stopping'});}
 assert.equal(path,'/api/status');
 if(held){held=false;oldSignal=options.signal;return new Promise((resolve,reject)=>{resolveOld=resolve;rejectOld=reject;});}
 if(stopped&&boundary==='unverified_stop')throw new TypeError('shutdown unverified');
 return response(status(stopped?'stopped':boundary==='navigation'?'starting':'ready'));
};
const code=html.match(/<script nonce="synthetic">([\s\S]*?)<\/script>/)[1];
(async()=>{win.eval(code+'\nwindow.__testPoll=poll;');await sleep(10);
 held=true;const oldPoll=win.__testPoll();assert.ok(resolveOld);get('sentence').value='Private authored text';
 if(navigating){
   win.dispatchEvent(new win.PageTransitionEvent('pagehide'));
   assert.equal(oldSignal.aborted,true);
   win.dispatchEvent(new win.PageTransitionEvent('pageshow',{persisted:true}));await sleep(10);
 }else{assert.equal(get('sentence').disabled,false);get('stop').click();assert.equal(oldSignal.aborted,true);await sleep(460);}
 const stoppedText=get('status').textContent;
 assert.match(stoppedText,boundary==='confirmed_stop'?/Demo stopped/:boundary==='unverified_stop'?/Ctrl\+C/:boundary==='navigation_ready'?/Model ready/:/60s budget/);
 // The stub intentionally ignores abort so ownership must guard both continuations.
 if(process.argv[3]==='ready')resolveOld(response(status('ready')));else rejectOld(new TypeError('late failure'));
 await oldPoll;await sleep(10);
 assert.equal(get('status').textContent,stoppedText);assert.equal(oldSignal.aborted,true);
 assert.equal(get('sentence').disabled,boundary!=='navigation_ready');assert.equal(get('classify').disabled,true);
 if(!navigating)assert.equal(get('stop').disabled,true);
 assert.equal(get('sentence').value,'');assert.equal(get('label').textContent,'');assert.equal(get('result').hidden,true);
 console.log('stale_status_guard_ok');win.close();
})().catch(error=>{console.error(error);win.close();process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", script, str(ui), str(jsdom), late, boundary],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "stale_status_guard_ok" and result.stderr == ""


@pytest.mark.parametrize("outcome", ["confirmed", "uncertain", "pending"])
@pytest.mark.parametrize("late", ["ready", "rejected"])
def test_ui_terminal_stop_survives_persisted_navigation(outcome, late):
    ui = SCRIPT.with_name("news_sentiment_demo.html")
    jsdom = SCRIPT.parents[2] / "frontend" / "node_modules" / "jsdom"
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require(process.argv[2]);
const html=fs.readFileSync(process.argv[1],'utf8').replaceAll('__NONCE__','synthetic').replaceAll('__TOKEN__','test-token');
const dom=new JSDOM(html,{runScripts:'outside-only',url:'http://127.0.0.1:8765/'}),win=dom.window;
const get=id=>win.document.getElementById(id),outcome=process.argv[3],late=process.argv[4];
let now=0,nextTimer=0;const timers=new Map(),requests=[];
win.setTimeout=(callback,delay=0)=>{const id=++nextTimer;timers.set(id,{at:now+delay,callback});return id;};
win.clearTimeout=id=>timers.delete(id);
Object.defineProperty(win.performance,'now',{value:()=>now});
const flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
async function advance(ms){const target=now+ms;for(let i=0;i<100;i++){
 await flush();const entry=[...timers].filter(([,timer])=>timer.at<=target).sort((a,b)=>a[1].at-b[1].at)[0];
 if(!entry){now=target;await flush();return;}const [id,timer]=entry;now=timer.at;timers.delete(id);timer.callback();
}throw Error('fake timer budget exceeded');}
const response=value=>({ok:true,json:async()=>value});
const status=state=>({state,phase:'fitting',elapsed_seconds:1,model_run_id:'run-a',method_version:'news-sentiment-tfidf-svc-v1',demo_version:'private-news-sentiment-demo-v1'});
let hold=false,resolveOld,rejectOld,oldSignal,shutdown=false,resolveShutdown;
win.fetch=async(path,options)=>{requests.push(path);
 if(path==='/api/shutdown'){shutdown=true;if(outcome==='pending')return new Promise(resolve=>resolveShutdown=resolve);return response({state:'stopping'});}
 assert.equal(path,'/api/status');
 if(hold){hold=false;oldSignal=options.signal;return new Promise((resolve,reject)=>{resolveOld=resolve;rejectOld=reject;});}
 if(shutdown){if(outcome==='confirmed')return response(status('stopped'));throw new TypeError('synthetic disconnect');}
 return response(status('ready'));
};
win.Storage.prototype.setItem=()=>{throw Error('storage forbidden');};
const code=html.match(/<script nonce="synthetic">([\s\S]*?)<\/script>/)[1];
(async()=>{win.eval(code+'\nwindow.__testPoll=poll;');await flush();assert.equal(get('sentence').disabled,false);
 hold=true;const oldPoll=win.__testPoll();await flush();assert.ok(resolveOld);
 get('sentence').value='Private authored sentence';get('sentence').dispatchEvent(new win.Event('input'));
 get('label').textContent='Positive';get('result').hidden=false;get('stop').click();await advance(400);
 const terminalText=get('status').textContent;
 assert.match(terminalText,outcome==='confirmed'?/Demo stopped/:outcome==='uncertain'?/Ctrl\+C/:/Stopping/);
 assert.equal(oldSignal.aborted,true);const statusCount=requests.filter(path=>path==='/api/status').length;
 win.dispatchEvent(new win.PageTransitionEvent('pagehide'));
 win.dispatchEvent(new win.PageTransitionEvent('pageshow',{persisted:true}));
 await advance(1100);
 assert.equal(requests.filter(path=>path==='/api/status').length,statusCount,'restoration must initiate zero status polls');
 assert.equal(get('status').textContent,terminalText);
 // An abort-insensitive old request must stay obsolete after restoration.
 if(late==='ready')resolveOld(response(status('ready')));else rejectOld(new TypeError('late failure'));
 await oldPoll;await flush();assert.equal(get('status').textContent,terminalText);
 if(outcome==='pending'){
   resolveShutdown(response({state:'stopping'}));await advance(400);
   assert.match(get('status').textContent,/Ctrl\+C/);
 }
 const finalText=get('status').textContent,finalCount=requests.filter(path=>path==='/api/status').length;
 win.dispatchEvent(new win.PageTransitionEvent('pagehide'));
 win.dispatchEvent(new win.PageTransitionEvent('pageshow',{persisted:true}));await advance(1100);
 assert.equal(requests.filter(path=>path==='/api/status').length,finalCount);assert.equal(get('status').textContent,finalText);
 assert.equal(get('sentence').disabled,true);assert.equal(get('classify').disabled,true);assert.equal(get('stop').disabled,true);
 assert.equal(get('sentence').value,'');assert.equal(get('label').textContent,'');assert.equal(get('result').hidden,true);
 console.log('terminal_navigation_ok');win.close();
})().catch(error=>{console.error(error);win.close();process.exitCode=1;});
'''
    result = subprocess.run(["node", "-e", script, str(ui), str(jsdom), outcome, late],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "terminal_navigation_ok" and result.stderr == ""


def test_minimal_child_environment_has_no_inherited_credentials(monkeypatch):
    monkeypatch.setenv("SYNTHETIC_PRIVATE_CREDENTIAL", "never-forward-this")
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "99")
    values = demo.NativeJob.minimal_environment()
    assert set(values) == {"SystemRoot", "WINDIR", "PATH", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                           "MKL_NUM_THREADS", "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"}
    assert values["OPENBLAS_NUM_THREADS"] == "1"
    assert "never-forward-this" not in values.values()
