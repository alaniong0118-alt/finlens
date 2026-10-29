"""Offline C1 acceptance, rejection, mutation and forbidden-effect controls.

Run: backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_research_contracts.py
All fixture identities are synthetic labels, with no real-source admission claim.
"""

import ast
from dataclasses import FrozenInstanceError, fields, replace
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import research_contracts as c


def key(namespace, identifier="test"):
    return c.KeyRef(namespace, identifier)


def entity(sec=True):
    cik = "0000123456" if sec else None
    return c.EntityRef(key("sec_cik", cik) if sec else key("external_entity"),
                       "Example 例", "US" if sec else None, cik, ())


def authority(**changes):
    args = dict(scheme="authority_id", authority="source", identifier="identifier",
                evidence_key=key("authority_record"), effective=None)
    args.update(changes)
    return c.AuthorityIdentifier(**args)


def security(**changes):
    args = dict(key=key("security"), issuer_key=entity().key,
                share_class="Class B", authority_ids=())
    args.update(changes)
    return c.SecurityRef(**args)


def alias(**changes):
    args = dict(provider="provider", product="feed", symbol="BRK.B",
                effective=None, evidence_key=key("authority_record"))
    args.update(changes)
    return c.SymbolAlias(**args)


def listing(**changes):
    args = dict(key=key("listing"), security_key=security().key, mic="XNAS", currency="USD",
                calendar_key=key("calendar"), calendar_version="v1", effective=None,
                aliases=(alias(),))
    args.update(changes)
    return c.ListingRef(**args)


def evidence(cls=c.DatabasePublicationRef, **changes):
    args = dict(entity_key=entity().key, origin="sec", owner_key=None, session_key=None,
                source_descriptor_key=None, source_revision_key=None,
                rights_policy_key=None, admission_record_key=None,
                public_available_at=c.TimePoint.unknown(), retrieved_at=c.TimePoint.date("2026-10-29"))
    if cls is c.DatabasePublicationRef:
        args.update(accession="9999999999-26-000001", publication_data_version=0,
                    evidence_version=0, data_version=0, manifest_sha256="a" * 64, chunk_id=None)
    elif cls is c.SessionArtifactRef:
        args.update(origin="user_upload", owner_key=key("principal"), session_key=key("session"),
                    source_descriptor_key=key("source_descriptor"), artifact_key=key("artifact"),
                    artifact_sha256="b" * 64)
    else:
        args.update(origin="market_provider", source_descriptor_key=key("source_descriptor"),
                    security_key=security().key, listing_key=listing().key,
                    market_publication_key=key("market_publication"),
                    market_data_version=0, manifest_sha256="c" * 64)
    args.update(changes)
    return cls(**args)


def roots():
    return (entity(), entity(False), security(), listing(),
            c.IdentityResolution("resolved", (entity().key,), (key("artifact"),), "reference"),
            evidence(), evidence(c.SessionArtifactRef), evidence(c.MarketPublicationRef))


def wire(record):
    return json.loads(c.encode(record))


