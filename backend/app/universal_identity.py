"""Offline candidate matching over supplied C1 metadata, never authority admission.

Exact keys, identifiers, MICs and provider/product symbols are case-sensitive.
Only name search folds NFC/case/whitespace; that is discovery, not identity proof.
No C1 IdentityResolution is emitted: even one candidate remains unverified.
"""

from dataclasses import dataclass, fields, replace
import json
import re
import unicodedata
from typing import ClassVar

from app import research_contracts as c


MAX_ENTITIES = 128
MAX_SECURITIES = 256
MAX_LISTINGS = 512
MAX_NAMES = 256
MAX_INVENTORY_BYTES = 1_048_576
MAX_CANDIDATES = 128
MAX_RESULT_REFERENCE_BYTES = 1_048_576
REQUIRED_VERIFICATION = (
    "original_source_identity", "provenance_and_revision", "effective_dates",
    "issuer_security_listing_links", "operation_specific_rights",
    "server_side_authority_admission",
)


class IdentityInputError(ValueError):
    """Malformed/contradictory metadata or resource excess; no payload in errors."""


def _require(condition, reason):
    if not condition:
        raise IdentityInputError(reason)


def _text(value, maximum, pattern=None):
    _require(type(value) is str, "text: exact string required")
    _require(1 <= len(value) <= maximum, "text: character limit")
    _require(value == value.strip(), "text: boundary whitespace")
    _require(not any(
        unicodedata.category(char) in ("Cc", "Cs")
        or 0x202A <= ord(char) <= 0x202E or 0x2066 <= ord(char) <= 0x2069
        for char in value
    ), "text: forbidden character")
    _require(len(value.encode("utf-8")) <= maximum * 4, "text: byte limit")
    if pattern is not None:
        _require(re.fullmatch(pattern, value) is not None, "text: syntax")


def _date(value, optional=False):
    if value is None and optional:
        return
    c.DateTimePoint(value)


def _key(value, namespaces):
    _require(type(value) is c.KeyRef, "key: exact C1 reference required")
    c.KeyRef(value.namespace, value.id)
    _require(value.namespace in namespaces, "key: namespace mismatch")


def _collection(value, cls, maximum):
    _require(type(value) is tuple, "collection: exact tuple required")
    _require(len(value) <= maximum, "collection: resource limit")
    _require(all(type(item) is cls for item in value), "collection: member type")


def _key_order(key):
    return key.namespace, key.id


def _interval_order(interval):
    return (0, "", "") if interval is None else (1, interval.start, interval.end or "")


def _authority_order(item):
    return (item.scheme, item.authority, item.identifier,
            _interval_order(item.effective), _key_order(item.evidence_key))


def _alias_order(item):
    return (item.provider, item.product, item.symbol,
            _interval_order(item.effective), _key_order(item.evidence_key))


def _name_order(item):
    return (_key_order(item.entity_key), item.name,
            _interval_order(item.effective), _key_order(item.evidence_key))


