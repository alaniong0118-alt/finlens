import { FinLensApiError, type AnnualFinancialComparison, type Company, type FinancialPeriod } from "@/lib/finlens-api";

export const COMPARISON_METRICS = ["revenue", "revenue_growth_yoy", "operating_margin", "net_margin",
  "operating_cash_flow", "capital_expenditures", "free_cash_flow"] as const;

export function validCompanySelection(tickers: string[]): boolean {
  return tickers.length >= 2 && tickers.length <= 4 && tickers.every(Boolean) && new Set(tickers).size === tickers.length;
}

export function comparisonYears(choices: number[][]): { years: number[]; preferred: number | null } {
  const years = [...new Set(choices.flat())].sort((a, b) => b - a);
  const common = years.find(year => choices.every(list => list.includes(year)));
  return { years, preferred: common ?? years[0] ?? null };
}

function dateValid(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(`${value}T00:00:00Z`))
    && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
}

function annualPeriod(p: FinancialPeriod | null, year: number): boolean {
  if (!p || !dateValid(p.start) || !dateValid(p.end)) return false;
  const duration = (Date.parse(p.end) - Date.parse(p.start)) / 86400000;
  return p.kind === "annual" && p.fiscal_year === year && p.fiscal_period === "FY"
    && p.end.startsWith(`${year}-`) && duration + 1 >= 330 && duration + 1 <= 390;
}

function comparablePriorAnnual(prior: FinancialPeriod, current: FinancialPeriod | null): boolean {
  if (!current || !annualPeriod(prior, prior.fiscal_year ?? NaN)) return false;
  // Mirror observation("revenue_growth_yoy") date compatibility, including week
  // calendars whose successive year ends have nonconsecutive calendar labels.
  // This validates periods only; the backend remains the financial calculator.
  const startGap = (Date.parse(current.start!) - Date.parse(prior.start!)) / 86400000;
  const endGap = (Date.parse(current.end) - Date.parse(prior.end)) / 86400000;
  return startGap >= 357 && startGap <= 378 && endGap >= 357 && endGap <= 378
    && Math.abs(endGap - startGap) <= 9;
}

function sameWindow(a: FinancialPeriod | null, b: FinancialPeriod | null): boolean {
  return a === null ? b === null : !!b && a.kind === b.kind && a.start === b.start && a.end === b.end
    && a.fiscal_year === b.fiscal_year && a.fiscal_period === b.fiscal_period;
}

// Validate identity and lineage, never recalculate financial values. Version headers
// are independently enforced by getAnnualFinancials and versionedController.
export function validateAnnualResponse(result: AnnualFinancialComparison, company: Company, year: number | null): AnnualFinancialComparison {
  const reject = () => { throw new FinLensApiError("Annual financial evidence does not match this company, fiscal year or reporting window.", 502, "INVALID_RESPONSE"); };
  if (!result || !/^\d{10}$/.test(company.cik) || result.ticker !== company.ticker || result.company_cik !== company.cik
      || result.requested_period !== "annual" || result.requested_fiscal_year !== year
      || !Array.isArray(result.fiscal_years) || result.fiscal_years.length > 200
      || result.fiscal_years.some(y => !Number.isInteger(y) || y < 1900 || y > 2099)
      || new Set(result.fiscal_years).size !== result.fiscal_years.length
      || !result.metrics || typeof result.metrics !== "object") reject();
  if (year === null) {
    if (result.period !== null || Object.keys(result.metrics).length !== 0) reject();
    return result;
  }
  if (result.period !== null && (!annualPeriod(result.period, year) || !result.fiscal_years.includes(year))) reject();
  if (result.period === null && (typeof result.period_reason !== "string" || !result.period_reason)) reject();
  if (Object.keys(result.metrics).length !== COMPARISON_METRICS.length) reject();
  for (const name of COMPARISON_METRICS) {
    const point = result.metrics[name];
    const expectedUnit = ["revenue_growth_yoy", "operating_margin", "net_margin"].includes(name) ? "ratio" : "USD";
    if (!point || point.metric !== name || point.unit !== expectedUnit
        || !["available", "unavailable", "not_applicable"].includes(point.status)
        || !sameWindow(point.period, result.period)
        || !Array.isArray(point.provenance) || !Array.isArray(point.alternatives) || !Array.isArray(point.inputs)) reject();
    if (point.status === "available") {
      if (!result.period || typeof point.value !== "string" || !/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(point.value)
          || !Number.isFinite(Number(point.value)) || point.provenance.length === 0) reject();
    } else if (point.value !== null || !point.reason) reject();
    for (const input of point.inputs) {
      const prior = name === "revenue_growth_yoy" && input.role === "prior";
      if (!input.period || (prior ? !comparablePriorAnnual(input.period, result.period)
          : !annualPeriod(input.period, year) || !sameWindow(input.period, result.period)) || input.unit !== "USD"
          || !Array.isArray(input.fact_ids) || input.fact_ids.length === 0) reject();
    }
    for (const source of [...point.provenance, ...point.alternatives]) {
      if (source.company_cik !== company.cik || !Number.isSafeInteger(source.fact_id)
          || !/^\d{10}-\d{2}-\d{6}$/.test(source.accession_number)
          || source.unit !== "USD" || !dateValid(source.period_start) || !dateValid(source.period_end)) reject();
    }
    // Selected sources must belong to the exact current window; the only supported
    // different window is the prior annual operand of backend-calculated Revenue YoY.
    for (const source of point.provenance) {
      const current = source.period_start === result.period?.start && source.period_end === result.period?.end;
      const prior = name === "revenue_growth_yoy" && point.inputs.some(input => input.role === "prior"
        && input.fact_ids.includes(source.fact_id) && source.period_start === input.period?.start && source.period_end === input.period?.end);
      if (!current && !prior) reject();
    }
  }
  return result;
}

export function reportingWindowsDiffer(results: AnnualFinancialComparison[]): boolean {
  const windows = results.filter(r => r.period !== null).map(r => `${r.period!.start}/${r.period!.end}`);
  return new Set(windows).size > 1;
}
