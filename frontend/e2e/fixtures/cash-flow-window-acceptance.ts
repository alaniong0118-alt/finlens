import type { MetricHistory, NormalizedMetric } from '../../lib/finlens-api';
import type { ApiRequest, Reply, Scenario } from './browser';
import { expectedRequest } from './annual-period-browser';
import * as data from './data';

// Fixed synthetic protocol values only; they make no claim about a real issuer.
export const cashMetrics = ['operating_cash_flow', 'capital_expenditures', 'free_cash_flow'] as const;
export type CashMetric = typeof cashMetrics[number];
export type CashKind = 'half_year' | 'nine_months';
export const cashWindows = (kind: CashKind) => {
  const end = kind === 'half_year' ? '06-30' : '09-30';
  return [
    { start: '2025-01-02', end: `2025-${end}` }, // Same end, distinct exact start.
    { start: '2025-01-01', end: `2025-${end}` },
    { start: '2024-01-01', end: `2024-${end}` },
    { start: '2023-01-01', end: `2023-${end}` },
    { start: '2022-01-01', end: `2022-${end}` },
  ];
};
export const cashExact = { AAA: '9007199254740993.1234567890123456789012345', BBB: '2000000000000001.000000000000000000001' } as const;
export const cashMissingReason = 'Synthetic compatible inputs unavailable <em>literal</em>.';
export const cashPath = (ticker: string, metric: CashMetric) => `/companies/${ticker}/financials/metrics/${metric}`;
export function cashMetric(request: ApiRequest): CashMetric | null {
  const metric = request.path.split('/').at(-1) as CashMetric;
  return cashMetrics.includes(metric) && request.path === cashPath(request.ticker ?? '', metric) ? metric : null;
}
export function cashHistory(ticker: string, metric: CashMetric, kind: CashKind): MetricHistory {
  if (!['AAA', 'BBB'].includes(ticker) || !cashMetrics.includes(metric) || !['half_year', 'nine_months'].includes(kind)) throw new Error('Unknown synthetic cash flow series');
  const issuer = data.company(ticker), issuerKey = ticker as keyof typeof cashExact;
  const history: NormalizedMetric[] = cashWindows(kind).flatMap((w, index) => {
    // A date-aligned gap is not a claim of missing upstream SEC coverage.
    if (metric === 'operating_cash_flow' && index === 0) return [];
    const period = { kind, ...w, fiscal_year: null, fiscal_period: null, fiscal_label_basis: 'unknown' };
    const source = (name: 'operating_cash_flow' | 'capital_expenditures') => ({
      fact_id: (ticker === 'AAA' ? 110000 : 210000) + (kind === 'half_year' ? 0 : 10000) + index * 10 + (name === 'operating_cash_flow' ? 1 : 2),
      canonical_metric: name, original_concept: `Synthetic_${name}`, value: name === 'operating_cash_flow' ? cashExact[issuerKey] : '10.0000000000001',
      unit: 'USD', period_start: w.start, period_end: w.end, form: '10-Q', filed: '2026-02-01',
      accession_number: data.accession(ticker), sec_url: data.secUrl(ticker), company_cik: issuer.cik,
      source_fiscal_year: null, source_fiscal_period: null,
    });
    const derived = metric === 'free_cash_flow';
    const provenance = derived ? [source('operating_cash_flow'), source('capital_expenditures')] : [source(metric)];
    const point: NormalizedMetric = { metric, unit: 'USD', status: 'available', value: derived ? (ticker === 'AAA' ? '9007199254740983.123456789012' : '1999999999999991.000000000000') : provenance[0].value,
      reason: null, period, formula: derived ? 'operating_cash_flow - capital_expenditures' : null, provenance, alternatives: [],
      inputs: derived ? provenance.map(s => ({ role: s.canonical_metric, metric: s.canonical_metric, value: s.value, unit: 'USD', period, fact_ids: [s.fact_id] })) : [] };
    if (index === 0 && metric !== 'operating_cash_flow') Object.assign(point,
      { status: 'unavailable', value: null, reason: cashMissingReason, provenance: [], inputs: [] });
    if (index === 1 && metric === 'operating_cash_flow') point.alternatives = [{ ...provenance[0], fact_id: provenance[0].fact_id + 1000, value: '25.000000000000001' }];
    return [point];
  });
  return { ticker, company_cik: issuer.cik, metric, unit: 'USD', requested_period: kind, status: 'available', reason: null, history };
}
export function cashReply(request: ApiRequest, scenario: Pick<Scenario, 'versions'>): Reply | undefined {
  const metric = cashMetric(request); if (!metric) return;
  const ticker = request.ticker, kind = request.query.get('period') as CashKind;
  if (!ticker || !['AAA', 'BBB'].includes(ticker) || request.method !== 'GET' || request.body !== null || request.request.postData() !== null
      || !['half_year', 'nine_months'].includes(kind) || request.query.toString() !== `period=${kind}&limit=12`
      || request.pin === undefined || !/^(0|[1-9]\d*)$/.test(request.pin) || !Number.isSafeInteger(Number(request.pin))) throw new Error('Unexpected synthetic cash flow request');
  const version = String(scenario.versions[ticker]);
  return request.pin === version ? { body: cashHistory(ticker, metric, kind), version } : { status: 409, code: 'DATA_VERSION_CHANGED', version };
}
export const cashRequests = (ticker = 'AAA', kind: CashKind = 'half_year', pin = 0) =>
  cashMetrics.map(metric => expectedRequest(cashPath(ticker, metric), pin, `period=${kind}&limit=12`));
