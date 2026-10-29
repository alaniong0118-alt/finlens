"""Authored synthetic controls; no SEC, database, model or service access.

Run only: backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_identity_capture.py
"""

import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import research_contracts as c
from app import universal_identity as u
from app import sec_identity_source as s
from app import sec_identity_capture as k


CIK = "0000123456"
UUID = "12345678-1234-4234-8234-123456789abc"
RAW = b'{"cik":"123456","name":"Synthetic Issuer"}'


def identity(module=k, **changes):
    values = dict(operation_uuid=UUID, owner_ref=c.KeyRef("principal", "synthetic-owner"),
                  session_ref=c.KeyRef("session", "synthetic-session"),
                  request=module.build_submissions_request(CIK),
                  policy_ref=c.KeyRef("rights_policy", "synthetic-policy"), policy_revision="v1",
                  original_start="2026-10-29T00:00:00.000000Z")
    values.update(changes)
    return module.ReplayIdentity(**values)


def context(module=k, *, offset=6, cancelled=False, revoked=False, **changes):
    return module.SyntheticContext(identity(module, **changes),
                                   module.SyntheticObservation(offset, cancelled, revoked))


def exchange(module=k, raw=RAW, **changes):
    values = dict(observed_url=module.build_submissions_request(CIK).url, status=200,
                  headers=(("Content-Length", str(len(raw))),), body_blocks=(raw,),
                  phases=module.PhaseCheckpoints(0, 1, 2, 3, 5, 6),
                  block_observations=(module.BlockObservation(0, 4),))
    values.update(changes)
    return module.SyntheticExchange(**values)


def capture(module=k, raw=RAW, ctx=None, ex=None):
    ctx = context(module) if ctx is None else ctx
    return module.capture_synthetic_submissions(ctx.identity.request, context=ctx,
                                              exchange=exchange(module, raw) if ex is None else ex)


def bypass(record, **changes):
    result = replace(record)
    for name, value in changes.items():
        object.__setattr__(result, name, value)
    return result


def delivery_decision(module=k, **changes):
    values = dict(allowed=True, reason="synthetic_only", operation_uuid=UUID,
                  receipt_sha256="0" * 64, observation=module.SyntheticObservation(7),
                  original_deadline_ns=module.MAX_OPERATION_NS)
    values.update(changes)
    return module.SyntheticDeliveryDecision(**values)


class CaptureTestCase(unittest.TestCase):
    def reject(self, function, code=None, exception=k.SyntheticCaptureError):
        with self.assertRaises(exception) as caught:
            function()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(str(caught.exception), code)


