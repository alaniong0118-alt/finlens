"""Inert C1 reference values. Valid structure is never an authority grant.

No registry, environment, I/O, ID generation or application dependencies live here.
Only the explicit CIK factory and aware-instant UTC conversion normalize input.
See docs/shared-research-contracts.md for the closed version-1 representation.
"""

from dataclasses import dataclass, fields
from datetime import date, datetime, timezone
import json
import re
import unicodedata
from typing import ClassVar


MAX_BYTES = 65536
MAX_DEPTH = 8
MAX_NODES = 2048
MAX_PIN = 9007199254740991
NAMESPACES = frozenset((
    "sec_cik", "external_entity", "security", "listing", "principal", "session",
    "artifact", "source_descriptor", "source_revision", "rights_policy",
    "admission_record", "market_publication", "authority_record", "calendar",
))
ENTITY_NAMESPACES = frozenset(("sec_cik", "external_entity"))
EVIDENCE_NAMESPACES = frozenset(("authority_record", "artifact"))
_OPAQUE = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"
_TOKEN = r"[A-Za-z0-9._:-]{1,64}"
_CIK = r"[0-9]{10}"
_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_INSTANT = (
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})"
)


class ContractError(ValueError):
    """Explicit structural rejection; messages never echo reference payloads."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _text(value, name, max_chars, max_bytes, pattern=None):
    _require(type(value) is str, name + ": expected exact string")
    _require(1 <= len(value) <= max_chars, name + ": character limit")
    _require(value == value.strip(), name + ": boundary whitespace")
    _require(not any(
        unicodedata.category(c) in ("Cc", "Cs")
        or 0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069
        for c in value
    ), name + ": forbidden character")
    _require(len(value.encode("utf-8")) <= max_bytes, name + ": byte limit")
    if pattern is not None:
        _require(re.fullmatch(pattern, value) is not None, name + ": syntax")


def _token(value, name):
    _text(value, name, 64, 64, _TOKEN)


def _cik(value):
    _text(value, "cik", 10, 10, _CIK)
    _require(value != "0000000000", "cik: zero")


def canonical_sec_cik(text):
    """Explicit text-only factory; canonical records/decoder never pad CIKs."""
    _text(text, "cik factory", 10, 10, r"[0-9]{1,10}")
    result = text.zfill(10)
    _cik(result)
    return result


def _date_text(value):
    _text(value, "date", 10, 10, _DATE)
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ContractError("date: invalid calendar date") from None


def _instant_text(value):
    _text(value, "instant", 32, 32, _INSTANT)
    # Some Python versions accept ISO 8601 24:00:00 as next-day midnight.
    # RFC3339 requires 00..23; reject before the library can normalize it.
    _require(int(value[11:13]) <= 23 and int(value[14:16]) <= 59
             and int(value[17:19]) <= 59, "instant: invalid clock time")
    # datetime.fromisoformat accepts offsets outside RFC3339's HH:MM ranges.
    if not value.endswith(("Z", "z")):
        _require(int(value[-5:-3]) <= 23 and int(value[-2:]) <= 59,
                 "instant: invalid offset")
    try:
        utc = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ContractError("instant: invalid date/time or UTC overflow") from None
    return utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _pin(value):
    _require(type(value) is int and 0 <= value <= MAX_PIN, "pin: invalid integer")


def _key(value, namespaces, nullable=False):
    if value is None and nullable:
        return
    _require(type(value) is KeyRef, "key: expected KeyRef")
    _require(value.namespace in namespaces, "key: wrong namespace")


def _tuple(value, item_type, maximum, name, identity=None):
    _require(type(value) is tuple, name + ": expected tuple")
    _require(len(value) <= maximum, name + ": collection limit")
    _require(all(type(x) is item_type for x in value), name + ": wrong member type")
    seen = set()
    for item in value:
        key = item if identity is None else identity(item)
        _require(key not in seen, name + ": duplicate member/identity")
        seen.add(key)


@dataclass(frozen=True, slots=True)
class KeyRef:
    namespace: str
    id: str

    def __post_init__(self):
        _text(self.namespace, "namespace", 32, 32)
        _require(self.namespace in NAMESPACES, "namespace: unsupported")
        _text(self.id, "key id", 128, 128, _OPAQUE)
        if self.namespace == "sec_cik":
            _cik(self.id)


@dataclass(frozen=True, slots=True)
class DateInterval:
    """Half-open [start,end); None end is open, None whole interval is unknown."""

    start: str
    end: str | None

    def __post_init__(self):
        _date_text(self.start)
        if self.end is not None:
            _date_text(self.end)
            _require(self.start < self.end, "interval: empty or reversed")


class TimePoint:
    __slots__ = ()

    @staticmethod
    def unknown():
        return UnknownTimePoint()

    @staticmethod
    def date(value):
        return DateTimePoint(value)

    @staticmethod
    def instant(value):
        return InstantTimePoint(value)


@dataclass(frozen=True, slots=True)
class UnknownTimePoint(TimePoint):
    kind: ClassVar[str] = "unknown"


@dataclass(frozen=True, slots=True)
class DateTimePoint(TimePoint):
    value: str
    kind: ClassVar[str] = "date"

    def __post_init__(self):
        _date_text(self.value)


@dataclass(frozen=True, slots=True)
class InstantTimePoint(TimePoint):
    value: str
    kind: ClassVar[str] = "instant"

    def __post_init__(self):
        object.__setattr__(self, "value", _instant_text(self.value))


_TIMES = (UnknownTimePoint, DateTimePoint, InstantTimePoint)


def _effective(value):
    _require(value is None or type(value) is DateInterval, "effective: expected interval or null")


@dataclass(frozen=True, slots=True)
class AuthorityIdentifier:
    scheme: str
    authority: str
    identifier: str
    evidence_key: KeyRef
    effective: DateInterval | None

    def __post_init__(self):
        _require(type(self.scheme) is str and self.scheme in ("sec_cik", "lei", "authority_id"),
                 "authority scheme: unsupported")
        _token(self.authority, "authority")
        if self.scheme == "sec_cik":
            _require(self.authority == "sec", "cik authority: expected sec")
            _cik(self.identifier)
        elif self.scheme == "lei":
            _text(self.identifier, "lei", 20, 20, r"[A-Z0-9]{20}")
        else:
            _text(self.identifier, "authority identifier", 128, 128, _OPAQUE)
        _key(self.evidence_key, EVIDENCE_NAMESPACES)
        _effective(self.effective)


def _authorities(value):
    _tuple(value, AuthorityIdentifier, 16, "authority_ids",
           lambda a: (a.scheme, a.authority, a.identifier))


class _Root:
    __slots__ = ()

    def _check_bounds(self):
        _bounded_tree(_envelope(self))


@dataclass(frozen=True, slots=True)
class EntityRef(_Root):
    key: KeyRef
    legal_name: str
    jurisdiction: str | None
    cik: str | None
    authority_ids: tuple[AuthorityIdentifier, ...]
    kind: ClassVar[str] = "entity"

    def __post_init__(self):
        _key(self.key, ENTITY_NAMESPACES)
        _text(self.legal_name, "legal_name", 200, 800)
        if self.jurisdiction is not None:
            _text(self.jurisdiction, "jurisdiction", 2, 2, r"[A-Z]{2}")
        if self.key.namespace == "sec_cik":
            _cik(self.cik)
            _require(self.key.id == self.cik, "entity: CIK/key mismatch")
        else:
            _require(self.cik is None, "external entity: cik must be null")
        _authorities(self.authority_ids)
        for item in self.authority_ids:
            if item.scheme == "sec_cik":
                _require(item.identifier == self.cik, "entity: authority CIK mismatch")
        self._check_bounds()


@dataclass(frozen=True, slots=True)
class SecurityRef(_Root):
    key: KeyRef
    issuer_key: KeyRef
    share_class: str
    authority_ids: tuple[AuthorityIdentifier, ...]
    kind: ClassVar[str] = "security"

    def __post_init__(self):
        _key(self.key, ("security",))
        _key(self.issuer_key, ENTITY_NAMESPACES)
        _text(self.share_class, "share_class", 64, 256)
        _authorities(self.authority_ids)
        _require(all(a.scheme == "authority_id" for a in self.authority_ids),
                 "security: issuer authority scheme")
        self._check_bounds()


@dataclass(frozen=True, slots=True)
class SymbolAlias:
    provider: str
    product: str
    symbol: str
    effective: DateInterval | None
    evidence_key: KeyRef

    def __post_init__(self):
        _token(self.provider, "provider")
        _token(self.product, "product")
        _text(self.symbol, "symbol", 64, 64, r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,63}")
        _effective(self.effective)
        _key(self.evidence_key, EVIDENCE_NAMESPACES)


def _aliases(value):
    _tuple(value, SymbolAlias, 64, "aliases")
    for index, alias in enumerate(value):
        for other in value[:index]:
            if (alias.provider, alias.product, alias.symbol) != (
                other.provider, other.product, other.symbol
            ):
                continue
            a, b = alias.effective, other.effective
            _require(a is not None and b is not None, "aliases: unknown disjointness")
            disjoint = ((a.end is not None and a.end <= b.start)
                        or (b.end is not None and b.end <= a.start))
            _require(disjoint, "aliases: overlapping intervals")


@dataclass(frozen=True, slots=True)
class ListingRef(_Root):
    key: KeyRef
    security_key: KeyRef
    mic: str
    currency: str
    calendar_key: KeyRef
    calendar_version: str
    effective: DateInterval | None
    aliases: tuple[SymbolAlias, ...]
    kind: ClassVar[str] = "listing"

    def __post_init__(self):
        _key(self.key, ("listing",))
        _key(self.security_key, ("security",))
        _text(self.mic, "mic", 4, 4, r"[A-Z0-9]{4}")
        _text(self.currency, "currency", 3, 3, r"[A-Z]{3}")
        _key(self.calendar_key, ("calendar",))
        _token(self.calendar_version, "calendar_version")
        _effective(self.effective)
        _aliases(self.aliases)
        self._check_bounds()


@dataclass(frozen=True, slots=True)
class IdentityResolution(_Root):
    status: str
    candidate_keys: tuple[KeyRef, ...]
    evidence_keys: tuple[KeyRef, ...]
    reason_code: str
    kind: ClassVar[str] = "identity_resolution"

    def __post_init__(self):
        _require(type(self.status) is str and self.status in ("resolved", "ambiguous", "unresolved"),
                 "resolution: unsupported status")
        _tuple(self.candidate_keys, KeyRef, 16, "candidate_keys")
        _tuple(self.evidence_keys, KeyRef, 16, "evidence_keys")
        for key in self.candidate_keys:
            _key(key, ENTITY_NAMESPACES)
        for key in self.evidence_keys:
            _key(key, EVIDENCE_NAMESPACES)
        count = len(self.candidate_keys)
        _require((self.status == "resolved" and count == 1)
                 or (self.status == "ambiguous" and 2 <= count <= 16)
                 or (self.status == "unresolved" and count == 0), "resolution: candidate count")
        _require(self.status == "unresolved" or len(self.evidence_keys) >= 1,
                 "resolution: missing evidence")
        _token(self.reason_code, "reason_code")
        self._check_bounds()


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceRef(_Root):
    """Common fields only; instantiate a closed concrete variant, never this base."""

    entity_key: KeyRef
    origin: str
    owner_key: KeyRef | None
    session_key: KeyRef | None
    source_descriptor_key: KeyRef | None
    source_revision_key: KeyRef | None
    rights_policy_key: KeyRef | None
    admission_record_key: KeyRef | None
    public_available_at: TimePoint
    retrieved_at: TimePoint

    def __post_init__(self):
        _require(type(self) in _EVIDENCE_TYPES, "evidence: concrete variant required")
        _key(self.entity_key, ENTITY_NAMESPACES)
        _require(type(self.origin) is str, "origin: expected exact string")
        for name, namespace in (
            ("owner_key", "principal"), ("session_key", "session"),
            ("source_descriptor_key", "source_descriptor"),
            ("source_revision_key", "source_revision"),
            ("rights_policy_key", "rights_policy"), ("admission_record_key", "admission_record"),
        ):
            _key(getattr(self, name), (namespace,), nullable=True)
        for value in (self.public_available_at, self.retrieved_at):
            _require(type(value) in _TIMES, "time: expected closed TimePoint")


@dataclass(frozen=True, slots=True, kw_only=True)
class DatabasePublicationRef(EvidenceRef):
    accession: str
    publication_data_version: int
    evidence_version: int
    data_version: int
    manifest_sha256: str
    chunk_id: str | None
    kind: ClassVar[str] = "database_publication"

    def __post_init__(self):
        EvidenceRef.__post_init__(self)
        _key(self.entity_key, ("sec_cik",))
        _require(self.origin == "sec" and self.owner_key is None and self.session_key is None,
                 "database publication: origin/owner/session")
        _text(self.accession, "accession", 20, 20, r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
        for pin in (self.publication_data_version, self.evidence_version, self.data_version):
            _pin(pin)
        _require(self.publication_data_version <= self.evidence_version <= self.data_version,
                 "database publication: pin order")
        _digest(self.manifest_sha256)
        if self.chunk_id is not None:
            _text(self.chunk_id, "chunk_id", 50, 50, _OPAQUE)
        self._check_bounds()


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionArtifactRef(EvidenceRef):
    artifact_key: KeyRef
    artifact_sha256: str
    kind: ClassVar[str] = "session_artifact"

    def __post_init__(self):
        EvidenceRef.__post_init__(self)
        _require(self.origin in ("official_sec", "official_issuer", "official_exchange",
                                 "official_regulator", "user_upload"), "session artifact: origin")
        _key(self.owner_key, ("principal",))
        _key(self.session_key, ("session",))
        _key(self.source_descriptor_key, ("source_descriptor",))
        _key(self.artifact_key, ("artifact",))
        _digest(self.artifact_sha256)
        self._check_bounds()


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketPublicationRef(EvidenceRef):
    security_key: KeyRef
    listing_key: KeyRef
    market_publication_key: KeyRef
    market_data_version: int
    manifest_sha256: str
    kind: ClassVar[str] = "market_publication"

    def __post_init__(self):
        EvidenceRef.__post_init__(self)
        _require(self.origin == "market_provider", "market publication: origin")
        _require(self.session_key is None or self.owner_key is not None,
                 "market publication: session requires owner")
        _key(self.source_descriptor_key, ("source_descriptor",))
        _key(self.security_key, ("security",))
        _key(self.listing_key, ("listing",))
        _key(self.market_publication_key, ("market_publication",))
        _pin(self.market_data_version)
        _digest(self.manifest_sha256)
        self._check_bounds()


def _digest(value):
    _text(value, "sha256", 64, 64, r"[0-9a-f]{64}")


_EVIDENCE_TYPES = (DatabasePublicationRef, SessionArtifactRef, MarketPublicationRef)
_ROOT_TYPES = (EntityRef, SecurityRef, ListingRef, IdentityResolution) + _EVIDENCE_TYPES
_VALUE_TYPES = (KeyRef, DateInterval, AuthorityIdentifier, SymbolAlias) + _TIMES + _ROOT_TYPES


def check_reference_context(record, *, entity=None, security=None, listing=None,
                            expected_owner_key=None, expected_session_key=None,
                            expected_entity_key=None, expected_security_key=None,
                            expected_listing_key=None):
    """Compare explicitly supplied records/keys; returns no authorization decision.

    Omitted records are not resolved. Expected owner/session None checks public/null
    context as well; private references require explicit owner AND session keys.
    """
    _require(type(record) in _ROOT_TYPES, "context: expected root record")
    for value, cls in ((entity, EntityRef), (security, SecurityRef), (listing, ListingRef)):
        _require(value is None or type(value) is cls, "context: wrong reference type")
    for value, spaces in ((expected_owner_key, ("principal",)),
                          (expected_session_key, ("session",)),
                          (expected_entity_key, ENTITY_NAMESPACES),
                          (expected_security_key, ("security",)),
                          (expected_listing_key, ("listing",))):
        _key(value, spaces, nullable=True)

    # Include the checked root itself in a supplied relationship chain.
    for cls, supplied in ((EntityRef, entity), (SecurityRef, security), (ListingRef, listing)):
        if type(record) is cls and supplied is not None:
            _require(record == supplied, "context: conflicting record metadata")
    entity = record if type(record) is EntityRef else entity
    security = record if type(record) is SecurityRef else security
    listing = record if type(record) is ListingRef else listing
    entity_keys = [x for x in (
        entity.key if entity else None, security.issuer_key if security else None,
        record.entity_key if type(record) in _EVIDENCE_TYPES else None,
    ) if x is not None]
    security_keys = [x for x in (
        security.key if security else None, listing.security_key if listing else None,
        record.security_key if type(record) is MarketPublicationRef else None,
    ) if x is not None]
    listing_keys = [x for x in (
        listing.key if listing else None,
        record.listing_key if type(record) is MarketPublicationRef else None,
    ) if x is not None]
    for keys, expected in ((entity_keys, expected_entity_key),
                           (security_keys, expected_security_key),
                           (listing_keys, expected_listing_key)):
        if expected is not None:
            _require(bool(keys), "context: relationship unavailable")
            keys.append(expected)
        _require(not keys or all(x == keys[0] for x in keys), "context: relationship mismatch")
    if type(record) in _EVIDENCE_TYPES:
        _require(record.owner_key == expected_owner_key, "context: owner mismatch")
        _require(record.session_key == expected_session_key, "context: session mismatch")


def _wire(value):
    if type(value) in _VALUE_TYPES:
        result = {f.name: _wire(getattr(value, f.name)) for f in fields(value)}
        if type(value) in _TIMES + _ROOT_TYPES:
            result["kind"] = value.kind
        return result
    if type(value) is tuple:
        return [_wire(x) for x in value]
    _require(value is None or type(value) in (str, int), "wire: unsupported type")
    return value


def _envelope(record):
    return {"schema_version": 1, "record": _wire(record)}


def _bounded_tree(tree):
    """Apply the same logical depth/node/byte limits to direct constructors."""
    count = 0

    def visit(value, depth):
        nonlocal count
        count += 1
        _require(count <= MAX_NODES, "json: node limit")
        if type(value) in (dict, list):
            _require(depth <= MAX_DEPTH, "json: depth limit")
            if type(value) is dict:
                for key, item in value.items():
                    visit(key, depth + 1)
                    visit(item, depth + 1)
            else:
                for item in value:
                    visit(item, depth + 1)

    visit(tree, 1)
    result = json.dumps(tree, ensure_ascii=False, allow_nan=False,
                        sort_keys=True, separators=(",", ":")).encode("utf-8")
    _require(len(result) <= MAX_BYTES, "json: byte limit")
    return result


def encode(record):
    """Return deterministic UTF-8 bytes for one exact closed root value."""
    _require(type(record) in _ROOT_TYPES, "encode: expected root record")
    return _bounded_tree(_envelope(record))


def _preflight(data):
    _require(type(data) is bytes, "decode: expected exact bytes")
    _require(len(data) <= MAX_BYTES, "json: byte limit")
    _require(not data.startswith(b"\xef\xbb\xbf"), "json: BOM forbidden")
    depth, quoted, escaped = 0, False, False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (123, 91):
            depth += 1
            _require(depth <= MAX_DEPTH, "json: depth limit")
        elif byte in (125, 93):
            depth -= 1
            _require(depth >= 0, "json: unbalanced container")
    _require(not quoted and depth == 0, "json: unterminated string/container")


class _Parser:
    """Bounded recursive descent: count nodes before allocating/retaining them.

    scanstring handles only one bounded JSON string. Duplicate names are rejected
    before dict insertion. No json.loads full-tree or coercive float parser is used.
    """

    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.nodes = 0

    def _space(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \r\n\t":
            self.pos += 1

    def _node(self):
        self.nodes += 1
        _require(self.nodes <= MAX_NODES, "json: node limit")

    def _string(self):
        self._node()
        try:
            value, self.pos = json.decoder.scanstring(self.text, self.pos + 1, True)
        except ValueError:
            raise ContractError("json: invalid string") from None
        # Even member names that would later fail shape checks cannot carry these.
        _require(not any(unicodedata.category(c) in ("Cc", "Cs")
                         or 0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069
                         for c in value), "json: forbidden string character")
        return value

    def value(self, depth=1):
        self._space()
        _require(self.pos < len(self.text), "json: missing value")
        char = self.text[self.pos]
        if char == '"':
            return self._string()
        self._node()
        if char in "{[":
            _require(depth <= MAX_DEPTH, "json: depth limit")
            self.pos += 1
            is_object = char == "{"
            result = {} if is_object else []
            closing = "}" if is_object else "]"
            self._space()
            if self.pos < len(self.text) and self.text[self.pos] == closing:
                self.pos += 1
                return result
            while True:
                self._space()
                if is_object:
                    _require(self.pos < len(self.text) and self.text[self.pos] == '"',
                             "json: expected member name")
                    key = self._string()
                    _require(key not in result, "json: duplicate member name")
                    self._space()
                    _require(self.pos < len(self.text) and self.text[self.pos] == ":",
                             "json: expected colon")
                    self.pos += 1
                    result[key] = self.value(depth + 1)
                else:
                    result.append(self.value(depth + 1))
                self._space()
                _require(self.pos < len(self.text), "json: unterminated container")
                separator = self.text[self.pos]
                self.pos += 1
                if separator == closing:
                    return result
                _require(separator == ",", "json: expected comma")
        for token, value in (("null", None), ("true", True), ("false", False)):
            if self.text.startswith(token, self.pos):
                self.pos += len(token)
                return value
        if char in "0123456789-":
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] not in " \t\r\n,]}":
                self.pos += 1
            token = self.text[start:self.pos]
            _require(1 <= len(token) <= 16 and re.fullmatch(r"0|[1-9][0-9]{0,15}", token)
                     is not None, "json: invalid integer token")
            number = int(token)
            _pin(number)
            return number
        raise ContractError("json: invalid value")


def _shape(value, expected):
    _require(type(value) is dict and value.keys() == set(expected), "schema: exact fields required")


def _nested(value, cls):
    _shape(value, (f.name for f in fields(cls)))
    args = dict(value)
    if cls in (AuthorityIdentifier, SymbolAlias):
        args["evidence_key"] = _nested(args["evidence_key"], KeyRef)
        args["effective"] = _interval(args["effective"])
    return cls(**args)


def _interval(value):
    return None if value is None else _nested(value, DateInterval)


def _time(value):
    _require(type(value) is dict and type(value.get("kind")) is str, "time: expected kind")
    cls = {"unknown": UnknownTimePoint, "date": DateTimePoint,
           "instant": InstantTimePoint}.get(value["kind"])
    _require(cls is not None, "time: unsupported kind")
    _shape(value, ("kind",) if cls is UnknownTimePoint else ("kind", "value"))
    return cls() if cls is UnknownTimePoint else cls(value["value"])


def _array(value, cls, maximum, name):
    _require(type(value) is list and len(value) <= maximum, name + ": expected bounded array")
    return tuple(_nested(x, cls) for x in value)


def _record(value):
    _require(type(value) is dict and type(value.get("kind")) is str, "record: expected kind")
    cls = {c.kind: c for c in _ROOT_TYPES}.get(value["kind"])
    _require(cls is not None, "record: unsupported kind")
    _shape(value, ["kind"] + [f.name for f in fields(cls)])
    args = {name: item for name, item in value.items() if name != "kind"}
    for name in args:
        if name == "key" or name.endswith("_key"):
            args[name] = None if args[name] is None else _nested(args[name], KeyRef)
        elif name == "authority_ids":
            args[name] = _array(args[name], AuthorityIdentifier, 16, name)
        elif name == "aliases":
            args[name] = _array(args[name], SymbolAlias, 64, name)
        elif name in ("candidate_keys", "evidence_keys"):
            args[name] = _array(args[name], KeyRef, 16, name)
        elif name == "effective":
            args[name] = _interval(args[name])
        elif name in ("public_available_at", "retrieved_at"):
            args[name] = _time(args[name])
    return cls(**args)


def decode(data):
    """Decode bounded v1 bytes into fresh immutable, still-untrusted references."""
    _preflight(data)
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise ContractError("json: invalid UTF-8") from None
    parser = _Parser(text)
    envelope = parser.value()
    parser._space()
    _require(parser.pos == len(text), "json: trailing content")
    _shape(envelope, ("schema_version", "record"))
    _require(type(envelope["schema_version"]) is int and envelope["schema_version"] == 1,
             "schema: unsupported version")
    return _record(envelope["record"])
