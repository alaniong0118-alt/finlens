import { FinLensApiError, type AnnualFinancialComparison, type Company, type FactProvenance } from "@/lib/finlens-api";
import { COMPARISON_METRICS, metricComparability, validateAnnualResponse } from "@/lib/company-comparison";

export type AnnualPeriodColumn = { year: number; result?: AnnualFinancialComparison; error?: string };

function requireEvidence(condition: unknown): asserts condition {
  if (!condition) throw new FinLensApiError("Annual period evidence could not be verified. No substitute value is used.", 502, "INVALID_RESPONSE");
}
const text = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const optionalText = (value: unknown) => value === null || value === undefined || text(value);
const decimal = (value: unknown) => typeof value === "string"
  && /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value) && Number.isFinite(Number(value));
const date = (value: unknown) => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && Number.isFinite(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;

export function validAnnualSelection(selected: number[], available: number[]): boolean {
  return selected.length >= 2 && selected.length <= 4 && new Set(selected).size === selected.length
    && selected.every(year => Number.isInteger(year) && available.includes(year));
}

// CC-02 owns metric, window and lineage semantics. This local boundary additionally
// verifies fields rendered by the new grid, without calculating financial values.
export function annualPeriodResponse(value: AnnualFinancialComparison, company: Company, year: number | null,
  discovered?: number[]): AnnualFinancialComparison {
  const result = validateAnnualResponse(value, company, year);
  requireEvidence(text(result.company_name) && text(result.selection_policy) && optionalText(result.period_reason));
  if (discovered) requireEvidence(result.fiscal_years.length === discovered.length
    && result.fiscal_years.every(fiscalYear => discovered.includes(fiscalYear)));
  if (year === null) return result;
  requireEvidence(discovered?.includes(year));
  if (result.period) requireEvidence(text(result.period.fiscal_label_basis));
  for (const name of COMPARISON_METRICS) {
    const point = result.metrics[name];
    requireEvidence(optionalText(point.reason) && optionalText(point.formula) && optionalText(point.revenue_basis));
    for (const source of [...point.provenance, ...point.alternatives]) {
      requireEvidence(source && Number.isSafeInteger(source.fact_id) && source.fact_id > 0
        && text(source.original_concept) && decimal(source.value) && text(source.form)
        && date(source.filed) && source.period_start! <= source.period_end && typeof source.sec_url === "string"
        && (source.source_fiscal_year === null || Number.isInteger(source.source_fiscal_year))
        && (source.source_fiscal_period === null || text(source.source_fiscal_period)));
    }
    for (const input of point.inputs) {
      requireEvidence(text(input.role) && text(input.metric) && decimal(input.value) && optionalText(input.revenue_basis)
        && text(input.period?.fiscal_label_basis)
        && input.fact_ids.every(id => Number.isSafeInteger(id) && id > 0
          && point.provenance.some(source => source.fact_id === id && source.period_start === input.period?.start
            && source.period_end === input.period?.end)));
    }
  }
  verifyAnnualSourceIdentities([{ year, result }]);
  return result;
}

// A stored fact identity may recur in a derived operand or another year's YoY
// sources; its original observation must remain identical wherever it appears.
export function verifyAnnualSourceIdentities(columns: AnnualPeriodColumn[]): void {
  const identities = new Map<number, string>();
  const identity = (source: FactProvenance) => JSON.stringify([source.company_cik, source.original_concept,
    source.value, source.unit, source.period_start, source.period_end, source.form, source.filed,
    source.accession_number, source.sec_url, source.source_fiscal_year, source.source_fiscal_period]);
  for (const column of columns) for (const point of Object.values(column.result?.metrics ?? {})) {
    for (const source of [...point.provenance, ...point.alternatives]) {
      const original = identity(source);
      requireEvidence(!identities.has(source.fact_id) || identities.get(source.fact_id) === original);
      identities.set(source.fact_id, original);
    }
  }
}

export function annualRowWarnings(metric: typeof COMPARISON_METRICS[number], columns: AnnualPeriodColumn[]): string[] {
  const diagnostics = metricComparability(metric, columns.map(column => column.result));
  const periods = columns.flatMap(column => column.result?.period ? [column.result.period] : []);
  const durations = new Set(periods.map(period => (Date.parse(period.end) - Date.parse(period.start!)) / 86400000 + 1));
  const boundaries = new Set(periods.map(period => `${period.start!.slice(5)}/${period.end.slice(5)}`));
  return [
    ...(durations.size > 1 ? ["Annual reporting durations differ; values are not normalized to equal day counts."] : []),
    ...(boundaries.size > 1 ? ["Fiscal boundaries differ across these periods; inspect the actual reporting dates."] : []),
    ...(diagnostics.basesDiffer ? ["Revenue-basis labels differ across periods or operands; equivalence is not established."] : []),
    ...(diagnostics.basisUnknown ? ["Revenue basis is unknown for at least one period or operand."] : []),
    ...(diagnostics.missingWindow ? ["A reporting window is unavailable; no other period is substituted."] : []),
    ...(diagnostics.excluded ? [`${diagnostics.excluded} period(s) have unavailable or not-applicable values; reasons remain in the cells.`] : []),
    ...(diagnostics.unverified ? [`${diagnostics.unverified} period response(s) could not be verified; comparability is unknown.`] : []),
  ];
}