class CaptureTests(CaptureTestCase):
    def test_minimal_issuer_and_exact_bytes_receipt_binding(self):
        cap = capture()
        bound = k.bind_synthetic_capture(cap)
        self.assertEqual(bound.capture, cap)
        self.assertEqual(bound.source_bound.original_bytes, RAW)
        self.assertEqual(cap.original_bytes, RAW)
        self.assertEqual(cap.body_sha256, hashlib.sha256(RAW).hexdigest())
        self.assertEqual(cap.body_sha256, bound.source_bound.response_sha256)
        self.assertEqual(cap.receipt_sha256, hashlib.sha256(cap.receipt_bytes).hexdigest())
        self.assertEqual(bound.inventory.names, ())
        record = json.loads(cap.receipt_bytes)
        self.assertEqual(record["capture_kind"], cap.capture_kind)
        self.assertEqual(record["body_sha256"], cap.body_sha256)
        self.assertEqual(record["untrusted_artifact_ref"]["id"], cap.untrusted_artifact_ref.id)
        self.assertEqual(cap.receipt_bytes, json.dumps(record, ensure_ascii=False,
                         separators=(",", ":")).encode())
        self.assertEqual(capture(), cap)
        class StringSubclass(str):
            pass
        self.reject(lambda: k.bind_synthetic_capture(bypass(cap,
                    body_sha256=StringSubclass(cap.body_sha256))), "digest")

    def test_current_former_and_cik_lookup_preserve_complete_capture(self):
        raw = b'{"cik":"123456","name":"Synthetic Issuer","formerNames":[{"name":"Earlier"}]}'
        bound = k.bind_synthetic_capture(capture(raw=raw))
        for query in (u.CikQuery(CIK), u.NameQuery("Synthetic Issuer"),
                      u.NameQuery("Earlier"), u.NameQuery("Syn", "contains")):
            with self.subTest(query=query):
                candidate = u.resolve_candidates(query, bound.inventory).candidates[0]
                self.assertEqual(bound.source_binding_for(candidate), bound)
                self.assertEqual(bound.source_binding_for(candidate).capture.original_bytes, raw)
                self.assertEqual(candidate.verification_status, "unverified")
                self.assertEqual(candidate.entity.authority_ids, ())
                self.assertIsNone(candidate.security)
                self.assertIsNone(candidate.listing)

    def test_byte_distinct_and_artifact_distinct_metadata(self):
        a = k.bind_synthetic_capture(capture())
        b = k.bind_synthetic_capture(capture(raw=RAW + b" "))
        other = context(operation_uuid="22345678-1234-4234-8234-123456789abc")
        d = k.bind_synthetic_capture(capture(ctx=other))
        self.assertEqual(a.inventory, b.inventory)
        self.assertEqual(a.inventory, d.inventory)
        self.assertNotEqual(a.capture.body_sha256, b.capture.body_sha256)
        self.assertNotEqual(a.capture.untrusted_artifact_ref, d.capture.untrusted_artifact_ref)
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, d)

    def test_fabricated_source_owner_policy_and_tls_stay_synthetic(self):
        ctx = context(owner_ref=c.KeyRef("principal", "official-sec"),
                      policy_ref=c.KeyRef("rights_policy", "official-approved"))
        for tls in (False, True):
            bound = k.bind_synthetic_capture(capture(ctx=ctx, ex=exchange(synthetic_tls_observed=tls)))
            self.assertEqual(bound.capture.capture_kind, "synthetic")
            self.assertEqual(bound.source_bound.verification_status, "unverified")
            self.assertEqual(bound.inventory.entities[0].authority_ids, ())
            self.assertEqual((bound.inventory.securities, bound.inventory.listings), ((), ()))
            self.assertNotIsInstance(bound, c.IdentityResolution)

    def test_request_canonical_closed_identity(self):
        request = k.build_submissions_request(CIK)
        for cik in ("123456", "0000000000", "１２３４５６７８９０", 123456, True):
            with self.subTest(cik=cik), self.assertRaises(c.ContractError):
                k.build_submissions_request(cik)
        for url in (request.url + "?x=1", request.url + "#x", request.url.replace("https", "http"),
                    request.url.replace("data.sec.gov", "data.sec.gov:443"),
                    request.url.replace("data.sec.gov", "user@data.sec.gov"),
                    request.url.replace("data.sec.gov", "evil.test"),
                    request.url.replace("submissions", "api")):
            self.reject(lambda: replace(request, url=url), "request_url")
            self.reject(lambda: capture(ex=exchange(observed_url=url)), "url_mismatch")
        self.reject(lambda: replace(request, method="POST"), "request_method")
        self.reject(lambda: capture(raw=RAW.replace(b"123456", b"654321")),
                    "cik_mismatch", s.SecIdentitySourceError)
        with self.assertRaises(TypeError):
            k.build_submissions_request(CIK, url=request.url)

    def test_fixed_and_supported_completed_chunked(self):
        ex = exchange(headers=(("Transfer-Encoding", "chunked"),
                               ("Content-Encoding", "identity")), chunked_complete=True)
        self.assertEqual(capture(ex=ex).original_bytes, RAW)
        self.assertEqual(capture().original_bytes, RAW)

    def test_status_encoding_critical_conflicts_and_framing(self):
        for status in (199, 201, 204, 206, 301, 302, 403, 429, 500, True, 200.0, "200"):
            self.reject(lambda: exchange(status=status), "response_status")
        for name, value in (("Content-Encoding", "gzip"), ("Content-Encoding", "deflate"),
                            ("Content-Type", "text/html"), ("Location", "https://data.sec.gov/"),
                            ("Content-Range", "bytes 0-1/2"), ("Trailer", "Digest")):
            self.reject(lambda: exchange(headers=exchange().headers + ((name, value),)))
        for headers in ((), (("Content-Length", "0"),), (("Content-Length", "+39"),),
                        (("Transfer-Encoding", "chunked"),),
                        (("Transfer-Encoding", "gzip, chunked"),),
                        exchange().headers + (("content-length", str(len(RAW))),),
                        exchange().headers + (("Transfer-Encoding", "chunked"),)):
            self.reject(lambda: exchange(headers=headers))
        for name in k.CRITICAL_HEADERS:
            self.reject(lambda: k.validate_response_headers(((name, "x"), (name.upper(), "x"))))
        self.reject(lambda: exchange(framing_complete=False), "incomplete_framing")
        self.reject(lambda: exchange(chunked_complete=True), "length_mismatch")
        self.reject(lambda: exchange(framing_complete=1), "exchange_flags")

    def test_header_retention_and_closed_schema(self):
        headers = exchange().headers + (("X-Discarded", "value"), ("ETag", '"tag"'))
        cap = capture(ex=exchange(headers=headers))
        record = json.loads(cap.receipt_bytes)
        self.assertEqual(record["headers"], [["content-length", str(len(RAW))], ["etag", '"tag"']])
        self.assertNotIn(b"x-discarded", cap.receipt_bytes)
        self.assertEqual(tuple(record), ("schema", "capture_kind", "outcome", "source_identity",
            "parser_revision", "replay_identity",
            "untrusted_artifact_ref", "observed_url", "status", "headers", "body_bytes",
            "body_sha256", "blocks", "phases", "capture_observation", "framing_complete",
            "chunked_complete", "synthetic_tls_observed", "issuer_count", "request_count",
            "retries", "redirects", "concurrency", "start_spacing_ns"))

    def test_body_order_missing_duplicate_truncate_and_original_mutation(self):
        blocks = (RAW[:20], RAW[20:])
        ex = exchange(body_blocks=blocks, block_observations=(k.BlockObservation(0, 4),
                                                            k.BlockObservation(1, 4)))
        cap = capture(ex=ex)
        for blocks in (tuple(reversed(blocks)), (blocks[0],), blocks + (blocks[0],),
                       (blocks[0][:-1], blocks[1])):
            bad = bypass(ex, body_blocks=blocks)
            self.reject(lambda: k.bind_synthetic_capture(bypass(cap, exchange=bad)),
                        exception=(k.SyntheticCaptureError, s.SecIdentitySourceError))
        self.reject(lambda: k.bind_synthetic_capture(bypass(cap, original_bytes=RAW + b" ")),
                    "capture_consistency")

    def test_bypassed_capture_mutations_revalidated_at_all_consumers(self):
        cap = capture()
        for changes in (dict(body_sha256="0" * 64), dict(receipt_sha256="0" * 64),
                        dict(receipt_bytes=cap.receipt_bytes + b" "),
                        dict(receipt_bytes=cap.receipt_bytes.replace(b'"synthetic"', b'"live"')),
                        dict(untrusted_artifact_ref=c.KeyRef("artifact", "another")),
                        dict(capture_kind="live"), dict(outcome="indeterminate"),
                        dict(original_bytes=b"{}"), dict(context=bypass(cap.context, identity={})),
                        dict(exchange=bypass(cap.exchange, body_blocks=[]))):
            bad = bypass(cap, **changes)
            for consume in (k.bind_synthetic_capture,
                            lambda x: k.decide_synthetic_delivery(x, context=context()),
                            lambda x: k.capture_synthetic_submissions(cap.context.identity.request,
                                context=context(offset=7), exchange=None, prior=x)):
                with self.subTest(changes=tuple(changes), consumer=consume):
                    self.reject(lambda: consume(bad))
        with self.assertRaises(FrozenInstanceError):
            cap.capture_kind = "live"
        for changes in (dict(trusted=True), dict(live=True), dict(source="sec")):
            with self.assertRaises(TypeError):
                replace(cap, **changes)

    def test_cross_envelope_and_candidate_substitution(self):
        a = k.bind_synthetic_capture(capture())
        b = k.bind_synthetic_capture(capture(raw=RAW.replace(b"Issuer", b"Other!")))
        self.reject(lambda: replace(a, source_bound=b.source_bound), "source_bound_substitution")
        candidate = u.resolve_candidates(u.CikQuery(CIK), b.inventory).candidates[0]
        self.reject(lambda: a.source_binding_for(candidate), "candidate_issuer_mismatch",
                    s.SecIdentitySourceError)
        forged = bypass(a, source_bound=b.source_bound)
        self.reject(lambda: forged.source_binding_for(candidate), "source_bound_substitution")
        other = k.bind_synthetic_capture(capture(ctx=context(
            operation_uuid="22345678-1234-4234-8234-123456789abc")))
        self.reject(lambda: replace(a, source_bound=other.source_bound), "source_bound_substitution")

    def test_delivery_cancel_revoke_expire_after_capture_and_rebinding(self):
        cap = capture()
        for changes, reason in ((dict(offset=7, cancelled=True), "cancelled"),
                                (dict(offset=7, revoked=True), "revoked"),
                                (dict(offset=k.MAX_OPERATION_NS + 1), "expired")):
            fresh = context(**changes)
            decision = k.decide_synthetic_delivery(cap, context=fresh)
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.reason, reason)
            rebound = k.bind_synthetic_capture(cap)
            self.assertEqual(rebound.capture.context, cap.context)
            self.assertFalse(k.decide_synthetic_delivery(rebound.capture, context=fresh).allowed)
        at_deadline = context(offset=k.MAX_OPERATION_NS)
        self.assertTrue(k.decide_synthetic_delivery(cap, context=at_deadline).allowed)
        decision = k.decide_synthetic_delivery(cap, context=at_deadline)
        self.reject(lambda: replace(decision, capture_kind="live"), "decision_kind")
        self.reject(lambda: replace(decision, allowed=False), "decision_shape")
        self.reject(lambda: k.decide_synthetic_delivery(cap, context=context(offset=5)),
                    "delivery_observation_order")
        self.reject(lambda: capture(ctx=context(cancelled=True)), "cancelled")
        self.reject(lambda: capture(ctx=context(revoked=True)), "revoked")
        self.reject(lambda: capture(ctx=context(offset=k.MAX_OPERATION_NS + 1)), "expired")

    def test_replay_complete_identity_fresh_observations_and_no_dispatch(self):
        cap = capture()
        fresh = context(offset=7)
        result = k.capture_synthetic_submissions(fresh.identity.request, context=fresh,
                                                exchange=None, prior=cap)
        self.assertEqual(result, cap)
        self.assertEqual(result.context.observation.offset_ns, 6)  # historical, never renewed
        changes = (dict(owner_ref=c.KeyRef("principal", "other")),
                   dict(session_ref=c.KeyRef("session", "other")),
                   dict(request=k.build_submissions_request("0000654321")),
                   dict(request=replace(cap.context.identity.request, future_user_agent="other")),
                   dict(policy_ref=c.KeyRef("rights_policy", "other")), dict(policy_revision="v2"),
                   dict(original_start="2026-10-29T00:00:01.000000Z"),
                   dict(original_deadline_ns=k.MAX_OPERATION_NS - 1),
                   dict(operation_uuid="22345678-1234-4234-8234-123456789abc"))
        for change in changes:
            ctx = context(offset=7, **change)
            self.reject(lambda: k.capture_synthetic_submissions(ctx.identity.request, context=ctx,
                                                               exchange=None, prior=cap), "replay_identity")
            self.reject(lambda: k.decide_synthetic_delivery(cap, context=ctx), "delivery_identity")
        for change, code in ((dict(revoked=True), "revoked"), (dict(cancelled=True), "cancelled"),
                             (dict(offset=k.MAX_OPERATION_NS + 1), "expired")):
            ctx = context(**({"offset": 7} | change))
            self.reject(lambda: k.capture_synthetic_submissions(ctx.identity.request, context=ctx,
                                                               exchange=None, prior=cap), code)
        self.reject(lambda: k.capture_synthetic_submissions(fresh.identity.request, context=fresh,
                    exchange=exchange(), prior=cap), "prior_with_exchange")
        for prior in ({}, False, bypass(cap, outcome="indeterminate"),
                      bypass(cap, outcome="incomplete")):
            self.reject(lambda: k.capture_synthetic_submissions(fresh.identity.request,
                        context=fresh, exchange=None, prior=prior))
        self.reject(lambda: k.capture_synthetic_submissions(fresh.identity.request,
                    context=context(offset=5), exchange=None, prior=cap), "replay_observation_order")

    def test_uuid_start_policy_context_and_request_types(self):
        for value in (UUID.upper(), "short", "00000000-0000-0000-0000-000000000000", 1):
            self.reject(lambda: identity(operation_uuid=value), "operation_uuid")
        for value in ("2026-10-29T00:00:00Z", "2026-10-29", 0):
            with self.assertRaises((c.ContractError, k.SyntheticCaptureError)):
                identity(original_start=value)
        for name, value in (("owner_ref", c.KeyRef("session", "x")),
                            ("session_ref", c.KeyRef("principal", "x")),
                            ("policy_ref", c.KeyRef("artifact", "x")),
                            ("request", {}), ("policy_revision", "v" * 65)):
            self.reject(lambda: identity(**{name: value}))
        self.reject(lambda: capture(ctx=bypass(context(), observation={})), "observation_type")
        self.reject(lambda: k.capture_synthetic_submissions(k.build_submissions_request("0000654321"),
                    context=context(), exchange=exchange()), "request_identity")


