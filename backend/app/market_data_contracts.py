"""Immutable offline market inputs. No provider, database or SEC dependencies.

Hashes bind supplied bytes/manifests, not the truth of a provider's observations.
Calendars and action-completeness attestations must be supplied, never inferred.
"""
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from zoneinfo import ZoneInfo

CALCULATION_VERSION = "raw-close-ex-date-v1"
PRECISION_VERSION = "decimal80-final18-half-even-v1"
MAX_SESSIONS = 6000


class MarketContractError(ValueError):
    """Stable rejection code; invalid inputs cannot become numeric results."""


def require(condition, reason):
    if not condition:
        raise MarketContractError(reason)


def aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def identifier(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def decimal_input(value):
    # Floats/coercions are forbidden. Bound significant digits and magnitude.
    return (isinstance(value, Decimal) and value.is_finite()
            and len(value.as_tuple().digits) <= 28
            and (value == 0 or -18 <= value.adjusted() <= 18))


@dataclass(frozen=True)
class Security:
    security_id: str
    company_id: int
    issuer_cik: str
    share_class: str


@dataclass(frozen=True)
class Listing:
    listing_id: str
    security_id: str
    mic: str
    currency: str
    calendar_id: str
    first_session: date
    last_session: date | None = None
    continuity: str = "unresolved"


@dataclass(frozen=True)
class SymbolMapping:
    provider: str
    product: str
    symbol: str
    ticker: str
    security_id: str
    listing_id: str
    mic: str
    effective_from: date
    effective_to: date | None
    identity_resolved: bool
    identity_evidence: str


@dataclass(frozen=True)
class TradingSession:
    session_date: date
    close_at: datetime


@dataclass(frozen=True)
class ExchangeCalendar:
    calendar_id: str
    version: str
    timezone: str
    close_convention: str
    covered_start: date
    covered_end: date
    sessions: tuple[TradingSession, ...]


@dataclass(frozen=True)
class Source:
    provider: str
    product: str
    source_id: str
    response_sha256: str
    retrieved_at: datetime
    available_at: datetime | None


@dataclass(frozen=True)
class PriceObservation:
    observation_ids: tuple[str, ...]
    listing_id: str
    session_date: date
    close: Decimal
    currency: str
    adjustment_basis: str
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class CorporateAction:
    action_id: str
    listing_id: str
    kind: str
    effective_date: date
    ex_date: date | None
    sources: tuple[Source, ...]
    sequence: int | None = None
    split_numerator: Decimal | None = None
    split_denominator: Decimal | None = None
    cash_amount: Decimal | None = None
    currency: str | None = None
    entitlement_basis: str | None = None
    basis_split_id: str | None = None
    treatment: str | None = None


@dataclass(frozen=True)
class ActionCoverage:
    start: date
    end: date
    state: str
    splits_complete: bool
    cash_complete: bool
    other_actions_complete: bool
    source: Source


@dataclass(frozen=True)
class Manifest:
    price_count: int
    action_count: int
    mapping_count: int
    session_count: int
    coverage_count: int
    sha256: str


@dataclass(frozen=True)
class MarketPublication:
    publication_id: str
    market_data_version: int
    supersedes: str | None
    published_at: datetime
    knowledge_mode: str  # retrospective_revised or observed_as_of; not a PIT proof.
    state: str
    security: Security
    listing: Listing
    mappings: tuple[SymbolMapping, ...]
    calendar: ExchangeCalendar
    prices: tuple[PriceObservation, ...]
    actions: tuple[CorporateAction, ...]
    action_coverage: tuple[ActionCoverage, ...]
    source: Source
    normalizer_version: str
    calculation_version: str = CALCULATION_VERSION
    precision_version: str = PRECISION_VERSION
    manifest: Manifest | None = None
    predecessor_market_data_version: int | None = None
    predecessor_manifest_sha256: str | None = None


@dataclass(frozen=True)
class PublicationPin:
    publication_id: str
    market_data_version: int
    manifest_sha256: str


@dataclass(frozen=True)
class DatasetPin:
    security_ids: tuple[str, ...]
    publications: tuple[PublicationPin, ...]
    universe_version: str
    universe_basis: str = "present_day_curated"  # No survivorship-free claim.


@dataclass(frozen=True)
class LabelWindow:
    prediction_at: datetime
    start_at: datetime
    end_at: datetime
    available_at: datetime


def _canonical(value):
    if isinstance(value, Decimal):
        require(value.is_finite(), "nonfinite_value")
        text = format(value, "f")
        return "0" if value == 0 else text.rstrip("0").rstrip(".") if "." in text else text
    if isinstance(value, datetime) and aware(value):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def _json(value):
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def manifest_for(publication):
    """Bind every supplied raw record, identity, calendar, version and receipt.

    Raw duplicates remain counted and fingerprinted even when calculations dedupe.
    Input inventory order is immaterial; calendar session order is contractual.
    """
    payload = asdict(publication)
    del payload["manifest"]
    for name in ("prices", "actions", "mappings", "action_coverage"):
        payload[name] = sorted(payload[name], key=_json)
    return Manifest(len(publication.prices), len(publication.actions), len(publication.mappings),
                    len(publication.calendar.sessions), len(publication.action_coverage),
                    hashlib.sha256(_json(payload).encode("utf-8")).hexdigest())


def seal_publication(publication):
    """Offline manifest construction only; this does not authenticate evidence."""
    return replace(publication, manifest=manifest_for(publication))


def validate_symbol_mappings(mappings):
    require(isinstance(mappings, tuple) and 0 < len(mappings) <= 256, "invalid_symbol_mappings")
    for mapping in mappings:
        require(all(identifier(getattr(mapping, name)) for name in
                    ("provider", "product", "symbol", "ticker", "security_id", "listing_id", "identity_evidence")),
                "invalid_symbol_identity")
        require(re.fullmatch(r"[A-Z0-9]{4}", mapping.mic) is not None, "invalid_mapping_mic")
        require(mapping.identity_resolved is True, "unresolved_symbol_identity")
        require(mapping.effective_to is None or mapping.effective_from <= mapping.effective_to,
                "invalid_mapping_dates")
    ordered = sorted(mappings, key=lambda m: (m.provider, m.product, m.symbol, m.mic, m.effective_from))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            overlap = max(left.effective_from, right.effective_from) <= min(
                left.effective_to or date.max, right.effective_to or date.max)
            require(not (overlap and (left.ticker, left.mic) == (right.ticker, right.mic)
                    and left.security_id != right.security_id), "ambiguous_ticker_identity")
            if (left.provider, left.product) != (right.provider, right.product):
                continue
            same_symbol = (left.symbol, left.mic) == (right.symbol, right.mic)
            same_listing = left.listing_id == right.listing_id
            require(not (overlap and (same_symbol or same_listing)), "ambiguous_symbol_mapping")
    return tuple(ordered)


def _validate_source(source, publication):
    require(isinstance(source, Source), "invalid_source")
    require(all(identifier(getattr(source, name)) for name in ("provider", "product", "source_id")),
            "invalid_source_identity")
    require(re.fullmatch(r"[0-9a-f]{64}", source.response_sha256 or "") is not None, "invalid_source_fingerprint")
    require(aware(source.retrieved_at) and source.retrieved_at <= publication.published_at,
            "invalid_retrieval_time")
    require(source.available_at is None or (aware(source.available_at)
            and source.available_at <= source.retrieved_at), "invalid_source_availability")
    require((source.provider, source.product) == (publication.source.provider, publication.source.product),
            "mixed_provider_product")


def _validate_sources(sources, publication):
    require(isinstance(sources, tuple) and 0 < len(sources) <= 16, "missing_source_provenance")
    for source in sources:
        _validate_source(source, publication)


def _dedupe(records, key, ignored, code):
    groups = {}
    for record in records:
        identity = key(record)
        body = asdict(record)
        for name in ignored:
            del body[name]
        if identity in groups:
            previous = groups[identity]
            old_body = asdict(previous)
            for name in ignored:
                del old_body[name]
            require(body == old_body, code)
            sources = tuple(sorted(set(previous.sources + record.sources), key=lambda s: _json(asdict(s))))
            if isinstance(record, PriceObservation):
                ids = tuple(sorted(set(previous.observation_ids + record.observation_ids)))
                groups[identity] = replace(previous, sources=sources, observation_ids=ids)
            else:
                groups[identity] = replace(previous, sources=sources)
        else:
            groups[identity] = record
    return tuple(groups[key] for key in sorted(groups))


def normalized_records(publication):
    prices = _dedupe(publication.prices, lambda p: (p.listing_id, p.session_date),
                     ("sources", "observation_ids"), "conflicting_price_observations")
    actions = _dedupe(publication.actions, lambda a: a.action_id,
                      ("sources",), "conflicting_corporate_actions")
    return prices, actions


def _validate_publication_body(publication):
    require(isinstance(publication, MarketPublication), "invalid_publication")
    require(identifier(publication.publication_id) and type(publication.market_data_version) is int
            and publication.market_data_version >= 0, "invalid_market_version")
    require(publication.supersedes is None or (identifier(publication.supersedes)
            and publication.supersedes != publication.publication_id), "invalid_supersession")
    if publication.supersedes is None:
        require(publication.predecessor_market_data_version is None
                and publication.predecessor_manifest_sha256 is None, "unexpected_predecessor_pin")
    else:
        require(type(publication.predecessor_market_data_version) is int
                and publication.predecessor_market_data_version >= 0
                and isinstance(publication.predecessor_manifest_sha256, str)
                and re.fullmatch(r"[0-9a-f]{64}", publication.predecessor_manifest_sha256) is not None,
                "invalid_predecessor_pin")
    require(aware(publication.published_at), "invalid_publication_time")
    require(publication.knowledge_mode in {"retrospective_revised", "observed_as_of"}, "invalid_knowledge_mode")
    require(publication.state in {"complete", "missing", "stale", "conflicting", "unsupported"}, "invalid_publication_state")
    require(publication.calculation_version == CALCULATION_VERSION
            and publication.precision_version == PRECISION_VERSION
            and identifier(publication.normalizer_version), "unsupported_calculation_policy")
    security, listing, calendar = publication.security, publication.listing, publication.calendar
    require(isinstance(security, Security) and isinstance(listing, Listing)
            and isinstance(calendar, ExchangeCalendar), "invalid_identity_contract")
    require(identifier(security.security_id) and type(security.company_id) is int and security.company_id > 0
            and re.fullmatch(r"[0-9]{10}", security.issuer_cik) is not None
            and identifier(security.share_class), "invalid_security_identity")
    require(identifier(listing.listing_id) and listing.listing_id != security.security_id
            and listing.security_id == security.security_id, "security_listing_mismatch")
    require(re.fullmatch(r"[A-Z0-9]{4}", listing.mic) is not None
            and re.fullmatch(r"[A-Z]{3}", listing.currency) is not None, "invalid_listing_market")
    require(listing.last_session is None or listing.first_session <= listing.last_session, "invalid_listing_dates")
    require(listing.continuity in {"same_security_verified", "unresolved"}, "invalid_security_continuity")
    require(calendar.calendar_id == listing.calendar_id and identifier(calendar.version)
            and calendar.close_convention == "regular_session_close", "invalid_calendar_identity")
    require(isinstance(calendar.sessions, tuple) and 0 < len(calendar.sessions) <= MAX_SESSIONS
            and calendar.covered_start <= calendar.covered_end, "invalid_calendar_scope")
    try:
        timezone = ZoneInfo(calendar.timezone)
    except (ValueError, KeyError):
        raise MarketContractError("invalid_calendar_timezone") from None
    dates = []
    for session in calendar.sessions:
        require(isinstance(session, TradingSession), "invalid_session_contract")
        require(aware(session.close_at) and session.close_at.astimezone(timezone).date() == session.session_date,
                "invalid_session_close")
        require(calendar.covered_start <= session.session_date <= calendar.covered_end, "session_outside_calendar")
        dates.append(session.session_date)
    require(dates == sorted(set(dates)), "ambiguous_calendar_sessions")
    closes = {session.session_date: session.close_at for session in calendar.sessions}
    _validate_source(publication.source, publication)
    mappings = validate_symbol_mappings(publication.mappings)
    for mapping in mappings:
        require((mapping.security_id, mapping.listing_id, mapping.mic) ==
                (security.security_id, listing.listing_id, listing.mic), "mapping_security_mismatch")
        require((mapping.provider, mapping.product) == (publication.source.provider, publication.source.product),
                "mixed_provider_product")
    eligible = {day for day in dates if listing.first_session <= day <= (listing.last_session or date.max)}
    require(all(sum(m.effective_from <= day <= (m.effective_to or date.max) for m in mappings) == 1
                for day in eligible), "missing_symbol_mapping")
    for name, cap in (("prices", MAX_SESSIONS), ("actions", 12000), ("action_coverage", MAX_SESSIONS)):
        require(isinstance(getattr(publication, name), tuple) and len(getattr(publication, name)) <= cap,
                "invalid_inventory_bound")
    observation_keys = {}
    for price in publication.prices:
        require(isinstance(price, PriceObservation), "invalid_price_contract")
        require(isinstance(price.observation_ids, tuple) and price.observation_ids
                and all(identifier(item) for item in price.observation_ids), "invalid_observation_identity")
        require(price.listing_id == listing.listing_id and price.session_date in eligible, "price_listing_session_mismatch")
        require(decimal_input(price.close) and price.close > 0, "invalid_raw_close")
        require(price.currency == listing.currency, "currency_mismatch")
        require(price.adjustment_basis == "raw", "adjusted_price_forbidden")
        for observation_id in price.observation_ids:
            key = (price.listing_id, price.session_date)
            require(observation_id not in observation_keys or observation_keys[observation_id] == key,
                    "reused_observation_identity")
            observation_keys[observation_id] = key
        _validate_sources(price.sources, publication)
        close_at = closes[price.session_date]
        require(all(s.retrieved_at >= close_at and (s.available_at is None or s.available_at >= close_at)
                    for s in price.sources), "closing_price_not_yet_available")
    for action in publication.actions:
        require(isinstance(action, CorporateAction), "invalid_action_contract")
        require(identifier(action.action_id) and action.listing_id == listing.listing_id
                and action.effective_date in eligible, "action_listing_session_mismatch")
        require(action.sequence is None or (type(action.sequence) is int and action.sequence >= 0), "invalid_action_sequence")
        require(all(value is None or decimal_input(value) for value in
                    (action.split_numerator, action.split_denominator, action.cash_amount)), "invalid_action_numeric_value")
        require(action.basis_split_id is None or identifier(action.basis_split_id), "invalid_cash_basis_reference")
        _validate_sources(action.sources, publication)
        if action.kind == "split":
            require(decimal_input(action.split_numerator) and action.split_numerator > 0
                    and decimal_input(action.split_denominator) and action.split_denominator > 0, "invalid_split")
            require(all(value is None for value in (action.cash_amount, action.currency, action.entitlement_basis,
                        action.basis_split_id, action.treatment, action.ex_date)), "ambiguous_split_fields")
        elif action.kind in {"cash_dividend", "special_cash_distribution"}:
            require(action.ex_date == action.effective_date, "authoritative_ex_date_required")
            require(decimal_input(action.cash_amount) and action.cash_amount >= 0, "invalid_cash_distribution")
            require(action.currency == listing.currency, "currency_mismatch")
            require(action.split_numerator is None and action.split_denominator is None, "ambiguous_cash_fields")
        else:
            require(identifier(action.kind), "invalid_action_type")  # Explicit unsupported interval, not omission.
    coverage_keys = set()
    pairs = set(zip(sorted(eligible), sorted(eligible)[1:]))
    for coverage in publication.action_coverage:
        require(isinstance(coverage, ActionCoverage), "invalid_coverage_contract")
        require((coverage.start, coverage.end) in pairs, "nonadjacent_action_coverage")
        require((coverage.start, coverage.end) not in coverage_keys, "conflicting_action_coverage")
        coverage_keys.add((coverage.start, coverage.end))
        require(coverage.state in {"complete", "missing", "stale", "conflicting", "unsupported"}
                and all(type(flag) is bool for flag in (coverage.splits_complete, coverage.cash_complete,
                                                       coverage.other_actions_complete)), "invalid_action_coverage")
        _validate_source(coverage.source, publication)
    normalized_records(publication)  # Reject conflicting raw candidates before any selection.
    require(publication.manifest == manifest_for(publication), "incomplete_or_changed_manifest")
    return publication


def validate_publication(publication, predecessor=None):
    """Validate the candidate and supplied immediate predecessor, never infer lineage."""
    _validate_publication_body(publication)
    if predecessor is None:
        require(publication.supersedes is None, "predecessor_required")
    else:
        _validate_publication_body(predecessor)
        require(publication.supersedes == predecessor.publication_id
                and publication.publication_id != predecessor.publication_id
                and publication.market_data_version == predecessor.market_data_version + 1
                and publication.published_at > predecessor.published_at, "invalid_supersession")
        require(publication.predecessor_market_data_version == predecessor.market_data_version
                and publication.predecessor_manifest_sha256 == predecessor.manifest.sha256,
                "predecessor_pin_mismatch")
        require((publication.security, publication.listing) == (predecessor.security, predecessor.listing),
                "unreviewed_security_succession")
        require((publication.source.provider, publication.source.product) ==
                (predecessor.source.provider, predecessor.source.product), "mixed_provider_product")
    return publication


def validate_dataset_pin(publications, pin):
    require(isinstance(publications, tuple) and isinstance(pin, DatasetPin)
            and all(isinstance(p, MarketPublication) for p in publications), "invalid_dataset_pin")
    require(len({p.publication_id for p in publications}) == len(publications), "duplicate_publication_id")
    require(isinstance(pin.security_ids, tuple) and 0 < len(pin.security_ids) <= 35
            and len(set(pin.security_ids)) == len(pin.security_ids)
            and isinstance(pin.publications, tuple) and identifier(pin.universe_version)
            and pin.universe_basis == "present_day_curated", "invalid_universe_pin")
    require(len(publications) == len(pin.security_ids)
            and {p.security.security_id for p in publications} == set(pin.security_ids), "unpinned_security_universe")
    require(all(isinstance(p.manifest, Manifest) and p.manifest == manifest_for(p) for p in publications),
            "incomplete_or_changed_manifest")
    require(all(isinstance(p, PublicationPin) for p in pin.publications), "invalid_publication_pin")
    require(len({p.publication_id for p in pin.publications}) == len(pin.publications),
            "duplicate_publication_id")
    expected = {PublicationPin(p.publication_id, p.market_data_version, p.manifest.sha256) for p in publications}
    require(len(expected) == len(publications) and len(set(pin.publications)) == len(pin.publications)
            and set(pin.publications) == expected, "unpinned_publication_vintage")


def validate_predecessor_inventory(publications, predecessors):
    """An ID names exactly one publication, including the supplied parent inventory."""
    require(isinstance(predecessors, tuple)
            and all(isinstance(p, MarketPublication) for p in predecessors), "invalid_predecessor_inventory")
    require(len({p.publication_id for p in predecessors}) == len(predecessors), "ambiguous_predecessor")
    current = {p.publication_id: p for p in publications}
    require(all(p.publication_id not in current or p == current[p.publication_id] for p in predecessors),
            "duplicate_publication_id")


def validate_prediction_cutoff(publications, pin, cutoff, predecessors=()):
    """Conservative eligibility check; caller assertions are not PIT certification."""
    require(aware(cutoff), "invalid_prediction_cutoff")
    validate_dataset_pin(publications, pin)
    validate_predecessor_inventory(publications, predecessors)
    for publication in publications:
        parent = next((p for p in predecessors if p.publication_id == publication.supersedes), None)
        validate_publication(publication, parent)
        require(publication.knowledge_mode == "observed_as_of", "retrospective_data_not_point_in_time")
        require(publication.published_at <= cutoff, "revision_after_cutoff")
        closes = {s.session_date: s.close_at for s in publication.calendar.sessions}
        sources = [publication.source, *(c.source for c in publication.action_coverage)]
        for record in (*publication.prices, *publication.actions):
            sources.extend(record.sources)
            economic_date = record.session_date if isinstance(record, PriceObservation) else record.effective_date
            require(closes[economic_date] <= cutoff, "economic_event_after_cutoff")
        for source in sources:
            require(source.available_at is not None and aware(source.available_at)
                    and source.available_at <= cutoff and source.retrieved_at <= cutoff, "source_not_known_at_cutoff")


def validate_training_labels(labels, training_cutoff):
    require(aware(training_cutoff), "invalid_training_cutoff")
    for label in labels:
        require(all(aware(time) for time in (label.prediction_at, label.start_at, label.end_at, label.available_at))
                and label.prediction_at <= label.start_at <= label.end_at <= label.available_at
                and label.prediction_at < label.end_at,
                "invalid_forward_label_window")
        require(label.end_at <= training_cutoff and label.available_at <= training_cutoff,
                "forward_label_crosses_training_cutoff")
