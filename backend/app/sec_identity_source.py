"""Offline SEC Submissions metadata; structural validity never grants authority.

Only supplied immutable bytes are read. No acquisition, registry, DB or config.
Source dates are metadata, not accepted legal effective intervals. Exchange names
are source hints, never MICs. See the FL-UCR-01B1 ExecPlan for supported policies.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import re
import unicodedata
from typing import ClassVar

from app import research_contracts as c
from app import universal_identity as u


MAX_RESPONSE_BYTES = 4_194_304
MAX_DEPTH = 16
MAX_NODES = 100_000  # includes object keys; charged before retaining each node
MAX_STRING_CHARS = 16_384
MAX_FORMER_NAMES = 64
MAX_ASSOCIATIONS = 64
SOURCE_IDENTITY = "sec.submissions.registrant_metadata"
PARSER_REVISION = "fl-ucr-01b1.v1"
# Other SEC fields are syntax/resource checked only; no identity claims are taken
# from them. Unknown root fields fail closed, including forged provenance claims.
_OTHER_FIELDS = frozenset((
    "entityType", "sic", "sicDescription", "ownerOrg",
    "insiderTransactionForOwnerExists", "insiderTransactionForIssuerExists",
    "ein", "description", "website", "investorWebsite", "category",
    "fiscalYearEnd", "stateOfIncorporation", "stateOfIncorporationDescription",
    "addresses", "phone", "flags", "filings",
))
_IDENTITY_FIELDS = frozenset(("cik", "name", "formerNames", "tickers", "exchanges"))


class SecIdentitySourceError(ValueError):
    """Stable payload-free code; no partial metadata accompanies a failure."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise SecIdentitySourceError(code)


def _safe_unicode(value):
    _require(not any(
        unicodedata.category(char) in ("Cc", "Cs")
        or 0x202A <= ord(char) <= 0x202E or 0x2066 <= ord(char) <= 0x2069
        for char in value
    ), "json_string_character")


def _text(value, maximum, code):
    _require(type(value) is str, code)
    _require(1 <= len(value) <= maximum and value == value.strip(), code)
    _safe_unicode(value)
    return value


class _Parser:
    """Bounded descent; no unbounded full-tree json.loads or numeric coercion.

    Input bytes cap scanstring's temporary work; strings and node counts are
    checked before insertion. Container depth is checked before recursion.
    """

    def __init__(self, text):
        self.text, self.pos, self.nodes = text, 0, 0

    def space(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def node(self):
        self.nodes += 1
        _require(self.nodes <= MAX_NODES, "json_node_limit")

    def string(self):
        self.node()
        try:
            value, self.pos = json.decoder.scanstring(self.text, self.pos + 1, True)
        except ValueError:
            raise SecIdentitySourceError("json_string") from None
        _require(len(value) <= MAX_STRING_CHARS, "json_string_limit")
        _safe_unicode(value)
        return value

    def value(self, depth=1):
        self.space()
        _require(self.pos < len(self.text), "json_syntax")
        char = self.text[self.pos]
        if char == '"':
            return self.string()
        self.node()
        if char in "[{":
            _require(depth <= MAX_DEPTH, "json_depth_limit")
            self.pos += 1
            obj = char == "{"
            result = {} if obj else []
            closing = "}" if obj else "]"
            self.space()
            if self.pos < len(self.text) and self.text[self.pos] == closing:
                self.pos += 1
                return result
            while True:
                self.space()
                if obj:
                    _require(self.pos < len(self.text) and self.text[self.pos] == '"',
                             "json_syntax")
                    key = self.string()
                    _require(key not in result, "json_duplicate_key")
                    self.space()
                    _require(self.pos < len(self.text) and self.text[self.pos] == ":",
                             "json_syntax")
                    self.pos += 1
                    result[key] = self.value(depth + 1)
                else:
                    result.append(self.value(depth + 1))
                self.space()
                _require(self.pos < len(self.text), "json_syntax")
                separator = self.text[self.pos]
                self.pos += 1
                if separator == closing:
                    return result
                _require(separator == ",", "json_syntax")
        for token, value in (("null", None), ("true", True), ("false", False)):
            if self.text.startswith(token, self.pos):
                self.pos += len(token)
                return value
        if char in "0123456789-":
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] not in " \r\n\t,]}":
                self.pos += 1
            token = self.text[start:self.pos]
            _require(len(token) <= 16 and re.fullmatch(r"0|[1-9][0-9]{0,15}", token)
                     is not None, "json_number")
            number = int(token)
            _require(number <= c.MAX_PIN, "json_number")
            return number
        raise SecIdentitySourceError("json_syntax")


