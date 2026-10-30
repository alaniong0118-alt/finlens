"""Standalone offline cryptographic tests; guards precede every application import.

Run from repository root with backend/.venv/Scripts/python.exe -I -S -B this_file.
Private RSA keys exist only in memory. No production issuer or account is seeded.
"""
import builtins
from dataclasses import FrozenInstanceError, replace
import importlib.abc
import io
import json
import os
from pathlib import Path
import socket
import sys
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND / ".venv" / "Lib" / "site-packages"), str(BACKEND), str(BACKEND / "tests")]


def forbidden(*args, **kwargs):
    raise AssertionError("offline_forbidden_effect")


def protect(original):
    def guarded(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(path)).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                forbidden()
        return original(path, *args, **kwargs)
    return guarded


builtins.open = protect(builtins.open)
io.open = protect(io.open)
os.open = protect(os.open)
socket.socket.connect = socket.socket.connect_ex = forbidden
socket.create_connection = socket.getaddrinfo = forbidden
# SQLAlchemy's Windows platform probe asks for the local hostname. Supply inert
# metadata while keeping every real socket audit event, DNS and connection denied.
socket.gethostname = lambda: "offline-test-host"


class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        allowed = {"app", "app.account_auth", "app.research_ownership", "app.research_contracts",
                   "app.models", "app.orm_base"}
        if (fullname.startswith("app.") and fullname not in allowed
                or fullname.split(".")[0] in {"dotenv", "uvicorn", "fastapi", "torch", "sentence_transformers"}):
            forbidden()


sys.meta_path.insert(0, ImportGuard())


def audit(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in {"sqlite3.connect", "os.system"}:
        forbidden()


sys.addaudithook(audit)
import psycopg
psycopg.connect = forbidden
psycopg.Connection.connect = classmethod(forbidden)
psycopg.AsyncConnection.connect = classmethod(forbidden)
import sqlite3
sqlite3.connect = forbidden

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from app import account_auth as auth


class Clock:
    def __init__(self):
        self.wall, self.mono = 2_000_000_000.0, 100.0

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


class CryptoFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.clock = Clock()
        self.policy = auth.IssuerPolicy("https://offline.invalid/", "offline-finlens-api", "offline-web",
                                        "https://offline.invalid/keys")
        self.snapshot = self.make_snapshot()
        self.verifier = auth.SingleIssuerVerifier(self.policy, self.snapshot,
            clock=lambda: self.clock.wall, monotonic=lambda: self.clock.mono)

    def jwk(self, key=None, kid="offline"):
        raw = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk((key or self.key).public_key()))
        raw.update(kid=kid, alg="RS256", use="sig", key_ops=["verify"])
        return raw

    def make_snapshot(self, keys=None, revision=1):
        return auth.KeySnapshot(self.policy.jwks_uri, revision, int(self.clock.wall),
            int(self.clock.wall) + 3600, json.dumps({"keys": keys or [self.jwk()]}).encode())

    def claims(self, **changes):
        now = int(self.clock.wall)
        result = dict(iss=self.policy.issuer, aud=self.policy.audience, client_id=self.policy.client_id,
                      sub="offline-alice", jti="offline-jti", iat=now, exp=now + 300)
        result.update(changes)
        return result

    def token(self, *, claims=None, headers=None, key=None, **changes):
        return jwt.encode(self.claims(**changes) if claims is None else claims,
            key or self.key, algorithm="RS256", headers=headers or {"kid": "offline", "typ": "at+jwt"})

    def raw_token(self, header, payload):
        import base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        def segment(data):
            return base64.urlsafe_b64encode(data).rstrip(b"=")
        message = segment(header) + b"." + segment(payload)
        signature = self.key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return (message + b"." + segment(signature)).decode()

    def denied(self, callback, code=None):
        with self.assertRaises(auth.AuthFailure) as caught:
            callback()
        if code:
            self.assertEqual(caught.exception.code, code)


