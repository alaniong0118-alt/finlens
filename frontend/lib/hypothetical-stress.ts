import {check, object, stable, exact, equalsDecimal, requestHypothetical, type Exact} from "./hypothetical-risk";

export const EXPOSURE_TYPE = "linear_price_notional" as const;
export type StressInputs = {reporting_currency: string; exposure_date: string;
  exposures: {asset_id: string; amount: string; currency: string; exposure_type: typeof EXPOSURE_TYPE}[];
  scenarios: {scenario_id: string; shocks: Record<string, string>}[]; common_shocks: string[]};
type Contribution = {asset_id: string; exposure: Exact; shock_percent: Exact; pnl: Exact; loss: Exact};
export type StressOutcome = {contributions: Contribution[]; total_pnl: Exact; total_loss: Exact};
export type StressReceipt = {schema_id: string; inputs: StressInputs; result: {
  method_id: string; precision_id: string; data_authority: string; reporting_currency: string; exposure_date: string;
  exposure_type: typeof EXPOSURE_TYPE; exposures: {asset_id: string; amount: Exact; currency: string; exposure_type: typeof EXPOSURE_TYPE}[];
  net_exposure: Exact; gross_exposure: Exact; common_shock_pnl_per_percentage_point: Exact;
  scenarios: (StressOutcome & {scenario_id: string})[];
  common_shock_sensitivity: (StressOutcome & {shock_percent: Exact})[]; notices: string[];
}};
function stressExact(value: unknown): asserts value is Exact {
  exact(value); check(value.numerator.replace("-", "").length <= 64 && value.denominator.length <= 64);
}
const n = (x: Exact) => BigInt(x.numerator), d = (x: Exact) => BigInt(x.denominator);
function same(a: Exact, b: Exact) {return n(a) * d(b) === n(b) * d(a);}
function total(values: Exact[], absolute = false) {
  let numerator = BigInt(0), denominator = BigInt(1);
  for (const v of values) {const value = absolute && n(v) < BigInt(0) ? -n(v) : n(v); numerator = numerator * d(v) + value * denominator; denominator *= d(v);}
  return {numerator: numerator.toString(), denominator: denominator.toString(), display: ""};
}
function decimalRatio(input: string) {
  const [whole, part = ""] = input.split(".");
  return {numerator: BigInt(whole + part).toString(), denominator: (BigInt(10) ** BigInt(part.length)).toString(), display: ""};
}
export function validateStressReceipt(value: unknown, inputs: StressInputs): StressReceipt {
  object(value, ["schema_id", "inputs", "result"]);
  check(value.schema_id === "hypothetical-linear-stress-v1" && stable(value.inputs) === stable(inputs));
  check(inputs.exposures.length >= 1 && inputs.exposures.length <= 8 && inputs.scenarios.length >= 1 && inputs.scenarios.length <= 12 && inputs.common_shocks.length >= 1 && inputs.common_shocks.length <= 21);
  const r = value.result;
  object(r, ["method_id", "precision_id", "data_authority", "reporting_currency", "exposure_date", "exposure_type", "exposures", "net_exposure", "gross_exposure", "common_shock_pnl_per_percentage_point", "scenarios", "common_shock_sensitivity", "notices"]);
  check(r.method_id === "hypothetical-linear-price-stress-v1" && r.precision_id === "exact-rational-display18-half-even-v1" && r.data_authority === "unverified_user_assumptions");
  check(r.reporting_currency === inputs.reporting_currency && r.exposure_date === inputs.exposure_date && r.exposure_type === EXPOSURE_TYPE);
  const assets = [...inputs.exposures].sort((a,b) => a.asset_id < b.asset_id ? -1 : a.asset_id > b.asset_id ? 1 : 0);
  check(Array.isArray(r.exposures) && r.exposures.length === assets.length);
  const amounts: Exact[] = [];
  r.exposures.forEach((e: unknown, i: number) => {
    object(e, ["asset_id", "amount", "currency", "exposure_type"]); stressExact(e.amount);
    check(e.asset_id === assets[i].asset_id && e.currency === assets[i].currency && assets[i].currency === inputs.reporting_currency && e.exposure_type === assets[i].exposure_type && e.exposure_type === EXPOSURE_TYPE && equalsDecimal(e.amount, assets[i].amount)); amounts.push(e.amount);
  });
  stressExact(r.net_exposure); stressExact(r.gross_exposure); stressExact(r.common_shock_pnl_per_percentage_point);
  check(same(r.net_exposure, total(amounts)) && same(r.gross_exposure, total(amounts, true)));
  check(n(r.common_shock_pnl_per_percentage_point) * d(r.net_exposure) * BigInt(100) === n(r.net_exposure) * d(r.common_shock_pnl_per_percentage_point));
  // Receipt integrity only. Render actual backend values; never create client estimates.
  const outcome = (v: unknown, shocks: Record<string, string>, kind: "scenario_id" | "shock_percent") => {
    object(v, [kind, "contributions", "total_pnl", "total_loss"]);
    stressExact(v.total_pnl); stressExact(v.total_loss);
    check(n(v.total_loss) * d(v.total_pnl) === -n(v.total_pnl) * d(v.total_loss));
    check(Array.isArray(v.contributions) && v.contributions.length === assets.length);
    const values: Exact[] = [];
    v.contributions.forEach((c: unknown, i: number) => {
      object(c, ["asset_id", "exposure", "shock_percent", "pnl", "loss"]);
      for (const key of ["exposure", "shock_percent", "pnl", "loss"]) stressExact(c[key]);
      const e = c.exposure as Exact, s = c.shock_percent as Exact, pnl = c.pnl as Exact, loss = c.loss as Exact;
      check(c.asset_id === assets[i].asset_id && same(e, amounts[i]) && equalsDecimal(s, shocks[assets[i].asset_id]));
      check(n(s) >= -BigInt(100) * d(s) && n(s) <= BigInt(1000) * d(s));
      check(n(pnl) * d(e) * d(s) * BigInt(100) === n(e) * n(s) * d(pnl));
      check(n(loss) * d(pnl) === -n(pnl) * d(loss)); values.push(pnl);
    });
    check(same(v.total_pnl, total(values)));
  };
  check(Array.isArray(r.scenarios) && r.scenarios.length === inputs.scenarios.length);
  r.scenarios.forEach((s: unknown, i: number) => {outcome(s, inputs.scenarios[i].shocks, "scenario_id"); check((s as Record<string, unknown>).scenario_id === inputs.scenarios[i].scenario_id);});
  const common = [...inputs.common_shocks].sort((a,b) => {const x=decimalRatio(a), y=decimalRatio(b), diff=n(x)*d(y)-n(y)*d(x); return diff < BigInt(0) ? -1 : diff > BigInt(0) ? 1 : 0;});
  check(Array.isArray(r.common_shock_sensitivity) && r.common_shock_sensitivity.length === common.length);
  r.common_shock_sensitivity.forEach((s: unknown, i: number) => {
    outcome(s, Object.fromEntries(assets.map(e => [e.asset_id, common[i]])), "shock_percent");
    const percentage=(s as Record<string, unknown>).shock_percent; stressExact(percentage); check(equalsDecimal(percentage, common[i]));
  });
  check(stable(r.notices) === stable(["user_assumptions_not_observed_market_data", "conditional_calculation_not_probability_forecast_or_advice", "linear_price_notionals_only_no_fx", "fixed_exposures_no_fees_financing_or_rebalancing", "common_shocks_independent_of_named_scenarios"]));
  return value as unknown as StressReceipt;
}
export function stressFormInputs(form: HTMLFormElement): StressInputs {
  const data = new FormData(form), field=(name: string)=>String(data.get(name) ?? "");
  const lines=(name: string)=>field(name).split(/\r?\n/).filter(line=>line.trim()).map(line=>line.trim().split(/\s+/));
  const currency=field("currency");
  const exposures=lines("exposures").map(parts=>{if(parts.length!==2) throw new Error("Each exposure needs an asset ID and signed notional amount."); return {asset_id:parts[0],amount:parts[1],currency,exposure_type:EXPOSURE_TYPE};});
  if(exposures.length<1 || exposures.length>8 || new Set(exposures.map(e=>e.asset_id)).size!==exposures.length) throw new Error("Enter 1 to 8 distinct exposures.");
  const scenarios=lines("scenarios").map(parts=>{
    if(parts.length!==exposures.length+1) throw new Error("Each scenario needs a name and an explicit percentage shock for every exposure. Missing shocks are not zero.");
    return {scenario_id:parts[0],shocks:Object.fromEntries(exposures.map((e,i)=>[e.asset_id,parts[i+1]]))};
  });
  if(scenarios.length<1 || scenarios.length>12 || new Set(scenarios.map(s=>s.scenario_id)).size!==scenarios.length) throw new Error("Enter 1 to 12 distinctly named scenarios.");
  const common_shocks=field("common").trim().split(/\s+/).filter(Boolean);
  if(common_shocks.length<1 || common_shocks.length>21) throw new Error("Enter 1 to 21 explicit common shock percentages.");
  return {reporting_currency:currency,exposure_date:field("date"),exposures,scenarios,common_shocks};
}
export function requestStress(inputs: StressInputs, signal: AbortSignal) {
  return requestHypothetical("hypothetical-stress",inputs,signal,validateStressReceipt,
    "Calculation rejected. Use complete shocks from -100 to 1000 percent, exact decimal strings, one explicit currency and linear price notionals only.");
}
