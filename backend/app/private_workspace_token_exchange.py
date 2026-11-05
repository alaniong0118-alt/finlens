"""Dormant, explicitly pinned HTTPS transport for the existing PKCE login seam.

No discovery, configuration from environment, provider defaults or global client.
MockTransport injection is an offline test seam, not a TLS/network acceptance.
"""
import asyncio
from dataclasses import dataclass, field
import re
import ssl
from urllib.parse import urlsplit

import certifi
import httpx

from app.private_workspace_login import (
    EXCHANGE_SECONDS, MAX_REPLY, LoginFailure, TokenExchange, TokenReply,
)

MAX_REQUEST_BYTES = 16 * 1024
MAX_HEADER_BYTES = 8 * 1024
JSON_TYPES = {"application/json", "application/json; charset=utf-8"}


def _tls_context():
    # Mirror Python's verified client defaults, without create_default_context's
    # ambient SSLKEYLOGFILE handling or OpenSSL ambient certificate-path lookup.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
    context.keylog_filename = None
    context.load_verify_locations(cafile=certifi.where())
    return context


def _require(condition):
    if not condition:
        raise LoginFailure(503, "LOGIN_UNAVAILABLE")


def _endpoint(value):
    try:
        _require(type(value) is str and 0 < len(value) <= 2048 and value.isascii()
                 and not any(ord(c) <= 32 or ord(c) == 127 for c in value))
        parsed = urlsplit(value)
        _require(parsed.scheme == "https" and parsed.hostname is not None
                 and len(parsed.hostname) <= 253
                 and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                         for label in parsed.hostname.split("."))
                 and parsed.username is None and parsed.password is None
                 and parsed.port != 0 and not parsed.query and not parsed.fragment
                 and not any(c in value for c in "?#\\%")
                 and not any(segment in {".", ".."} for segment in parsed.path.split("/"))
                 and re.fullmatch(r"/[A-Za-z0-9/._~-]*", parsed.path) is not None
                 and str(httpx.URL(value)) == value)
    except (ValueError, httpx.InvalidURL):
        raise LoginFailure(503, "LOGIN_UNAVAILABLE") from None


@dataclass(frozen=True, slots=True, repr=False)
class HttpsTokenExchange:
    """Trusted server code must explicitly supply the exact configured endpoint.

    Each invocation owns its client and response. The existing login seam remains
    default-off and retains response JSON, signature, invite and state checks.
    """
    endpoint: str
    _test_transport: httpx.MockTransport | None = field(default=None, repr=False)

    def __post_init__(self):
        _endpoint(self.endpoint)
        _require(self._test_transport is None or type(self._test_transport) is httpx.MockTransport)

    async def __call__(self, request):
        _require(type(request) is TokenExchange and type(request.url) is str
                 and request.url == self.endpoint and type(request.body) is bytes
                 and 0 < len(request.body) <= MAX_REQUEST_BYTES
                 and type(request.timeout_seconds) is int and 1 <= request.timeout_seconds <= EXCHANGE_SECONDS
                 and type(request.max_response_bytes) is int and 1 <= request.max_response_bytes <= MAX_REPLY
                 and request.follow_redirects is False
                 and type(request.content_type) is str
                 and request.content_type == "application/x-www-form-urlencoded")
        try:
            async with asyncio.timeout(request.timeout_seconds):
                limits = httpx.Limits(max_connections=1, max_keepalive_connections=0)
                transport = self._test_transport
                tls = True if transport is not None else _tls_context()
                if transport is None:
                    transport = httpx.AsyncHTTPTransport(verify=tls, trust_env=False, retries=0,
                                                        limits=limits, http1=True, http2=False)
                async with httpx.AsyncClient(transport=transport, verify=tls, trust_env=False,
                        auth=None, follow_redirects=False, timeout=httpx.Timeout(request.timeout_seconds),
                        limits=limits, http1=True, http2=False) as client:
                    async with client.stream("POST", self.endpoint, content=request.body,
                            headers={"Content-Type": request.content_type, "Accept": "application/json",
                                     "Accept-Encoding": "identity"}, follow_redirects=False) as response:
                        _require(response.status_code == 200 and str(response.url) == self.endpoint)
                        pairs = response.headers.raw
                        _require(sum(len(k) + len(v) for k, v in pairs) <= MAX_HEADER_BYTES)
                        for key in ("content-type", "content-length", "content-encoding", "transfer-encoding"):
                            _require(len(response.headers.get_list(key)) <= 1)
                        content_type = response.headers.get("content-type", "")
                        length = response.headers.get("content-length")
                        encoding = response.headers.get("content-encoding")
                        transfer = response.headers.get("transfer-encoding")
                        _require(content_type in JSON_TYPES and encoding in (None, "identity")
                                 and transfer in (None, "chunked") and not (length is not None and transfer is not None))
                        if length is not None:
                            _require(re.fullmatch(r"[0-9]{1,5}", length) is not None
                                     and 0 < int(length) <= request.max_response_bytes)
                        body = bytearray()
                        async for part in response.aiter_raw(chunk_size=4096):
                            _require(len(body) + len(part) <= request.max_response_bytes)
                            body.extend(part)
                        _require(0 < len(body) <= request.max_response_bytes
                                 and (length is None or len(body) == int(length)))
                        return TokenReply(200, content_type, bytes(body))
        except asyncio.CancelledError:
            raise
        except Exception:
            # A close failure must not replace an outstanding caller cancellation.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError from None
            # No response body, request, token, code, verifier or transport text.
            raise LoginFailure(503, "LOGIN_UNAVAILABLE") from None
