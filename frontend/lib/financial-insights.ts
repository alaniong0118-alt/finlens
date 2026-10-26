/** FIN-DEPTH-01: bounded admission and presentation, never a finance calculator. */
export const INSIGHT_METRICS = ["revenue", "operating_income", "net_income", "operating_margin", "net_margin", "operating_cash_flow", "free_cash_flow"] as const;
export const INSIGHT_HEADLINE = ["revenue", "operating_margin", "net_margin", "operating_cash_flow", "free_cash_flow"] as const;
export const INSIGHT_DEPENDENCIES: Readonly<Record<string, readonly string[]>> = {
  operating_margin: ["operating_income", "revenue"], net_margin: ["net_income", "revenue"], free_cash_flow: ["operating_cash_flow", "capital_expenditures"],
};
export const INSIGHT_LIMITS = Object.freeze({ bytes: 4194304, slice: 16384, batch: 32768, entries: 1024,
  initial: 131072, nodes: 8192, edges: 16384, sources: 2048, candidates: 4096, slot: 256,
  observations: 64, operands: 32, rejections: 256, windows: 256, yearWindows: 16,
  statements: 35, statementRefs: 8192, refs: 32768, depth: 6, work: 2000000,
  values: 1000000, jsonDepth: 32, members: 64, array: 16384, formatted: 8388608, formatEntries: 8192 });
type Dict = Record<string, unknown>;
export type InsightSelection = { mode: "discover" } | { mode: "compare"; earlier: number; later: number };
export type InsightIdentity = { ticker: string; cik: string; pin: number; selection: InsightSelection; publication?: { facts: number; evidence: number } };
export type InsightRef = { scope: string; category: "F" | "D"; kind: "observation" | "comparison" | "operand" | "source" | "candidate" | "window" | "rejection";
  key: string; metric: string | null; side: "earlier" | "later" | null; role: string | null; window: string | null };
export type InsightNode = { ref: InsightRef; edges: InsightRef[]; data: Dict };
export type InsightStatement = { ruleset: "fin-depth-01-v1"; key: string; rule: string; metric: string | null; side: string | null;
  outcome: string | null; text: string; financial: InsightRef[]; diagnostic: InsightRef[] };
export type InsightResponse = { mode: "discover" | "compare"; ticker: string; company_cik: string; company_name: string;
  data_version: number; facts_version: number; evidence_version: number; scope: string; fiscal_years: number[];
  earlier_fiscal_year: number | null; later_fiscal_year: number | null; periods: Dict; selection_policy: string;
  completeness: "complete" | "partial" | "unavailable" | null; comparisons: Record<string, Dict>; evidence: InsightNode[]; statements: InsightStatement[] };
export class InsightsError extends Error {
  readonly code: string; readonly status: number;
  constructor(code = "INVALID_RESPONSE", message = "Financial insights could not be verified.", status = 502) { super(message); this.name = "InsightsError"; this.code = code; this.status = status; }
}
export function demand(test: unknown, code = "INVALID_RESPONSE"): asserts test { if (!test) throw new InsightsError(code); }
export const isRecord = (v: unknown): v is Dict => v !== null && typeof v === "object" && !Array.isArray(v);
function obj(v: unknown, required: readonly string[], optional: readonly string[] = []): Dict {
  demand(isRecord(v)); const keys = Object.keys(v);
  demand(required.every(k => Object.hasOwn(v, k)) && keys.every(k => required.includes(k) || optional.includes(k))); return v;
}
const list = (v: unknown): unknown[] => { demand(Array.isArray(v)); return v; };
const str = (v: unknown): string => { demand(typeof v === "string"); return v; };
const nullableString = (v: unknown) => v === null || typeof v === "string";
const integer = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && !Object.is(v, -0);
const unsigned = (v: unknown): v is number => integer(v) && v >= 0;
const unit = (metric: string) => metric.endsWith("_margin") ? "ratio" : "USD";
const slots = [...INSIGHT_METRICS, "capital_expenditures"] as readonly string[];
const sides = ["earlier", "later"] as const;
const encoder = new TextEncoder();
export function utf8Length(value: string): number {
  let bytes = 0;
  for (let i = 0; i < value.length; i++) {
    const c = value.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) { const n = value.charCodeAt(++i); demand(n >= 0xdc00 && n <= 0xdfff); bytes += 4; }
    else { demand(c < 0xdc00 || c > 0xdfff); bytes += c < 128 ? 1 : c < 2048 ? 2 : 3; }
  }
  return bytes;
}
function fieldLimit(field: string) {
  return field === "text" ? 2048 : ["reason", "parent_reason", "selection_policy", "percentage_reason"].includes(field) ? 1024
    : field === "company_name" ? 800 : ["metric", "stored_metric", "source", "original_concept"].includes(field) ? 400
      : ["scope", "key", "sec_url"].includes(field) ? 192 : 128;
}
export class InsightBudget {
  work = 0; private sliceWork = 0; private last: number;
  constructor(readonly check: () => void = () => {}, readonly now: () => number = () => performance.now(),
    readonly yieldTask: () => Promise<void> = () => new Promise(resolve => setTimeout(resolve, 0))) { this.last = now(); }
  async tick(amount = 1) {
    this.work += amount; this.sliceWork += amount; demand(this.work <= INSIGHT_LIMITS.work, "INSIGHTS_CLIENT_LIMIT");
    this.check();
    if (this.sliceWork >= 256 || this.now() - this.last >= 4) { await this.yieldTask(); this.check(); this.sliceWork = 0; this.last = this.now(); }
  }
}

/** Bounded tokenizer + iterative grammar. Native JSON.parse happens only after this. */
export async function preflightInsightsJson(text: string, budget = new InsightBudget()): Promise<void> {
  demand(text.length <= INSIGHT_LIMITS.bytes, "INSIGHTS_CLIENT_LIMIT");
  let pos = 0, values = 0;
  type Frame = { kind: "object" | "array"; state: string; count: number; field: string; key: string; keys: Set<string> };
  const stack: Frame[] = [];
  let scannedAt = 0;
  async function scanTick() { if (pos - scannedAt >= 128) { scannedAt = pos; budget.check(); await budget.tick(); } }
  async function whitespace() { while (pos < text.length && /[\x20\t\r\n]/.test(text[pos])) { pos++; await scanTick(); } }
  async function stringToken(limit: number): Promise<string> {
    demand(text[pos++] === '"'); const chars: string[] = []; let bytes = 0;
    async function codeUnit(): Promise<number> {
      demand(pos < text.length); let c = text.charCodeAt(pos++);
      if (c === 92) {
        demand(pos < text.length); const escape = text[pos++];
        if (escape === "u") { const hex = text.slice(pos, pos + 4); demand(/^[0-9a-fA-F]{4}$/.test(hex)); pos += 4; c = parseInt(hex, 16); }
        else { const escapes: Record<string, number> = { '"': 34, "\\": 92, "/": 47, b: 8, f: 12, n: 10, r: 13, t: 9 }; demand(Object.hasOwn(escapes, escape)); c = escapes[escape]; }
      } else demand(c >= 32 && c !== 34);
      return c;
    }
    while (pos < text.length && text[pos] !== '"') {
      let c = await codeUnit();
      if (c >= 0xd800 && c <= 0xdbff) { const low = await codeUnit(); demand(low >= 0xdc00 && low <= 0xdfff); c = 0x10000 + (c - 0xd800) * 1024 + low - 0xdc00; }
      else demand(c < 0xdc00 || c > 0xdfff);
      bytes += c < 128 ? 1 : c < 2048 ? 2 : c < 65536 ? 3 : 4;
      demand(bytes <= limit, "INSIGHTS_CLIENT_LIMIT"); chars.push(String.fromCodePoint(c)); await scanTick();
    }
    demand(text[pos++] === '"'); return chars.join("");
  }
  async function value(field: string, depth: number) {
    await budget.tick(); demand(++values <= INSIGHT_LIMITS.values && depth <= 32, "INSIGHTS_CLIENT_LIMIT"); await whitespace();
    const c = text[pos];
    if (c === "{" || c === "[") { pos++; stack.push({ kind: c === "{" ? "object" : "array", state: "first", count: 0, field, key: "", keys: new Set() }); }
    else if (c === '"') await stringToken(fieldLimit(field));
    else if (c === "t" || c === "f" || c === "n") { const literal = c === "t" ? "true" : c === "f" ? "false" : "null"; demand(text.startsWith(literal, pos)); pos += literal.length; }
    else {
      const start = pos; while (pos < text.length && /[0-9eE+.\-]/.test(text[pos])) { pos++; demand(pos - start <= 17, "INSIGHTS_CLIENT_LIMIT"); }
      const token = text.slice(start, pos); demand(/^-?(?:0|[1-9]\d*)$/.test(token) && integer(Number(token)));
    }
  }
  await value("", 0);
  while (stack.length) {
    await budget.tick(); await whitespace(); const f = stack[stack.length - 1]; const close = f.kind === "object" ? "}" : "]";
    if (f.state === "first" && text[pos] === close) { pos++; stack.pop(); continue; }
    if (f.state === "comma") { if (text[pos] === close) { pos++; stack.pop(); continue; } demand(text[pos++] === ","); f.state = "next"; await whitespace(); }
    if (f.kind === "object") {
      demand(++f.count <= 64, "INSIGHTS_CLIENT_LIMIT"); f.key = await stringToken(192); demand(!f.keys.has(f.key)); f.keys.add(f.key);
      await whitespace(); demand(text[pos++] === ":"); f.state = "comma"; await value(f.key, stack.length);
    } else { demand(++f.count <= 16384, "INSIGHTS_CLIENT_LIMIT"); f.state = "comma"; await value(f.field, stack.length); }
  }
  await whitespace(); demand(pos === text.length); budget.check();
}

