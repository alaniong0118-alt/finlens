"""Synthetic offline provider fixtures; no live APIs, DB or model dependencies."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, Inexact, ROUND_DOWN, Rounded, localcontext
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.market_data_contracts import (
    ExchangeCalendar, Listing, MarketContractError, PublicationPin, Security, Source,
    SymbolMapping, TradingSession, validate_publication,
)
from app.market_returns import calculate_returns
from app.tiingo_eod_normalizer import (
    FIELDS, TiingoEodFormat, TiingoEodRequest, normalize_tiingo_eod, parse_tiingo_eod,
)

D = Decimal
FIXTURES = Path(__file__).parent / "fixtures" / "tiingo_eod"
MON, TUE, WED = (date(2026, 1, day) for day in (5, 6, 7))
RETRIEVED = datetime(2026, 1, 9, 22, tzinfo=timezone.utc)


def fixture(name="ordinary"):
    return (FIXTURES / f"{name}.json").read_bytes()


def request(payload, *, days=(MON, TUE)):
    security = Security("synthetic-security", 1, "0000000001", "common")
    listing = Listing("synthetic-listing", security.security_id, "XNYS", "USD", "synthetic-calendar", MON,
                      continuity="same_security_verified")
    mapping = SymbolMapping("tiingo", "eod", "FICT", "FICT", security.security_id, listing.listing_id,
                            "XNYS", date(2000, 1, 1), None, True, "synthetic mapping declaration")
    calendar = ExchangeCalendar("synthetic-calendar", "synthetic-v1", "America/New_York", "regular_session_close",
        days[0], days[-1], tuple(TradingSession(day, datetime(day.year, day.month, day.day, 16,
                                      tzinfo=ZoneInfo("America/New_York"))) for day in days))
    source = Source("tiingo", "eod", "synthetic-response", hashlib.sha256(payload).hexdigest(), RETRIEVED, RETRIEVED)
    return TiingoEodRequest("FICT", security, listing, (mapping,), calendar, days[0], days[-1], source,
        "synthetic-publication-0", 0, RETRIEVED + timedelta(hours=1),
        TiingoEodFormat("new_shares_per_old_share", "synthetic-format-declaration-v1"))


def mutated_payload(field, value, *, remove=False):
    # Fixture values here are integers; financial Decimal parsing is the adapter's job.
    rows = json.loads(fixture())
    if remove:
        del rows[0][field]
    else:
        rows[0][field] = value
    return json.dumps(rows).encode()


def normalized(payload=None, req=None, **kwargs):
    payload = fixture() if payload is None else payload
    return normalize_tiingo_eod(payload, request(payload) if req is None else req, **kwargs)


def test_ordinary_fields_exact_mapping_sealing_and_explicit_unavailability():
    result = normalized()
    assert result.status == "blocked" and result.reasons == ("missing_corporate_action_coverage",)
    assert result.bars[1].raw.close == D(105) and result.bars[1].raw.volume == D(1200)
    assert result.bars[1].adjusted.close == D(105)
    assert result.bars[1].session_date == TUE
    assert result.bars[1].provider_timestamp == datetime(2026, 1, 6, tzinfo=timezone.utc)
    assert result.publication.prices[1].adjustment_basis == "raw"
    assert result.publication.prices[1].close == result.bars[1].raw.close
    assert result.publication.actions == result.publication.action_coverage == ()
    assert result.publication.state == "missing"
    assert validate_publication(result.publication) is result.publication
    assert result.publication.source.response_sha256 == hashlib.sha256(fixture()).hexdigest()
    assert result.normalized_content_sha256 != result.publication.source.response_sha256
    assert result.normalized_content_sha256 != result.publication.manifest.sha256
    assert result.normalized_content_sha256 in result.publication.prices[0].observation_ids[0]
    series = calculate_returns(result.publication)
    assert series.valid_interval_count == 0
    assert all(p.price_return is None and p.total_return is None for p in series.intervals)
    with pytest.raises(FrozenInstanceError):
        result.bars[0].raw.close = D(999)


@pytest.mark.parametrize("name,indicator,reason", [
    ("split", "split_factor", "unverified_split_event"),
    ("dividend", "div_cash", "unclassified_cash_distribution"),
])
def test_split_and_dividend_indicators_are_preserved_but_never_authorized(name, indicator, reason):
    result = normalized(fixture(name))
    assert getattr(result.bars[1], indicator) > 0
    assert reason in result.reasons and "unexplained_adjustment_difference" in result.reasons
    assert result.format.split_factor_direction == "new_shares_per_old_share"
    assert result.format.dividend_share_basis == "unverified"
    assert result.publication.state == "unsupported" and result.publication.actions == ()
    assert result.publication.prices[0].close == D(100)
    assert result.publication.prices[0].close != result.bars[0].adjusted.close
    assert calculate_returns(result.publication).valid_interval_count == 0


def test_reverse_split_and_same_day_cash_do_not_infer_direction_or_event_order():
    payload = mutated_payload("splitFactor", 0)  # Invalid zero split rejects rather than meaning no action.
    with pytest.raises(MarketContractError, match="invalid_action_indicator"):
        normalized(payload)
    payload = fixture().replace(b'"splitFactor":1', b'"splitFactor":0.1', 1).replace(b'"divCash":0', b'"divCash":1', 1)
    result = normalized(payload)
    assert result.bars[0].split_factor == D("0.1")
    assert "ambiguous_same_day_actions" in result.reasons
    assert result.publication.actions == () and calculate_returns(result.publication).valid_interval_count == 0


def test_cash_without_split_or_adjustment_still_cannot_be_classified_as_ordinary_dividend():
    result = normalized(mutated_payload("divCash", 1))
    assert "unclassified_cash_distribution" in result.reasons
    assert "ambiguous_same_day_actions" not in result.reasons
    assert result.publication.actions == ()


@pytest.mark.parametrize("field", sorted(FIELDS))
def test_every_documented_field_is_required(field):
    with pytest.raises(MarketContractError, match="missing_eod_field"):
        normalized(mutated_payload(field, None, remove=True))


@pytest.mark.parametrize("value", [None, True, False, "100", [], {}])
@pytest.mark.parametrize("field", ["close", "volume", "adjClose", "divCash", "splitFactor"])
def test_invalid_or_ambiguous_numeric_types_reject(field, value):
    with pytest.raises(MarketContractError, match="invalid_eod_numeric_type"):
        normalized(mutated_payload(field, value))


@pytest.mark.parametrize("token", [b"NaN", b"Infinity", b"-Infinity", b"1e999999999", b"1e-999999999",
                                   b"0e-999999999", b"1.1234567890123456789012345678", b"9" * 97])
def test_nonfinite_excess_precision_exponent_and_token_bounds(token):
    payload = fixture().replace(b'"close":100', b'"close":' + token, 1)
    with pytest.raises(MarketContractError):
        normalized(payload)


def test_decimal_precision_never_passes_through_binary_float_and_ignores_context():
    rows = fixture().replace(b'"close":100', b'"close":100.000000000000000001', 1)
    result = normalized(rows)
    assert result.bars[0].raw.close == D("100.000000000000000001")
    with localcontext() as context:
        context.prec, context.rounding = 2, ROUND_DOWN
        context.traps[Inexact] = context.traps[Rounded] = True
        assert normalized(rows) == result
    with pytest.raises(MarketContractError, match="invalid_response_bound"):
        parse_tiingo_eod([{"close": 100.0}])  # Already decoded floats cannot enter the adapter.


@pytest.mark.parametrize("field,value,reason", [
    ("open", 0, "nonpositive_ohlc"), ("close", -1, "nonpositive_ohlc"),
    ("high", 99, "inconsistent_ohlc"), ("low", 101, "inconsistent_ohlc"),
    ("adjHigh", 99, "inconsistent_ohlc"), ("adjClose", 0, "nonpositive_ohlc"),
    ("volume", -1, "negative_volume"), ("adjVolume", -1, "negative_volume"),
    ("divCash", -1, "invalid_action_indicator"), ("splitFactor", -1, "invalid_action_indicator"),
])
def test_invalid_bar_economics_reject(field, value, reason):
    with pytest.raises(MarketContractError, match=reason):
        normalized(mutated_payload(field, value))


def test_volume_rules_allow_zero_and_fractional_adjusted_but_not_raw_volume():
    payload = fixture().replace(b'"volume":1000', b'"volume":0', 1).replace(b'"adjVolume":1000', b'"adjVolume":0.125', 1)
    assert normalized(payload).bars[0].adjusted.volume == D("0.125")
    payload = fixture().replace(b'"volume":1000', b'"volume":1000.125', 1)
    with pytest.raises(MarketContractError, match="fractional_raw_volume"):
        normalized(payload)


@pytest.mark.parametrize("stamp", ["2026-01-05", "2026-01-05T16:00:00Z", "2026-01-05T00:00:00-05:00",
    "2026-01-05T00:00:00", "2026-01-05T00:00:00.001Z", "2026-02-30T00:00:00Z", "not-a-date", None])
def test_noncanonical_or_invalid_date_labels_reject(stamp):
    with pytest.raises(MarketContractError, match="invalid_eod_date_label"):
        normalized(mutated_payload("date", stamp))


def test_midnight_utc_date_label_is_not_converted_to_previous_new_york_session():
    result = normalized(mutated_payload("date", "2026-01-05T00:00:00+00:00"))
    assert result.bars[0].session_date == MON
    assert result.publication.calendar.sessions[0].close_at.hour == 16


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_and_conflicting_observations_reject_without_selection(conflicting):
    rows = json.loads(fixture())
    duplicate = dict(rows[0], close=101) if conflicting else rows[0]
    for values in (rows + [duplicate], [duplicate] + rows):
        with pytest.raises(MarketContractError, match="duplicate_eod_observation"):
            normalized(json.dumps(values).encode())


def test_duplicate_keys_unknown_fields_and_invalid_json_reject():
    duplicate_key = fixture().replace(b'"close":100', b'"close":100,"close":100', 1)
    with pytest.raises(MarketContractError, match="duplicate_json_field"):
        normalized(duplicate_key)
    with pytest.raises(MarketContractError, match="unsupported_eod_field"):
        normalized(mutated_payload("distributionType", "special"))
    for payload in (b"{", b"\xff", b"[" * 1500):
        with pytest.raises(MarketContractError, match="invalid_response_json"):
            parse_tiingo_eod(payload)


def test_bounded_inputs_and_non_array_responses_reject():
    with patch("app.tiingo_eod_normalizer.MAX_RESPONSE_BYTES", 10):
        with pytest.raises(MarketContractError, match="invalid_response_bound"):
            normalized()
    with patch("app.tiingo_eod_normalizer.MAX_SESSIONS", 1):
        with pytest.raises(MarketContractError, match="invalid_response_inventory"):
            normalized()
    with pytest.raises(MarketContractError, match="invalid_response_inventory"):
        parse_tiingo_eod(b"{}")
    payload = fixture()
    req = request(payload)
    distant = date(2060, 1, 6)
    with pytest.raises(MarketContractError, match="unbounded_response_coverage"):
        normalized(payload, replace(req, coverage_end=distant, calendar=replace(req.calendar, covered_end=distant)))


def test_missing_sessions_empty_response_and_off_calendar_dates_fail_closed():
    payload = fixture()
    result = normalized(payload, request(payload, days=(MON, TUE, WED)))
    assert "missing_session_observations" in result.reasons
    assert calculate_returns(result.publication).valid_interval_count == 0
    empty = normalized(b"[]")
    assert "empty_eod_response" in empty.reasons and empty.publication.prices == ()
    with pytest.raises(MarketContractError, match="eod_date_outside_listing_calendar"):
        normalized(mutated_payload("date", "2026-01-04T00:00:00Z"))


def test_changed_ohlcv_and_adjustment_metadata_are_bound_even_when_raw_closes_unchanged():
    original = normalized()
    for field in ("open", "adjOpen", "volume", "adjVolume", "divCash", "splitFactor"):
        value = 101 if field in {"open", "adjOpen"} else 2
        altered = normalized(mutated_payload(field, value))
        assert altered.publication.prices[0].close == original.publication.prices[0].close
        assert altered.normalized_content_sha256 != original.normalized_content_sha256
        assert altered.publication.manifest != original.publication.manifest


def test_response_reordering_preserves_normalized_content_but_not_raw_byte_receipt():
    payload = fixture()
    reordered = json.dumps(list(reversed(json.loads(payload))), sort_keys=True).encode()
    original, other = normalized(payload), normalized(reordered)
    assert original.bars == other.bars
    assert original.normalized_content_sha256 == other.normalized_content_sha256
    assert tuple(p.observation_ids for p in original.publication.prices) == tuple(p.observation_ids for p in other.publication.prices)
    assert original.publication.source.response_sha256 != other.publication.source.response_sha256
    assert original.publication.manifest != other.publication.manifest  # Receipt bytes MUST remain distinct.
    assert normalized(payload) == original


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: replace(r, symbol="OTHER"), "incompatible_request_symbol"),
    (lambda r: replace(r, security=replace(r.security, security_id="other")), "security_listing_mismatch"),
    (lambda r: replace(r, listing=replace(r.listing, mic="XNAS")), "mapping_security_mismatch"),
    (lambda r: replace(r, source=replace(r.source, product="other")), "incompatible_provider_product"),
    (lambda r: replace(r, source=replace(r.source, response_sha256="b" * 64)), "response_fingerprint_mismatch"),
    (lambda r: replace(r, calendar=replace(r.calendar, calendar_id="other")), "invalid_calendar_identity"),
    (lambda r: replace(r, coverage_start=TUE), "incompatible_response_coverage"),
    (lambda r: replace(r, mappings=(replace(r.mappings[0], identity_resolved=False),)), "unresolved_symbol_identity"),
    (lambda r: replace(r, mappings=(replace(r.mappings[0], effective_to=MON),)), "missing_symbol_mapping"),
    (lambda r: replace(r, format=replace(r.format, split_factor_direction="old_shares_per_new_share")), "unsupported_split_direction"),
    (lambda r: replace(r, format=replace(r.format, dividend_share_basis="previous_session_share")), "unsupported_dividend_basis"),
    (lambda r: replace(r, format=replace(r.format, declaration_reference="")), "missing_format_declaration"),
])
def test_explicit_identity_format_calendar_and_provenance_validation(mutation, reason):
    payload = fixture()
    with pytest.raises(MarketContractError, match=reason):
        normalized(payload, mutation(request(payload)))


def test_unresolved_continuity_is_blocked_not_an_implicit_listing_bridge():
    payload = fixture()
    req = request(payload)
    result = normalized(payload, replace(req, listing=replace(req.listing, continuity="unresolved")))
    assert "unsupported_security_continuity" in result.reasons and result.publication.state == "unsupported"
    assert calculate_returns(result.publication).valid_interval_count == 0


def test_source_and_identity_changes_cannot_reuse_normalized_or_publication_digests():
    payload = fixture()
    req = request(payload)
    original = normalized(payload, req)
    renamed = replace(req, symbol="OTHER", mappings=(replace(req.mappings[0], symbol="OTHER", ticker="OTHER"),))
    other = normalized(payload, renamed)
    assert original.normalized_content_sha256 != other.normalized_content_sha256
    assert original.publication.manifest != other.publication.manifest
    # Same normalized values under a different receipt/vintage still bind provenance.
    receipt_changed = normalized(payload, replace(req, source=replace(req.source, source_id="synthetic-response-2")))
    assert original.normalized_content_sha256 == receipt_changed.normalized_content_sha256
    assert original.publication.manifest != receipt_changed.publication.manifest


def test_semantically_equal_json_number_lexemes_keep_exact_bytes_separate():
    payload = fixture()
    other_payload = payload.replace(b'"close":100', b'"close":1.00e2', 1)
    first, second = normalized(payload), normalized(other_payload)
    assert first.bars == second.bars
    assert first.normalized_content_sha256 == second.normalized_content_sha256
    assert first.publication.source.response_sha256 != second.publication.source.response_sha256
    assert second.bars[0].raw.close.as_tuple() == D("1.00e2").as_tuple()


@pytest.mark.parametrize("mutation", [
    lambda r: replace(r, source=None),
    lambda r: replace(r, predecessor_pin="not-a-pin"),
    lambda r: replace(r, security=replace(r.security, issuer_cik=None)),
    lambda r: replace(r, coverage_start=datetime(2026, 1, 5)),
])
def test_malformed_request_contracts_raise_explicit_rejections(mutation):
    payload = fixture()
    with pytest.raises(MarketContractError):
        normalized(payload, mutation(request(payload)))


def test_source_time_must_follow_session_close_and_publication_follow_retrieval():
    payload = fixture()
    req = request(payload)
    early = datetime(2026, 1, 5, 1, tzinfo=timezone.utc)
    with pytest.raises(MarketContractError, match="closing_price_not_yet_available"):
        normalized(payload, replace(req, source=replace(req.source, retrieved_at=early, available_at=early)))
    with pytest.raises(MarketContractError, match="invalid_retrieval_time"):
        normalized(payload, replace(req, published_at=req.source.retrieved_at - timedelta(seconds=1)))


def test_successor_is_pinned_to_exact_parent_and_canonical_versions():
    payload = fixture()
    parent = normalized(payload).publication
    req = request(payload)
    pin = PublicationPin(parent.publication_id, parent.market_data_version, parent.manifest.sha256)
    child_request = replace(req, publication_id="synthetic-publication-1", market_data_version=1,
                            published_at=parent.published_at + timedelta(hours=1), predecessor_pin=pin)
    child = normalized(payload, child_request, predecessor=parent).publication
    assert validate_publication(child, parent) is child
    assert child.predecessor_manifest_sha256 == parent.manifest.sha256
    with pytest.raises(MarketContractError, match="predecessor_required"):
        normalized(payload, child_request)
    with pytest.raises(MarketContractError, match="predecessor_pin_mismatch"):
        normalized(payload, replace(child_request, predecessor_pin=replace(pin, manifest_sha256="b" * 64)), predecessor=parent)
    with pytest.raises(MarketContractError, match="invalid_supersession"):
        normalized(payload, replace(child_request, market_data_version=2), predecessor=parent)


def test_normalization_is_offline_and_does_not_import_application_or_provider_clients():
    with patch("socket.socket", side_effect=AssertionError("network forbidden")):
        result = normalized()
        assert result.status == "blocked"
