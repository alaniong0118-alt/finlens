"""Synthetic offline UCR-01A acceptance and in-memory mutation controls.

Run from repository root:
backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_universal_identity.py
No fixture is a claim about a real issuer, source, exchange or authority.
"""

import ast
from dataclasses import FrozenInstanceError, fields, replace
import itertools
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import research_contracts as c
from app import universal_identity as u


def key(namespace, identifier="fixture"):
    return c.KeyRef(namespace, identifier)


def interval(start="2020-01-01", end=None):
    return c.DateInterval(start, end)


def authority(identifier="ISSUER", scheme="authority_id", source="fixture", effective=None,
              evidence="authority"):
    return c.AuthorityIdentifier(scheme, source, identifier, key("authority_record", evidence), effective)


def entity(identifier="0000123456", name="Synthetic Industries", authorities=()):
    sec = identifier.isascii() and identifier.isdigit()
    return c.EntityRef(key("sec_cik" if sec else "external_entity", identifier), name,
                       "US" if sec else None, identifier if sec else None, authorities)


def security(issuer=None, identifier="security", share_class="Common", authorities=()):
    return c.SecurityRef(key("security", identifier), (issuer or entity()).key, share_class, authorities)


def alias(symbol="SYN", effective=interval(), evidence="alias", provider="fixture", product="symbols"):
    return c.SymbolAlias(provider, product, symbol, effective, key("authority_record", evidence))


def listing(sec=None, identifier="listing", mic="XNAS", effective=interval(), aliases=None):
    return c.ListingRef(key("listing", identifier), (sec or security()).key, mic, "USD",
                        key("calendar"), "v1", effective, (alias(),) if aliases is None else aliases)


def inventory():
    return u.IdentityInventory((entity(),), (security(),), (listing(),))


def query(**changes):
    args = dict(symbol="SYN", mic="XNAS", as_of="2026-10-29", provider="fixture", product="symbols")
    args.update(changes)
    return u.SymbolQuery(**args)


def two_listings(mic="XNAS", second_issuer=False, second_class=False):
    one = entity()
    two = entity("external-successor") if second_issuer else one
    a = security(one, "s1", "A" if second_class else "Common")
    b = security(two, "s2", "B" if second_class else "Common")
    la, lb = listing(a, "l1"), listing(b, "l2", mic)
    return u.IdentityInventory((one, two) if second_issuer else (one,), (a, b), (la, lb))


