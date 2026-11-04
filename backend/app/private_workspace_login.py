"""Default-off OAuth public-client PKCE seam; injected transport, never discovery/I/O.

This is not OIDC/ID-token login or an installed provider. Trusted composition must
pin all policy and transport. Process memory is a development, single-worker store.
"""
import asyncio
import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import math
import re
import secrets
from threading import Event, RLock
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from app.account_auth import AuthFailure, IssuerPolicy, SingleIssuerVerifier, MAX_TOKEN, MAX_LIFETIME, SKEW
from app.private_workspace_http import COOKIE, SESSION_SECONDS, PrivateWorkspace

CORRELATION_COOKIE = "__Host-finlens-login"
CALLBACK_PATH = "/private-research/login/callback"
FLOW_SECONDS = 180
MAX_FLOWS = 100
EXCHANGE_SECONDS = 5
MAX_REPLY = 32 * 1024
LOGIN_PATHS = {"/login/start", "/login/callback", "/login/cancel"}


class LoginFailure(ValueError):
    def __init__(self, status=400, code="LOGIN_INVALID", *, consumed=False):
        self.status, self.code, self.consumed = status, code, consumed
        super().__init__(code)


def _require(condition, status=400, code="LOGIN_INVALID"):
    if not condition:
        raise LoginFailure(status, code)


def _text(value, limit):
    try:
        return (type(value) is str and 0 < len(value.encode("utf-8")) <= limit
                and not any(ord(c) < 32 or ord(c) == 127 for c in value))
    except UnicodeError:
        return False


def _url(value, *, origin=False):
    _require(_text(value, 2048) and value.isascii() and "\\" not in value,
             503, "LOGIN_CONFIGURATION_INVALID")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and bool(parsed.hostname)
                 and re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname) is not None and parsed.port != 0
                 and parsed.username is None and parsed.password is None and not parsed.query
                 and not parsed.fragment and re.fullmatch(r"[A-Za-z0-9/._~-]*", parsed.path) is not None)
        if origin:
            valid = valid and not parsed.path and value == f"https://{parsed.netloc}" and value == value.lower()
        _require(valid, 503, "LOGIN_CONFIGURATION_INVALID")
    except ValueError:
        raise LoginFailure(503, "LOGIN_CONFIGURATION_INVALID") from None


@dataclass(frozen=True, slots=True, repr=False)
class InviteAdmission:
    issuer: str
    subjects: frozenset[str]

    def __post_init__(self):
        _url(self.issuer)
        _require(type(self.subjects) is frozenset and len(self.subjects) <= 100
                 and all(_text(subject, 255) for subject in self.subjects), 503, "LOGIN_CONFIGURATION_INVALID")

    def require_subject(self, identity):
        _require(identity.issuer == self.issuer and identity.subject in self.subjects, 403, "LOGIN_DENIED")


@dataclass(frozen=True, slots=True, repr=False)
class LoginConfiguration:
    policy: IssuerPolicy
    authorization_endpoint: str
    token_endpoint: str
    origin: str
    scopes: tuple[str, ...]
    admission: InviteAdmission

    def __post_init__(self):
        _require(type(self.policy) is IssuerPolicy and type(self.admission) is InviteAdmission
                 and self.admission.issuer == self.policy.issuer, 503, "LOGIN_CONFIGURATION_INVALID")
        _url(self.authorization_endpoint); _url(self.token_endpoint); _url(self.origin, origin=True)
        _require(type(self.scopes) is tuple and 0 < len(self.scopes) <= 16
                 and all(type(s) is str and re.fullmatch(r"[A-Za-z0-9._:/-]{1,128}", s) for s in self.scopes)
                 and len(set(self.scopes)) == len(self.scopes)
                 and not (set(self.scopes) & {"offline_access", "openid"}), 503, "LOGIN_CONFIGURATION_INVALID")

    @property
    def redirect_uri(self):
        return self.origin + CALLBACK_PATH


@dataclass(frozen=True, slots=True, repr=False)
class TokenExchange:
    url: str
    body: bytes = field(repr=False)
    timeout_seconds: int = EXCHANGE_SECONDS
    max_response_bytes: int = MAX_REPLY
    follow_redirects: bool = False
    content_type: str = "application/x-www-form-urlencoded"


