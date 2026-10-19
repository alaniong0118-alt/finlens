"""Fictional bytes only. No operator datasets, files, providers or financial identity."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from decimal import Decimal, Inexact, Rounded, localcontext
import builtins
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from app.market_data_contracts import MarketContractError
from app import nasdaq_wiki_adapter as wiki


RUN = "20260109T120000Z-1234abcd"
START, END = date(2026, 1, 1), date(2026, 1, 9)
CAPTURE = "2026-01-09T12:00:01.1234567Z"
SCHEMA = [
    ("ticker", "String"), ("date", "Date"),
    ("open", "BigDecimal(34,12)"), ("high", "BigDecimal(34,12)"),
    ("low", "BigDecimal(34,12)"), ("close", "BigDecimal(34,12)"),
    ("volume", "BigDecimal(37,15)"), ("ex-dividend", "BigDecimal(42,20)"),
    ("split_ratio", "double"), ("adj_open", "BigDecimal(50,28)"),
    ("adj_high", "BigDecimal(50,28)"), ("adj_low", "BigDecimal(50,28)"),
    ("adj_close", "BigDecimal(50,28)"), ("adj_volume", "double"),
]


def bar(day, close=100, *, ticker="FICT", dividend=0, split=1):
    return [ticker, day, close, close, close, close, 1200, dividend, split,
            close, close, close, close, 1200]


def fixture():
    body = dict(datatable=dict(columns=[dict(name=name, type=kind) for name, kind in SCHEMA],
                               data=[bar("2026-01-08", 110), bar("2026-01-05"), bar("2026-01-06", 105)]),
                meta=dict(next_cursor_id=None))
    record = dict(ticker="FICT", status="CAPTURED_STRUCTURAL_ONLY", requested_start=str(START),
                  requested_end=str(END), actual_min_date="2026-01-05", actual_max_date="2026-01-08",
                  rows=3, http_status=200, source="Nasdaq Data Link WIKI/PRICES",
                  query_without_credentials="ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-09&qopts.per_page=1000",
                  filename="WIKI_PRICES_FICT_2026-01-01_2026-01-09.json", raw_bytes=1, sha256="0" * 64,
                  has_more_pages=False, financial_quality_approved=False)
    receipt = dict(pilot="MD-WIKI limited original acquisition", run_id=RUN, captured_at_utc=CAPTURE,
                   source="Nasdaq Data Link WIKI/PRICES", requested_tickers=["FICT"],
                   requested_start=str(START), requested_end=str(END), maximum_get_requests=1,
                   actual_get_requests=1, maximum_rows_per_request=1000, acquisition_complete=True,
                   stop_reason="complete", financial_quality_approved=False,
                   known_issue="Fictional fixture, not financial evidence.", records=[record])
    return body, receipt


def bind(body, receipt, *, raw=None):
    """Synthetic acquisition bindings only; deliberately never repair test mutations later."""
    payload = json.dumps(body).encode() if raw is None else raw
    metadata = deepcopy(receipt)
    metadata["records"][0].update(raw_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest().upper())
    receipt_bytes = json.dumps(metadata).encode()
    req = wiki.WikiInspectionRequest("FICT", hashlib.sha256(payload).hexdigest().upper(), RUN,
                                     START, END, START, END, "synthetic")
    return payload, receipt_bytes, req


def inspect(body=None, receipt=None, *, raw=None, **request_changes):
    default_body, default_receipt = fixture()
    args = bind(default_body if body is None else body, default_receipt if receipt is None else receipt, raw=raw)
    return wiki.inspect_wiki_bytes(args[0], args[1], replace(args[2], **request_changes))


def test_valid_immutable_exact_projection_and_separate_bindings():
    result = inspect()
    assert tuple(row.session_date.isoformat() for row in result.observations) == (
        "2026-01-05", "2026-01-06", "2026-01-08")
    assert tuple(row.original_row_index for row in result.observations) == (1, 2, 0)
    assert tuple(row.raw_close for row in result.observations) == (Decimal(100), Decimal(105), Decimal(110))
    assert result.captured_at_utc == CAPTURE
    output = result.to_dict()
    assert output["source"]["retrieved_at"] is output["source"]["available_at"] is None
    assert output["financial_eligibility"] == "blocked"
    assert output["publication_state"] == "not_created"
    assert output["trusted_custody"] is False
    assert len(set(output["digests"].values())) == 4
    assert result == inspect()
    for target, attr, value in ((result, "captured_at_utc", "changed"),
                                 (result.request, "ticker", "OTHER"),
                                 (result.observations[0], "raw_close", Decimal(1))):
        with pytest.raises(FrozenInstanceError):
            setattr(target, attr, value)
    output["observations"][0]["unadjusted_close"] = "changed"
    output["blockers"].clear()
    assert result.to_dict()["observations"][0]["unadjusted_close"] == "100"
    assert result.to_dict()["blockers"]
    json.dumps(result.to_dict(), allow_nan=False)


def test_full_acquisition_is_checked_before_selection_and_missing_dates_are_not_created():
    result = inspect(selection_start=date(2026, 1, 6), selection_end=date(2026, 1, 8))
    data = result.to_dict()
    assert data["acquisition"] == dict(requested_start=str(START), requested_end=str(END),
                                      actual_min_date="2026-01-05", actual_max_date="2026-01-08", row_count=3)
    assert data["selection"] == dict(start="2026-01-06", end="2026-01-08", row_count=2)
    assert [row["session_date"] for row in data["observations"]] == ["2026-01-06", "2026-01-08"]
    body, _ = fixture()
    body["datatable"]["data"][1][5] = 0  # Invalid price outside selected window still rejects.
    with pytest.raises(MarketContractError, match="nonpositive_wiki_price"):
        inspect(body, selection_start=date(2026, 1, 6))


def test_empty_selection_is_explicitly_blocked_without_synthetic_rows():
    result = inspect(selection_start=date(2026, 1, 7), selection_end=date(2026, 1, 7))
    assert result.observations == ()
    assert "empty_selected_observations" in result.blockers


def test_exact_decimal_lexemes_ignore_ambient_precision_and_traps():
    body, receipt = fixture()
    raw = json.dumps(body).encode().replace(b"110", b"110.000000000000000001")
    with localcontext() as ctx:
        ctx.prec = 3
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        result = inspect(body, receipt, raw=raw)
    assert result.observations[-1].raw_close == Decimal("110.000000000000000001")
    assert result.to_dict()["observations"][-1]["unadjusted_close"] == "110.000000000000000001"


def test_actions_and_adjusted_fields_never_grant_financial_eligibility():
    body, _ = fixture()
    body["datatable"]["data"][0] = bar("2026-01-08", 55, dividend=2, split=2)
    body["datatable"]["data"][0][9:13] = [999, 999, 999, 999]
    result = inspect(body)
    assert result.observations[-1].raw_close == Decimal(55)
    assert "unclassified_vendor_cash_indicator" in result.blockers
    assert "unverified_vendor_split_indicator" in result.blockers
    data = result.to_dict()
    assert data["return_state"] == data["adjusted_series_state"] == "unavailable"
    assert data["corporate_action_completeness"] == "unverified"
    assert "2017-11-10" in data["known_dataset_limitations"][0]
    assert "2018-02-09" in data["known_dataset_limitations"][0]
    forbidden = {"publication", "market_data_version", "publication_manifest_sha256", "security_id",
                 "listing_id", "company_id", "issuer_cik", "mic", "currency", "close_at", "adj_close",
                 "adjusted_close", "price_return", "total_return", "performance", "growth", "action_coverage"}

    def check(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(data)


def test_column_reordering_uses_names_and_preserves_original_row_references():
    body, _ = fixture()
    body["datatable"]["columns"].reverse()
    for row in body["datatable"]["data"]:
        row.reverse()
    assert inspect(body).observations == inspect().observations


@pytest.mark.parametrize("volume_type,accepted", [
    ("BigDecimal(37,15)", True), ("BigDecimal(37,0)", False), ("double", False),
])
def test_observed_volume_schema_is_accepted_and_other_types_reject(volume_type, accepted):
    body, _ = fixture()
    next(column for column in body["datatable"]["columns"] if column["name"] == "volume")["type"] = volume_type
    if accepted:
        assert len(inspect(body).observations) == 3
    else:
        with pytest.raises(MarketContractError, match="invalid_wiki_columns"):
            inspect(body)


def test_response_changes_are_not_auto_repaired_against_external_pin():
    body, receipt = fixture()
    payload, metadata, req = bind(body, receipt)
    with pytest.raises(MarketContractError, match="wiki_response_fingerprint_mismatch"):
        wiki.inspect_wiki_bytes(payload + b" ", metadata, req)
    with pytest.raises(MarketContractError, match="wiki_response_fingerprint_mismatch"):
        wiki.inspect_wiki_bytes(payload, metadata, replace(req, expected_response_sha256="1" * 64))


@pytest.mark.parametrize("key,value,reason", [
    ("sha256", "1" * 64, "wiki_receipt_response_mismatch"),
    ("raw_bytes", 2, "wiki_response_size_mismatch"),
    ("rows", 2, "wiki_row_count_mismatch"),
    ("actual_min_date", "2026-01-04", "wiki_date_extrema_mismatch"),
    ("actual_max_date", "2026-01-09", "wiki_date_extrema_mismatch"),
    ("filename", "../other.json", "wiki_filename_mismatch"),
    ("ticker", "OTHER", "invalid_wiki_receipt_inventory"),
    ("source", "other", "invalid_wiki_receipt_status"),
    ("requested_start", "2026-01-02", "wiki_acquisition_mismatch"),
    ("http_status", True, "invalid_wiki_count"),
    ("http_status", 201, "invalid_wiki_count"),
    ("has_more_pages", True, "invalid_wiki_receipt_status"),
    ("has_more_pages", 0, "invalid_wiki_receipt_status"),
    ("financial_quality_approved", True, "invalid_wiki_receipt_status"),
    ("status", "APPROVED", "invalid_wiki_receipt_status"),
])
def test_receipt_record_mismatches(key, value, reason):
    body, receipt = fixture()
    payload, metadata, req = bind(body, receipt)
    data = json.loads(metadata)
    data["records"][0][key] = value
    with pytest.raises(MarketContractError, match=reason):
        wiki.inspect_wiki_bytes(payload, json.dumps(data).encode(), req)


@pytest.mark.parametrize("key,value", [
    ("pilot", "other"), ("source", "other"), ("run_id", "20260109T120000Z-deadbeef"),
    ("requested_start", "2025-01-01"), ("requested_end", "2026-01-10"),
    ("acquisition_complete", False), ("acquisition_complete", 1),
    ("financial_quality_approved", True), ("financial_quality_approved", 0),
    ("actual_get_requests", 2), ("actual_get_requests", True), ("maximum_get_requests", 4),
    ("maximum_rows_per_request", 999), ("requested_tickers", ["FICT", "FICT"]),
    ("requested_tickers", []), ("requested_tickers", ["OTHER"]),
    ("requested_tickers", ["FICT", "B", "C", "D"]), ("records", []),
    ("known_issue", "\x1bunsafe"), ("stop_reason", "x" * 2049),
])
def test_invalid_receipt_root(key, value):
    body, receipt = fixture()
    payload, metadata, req = bind(body, receipt)
    mutated = json.loads(metadata)
    mutated[key] = value
    with pytest.raises(MarketContractError):
        wiki.inspect_wiki_bytes(payload, json.dumps(mutated).encode(), req)


def test_duplicate_and_nonselected_receipt_records_are_validated_without_reading_other_payloads():
    body, receipt = fixture()
    other = deepcopy(receipt["records"][0])
    other.update(ticker="OTHER", filename="WIKI_PRICES_OTHER_2026-01-01_2026-01-09.json",
                 query_without_credentials="ticker=OTHER&date.gte=2026-01-01&date.lte=2026-01-09&qopts.per_page=1000")
    receipt.update(requested_tickers=["FICT", "OTHER"], maximum_get_requests=2, actual_get_requests=2)
    receipt["records"].append(other)
    assert len(inspect(body, receipt).observations) == 3
    receipt["records"][1]["ticker"] = "FICT"
    with pytest.raises(MarketContractError, match="invalid_wiki_receipt_inventory"):
        inspect(body, receipt)


@pytest.mark.parametrize("query", [
    "ticker=OTHER&date.gte=2026-01-01&date.lte=2026-01-09&qopts.per_page=1000",
    "ticker=FICT&date.gte=2026-01-02&date.lte=2026-01-09&qopts.per_page=1000",
    "ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-10&qopts.per_page=1000",
    "ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-09&qopts.per_page=999",
    "ticker=FICT&ticker=FICT&date.lte=2026-01-09&qopts.per_page=1000",
    "ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-09&api_key=SECRET_SENTINEL",
    "ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-09&qopts.per_page=1000&api_key=SECRET_SENTINEL",
    "https://example.invalid/?ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-09&qopts.per_page=1000",
    "ticker=FICT&broken", "", "ticker=FICT\n",
])
def test_request_metadata_is_credential_free_and_exactly_bound(query):
    body, receipt = fixture()
    receipt["records"][0]["query_without_credentials"] = query
    with pytest.raises(MarketContractError) as error:
        inspect(body, receipt)
    assert "SECRET_SENTINEL" not in str(error.value)
    assert query != str(error.value)


@pytest.mark.parametrize("stamp", [
    "2026-01-09T12:00:01.1234567Z", "2026-01-09T12:00:01.0000000Z", "2026-01-09T12:00:01Z",
])
def test_run_capture_timestamp_text_is_lossless(stamp):
    body, receipt = fixture()
    receipt["captured_at_utc"] = stamp
    assert inspect(body, receipt).to_dict()["source"]["captured_at_utc"] == stamp


@pytest.mark.parametrize("stamp", [
    "2026-01-09T12:00:01.12345678Z", "2026-01-09T12:00:01", "2026-01-09T12:00:01+00:00",
    "2026-02-30T12:00:01.1234567Z", "2026-01-09T24:00:01Z", "2026-01-09T11:59:59.9999999Z", None,
])
def test_invalid_capture_times_do_not_get_coerced(stamp):
    body, receipt = fixture()
    receipt["captured_at_utc"] = stamp
    with pytest.raises(MarketContractError, match="invalid_wiki_capture_time"):
        inspect(body, receipt)


@pytest.mark.parametrize("mutation", [
    "root_extra", "root_missing", "table_extra", "meta_missing", "cursor_missing", "cursor_nonterminal",
    "columns_missing", "columns_extra", "columns_duplicate", "columns_wrong_type", "column_extra",
    "row_short", "row_long", "row_object", "rows_object", "rows_empty", "ticker_wrong", "date_duplicate",
])
def test_response_schema_and_pagination_are_strict(mutation):
    body, _ = fixture()
    table = body["datatable"]
    if mutation == "root_extra": body["extra"] = 1
    elif mutation == "root_missing": del body["datatable"]
    elif mutation == "table_extra": table["extra"] = 1
    elif mutation == "meta_missing": del body["meta"]
    elif mutation == "cursor_missing": body["meta"].clear()
    elif mutation == "cursor_nonterminal": body["meta"]["next_cursor_id"] = "next"
    elif mutation == "columns_missing": table["columns"].pop()
    elif mutation == "columns_extra": table["columns"].append(dict(name="extra", type="double"))
    elif mutation == "columns_duplicate": table["columns"][2] = table["columns"][3]
    elif mutation == "columns_wrong_type": table["columns"][2]["type"] = "String"
    elif mutation == "column_extra": table["columns"][0]["extra"] = True
    elif mutation == "row_short": table["data"][0].pop()
    elif mutation == "row_long": table["data"][0].append(1)
    elif mutation == "row_object": table["data"][0] = {}
    elif mutation == "rows_object": table["data"] = {}
    elif mutation == "rows_empty": table["data"] = []
    elif mutation == "ticker_wrong": table["data"][0][0] = "OTHER"
    elif mutation == "date_duplicate": table["data"][0][1] = "2026-01-05"
    with pytest.raises(MarketContractError):
        inspect(body)


@pytest.mark.parametrize("day", ["2026-02-30", "2026-1-08", "2026-01-08T00:00:00Z", "2025-12-31", "2026-01-10", None])
def test_invalid_row_dates(day):
    body, _ = fixture()
    body["datatable"]["data"][0][1] = day
    with pytest.raises(MarketContractError):
        inspect(body)


@pytest.mark.parametrize("column,value", [
    ("close", 0), ("close", -1), ("close", "100"), ("close", None), ("close", True),
    ("high", 1), ("low", 1000), ("open", -1), ("volume", -1), ("volume", 1.5),
    ("adj_close", 0), ("adj_high", 1), ("adj_low", 1000), ("adj_volume", -1),
    ("ex-dividend", -1), ("split_ratio", 0), ("split_ratio", -1),
])
def test_invalid_numeric_fields(column, value):
    body, _ = fixture()
    body["datatable"]["data"][0][[name for name, _ in SCHEMA].index(column)] = value
    with pytest.raises(MarketContractError):
        inspect(body)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e99999999999999999999999", "1e-46",
                                       "1e19", "0.0000000000000000001", "12345678901234567890123456789", "1" * 97])
def test_bounded_nonfinite_and_overprecise_numbers(token):
    body, receipt = fixture()
    raw = json.dumps(body).encode().replace(b"110", token.encode(), 1)
    with pytest.raises(MarketContractError):
        inspect(body, receipt, raw=raw)


@pytest.mark.parametrize("raw", [b"\xff", b"{", b"[]", b"null", b'{"meta":{},"meta":{}}', b"[" * 2000 + b"]" * 2000])
def test_invalid_response_json_is_a_sanitized_contract_error(raw):
    with pytest.raises(MarketContractError) as error:
        inspect(raw=raw)
    assert str(error.value).replace("_", "").isalpha()


@pytest.mark.parametrize("raw", [b"\xff", b"{", b"[]", b"null", b'{"run_id":"a","run_id":"b"}',
                                       b'{"actual_get_requests":NaN}', b'{"actual_get_requests":1.0}',
                                       b'{"actual_get_requests":123456789012345678901}'])
def test_invalid_receipt_json(raw):
    payload, _, req = bind(*fixture())
    with pytest.raises(MarketContractError):
        wiki.inspect_wiki_bytes(payload, raw, req)


@pytest.mark.parametrize("field,value", [
    ("ticker", "../FICT"), ("ticker", "FICT\n"), ("ticker", []),
    ("expected_response_sha256", "a" * 63), ("expected_response_sha256", None),
    ("expected_receipt_sha256", "not-a-digest"), ("expected_run_id", "20260230T120000Z-1234abcd"),
    ("expected_run_id", "bad"), ("input_kind", "approved"), ("input_kind", []),
    ("selection_start", END + timedelta(days=1)), ("selection_end", START - timedelta(days=1)),
    ("acquisition_start", "2026-01-01"), ("acquisition_start", END + timedelta(days=1)),
    ("acquisition_end", START + timedelta(days=1461)),
])
def test_invalid_explicit_context(field, value):
    with pytest.raises(MarketContractError):
        inspect(**{field: value})


def test_context_type_receipt_pin_and_independent_digest_changes():
    payload, receipt, req = bind(*fixture())
    with pytest.raises(MarketContractError, match="invalid_wiki_request"):
        wiki.inspect_wiki_bytes(payload, receipt, {})
    pinned = replace(req, expected_receipt_sha256=hashlib.sha256(receipt).hexdigest().upper())
    assert wiki.inspect_wiki_bytes(payload, receipt, pinned).receipt_sha256 == hashlib.sha256(receipt).hexdigest()
    with pytest.raises(MarketContractError, match="wiki_receipt_fingerprint_mismatch"):
        wiki.inspect_wiki_bytes(payload, receipt + b" ", pinned)
    first = wiki.inspect_wiki_bytes(payload, receipt, req)
    metadata = json.loads(receipt)
    metadata["captured_at_utc"] = "2026-01-09T12:00:01.1234568Z"
    second = wiki.inspect_wiki_bytes(payload, json.dumps(metadata).encode(), req)
    assert first.response_sha256 == second.response_sha256
    assert first.observations == second.observations
    assert first.receipt_sha256 != second.receipt_sha256
    assert first.inspection_sha256 != second.inspection_sha256
    narrowed = inspect(selection_start=date(2026, 1, 6))
    assert first.context_sha256 != narrowed.context_sha256
    assert first.inspection_sha256 != narrowed.inspection_sha256


def test_unprojected_adjustment_changes_still_change_original_and_inspection_bindings():
    first = inspect()
    body, _ = fixture()
    body["datatable"]["data"][0][9:13] = [999, 999, 999, 999]
    second = inspect(body)
    assert first.observations == second.observations
    assert first.response_sha256 != second.response_sha256
    assert first.inspection_sha256 != second.inspection_sha256


@pytest.mark.parametrize("location,mutation", [
    ("root", "missing"), ("root", "extra"), ("record", "missing"), ("record", "extra"),
    ("record", "null"), ("root", "null"),
])
def test_receipt_exact_keys_and_object_types(location, mutation):
    payload, metadata, req = bind(*fixture())
    data = json.loads(metadata)
    target = data if location == "root" else data["records"][0]
    if mutation == "missing":
        del target["source"]
    elif mutation == "extra":
        target["extra"] = "unsupported"
    elif location == "root":
        data = None
    else:
        data["records"][0] = None
    with pytest.raises(MarketContractError, match="invalid_wiki_fields"):
        wiki.inspect_wiki_bytes(payload, json.dumps(data).encode(), req)


@pytest.mark.parametrize("field,value", [
    ("rows", 0), ("rows", 1001), ("rows", True), ("raw_bytes", 0),
    ("raw_bytes", 4 * 1024 * 1024 + 1), ("sha256", "z" * 64),
    ("actual_min_date", "2026-02-30"), ("actual_min_date", "2026-01-09"),
    ("actual_max_date", "2026-01-10"), ("actual_min_date", "2025-12-31"),
])
def test_receipt_record_count_date_and_hash_bounds(field, value):
    payload, metadata, req = bind(*fixture())
    data = json.loads(metadata)
    data["records"][0][field] = value
    with pytest.raises(MarketContractError):
        wiki.inspect_wiki_bytes(payload, json.dumps(data).encode(), req)


def test_observation_dates_cannot_be_after_run_capture():
    body, receipt = fixture()
    body["datatable"]["data"][0][1] = "2026-01-10"
    receipt["requested_end"] = "2026-01-10"
    receipt["records"][0].update(actual_max_date="2026-01-10", requested_end="2026-01-10",
                                 filename="WIKI_PRICES_FICT_2026-01-01_2026-01-10.json",
                                 query_without_credentials="ticker=FICT&date.gte=2026-01-01&date.lte=2026-01-10&qopts.per_page=1000")
    payload, metadata, req = bind(body, receipt)
    req = replace(req, acquisition_end=date(2026, 1, 10))
    with pytest.raises(MarketContractError, match="invalid_wiki_observation_bounds"):
        wiki.inspect_wiki_bytes(payload, metadata, req)


def test_request_context_limit_is_inclusive(monkeypatch):
    payload, receipt, req = bind(*fixture())
    context = {key: value.isoformat() if type(value) is date else value
               for key, value in req.__dict__.items()}
    length = len(json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
    monkeypatch.setattr(wiki, "MAX_CONTEXT_BYTES", length)
    assert wiki.inspect_wiki_bytes(payload, receipt, req).observations
    monkeypatch.setattr(wiki, "MAX_CONTEXT_BYTES", length - 1)
    with pytest.raises(MarketContractError, match="invalid_wiki_context_bound"):
        wiki.inspect_wiki_bytes(payload, receipt, req)


@pytest.mark.parametrize("which,invalid", [("payload", b""), ("payload", "not bytes"),
                                            ("receipt", b""), ("receipt", bytearray(b"{}"))])
def test_input_types_and_empty_byte_bounds(which, invalid):
    payload, receipt, req = bind(*fixture())
    with pytest.raises(MarketContractError, match="invalid_wiki_byte_bound"):
        wiki.inspect_wiki_bytes(invalid if which == "payload" else payload,
                                invalid if which == "receipt" else receipt, req)


@pytest.mark.parametrize("which", ["payload", "receipt"])
def test_exact_byte_caps_and_one_byte_overflow(which, monkeypatch):
    payload, receipt, req = bind(*fixture())
    name, data = ("MAX_RESPONSE_BYTES", payload) if which == "payload" else ("MAX_RECEIPT_BYTES", receipt)
    monkeypatch.setattr(wiki, name, len(data))
    assert wiki.inspect_wiki_bytes(payload, receipt, req).observations
    with pytest.raises(MarketContractError, match="invalid_wiki_byte_bound"):
        wiki.inspect_wiki_bytes(payload + (b" " if which == "payload" else b""),
                                receipt + (b" " if which == "receipt" else b""), req)


def test_row_cap_and_inclusive_coverage_boundary():
    body, receipt = fixture()
    start = date(2022, 1, 1)
    end = start + timedelta(days=1460)
    body["datatable"]["data"] = [bar(str(start + timedelta(days=index))) for index in range(1000)]
    receipt.update(requested_start=str(start), requested_end=str(end))
    receipt["records"][0].update(requested_start=str(start), requested_end=str(end), rows=1000,
                                 actual_min_date=str(start), actual_max_date=str(start + timedelta(days=999)),
                                 filename=f"WIKI_PRICES_FICT_{start}_{end}.json",
                                 query_without_credentials=f"ticker=FICT&date.gte={start}&date.lte={end}&qopts.per_page=1000")
    payload, metadata, req = bind(body, receipt)
    req = replace(req, acquisition_start=start, acquisition_end=end, selection_start=start, selection_end=end)
    assert len(wiki.inspect_wiki_bytes(payload, metadata, req).observations) == 1000
    body["datatable"]["data"].append(bar(str(start + timedelta(days=1000))))
    payload, metadata, _ = bind(body, receipt)
    with pytest.raises(MarketContractError, match="invalid_wiki_row_bound"):
        wiki.inspect_wiki_bytes(payload, metadata, replace(req, expected_response_sha256=hashlib.sha256(payload).hexdigest()))


def test_pure_adapter_uses_no_file_network_or_application_services(monkeypatch):
    args = bind(*fixture())
    inspect()  # Warm standard-library strptime imports before guarding all I/O.

    def forbidden(*_args, **_kwargs):
        raise AssertionError("adapter attempted I/O")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(("sqlalchemy", "requests", "httpx", "sentence_transformers", "app.database",
                            "app.models", "app.main", "app.market_returns", "app.tiingo_eod_normalizer")):
            raise AssertionError("forbidden dependency")
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(Path, "open", forbidden)
        guard.setattr(os, "open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        guard.setattr(builtins, "__import__", guarded_import)
        assert wiki.inspect_wiki_bytes(*args).observations


def test_fresh_import_rejects_service_dependencies_and_inspection_has_no_io_audit_events():
    payload, receipt, _ = bind(*fixture())
    script = f'''
import builtins, datetime, sys, _strptime
original_import = builtins.__import__
def guard_import(name, *args, **kwargs):
    if name.startswith(("sqlalchemy", "requests", "httpx", "sentence_transformers")) or (
        name.startswith("app.") and name not in ("app.nasdaq_wiki_adapter", "app.market_data_contracts")):
        raise AssertionError("service import")
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard_import
from app.nasdaq_wiki_adapter import WikiInspectionRequest, inspect_wiki_bytes
from datetime import date
request = WikiInspectionRequest("FICT", {hashlib.sha256(payload).hexdigest()!r}, {RUN!r},
    date(2026,1,1), date(2026,1,9), date(2026,1,1), date(2026,1,9), "synthetic")
def audit(event, args):
    if event == "open" or event.startswith(("socket.", "subprocess.", "os.system")):
        raise AssertionError("inspection I/O")
sys.addaudithook(audit)
result = inspect_wiki_bytes({payload!r}, {receipt!r}, request)
assert len(result.observations) == 3
print("offline inspection passed")
'''
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "offline inspection passed"
