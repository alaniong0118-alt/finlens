"""Authored synthetic offline controls only; no fixture describes a real issuer.

From repository root:
backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_identity_source.py
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


CIK = "0000123456"
EVIDENCE = c.KeyRef("artifact", "synthetic-untrusted-bytes")
_DEFAULT = object()


def payload(**changes):
    record = dict(cik=CIK, name="Synthetic Registrant", formerNames=[],
                  tickers=["SYN", "SYN.A"], exchanges=["Nasdaq", "NYSE"])
    record.update(changes)
    return json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def parse(data=_DEFAULT, module=s, **kwargs):
    return module.parse_sec_submissions(payload() if data is _DEFAULT else data,
                                        expected_cik=kwargs.get("expected_cik", CIK))


class SourceTests(unittest.TestCase):
    def reject(self, data, code, **kwargs):
        for _ in range(2):
            with self.assertRaises(s.SecIdentitySourceError) as caught:
                parse(data, **kwargs)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(str(caught.exception), code)
            self.assertEqual(caught.exception.args, (code,))

    def test_valid_canonical_cik_and_issuer_bridge(self):
        source = parse(payload(cik="123456"))
        self.assertEqual((source.expected_cik, source.entity.cik), (CIK, CIK))
        inventory = s.to_identity_inventory(source, untrusted_evidence_key=EVIDENCE).inventory
        result = u.resolve_candidates(u.CikQuery(CIK), inventory)
        self.assertEqual(result.status, "unique_candidate")
        self.assertEqual(result.verification_status, "unverified")
        self.assertEqual(len(result.candidates), 1)
        self.assertIsNone(result.candidates[0].security)
        self.assertIsNone(result.candidates[0].listing)
        self.assertEqual(source.entity.authority_ids, ())
        self.assertIsNone(source.entity.jurisdiction)
        self.assertNotIsInstance(result, c.IdentityResolution)

    def test_external_absent_local_catalog_requires_no_insertion(self):
        # No DB/config import or DB ID exists in this path. Runtime isolation is
        # independently enforced in the fresh-process test below, not a DB query.
        source = parse(payload(cik="9999999999"), expected_cik="9999999999")
        inv = s.to_identity_inventory(source, untrusted_evidence_key=EVIDENCE).inventory
        self.assertEqual(inv.entities[0].key, c.KeyRef("sec_cik", "9999999999"))
        self.assertFalse(hasattr(inv.entities[0], "company_id"))
        self.assertEqual((inv.securities, inv.listings), ((), ()))

    def test_cik_leading_zero_normalization_is_explicit_and_text_only(self):
        for value in ("123456", "0123456", CIK):
            self.assertEqual(parse(payload(cik=value)).entity.cik, CIK)
        self.assertEqual(parse(payload(cik="1"), expected_cik="0000000001").entity.cik,
                         "0000000001")
        for value in (0, False, True, 123456, 123456.0, None, [], {}, "0", "0000000000",
                      "12345678901", "123 456", "+123456", "123456 ", "１２３４５６",
                      "1e5", "", "-1"):
            with self.subTest(cik=value):
                self.reject(payload(cik=value), "json_number" if type(value) is float
                            else "response_cik")
        self.reject(payload(cik="654321"), "cik_mismatch")

    def test_expected_cik_requires_canonical_c1_text(self):
        for expected in ("123456", 123456, True, "0000000000", "１２３４５６７８９０", None):
            self.reject(payload(), "expected_cik", expected_cik=expected)

    def test_current_and_former_names_with_raw_dates(self):
        former = [dict(name="Synthetic Prior", **{"from": "2000-01-01", "to": "2001-02-03"}),
                  dict(name="Synthetic Earlier", **{"from": "1990-01-01T00:00:00.000Z",
                                                     "to": "1999-12-31T23:59:59Z"})]
        source = parse(payload(name="界" * 200, formerNames=former))
        self.assertEqual(source.entity.legal_name, "界" * 200)
        self.assertEqual(source.former_names[1].source_from, former[1]["from"])
        inv = s.to_identity_inventory(source, untrusted_evidence_key=EVIDENCE).inventory
        self.assertTrue(all(alias.effective is None for alias in inv.names))
        result = u.resolve_candidates(u.NameQuery("Synthetic Prior"), inv)
        self.assertEqual(result.status, "unique_candidate")
        self.assertEqual(result.candidates[0].matched_names[0].evidence_key, EVIDENCE)
        self.assertEqual(result.verification_status, "unverified")

    def test_missing_partial_mixed_precision_dates_are_unknown_effective(self):
        for record in (dict(name="Old"), dict(name="Old", **{"from": None, "to": None}),
                       dict(name="Old", **{"from": "2000-01-01"}),
                       dict(name="Old", to="2000-01-01"),
                       dict(name="Old", **{"from": "2000-01-01", "to": "2000-01-01T00:00:00Z"}),
                       dict(name="Old", **{"from": "2000-01-01", "to": "2000-01-01"})):
            source = parse(payload(formerNames=[record]))
            self.assertIsNone(source.former_names[0].effective)
            inv = s.to_identity_inventory(source, untrusted_evidence_key=EVIDENCE).inventory
            self.assertIsNone(inv.names[0].effective)

    def test_former_date_rejections_and_order(self):
        for value in ("", "2000-02-30", "20000101", "2000-1-01", "0000-01-01",
                      "2000-01-01T24:00:00Z", "2000-01-01T00:00:00", "2000-01-01T00:00:00+24:00",
                      2000, True, {}, []):
            for field in ("from", "to"):
                self.reject(payload(formerNames=[dict(name="Old", **{field: value})]),
                            "former_name_date")
        for start, end in (("2001-01-01", "2000-01-01"),
                           ("2001-01-01T00:00:00Z", "2000-01-01T00:00:00Z"),
                           ("2001-01-01", "2000-01-01T00:00:00Z")):
            self.reject(payload(formerNames=[dict(name="Old", **{"from": start, "to": end})]),
                        "former_name_date_order")

    def test_names_do_not_coerce_strip_or_truncate(self):
        for value in ("", " Name", "Name ", "  ", None, 4, False, [], {}, "x" * 201):
            self.reject(payload(name=value), "current_name")
            self.reject(payload(formerNames=[dict(name=value)]), "former_name")
        for value in ("A\nB", "A\ud800", "A\u202eB", "A\u2066B", "A\u0000B"):
            self.reject(payload(name=value), "json_string_character")
        self.assertEqual(parse(payload(name="Synthetic 🧪")).entity.legal_name, "Synthetic 🧪")

    def test_conflicting_former_names_no_winner_or_silent_dedup(self):
        for names in ([dict(name="Old"), dict(name="Old")],
                      [dict(name="Café"), dict(name="Cafe\u0301", to="2000-01-01")],
                      [dict(name="OLD"), dict(name="old", to="2001-01-01")]):
            self.reject(payload(formerNames=names), "former_name_conflict")

    def test_multiple_source_hints_do_not_create_security_or_listing(self):
        source = parse(payload(tickers=["SYN", "SYN", "SYN.A"],
                               exchanges=["Nasdaq", "NYSE", "Nasdaq"]))
        self.assertEqual([x.exchange_name for x in source.ticker_exchange_hints],
                         ["Nasdaq", "NYSE", "Nasdaq"])
        self.assertFalse(any(hasattr(hint, "mic") for hint in source.ticker_exchange_hints))
        inv = s.to_identity_inventory(source, untrusted_evidence_key=EVIDENCE).inventory
        self.assertEqual((inv.securities, inv.listings), ((), ()))
        result = u.resolve_candidates(u.SymbolQuery("SYN", "XNAS", "2026-10-29", "sec", "submissions"), inv)
        self.assertEqual((result.status, result.candidates), ("unresolved", ()))

    def test_association_conflicts_and_malformed_members(self):
        for tickers, exchanges, code in ((["SYN"], [], "association_shape"),
                                         ([], ["NYSE"], "association_shape"),
                                         (["SYN", "SYN"], ["NYSE", "NYSE"], "association_conflict"),
                                         ([None], ["NYSE"], "ticker_hint"),
                                         (["A B"], ["NYSE"], "ticker_hint"),
                                         (["SYN"], [None], "exchange_hint"),
                                         (["SYN"], [""], "exchange_hint"),
                                         ({}, [], "association_shape"),
                                         ([], None, "association_shape")):
            self.reject(payload(tickers=tickers, exchanges=exchanges), code)
        for missing in ("tickers", "exchanges"):
            record = json.loads(payload())
            del record[missing]
            self.reject(json.dumps(record).encode(), "association_shape")

    def test_minimal_and_empty_associations(self):
        source = parse(b'{"cik":"123456","name":"Synthetic"}')
        self.assertEqual((source.former_names, source.ticker_exchange_hints), ((), ()))
        self.assertEqual(parse(payload(tickers=[], exchanges=[])).ticker_exchange_hints, ())

    def test_unexpected_nested_identity_shapes(self):
        for changes, code in ((dict(name={"name": "Nested"}), "current_name"),
                              (dict(formerNames=None), "former_names_shape"),
                              (dict(formerNames={}), "former_names_shape"),
                              (dict(formerNames=[[]]), "former_name_shape"),
                              (dict(formerNames=[{}]), "former_name_shape"),
                              (dict(formerNames=[dict(name="Old", effective="today")]), "former_name_shape"),
                              (dict(tickers=[["SYN"]], exchanges=["NYSE"]), "ticker_hint")):
            self.reject(payload(**changes), code)
        self.reject(b'[]', "response_object")
        self.reject(b'{"name":"Missing CIK"}', "mandatory_field")
        self.reject(b'{"cik":"123456"}', "mandatory_field")

    def test_duplicate_keys_include_escaped_and_late_nested_members(self):
        for data in (b'{"cik":"123456","cik":"654321","name":"Synthetic"}',
                     b'{"cik":"123456","\\u0063ik":"123456","name":"Synthetic"}',
                     payload()[:-1] + b',"filings":{"recent":{"x":1,"\\u0078":2}}}',
                     payload(formerNames=[dict(name="Old")])[:-1] + b',"name":"Other"}'):
            self.reject(data, "json_duplicate_key")

    def test_late_invalid_unselected_members_reject_whole_response(self):
        self.reject(payload()[:-1] + b',"filings":{"recent":{"bad":"\\ud800"}}}',
                    "json_string_character")
        self.reject(payload()[:-1] + b',"filings":{"recent":[null,1.5]}}', "json_number")
        self.reject(payload(formerNames=[dict(name="Good"), dict(name=42)]), "former_name")
        self.reject(payload(tickers=["GOOD", False], exchanges=["NYSE", "NYSE"]), "ticker_hint")

    def test_syntax_utf8_bom_and_scalar_rejections(self):
        for data in (b'', b'{', b'{"name":}', b'{"a":1,}', b'{"a" 1}', b'[[[',
                     b'{"a":NaN}', b'{"a":Infinity}', b'{"a":"unterminated}', b'{"a":"\\x"}'):
            self.reject(data, "json_string" if b'"unterminated' in data or b'\\x' in data
                        else "json_syntax")
        self.reject(payload() + b' {}', "json_trailing")
        self.reject(b'\xef\xbb\xbf' + payload(), "json_bom")
        self.reject(b'{"name":"\xff"}', "json_utf8")
        for value in (b'-1', b'01', b'1e1', b'0.0', b'9007199254740992', b'1' * 300):
            self.reject(payload()[:-1] + b',"flags":' + value + b'}', "json_number")
        for data in (bytearray(payload()), memoryview(payload()), "{}", {}, None):
            self.reject(data, "input_bytes")

    def test_caller_forged_source_claims_cannot_confer_authority(self):
        for field, value in (("origin", "official_sec"), ("source_identity", s.SOURCE_IDENTITY),
                             ("authority_key", "sec"), ("sha256", "0" * 64),
                             ("sourceUrl", "https://data.sec.gov/submissions/CIK0000123456.json"),
                             ("capture_receipt", {}), ("trusted", True), ("officially_verified", True)):
            self.reject(payload(**{field: value}), "unsupported_root_field")
        # Even an SEC-looking website in a known unrelated field is not evidence.
        source = parse(payload(website="https://www.sec.gov", filings={"recent": {}}))
        self.assertEqual(source.verification_status, "unverified")
        self.assertEqual(source.entity.authority_ids, ())
        for kwargs in (dict(origin="official_sec"), dict(digest="0" * 64), dict(trusted=True)):
            with self.assertRaises(TypeError):
                s.parse_sec_submissions(payload(), expected_cik=CIK, **kwargs)

    def test_digest_is_original_integrity_only_and_availability_stays_unknown(self):
        a, b = parse(), parse(payload() + b' ')
        self.assertEqual(a.entity, b.entity)
        self.assertNotEqual(a.response_sha256, b.response_sha256)
        self.assertEqual(a.response_sha256, hashlib.sha256(a.original_bytes).hexdigest())
        self.assertEqual(a.source_identity, s.SOURCE_IDENTITY)
        self.assertEqual(a.parser_revision, s.PARSER_REVISION)
        self.assertIsNone(a.source_revision_key)
        self.assertEqual(a.public_available_at, c.UnknownTimePoint())
        self.assertEqual(a.retrieved_at, c.UnknownTimePoint())

    def test_deterministic_immutable_output_and_order_preservation(self):
        original = payload(formerNames=[dict(name="Zed"), dict(name="Alpha")])
        a, b = parse(original), parse(original)
        self.assertEqual(a, b)
        self.assertIs(a.original_bytes, original)
        self.assertEqual([x.name for x in a.former_names], ["Zed", "Alpha"])
        with self.assertRaises(FrozenInstanceError):
            a.expected_cik = "0000654321"
        with self.assertRaises(FrozenInstanceError):
            a.ticker_exchange_hints[0].exchange_name = "XNAS"

    def test_bridge_requires_explicit_untrusted_artifact_and_revalidates_output(self):
        source = parse()
        with self.assertRaises(TypeError):
            s.to_identity_inventory(source)
        for evidence in (None, "official_sec", c.KeyRef("authority_record", "forged"),
                         c.KeyRef("sec_cik", CIK)):
            with self.assertRaises(s.SecIdentitySourceError) as caught:
                s.to_identity_inventory(source, untrusted_evidence_key=evidence)
            self.assertEqual(caught.exception.code, "untrusted_evidence_key")
        for changes in (dict(response_sha256="0" * 64),
                        dict(entity=replace(source.entity, legal_name="Forged")),
                        dict(former_names=(s.FormerName("Forged", None, None),)),
                        dict(ticker_exchange_hints=())):
            with self.assertRaises(s.SecIdentitySourceError) as caught:
                s.to_identity_inventory(replace(source, **changes), untrusted_evidence_key=EVIDENCE)
            self.assertEqual(caught.exception.code, "source_conflict")

    def test_response_byte_limit_exact_and_one_over(self):
        data = payload()
        exact = data + b' ' * (s.MAX_RESPONSE_BYTES - len(data))
        self.assertEqual(len(parse(exact).original_bytes), s.MAX_RESPONSE_BYTES)
        self.reject(exact + b' ', "response_byte_limit")

    def test_container_depth_limit_exact_and_one_over(self):
        for depth in (s.MAX_DEPTH, s.MAX_DEPTH + 1):
            data = payload()[:-1] + b',"flags":' + b'[' * (depth - 1) + b']' * (depth - 1) + b'}'
            if depth == s.MAX_DEPTH:
                parse(data)
            else:
                self.reject(data, "json_depth_limit")

    def test_node_limit_exact_and_one_over(self):
        # Root, three keys, two string values, array = 7 nodes before nulls.
        for count in (s.MAX_NODES - 7, s.MAX_NODES - 6):
            data = b'{"cik":"123456","name":"Synthetic","flags":[' + b','.join([b'null'] * count) + b']}'
            if count == s.MAX_NODES - 7:
                parse(data)
            else:
                self.reject(data, "json_node_limit")

    def test_generic_string_limit_exact_and_one_over(self):
        parse(payload(description="x" * s.MAX_STRING_CHARS))
        self.reject(payload(description="x" * (s.MAX_STRING_CHARS + 1)), "json_string_limit")
        self.reject(payload()[:-1] + b',"' + b'x' * (s.MAX_STRING_CHARS + 1) + b'":null}',
                    "json_string_limit")

    def test_former_names_and_associations_limits_exact_and_one_over(self):
        names = [dict(name="Old " + str(i)) for i in range(s.MAX_FORMER_NAMES)]
        source = parse(payload(formerNames=names))
        self.assertEqual(len(s.to_identity_inventory(source, untrusted_evidence_key=EVIDENCE).inventory.names), 64)
        self.reject(payload(formerNames=names + [dict(name="Extra")]), "former_names_shape")
        tickers = ["S" + str(i) for i in range(s.MAX_ASSOCIATIONS)]
        parse(payload(tickers=tickers, exchanges=["NYSE"] * len(tickers)))
        self.reject(payload(tickers=tickers + ["EXTRA"], exchanges=["NYSE"] * 65), "association_shape")

    def test_hint_text_boundaries_and_no_exchange_normalization(self):
        source = parse(payload(tickers=["X" * 64], exchanges=["界" * 200]))
        self.assertEqual(source.ticker_exchange_hints[0].ticker, "X" * 64)
        for changes, code in ((dict(tickers=["X" * 65], exchanges=["NYSE"]), "ticker_hint"),
                              (dict(tickers=["X"], exchanges=["x" * 201]), "exchange_hint"),
                              (dict(tickers=["X"], exchanges=[" Nasdaq"]), "exchange_hint")):
            self.reject(payload(**changes), code)
        for exchange in ("Nasdaq", "NASDAQ", "XNAS", "Unmapped Exchange"):
            source = parse(payload(tickers=["X"], exchanges=[exchange]))
            self.assertEqual(source.ticker_exchange_hints[0].exchange_name, exchange)
            self.assertFalse(hasattr(source.ticker_exchange_hints[0], "mic"))

    def test_rejection_exposes_no_partial_success_or_source_values(self):
        sensitive = "synthetic-private-label"
        data = payload(name=sensitive, formerNames=[dict(name="Valid"), dict(name=" Invalid")])
        for _ in range(2):
            with self.assertRaises(s.SecIdentitySourceError) as caught:
                parse(data)
            self.assertEqual(caught.exception.__dict__, {"code": "former_name"})
            self.assertNotIn(sensitive, str(caught.exception))
            self.assertNotIsInstance(caught.exception, s.SecIdentitySource)

    def test_every_supported_unselected_field_is_only_inert_metadata(self):
        fields = dict(entityType="operating", sic="0000", sicDescription="Synthetic",
                      ownerOrg="Synthetic", insiderTransactionForOwnerExists=0,
                      insiderTransactionForIssuerExists=1, ein="000000000", description="",
                      website="", investorWebsite="", category="", fiscalYearEnd="1231",
                      stateOfIncorporation="DE", stateOfIncorporationDescription="DE",
                      addresses={"business": {"city": "Synthetic"}}, phone="", flags=[],
                      filings={"recent": {"form": ["10-K"], "isXBRL": [1]}, "files": []})
        self.assertEqual(set(fields), set(s._OTHER_FIELDS))
        source = parse(payload(**fields))
        self.assertEqual(source.entity.jurisdiction, None)
        self.assertEqual(source.entity.authority_ids, ())
        self.assertEqual(source.public_available_at, c.UnknownTimePoint())

    def test_bridge_rejects_bad_source_types_and_bypassed_evidence_key(self):
        for bad in (None, {}, "official_sec", c.KeyRef("sec_cik", CIK)):
            with self.assertRaises(s.SecIdentitySourceError) as caught:
                s.to_identity_inventory(bad, untrusted_evidence_key=EVIDENCE)
            self.assertEqual(caught.exception.code, "source_type")
        bad = c.KeyRef("artifact", "synthetic")
        object.__setattr__(bad, "id", "../untrusted")
        with self.assertRaises(s.SecIdentitySourceError) as caught:
            s.to_identity_inventory(parse(), untrusted_evidence_key=bad)
        self.assertEqual(caught.exception.code, "untrusted_evidence_key")


class ProvenanceTests(unittest.TestCase):
    def bound(self, raw=b'{"cik":"123456","name":"Review Issuer"}', artifact="A"):
        return s.to_identity_inventory(parse(raw), untrusted_evidence_key=c.KeyRef("artifact", artifact))

    def candidate(self, bound, query=None):
        return u.resolve_candidates(query or u.CikQuery(CIK), bound.inventory).candidates[0]

    def reject(self, function, code):
        for _ in range(2):
            with self.assertRaises(s.SecIdentitySourceError) as caught:
                function()
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(str(caught.exception), code)

    def test_cik_without_former_names_binds_issuer_artifact_and_original_bytes(self):
        for raw in (b'{"cik":"123456","name":"Review Issuer"}',
                    b'{"cik":"123456","name":"Review Issuer","formerNames":[]}'):
            bound = self.bound(raw)
            candidate = self.candidate(bound)
            binding = bound.source_binding_for(candidate)
            self.assertIsInstance(bound, s.SourceBoundIdentityInventory)
            self.assertEqual(binding.issuer_key, candidate.entity.key)
            self.assertEqual(binding.untrusted_artifact_key, c.KeyRef("artifact", "A"))
            self.assertIs(binding.original_bytes, raw)
            self.assertEqual(binding.response_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(binding.expected_cik, CIK)
            self.assertEqual(binding.inventory.names, ())
            self.assertEqual(candidate.evidence_keys, ())  # not the issuer provenance API

    def test_current_name_match_retains_binding_without_alias_workaround(self):
        bound = self.bound()
        candidate = self.candidate(bound, u.NameQuery("Review Issuer"))
        self.assertEqual(candidate.match_basis, "name_exact")
        self.assertEqual(candidate.matched_names, ())
        self.assertEqual(candidate.evidence_keys, ())
        self.assertEqual(bound.source_binding_for(candidate), bound)
        contains = self.candidate(bound, u.NameQuery("Review", "contains"))
        self.assertEqual(bound.source_binding_for(contains), bound)

    def test_former_name_match_retains_same_issuer_binding(self):
        bound = self.bound(payload(formerNames=[dict(name="Earlier", to="2000-01-01")]))
        former = self.candidate(bound, u.NameQuery("Earlier"))
        current = self.candidate(bound, u.NameQuery("Synthetic Registrant"))
        self.assertEqual(former.matched_names[0].evidence_key, bound.untrusted_artifact_key)
        self.assertEqual(bound.source_binding_for(former), bound.source_binding_for(current))
        self.assertEqual(bound.source_binding_for(self.candidate(bound)), bound)
        self.assertIsNone(former.matched_names[0].effective)

    def test_byte_distinctions_survive_identical_normalized_inventory(self):
        raw = b'{"cik":"123456","name":"Review Issuer"}'
        a, b = self.bound(raw), self.bound(raw + b" ")
        self.assertEqual(a.inventory, b.inventory)
        self.assertNotEqual(a, b)
        self.assertNotEqual(a.response_sha256, b.response_sha256)
        self.assertNotEqual(a.original_bytes, b.original_bytes)
        self.assertEqual(a.untrusted_artifact_key, b.untrusted_artifact_key)
        self.assertNotEqual(a.source_binding_for(self.candidate(a)), b.source_binding_for(self.candidate(b)))

    def test_distinct_artifact_keys_do_not_collapse_even_with_same_bytes(self):
        a, b = self.bound(artifact="A"), self.bound(artifact="B")
        self.assertEqual(a.inventory, b.inventory)
        self.assertEqual(a.response_sha256, b.response_sha256)
        self.assertNotEqual(a, b)
        candidate = self.candidate(a)
        # Same entity can be supported by both; lookup is scoped to this source,
        # not a claim of exclusive original custody for the bare UCR candidate.
        self.assertEqual(a.source_binding_for(candidate).untrusted_artifact_key.id, "A")
        self.assertEqual(b.source_binding_for(candidate).untrusted_artifact_key.id, "B")

    def test_lookup_rejects_unrelated_issuer_or_contradictory_entity_metadata(self):
        bound = self.bound()
        other_entity = c.EntityRef(c.KeyRef("sec_cik", "0000654321"), "Other", None, "0000654321", ())
        other = u.resolve_candidates(u.CikQuery("0000654321"), u.IdentityInventory((other_entity,))).candidates[0]
        self.reject(lambda: bound.source_binding_for(other), "candidate_issuer_mismatch")
        candidate = replace(self.candidate(bound), entity=replace(bound.inventory.entities[0], legal_name="Forged"))
        self.reject(lambda: bound.source_binding_for(candidate), "candidate_issuer_mismatch")
        for invalid in (None, {}, bound.issuer_key, c.IdentityResolution("unresolved", (), (), "no_match")):
            self.reject(lambda: bound.source_binding_for(invalid), "candidate_type")

    def test_lookup_rejects_unrelated_alias_evidence_and_invalid_candidate_shape(self):
        raw = payload(formerNames=[dict(name="Earlier")])
        a, b = self.bound(raw, "A"), self.bound(raw, "B")
        other = self.candidate(b, u.NameQuery("Earlier"))
        self.reject(lambda: a.source_binding_for(other), "candidate_source_mismatch")
        bad = replace(self.candidate(a))
        object.__setattr__(bad, "matched_names", [])
        self.reject(lambda: a.source_binding_for(bad), "candidate_source_mismatch")
        bad = replace(self.candidate(a))
        object.__setattr__(bad, "match_basis", "exact_authority_identifier")
        self.reject(lambda: a.source_binding_for(bad), "candidate_source_mismatch")

    def test_envelope_validates_digest_expected_cik_issuer_and_inventory(self):
        bound = self.bound()
        class TextSubclass(str):
            pass
        bad_issuer = c.KeyRef("sec_cik", CIK)
        object.__setattr__(bad_issuer, "id", TextSubclass(CIK))
        bad_inventory = replace(bound.inventory)
        object.__setattr__(bad_inventory, "entities", list(bad_inventory.entities))
        for changes, code in ((dict(response_sha256="0" * 64), "binding_digest_mismatch"),
                              (dict(response_sha256=True), "binding_digest_mismatch"),
                              (dict(original_bytes=bound.original_bytes + b" "), "binding_digest_mismatch"),
                              (dict(expected_cik="0000654321"), "cik_mismatch"),
                              (dict(expected_cik="123456"), "expected_cik"),
                              (dict(issuer_key=c.KeyRef("sec_cik", "0000654321")), "binding_issuer_mismatch"),
                              (dict(issuer_key=CIK), "binding_issuer_mismatch"),
                              (dict(issuer_key=bad_issuer), "binding_issuer_mismatch"),
                              (dict(inventory={}), "binding_inventory_type"),
                              (dict(inventory=bad_inventory), "binding_inventory_mismatch"),
                              (dict(inventory=u.IdentityInventory(())), "binding_inventory_mismatch"),
                              (dict(untrusted_artifact_key=c.KeyRef("authority_record", "SEC")),
                               "untrusted_evidence_key")):
            with self.subTest(changes=changes):
                self.reject(lambda: replace(bound, **changes), code)

    def test_parsed_carrier_byte_and_digest_changes_cannot_silently_rebind(self):
        source = parse()
        for changes, code in ((dict(original_bytes=source.original_bytes + b" "), "source_conflict"),
                              (dict(response_sha256="0" * 64), "source_conflict"),
                              (dict(expected_cik="0000654321"), "cik_mismatch"),
                              (dict(entity=replace(source.entity, legal_name="Forged")), "source_conflict")):
            self.reject(lambda: s.to_identity_inventory(replace(source, **changes),
                                                       untrusted_evidence_key=EVIDENCE), code)

    def test_binding_is_immutable_detached_and_lookup_revalidates_bypassed_fields(self):
        evidence = c.KeyRef("artifact", "A")
        bound = s.to_identity_inventory(parse(), untrusted_evidence_key=evidence)
        object.__setattr__(evidence, "id", "B")
        self.assertEqual(bound.untrusted_artifact_key.id, "A")
        for name, value in (("response_sha256", "0" * 64), ("issuer_key", EVIDENCE),
                            ("original_bytes", b"{}"), ("untrusted_artifact_key", EVIDENCE)):
            with self.assertRaises(FrozenInstanceError):
                setattr(bound, name, value)
        candidate = self.candidate(bound)
        for name, value, code in (("response_sha256", "0" * 64, "binding_digest_mismatch"),
                                  ("original_bytes", bound.original_bytes + b" ", "binding_digest_mismatch"),
                                  ("issuer_key", EVIDENCE, "binding_issuer_mismatch"),
                                  ("inventory", u.IdentityInventory(()), "binding_inventory_mismatch")):
            bad = replace(bound)
            object.__setattr__(bad, name, value)
            self.reject(lambda: bad.source_binding_for(candidate), code)

    def test_forged_looking_artifact_labels_remain_unverified(self):
        bound = self.bound(artifact="official_sec")
        candidate = self.candidate(bound)
        binding = bound.source_binding_for(candidate)
        self.assertEqual(binding.verification_status, "unverified")
        self.assertEqual(candidate.verification_status, "unverified")
        self.assertEqual(candidate.entity.authority_ids, ())
        self.assertEqual((binding.inventory.securities, binding.inventory.listings), ((), ()))
        self.assertNotIsInstance(binding, c.IdentityResolution)
        self.assertEqual(binding.source_identity, s.SOURCE_IDENTITY)
        self.assertEqual(binding.parser_revision, s.PARSER_REVISION)
        for changes in (dict(source_identity="official_sec"), dict(parser_revision="forged"),
                        dict(trusted=True), dict(verification_status="verified")):
            with self.assertRaises(TypeError):
                replace(bound, **changes)

    def test_default_bridge_requires_explicit_inventory_extraction(self):
        bound = self.bound()
        self.assertIs(type(bound), s.SourceBoundIdentityInventory)
        self.assertIs(type(bound.inventory), u.IdentityInventory)
        self.assertEqual(replace(bound), bound)
        with self.assertRaises(u.IdentityInputError):
            u.resolve_candidates(u.CikQuery(CIK), bound)
        class SubBound(s.SourceBoundIdentityInventory):
            pass
        self.reject(lambda: SubBound(bound.inventory, bound.issuer_key, bound.untrusted_artifact_key,
                                     bound.original_bytes, bound.response_sha256, bound.expected_cik), "binding_type")


class IsolationAndMutationTests(unittest.TestCase):
    def test_import_surface_only_stdlib_and_two_pure_contract_modules(self):
        tree = ast.parse((BACKEND / "app" / "sec_identity_source.py").read_text(encoding="utf-8"))
        imports, app_names = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
                if node.module == "app":
                    app_names.update(item.name for item in node.names)
        self.assertEqual(imports, {"dataclasses", "hashlib", "json", "re", "unicodedata", "typing", "app"})
        self.assertEqual(app_names, {"research_contracts", "universal_identity"})

    def test_fresh_process_import_parse_bridge_and_resolve_deny_effects(self):
        script = r'''
import sys, importlib.abc, os, socket, subprocess, builtins, pathlib, io
sys.path.insert(0, sys.argv[1])
blocked = ("app.config", "app.database", "app.models", "app.sec_client", "app.main",
           "dotenv", "sqlalchemy", "httpx", "requests", "torch", "transformers",
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
from app import sec_identity_source as s, research_contracts as c, universal_identity as u
builtins.open = io.open = pathlib.Path.open = os.open = deny
source = s.parse_sec_submissions(b'{"cik":"9999999999","name":"Absent Synthetic","formerNames":[{"name":"Old"}]}',
                                  expected_cik="9999999999")
bound = s.to_identity_inventory(source, untrusted_evidence_key=c.KeyRef("artifact", "untrusted"))
inv = bound.inventory
result = u.resolve_candidates(u.CikQuery("9999999999"), inv)
assert result.status == "unique_candidate" and result.verification_status == "unverified"
assert inv.entities[0].authority_ids == () and inv.securities == () and inv.listings == ()
for query in (u.CikQuery("9999999999"), u.NameQuery("Absent Synthetic"), u.NameQuery("Old")):
    candidate = u.resolve_candidates(query, inv).candidates[0]
    binding = bound.source_binding_for(candidate)
    assert binding.untrusted_artifact_key == c.KeyRef("artifact", "untrusted")
    assert binding.original_bytes == source.original_bytes and binding.verification_status == "unverified"
assert not any(name in sys.modules for name in blocked)
print("isolated import, parse, bridge and resolution passed")
'''
        run = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(BACKEND)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("isolated import, parse, bridge and resolution passed", run.stdout)

    def test_focused_negative_probes_kill_in_memory_mutants(self):
        source = (BACKEND / "app" / "sec_identity_source.py").read_text(encoding="utf-8")

        def rejection(data, code):
            def probe(module):
                with self.assertRaises(module.SecIdentitySourceError) as caught:
                    parse(data, module)
                self.assertEqual(caught.exception.code, code)
            return probe

        def unverified(module):
            self.assertEqual(parse(module=module).verification_status, "unverified")

        def digest(module):
            data = payload()
            self.assertEqual(parse(data, module).response_sha256, hashlib.sha256(data).hexdigest())

        def unknown_effective(module):
            inv = module.to_identity_inventory(parse(payload(formerNames=[dict(name="Old")]), module),
                                               untrusted_evidence_key=EVIDENCE).inventory
            self.assertIsNone(inv.names[0].effective)
            self.assertEqual((inv.entities[0].authority_ids, inv.securities, inv.listings), ((), (), ()))

        def revalidate(module):
            bad = replace(parse(module=module), response_sha256="0" * 64)
            with self.assertRaises(module.SecIdentitySourceError):
                module.to_identity_inventory(bad, untrusted_evidence_key=EVIDENCE)

        def issuer_source_retained(module):
            raw = b'{"cik":"123456","name":"Review Issuer"}'
            bound = module.to_identity_inventory(parse(raw, module), untrusted_evidence_key=EVIDENCE)
            self.assertIsInstance(bound, module.SourceBoundIdentityInventory,
                                  "issuer source binding lost for CIK without formerNames")
            candidate = u.resolve_candidates(u.CikQuery(CIK), bound.inventory).candidates[0]
            binding = bound.source_binding_for(candidate)
            self.assertEqual(binding.untrusted_artifact_key, EVIDENCE)
            self.assertEqual(binding.response_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(binding.original_bytes, raw)

        def unrelated_issuer_rejects(module):
            bound = module.to_identity_inventory(parse(module=module), untrusted_evidence_key=EVIDENCE)
            other = c.EntityRef(c.KeyRef("sec_cik", "0000654321"), "Other", None, "0000654321", ())
            candidate = u.resolve_candidates(u.CikQuery(other.cik), u.IdentityInventory((other,))).candidates[0]
            with self.assertRaises(module.SecIdentitySourceError):
                bound.source_binding_for(candidate)

        def binding_digest_rejects(module):
            bound = module.to_identity_inventory(parse(module=module), untrusted_evidence_key=EVIDENCE)
            with self.assertRaises(module.SecIdentitySourceError):
                replace(bound, response_sha256="0" * 64)

        mutants = (
            ("cik_mismatch", 'cik == expected_cik, "cik_mismatch"', 'True, "cik_mismatch"',
             rejection(payload(cik="654321"), "cik_mismatch")),
            ("numeric_cik_coercion", 'c.canonical_sec_cik(root["cik"])', 'c.canonical_sec_cik(str(root["cik"]))',
             rejection(payload(cik=123456), "response_cik")),
            ("duplicate_key", 'key not in result, "json_duplicate_key"', 'True, "json_duplicate_key"',
             rejection(b'{"cik":"123456","name":"A","name":"B"}', "json_duplicate_key")),
            ("association_truncation", 'len(tickers) == len(exchanges)', 'True',
             rejection(payload(tickers=["SYN"], exchanges=[]), "association_shape")),
            ("origin_claim", 'root.keys() <= _IDENTITY_FIELDS | _OTHER_FIELDS', 'True',
             rejection(payload(origin="official_sec"), "unsupported_root_field")),
            ("date_validation", 'c.DateTimePoint(value)', 'c.UnknownTimePoint()',
             rejection(payload(formerNames=[dict(name="Old", to="2000-02-30")]), "former_name_date")),
            ("byte_limit", 'len(original_bytes) <= MAX_RESPONSE_BYTES', 'True',
             rejection(payload() + b' ' * s.MAX_RESPONSE_BYTES, "response_byte_limit")),
            ("depth_limit", 'depth <= MAX_DEPTH', 'True',
             rejection(payload()[:-1] + b',"flags":' + b'[' * 16 + b']' * 16 + b'}', "json_depth_limit")),
            ("authority_promotion", 'verification_status: ClassVar[str] = "unverified"\n    source_revision_key',
             'verification_status: ClassVar[str] = "verified"\n    source_revision_key', unverified),
            ("digest_substitution", 'hashlib.sha256(original_bytes).hexdigest()', '"0" * 64', digest),
            ("inferred_effective", 'item.name, evidence, None)',
             'item.name, evidence, c.DateInterval("2000-01-01", None))', unknown_effective),
            ("bridge_conflict", 'source == clean, "source_conflict"', 'True, "source_conflict"', revalidate),
            ("issuer_source_binding_removed",
             'return SourceBoundIdentityInventory(inventory, clean.entity.key, evidence,\n'
             '                                        clean.original_bytes, clean.response_sha256, clean.expected_cik)',
             'return inventory', issuer_source_retained),
            ("unrelated_issuer_bound", 'candidate.entity == clean.inventory.entities[0]',
             'True', unrelated_issuer_rejects),
            ("binding_digest_ignored", 'self.response_sha256 == source.response_sha256',
             'True', binding_digest_rejects),
        )
        for name, before, after, probe in mutants:
            with self.subTest(mutant=name):
                self.assertEqual(source.count(before), 1)
                probe(s)  # probe passes against the actual implementation first
                module = types.ModuleType("sec_identity_mutant_" + name)
                sys.modules[module.__name__] = module
                try:
                    exec(compile(source.replace(before, after), "<in-memory-mutant>", "exec"), module.__dict__)
                    with self.assertRaises(AssertionError) as killed:
                        probe(module)
                    if name == "issuer_source_binding_removed":
                        self.assertIn("issuer source binding lost for CIK without formerNames", str(killed.exception))
                finally:
                    del sys.modules[module.__name__]


if __name__ == "__main__":
    unittest.main(verbosity=2)
