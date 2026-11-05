// Transport and receipt validation only. Financial arithmetic lives in Python.
export type RiskInputs = {
  reporting_currency: string; exposure_date: string; confidence: string; horizon: number;
  portfolio_value: string | null; exposures: {asset_id: string; amount: string}[];
  sessions: {session_id: string; start: string; end: string; factors: Record<string, string>}[];
};
export type Exact = {numerator: string; denominator: string; display: string};
type Measure = {exact: Exact | null; reason: string | null};
type Scenario = {scenario_id: string[]; start_index: number; stop_index: number; loss: Exact; tail_mass: Exact | null};
export type RiskReceipt = {schema_id: string; inputs: RiskInputs; result: {
  method_id: string; precision_id: string; data_authority: string; reporting_currency: string; exposure_date: string;
  exposures: {asset_id: string; currency: string; amount: Exact}[];
  panel: {panel_id: string; factor_method_id: string; sessions: {session_id: string; start: string; end: string; factors: {asset_id: string; gross_factor: Exact}[]}[]};
  portfolio_value: Exact | null; net_exposure: Exact; gross_exposure: Exact; horizon: number; confidence: Exact;
  scenario_count: number; overlapping: boolean; rank: number | null; tail_mass: Exact; strict_tail_count: number;
  threshold_tie_count: number; var: Measure; es: Measure; var_percent: Measure; es_percent: Measure;
  scenarios: Scenario[]; notices: string[];
}};
const bad = (): never => { throw new Error("The calculation response could not be verified. No result is shown."); };
export function check(value: unknown): asserts value { if (!value) bad(); }
export function object(value: unknown, keys: string[]): asserts value is Record<string, unknown> {
  check(value !== null && typeof value === "object" && !Array.isArray(value));
  check(Object.keys(value).sort().join("|") === [...keys].sort().join("|"));
}
export function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([k, v]) => `${JSON.stringify(k)}:${stable(v)}`).join(",")}}`;
  return JSON.stringify(value);
}
export function exact(value: unknown): asserts value is Exact {
  object(value, ["numerator", "denominator", "display"]);
  check(typeof value.numerator === "string" && /^-?(0|[1-9][0-9]{0,2499})$/.test(value.numerator));
  check(typeof value.denominator === "string" && /^[1-9][0-9]{0,2499}$/.test(value.denominator));
  check(typeof value.display === "string" && /^-?[0-9]+\.[0-9]{18}$/.test(value.display) && value.display.length <= 2520);
  // Verify the display boundary with integer HALF_EVEN; never estimate losses.
  const n = BigInt(value.numerator), d = BigInt(value.denominator), scale = BigInt(10) ** BigInt(18);
  const abs = n < BigInt(0) ? -n : n, remainder = abs * scale % d;
  let units = abs * scale / d;
  if (BigInt(2) * remainder > d || (BigInt(2) * remainder === d && units % BigInt(2) === BigInt(1))) units++;
  const digits = units.toString().padStart(19, "0");
  check(value.display === `${n < BigInt(0) ? "-" : ""}${digits.slice(0, -18)}.${digits.slice(-18)}`);
}
export function equalsDecimal(value: Exact, input: string) {
  const negative = input.startsWith("-"), unsigned = negative ? input.slice(1) : input;
  const [whole, part = ""] = unsigned.split(".");
  return BigInt(value.numerator) * BigInt(10) ** BigInt(part.length) === BigInt(`${negative ? "-" : ""}${whole}${part}`) * BigInt(value.denominator);
}
function measure(value: unknown): asserts value is Measure {
  object(value, ["exact", "reason"]);
  if (value.exact === null) check(["insufficient_scenarios", "insufficient_tail_mass", "portfolio_value_not_declared", "nonpositive_portfolio_value"].includes(value.reason as string));
  else { exact(value.exact); check(value.reason === null); }
}
function integer(value: unknown, low: number, high: number): asserts value is number {
  check(Number.isSafeInteger(value) && (value as number) >= low && (value as number) <= high);
}
export function validateReceipt(value: unknown, inputs: RiskInputs): RiskReceipt {
  object(value, ["schema_id", "inputs", "result"]);
  check(value.schema_id === "hypothetical-risk-v1" && stable(value.inputs) === stable(inputs));
  const r = value.result;
  object(r, ["method_id", "precision_id", "data_authority", "reporting_currency", "exposure_date", "exposures", "panel", "portfolio_value", "net_exposure", "gross_exposure", "horizon", "confidence", "scenario_count", "overlapping", "rank", "tail_mass", "strict_tail_count", "threshold_tie_count", "var", "es", "var_percent", "es_percent", "scenarios", "notices"]);
  check(r.method_id === "historical-loss-es-v1" && r.precision_id === "exact-rational-display18-half-even-v1" && r.data_authority === "unverified_synthetic_inputs");
  check(r.reporting_currency === inputs.reporting_currency && r.exposure_date === inputs.exposure_date && r.horizon === inputs.horizon);
  const assets = [...inputs.exposures].sort((a, b) => a.asset_id < b.asset_id ? -1 : a.asset_id > b.asset_id ? 1 : 0);
  check(Array.isArray(r.exposures) && r.exposures.length === assets.length);
  r.exposures.forEach((e: unknown, i: number) => {
    object(e, ["asset_id", "currency", "amount"]); exact(e.amount);
    check(e.asset_id === assets[i].asset_id && e.currency === inputs.reporting_currency && equalsDecimal(e.amount, assets[i].amount));
  });
  object(r.panel, ["panel_id", "factor_method_id", "sessions"]);
  check(r.panel.panel_id === "user-hypothetical" && r.panel.factor_method_id === "user-entered-exact-gross-factors-v1");
  check(Array.isArray(r.panel.sessions) && r.panel.sessions.length === inputs.sessions.length);
  r.panel.sessions.forEach((s: unknown, i: number) => {
    object(s, ["session_id", "start", "end", "factors"]); const input = inputs.sessions[i];
    check(s.session_id === input.session_id && s.start === input.start && s.end === input.end);
    check(Array.isArray(s.factors) && s.factors.length === assets.length);
    s.factors.forEach((f: unknown, j: number) => { object(f, ["asset_id", "gross_factor"]); exact(f.gross_factor);
      check(f.asset_id === assets[j].asset_id && equalsDecimal(f.gross_factor, input.factors[assets[j].asset_id])); });
  });
  if (inputs.portfolio_value === null) check(r.portfolio_value === null);
  else { exact(r.portfolio_value); check(equalsDecimal(r.portfolio_value, inputs.portfolio_value)); }
  for (const name of ["net_exposure", "gross_exposure", "confidence", "tail_mass"]) exact(r[name]);
  check(equalsDecimal(r.confidence as Exact, inputs.confidence));
  const count = Math.max(0, inputs.sessions.length - inputs.horizon + 1);
  check(r.scenario_count === count && r.overlapping === (inputs.horizon > 1 && count > 1));
  if (count < 2) check(r.rank === null); else integer(r.rank, 1, count);
  integer(r.strict_tail_count, 0, count); integer(r.threshold_tie_count, 0, count);
  for (const name of ["var", "es", "var_percent", "es_percent"]) measure(r[name]);
  const varMeasure = r.var as Measure, esMeasure = r.es as Measure;
  check((varMeasure.exact !== null) === (count >= 2));
  if (count < 2) check(varMeasure.reason === "insufficient_scenarios" && esMeasure.reason === "insufficient_scenarios" && r.strict_tail_count === 0 && r.threshold_tie_count === 0);
  else {
    check((esMeasure.exact !== null) === (BigInt((r.tail_mass as Exact).numerator) >= BigInt((r.tail_mass as Exact).denominator)));
    if (esMeasure.exact === null) check(esMeasure.reason === "insufficient_tail_mass");
    check((r.threshold_tie_count as number) >= 1);
  }
  for (const [base, percent] of [[r.var, r.var_percent], [r.es, r.es_percent]] as [Measure, Measure][]) {
    if (r.portfolio_value === null) check(percent.exact === null && percent.reason === "portfolio_value_not_declared");
    else if (BigInt((r.portfolio_value as Exact).numerator) <= BigInt(0)) check(percent.exact === null && percent.reason === "nonpositive_portfolio_value");
    else check((base.exact === null) === (percent.exact === null) && base.reason === percent.reason);
  }
  check(Array.isArray(r.scenarios) && r.scenarios.length === count);
  const seen = new Set<number>(); let previous: Exact | undefined;
  r.scenarios.forEach((s: unknown) => {
    object(s, ["scenario_id", "start_index", "stop_index", "loss", "tail_mass"]);
    integer(s.start_index, 0, count - 1); integer(s.stop_index, 1, inputs.sessions.length);
    check(s.stop_index === s.start_index + inputs.horizon && !seen.has(s.start_index)); seen.add(s.start_index);
    check(stable(s.scenario_id) === stable(["user-hypothetical", inputs.sessions[s.start_index].session_id, inputs.sessions[s.stop_index - 1].session_id]));
    exact(s.loss); if (previous) check(BigInt(previous.numerator) * BigInt(s.loss.denominator) <= BigInt(s.loss.numerator) * BigInt(previous.denominator)); previous = s.loss;
    check((s.tail_mass === null) === (esMeasure.exact === null));
    if (s.tail_mass !== null) { exact(s.tail_mass); check(BigInt(s.tail_mass.numerator) >= BigInt(0) && BigInt(s.tail_mass.numerator) <= BigInt(s.tail_mass.denominator)); }
  });
  check(stable(r.notices) === stable(["empirical_sample_not_statistical_adequacy", "supplied_calendar_not_verified", "synthetic_inputs_not_source_authority", "no_fees_or_financing"]));
  return value as unknown as RiskReceipt;
}
export function formInputs(form: HTMLFormElement): RiskInputs {
  const data = new FormData(form), field = (name: string) => String(data.get(name) ?? "");
  const lines = (name: string) => field(name).split(/\r?\n/).filter(line => line.trim()).map(line => line.trim().split(/\s+/));
  const exposures = lines("exposures").map(parts => { if (parts.length !== 2) throw new Error("Each exposure needs an asset ID and signed amount."); return {asset_id: parts[0], amount: parts[1]}; });
  if (exposures.length < 1 || exposures.length > 8 || new Set(exposures.map(e => e.asset_id)).size !== exposures.length) throw new Error("Enter 1 to 8 distinct assets.");
  const rows = lines("sessions"); if (rows.length > 120) throw new Error("Enter at most 120 intervals.");
  const sessions = rows.map(parts => {
    if (parts.length !== 3 + exposures.length) throw new Error("Every interval needs an ID, start, end and one factor per asset. Missing observations cannot be filled.");
    return {session_id: parts[0], start: parts[1], end: parts[2], factors: Object.fromEntries(exposures.map((e, i) => [e.asset_id, parts[i + 3]]))};
  });
  if (!/^[1-9][0-9]?$/.test(field("horizon")) || Number(field("horizon")) > 20) throw new Error("Horizon must be an integer from 1 to 20.");
  return {reporting_currency: field("currency"), exposure_date: field("date"), confidence: field("confidence"), horizon: Number(field("horizon")), portfolio_value: field("value") === "" ? null : field("value"), exposures, sessions};
}
export async function requestRisk(inputs: RiskInputs, signal: AbortSignal): Promise<RiskReceipt> {
  return requestHypothetical("hypothetical-risk", inputs, signal, validateReceipt);
}
export async function requestHypothetical<I, R>(endpoint: "hypothetical-risk" | "hypothetical-stress" | "hypothetical-panel-statistics", inputs: I, signal: AbortSignal,
  validate: (value: unknown, inputs: I) => R,
  rejectedMessage = "Calculation rejected. Check exact decimal strings, dates, complete factors and the stated limits, then retry."): Promise<R> {
  check(endpoint === "hypothetical-risk" || endpoint === "hypothetical-stress" || endpoint === "hypothetical-panel-statistics");
  const body = JSON.stringify(inputs);
  if (new TextEncoder().encode(body).length > 131072) throw new Error("Inputs exceed the request limit.");
  const response = await fetch(`/api/finlens/${endpoint}`, {method: "POST", headers: {"Content-Type": "application/json"}, body, signal, cache: "no-store"});
  if (!response.ok) throw new Error(response.status === 404 ? "This development candidate is disabled on the server." : response.status === 429 ? "A calculation is already running. Retry explicitly." : rejectedMessage);
  if (!response.headers.get("content-type")?.toLowerCase().startsWith("application/json")) bad();
  const reader = response.body?.getReader(); check(reader);
  const decoder = new TextDecoder("utf-8", {fatal: true}); let text = "", size = 0;
  try {
    for (;;) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.byteLength; if (size > 1048576) { await reader.cancel(); bad(); }
      text += decoder.decode(value, {stream: true});
    }
    text += decoder.decode();
    return validate(JSON.parse(text), inputs);
  } finally { reader.releaseLock(); }
}
