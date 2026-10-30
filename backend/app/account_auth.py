"""Dormant single-issuer API-token verification; no discovery, I/O or configuration loading.

Only trusted server composition may install public-key snapshots. These Python
objects are not an OS boundary against privileged code. No production policy is
shipped. Ownership verification never grants financial or source authority.
"""
from dataclasses import dataclass, field
import base64
import json
import math
from threading import RLock
import time
from types import MappingProxyType
from urllib.parse import urlsplit

import jwt


MAX_TOKEN = 16 * 1024
MAX_JWKS = 64 * 1024
MAX_KEYS = 16
SKEW = 30
MAX_LIFETIME = 900
MAX_SNAPSHOT_AGE = 3600


class AuthFailure(ValueError):
    def __init__(self, code="AUTH_INVALID"):
        self.code = code
        super().__init__(code)


def require(condition, code="AUTH_INVALID"):
    if not condition:
        raise AuthFailure(code)


def _text(value, limit):
    if type(value) is not str:
        return False
    try:
        return (0 < len(value.encode("utf-8")) <= limit
                and not any(ord(c) < 32 or ord(c) == 127 for c in value))
    except UnicodeError:
        return False


def _https(value):
    require(_text(value, 2048), "AUTH_CONFIGURATION_INVALID")
    url = urlsplit(value)
    require(url.scheme == "https" and bool(url.hostname) and url.username is None
            and url.password is None and not url.fragment and not url.query,
            "AUTH_CONFIGURATION_INVALID")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _json(data):
    try:
        result = json.loads(data, object_pairs_hook=_unique,
                            parse_constant=lambda _: require(False))
        stack = [(result, 0)]
        nodes = 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            require(depth <= 8 and nodes <= 1024)
            if type(value) is dict:
                stack.extend((v, depth + 1) for v in value.values())
            elif type(value) is list:
                stack.extend((v, depth + 1) for v in value)
        require(type(result) is dict)
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AuthFailure() from None


@dataclass(frozen=True, slots=True)
class IssuerPolicy:
    issuer: str
    audience: str
    client_id: str
    jwks_uri: str

    def __post_init__(self):
        _https(self.issuer)
        _https(self.jwks_uri)
        require(_text(self.audience, 2048) and _text(self.client_id, 255)
                and self.audience != self.client_id, "AUTH_CONFIGURATION_INVALID")


@dataclass(frozen=True, slots=True)
class KeySnapshot:
    source_uri: str
    revision: int
    fetched_at: int
    valid_until: int
    jwks: bytes = field(repr=False)

    def __post_init__(self):
        _https(self.source_uri)
        require(type(self.revision) is int and 0 < self.revision < 2**63
                and type(self.fetched_at) is int and self.fetched_at >= 0
                and type(self.valid_until) is int
                and 0 < self.valid_until - self.fetched_at <= MAX_SNAPSHOT_AGE
                and type(self.jwks) is bytes and 0 < len(self.jwks) <= MAX_JWKS,
                "AUTH_CONFIGURATION_INVALID")


@dataclass(frozen=True, slots=True, repr=False)
class _Subject:
    issuer: str
    subject: str
    issued_at: int
    expires_at: int
    not_before: int | None
    key_revision: int


