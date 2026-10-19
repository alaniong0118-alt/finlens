"""Private local demonstration. Importing this module starts nothing."""
import sys

sys.dont_write_bytecode = True

import ctypes
from ctypes import wintypes as w
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import unicodedata
import warnings


class DemoError(ValueError):
    """Safe code only; never include input, paths, tokens or native diagnostics."""


def ensure(condition, code):
    if not condition:
        raise DemoError(code)


SIZE = ctypes.c_size_t
HANDLE = w.HANDLE


class SecurityAttributes(ctypes.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", w.BOOL)]


class BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", w.DWORD), ("min_working_set", SIZE), ("max_working_set", SIZE),
                ("active_processes", w.DWORD), ("affinity", SIZE),
                ("priority", w.DWORD), ("scheduling", w.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters), ("process_memory", SIZE),
                ("job_memory", SIZE), ("peak_process_memory", SIZE), ("peak_job_memory", SIZE)]


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR),
                ("title", w.LPWSTR), *[(n, w.DWORD) for n in
                ("x", "y", "x_size", "y_size", "x_chars", "y_chars", "fill", "flags")],
                ("show", w.WORD), ("reserved_size", w.WORD), ("reserved_bytes", ctypes.c_void_p),
                ("stdin", HANDLE), ("stdout", HANDLE), ("stderr", HANDLE)]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [("startup", StartupInfo), ("attributes", ctypes.c_void_p)]


