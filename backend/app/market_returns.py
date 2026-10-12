"""Pure Decimal returns from raw closes, explicit actions and supplied sessions.

Finite-Decimal economic inputs use exact bounded rational arithmetic. Final
return/growth outputs use integer HALF_EVEN rounding to 18 places. Logarithms
must have certified rounding bounds. Public gross factors remain 80-digit Decimal
approximations for display/inspection; compounding never consumes those factors.
No annualization, pricing provider, persistence, forecasting or allocation logic.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, InvalidOperation, Overflow,
    ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, localcontext,
)
from fractions import Fraction

from app.market_data_contracts import (
    DatasetPin, MarketContractError, MarketPublication, normalized_records, require,
    validate_dataset_pin, validate_predecessor_inventory, validate_publication,
)

SCALE = 10 ** 18
MAX_RATIONAL_BITS = 65536
LOG_PRECISIONS = (80, 160, 320)


def _context(precision=80, rounding=ROUND_HALF_EVEN):
    return Context(prec=precision, rounding=rounding, Emin=-999, Emax=999,
                   capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])


def _bounded(value):
    require(max(value.numerator.bit_length(), value.denominator.bit_length()) <= MAX_RATIONAL_BITS,
            "precision_limited")
    return value


def _round18(value):
    """Exact rational rounding: compare the remainder to half, then parity.

    Decimal construction from an integer/tuple is exact and ignores ambient
    precision. No approximate division or intermediate quantization is involved.
    """
    value = _bounded(value)
    units, remainder = divmod(abs(value.numerator) * SCALE, value.denominator)
    if 2 * remainder > value.denominator or (2 * remainder == value.denominator and units % 2):
        units += 1
    return Decimal((int(value < 0), Decimal(units).as_tuple().digits, -18))


def _working_decimal(value):
    with localcontext(_context()):
        return Decimal(value.numerator) / Decimal(value.denominator)


def _certified_log(value):
    """Enclose ln(exact rational); accept only one proven final rounding bin.

    Directed division encloses the argument. Decimal.ln is correctly HALF_EVEN
    rounded; adjacent representable numbers enclose its true result. Monotonicity
    gives outer ln bounds. Refinement is bounded and never guesses near a tie.
    """
    value = _bounded(value)
    require(value > 0, "nonpositive_log_factor")
    if value == 1:
        return Decimal("0e-18")
    for precision in LOG_PRECISIONS:
        numerator, denominator = Decimal(value.numerator), Decimal(value.denominator)
        lower = _context(precision, ROUND_FLOOR).divide(numerator, denominator)
        upper = _context(precision, ROUND_CEILING).divide(numerator, denominator)
        require(lower.is_finite() and upper.is_finite() and lower > 0, "precision_limited")
        context = _context(precision)
        lower_log = context.next_minus(context.ln(lower))
        upper_log = context.next_plus(context.ln(upper))
        rounded_lower, rounded_upper = _round18(Fraction(lower_log)), _round18(Fraction(upper_log))
        if rounded_lower == rounded_upper:
            # Both bounds may round to differently signed zero near ln(1).
            return Decimal((int(value < 1), (0,), -18)) if rounded_lower == 0 else rounded_lower
    raise MarketContractError("precision_limited")


def log_return(gross_factor):
    require(isinstance(gross_factor, Decimal) and gross_factor.is_finite()
            and gross_factor > 0, "nonpositive_log_factor")
    parts = gross_factor.as_tuple()
    require(len(parts.digits) + abs(parts.exponent) <= MAX_RATIONAL_BITS // 4, "precision_limited")
    try:
        return _certified_log(Fraction(gross_factor))
    except DecimalException:
        raise MarketContractError("arithmetic_out_of_range") from None


@dataclass(frozen=True)
class ReturnInterval:
    security_id: str
    listing_id: str
    start: datetime | None
    end: datetime
    status: str
    reason: str | None = None
    price_return: Decimal | None = None
    total_return: Decimal | None = None
    price_log_return: Decimal | None = None
    total_log_return: Decimal | None = None
    price_factor: Decimal | None = None
    total_factor: Decimal | None = None
    observation_ids: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReturnSeries:
    publication: MarketPublication
    intervals: tuple[ReturnInterval, ...]
    expected_interval_count: int
    valid_interval_count: int
    exclusions: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AlignedPanel:
    status: str
    reason: str | None
    pin: DatasetPin
    security_ids: tuple[str, ...]
    intervals: tuple[tuple[datetime, datetime], ...]
    price_returns: tuple[tuple[Decimal, ...], ...]
    total_returns: tuple[tuple[Decimal, ...], ...]
    expected_counts: tuple[tuple[str, int], ...]
    valid_counts: tuple[tuple[str, int], ...]
    aligned_interval_count: int
    exclusions: tuple[tuple[str, str, int], ...]


def _entitlements(actions):
    """One old share, applying ordered splits; cash retains its named share basis."""
    require(all(a.kind in {"split", "cash_dividend", "special_cash_distribution"} for a in actions),
            "unsupported_corporate_action")
    if len(actions) > 1:
        require(all(a.sequence is not None for a in actions)
                and len({a.sequence for a in actions}) == len(actions), "ambiguous_same_day_action_order")
    ordered = sorted(actions, key=lambda a: (a.sequence if a.sequence is not None else 0, a.action_id))
    shares, cash, share_bases = Fraction(1), Fraction(0), {}
    for action in ordered:
        if action.kind == "split":
            shares = _bounded(shares * Fraction(action.split_numerator) / Fraction(action.split_denominator))
            share_bases[action.action_id] = shares
            continue
        require(action.treatment == "gross_cash", "unsupported_cash_treatment")
        if action.entitlement_basis == "previous_session_share":
            require(action.basis_split_id is None, "ambiguous_cash_share_basis")
            entitlement = Fraction(action.cash_amount)
        elif action.entitlement_basis == "post_split_share":
            require(action.basis_split_id in share_bases, "unresolved_cash_share_basis")
            entitlement = _bounded(Fraction(action.cash_amount) * share_bases[action.basis_split_id])
        else:
            require(False, "ambiguous_cash_share_basis")
        cash = _bounded(cash + entitlement)
    return shares, cash


def _gross_factors(previous_price, current_price, actions):
    shares, cash = _entitlements(actions)
    current_value = _bounded(shares * Fraction(current_price.close))
    previous_value = Fraction(previous_price.close)
    return (_bounded(current_value / previous_value),
            _bounded(_bounded(current_value + cash) / previous_value))


def calculate_returns(publication, predecessor=None):
    """Invalid contracts raise; incomplete/unsupported economic intervals abstain."""
    validate_publication(publication, predecessor)
    prices, actions = normalized_records(publication)
    listing = publication.listing
    sessions = tuple(s for s in publication.calendar.sessions if listing.first_session <= s.session_date
                     <= (listing.last_session or date.max))
    by_date = {price.session_date: price for price in prices}
    by_action_date = {}
    for action in actions:
        by_action_date.setdefault(action.effective_date, []).append(action)
    coverage = {(item.start, item.end): item for item in publication.action_coverage}
    intervals = []
    if sessions:
        intervals.append(ReturnInterval(publication.security.security_id, listing.listing_id, None,
                                        sessions[0].close_at, "unavailable", "first_listing_observation"))
    for previous, current in zip(sessions, sessions[1:]):
        common = dict(security_id=publication.security.security_id, listing_id=listing.listing_id,
                      start=previous.close_at, end=current.close_at)
        reason = None
        if publication.state != "complete":
            reason = f"{publication.state}_publication"
        elif listing.continuity != "same_security_verified":
            reason = "unresolved_security_continuity"
        elif previous.session_date not in by_date:
            reason = "missing_previous_price"
        elif current.session_date not in by_date:
            reason = "missing_current_price"
        day_coverage = coverage.get((previous.session_date, current.session_date))
        if reason is None:
            if day_coverage is None:
                reason = "missing_action_coverage"
            elif day_coverage.state != "complete":
                reason = f"{day_coverage.state}_action_coverage"
            elif not (day_coverage.splits_complete and day_coverage.cash_complete
                      and day_coverage.other_actions_complete):
                reason = "incomplete_action_coverage"
        if reason:
            intervals.append(ReturnInterval(**common, status="unavailable", reason=reason))
            continue
        previous_price, current_price = by_date[previous.session_date], by_date[current.session_date]
        day_actions = tuple(by_action_date.get(current.session_date, ()))
        try:
            price_factor, total_factor = _gross_factors(previous_price, current_price, day_actions)
            require(_round18(price_factor) > 0 and _round18(total_factor) > 0, "precision_underflow")
            point = ReturnInterval(**common, status="available",
                price_return=_round18(price_factor - 1), total_return=_round18(total_factor - 1),
                price_log_return=_certified_log(price_factor), total_log_return=_certified_log(total_factor),
                price_factor=_working_decimal(price_factor), total_factor=_working_decimal(total_factor),
                observation_ids=tuple(sorted(set(previous_price.observation_ids + current_price.observation_ids))),
                action_ids=tuple(sorted(a.action_id for a in day_actions)))
        except MarketContractError as error:
            point = ReturnInterval(**common, status="unavailable", reason=str(error))
        except DecimalException:
            point = ReturnInterval(**common, status="unavailable", reason="arithmetic_out_of_range")
        intervals.append(point)
    economic = [point for point in intervals if point.start is not None]
    exclusions = Counter(point.reason for point in economic if point.status != "available")
    return ReturnSeries(publication, tuple(intervals), len(economic),
                        sum(point.status == "available" for point in economic), tuple(sorted(exclusions.items())))


def reinvested_growth(publication, predecessor=None):
    """Fractional-share ex-date reinvestment; cannot bridge unavailable intervals."""
    series = calculate_returns(publication, predecessor)
    points = tuple(point for point in series.intervals if point.start is not None)
    require(points and all(point.status == "available" for point in points), "incomplete_reinvestment_path")
    require(all(left.end == right.start for left, right in zip(points, points[1:])), "nonadjacent_reinvestment_path")
    prices, actions = normalized_records(publication)
    by_date = {price.session_date: price for price in prices}
    day_for_close = {s.close_at: s.session_date for s in publication.calendar.sessions}
    by_action_date = {}
    for action in actions:
        by_action_date.setdefault(action.effective_date, []).append(action)
    try:
        growth = Fraction(1)
        for point in points:
            start, end = day_for_close[point.start], day_for_close[point.end]
            _, total = _gross_factors(by_date[start], by_date[end], tuple(by_action_date.get(end, ())))
            growth = _bounded(growth * total)
        rounded = _round18(growth)
        require(rounded > 0, "precision_underflow")
        return rounded
    except DecimalException:
        raise MarketContractError("arithmetic_out_of_range") from None


def align_returns(publications, pin, predecessors=()):
    """Align already-calculated intervals, never inner-join prices then bridge gaps."""
    validate_dataset_pin(publications, pin)
    validate_predecessor_inventory(publications, predecessors)
    # Own calculation here: callers cannot substitute stale or fabricated series
    # underneath a newly pinned publication. Each security is calculated once.
    series = tuple(calculate_returns(p, next((parent for parent in predecessors
                   if parent.publication_id == p.supersedes), None)) for p in publications)
    ordered = sorted(series, key=lambda item: item.publication.security.security_id)
    ids = tuple(item.publication.security.security_id for item in ordered)
    expected = tuple((item.publication.security.security_id, item.expected_interval_count) for item in ordered)
    valid = tuple((item.publication.security.security_id, item.valid_interval_count) for item in ordered)
    exclusions = [(item.publication.security.security_id, reason, count) for item in ordered
                  for reason, count in item.exclusions]
    compatibility = {(item.publication.listing.currency, item.publication.calendar.calendar_id,
                      item.publication.calendar.version, item.publication.calendar.timezone,
                      item.publication.calendar.close_convention,
                      item.publication.source.provider, item.publication.source.product,
                      item.publication.normalizer_version, item.publication.calculation_version,
                      item.publication.precision_version) for item in ordered}
    if len(compatibility) != 1:
        exclusions.extend((item.publication.security.security_id, "incompatible_panel_contract",
                           item.valid_interval_count) for item in ordered if item.valid_interval_count)
        return AlignedPanel("unavailable", "incompatible_panel_contract", pin, ids, (), (), (),
                            expected, valid, 0, tuple(sorted(exclusions)))
    # Same named calendar/version cannot describe contradictory sessions or closes
    # in overlapping coverage. Different covered ranges remain compatible.
    for index, left in enumerate(publications):
        for right in publications[index + 1:]:
            start = max(left.calendar.covered_start, right.calendar.covered_start)
            end = min(left.calendar.covered_end, right.calendar.covered_end)
            left_schedule = tuple((s.session_date, s.close_at) for s in left.calendar.sessions
                                  if start <= s.session_date <= end)
            right_schedule = tuple((s.session_date, s.close_at) for s in right.calendar.sessions
                                   if start <= s.session_date <= end)
            if left_schedule != right_schedule:
                exclusions.extend((item.publication.security.security_id, "calendar_schedule_conflict",
                                   item.valid_interval_count) for item in ordered if item.valid_interval_count)
                return AlignedPanel("unavailable", "calendar_schedule_conflict", pin, ids, (), (), (),
                                    expected, valid, 0, tuple(sorted(exclusions)))
    maps = [{(point.start, point.end): point for point in item.intervals if point.status == "available"}
            for item in ordered]
    shared = set.intersection(*(set(mapping) for mapping in maps))
    intervals = tuple(sorted(shared))
    for item, mapping in zip(ordered, maps):
        count = len(mapping) - len(shared)
        if count:
            exclusions.append((item.publication.security.security_id, "unaligned_interval", count))
    return AlignedPanel("available" if intervals else "unavailable", None if intervals else "no_common_intervals",
                        pin, ids, intervals,
                        tuple(tuple(mapping[interval].price_return for mapping in maps) for interval in intervals),
                        tuple(tuple(mapping[interval].total_return for mapping in maps) for interval in intervals),
                        expected, valid, len(intervals), tuple(sorted(exclusions)))
