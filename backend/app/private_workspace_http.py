"""Default-off ASGI adapter. No provider, settings, engine or credential loading.

Only trusted composition/the separate PKCE wrapper can establish a browser session.
This adapter accepts no raw HTTP token-installation request. Process memory is a
development boundary, not an accepted production/multi-worker session store.
"""
import asyncio
from contextlib import nullcontext
from dataclasses import dataclass
import hmac
import json
import re
import secrets
from threading import RLock
import time
from urllib.parse import parse_qs, urlsplit

from app.research_contracts import KeyRef, decode

COOKIE = "__Host-finlens-research"
MAX_BODY = 48 * 1024
MAX_SESSIONS = 100
SESSION_SECONDS = 300


class _Failure(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code


@dataclass(slots=True, repr=False)
class _Session:
    token: str
    investigation: object
    csrf: str
    deadline: float
    expires_at: float


@dataclass(slots=True)
class _NoteWriteOutcome:
    """Request-local note COMMIT outcome; authorization reads cannot overwrite it."""
    state: str = "not_issued"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _Failure(400, "INVALID_REQUEST")
        result[key] = value
    return result


class PrivateWorkspace:
    """Unconfigured default is unavailable, including session establishment."""
    def __init__(self, service=None, *, origin=None, clock=time.time, monotonic=time.monotonic):
        if service is not None:
            parsed = urlsplit(origin or "")
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path or parsed.query or parsed.fragment or origin != f"https://{parsed.netloc}"):
                raise ValueError("An exact trusted HTTPS browser origin is required.")
        elif origin is not None:
            raise ValueError("No private workspace service is installed.")
        self._service, self._origin = service, origin
        self._clock, self._monotonic = clock, monotonic
        self._sessions, self._lock = {}, RLock()

    @staticmethod
    def _cookie(handle="", age=0):
        return f"{COOKIE}={handle}; Max-Age={age}; Path=/; Secure; HttpOnly; SameSite=Strict"

    def establish(self, token, *, cancellation=None):
        """Internal login-callback seam; returns only a Set-Cookie value.

        Verifies the actual token through the installed ownership verifier. No
        request can provide a session identifier, principal, origin or verifier.
        A new establishment rotates every in-process handle for the same owner.
        """
        with self._lock:
            if self._service is None:
                raise _Failure(503, "PRIVATE_WORKSPACE_UNAVAILABLE")
            if cancellation is not None:
                from app.research_ownership import Cancellation
                if type(cancellation) is not Cancellation:
                    raise _Failure(400, "REQUEST_DENIED")
                if cancellation._cancelled:
                    raise _Failure(401, "AUTH_REQUIRED")
            identity = self._service._verifier.verify_principal(token)
            lifetime = min(SESSION_SECONDS, identity.expires_at - self._clock())
            if lifetime < 1:
                raise _Failure(401, "AUTH_REQUIRED")
            investigation = (self._service.create_session(token, "private-notes", cancellation=cancellation)
                             if cancellation is not None else self._service.create_session(token, "private-notes"))
            with (cancellation._lock if cancellation is not None else nullcontext()):
                if cancellation is not None and cancellation._cancelled:
                    raise _Failure(401, "AUTH_REQUIRED")
                lifetime = min(SESSION_SECONDS, identity.expires_at - self._clock())
                if lifetime < 1:
                    raise _Failure(401, "AUTH_REQUIRED")
                now = self._monotonic()
                self._sessions = {key: value for key, value in self._sessions.items()
                    if value.deadline > now and value.expires_at > self._clock()
                    and value.investigation.owner_key != investigation.owner_key}
                if len(self._sessions) >= MAX_SESSIONS:
                    raise _Failure(503, "PRIVATE_WORKSPACE_UNAVAILABLE")
                handle = secrets.token_urlsafe(32)
                self._sessions[handle] = _Session(token, investigation, secrets.token_urlsafe(32),
                                                  now + lifetime, identity.expires_at)
                return self._cookie(handle, int(lifetime))

    def discard(self, handle):
        """Trusted login lifecycle only: revoke an opaque handle without DB I/O."""
        if type(handle) is not str or re.fullmatch(r"[A-Za-z0-9_-]{43}", handle) is None:
            raise ValueError("Invalid internal browser handle.")
        with self._lock:
            self._sessions.pop(handle, None)

    def _handle(self, headers):
        raw = headers.get("cookie", "")
        if len(raw) > 4096:
            raise _Failure(401, "AUTH_REQUIRED")
        handles = [part.strip().split("=", 1)[1] for part in raw.split(";")
                   if part.strip().startswith(COOKIE + "=")]
        if len(handles) != 1 or re.fullmatch(r"[A-Za-z0-9_-]{43}", handles[0]) is None:
            raise _Failure(401, "AUTH_REQUIRED")
        return handles[0]

    def _authorize(self, handle, session, cancellation):
        if (self._sessions.get(handle) is not session or self._monotonic() >= session.deadline
                or self._clock() >= session.expires_at):
            self._sessions.pop(handle, None)
            raise _Failure(401, "AUTH_REQUIRED")
        root = session.investigation
        try:
            self._service.resolve_session(session.token, root.key, root.revision, cancellation=cancellation)
        except ValueError as error:
            code = getattr(error, "code", "")
            if code.startswith("AUTH_") or code in {"OWNERSHIP_DENIED", "OWNERSHIP_REVISION_CHANGED"}:
                self._sessions.pop(handle, None)
                raise _Failure(401, "AUTH_REQUIRED") from None
            raise

    def _dispatch(self, method, path, headers, query, body, cancellation, note_write):
        with self._lock:
            if self._service is None:
                raise _Failure(503, "PRIVATE_WORKSPACE_UNAVAILABLE")
            if ("authorization" in headers or headers.get("sec-fetch-site", "same-origin") != "same-origin"
                    or headers.get("origin", self._origin) != self._origin):
                raise _Failure(403, "REQUEST_DENIED")
            handle = self._handle(headers)
            session = self._sessions.get(handle)
            if session is None:
                raise _Failure(401, "AUTH_REQUIRED")
            if method == "POST" and (headers.get("origin") != self._origin
                    or headers.get("content-type") != "application/json"
                    or re.fullmatch(r"[A-Za-z0-9_-]{43}", headers.get("x-finlens-csrf", "")) is None
                    or not hmac.compare_digest(headers.get("x-finlens-csrf", ""), session.csrf)):
                raise _Failure(403, "REQUEST_DENIED")
            self._authorize(handle, session, cancellation)
            extra = []
            if method == "GET" and path == "/state" and not query:
                result = dict(status="authenticated", owner_key=session.investigation.owner_key.id, csrf=session.csrf,
                    expires_in=max(0, int(min(session.deadline - self._monotonic(), session.expires_at - self._clock()))))
            elif method == "POST" and path == "/logout" and not query and body == {}:
                self._sessions.pop(handle)
                return b'{"status":"signed_out"}', [(b"set-cookie", self._cookie().encode())]
            elif method == "GET" and path == "/notes" and set(query) <= {"after"}:
                result = json.loads(self._service.list_notes(session.token, query.get("after"), cancellation=cancellation).encode())
            elif method == "GET" and path == "/sources" and set(query) == {"cik"}:
                result = json.loads(self._service.list_note_sources(session.token, query["cik"], cancellation=cancellation).encode())
            elif method == "POST" and path == "/notes" and not query and set(body) == {"request_key", "body", "source"}:
                source = decode(json.dumps(body["source"], separators=(",", ":")).encode("utf-8"))
                root = session.investigation
                from app.account_auth import AuthFailure
                # Once invoked, an unexpected service failure cannot prove the
                # write was not issued. Trust only its explicit lifecycle state.
                note_write.state = "indeterminate"
                try:
                    saved = self._service.save_new_note(session.token, root.key, root.revision,
                        body["request_key"], body["body"], source, cancellation=cancellation)
                except Exception as error:
                    state = getattr(error, "commit_state", None)
                    if state in ("not_issued", "indeterminate", "confirmed"):
                        note_write.state = state
                    elif isinstance(error, AuthFailure):  # Verifier rejection before _run begins its transaction.
                        note_write.state = "not_issued"
                    raise
                note_write.state = "confirmed"
                result = json.loads(saved.encode())
            elif method == "GET" and path in {"/note", "/export"} and set(query) == {
                    "session", "session_revision", "artifact", "artifact_revision"}:
                for field in ("session_revision", "artifact_revision"):
                    if not re.fullmatch(r"[1-9][0-9]{0,18}", query[field]):
                        raise _Failure(400, "INVALID_REQUEST")
                args = (session.token, KeyRef("session", query["session"]), int(query["session_revision"]),
                        KeyRef("artifact", query["artifact"]), int(query["artifact_revision"]))
                result = json.loads(self._service.export_note(*args, cancellation=cancellation))
                if path == "/export":
                    extra = [(b"content-disposition", b'attachment; filename="finlens-research-note.json"')]
            else:
                raise _Failure(400, "INVALID_REQUEST")
            # Logout/rotation cannot interleave with this last delivery check.
            self._authorize(handle, session, cancellation)
            data = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(data) > 65536:
                raise _Failure(503, "PRIVATE_WORKSPACE_UNAVAILABLE")
            return data, extra

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return
        status, extra, cancellation = 200, [], None
        note_write = _NoteWriteOutcome()
        try:
            if self._service is None:
                raise _Failure(503, "PRIVATE_WORKSPACE_UNAVAILABLE")
            headers = {}
            for key, value in scope.get("headers", []):
                key, value = key.decode("ascii").lower(), value.decode("latin-1")
                if key in headers and key in {"cookie", "origin", "authorization", "x-finlens-csrf", "content-type"}:
                    raise _Failure(403, "REQUEST_DENIED")
                headers[key] = value
            method = scope["method"]
            if method not in {"GET", "POST"}:
                raise _Failure(405, "REQUEST_DENIED")
            raw_query = scope.get("query_string", b"")
            if len(raw_query) > 1024:
                raise _Failure(400, "INVALID_REQUEST")
            parsed = parse_qs(raw_query.decode("ascii"), keep_blank_values=True, strict_parsing=True)
            if any(len(values) != 1 for values in parsed.values()):
                raise _Failure(400, "INVALID_REQUEST")
            query = {key: values[0] for key, values in parsed.items()}
            body = {}
            if method == "POST":
                data, deadline = bytearray(), asyncio.get_running_loop().time() + 3
                while True:
                    event = await asyncio.wait_for(receive(), max(0, deadline - asyncio.get_running_loop().time()))
                    if event["type"] != "http.request":
                        raise _Failure(400, "INVALID_REQUEST")
                    chunk = event.get("body", b"")
                    if len(data) + len(chunk) > MAX_BODY:
                        raise _Failure(413, "INVALID_REQUEST")
                    data.extend(chunk)
                    if not event.get("more_body", False):
                        break
                body = json.loads(data, object_pairs_hook=_unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                if type(body) is not dict:
                    raise _Failure(400, "INVALID_REQUEST")
            # Import only after trusted composition exists; never initialize an
            # app/database/provider stack to answer the default-off request.
            from app.research_ownership import Cancellation
            cancellation = Cancellation()
            path = scope["path"][len(scope.get("root_path", "")):] or "/"
            data, extra = await asyncio.to_thread(self._dispatch, method, path, headers, query, body, cancellation, note_write)
        except asyncio.CancelledError:
            if cancellation is not None:
                cancellation.cancel()
            raise
        except Exception as error:
            code = getattr(error, "code", None)
            if isinstance(error, _Failure):
                status = error.status
            elif code and code.startswith("AUTH_"):
                status, code = 401, "AUTH_REQUIRED"
            elif code == "OWNERSHIP_DENIED":
                status = 404
            elif code in {"OWNERSHIP_IDEMPOTENCY_CONFLICT", "OWNERSHIP_REVISION_CHANGED"}:
                status = 409
            elif code in {"OWNERSHIP_SELECTOR_INVALID", "OWNERSHIP_NOTE_INVALID", "INVALID_REQUEST"}:
                status = 400
            elif code is None and isinstance(error, (ValueError, UnicodeError)) and note_write.state == "not_issued":
                status, code = 400, "INVALID_REQUEST"
            else:
                status, code = 503, "PRIVATE_WORKSPACE_UNAVAILABLE"
            data = json.dumps(dict(code=code, commit_state=note_write.state),
                              separators=(",", ":")).encode()
            if status == 401:
                extra = [(b"set-cookie", self._cookie().encode())]
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json; charset=utf-8"), (b"cache-control", b"private, no-store"),
            (b"x-content-type-options", b"nosniff"), (b"vary", b"Cookie, Origin"), *extra]})
        await send({"type": "http.response.body", "body": data})
