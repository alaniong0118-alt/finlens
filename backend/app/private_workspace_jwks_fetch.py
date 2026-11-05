"""Dormant exact-URI fetch; returned bytes are not installed or trusted keys."""
import asyncio
from dataclasses import dataclass, field
import math
import re
import ssl
import time
from urllib.parse import urlsplit

import certifi
import httpx

from app.account_auth import AuthFailure, IssuerPolicy, KeySnapshot, MAX_JWKS, MAX_SNAPSHOT_AGE, SKEW

FETCH_SECONDS = 5
MAX_HEADER_BYTES = 8192
JSON_TYPES = {"application/json", "application/json; charset=utf-8",
              "application/jwk-set+json", "application/jwk-set+json; charset=utf-8"}


def _require(condition, code="AUTH_UNAVAILABLE"):
    if not condition:
        raise AuthFailure(code)


def _endpoint(value):
    try:
        _require(type(value) is str and 0 < len(value) <= 2048 and value.isascii()
                 and not any(ord(c) <= 32 or ord(c) == 127 for c in value), "AUTH_CONFIGURATION_INVALID")
        parsed = urlsplit(value)
        _require(parsed.scheme == "https" and parsed.hostname is not None
                 and len(parsed.hostname) <= 253
                 and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                         for label in parsed.hostname.split("."))
                 and parsed.username is None and parsed.password is None and parsed.port != 0
                 and not any(c in value for c in "?#\\%")
                 and not any(segment in {".", ".."} for segment in parsed.path.split("/"))
                 and re.fullmatch(r"/[A-Za-z0-9/._~-]*", parsed.path) is not None
                 and str(httpx.URL(value)) == value, "AUTH_CONFIGURATION_INVALID")
    except (ValueError, httpx.InvalidURL):
        raise AuthFailure("AUTH_CONFIGURATION_INVALID") from None


def _tls_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
    context.keylog_filename = None
    context.load_verify_locations(cafile=certifi.where())
    return context


def _sample(clock, monotonic):
    wall, mono = clock(), monotonic()
    _require(type(wall) in (int, float) and math.isfinite(wall)
             and 0 <= wall <= 2**63 - 1 - MAX_SNAPSHOT_AGE
             and type(mono) in (int, float) and math.isfinite(mono))
    return wall, mono


@dataclass(frozen=True, slots=True, repr=False)
class HttpsJwksSnapshotFetcher:
    """Only explicit trusted composition can fetch and later install a snapshot.

    No verifier is accepted or mutated. Malformed key bytes remain untrusted
    until SingleIssuerVerifier.install_snapshot validates them separately.
    """
    policy: IssuerPolicy = field(repr=False)
    _test_transport: httpx.MockTransport | None = field(default=None, repr=False)
    clock: object = field(default=time.time, repr=False)
    monotonic: object = field(default=time.monotonic, repr=False)

    def __post_init__(self):
        _require(type(self.policy) is IssuerPolicy and callable(self.clock) and callable(self.monotonic),
                 "AUTH_CONFIGURATION_INVALID")
        _endpoint(self.policy.jwks_uri)
        _require(self._test_transport is None or type(self._test_transport) is httpx.MockTransport,
                 "AUTH_CONFIGURATION_INVALID")

    async def __call__(self, *, revision, lifetime_seconds):
        _require(type(revision) is int and 0 < revision < 2**63
                 and type(lifetime_seconds) is int and 0 < lifetime_seconds <= MAX_SNAPSHOT_AGE,
                 "AUTH_CONFIGURATION_INVALID")
        try:
            async with asyncio.timeout(FETCH_SECONDS):
                wall, mono = _sample(self.clock, self.monotonic)
                fetched_at = int(wall)
                until = fetched_at + lifetime_seconds
                limits = httpx.Limits(max_connections=1, max_keepalive_connections=0)
                transport = self._test_transport
                tls = True if transport is not None else _tls_context()
                if transport is None:
                    transport = httpx.AsyncHTTPTransport(verify=tls, trust_env=False, retries=0,
                                                        limits=limits, http1=True, http2=False)
                async with httpx.AsyncClient(transport=transport, verify=tls, trust_env=False,
                        auth=None, follow_redirects=False, timeout=httpx.Timeout(FETCH_SECONDS),
                        limits=limits, http1=True, http2=False) as client:
                    async with client.stream("GET", self.policy.jwks_uri,
                            headers={"Accept": "application/jwk-set+json, application/json",
                                     "Accept-Encoding": "identity"}, follow_redirects=False) as response:
                        _require(response.status_code == 200 and str(response.url) == self.policy.jwks_uri)
                        _require(sum(len(k) + len(v) for k, v in response.headers.raw) <= MAX_HEADER_BYTES)
                        for key in ("content-type", "content-length", "content-encoding", "transfer-encoding"):
                            _require(len(response.headers.get_list(key)) <= 1)
                        media = response.headers.get("content-type", "")
                        length = response.headers.get("content-length")
                        encoding = response.headers.get("content-encoding")
                        transfer = response.headers.get("transfer-encoding")
                        _require(media in JSON_TYPES and encoding in (None, "identity")
                                 and transfer in (None, "chunked") and not (length is not None and transfer is not None))
                        if length is not None:
                            _require(re.fullmatch(r"[0-9]{1,5}", length) is not None and 0 < int(length) <= MAX_JWKS)
                        body = bytearray()
                        async for part in response.aiter_raw(chunk_size=4096):
                            _require(len(body) + len(part) <= MAX_JWKS)
                            body.extend(part)
                        _require(0 < len(body) <= MAX_JWKS and (length is None or len(body) == int(length)))
                end_wall, end_mono = _sample(self.clock, self.monotonic)
                _require(end_wall >= wall and end_mono >= mono
                         and abs((end_wall - wall) - (end_mono - mono)) <= SKEW
                         and end_wall < until and end_mono - mono < lifetime_seconds)
                return KeySnapshot(self.policy.jwks_uri, revision, fetched_at, until, bytes(body))
        except asyncio.CancelledError:
            raise
        except Exception:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError from None
            raise AuthFailure("AUTH_UNAVAILABLE") from None