export function formatInsightDecimal(raw: string, measure: "USD" | "ratio"): string {
  demand(utf8Length(raw) <= 128, "INSIGHTS_CLIENT_LIMIT");
  const match = /^([+-]?)(\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?)(\d+))?$/.exec(raw); demand(match && match[0] === raw);
  const coefficient = match[2], digits = coefficient.replace(".", ""); demand(digits.length <= 128, "INSIGHTS_CLIENT_LIMIT");
  const exponentDigits = (match[4] ?? "0").replace(/^0+/, "") || "0";
  demand(exponentDigits.length < 3 || exponentDigits.length === 3 && exponentDigits <= "512", "INSIGHTS_CLIENT_LIMIT");
  const exponent = Number(exponentDigits) * (match[3] === "-" ? -1 : 1);
  const point = (coefficient.includes(".") ? coefficient.indexOf(".") : coefficient.length) + exponent + (measure === "ratio" ? 2 : 0);
  const wholeLength = Math.max(1, point), fractionLength = Math.max(0, digits.length - point);
  const predicted = match[1].length + wholeLength + Math.floor((wholeLength - 1) / 3) + (fractionLength ? fractionLength + 1 : 0) + 4;
  demand(predicted <= 1024, "INSIGHTS_CLIENT_LIMIT");
  let whole: string, fraction: string;
  if (point <= 0) { whole = "0"; fraction = "0".repeat(-point) + digits; }
  else { whole = digits.slice(0, point) + "0".repeat(Math.max(0, point - digits.length)); fraction = digits.slice(point); }
  // Canonical display removes redundant integer zeros; raw spelling stays separate.
  // Fractional trailing zeros and the original sign are preserved without Number.
  const grouped = whole.replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return match[1] + grouped + (fraction ? "." + fraction : "") + (measure === "ratio" ? "%" : " USD");
}
const finiteDecimal = (v: unknown): v is string => typeof v === "string" && v.trim() === v && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(v) && v.length <= 128;
function decimalIdentity(v: unknown): string {
  demand(finiteDecimal(v)); const exact = formatInsightDecimal(v, "USD").slice(0, -4).replaceAll(",", "").replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "").replace(/^\+/, "");
  // Decimal equality treats signed zeros as equal; presentation retains their sign.
  return exact === "-0" ? "0" : exact;
}
// Closed admission manifest from Backend 1A METRICS, not a selector or ranking policy.
export const INSIGHT_BASE_CONCEPTS: Readonly<Record<string, readonly string[]>> = Object.freeze({
  revenue: ["RevenuesNetOfInterestExpense", "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
  operating_income: ["OperatingIncomeLoss"], net_income: ["NetIncomeLoss"],
  operating_cash_flow: ["NetCashProvidedByUsedInOperatingActivities"], capital_expenditures: ["PaymentsToAcquirePropertyPlantAndEquipment"],
});
export const INSIGHT_REVENUE_BASES: Readonly<Record<string, string>> = Object.freeze({
  Revenues: "total_revenue", RevenueFromContractWithCustomerExcludingAssessedTax: "customer_contract",
  SalesRevenueNet: "net_sales", RevenuesNetOfInterestExpense: "net_interest",
});
const sourceIdentityFields = ["company_cik", "source", "original_concept", "period_start", "period_end", "unit", "accession_number", "form", "filed"] as const;
function sameSourceIdentity(a: Dict, b: Dict): boolean { return sourceIdentityFields.every(field => a[field] === b[field]); }
function date(v: unknown): v is string { return typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) && !v.startsWith("0000-") && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v; }
const periodKeys = ["kind", "start", "end", "fiscal_year", "fiscal_period", "fiscal_label_basis"];
function period(v: unknown, annual = false, year?: number): Dict {
  const p = obj(v, periodKeys); demand(date(p.end) && (p.fiscal_year === null || integer(p.fiscal_year)) && nullableString(p.fiscal_period) && typeof p.fiscal_label_basis === "string");
  if (annual) demand(p.kind === "annual" && p.fiscal_period === "FY" && p.fiscal_year === year && p.end.startsWith(String(year) + "-"));
  const bands: Record<string, [number, number]> = { quarter: [75, 105], half_year: [165, 200], nine_months: [245, 295], annual: [330, 390] };
  if (p.kind === "instant") demand(!annual && p.start === null);
  else { demand(typeof p.kind === "string" && Object.hasOwn(bands, p.kind) && date(p.start)); const days = (Date.parse(p.end) - Date.parse(p.start)) / 86400000 + 1; demand(days >= bands[p.kind][0] && days <= bands[p.kind][1]); }
  return p;
}
const windowKey = (p: unknown) => p === null ? null : `${(p as Dict).start}/${(p as Dict).end}/${(p as Dict).kind}`;
async function equal(a: unknown, b: unknown, budget: InsightBudget): Promise<boolean> {
  const pending: [unknown, unknown][] = [[a, b]];
  while (pending.length) { await budget.tick(); const [x, y] = pending.pop()!; if (x === y) continue;
    if (Array.isArray(x) && Array.isArray(y)) { if (x.length !== y.length) return false; for (let i = 0; i < x.length; i++) pending.push([x[i], y[i]]); }
    else if (isRecord(x) && isRecord(y)) { const keys = Object.keys(x); if (keys.length !== Object.keys(y).length) return false; for (const k of keys) { if (!Object.hasOwn(y, k)) return false; pending.push([x[k], y[k]]); } }
    else return false;
  } return true;
}
function safeSec(v: unknown, cik: string, accession: unknown): boolean {
  if (typeof v !== "string" || typeof accession !== "string" || accession.length !== 20 || !/^\d{10}-\d{2}-\d{6}$/.test(accession)) return false;
  return v === `https://www.sec.gov/Archives/edgar/data/${cik.replace(/^0+/, "") || "0"}/${accession.replaceAll("-", "")}/${accession}-index.html`;
}
const sourceKeys = ["fact_id", "canonical_metric", "company_cik", "stored_metric", "original_concept", "value", "unit", "period_start", "period_end", "stored_period_type", "source_fiscal_year", "source_fiscal_period", "frame", "filed", "form", "accession_number", "source", "sec_url", "stored_at"];
function source(v: unknown, cik: string) {
  const s = obj(v, sourceKeys); demand(integer(s.fact_id) && s.company_cik === cik && finiteDecimal(s.value) && s.unit === "USD" && date(s.period_start) && date(s.period_end) && date(s.filed));
  demand(safeSec(s.sec_url, cik, s.accession_number) && typeof s.form === "string" && typeof s.original_concept === "string" && typeof s.stored_metric === "string" && typeof s.canonical_metric === "string" && typeof s.source === "string" && typeof s.stored_at === "string" && Number.isFinite(Date.parse(s.stored_at)));
  demand(nullableString(s.stored_period_type) && nullableString(s.source_fiscal_period) && nullableString(s.frame) && (s.source_fiscal_year === null || integer(s.source_fiscal_year)));
}
const metricKeys = ["metric", "unit", "status", "value", "reason", "period", "formula", "provenance", "alternatives", "inputs"];
async function metric(v: unknown, name: string, cik: string, budget: InsightBudget): Promise<Dict> {
  await budget.tick(metricKeys.length);
  const p = obj(v, metricKeys, ["revenue_basis", "scope_authorization"]); demand(p.metric === name && p.unit === unit(name) && ["available", "unavailable", "not_applicable"].includes(str(p.status)) && nullableString(p.reason) && nullableString(p.formula));
  const formulas: Record<string, string> = { operating_margin: "operating_income / revenue", net_margin: "net_income / revenue", free_cash_flow: "operating_cash_flow - capital_expenditures" }; demand(p.formula === (formulas[name] ?? null));
  demand(p.status === "available" ? finiteDecimal(p.value) && p.period !== null : p.value === null && typeof p.reason === "string" && p.reason.length > 0);
  if (p.period !== null) period(p.period);
  if (Object.hasOwn(p, "revenue_basis")) demand(["total_revenue", "customer_contract", "net_sales", "net_interest"].includes(str(p.revenue_basis)));
  // Backend 1A requires all authorization registries empty.
  demand(!Object.hasOwn(p, "scope_authorization"));
  demand(list(p.provenance).length <= 2 && list(p.alternatives).length <= 256 && list(p.inputs).length <= 2, "INSIGHTS_CLIENT_LIMIT");
  for (const s of [...list(p.provenance), ...list(p.alternatives)]) { await budget.tick(sourceKeys.length); source(s, cik); }
  for (const value of list(p.inputs)) { await budget.tick(7); const i = obj(value, ["role", "metric", "value", "unit", "period", "fact_ids"], ["revenue_basis"]); demand(typeof i.role === "string" && typeof i.metric === "string" && finiteDecimal(i.value) && i.unit === "USD"); period(i.period); demand(list(i.fact_ids).length <= 2 && list(i.fact_ids).every(integer)); if (Object.hasOwn(i, "revenue_basis")) demand(["total_revenue", "customer_contract", "net_sales", "net_interest"].includes(str(i.revenue_basis))); }
  return p;
}
const comparisonKeys = ["status", "reason", "earlier_period", "later_period", "earlier", "later", "absolute_change", "percentage_change", "percentage_status", "percentage_reason", "direction", "formula"];
async function comparison(v: unknown, name: string, identity: InsightIdentity, budget: InsightBudget, diagnostic = false): Promise<Dict> {
  demand(identity.selection.mode === "compare"); const c = obj(v, comparisonKeys);
  for (const side of sides) { const request = obj(c[side + "_period"], ["fiscal_year", "quarter"]); demand(request.fiscal_year === identity.selection[side] && request.quarter === null); const p = await metric(c[side], name, identity.cik, budget); if (p.period !== null) period(p.period, true, identity.selection[side]); }
  demand(["available", "unavailable", "not_applicable"].includes(str(c.status)) && nullableString(c.reason) && nullableString(c.percentage_reason));
  demand(c.formula === "absolute_change = later - earlier; percentage_change = (later - earlier) / earlier");
  demand(["available", "unavailable", "not_applicable"].includes(str(c.percentage_status)));
  if (c.status === "available") demand(finiteDecimal(c.absolute_change) && ["increase", "decrease", "no_change"].includes(str(c.direction)));
  else demand(c.absolute_change === null && c.percentage_change === null && c.direction === null && typeof c.reason === "string" && c.percentage_status === "unavailable");
  demand(c.percentage_status === "available" ? finiteDecimal(c.percentage_change) : c.percentage_change === null && (typeof c.percentage_reason === "string" || diagnostic && c.percentage_reason === null)); return c;
}
const refKeys = ["scope", "kind", "key", "metric", "side", "role", "window", "category"];
function reference(v: unknown, scope: string): InsightRef {
  const r = obj(v, refKeys); demand(r.scope === scope && ["F", "D"].includes(str(r.category)) && typeof r.key === "string" && ["comparison", "observation", "operand", "source", "candidate", "window", "rejection"].includes(str(r.kind)));
  demand(r.metric === null || slots.includes(str(r.metric))); demand(r.side === null || sides.includes(r.side as "earlier")); demand(nullableString(r.role) && nullableString(r.window));
  demand(r.category !== "F" || ["comparison", "observation", "operand", "source"].includes(str(r.kind))); return r as unknown as InsightRef;
}
const rawFields = ["id", "company_cik", "metric", "value", "unit", "period_start", "period_end", "period_type", "fiscal_year", "fiscal_period", "form", "filed", "accession_number", "frame", "source", "created_at"];
export function validInsightIdentity(i: InsightIdentity) {
  demand(typeof i.ticker === "string" && i.ticker.trim() === i.ticker && /^[A-Z0-9.\-]{1,10}$/.test(i.ticker) && typeof i.cik === "string" && i.cik.length === 10 && /^\d{10}$/.test(i.cik) && unsigned(i.pin));
  if (i.publication) demand(unsigned(i.publication.facts) && unsigned(i.publication.evidence) && i.publication.facts <= i.pin && i.publication.evidence <= i.pin);
  if (i.selection.mode === "compare") { obj(i.selection, ["mode", "earlier", "later"]); demand(integer(i.selection.earlier) && integer(i.selection.later) && i.selection.earlier >= 1900 && i.selection.later <= 2099 && i.selection.earlier < i.selection.later); }
  else { obj(i.selection, ["mode"]); demand(i.selection.mode === "discover"); }
}