class AuthTests(CryptoFixtures):
    def test_real_signature_profile_and_multi_audience(self):
        for typ in ("at+jwt", "application/at+jwt"):
            subject = self.verifier.verify_principal(self.token(headers={"kid": "offline", "typ": typ},
                aud=[self.policy.audience, "offline-userinfo"]))
            self.assertEqual(subject.subject, "offline-alice")
            self.verifier.recheck(subject, database_time=self.clock.wall)

    def test_no_configuration_or_caller_principal_bypass(self):
        self.denied(lambda: auth.SingleIssuerVerifier().verify_principal(self.token()), "AUTH_UNAVAILABLE")
        self.denied(lambda: self.verifier.verify_principal(self.verifier.verify_principal(self.token())))

    def test_bad_signature_and_missing_required_claims(self):
        self.denied(lambda: self.verifier.verify_principal(self.token(key=self.other_key)))
        for name in ("iss", "aud", "sub", "client_id", "jti", "iat", "exp"):
            with self.subTest(name=name):
                claims = self.claims()
                del claims[name]
                self.denied(lambda: self.verifier.verify_principal(self.token(claims=claims)))

    def test_id_tokens_wrong_issuer_audience_client_and_delegation(self):
        for changes in (dict(iss="https://other.invalid/"), dict(aud="other"), dict(aud=self.policy.client_id),
                        dict(client_id="machine-client"), dict(act={"sub": "agent"}),
                        dict(aud=[self.policy.audience, self.policy.client_id]), dict(sub_profile="agent")):
            with self.subTest(fields=list(changes)):
                self.denied(lambda: self.verifier.verify_principal(self.token(**changes)))
        self.denied(lambda: self.verifier.verify_principal(self.token(headers={"kid": "offline", "typ": "JWT"})))

    def test_untrusted_key_urls_and_critical_headers(self):
        for name, value in (("jku", "https://host.invalid/"), ("x5u", "https://host.invalid/"),
                            ("jwk", self.jwk()), ("crit", ["example"]), ("b64", True)):
            with self.subTest(header=name):
                # PyJWT's encoder removes redundant b64=true; sign exact bytes
                # so the decoder really receives every prohibited header.
                token = self.raw_token(json.dumps({"kid": "offline", "typ": "at+jwt",
                    "alg": "RS256", name: value}).encode(), json.dumps(self.claims()).encode())
                self.denied(lambda: self.verifier.verify_principal(token))
        self.denied(lambda: self.verifier.verify_principal(self.token(headers={"kid": "unknown", "typ": "at+jwt"})),
                    "AUTH_KEY_UNKNOWN")

    def test_none_and_hmac_are_not_accepted(self):
        for algorithm, key in (("none", None), ("HS256", "synthetic-test-secret" * 4)):
            token = jwt.encode(self.claims(), key, algorithm=algorithm,
                               headers={"kid": "offline", "typ": "at+jwt"})
            self.denied(lambda: self.verifier.verify_principal(token))

    def test_typed_times_lifetime_and_skew_boundaries(self):
        now = int(self.clock.wall)
        for changes in (dict(iat=True), dict(iat=str(now)), dict(exp=float(now + 300)),
                        dict(exp=now), dict(exp=now + 901), dict(iat=now + 31),
                        dict(nbf=now + 31), dict(nbf=True), dict(exp=now - 30, iat=now - 300)):
            with self.subTest(fields=list(changes)):
                self.denied(lambda: self.verifier.verify_principal(self.token(**changes)))
        self.verifier.verify_principal(self.token(iat=now + 30, exp=now + 300, nbf=now + 30))
        self.verifier.verify_principal(self.token(iat=now - 300, exp=now - 29))

    def test_claim_scalar_limits_and_no_email_identity(self):
        for field in ("sub", "jti"):
            for value in ("", [], "x" * 256, "a\n"):
                self.denied(lambda: self.verifier.verify_principal(self.token(**{field: value})))
        self.assertEqual(self.verifier.verify_principal(self.token(email="forged@example.invalid")).subject,
                         "offline-alice")

    def test_shape_duplicates_depth_and_token_size(self):
        import base64
        def segment(value):
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
        for value in ("", "x.y", "a.b.c", "x" * (auth.MAX_TOKEN + 1), "é", None):
            self.denied(lambda: self.verifier.verify_principal(value))
        for raw in (b'{"iss":"one","iss":"two"}', b'{"x":NaN}',
                    b'{"x":' + b'[' * 10 + b'0' + b']' * 10 + b'}'):
            token = self.token().split(".")
            token[1] = segment(raw)
            self.denied(lambda: self.verifier.verify_principal(".".join(token)))

    def test_real_signed_token_at_exact_byte_limit_and_one_over(self):
        exact = None
        for extra in range(3):
            token = self.token(jti="offline-jti" + "x" * extra, padding="x" * 11000)
            # Encoding grows by roughly 4/3; only a short local search is needed.
            start = 11000 + int((auth.MAX_TOKEN - len(token)) * 3 / 4)
            for size in range(start - 3, start + 4):
                candidate = self.token(jti="offline-jti" + "x" * extra, padding="x" * size)
                if len(candidate) == auth.MAX_TOKEN:
                    exact = candidate
                    break
            if exact is not None:
                break
        self.assertIsNotNone(exact)
        self.verifier.verify_principal(exact)
        self.denied(lambda: self.verifier.verify_principal(exact + "x"))

    def test_rotation_invalidates_inflight_identity_and_removed_keys(self):
        identity = self.verifier.verify_principal(self.token())
        new = self.make_snapshot([self.jwk(self.other_key, "next")], revision=2)
        self.verifier.install_snapshot(new)
        self.denied(lambda: self.verifier.recheck(identity), "AUTH_CONFIGURATION_CHANGED")
        self.denied(lambda: self.verifier.verify_principal(self.token()), "AUTH_KEY_UNKNOWN")
        self.verifier.verify_principal(self.token(key=self.other_key, headers={"kid": "next", "typ": "at+jwt"}))
        self.denied(lambda: self.verifier.install_snapshot(new), "AUTH_CONFIGURATION_INVALID")

    def test_snapshot_expiry_and_clock_regression(self):
        self.clock.advance(3600)
        self.denied(lambda: self.verifier.verify_principal(self.token()), "AUTH_KEYS_STALE")
        self.setUp()
        self.clock.wall -= 31
        self.denied(lambda: self.verifier.verify_principal(self.token()), "AUTH_CLOCK_INVALID")

    def test_database_clock_must_agree_and_validate_its_own_time(self):
        subject = self.verifier.verify_principal(self.token(iat=int(self.clock.wall) + 30))
        self.denied(lambda: self.verifier.recheck(subject, database_time=self.clock.wall - 1))
        self.denied(lambda: self.verifier.recheck(subject, database_time=self.clock.wall + 31), "AUTH_CLOCK_INVALID")

    def test_policy_and_snapshot_immutability(self):
        with self.assertRaises(FrozenInstanceError):
            self.policy.issuer = "other"
        for changes in (dict(issuer="http://offline.invalid/"), dict(audience=self.policy.client_id),
                        dict(jwks_uri="https://user:pass@offline.invalid/keys"), dict(client_id="\ud800")):
            self.denied(lambda: replace(self.policy, **changes))
        self.denied(lambda: replace(self.snapshot, valid_until=self.snapshot.fetched_at + 3601))

    def test_key_manifest_and_size_limits(self):
        for keys in ([self.jwk(), self.jwk()], [dict(self.jwk(), use="enc")],
                     [dict(self.jwk(), key_ops=["sign"])], [dict(self.jwk(), d="private")],
                     [dict(self.jwk(), alg="HS256")], [self.jwk(kid=str(i)) for i in range(17)]):
            self.denied(lambda: self.verifier.install_snapshot(self.make_snapshot(keys, 2)))
        self.verifier.install_snapshot(self.make_snapshot([self.jwk(kid=str(i)) for i in range(16)], 2))
        replace(self.snapshot, jwks=b"x" * auth.MAX_JWKS)
        self.denied(lambda: replace(self.snapshot, jwks=b"x" * (auth.MAX_JWKS + 1)))

    def test_guards_block_forbidden_effects_and_no_operational_imports(self):
        for callback in (lambda: socket.getaddrinfo("invalid", 443),
                         lambda: psycopg.connect("unreachable"), lambda: sqlite3.connect(":memory:"),
                         lambda: __import__("app.database"), lambda: __import__("dotenv"),
                         lambda: open(BACKEND / ".env")):
            with self.assertRaises(AssertionError):
                callback()
        self.assertNotIn("app.config", sys.modules)
        self.assertNotIn("app.main", sys.modules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
