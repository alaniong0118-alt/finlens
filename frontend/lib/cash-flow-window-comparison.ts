import { FinLensApiError, type Company, type MetricHistory, type NormalizedMetric, type ReportedWindow } from "./finlens-api";

export const CASH_FLOW_METRICS = ["operating_cash_flow", "capital_expenditures", "free_cash_flow"] as const;
export const CASH_FLOW_HISTORY_LIMIT = 12;
export type CashFlowMetric = typeof CASH_FLOW_METRICS[number];
export type CashFlowKind = "half_year" | "nine_months";
export type CashFlowSeries = { metric: CashFlowMetric; data: MetricHistory; error: null }
  | { metric: CashFlowMetric; data: null; error: string };
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0;
const nullableText = (v: unknown) => v === null || typeof v === "string";
const nullableInteger = (v: unknown) => v === null || Number.isSafeInteger(v);
const decimal = (v: unknown): v is string => typeof v === "string" && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(v) && Number.isFinite(Number(v));
const date = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) && !v.startsWith("0000-")
  && Number.isFinite(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v;
const status = (v: unknown) => v === "available" || v === "unavailable" || v === "not_applicable";
export const cashFlowWindowKey = (w: ReportedWindow) => `${w.start},${w.end}`;
function period(v: unknown, kind: CashFlowKind): v is Record<string, unknown> & ReportedWindow {
  if (!record(v) || v.kind !== kind || !date(v.start) || !date(v.end)
      || !nullableInteger(v.fiscal_year) || !nullableText(v.fiscal_period) || !text(v.fiscal_label_basis)) return false;
  const days = (Date.parse(v.end) - Date.parse(v.start)) / 86400000 + 1;
  return kind === "half_year" ? days >= 165 && days <= 200 : days >= 245 && days <= 295;
}
function sourceUrl(v: unknown, cik: string, accession: string): boolean {
  if (typeof v !== "string") return false;
  const prefix = `/Archives/edgar/data/${cik.replace(/^0+(?=\d)/, "")}/${accession.replaceAll("-", "")}/`;
  try {
    const url = new URL(v), file = url.pathname.slice(prefix.length);
    return url.protocol === "https:" && ["www.sec.gov", "sec.gov"].includes(url.hostname) && !url.port
      && !url.username && !url.password && !url.search && !url.hash && url.pathname.startsWith(prefix)
      && /^[A-Za-z0-9_.-]+$/.test(file) && file !== "." && file !== "..";
  } catch { return false; }
}
// A reused fact must retain its canonical operand assignment across histories.
function identity(s: Record<string, unknown>) {
  return JSON.stringify([s.company_cik, s.canonical_metric, s.original_concept, s.value, s.unit, s.period_start, s.period_end,
    s.form, s.filed, s.accession_number, s.sec_url, s.source_fiscal_year, s.source_fiscal_period]);
}
export function validateCashFlowHistory(value: unknown, company: Pick<Company, "ticker" | "cik">, metric: CashFlowMetric, kind: CashFlowKind): MetricHistory {
  const bad = (): never => { throw new FinLensApiError("Cash flow history could not be verified for this company, metric, windows and sources.", 502, "INVALID_RESPONSE"); };
  if (!CASH_FLOW_METRICS.includes(metric) || !["half_year", "nine_months"].includes(kind) || !/^\d{10}$/.test(company.cik)
      || !record(value) || value.ticker !== company.ticker || value.company_cik !== company.cik || value.metric !== metric
      || value.unit !== "USD" || value.requested_period !== kind || !status(value.status) || !nullableText(value.reason)
      || !Array.isArray(value.history) || value.history.length > CASH_FLOW_HISTORY_LIMIT) return bad();
  const windows = new Set<string>(), sources = new Map<number, string>();
  for (const point of value.history) {
    if (!record(point) || point.metric !== metric || point.unit !== "USD" || !status(point.status) || !nullableText(point.reason)
        || point.revenue_basis != null || !Array.isArray(point.inputs) || !Array.isArray(point.provenance) || !Array.isArray(point.alternatives)
        || (metric === "free_cash_flow" ? point.formula !== "operating_cash_flow - capital_expenditures" : point.formula !== null)
        || (point.status === "available" ? !decimal(point.value) : point.value !== null || !text(point.reason))
        || !period(point.period, kind)) return bad();
    const p = point.period, key = cashFlowWindowKey(p);
    if (windows.has(key)) return bad();
    windows.add(key);
    const ids = new Set<number>();
    for (const s of [...point.provenance, ...point.alternatives]) {
      if (!record(s) || !Number.isSafeInteger(s.fact_id) || Number(s.fact_id) <= 0 || ids.has(Number(s.fact_id))
          || s.company_cik !== company.cik || !text(s.original_concept) || !decimal(s.value) || s.unit !== "USD"
          || s.period_start !== p.start || s.period_end !== p.end || !date(s.filed) || s.filed < p.end
          || !text(s.form) || typeof s.accession_number !== "string" || !/^\d{10}-\d{2}-\d{6}$/.test(s.accession_number)
          || !sourceUrl(s.sec_url, company.cik, s.accession_number) || !nullableInteger(s.source_fiscal_year) || !nullableText(s.source_fiscal_period)
          || (metric === "free_cash_flow" ? typeof s.canonical_metric !== "string"
            || !["operating_cash_flow", "capital_expenditures"].includes(s.canonical_metric) : s.canonical_metric !== metric)) return bad();
      const id = Number(s.fact_id), sig = identity(s); ids.add(id);
      if (sources.has(id) && sources.get(id) !== sig) return bad();
      sources.set(id, sig);
    }
    if (point.status !== "available") {
      if (point.provenance.length || point.inputs.length) return bad();
    } else if (metric !== "free_cash_flow") {
      if (point.inputs.length || point.provenance.length !== 1 || point.provenance[0].value !== point.value) return bad();
    } else {
      if (point.inputs.length !== 2 || point.provenance.length !== 2 || point.alternatives.length) return bad();
      const used = new Set<number>();
      for (const name of ["operating_cash_flow", "capital_expenditures"]) {
        const input = point.inputs.find(i => record(i) && i.role === name && i.metric === name);
        if (!record(input) || !decimal(input.value) || input.unit !== "USD"
            || (input.revenue_basis != null && (typeof input.revenue_basis !== "string"
              || !["total_revenue", "customer_contract", "net_sales", "net_interest"].includes(input.revenue_basis)))
            || !period(input.period, kind)
            || cashFlowWindowKey(input.period) !== key || input.period.fiscal_year !== p.fiscal_year
            || input.period.fiscal_period !== p.fiscal_period || input.period.fiscal_label_basis !== p.fiscal_label_basis || !Array.isArray(input.fact_ids) || input.fact_ids.length !== 1
            || !Number.isSafeInteger(input.fact_ids[0]) || used.has(input.fact_ids[0])) return bad();
        const factId = input.fact_ids[0]; used.add(factId);
        if (!point.provenance.some(s => s.fact_id === factId && s.canonical_metric === name && s.value === input.value)) return bad();
      }
    }
  }
  const history = value.history as NormalizedMetric[];
  if ((value.status === "available") !== history.some(p => p.status === "available")
      || (value.status !== "available" && !text(value.reason))) return bad();
  return value as MetricHistory;
}
export function checkCashFlowSources(series: readonly CashFlowSeries[]): CashFlowSeries[] {
  const refs = new Map<number, { signature: string; owners: Set<number>; conflicted: boolean }>(), rejected = new Set<number>();
  series.forEach((item, index) => {
    for (const point of item.data?.history ?? []) for (const source of [...point.provenance, ...point.alternatives]) {
      const sig = identity(source as unknown as Record<string, unknown>), prior = refs.get(source.fact_id);
      if (prior) { if (prior.signature !== sig) prior.conflicted = true; if (prior.conflicted) { rejected.add(index); prior.owners.forEach(i => rejected.add(i)); } prior.owners.add(index); }
      else refs.set(source.fact_id, { signature: sig, owners: new Set([index]), conflicted: false });
    }
  });
  // Identical windows cannot have conflicting fiscal metadata across histories.
  const periods = new Map<string, { signature: string; owners: Set<number>; conflicted: boolean }>();
  series.forEach((item, index) => { for (const point of item.data?.history ?? []) if (point.period?.start) {
    const p = point.period, key = cashFlowWindowKey({ start: p.start!, end: p.end });
    const sig = JSON.stringify([p.kind, p.fiscal_year, p.fiscal_period, p.fiscal_label_basis]), prior = periods.get(key);
    if (prior) { if (prior.signature !== sig) prior.conflicted = true; if (prior.conflicted) { rejected.add(index); prior.owners.forEach(i => rejected.add(i)); } prior.owners.add(index); }
    else periods.set(key, { signature: sig, owners: new Set([index]), conflicted: false });
  } });
  // For a shared exact window, separately loaded raw observations must agree with FCF's operand lineage.
  const fcfIndex = series.findIndex(s => s.metric === "free_cash_flow");
  const fcf = series[fcfIndex];
  if (fcf?.data) for (const point of fcf.data.history) if (point.status === "available" && point.period) {
    for (const input of point.inputs) {
      const index = series.findIndex(s => s.metric === input.metric), raw = series[index]?.data?.history.find(p => p.period
        && p.period.start === point.period!.start && p.period.end === point.period!.end);
      if (raw && (raw.status !== "available" || raw.value !== input.value || raw.provenance.length !== 1
          || raw.provenance[0].fact_id !== input.fact_ids[0])) { rejected.add(index); rejected.add(fcfIndex); }
    }
  }
  return series.map((item, index) => rejected.has(index) ? { metric: item.metric, data: null,
    error: "Conflicting source identities or operands were returned across cash flow histories. Load explicitly to retry." } : item);
}
export function cashFlowWindows(series: readonly CashFlowSeries[]): ReportedWindow[] {
  const unique = new Map<string, ReportedWindow>();
  for (const item of series) for (const point of item.data?.history ?? []) if (point.period?.start) {
    const w = { start: point.period.start, end: point.period.end }; unique.set(cashFlowWindowKey(w), w);
  }
  return [...unique.values()].sort((a, b) => cashFlowWindowKey(b).localeCompare(cashFlowWindowKey(a)));
}
export function validCashFlowWindows(selected: readonly ReportedWindow[], available: readonly ReportedWindow[]): boolean {
  const keys = selected.map(cashFlowWindowKey), offered = new Set(available.map(cashFlowWindowKey));
  return keys.length >= 2 && keys.length <= 4 && new Set(keys).size === keys.length && keys.every(key => offered.has(key));
}
export function cashFlowCell(series: CashFlowSeries, window: ReportedWindow): { kind: "observation"; point: NormalizedMetric } | { kind: "error" | "absent"; reason: string } {
  if (!series.data) return { kind: "error", reason: series.error };
  const point = series.data.history.find(item => item.period?.start === window.start && item.period.end === window.end);
  return point ? { kind: "observation", point } : { kind: "absent", reason: "No observation for this exact window was returned in this metric’s bounded history; this does not establish missing SEC coverage." };
}