def raw(tree):
    return json.dumps(tree, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def node_count(value):
    if isinstance(value, dict):
        return 1 + sum(1 + node_count(item) for item in value.values())
    if isinstance(value, list):
        return 1 + sum(node_count(item) for item in value)
    return 1


class ContractTests(unittest.TestCase):
    def reject(self, func, *args, **kwargs):
        with self.assertRaises(c.ContractError):
            func(*args, **kwargs)

    def test_closed_namespace_set_and_all_valid_keys(self):
        expected = {"sec_cik", "external_entity", "security", "listing", "principal", "session",
                    "artifact", "source_descriptor", "source_revision", "rights_policy",
                    "admission_record", "market_publication", "authority_record", "calendar"}
        self.assertEqual(c.NAMESPACES, expected)
        for namespace in expected:
            with self.subTest(namespace=namespace):
                self.assertEqual(key(namespace, "0000000001" if namespace == "sec_cik" else "A._:-9").namespace,
                                 namespace)

    def test_cik_factory_strict_records_and_wire(self):
        for value in ("1", "123456", "0000123456", "9999999999"):
            with self.subTest(value=value):
                self.assertEqual(c.canonical_sec_cik(value), value.zfill(10))
        for value in (1, True, None, "", "0", "0000000000", "12345678901", " 1", "+1", "１", "١"):
            with self.subTest(invalid=value):
                self.reject(c.canonical_sec_cik, value)
                self.reject(key, "sec_cik", value)
        data = wire(entity())
        data["record"]["key"]["id"] = data["record"]["cik"] = "123456"
        self.reject(c.decode, raw(data))

    def test_no_database_identity_required(self):
        self.assertIsNone(entity(False).cik)
        self.assertNotIn("company_id", wire(entity(False))["record"])
        for record in (entity(), entity(False)):
            self.assertEqual(c.decode(c.encode(record)), record)

    def test_entity_cik_and_authority_consistency(self):
        good = authority(scheme="sec_cik", authority="sec", identifier=entity().cik)
        self.assertEqual(replace(entity(), authority_ids=(good,)).authority_ids, (good,))
        for operation in (
            lambda: replace(entity(), cik="0000000001"),
            lambda: replace(entity(), cik=None),
            lambda: replace(entity(False), cik=entity().cik),
            lambda: replace(entity(False), authority_ids=(good,)),
            lambda: replace(entity(), authority_ids=(replace(good, identifier="0000000001"),)),
            lambda: replace(good, authority="SEC"),
        ):
            with self.subTest(operation=operation):
                self.reject(operation)

    def test_authority_schemes_and_exact_widths(self):
        self.assertEqual(authority(scheme="lei", identifier="A1" * 10).scheme, "lei")
        for changes in (dict(scheme="unknown"), dict(scheme=True), dict(identifier="x" * 129),
                        dict(scheme="lei", identifier="a" * 20),
                        dict(scheme="lei", identifier="A" * 19),
                        dict(scheme="lei", identifier="A" * 21),
                        dict(evidence_key=key("admission_record")), dict(effective="2026-01-01")):
            with self.subTest(changes=changes):
                self.reject(authority, **changes)

    def test_share_class_and_listing_collisions(self):
        first = listing()
        second_security = security(key=key("security", "class_a"), share_class="Class A")
        second = listing(key=key("listing", "another"), security_key=second_security.key, mic="XNYS")
        self.assertEqual(first.aliases, second.aliases)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first.key, second.key)
        self.assertNotEqual(security(), second_security)
        spelling = replace(first, aliases=(alias(symbol="BRK-B"),))
        self.assertNotEqual(first, spelling)
        c.check_reference_context(second, entity=entity(), security=second_security)

    def test_stable_keys_and_full_record_equality(self):
        self.assertEqual(entity().key, replace(entity(), legal_name="Renamed").key)
        self.assertNotEqual(entity(), replace(entity(), legal_name="Renamed"))
        self.assertNotEqual(key("security", "a"), key("security", "A"))
        self.assertNotEqual(key("security"), key("listing"))
        for record in roots():
            with self.subTest(kind=record.kind):
                self.assertEqual(hash(record), hash(c.decode(c.encode(record))))
                self.assertEqual(len({record, c.decode(c.encode(record))}), 1)
        for changed in (replace(evidence(), data_version=1),
                        replace(evidence(), manifest_sha256="d" * 64),
                        replace(evidence(), chunk_id="chunk")):
            self.assertNotEqual(changed, evidence())
            self.assertEqual(len({changed, evidence()}), 2)
        private = evidence(c.SessionArtifactRef)
        self.assertNotEqual(private, replace(private, owner_key=key("principal", "different")))

    def test_supplied_relationship_chain(self):
        c.check_reference_context(evidence(c.MarketPublicationRef), entity=entity(),
                                  security=security(), listing=listing(),
                                  expected_entity_key=entity().key,
                                  expected_security_key=security().key, expected_listing_key=listing().key)
        for changed in (dict(entity=entity(False)),
                        dict(security=security(issuer_key=entity(False).key)),
                        dict(listing=listing(security_key=key("security", "other"))),
                        dict(expected_entity_key=key("external_entity", "other")),
                        dict(expected_security_key=key("security", "other")),
                        dict(expected_listing_key=key("listing", "other"))):
            args = dict(entity=entity(), security=security(), listing=listing())
            args.update(changed)
            with self.subTest(changed=changed):
                self.reject(c.check_reference_context, evidence(c.MarketPublicationRef), **args)
        self.reject(c.check_reference_context, listing(), security=security(key=key("security", "other")))
        self.reject(c.check_reference_context, security(), entity=entity(False))
        self.reject(c.check_reference_context, entity(), entity=replace(entity(), legal_name="Conflict"))

    def test_owner_session_context(self):
        private = evidence(c.SessionArtifactRef)
        c.check_reference_context(private, expected_owner_key=private.owner_key,
                                  expected_session_key=private.session_key)
        for changes in ({}, dict(expected_owner_key=private.owner_key),
                        dict(expected_owner_key=key("principal", "other"), expected_session_key=private.session_key),
                        dict(expected_owner_key=private.owner_key, expected_session_key=key("session", "other")),
                        dict(expected_owner_key=key("session"), expected_session_key=private.session_key)):
            with self.subTest(changes=changes):
                self.reject(c.check_reference_context, private, **changes)

    def test_expected_context_requires_an_actual_comparable_link(self):
        for record, expected in ((listing(), {"expected_entity_key": entity().key}),
                                 (entity(), {"expected_security_key": security().key}),
                                 (security(), {"expected_listing_key": listing().key})):
            with self.subTest(kind=record.kind):
                self.reject(c.check_reference_context, record, **expected)
        c.check_reference_context(listing(), security=security(), expected_entity_key=entity().key)

    def test_nullable_metadata_keys_and_variant_context_rules(self):
        for cls in (c.DatabasePublicationRef, c.SessionArtifactRef, c.MarketPublicationRef):
            for name, namespace in (("source_descriptor_key", "source_descriptor"),
                                    ("source_revision_key", "source_revision"),
                                    ("rights_policy_key", "rights_policy"),
                                    ("admission_record_key", "admission_record")):
                with self.subTest(kind=cls.kind, field=name):
                    record = evidence(cls, **{name: key(namespace)})
                    self.assertEqual(c.decode(c.encode(record)), record)
                    self.reject(evidence, cls, **{name: key("artifact")})
                    if name == "source_descriptor_key" and cls is not c.DatabasePublicationRef:
                        self.reject(evidence, cls, **{name: None})
                    else:
                        self.assertIsNone(getattr(evidence(cls, **{name: None}), name))
            for name in ("owner_key", "session_key"):
                with self.subTest(kind=cls.kind, field=name):
                    self.reject(evidence, cls, **{name: key("artifact")})
        for origin in ("official_sec", "official_issuer", "official_exchange", "official_regulator", "user_upload"):
            with self.subTest(origin=origin):
                record = evidence(c.SessionArtifactRef, origin=origin)
                self.assertEqual(c.decode(c.encode(record)), record)
        self.reject(evidence, owner_key=key("principal"))
        self.reject(evidence, session_key=key("session"))
        self.reject(evidence, c.SessionArtifactRef, owner_key=None)
        self.reject(evidence, c.SessionArtifactRef, session_key=None)
        self.assertIsNone(evidence(c.MarketPublicationRef, owner_key=key("principal")).session_key)

    def test_namespace_substitution_in_every_key_field(self):
        for record in roots():
            for field in fields(record):
                value = getattr(record, field.name)
                if type(value) is c.KeyRef:
                    wrong = key("artifact") if value.namespace != "artifact" else key("principal")
                    with self.subTest(kind=record.kind, field=field.name):
                        self.reject(replace, record, **{field.name: wrong})
        self.reject(security, authority_ids=(authority(scheme="lei", identifier="A" * 20),))

    def test_accession_prefix_is_independent(self):
        record = evidence()
        self.assertNotEqual(record.accession[:10], record.entity_key.id)
        self.assertEqual(c.decode(c.encode(record)), record)
        for value in ("999999999926000001", "9999999999-2-000001", 123, " 9999999999-26-000001",
                      "9999999999-26-00000１", "9999999999-26-000001x"):
            with self.subTest(value=value):
                self.reject(evidence, accession=value)

    def test_exact_closed_record_field_sets(self):
        for record in roots():
            base = wire(record)
            for name in base["record"]:
                with self.subTest(kind=record.kind, missing=name):
                    data = wire(record)
                    del data["record"][name]
                    self.reject(c.decode, raw(data))
                with self.subTest(kind=record.kind, null=name):
                    if base["record"][name] is not None and name != "jurisdiction":
                        data = wire(record)
                        data["record"][name] = None
                        self.reject(c.decode, raw(data))
            for name, value in (("unknown", None), ("company_id", 1), ("fact_id", 1),
                                ("trusted", True), ("url", "https://example.invalid"),
                                ("raw_content", "text"), ("financial_value", "1")):
                with self.subTest(kind=record.kind, extra=name):
                    data = wire(record)
                    data["record"][name] = value
                    self.reject(c.decode, raw(data))

    def test_nested_closed_fields_and_missing_nulls(self):
        record = replace(entity(), authority_ids=(authority(effective=c.DateInterval("2020-01-01", None)),))
        for path in (("key",), ("authority_ids", 0), ("authority_ids", 0, "evidence_key"),
                     ("authority_ids", 0, "effective")):
            for mode in ("extra", "missing"):
                with self.subTest(path=path, mode=mode):
                    data = wire(record)
                    target = data["record"]
                    for part in path:
                        target = target[part]
                    if mode == "extra":
                        target["unexpected"] = None
                    else:
                        del target[next(iter(target))]
                    self.reject(c.decode, raw(data))
        data = wire(listing())
        del data["record"]["aliases"][0]["effective"]
        self.reject(c.decode, raw(data))

    def test_unknown_mixed_and_recursive_variants(self):
        for kind in ("unknown", "date", "artifact", "database", None, True):
            with self.subTest(kind=kind):
                data = wire(evidence())
                data["record"]["kind"] = kind
                self.reject(c.decode, raw(data))
        for record in (evidence(), evidence(c.SessionArtifactRef), evidence(c.MarketPublicationRef)):
            data = wire(record)
            data["record"]["artifact_key" if record.kind != "session_artifact" else "accession"] = None
            self.reject(c.decode, raw(data))
        data = wire(entity())
        data["record"]["key"] = data["record"].copy()
        self.reject(c.decode, raw(data))

    def test_duplicate_json_names_including_escapes(self):
        valid = c.encode(entity())
        for payload in (valid.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1'),
                        valid.replace(b'"schema_version":1', b'"schema_version":1,"schema_versi\\u006fn":1'),
                        valid.replace(b'"id":"0000123456"', b'"id":"0000123456","\\u0069d":"other"'),
                        b'{"record":null,"record":{"kind":"entity"},"schema_version":1}'):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(c.ContractError, "duplicate member"):
                    c.decode(payload)

    def test_schema_version_and_envelope(self):
        for version in (True, False, "1", 1.0, 0, 2, None, [], {}):
            with self.subTest(version=version):
                data = wire(entity())
                data["schema_version"] = version
                self.reject(c.decode, raw(data))
        for data in ({"record": wire(entity())["record"]},
                     {"schema_version": 1}, {"schema_version": 1, "record": None},
                     dict(wire(entity()), extra=None), [], None):
            with self.subTest(envelope=data):
                self.reject(c.decode, raw(data))

    def test_pins_zero_max_and_order(self):
        for value in (0, 1, c.MAX_PIN):
            with self.subTest(value=value):
                record = evidence(publication_data_version=value, evidence_version=value, data_version=value)
                self.assertEqual(c.decode(c.encode(record)), record)
                market = evidence(c.MarketPublicationRef, market_data_version=value)
                self.assertEqual(c.decode(c.encode(market)), market)
        for pins in ((1, 0, 1), (0, 2, 1), (2, 1, 0)):
            with self.subTest(pins=pins):
                self.reject(evidence, **dict(zip(("publication_data_version", "evidence_version", "data_version"), pins)))
        self.assertEqual(evidence(publication_data_version=0, evidence_version=1, data_version=2).evidence_version, 1)

    def test_noncoercive_pin_rejections(self):
        for value in (-1, True, False, "0", 0.0, 1.0, c.MAX_PIN + 1, 10**100, None):
            for name in ("publication_data_version", "evidence_version", "data_version"):
                with self.subTest(value=value, field=name):
                    self.reject(evidence, **{name: value})
            with self.subTest(value=value, field="market_data_version"):
                self.reject(evidence, c.MarketPublicationRef, market_data_version=value)

    def test_pin_lexemes_no_exponent_negative_zero_or_long_int(self):
        base = c.encode(evidence())
        for token in (b"-0", b"-1", b"1.0", b"0e0", b"1E0", b"1e999999", b"NaN", b"Infinity",
                      b"-Infinity", b"9007199254740992", b"000", b"+0", b"9" * 10000):
            with self.subTest(token=token[:30]):
                self.reject(c.decode, base.replace(b'"data_version":0', b'"data_version":' + token))
        self.reject(c.decode, c.encode(entity()).replace(b'"schema_version":1', b'"schema_version":-0'))

    def test_unknown_date_and_instant_are_distinct(self):
        unknown = c.TimePoint.unknown()
        date_only = c.TimePoint.date("2026-10-29")
        instant = c.TimePoint.instant("2026-10-29T00:00:00Z")
        self.assertNotEqual(unknown, date_only)
        self.assertNotEqual(date_only, instant)
        self.assertFalse(hasattr(unknown, "value"))
        self.assertEqual(instant.value, "2026-10-29T00:00:00.000000Z")
        for value in (unknown, date_only, instant):
            record = evidence(public_available_at=value)
            self.assertEqual(c.decode(c.encode(record)), record)

    def test_instant_normalization_without_precision_loss(self):
        for value, expected in (
            ("2026-10-29T08:12:13.123456+08:00", "2026-10-29T00:12:13.123456Z"),
            ("2026-10-29T00:00:00.1-01:30", "2026-10-29T01:30:00.100000Z"),
            ("2026-01-01T00:15:00+01:00", "2025-12-31T23:15:00.000000Z"),
            ("0001-01-01T00:00:00Z", "0001-01-01T00:00:00.000000Z"),
            ("9999-12-31T23:59:59.999999Z", "9999-12-31T23:59:59.999999Z"),
            ("2026-10-29t08:12:13.123456+08:00", "2026-10-29T00:12:13.123456Z"),
            ("2026-10-29t00:00:00z", "2026-10-29T00:00:00.000000Z"),
        ):
            with self.subTest(value=value):
                self.assertEqual(c.TimePoint.instant(value).value, expected)

    def test_invalid_instant_variants_offsets_and_overflow(self):
        for value in ("2026-10-29T00:00:00", "2026-10-29 00:00:00Z", "2026-10-29T00:00Z",
                      "2026-10-29T00:00:00 UTC", "2026-10-29T00:00:60Z", "2026-10-29T24:00:00Z",
                      "2026-10-29T00:00:00.1234567Z", "2026-10-29T00:00:00+24:00",
                      "2026-10-29T00:00:00+01:60", "2026-10-29T00:00:00+0800",
                      "0001-01-01T00:00:00+00:01", "9999-12-31T23:59:59-00:01",
                      "2025-02-29T00:00:00Z", "2026-10-29T00:00:00+00:00:00", None, 0):
            with self.subTest(value=value):
                self.reject(c.TimePoint.instant, value)
        for time in ({"kind": "unknown", "value": None}, {"kind": "date"},
                     {"kind": "instant", "value": None}, {"kind": "date", "value": "2026-10-29", "zone": "UTC"},
                     {"kind": "other"}, None):
            with self.subTest(time=time):
                data = wire(evidence())
                data["record"]["retrieved_at"] = time
                self.reject(c.decode, raw(data))

    def test_date_and_half_open_intervals(self):
        for value in ("2024-02-29", "0001-01-01", "9999-12-31"):
            with self.subTest(value=value):
                self.assertEqual(c.TimePoint.date(value).value, value)
        for value in ("2025-02-29", "2026-13-01", "2026-1-01", "0000-01-01", "2026-10-29T00:00:00Z"):
            with self.subTest(value=value):
                self.reject(c.TimePoint.date, value)
        self.assertIsNone(c.DateInterval("2020-01-01", None).end)
        for start, end in (("2020-01-01", "2020-01-01"), ("2020-01-02", "2020-01-01"),
                           (None, "2020-01-01"), ("2020-01-01", "bad")):
            with self.subTest(start=start, end=end):
                self.reject(c.DateInterval, start, end)
        self.assertNotEqual(listing(effective=None), listing(effective=c.DateInterval("2020-01-01", None)))

    def test_alias_adjacent_gapped_and_reordered_intervals(self):
        first = alias(effective=c.DateInterval("2020-01-01", "2021-01-01"))
        for second in (alias(effective=c.DateInterval("2021-01-01", None)),
                       alias(effective=c.DateInterval("2022-01-01", "2023-01-01"))):
            with self.subTest(second=second):
                self.assertEqual(listing(aliases=(first, second)).aliases, (first, second))
                self.assertEqual(listing(aliases=(second, first)).aliases, (second, first))
                self.assertNotEqual(listing(aliases=(first, second)), listing(aliases=(second, first)))

    def test_alias_duplicate_overlap_and_unknown_rejection(self):
        first = alias(effective=c.DateInterval("2020-01-01", "2022-01-01"))
        for second in (first, replace(first, evidence_key=key("artifact")), alias(),
                       alias(effective=c.DateInterval("2021-01-01", None)),
                       alias(effective=c.DateInterval("2019-01-01", "2021-01-01")),
                       alias(effective=c.DateInterval("2019-01-01", None))):
            with self.subTest(second=second):
                self.reject(listing, aliases=(first, second))
                self.reject(listing, aliases=(second, first))
        self.reject(listing, aliases=(alias(), alias(evidence_key=key("artifact"))))
        self.assertEqual(len(listing(aliases=(alias(), alias(provider="other"), alias(product="other"),
                                             alias(symbol="brk.b"))).aliases), 4)

    def test_duplicate_members_and_conflicting_authority_metadata(self):
        first = authority()
        for second in (first, replace(first, evidence_key=key("artifact")),
                       replace(first, effective=c.DateInterval("2020-01-01", None))):
            with self.subTest(second=second):
                self.reject(replace, entity(), authority_ids=(first, second))
                self.reject(security, authority_ids=(first, second))
        for status, candidates, evidences in (
            ("ambiguous", (entity().key, entity().key), (key("artifact"),)),
            ("resolved", (entity().key,), (key("artifact"), key("artifact"))),
        ):
            with self.subTest(status=status):
                self.reject(c.IdentityResolution, status, candidates, evidences, "duplicate")

    def test_resolution_status_counts_and_namespaces(self):
        self.assertEqual(c.IdentityResolution("unresolved", (), (), "unknown").candidate_keys, ())
        self.assertEqual(c.IdentityResolution("ambiguous", (entity().key, entity(False).key),
                                             (key("authority_record"),), "collision").status, "ambiguous")
        for status, candidates, evidences in (
            ("resolved", (), (key("artifact"),)), ("resolved", (entity().key,), ()),
            ("resolved", (entity().key, entity(False).key), (key("artifact"),)),
            ("ambiguous", (entity().key,), (key("artifact"),)),
            ("unresolved", (entity().key,), ()), ("unknown", (), ()),
            ("resolved", (key("security"),), (key("artifact"),)),
            ("resolved", (entity().key,), (key("admission_record"),)),
        ):
            with self.subTest(status=status, candidates=candidates, evidences=evidences):
                self.reject(c.IdentityResolution, status, candidates, evidences, "reason")

    def test_unicode_label_boundaries_and_preservation(self):
        for value in ("x" * 200, "😀" * 200, "e\u0301", "é", "Names 中 with spaces"):
            with self.subTest(value=value[:20]):
                record = replace(entity(), legal_name=value)
                self.assertEqual(c.decode(c.encode(record)).legal_name, value)
        for value in ("x" * 201, "😀" * 201):
            self.reject(replace, entity(), legal_name=value)
        self.assertNotEqual(replace(entity(), legal_name="e\u0301"), replace(entity(), legal_name="é"))
        self.assertEqual(security(share_class="😀" * 64).share_class, "😀" * 64)
        self.reject(security, share_class="😀" * 65)

    def test_reject_controls_surrogates_bidi_and_boundary_whitespace(self):
        for value in ("", " x", "x ", "\tx", "x\n", "x\x00", "x\x7f", "x\x85", "x\ud800", "x\udfff",
                      "x\u202a", "x\u202e", "x\u2066", "x\u2069", "\u00a0x", "x\u3000"):
            with self.subTest(value=ascii(value)):
                self.reject(replace, entity(), legal_name=value)
                data = wire(entity())
                data["record"]["legal_name"] = value
                self.reject(c.decode, json.dumps(data).encode())
        self.reject(c.decode, b'{"schema_versi\\ud800on":1,"record":null}')

    def test_ascii_identifier_token_symbol_and_chunk_boundaries(self):
        self.assertEqual(len(key("artifact", "a" * 128).id), 128)
        self.assertEqual(len(authority(identifier="a" * 128).identifier), 128)
        for value in ("a" * 129, "-a", "a/b", "a b", "é", "a?", "a%20"):
            with self.subTest(value=value):
                self.reject(key, "artifact", value)
                self.reject(authority, identifier=value)
        for field in ("provider", "product"):
            self.assertEqual(len(getattr(alias(**{field: "." * 64}), field)), 64)
            for value in ("a" * 65, "", "a/b", "é"):
                with self.subTest(field=field, value=value):
                    self.reject(alias, **{field: value})
        self.assertEqual(alias(symbol="A" + ":/+-._" * 10).symbol[0], "A")
        self.assertEqual(len(alias(symbol="A" * 64).symbol), 64)
        for value in ("A" * 65, ".A", "A B", "é", ""):
            with self.subTest(symbol=value):
                self.reject(alias, symbol=value)
        self.assertEqual(len(evidence(chunk_id="a" * 50).chunk_id), 50)
        self.reject(evidence, chunk_id="a" * 51)

    def test_other_tokens_widths_and_hashes(self):
        for changes in (dict(mic="ABC"), dict(mic="ABCDE"), dict(mic="xnas"), dict(mic="XNAé"),
                        dict(currency="US"), dict(currency="USDD"), dict(currency="usd")):
            with self.subTest(changes=changes):
                self.reject(listing, **changes)
        self.assertEqual(listing(mic="AB12").mic, "AB12")
        for value in ("U", "USA", "us", "éA", 1):
            with self.subTest(jurisdiction=value):
                self.reject(replace, entity(), jurisdiction=value)
        for field, maker in (("authority", authority), ("calendar_version", listing),
                             ("reason_code", lambda **kw: c.IdentityResolution("unresolved", (), (), **kw))):
            with self.subTest(field=field):
                self.assertEqual(len(getattr(maker(**{field: "a" * 64}), field)), 64)
                self.reject(maker, **{field: "a" * 65})
                self.reject(maker, **{field: "a/b"})
        for value in ("A" * 64, "a" * 63, "a" * 65, "g" * 64, None, 1):
            with self.subTest(digest=value):
                self.reject(evidence, manifest_sha256=value)
                self.reject(evidence, c.SessionArtifactRef, artifact_sha256=value)
                self.reject(evidence, c.MarketPublicationRef, manifest_sha256=value)

    def test_collection_boundaries_direct_and_wire(self):
        authorities = tuple(authority(identifier="id" + str(i)) for i in range(17))
        aliases = tuple(alias(symbol="S" + str(i)) for i in range(65))
        candidates = tuple(key("external_entity", "e" + str(i)) for i in range(17))
        evidences = tuple(key("artifact", "a" + str(i)) for i in range(17))
        records = (
            replace(entity(), authority_ids=authorities[:16]), security(authority_ids=authorities[:16]),
            listing(aliases=aliases[:64]),
            c.IdentityResolution("ambiguous", candidates[:16], evidences[:16], "bounded"),
        )
        for record in records:
            with self.subTest(kind=record.kind):
                self.assertEqual(c.decode(c.encode(record)), record)
        for operation in (lambda: replace(entity(), authority_ids=authorities),
                          lambda: security(authority_ids=authorities), lambda: listing(aliases=aliases),
                          lambda: c.IdentityResolution("ambiguous", candidates, evidences[:16], "bound"),
                          lambda: c.IdentityResolution("ambiguous", candidates[:16], evidences, "bound")):
            with self.subTest(operation=operation):
                self.reject(operation)
        for record, field, item in ((records[0], "authority_ids", authorities[-1]),
                                    (records[2], "aliases", aliases[-1]),
                                    (records[3], "candidate_keys", candidates[-1]),
                                    (records[3], "evidence_keys", evidences[-1])):
            with self.subTest(field=field):
                data = wire(record)
                data["record"][field].append(c._wire(item))
                self.reject(c.decode, raw(data))

    def test_constructor_exact_types_no_mutable_or_coercive_values(self):
        class String(str):
            pass

        class Integer(int):
            pass

        class Key(c.KeyRef):
            pass

        for operation in (lambda: key("artifact", String("test")),
                          lambda: evidence(data_version=Integer(0)),
                          lambda: security(key=Key("security", "test")),
                          lambda: replace(entity(), authority_ids=[]),
                          lambda: listing(aliases=[alias()]),
                          lambda: c.IdentityResolution("unresolved", iter(()), (), "reason"),
                          lambda: evidence(public_available_at={"kind": "unknown"}),
                          lambda: listing(effective={"start": "2020-01-01", "end": None}),
                          lambda: c.TimePoint.instant(__import__("datetime").datetime(2026, 1, 1)),
                          lambda: c.EvidenceRef(**{f.name: getattr(evidence(), f.name) for f in fields(c.EvidenceRef)})):
            with self.subTest(operation=operation):
                self.reject(operation)

    def test_nested_immutability_and_fresh_copies(self):
        source = wire(listing())
        decoded = c.decode(raw(source))
        before = c.encode(decoded)
        source["record"]["aliases"][0]["symbol"] = "changed"
        source["record"]["aliases"].clear()
        self.assertEqual(c.encode(decoded), before)
        for value, name in ((decoded, "mic"), (decoded.key, "id"), (decoded.aliases[0], "symbol"),
                            (c.DateInterval("2020-01-01", None), "end"),
                            (c.TimePoint.instant("2026-01-01T00:00:00Z"), "value"),
                            (authority(), "identifier")):
            with self.subTest(value=value):
                with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
                    setattr(value, name, "changed")
                self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(TypeError):
            decoded.aliases[0] = alias()
        self.assertIsNot(decoded, c.decode(before))
        self.assertIsNot(decoded.aliases, c.decode(before).aliases)

    def test_canonical_serialization_and_input_order(self):
        for record in roots():
            with self.subTest(kind=record.kind):
                encoded = c.encode(record)
                self.assertIs(type(encoded), bytes)
                self.assertEqual(encoded, json.dumps(wire(record), ensure_ascii=False, allow_nan=False,
                                                     sort_keys=True, separators=(",", ":")).encode("utf-8"))
                self.assertEqual(c.encode(c.decode(encoded)), encoded)
                reordered = dict(reversed(list(wire(record).items())))
                noncanonical = json.dumps(reordered, indent=2, ensure_ascii=True).encode()
                self.assertEqual(c.encode(c.decode(noncanonical)), encoded)
        self.assertIn("例".encode(), c.encode(entity()))
        self.assertNotIn(b"\\u4f8b", c.encode(entity()))

    def test_bytes_utf8_bom_and_syntax_rejection(self):
        for data in (bytearray(c.encode(entity())), memoryview(c.encode(entity())), c.encode(entity()).decode(),
                     b"\xef\xbb\xbf" + c.encode(entity()), b"\xff", b"", b"{}{}", b"{]", b"[}",
                     b'{"a":1,}', b"[1,]", b"[01]", b'{"a" 1}', b"[true false]", b'"\\x00"',
                     b'{"a":"unterminated}', b"{" + b" " * 10, b"[undefined]", b"[.1]", b"[] trailing"):
            with self.subTest(data=repr(data)[:80]):
                self.reject(c.decode, data)
        for value in (key("artifact"), c.TimePoint.unknown(), c.DateInterval("2020-01-01", None),
                      {}, [], None):
            self.reject(c.encode, value)

    def test_exact_byte_input_boundary_and_one_over(self):
        payload = c.encode(entity())
        boundary = payload + b" " * (c.MAX_BYTES - len(payload))
        self.assertEqual(len(boundary), 65536)
        self.assertEqual(c.decode(boundary), entity())
        with self.assertRaisesRegex(c.ContractError, "byte limit"):
            c.decode(boundary + b" ")
        # Byte check precedes even UTF-8 or string materialization.
        with patch.object(c.json.decoder, "scanstring", side_effect=AssertionError("parsed early")):
            with self.assertRaisesRegex(c.ContractError, "byte limit"):
                c.decode(b"\xff" * 65537)

    def test_depth_preflight_before_strings_are_decoded(self):
        boundary = b"[" * 8 + b"null" + b"]" * 8
        c._preflight(boundary)
        self.assertEqual(c._Parser(boundary.decode()).value(), [[[[[[[[None]]]]]]]])
        # Depth 8 generic JSON parses, but is not a valid C1 root fixture.
        self.reject(c.decode, boundary)
        with patch.object(c.json.decoder, "scanstring", side_effect=AssertionError("parsed early")):
            with self.assertRaisesRegex(c.ContractError, "depth limit"):
                c.decode(b"[" * 9 + b'"x"' + b"]" * 9)
        # Brackets and escaped quotes in labels do not add container depth.
        record = replace(entity(), legal_name='[[[{"x":"\\"}]]]' * 8)
        self.assertEqual(c.decode(c.encode(record)), record)

    def test_nodes_include_names_and_containers_and_stop_incrementally(self):
        boundary = "[" + ",".join("null" for _ in range(2047)) + "]"
        parser = c._Parser(boundary)
        self.assertEqual(len(parser.value()), 2047)
        self.assertEqual(parser.nodes, 2048)
        self.reject(c.decode, boundary.encode())  # invalid schema, never advertised valid
        parser = c._Parser(boundary[:-1] + ",null]")
        with self.assertRaisesRegex(c.ContractError, "node limit"):
            parser.value()
        self.assertEqual(parser.nodes, 2049)
        with self.assertRaisesRegex(c.ContractError, "node limit"):
            c.decode((boundary[:-1] + ",null]").encode())
        tree = {"x": [None, {"y": 1}]}
        parser = c._Parser(json.dumps(tree))
        self.assertEqual(parser.value(), tree)
        self.assertEqual(parser.nodes, node_count(tree))

    def test_direct_construction_aggregate_enforcement(self):
        record = listing()
        size = len(c.encode(record))
        count = node_count(wire(record))
        with patch.object(c, "MAX_BYTES", size):
            self.assertEqual(listing(), record)
        with patch.object(c, "MAX_BYTES", size - 1):
            self.reject(listing)
        with patch.object(c, "MAX_NODES", count):
            self.assertEqual(listing(), record)
        with patch.object(c, "MAX_NODES", count - 1):
            self.reject(listing)
        # Deepest current closed shape is envelope/record/array/member/nested value (5).
        with patch.object(c, "MAX_DEPTH", 5):
            self.assertEqual(listing(), record)
        with patch.object(c, "MAX_DEPTH", 4):
            self.reject(listing)

    def test_largest_closed_listing_shape_stays_below_aggregate_caps(self):
        record = listing(calendar_version="v" * 64,
                         aliases=tuple(alias(provider="p" * 64, product="q" * 64,
                                             symbol="S" * 62 + f"{i:02}",
                                             effective=c.DateInterval("0001-01-01", "9999-12-31"),
                                             evidence_key=key("authority_record", "a" * 128))
                                       for i in range(64)))
        self.assertEqual(c.decode(c.encode(record)), record)
        # The aggregate byte/node/depth caps need no invented valid schema fixture.
        self.assertLess(len(c.encode(record)), c.MAX_BYTES)
        self.assertLess(node_count(wire(record)), c.MAX_NODES)

    def test_surrogate_pairs_and_rfc_clock_ranges(self):
        data = wire(entity())
        data["record"]["legal_name"] = "😀"
        self.assertEqual(c.decode(json.dumps(data).encode()).legal_name, "😀")
        for time in ("2026-10-29T00:60:00Z", "2026-10-29T00:00:61Z",
                     "2026-10-29T24:00:00.000000Z", "2026-10-29T24:01:00+00:00"):
            with self.subTest(time=time):
                self.reject(c.TimePoint.instant, time)

    def test_escaped_limits_are_checked_after_decoding(self):
        for count in (200, 201):
            with self.subTest(count=count):
                data = c.encode(entity()).replace('Example 例'.encode(), b"\\u0061" * count)
                if count == 200:
                    self.assertEqual(c.decode(data).legal_name, "a" * count)
                else:
                    self.reject(c.decode, data)

    def test_rights_origin_and_forged_metadata_remain_untrusted(self):
        private = evidence(c.SessionArtifactRef, origin="official_sec",
                           rights_policy_key=key("rights_policy", "forged"),
                           admission_record_key=key("admission_record", "forged"))
        self.assertEqual(c.decode(c.encode(private)), private)
        self.assertFalse(hasattr(private, "authorized"))
        self.assertFalse(hasattr(private, "admitted"))
        self.reject(c.check_reference_context, private)
        for origin in ("sec", "market_provider", "verified", None):
            with self.subTest(origin=origin):
                self.reject(evidence, c.SessionArtifactRef, origin=origin)
        for cls in (c.DatabasePublicationRef, c.MarketPublicationRef):
            self.reject(evidence, cls, origin="user_upload")
        market = evidence(c.MarketPublicationRef, owner_key=key("principal"), session_key=key("session"))
        self.assertEqual(c.decode(c.encode(market)), market)
        self.reject(evidence, c.MarketPublicationRef, session_key=key("session"))
        self.assertIsNone(evidence(c.SessionArtifactRef).rights_policy_key)
        self.assertIsNone(evidence(c.SessionArtifactRef).admission_record_key)

    def test_inert_import_ast_boundary(self):
        tree = ast.parse(Path(c.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {"dataclasses", "datetime", "json", "re", "unicodedata", "typing"})

    def test_guarded_fresh_process_import_and_all_constructors(self):
        source = Path(c.__file__).read_text(encoding="utf-8")
        fixture_source = Path(__file__).read_text(encoding="utf-8").split("class ContractTests")[0]
        # Only pure fixture helper definitions, without test module imports/path setup.
        fixture_source = fixture_source[fixture_source.index("def key("):]
        probe = r'''
import builtins, dataclasses, datetime, importlib.metadata, io, json, os, pathlib
import random, re, secrets, socket, sys, types, typing, unicodedata, uuid
payload = json.loads(sys.stdin.read())
code = compile(payload["source"], "<guarded-c1>", "exec")
fixtures = compile(payload["fixtures"], "<pure-fixtures>", "exec")
attempts = []
def deny(*args, **kwargs):
    attempts.append("forbidden effect")
    raise AssertionError("forbidden operational effect")
original_import = builtins.__import__
allowed = {"dataclasses", "datetime", "json", "re", "unicodedata", "typing"}
def guarded_import(name, *args, **kwargs):
    if name not in allowed:
        attempts.append("import:" + name)
        raise AssertionError("forbidden import")
    return original_import(name, *args, **kwargs)
class Environment:
    __getitem__ = get = __iter__ = __contains__ = __len__ = deny
builtins.open = io.open = deny
os.getenv = os.urandom = os.system = deny
os.environ = Environment()
socket.socket = socket.create_connection = socket.getaddrinfo = deny
random.random = random.getrandbits = secrets.token_bytes = secrets.token_hex = deny
uuid.uuid4 = uuid.uuid1 = importlib.metadata.entry_points = deny
pathlib.Path.open = pathlib.Path.read_text = pathlib.Path.read_bytes = deny
def audit(event, args):
    if event == "open" or event.startswith(("socket.", "subprocess.", "os.system", "os.listdir", "os.scandir")):
        deny()
sys.addaudithook(audit)
builtins.__import__ = guarded_import
# Positive sentinel controls: effects must be recorded even if a caller catches.
controls = [lambda: builtins.open("not-opened"), lambda: os.getenv("NOT_READ"),
            lambda: os.environ.get("NOT_READ"), lambda: socket.socket(),
            lambda: uuid.uuid4(), lambda: os.urandom(1),
            lambda: importlib.metadata.entry_points(), lambda: guarded_import("app.config"),
            lambda: guarded_import("sqlalchemy"), lambda: guarded_import("sentence_transformers")]
for control in controls:
    before = len(attempts)
    try:
        control()
    except AssertionError:
        pass
    assert len(attempts) > before
attempts.clear()
module = types.ModuleType("guarded_c1")
sys.modules[module.__name__] = module
exec(code, module.__dict__)
scope = {"c": module, "json": json}
exec(fixtures, scope)
for record in scope["roots"]():
    assert module.decode(module.encode(record)) == record
assert module.canonical_sec_cik("1") == "0000000001"
module.AuthorityIdentifier("authority_id", "source", "id", module.KeyRef("artifact", "a"),
                           module.DateInterval("2020-01-01", None))
module.TimePoint.instant("2026-10-29T08:00:00.123456+08:00")
module.check_reference_context(scope["listing"](), entity=scope["entity"](), security=scope["security"]())
assert attempts == [], attempts
assert not any(n.startswith(("app.", "sqlalchemy", "fastapi", "dotenv", "torch", "transformers")) for n in sys.modules)
print("PASS: guarded import, constructors, context and codec; 10 sentinel controls")
'''
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", probe],
                                input=json.dumps({"source": source, "fixtures": fixture_source}),
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("10 sentinel controls", result.stdout)

    def test_targeted_in_memory_mutation_controls(self):
        source = Path(c.__file__).read_text(encoding="utf-8")
        # Each control reaches the changed semantic branch; unrelated parse/guard
        # failure is a test error, not a killed mutant. No candidate file is edited.
        cases = (
            ("pin_boolean", "type(value) is int and 0 <= value <= MAX_PIN",
             "isinstance(value, int) and 0 <= value <= MAX_PIN",
             lambda m: m._pin(True)),
            ("namespace", 'value.namespace in namespaces, "key: wrong namespace"',
             'True, "key: wrong namespace"',
             lambda m: m.SecurityRef(m.KeyRef("listing", "x"), m.KeyRef("external_entity", "e"), "A", ())),
            ("cik_wire", '_cik(self.id)', '_cik(canonical_sec_cik(self.id))',
             lambda m: m.KeyRef("sec_cik", "1")),
            ("interval_equal", 'self.start < self.end, "interval: empty or reversed"',
             'self.start <= self.end, "interval: empty or reversed"',
             lambda m: m.DateInterval("2020-01-01", "2020-01-01")),
            ("alias_overlap", 'disjoint, "aliases: overlapping intervals"',
             'True, "aliases: overlapping intervals"',
             lambda m: m.ListingRef(m.KeyRef("listing", "l"), m.KeyRef("security", "s"), "XNAS", "USD",
                                   m.KeyRef("calendar", "c"), "v1", None,
                                   tuple(m.SymbolAlias("p", "p", "S", m.DateInterval(start, end),
                                                       m.KeyRef("artifact", start)) for start, end in
                                         (("2020-01-01", "2022-01-01"), ("2021-01-01", "2023-01-01"))))),
            ("duplicate_json", 'key not in result, "json: duplicate member name"',
             'True, "json: duplicate member name"',
             lambda m: m.decode(c.encode(entity()).replace(b'"schema_version":1',
                                                          b'"schema_version":1,"schema_version":1'))),
            ("owner_context", 'record.owner_key == expected_owner_key, "context: owner mismatch"',
             'True, "context: owner mismatch"',
             lambda m: m.check_reference_context(m.decode(c.encode(evidence(c.SessionArtifactRef))),
                                                expected_owner_key=m.KeyRef("principal", "other"),
                                                expected_session_key=m.KeyRef("session", "test"))),
            ("hash_case", 'r"[0-9a-f]{64}"', 'r"[0-9a-fA-F]{64}"',
             lambda m: m._digest("A" * 64)),
        )
        for name, old, new, exercise in cases:
            with self.subTest(mutant=name):
                self.assertEqual(source.count(old), 1)
                original = types.ModuleType("c1_original_" + name)
                mutant = types.ModuleType("c1_mutant_" + name)
                for module, code in ((original, source), (mutant, source.replace(old, new))):
                    sys.modules[module.__name__] = module
                    try:
                        exec(compile(code, "<mutation-control>", "exec"), module.__dict__)
                    finally:
                        del sys.modules[module.__name__]
                with self.assertRaises(original.ContractError):
                    exercise(original)
                # The altered implementation erroneously accepts this input.
                exercise(mutant)


class CountingResult(unittest.TextTestResult):
    successful_subtests = 0
    failed_subtests = 0

    def addSubTest(self, test, subtest, err):
        if err is None:
            self.successful_subtests += 1
        else:
            self.failed_subtests += 1
        super().addSubTest(test, subtest, err)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CountingResult)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests))
    print(f"Subtests: {result.successful_subtests} passed, {result.failed_subtests} failed")
    sys.exit(not result.wasSuccessful())