def _decode(original_bytes):
    _require(type(original_bytes) is bytes, "input_bytes")
    _require(len(original_bytes) <= MAX_RESPONSE_BYTES, "response_byte_limit")
    _require(not original_bytes.startswith(b"\xef\xbb\xbf"), "json_bom")
    try:
        text = original_bytes.decode("utf-8", errors="strict")
    except UnicodeError:
        raise SecIdentitySourceError("json_utf8") from None
    parser = _Parser(text)
    root = parser.value()
    parser.space()
    _require(parser.pos == len(text), "json_trailing")
    _require(type(root) is dict, "response_object")
    return root


def _source_date(value):
    if value is None:
        return None
    _text(value, 32, "former_name_date")
    try:
        if len(value) == 10:
            return c.DateTimePoint(value)
        return c.InstantTimePoint(value)
    except c.ContractError:
        raise SecIdentitySourceError("former_name_date") from None


def _fold(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@dataclass(frozen=True, slots=True)
class FormerName:
    name: str
    source_from: str | None
    source_to: str | None
    # The raw dates do not establish C1 half-open legal effectiveness.
    effective: ClassVar[None] = None


@dataclass(frozen=True, slots=True)
class TickerExchangeHint:
    ticker: str
    exchange_name: str
    association_kind: ClassVar[str] = "source_reported_ticker_exchange_hint"
    effective: ClassVar[None] = None


@dataclass(frozen=True, slots=True)
class SecIdentitySource:
    original_bytes: bytes
    expected_cik: str
    response_sha256: str
    entity: c.EntityRef
    former_names: tuple[FormerName, ...]
    ticker_exchange_hints: tuple[TickerExchangeHint, ...]
    source_identity: ClassVar[str] = SOURCE_IDENTITY
    parser_revision: ClassVar[str] = PARSER_REVISION
    verification_status: ClassVar[str] = "unverified"
    source_revision_key: ClassVar[None] = None
    public_available_at: ClassVar[c.UnknownTimePoint] = c.UnknownTimePoint()
    retrieved_at: ClassVar[c.UnknownTimePoint] = c.UnknownTimePoint()
    required_verification: ClassVar[tuple[str, ...]] = u.REQUIRED_VERIFICATION


def parse_sec_submissions(original_bytes, *, expected_cik):
    """Validate the entire response before returning immutable unverified data.

    SEC `cik` accepts only 1..10 ASCII decimal characters, explicitly padded;
    expected_cik is already canonical nonzero ten-digit C1 text. No source labels,
    claimed hashes, URLs, receipts or trust flags are API arguments.
    """
    try:
        c.KeyRef("sec_cik", expected_cik)
    except c.ContractError:
        raise SecIdentitySourceError("expected_cik") from None
    root = _decode(original_bytes)
    _require(root.keys() <= _IDENTITY_FIELDS | _OTHER_FIELDS, "unsupported_root_field")
    _require("cik" in root and "name" in root, "mandatory_field")
    try:
        cik = c.canonical_sec_cik(root["cik"])
    except c.ContractError:
        raise SecIdentitySourceError("response_cik") from None
    _require(cik == expected_cik, "cik_mismatch")
    name = _text(root["name"], 200, "current_name")

    former = root.get("formerNames", [])
    _require(type(former) is list and len(former) <= MAX_FORMER_NAMES, "former_names_shape")
    names, seen = [], set()
    for item in former:
        _require(type(item) is dict and "name" in item
                 and item.keys() <= {"name", "from", "to"}, "former_name_shape")
        old_name = _text(item["name"], 200, "former_name")
        start, end = item.get("from"), item.get("to")
        a, b = _source_date(start), _source_date(end)
        if a is not None and b is not None:
            # Mixed precision cannot prove order within the same calendar day.
            if type(a) is type(b):
                _require(a.value <= b.value, "former_name_date_order")
            else:
                _require(a.value[:10] <= b.value[:10], "former_name_date_order")
        folded = _fold(old_name)
        _require(folded not in seen, "former_name_conflict")
        seen.add(folded)
        names.append(FormerName(old_name, start, end))

    _require(("tickers" in root) == ("exchanges" in root), "association_shape")
    tickers, exchanges = root.get("tickers", []), root.get("exchanges", [])
    _require(type(tickers) is list and type(exchanges) is list
             and len(tickers) == len(exchanges) and len(tickers) <= MAX_ASSOCIATIONS,
             "association_shape")
    hints, seen = [], set()
    for ticker, exchange in zip(tickers, exchanges):
        _text(ticker, 64, "ticker_hint")
        _require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,63}", ticker)
                 is not None, "ticker_hint")
        _text(exchange, 200, "exchange_hint")
        pair = ticker, exchange
        _require(pair not in seen, "association_conflict")
        seen.add(pair)
        hints.append(TickerExchangeHint(*pair))

    entity = c.EntityRef(c.KeyRef("sec_cik", cik), name, None, cik, ())
    return SecIdentitySource(original_bytes, expected_cik,
                             hashlib.sha256(original_bytes).hexdigest(), entity,
                             tuple(names), tuple(hints))