class DeliveryDecisionTests(CaptureTestCase):
    def test_direct_and_replace_reject_disqualifying_lifecycle(self):
        cases = ((k.SyntheticObservation(7, revoked=True), k.MAX_OPERATION_NS, "revoked"),
                 (k.SyntheticObservation(7, cancelled=True), k.MAX_OPERATION_NS, "cancelled"),
                 (k.SyntheticObservation(7, True, True), k.MAX_OPERATION_NS, "cancelled"),
                 (k.SyntheticObservation(k.MAX_OPERATION_NS+1), k.MAX_OPERATION_NS, "expired"),
                 (k.SyntheticObservation(11), 10, "expired"))
        for observation, deadline, reason in cases:
            with self.subTest(observation=observation, deadline=deadline):
                valid = delivery_decision(allowed=False, reason=reason, observation=observation,
                                          original_deadline_ns=deadline)
                self.assertEqual(replace(valid), valid)
                self.reject(lambda: delivery_decision(observation=observation,
                    original_deadline_ns=deadline), "decision_lifecycle")
                self.reject(lambda: replace(valid, allowed=True, reason="synthetic_only"),
                            "decision_lifecycle")
                forged = bypass(delivery_decision(), observation=observation,
                                original_deadline_ns=deadline)
                self.reject(lambda: replace(forged), "decision_lifecycle")

    def test_inclusive_original_deadlines_and_correct_denial_precedence(self):
        for deadline in (1, 10, k.MAX_OPERATION_NS):
            at = delivery_decision(observation=k.SyntheticObservation(deadline),
                                   original_deadline_ns=deadline)
            self.assertTrue(at.allowed)
            self.assertEqual(replace(at), at)
            self.reject(lambda: replace(at, observation=k.SyntheticObservation(deadline+1)),
                        "decision_lifecycle")
            for cancelled, revoked, reason in ((True, False, "cancelled"),
                                               (False, True, "revoked"),
                                               (True, True, "cancelled"),
                                               (False, False, "expired")):
                observation = k.SyntheticObservation(deadline+1, cancelled, revoked)
                denied = delivery_decision(allowed=False, reason=reason, observation=observation,
                                           original_deadline_ns=deadline)
                self.assertEqual(replace(denied), denied)
                for wrong_reason in {"synthetic_only", "cancelled", "revoked", "expired"} - {reason}:
                    self.reject(lambda: delivery_decision(allowed=wrong_reason == "synthetic_only",
                        reason=wrong_reason, observation=observation, original_deadline_ns=deadline),
                        "decision_lifecycle")
                    self.reject(lambda: replace(denied, allowed=wrong_reason == "synthetic_only",
                        reason=wrong_reason), "decision_lifecycle")
        for allowed, reason in ((False, "synthetic_only"), (True, "revoked"),
                                (True, "cancelled"), (True, "expired"), (True, "unknown")):
            self.reject(lambda: delivery_decision(allowed=allowed, reason=reason), "decision_shape")
            self.reject(lambda: replace(delivery_decision(), allowed=allowed, reason=reason),
                        "decision_shape")

    def test_strict_metadata_types_bypasses_and_public_consumer_boundaries(self):
        valid = delivery_decision()
        self.reject(lambda: delivery_decision(original_deadline_ns=6), "decision_lifecycle")
        self.reject(lambda: replace(valid, original_deadline_ns=6), "decision_lifecycle")
        self.reject(lambda: replace(bypass(valid, original_deadline_ns=6)), "decision_lifecycle")
        for value in (True, 10.0, "10", 0, -1, k.MAX_OPERATION_NS+1, None):
            self.reject(lambda: delivery_decision(original_deadline_ns=value), "deadline")
            self.reject(lambda: replace(valid, original_deadline_ns=value), "deadline")
            self.reject(lambda: replace(bypass(valid, original_deadline_ns=value)), "deadline")
        for observation, code in (({}, "observation_type"),
                (bypass(k.SyntheticObservation(7), offset_ns=True), "observation_offset"),
                (bypass(k.SyntheticObservation(7), cancelled=1), "observation_flags"),
                (bypass(k.SyntheticObservation(7), revoked="yes"), "observation_flags")):
            self.reject(lambda: delivery_decision(observation=observation), code)
            self.reject(lambda: replace(bypass(valid, observation=observation)), code)
        class TextSubclass(str):
            pass
        for changes in (dict(allowed=1), dict(reason=TextSubclass("synthetic_only"))):
            self.reject(lambda: delivery_decision(**changes), "decision_shape")
            self.reject(lambda: replace(valid, **changes), "decision_shape")
        forged = bypass(valid, observation=k.SyntheticObservation(7, revoked=True))
        # No public operation accepts a decision as an authorization capability.
        for decision in (valid, forged):
            self.reject(lambda: k.bind_synthetic_capture(decision), "capture_type")
            self.reject(lambda: k.decide_synthetic_delivery(decision, context=context()), "capture_type")
            self.reject(lambda: k.capture_synthetic_submissions(k.build_submissions_request(CIK),
                context=context(), exchange=None, prior=decision), "prior_type")
            self.reject(lambda: k.decide_synthetic_delivery(capture(), context=decision), "context_type")
        for name, value in (("original_deadline_ns", 1), ("observation", k.SyntheticObservation(8))):
            with self.assertRaises(FrozenInstanceError):
                setattr(valid, name, value)

    def test_short_deadline_factory_historical_binding_and_replay_lifetime(self):
        original = context(original_deadline_ns=10)
        cap = capture(ctx=original)
        bound = k.bind_synthetic_capture(cap)
        for observation, allowed, reason in ((k.SyntheticObservation(10), True, "synthetic_only"),
                (k.SyntheticObservation(11), False, "expired"),
                (k.SyntheticObservation(10, revoked=True), False, "revoked"),
                (k.SyntheticObservation(10, cancelled=True), False, "cancelled"),
                (k.SyntheticObservation(11, True, True), False, "cancelled"),
                (k.SyntheticObservation(32*k.NS), False, "expired")):
            fresh = replace(original, observation=observation)
            decision = k.decide_synthetic_delivery(cap, context=fresh)
            self.assertEqual((decision.allowed, decision.reason, decision.original_deadline_ns),
                             (allowed, reason, 10))
            self.assertEqual(replace(decision), decision)
            self.assertEqual(k.bind_synthetic_capture(cap), bound)
        replay = k.capture_synthetic_submissions(original.identity.request,
            context=replace(original, observation=k.SyntheticObservation(10)), exchange=None, prior=cap)
        self.assertEqual(replay.context.identity.original_start, original.identity.original_start)
        self.assertEqual(replay.context.identity.original_deadline_ns, 10)
        self.assertEqual(replay, cap)
        self.reject(lambda: k.capture_synthetic_submissions(original.identity.request,
            context=replace(original, observation=k.SyntheticObservation(11)), exchange=None, prior=cap),
            "expired")
        for change in (dict(original_deadline_ns=11),
                       dict(original_start="2026-10-29T00:00:01.000000Z")):
            self.reject(lambda: k.capture_synthetic_submissions(original.identity.request,
                context=replace(original, identity=replace(original.identity, **change)),
                exchange=None, prior=cap), "replay_identity")