def _name_fold(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@dataclass(frozen=True, slots=True)
class CikQuery:
    cik: str

    def __post_init__(self):
        c.KeyRef("sec_cik", self.cik)

    @classmethod
    def from_unpadded(cls, text):
        """Opt-in C1 text normalization, never implicit canonical coercion."""
        return cls(c.canonical_sec_cik(text))


@dataclass(frozen=True, slots=True)
class SymbolQuery:
    symbol: str
    mic: str
    as_of: str
    provider: str
    product: str

    def __post_init__(self):
        _text(self.symbol, 64, r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,63}")
        _text(self.mic, 4, r"[A-Z0-9]{4}")
        _date(self.as_of)
        _text(self.provider, 64, r"[A-Za-z0-9._:-]{1,64}")
        _text(self.product, 64, r"[A-Za-z0-9._:-]{1,64}")


@dataclass(frozen=True, slots=True)
class AuthorityQuery:
    scheme: str
    authority: str
    identifier: str
    as_of: str | None = None

    def __post_init__(self):
        _require(type(self.scheme) is str and self.scheme in ("sec_cik", "lei", "authority_id"),
                 "authority: unsupported scheme")
        _text(self.authority, 64, r"[A-Za-z0-9._:-]{1,64}")
        if self.scheme == "sec_cik":
            _require(self.authority == "sec", "authority: SEC namespace required")
            c.KeyRef("sec_cik", self.identifier)
        elif self.scheme == "lei":
            _text(self.identifier, 20, r"[A-Z0-9]{20}")
        else:
            _text(self.identifier, 128, r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
        _date(self.as_of, optional=True)


@dataclass(frozen=True, slots=True)
class NameQuery:
    name: str
    mode: str = "exact"

    def __post_init__(self):
        _text(self.name, 200)
        _require(type(self.mode) is str and self.mode in ("exact", "contains"),
                 "name: unsupported search mode")
        if self.mode == "contains":
            _require(len(_name_fold(self.name)) >= 3, "name: contains needs three characters")


@dataclass(frozen=True, slots=True)
class NameAlias:
    """Supplied historical/search name, never an authority or succession claim."""

    entity_key: c.KeyRef
    name: str
    evidence_key: c.KeyRef
    effective: c.DateInterval | None

    def __post_init__(self):
        _key(self.entity_key, ("sec_cik", "external_entity"))
        _text(self.name, 200)
        _key(self.evidence_key, ("authority_record", "artifact"))
        _require(self.effective is None or type(self.effective) is c.DateInterval,
                 "name: invalid interval type")
        if self.effective is not None:
            c.DateInterval(self.effective.start, self.effective.end)


def _clean_reference(record):
    """Bound before C1 encode, then decode to revalidate/detach every nested field.

    This also rejects constructor-bypassed malformed C1 values. These checks are
    structural defenses, not a sandbox against code running in this process.
    """
    allowed = (c.EntityRef, c.SecurityRef, c.ListingRef, c.AuthorityIdentifier,
               c.SymbolAlias, c.KeyRef, c.DateInterval)
    nodes = 0

    def visit(value, depth):
        nonlocal nodes
        nodes += 1
        _require(nodes <= c.MAX_NODES and depth <= c.MAX_DEPTH, "reference: tree limit")
        if type(value) in allowed:
            for field in fields(value):
                visit(getattr(value, field.name), depth + 1)
        elif type(value) is tuple:
            _require(len(value) <= 64, "reference: nested collection limit")
            for item in value:
                visit(item, depth + 1)
        elif type(value) is str:
            _text(value, 800)
        else:
            _require(value is None, "reference: invalid nested value")

    visit(record, 1)
    result = c.decode(c.encode(record))
    if type(result) in (c.EntityRef, c.SecurityRef):
        return replace(result, authority_ids=tuple(sorted(result.authority_ids, key=_authority_order)))
    return replace(result, aliases=tuple(sorted(result.aliases, key=_alias_order)))


def _name_bytes(item):
    # Logical representation for the additional (non-C1) name record only.
    return json.dumps((item.entity_key.namespace, item.entity_key.id, item.name,
                       item.evidence_key.namespace, item.evidence_key.id,
                       None if item.effective is None else
                       (item.effective.start, item.effective.end)),
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _contained(inner, outer):
    return (inner.start >= outer.start and (outer.end is None or
            (inner.end is not None and inner.end <= outer.end)))


@dataclass(frozen=True, slots=True)
class IdentityInventory:
    entities: tuple[c.EntityRef, ...]
    securities: tuple[c.SecurityRef, ...] = ()
    listings: tuple[c.ListingRef, ...] = ()
    names: tuple[NameAlias, ...] = ()

    def __post_init__(self):
        for name, cls, maximum in (("entities", c.EntityRef, MAX_ENTITIES),
                                   ("securities", c.SecurityRef, MAX_SECURITIES),
                                   ("listings", c.ListingRef, MAX_LISTINGS),
                                   ("names", NameAlias, MAX_NAMES)):
            _collection(getattr(self, name), cls, maximum)
        byte_count = 0
        for name in ("entities", "securities", "listings"):
            values = []
            seen = set()
            for record in getattr(self, name):
                clean = _clean_reference(record)
                _require(clean.key not in seen, "inventory: duplicate reference key")
                seen.add(clean.key)
                byte_count += len(c.encode(clean))
                _require(byte_count <= MAX_INVENTORY_BYTES, "inventory: reference byte limit")
                values.append(clean)
            object.__setattr__(self, name, tuple(sorted(values, key=lambda x: _key_order(x.key))))
        entities = {item.key: item for item in self.entities}
        securities = {item.key: item for item in self.securities}
        for security in self.securities:
            _require(security.issuer_key in entities, "chain: missing issuer")
        for listing in self.listings:
            _require(listing.security_key in securities, "chain: missing security")
            for alias in listing.aliases:
                _require(alias.effective is None or listing.effective is None
                         or _contained(alias.effective, listing.effective),
                         "chain: alias interval contradicts listing")
        names = []
        seen = set()
        for item in self.names:
            clean = replace(item)
            _require(clean.entity_key in entities, "name: missing issuer")
            identity = clean.entity_key, _name_fold(clean.name), clean.effective
            _require(identity not in seen, "name: duplicate name interval")
            seen.add(identity)
            byte_count += len(_name_bytes(clean))
            _require(byte_count <= MAX_INVENTORY_BYTES, "inventory: reference byte limit")
            names.append(clean)
        object.__setattr__(self, "names", tuple(sorted(names, key=_name_order)))


@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    entity: c.EntityRef
    security: c.SecurityRef | None
    listing: c.ListingRef | None
    match_basis: str
    temporal_state: str
    matched_authorities: tuple[c.AuthorityIdentifier, ...] = ()
    matched_aliases: tuple[c.SymbolAlias, ...] = ()
    matched_names: tuple[NameAlias, ...] = ()
    verification_status: ClassVar[str] = "unverified"
    required_verification: ClassVar[tuple[str, ...]] = REQUIRED_VERIFICATION

    def __post_init__(self):
        _require(type(self.entity) is c.EntityRef, "candidate: entity type")
        _require(self.security is None or type(self.security) is c.SecurityRef, "candidate: security type")
        _require(self.listing is None or type(self.listing) is c.ListingRef, "candidate: listing type")
        _require(self.listing is None or self.security is not None, "candidate: incomplete chain")
        c.check_reference_context(self.entity, security=self.security, listing=self.listing)
        _collection(self.matched_authorities, c.AuthorityIdentifier, 16)
        _collection(self.matched_aliases, c.SymbolAlias, 64)
        _collection(self.matched_names, NameAlias, MAX_NAMES)
        _require(type(self.match_basis) is str and self.match_basis in (
            "canonical_cik", "dated_symbol_mic_provider_product", "exact_authority_identifier",
            "name_exact", "name_contains"), "candidate: unsupported basis")
        _require(type(self.temporal_state) is str and self.temporal_state in (
            "not_requested", "in_effect", "unknown_effective", "outside_effective"),
            "candidate: unsupported temporal state")
        for values in (self.matched_authorities, self.matched_aliases, self.matched_names):
            _require(len(set(values)) == len(values), "candidate: duplicate matched record")
        source = self.entity if self.security is None else self.security
        _require(all(item in source.authority_ids for item in self.matched_authorities),
                 "candidate: unmatched authority")
        _require(not self.matched_aliases or (self.listing is not None and all(
            item in self.listing.aliases for item in self.matched_aliases)), "candidate: unmatched alias")
        _require(all(item.entity_key == self.entity.key for item in self.matched_names),
                 "candidate: mismatched name issuer")
        if self.match_basis == "dated_symbol_mic_provider_product":
            _require(self.listing is not None and bool(self.matched_aliases)
                     and not self.matched_authorities and not self.matched_names
                     and self.temporal_state != "not_requested", "candidate: symbol match shape")
        elif self.match_basis == "exact_authority_identifier":
            _require(self.listing is None and bool(self.matched_authorities)
                     and not self.matched_aliases and not self.matched_names,
                     "candidate: authority match shape")
        else:
            _require(self.security is None and self.listing is None
                     and not self.matched_aliases and not self.matched_authorities
                     and self.temporal_state == "not_requested", "candidate: issuer match shape")
            if self.match_basis == "canonical_cik":
                _require(self.entity.key.namespace == "sec_cik" and not self.matched_names,
                         "candidate: canonical CIK shape")

    @property
    def evidence_keys(self):
        """All supplied evidence on this returned chain, including inactive aliases."""
        keys = {item.evidence_key for item in self.entity.authority_ids}
        if self.security is not None:
            keys.update(item.evidence_key for item in self.security.authority_ids)
        if self.listing is not None:
            keys.update(item.evidence_key for item in self.listing.aliases)
        keys.update(item.evidence_key for item in self.matched_names)
        return tuple(sorted(keys, key=_key_order))


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    status: str
    candidates: tuple[IdentityCandidate, ...]
    reasons: tuple[str, ...]
    verification_status: ClassVar[str] = "unverified"
    required_verification: ClassVar[tuple[str, ...]] = REQUIRED_VERIFICATION

    def __post_init__(self):
        _collection(self.candidates, IdentityCandidate, MAX_CANDIDATES)
        _collection(self.reasons, str, 6)
        _require(type(self.status) is str and self.status in (
            "unique_candidate", "ambiguous", "unresolved"), "result: unsupported status")
        allowed_reasons = ("multiple_candidates", "competing_listings", "competing_authority_claims",
                          "unknown_effective_dates", "unverified_structural_match",
                          "outside_effective_dates", "no_candidates", "name_search_only")
        _require(bool(self.reasons) and all(item in allowed_reasons for item in self.reasons)
                 and len(set(self.reasons)) == len(self.reasons), "result: invalid reasons")
        identities = tuple(_candidate_order(item) for item in self.candidates)
        _require(len(set(identities)) == len(identities) and identities == tuple(sorted(identities)),
                 "result: duplicate or unordered candidate identities")
        possible = self.possible_candidates
        unknown = any(item.temporal_state == "unknown_effective" for item in possible)
        expected = ("ambiguous" if len(possible) > 1 else "unresolved" if unknown or not possible
                    else "unique_candidate")
        _require(self.status == expected, "result: inconsistent candidate status")
        byte_count = 0
        for item in self.candidates:
            byte_count += sum(len(c.encode(ref)) for ref in (item.entity, item.security, item.listing)
                              if ref is not None)
            byte_count += sum(len(_name_bytes(name)) for name in item.matched_names)
            _require(byte_count <= MAX_RESULT_REFERENCE_BYTES, "result: reference byte limit")

    @property
    def possible_candidates(self):
        """Exclude known inactive diagnostics; retain unknown-effective rivals."""
        return tuple(item for item in self.candidates if item.temporal_state != "outside_effective")


def _temporal(intervals, as_of):
    if as_of is None:
        return "not_requested"
    if any(interval is not None and (as_of < interval.start or
           (interval.end is not None and as_of >= interval.end)) for interval in intervals):
        return "outside_effective"
    if any(interval is None for interval in intervals):
        return "unknown_effective"
    return "in_effect"


def _best_temporal(states):
    # Several disjoint matching aliases on the same listing remain one candidate.
    return next(state for state in ("in_effect", "unknown_effective", "outside_effective")
                if state in states)


def _candidate_order(item):
    return (_key_order(item.entity.key),
            ("", "") if item.security is None else _key_order(item.security.key),
            ("", "") if item.listing is None else _key_order(item.listing.key))


def _finish(candidates, query):
    candidates = tuple(sorted(candidates, key=_candidate_order))
    possible = tuple(item for item in candidates if item.temporal_state != "outside_effective")
    unknown = any(item.temporal_state == "unknown_effective" for item in possible)
    if len(possible) > 1:
        status, reasons = "ambiguous", ("multiple_candidates",)
        if type(query) is SymbolQuery:
            reasons += ("competing_listings",)
        if type(query) is AuthorityQuery:
            reasons += ("competing_authority_claims",)
    elif unknown:
        status, reasons = "unresolved", ()
    elif possible:
        status, reasons = "unique_candidate", ("unverified_structural_match",)
    else:
        status = "unresolved"
        reasons = ("outside_effective_dates",) if candidates else ("no_candidates",)
    if unknown:
        reasons += ("unknown_effective_dates",)
    if type(query) is NameQuery:
        reasons += ("name_search_only",)
    return CandidateResolution(status, candidates, reasons)


def resolve_candidates(query, inventory):
    """Validate the complete bounded inventory, then match without effects.

    Candidate tuples retain matching out-of-date records as diagnostics. A
    unique_candidate has exactly one possible, temporally supported match (or an
    undated query); unknown-effective competitors prevent that status. None of
    these outcomes is a verified identity, admission, ownership or rights grant.
    Invalid input/overflow raises IdentityInputError or C1 ContractError; no
    partial result is returned. Input order never breaks a tie.
    """
    _require(type(query) in (CikQuery, SymbolQuery, AuthorityQuery, NameQuery),
             "query: closed query type required")
    query = replace(query)
    _require(type(inventory) is IdentityInventory, "inventory: exact inventory required")
    inventory = replace(inventory)
    entities = {item.key: item for item in inventory.entities}
    securities = {item.key: item for item in inventory.securities}
    candidates = []

    def add(candidate):
        _require(len(candidates) < MAX_CANDIDATES, "result: candidate limit")
        candidates.append(candidate)

    if type(query) is CikQuery:
        entity = entities.get(c.KeyRef("sec_cik", query.cik))
        if entity is not None:
            add(IdentityCandidate(entity, None, None, "canonical_cik", "not_requested"))
    elif type(query) is SymbolQuery:
        for listing in inventory.listings:
            aliases = tuple(alias for alias in listing.aliases if
                            (alias.provider, alias.product, alias.symbol) ==
                            (query.provider, query.product, query.symbol))
            if listing.mic != query.mic or not aliases:
                continue
            security = securities[listing.security_key]
            temporal = _best_temporal(tuple(_temporal((listing.effective, alias.effective), query.as_of)
                                            for alias in aliases))
            add(IdentityCandidate(entities[security.issuer_key], security, listing,
                                  "dated_symbol_mic_provider_product", temporal,
                                  matched_aliases=aliases))
    elif type(query) is AuthorityQuery:
        for record in inventory.entities + inventory.securities:
            authorities = tuple(item for item in record.authority_ids if
                                (item.scheme, item.authority, item.identifier) ==
                                (query.scheme, query.authority, query.identifier))
            if not authorities:
                continue
            entity = record if type(record) is c.EntityRef else entities[record.issuer_key]
            security = record if type(record) is c.SecurityRef else None
            temporal = _temporal((authorities[0].effective,), query.as_of)
            add(IdentityCandidate(entity, security, None, "exact_authority_identifier", temporal,
                                  matched_authorities=authorities))
    else:
        target = _name_fold(query.name)

        def matches(name):
            folded = _name_fold(name)
            return target == folded if query.mode == "exact" else target in folded

        for entity in inventory.entities:
            names = tuple(item for item in inventory.names
                          if item.entity_key == entity.key and matches(item.name))
            if matches(entity.legal_name) or names:
                add(IdentityCandidate(entity, None, None, "name_" + query.mode,
                                      "not_requested", matched_names=names))
    return _finish(candidates, query)
