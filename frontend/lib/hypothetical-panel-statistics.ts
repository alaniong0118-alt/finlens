// Validate the separate synthetic receipt. Statistical calculations stay in Python.
import {check, object, stable, exact, equalsDecimal, requestHypothetical, type Exact, type RiskInputs} from "./hypothetical-risk";

type Measure = {exact: Exact | null; reason: string | null};
type Root = {radicand: Exact | null; display: string | null; reason: string | null};
type Asset = {asset_id: string; cumulative_return: Measure; maximum_drawdown: Measure;
  peak_boundary: number | null; trough_boundary: number | null; sample_mean_return: Measure;
  sample_variance: Measure; sample_volatility: Root};
export type StatisticsReceipt = {schema_id: string; inputs: RiskInputs; result: {
  method_id: string; precision_id: string; data_authority: string; observation_basis: string;
  return_unit: string; covariance_unit: string; sample_count: number; sample_denominator: number | null;
  interval_days: number[]; equal_interval_lengths: boolean | null;
  panel: {panel_id: string; factor_method_id: string; sessions: {session_id: string; start: string; end: string;
    factors: {asset_id: string; gross_factor: Exact}[]}[]};
  asset_ids: string[]; assets: Asset[]; covariance: Measure[][]; covariance_complete: boolean; notices: string[];
}};
const notices = ["hypothetical_user_entered_factors_only", "equal_weight_supplied_intervals_not_annualized",
  "initial_unit_asset_index_included", "signed_exposures_not_used_for_asset_statistics",
  "no_portfolio_wealth_rebalancing_or_financing", "calendar_and_statistical_adequacy_not_verified",
  "rounded_sqrt_display_exact_radicand_retained", "v1_risk_receipt_unchanged"];
