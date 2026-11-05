"""Exact statistics of supplied synthetic asset factors; no portfolio path or I/O.

All intervals have equal observation weight, even when their date lengths differ.
Volatility is the nonnegative square root of an exact sample variance; its
radicand remains exact, while the displayed root alone rounds to 18 places.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from math import isqrt

from app.portfolio_risk import (
    ExactFactorPanel, PortfolioRiskError, RiskValue, SCALE,
    MAX_FACTOR_OPERATIONS, MAX_TOTAL_OUTPUT_BITS,
    _validate, _bounded, _bits, _require,
)

METHOD_ID = 'supplied-factor-panel-statistics-v1'
PRECISION_ID = 'exact-rational-symbolic-root-display18-half-even-v1'


def sqrt_display18(value):
    """Round sqrt(a/b) by exact integer midpoint comparison, never floating point."""
    _require(type(value) is Fraction and value >= 0, 'nonnegative_exact_variance_required')
    value = _bounded(value)
    scaled = value.numerator * SCALE * SCALE
    units = isqrt(scaled // value.denominator)
    midpoint = 4 * scaled - value.denominator * (2 * units + 1) ** 2
    if midpoint > 0 or (midpoint == 0 and units % 2):
        units += 1
    return Decimal((0, Decimal(units).as_tuple().digits, -18))


@dataclass(frozen=True)
class RootValue:
    # The exact value is sqrt(radicand), not an asserted rational approximation.
    radicand: Fraction | None
    display: str | None
    reason: str | None = None


@dataclass(frozen=True)
class AssetStatistics:
    asset_id: str
    cumulative_return: RiskValue
    maximum_drawdown: RiskValue
    peak_boundary: int | None
    trough_boundary: int | None
    sample_mean_return: RiskValue
    sample_variance: RiskValue
    sample_volatility: RootValue


@dataclass(frozen=True)
class PanelStatistics:
    method_id: str
    precision_id: str
    data_authority: str
    observation_basis: str
    return_unit: str
    covariance_unit: str
    sample_count: int
    sample_denominator: int | None
    interval_days: tuple[int, ...]
    equal_interval_lengths: bool | None
    panel: ExactFactorPanel
    asset_ids: tuple[str, ...]
    assets: tuple[AssetStatistics, ...]
    covariance: tuple[tuple[RiskValue, ...], ...]
    covariance_complete: bool
    notices: tuple[str, ...]


def _measure(function):
    try:
        return RiskValue(function())
    except PortfolioRiskError as error:
        if str(error) != 'arithmetic_resource_limit':
            raise
        return RiskValue(None, 'arithmetic_resource_limit')


def _sum(values):
    total = Fraction(0)
    for value in values:
        total = _bounded(total + value)
    return total


def _cumulative(factors):
    product = Fraction(1)
    for factor in factors:
        product = _bounded(product * factor)
    return _bounded(product - 1)


def _drawdown(factors):
    # current / running peak starts at 1 before the first supplied interval.
    relative, worst = Fraction(1), Fraction(0)
    peak = worst_peak = worst_trough = 0
    try:
        for boundary, factor in enumerate(factors, 1):
            relative = _bounded(relative * factor)
            if relative > 1:
                relative, peak = Fraction(1), boundary
            decline = _bounded(1 - relative)
            if decline > worst:
                worst, worst_peak, worst_trough = decline, peak, boundary
        return RiskValue(worst), worst_peak, worst_trough
    except PortfolioRiskError as error:
        if str(error) != 'arithmetic_resource_limit':
            raise
        return RiskValue(None, 'arithmetic_resource_limit'), None, None


def _covariance(left, right, left_mean, right_mean):
    return _bounded(_sum(_bounded(_bounded(x - left_mean) * _bounded(y - right_mean))
                         for x, y in zip(left, right)) / (len(left) - 1))


def calculate_panel_statistics(*, exposures, reporting_currency, exposure_date, panel,
                               horizon, confidence, portfolio_value=None):
    """Reuse the exact Risk Lab boundary; derive only asset-factor observations.

    Risk-form fields remain validated but do not weight/annualize these measures.
    A complete common panel is required; observations are never silently dropped.
    """
    exposures, panel, _, _ = _validate(exposures, reporting_currency, exposure_date,
                                      panel, horizon, confidence, portfolio_value)
    count, size = len(panel.sessions), len(exposures)
    _require(count * size * size <= MAX_FACTOR_OPERATIONS, 'statistics_operation_resource_limit')
    asset_ids = tuple(item.asset_id for item in exposures)
    factors = tuple(tuple(session.factors[j].gross_factor for session in panel.sessions) for j in range(size))
    returns = tuple(tuple(_bounded(value - 1) for value in column) for column in factors)
    assets = []
    for identifier, column, observations in zip(asset_ids, factors, returns):
        if count == 0:
            cumulative = drawdown = mean = RiskValue(None, 'insufficient_observations')
            peak = trough = None
        else:
            cumulative = _measure(lambda: _cumulative(column))
            drawdown, peak, trough = _drawdown(column)
            mean = _measure(lambda: _bounded(_sum(observations) / count))
        variance = RiskValue(None, 'insufficient_observations')
        if count >= 2:
            variance = (RiskValue(None, mean.reason) if mean.exact is None else
                        _measure(lambda: _covariance(observations, observations, mean.exact, mean.exact)))
        if variance.exact is not None:
            _require(variance.exact >= 0, 'variance_invariant_failed')
        volatility = RootValue(variance.exact,
            None if variance.exact is None else format(sqrt_display18(variance.exact), 'f'), variance.reason)
        assets.append(AssetStatistics(identifier, cumulative, drawdown, peak, trough, mean, variance, volatility))
    covariance = [[RiskValue(None, 'insufficient_observations') for _ in assets] for _ in assets]
    for i, left in enumerate(assets):
        covariance[i][i] = left.sample_variance
        for j in range(i + 1, size):
            right = assets[j]
            value = RiskValue(None, 'insufficient_observations')
            if count >= 2:
                reason = left.sample_mean_return.reason or right.sample_mean_return.reason
                value = (RiskValue(None, reason) if reason else _measure(lambda: _covariance(
                    returns[i], returns[j], left.sample_mean_return.exact, right.sample_mean_return.exact)))
            covariance[i][j] = covariance[j][i] = value
    # Bound the actual repeated exact scalar inventory, including the audit panel.
    output_bits = sum(_bits(f.gross_factor) for session in panel.sessions for f in session.factors)
    for asset in assets:
        output_bits += sum(_bits(m.exact) for m in (asset.cumulative_return, asset.maximum_drawdown,
            asset.sample_mean_return, asset.sample_variance) if m.exact is not None)
        if asset.sample_volatility.radicand is not None:
            output_bits += _bits(asset.sample_volatility.radicand)
    output_bits += sum(_bits(value.exact) for row in covariance for value in row if value.exact is not None)
    _require(output_bits <= MAX_TOTAL_OUTPUT_BITS, 'aggregate_output_resource_limit')
    days = tuple((session.end - session.start).days for session in panel.sessions)
    return PanelStatistics(METHOD_ID, PRECISION_ID, 'unverified_synthetic_inputs',
        'equal_weight_supplied_intervals', 'return_ratio', 'return_ratio_squared', count,
        count - 1 if count >= 2 else None, days, None if not days else len(set(days)) == 1,
        panel, asset_ids, tuple(assets), tuple(tuple(row) for row in covariance),
        all(value.exact is not None for row in covariance for value in row),
        ('hypothetical_user_entered_factors_only', 'equal_weight_supplied_intervals_not_annualized',
         'initial_unit_asset_index_included', 'signed_exposures_not_used_for_asset_statistics',
         'no_portfolio_wealth_rebalancing_or_financing', 'calendar_and_statistical_adequacy_not_verified',
         'rounded_sqrt_display_exact_radicand_retained', 'v1_risk_receipt_unchanged'))