@dataclass(frozen=True, slots=True, repr=False)
class TokenReply:
    status: int
    content_type: str
    body: bytes = field(repr=False)


@dataclass(slots=True, repr=False)
class _Flow:
    browser_digest: bytes
    verifier: str
    wall_deadline: float
    mono_deadline: float
    cancellation: object
    status: str = "pending"
    research_handle: str | None = None


@dataclass(slots=True, repr=False)
class _Attempt:
    cancelled: Event = field(default_factory=Event)
    state: str | None = None
    browser_digest: bytes | None = None
    flow: _Flow | None = None


def _cookie(handle="", age=0):
    return f"{CORRELATION_COOKIE}={handle}; Max-Age={age}; Path=/; Secure; HttpOnly; SameSite=Lax"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


class PrivateWorkspaceLogin:
    """Unconfigured main mount; only trusted server code can install this profile."""
    def __init__(self, workspace=None, *, configuration=None, exchange=None, clock=time.time, monotonic=time.monotonic):
        self._workspace = PrivateWorkspace() if workspace is None else workspace
        _require(type(self._workspace) is PrivateWorkspace, 503, "LOGIN_CONFIGURATION_INVALID")
        if configuration is not None:
            _require(type(configuration) is LoginConfiguration and callable(exchange)
                     and self._workspace._origin == configuration.origin
                     and type(getattr(self._workspace._service, "_verifier", None)) is SingleIssuerVerifier
                     and self._workspace._service._verifier._policy == configuration.policy,
                     503, "LOGIN_CONFIGURATION_INVALID")
        else:
            _require(exchange is None, 503, "LOGIN_CONFIGURATION_INVALID")
        self._configuration, self._exchange = configuration, exchange
        self._clock, self._monotonic = clock, monotonic
        self._flows, self._lock, self._sample = {}, RLock(), None
        self._cleanup_tasks = set()
        self._cleanup_failures = 0

    def _cleanup(self, function, *args):
        """Track off-loop cleanup even when its initiating request is cancelled."""
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        self._cleanup_tasks.add(task)
        def done(result):
            self._cleanup_tasks.discard(result)
            if not result.cancelled():
                if result.exception() is not None:
                    self._cleanup_failures += 1  # No private diagnostic is retained or exposed.
        task.add_done_callback(done)
        return task

    def _now(self):
        wall, mono = self._clock(), self._monotonic()
        _require(type(wall) in (int, float) and math.isfinite(wall) and wall >= 0
                 and type(mono) in (int, float) and math.isfinite(mono), 503, "LOGIN_UNAVAILABLE")
        if self._sample is not None:
            old_wall, old_mono = self._sample
            _require(mono >= old_mono and abs(wall - old_wall - (mono - old_mono)) <= SKEW,
                     503, "LOGIN_UNAVAILABLE")
        self._sample = wall, mono
        return wall, mono

    @staticmethod
    def _values(headers):
        return [part.strip().split("=", 1)[1] for part in headers.get("cookie", "").split(";")
                if part.strip().startswith(CORRELATION_COOKIE + "=")]

    @classmethod
    def _binding(cls, headers, optional=False):
        values = cls._values(headers)
        if optional and not values:
            return None
        _require(len(values) == 1 and re.fullmatch(r"[A-Za-z0-9_-]{43}", values[0]) is not None)
        return hashlib.sha256(values[0].encode("ascii")).digest()

    def _cancel(self, headers):
        # Cancellation may invalidate every recognizable duplicate, never grant access.
        digests = {hashlib.sha256(v.encode()).digest() for v in self._values(headers)
                   if re.fullmatch(r"[A-Za-z0-9_-]{43}", v)}
        with self._lock:
            removed = [(key, flow) for key, flow in self._flows.items() if flow.browser_digest in digests]
            for key, _ in removed:
                del self._flows[key]
        return self._dispose(flow for _, flow in removed)

    def _dispose(self, flows):
        """Detached flows only: never hold the flow lock across external locks/I/O."""
        discarded = False
        for flow in flows:
            flow.cancellation.cancel()
            flow.verifier = ""
            if flow.research_handle is not None:
                self._workspace.discard(flow.research_handle)
                discarded = True
        return discarded

    def _abandon(self, attempt, pending=False):
        attempt.cancelled.set()
        if attempt.flow is None and not pending:
            return
        with self._lock:
            flow = attempt.flow
            if flow is None:
                candidate = self._flows.get(attempt.state)
                if (candidate is not None and candidate.status == "pending" and attempt.browser_digest is not None
                        and hmac.compare_digest(candidate.browser_digest, attempt.browser_digest)):
                    flow = candidate
            if flow is None:
                return
            if self._flows.get(attempt.state) is flow:
                del self._flows[attempt.state]
        self._dispose((flow,))

    def _start(self, headers, attempt):
        from app.research_ownership import Cancellation
        own = self._binding(headers, optional=True)
        previous = None
        if any(part.strip().startswith(COOKIE + "=") for part in headers.get("cookie", "").split(";")):
            previous = self._workspace._handle(headers)
        state, browser, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        browser_digest, cancellation = hashlib.sha256(browser.encode()).digest(), Cancellation()
        with self._lock:
            wall, mono = self._now()
            _require(not attempt.cancelled.is_set())
            removed = [(key, flow) for key, flow in self._flows.items()
                       if flow.browser_digest == own or wall >= flow.wall_deadline or mono >= flow.mono_deadline]
            _require(len(self._flows) - len(removed) < MAX_FLOWS,
                     503, "LOGIN_UNAVAILABLE")
            for key, _ in removed:
                del self._flows[key]
            flow = _Flow(browser_digest, verifier, wall + FLOW_SECONDS, mono + FLOW_SECONDS, cancellation)
            attempt.state, attempt.browser_digest, attempt.flow = state, browser_digest, flow
            self._flows[state] = flow
        try:
            self._dispose(value for _, value in removed)
            if previous is not None:
                self._workspace.discard(previous)
            _require(not attempt.cancelled.is_set())
        except BaseException:
            self._abandon(attempt)
            raise
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
        cfg = self._configuration
        url = cfg.authorization_endpoint + "?" + urlencode(dict(response_type="code", client_id=cfg.policy.client_id,
            redirect_uri=cfg.redirect_uri, scope=" ".join(cfg.scopes), state=state,
            code_challenge=challenge, code_challenge_method="S256", response_mode="query"))
        return 200, json.dumps({"authorization_url": url}, separators=(",", ":")).encode(), [
            (b"set-cookie", _cookie(browser, FLOW_SECONDS).encode()),
            (b"set-cookie", self._workspace._cookie().encode())]

    def _active(self, state, flow, status):
        wall, mono = self._now()
        _require(self._flows.get(state) is flow and flow.status == status
                 and wall < flow.wall_deadline and mono < flow.mono_deadline)

    def _consume(self, attempt):
        with self._lock:
            flow = self._flows.get(attempt.state)
            _require(flow is not None and hmac.compare_digest(flow.browser_digest, attempt.browser_digest))
            self._active(attempt.state, flow, "pending")
            _require(not attempt.cancelled.is_set())
            flow.status = "exchanging"  # Atomic one-use transition; no I/O or other lock acquisition.
            attempt.flow = flow
        return flow

    def _finish(self, attempt, token):
        cfg = self._configuration
        state, flow = attempt.state, attempt.flow
        with self._lock:
            self._active(state, flow, "exchanging")
            _require(not attempt.cancelled.is_set())
        verifier = self._workspace._service._verifier
        _require(type(verifier) is SingleIssuerVerifier and verifier._policy == cfg.policy,
                 503, "LOGIN_UNAVAILABLE")
        identity = verifier.verify_principal(token)
        cfg.admission.require_subject(identity)  # Must precede any account/session creation.
        _require(not attempt.cancelled.is_set())
        cookie = self._workspace.establish(token, cancellation=flow.cancellation)
        handle = cookie.split(";", 1)[0].split("=", 1)[1]
        try:
            with self._lock:
                self._active(state, flow, "exchanging")
                _require(not attempt.cancelled.is_set())
                wall, mono = self._now()
                flow.status, flow.research_handle, flow.verifier = "completed", handle, ""
                # Retain the handle for late concurrent logout/cancel requests only.
                flow.wall_deadline, flow.mono_deadline = wall + SESSION_SECONDS, mono + SESSION_SECONDS
        except BaseException:
            self._workspace.discard(handle)
            raise
        return cookie

    async def _callback(self, headers, query, attempt):
        cfg = self._configuration
        _require(set(query) <= {"code", "state", "iss", "error", "error_description", "error_uri"}
                 and {"state", "iss"} <= set(query) and query["iss"] == cfg.policy.issuer
                 and re.fullmatch(r"[A-Za-z0-9_-]{43}", query["state"]) is not None)
        attempt.state, attempt.browser_digest = query["state"], self._binding(headers)
        try:
            flow = await asyncio.to_thread(self._consume, attempt)
            _require(not attempt.cancelled.is_set())
            _require("error" not in query, 400, "LOGIN_DENIED")
            _require(set(query) == {"state", "iss", "code"} and _text(query["code"], 2048)
                     and query["code"].isascii() and " " not in query["code"])
            request = TokenExchange(cfg.token_endpoint, urlencode(dict(grant_type="authorization_code",
                code=query["code"], redirect_uri=cfg.redirect_uri, client_id=cfg.policy.client_id,
                code_verifier=flow.verifier)).encode("ascii"))
            reply = await asyncio.wait_for(self._exchange(request), EXCHANGE_SECONDS)
            _require(type(reply) is TokenReply and type(reply.status) is int and reply.status == 200
                     and reply.content_type in {"application/json", "application/json; charset=utf-8"}
                     and type(reply.body) is bytes and 0 < len(reply.body) <= MAX_REPLY, 503, "LOGIN_UNAVAILABLE")
            data = json.loads(reply.body, object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            _require(type(data) is dict and {"access_token", "token_type", "expires_in"} <= set(data)
                     and set(data) <= {"access_token", "token_type", "expires_in", "scope"}
                     and type(data["access_token"]) is str and data["access_token"].isascii()
                     and 0 < len(data["access_token"]) <= MAX_TOKEN
                     and type(data["token_type"]) is str and data["token_type"].lower() == "bearer"
                     and type(data["expires_in"]) is int and 0 < data["expires_in"] <= MAX_LIFETIME
                     and ("scope" not in data or data["scope"] == " ".join(cfg.scopes)), 503, "LOGIN_UNAVAILABLE")
            cookie = await asyncio.wait_for(asyncio.to_thread(self._finish, attempt, data["access_token"]), 5)
            return 303, b"", [(b"location", (cfg.origin + "/investigations").encode()),
                (b"set-cookie", cookie.encode()), (b"set-cookie", _cookie().encode())]
        except BaseException as error:
            attempt.cancelled.set()
            if isinstance(error, asyncio.CancelledError):
                self._cleanup(self._abandon, attempt, True)
                raise
            if attempt.flow is not None:
                await asyncio.shield(self._cleanup(self._abandon, attempt))
            if isinstance(error, LoginFailure):
                error.consumed = attempt.flow is not None
                raise
            if isinstance(error, AuthFailure) or getattr(error, "code", "") == "AUTH_REQUIRED":
                raise LoginFailure(401, "LOGIN_DENIED", consumed=True) from None
            raise LoginFailure(503, "LOGIN_UNAVAILABLE", consumed=True) from None
        finally:
            if attempt.flow is not None:
                attempt.flow.verifier = ""

    @staticmethod
    def _headers(scope):
        headers = {}
        _require(len(scope.get("headers", [])) <= 64)
        total = 0
        for key, value in scope.get("headers", []):
            total += len(key) + len(value)
            key, value = key.decode("ascii").lower(), value.decode("latin-1")
            _require(total <= 8192 and len(value) <= 4096 and key not in headers
                     and not any(ord(c) < 32 or ord(c) == 127 for c in value))
            headers[key] = value
        _require("authorization" not in headers, 403, "LOGIN_DENIED")
        return headers

    def _same_origin(self, headers):
        return (headers.get("origin") == self._configuration.origin
                and headers.get("sec-fetch-site") == "same-origin")

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")[len(scope.get("root_path", "")):] or "/"
        if path not in LOGIN_PATHS:
            async def workspace_send(message):
                if (self._configuration is not None and path == "/logout" and scope.get("method") == "POST"
                        and message["type"] == "http.response.start" and message["status"] in {200, 401}):
                    try:
                        headers = self._headers(scope)
                        if (self._same_origin(headers) and scope.get("scheme") == "https"
                                and headers.get("host") == urlsplit(self._configuration.origin).netloc):
                            await asyncio.to_thread(self._cancel, headers)
                            message = {**message, "headers": [*message["headers"], (b"set-cookie", _cookie().encode())]}
                    except LoginFailure:
                        pass
                await send(message)
            return await self._workspace(scope, receive, workspace_send)
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return
        extra, headers, attempt = [], {}, None
        try:
            cfg = self._configuration
            _require(cfg is not None, 503, "LOGIN_UNAVAILABLE")
            headers = self._headers(scope)
            _require(scope.get("scheme") == "https" and headers.get("host") == urlsplit(cfg.origin).netloc,
                     403, "LOGIN_DENIED")
            raw = scope.get("query_string", b"")
            _require(len(raw) <= 4096 and re.search(rb"%(?![0-9a-fA-F]{2})", raw) is None)
            pairs = parse_qsl(raw.decode("ascii"), keep_blank_values=True, strict_parsing=True,
                              encoding="utf-8", errors="strict")
            query = _unique(pairs)
            if path == "/login/callback":
                _require(scope["method"] == "GET" and headers.get("sec-fetch-mode") == "navigate"
                         and headers.get("sec-fetch-dest") == "document"
                         and headers.get("sec-fetch-site") in {"cross-site", "same-site", "same-origin", "none"},
                         403, "LOGIN_DENIED")
                attempt = _Attempt()
                status, data, extra = await self._callback(headers, query, attempt)
            else:
                _require(scope["method"] == "POST" and not query and self._same_origin(headers)
                         and headers.get("content-type") == "application/json", 403, "LOGIN_DENIED")
                body, chunks = bytearray(), 0
                deadline = asyncio.get_running_loop().time() + 3
                while True:
                    event = await asyncio.wait_for(receive(), max(0, deadline - asyncio.get_running_loop().time()))
                    chunks += 1
                    _require(chunks <= 8 and event["type"] == "http.request"
                             and len(body) + len(event.get("body", b"")) <= 16)
                    body.extend(event.get("body", b""))
                    if not event.get("more_body", False):
                        break
                _require(json.loads(body) == {})
                if path == "/login/start":
                    attempt = _Attempt()
                    try:
                        status, data, extra = await asyncio.to_thread(self._start, headers, attempt)
                    except asyncio.CancelledError:
                        attempt.cancelled.set()
                        self._cleanup(self._abandon, attempt)
                        raise
                else:
                    discarded = await asyncio.to_thread(self._cancel, headers)
                    status, data, extra = 200, b'{"status":"cancelled"}', [(b"set-cookie", _cookie().encode())]
                    if discarded:
                        extra.append((b"set-cookie", self._workspace._cookie().encode()))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            invalid = type(error) is ValueError or isinstance(error, (UnicodeError, json.JSONDecodeError))
            status = error.status if isinstance(error, LoginFailure) else 400 if invalid else 503
            code = error.code if isinstance(error, LoginFailure) else "LOGIN_INVALID" if invalid else "LOGIN_UNAVAILABLE"
            if getattr(error, "consumed", False):
                extra = [(b"set-cookie", _cookie().encode())]
            data = json.dumps({"code": code}, separators=(",", ":")).encode()
        try:
            await send({"type": "http.response.start", "status": status, "headers": [
                (b"content-type", b"application/json; charset=utf-8"), (b"cache-control", b"private, no-store"),
                (b"referrer-policy", b"no-referrer"), (b"x-content-type-options", b"nosniff"),
                (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
                (b"vary", b"Cookie, Origin"), *extra]})
            await send({"type": "http.response.body", "body": data})
        except BaseException as error:
            if attempt is not None and attempt.flow is not None:
                # Delivery failure owns only this request's reserved/consumed flow.
                # A shared browser cookie may also belong to a concurrent callback.
                cleanup = self._cleanup(self._abandon, attempt)
                if not isinstance(error, asyncio.CancelledError):
                    await asyncio.shield(cleanup)
            raise
