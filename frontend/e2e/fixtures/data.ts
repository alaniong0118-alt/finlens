import type { AnnualFinancialComparison, Citation, Company, CompanyContext, CompanyFreshness, FilingContext, FilingSource, FinancialPeriod, FinancialSummary, MetricHistory, NormalizedMetric, PeriodKind, ResearchAnswer } from '../../lib/finlens-api';

// Test-only issuers and fixed observations. Never imported by application code.
export const companies: Company[] = [
  { id: 900001, ticker: 'AAA', name: 'Synthetic Alpha', cik: '0000900001', exchange: 'TEST', has_indexed_filing: true, indexed_filing_count: 1 },
  { id: 900002, ticker: 'BBB', name: 'Synthetic Beta', cik: '0000900002', exchange: 'TEST', has_indexed_filing: true, indexed_filing_count: 1 },
];
export const metrics = ['revenue', 'gross_profit', 'operating_income', 'net_income', 'diluted_eps', 'revenue_growth_yoy', 'gross_margin', 'operating_margin', 'net_margin', 'cash_and_equivalents', 'total_assets', 'total_liabilities', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow'] as const;
export const annualMetrics = ['revenue', 'revenue_growth_yoy', 'operating_margin', 'net_margin', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow', 'gross_profit', 'operating_income', 'net_income', 'gross_margin'] as const;
export function company(ticker: string): Company {
  const result = companies.find(item => item.ticker === ticker);
  if (!result) throw new Error(`Unknown synthetic issuer ${ticker}`);
  return result;
}
export function accession(ticker: string, suffix = '000001'): string { return `${company(ticker).cik}-25-${suffix}`; }
export function secUrl(ticker: string, suffix = '000001'): string { return `https://www.sec.gov/Archives/edgar/data/${Number(company(ticker).cik)}/${accession(ticker, suffix).replaceAll('-', '')}/synthetic.htm`; }
export function period(kind: PeriodKind, year = 2025): FinancialPeriod {
  const end = kind === 'quarter' ? `${year}-03-31` : kind === 'half_year' ? `${year}-06-30` : kind === 'nine_months' ? `${year}-09-30` : `${year}-12-31`;
  return { kind, start: kind === 'instant' ? null : `${year}-01-01`, end, fiscal_year: year, fiscal_period: kind === 'annual' ? 'FY' : kind === 'quarter' ? 'Q1' : null, fiscal_label_basis: 'synthetic_reported' };
}
// Fixed synthetic observations, deliberately distinct on both axes. No issuer
// formula is evaluated here; periods select an explicit test response value.
const periodValues: Record<string, Record<PeriodKind, string>> = {
  'AAA:2025': { quarter: '1000000000', half_year: '2400000000', nine_months: '3700000000', annual: '5000000000', instant: '750000000' },
  'AAA:2024': { quarter: '800000000', half_year: '1900000000', nine_months: '2800000000', annual: '4000000000', instant: '600000000' },
  'BBB:2025': { quarter: '2000000000', half_year: '4200000000', nine_months: '6500000000', annual: '9000000000', instant: '1500000000' },
  'BBB:2024': { quarter: '1600000000', half_year: '3300000000', nine_months: '5100000000', annual: '7000000000', instant: '1100000000' },
};
export function observation(ticker: string, metric: string, kind: PeriodKind = 'quarter', year = 2025): NormalizedMetric {
  if (!metrics.includes(metric as typeof metrics[number])) throw new Error(`Unknown metric ${metric}`);
  const unit = metric.includes('margin') || metric === 'revenue_growth_yoy' ? 'ratio' : metric === 'diluted_eps' ? 'USD/share' : 'USD';
  const p = period(['cash_and_equivalents', 'total_assets', 'total_liabilities'].includes(metric) ? 'instant' : kind, year);
  const fixedValue = periodValues[`${ticker}:${year}`]?.[p.kind];
  if (!fixedValue) throw new Error('Unsupported synthetic reporting window');
  // These fixed synthetic API values test display; they are not financial calculations.
  const value = metric === 'net_income' ? (year === 2025 && kind === 'quarter' ? '-25000000' : '-40000000') : metric === 'operating_income' && year === 2025 && kind === 'quarter' ? '0' : metric === 'diluted_eps' ? (year === 2025 ? '-0.25' : '-0.40') : unit === 'ratio' ? '0' : fixedValue;
  const status = metric === 'gross_margin' ? 'unavailable' : metric === 'revenue_growth_yoy' ? 'not_applicable' : 'available';
  return { metric, unit, status, value: status === 'available' ? value : null, reason: status === 'available' ? null : metric === 'gross_margin' ? 'Synthetic compatible gross-profit evidence is missing.' : 'Synthetic prior revenue is zero; growth is not applicable.', period: p, formula: null, provenance: status === 'available' ? [{ fact_id: company(ticker).id + metrics.indexOf(metric as typeof metrics[number]), original_concept: `Synthetic_${metric}`, value, unit: unit === 'ratio' ? 'USD' : unit, period_start: p.start, period_end: p.end, form: '10-K', filed: '2026-02-01', accession_number: accession(ticker), sec_url: secUrl(ticker), company_cik: company(ticker).cik, source_fiscal_year: year, source_fiscal_period: p.fiscal_period }] : [], alternatives: [], inputs: [] };
}
export function summary(ticker: string, kind: PeriodKind = 'quarter'): FinancialSummary {
  return { ticker, company_name: company(ticker).name, company_cik: company(ticker).cik, requested_period: kind, period: period(kind), metrics: Object.fromEntries(metrics.map(id => [id, observation(ticker, id, kind)])), selection_policy: 'Synthetic fixed observations; no production data.' };
}
export function history(ticker: string, metric: string, kind: PeriodKind): MetricHistory {
  const point = observation(ticker, metric, kind);
  const zero = observation(ticker, metric, kind, 2024);
  zero.value = '0'; zero.provenance = zero.provenance.map(source => ({ ...source, value: '0' }));
  const unavailable: NormalizedMetric = { ...point, status: 'unavailable', value: null, reason: 'Synthetic source evidence is unavailable for this older observation.', period: period(kind, 2023), provenance: [], alternatives: [], inputs: [] };
  const points = ['revenue', 'operating_cash_flow', 'diluted_eps', 'total_assets'].includes(metric) ? [unavailable, zero, point] : [point];
  return { ticker, company_cik: company(ticker).cik, metric, unit: point.unit, requested_period: kind, status: point.status, reason: point.reason, history: points, ...(metric === 'diluted_eps' ? { comparability: { value_basis: 'reported_as_filed' as const, status: 'unverified' as const, reason: 'Synthetic share bases unverified.' } } : {}) };
}
export function annual(ticker: string, year: number | null): AnnualFinancialComparison {
  const base = summary(ticker, 'annual');
  const points = year === null ? {} : Object.fromEntries(annualMetrics.map(id => {
    const point = observation(ticker, id, 'annual', year);
    // No synthetic derived formula or invented supporting denominator.
    if (point.unit === 'ratio') Object.assign(point, { status: 'unavailable', value: null, reason: 'Synthetic ratio evidence is unavailable.', provenance: [] });
    return [id, point];
  }));
  return { ...base, requested_period: 'annual', requested_fiscal_year: year, fiscal_years: [2025, 2024], period: year === null ? null : period('annual', year), period_reason: null, metrics: points };
}

// Opt-in annual comparison only. Default catalog, observations and publications
// above remain unchanged; these additional issuers cannot enter other workflows.
export const comparisonCompanies: Company[] = [...companies,
  { id: 900003, ticker: 'CCC', name: 'Synthetic Gamma', cik: '0000900003', exchange: 'TEST', has_indexed_filing: false, indexed_filing_count: 0 },
  { id: 900004, ticker: 'DDD', name: 'Synthetic Delta', cik: '0000900004', exchange: 'TEST', has_indexed_filing: false, indexed_filing_count: 0 },
];
export const comparisonPins: Readonly<Record<string, number>> = Object.freeze({ AAA: 0, BBB: 1, CCC: 4, DDD: 7 });
export const comparisonUnknownReason = 'synthetic_unknown_rule__v9 <em>literal text</em>\nKeep this reason unchanged.';
export const comparisonPeriodReason = 'synthetic_window_unknown__v3 — no annual window supplied.';
export function comparisonCompany(ticker: string): Company {
  const issuer = comparisonCompanies.find(item => item.ticker === ticker);
  if (!issuer) throw new Error(`Unknown synthetic comparison issuer ${ticker}`);
  return issuer;
}
export function comparisonAnnual(ticker: string, year: number | null): AnnualFinancialComparison {
  const issuer = comparisonCompany(ticker);
  if (year !== null && year !== 2025 && year !== 2024) throw new Error('Unsupported synthetic comparison year');
  const result = annual(ticker === 'BBB' ? 'BBB' : 'AAA', year);
  Object.assign(result, { ticker, company_cik: issuer.cik, company_name: issuer.name });
  if (year === null) return result;
  if (ticker === 'DDD') {
    result.period = null; result.period_reason = comparisonPeriodReason;
    for (const point of Object.values(result.metrics)) Object.assign(point, {
      period: null, status: 'unavailable', value: null, reason: comparisonPeriodReason, provenance: [], alternatives: [], inputs: [],
    });
    return result;
  }
  const window = ticker === 'BBB' ? { ...period('annual', year), start: `${year - 1}-09-29`, end: `${year}-09-27` } : period('annual', year);
  result.period = window;
  for (const [index, point] of Object.values(result.metrics).entries()) {
    point.period = window;
    if (ticker === 'CCC' && point.metric === 'revenue') point.value = year === 2025 ? '3000000000' : '2500000000';
    point.provenance = point.provenance.map(source => ({ ...source,
      fact_id: issuer.id * 100 + index, company_cik: issuer.cik, value: point.value!,
      period_start: window.start, period_end: window.end,
      accession_number: `${issuer.cik}-26-000001`,
      sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${issuer.cik}26000001/synthetic.htm`,
    }));
  }
  if (ticker !== 'CCC') result.metrics.revenue.revenue_basis = ticker === 'AAA' ? 'total_revenue' : 'customer_contract';
  result.metrics.gross_margin.reason = ticker === 'BBB' ? 'synthetic_exclusion__not_translated' : comparisonUnknownReason;
  if (ticker === 'BBB') result.metrics.gross_margin.status = 'not_applicable';
  return result;
}
export function comparisonFreshness(ticker: string, version: number): CompanyFreshness {
  comparisonCompany(ticker);
  return { ...freshness('AAA', version), ticker, latest_indexed_filing: null, scope: 'Synthetic annual comparison publication only.' };
}

export function freshness(ticker: string, version: number): CompanyFreshness {
  const stream = { status: 'current' as const, last_checked_at: '2026-10-13T00:00:00Z', last_successful_sync_at: '2026-10-12T00:00:00Z', latest_source_filing_date: '2026-02-01', last_error: null, failure_stage: null, pending_targets: [], inventory_complete: true };
  return { ticker, data_version: version, facts_version: version, evidence_version: version, status: 'current', facts: { ...stream }, evidence: { ...stream }, latest_indexed_filing: { accession_number: accession(ticker), form: '10-K', filed: '2026-02-01' }, migration_required: false, scope: 'Synthetic publications only.' };
}
export function sources(ticker: string): FilingSource[] {
  return [true, false].map((ready, index) => ({ accession_number: accession(ticker, index ? '000002' : '000001'), form: index ? '8-K' : '10-K', filed: '2026-02-01', period_start: '2025-01-01', period_end: '2025-12-31', metrics: [], sec_url: secUrl(ticker, index ? '000002' : '000001'), has_filing_chunks: ready }));
}
export function answer(ticker: string, question: string): ResearchAnswer {
  return { ticker, company_name: company(ticker).name, question, matched: true, status: 'available', metric: 'revenue', metric_label: 'Revenue', period_intent: 'latest_available', formatted_value: ticker === 'AAA' ? '$1B' : '$2B', answer_text: `${company(ticker).name} synthetic reported revenue.`, explanation: null, observation: observation(ticker, 'revenue'), comparability: null, selection_policy: 'Synthetic fixture', answer_kind: 'latest_metric', requested_period: null, comparison: null, formatted_absolute_change: null, formatted_percentage_change: null };
}
export function evidence(ticker: string, query: string, version: number, filing?: string): FilingContext | CompanyContext {
  const text = `${company(ticker).name} synthetic filing passage about reported revenue.`;
  const citation: Citation = { company_cik: company(ticker).cik, citation_id: 'source_1', chunk_id: `${ticker}-synthetic-1`, accession_number: filing ?? accession(ticker), form: '10-K', filed: '2026-02-01', filename: 'synthetic.htm', start_char: 0, end_char: text.length, sec_url: secUrl(ticker), similarity: 0.9, semantic_similarity: 0.9, lexical_score: 1, hybrid_score: 1, evidence_reason: 'synthetic_exact_match' };
  const metadata = Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, citation[key as keyof Citation]]));
  const base = { ticker, company_name: company(ticker).name, query, context: `[SOURCE source_1]\nmetadata: ${JSON.stringify(metadata)}\ntext: |-\n  ${text}\n[END SOURCE source_1]`, citations: [citation], evidence_status: 'sufficient' as const };
  return filing ? { ...base, accession_number: filing } : { ...base, retrieval_scope: 'company', company_cik: company(ticker).cik, data_version: version, evidence_version: version, searched_accessions: [accession(ticker)], excluded_publication_count: 0 };
}
