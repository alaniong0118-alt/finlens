import { COMPARISON_METRICS } from "./company-comparison";
import { validateStoredColumns, windowKey } from "./quarter-window-comparison";
import type { Company, StoredFinancialCoverage } from "./finlens-api";

export const COVERAGE_LIMITS = { windows: 64, cells: 704, sourceReferences: 4096 } as const;
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const canonicalMetric = (v: unknown) => record(v) ? v.canonical_metric : undefined;
const version = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0 && !Object.is(v, -0);
export function validateCoverage(value: unknown, company: Company, kind: "annual" | "quarter", pin: number): StoredFinancialCoverage {
  const bad = () => { throw new Error("Stored coverage could not be verified for this company, period and publication."); };
  if (!version(pin) || !["annual", "quarter"].includes(kind) || !/^\d{10}$/.test(company.cik)
      || !record(value) || value.ticker !== company.ticker || value.company_cik !== company.cik
      || typeof value.company_name !== "string" || !value.company_name || value.requested_period !== kind
      || value.coverage_scope !== "stored_reported_windows" || typeof value.selection_policy !== "string" || !value.selection_policy
      || value.data_version !== pin || !version(value.facts_version) || value.facts_version > pin
      || !version(value.evidence_version) || value.evidence_version > pin || !Array.isArray(value.columns)
      || value.columns.length > COVERAGE_LIMITS.windows || !version(value.window_count) || !version(value.cell_count)
      || !version(value.source_reference_count) || value.window_count !== value.columns.length
      || value.cell_count !== value.columns.length * COMPARISON_METRICS.length || Number(value.cell_count) > COVERAGE_LIMITS.cells) return bad();
  let references = 0;
  const selected = [];
  for (const column of value.columns) {
    if (!record(column) || !record(column.window) || typeof column.window.start !== "string" || typeof column.window.end !== "string"
        || !record(column.metrics) || Object.keys(column.metrics).length !== COMPARISON_METRICS.length) return bad();
    selected.push({ start: column.window.start, end: column.window.end });
    for (const metric of COMPARISON_METRICS) {
      const point = column.metrics[metric];
      if (!record(point) || !Array.isArray(point.provenance) || !Array.isArray(point.alternatives) || !Array.isArray(point.inputs)) return bad();
      references += point.provenance.length + point.alternatives.length;
      if (point.inputs.length > COVERAGE_LIMITS.sourceReferences) return bad();
      for (const input of point.inputs) {
        if (!record(input) || !Array.isArray(input.fact_ids)) return bad();
        references += input.fact_ids.length;
      }
      if (references > COVERAGE_LIMITS.sourceReferences) return bad();
    }
  }
  if (new Set(selected.map(windowKey)).size !== selected.length || value.source_reference_count !== references) return bad();
  validateStoredColumns(value.columns, company, selected, kind);
  // This complete map contains the raw metric projections for every returned
  // operand period. Bind lineage to those projections, without recalculating
  // any derived value or extending the selected-window comparison contract.
  const columns = value.columns as StoredFinancialCoverage["columns"];
  const windows = new Map(columns.map(column => [windowKey(column.window), column]));
  const derived = new Set(["revenue_growth_yoy", "gross_margin", "operating_margin", "net_margin", "free_cash_flow"]);
  for (const column of columns) for (const metric of COMPARISON_METRICS) {
    const point = column.metrics[metric];
    if (point.status !== "available") continue;
    if (!derived.has(metric)) {
      const source = point.provenance[0];
      if (point.provenance.length !== 1 || canonicalMetric(source) !== metric
          || source.value !== point.value || source.unit !== point.unit
          || source.period_start !== point.period?.start || source.period_end !== point.period?.end) return bad();
    }
    for (const input of point.inputs) {
      if (!input.period?.start) return bad();
      const base = windows.get(windowKey({ start: input.period.start, end: input.period.end }))?.metrics[input.metric];
      if (!base || derived.has(input.metric) || base.status !== "available" || base.value !== input.value || base.unit !== input.unit
          || base.period?.kind !== input.period.kind || base.period.start !== input.period.start || base.period.end !== input.period.end
          || base.provenance.length !== input.fact_ids.length
          || base.provenance.some(source => !input.fact_ids.includes(source.fact_id))) return bad();
      if (input.fact_ids.some(id => !point.provenance.some(source => source.fact_id === id
          && canonicalMetric(source) === input.metric && source.value === input.value && source.unit === input.unit
          && source.period_start === input.period!.start && source.period_end === input.period!.end))) return bad();
    }
  }
  return value as StoredFinancialCoverage;
}