class CandidateTests(unittest.TestCase):
    def reject(self, function, *args, **kwargs):
        with self.assertRaises((u.IdentityInputError, c.ContractError)):
            function(*args, **kwargs)

    def test_sec_issuer_without_database_ids(self):
        result = u.resolve_candidates(u.CikQuery("0000123456"), u.IdentityInventory((entity(),)))
        self.assertEqual(result.status, "unique_candidate")
        self.assertEqual(result.candidates[0].entity, entity())
        self.assertIsNone(result.candidates[0].security)
        self.assertEqual(result.candidates[0].match_basis, "canonical_cik")
        self.assertEqual(result.candidates[0].evidence_keys, ())
        self.assertFalse(any("company_id" == field.name for field in fields(result.candidates[0])))

    def test_non_sec_external_without_cik(self):
        ext = entity("external", authorities=(authority(),))
        result = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", "ISSUER"),
                                      u.IdentityInventory((ext,)))
        self.assertEqual(result.status, "unique_candidate")
        self.assertEqual(result.candidates[0].entity.key.namespace, "external_entity")
        self.assertIsNone(result.candidates[0].entity.cik)
        self.assertEqual(result.candidates[0].evidence_keys, (key("authority_record", "authority"),))

    def test_two_listings_same_ticker_never_collapse_even_one_issuer(self):
        for inv in (two_listings(), two_listings(second_issuer=True)):
            with self.subTest(issuers=len(inv.entities)):
                result = u.resolve_candidates(query(), inv)
                self.assertEqual(result.status, "ambiguous")
                self.assertEqual(len(result.candidates), 2)
                self.assertIn("competing_listings", result.reasons)

    def test_two_listings_of_one_security_remain_separate(self):
        inv = replace(inventory(), listings=(listing(identifier="l1"), listing(identifier="l2")))
        result = u.resolve_candidates(query(), inv)
        self.assertEqual((result.status, len(result.candidates)), ("ambiguous", 2))
        self.assertEqual(len({item.security.key for item in result.candidates}), 1)

    def test_two_share_classes_remain_separate(self):
        result = u.resolve_candidates(query(), two_listings(second_class=True))
        self.assertEqual({item.security.share_class for item in result.candidates}, {"A", "B"})
        self.assertEqual(len({item.entity.key for item in result.candidates}), 1)
        self.assertEqual(result.status, "ambiguous")

    def test_same_symbol_on_different_exchanges(self):
        inv = two_listings(mic="XNYS", second_issuer=True)
        for mic, listing_id in (("XNAS", "l1"), ("XNYS", "l2")):
            with self.subTest(mic=mic):
                result = u.resolve_candidates(query(mic=mic), inv)
                self.assertEqual(result.status, "unique_candidate")
                self.assertEqual(result.candidates[0].listing.key.id, listing_id)

    def test_symbol_provider_product_and_case_are_exact(self):
        for changes in (dict(symbol="syn"), dict(provider="other"), dict(product="other"), dict(mic="XXXX")):
            with self.subTest(changes=changes):
                result = u.resolve_candidates(query(**changes), inventory())
                self.assertEqual((result.status, result.candidates), ("unresolved", ()))
                self.assertEqual(result.reasons, ("no_candidates",))

    def test_ticker_reuse_retains_inactive_competitor_and_evidence(self):
        inv = two_listings(second_issuer=True)
        first = replace(inv.listings[0], effective=interval("2020-01-01", "2025-01-01"),
                        aliases=(alias(effective=interval("2020-01-01", "2025-01-01"), evidence="old"),))
        second = replace(inv.listings[1], effective=interval("2025-01-01"),
                         aliases=(alias(effective=interval("2025-01-01"), evidence="new"),))
        inv = replace(inv, listings=(first, second))
        for day, active in (("2024-12-31", "l1"), ("2025-01-01", "l2")):
            with self.subTest(day=day):
                result = u.resolve_candidates(query(as_of=day), inv)
                self.assertEqual(result.status, "unique_candidate")
                self.assertEqual(len(result.candidates), 2)
                self.assertEqual(len(result.possible_candidates), 1)
                eligible = [item for item in result.candidates if item.temporal_state == "in_effect"]
                self.assertEqual([item.listing.key.id for item in eligible], [active])
                self.assertEqual({item.evidence_keys[0].id for item in result.candidates}, {"old", "new"})

    def test_adjacent_aliases_and_gap_endpoints(self):
        aliases = (alias(effective=interval("2020-01-01", "2025-01-01"), evidence="one"),
                   alias(effective=interval("2025-01-01", "2026-01-01"), evidence="two"))
        inv = replace(inventory(), listings=(listing(aliases=aliases),))
        result = u.resolve_candidates(query(as_of="2025-01-01"), inv)
        self.assertEqual(result.status, "unique_candidate")
        self.assertEqual(result.candidates[0].matched_aliases, aliases)
        result = u.resolve_candidates(query(as_of="2026-01-01"), inv)
        self.assertEqual((result.status, result.reasons), ("unresolved", ("outside_effective_dates",)))
        self.assertEqual(len(result.candidates[0].evidence_keys), 2)
        gap = replace(inv, listings=(listing(aliases=(aliases[0], replace(aliases[1],
                                         effective=interval("2025-02-01")))),))
        self.assertEqual(u.resolve_candidates(query(as_of="2025-01-15"), gap).status, "unresolved")

    def test_overlapping_aliases_within_listing_reject(self):
        self.reject(listing, aliases=(alias(), alias(effective=interval("2024-01-01"), evidence="two")))
        self.reject(listing, aliases=(alias(), alias(effective=None, evidence="unknown")))
        self.reject(listing, aliases=(alias(), alias()))

    def test_overlapping_aliases_across_listings_are_ambiguous(self):
        result = u.resolve_candidates(query(), two_listings(second_issuer=True))
        self.assertEqual([item.temporal_state for item in result.candidates], ["in_effect", "in_effect"])
        self.assertEqual(result.status, "ambiguous")

    def test_unknown_alias_or_listing_cannot_establish_dated_unique(self):
        for item in (listing(aliases=(alias(effective=None),)), listing(effective=None)):
            with self.subTest(listing=item):
                result = u.resolve_candidates(query(), replace(inventory(), listings=(item,)))
                self.assertEqual(result.status, "unresolved")
                self.assertEqual(result.candidates[0].temporal_state, "unknown_effective")
                self.assertIn("unknown_effective_dates", result.reasons)

    def test_unknown_competitor_blocks_known_unique_candidate(self):
        inv = two_listings()
        inv = replace(inv, listings=(inv.listings[0], replace(inv.listings[1], effective=None)))
        result = u.resolve_candidates(query(), inv)
        self.assertEqual(result.status, "ambiguous")
        self.assertIn("unknown_effective_dates", result.reasons)
        self.assertEqual(len(result.possible_candidates), 2)

    def test_multiple_unknown_candidates_are_ambiguous_and_all_inactive_abstain(self):
        inv = two_listings()
        unknown = replace(inv, listings=tuple(replace(item, effective=None) for item in inv.listings))
        result = u.resolve_candidates(query(), unknown)
        self.assertEqual((result.status, len(result.possible_candidates)), ("ambiguous", 2))
        inactive = replace(inv, listings=tuple(replace(item,
                           aliases=(alias(effective=interval("2021-01-01", "2022-01-01")),))
                                               for item in inv.listings))
        result = u.resolve_candidates(query(), inactive)
        self.assertEqual((result.status, result.possible_candidates), ("unresolved", ()))
        self.assertEqual(len(result.candidates), 2)

    def test_known_inactive_listing_excludes_unknown_alias(self):
        item = listing(effective=interval("2020-01-01", "2021-01-01"), aliases=(alias(effective=None),))
        result = u.resolve_candidates(query(), replace(inventory(), listings=(item,)))
        self.assertEqual(result.candidates[0].temporal_state, "outside_effective")
        self.assertNotIn("unknown_effective_dates", result.reasons)

    def test_cik_normalization_is_explicit(self):
        self.assertEqual(u.CikQuery.from_unpadded("123456"), u.CikQuery("0000123456"))
        for value in ("123456", "0", "0000000000", "１２３４５６７８９０", 123456, True,
                      " 0000123456", "+000123456", "12345678901", None):
            with self.subTest(value=value):
                self.reject(u.CikQuery, value)
        for value in ("0", 1, " 1", "１", "1.0"):
            self.reject(u.CikQuery.from_unpadded, value)
        self.assertEqual(u.resolve_candidates(u.CikQuery("0000999999"), inventory()).candidates, ())

    def test_authority_tuple_is_exact_and_cross_namespace_claims_remain(self):
        first = entity(authorities=(authority(),))
        second = entity("external", authorities=(authority(source="other"),))
        inv = u.IdentityInventory((first, second))
        result = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", "ISSUER"), inv)
        self.assertEqual([item.entity for item in result.candidates], [first])
        for args in (("authority_id", "fixture", "issuer"), ("authority_id", "other", "absent"),
                     ("lei", "fixture", "A" * 20)):
            self.assertEqual(u.resolve_candidates(u.AuthorityQuery(*args), inv).candidates, ())
        claimed = entity("external", authorities=(authority(),))
        result = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", "ISSUER"),
                                      u.IdentityInventory((first, claimed)))
        self.assertEqual(result.status, "ambiguous")
        self.assertIn("competing_authority_claims", result.reasons)
        self.assertEqual({item.entity.key.namespace for item in result.candidates}, {"sec_cik", "external_entity"})

    def test_authority_schemes_and_namespace_rejections(self):
        for args in (("external_entity", "sec", "0000123456"), ("sec_cik", "not-sec", "0000123456"),
                     ("sec_cik", "sec", "123456"), ("lei", "fixture", "invalid"),
                     ("authority_id", "fixture", key("external_entity"))):
            with self.subTest(args=args):
                self.reject(u.AuthorityQuery, *args)
        self.reject(u.CikQuery, key("external_entity", "0000123456"))
        self.reject(u.NameAlias, key("security"), "Name", key("artifact"), None)
        self.reject(u.NameAlias, entity().key, "Name", key("source_revision"), None)

    def test_same_authority_identifier_text_different_scheme_never_substitutes(self):
        same_text = "A" * 20
        ent = entity(authorities=(authority(same_text, "lei", "fixture"),))
        sec = security(ent, authorities=(authority(same_text, "authority_id", "fixture"),))
        inv = u.IdentityInventory((ent,), (sec,))
        issuer = u.resolve_candidates(u.AuthorityQuery("lei", "fixture", same_text), inv)
        share = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", same_text), inv)
        self.assertEqual(issuer.status, "unique_candidate")
        self.assertIsNone(issuer.candidates[0].security)
        self.assertEqual(share.candidates[0].security, sec)

    def test_authority_sec_and_lei_positive_and_no_inferred_authority(self):
        for identifier in (authority("0000123456", "sec_cik", "sec"),
                           authority("A" * 20, "lei", "lei-registry")):
            with self.subTest(scheme=identifier.scheme):
                inv = u.IdentityInventory((entity(authorities=(identifier,)),))
                result = u.resolve_candidates(u.AuthorityQuery(identifier.scheme, identifier.authority,
                                                                identifier.identifier), inv)
                self.assertEqual(result.status, "unique_candidate")
                self.assertEqual(result.candidates[0].matched_authorities, (identifier,))
        result = u.resolve_candidates(u.AuthorityQuery("sec_cik", "sec", "0000123456"), inventory())
        self.assertEqual(result.candidates, ())

    def test_dated_authority_requires_known_valid_interval(self):
        for dates, state, status in ((None, "unknown_effective", "unresolved"),
                                     (interval(), "in_effect", "unique_candidate"),
                                     (interval("2020-01-01", "2021-01-01"), "outside_effective", "unresolved")):
            with self.subTest(dates=dates):
                inv = u.IdentityInventory((entity(authorities=(authority(effective=dates),)),))
                result = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", "ISSUER",
                                                               "2026-10-29"), inv)
                self.assertEqual((result.status, result.candidates[0].temporal_state), (status, state))

    def test_security_authority_preserves_security_and_issuer(self):
        sec = security(authorities=(authority("SECURITY"),))
        inv = u.IdentityInventory((entity(),), (sec,))
        result = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", "SECURITY"), inv)
        self.assertEqual(result.candidates[0].security, sec)
        self.assertEqual(result.candidates[0].entity.key, sec.issuer_key)
        self.assertIsNone(result.candidates[0].listing)

    def test_same_authority_on_issuer_and_security_is_competing_claim(self):
        ent = entity(authorities=(authority(),))
        sec = security(ent, authorities=(authority(),))
        result = u.resolve_candidates(u.AuthorityQuery("authority_id", "fixture", "ISSUER"),
                                      u.IdentityInventory((ent,), (sec,)))
        self.assertEqual((result.status, len(result.candidates)), ("ambiguous", 2))

    def test_company_name_ambiguity_and_discovery_folding(self):
        one = entity(name="SYNTHÉTIC   Industries")
        two = entity("external", name="Synthe\u0301tic Industries")
        result = u.resolve_candidates(u.NameQuery("synthétic industries"), u.IdentityInventory((one, two)))
        self.assertEqual(result.status, "ambiguous")
        self.assertIn("name_search_only", result.reasons)
        self.assertEqual({item.entity.legal_name for item in result.candidates},
                         {one.legal_name, two.legal_name})
        self.assertEqual(u.resolve_candidates(u.NameQuery("Industries", "contains"),
                                              u.IdentityInventory((one, two))).status, "ambiguous")
        self.assertEqual(u.resolve_candidates(u.NameQuery("Synthetic"), inventory()).status, "unresolved")

    def test_rename_alias_preserves_evidence_and_effective_dates(self):
        old = u.NameAlias(entity().key, "Former Synthetic Name", key("artifact", "old-name"),
                          interval("2001-01-01", "2020-01-01"))
        inv = replace(inventory(), names=(old,))
        result = u.resolve_candidates(u.NameQuery("former synthetic name"), inv)
        self.assertEqual(result.status, "unique_candidate")
        self.assertEqual(result.candidates[0].matched_names, (old,))
        self.assertEqual(result.candidates[0].evidence_keys, (old.evidence_key,))
        self.assertIn("name_search_only", result.reasons)

    def test_predecessor_successor_remain_separate(self):
        predecessor = entity("0000000001", "Same Synthetic Name")
        successor = entity("0000000002", "Same Synthetic Name")
        inv = u.IdentityInventory((successor, predecessor))
        result = u.resolve_candidates(u.NameQuery("Same Synthetic Name"), inv)
        self.assertEqual((result.status, len(result.candidates)), ("ambiguous", 2))
        for ent in (predecessor, successor):
            result = u.resolve_candidates(u.CikQuery(ent.cik), inv)
            self.assertEqual([item.entity for item in result.candidates], [ent])

    def test_missing_or_conflicting_links_reject_entire_inventory(self):
        self.reject(u.IdentityInventory, (entity(),), (security(entity("other")),))
        self.reject(u.IdentityInventory, (entity(),), (security(),),
                    (listing(security(identifier="absent")),))
        self.reject(u.IdentityInventory, (entity(),), (security(),),
                    (listing(effective=interval("2024-01-01")),))
        self.reject(u.IdentityInventory, (entity(),), (security(),),
                    (listing(effective=interval("2020-01-01", "2025-01-01")),))
        self.reject(u.IdentityInventory, (entity(),), names=(
                    u.NameAlias(entity("absent").key, "Old", key("artifact"), None),))

    def test_namespace_substitutions_and_contradictory_cik_reject(self):
        bad = replace(security())
        object.__setattr__(bad, "issuer_key", key("security", "0000123456"))
        self.reject(u.IdentityInventory, (entity(),), (bad,))
        bad_listing = replace(listing())
        object.__setattr__(bad_listing, "security_key", entity().key)
        self.reject(u.IdentityInventory, (entity(),), (security(),), (bad_listing,))
        self.reject(entity, authorities=(authority("0000000001", "sec_cik", "sec"),))
        self.reject(entity, "external", authorities=(authority("0000123456", "sec_cik", "sec"),))
        self.reject(c.EntityRef, key("sec_cik", "0000123456"), "Name", None, "0000000001", ())

    def test_identical_and_conflicting_duplicate_records_reject(self):
        inv = inventory()
        for name in ("entities", "securities", "listings"):
            original = getattr(inv, name)[0]
            for duplicate in (original, replace(original, **{
                    "entities": {"legal_name": "Different"},
                    "securities": {"share_class": "Different"},
                    "listings": {"currency": "EUR"}}[name])):
                with self.subTest(name=name, duplicate=duplicate):
                    self.reject(replace, inv, **{name: (original, duplicate)})
        name = u.NameAlias(entity().key, "Old Name", key("artifact", "one"), interval())
        self.reject(replace, inv, names=(name, replace(name, evidence_key=key("artifact", "two"))))

    def test_same_namespace_opaque_keys_are_never_assumed_equivalent(self):
        one, two = entity("external-one"), entity("external-two")
        result = u.resolve_candidates(u.NameQuery(one.legal_name), u.IdentityInventory((one, two)))
        self.assertEqual((result.status, len(result.candidates)), ("ambiguous", 2))
        # A structurally consistent substituted chain cannot prove real ownership.
        inv = u.IdentityInventory((two,), (security(two),), (listing(),))
        self.assertEqual(u.resolve_candidates(query(), inv).verification_status, "unverified")

    def test_all_chain_evidence_survives_matching(self):
        ent = entity(authorities=(authority("ENTITY", evidence="entity"),))
        sec = security(ent, authorities=(authority("SECURITY", evidence="security"),))
        aliases = (alias(evidence="match"), alias("OTHER", evidence="other"))
        result = u.resolve_candidates(query(), u.IdentityInventory((ent,), (sec,),
                                      (listing(sec, aliases=aliases),)))
        self.assertEqual({item.id for item in result.candidates[0].evidence_keys},
                         {"entity", "security", "match", "other"})
        self.assertEqual(result.candidates[0].listing.aliases,
                         tuple(sorted(aliases, key=lambda item: item.symbol)))

    def test_inventory_and_nested_reordering_produces_equal_results(self):
        inv = two_listings(second_issuer=True)
        names = tuple(u.NameAlias(ent.key, "Old Name", key("artifact", str(i)), interval())
                      for i, ent in enumerate(inv.entities))
        authorities = (authority("B", evidence="b"), authority("A", evidence="a"))
        inv = replace(inv, entities=tuple(replace(ent, authority_ids=authorities) for ent in inv.entities),
                      names=names, listings=tuple(replace(item, aliases=(alias("OTHER"), alias()))
                                                  for item in inv.listings))
        queries = (query(), u.NameQuery("Old Name"), u.AuthorityQuery("authority_id", "fixture", "A"))
        expected = [u.resolve_candidates(item, inv) for item in queries]
        for entities in itertools.permutations(inv.entities):
            reordered = u.IdentityInventory(tuple(replace(ent, authority_ids=ent.authority_ids[::-1])
                                                   for ent in entities), inv.securities[::-1],
                            tuple(replace(item, aliases=item.aliases[::-1]) for item in inv.listings[::-1]),
                            inv.names[::-1])
            self.assertEqual(expected, [u.resolve_candidates(item, reordered) for item in queries])

    def test_result_is_deeply_immutable_and_never_authoritative(self):
        result = u.resolve_candidates(query(), inventory())
        self.assertEqual(result.verification_status, "unverified")
        self.assertEqual(result.candidates[0].required_verification, u.REQUIRED_VERIFICATION)
        self.assertNotIsInstance(result, c.IdentityResolution)
        for obj, field, value in ((result, "status", "resolved"),
                                   (result, "verification_status", "verified"),
                                   (result.candidates[0], "entity", entity("other")),
                                   (result.candidates[0].entity, "legal_name", "Changed"),
                                   (result.candidates[0].listing.aliases[0], "symbol", "OTHER")):
            with self.subTest(field=field):
                with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
                    setattr(obj, field, value)
        self.assertEqual(hash(result), hash(u.resolve_candidates(query(), inventory())))
        with self.assertRaises(TypeError):
            u.AuthorityQuery("authority_id", "fixture", "ISSUER", verified=True)

    def test_direct_result_constructors_reject_mutability_and_authority_statuses(self):
        result = u.resolve_candidates(query(), inventory())
        for changes in (dict(status="resolved"), dict(candidates=list(result.candidates)),
                        dict(reasons=list(result.reasons)), dict(reasons=("trusted",)),
                        dict(candidates=result.candidates * 2), dict(status="ambiguous")):
            with self.subTest(changes=changes):
                self.reject(replace, result, **changes)
        with self.assertRaises(TypeError):
            u.CandidateResolution("unique_candidate", result.candidates, result.reasons, verified=True)

    def test_direct_candidate_constructors_reject_invalid_chains_and_mutable_matches(self):
        candidate = u.resolve_candidates(query(), inventory()).candidates[0]
        for changes in (dict(entity="entity"), dict(security=None), dict(listing={}),
                        dict(match_basis="verified"), dict(temporal_state="verified"),
                        dict(matched_aliases=list(candidate.matched_aliases)),
                        dict(matched_names=[]), dict(matched_authorities=(authority(),)),
                        dict(matched_aliases=(alias("ABSENT"),))):
            with self.subTest(changes=changes):
                self.reject(replace, candidate, **changes)
        self.reject(replace, candidate, entity=entity("other"))

    def test_empty_inventory_and_unrelated_invalid_record_not_ignored(self):
        self.assertEqual(u.resolve_candidates(query(), u.IdentityInventory(())).status, "unresolved")
        inv = inventory()
        object.__setattr__(inv, "securities", inv.securities + (security(entity("missing"), "unrelated"),))
        self.reject(u.resolve_candidates, u.CikQuery(entity().cik), inv)

    def test_closed_query_types_no_duck_typing_or_paths(self):
        class SubQuery(u.CikQuery):
            pass
        for invalid in (None, {}, "SYN", key("sec_cik", entity().cik), SubQuery(entity().cik)):
            self.reject(u.resolve_candidates, invalid, inventory())
        for invalid in ({}, [], None, (entity(),), "C:/arbitrary/path"):
            self.reject(u.resolve_candidates, query(), invalid)
        for value in ("https://host/path", "../file", "C:\\file"):
            self.reject(u.AuthorityQuery, "authority_id", "fixture", value)

    def test_malformed_dates_and_text(self):
        for day in ("2026-02-30", "20261029", "2026-1-01", "2026-10-29T00:00:00Z", "0000-01-01", None, 1):
            with self.subTest(day=day):
                self.reject(query, as_of=day)
                if day is not None:
                    self.reject(u.AuthorityQuery, "authority_id", "fixture", "ID", day)
        for invalid in ("", " Name", "Name ", "A\nB", "A\ud800", "A\u202eB", True, "a" * 201):
            self.reject(u.NameQuery, invalid)
        for changes in (dict(mic="nasdaq"), dict(mic="xnas"), dict(provider="x/y"),
                        dict(product=True), dict(symbol="A B"), dict(symbol="x" * 65)):
            self.reject(query, **changes)
        self.reject(u.NameQuery, "ab", "contains")
        self.reject(u.NameQuery, "valid", "fuzzy")
        self.reject(interval, "2026-01-01", "2026-01-01")
        self.reject(interval, "2026-01-02", "2026-01-01")

    def test_forged_nested_values_revalidated_before_matching(self):
        for invalid in ("123456", "0000000000", "1" * 1_000_000):
            bad = replace(entity())
            object.__setattr__(bad.key, "id", invalid)
            self.reject(u.IdentityInventory, (bad,))
        bad_alias = alias()
        object.__setattr__(bad_alias, "effective", "2026-01-01")
        bad_listing = replace(listing())
        object.__setattr__(bad_listing, "aliases", (bad_alias,))
        self.reject(u.IdentityInventory, (entity(),), (security(),), (bad_listing,))
        bad_query = query()
        object.__setattr__(bad_query, "as_of", "bad-date")
        self.reject(u.resolve_candidates, bad_query, inventory())

    def test_exact_collection_limits_and_one_over(self):
        entities = tuple(entity(f"e{i}") for i in range(u.MAX_ENTITIES))
        securities = tuple(security(entities[0], f"s{i}") for i in range(u.MAX_SECURITIES))
        listings = tuple(listing(securities[0], f"l{i}") for i in range(u.MAX_LISTINGS))
        names = tuple(u.NameAlias(entities[0].key, f"Old {i}", key("artifact", str(i)), None)
                      for i in range(u.MAX_NAMES))
        inv = u.IdentityInventory(entities, securities, listings, names)
        self.assertEqual(tuple(len(getattr(inv, name)) for name in ("entities", "securities", "listings", "names")),
                         (128, 256, 512, 256))
        for name in ("entities", "securities", "listings", "names"):
            with self.subTest(name=name):
                values = getattr(inv, name)
                self.reject(replace, inv, **{name: values + (values[0],)})
                self.reject(replace, inv, **{name: list(values)})
        result = u.resolve_candidates(u.NameQuery("Synthetic", "contains"), inv)
        self.assertEqual((result.status, len(result.candidates)), ("ambiguous", u.MAX_CANDIDATES))
        self.reject(u.resolve_candidates, query(), inv)  # 512 hits: never truncate to 128.

    def test_nested_collection_limits_and_wrong_members(self):
        self.reject(u.IdentityInventory, ("entity",))
        bad = replace(listing())
        object.__setattr__(bad, "aliases", (alias(),) * 65)
        self.reject(u.IdentityInventory, (entity(),), (security(),), (bad,))
        bad = replace(entity())
        object.__setattr__(bad, "authority_ids", (authority(),) * 17)
        self.reject(u.IdentityInventory, (bad,))

    def test_inventory_logical_byte_limit_inclusive_and_one_over(self):
        inv = inventory()
        actual = sum(len(c.encode(ref)) for ref in inv.entities + inv.securities + inv.listings)
        with patch.object(u, "MAX_INVENTORY_BYTES", actual):
            self.assertEqual(replace(inv), inv)
        with patch.object(u, "MAX_INVENTORY_BYTES", actual - 1):
            self.reject(replace, inv)
        name = u.NameAlias(entity().key, "Old", key("artifact"), None)
        actual += len(u._name_bytes(name))
        with patch.object(u, "MAX_INVENTORY_BYTES", actual):
            self.assertEqual(len(replace(inv, names=(name,)).names), 1)
        with patch.object(u, "MAX_INVENTORY_BYTES", actual - 1):
            self.reject(replace, inv, names=(name,))

    def test_real_inventory_byte_overflow_is_reachable(self):
        aliases = tuple(alias("S" + str(i), evidence=str(i), provider="p" * 64, product="f" * 64)
                        for i in range(60))
        listings = tuple(listing(identifier="l" + str(i), aliases=aliases) for i in range(64))
        self.assertLess(len(c.encode(listings[0])), c.MAX_BYTES)
        self.assertGreater(sum(len(c.encode(item)) for item in listings), u.MAX_INVENTORY_BYTES)
        self.reject(u.IdentityInventory, (entity(),), (security(),), listings)

    def test_result_count_exact_and_one_over_independent_of_inventory_count(self):
        sec = security()
        listings = tuple(listing(sec, str(i)) for i in range(u.MAX_CANDIDATES + 1))
        inv = u.IdentityInventory((entity(),), (sec,), listings[:-1])
        self.assertEqual(len(u.resolve_candidates(query(), inv).candidates), u.MAX_CANDIDATES)
        self.reject(u.resolve_candidates, query(), replace(inv, listings=listings))

    def test_result_logical_reference_bytes_inclusive_and_one_over(self):
        inv = two_listings()
        result = u.resolve_candidates(query(), inv)
        actual = sum(len(c.encode(ref)) for item in result.candidates
                     for ref in (item.entity, item.security, item.listing))
        with patch.object(u, "MAX_RESULT_REFERENCE_BYTES", actual):
            self.assertEqual(u.resolve_candidates(query(), inv), result)
        with patch.object(u, "MAX_RESULT_REFERENCE_BYTES", actual - 1):
            self.reject(u.resolve_candidates, query(), inv)

    def test_name_result_byte_accounting_and_search_limit_edges(self):
        long_name = "界" * 200
        ent = entity(name=long_name)
        name = u.NameAlias(ent.key, long_name, key("artifact"), None)
        inv = u.IdentityInventory((ent,), names=(name,))
        query = u.NameQuery(long_name)
        actual = len(c.encode(ent)) + len(u._name_bytes(name))
        with patch.object(u, "MAX_RESULT_REFERENCE_BYTES", actual):
            self.assertEqual(u.resolve_candidates(query, inv).status, "unique_candidate")
        with patch.object(u, "MAX_RESULT_REFERENCE_BYTES", actual - 1):
            self.reject(u.resolve_candidates, query, inv)
        self.assertEqual(u.NameQuery("abc", "contains").mode, "contains")
        self.assertEqual(u.NameQuery("ＡＢＣ").name, "ＡＢＣ")  # NFC never NFKC/confusable folding.
        self.assertEqual(u.resolve_candidates(u.NameQuery("ABC"),
                          u.IdentityInventory((entity(name="ＡＢＣ"),))).candidates, ())

    def test_real_result_reference_overflow_rejects_without_partial_output(self):
        authorities = tuple(authority(str(i) + "I" * 120, evidence=str(i) + "E" * 120,
                                      source="s" * 64) for i in range(16))
        ent = entity(authorities=authorities)
        sec = security(ent, authorities=authorities)
        listings = tuple(listing(sec, str(i)) for i in range(128))
        inv = u.IdentityInventory((ent,), (sec,), listings)
        self.assertLess(sum(len(c.encode(ref)) for ref in inv.entities + inv.securities + inv.listings),
                        u.MAX_INVENTORY_BYTES)
        self.reject(u.resolve_candidates, query(), inv)

    def test_errors_do_not_echo_supplied_labels(self):
        secret_label = "sensitive_fixture_label"
        try:
            u.SymbolQuery(secret_label + " ", "XNAS", "2026-10-29", "fixture", "symbols")
        except u.IdentityInputError as exc:
            self.assertNotIn(secret_label, str(exc))
        else:
            self.fail("invalid input accepted")


