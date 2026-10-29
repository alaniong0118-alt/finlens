"""Synthetic exact-factor historical loss kernel; no data authority or I/O.

Each factor is the exact mathematical gross total-return operand for one
declared interval, NOT a rounded return or market_returns.ReturnInterval factor.
No prices, corporate actions, dividends or FX are calculated here. A future
reviewed adapter must preserve the existing return engine's exact operands and
prove calendar/window/action completeness, currency/FX, identity, vintage,
custody and operation-specific rights. Labels supplied here prove none of those.

All intermediate arithmetic is rational. Display alone rounds to 18 decimal
places, HALF_EVEN, independently of the ambient Decimal context. Positive losses
mean loss; negative VaR/ES remain negative. No fees or financing are included.
"""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from fractions import Fraction
import re

METHOD_ID = "historical-loss-es-v1"
PRECISION_ID = "exact-rational-display18-half-even-v1"
MAX_ASSETS = 35
MAX_SESSIONS = 6000
MAX_HORIZON = 252
MAX_FACTOR_CELLS = 60000
MAX_FACTOR_OPERATIONS = 1000000
MAX_INPUT_BITS = 2048
MAX_RATIONAL_BITS = 8192
MAX_DECIMAL_DIGITS = 128
MAX_DECIMAL_EXPONENT = 256
MAX_TOTAL_INPUT_BITS = 4000000
MAX_TOTAL_OUTPUT_BITS = 8000000
SCALE = 10 ** 18


class PortfolioRiskError(ValueError):
    """Stable invalid-input/resource reason; no partial result is returned."""


def _require(condition, reason):
    if not condition:
        raise PortfolioRiskError(reason)