class SingleIssuerVerifier:
    """Unconfigured by default. No request can supply trust or a key resolver."""

    def __init__(self, policy=None, snapshot=None, *, clock=time.time, monotonic=time.monotonic):
        require(policy is None or type(policy) is IssuerPolicy, "AUTH_CONFIGURATION_INVALID")
        self._policy = policy
        self._clock, self._monotonic = clock, monotonic
        self._lock = RLock()
        self._snapshot = None
        self._keys = MappingProxyType({})
        self._sample = None
        if snapshot is not None:
            self.install_snapshot(snapshot)

    def _now(self):
        wall, mono = self._clock(), self._monotonic()
        require(type(wall) in (int, float) and math.isfinite(wall) and wall >= 0
                and type(mono) in (int, float) and math.isfinite(mono), "AUTH_CLOCK_INVALID")
        if self._sample is not None:
            old_wall, old_mono = self._sample
            require(mono >= old_mono and abs((wall - old_wall) - (mono - old_mono)) <= SKEW,
                    "AUTH_CLOCK_INVALID")
        self._sample = wall, mono
        return wall, mono

    def install_snapshot(self, snapshot):
        """Server control plane only; no configuration or URL is read from tokens."""
        with self._lock:
            require(self._policy is not None, "AUTH_UNAVAILABLE")
            require(type(snapshot) is KeySnapshot and snapshot.source_uri == self._policy.jwks_uri
                    and (self._snapshot is None or snapshot.revision > self._snapshot.revision),
                    "AUTH_CONFIGURATION_INVALID")
            now, mono = self._now()
            require(snapshot.fetched_at <= now + SKEW and now < snapshot.valid_until,
                    "AUTH_KEYS_STALE")
            data = _json(snapshot.jwks)
            require(set(data) == {"keys"} and type(data["keys"]) is list
                    and 0 < len(data["keys"]) <= MAX_KEYS, "AUTH_CONFIGURATION_INVALID")
            keys = {}
            try:
                for raw in data["keys"]:
                    require(type(raw) is dict and raw.get("kty") == "RSA"
                            and raw.get("alg", "RS256") == "RS256"
                            and raw.get("use", "sig") == "sig"
                            and raw.get("key_ops", ["verify"]) == ["verify"]
                            and not (set(raw) & {"d", "p", "q", "dp", "dq", "qi", "oth"})
                            and _text(raw.get("kid"), 128) and raw["kid"] not in keys,
                            "AUTH_CONFIGURATION_INVALID")
                    key = jwt.PyJWK.from_dict(raw, algorithm="RS256").key
                    require(2048 <= key.key_size <= 4096, "AUTH_CONFIGURATION_INVALID")
                    keys[raw["kid"]] = key
            except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
                raise AuthFailure("AUTH_CONFIGURATION_INVALID") from None
            self._snapshot, self._keys = snapshot, MappingProxyType(keys)
            self._installed_mono, self._remaining = mono, snapshot.valid_until - now

    def _active(self):
        require(self._policy is not None and self._snapshot is not None, "AUTH_UNAVAILABLE")
        now, mono = self._now()
        require(now < self._snapshot.valid_until
                and mono - self._installed_mono < self._remaining, "AUTH_KEYS_STALE")
        return now

    @staticmethod
    def _times(subject, now):
        require(subject.issued_at <= now + SKEW and now < subject.expires_at + SKEW
                and (subject.not_before is None or subject.not_before <= now + SKEW))

    def verify_principal(self, token):
        with self._lock:
            now = self._active()
            require(type(token) is str and token.isascii() and 0 < len(token) <= MAX_TOKEN)
            try:
                parts = token.split(".")
                require(len(parts) == 3 and all(parts))
                header, payload = [_json(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
                                   for p in parts[:2]]
                require(header.get("alg") == "RS256" and header.get("typ") in {"at+jwt", "application/at+jwt"}
                        and not (set(header) & {"jku", "x5u", "jwk", "crit", "b64"})
                        and _text(header.get("kid"), 128))
                require(header["kid"] in self._keys, "AUTH_KEY_UNKNOWN")
                claims = jwt.decode(token, self._keys[header["kid"]], algorithms=["RS256"],
                    issuer=self._policy.issuer, audience=self._policy.audience,
                    options={"require": ["iss", "aud", "sub", "client_id", "jti", "iat", "exp"],
                             "verify_iat": False, "verify_exp": False, "verify_nbf": False})
                require(claims == payload and claims["iss"] == self._policy.issuer
                        and claims["client_id"] == self._policy.client_id
                        and _text(claims["sub"], 255) and _text(claims["jti"], 255)
                        and not (set(claims) & {"act", "sub_profile", "client_profile"}))
                audiences = [claims["aud"]] if type(claims["aud"]) is str else claims["aud"]
                require(type(audiences) is list and 0 < len(audiences) <= 4
                        and all(_text(a, 2048) for a in audiences)
                        and len(set(audiences)) == len(audiences)
                        and self._policy.client_id not in audiences)
                require(type(claims["iat"]) is int and claims["iat"] >= 0
                        and type(claims["exp"]) is int
                        and 0 < claims["exp"] - claims["iat"] <= MAX_LIFETIME
                        and ("nbf" not in claims or (type(claims["nbf"]) is int
                             and 0 <= claims["nbf"] < claims["exp"])))
                subject = _Subject(claims["iss"], claims["sub"], claims["iat"], claims["exp"],
                                   claims.get("nbf"), self._snapshot.revision)
                self._times(subject, now)
                return subject
            except AuthFailure:
                raise
            except (jwt.PyJWTError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
                raise AuthFailure() from None

    def recheck(self, subject, *, database_time=None):
        """Internal lifecycle check, not an entrypoint accepting caller principals."""
        with self._lock:
            now = self._active()
            require(type(subject) is _Subject and subject.key_revision == self._snapshot.revision,
                    "AUTH_CONFIGURATION_CHANGED")
            self._times(subject, now)
            if database_time is not None:
                require(type(database_time) in (int, float) and math.isfinite(database_time)
                        and database_time >= 0 and abs(database_time - now) <= SKEW,
                        "AUTH_CLOCK_INVALID")
                self._times(subject, database_time)
