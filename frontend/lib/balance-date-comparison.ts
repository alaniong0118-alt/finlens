import { FinLensApiError, type Company, type MetricHistory, type NormalizedMetric } from "./finlens-api";

export const BALANCE_METRICS = ["cash_and_equivalents", "total_assets", "total_liabilities"] as const;
export const BALANCE_HISTORY_LIMIT = 12;
export type BalanceMetric = typeof BALANCE_METRICS[number];
export type BalanceSeries = { metric: BalanceMetric; data: MetricHistory; error: null }
  | { metric: BalanceMetric; data: null; error: string };

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0;
const nullableText = (value: unknown) => value === null || typeof value === "string";
const nullableInteger = (value: unknown) => value === null || Number.isSafeInteger(value);
const decimal = (value: unknown): value is string => typeof value === "string"
  && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value) && Number.isFinite(Number(value));
const date = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && !value.startsWith("0000-") && Number.isFinite(Date.parse(`${value}T00:00:00Z`))
  && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
const status = (value: unknown) => value === "available" || value === "unavailable" || value === "not_applicable";

function sourceUrl(value: unknown, cik: string, accession: string): boolean {
  if (typeof value !== "string") return false;
  const prefix = `/Archives/edgar/data/${cik.replace(/^0+(?=\d)/, "")}/${accession.replaceAll("-", "")}/`;
  try {
    const url = new URL(value), file = url.pathname.slice(prefix.length);
    return url.protocol === "https:" && ["www.sec.gov", "sec.gov"].includes(url.hostname)
      && !url.port && !url.username && !url.password && !url.search && !url.hash && url.pathname.startsWith(prefix)
      && /^[A-Za-z0-9_.-]+$/.test(file) && file !== "." && file !== "..";
  } catch { return false; }
}

// This boundary validates three raw instant measures only. It never selects a
// filing vintage, changes a value, recalculates finance or fills a missing date.
// Publication headers remain owned by getMetricHistory/versionedController.
export function validateBalanceHistory(value: unknown, company: Pick<Company, "ticker" | "cik">, metric: BalanceMetric): MetricHistory {
  const bad = (): never => { throw new FinLensApiError("Balance history could not be verified for this company, metric, dates and sources.", 502, "INVALID_RESPONSE"); };
  if (!BALANCE_METRICS.includes(metric) || !/^\d{10}$/.test(company.cik) || !record(value)
      || value.ticker !== company.ticker || value.company_cik !== company.cik || value.metric !== metric
      || value.unit !== "USD" || value.requested_period !== "instant" || !status(value.status)
      || !nullableText(value.reason) || !Array.isArray(value.history) || value.history.length > BALANCE_HISTORY_LIMIT) return bad();
  if (value.comparability != null && (!record(value.comparability) || value.comparability.value_basis !== "reported_as_filed"
      || value.comparability.status !== "unverified" || !text(value.comparability.reason))) return bad();
  const dates = new Set<string>(), sources = new Map<number, string>();
  for (const point of value.history) {
    if (!record(point) || point.metric !== metric || point.unit !== "USD" || !status(point.status)
        || !nullableText(point.reason) || point.formula !== null || point.revenue_basis != null
        || !Array.isArray(point.inputs) || point.inputs.length !== 0
        || !Array.isArray(point.provenance) || !Array.isArray(point.alternatives)
        || (point.status === "available" ? !decimal(point.value) || point.provenance.length !== 1
          : point.value !== null || !text(point.reason) || point.provenance.length !== 0)) return bad();
    if (point.period === null) {
      if (point.status === "available" || point.provenance.length || point.alternatives.length) return bad();
    } else {
      const period = point.period;
      if (!record(period) || period.kind !== "instant" || period.start !== null || !date(period.end)
          || !nullableInteger(period.fiscal_year) || !nullableText(period.fiscal_period) || !text(period.fiscal_label_basis)
          // Even identical duplicates are ambiguous at this contract boundary.
          // Reject the series; never silently rank, deduplicate or drop a row.
          || dates.has(period.end)) return bad();
      dates.add(period.end);
    }
    const pointIds = new Set<number>();
    for (const source of [...point.provenance, ...point.alternatives]) {
      if (!record(source) || !Number.isSafeInteger(source.fact_id) || Number(source.fact_id) <= 0
          || pointIds.has(Number(source.fact_id)) || source.canonical_metric !== metric || source.company_cik !== company.cik
          || !text(source.original_concept) || !decimal(source.value) || source.unit !== "USD" || source.period_start !== null
          || !record(point.period) || source.period_end !== point.period.end || !date(source.period_end)
          || !date(source.filed) || !text(source.form) || typeof source.accession_number !== "string"
          || !/^\d{10}-\d{2}-\d{6}$/.test(source.accession_number)
          || !sourceUrl(source.sec_url, company.cik, source.accession_number)
          || !nullableInteger(source.source_fiscal_year) || !nullableText(source.source_fiscal_period)) return bad();
      pointIds.add(Number(source.fact_id));
      const identity = JSON.stringify([source.company_cik, source.canonical_metric, source.original_concept, source.value,
        source.unit, source.period_start, source.period_end, source.form, source.filed, source.accession_number,
        source.sec_url, source.source_fiscal_year, source.source_fiscal_period]);
      if (sources.has(Number(source.fact_id)) && sources.get(Number(source.fact_id)) !== identity) return bad();
      sources.set(Number(source.fact_id), identity);
    }
    if (point.status === "available" && point.provenance[0].value !== point.value) return bad();
  }
  const history = value.history as NormalizedMetric[];
  if ((value.status === "available") !== history.some(point => point.status === "available")
      || (value.status === "not_applicable" && (!text(value.reason) || history.some(point => point.status !== "not_applicable")))
      || (value.status === "unavailable" && !text(value.reason))) return bad();
  return value as MetricHistory;
}

