import { COMPARISON_METRICS } from "./company-comparison";
import { snapshotPoint } from "./snapshot-gaps";
import type { Company, FactProvenance, QuarterComparison, ReportedWindow } from "./finlens-api";

const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const date = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v;
export function windowKey(w: ReportedWindow) { return `${w.start},${w.end}`; }
function validWindow(v: unknown): v is ReportedWindow {
  if (!record(v) || !date(v.start) || !date(v.end)) return false;
  const days = (Date.parse(v.end) - Date.parse(v.start)) / 86400000 + 1;
  return days >= 75 && days <= 105;
}
const operands: Readonly<Record<string, readonly (readonly [string, string])[]>> = {
  revenue_growth_yoy: [["current", "revenue"], ["prior", "revenue"]],
  gross_margin: [["gross_profit", "gross_profit"], ["revenue", "revenue"]],
  operating_margin: [["operating_income", "operating_income"], ["revenue", "revenue"]],
  net_margin: [["net_income", "net_income"], ["revenue", "revenue"]],
  free_cash_flow: [["operating_cash_flow", "operating_cash_flow"], ["capital_expenditures", "capital_expenditures"]],
};
function sourceIdentity(source: FactProvenance): string {
  // Same immutable source fields as the annual facade; canonical_metric is a
  // projection of a reference, not a different identity for the underlying fact.
  return JSON.stringify([source.company_cik, source.original_concept, source.value, source.unit,
    source.period_start, source.period_end, source.form, source.filed, source.accession_number,
    source.sec_url, source.source_fiscal_year, source.source_fiscal_period]);
}
function archiveMatches(source: FactProvenance, cik: string): boolean {
  if (!/^\d{10}$/.test(cik) || !/^\d{10}-\d{2}-\d{6}$/.test(source.accession_number)) return false;
  // Validate the supplied URL; never replace a mismatched URL with a constructed link.
  const path = `/Archives/edgar/data/${cik.replace(/^0+(?=\d)/, "")}/${source.accession_number.replaceAll("-", "")}/`;
  try {
    const url = new URL(source.sec_url), filename = url.pathname.slice(path.length);
    return url.protocol === "https:" && ["www.sec.gov", "sec.gov"].includes(url.hostname)
      && !url.port && !url.username && !url.password && url.pathname.startsWith(path)
      && /^[A-Za-z0-9_.-]+$/.test(filename) && filename !== "." && filename !== "..";
  } catch { return false; }
}
export function validateQuarterResponse(value: unknown, company: Company, selected: ReportedWindow[], discovered?: ReportedWindow[]): QuarterComparison {
  const bad = () => { throw new Error("Reported windows or financial evidence could not be verified."); };
  if (!record(value) || value.ticker !== company.ticker || value.company_cik !== company.cik
      || typeof value.company_name !== "string" || value.requested_period !== "quarter"
      || typeof value.selection_policy !== "string" || !value.selection_policy
      || !Array.isArray(value.available_windows) || value.available_windows.length > 256
      || !value.available_windows.every(validWindow) || !Array.isArray(value.columns)) return bad();
  const windows = value.available_windows as ReportedWindow[];
  const keys = windows.map(windowKey);
  if (new Set(keys).size !== keys.length || (discovered && (discovered.length !== keys.length
      || discovered.some(w => !keys.includes(windowKey(w)))))
      || (selected.length !== 0 && (selected.length < 2 || selected.length > 4))
      || new Set(selected.map(windowKey)).size !== selected.length
      || selected.some(w => !validWindow(w) || !keys.includes(windowKey(w)))
      || value.columns.length !== selected.length) return bad();
  const sources = new Map<number, string>();
  for (const [index, column] of value.columns.entries()) {
    if (!record(column) || !validWindow(column.window) || windowKey(column.window) !== windowKey(selected[index])
        || !record(column.metrics) || Object.keys(column.metrics).length !== COMPARISON_METRICS.length) return bad();
    const anchor = { kind: "quarter", start: column.window.start, end: column.window.end, fiscal_year: null,
      fiscal_period: null, fiscal_label_basis: "unknown" };
    for (const metric of COMPARISON_METRICS) {
      const point = column.metrics[metric];
      if (!snapshotPoint(point, metric, company.cik, "quarter", anchor) || !point.period
          || point.period.fiscal_label_basis !== "unknown"
          || (point.status !== "available" && !point.reason)) return bad();
      const expected = operands[metric];
      if (point.status === "available") {
        if (point.inputs.length !== (expected?.length ?? 0)
            || new Set(point.inputs.map(input => input.role)).size !== point.inputs.length
            || expected?.some(([role, name]) => !point.inputs.some(input => input.role === role && input.metric === name))) return bad();
        if (expected) {
          const ids = point.inputs.flatMap(input => input.fact_ids);
          if (new Set(ids).size !== ids.length || ids.length !== point.provenance.length
              || new Set(point.provenance.map(source => source.fact_id)).size !== point.provenance.length
              || point.provenance.some(source => !ids.includes(source.fact_id))) return bad();
        }
      }
      for (const input of point.inputs) {
        if (!input.period || input.unit !== "USD" || !input.fact_ids.length || !input.fact_ids.every(id => id > 0)
            || new Set(input.fact_ids).size !== input.fact_ids.length) return bad();
        const p = input.period, prior = metric === "revenue_growth_yoy" && input.role === "prior";
        if (p.kind !== "quarter" || p.fiscal_year !== null || p.fiscal_period !== null || p.fiscal_label_basis !== "unknown" || !p.start) return bad();
        if (prior) {
          const starts = (Date.parse(anchor.start) - Date.parse(p.start)) / 86400000;
          const ends = (Date.parse(anchor.end) - Date.parse(p.end)) / 86400000;
          if (starts < 357 || starts > 378 || ends < 357 || ends > 378 || Math.abs(ends - starts) > 9) return bad();
        } else if (p.start !== anchor.start || p.end !== anchor.end) return bad();
        if (input.fact_ids.some(id => !point.provenance.some(source => source.fact_id === id
          && source.period_start === p.start && source.period_end === p.end && source.value === input.value))) return bad();
      }
      for (const source of point.provenance) {
        if (source.fact_id <= 0 || source.unit !== "USD" || !/^\d{10}-\d{2}-\d{6}$/.test(source.accession_number)) return bad();
        const current = source.period_start === anchor.start && source.period_end === anchor.end;
        const prior = metric === "revenue_growth_yoy" && point.inputs.some(input => input.role === "prior"
          && input.fact_ids.includes(source.fact_id) && input.period?.start === source.period_start && input.period?.end === source.period_end);
        if (!current && !prior) return bad();
      }
      for (const source of [...point.provenance, ...point.alternatives]) {
        if (source.fact_id <= 0 || !archiveMatches(source, company.cik)) return bad();
        const identity = sourceIdentity(source);
        if (sources.has(source.fact_id) && sources.get(source.fact_id) !== identity) return bad();
        sources.set(source.fact_id, identity);
      }
    }
  }
  return value as QuarterComparison;
}
