import { financialInsightsFixture } from './financial-insights';
import { company } from './data';
import type { InsightResponse } from '../../lib/financial-insights';

// Insights-only synthetic data. Its amounts do not reconcile with the unrelated
// QA-01 snapshot fixtures. Never imported by application code.
export function supportsInsightsPublication(ticker: string, version: number): boolean {
  return !Object.is(version, -0) && (ticker === 'AAA' && version === 0 || ticker === 'BBB' && version === 1);
}

export function browserFinancialInsights(ticker: string, version: number, mode: 'discover' | 'compare'): InsightResponse {
  if (!supportsInsightsPublication(ticker, version) || !['discover', 'compare'].includes(mode)) {
    throw new Error('Unsupported synthetic insights publication or mode');
  }
  const issuer = company(ticker);
  const input = financialInsightsFixture(mode);
  const oldScope = `0000000001:0:0:0:${mode === 'discover' ? 'None:None' : '2024:2025'}`;
  const scope = `${issuer.cik}:${version}:${version}:${version}:${mode === 'discover' ? 'None:None' : '2024:2025'}`;
  const accessions = new Map(['25', '26'].map(year => [
    `0000000001-${year}-000001`, `${issuer.cik}-${year}-100001`,
  ]));
  const urls = new Map([...accessions].map(([before, after]) => [
    `https://www.sec.gov/Archives/edgar/data/1/${before.replaceAll('-', '')}/${before}-index.html`,
    `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${after.replaceAll('-', '')}/${after}-index.html`,
  ]));
  function rewrite(value: unknown, key = ''): unknown {
    if (Array.isArray(value)) return value.map(item => rewrite(item));
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value).map(([field, child]) => [field, rewrite(child, field)]));
    }
    if (key === 'ticker') return issuer.ticker;
    if (key === 'company_name') return issuer.name;
    if (key === 'company_cik') return issuer.cik;
    if (['data_version', 'facts_version', 'evidence_version'].includes(key)) return version;
    if (key === 'scope') {
      if (value !== oldScope) throw new Error('Unexpected committed insights scope');
      return scope;
    }
    if (key === 'accession_number' || key === 'sec_url') {
      const replacement = typeof value === 'string' ? (key === 'sec_url' ? urls : accessions).get(value) : undefined;
      if (!replacement) throw new Error('Unexpected committed insights source identity');
      return replacement;
    }
    return value;
  }
  // This is identity rebasing only. Production admission is exercised separately
  // by persistent Node tests and, after authorization, the real browser Worker.
  return rewrite(input) as InsightResponse;
}