// A database fact ID must retain one immutable identity across all three
// responses. Reject every implicated series rather than trust response order.
export function checkBalanceSources(series: readonly BalanceSeries[]): BalanceSeries[] {
  const references = new Map<number, { signature: string; owners: Set<number>; conflicted: boolean }>();
  const rejected = new Set<number>();
  series.forEach((item, index) => {
    for (const point of item.data?.history ?? []) for (const source of [...point.provenance, ...point.alternatives]) {
      const signature = JSON.stringify([item.metric, source.company_cik, source.original_concept, source.value, source.unit,
        source.period_start, source.period_end, source.form, source.filed, source.accession_number, source.sec_url,
        source.source_fiscal_year, source.source_fiscal_period]);
      const prior = references.get(source.fact_id);
      if (prior) {
        if (prior.signature !== signature) prior.conflicted = true;
        if (prior.conflicted) { rejected.add(index); prior.owners.forEach(owner => rejected.add(owner)); }
        prior.owners.add(index);
      } else references.set(source.fact_id, { signature, owners: new Set([index]), conflicted: false });
    }
  });
  return series.map((item, index) => rejected.has(index) ? { metric: item.metric, data: null,
    error: "Conflicting source identities were returned across balance histories. These histories could not be verified; load explicitly to retry." } : item);
}

export function balanceDates(series: readonly BalanceSeries[]): string[] {
  return [...new Set(series.flatMap(item => item.data?.history.flatMap(point => point.period ? [point.period.end] : []) ?? []))]
    .sort().reverse();
}

export function validBalanceDates(selected: readonly string[], available: readonly string[]): boolean {
  return selected.length >= 2 && selected.length <= 4 && new Set(selected).size === selected.length
    && selected.every(value => date(value) && available.includes(value));
}

export function balanceCell(series: BalanceSeries, end: string): { kind: "observation"; point: NormalizedMetric }
  | { kind: "error" | "absent"; reason: string } {
  if (!series.data) return { kind: "error", reason: series.error };
  const point = series.data.history.find(item => item.period?.kind === "instant" && item.period.start === null && item.period.end === end);
  return point ? { kind: "observation", point }
    : { kind: "absent", reason: "Not present in loaded history. No observation for this exact date was returned in this metric’s bounded window; this does not establish missing SEC coverage." };
}
