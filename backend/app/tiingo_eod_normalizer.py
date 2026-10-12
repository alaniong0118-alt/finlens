"""Bounded offline Tiingo EOD JSON normalization; no acquisition or persistence.

The task's documented fields do not prove corporate-action completeness. Every
result is blocked and its canonical publication is missing/unsupported, never
complete. Raw closes alone enter PriceObservation; OHLCV and adjusted values stay
in an immutable, digest-bound sidecar. No return calculations are implemented.

The supported fixture format declares splitFactor as new shares / old share
(2 = 2-for-1, 0.1 = 1-for-10). The declaration must be supplied explicitly and
is NOT provider authentication or independently verified production semantics.
divCash is retained on its ex-date label with UNVERIFIED share basis and economic
classification. It never becomes an ordinary/gross-cash canonical dividend.
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, DecimalException
import hashlib
import json
import re

from app.market_data_contracts import (
    ExchangeCalendar, Listing, MAX_SESSIONS, MarketContractError, MarketPublication,
    PriceObservation, PublicationPin, Security, Source, SymbolMapping, decimal_input,
    identifier, require, seal_publication, validate_publication,
)

NORMALIZER_VERSION = "tiingo-eod-offline-v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_COVERAGE_DAYS = 10000
FIELDS = frozenset(("date", "open", "high", "low", "close", "volume", "adjOpen",
                    "adjHigh", "adjLow", "adjClose", "adjVolume", "divCash", "splitFactor"))


@dataclass(frozen=True)
class TiingoEodFormat:
    split_factor_direction: str
    declaration_reference: str
    dividend_share_basis: str = "unverified"


@dataclass(frozen=True)
class TiingoEodRequest:
    symbol: str
    security: Security
    listing: Listing
    mappings: tuple[SymbolMapping, ...]
    calendar: ExchangeCalendar
    coverage_start: date
    coverage_end: date
    source: Source
    publication_id: str
    market_data_version: int
    published_at: datetime
    format: TiingoEodFormat
    predecessor_pin: PublicationPin | None = None


@dataclass(frozen=True)
class Ohlcv:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class TiingoEodBar:
    listing_id: str
    session_date: date
    provider_timestamp: datetime  # UTC-midnight date label, NOT the session close.
    raw: Ohlcv
    adjusted: Ohlcv
    div_cash: Decimal
    split_factor: Decimal


@dataclass(frozen=True)
class TiingoEodNormalization:
    status: str
    reasons: tuple[str, ...]
    bars: tuple[TiingoEodBar, ...]
    normalized_content_sha256: str
    publication: MarketPublication
    format: TiingoEodFormat


def _number(token):
    require(len(token) <= 96, "unbounded_numeric_token")
    try:
        value = Decimal(token)
    except DecimalException:
        raise MarketContractError("invalid_numeric_token") from None
    require(decimal_input(value) and abs(value.as_tuple().exponent) <= 45, "invalid_numeric_value")
    return value


def _nonfinite(_token):
    raise MarketContractError("nonfinite_numeric_value")


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_field")
        result[key] = value
    return result


def parse_tiingo_eod(payload):
    """Provider-only validation. Input MUST be original JSON bytes, never floats.

    Repeated dates, even identical rows, reject instead of selecting a vintage.
    UTC midnight labels permit Z/+00:00 and zero fractional seconds only.
    """
    require(type(payload) is bytes and 0 < len(payload) <= MAX_RESPONSE_BYTES, "invalid_response_bound")
    try:
        rows = json.loads(payload.decode("utf-8"), parse_float=_number, parse_int=_number,
                          parse_constant=_nonfinite, object_pairs_hook=_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise MarketContractError("invalid_response_json") from None
    require(isinstance(rows, list) and len(rows) <= MAX_SESSIONS, "invalid_response_inventory")
    parsed, dates = [], set()
    for row in rows:
        require(isinstance(row, dict), "invalid_eod_row")
        require(FIELDS <= row.keys(), "missing_eod_field")
        require(row.keys() <= FIELDS, "unsupported_eod_field")
        stamp = row["date"]
        require(isinstance(stamp, str) and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T00:00:00(?:\.0{1,6})?(?:Z|\+00:00)", stamp) is not None,
            "invalid_eod_date_label")
        try:
            day = date.fromisoformat(stamp[:10])
        except ValueError:
            raise MarketContractError("invalid_eod_date_label") from None
        require(day not in dates, "duplicate_eod_observation")
        dates.add(day)
        require(all(decimal_input(row[field]) for field in FIELDS - {"date"}), "invalid_eod_numeric_type")
        raw = Ohlcv(*(row[field] for field in ("open", "high", "low", "close", "volume")))
        adjusted = Ohlcv(*(row[field] for field in ("adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume")))
        for values in (raw, adjusted):
            require(all(value > 0 for value in (values.open, values.high, values.low, values.close)), "nonpositive_ohlc")
            require(values.low <= min(values.open, values.close) <= max(values.open, values.close) <= values.high,
                    "inconsistent_ohlc")
            require(values.volume >= 0, "negative_volume")
        require(raw.volume == raw.volume.to_integral_value(), "fractional_raw_volume")
        require(row["divCash"] >= 0 and row["splitFactor"] > 0, "invalid_action_indicator")
        parsed.append((day, datetime(day.year, day.month, day.day, tzinfo=timezone.utc), raw, adjusted,
                       row["divCash"], row["splitFactor"]))
    return tuple(sorted(parsed, key=lambda item: item[0]))


def _canonical(value):
    if isinstance(value, Decimal):
        text = format(value, "f")
        return "0" if value == 0 else text.rstrip("0").rstrip(".") if "." in text else text
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def _digest(value):
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _publication(request, bars, content_digest, state):
    pin = request.predecessor_pin
    prices = tuple(PriceObservation((f"tiingo-eod:{bar.listing_id}:{bar.session_date}:{content_digest}",),
        bar.listing_id, bar.session_date, bar.raw.close, request.listing.currency, "raw", (request.source,)) for bar in bars)
    return seal_publication(MarketPublication(
        request.publication_id, request.market_data_version, pin.publication_id if pin else None,
        request.published_at, "retrospective_revised", state, request.security, request.listing,
        request.mappings, request.calendar, prices, (), (), request.source, NORMALIZER_VERSION,
        predecessor_market_data_version=pin.market_data_version if pin else None,
        predecessor_manifest_sha256=pin.manifest_sha256 if pin else None))


def _validate_request(request, predecessor):
    require(isinstance(request, TiingoEodRequest), "invalid_tiingo_request")
    require(isinstance(request.format, TiingoEodFormat) and identifier(request.format.declaration_reference),
            "missing_format_declaration")
    require(request.format.split_factor_direction == "new_shares_per_old_share", "unsupported_split_direction")
    require(request.format.dividend_share_basis == "unverified", "unsupported_dividend_basis")
    require(isinstance(request.source, Source) and (request.source.provider, request.source.product) == ("tiingo", "eod"),
            "incompatible_provider_product")
    require(identifier(request.symbol), "invalid_request_symbol")
    require(isinstance(request.calendar, ExchangeCalendar) and isinstance(request.listing, Listing), "invalid_request_identity")
    require(type(request.coverage_start) is date and type(request.coverage_end) is date
            and (request.coverage_start, request.coverage_end) == (request.calendar.covered_start, request.calendar.covered_end),
            "incompatible_response_coverage")
    require(0 <= (request.coverage_end - request.coverage_start).days <= MAX_COVERAGE_DAYS,
            "unbounded_response_coverage")
    require(request.predecessor_pin is None or isinstance(request.predecessor_pin, PublicationPin), "invalid_predecessor_pin")
    # Existing validators own company/listing/unit/calendar/source/version checks.
    validate_publication(_publication(request, (), "", "missing"), predecessor)
    eligible = {s.session_date for s in request.calendar.sessions
                if request.listing.first_session <= s.session_date <= (request.listing.last_session or date.max)}
    require(eligible, "empty_listing_coverage")
    require(all(sum(m.symbol == request.symbol and m.effective_from <= day <= (m.effective_to or date.max)
                    for m in request.mappings) == 1 for day in eligible), "incompatible_request_symbol")
    return eligible


def normalize_tiingo_eod(payload, request, *, predecessor=None):
    """Build validated blocked publication; no caller flag can assert completeness.

    Request metadata binds a symbol to the supplied payload but does not prove
    its provider origin: EOD rows contain no instrument identity. A future trusted
    acquisition layer must verify the actual request/response and independent
    corporate-action inventory. Hashes and format-reference strings do not do so.
    """
    require(type(payload) is bytes and 0 < len(payload) <= MAX_RESPONSE_BYTES, "invalid_response_bound")
    try:
        eligible = _validate_request(request, predecessor)
    except MarketContractError:
        raise
    except (TypeError, AttributeError, ValueError, OverflowError):
        raise MarketContractError("invalid_tiingo_request") from None
    require(hashlib.sha256(payload).hexdigest() == request.source.response_sha256, "response_fingerprint_mismatch")
    parsed = parse_tiingo_eod(payload)
    require(all(item[0] in eligible for item in parsed), "eod_date_outside_listing_calendar")
    bars = tuple(TiingoEodBar(request.listing.listing_id, *item) for item in parsed)
    content_digest = _digest(dict(normalizer_version=NORMALIZER_VERSION, symbol=request.symbol,
        security=asdict(request.security), listing=asdict(request.listing),
        mappings=sorted((asdict(m) for m in request.mappings), key=lambda m: (m["symbol"], m["effective_from"])),
        calendar=asdict(request.calendar), coverage_start=request.coverage_start, coverage_end=request.coverage_end,
        format=asdict(request.format), bars=[asdict(bar) for bar in bars]))
    reasons = {"missing_corporate_action_coverage"}
    if not bars:
        reasons.add("empty_eod_response")
    if {bar.session_date for bar in bars} != eligible:
        reasons.add("missing_session_observations")
    if request.listing.continuity != "same_security_verified":
        reasons.add("unsupported_security_continuity")
    for bar in bars:
        if bar.split_factor != 1:
            reasons.add("unverified_split_event")
        if bar.div_cash > 0:
            reasons.add("unclassified_cash_distribution")
        if bar.split_factor != 1 and bar.div_cash > 0:
            reasons.add("ambiguous_same_day_actions")
        if bar.raw != bar.adjusted:
            reasons.add("unexplained_adjustment_difference")
    unsupported = reasons - {"missing_corporate_action_coverage", "empty_eod_response", "missing_session_observations"}
    publication = _publication(request, bars, content_digest, "unsupported" if unsupported else "missing")
    validate_publication(publication, predecessor)
    return TiingoEodNormalization("blocked", tuple(sorted(reasons)), bars, content_digest, publication, request.format)