function integer(value: unknown, low: number, high: number): asserts value is number {
  check(Number.isSafeInteger(value) && (value as number) >= low && (value as number) <= high);
}
function measure(value: unknown, count: number, minimum: number): asserts value is Measure {
  object(value, ["exact", "reason"]);
  if (count < minimum) check(value.exact === null && value.reason === "insufficient_observations");
  else if (value.exact === null) check(value.reason === "arithmetic_resource_limit");
  else {exact(value.exact); check(value.reason === null);}
}
function same(left: Measure, right: Measure) {
  if (left.exact === null || right.exact === null) return left.exact === right.exact && left.reason === right.reason;
  return BigInt(left.exact.numerator) * BigInt(right.exact.denominator) === BigInt(right.exact.numerator) * BigInt(left.exact.denominator);
}
function root(value: unknown, variance: Measure): asserts value is Root {
  object(value, ["radicand", "display", "reason"]);
  check(value.reason === variance.reason);
  if (variance.exact === null) {check(value.radicand === null && value.display === null); return;}
  exact(value.radicand); check(same({exact: value.radicand, reason: null}, variance));
  check(typeof value.display === "string" && /^(0|[1-9][0-9]*)\.[0-9]{18}$/.test(value.display) && value.display.length <= 2520);
  // Check the exact squared midpoint boundaries for the server's HALF_EVEN root
  // display; do not compute observations, moments or a floating approximation.
  const units = BigInt((value.display as string).replace(".", "")), even = units % BigInt(2) === BigInt(0);
  const n = BigInt(value.radicand.numerator), d = BigInt(value.radicand.denominator);
  const scaled4 = BigInt(4) * n * BigInt(10) ** BigInt(36);
  const upper = d * (BigInt(2) * units + BigInt(1)) ** BigInt(2);
  check(n >= BigInt(0) && (scaled4 < upper || (scaled4 === upper && even)));
  if (units > BigInt(0)) {
    const lower = d * (BigInt(2) * units - BigInt(1)) ** BigInt(2);
    check(scaled4 > lower || (scaled4 === lower && even));
  }
}
export function validateStatistics(value: unknown, inputs: RiskInputs): StatisticsReceipt {
  object(value, ["schema_id", "inputs", "result"]);
  check(value.schema_id === "hypothetical-panel-statistics-v1" && stable(value.inputs) === stable(inputs));
  const r = value.result;
  object(r, ["method_id", "precision_id", "data_authority", "observation_basis", "return_unit", "covariance_unit",
    "sample_count", "sample_denominator", "interval_days", "equal_interval_lengths", "panel", "asset_ids", "assets", "covariance", "covariance_complete", "notices"]);
  check(r.method_id === "supplied-factor-panel-statistics-v1" && r.precision_id === "exact-rational-symbolic-root-display18-half-even-v1");
  check(r.data_authority === "unverified_synthetic_inputs" && r.observation_basis === "equal_weight_supplied_intervals");
  check(r.return_unit === "return_ratio" && r.covariance_unit === "return_ratio_squared" && stable(r.notices) === stable(notices));
  const count = inputs.sessions.length, assets = inputs.exposures.map(e => e.asset_id).sort();
  integer(count, 0, 120); integer(assets.length, 1, 8);
  check(r.sample_count === count && r.sample_denominator === (count >= 2 ? count - 1 : null));
  check(stable(r.asset_ids) === stable(assets));
  check(Array.isArray(r.interval_days) && r.interval_days.length === count);
  r.interval_days.forEach((days: unknown, i: number) => {
    integer(days, 1, 3652058);
    check(days === (Date.parse(inputs.sessions[i].end) - Date.parse(inputs.sessions[i].start)) / 86400000);
  });
  check(r.equal_interval_lengths === (count === 0 ? null : new Set(r.interval_days).size === 1));
  object(r.panel, ["panel_id", "factor_method_id", "sessions"]);
  check(r.panel.panel_id === "user-hypothetical" && r.panel.factor_method_id === "user-entered-exact-gross-factors-v1");
  check(Array.isArray(r.panel.sessions) && r.panel.sessions.length === count);
  r.panel.sessions.forEach((session: unknown, i: number) => {
    object(session, ["session_id", "start", "end", "factors"]); const input = inputs.sessions[i];
    check(session.session_id === input.session_id && session.start === input.start && session.end === input.end);
    check(Array.isArray(session.factors) && session.factors.length === assets.length);
    session.factors.forEach((factor: unknown, j: number) => {
      object(factor, ["asset_id", "gross_factor"]); exact(factor.gross_factor);
      check(factor.asset_id === assets[j] && BigInt(factor.gross_factor.numerator) > BigInt(0));
      check(equalsDecimal(factor.gross_factor, input.factors[assets[j]]));
    });
  });
  check(Array.isArray(r.assets) && r.assets.length === assets.length);
  r.assets.forEach((asset: unknown, i: number) => {
    object(asset, ["asset_id", "cumulative_return", "maximum_drawdown", "peak_boundary", "trough_boundary", "sample_mean_return", "sample_variance", "sample_volatility"]);
    check(asset.asset_id === assets[i]);
    for (const name of ["cumulative_return", "maximum_drawdown", "sample_mean_return"]) measure(asset[name], count, 1);
    measure(asset.sample_variance, count, 2);
    const a = asset as unknown as Asset;
    if (a.cumulative_return.exact) check(BigInt(a.cumulative_return.exact.numerator) > -BigInt(a.cumulative_return.exact.denominator));
    if (a.maximum_drawdown.exact) {
      const n = BigInt(a.maximum_drawdown.exact.numerator), d = BigInt(a.maximum_drawdown.exact.denominator);
      check(n >= BigInt(0) && n < d);
      integer(a.peak_boundary, 0, count); integer(a.trough_boundary, a.peak_boundary, count);
      check(n === BigInt(0) ? a.peak_boundary === 0 && a.trough_boundary === 0 : a.peak_boundary < a.trough_boundary);
    } else check(a.peak_boundary === null && a.trough_boundary === null);
    if (a.sample_variance.exact) check(BigInt(a.sample_variance.exact.numerator) >= BigInt(0));
    if (count >= 2 && a.sample_mean_return.exact === null) check(a.sample_variance.exact === null && a.sample_variance.reason === a.sample_mean_return.reason);
    root(a.sample_volatility, a.sample_variance);
  });
  check(Array.isArray(r.covariance) && r.covariance.length === assets.length);
  const matrix = r.covariance as unknown[][];
  matrix.forEach(row => {check(Array.isArray(row) && row.length === assets.length); row.forEach(cell => measure(cell, count, 2));});
  const checked = matrix as Measure[][], checkedAssets = r.assets as Asset[];
  checked.forEach((row, i) => row.forEach((cell, j) => {
    check(same(cell, checked[j][i]));
    if (i === j) check(same(cell, checkedAssets[i].sample_variance));
    if (count >= 2 && (checkedAssets[i].sample_mean_return.exact === null || checkedAssets[j].sample_mean_return.exact === null)) check(cell.exact === null && cell.reason === "arithmetic_resource_limit");
  }));
  check(r.covariance_complete === checked.every(row => row.every(cell => cell.exact !== null)));
  return value as unknown as StatisticsReceipt;
}
export function requestStatistics(inputs: RiskInputs, signal: AbortSignal): Promise<StatisticsReceipt> {
  return requestHypothetical("hypothetical-panel-statistics", inputs, signal, validateStatistics);
}