class IsolationAndMutationTests(unittest.TestCase):
    def test_static_import_surface_is_only_stdlib_and_c1(self):
        tree = ast.parse((BACKEND / "app" / "universal_identity.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
                if node.module == "app":
                    self.assertEqual([item.name for item in node.names], ["research_contracts"])
        self.assertEqual(set(imports), {"dataclasses", "json", "re", "unicodedata", "typing", "app"})

    def test_fresh_process_import_and_resolution_forbid_operational_effects(self):
        script = r'''
import sys, importlib.abc, os, socket, subprocess, builtins, pathlib, io
sys.dont_write_bytecode = True
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
# Import machinery may read Python sources only. Every other open is rejected.
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
from app import universal_identity as u, research_contracts as c
# Once imports finish, forbid even source-file reads during resolution.
builtins.open = io.open = pathlib.Path.open = os.open = deny
ent = c.EntityRef(c.KeyRef("external_entity", "synthetic"), "Synthetic", None, None, ())
result = u.resolve_candidates(u.NameQuery("Synthetic"), u.IdentityInventory((ent,)))
assert result.status == "unique_candidate" and result.verification_status == "unverified"
assert not any(name in sys.modules for name in blocked)
print("isolated import and resolution passed")
'''
        run = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(BACKEND)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("isolated import and resolution passed", run.stdout)

    def test_negative_probes_kill_in_memory_mutants(self):
        source = (BACKEND / "app" / "universal_identity.py").read_text(encoding="utf-8")

        def unique_remains_unverified(module):
            inv = module.IdentityInventory((entity(),), (security(),), (listing(),))
            result = module.resolve_candidates(module.SymbolQuery("SYN", "XNAS", "2026-10-29",
                                                                  "fixture", "symbols"), inv)
            self.assertEqual(result.status, "unique_candidate")
            self.assertEqual(result.verification_status, "unverified")

        def unknown_abstains(module):
            inv = module.IdentityInventory((entity(),), (security(),), (listing(effective=None),))
            result = module.resolve_candidates(module.SymbolQuery("SYN", "XNAS", "2026-10-29",
                                                                  "fixture", "symbols"), inv)
            self.assertEqual(result.status, "unresolved")

        def mic_scopes(module):
            inv = module.IdentityInventory((entity(),), (security(),), (listing(mic="XNYS"),))
            result = module.resolve_candidates(module.SymbolQuery("SYN", "XNAS", "2026-10-29",
                                                                  "fixture", "symbols"), inv)
            self.assertEqual(result.candidates, ())

        def exclusive_end(module):
            inv = module.IdentityInventory((entity(),), (security(),),
                        (listing(aliases=(alias(effective=interval("2020-01-01", "2026-10-29")),)),))
            result = module.resolve_candidates(module.SymbolQuery("SYN", "XNAS", "2026-10-29",
                                                                  "fixture", "symbols"), inv)
            self.assertEqual(result.status, "unresolved")

        def authority_namespace(module):
            inv = module.IdentityInventory((entity(authorities=(authority(source="other"),)),))
            result = module.resolve_candidates(module.AuthorityQuery("authority_id", "fixture", "ISSUER"), inv)
            self.assertEqual(result.candidates, ())

        def duplicates_reject(module):
            with self.assertRaises((module.IdentityInputError, c.ContractError)):
                module.IdentityInventory((entity(), entity()))

        def competitors_preserved(module):
            inv = two_listings()
            result = module.resolve_candidates(module.SymbolQuery("SYN", "XNAS", "2026-10-29",
                                                                  "fixture", "symbols"),
                        module.IdentityInventory(inv.entities, inv.securities, inv.listings))
            self.assertEqual((result.status, len(result.candidates)), ("ambiguous", 2))

        def candidate_bound(module):
            inv = module.IdentityInventory((entity(),), (security(),),
                                           tuple(listing(identifier=str(i)) for i in range(129)))
            with self.assertRaises(module.IdentityInputError):
                module.resolve_candidates(module.SymbolQuery("SYN", "XNAS", "2026-10-29",
                                                              "fixture", "symbols"), inv)

        mutants = (
            ("authority_promotion", 'status, reasons = "unique_candidate",',
             'status, reasons = "resolved",', unique_remains_unverified),
            ("unknown_date_promotion", 'return "unknown_effective"', 'return "in_effect"', unknown_abstains),
            ("mic_ignored", 'listing.mic != query.mic or not aliases', 'not aliases', mic_scopes),
            ("inclusive_end", 'as_of >= interval.end', 'as_of > interval.end', exclusive_end),
            ("authority_namespace_ignored", '(item.scheme, item.authority, item.identifier) ==\n'
             '                                (query.scheme, query.authority, query.identifier)',
             'item.identifier == query.identifier', authority_namespace),
            ("duplicate_key_accepted", '_require(clean.key not in seen, "inventory: duplicate reference key")',
             'pass', duplicates_reject),
            ("competitor_discarded", 'candidates = tuple(sorted(candidates, key=_candidate_order))',
             'candidates = tuple(sorted(candidates, key=_candidate_order))[:1]', competitors_preserved),
            ("candidate_bound_removed", 'MAX_CANDIDATES = 128', 'MAX_CANDIDATES = 129', candidate_bound),
        )
        for name, before, after, probe in mutants:
            with self.subTest(mutant=name):
                probe(u)
                self.assertEqual(source.count(before), 1, "mutation must target exactly one site")
                module = types.ModuleType("app._ucr_mutant_" + name)
                sys.modules[module.__name__] = module
                try:
                    exec(compile(source.replace(before, after, 1), "<ucr-mutant>", "exec"), module.__dict__)
                    with self.assertRaises((AssertionError, module.IdentityInputError, c.ContractError)):
                        probe(module)
                finally:
                    del sys.modules[module.__name__]


if __name__ == "__main__":
    unittest.main(verbosity=2)
