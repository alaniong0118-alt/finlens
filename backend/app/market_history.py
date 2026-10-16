"""Untrusted local raw-close inspection. No acquisition, admission or calculations."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import json
import re

from app.market_data_contracts import (
    ExchangeCalendar, Listing, MarketContractError, Security, Source, SymbolMapping,
    TradingSession, require,
)
from app.tiingo_eod_normalizer import (
    MAX_RESPONSE_BYTES, NORMALIZER_VERSION, TiingoEodFormat, TiingoEodRequest, normalize_tiingo_eod,
)

MAX_CONTEXT_BYTES = 256 * 1024
MAX_HISTORY_DAYS = 366
MAX_HISTORY_SESSIONS = 366


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_context_field")
        result[key] = value
    return result


def _integer(token):
    require(len(token) <= 20, "invalid_context_integer")
    return int(token)


def _no_number(_token):
    raise MarketContractError("unsupported_context_number")


def _fields(value, required, optional=()):
    require(type(value) is dict and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional), "invalid_context_fields")
    return value


def _text(value):
    require(type(value) is str and 0 < len(value) <= 256 and value == value.strip()
            and all(32 <= ord(c) <= 126 for c in value), "invalid_context_text")
    return value


def _day(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value),
            "invalid_context_date")
    return date.fromisoformat(value)


def _stamp(value):
    require(type(value) is str and len(value) <= 40 and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value),
        "invalid_context_timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _nullable(value, decoder):
    return None if value is None else decoder(value)


def _record(value, cls, fields, *, dates=(), stamps=(), nullable_dates=(), nullable_stamps=(),
            integers=(), booleans=()):
    data = dict(_fields(value, fields))
    for key in fields:
        item = data[key]
        if key in dates:
            data[key] = _day(item)
        elif key in stamps:
            data[key] = _stamp(item)
        elif key in nullable_dates:
            data[key] = _nullable(item, _day)
        elif key in nullable_stamps:
            data[key] = _nullable(item, _stamp)
        elif key in integers:
            require(type(item) is int and item >= 0, "invalid_context_integer")
        elif key in booleans:
            require(type(item) is bool, "invalid_context_boolean")
        else:
            data[key] = _text(item)
    return cls(**data)


def _decode(context):
    require(type(context) is bytes and 0 < len(context) <= MAX_CONTEXT_BYTES, "invalid_context_bound")
    root = json.loads(context.decode("utf-8"), object_pairs_hook=_object,
                      parse_int=_integer, parse_float=_no_number, parse_constant=_no_number)
    _fields(root, ("schema_version", "input_kind", "adjustment_basis", "request"), ("expected_bindings",))
    require(type(root["schema_version"]) is int and root["schema_version"] == 1, "unsupported_context_version")
    require(root["input_kind"] in ("synthetic", "unverified_local"), "unsupported_input_kind")
    require(root["adjustment_basis"] == "raw", "incompatible_adjustment_basis")
    req = _fields(root["request"], ("symbol", "security", "listing", "mappings", "calendar", "source",
                  "coverage_start", "coverage_end", "publication_id", "market_data_version", "published_at", "format"))
    security = _record(req["security"], Security, ("security_id", "company_id", "issuer_cik", "share_class"),
                       integers=("company_id",))
    listing = _record(req["listing"], Listing, ("listing_id", "security_id", "mic", "currency", "calendar_id",
                       "first_session", "last_session", "continuity"), dates=("first_session",), nullable_dates=("last_session",))
    require(type(req["mappings"]) is list and 0 < len(req["mappings"]) <= 256, "invalid_context_mappings")
    mappings = tuple(_record(item, SymbolMapping, ("provider", "product", "symbol", "ticker", "security_id",
        "listing_id", "mic", "effective_from", "effective_to", "identity_resolved", "identity_evidence"),
        dates=("effective_from",), nullable_dates=("effective_to",), booleans=("identity_resolved",))
        for item in req["mappings"])
    cal = _fields(req["calendar"], ("calendar_id", "version", "timezone", "close_convention",
                                   "covered_start", "covered_end", "sessions"))
    require(type(cal["sessions"]) is list and 0 < len(cal["sessions"]) <= MAX_HISTORY_SESSIONS,
            "invalid_history_session_bound")
    sessions = tuple(_record(item, TradingSession, ("session_date", "close_at"),
                            dates=("session_date",), stamps=("close_at",)) for item in cal["sessions"])
    calendar = ExchangeCalendar(*(_text(cal[key]) for key in ("calendar_id", "version", "timezone", "close_convention")),
                                _day(cal["covered_start"]), _day(cal["covered_end"]), sessions)
    start, end = _day(req["coverage_start"]), _day(req["coverage_end"])
    require(1 <= (end - start).days + 1 <= MAX_HISTORY_DAYS, "invalid_history_day_bound")
    require((calendar.covered_start, calendar.covered_end) == (start, end), "incompatible_response_coverage")
    source = _record(req["source"], Source, ("provider", "product", "source_id", "response_sha256",
                     "retrieved_at", "available_at"), stamps=("retrieved_at",), nullable_stamps=("available_at",))
    version = req["market_data_version"]
    require(type(version) is int and version >= 0, "invalid_context_integer")
    fmt = _record(req["format"], TiingoEodFormat, ("split_factor_direction", "declaration_reference", "dividend_share_basis"))
    request = TiingoEodRequest(_text(req["symbol"]), security, listing, mappings, calendar, start, end, source,
                              _text(req["publication_id"]), version, _stamp(req["published_at"]), fmt)
    expected = root.get("expected_bindings", {})
    _fields(expected, (), ("normalized_content_sha256", "publication_manifest_sha256"))
    for value in expected.values():
        require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "invalid_expected_binding")
    return root["input_kind"], request, expected


@dataclass(frozen=True)
class HistoryRow:
    session_date: str
    close_at: str
    observation_state: str
    unadjusted_close: str | None
    declared_currency: str
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class RawCloseHistory:
    input_kind: str
    context_sha256: str
    request: TiingoEodRequest
    normalized_content_sha256: str
    publication_manifest_sha256: str
    normalization_state: str
    publication_state: str
    reasons: tuple[str, ...]
    rows: tuple[HistoryRow, ...]

    def to_dict(self):
        """Fresh JSON-safe projection. No adjusted values, price changes or returns."""
        request = self.request
        return dict(
            schema_version=1, input_kind=self.input_kind, value_label="Unadjusted close",
            adjustment_basis="raw", provenance_state="unverified", trusted_custody=False,
            declaration_notice="Input kind, identity, calendar and timestamps are caller declarations, not authenticated evidence.",
            normalization_state=self.normalization_state, publication_state=self.publication_state,
            return_state="unavailable", adjusted_series_state="unavailable", reasons=list(self.reasons),
            knowledge_mode="retrospective_revised", freshness_state="unknown",
            declared_identity=dict(security=asdict(request.security), listing=_json_record(request.listing),
                                   symbol=request.symbol, mappings=[_json_record(m) for m in request.mappings]),
            calendar=dict(calendar_id=request.calendar.calendar_id, version=request.calendar.version,
                          timezone=request.calendar.timezone, close_convention=request.calendar.close_convention),
            coverage_start=request.coverage_start.isoformat(), coverage_end=request.coverage_end.isoformat(),
            publication_id=request.publication_id, market_data_version=request.market_data_version,
            published_at=request.published_at.isoformat(), normalizer_version=NORMALIZER_VERSION,
            provenance=dict(source=_json_record(request.source), context_sha256=self.context_sha256,
                normalized_content_sha256=self.normalized_content_sha256,
                publication_manifest_sha256=self.publication_manifest_sha256),
            rows=[dict(asdict(row), observation_ids=list(row.observation_ids)) for row in self.rows])


def _json_record(record):
    return {key: value.isoformat() if isinstance(value, (date, datetime)) else value
            for key, value in asdict(record).items()}


def inspect_raw_history(payload, context):
    """Only entry point: always normalize original bytes; never accept a sealed result."""
    require(type(payload) is bytes and 0 < len(payload) <= MAX_RESPONSE_BYTES, "invalid_response_bound")
    try:
        kind, request, expected = _decode(context)
        result = normalize_tiingo_eod(payload, request)
    except MarketContractError:
        raise
    except (ValueError, TypeError, AttributeError, OverflowError, RecursionError):
        raise MarketContractError("invalid_context") from None
    actual = dict(normalized_content_sha256=result.normalized_content_sha256,
                  publication_manifest_sha256=result.publication.manifest.sha256)
    require(all(actual[key] == value for key, value in expected.items()), "stale_history_binding")
    prices = {price.session_date: price for price in result.publication.prices}
    sessions = tuple(s for s in request.calendar.sessions if request.listing.first_session <= s.session_date
                     <= (request.listing.last_session or date.max))
    require(len(sessions) <= MAX_HISTORY_SESSIONS, "invalid_history_session_bound")
    rows = tuple(HistoryRow(s.session_date.isoformat(), s.close_at.isoformat(),
        "present" if s.session_date in prices else "missing",
        format(prices[s.session_date].close, "f") if s.session_date in prices else None,
        request.listing.currency, prices[s.session_date].observation_ids if s.session_date in prices else ())
        for s in sessions)
    return RawCloseHistory(kind, hashlib.sha256(context).hexdigest(), request,
                           actual["normalized_content_sha256"], actual["publication_manifest_sha256"],
                           result.status, result.publication.state, result.reasons, rows)
