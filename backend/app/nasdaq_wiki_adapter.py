"""Pure, bounded WIKI/PRICES byte inspection; no acquisition or financial admission.

Receipt declarations and consistent hashes bind caller-supplied inputs, not
authenticated custody, instrument identity or economic correctness. This module
creates no MarketPublication and performs no return or adjustment calculations.
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, DecimalException
import hashlib
import json
import re
from urllib.parse import parse_qsl

from app.market_data_contracts import MarketContractError, decimal_input, require

ADAPTER_VERSION = "nasdaq-wiki-observations-v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_CONTEXT_BYTES = 64 * 1024
MAX_ROWS = 1000
MAX_TICKERS = 3
MAX_COVERAGE_DAYS = 1461
SOURCE_LABEL = "Nasdaq Data Link WIKI/PRICES"

# Exact supported schema, including numeric type declarations. Columns may be
# reordered with their row cells; unknown names/types never trigger inference.
COLUMN_SCHEMA = (
    ("ticker", "String"), ("date", "Date"),
    ("open", "BigDecimal(34,12)"), ("high", "BigDecimal(34,12)"),
    ("low", "BigDecimal(34,12)"), ("close", "BigDecimal(34,12)"),
    ("volume", "BigDecimal(37,15)"), ("ex-dividend", "BigDecimal(42,20)"),
    ("split_ratio", "double"), ("adj_open", "BigDecimal(50,28)"),
    ("adj_high", "BigDecimal(50,28)"), ("adj_low", "BigDecimal(50,28)"),
    ("adj_close", "BigDecimal(50,28)"), ("adj_volume", "double"),
)
BLOCKERS = (
    "unverified_provider_custody", "unverified_security_identity",
    "unverified_currency_authority", "unverified_listing_continuity",
    "unverified_calendar_completeness", "unverified_corporate_action_completeness",
    "unverified_adjustment_semantics", "unknown_historical_availability",
    "known_wiki_dividend_incompleteness",
)
KNOWN_DATASET_LIMITATIONS = (
    "Coordinator-supplied WIKI limitation: AAPL ex-dividend is zero on "
    "2017-11-10 and 2018-02-09 despite independently established dividends. "
    "This adapter does not verify or repair those originals.",
)


@dataclass(frozen=True)
class WikiInspectionRequest:
    ticker: str
    expected_response_sha256: str
    expected_run_id: str
    acquisition_start: date
    acquisition_end: date
    selection_start: date
    selection_end: date
    input_kind: str = "unverified_local"
    expected_receipt_sha256: str | None = None


@dataclass(frozen=True)
class WikiRawClose:
    ticker: str
    session_date: date  # Vendor date label; not proof of an exchange session.
    original_row_index: int
    raw_close: Decimal
    ex_dividend_indicator: Decimal  # Unverified vendor indicators, not actions.
    split_ratio_indicator: Decimal

    def to_dict(self):
        return dict(ticker=self.ticker, session_date=self.session_date.isoformat(),
                    original_row_index=self.original_row_index,
                    unadjusted_close=format(self.raw_close, "f"),
                    unverified_ex_dividend_indicator=format(self.ex_dividend_indicator, "f"),
                    unverified_split_ratio_indicator=format(self.split_ratio_indicator, "f"))


@dataclass(frozen=True)
class WikiInspection:
    request: WikiInspectionRequest
    captured_at_utc: str
    source_filename: str
    response_sha256: str
    receipt_sha256: str
    context_sha256: str
    inspection_sha256: str
    acquisition_row_count: int
    actual_min_date: date
    actual_max_date: date
    observations: tuple[WikiRawClose, ...]
    blockers: tuple[str, ...]

    def to_dict(self):
        """Fresh JSON-safe projection; no adjusted prices or calculated values."""
        req = self.request
        return dict(
            schema_version=1, adapter_version=ADAPTER_VERSION, input_kind=req.input_kind,
            value_label="Unadjusted close", adjustment_basis="raw",
            financial_eligibility="blocked", provenance_state="unverified", trusted_custody=False,
            identity_state="unverified", currency_authority="unverified",
            listing_continuity="unverified", calendar_completeness="unverified",
            corporate_action_completeness="unverified", publication_state="not_created",
            return_state="unavailable", adjusted_series_state="unavailable",
            knowledge_mode="retrospective_revised", freshness_state="unknown",
            declaration_notice="Hashes and operator metadata bind supplied inputs; they do not "
                               "authenticate provider custody or establish financial correctness.",
            source=dict(provider="nasdaq_data_link", product="WIKI/PRICES",
                        declared_source=SOURCE_LABEL, ticker=req.ticker,
                        filename=self.source_filename, run_id=req.expected_run_id,
                        captured_at_utc=self.captured_at_utc, retrieved_at=None, available_at=None),
            acquisition=dict(requested_start=req.acquisition_start.isoformat(),
                             requested_end=req.acquisition_end.isoformat(),
                             actual_min_date=self.actual_min_date.isoformat(),
                             actual_max_date=self.actual_max_date.isoformat(),
                             row_count=self.acquisition_row_count),
            selection=dict(start=req.selection_start.isoformat(), end=req.selection_end.isoformat(),
                           row_count=len(self.observations)),
            digests=dict(original_response_sha256=self.response_sha256,
                         operator_receipt_sha256=self.receipt_sha256,
                         inspection_context_sha256=self.context_sha256,
                         inspection_sha256=self.inspection_sha256),
            blockers=list(self.blockers), known_dataset_limitations=list(KNOWN_DATASET_LIMITATIONS),
            observations=[row.to_dict() for row in self.observations])


def _fields(value, names):
    require(type(value) is dict and value.keys() == set(names), "invalid_wiki_fields")


def _text(value, limit=256, *, empty=False):
    require(type(value) is str and int(not empty) <= len(value) <= limit
            and all(32 <= ord(c) <= 126 for c in value), "invalid_wiki_text")
    return value


def _ticker(value):
    _text(value, 16)
    require(re.fullmatch(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)?", value) is not None,
            "invalid_wiki_ticker")
    return value


def _sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None,
            "invalid_wiki_fingerprint")
    return value.lower()


def _day(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None,
            "invalid_wiki_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise MarketContractError("invalid_wiki_date") from None


def _capture(value):
    # Validate without converting the fractional text into microsecond datetime.
    require(type(value) is str and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,7})?Z", value),
        "invalid_wiki_capture_time")
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise MarketContractError("invalid_wiki_capture_time") from None


def _run(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", value),
            "invalid_wiki_run_id")
    try:
        return datetime.strptime(value[:16], "%Y%m%dT%H%M%SZ")
    except ValueError:
        raise MarketContractError("invalid_wiki_run_id") from None


def _count(value, low, high):
    require(type(value) is int and low <= value <= high, "invalid_wiki_count")
    return value


def _number(token):
    require(len(token) <= 96, "unbounded_wiki_number")
    try:
        value = Decimal(token)
    except DecimalException:
        raise MarketContractError("invalid_wiki_number") from None
    require(decimal_input(value) and abs(value.as_tuple().exponent) <= 45, "invalid_wiki_number")
    return value


def _integer(token):
    require(len(token) <= 20, "unbounded_wiki_integer")
    return int(token)


def _no_number(_token):
    raise MarketContractError("unsupported_wiki_number")


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_wiki_field")
        result[key] = value
    return result


def _decode(payload, limit, *, response=False):
    require(type(payload) is bytes and 0 < len(payload) <= limit, "invalid_wiki_byte_bound")
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_object,
                          parse_int=_number if response else _integer,
                          parse_float=_number if response else _no_number,
                          parse_constant=_no_number)
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, MarketContractError):
            raise
        raise MarketContractError("invalid_wiki_json") from None


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _request_context(req):
    require(type(req) is WikiInspectionRequest, "invalid_wiki_request")
    _ticker(req.ticker)
    _sha(req.expected_response_sha256)
    if req.expected_receipt_sha256 is not None:
        _sha(req.expected_receipt_sha256)
    _run(req.expected_run_id)
    _text(req.input_kind, 16)
    require(req.input_kind in {"synthetic", "unverified_local"},
            "invalid_wiki_input_kind")
    require(all(type(day) is date for day in (req.acquisition_start, req.acquisition_end,
                                            req.selection_start, req.selection_end)), "invalid_wiki_date")
    require(1 <= (req.acquisition_end - req.acquisition_start).days + 1 <= MAX_COVERAGE_DAYS,
            "invalid_wiki_coverage_bound")
    require(req.acquisition_start <= req.selection_start <= req.selection_end <= req.acquisition_end,
            "invalid_wiki_selection")
    context = {key: value.isoformat() if type(value) is date else value
               for key, value in asdict(req).items()}
    encoded = _json_bytes(context)
    require(len(encoded) <= MAX_CONTEXT_BYTES, "invalid_wiki_context_bound")
    return hashlib.sha256(encoded).hexdigest()


def _query(value, ticker, start, end):
    _text(value)
    try:
        pairs = parse_qsl(value, keep_blank_values=True, strict_parsing=True, max_num_fields=4,
                          encoding="ascii", errors="strict")
    except (ValueError, UnicodeError):
        raise MarketContractError("invalid_wiki_query") from None
    expected = {"ticker": ticker, "date.gte": start, "date.lte": end, "qopts.per_page": str(MAX_ROWS)}
    require(len(pairs) == 4 and dict(pairs) == expected, "invalid_wiki_query")


def _receipt(data, req):
    _fields(data, ("pilot", "run_id", "captured_at_utc", "source", "requested_tickers",
                   "requested_start", "requested_end", "maximum_get_requests", "actual_get_requests",
                   "maximum_rows_per_request", "acquisition_complete", "stop_reason",
                   "financial_quality_approved", "known_issue", "records"))
    require(data["pilot"] == "MD-WIKI limited original acquisition"
            and data["source"] == SOURCE_LABEL, "incompatible_wiki_source")
    require(data["run_id"] == req.expected_run_id, "wiki_run_mismatch")
    captured = _capture(data["captured_at_utc"])
    require(_run(data["run_id"]) <= captured, "invalid_wiki_capture_time")
    require(data["acquisition_complete"] is True and data["financial_quality_approved"] is False,
            "invalid_wiki_receipt_status")
    _text(data["stop_reason"], 2048, empty=True)
    _text(data["known_issue"], 2048, empty=True)
    start, end = _day(data["requested_start"]), _day(data["requested_end"])
    require((start, end) == (req.acquisition_start, req.acquisition_end), "wiki_acquisition_mismatch")
    tickers, records = data["requested_tickers"], data["records"]
    require(type(tickers) is list and 1 <= len(tickers) <= MAX_TICKERS, "invalid_wiki_ticker_inventory")
    for ticker in tickers:
        _ticker(ticker)
    require(len(set(tickers)) == len(tickers) and req.ticker in tickers, "invalid_wiki_ticker_inventory")
    require(type(records) is list and len(records) == len(tickers), "invalid_wiki_receipt_inventory")
    require(_count(data["maximum_get_requests"], 1, MAX_TICKERS)
            == _count(data["actual_get_requests"], 1, MAX_TICKERS) == len(tickers),
            "invalid_wiki_request_count")
    require(_count(data["maximum_rows_per_request"], 1, MAX_ROWS) == MAX_ROWS, "invalid_wiki_page_size")
    by_ticker = {}
    for record in records:
        _fields(record, ("ticker", "status", "requested_start", "requested_end", "actual_min_date",
                         "actual_max_date", "rows", "http_status", "source", "query_without_credentials",
                         "filename", "raw_bytes", "sha256", "has_more_pages", "financial_quality_approved"))
        ticker = _ticker(record["ticker"])
        require(ticker in tickers and ticker not in by_ticker, "invalid_wiki_receipt_inventory")
        require(record["status"] == "CAPTURED_STRUCTURAL_ONLY" and record["source"] == SOURCE_LABEL
                and _count(record["http_status"], 200, 200) == 200
                and record["has_more_pages"] is False and record["financial_quality_approved"] is False,
                "invalid_wiki_receipt_status")
        require((record["requested_start"], record["requested_end"])
                == (data["requested_start"], data["requested_end"]), "wiki_acquisition_mismatch")
        low, high = _day(record["actual_min_date"]), _day(record["actual_max_date"])
        require(start <= low <= high <= end and high <= captured.date(), "invalid_wiki_observation_bounds")
        _count(record["rows"], 1, MAX_ROWS)
        _count(record["raw_bytes"], 1, MAX_RESPONSE_BYTES)
        _sha(record["sha256"])
        require(record["filename"] == f"WIKI_PRICES_{ticker}_{start}_{end}.json", "wiki_filename_mismatch")
        _query(record["query_without_credentials"], ticker, str(start), str(end))
        by_ticker[ticker] = record
    return by_ticker[req.ticker]


def _rows(data, req, record):
    _fields(data, ("datatable", "meta"))
    _fields(data["datatable"], ("columns", "data"))
    _fields(data["meta"], ("next_cursor_id",))
    require(data["meta"]["next_cursor_id"] is None, "incomplete_wiki_pagination")
    table = data["datatable"]
    columns = table["columns"]
    require(type(columns) is list and len(columns) == len(COLUMN_SCHEMA), "invalid_wiki_columns")
    schema = []
    for column in columns:
        _fields(column, ("name", "type"))
        schema.append((_text(column["name"]), _text(column["type"])))
    require(len(set(name for name, _ in schema)) == len(schema)
            and set(schema) == set(COLUMN_SCHEMA), "invalid_wiki_columns")
    names = tuple(name for name, _ in schema)
    rows = table["data"]
    require(type(rows) is list and 1 <= len(rows) <= MAX_ROWS, "invalid_wiki_row_bound")
    require(len(rows) == record["rows"], "wiki_row_count_mismatch")
    dates, parsed = set(), []
    for index, cells in enumerate(rows):
        require(type(cells) is list and len(cells) == len(names), "invalid_wiki_row_width")
        row = dict(zip(names, cells))
        require(type(row["ticker"]) is str and row["ticker"] == req.ticker, "wiki_ticker_mismatch")
        day = _day(row["date"])
        require(req.acquisition_start <= day <= req.acquisition_end, "invalid_wiki_observation_bounds")
        require(day not in dates, "duplicate_wiki_observation")
        dates.add(day)
        require(all(decimal_input(row[name]) for name in names if name not in {"ticker", "date"}),
                "invalid_wiki_numeric_type")
        for prefix in ("", "adj_"):
            opened, high, low, close, volume = (row[prefix + key] for key in ("open", "high", "low", "close", "volume"))
            require(all(value > 0 for value in (opened, high, low, close)), "nonpositive_wiki_price")
            require(low <= min(opened, close) <= max(opened, close) <= high, "inconsistent_wiki_ohlc")
            require(volume >= 0, "negative_wiki_volume")
        require(row["volume"] == row["volume"].to_integral_value(), "fractional_wiki_raw_volume")
        require(row["ex-dividend"] >= 0 and row["split_ratio"] > 0, "invalid_wiki_action_indicator")
        parsed.append(WikiRawClose(req.ticker, day, index, row["close"], row["ex-dividend"], row["split_ratio"]))
    require((min(dates), max(dates)) == (_day(record["actual_min_date"]), _day(record["actual_max_date"])),
            "wiki_date_extrema_mismatch")
    return tuple(sorted(parsed, key=lambda row: row.session_date))


def inspect_wiki_bytes(payload, receipt, request):
    """Validate all supplied acquisition rows before selecting observations.

    The expected response digest is independent of the receipt. An optional
    external receipt digest also pins metadata; neither pin authenticates custody.
    Nonselected receipt records are structurally checked, not cross-file verified.
    No date missing from the payload is created or classified as a trading day.
    """
    context_digest = _request_context(request)
    require(type(payload) is bytes and 0 < len(payload) <= MAX_RESPONSE_BYTES, "invalid_wiki_byte_bound")
    require(type(receipt) is bytes and 0 < len(receipt) <= MAX_RECEIPT_BYTES, "invalid_wiki_byte_bound")
    response_digest = hashlib.sha256(payload).hexdigest()
    receipt_digest = hashlib.sha256(receipt).hexdigest()
    require(response_digest == _sha(request.expected_response_sha256), "wiki_response_fingerprint_mismatch")
    if request.expected_receipt_sha256 is not None:
        require(receipt_digest == _sha(request.expected_receipt_sha256), "wiki_receipt_fingerprint_mismatch")
    metadata = _decode(receipt, MAX_RECEIPT_BYTES)
    record = _receipt(metadata, request)
    require(_sha(record["sha256"]) == response_digest, "wiki_receipt_response_mismatch")
    require(record["raw_bytes"] == len(payload), "wiki_response_size_mismatch")
    rows = _rows(_decode(payload, MAX_RESPONSE_BYTES, response=True), request, record)
    selected = tuple(row for row in rows if request.selection_start <= row.session_date <= request.selection_end)
    blockers = set(BLOCKERS)
    if not selected:
        blockers.add("empty_selected_observations")
    if any(row.ex_dividend_indicator > 0 for row in rows):
        blockers.add("unclassified_vendor_cash_indicator")
    if any(row.split_ratio_indicator != 1 for row in rows):
        blockers.add("unverified_vendor_split_indicator")
    inspection_digest = hashlib.sha256(_json_bytes(dict(
        adapter_version=ADAPTER_VERSION, response_sha256=response_digest,
        receipt_sha256=receipt_digest, context_sha256=context_digest,
        observations=[row.to_dict() for row in selected], blockers=sorted(blockers),
        known_dataset_limitations=KNOWN_DATASET_LIMITATIONS))).hexdigest()
    return WikiInspection(request, metadata["captured_at_utc"], record["filename"], response_digest,
                          receipt_digest, context_digest, inspection_digest, len(rows),
                          rows[0].session_date, rows[-1].session_date, selected, tuple(sorted(blockers)))