class ProcessInformation(ctypes.Structure):
    _fields_ = [("process", HANDLE), ("thread", HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


class Windows:
    """Only documented kernel APIs; no post-creation job assignment path."""
    def __init__(self):
        ensure(os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8, "unsupported_windows")
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], HANDLE),
            "SetInformationJobObject": ([HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "QueryInformationJobObject": ([HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p], w.BOOL),
            "CreatePipe": ([ctypes.POINTER(HANDLE), ctypes.POINTER(HANDLE), ctypes.POINTER(SecurityAttributes), w.DWORD], w.BOOL),
            "SetHandleInformation": ([HANDLE, w.DWORD, w.DWORD], w.BOOL),
            "GetHandleInformation": ([HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "CreateFileW": ([w.LPCWSTR, w.DWORD, w.DWORD, ctypes.POINTER(SecurityAttributes), w.DWORD, w.DWORD, HANDLE], HANDLE),
            "InitializeProcThreadAttributeList": ([ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(SIZE)], w.BOOL),
            "UpdateProcThreadAttribute": ([ctypes.c_void_p, w.DWORD, SIZE, ctypes.c_void_p, SIZE, ctypes.c_void_p, ctypes.c_void_p], w.BOOL),
            "DeleteProcThreadAttributeList": ([ctypes.c_void_p], None),
            "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
                                w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(StartupInfoEx),
                                ctypes.POINTER(ProcessInformation)], w.BOOL),
            "CloseHandle": ([HANDLE], w.BOOL),
            "TerminateJobObject": ([HANDLE, w.UINT], w.BOOL),
            "WaitForSingleObject": ([HANDLE, w.DWORD], w.DWORD),
            "IsProcessInJob": ([HANDLE, HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL),
            "PeekNamedPipe": ([HANDLE, ctypes.c_void_p, w.DWORD, ctypes.c_void_p,
                               ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
            "ReadFile": ([HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
            "WriteFile": ([HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
            "CancelIoEx": ([HANDLE, ctypes.c_void_p], w.BOOL),
        }
        try:
            for name, (args, result) in signatures.items():
                fn = getattr(self.k, name)
                fn.argtypes, fn.restype = args, result
        except AttributeError:
            raise DemoError("atomic_job_api_unavailable") from None

    def check(self, result, code="native_operation_failed"):
        ensure(bool(result), code)
        return result

    def close(self, handle):
        if handle:
            self.k.CloseHandle(handle)


class NativeJob:
    """CreateProcess JOB_LIST + HANDLE_LIST attach ownership atomically.

    Windows 10+ nested-job compatibility is verified by creation itself. The
    unnamed non-inheritable job handle stays exclusively in this parent.
    """
    FLAGS = 0x2000 | 0x200 | 0x8  # kill-on-close, JOB memory, active processes
    MEMORY = 1 << 30

    def __init__(self):
        self.win = Windows()
        self.job = self.process = self.tx = self.rx = None
        self.pid = None

    def _job_attribute(self):
        return (HANDLE * 1)(self.job)

    @staticmethod
    def minimal_environment():
        root = os.environ.get("SystemRoot", r"C:\Windows")
        return {"SystemRoot": root, "WINDIR": root,
                "PATH": str(Path(sys._base_executable).parent) + ";" + root + r"\System32",
                # Bound native initialization too: threadpoolctl is applied only
                # after imports, which is too late for BLAS startup allocations.
                "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                "BLIS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}

    def spawn(self, argv):
        ensure(not self.job and not self.process, "already_started")
        k, check = self.win.k, self.win.check
        handles = []
        attrs = None
        initialized = False
        try:
            self.job = check(k.CreateJobObjectW(None, None), "job_creation_failed")
            limits = ExtendedLimits()
            limits.basic.flags = self.FLAGS
            limits.basic.active_processes = 1
            limits.job_memory = self.MEMORY
            check(k.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)), "job_limits_failed")
            # Verify the kernel-applied limits before child creation.
            actual = self.limits()
            ensure(actual == {"flags": self.FLAGS, "active_processes": 1, "job_memory": self.MEMORY}, "job_limits_failed")
            flags = w.DWORD()
            check(k.GetHandleInformation(self.job, ctypes.byref(flags)))
            ensure(not flags.value & 1, "job_handle_inheritable")
            security = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, True)
            in_read, in_write, out_read, out_write = (HANDLE() for _ in range(4))
            check(k.CreatePipe(ctypes.byref(in_read), ctypes.byref(in_write), ctypes.byref(security), 4096))
            handles.extend((in_read.value, in_write.value))
            check(k.CreatePipe(ctypes.byref(out_read), ctypes.byref(out_write), ctypes.byref(security), 4096))
            handles.extend((out_read.value, out_write.value))
            check(k.SetHandleInformation(in_write, 1, 0))
            check(k.SetHandleInformation(out_read, 1, 0))
            nul = k.CreateFileW("NUL", 0x40000000, 3, ctypes.byref(security), 3, 0, None)
            ensure(nul and nul != ctypes.c_void_p(-1).value, "stderr_handle_failed")
            handles.append(nul)
            length = SIZE()
            k.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(length))
            ensure(ctypes.get_last_error() == 122 and 0 < length.value <= 65536, "atomic_job_api_unavailable")
            attrs = ctypes.create_string_buffer(length.value)
            check(k.InitializeProcThreadAttributeList(attrs, 2, 0, ctypes.byref(length)), "atomic_job_api_unavailable")
            initialized = True
            jobs = self._job_attribute()
            inherited = (HANDLE * 3)(in_read.value, out_write.value, nul)
            check(k.UpdateProcThreadAttribute(attrs, 0, 0x2000D, jobs, ctypes.sizeof(jobs), None, None), "atomic_job_attribute_failed")
            check(k.UpdateProcThreadAttribute(attrs, 0, 0x20002, inherited, ctypes.sizeof(inherited), None, None), "handle_attribute_failed")
            startup = StartupInfoEx()
            startup.startup.cb = ctypes.sizeof(startup)
            startup.startup.flags = 0x100
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = in_read, out_write, nul
            startup.attributes = ctypes.cast(attrs, ctypes.c_void_p)
            process = ProcessInformation()
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
            env = ctypes.create_unicode_buffer("\0".join(f"{a}={b}" for a, b in sorted(self.minimal_environment().items())) + "\0\0")
            # EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW.
            check(k.CreateProcessW(str(argv[0]), command, None, None, True, 0x08080400,
                                   env, str(Path(__file__).resolve().parent), ctypes.byref(startup),
                                   ctypes.byref(process)), "atomic_child_creation_failed")
            self.process, self.pid = process.process, int(process.pid)
            self.win.close(process.thread)
            self.tx, self.rx = in_write.value, out_read.value
            handles.remove(self.tx)
            handles.remove(self.rx)
            member = w.BOOL()
            check(k.IsProcessInJob(self.process, self.job, ctypes.byref(member)))
            ensure(member.value, "atomic_membership_failed")
            return self
        except BaseException:
            self.stop()
            raise
        finally:
            if initialized:
                k.DeleteProcThreadAttributeList(attrs)
            for handle in handles:
                self.win.close(handle)

    def limits(self):
        info = ExtendedLimits()
        self.win.check(self.win.k.QueryInformationJobObject(self.job, 9, ctypes.byref(info), ctypes.sizeof(info), None))
        return {"flags": int(info.basic.flags), "active_processes": int(info.basic.active_processes),
                "job_memory": int(info.job_memory)}

    def alive(self):
        if not self.process:
            return False
        value = self.win.k.WaitForSingleObject(self.process, 0)
        ensure(value in (0, 258), "process_wait_failed")
        return value == 258

    def read_available(self, maximum=32772):
        ensure(0 < maximum <= 32772 and self.rx, "invalid_ipc_read")
        available = w.DWORD()
        self.win.check(self.win.k.PeekNamedPipe(self.rx, None, 0, None, ctypes.byref(available), None), "child_disconnected")
        length = min(maximum, available.value)
        if not length:
            return b""
        buffer = ctypes.create_string_buffer(length)
        received = w.DWORD()
        self.win.check(self.win.k.ReadFile(self.rx, buffer, length, ctypes.byref(received), None), "child_disconnected")
        ensure(received.value > 0, "child_disconnected")
        return buffer.raw[:received.value]

    def write(self, data):
        # Caller must run this independently interruptible operation off the HTTP loop.
        ensure(type(data) is bytes and 0 < len(data) <= 32772 and self.tx, "invalid_ipc_write")
        offset = 0
        while offset < len(data):
            block = data[offset:]
            sent = w.DWORD()
            self.win.check(self.win.k.WriteFile(self.tx, block, len(block), ctypes.byref(sent), None), "child_disconnected")
            ensure(sent.value > 0, "child_disconnected")
            offset += sent.value

    def stop(self, seconds=5.):
        """Terminate only this owned job; wait on retained process handle."""
        if self.job and self.alive():
            self.win.check(self.win.k.TerminateJobObject(self.job, 0xE0000001), "job_termination_failed")
        if self.process:
            ensure(self.win.k.WaitForSingleObject(self.process, max(0, int(seconds * 1000))) == 0,
                   "child_exit_unverified")
        if self.tx:
            self.win.k.CancelIoEx(self.tx, None)
        for name in ("tx", "rx", "process", "job"):
            self.win.close(getattr(self, name))
            setattr(self, name, None)


PROTOCOL = 1
DEMO_VERSION = "private-news-sentiment-demo-v1"
METHOD_VERSION = "news-sentiment-tfidf-svc-v1"
LABELS = ("negative", "neutral", "positive")
PHASES = ("validating_source", "grouping", "splitting", "fitting")
MAX_FRAME = 32768
MAX_BODY = 16384
MAX_SENTENCE = 2000
BODY_READ_SECONDS = 5.
TOKEN_HEADER = b"x-finlens-demo-token"
WORKER_ERRORS = frozenset({"PREPARATION_FAILED", "INFERENCE_FAILED"})


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            ensure(key not in result, "INVALID_JSON")
            result[key] = value
        return result

    def invalid(_value):
        raise DemoError("INVALID_JSON")

    try:
        return json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError):
        raise DemoError("INVALID_JSON") from None


def sentence(payload):
    ensure(type(payload) is dict and set(payload) == {"text"}, "INVALID_INPUT")
    text = payload["text"]
    ensure(type(text) is str and 0 < len(text) <= MAX_SENTENCE and bool(text.strip()), "INVALID_INPUT")
    ensure(not any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in text), "INVALID_INPUT")
    return text  # Validate without trimming, normalizing or echoing the input.


def message(launch, request, kind, payload):
    return {"v": PROTOCOL, "launch": launch, "request": request, "kind": kind, "payload": payload}


def frame(value):
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    ensure(0 < len(data) <= MAX_FRAME, "IPC_FRAME_LIMIT")
    return len(data).to_bytes(4, "big") + data


def envelope(value, launch):
    ensure(type(value) is dict and set(value) == {"v", "launch", "request", "kind", "payload"}, "IPC_SCHEMA")
    ensure(type(value["v"]) is int and value["v"] == PROTOCOL and
           type(value["launch"]) is str and value["launch"] == launch and
           type(value["request"]) is int and 0 <= value["request"] < 2**31 and
           type(value["kind"]) is str and type(value["payload"]) is dict, "IPC_OWNERSHIP")
    return value


class Frames:
    """Incremental decoder: inspect length before retaining a payload."""
    def __init__(self):
        self.buffer = bytearray()
        self.length = None

    def feed(self, data):
        ensure(type(data) is bytes and len(data) <= MAX_FRAME + 4, "IPC_FRAME_LIMIT")
        values = []
        offset = 0
        while offset < len(data):
            target = 4 if self.length is None else self.length
            take = min(target - len(self.buffer), len(data) - offset)
            self.buffer.extend(data[offset:offset + take])
            offset += take
            if len(self.buffer) != target:
                continue
            if self.length is None:
                self.length = int.from_bytes(self.buffer, "big")
                ensure(0 < self.length <= MAX_FRAME, "IPC_FRAME_LIMIT")
                self.buffer.clear()
            else:
                values.append(strict_json(bytes(self.buffer)))
                self.buffer.clear()
                self.length = None
        return values


def news_module():
    backend = str(Path(__file__).resolve().parents[1])
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from scripts import evaluate_news_sentiment
    return evaluate_news_sentiment


def prepare_model(path, progress):
    """Called only by an explicitly launched worker, never on import/HTTP input."""
    news = news_module()
    progress("validating_source")
    rows = news.read_archive(news.local_zip_bytes(path))
    news.require(len(rows) == 3453 and news.counts(rows) == dict(zip(news.LABELS, (420, 2146, 887))), "source_count_mismatch")
    progress("grouping")
    grouping = news.group_rows(rows)
    news.require((grouping.audit["groups"], grouping.audit["nonsingleton_groups"],
                  grouping.audit["rows_in_nonsingleton_groups"]) == (3349, 76, 180), "group_reference_mismatch")
    ml = news.load_ml()
    progress("splitting")
    parts, fingerprint = news.make_split(rows, grouping, ml)
    news.require(fingerprint == news.REFERENCE_SPLIT and len(parts["train"]) == 2071, "split_reference_mismatch")
    progress("fitting")
    with ml.thread_limit(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", ml.convergence_warning)
        vectorizer, matrix, labels = news.fit_training_features(rows, parts["train"], ml)
        classifier = news.fit_linear_classifier(matrix, labels, ml, 10.)
    news.require(len(vectorizer.vocabulary_) == 6866, "feature_reference_mismatch")
    # Return no corpus, labels, grouping, partitions or training matrix references.
    return vectorizer, classifier, ml


def read_worker_frame():
    def exact(count):
        chunks = bytearray()
        while len(chunks) < count:
            block = os.read(0, count - len(chunks))
            ensure(bool(block), "IPC_DISCONNECTED")
            chunks.extend(block)
        return bytes(chunks)
    length = int.from_bytes(exact(4), "big")
    ensure(0 < length <= MAX_FRAME, "IPC_FRAME_LIMIT")
    return strict_json(exact(length))


def write_worker_frame(value):
    data = frame(value)
    while data:
        count = os.write(1, data)
        ensure(count > 0, "IPC_DISCONNECTED")
        data = data[count:]


def predict_label(vectorizer, classifier, text):
    matrix = vectorizer.transform([text])
    if not matrix.nnz:
        return None
    label = str(classifier.predict(matrix)[0])
    ensure(label in LABELS, "INVALID_MODEL_RESULT")
    return label


def worker_main(packages):
    """Private inherited stdio only; no model object crosses this channel."""
    import msvcrt
    msvcrt.setmode(0, os.O_BINARY)
    msvcrt.setmode(1, os.O_BINARY)
    kernel = Windows().k
    kernel.GetCurrentProcess.restype = HANDLE
    kernel.GetStdHandle.argtypes, kernel.GetStdHandle.restype = [w.DWORD], HANDLE
    kernel.GetFileType.argtypes, kernel.GetFileType.restype = [HANDLE], w.DWORD
    member = w.BOOL()
    ensure(kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(member)) and member.value,
           "WORKER_NOT_OWNED")
    ensure(all(kernel.GetFileType(kernel.GetStdHandle(n)) == 3 for n in (0xFFFFFFF6, 0xFFFFFFF5)), "INVALID_IPC_HANDLES")
    ensure(Path(packages).is_absolute() and Path(packages).is_dir(), "MISSING_LOCAL_PACKAGES")
    sys.path.insert(0, packages)
    news = news_module()
    # IPC already exists; the original ML-PB-01 hook remains unchanged.
    sys.addaudithook(news.audit_side_effects)
    first = read_worker_frame()
    launch = first.get("launch") if type(first) is dict else None
    ensure(type(launch) is str and len(launch) == 32 and all(c in "0123456789abcdef" for c in launch), "IPC_OWNERSHIP")
    envelope(first, launch)
    ensure(first["request"] == 0 and first["kind"] == "init" and
           set(first["payload"]) == {"zip"} and type(first["payload"]["zip"]) is str, "IPC_SCHEMA")
    try:
        vectorizer, classifier, ml = prepare_model(first["payload"]["zip"],
            lambda phase: write_worker_frame(message(launch, 0, "phase", {"phase": phase})))
    except Exception:
        write_worker_frame(message(launch, 0, "error", {"code": "PREPARATION_FAILED"}))
        return 2
    del first
    write_worker_frame(message(launch, 0, "ready", {"method": METHOD_VERSION, "train_rows": 2071, "features": 6866}))
    last_request = 0
    with ml.thread_limit(limits=1):
        while True:
            incoming = envelope(read_worker_frame(), launch)
            request = incoming["request"]
            ensure(request == last_request + 1, "IPC_OWNERSHIP")
            last_request = request
            if incoming["kind"] == "shutdown" and incoming["payload"] == {}:
                return 0
            ensure(incoming["kind"] == "classify", "IPC_SCHEMA")
            text = sentence(incoming["payload"])
            try:
                label = predict_label(vectorizer, classifier, text)
                if label is None:
                    response = message(launch, request, "unsupported", {"code": "UNSUPPORTED_FEATURES"})
                else:
                    response = message(launch, request, "result", {"label": label})
            except Exception:
                write_worker_frame(message(launch, request, "error", {"code": "INFERENCE_FAILED"}))
                return 2
            del text, incoming
            write_worker_frame(response)
            del response


class Supervisor:
    def __init__(self, path, port=8765, *, factory=NativeJob, clock=time.monotonic,
                 warmup_seconds=60., inference_seconds=2., cleanup_seconds=5.):
        ensure(type(port) is int and 1 <= port <= 65535, "INVALID_PORT")
        self.path, self.port, self.factory, self.clock = path, port, factory, clock
        self.warmup_seconds, self.inference_seconds, self.cleanup_seconds = warmup_seconds, inference_seconds, cleanup_seconds
        self.launch, self.token = secrets.token_hex(16), secrets.token_hex(32)
        self.state, self.phase, self.error = "starting", None, None
        self.started = self.ready_at = None
        self.native = self.monitor = self.writer = self.pending = self.cleanup = None
        self.request = 0
        self.decoder = Frames()
        self.on_stopped = None
        self._cleanup_lock = asyncio.Lock()
        self._shutdown_task = None

    def _send(self, value):
        ensure(self.writer is None or self.writer.done(), "IPC_WRITER_BUSY")
        self.writer = asyncio.create_task(asyncio.to_thread(self.native.write, frame(value)))
        self.writer.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)

    async def start(self):
        ensure(self.started is None, "ALREADY_STARTED")
        self.started = self.clock()  # Includes job creation, process startup and init IPC.
        try:
            self.native = self.factory()
            self.native.spawn([sys._base_executable, "-I", "-B", str(Path(__file__).resolve()), "--worker",
                               str(Path(sys.prefix) / "Lib" / "site-packages")])
            self._send(message(self.launch, 0, "init", {"zip": self.path}))
            self.monitor = asyncio.create_task(self._monitor())
        except Exception:
            await self.fail("STARTUP_FAILED")

    def status(self):
        end = self.clock() if self.ready_at is None else self.ready_at
        start = self.clock() if self.started is None else self.started
        return {"state": self.state, "phase": self.phase, "error": self.error,
                "elapsed_seconds": round(max(0., end - start), 1),
                "model_run_id": self.launch, "method_version": METHOD_VERSION, "demo_version": DEMO_VERSION}

    async def fail(self, code):
        if self.state in {"failed", "stopped", "stopping"}:
            return
        self.state, self.error = "failed", code
        if self.pending and not self.pending[2].done():
            self.pending[2].set_exception(DemoError(code))
        self.cleanup = asyncio.create_task(self._terminate())
        await asyncio.shield(self.cleanup)

    async def _terminate(self):
        async with self._cleanup_lock:
            return await self._terminate_locked()

    async def _terminate_locked(self):
        try:
            if self.native:
                await asyncio.to_thread(self.native.stop, self.cleanup_seconds)
            if self.writer:
                await asyncio.wait_for(asyncio.shield(self.writer), self.cleanup_seconds)
        except Exception:
            # A disconnected writer after verified termination is expected.
            if self.native and self.native.process:
                self.state, self.error = "failed", "CLEANUP_UNVERIFIED"
                return False
            if self.writer and not self.writer.done():
                self.state, self.error = "failed", "IPC_CLEANUP_UNVERIFIED"
                return False
        self.pending = None
        return True

    async def _receive(self, value):
        value = envelope(value, self.launch)
        kind, payload, request = value["kind"], value["payload"], value["request"]
        deadline = self.started + self.warmup_seconds if self.state == "starting" else (
            self.pending[1] if self.pending else self.clock())
        timeout_code = "WARMUP_TIMEOUT" if self.state == "starting" else "INFERENCE_TIMEOUT"
        # A fast worker may answer before the writer thread's completion callback
        # runs. Do not release ownership until both directions are complete.
        if self.writer and not self.writer.done():
            ensure(self.clock() < deadline, timeout_code)
            try:
                await asyncio.wait_for(asyncio.shield(self.writer), deadline - self.clock())
            except TimeoutError:
                raise DemoError(timeout_code) from None
        if self.writer:
            self.writer.result()
        if self.state == "starting":
            ensure(self.clock() - self.started < self.warmup_seconds, "WARMUP_TIMEOUT")
            ensure(request == 0, "IPC_OWNERSHIP")
            if kind == "phase":
                ensure(set(payload) == {"phase"} and payload["phase"] in PHASES, "IPC_SCHEMA")
                ensure(self.phase is None or PHASES.index(payload["phase"]) > PHASES.index(self.phase), "IPC_DUPLICATE")
                self.phase = payload["phase"]
                return
            if kind == "error":
                ensure(payload == {"code": "PREPARATION_FAILED"}, "IPC_SCHEMA")
                raise DemoError("PREPARATION_FAILED")
            ensure(kind == "ready" and self.phase == "fitting" and
                   payload == {"method": METHOD_VERSION, "train_rows": 2071, "features": 6866}, "IPC_SCHEMA")
            ensure(self.clock() < deadline, timeout_code)
            self.state, self.ready_at = "ready", self.clock()
            return
        ensure(self.state == "ready" and self.pending is not None and request == self.pending[0], "IPC_OWNERSHIP")
        ensure(self.clock() < self.pending[1], "INFERENCE_TIMEOUT")
        if kind == "result":
            ensure(set(payload) == {"label"} and payload["label"] in LABELS, "IPC_SCHEMA")
            result = {"label": payload["label"], "method_version": METHOD_VERSION,
                      "demo_version": DEMO_VERSION, "model_run_id": self.launch}
            ensure(self.clock() < deadline, timeout_code)
        elif kind == "unsupported":
            ensure(payload == {"code": "UNSUPPORTED_FEATURES"}, "IPC_SCHEMA")
            ensure(self.clock() < deadline, timeout_code)
            result = DemoError("UNSUPPORTED_FEATURES")
        else:
            ensure(kind == "error" and payload == {"code": "INFERENCE_FAILED"}, "IPC_SCHEMA")
            raise DemoError("INFERENCE_FAILED")
        # Stage completion; tick owns publication after validating its entire
        # finite receive batch, including any additional or partial frame.
        return self.pending, result

    async def tick(self):
        if self.state not in {"starting", "ready"}:
            return
        try:
            now = self.clock()
            ensure(not (self.state == "starting" and now - self.started >= self.warmup_seconds), "WARMUP_TIMEOUT")
            ensure(not (self.pending and now >= self.pending[1]), "INFERENCE_TIMEOUT")
            if self.writer and self.writer.done():
                self.writer.result()
            completion = None
            # The batch ends at the first empty nonblocking read. Eight nonempty
            # reads exhaust the budget and fail closed instead of publishing an
            # incompletely checked response. Never wait for hypothetical traffic.
            for _ in range(8):
                data = self.native.read_available()
                if not data:
                    break
                for value in self.decoder.feed(data):
                    ensure(completion is None, "IPC_DUPLICATE")
                    completion = await self._receive(value)
            else:
                raise DemoError("IPC_BATCH_LIMIT")
            ensure(self.native.alive(), "CHILD_DISCONNECTED")
            if completion is not None:
                pending, result = completion
                ensure(not self.decoder.buffer and self.decoder.length is None, "IPC_EXTRA_PARTIAL")
                ensure(self.state == "ready" and self.pending is pending, "IPC_OWNERSHIP")
                ensure(self.clock() < pending[1], "INFERENCE_TIMEOUT")
                future = pending[2]
                ensure(not future.done(), "IPC_OWNERSHIP")
                self.pending = None
                if isinstance(result, DemoError):
                    future.set_exception(result)
                else:
                    future.set_result(result)
        except Exception as exc:
            safe = {"WARMUP_TIMEOUT", "INFERENCE_TIMEOUT", "PREPARATION_FAILED", "INFERENCE_FAILED"}
            await self.fail(str(exc) if isinstance(exc, DemoError) and str(exc) in safe else "WORKER_PROTOCOL_FAILED")

    async def _monitor(self):
        while self.state in {"starting", "ready"}:
            await self.tick()
            await asyncio.sleep(.01)

    async def classify(self, text):
        sentence({"text": text})
        ensure(self.state == "ready", "MODEL_NOT_READY")
        ensure(self.pending is None, "BUSY")
        ensure(self.request + 1 < 2**31, "REQUEST_LIMIT")
        self.request += 1
        future = asyncio.get_running_loop().create_future()
        future.add_done_callback(lambda item: item.exception() if not item.cancelled() else None)
        self.pending = (self.request, self.clock() + self.inference_seconds, future)
        try:
            self._send(message(self.launch, self.request, "classify", {"text": text}))
        except Exception:
            await self.fail("WORKER_PROTOCOL_FAILED")
        # Browser disconnect/cancellation cannot release the worker slot.
        return await asyncio.shield(future)

    async def shutdown(self):
        if self.state == "stopped":
            return True
        if self._shutdown_task is None:
            self._shutdown_task = asyncio.create_task(self._shutdown())
        return await asyncio.shield(self._shutdown_task)

    async def _shutdown(self):
        had_pending = self.pending is not None
        self.state = "stopping"
        if self.pending and not self.pending[2].done():
            self.pending[2].set_exception(DemoError("SHUTTING_DOWN"))
        if self.native and not had_pending and (self.writer is None or self.writer.done()):
            try:
                self.request += 1
                self._send(message(self.launch, self.request, "shutdown", {}))
                end = self.clock() + self.cleanup_seconds
                while self.native.alive() and self.clock() < end:
                    await asyncio.sleep(.01)
            except Exception:
                pass
        ok = await self._terminate()
        if self.monitor:
            await self.monitor
        if ok:
            self.state = "stopped"
            if self.on_stopped:
                self.on_stopped()
        return ok


def create_app(supervisor):
    """Application construction is inert; tests use an in-memory ASGI transport."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException
    from starlette.responses import HTMLResponse, JSONResponse

    @asynccontextmanager
    async def lifespan(_app):
        await supervisor.start()
        try:
            yield
        finally:
            await supervisor.shutdown()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, debug=False)
    nonce = secrets.token_hex(16)
    security = {
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'none'; script-src 'nonce-" + nonce +
            "'; style-src 'nonce-" + nonce + "'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    }
    origin = f"http://127.0.0.1:{supervisor.port}"
    authority = f"127.0.0.1:{supervisor.port}".encode("ascii")

    def error(code, status=400):
        return JSONResponse({"error": code}, status_code=status, headers=security)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return error("INVALID_INPUT")

    @app.exception_handler(Exception)
    async def unexpected_error(_request, _exc):
        return error("UNAVAILABLE", 503)

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return error("INVALID_REQUEST", 400) if 400 <= exc.status_code < 500 else error("UNAVAILABLE", 503)

    async def body(request):
        async def read():
            data = bytearray()
            async for block in request.stream():
                ensure(len(data) + len(block) <= MAX_BODY, "BODY_TOO_LARGE")
                data.extend(block)
            return strict_json(bytes(data))
        try:
            return await asyncio.wait_for(read(), BODY_READ_SECONDS)
        except TimeoutError:
            raise DemoError("BODY_TIMEOUT") from None

    @app.get("/")
    async def index():
        page = Path(__file__).with_name("news_sentiment_demo.html").read_text(encoding="utf-8")
        page = page.replace("__NONCE__", nonce).replace("__TOKEN__", supervisor.token)
        return HTMLResponse(page, headers=security)

    @app.get("/api/status")
    async def status():
        return JSONResponse(supervisor.status(), headers=security)

    @app.post("/api/classify")
    async def classify(request: Request):
        try:
            text = sentence(await body(request))
            result = await supervisor.classify(text)
            # The monitor may have failed the worker after future settlement
            # but before this continuation. No await separates this gate/response.
            ensure(supervisor.state == "ready" and result["model_run_id"] == supervisor.launch,
                   "WORKER_PROTOCOL_FAILED")
            return JSONResponse(result, headers=security)
        except DemoError as exc:
            code = str(exc)
            statuses = {"INVALID_INPUT": 400, "INVALID_JSON": 400, "BODY_TOO_LARGE": 413,
                        "BODY_TIMEOUT": 408, "UNSUPPORTED_FEATURES": 422, "BUSY": 409}
            code = code if code in statuses or code in {
                "MODEL_NOT_READY", "INFERENCE_TIMEOUT", "WORKER_PROTOCOL_FAILED", "SHUTTING_DOWN",
                "INFERENCE_FAILED", "REQUEST_LIMIT", "CHILD_DISCONNECTED"} else "UNAVAILABLE"
            return error(code, statuses.get(code, 503))

    @app.post("/api/shutdown")
    async def shutdown(request: Request):
        try:
            ensure(await body(request) == {}, "INVALID_INPUT")
        except DemoError as exc:
            code = str(exc) if str(exc) in {"INVALID_INPUT", "INVALID_JSON", "BODY_TIMEOUT", "BODY_TOO_LARGE"} else "INVALID_INPUT"
            return error(code, {"BODY_TIMEOUT": 408, "BODY_TOO_LARGE": 413}.get(code, 400))
        # Complete the acknowledgement before shutdown closes the server.
        from starlette.background import BackgroundTask
        return JSONResponse({"state": "stopping"}, status_code=202, headers=security,
                            background=BackgroundTask(supervisor.shutdown))

    class Gate:
        def __init__(self, application):
            self.application = application

        async def __call__(self, scope, receive, send):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            if scope["type"] != "http":
                return await self.application(scope, receive, send)
            values = {}
            for key, value in scope.get("headers", []):
                values.setdefault(key.lower(), []).append(value)
            sensitive = (b"host", b"origin", TOKEN_HEADER, b"content-type", b"content-length", b"transfer-encoding")
            if any(len(values.get(key, [])) > 1 for key in sensitive):
                return await error("INVALID_HEADERS")(scope, receive, send)
            peer = scope.get("client")
            if not peer or peer[0] != "127.0.0.1" or values.get(b"host") != [authority]:
                return await error("FORBIDDEN", 403)(scope, receive, send)
            if scope.get("query_string"):
                return await error("NOT_FOUND", 404)(scope, receive, send)
            path, method = scope.get("path"), scope.get("method")
            routes = {"/": "GET", "/api/status": "GET", "/api/classify": "POST", "/api/shutdown": "POST"}
            if path not in routes:
                return await error("NOT_FOUND", 404)(scope, receive, send)
            if method != routes[path]:
                return await error("METHOD_NOT_ALLOWED", 405)(scope, receive, send)
            if path != "/":
                token = values.get(TOKEN_HEADER, [b""])[0]
                if not secrets.compare_digest(token, supervisor.token.encode("ascii")):
                    return await error("FORBIDDEN", 403)(scope, receive, send)
            if method == "POST":
                if values.get(b"origin") != [origin.encode("ascii")]:
                    return await error("FORBIDDEN", 403)(scope, receive, send)
                if values.get(b"content-type") != [b"application/json"]:
                    return await error("INVALID_CONTENT_TYPE", 415)(scope, receive, send)
            length = values.get(b"content-length", [None])[0]
            if length is not None:
                if not length or not all(48 <= c <= 57 for c in length) or len(length) > 8:
                    return await error("INVALID_HEADERS")(scope, receive, send)
                if int(length) > MAX_BODY:
                    return await error("BODY_TOO_LARGE", 413)(scope, receive, send)
                if method == "GET" and int(length) != 0:
                    return await error("INVALID_HEADERS")(scope, receive, send)
            return await self.application(scope, receive, send)

    return Gate(app)


def supervisor_audit(port):
    news = news_module()

    def audit(event, args):
        if event.startswith("socket."):
            if event == "socket.bind":
                ensure(args[1] == ("127.0.0.1", port), "NETWORK_BLOCKED")
            elif event not in {"socket.__new__", "socket.gethostname"}:
                raise DemoError("NETWORK_BLOCKED")
            return
        news.audit_side_effects(event, args)
    return audit


def main(argv=None):
    import argparse
    import logging

    class Parser(argparse.ArgumentParser):
        def error(self, _message):
            raise DemoError("INVALID_ARGUMENTS")

    try:
        parser = Parser(allow_abbrev=False, description=__doc__)
        parser.add_argument("--zip", required=True)
        parser.add_argument("--port", type=int, default=8765)
        args = parser.parse_args(argv)
        ensure(os.name == "nt" and 1 <= args.port <= 65535, "UNSUPPORTED_CONFIGURATION")
        # No source access here: pinned source checks belong to the owned child.
        owner = Supervisor(args.zip, args.port)
        import uvicorn
        import socket
        application = create_app(owner)
        # The Windows event-loop wakeup channel is established before imposing
        # outbound-connect denial. It is not an exposed application listener.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "asyncio"):
            logger = logging.getLogger(name)
            logger.handlers, logger.propagate = [logging.NullHandler()], False
        sys.addaudithook(supervisor_audit(args.port))
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", args.port))
            listener.listen(8)
            listener.setblocking(False)
            config = uvicorn.Config(application, host="127.0.0.1", port=args.port,
                workers=1, reload=False, proxy_headers=False, forwarded_allow_ips="",
                access_log=False, log_config=None, server_header=False, date_header=False,
                ws="none", http="h11", loop="asyncio", lifespan="on", limit_concurrency=8,
                backlog=8, timeout_keep_alive=2, timeout_graceful_shutdown=5,
                h11_max_incomplete_event_size=16384)
            server = uvicorn.Server(config)
            # Briefly expose the verified terminal status before closing, so the
            # UI never treats an ambiguous connection error as proof of cleanup.
            owner.on_stopped = lambda: loop.call_later(1., setattr, server, "should_exit", True)
            print(f"Private demo: http://127.0.0.1:{args.port} — preparing; Ctrl+C stops this demo.", flush=True)
            try:
                loop.run_until_complete(server.serve(sockets=[listener]))
            finally:
                loop.run_until_complete(owner.shutdown())
                loop.run_until_complete(loop.shutdown_default_executor(timeout=5))
        finally:
            listener.close()
            loop.close()
        return 0 if owner.state == "stopped" else 2
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('{"error":"DEMO_START_OR_CLEANUP_FAILED"}')
        return 2


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        try:
            raise SystemExit(worker_main(sys.argv[2]))
        except Exception:
            raise SystemExit(2) from None
    raise SystemExit(main())