def _artifact_key(value):
    _require(type(value) is c.KeyRef, "untrusted_evidence_key")
    try:
        key = c.KeyRef(value.namespace, value.id)
    except c.ContractError:
        raise SecIdentitySourceError("untrusted_evidence_key") from None
    _require(key.namespace == "artifact", "untrusted_evidence_key")
    return key


def _issuer_inventory(source, evidence):
    names = tuple(u.NameAlias(source.entity.key, item.name, evidence, None)
                  for item in source.former_names)
    return u.IdentityInventory((source.entity,), names=names)


@dataclass(frozen=True, slots=True)
class SourceBoundIdentityInventory:
    """One untrusted artifact's support for exactly one supplied issuer.

    Pass `.inventory` to UCR-01A, retain this envelope, then use
    `.source_binding_for(candidate)` for every issuer match basis. Identical
    issuer metadata can have several source bindings; lookup establishes support
    by this artifact, not exclusive candidate origin or authenticated custody.
    """

    inventory: u.IdentityInventory
    issuer_key: c.KeyRef
    untrusted_artifact_key: c.KeyRef
    original_bytes: bytes
    response_sha256: str
    expected_cik: str
    source_identity: ClassVar[str] = SOURCE_IDENTITY
    parser_revision: ClassVar[str] = PARSER_REVISION
    verification_status: ClassVar[str] = "unverified"

    def __post_init__(self):
        _require(type(self) is SourceBoundIdentityInventory, "binding_type")
        source = parse_sec_submissions(self.original_bytes, expected_cik=self.expected_cik)
        evidence = _artifact_key(self.untrusted_artifact_key)
        _require(type(self.issuer_key) is c.KeyRef, "binding_issuer_mismatch")
        try:
            issuer = c.KeyRef(self.issuer_key.namespace, self.issuer_key.id)
        except c.ContractError:
            raise SecIdentitySourceError("binding_issuer_mismatch") from None
        _require(issuer == source.entity.key, "binding_issuer_mismatch")
        _require(type(self.response_sha256) is str
                 and self.response_sha256 == source.response_sha256, "binding_digest_mismatch")
        _require(type(self.inventory) is u.IdentityInventory, "binding_inventory_type")
        try:
            replace(self.inventory)
        except (c.ContractError, u.IdentityInputError):
            raise SecIdentitySourceError("binding_inventory_mismatch") from None
        inventory = _issuer_inventory(source, evidence)
        _require(self.inventory == inventory, "binding_inventory_mismatch")
        # Detach nested caller-owned references after complete revalidation.
        object.__setattr__(self, "inventory", inventory)
        object.__setattr__(self, "issuer_key", source.entity.key)
        object.__setattr__(self, "untrusted_artifact_key", evidence)

    def source_binding_for(self, candidate):
        """Return this validated untrusted binding, or reject unrelated metadata.

        Match exact issuer metadata and any matched aliases against this source;
        never infer provenance from candidate.evidence_keys. Revalidate even
        constructor-bypassed envelopes before lookup. No external lookup occurs.
        """
        _require(type(self) is SourceBoundIdentityInventory, "binding_type")
        clean = replace(self)
        _require(type(candidate) is u.IdentityCandidate, "candidate_type")
        _require(type(candidate.entity) is c.EntityRef
                 and candidate.entity == clean.inventory.entities[0], "candidate_issuer_mismatch")
        _require(candidate.security is None and candidate.listing is None
                 and candidate.match_basis in ("canonical_cik", "name_exact", "name_contains"),
                 "candidate_source_mismatch")
        try:
            candidate = replace(candidate)
        except (c.ContractError, u.IdentityInputError):
            raise SecIdentitySourceError("candidate_source_mismatch") from None
        _require(all(item in clean.inventory.names for item in candidate.matched_names),
                 "candidate_source_mismatch")
        return clean


def to_identity_inventory(source, *, untrusted_evidence_key):
    """Return a SourceBoundIdentityInventory, never a lossy bare inventory.

    Reparse originals so manually forged/mutated output fields cannot bypass
    guards. This is structural revalidation, not authenticity verification.
    No authority identifiers, securities, listings, MICs or dated aliases emerge.
    Keep the envelope when passing its `.inventory` to UCR-01A.
    """
    _require(type(source) is SecIdentitySource, "source_type")
    clean = parse_sec_submissions(source.original_bytes, expected_cik=source.expected_cik)
    _require(source == clean, "source_conflict")
    evidence = _artifact_key(untrusted_evidence_key)
    inventory = _issuer_inventory(clean, evidence)
    return SourceBoundIdentityInventory(inventory, clean.entity.key, evidence,
                                        clean.original_bytes, clean.response_sha256, clean.expected_cik)
