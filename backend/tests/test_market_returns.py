"""Deterministic synthetic market inputs only: no DB, provider, SEC or model."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DefaultContext, Inexact, ROUND_DOWN, Rounded, getcontext, localcontext
from fractions import Fraction
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.market_data_contracts import (
    ActionCoverage, CorporateAction, DatasetPin, ExchangeCalendar, LabelWindow, Listing,
    MarketContractError, MarketPublication, PriceObservation, PublicationPin, Security,
    Source, SymbolMapping, TradingSession, manifest_for, normalized_records, seal_publication,
    validate_dataset_pin, validate_prediction_cutoff, validate_publication,
    validate_symbol_mappings, validate_training_labels,
)
from app.market_returns import align_returns, calculate_returns, log_return, reinvested_growth

D = Decimal
MON, TUE, WED, THU = (date(2026, 1, day) for day in (5, 6, 7, 8))
RETRIEVED = datetime(2026, 1, 21, 20, tzinfo=timezone.utc)
SOURCE = Source("synthetic-provider", "synthetic-daily", "fixture-response", "a" * 64,
                RETRIEVED, RETRIEVED - timedelta(hours=1))


def publication(*, days=(MON, TUE), closes=("100", "100"), actions=(), security="security-a",
                currency="USD", first=None, source=SOURCE, close_hours=None, knowledge="retrospective_revised"):
    listing_id = f"listing-{security}"
    sessions = tuple(TradingSession(day, datetime(day.year, day.month, day.day,
                      (close_hours or {}).get(day, 16), tzinfo=ZoneInfo("America/New_York"))) for day in days)
    listing = Listing(listing_id, security, "XNYS", currency, "fixture-us-equities", first or days[0],
                      continuity="same_security_verified")
    prices = tuple(PriceObservation((f"{listing_id}-{day}",), listing_id, day, D(value), currency, "raw", (source,))
                   for day, value in zip(days, closes) if value is not None and day >= listing.first_session)
    coverage = tuple(ActionCoverage(a, b, "complete", True, True, True, source)
                     for a, b in zip(days, days[1:]) if a >= listing.first_session)
    return seal_publication(MarketPublication(
        f"publication-{security}-0", 0, None, max(RETRIEVED, source.retrieved_at) + timedelta(hours=1), knowledge, "complete",
        Security(security, 1 if security == "security-a" else 2, "0000000001", "common-A"), listing,
        (SymbolMapping(source.provider, source.product, f"SYMBOL-{security}", f"TICKER-{security}", security, listing_id,
                       "XNYS", date(2000, 1, 1), None, True, "synthetic reviewed mapping"),),
        ExchangeCalendar("fixture-us-equities", "fixture-calendar-v1", "America/New_York",
                         "regular_session_close", days[0], days[-1], sessions),
        prices, actions, coverage, source, "fixture-normalizer-v1"))


def changed(pub, **fields):
    return seal_publication(replace(pub, **fields))


def split(numerator="2", denominator="1", *, action_id="split-1", sequence=None, day=TUE):
    return CorporateAction(action_id, "listing-security-a", "split", day, None, (SOURCE,), sequence,
                           D(numerator), D(denominator))


def dividend(amount="1", *, basis="previous_session_share", reference=None, sequence=None,
             day=TUE, action_id="dividend-1", kind="cash_dividend", treatment="gross_cash"):
    return CorporateAction(action_id, "listing-security-a", kind, day, day, (SOURCE,), sequence,
                           cash_amount=D(amount), currency="USD", entitlement_basis=basis,
                           basis_split_id=reference, treatment=treatment)


def last(pub):
    return calculate_returns(pub).intervals[-1]


def pin(*pubs):
    return DatasetPin(tuple(p.security.security_id for p in pubs),
                      tuple(PublicationPin(p.publication_id, p.market_data_version, p.manifest.sha256) for p in pubs),
                      "synthetic-universe-v1")


@pytest.mark.parametrize("previous,current,actions,price,total", [
    ("100", "50", (split(),), "0", "0"),
    ("100", "99", (dividend(),), "-0.01", "0"),
    ("100", "49", (split(sequence=0), dividend("2", sequence=1)), "-0.02", "0"),
    ("10", "100", (split("1", "10"),), "0", "0"),
    ("100", "49", (split(sequence=0), dividend("1", basis="post_split_share", reference="split-1", sequence=1)), "-0.02", "0"),
    ("100", "99", (dividend(kind="special_cash_distribution"),), "-0.01", "0"),
    ("100", "105", (), "0.05", "0.05"),
])
def test_exact_split_dividend_and_raw_return_arithmetic(previous, current, actions, price, total):
    point = last(publication(closes=(previous, current), actions=actions))
    assert point.status == "available"
    assert point.price_return == D(price) and point.total_return == D(total)
    assert point.total_log_return == log_return(point.total_factor)
    assert point.observation_ids and point.action_ids == tuple(sorted(a.action_id for a in actions))


def test_each_distribution_uses_its_own_reference_not_the_final_split_factor():
    actions = (split(sequence=0), dividend("1", basis="post_split_share", reference="split-1", sequence=1),
               split("3", action_id="split-2", sequence=2),
               dividend("1", basis="previous_session_share", sequence=3, action_id="dividend-2"))
    # Six final shares at $10 plus $2 + $1 cash; blindly multiplying cash by 6 is wrong.
    point = last(publication(closes=("100", "10"), actions=tuple(reversed(actions))))
    assert point.price_return == D("-0.4") and point.total_return == D("-0.37")
    assert point.total_factor == D("0.63")


def test_fractional_share_reinvestment_is_not_cash_held():
    pub = publication(days=(MON, TUE, WED), closes=("100", "100", "100"),
        actions=(dividend("10", day=TUE), dividend("10", day=WED, action_id="dividend-2")))
    assert reinvested_growth(pub) == D("1.21")
    assert D("1.21") != (D(100) + D(10) + D(10)) / D(100)  # Cash held would be 1.20.


@pytest.mark.parametrize("value", [D("NaN"), D("sNaN"), D("Infinity"), D("-Infinity"), D(0), D(-1), 100.0,
                                   D("1e19"), D("1e-19"), D("1.1234567890123456789012345678")])
def test_invalid_prices_reject_without_numeric_fallback(value):
    pub = publication()
    # Do not seal nonfinite inputs: the manifest builder also rejects them.
    with pytest.raises(MarketContractError):
        bad = changed(pub, prices=(replace(pub.prices[0], close=value), pub.prices[1]))
        calculate_returns(bad)


@pytest.mark.parametrize("action", [split("0"), split("-1"), split("1", "0"), split("NaN"),
                                    dividend("-1"), dividend("Infinity")])
def test_invalid_actions_reject(action):
    with pytest.raises(MarketContractError):
        calculate_returns(publication(actions=(action,)))


@pytest.mark.parametrize("basis", ["split_adjusted", "total_return_adjusted", "vendor_adjusted"])
def test_adjusted_close_cannot_double_count_actions(basis):
    pub = publication(closes=("100", "99"), actions=(dividend(),))
    with pytest.raises(MarketContractError, match="adjusted_price_forbidden"):
        calculate_returns(changed(pub, prices=tuple(replace(p, adjustment_basis=basis) for p in pub.prices)))


@pytest.mark.parametrize("factor", [D(0), D(-1), D("NaN"), D("Infinity"), 1.0])
def test_log_domain_rejection(factor):
    with pytest.raises(MarketContractError, match="nonpositive_log_factor"):
        log_return(factor)


def test_precision_is_explicit_and_independent_of_ambient_context():
    pub = publication(closes=("3", "4"))
    expected = last(pub)
    assert expected.price_return == D("0.333333333333333333")
    assert expected.price_log_return == D("0.287682072451780927")
    assert len(expected.price_factor.as_tuple().digits) == 80  # Working factor was not display-rounded.
    with localcontext() as context:
        context.prec, context.rounding = 2, ROUND_DOWN
        assert last(pub) == expected
        assert log_return(D("1.333333333333333333333333333333")) == expected.price_log_return
    assert getcontext().prec >= 2  # Test never mutates the caller's global context.
    underflow = last(publication(closes=("1e18", "1e-18")))
    assert underflow.status == "unavailable" and underflow.reason == "precision_underflow"
    assert underflow.price_return is None


@pytest.mark.parametrize("actions,reason", [
    ((split(), dividend()), "ambiguous_same_day_action_order"),
    ((split(sequence=1), dividend(sequence=1)), "ambiguous_same_day_action_order"),
    ((dividend(basis="unknown"),), "ambiguous_cash_share_basis"),
    ((dividend(reference="split-1"),), "ambiguous_cash_share_basis"),
    ((split(sequence=2), dividend(basis="post_split_share", reference="split-1", sequence=1)), "unresolved_cash_share_basis"),
    ((dividend(kind="special_cash_distribution", treatment=None),), "unsupported_cash_treatment"),
    ((CorporateAction("action", "listing-security-a", "spin_off", TUE, TUE, (SOURCE,)),), "unsupported_corporate_action"),
    ((CorporateAction("action", "listing-security-a", "merger", TUE, TUE, (SOURCE,)),), "unsupported_corporate_action"),
    ((CorporateAction("action", "listing-security-a", "stock_distribution", TUE, TUE, (SOURCE,)),), "unsupported_corporate_action"),
])
def test_ambiguous_or_unsupported_actions_abstain(actions, reason):
    point = last(publication(actions=actions))
    assert point.reason == reason and point.status == "unavailable"
    assert point.price_return is None and point.total_return is None


def test_cash_uses_authoritative_ex_date_not_payment_or_record_date():
    with pytest.raises(MarketContractError, match="authoritative_ex_date_required"):
        calculate_returns(publication(actions=(replace(dividend(), ex_date=WED),)))
    with pytest.raises(MarketContractError, match="authoritative_ex_date_required"):
        calculate_returns(publication(actions=(replace(dividend(), ex_date=None),)))


def test_supplied_holiday_half_day_and_timezone_sessions():
    # Synthetic calendar explicitly omits a holiday/weekend; a 13:00 half-day is valid.
    before, after = date(2026, 1, 16), date(2026, 1, 20)
    pub = publication(days=(before, after), closes=("100", "101"), close_hours={before: 13})
    result = calculate_returns(pub)
    assert result.expected_interval_count == result.valid_interval_count == 1
    assert result.intervals[-1].start.hour == 13
    assert result.intervals[-1].price_return == D("0.01")
    assert result.intervals[0].reason == "first_listing_observation"
    with pytest.raises(MarketContractError, match="invalid_session_close"):
        validate_publication(changed(pub, calendar=replace(pub.calendar, sessions=(
            replace(pub.calendar.sessions[0], close_at=datetime(2026, 1, 16, 13)), pub.calendar.sessions[1]))))


def test_missing_tuesday_never_becomes_monday_wednesday_return_and_resumes_thursday():
    pub = publication(days=(MON, TUE, WED, THU), closes=("100", None, "110", "121"))
    series = calculate_returns(pub)
    assert [point.reason for point in series.intervals] == ["first_listing_observation", "missing_current_price",
                                                          "missing_previous_price", None]
    assert series.expected_interval_count == 3 and series.valid_interval_count == 1
    assert series.intervals[-1].price_return == D("0.1")
    assert all(point.price_return is None for point in series.intervals[:-1])
    with pytest.raises(MarketContractError, match="incomplete_reinvestment_path"):
        reinvested_growth(pub)


def test_first_listing_does_not_borrow_a_prelisting_price():
    pub = publication(days=(MON, TUE, WED), closes=("999", "100", "110"), first=TUE)
    series = calculate_returns(pub)
    assert series.expected_interval_count == 1 and len(series.intervals) == 2
    assert series.intervals[0].start is None
    with pytest.raises(MarketContractError, match="nonadjacent_action_coverage"):
        changed_coverage = replace(pub.action_coverage[0], start=MON)
        validate_publication(changed(pub, action_coverage=(changed_coverage,)))


@pytest.mark.parametrize("field", ["splits_complete", "cash_complete", "other_actions_complete"])
def test_missing_action_completeness_cannot_mean_no_actions(field):
    pub = publication()
    item = replace(pub.action_coverage[0], **{field: False})
    assert last(changed(pub, action_coverage=(item,))).reason == "incomplete_action_coverage"
    assert last(changed(pub, action_coverage=())).reason == "missing_action_coverage"


@pytest.mark.parametrize("state", ["missing", "stale", "conflicting", "unsupported"])
def test_unavailable_states_remain_distinct(state):
    pub = publication()
    assert last(changed(pub, state=state)).reason == f"{state}_publication"
    coverage = replace(pub.action_coverage[0], state=state)
    assert last(changed(pub, action_coverage=(coverage,))).reason == f"{state}_action_coverage"


def test_alignment_is_deterministic_and_computes_returns_before_matching_intervals():
    a = publication(days=(MON, TUE, WED, THU), closes=("100", None, "110", "121"))
    b = publication(days=(MON, TUE, WED, THU), closes=("100", "105", "110", "121"), security="security-b")
    result = align_returns((b, a), pin(a, b))
    assert result == align_returns((a, b), pin(a, b))
    assert result.security_ids == ("security-a", "security-b") and result.aligned_interval_count == 1
    assert result.intervals == ((a.calendar.sessions[2].close_at, a.calendar.sessions[3].close_at),)
    assert result.price_returns == ((D("0.1"), D("0.1")),)
    assert result.expected_counts == (("security-a", 3), ("security-b", 3))
    assert result.valid_counts == (("security-a", 1), ("security-b", 3))
    assert ("security-b", "unaligned_interval", 2) in result.exclusions


def test_matching_end_alone_never_aligns_different_start_closes():
    a = publication()
    b = publication(security="security-b", close_hours={MON: 13})
    result = align_returns((a, b), pin(a, b))
    assert result.aligned_interval_count == 0 and result.status == "unavailable"


@pytest.mark.parametrize("change", ["calendar", "calendar_version", "currency", "provider", "product", "normalizer"])
def test_incompatible_panel_contracts_never_mix(change):
    a, b = publication(), publication(security="security-b")
    if change == "calendar":
        b = changed(b, calendar=replace(b.calendar, calendar_id="different"), listing=replace(b.listing, calendar_id="different"))
    elif change == "calendar_version": b = changed(b, calendar=replace(b.calendar, version="different"))
    elif change == "currency":
        b = changed(b, listing=replace(b.listing, currency="EUR"), prices=tuple(replace(p, currency="EUR") for p in b.prices))
    elif change == "normalizer": b = changed(b, normalizer_version="different")
    else:
        source = replace(SOURCE, **{change: "different"})
        b = publication(security="security-b", source=source)
    result = align_returns((a, b), pin(a, b))
    assert result.reason == "incompatible_panel_contract" and result.aligned_interval_count == 0


def test_price_action_and_provider_currency_provenance_isolation():
    pub = publication()
    for prices, code in [((replace(pub.prices[0], currency="EUR"), pub.prices[1]), "currency_mismatch"),
                         ((replace(pub.prices[0], sources=(replace(SOURCE, provider="fallback"),)), pub.prices[1]), "mixed_provider_product")]:
        with pytest.raises(MarketContractError, match=code):
            validate_publication(changed(pub, prices=prices))
    for action, code in [(replace(dividend(), currency="EUR"), "currency_mismatch"),
                         (replace(dividend(), sources=(replace(SOURCE, product="fallback"),)), "mixed_provider_product")]:
        with pytest.raises(MarketContractError, match=code):
            validate_publication(changed(pub, actions=(action,)))


def test_effective_dated_symbol_identity_and_ticker_reuse():
    mapping = publication().mappings[0]
    with pytest.raises(MarketContractError, match="ambiguous_symbol_mapping"):
        validate_symbol_mappings((mapping, replace(mapping, symbol="NEW")))
    with pytest.raises(MarketContractError, match="ambiguous_ticker_identity"):
        validate_symbol_mappings((mapping, replace(mapping, security_id="other", listing_id="other-listing")))
    old = replace(mapping, effective_to=date(2025, 12, 31))
    new = replace(mapping, effective_from=MON, security_id="other", listing_id="other-listing")
    assert len(validate_symbol_mappings((new, old))) == 2  # Explicit resolved identities, no automatic continuity.
    with pytest.raises(MarketContractError, match="unresolved_symbol_identity"):
        validate_symbol_mappings((old, replace(new, identity_resolved=False)))
    pub = publication()
    assert last(changed(pub, listing=replace(pub.listing, continuity="unresolved"))).reason == "unresolved_security_continuity"


def test_conflicting_raw_candidates_reject_and_identical_duplicates_retain_lineage():
    pub = publication(actions=(dividend(),))
    receipt = replace(SOURCE, source_id="second-receipt", response_sha256="b" * 64)
    duplicate_price = replace(pub.prices[0], observation_ids=("duplicate-id",), sources=(receipt,))
    duplicate_action = replace(pub.actions[0], sources=(receipt,))
    doubled = changed(pub, prices=pub.prices + (duplicate_price,), actions=pub.actions + (duplicate_action,))
    assert last(doubled).total_return == D("0.01")  # Dividend counted once.
    prices, actions = normalized_records(doubled)
    assert len(prices) == 2 and len(actions) == 1
    assert "duplicate-id" in prices[0].observation_ids and len(prices[0].sources) == 2
    assert len(actions[0].sources) == 2
    assert doubled.manifest.price_count == 3 and doubled.manifest.action_count == 2
    for fields, code in [({"prices": pub.prices + (replace(pub.prices[0], close=D(101)),)}, "conflicting_price"),
                         ({"actions": pub.actions + (replace(pub.actions[0], cash_amount=D(2)),)}, "conflicting_corporate")]:
        with pytest.raises(MarketContractError, match=code): validate_publication(changed(pub, **fields))


def test_manifest_counts_digests_and_immutable_supersession():
    pub = publication()
    original = pub.manifest
    with pytest.raises(FrozenInstanceError): pub.market_data_version = 1
    with pytest.raises(MarketContractError, match="incomplete_or_changed_manifest"):
        validate_publication(replace(pub, prices=pub.prices[:-1]))
    with pytest.raises(MarketContractError, match="incomplete_or_changed_manifest"):
        validate_publication(replace(pub, manifest=replace(pub.manifest, action_count=1)))
    revised = changed(pub, publication_id="revision-1", market_data_version=1, supersedes=pub.publication_id,
                      predecessor_market_data_version=pub.market_data_version,
                      predecessor_manifest_sha256=pub.manifest.sha256,
                      published_at=pub.published_at + timedelta(hours=1),
                      prices=(pub.prices[0], replace(pub.prices[1], close=D(110))))
    assert validate_publication(revised, pub) is revised
    assert calculate_returns(revised, pub).intervals[-1].price_return == D("0.1")
    assert pub.manifest == original and last(pub).price_return == 0
    assert revised.manifest.sha256 != original.sha256
    with pytest.raises(MarketContractError, match="predecessor_required"): validate_publication(revised)
    for fields, code in [({"market_data_version": 0}, "invalid_supersession"),
                         ({"publication_id": pub.publication_id}, "invalid_supersession"),
                         ({"supersedes": "wrong"}, "invalid_supersession"),
                         ({"security": replace(pub.security, share_class="converted")}, "unreviewed_security_succession")]:
        with pytest.raises(MarketContractError, match=code): validate_publication(changed(revised, **fields), pub)


def test_vintage_universe_and_calculation_version_pins():
    pub = publication()
    validate_dataset_pin((pub,), pin(pub))
    for bad in [replace(pin(pub), security_ids=("other",)),
                replace(pin(pub), publications=(replace(pin(pub).publications[0], market_data_version=1),)),
                replace(pin(pub), publications=(replace(pin(pub).publications[0], manifest_sha256="b" * 64),))]:
        with pytest.raises(MarketContractError): validate_dataset_pin((pub,), bad)
    with pytest.raises(MarketContractError, match="unsupported_calculation_policy"):
        validate_publication(changed(pub, calculation_version="future"))
    with pytest.raises(MarketContractError, match="unsupported_calculation_policy"):
        validate_publication(changed(pub, precision_version="future"))
    assert not any("evidence_version" == key or "facts_version" == key for key in pub.__dataclass_fields__)


def test_knowledge_time_and_revised_historical_leakage_guards():
    pub = publication(knowledge="observed_as_of", actions=(dividend(),))
    validate_prediction_cutoff((pub,), pin(pub), pub.published_at)
    retrospective = changed(pub, knowledge_mode="retrospective_revised")
    with pytest.raises(MarketContractError, match="retrospective_data_not_point_in_time"):
        validate_prediction_cutoff((retrospective,), pin(retrospective), pub.published_at)
    with pytest.raises(MarketContractError, match="revision_after_cutoff"):
        validate_prediction_cutoff((pub,), pin(pub), pub.published_at - timedelta(seconds=1))
    unknown = publication(knowledge="observed_as_of", source=replace(SOURCE, available_at=None))
    with pytest.raises(MarketContractError, match="source_not_known_at_cutoff"):
        validate_prediction_cutoff((unknown,), pin(unknown), pub.published_at)
    # Old economic dates do not make a later receipt/revision historically knowable.
    later = changed(pub, publication_id="later-revision", market_data_version=1, supersedes=pub.publication_id,
                    predecessor_market_data_version=pub.market_data_version,
                    predecessor_manifest_sha256=pub.manifest.sha256,
                    published_at=pub.published_at + timedelta(hours=2),
                    source=replace(SOURCE, retrieved_at=pub.published_at + timedelta(hours=1),
                                   available_at=pub.published_at + timedelta(minutes=1)))
    with pytest.raises(MarketContractError, match="revision_after_cutoff"):
        validate_prediction_cutoff((later,), pin(later), pub.published_at, predecessors=(pub,))


def test_forward_label_windows_cannot_cross_training_cutoff_or_availability():
    cutoff = RETRIEVED
    good = LabelWindow(cutoff - timedelta(days=3), cutoff - timedelta(days=2),
                       cutoff - timedelta(days=1), cutoff)
    validate_training_labels((good,), cutoff)
    for bad in [replace(good, end_at=cutoff + timedelta(hours=1), available_at=cutoff + timedelta(hours=2)),
                replace(good, available_at=cutoff + timedelta(seconds=1))]:
        with pytest.raises(MarketContractError, match="forward_label_crosses_training_cutoff"):
            validate_training_labels((bad,), cutoff)
    with pytest.raises(MarketContractError, match="invalid_forward_label_window"):
        validate_training_labels((replace(good, prediction_at=good.end_at),), cutoff)


def test_reproducibility_order_and_no_network_dependencies():
    pub = publication(actions=(split(sequence=0), dividend(sequence=1)))
    reordered = changed(pub, prices=tuple(reversed(pub.prices)), actions=tuple(reversed(pub.actions)))
    assert reordered.manifest == pub.manifest
    assert calculate_returns(reordered).intervals == calculate_returns(pub).intervals
    with patch("socket.socket", side_effect=AssertionError("network forbidden")):
        assert last(publication()).total_return == 0


def test_split_ratio_precision_final_half_even_and_unrounded_chaining():
    # HALF_EVEN at the final 18th place: ties below/above an even retained digit.
    assert last(publication(closes=("1", "1.0000000000000000005"))).price_return == D("0e-18")
    assert last(publication(closes=("1", "1.0000000000000000015"))).price_return == D("2e-18")
    assert last(publication(closes=("3", "2"), actions=(split("3", "2"),))).total_return == 0
    pub = publication(days=(MON, TUE, WED), closes=("3", "4", "3"))
    assert reinvested_growth(pub) == D("1.000000000000000000")


def test_dividend_before_split_and_later_split_reference_are_explicit():
    old_cash = last(publication(closes=("100", "49"),
                               actions=(dividend("2", sequence=0), split(sequence=1))))
    assert old_cash.total_return == 0
    actions = (split(sequence=0), split("3", action_id="split-2", sequence=1),
               dividend("1", basis="post_split_share", reference="split-2", sequence=2))
    assert last(publication(closes=("100", "10"), actions=actions)).total_return == D("-0.34")


def test_first_and_unsupported_class_conversion_cannot_establish_continuity():
    pub = publication(days=(MON,), closes=("100",))
    assert calculate_returns(pub).expected_interval_count == 0
    result = align_returns((pub,), pin(pub))
    assert result.reason == "no_common_intervals" and result.aligned_interval_count == 0
    action = CorporateAction("convert", "listing-security-a", "class_conversion", TUE, TUE, (SOURCE,))
    assert last(publication(actions=(action,))).reason == "unsupported_corporate_action"


def test_supplied_calendar_duplicates_bounds_and_nonadjacent_intervals():
    pub = publication(days=(MON, TUE, WED), closes=("100", "100", "100"))
    for sessions in (tuple(reversed(pub.calendar.sessions)), pub.calendar.sessions + (pub.calendar.sessions[-1],)):
        with pytest.raises(MarketContractError, match="ambiguous_calendar_sessions"):
            validate_publication(changed(pub, calendar=replace(pub.calendar, sessions=sessions)))
    with pytest.raises(MarketContractError, match="nonadjacent_action_coverage"):
        validate_publication(changed(pub, action_coverage=(replace(pub.action_coverage[0], end=WED),)))
    with pytest.raises(MarketContractError, match="invalid_session_close"):
        bad_session = replace(pub.calendar.sessions[0], close_at=datetime(2026, 1, 4, 16, tzinfo=timezone.utc))
        validate_publication(changed(pub, calendar=replace(pub.calendar, sessions=(bad_session, *pub.calendar.sessions[1:]))))


def test_raw_inventory_bounds_reject_before_candidate_deduplication(monkeypatch):
    import app.market_data_contracts as contracts
    pub = publication()
    monkeypatch.setattr(contracts, "MAX_SESSIONS", 2)
    with pytest.raises(MarketContractError, match="invalid_inventory_bound"):
        validate_publication(changed(pub, prices=pub.prices + (pub.prices[0],)))
    with pytest.raises(MarketContractError, match="invalid_calendar_scope"):
        validate_publication(publication(days=(MON, TUE, WED), closes=("100", "100", "100")))


def test_complete_manifest_and_source_hash_do_not_authenticate_source_truth():
    pub = publication()
    assert validate_publication(pub) is pub  # Synthetic receipt is only a supplied-input assertion.
    with pytest.raises(MarketContractError, match="invalid_source_fingerprint"):
        validate_publication(changed(pub, source=replace(SOURCE, response_sha256="not-a-hash")))
    with pytest.raises(MarketContractError, match="missing_source_provenance"):
        validate_publication(changed(pub, prices=(replace(pub.prices[0], sources=()), pub.prices[1])))
    with pytest.raises(MarketContractError, match="invalid_retrieval_time"):
        validate_publication(changed(pub, source=replace(SOURCE, retrieved_at=pub.published_at + timedelta(seconds=1))))
    with pytest.raises(MarketContractError, match="closing_price_not_yet_available"):
        early = replace(SOURCE, available_at=pub.calendar.sessions[0].close_at - timedelta(seconds=1))
        validate_publication(changed(pub, prices=(replace(pub.prices[0], sources=(early,)), pub.prices[1])))


def test_market_vintage_changed_manifest_and_duplicate_universe_reject():
    pub = publication()
    with pytest.raises(MarketContractError, match="incomplete_or_changed_manifest"):
        validate_dataset_pin((replace(pub, prices=pub.prices[:-1]),), pin(pub))
    with pytest.raises(MarketContractError, match="duplicate_publication_id"):
        validate_dataset_pin((pub, pub), replace(pin(pub), security_ids=("security-a", "security-a")))
    with pytest.raises(MarketContractError, match="duplicate_publication_id"):
        validate_dataset_pin((pub,), replace(pin(pub), publications=pin(pub).publications * 2))
    with pytest.raises(MarketContractError, match="invalid_universe_pin"):
        validate_dataset_pin((pub,), replace(pin(pub), universe_basis="survivorship_bias_free"))


def test_revised_alignment_requires_predecessor_and_fresh_exact_pin():
    pub = publication()
    revised = changed(pub, publication_id="revision", market_data_version=1, supersedes=pub.publication_id,
                      predecessor_market_data_version=pub.market_data_version,
                      predecessor_manifest_sha256=pub.manifest.sha256,
                      published_at=pub.published_at + timedelta(hours=1),
                      prices=(pub.prices[0], replace(pub.prices[1], close=D(110))))
    with pytest.raises(MarketContractError, match="unpinned_publication_vintage"):
        align_returns((revised,), pin(pub), predecessors=(pub,))
    with pytest.raises(MarketContractError, match="predecessor_required"):
        align_returns((revised,), pin(revised))
    with pytest.raises(MarketContractError, match="ambiguous_predecessor"):
        align_returns((revised,), pin(revised), predecessors=(pub, pub))
    panel = align_returns((revised,), pin(revised), predecessors=(pub,))
    assert panel.total_returns == ((D("0.1"),),)
    # A hash-matching but invalid predecessor cannot establish a valid correction.
    bad_parent = changed(pub, prices=(replace(pub.prices[0], close=D(-100)), pub.prices[1]))
    with pytest.raises(MarketContractError, match="invalid_raw_close"):
        validate_publication(revised, bad_parent)


def test_calendar_version_and_provider_mapping_are_manifest_bound():
    pub = publication()
    with pytest.raises(MarketContractError, match="incomplete_or_changed_manifest"):
        validate_publication(replace(pub, calendar=replace(pub.calendar, version="revised-calendar")))
    with pytest.raises(MarketContractError, match="mapping_security_mismatch"):
        validate_publication(changed(pub, mappings=(replace(pub.mappings[0], security_id="other"),)))
    with pytest.raises(MarketContractError, match="mixed_provider_product"):
        validate_publication(changed(pub, mappings=(replace(pub.mappings[0], provider="fallback"),)))
    with pytest.raises(MarketContractError, match="missing_symbol_mapping"):
        validate_publication(changed(pub, mappings=(replace(pub.mappings[0], effective_from=WED),)))


def test_action_knowledge_time_and_future_adjustment_factors_are_not_features():
    pub = publication(knowledge="observed_as_of", actions=(replace(dividend(), sources=(replace(SOURCE, available_at=None),)),))
    with pytest.raises(MarketContractError, match="source_not_known_at_cutoff"):
        validate_prediction_cutoff((pub,), pin(pub), pub.published_at)
    future = date(2026, 1, 22)
    pub = publication(days=(MON, TUE, future), closes=("100", "100", None),
                      actions=(split(day=future),), knowledge="observed_as_of")
    with pytest.raises(MarketContractError, match="economic_event_after_cutoff"):
        validate_prediction_cutoff((pub,), pin(pub), pub.published_at)


def test_timezone_knowledge_and_overlapping_labels_at_cutoff():
    pub = publication(knowledge="observed_as_of")
    with pytest.raises(MarketContractError, match="invalid_prediction_cutoff"):
        validate_prediction_cutoff((pub,), pin(pub), datetime(2026, 1, 22))
    cutoff = RETRIEVED
    training = LabelWindow(cutoff - timedelta(days=3), cutoff - timedelta(days=2),
                           cutoff - timedelta(days=1), cutoff)
    overlap = LabelWindow(cutoff - timedelta(days=2), cutoff - timedelta(days=1),
                          cutoff + timedelta(days=1), cutoff + timedelta(days=1))
    with pytest.raises(MarketContractError, match="forward_label_crosses_training_cutoff"):
        validate_training_labels((training, overlap), cutoff)
    with pytest.raises(MarketContractError, match="invalid_training_cutoff"):
        validate_training_labels((training,), datetime(2026, 1, 22))


def test_offline_modules_do_not_import_application_or_storage_services():
    import ast
    from pathlib import Path
    for name in ("market_data_contracts.py", "market_returns.py"):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "app" / name).read_text(encoding="utf-8"))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
        assert all(not module.startswith("app.") or module == "app.market_data_contracts" for module in imports)
        assert not any(module.startswith(("sqlalchemy", "httpx", "openai")) for module in imports)


def test_observation_identifiers_cannot_be_reused_across_different_sessions():
    pub = publication()
    reused = replace(pub.prices[1], observation_ids=pub.prices[0].observation_ids)
    with pytest.raises(MarketContractError, match="reused_observation_identity"):
        validate_publication(changed(pub, prices=(pub.prices[0], reused)))


def test_same_calendar_version_cannot_hide_conflicting_schedules():
    a = publication(days=(MON, TUE, WED, THU), closes=("100", "100", "100", "100"))
    b = publication(days=(MON, WED, THU), closes=("100", "100", "100"), security="security-b")
    result = align_returns((a, b), pin(a, b))
    assert result.reason == "calendar_schedule_conflict" and result.aligned_interval_count == 0
    assert ("security-b", "calendar_schedule_conflict", 2) in result.exclusions


def test_calendar_subranges_align_only_compatible_shared_intervals():
    a = publication(days=(MON, TUE, WED, THU), closes=("100", "100", "100", "100"))
    b = publication(days=(TUE, WED, THU), closes=("100", "100", "100"), security="security-b")
    result = align_returns((a, b), pin(a, b))
    assert result.aligned_interval_count == 2 and result.status == "available"


@pytest.mark.parametrize("value", [D("NaN"), D("Infinity"), 2.0])
def test_even_unsupported_action_payloads_cannot_contain_invalid_numeric_values(value):
    action = CorporateAction("unsupported", "listing-security-a", "spin_off", TUE, TUE, (SOURCE,), cash_amount=value)
    with pytest.raises(MarketContractError):
        validate_publication(publication(actions=(action,)))


def test_immutable_tuple_inventory_and_invalid_market_versions():
    pub = publication()
    with pytest.raises(MarketContractError, match="invalid_inventory_bound"):
        validate_publication(changed(pub, prices=list(pub.prices)))
    for version in (-1, True, 1.0):
        with pytest.raises(MarketContractError, match="invalid_market_version"):
            validate_publication(changed(pub, market_data_version=version))
    with pytest.raises(MarketContractError, match="security_listing_mismatch"):
        validate_publication(changed(pub, listing=replace(pub.listing, listing_id=pub.security.security_id)))


def test_adjusted_factors_and_unknown_sources_do_not_pass_the_leakage_gate():
    pub = publication(knowledge="observed_as_of")
    adjusted = changed(pub, prices=tuple(replace(p, adjustment_basis="vendor_adjusted") for p in pub.prices))
    with pytest.raises(MarketContractError, match="adjusted_price_forbidden"):
        validate_prediction_cutoff((adjusted,), pin(adjusted), pub.published_at)
    with pytest.raises(MarketContractError, match="invalid_source_availability"):
        bad = publication(knowledge="observed_as_of", source=replace(SOURCE, available_at=RETRIEVED + timedelta(seconds=1)))
        validate_prediction_cutoff((bad,), pin(bad), bad.published_at)


def test_dst_changes_elapsed_hours_not_exchange_session_adjacency():
    before, after = date(2026, 3, 6), date(2026, 3, 9)
    retrieved = datetime(2026, 3, 10, 20, tzinfo=timezone.utc)
    source = replace(SOURCE, retrieved_at=retrieved, available_at=retrieved)
    pub = publication(days=(before, after), closes=("100", "101"), source=source)
    first, second = pub.calendar.sessions
    assert first.close_at.utcoffset() == timedelta(hours=-5)
    assert second.close_at.utcoffset() == timedelta(hours=-4)
    assert second.close_at.astimezone(timezone.utc) - first.close_at.astimezone(timezone.utc) == timedelta(hours=71)
    assert last(pub).price_return == D("0.01")


def test_announced_action_can_be_known_before_its_economic_effective_date():
    earlier = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    source = replace(SOURCE, retrieved_at=earlier, available_at=earlier)
    pub = publication(actions=(replace(dividend(), sources=(source,)),), knowledge="observed_as_of")
    assert last(pub).total_return == D("0.01")
    validate_prediction_cutoff((pub,), pin(pub), pub.published_at)


def test_forward_label_can_start_at_prediction_but_must_end_in_the_future():
    prediction = RETRIEVED - timedelta(days=2)
    valid = LabelWindow(prediction, prediction, RETRIEVED - timedelta(days=1), RETRIEVED)
    validate_training_labels((valid,), RETRIEVED)
    with pytest.raises(MarketContractError, match="invalid_forward_label_window"):
        validate_training_labels((replace(valid, end_at=prediction),), RETRIEVED)


@pytest.mark.parametrize("current,expected", [
    ("1.0000000000000000005", "0e-18"),
    ("1.0000000000000000015", "2e-18"),
    ("1.0000000000000000025", "2e-18"),
    ("0.9999999999999999995", "-0e-18"),
    ("0.9999999999999999985", "-2e-18"),
    ("0.9999999999999999975", "-2e-18"),
])
@pytest.mark.parametrize("ratios", [(), (("21", "22"), ("22", "21")),
                                       (("2", "3"), ("15", "14"), ("7", "5"))])
def test_exact_cancelled_split_decompositions_preserve_signed_half_even_ties(current, expected, ratios):
    actions = tuple(split(n, d, action_id=f"split-{i}", sequence=i) for i, (n, d) in enumerate(ratios))
    assert all(isinstance(a.split_numerator, D) for a in actions)
    point = last(publication(closes=("1", current), actions=actions))
    assert point.status == "available"
    assert point.price_return == point.total_return == D(expected)
    with localcontext() as context:
        context.prec, context.rounding = 2, ROUND_DOWN
        assert last(publication(closes=("1", current), actions=actions)) == point


@pytest.mark.parametrize("end,expected", [
    ("1.0000000000000000005", "1.000000000000000000"),
    ("1.0000000000000000015", "1.000000000000000002"),
    ("0.9999999999999999995", "1.000000000000000000"),
    ("0.9999999999999999985", "0.999999999999999998"),
])
def test_exact_chained_growth_ties_do_not_consume_decimal_factor_approximations(end, expected):
    pub = publication(days=(MON, TUE, WED), closes=("1", "3", end),
                      actions=(split("21", "22", day=TUE), split("22", "21", day=WED, action_id="split-2")))
    assert reinvested_growth(pub) == D(expected)
    with localcontext() as context:
        context.prec, context.rounding = 2, ROUND_DOWN
        assert reinvested_growth(pub) == D(expected)


def test_exact_rational_cash_and_multiday_compounding_against_reference():
    pub = publication(days=(MON, TUE, WED, THU), closes=("7", "11", "13", "17"), actions=(
        split("21", "22", sequence=0),
        dividend("0.125", basis="post_split_share", reference="split-1", sequence=1),
        split("22", "21", day=WED, action_id="split-2"),
        dividend("0.25", day=THU, action_id="dividend-2")))
    # Reference specifies the economic expression independently of engine helpers.
    factors = ((Fraction(21, 22) * (11 + Fraction(1, 8))) / 7,
               Fraction(22, 21) * 13 / 11, (17 + Fraction(1, 4)) / 13)
    reference = factors[0] * factors[1] * factors[2]
    with localcontext() as context:
        context.prec = 300
        expected_growth = (D(reference.numerator) / D(reference.denominator)).quantize(D("1e-18"))
        expected_returns = tuple((D(f.numerator) / D(f.denominator) - 1).quantize(D("1e-18")) for f in factors)
    assert reinvested_growth(pub) == expected_growth
    assert tuple(p.total_return for p in calculate_returns(pub).intervals[1:]) == expected_returns


def test_uncertified_log_rounding_is_unavailable_not_an_approximate_available_result():
    with patch("app.market_returns.LOG_PRECISIONS", (1,)):
        point = last(publication(closes=("3", "4")))
        assert point.status == "unavailable" and point.reason == "precision_limited"
        assert point.price_return is None and point.total_return is None
        with pytest.raises(MarketContractError, match="precision_limited"):
            log_return(D("1.333333333333333333333333333333"))


def test_certified_log_near_one_preserves_zero_sign_and_rejects_unbounded_input():
    positive = D("1." + "0" * 99 + "1")
    negative = D("0." + "9" * 100)
    assert log_return(positive).as_tuple() == D("0e-18").as_tuple()
    assert log_return(negative).as_tuple() == D("-0e-18").as_tuple()
    with pytest.raises(MarketContractError, match="^precision_limited$"):
        log_return(D("1e-1000000000"))
    with pytest.raises(MarketContractError, match="^precision_limited$"):
        log_return(D("1e-1500"))  # A zero lower bound cannot certify ln.


def test_exact_rational_resource_limit_fails_closed():
    with patch("app.market_returns.MAX_RATIONAL_BITS", 128):
        point = last(publication(closes=("3", "4")))
        assert point.status == "unavailable" and point.reason == "precision_limited"


def test_compounding_resource_limit_cannot_return_rounded_approximate_growth():
    days = tuple(MON + timedelta(days=i) for i in range(16))
    actions = tuple(split("1e12", day=day, action_id=f"split-{i}") for i, day in enumerate(days[1:]))
    pub = publication(days=days, closes=("1",) * len(days), actions=actions)
    with patch("app.market_returns.MAX_RATIONAL_BITS", 512):
        assert calculate_returns(pub).valid_interval_count == 15
        with pytest.raises(MarketContractError, match="^precision_limited$"):
            reinvested_growth(pub)


def test_rounding_and_logs_ignore_global_default_traps_as_well_as_caller_context():
    pub = publication(closes=("3", "4"))
    expected = last(pub)
    original = DefaultContext.traps.copy()
    try:
        DefaultContext.traps[Inexact] = DefaultContext.traps[Rounded] = True
        with localcontext() as context:
            context.prec, context.rounding = 2, ROUND_DOWN
            context.traps[Inexact] = context.traps[Rounded] = True
            assert last(pub) == expected
            assert reinvested_growth(pub) == D("1.333333333333333333")
    finally:
        DefaultContext.traps = original


def successor(parent, **fields):
    return changed(parent, **dict(publication_id=f"{parent.publication_id}-next",
        market_data_version=parent.market_data_version + 1, supersedes=parent.publication_id,
        predecessor_market_data_version=parent.market_data_version,
        predecessor_manifest_sha256=parent.manifest.sha256,
        published_at=parent.published_at + timedelta(hours=1), **fields))


@pytest.mark.parametrize("mutation", ["price", "action", "calendar", "provenance"])
def test_successor_rejects_same_identity_resealed_predecessor(mutation):
    parent = publication()
    child = successor(parent)
    assert validate_publication(child, parent) is child
    if mutation == "price":
        substitute = changed(parent, prices=(parent.prices[0], replace(parent.prices[1], close=D(90))))
    elif mutation == "action":
        substitute = changed(parent, actions=(split(),))
    elif mutation == "calendar":
        sessions = (parent.calendar.sessions[0], replace(parent.calendar.sessions[1],
                    close_at=parent.calendar.sessions[1].close_at - timedelta(hours=1)))
        substitute = changed(parent, calendar=replace(parent.calendar, sessions=sessions))
    else:
        substitute = changed(parent, source=replace(parent.source, response_sha256="b" * 64))
    assert validate_publication(substitute) is substitute
    assert (parent.publication_id, parent.market_data_version, parent.published_at) == (
        substitute.publication_id, substitute.market_data_version, substitute.published_at)
    assert parent.manifest.sha256 != substitute.manifest.sha256
    with pytest.raises(MarketContractError, match="^predecessor_pin_mismatch$"):
        validate_publication(child, substitute)
    with pytest.raises(MarketContractError, match="predecessor_pin_mismatch"):
        align_returns((child,), pin(child), predecessors=(substitute,))
    observed = changed(child, knowledge_mode="observed_as_of")
    with pytest.raises(MarketContractError, match="predecessor_pin_mismatch"):
        validate_prediction_cutoff((observed,), pin(observed), observed.published_at, predecessors=(substitute,))


def test_predecessor_pin_is_manifest_content_not_a_self_referential_hash():
    parent = publication()
    child = successor(parent)
    assert child.predecessor_manifest_sha256 == parent.manifest.sha256
    assert seal_publication(child) == child
    assert changed(child, predecessor_manifest_sha256="c" * 64).manifest != child.manifest
    with pytest.raises(MarketContractError, match="incomplete_or_changed_manifest"):
        validate_publication(replace(child, predecessor_manifest_sha256="c" * 64), parent)
    with pytest.raises(MarketContractError, match="predecessor_pin_mismatch"):
        validate_publication(changed(child, predecessor_market_data_version=1), parent)
    grandchild = successor(child)
    assert validate_publication(grandchild, child) is grandchild
    assert align_returns((grandchild,), pin(grandchild), predecessors=(child,)).status == "available"
    reordered = changed(parent, prices=tuple(reversed(parent.prices)))
    assert reordered.manifest == parent.manifest
    assert validate_publication(child, reordered) is child


@pytest.mark.parametrize("fields,reason", [
    ({"predecessor_manifest_sha256": "c" * 64}, "unexpected_predecessor_pin"),
    ({"predecessor_market_data_version": 0}, "unexpected_predecessor_pin"),
    ({"supersedes": "old"}, "invalid_predecessor_pin"),
    ({"supersedes": "old", "predecessor_market_data_version": True,
      "predecessor_manifest_sha256": "c" * 64}, "invalid_predecessor_pin"),
    ({"supersedes": "old", "predecessor_market_data_version": 0,
      "predecessor_manifest_sha256": "invalid"}, "invalid_predecessor_pin"),
])
def test_initial_and_successor_predecessor_pin_shape(fields, reason):
    with pytest.raises(MarketContractError, match=f"^{reason}$"):
        validate_publication(changed(publication(), **fields))


@pytest.mark.parametrize("version", [0, 1, 7])
def test_duplicate_publication_ids_reject_different_security_version_or_digest_before_calculation(version):
    first = publication()
    second = changed(publication(security="security-b", closes=("100", "90")),
                     publication_id=first.publication_id, market_data_version=version)
    assert first.manifest.sha256 != second.manifest.sha256
    for pubs in ((first, second), (second, first)):
        with patch("app.market_returns.calculate_returns", side_effect=AssertionError("must reject before calculation")):
            with pytest.raises(MarketContractError, match="^duplicate_publication_id$"):
                align_returns(pubs, pin(*pubs))
        with pytest.raises(MarketContractError, match="^duplicate_publication_id$"):
            validate_prediction_cutoff(pubs, pin(*pubs), RETRIEVED)


def test_valid_unique_publication_alignment_is_order_independent():
    first, second = publication(), publication(security="security-b", closes=("100", "110"))
    dataset = pin(first, second)
    expected = align_returns((first, second), dataset)
    assert expected.status == "available"
    assert align_returns((second, first), dataset) == expected


def test_all_predecessor_lookup_consumers_enforce_unique_ids():
    parent = publication()
    child = successor(parent)
    substitute = changed(parent, prices=(parent.prices[0], replace(parent.prices[1], close=D(90))))
    for parents in ((parent, substitute), (substitute, parent)):
        with pytest.raises(MarketContractError, match="^ambiguous_predecessor$"):
            align_returns((child,), pin(child), predecessors=parents)
        with pytest.raises(MarketContractError, match="^ambiguous_predecessor$"):
            validate_prediction_cutoff((child,), pin(child), child.published_at, predecessors=parents)
    with pytest.raises(MarketContractError, match="^duplicate_publication_id$"):
        align_returns((parent,), pin(parent), predecessors=(substitute,))