def _identifier(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is not None


def _bits(value):
    return abs(value.numerator).bit_length() + value.denominator.bit_length()


def _bounded(value):
    _require(max(abs(value.numerator).bit_length(), value.denominator.bit_length())
             <= MAX_RATIONAL_BITS, "arithmetic_resource_limit")
    return value


def _exact(value):
    # Check before Fraction(Decimal): an extreme exponent must never allocate
    # a huge power of ten. Reject coercions and numeric subclasses as well.
    _require(type(value) in (Decimal, Fraction), "exact_number_required")
    if type(value) is Decimal:
        _require(value.is_finite(), "nonfinite_input")
        parts = value.as_tuple()
        _require(len(parts.digits) <= MAX_DECIMAL_DIGITS
                 and abs(parts.exponent) <= MAX_DECIMAL_EXPONENT, "input_resource_limit")
        value = Fraction(value)
    _require(max(abs(value.numerator).bit_length(), value.denominator.bit_length())
             <= MAX_INPUT_BITS, "input_resource_limit")
    return _bounded(value)


def display18(value):
    """Round an exact result using integer remainder/parity, never division."""
    _require(type(value) is Fraction, "exact_result_required")
    value = _bounded(value)
    units, remainder = divmod(abs(value.numerator) * SCALE, value.denominator)
    if 2 * remainder > value.denominator or (2 * remainder == value.denominator and units % 2):
        units += 1
    return Decimal((int(value < 0), Decimal(units).as_tuple().digits, -18))


@dataclass(frozen=True)
class AssetExposure:
    asset_id: str
    currency: str
    amount: Decimal | Fraction  # Signed initial reporting-currency notional.


@dataclass(frozen=True)
class AssetFactor:
    asset_id: str
    gross_factor: Decimal | Fraction  # Strictly positive exact synthetic operand.


@dataclass(frozen=True)
class FactorSession:
    session_id: str
    start: date
    end: date
    factors: tuple[AssetFactor, ...]


@dataclass(frozen=True)
class ExactFactorPanel:
    """Synthetic-only boundary; names/method labels are unverified audit labels.

    Sessions are chronological intervals with left.end == right.start. Each
    must contain exactly the exposed assets, with no missing/unknown cells.
    Date continuity cannot attest exchange-calendar completeness or real actions.
    """
    panel_id: str
    factor_method_id: str
    sessions: tuple[FactorSession, ...]


@dataclass(frozen=True)
class RiskValue:
    exact: Fraction | None
    reason: str | None = None

    @property
    def display(self):
        return None if self.exact is None else display18(self.exact)


@dataclass(frozen=True)
class LossScenario:
    scenario_id: tuple[str, str, str]  # panel, first interval ID, last interval ID
    start_index: int  # Inclusive supplied interval index.
    stop_index: int  # Exclusive supplied interval index.
    loss: Fraction
    tail_mass: Fraction | None  # Observation mass, NOT normalized probability.


@dataclass(frozen=True)
class HistoricalRisk:
    method_id: str
    precision_id: str
    data_authority: str
    reporting_currency: str
    exposure_date: date
    exposures: tuple[AssetExposure, ...]  # Canonical asset order; exact Fractions.
    panel: ExactFactorPanel  # Full normalized exact inputs retained for replay.
    portfolio_value: Fraction | None
    net_exposure: Fraction
    gross_exposure: Fraction
    horizon: int
    confidence: Fraction
    scenario_count: int
    overlapping: bool
    rank: int | None
    tail_mass: Fraction
    strict_tail_count: int
    threshold_tie_count: int
    var: RiskValue
    es: RiskValue
    var_percent: RiskValue  # Percentage points, not a 0..1 ratio.
    es_percent: RiskValue
    scenarios: tuple[LossScenario, ...]  # Ascending loss, then scenario ID.
    notices: tuple[str, ...]


def _validate(exposures, currency, exposure_date, panel, horizon, confidence, portfolio_value):
    _require(type(currency) is str and re.fullmatch(r"[A-Z]{3}", currency) is not None,
             "invalid_reporting_currency")
    _require(type(exposure_date) is date, "invalid_exposure_date")
    _require(type(horizon) is int and 1 <= horizon <= MAX_HORIZON, "unsupported_horizon")
    alpha = _exact(confidence)
    _require(0 < alpha < 1, "invalid_confidence")
    value = None if portfolio_value is None else _exact(portfolio_value)
    _require(type(exposures) is tuple and 0 < len(exposures) <= MAX_ASSETS, "invalid_exposures")
    budget = _bits(alpha) + (0 if value is None else _bits(value))
    normalized = []
    for exposure in exposures:
        _require(type(exposure) is AssetExposure and _identifier(exposure.asset_id), "invalid_exposure")
        _require(exposure.currency == currency and type(exposure.currency) is str, "exposure_currency_mismatch")
        amount = _exact(exposure.amount)
        budget += _bits(amount)
        normalized.append(replace(exposure, amount=amount))
    assets = {e.asset_id for e in normalized}
    _require(len(assets) == len(normalized), "duplicate_exposure")
    _require(type(panel) is ExactFactorPanel and _identifier(panel.panel_id)
             and _identifier(panel.factor_method_id), "invalid_exact_factor_panel")
    _require(type(panel.sessions) is tuple and len(panel.sessions) <= MAX_SESSIONS, "session_resource_limit")
    _require(len(panel.sessions) * len(assets) <= MAX_FACTOR_CELLS, "factor_cell_resource_limit")
    count = max(0, len(panel.sessions) - horizon + 1)
    _require(count * horizon * len(assets) <= MAX_FACTOR_OPERATIONS, "operation_resource_limit")
    sessions, seen = [], set()
    for session in panel.sessions:
        _require(type(session) is FactorSession and _identifier(session.session_id), "invalid_session")
        _require(session.session_id not in seen, "duplicate_session")
        seen.add(session.session_id)
        _require(type(session.start) is date and type(session.end) is date
                 and session.start < session.end, "invalid_session_boundaries")
        _require(not sessions or sessions[-1].end == session.start, "nonconsecutive_sessions")
        _require(type(session.factors) is tuple and len(session.factors) == len(assets), "incomplete_factor_panel")
        factors, found = [], set()
        for factor in session.factors:
            _require(type(factor) is AssetFactor and _identifier(factor.asset_id), "invalid_asset_factor")
            _require(factor.asset_id in assets and factor.asset_id not in found, "inconsistent_factor_assets")
            found.add(factor.asset_id)
            exact = _exact(factor.gross_factor)
            _require(exact > 0, "nonpositive_gross_factor")
            budget += _bits(exact)
            _require(budget <= MAX_TOTAL_INPUT_BITS, "aggregate_input_resource_limit")
            factors.append(replace(factor, gross_factor=exact))
        sessions.append(replace(session, factors=tuple(sorted(factors, key=lambda f: f.asset_id))))
    _require(budget <= MAX_TOTAL_INPUT_BITS, "aggregate_input_resource_limit")
    return (tuple(sorted(normalized, key=lambda e: e.asset_id)),
            replace(panel, sessions=tuple(sessions)), alpha, value)


def _scenario_loss(exposures, sessions):
    pnl = Fraction(0)
    for index, exposure in enumerate(exposures):
        growth = Fraction(1)
        for session in sessions:
            growth = _bounded(growth * session.factors[index].gross_factor)
        pnl = _bounded(pnl + _bounded(exposure.amount * _bounded(growth - 1)))
    return -pnl


def _tail_statistics(losses, alpha):
    """Input is already sorted, with N >= 2. Return exact audit statistics."""
    count = len(losses)
    mass = _bounded(count * (1 - alpha))
    rank_numerator = alpha.numerator * count
    rank = (rank_numerator + alpha.denominator - 1) // alpha.denominator
    threshold = losses[rank - 1]
    strict = tuple(loss for loss in losses if loss > threshold)
    ties = losses.count(threshold)
    if mass < 1:
        return rank, threshold, mass, len(strict), ties, None, (None,) * count
    boundary_mass = _bounded((mass - len(strict)) / ties)
    weights = tuple(Fraction(1) if loss > threshold else boundary_mass if loss == threshold
                    else Fraction(0) for loss in losses)
    total = Fraction(0)
    for loss, weight in zip(losses, weights):
        total = _bounded(total + _bounded(loss * weight))
    es = _bounded(total / mass)
    return rank, threshold, mass, len(strict), ties, es, weights


def _percent(measure, value):
    if value is None:
        return RiskValue(None, "portfolio_value_not_declared")
    if value <= 0:
        return RiskValue(None, "nonpositive_portfolio_value")
    if measure.exact is None:
        return RiskValue(None, measure.reason)
    return RiskValue(_bounded(_bounded(100 * measure.exact) / value))


def calculate_historical_risk(*, exposures, reporting_currency, exposure_date, panel,
                              horizon, confidence, portfolio_value=None):
    """Validate the entire panel before calculating; never drop or bridge a gap.

    Invalid/missing cells raise PortfolioRiskError. Empty/singleton complete
    scenario inventories return insufficient_scenarios. Horizon > supplied
    intervals is a valid insufficient sample if within 1..MAX_HORIZON.
    A nonpositive declared value disables percentages only, not currency risk.
    """
    exposures, panel, alpha, value = _validate(exposures, reporting_currency, exposure_date,
                                              panel, horizon, confidence, portfolio_value)
    net = gross = Fraction(0)
    for exposure in exposures:
        net = _bounded(net + exposure.amount)
        gross = _bounded(gross + abs(exposure.amount))
    scenarios, output_bits = [], 0
    for start in range(max(0, len(panel.sessions) - horizon + 1)):
        window = panel.sessions[start:start + horizon]
        loss = _scenario_loss(exposures, window)
        output_bits += _bits(loss)
        _require(output_bits <= MAX_TOTAL_OUTPUT_BITS, "aggregate_output_resource_limit")
        scenarios.append(LossScenario((panel.panel_id, window[0].session_id, window[-1].session_id),
                                      start, start + horizon, loss, None))
    scenarios.sort(key=lambda s: (s.loss, s.scenario_id))
    count = len(scenarios)
    rank, strict, ties = None, 0, 0
    mass = _bounded(count * (1 - alpha))
    var = es = RiskValue(None, "insufficient_scenarios")
    if count >= 2:
        rank, threshold, mass, strict, ties, expected, weights = _tail_statistics(
            tuple(s.loss for s in scenarios), alpha)
        var = RiskValue(threshold)
        es = RiskValue(expected, None if expected is not None else "insufficient_tail_mass")
        scenarios = [replace(s, tail_mass=w) for s, w in zip(scenarios, weights)]
    var_percent, es_percent = _percent(var, value), _percent(es, value)
    scalars = [net, gross, alpha, mass, *(m.exact for m in (var, es, var_percent, es_percent)
                                        if m.exact is not None)]
    output_bits += sum(_bits(v) for v in scalars)
    output_bits += sum(_bits(s.tail_mass) for s in scenarios if s.tail_mass is not None)
    _require(output_bits <= MAX_TOTAL_OUTPUT_BITS, "aggregate_output_resource_limit")
    return HistoricalRisk(
        METHOD_ID, PRECISION_ID, "unverified_synthetic_inputs", reporting_currency, exposure_date,
        exposures, panel, value, net, gross, horizon, alpha, count, horizon > 1 and count > 1,
        rank, mass, strict, ties, var, es, var_percent, es_percent, tuple(scenarios),
        ("empirical_sample_not_statistical_adequacy", "supplied_calendar_not_verified",
         "synthetic_inputs_not_source_authority", "no_fees_or_financing"))