class BoundaryTests(CaptureTestCase):
    def test_scalar_count_limits_exact_and_one_over(self):
        for name, value in (("issuer_count", k.MAX_ISSUERS), ("request_count", k.MAX_REQUESTS),
                            ("retries", k.MAX_RETRIES), ("redirects", k.MAX_REDIRECTS),
                            ("concurrency", k.MAX_CONCURRENCY)):
            self.assertEqual(getattr(exchange(**{name: value}), name), value)
            self.reject(lambda: exchange(**{name: value + 1}), name)
            for bad in (True, float(value), str(value)):
                self.reject(lambda: exchange(**{name: bad}), name)
        self.assertEqual(exchange(start_spacing_ns=k.MIN_START_SPACING_NS).start_spacing_ns,
                         k.MIN_START_SPACING_NS)
        self.reject(lambda: exchange(start_spacing_ns=k.MIN_START_SPACING_NS - 1), "start_spacing")
        self.assertEqual(len(replace(k.build_submissions_request(CIK),
                                     future_user_agent="a" * 256).future_user_agent), 256)
        for value in ("a" * 257, "é", "a\r\nb", True):
            self.reject(lambda: replace(k.build_submissions_request(CIK), future_user_agent=value),
                        "user_agent")

    def test_body_size_block_size_count_independent_limits(self):
        block = b" " * k.MAX_BLOCK_BYTES
        self.assertEqual(k.validate_body_blocks((block,)), k.MAX_BLOCK_BYTES)
        self.reject(lambda: k.validate_body_blocks((block + b" ",)), "body_block")
        exact = (block,) * 64
        self.assertEqual(k.validate_body_blocks(exact), k.MAX_BODY_BYTES)
        self.reject(lambda: k.validate_body_blocks(exact + (b" ",)), "body_size")
        self.assertEqual(k.validate_body_blocks((b" ",) * k.MAX_BLOCKS), k.MAX_BLOCKS)
        self.reject(lambda: k.validate_body_blocks((b" ",) * (k.MAX_BLOCKS + 1)), "body_blocks")
        for bad in ([], iter((b"x",)), b"x", (bytearray(b"x"),), (b"",)):
            self.reject(lambda: k.validate_body_blocks(bad))
        # Full 4MiB body still passes unchanged UCR-01B1 parser; 64 digests fit receipt.
        raw = RAW + b" " * (k.MAX_BODY_BYTES - len(RAW))
        blocks = tuple(raw[i:i + k.MAX_BLOCK_BYTES] for i in range(0, len(raw), k.MAX_BLOCK_BYTES))
        ex = exchange(raw=raw, body_blocks=blocks,
                      block_observations=tuple(k.BlockObservation(i, 4) for i in range(64)))
        self.assertEqual(len(capture(raw=raw, ex=ex).original_bytes), k.MAX_BODY_BYTES)
        # 1024 block observations are valid independently, receipt is another cap.
        blocks = (RAW,) + (b" ",) * (k.MAX_BLOCKS - 1)
        ex = exchange(raw=b"".join(blocks), body_blocks=blocks,
                      block_observations=tuple(k.BlockObservation(i, 4) for i in range(k.MAX_BLOCKS)))
        self.reject(lambda: capture(ex=ex), "receipt_size")

    def test_header_count_name_value_and_aggregate_limits(self):
        headers = tuple((f"X-{i}", "v") for i in range(k.MAX_HEADERS))
        self.assertEqual(k.validate_response_headers(headers), ())
        self.reject(lambda: k.validate_response_headers(headers + (("X-extra", "v"),)), "header_count")
        k.validate_response_headers((("x" * 128, "v"),))
        self.reject(lambda: k.validate_response_headers((("x" * 129, "v"),)), "header_name")
        k.validate_response_headers((("x", "v" * 2048),))
        self.reject(lambda: k.validate_response_headers((("x", "v" * 2049),)), "header_value")
        headers = tuple(("x", "v" * 2048) for _ in range(7)) + (("x", "v" * 2008),)
        self.assertEqual(sum(len(a) + len(b) + 4 for a, b in headers), k.MAX_HEADER_BYTES)
        k.validate_response_headers(headers)
        self.reject(lambda: k.validate_response_headers(headers[:-1] + (("x", "v" * 2009),)),
                    "header_size")
        for bad in ([('x', 'v')], (("a\r", "v"),), (("x", "v\n"),), (("x", "é"),),
                    (("x", "v", "z"),), (("x", object()),)):
            self.reject(lambda: k.validate_response_headers(bad))

    def test_header_exact_limit_can_fail_independent_receipt_limit(self):
        retained = tuple((name, "\\" * 2048) for name in
                         ("content-type", "date", "etag", "last-modified"))
        # Header validator accepts all critical syntax; exchange separately checks type.
        headers = retained + tuple(("x", "v" * 2048) for _ in range(3))
        missing = k.MAX_HEADER_BYTES - sum(len(a) + len(b) + 4 for a, b in headers) - 5
        headers += (("x", "v" * missing),)
        self.assertEqual(sum(len(a) + len(b) + 4 for a, b in headers), 16384)
        k.validate_response_headers(headers)
        # Valid exchange at exact header budget with escaping inflation in retained values.
        headers = (("Content-Length", str(len(RAW))),) + tuple(
            (name, "\\" * 2048) for name in ("date", "etag", "last-modified"))
        while sum(len(a) + len(b) + 4 for a, b in headers) + 2053 < 16384:
            headers += (("x", "v" * 2048),)
        missing = 16384 - sum(len(a) + len(b) + 4 for a, b in headers) - 5
        headers += (("x", "v" * missing),)
        ex = exchange(headers=headers)
        self.assertEqual(sum(len(a) + len(b) + 4 for a, b in ex.headers), 16384)
        # Three escaping fields produce >12KiB; add blocks so receipt exceeds 16KiB.
        blocks = (RAW,) + (b" ",) * 30
        ex = replace(ex, body_blocks=blocks, headers=(("Content-Length", str(len(RAW) + 30)),)
                     + ex.headers[1:], block_observations=tuple(k.BlockObservation(i, 4) for i in range(31)))
        self.assertEqual(sum(len(a) + len(b) + 4 for a, b in ex.headers), 16384)
        self.reject(lambda: capture(ex=ex), "receipt_size")
        k.validate_receipt_bytes(b"x" * k.MAX_RECEIPT_BYTES)
        self.reject(lambda: k.validate_receipt_bytes(b"x" * (k.MAX_RECEIPT_BYTES + 1)), "receipt_size")

    def test_canonical_encoded_receipt_exact_limit_and_one_over(self):
        blocks = (RAW,) + (b" ",) * 89
        ex = exchange(raw=b"".join(blocks), body_blocks=blocks,
            block_observations=tuple(k.BlockObservation(i, 4) for i in range(90)),
            headers=(("Content-Length", str(sum(map(len, blocks)))),
                     ("date", "x" * 2048), ("etag", "x" * 2048), ("last-modified", "x")))
        base_size = len(capture(ex=ex).receipt_bytes)
        padding = k.MAX_RECEIPT_BYTES - base_size + 1
        self.assertTrue(1 <= padding <= k.MAX_HEADER_VALUE_BYTES)
        ex = replace(ex, headers=ex.headers[:-1] + (("last-modified", "x" * padding),))
        self.assertEqual(len(capture(ex=ex).receipt_bytes), k.MAX_RECEIPT_BYTES)
        ex = replace(ex, headers=ex.headers[:-1] + (("last-modified", "x" * (padding + 1)),))
        self.reject(lambda: capture(ex=ex), "receipt_size")

    def test_phase_timeout_boundaries_exact_and_one_ns_over(self):
        # Pool, connection, write, header, body, cleanup as consecutive offsets.
        cases = (([k.NS, k.NS, k.NS, k.NS, k.NS, k.NS], 0, "pool_wait"),
                 ([0, 5*k.NS, 5*k.NS, 5*k.NS, 5*k.NS, 5*k.NS], 1, "connection_timeout"),
                 ([0, 0, 5*k.NS, 5*k.NS, 5*k.NS, 5*k.NS], 2, "write_timeout"),
                 ([0, 0, 0, 10*k.NS, 10*k.NS, 10*k.NS], 3, "header_timeout"),
                 ([0, 0, 0, 0, 30*k.NS, 30*k.NS], 4, "body_deadline"),
                 ([0, 0, 0, 0, 0, 2*k.NS], 5, "cleanup_timeout"))
        for offsets, index, code in cases:
            k.PhaseCheckpoints(*offsets)
            over = [value + (i >= index) for i, value in enumerate(offsets)]
            self.reject(lambda: k.PhaseCheckpoints(*over), code)
        k.PhaseCheckpoints(0, 0, 0, 0, 30*k.NS, 32*k.NS)
        self.reject(lambda: identity(original_deadline_ns=30*k.NS + 1), "deadline")
        self.assertEqual(identity(original_deadline_ns=30*k.NS).original_deadline_ns, 30*k.NS)
        self.assertEqual(k.SyntheticObservation(32*k.NS).offset_ns, 32*k.NS)
        self.reject(lambda: k.SyntheticObservation(32*k.NS + 1), "observation_offset")
        ex = exchange(phases=k.PhaseCheckpoints(0, 0, 0, 0, 5*k.NS, 5*k.NS),
                      block_observations=(k.BlockObservation(0, 5*k.NS),))
        capture(ctx=context(offset=5*k.NS), ex=ex)
        self.reject(lambda: replace(ex, phases=k.PhaseCheckpoints(0, 0, 0, 0, 5*k.NS+1, 5*k.NS+1),
                                  block_observations=(k.BlockObservation(0, 5*k.NS+1),)), "read_inactivity")
        ex = replace(ex, block_observations=(k.BlockObservation(0, 0),))
        replace(ex, phases=k.PhaseCheckpoints(0, 0, 0, 0, 5*k.NS, 5*k.NS))
        self.reject(lambda: replace(ex, phases=k.PhaseCheckpoints(0, 0, 0, 0, 5*k.NS+1, 5*k.NS+1)),
                    "read_inactivity")

    def test_cleanup_allowance_cannot_extend_successful_delivery(self):
        blocks = (RAW,) + (b" ",) * 5
        ex = exchange(raw=b"".join(blocks), body_blocks=blocks,
            phases=k.PhaseCheckpoints(0, 0, 0, 0, 30*k.NS, 32*k.NS),
            block_observations=tuple(k.BlockObservation(i, (i+1)*5*k.NS) for i in range(6)))
        self.reject(lambda: capture(ctx=context(offset=32*k.NS), ex=ex), "expired")
        self.reject(lambda: capture(ctx=context(offset=30*k.NS), ex=ex), "capture_observation_order")
        ex = replace(ex, phases=replace(ex.phases, cleanup_complete_ns=30*k.NS))
        self.assertTrue(k.decide_synthetic_delivery(capture(ctx=context(offset=30*k.NS), ex=ex),
                                                   context=context(offset=30*k.NS)).allowed)

    def test_finite_phase_and_block_observation_shape_and_types(self):
        for bad in ([], {}, (("headers", 3),), (object(),) * 7):
            self.reject(lambda: exchange(phases=bad), "phases_type")
        with self.assertRaises(TypeError):
            k.PhaseCheckpoints(0, 1, 2, 3, 5, 6, unknown=7)
        with self.assertRaises(TypeError):
            k.PhaseCheckpoints(0, 1, 2, 3, 5, 6, pool_acquired_ns=0)
        self.reject(lambda: k.PhaseCheckpoints(0, 2, 1, 3, 5, 6), "phase_order")
        for bad in (True, 1.0, "1", -1):
            self.reject(lambda: k.SyntheticObservation(bad), "observation_offset")
            self.reject(lambda: k.BlockObservation(bad, 0), "block_index")
            self.reject(lambda: k.BlockObservation(0, bad), "block_offset")
            self.reject(lambda: k.PhaseCheckpoints(bad, 1, 2, 3, 5, 6), "phase_offset")
            self.reject(lambda: identity(original_deadline_ns=bad), "deadline")
            self.reject(lambda: exchange(start_spacing_ns=bad), "start_spacing")
        k.BlockObservation(k.MAX_BLOCKS-1, k.MAX_OPERATION_NS)
        self.reject(lambda: k.BlockObservation(k.MAX_BLOCKS, 0), "block_index")
        self.reject(lambda: k.BlockObservation(0, k.MAX_OPERATION_NS+1), "block_offset")
        for bad in ([], iter(()), (), (k.BlockObservation(0, 4),)*2,
                    (object(),)*(k.MAX_BLOCKS+1)):
            self.reject(lambda: exchange(block_observations=bad))
        self.reject(lambda: exchange(block_observations=(k.BlockObservation(1, 4),)),
                    "block_observation_index")
        self.reject(lambda: exchange(block_observations=(k.BlockObservation(0, 2),)),
                    "block_observation_order")
        self.reject(lambda: exchange(block_observations=(k.BlockObservation(0, 6),)),
                    "block_observation_order")
        # Oversized collection fails before even inspecting malformed elements.
        self.reject(lambda: exchange(body_blocks=(object(),)*(k.MAX_BLOCKS+1)), "body_blocks")
        self.reject(lambda: exchange(headers=(object(),)*(k.MAX_HEADERS+1)), "header_count")
        self.reject(lambda: exchange(block_observations=(object(),)*(k.MAX_BLOCKS+1)),
                    "block_observations")