export async function validateInsights(value: unknown, identity: InsightIdentity, budget = new InsightBudget()): Promise<InsightResponse> {
  validInsightIdentity(identity);
  const r = obj(value, ["mode", "ticker", "company_cik", "company_name", "data_version", "facts_version", "evidence_version", "scope", "fiscal_years", "earlier_fiscal_year", "later_fiscal_year", "periods", "selection_policy", "completeness", "comparisons", "evidence", "statements"]);
  demand(r.ticker === identity.ticker && r.company_cik === identity.cik && r.mode === identity.selection.mode && r.data_version === identity.pin && typeof r.company_name === "string" && typeof r.selection_policy === "string");
  demand(unsigned(r.facts_version) && unsigned(r.evidence_version) && r.facts_version <= identity.pin && r.evidence_version <= identity.pin);
  if (identity.publication) demand(r.facts_version === identity.publication.facts && r.evidence_version === identity.publication.evidence);
  const earlier = identity.selection.mode === "compare" ? identity.selection.earlier : null, later = identity.selection.mode === "compare" ? identity.selection.later : null;
  demand(r.scope === `${identity.cik}:${identity.pin}:${r.facts_version}:${r.evidence_version}:${earlier ?? "None"}:${later ?? "None"}` && r.earlier_fiscal_year === earlier && r.later_fiscal_year === later);
  const years = list(r.fiscal_years); demand(years.length <= 200 && years.every((y, n) => integer(y) && y >= 1900 && y <= 2099 && (!n || (years[n - 1] as number) > y)));
  if (identity.selection.mode === "discover") { demand(Object.keys(obj(r.periods, [])).length === 0 && Object.keys(obj(r.comparisons, [])).length === 0 && list(r.evidence).length === 0 && list(r.statements).length === 0 && r.completeness === null); return r as unknown as InsightResponse; }
  const periods = obj(r.periods, sides), comparisons = obj(r.comparisons, INSIGHT_METRICS);
  for (const side of sides) if (periods[side] !== null) { period(periods[side], true, identity.selection[side]); demand(years.includes(identity.selection[side])); }
  for (const name of INSIGHT_METRICS) { await budget.tick(); await comparison(comparisons[name], name, identity, budget); }
  const nodes = list(r.evidence); demand(nodes.length <= 8192, "INSIGHTS_CLIENT_LIMIT");
  const map = new Map<string, InsightNode>(), indexed = new Map<string, InsightNode>(), rawSources = new Map<string, Dict>(), counts: Record<string, number> = {}, sourceIds = new Set<string>(), windows = new Set<string>(), slotsCount = new Map<string, number>(); let edges = 0;
  for (const item of nodes) {
    await budget.tick(); const node = obj(item, ["ref", "edges", "data"]); const ref = reference(node.ref, str(r.scope)); demand(!map.has(ref.key)); demand(isRecord(node.data));
    const n = node as unknown as InsightNode; map.set(ref.key, n); edges += list(n.edges).length; demand(edges <= 16384, "INSIGHTS_CLIENT_LIMIT");
    if (["observation", "comparison", "operand"].includes(ref.kind)) { const index = [ref.category, ref.kind, ref.metric, ref.side, ref.role].join(":"); demand(!indexed.has(index)); indexed.set(index, n); }
    if (ref.kind === "source") demand(ref.metric === null && ref.side === null && ref.role === null && ref.window === null);
    else if (ref.kind === "window") demand(ref.metric === null && ref.role === null && ref.side !== null && ref.window === windowKey(n.data));
    else { demand(ref.metric !== null && (ref.kind === "comparison" || ref.kind === "rejection" && ref.side === null ? ref.side === null && ref.window === null : ref.side !== null && ref.window === windowKey(periods[ref.side]))); demand(ref.kind === "operand" ? INSIGHT_DEPENDENCIES[ref.metric!]?.includes(ref.role!) : ref.role === null); }
    counts[ref.kind] = (counts[ref.kind] ?? 0) + 1;
    if (ref.kind === "source") { obj(n.data, [...rawFields, "original_concept", "sec_url"]); for (const f of rawFields) { demand(nullableString(n.data[f])); if (n.data[f] !== null) demand(utf8Length(str(n.data[f])) <= (["metric", "source"].includes(f) ? 400 : ["period_start", "period_end", "filed", "created_at"].includes(f) ? 64 : 128), "INSIGHTS_CLIENT_LIMIT"); }
      demand(n.data.company_cik === identity.cik && typeof n.data.id === "string" && integer(Number(n.data.id)) && String(Number(n.data.id)) === n.data.id && typeof n.data.original_concept === "string" && nullableString(n.data.sec_url));
      sourceIds.add(str(n.data.id)); demand(sourceIds.size <= 2048, "INSIGHTS_CLIENT_LIMIT");
      const old = rawSources.get(str(n.data.id)); if (old) demand(await equal(old, n.data, budget)); else rawSources.set(str(n.data.id), n.data);
      if (ref.category === "F") demand(finiteDecimal(n.data.value) && safeSec(n.data.sec_url, identity.cik, n.data.accession_number));
    } else if (ref.kind === "observation") { obj(n.data, ["canonical", "admitted"]); demand(typeof n.data.admitted === "boolean" && (ref.category !== "F" || n.data.admitted)); await metric(n.data.canonical, str(ref.metric), identity.cik, budget); }
    else if (ref.kind === "comparison") { if (ref.category === "D") { obj(n.data, ["canonical", "admitted"]); demand(typeof n.data.admitted === "boolean"); await comparison(n.data.canonical, str(ref.metric), identity, budget, true); }
      else { await comparison(n.data, str(ref.metric), identity, budget); demand(await equal(n.data, comparisons[str(ref.metric)], budget)); } }
    else if (ref.kind === "operand") { obj(n.data, ref.category === "F" ? ["required_metric"] : ["required_metric", "expected_unit", "expected_period", "admitted_for_parent", "parent_reason"]); demand(n.data.required_metric === ref.role);
      if (ref.category === "D") demand(n.data.expected_unit === "USD" && typeof n.data.admitted_for_parent === "boolean" && nullableString(n.data.parent_reason) && await equal(n.data.expected_period, periods[str(ref.side)], budget)); }
    else if (ref.kind === "candidate") { demand(ref.category === "D"); obj(n.data, ["dispositions", "duration_kind"]); const dispositions = list(n.data.dispositions); demand(dispositions.length > 0 && new Set(dispositions).size === dispositions.length && dispositions.every(d => ["selected_by_existing_normalization", "conflicting_value", "equivalent_duplicate", "scope_excluded", "alternative_vintage", "scope_ambiguous", "nonfinite_value", "invalid_source_unit_period_or_metadata", "outside_selected_annual_window", "negative_capex_payment", "alternative_candidate"].includes(str(d)))); demand(n.data.duration_kind === null || ["annual", "quarter", "half_year", "nine_months", "instant"].includes(str(n.data.duration_kind))); const key = ref.metric + ":" + ref.side; slotsCount.set(key, (slotsCount.get(key) ?? 0) + 1); demand(slotsCount.get(key)! <= 256, "INSIGHTS_CLIENT_LIMIT"); }
    else if (ref.kind === "rejection") { demand(ref.category === "D"); obj(n.data, ["code", "reason"]); demand(["observation_not_admitted", "comparison_not_admitted"].includes(str(n.data.code)) && typeof n.data.reason === "string"); }
    else { demand(ref.category === "D"); period(n.data, true, identity.selection[ref.side as "earlier"]); windows.add(windowKey(n.data)!); }
    const suffix = ref.kind === "source" ? n.data.id : ref.kind === "candidate" ? n.edges[0]?.key.split("|").at(-1) : ref.kind === "rejection" ? n.data.code : "";
    demand(ref.key === [ref.category, ref.kind, ref.metric, ref.side, ref.role, ref.window, suffix].map(v => v ?? "").join("|"));
  }
  for (const [kind, ceiling] of Object.entries({ candidate: 4096, observation: 64, operand: 32, rejection: 256 })) demand((counts[kind] ?? 0) <= ceiling, "INSIGHTS_CLIENT_LIMIT");
  demand(windows.size <= 256, "INSIGHTS_CLIENT_LIMIT"); for (const year of [earlier, later]) demand([...windows].filter(w => w.split("/")[1]?.startsWith(String(year))).length <= 16, "INSIGHTS_CLIENT_LIMIT");
  const nodeFor = async (ref: InsightRef) => { const node = map.get(ref.key); demand(node && await equal(node.ref, ref, budget)); return node; };
  const find = (category: string, kind: string, name: string, side: string | null = null) => indexed.get([category, kind, name, side, null].join(":"));
  for (const n of map.values()) {
    await budget.tick(); let previous = "";
    for (const ref of n.edges) { await budget.tick(); reference(ref, str(r.scope)); demand(ref.key > previous && ref.category === n.ref.category); previous = ref.key; await nodeFor(ref);
      const allowed: Record<string, string[]> = { comparison: ["observation", "rejection", "window"], observation: ["operand", "source", ...(ref.category === "D" ? ["candidate", "rejection", "window"] : [])], operand: ["observation", ...(ref.category === "D" ? ["candidate", "rejection"] : [])], source: [], candidate: ["source"], rejection: ["candidate", "source", "window"], window: ["source"] };
      demand(allowed[n.ref.kind].includes(ref.kind));
      if (n.ref.kind === "comparison" && ref.kind === "observation") demand(ref.metric === n.ref.metric && sides.includes(ref.side as "earlier"));
      if (n.ref.kind === "comparison" && ref.kind === "rejection") demand(ref.metric === n.ref.metric && ref.side === null);
      if (n.ref.kind === "observation" && ref.kind === "operand") demand(ref.metric === n.ref.metric && ref.side === n.ref.side && INSIGHT_DEPENDENCIES[n.ref.metric!]?.includes(ref.role!));
      if (n.ref.kind === "observation" && ["candidate", "rejection"].includes(ref.kind)) demand(ref.metric === n.ref.metric && ref.side === n.ref.side);
      if (n.ref.kind === "operand" && ref.kind === "observation") demand(ref.metric === n.ref.role && ref.side === n.ref.side && ref.window === n.ref.window);
    }
    if (n.ref.kind === "candidate") demand(n.edges.length === 1 && !INSIGHT_DEPENDENCIES[n.ref.metric!]);
    if (n.ref.kind === "rejection") demand(n.edges.length === 0);
  }
  // One iterative DAG pass; shared subgraphs do not enumerate paths.
  const heights = new Map<string, number>(), active = new Set<string>();
  for (const root of map.keys()) {
    const stack: { key: string; next: number; height: number }[] = [{ key: root, next: 0, height: 0 }];
    while (stack.length) { await budget.tick(); demand(stack.length <= 7, "INSIGHTS_CLIENT_LIMIT"); const f = stack.at(-1)!; if (heights.has(f.key)) { stack.pop(); continue; } active.add(f.key); const n = map.get(f.key)!;
      if (f.next < n.edges.length) { const key = n.edges[f.next].key; if (heights.has(key)) { f.height = Math.max(f.height, heights.get(key)! + 1); f.next++; } else { demand(!active.has(key)); stack.push({ key, next: 0, height: 0 }); } }
      else { demand(f.height <= 6, "INSIGHTS_CLIENT_LIMIT"); heights.set(f.key, f.height); active.delete(f.key); stack.pop(); }
    }
  }
  async function closure(roots: InsightNode[]): Promise<InsightRef[]> {
    const queued = new Set<string>(), todo: InsightRef[] = []; for (const n of roots) if (!queued.has(n.ref.key)) { queued.add(n.ref.key); todo.push(n.ref); }
    let examined = 0; const out: InsightRef[] = [];
    while (todo.length) { await budget.tick(); const ref = todo.pop()!; out.push(ref); demand(out.length <= 8192, "INSIGHTS_CLIENT_LIMIT");
      for (const edge of map.get(ref.key)!.edges) { await budget.tick(); demand(++examined <= 16384, "INSIGHTS_CLIENT_LIMIT"); if (!queued.has(edge.key)) { queued.add(edge.key); todo.push(edge); } }
      demand(todo.length <= 8192, "INSIGHTS_CLIENT_LIMIT");
    } return out.sort((a, b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
  }
  // Observation admission is independent of comparison admission.
  for (const name of slots) for (const side of sides) {
    const d = find("D", "observation", name, side), f = find("F", "observation", name, side); demand(d);
    demand(Boolean(f) === d.data.admitted);
    if (f) {
      demand(await equal(f.data, d.data, budget)); const p = f.data.canonical as Dict; demand(p.status === "available" && await equal(p.period, periods[side], budget) && f.ref.window === windowKey(periods[side]));
      const dependencies = INSIGHT_DEPENDENCIES[name] ?? []; demand(list(p.inputs).length === dependencies.length && f.edges.length === (dependencies.length || 1));
      if (dependencies.length) {
        const provenance: unknown[] = [];
        demand(p.formula !== null); for (const [i, role] of dependencies.entries()) { const operand = f.edges.find(e => e.role === role); demand(operand); const on = map.get(operand.key)!; demand(on.edges.length === 1); const child = map.get(on.edges[0].key)!; const input = (p.inputs as Dict[])[i], cp = child.data.canonical as Dict;
          demand(input.role === role && input.metric === role && input.value === cp.value && input.unit === cp.unit && await equal(input.period, cp.period, budget) && await equal(input.fact_ids, (cp.provenance as Dict[]).map(s => s.fact_id), budget) && input.revenue_basis === cp.revenue_basis);
          provenance.push(...list(cp.provenance));
        }
        demand(await equal(p.provenance, provenance, budget));
      } else {
        demand(p.formula === null && list(p.provenance).length === 1);
        const raw = map.get(f.edges[0].key)!; demand(raw.ref.kind === "source");
        const src = (p.provenance as Dict[])[0], shared = periods[side] as Dict;
        // Bind the displayed base observation itself, not just two agreeing source copies.
        demand(src.canonical_metric === name && src.stored_metric === raw.data.metric
          && INSIGHT_BASE_CONCEPTS[name]?.includes(str(src.original_concept))
          && raw.data.source === "SEC Company Facts API: " + src.original_concept
          && src.original_concept === raw.data.original_concept);
        demand(String(src.fact_id) === raw.data.id && src.company_cik === identity.cik
          && decimalIdentity(p.value) === decimalIdentity(src.value) && decimalIdentity(src.value) === decimalIdentity(raw.data.value)
          && p.unit === src.unit && src.unit === raw.data.unit);
        demand(shared && shared.kind === "annual" && src.period_start === shared.start && src.period_end === shared.end
          && raw.data.period_start === shared.start && raw.data.period_end === shared.end);
        demand(["10-Q", "10-Q/A", "10-K", "10-K/A"].includes(str(raw.data.form))
          && date(raw.data.filed) && raw.data.filed >= str(shared.end));
        if (name === "revenue") demand(p.revenue_basis === INSIGHT_REVENUE_BASES[str(src.original_concept)]);

        let selectedCandidate = false;
        for (const ref of d.edges) {
          if (ref.kind !== "candidate") continue;
          await budget.tick(sourceIdentityFields.length + 1);
          const candidate = map.get(ref.key)!, input = map.get(candidate.edges[0].key)!.data;
          const dispositions = candidate.data.dispositions as string[];
          const selected = input.id === raw.data.id;
          demand(dispositions.includes("selected_by_existing_normalization") === selected);
          selectedCandidate ||= selected;
          if (selected || sameSourceIdentity(input, raw.data)) {
            // A declared selected-identity conflict cannot coexist with F admission.
            demand(!dispositions.includes("conflicting_value"));
            // Missing/mislabelled dispositions cannot conceal a finite identity conflict.
            // Nonfinite rejected candidates remain diagnostic, as in Backend 1A usable().
            if (finiteDecimal(input.value)) demand(decimalIdentity(input.value) === decimalIdentity(raw.data.value));
          }
        }
        demand(selectedCandidate);
      }
    }
    demand(await equal((d.data.canonical as Dict).period, periods[side], budget));
    const dependencies = INSIGHT_DEPENDENCIES[name] ?? [];
    const operands = d.edges.filter(e => e.kind === "operand"); demand(operands.length === dependencies.length);
    for (const role of dependencies) { const operand = operands.find(e => e.role === role); demand(operand); const child = map.get(operand.key)!; demand(child.data.admitted_for_parent === d.data.admitted && child.edges.length === 1 && child.edges[0].key === find("D", "observation", role, side)?.ref.key); }
    demand(d.data.admitted || d.edges.some(e => e.kind === "rejection"));
  }
  for (const name of INSIGHT_METRICS) {
    const c = comparisons[name] as Dict, d = find("D", "comparison", name), f = find("F", "comparison", name); demand(d && Boolean(f) === (c.status === "available") && d.data.admitted === Boolean(f));
    const canonical = d.data.canonical as Dict;
    demand(await equal(c.earlier, canonical.earlier, budget) && await equal(c.later, canonical.later, budget));
    if (!f) demand(c.status === (canonical.status === "available" ? "unavailable" : canonical.status) && (canonical.reason === null || c.reason === canonical.reason));
    for (const side of sides) { const observation = find("D", "observation", name, side)!; demand(d.edges.some(e => e.key === observation.ref.key)); }
    if (f) { demand(f.edges.length === 2); for (const side of sides) { const o = find("F", "observation", name, side); demand(o && f.edges.some(e => e.key === o.ref.key) && await equal(c[side], o.data.canonical, budget)); } demand(await equal(d.data.canonical, c, budget));
      const left = c.earlier as Dict, right = c.later as Dict, a = left.period as Dict, b = right.period as Dict;
      const gap = identity.selection.later - identity.selection.earlier, tolerance = 15 + Math.floor(gap / 4);
      const startGap = (Date.parse(str(b.start)) - Date.parse(str(a.start))) / 86400000, endGap = (Date.parse(str(b.end)) - Date.parse(str(a.end))) / 86400000;
      demand(Math.abs(startGap - 365 * gap) <= tolerance && Math.abs(endGap - 365 * gap) <= tolerance && Math.abs(endGap - startGap) <= 9);
      if (name === "revenue") demand(left.revenue_basis === right.revenue_basis);
      const li = list(left.inputs) as Dict[], ri = list(right.inputs) as Dict[]; demand(li.length === ri.length && li.every((input, i) => input.metric === ri[i].metric && input.role === ri[i].role && input.unit === ri[i].unit && input.revenue_basis === ri[i].revenue_basis));
    }
  }
  const available = INSIGHT_HEADLINE.filter(m => (comparisons[m] as Dict).status === "available");
  demand(r.completeness === (available.length === 5 ? "complete" : available.length ? "partial" : "unavailable"));
  const statements = list(r.statements); demand(statements.length <= 35, "INSIGHTS_CLIENT_LIMIT"); const actual = new Map<string, InsightStatement>(); let totalRefs = 0;
  for (const value of statements) { await budget.tick(); const s = obj(value, ["ruleset", "key", "rule", "metric", "side", "outcome", "text", "financial", "diagnostic"]) as unknown as InsightStatement;
    demand(s.ruleset === "fin-depth-01-v1" && typeof s.key === "string" && typeof s.text === "string" && s.text.length > 0 && !actual.has(s.key)); actual.set(s.key, s);
    const refs = [...list(s.financial), ...list(s.diagnostic)]; totalRefs += refs.length; demand(refs.length <= 8192 && totalRefs <= 32768, "INSIGHTS_CLIENT_LIMIT");
    for (const [category, refs] of [["F", s.financial], ["D", s.diagnostic]] as const) { let prev = ""; for (const ref of refs) { await budget.tick(); reference(ref, str(r.scope)); demand(ref.category === category && ref.key > prev); prev = ref.key; await nodeFor(ref); } }
  }
  const required = new Set<string>();
  async function requireStatement(key: string, rule: string, name: string | null, side: string | null, financial: InsightNode[], diagnostic: InsightNode[], outcome: string | null = null, optional = false) {
    const s = actual.get(key); if (!s && optional) return; demand(s); required.add(key);
    demand(s.rule === rule && s.metric === name && s.side === side && s.outcome === outcome && await equal(s.financial, await closure(financial), budget) && await equal(s.diagnostic, await closure(diagnostic), budget));
  }
  for (const name of INSIGHT_METRICS) {
    for (const side of sides) { const f = find("F", "observation", name, side); if (f) await requireStatement(`value:${name}:${side}`, "VALUE", name, side, [f], []); }
    const f = find("F", "comparison", name);
    if (!f) { await requireStatement(`unavailable:${name}`, "UNAVAILABLE", name, null, [], [find("D", "comparison", name)!]); continue; }
    await requireStatement(`change:${name}`, "CHANGE", name, null, [f], []);
    const c = comparisons[name] as Dict;
    if (unit(name) === "USD") { const percent = c.percentage_status === "available"; await requireStatement(`${percent ? "percentage" : "percentage-unavailable"}:${name}`, percent ? "PERCENT_CHANGE" : "PERCENT_UNAVAILABLE", name, null, [f], []); }
    else demand(c.percentage_status === "not_applicable");
    await requireStatement(`precision:${name}`, "PRECISION_NOTICE", name, null, [f], [], null, true);
  }
  const blocking = INSIGHT_HEADLINE.filter(m => (comparisons[m] as Dict).status !== "available");
  const outcome = blocking.length ? "not_assessable" : (comparisons.revenue as Dict).direction !== "increase" ? "revenue_not_increased" : INSIGHT_HEADLINE.every(m => (comparisons[m] as Dict).direction === "increase") ? "all_increased" : "mixed";
  await requireStatement("overall", "OVERALL", null, null, blocking.length ? [] : INSIGHT_HEADLINE.map(m => find("F", "comparison", m)!), blocking.map(m => find("D", "comparison", m)!), outcome);
  await requireStatement("limitation", "LIMITATION", null, null, [], []);
  demand(actual.size === required.size && [...actual.keys()].every((key, i) => key === [...required][i]));
  // Reconcile complete source metadata, including alternatives and diagnostic operands.
  const checkSource = async (s: Dict) => {
    await budget.tick(); const raw = rawSources.get(String(s.fact_id)); demand(raw);
    demand(decimalIdentity(s.value) === decimalIdentity(raw.value));
    for (const field of ["company_cik", "original_concept", "unit", "period_start", "period_end", "filed", "form", "accession_number", "frame", "source", "sec_url"]) demand(s[field] === raw[field]);
    demand(s.stored_metric === raw.metric && s.stored_period_type === raw.period_type);
    demand((s.source_fiscal_year === null ? null : String(s.source_fiscal_year)) === raw.fiscal_year && s.source_fiscal_period === raw.fiscal_period);
    const timestamp = (v: unknown) => str(v).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1"); demand(timestamp(s.stored_at) === timestamp(raw.created_at));
  };
  for (const node of map.values()) {
    const canonical = node.ref.kind === "observation" ? node.data.canonical : node.ref.kind === "comparison" ? node.ref.category === "F" ? node.data : node.data.canonical : null;
    if (!isRecord(canonical)) continue;
    const points = node.ref.kind === "observation" ? [canonical] : [canonical.earlier as Dict, canonical.later as Dict];
    for (const p of points) for (const s of [...p.provenance as Dict[], ...p.alternatives as Dict[]]) await checkSource(s);
  }
  const roots = [...map.values()].filter(n => n.ref.category === "F" && ["observation", "comparison"].includes(n.ref.kind) || n.ref.category === "D" && n.ref.kind === "comparison");
  demand((await closure(roots)).length === map.size);
  budget.check(); return r as unknown as InsightResponse;
}

export type DisplayRecord = { ref: InsightRef; fields: [string, string | number | boolean | null][]; links: (InsightRef & { collection: string; page: number })[]; section: string };
export type InsightsPresentation = Omit<InsightResponse, "evidence" | "comparisons" | "statements"> & {
  statements: (Omit<InsightStatement, "financial" | "diagnostic"> & { targets: { collection: string; page: number; key: string }[] })[]; metrics: { metric: string; side: string; raw: string; formatted: string; unit: string; calculated: boolean; ref: InsightRef }[];
  collections: { id: string; pages: number; records: number }[] };
export type PreparedInsights = { initial: InsightsPresentation; pages: Map<string, number[][]>; nodes: InsightNode[]; record: (index: number) => DisplayRecord };
export function encodedSize(v: unknown): number { return encoder.encode(JSON.stringify(v)).byteLength; }
export function structuralEntries(v: unknown): number {
  let count = 0; const stack = [v]; while (stack.length) { const x = stack.pop(); if (Array.isArray(x)) { count += x.length; stack.push(...x); } else if (isRecord(x)) { const values = Object.values(x); count += values.length; stack.push(...values); } demand(count <= 4096, "INSIGHTS_CLIENT_LIMIT"); } return count;
}
export async function prepareInsights(r: InsightResponse, budget: InsightBudget): Promise<PreparedInsights> {
  const metrics: InsightsPresentation["metrics"] = [], formats = new Map<string, string>(); let formattedBytes = 0;
  const locations = new Map<string, { collection: string; page: number; key: string }>();
  function format(raw: string, measure: "USD" | "ratio") { const key = measure + ":" + raw; let v = formats.get(key); if (v === undefined) { v = formatInsightDecimal(raw, measure); formattedBytes += utf8Length(v); demand(formats.size < 8192 && formattedBytes <= 8388608, "INSIGHTS_CLIENT_LIMIT"); formats.set(key, v); } return v; }
  for (const n of r.evidence) { await budget.tick(); if (n.ref.category === "F" && n.ref.kind === "observation" && INSIGHT_METRICS.includes(n.ref.metric as typeof INSIGHT_METRICS[number])) { const p = n.data.canonical as Dict; metrics.push({ metric: n.ref.metric!, side: n.ref.side!, raw: str(p.value), formatted: format(str(p.value), p.unit as "USD" | "ratio"), unit: str(p.unit), calculated: Boolean(INSIGHT_DEPENDENCIES[n.ref.metric!]), ref: n.ref }); } }
  // Flatten all nested fields, retaining exact paths; graph references stay links.
  function record(index: number): DisplayRecord {
    const n = r.evidence[index]; demand(n); const fields: DisplayRecord["fields"] = [];
    const todo: [string, unknown][] = [["data", n.data]];
    while (todo.length) { const [path, v] = todo.pop()!; if (Array.isArray(v)) { for (let i = v.length - 1; i >= 0; i--) todo.push([`${path}[${i}]`, v[i]]); }
      else if (isRecord(v)) { for (const k of Object.keys(v).reverse()) todo.push([`${path}.${k}`, v[k]]); }
      else { demand(v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean"); fields.push([path, v]); }
      demand(todo.length + fields.length <= 900, "INSIGHTS_CLIENT_LIMIT");
    }
    // Before packing, reserve the largest possible page-index spelling.
    return { ref: n.ref, fields, links: n.edges.map(ref => ({ ...ref, collection: ref.category, page: locations.get(ref.key)?.page ?? 8191 })), section: n.ref.category };
  }
  const pages = new Map<string, number[][]>();
  for (const category of ["F", "D"]) {
    const packed: number[][] = []; let current: number[] = [], bytes = 2, entries = 0;
    for (let i = 0; i < r.evidence.length; i++) { await budget.tick(); if (r.evidence[i].ref.category !== category) continue;
      const value = record(i); const size = encodedSize(value) + 1, count = structuralEntries(value) + 1;
      demand(size <= 32256 && count <= 1000, "INSIGHTS_CLIENT_LIMIT");
      if (current.length && (current.length === 25 || bytes + size > 32256 || entries + count > 1000)) { packed.push(current); current = []; bytes = 2; entries = 0; }
      current.push(i); bytes += size; entries += count;
    }
    if (current.length) packed.push(current); demand(packed.length <= 8192, "INSIGHTS_CLIENT_LIMIT"); pages.set(category, packed);
  }
  const { evidence: _evidence, comparisons: _comparisons, statements, ...header } = r;
  void _evidence; void _comparisons;
  for (const [collection, group] of pages) group.forEach((indices, page) => indices.forEach(i => locations.set(r.evidence[i].ref.key, { collection, page, key: r.evidence[i].ref.key })));
  const initial: InsightsPresentation = { ...header, statements: statements.map(({ financial, diagnostic, ...s }) => ({ ...s,
    targets: [...financial, ...diagnostic].filter(ref => s.rule === "VALUE" ? ref.kind === "observation" && ref.metric === s.metric && ref.side === s.side : ref.kind === "comparison").map(ref => locations.get(ref.key)!),
  })), metrics, collections: [...pages].map(([id, p]) => ({ id, pages: p.length, records: p.reduce((sum, indices) => sum + indices.length, 0) })) };
  demand(encodedSize(initial) <= 131072 && structuralEntries(initial) <= 4096, "INSIGHTS_CLIENT_LIMIT");
  return { initial, pages, nodes: r.evidence, record };
}

export type InsightsState = "INITIALIZING" | "INITIAL_DELIVERY" | "READY" | "PAGING" | "DISPOSED";
export type InsightsPage = { collection: string; page: number; records: DisplayRecord[] };
export type InsightsWorker = { postMessage(message: unknown, transfer?: Transferable[]): void; terminate(): void;
  addEventListener(type: string, listener: EventListener): void; removeEventListener(type: string, listener: EventListener): void };
export type InsightsEnvironment = { worker: () => InsightsWorker; fetch: typeof fetch; now: () => number;
  timer: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>; clear: (id: ReturnType<typeof setTimeout>) => void;
  window?: Pick<Window, "addEventListener" | "removeEventListener">; document?: Pick<Document, "addEventListener" | "removeEventListener"> };
export type InsightsRequest = InsightIdentity & { signal: AbortSignal; current: () => boolean; changed: () => void };
export type InsightsDelivery = { mode: "discover"; data: InsightsPresentation } | { mode: "compare"; handle: InsightsResultHandle };
export interface InsightsResultHandle {
  readonly state: InsightsState; readonly snapshot: InsightsPresentation | null; readonly page: InsightsPage | null;
  requestPage(collection: string, page: number): Promise<InsightsPage>;
  interact(): void; subscribe(listener: () => void): () => void; dispose(reason?: string): void;
  inspect(): { parentBytes: number; stagedBytes: number; pendingPages: number; timers: number; retainedPages: number };
}
type Deferred<T> = { promise: Promise<T>; resolve: (value: T) => void; reject: (error: unknown) => void };
function deferred<T>(): Deferred<T> { let resolve!: (v: T) => void, reject!: (e: unknown) => void; const promise = new Promise<T>((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
let generationSequence = 0;
/** One panel owns one worker, including discovery/initialization. No UI or global singleton. */
export class InsightsPanel {
  private currentHandle: InsightsSession | null = null;
  readonly environment: InsightsEnvironment;
  constructor(environment: Partial<InsightsEnvironment> = {}) {
    this.environment = { worker: () => new Worker(new URL("./financial-insights.worker.ts", import.meta.url), { type: "module" }),
      fetch: (...args) => globalThis.fetch(...args), now: () => performance.now(), timer: (fn, ms) => setTimeout(fn, ms), clear: id => clearTimeout(id),
      window: typeof window === "undefined" ? undefined : window, document: typeof document === "undefined" ? undefined : document, ...environment };
  }
  start(request: InsightsRequest): Promise<InsightsDelivery> {
    this.dispose("replacement");
    try { if (request.signal.aborted) throw new DOMException("Financial insights cancelled", "AbortError"); validInsightIdentity(request); demand(request.current()); }
    catch (e) { return Promise.reject(e); }
    const captured: InsightsRequest = { ...request, selection: { ...request.selection }, ...(request.publication ? { publication: { ...request.publication } } : {}) };
    const session = new InsightsSession(this, captured, `insights-${++generationSequence}`); this.currentHandle = session;
    session.begin(); return session.initial.promise;
  }
  owns(session: InsightsSession) { return this.currentHandle === session; }
  release(session: InsightsSession) { if (this.owns(session)) this.currentHandle = null; }
  dispose(reason = "cancelled") { this.currentHandle?.dispose(reason); }
}
class InsightsSession implements InsightsResultHandle {
  private status: InsightsState = "INITIALIZING";
  private model: InsightsPresentation | null = null; private committed: InsightsPage | null = null; private staged: InsightsPage | null = null;
  readonly initial = deferred<InsightsDelivery>();
  private worker: InsightsWorker | null = null; private transport = new AbortController(); private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private timers = new Map<string, ReturnType<typeof setTimeout>>(); private listeners = new Set<() => void>();
  private inputWait: { type: string; sequence?: number; deferred: Deferred<void> } | null = null;
  private parts: { header?: Dict; metrics: InsightsPresentation["metrics"]; statements: InsightsPresentation["statements"] } = { metrics: [], statements: [] };
  private initialBytes = 0; private initialEntries = 0; private outputSequence = 0; private operation = 0;
  private pending: { collection: string; page: number; deferred: Deferred<InsightsPage> } | null = null;
  private expiresAt: number; private idleAt = Infinity; private absoluteAt = Infinity; private publishedWall = Infinity;
  private pageExpiresAt = Infinity; private pingExpiresAt = Infinity;
  private initialWall = Date.now(); private idleWall = Infinity; private pageWall = Infinity; private pingWall = Infinity;
  private heartbeatNonce = 0; private ping: number | null = null; private settled = false;
  private cancellation = deferred<never>(); private yieldWait: Deferred<void> | null = null;
  private readonly message = ((event: MessageEvent) => { this.receive(event.data); }) as EventListener;
  private readonly failure = (() => this.dispose("WORKER_FAILED")) as EventListener;
  private readonly abort = (() => this.dispose("cancelled")) as EventListener;
  private readonly pagehide = (() => this.dispose("pagehide")) as EventListener;
  private readonly resume = (() => { this.live(); }) as EventListener;
  constructor(private panel: InsightsPanel, private request: InsightsRequest, private generation: string) { this.expiresAt = panel.environment.now() + 30000; void this.cancellation.promise.catch(() => {}); }
  get state() { this.live(); return this.status; }
  get snapshot() { return this.live() ? this.model : null; }
  get page() { return this.live() ? this.committed : null; }
  private get env() { return this.panel.environment; }
  private live(): boolean {
    if (this.status === "DISPOSED") return false;
    if (!this.panel.owns(this) || !this.request.current()) { this.dispose("obsolete"); return false; }
    const now = this.env.now();
    if (now >= this.idleAt || now >= this.absoluteAt || Date.now() - this.publishedWall >= 900000 || Date.now() - this.idleWall >= 300000) { this.dispose("EXPIRED"); return false; }
    if (!this.settled && (now >= this.expiresAt || Date.now() - this.initialWall >= 30000)) { this.dispose("REQUEST_TIMEOUT"); return false; }
    if (this.status === "PAGING" && (now >= this.pageExpiresAt || Date.now() - this.pageWall >= 5000)) { this.dispose("PAGE_TIMEOUT"); return false; }
    if (this.ping !== null && (now >= this.pingExpiresAt || Date.now() - this.pingWall >= 5000)) { this.dispose("WORKER_FAILED"); return false; }
    return true;
  }
  private arm(key: string, ms: number, fn: () => void) { this.clear(key); this.timers.set(key, this.env.timer(() => { this.timers.delete(key); fn(); }, Math.max(0, ms))); }
  private clear(key: string) { const timer = this.timers.get(key); if (timer !== undefined) this.env.clear(timer); this.timers.delete(key); }
  private send(message: Dict, transfer: Transferable[] = []) { demand(this.worker); this.worker.postMessage({ generation: this.generation, ...message }, transfer); }
  begin() {
    try {
      this.arm("initial", this.expiresAt - this.env.now(), () => this.dispose("REQUEST_TIMEOUT"));
      this.request.signal.addEventListener("abort", this.abort, { once: true });
      this.env.window?.addEventListener("pagehide", this.pagehide); this.env.window?.addEventListener("focus", this.resume); this.env.document?.addEventListener("visibilitychange", this.resume);
      this.worker = this.env.worker(); this.worker.addEventListener("message", this.message); this.worker.addEventListener("error", this.failure); this.worker.addEventListener("messageerror", this.failure);
      void this.read().catch(error => this.dispose(error instanceof InsightsError ? error.code : error instanceof DOMException && error.name === "AbortError" ? "cancelled" : "INVALID_RESPONSE", error));
    } catch { this.dispose("WORKER_FAILED"); }
  }
  private wait(type: string, sequence?: number) { demand(!this.inputWait); const wait = deferred<void>(); this.inputWait = { type, sequence, deferred: wait }; return wait.promise; }
  private async read() {
    const identity: InsightIdentity = { ticker: this.request.ticker, cik: this.request.cik, pin: this.request.pin, selection: this.request.selection, ...(this.request.publication ? { publication: this.request.publication } : {}) };
    const started = this.wait("STARTED"); this.send({ type: "INIT", identity, remaining: this.expiresAt - this.env.now() }); await started; if (!this.live()) return;
    const selection = this.request.selection;
    const query = selection.mode === "discover" ? "mode=discover" : `mode=compare&earlier_fiscal_year=${selection.earlier}&later_fiscal_year=${selection.later}`;
    const response = await Promise.race([this.env.fetch(`/api/finlens/companies/${encodeURIComponent(this.request.ticker)}/financials/insights?${query}`, { cache: "no-store", signal: this.transport.signal, headers: { "X-FinLens-Data-Version": String(this.request.pin) } }), this.cancellation.promise]);
    if (!this.live()) { void response.body?.cancel().catch(() => {}); return; }
    const version = response.headers.get("X-FinLens-Data-Version"), code = response.headers.get("X-FinLens-Error-Code");
    if (code === "DATA_VERSION_CHANGED" || version !== null && version !== String(this.request.pin)) {
      void response.body?.cancel().catch(() => {}); if (this.live()) this.request.changed(); throw new InsightsError("DATA_VERSION_CHANGED", "Published data changed.", 409);
    }
    if (!response.ok) { void response.body?.cancel().catch(() => {}); throw new InsightsError(code ?? "HTTP_ERROR", "Financial insights request failed.", response.status); }
    demand(version === String(this.request.pin) && response.body); this.reader = response.body.getReader(); let bytes = 0, sequence = 0;
    while (this.live()) {
      const result = await Promise.race([this.reader.read(), this.cancellation.promise]); if (!this.live()) return; if (result.done) break;
      // Count the complete HTTP-decoded chunk BEFORE retaining/copying any slice.
      bytes += result.value.byteLength; demand(bytes <= 4194304, "INSIGHTS_CLIENT_LIMIT");
      for (let offset = 0; offset < result.value.byteLength; offset += 16384) {
        if (!this.live()) return; const slice = result.value.slice(offset, Math.min(offset + 16384, result.value.byteLength));
        const wait = this.wait("INPUT_ACK", sequence); this.send({ type: "CHUNK", sequence, buffer: slice.buffer }, [slice.buffer]); await wait; sequence++;
      }
      // Empty/tiny-chunk streams must also return to the browser task queue.
      this.yieldWait = deferred<void>(); this.arm("readYield", 0, () => { this.yieldWait?.resolve(); this.yieldWait = null; }); await this.yieldWait.promise;
    }
    if (!this.live()) return; this.reader.releaseLock(); this.reader = null;
    this.send({ type: "END", sequence });
  }
  private receive(value: unknown) {
    if (!this.live()) return;
    try {
      demand(isRecord(value) && value.generation === this.generation && typeof value.type === "string");
      demand(Object.keys(value).length <= 8 && Object.keys(value).every(k => ["type", "generation", "operation", "sequence", "bytes", "entries", "payload", "batches", "nonce", "code"].includes(k)));
      for (const [key, field] of Object.entries(value)) if (key !== "payload") demand(typeof field === "string" ? field.length <= 128 : integer(field));
      if (value.type === "FAIL") { demand(typeof value.code === "string"); this.dispose(value.code); return; }
      if (value.type === "STARTED" || value.type === "INPUT_ACK") { demand(this.inputWait && this.inputWait.type === value.type && this.inputWait.sequence === value.sequence); const wait = this.inputWait; this.inputWait = null; wait.deferred.resolve(); return; }
      if (value.type === "PONG") { demand(this.ping !== null && value.nonce === this.ping); this.ping = null; this.pingExpiresAt = Infinity; this.clear("pong"); return; }
      if (value.type === "BATCH") {
        demand(value.operation === this.operation && value.sequence === this.outputSequence);
        const { payload: batch, ...meta } = value;
        // Bound protocol inspection before serialization; no body JSON parsing on the parent.
        const todo = [batch]; let checkedEntries = 0;
        while (todo.length) { const item = todo.pop(); if (typeof item === "string") { demand(item.length <= 32768); utf8Length(item); }
          else if (Array.isArray(item) || isRecord(item)) { const children = Object.values(item); checkedEntries += children.length; demand(checkedEntries <= 1024); todo.push(...children); }
          else demand(item === null || typeof item === "boolean" || integer(item));
        }
        demand(integer(value.bytes) && value.bytes <= 32768 && encodedSize(batch) === value.bytes && encodedSize(meta) + value.bytes + 16 <= 32768 && integer(value.entries) && value.entries + 8 <= 1024);
        demand(structuralEntries(batch) === value.entries && isRecord(batch));
        if (!this.settled) {
          demand((this.status === "INITIALIZING" || this.status === "INITIAL_DELIVERY") && batch.kind === "initial" && this.outputSequence < 4);
          this.status = "INITIAL_DELIVERY"; this.initialBytes += value.bytes; this.initialEntries += value.entries;
          demand(this.initialBytes <= 131072 && this.initialEntries <= 4096, "INSIGHTS_CLIENT_LIMIT");
          for (const raw of list(batch.items)) { const item = obj(raw, ["kind", "value"]); demand(isRecord(item.value));
            if (item.kind === "header") { demand(!this.parts.header); this.parts.header = item.value; }
            else if (item.kind === "metric") { demand(this.parts.metrics.length < 14); this.parts.metrics.push(item.value as InsightsPresentation["metrics"][number]); }
            else { demand(item.kind === "statement" && this.parts.statements.length < 35); this.parts.statements.push(item.value as InsightsPresentation["statements"][number]); }
          }
        } else {
          demand(this.status === "PAGING" && this.pending && this.staged === null && batch.kind === "page" && batch.collection === this.pending.collection && batch.page === this.pending.page && list(batch.records).length <= 25);
          this.staged = { collection: str(batch.collection), page: batch.page as number, records: batch.records as DisplayRecord[] };
        }
        this.outputSequence++; this.send({ type: "ACK", operation: this.operation, sequence: value.sequence }); return;
      }
      demand(value.type === "OP_COMPLETE" && value.operation === this.operation && value.batches === this.outputSequence && this.outputSequence > 0);
      if (!this.settled) {
        demand(this.parts.header && this.status === "INITIAL_DELIVERY");
        const model = { ...this.parts.header, metrics: this.parts.metrics, statements: this.parts.statements } as InsightsPresentation;
        demand(model.ticker === this.request.ticker && model.company_cik === this.request.cik && model.data_version === this.request.pin && model.mode === this.request.selection.mode && encodedSize(model) <= 131072 && structuralEntries(model) <= 4096);
        this.parts = { metrics: [], statements: [] }; this.clear("initial"); this.settled = true;
        if (model.mode === "discover") { this.initial.resolve({ mode: "discover", data: model }); this.dispose("discovery-complete"); return; }
        this.model = model; this.status = "READY"; this.absoluteAt = this.env.now() + 900000; this.publishedWall = Date.now(); this.arm("absolute", 900000, () => this.dispose("EXPIRED")); this.interact(); this.heartbeat(); this.initial.resolve({ mode: "compare", handle: this });
      } else {
        demand(this.status === "PAGING" && this.staged && this.pending); const wait = this.pending; this.committed = this.staged; this.staged = null; this.pending = null; this.status = "READY"; this.pageExpiresAt = Infinity; this.clear("page"); this.interact(); wait.deferred.resolve(this.committed); this.emit();
      }
    } catch { this.dispose("INVALID_RESPONSE"); }
  }
  requestPage(collection: string, page: number): Promise<InsightsPage> {
    if (!this.live() || !this.model) return Promise.reject(new InsightsError("HANDLE_DISPOSED", "Reload comparison to continue."));
    if (this.pending) return this.pending.collection === collection && this.pending.page === page ? this.pending.deferred.promise : Promise.reject(new InsightsError("PAGE_BUSY", "Another evidence page is loading."));
    const group = this.model.collections.find(c => c.id === collection);
    if (!group || !unsigned(page) || page >= group.pages) return Promise.reject(new InsightsError("INVALID_PAGE"));
    this.operation++; this.outputSequence = 0; this.status = "PAGING"; const wait = deferred<InsightsPage>(); this.pending = { collection, page, deferred: wait };
    const remaining = Math.min(5000, this.idleAt - this.env.now(), this.absoluteAt - this.env.now()); this.pageWall = Date.now(); this.pageExpiresAt = this.env.now() + remaining; this.arm("page", remaining, () => this.dispose("PAGE_TIMEOUT"));
    try { this.send({ type: "PAGE", operation: this.operation, collection, page, remaining }); } catch { this.dispose("WORKER_FAILED"); }
    return wait.promise;
  }
  interact() { if (!this.live() || !this.settled || !this.model) return; this.idleWall = Date.now(); this.idleAt = this.env.now() + 300000; this.arm("idle", 300000, () => this.dispose("EXPIRED")); }
  private heartbeat() {
    this.arm("heartbeat", 15000, () => {
      if (!this.live()) return;
      if (this.status === "READY" && this.ping === null) {
        this.ping = ++this.heartbeatNonce; this.pingWall = Date.now(); this.pingExpiresAt = this.env.now() + 5000; this.arm("pong", 5000, () => this.dispose("WORKER_FAILED"));
        try { this.send({ type: "PING", nonce: this.ping }); } catch { this.dispose("WORKER_FAILED"); }
      }
      if (this.status !== "DISPOSED") this.heartbeat();
    });
  }
  subscribe(listener: () => void) { if (this.status === "DISPOSED") return () => {}; demand(this.listeners.has(listener) || this.listeners.size < 8, "INSIGHTS_CLIENT_LIMIT"); this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private emit() { for (const listener of this.listeners) { try { listener(); } catch { /* A consumer cannot break ownership cleanup. */ } } }
  dispose(reason = "cancelled", failure?: unknown) {
    if (this.status === "DISPOSED") return; this.status = "DISPOSED"; this.panel.release(this);
    for (const timer of this.timers.values()) this.env.clear(timer); this.timers.clear(); this.transport.abort();
    if (this.reader) { const reader = this.reader; void reader.cancel().catch(() => {}).finally(() => { try { reader.releaseLock(); } catch { /* Ignored cancellation must not delay disposal. */ } }); this.reader = null; }
    this.request.signal.removeEventListener("abort", this.abort); this.env.window?.removeEventListener("pagehide", this.pagehide); this.env.window?.removeEventListener("focus", this.resume); this.env.document?.removeEventListener("visibilitychange", this.resume);
    if (this.worker) { this.worker.removeEventListener("message", this.message); this.worker.removeEventListener("error", this.failure); this.worker.removeEventListener("messageerror", this.failure); this.worker.terminate(); this.worker = null; }
    const error = ["cancelled", "replacement", "obsolete", "pagehide"].includes(reason) ? new DOMException("Financial insights cancelled", "AbortError") : failure instanceof InsightsError ? failure : new InsightsError(reason, reason === "EXPIRED" ? "Comparison closed. Reload comparison to continue." : "Financial insights could not complete.", reason === "REQUEST_TIMEOUT" ? 0 : 502);
    this.cancellation.reject(error); this.yieldWait?.resolve(); this.yieldWait = null;
    if (!this.settled) this.initial.reject(error); this.inputWait?.deferred.reject(error); this.inputWait = null; this.pending?.deferred.reject(error); this.pending = null;
    this.parts = { metrics: [], statements: [] }; this.model = null; this.committed = null; this.staged = null; this.emit(); this.listeners.clear();
  }
  inspect() { return { parentBytes: (this.model ? encodedSize(this.model) : 0) + (this.committed ? encodedSize(this.committed) : 0) + (this.staged ? encodedSize(this.staged) : 0), stagedBytes: this.staged ? encodedSize(this.staged) : 0, pendingPages: this.pending ? 1 : 0, timers: this.timers.size, retainedPages: this.committed ? 1 : 0 }; }
}
