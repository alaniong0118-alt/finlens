import { test as base } from './annual-period-browser';
import type { ApiRequest, Scenario, Reply } from './browser';
import type { FilingContext, FilingSource } from '../../lib/finlens-api';
import * as data from './data';
export { expect } from './annual-period-browser';

// Explicit synthetic filings only; no acquisition or real-data acceptance.
export function dualSources(ticker: string): FilingSource[] {
  return ['000001', '000003'].map((suffix, index) => {
    const acc = data.accession(ticker, suffix);
    return { accession_number: acc, form: index ? '10-Q' : '10-K', filed: index ? '2025-05-01' : '2025-02-01',
      period_start: null, period_end: null, metrics: [], has_filing_chunks: true,
      sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(data.company(ticker).cik)}/${acc.replaceAll('-', '')}/${acc}-index.html` };
  });
}
export function dualEvidence(ticker: string, accession: string, query: string, count = 2): FilingContext {
  const filing = dualSources(ticker).find(item => item.accession_number === accession);
  if (!filing || count < 0 || count > 5) throw new Error('Undeclared dual-filing fixture');
  const text = `${ticker} synthetic original disclosure for ${accession}. Supply chain constraints. 😀 <script>literal()</script>\n\n  Source wording retained.`;
  const citations = Array.from({ length: count }, (_, i) => ({ citation_id: `source_${i + 1}`, chunk_id: `chunk_${String(i).padStart(4, '0')}`,
    accession_number: accession, form: filing.form!, filed: filing.filed, filename: 'synthetic.htm', start_char: i * 3000,
    end_char: i * 3000 + Array.from(text).length, sec_url: filing.sec_url, similarity: .8, semantic_similarity: .8, lexical_score: 1, hybrid_score: 1, evidence_reason: 'strong_lexical' }));
  return { ticker, company_name: data.company(ticker).name, accession_number: accession, query,
    evidence_status: count ? 'sufficient' : 'insufficient', citations,
    context: citations.map(c => `[SOURCE ${c.citation_id}]\nchunk_id: ${c.chunk_id}\naccession_number: ${accession}\nform: ${c.form}\nsimilarity: 0.800000\ntext: |-\n${text.split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE ${c.citation_id}]`).join('\n\n') };
}
export function validateDualRequest(item: ApiRequest, scenario: Pick<Scenario, 'versions'>): { ticker: string; accession: string; question: string } {
  const match = /^\/companies\/(AAA|BBB)\/filings\/(\d{10}-\d{2}-\d{6})\/context$/.exec(item.path);
  const ticker = match?.[1], accession = match?.[2], question = item.query.get('q');
  if (!ticker || !accession || item.ticker !== ticker || !dualSources(ticker).some(f => f.accession_number === accession)
      || item.method !== 'GET' || item.body !== null || item.request.postData() !== null
      || !Number.isSafeInteger(scenario.versions[ticker]) || scenario.versions[ticker] < 0 || item.pin !== String(scenario.versions[ticker])
      || [...item.query.keys()].sort().join(',') !== 'limit,q' || item.query.get('limit') !== '5'
      || !question || question !== question.trim() || question.length > 2000) throw new Error('Invalid synthetic dual-filing request');
  return { ticker, accession, question };
}
export const test = base.extend<{ dualScenario: Scenario }>({
  dualScenario: [async ({ context, annualScenario: scenario }, use) => {
    scenario.overrides.push(item => item.path === '/companies' ? { body: data.companies.map(c => ({ ...c, indexed_filing_count: 2 })) }
      : item.path.endsWith('/sources') ? { body: dualSources(item.ticker!) } : undefined);
    // Narrow extra route, shared lifecycle recorder/ledger and unchanged egress guards.
    await context.route('**/api/finlens/companies/*/filings/*/context*', async route => {
      const request = route.request(), url = new URL(request.url());
      try {
        if (url.origin !== 'http://127.0.0.1:3107') throw new Error('Nonlocal dual-filing request');
        const item: ApiRequest = { method: request.method(), path: url.pathname.slice('/api/finlens'.length), ticker: url.pathname.split('/')[4],
          pin: request.headers()['x-finlens-data-version'], query: url.searchParams, body: request.postData() ? request.postDataJSON() : null, request };
        if (scenario.ledger.length >= 200) throw new Error('Full-page request budget exceeded');
        scenario.ledger.push(item);
        const { ticker, accession, question } = validateDualRequest(item, scenario);
        let reply: Reply | undefined;
        for (const override of scenario.overrides) { reply = await override(item); if (reply) break; }
        reply ??= { body: dualEvidence(ticker, accession, question) };
        if (reply.abort) throw new Error('Undeclared dual-filing network failure');
        const version = reply.version === undefined ? String(scenario.versions[ticker]) : reply.version;
        await route.fulfill({ status: reply.status ?? 200, contentType: 'application/json', headers: {
          ...(version === null ? {} : { 'X-FinLens-Data-Version': version }), ...(reply.code ? { 'X-FinLens-Error-Code': reply.code } : {}),
        }, body: JSON.stringify(reply.body ?? { detail: 'Synthetic failure' }) });
      } catch (error) {
        if (!String(error).includes('Target page, context or browser has been closed') && !String(error).includes('Invalid InterceptionId')) scenario.violations.push(String(error));
        await route.abort('blockedbyclient').catch(() => {});
      }
    });
    await use(scenario);
  }, { auto: true }],
});