class IsolationAndMutationTests(unittest.TestCase):
    def test_constructor_lifecycle_mutations_require_intended_rejection(self):
        source = (BACKEND / "app/sec_identity_capture.py").read_text(encoding="utf-8")

        class IntendedLifecycleFailure(AssertionError):
            pass

        def probe(module, offset, cancelled, revoked, deadline, reconstruct):
            observation = module.SyntheticObservation(offset, cancelled, revoked)
            try:
                if reconstruct:
                    base = delivery_decision(module, observation=module.SyntheticObservation(0),
                                             original_deadline_ns=deadline)
                    replace(base, observation=observation)
                else:
                    delivery_decision(module, observation=observation, original_deadline_ns=deadline)
            except module.SyntheticCaptureError as error:
                if error.code != "decision_lifecycle":
                    raise RuntimeError("unrelated lifecycle rejection: " + error.code) from error
            else:
                raise IntendedLifecycleFailure("contradictory allowed decision accepted")

        cases = ((7, False, True, k.MAX_OPERATION_NS),
                 (7, True, False, k.MAX_OPERATION_NS),
                 (7, True, True, k.MAX_OPERATION_NS),
                 (k.MAX_OPERATION_NS+1, False, False, k.MAX_OPERATION_NS),
                 (11, False, False, 10))
        mutants = (
            ("constructor_guard_removed",
             "self.reason == _delivery_reason(self.observation, self.original_deadline_ns)",
             "True", cases),
            ("short_deadline_ignored", "observation.offset_ns > original_deadline_ns",
             "observation.offset_ns > MAX_OPERATION_NS", cases[-1:]),
        )
        for name, before, after, observations in mutants:
            self.assertEqual(source.count(before), 1)
            for case in observations:
                for reconstruct in (False, True):
                    probe(k, *case, reconstruct)  # Original behavior must pass first.
            module = types.ModuleType("decision_mutant_" + name)
            sys.modules[module.__name__] = module
            try:
                exec(compile(source.replace(before, after), "<decision-mutant>", "exec"), module.__dict__)
                for case in observations:
                    for reconstruct in (False, True):
                        with self.subTest(mutant=name, case=case, reconstruct=reconstruct):
                            with self.assertRaises(IntendedLifecycleFailure):
                                probe(module, *case, reconstruct)
            finally:
                sys.modules.pop(module.__name__, None)

    def test_import_surface_closed(self):
        tree = ast.parse((BACKEND / "app/sec_identity_capture.py").read_text(encoding="utf-8"))
        imports, app_names = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
                if node.module == "app":
                    app_names.update(alias.name for alias in node.names)
        self.assertEqual(imports, {"dataclasses", "hashlib", "json", "re", "app"})
        self.assertEqual(app_names, {"research_contracts", "sec_identity_source"})

    def test_fresh_process_import_and_execution_deny_effects(self):
        script = r'''
import sys, importlib.abc, os, socket, subprocess, builtins, pathlib, io
sys.path.insert(0, sys.argv[1])
blocked = ("app.config", "app.database", "app.models", "app.sec_client", "app.release_policy",
           "app.main", "dotenv", "sqlalchemy", "httpx", "requests", "torch", "transformers",
           "sentence_transformers", "openai", "fastapi")
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in blocked):
            raise AssertionError("operational import")
sys.meta_path.insert(0, Guard())
def deny(*args, **kwargs):
    raise AssertionError("forbidden effect")
def audit(event, args):
    if event == "open":
        value, mode, flags = args
        if not (type(value) is str and value.endswith((".py", ".pyc")) and
                (mode is None or mode in ("r", "rb")) and not (flags & (os.O_WRONLY | os.O_RDWR))):
            deny()
    if event.startswith(("socket.", "subprocess.", "os.spawn", "os.exec")) or event in (
            "os.system", "os.putenv", "os.unsetenv", "os.mkdir", "os.remove", "os.rename"):
        deny()
sys.addaudithook(audit)
os.getenv = deny
class NoEnvironment(dict):
    __getitem__ = get = __iter__ = __setitem__ = deny
os.environ = NoEnvironment()
socket.socket = socket.create_connection = subprocess.Popen = deny
from app import sec_identity_capture as k, research_contracts as c, universal_identity as u
builtins.open = io.open = pathlib.Path.open = os.open = deny
r = k.build_submissions_request("0000123456")
i = k.ReplayIdentity("12345678-1234-4234-8234-123456789abc", c.KeyRef("principal", "owner"),
    c.KeyRef("session", "session"), r, c.KeyRef("rights_policy", "policy"), "v1",
    "2026-10-29T00:00:00.000000Z")
ctx = k.SyntheticContext(i, k.SyntheticObservation(6))
raw = b'{"cik":"123456","name":"Synthetic","formerNames":[{"name":"Earlier"}]}'
ex = k.SyntheticExchange(r.url, 200, (("Content-Length", str(len(raw))),), (raw,),
    k.PhaseCheckpoints(0,1,2,3,5,6), (k.BlockObservation(0,4),))
cap = k.capture_synthetic_submissions(r, context=ctx, exchange=ex)
bound = k.bind_synthetic_capture(cap)
for query in (u.CikQuery(r.expected_cik), u.NameQuery("Synthetic"), u.NameQuery("Earlier")):
    candidate = u.resolve_candidates(query, bound.inventory).candidates[0]
    assert bound.source_binding_for(candidate).capture == cap
    assert candidate.verification_status == "unverified" and candidate.entity.authority_ids == ()
assert k.capture_synthetic_submissions(r, context=ctx, exchange=None, prior=cap) == cap
assert k.decide_synthetic_delivery(cap, context=ctx).allowed
assert not k.decide_synthetic_delivery(cap, context=k.SyntheticContext(i,k.SyntheticObservation(7,revoked=True))).allowed
from dataclasses import replace
decision = k.decide_synthetic_delivery(cap, context=ctx)
assert decision.original_deadline_ns == i.original_deadline_ns
for rebuild in (lambda: k.SyntheticDeliveryDecision(True,"synthetic_only",i.operation_uuid,
        cap.receipt_sha256,k.SyntheticObservation(7,revoked=True),i.original_deadline_ns),
        lambda: replace(decision,observation=k.SyntheticObservation(7,cancelled=True))):
    try:
        rebuild()
    except k.SyntheticCaptureError as error:
        assert error.code == "decision_lifecycle"
    else:
        raise AssertionError("contradictory decision accepted")
assert not any(name in sys.modules for name in blocked)
print("isolated import/capture/bind/lookup/replay/delivery passed")
'''
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(BACKEND)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("isolated import/capture/bind/lookup/replay/delivery passed", result.stdout)

    def test_four_p2_targeted_in_memory_behavioral_mutations(self):
        source = (BACKEND / "app/sec_identity_capture.py").read_text(encoding="utf-8")

        class IntendedBehaviorFailure(AssertionError):
            pass

        def delivery_probe(module, changes):
            cap = capture(module)
            decision = module.decide_synthetic_delivery(cap, context=context(module, **changes))
            if decision.allowed:
                raise IntendedBehaviorFailure("final delivery incorrectly allowed")

        def rejection_probe(module, function, code):
            # Manual assertion ensures unrelated exceptions never count as kills.
            try:
                function(module)
            except module.SyntheticCaptureError as error:
                if error.code != code:
                    raise RuntimeError("unrelated rejection: " + error.code) from error
            else:
                raise IntendedBehaviorFailure("intended rejection was bypassed: " + code)

        mutants = (
            ("P2-1-expiry", 'observation.offset_ns > original_deadline_ns', 'False',
             lambda m: delivery_probe(m, dict(offset=m.MAX_OPERATION_NS+1))),
            ("P2-1-revocation", '"revoked" if observation.revoked', '"revoked" if False',
             lambda m: delivery_probe(m, dict(offset=7, revoked=True))),
            ("P2-2-receipt-limit", 'len(encoded) <= MAX_RECEIPT_BYTES', 'True',
             lambda m: rejection_probe(m, lambda n: n.validate_receipt_bytes(b"x" * 16385), "receipt_size")),
            ("P2-2-discriminator", 'self.capture_kind == CAPTURE_KIND,\n                 "capture_kind"',
             'True,\n                 "capture_kind"',
             lambda m: rejection_probe(m, lambda n: n.bind_synthetic_capture(
                 bypass(capture(n), capture_kind="live")), "capture_kind")),
            ("P2-3-finite-block-observations", '_tuple(self.block_observations, MAX_BLOCKS, "block_observations")',
             'pass', lambda m: rejection_probe(m, lambda n: exchange(n,
                 block_observations=[n.BlockObservation(0, 4)]), "block_observations")),
            ("P2-3-exact-integer", 'type(value) is int and minimum <= value <= maximum',
             'isinstance(value, (int, float)) and minimum <= value <= maximum',
             lambda m: rejection_probe(m, lambda n: n.SyntheticObservation(True), "observation_offset")),
            ("P2-4-original-identity", 'prior.context.identity == context.identity', 'True',
             lambda m: rejection_probe(m, lambda n: n.capture_synthetic_submissions(
                 n.build_submissions_request(CIK), context=context(n, offset=7,
                 original_start="2026-10-29T00:00:01.000000Z"), exchange=None, prior=capture(n)), "replay_identity")),
            ("P2-4-no-second-exchange", 'exchange is None, "prior_with_exchange"',
             'True, "prior_with_exchange"', lambda m: rejection_probe(m,
                 lambda n: n.capture_synthetic_submissions(n.build_submissions_request(CIK),
                     context=context(n, offset=7), exchange=exchange(n), prior=capture(n)), "prior_with_exchange")),
        )
        for name, before, after, probe in mutants:
            with self.subTest(mutant=name):
                probe(k)  # Must pass original behavior first.
                self.assertEqual(source.count(before), 1, name)
                module = types.ModuleType("capture_mutant_" + name.replace("-", "_"))
                sys.modules[module.__name__] = module
                try:
                    exec(compile(source.replace(before, after), "<synthetic-mutant>", "exec"), module.__dict__)
                    with self.assertRaises(IntendedBehaviorFailure):
                        probe(module)
                finally:
                    sys.modules.pop(module.__name__, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
