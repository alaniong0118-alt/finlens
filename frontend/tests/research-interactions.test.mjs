import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

// Node's existing test runner + real ReactDOM. Only Next's routing link and
// browser layout/media APIs are adapted; page, effects, API calls and guards run.
const require = createRequire(import.meta.url);
let dom, createRoot, Home, ResearchFreshness;
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const key of ['window', 'document', 'HTMLElement', 'SVGElement', 'Node', 'Event', 'MouseEvent']) {
    Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  dom.window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  globalThis.matchMedia = dom.window.matchMedia;
  globalThis.localStorage = dom.window.localStorage;
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback; }
    observe(target) { this.callback([{ target, contentRect: { width: 700, height: 250 } }]); }
    unobserve() {}
    disconnect() {}
  };
  dom.window.HTMLElement.prototype.getBoundingClientRect = () => ({ width: 700, height: 250, top: 0, left: 0, right: 700, bottom: 250 });
  ({ createRoot } = await import('react-dom/client'));
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const exports = {};
    cache.set(path, exports);
    const output = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    } }).outputText;
    const localRequire = name => {
      if (name === 'next/link') return { __esModule: true, default: props => React.createElement('a', props) };
      if (!name.startsWith('@/')) return require(name);
      const base = fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url));
      return load(['.tsx', '.ts'].map(extension => base + extension).find(existsSync));
    };
    new Function('require', 'exports', output)(localRequire, exports);
    return exports;
  }
  Home = load(fileURLToPath(new URL('../app/page.tsx', import.meta.url))).default;
  ResearchFreshness = load(fileURLToPath(new URL('../components/research-freshness.tsx', import.meta.url))).default;
});
after(() => dom.window.close());

function presentationContext(ticker, query, texts) {
  const base = context(ticker, query);
  return { ...base,
    context: texts.map((text, index) => `[SOURCE source_${index + 1}]\ntext: |-\n  ${text}\n[END SOURCE source_${index + 1}]`).join('\n\n'),
    citations: texts.map((text, index) => ({ ...base.citations[0], citation_id: `source_${index + 1}`, chunk_id: `${ticker}-chunk-${index + 1}`, end_char: text.length })) };
}

const salesRow = 'Services 30,739 27,423 91,728 80,408 Total net sales $ 109,417 $ 94,036.';

test('mounted amount shows compact highlighted proof, two cards and ranked accessible expansions', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const query = 'How much revenue did Apple report?';
  const pending = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  const texts = ['Unrelated introduction. '.repeat(35) + salesRow, `(in millions): ${salesRow}`, 'Revenue third ranked passage.', 'Revenue fourth ranked passage.', 'Revenue fifth ranked passage.'];
  await app.release(pending, presentationContext('AAPL', query, texts));
  const direct = app.host.querySelector('.direct-answer');
  assert.equal(direct.querySelector('.metric-value').textContent, '$109.42B');
  assert.equal(direct.querySelectorAll('.answer-text').length, 1);
  assert.equal(direct.querySelector('details').open, false);
  assert.doesNotMatch(direct.textContent, /Supporting passages search/);
  assert.equal(app.evidence().length, 2);
  const first = app.host.querySelector('.evidence-card');
  assert.match(first.querySelector('.evidence-preview').textContent, /Total net sales \$ 109,417/);
  assert.doesNotMatch(first.querySelector('.evidence-preview').textContent, /Unrelated introduction/);
  assert.equal(first.querySelector('mark.value-match').textContent, '$ 109,417');
  const full = first.querySelector('details'); assert.equal(full.open, false);
  full.querySelector('summary').focus(); assert.equal(document.activeElement, full.querySelector('summary'));
  await act(async () => full.querySelector('summary').click());
  assert.equal(full.open, true); assert.equal(full.querySelector('p').textContent, texts[0]);
  const toggle = app.host.querySelector('.evidence-toggle'); assert.equal(toggle.getAttribute('aria-expanded'), 'false');
  const requestCount = app.requests.length;
  await app.click('Show more evidence (3)'); assert.equal(toggle.getAttribute('aria-expanded'), 'true');
  assert.deepEqual([...app.host.querySelectorAll('.evidence-heading h4')].map(item => item.textContent), Array.from({length:5}, (_, index) => `Evidence ${index + 1} · 10-Q`));
  await app.click('Show less evidence'); assert.equal(app.evidence().length, 2);
  assert.equal(app.requests.length, requestCount, 'Disclosure/expansion must not fetch data');
  assert.equal(app.requests.filter(request => /\/answer$/.test(request.path)).length, 0);
});

test('mounted method research prefers accounting text without numeric direct answer', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const query = 'How does Apple report revenue?'; const pending = await app.search('AAPL', query);
  const text = 'Total net sales $109,417 million. '.repeat(20) + 'Revenue is recognized when control transfers to the customer. Accounting policies describe performance obligations.';
  await app.release(pending, presentationContext('AAPL', query, [text]));
  assert.ok(!app.host.querySelector('.direct-answer'));
  const preview = app.host.querySelector('.evidence-preview'); assert.match(preview.textContent, /Revenue is recognized/);
  assert.ok([...preview.querySelectorAll('mark')].some(mark => /recognized/.test(mark.textContent)));
  assert.ok(!preview.querySelector('mark.value-match'));
});

test('mounted keyword fallback highlights terms and safely renders literal markup', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const query = 'supply constraints'; const pending = await app.search('AAPL', query);
  await app.release(pending, presentationContext('AAPL', query, ['Unrelated text. '.repeat(30) + 'Supply constraints affect components <script>unsafe()</script>.']));
  const preview = app.host.querySelector('.evidence-preview'); assert.match(preview.textContent, /Supply constraints/);
  assert.equal(preview.querySelectorAll('mark').length, 1);
  assert.ok(!preview.querySelector('script')); assert.match(preview.textContent, /<script>/);
});

test('mounted unavailable answer retains reason without numeric-validation marks', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const query = 'latest quarterly revenue growth'; const pending = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query, 'unavailable'));
  await app.release(pending, presentationContext('AAPL', query, [`(in millions): ${salesRow}`]));
  assert.match(app.host.querySelector('.direct-answer').textContent, /Unavailable.*economic bases/);
  assert.equal(app.host.querySelectorAll('mark.value-match').length, 0); assert.ok(app.host.querySelector('mark'));
});

test('mounted query/company changes remove highlights and reset evidence expansion', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  let pending = await app.search('AAPL', 'revenue');
  await app.release(pending, presentationContext('AAPL', 'revenue', Array.from({length:5}, (_, index) => `Revenue old scope ${index}.`)));
  await app.click('Show more evidence (3)'); assert.equal(app.evidence().length, 5);
  await app.change(app.host.querySelector('textarea'), 'supply constraints');
  assert.equal(app.host.querySelectorAll('mark').length, 0); assert.deepEqual(app.evidence(), []);
  pending = await app.search('AAPL', 'supply constraints');
  await app.release(pending, presentationContext('AAPL', 'supply constraints', Array(5).fill('Supply constraints current scope.')));
  assert.equal(app.evidence().length, 2); assert.doesNotMatch(app.host.querySelector('.evidence-results').textContent, /old scope/);
  await app.change(app.host.querySelector('#company'), 'JPM');
  assert.equal(app.host.querySelectorAll('mark').length, 0); assert.deepEqual(app.evidence(), []);
});

// Explicit synthetic API fixtures live only in tests. One filing per company;
// no database, network, production data or generated model output is involved.
const companies = [
  { id: 1, ticker: 'AAPL', name: 'Apple fixture', cik: '0000320193', exchange: 'NASDAQ', has_indexed_filing: true, indexed_filing_count: 1 },
  { id: 2, ticker: 'JPM', name: 'JPM fixture', cik: '0000019617', exchange: 'NYSE', has_indexed_filing: true, indexed_filing_count: 1 },
];
function filing(ticker) {
  return { accession_number: `${ticker}-test-accession`, form: '10-Q', filed: '2025-05-01',
    period_start: '2025-01-01', period_end: '2025-03-31', metrics: [], has_filing_chunks: true,
    sec_url: `https://www.sec.gov/Archives/test/${ticker}` };
}
function point(ticker, value, metric = 'revenue', kind = 'quarter') {
  const period = { kind, start: '2025-01-01', end: kind === 'annual' ? '2025-12-31' : '2025-03-31', fiscal_year: 2025, fiscal_period: kind === 'annual' ? 'FY' : 'Q1', fiscal_label_basis: 'test fixture' };
  return { metric, unit: 'USD', status: 'available', value, reason: null, period,
    formula: null, revenue_basis: 'total_revenue', alternatives: [], inputs: [],
    provenance: [{ fact_id: 1, original_concept: `${ticker} ${metric} test concept`, value, unit: 'USD',
      period_start: period.start, period_end: period.end, form: '10-Q', filed: '2025-05-01',
      accession_number: filing(ticker).accession_number, sec_url: filing(ticker).sec_url,
      company_cik: companies.find(company => company.ticker === ticker).cik, source_fiscal_year: 2025, source_fiscal_period: 'Q1' }] };
}
function summary(ticker, value, kind = 'quarter') {
  const revenue = point(ticker, value, 'revenue', kind);
  return { ticker, company_cik: companies.find(company => company.ticker === ticker).cik, company_name: `${ticker} fixture`, requested_period: kind, period: revenue.period,
    metrics: { revenue }, selection_policy: 'test fixture' };
}
function history(ticker, value, metric = 'revenue') {
  return { ticker, company_cik: companies.find(company => company.ticker === ticker).cik, metric, unit: 'USD', requested_period: 'quarter', status: 'available', reason: null,
    history: [point(ticker, value, metric)] };
}
function context(ticker, query = 'revenue growth') {
  const source = filing(ticker);
  const text = `${ticker} test evidence: reported revenue increased. This is a stored-excerpt fixture, not a generated answer.`;
  return { ticker, company_name: `${ticker} fixture`, query, accession_number: source.accession_number,
    evidence_status: 'sufficient', context: `[SOURCE source_1]\ntext: |-\n  ${text}\n[END SOURCE source_1]`,
    citations: [{ ...source, citation_id: 'source_1', chunk_id: `${ticker}-chunk`, filename: `${ticker}-fixture.htm`,
      start_char: 0, end_char: text.length, evidence_reason: 'strong_lexical', similarity: 0.8, semantic_similarity: 0.8, lexical_score: 1, hybrid_score: 1 }] };
}
function companyPath(ticker, suffix) { return `/companies/${ticker}/${suffix}`; }

function companyContext(ticker, query = 'revenue growth', version = 0) {
  const { accession_number, ...evidence } = context(ticker, query);
  const cik = companies.find(company => company.ticker === ticker).cik;
  const citations = evidence.citations.map(citation => ({ ...citation, company_cik: cik }));
  return { ...evidence, retrieval_scope: 'company', company_cik: cik, data_version: version,
    evidence_version: 0, searched_accessions: [accession_number], excluded_publication_count: 0,
    context: companySource(citations[0], `${ticker} test evidence revenue growth.`), citations };
}

function companySource(citation, text) {
  const metadata = Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id',
    'form', 'filed', 'start_char', 'end_char'].map(key => [key, citation[key]]));
  return `[SOURCE ${citation.citation_id}]\nmetadata: ${JSON.stringify(metadata)}\ntext: |-\n${text.split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE ${citation.citation_id}]`;
}

// RISK-SEC-01 fixtures use actual backend identities/framing, separately from
// historical generic fixtures. No shared harness or older evidence is changed.
const riskAcc = (ticker = 'AAPL', suffix = '000001') => `${companies.find(c => c.ticker === ticker).cik}-25-${suffix}`;
function riskSource(ticker = 'AAPL', suffix = '000001') {
  const acc = riskAcc(ticker, suffix), cik = companies.find(c => c.ticker === ticker).cik;
  return { ...filing(ticker), accession_number: acc, sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(cik)}/${acc.replaceAll('-', '')}/${acc}-index.html` };
}
function riskResponse(scope = 'filing', query = 'supply chain', version = 0, text = 'Synthetic issuer: supply chain disruptions may affect operations.') {
  const original = context('AAPL', query).citations[0];
  const fields = ['citation_id', 'chunk_id', 'accession_number', 'form', 'filed', 'filename', 'start_char', 'end_char', 'sec_url',
    'similarity', 'semantic_similarity', 'lexical_score', 'hybrid_score', 'evidence_reason'];
  const c = { ...Object.fromEntries(fields.map(key => [key, original[key]])), accession_number: riskAcc(), chunk_id: 'chunk_0000',
    sec_url: riskSource().sec_url, end_char: text.length, ...(scope === 'company' ? { company_cik: companies[0].cik } : {}) };
  const base = { ticker: 'AAPL', company_name: 'Synthetic issuer', query, evidence_status: 'sufficient', citations: [c],
    context: scope === 'company' ? companySource(c, text)
      : `[SOURCE source_1]\nchunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: ${c.similarity.toFixed(6)}\ntext: |-\n  ${text}\n[END SOURCE source_1]` };
  return scope === 'filing' ? { ...base, accession_number: riskAcc() } : { ...base, retrieval_scope: 'company', company_cik: companies[0].cik,
    data_version: version, evidence_version: 0, searched_accessions: [riskAcc()], excluded_publication_count: 0 };
}
async function mountRisk(ctx, { strict = false, version = 0, scope = 'filing', sourceState = 'ready' } = {}) {
  const app = await mount(ctx, true, companies, { initialVersion: version, strict });
  if (version !== null) {
    await app.release(app.request(companyPath('AAPL', 'financials/summary')), summary('AAPL', '1000000000'));
    await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '1000000000'));
    await app.release(app.request(companyPath('AAPL', 'sources')), sourceState === 'error' ? { detail: 'Synthetic filing list unavailable' }
      : sourceState === 'empty' ? [] : sourceState === 'metadata' ? [{ ...riskSource(), has_filing_chunks: false }]
        : [riskSource(), riskSource('AAPL', '000002')], sourceState === 'error' ? 503 : 200);
  }
  await app.change(app.select('Research purpose'), 'risk');
  if (scope === 'company') await app.change(app.select('Evidence search scope'), 'company');
  await app.click('Use risk topic');
  return app;
}
const riskRequestPath = scope => companyPath('AAPL', scope === 'company' ? 'context' : `filings/${riskAcc()}/context`);
const unexpectedRiskWork = app => app.requests.filter(r => /research-answer|\/answer$|\/tone$/.test(r.path));

for (const strict of [false, true]) for (const version of [0, 1]) for (const scope of ['filing', 'company']) {
  test(`RISK-SEC-01 ${scope} pin ${version} strict ${strict}: preparation, single dispatch, provenance and duplicate-click guard`, async ctx => {
    const app = await mountRisk(ctx, { strict, version, scope });
    const count = app.requests.length;
    assert.equal(document.activeElement, app.host.querySelector('textarea'));
    assert.equal(app.host.querySelector('textarea').value, 'supply chain');
    assert.equal(app.select('Risk topic').options.length, 6);
    await app.change(app.select('Risk topic'), 'competition');
    assert.equal(app.host.querySelector('textarea').value, 'competition');
    await app.click('Use risk topic');
    assert.equal(app.requests.length, count, 'Preparing topics never fetches');
    const form = app.host.querySelector('.search-form');
    await act(async () => { form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
    assert.equal(app.requests.length, count + 1);
    const pending = app.request(riskRequestPath(scope));
    assert.equal(pending.params.get('q'), 'competition'); assert.equal(pending.params.get('limit'), '5');
    assert.equal(pending.init.headers['X-FinLens-Data-Version'], String(version));
    await app.release(pending, riskResponse(scope, 'competition', version));
    assert.match(app.host.querySelector('.evidence-results').textContent, /Candidate SEC passages/);
    assert.match(app.host.textContent, new RegExp(`CIK 0000320193 · Publication ${version}`));
    assert.match(app.evidence()[0], new RegExp(riskAcc()));
    assert.match(app.evidence()[0], /Filed May 1, 2025/);
    assert.equal(app.host.querySelector('.evidence-card .source-link').href, riskSource().sec_url);
    assert.equal(unexpectedRiskWork(app).length, 0);
    assert.equal(app.host.querySelectorAll('.ai-panel, .passage-tone, .direct-answer').length, 0);
    assert.match(app.host.textContent, /Search relevance is not risk severity or probability/);
    const after = app.requests.length;
    await app.change(app.host.querySelector('textarea'), 'custom operating disclosure');
    assert.equal(app.evidence().length, 0); assert.equal(app.requests.length, after);
    await app.click('Search risk topic');
    await app.release(app.request(riskRequestPath(scope)), riskResponse(scope, 'custom operating disclosure', version));
    assert.match(app.host.textContent, /Custom risk-topic search/);
  });
}

for (const state of ['error', 'empty', 'metadata']) for (const scope of ['filing', 'company']) test(`RISK-SEC-01 ${state} ${scope} evidence is unavailable, never insufficient`, async ctx => {
  const app = await mountRisk(ctx, { sourceState: state, scope });
  const count = app.requests.length;
  assert.equal(app.host.querySelector('.primary-button').disabled, true);
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(app.requests.length, count); assert.equal(app.evidence().length, 0);
  assert.match(app.host.textContent, /Searchable SEC evidence is unavailable/);
  assert.doesNotMatch(app.host.textContent, /Insufficient topic evidence/);
  if (state === 'error') assert.match(app.host.textContent, /Could not load the filing list/);
});
test('RISK-SEC-01 unknown pin keeps preparation editable and blocks every context submission', async ctx => {
  const app = await mountRisk(ctx, { version: null, strict: true });
  await app.change(app.select('Risk topic'), 'cybersecurity');
  assert.equal(app.host.querySelector('textarea').value, 'cybersecurity');
  const count = app.requests.length;
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(app.requests.length, count);
  assert.match(app.host.textContent, /Verify this company’s published data before searching/);
});

for (const scope of ['filing', 'company']) test(`RISK-SEC-01 ${scope} valid empty response is insufficient, malformed response is unavailable and retry explicit`, async ctx => {
  const app = await mountRisk(ctx, { scope });
  await app.click('Search risk topic');
  const empty = { ...riskResponse(scope), citations: [], context: '', evidence_status: 'insufficient' };
  await app.release(app.request(riskRequestPath(scope)), empty);
  assert.match(app.host.querySelector('.evidence-results').textContent, /Insufficient topic evidence/);
  assert.match(app.host.querySelector('.evidence-results').textContent, /does not mean no risk/);
  await app.click('Search risk topic');
  const bad = riskResponse(scope); bad.citations[0].sec_url = 'https://evil.test/source';
  const count = app.requests.length;
  await app.release(app.request(riskRequestPath(scope)), bad);
  assert.match(app.host.querySelector('[role="alert"]').textContent, /could not be verified/);
  assert.equal(app.evidence().length, 0); assert.equal(app.requests.length, count);
  await app.click('Retry risk-topic search');
  assert.equal(app.requests.length, count + 1);
  await app.release(app.request(riskRequestPath(scope)), riskResponse(scope));
  assert.equal(app.evidence().length, 1); assert.equal(unexpectedRiskWork(app).length, 0);
});

for (const scope of ['filing', 'company']) for (const defect of ['span', 'form', 'filed', 'filename']) {
  test(`RISK-SEC-01 P2 mounted ${scope} rejects ${defect} before source cards or attribution render`, async ctx => {
    const app = await mountRisk(ctx, { scope, strict: true });
    await app.click('Search risk topic');
    await app.release(app.request(riskRequestPath(scope)), riskResponse(scope));
    assert.equal(app.evidence().length, 1, 'Establish valid evidence before the rejected replacement');
    await app.click('Search risk topic');
    const texts = ['MALFORMED PROVENANCE passage one.', 'MALFORMED PROVENANCE passage two.'];
    const value = riskResponse(scope, 'supply chain', 0, texts[0]);
    if (defect === 'span') value.citations[0].end_char = 1;
    else {
      const other = { ...value.citations[0], citation_id: 'source_2', chunk_id: 'chunk_0001', start_char: 100, end_char: 100 + texts[1].length };
      other[defect] = { form: '10-K', filed: '2025-06-01', filename: 'other.htm' }[defect];
      value.citations.push(other);
    }
    // Keep every SOURCE header/metadata field consistent with its own citation.
    value.context = value.citations.map((c, index) => scope === 'company' ? companySource(c, texts[index])
      : `[SOURCE ${c.citation_id}]\nchunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: ${c.similarity.toFixed(6)}\ntext: |-\n  ${texts[index]}\n[END SOURCE ${c.citation_id}]`).join('\n\n');
    const count = app.requests.length;
    await app.release(app.request(riskRequestPath(scope)), value);
    assert.match(app.host.querySelector('[role="alert"]').textContent, /evidence response could not be verified/);
    assert.equal(app.host.querySelectorAll('.evidence-results, .evidence-card, .evidence-results .source-link').length, 0);
    assert.doesNotMatch(app.host.textContent, /MALFORMED PROVENANCE|Candidate SEC passages/);
    assert.equal(app.requests.length, count, 'Rejection does not retry or change scope');
    assert.equal(unexpectedRiskWork(app).length, 0);
  });
}

for (const strict of [false, true]) for (const action of ['purpose', 'topic', 'query', 'filing', 'scope', 'company']) {
  test(`RISK-SEC-01 ${action} change strict ${strict} rejects late risk delivery without automatic research`, async ctx => {
    const app = await mountRisk(ctx, { strict }); await app.click('Search risk topic');
    const old = app.request(riskRequestPath('filing')), count = app.requests.length;
    if (action === 'purpose') await app.change(app.select('Research purpose'), 'general');
    if (action === 'topic') await app.change(app.select('Risk topic'), 'cybersecurity');
    if (action === 'query') await app.change(app.host.querySelector('textarea'), 'new custom query');
    if (action === 'filing') await app.change(app.select('Indexed SEC filing'), riskAcc('AAPL', '000002'));
    if (action === 'scope') await app.change(app.select('Evidence search scope'), 'company');
    if (action === 'company') await app.change(app.host.querySelector('#company'), 'JPM');
    assert.equal(old.init.signal.aborted, true);
    await app.release(old, riskResponse('filing', 'supply chain', 0, 'OBSOLETE synthetic risk passage'));
    assert.equal(app.evidence().length, 0); assert.doesNotMatch(app.host.textContent, /OBSOLETE synthetic/);
    assert.equal(app.requests.slice(count).filter(r => /\/context$|research-answer|\/answer$|\/tone$/.test(r.path)).length, 0);
  });
}

for (const strict of [false, true]) test(`RISK-SEC-01 pre-commit obsolete 409 strict ${strict} cannot invalidate a newly verified publication`, async ctx => {
  const app = await mountRisk(ctx, { strict }); await app.click('Search risk topic');
  const old = app.request(riskRequestPath('filing'));
  await focusCheck(); const check = app.request(companyPath('AAPL', 'freshness'));
  const freshnessCount = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await act(async () => {
    app.deliverBeforeCommit(check, freshnessFixture('AAPL', 1, 1)); await drainResponseMicrotasks();
    assert.ok(app.request('/companies'));
    assert.equal(old.init.signal.aborted, false, 'Deliver before passive cancellation');
    app.deliverBeforeCommit(old, {}, 409, 1); await drainResponseMicrotasks();
  });
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, freshnessCount);
  assert.equal(app.evidence().length, 0);
  await app.release(app.request(companyPath('AAPL', 'sources')), [riskSource()], 200, 1);
  const count = app.requests.length;
  await app.click('Search risk topic'); const next = app.request(riskRequestPath('filing'));
  assert.equal(next.init.headers['X-FinLens-Data-Version'], '1'); assert.equal(app.requests.length, count + 1);
  await app.release(next, riskResponse('filing', 'supply chain', 1), 200, 1);
  assert.equal(app.evidence().length, 1);
  assert.equal(unexpectedRiskWork(app).length, 0);
});

test('RISK-SEC-01 current stale pin reconciles once and never replays risk search', async ctx => {
  const app = await mountRisk(ctx); await app.click('Search risk topic');
  const before = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await app.release(app.request(riskRequestPath('filing')), {}, 409, 1);
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, before + 1);
  assert.equal(app.host.querySelector('.primary-button').disabled, true);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1, 1));
  assert.equal(app.requests.filter(r => /\/context$/.test(r.path)).length, 1);
  assert.equal(app.evidence().length, 0);
});

test('RISK-SEC-01 switching back preserves explicit general direct-answer and selected AI behavior', async ctx => {
  const app = await mountRisk(ctx); await app.change(app.select('Research purpose'), 'general');
  assert.equal(app.select('Research purpose').value, 'general');
  await app.click('Use question'); await app.click('Research question');
  const q = 'What is the latest available revenue?';
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', q));
  const response = riskResponse('filing', q);
  await app.release(app.request(riskRequestPath('filing')), response);
  assert.ok(app.host.querySelector('.direct-answer')); assert.ok(app.host.querySelector('.ai-panel'));
  assert.ok(app.host.querySelector('.passage-tone'));
  assert.equal(app.requests.filter(r => /\/answer$|\/tone$/.test(r.path)).length, 0);
});

for (const scope of ['filing', 'company']) for (const [code, status, message] of [
  ['EVIDENCE_PENDING', 409, 'Synthetic evidence is pending.'],
  ['SEARCH_SCOPE_TOO_LARGE', 409, 'Synthetic scope exceeds its resource limit.'],
  ['RETRIEVAL_UNAVAILABLE', 503, 'Synthetic encoder is unavailable.'],
  ['DATABASE_UNAVAILABLE', 503, 'Synthetic database is unavailable.'],
  ['DATABASE_TIMEOUT', 504, 'Synthetic database deadline expired.'],
  ['DATABASE_BUSY', 503, 'Synthetic database is busy.'],
]) test(`RISK-SEC-01 ${scope} ${code} is an error without scope fallback or automatic retry`, async ctx => {
  const app = await mountRisk(ctx, { scope }); await app.click('Search risk topic');
  const pending = app.request(riskRequestPath(scope));
  const count = app.requests.length;
  pending.released = true;
  await act(async () => pending.resolve(new Response(JSON.stringify({ detail: message }), { status, headers: {
    'X-FinLens-Data-Version': '0', 'X-FinLens-Error-Code': code,
  } })));
  assert.equal(app.host.querySelector('[role="alert"]').textContent, message);
  assert.equal(app.select('Evidence search scope').value, scope);
  assert.equal(app.requests.length, count); assert.equal(app.evidence().length, 0);
  assert.doesNotMatch(app.host.textContent, /Insufficient topic evidence/);
  await app.click('Retry risk-topic search');
  assert.equal(app.requests.length, count + 1); assert.equal(unexpectedRiskWork(app).length, 0);
});

for (const failure of ['network', 'timeout']) test(`RISK-SEC-01 ${failure} permits explicit retry and rejects late completion`, async ctx => {
  const expire = failure === 'timeout' ? researchDeadlineClock(ctx) : null;
  const app = await mountRisk(ctx);
  await app.click('Search risk topic'); const pending = app.request(riskRequestPath('filing'));
  const count = app.requests.length;
  if (expire) await expire(); else { pending.released = true; await act(async () => pending.reject(new Error('Synthetic transport interruption'))); }
  assert.match(app.host.querySelector('[role="alert"]').textContent, failure === 'timeout' ? /too long/ : /Cannot reach/);
  assert.equal(app.requests.length, count); assert.equal(app.evidence().length, 0);
  await app.click('Retry risk-topic search'); const retry = app.request(riskRequestPath('filing'));
  if (expire) {
    await app.release(pending, riskResponse('filing', 'supply chain', 0, 'LATE timed out synthetic passage'));
    assert.equal(app.evidence().length, 0);
  }
  await app.release(retry, riskResponse()); assert.equal(app.evidence().length, 1);
});

for (const strict of [false, true]) test(`RISK-SEC-01 successful old response before version commit strict ${strict} cannot survive the new render`, async ctx => {
  const app = await mountRisk(ctx, { strict }); await app.click('Search risk topic');
  const old = app.request(riskRequestPath('filing'));
  await focusCheck(); const check = app.request(companyPath('AAPL', 'freshness'));
  await act(async () => {
    app.deliverBeforeCommit(check, freshnessFixture('AAPL', 1, 1)); await drainResponseMicrotasks();
    assert.equal(old.init.signal.aborted, false);
    app.deliverBeforeCommit(old, riskResponse('filing', 'supply chain', 0, 'OLD source before passive cleanup'), 200, 0);
    await drainResponseMicrotasks();
  });
  assert.equal(app.evidence().length, 0); assert.doesNotMatch(app.host.textContent, /OLD source before passive cleanup/);
  assert.equal(app.requests.filter(r => /\/context$/.test(r.path)).length, 1);
});

async function startCompanySearch(app, ticker = 'AAPL') {
  await app.change(app.select('Evidence search scope'), 'company');
  await app.change(app.host.querySelector('textarea'), 'revenue growth');
  await app.click('Research question');
  await app.release(app.request(companyPath(ticker, 'research-answer')), {
    ticker, question: 'revenue growth', matched: false, status: 'not_matched',
  });
  return app.request(companyPath(ticker, 'context'));
}

test('mounted company-wide scope preserves source lineage and exposes no AI action', async ctx => {
  const app = await mount(ctx, true);
  await app.completeCompany('AAPL', '1000000000');
  assert.equal(app.select('Evidence search scope').value, 'filing');
  const response = await startCompanySearch(app);
  assert.equal(app.select('Indexed SEC filing'), undefined);
  assert.equal(response.init.headers['X-FinLens-Data-Version'], '0');
  await app.release(response, companyContext('AAPL'));
  assert.match(app.host.textContent, /Company-wide · 1 verified published filings searched/);
  assert.match(app.evidence().join(''), /CIK 0000320193|CIK 320193/);
  assert.match(app.evidence().join(''), /AAPL-test-accession/);
  assert.match(app.evidence().join(''), /AAPL-fixture.htm/);
  assert.ok(![...app.host.querySelectorAll('button')].some(b => b.textContent === 'Generate AI analysis'));
  assert.equal(app.requests.filter(r => r.path.endsWith('/answer')).length, 0);
  assert.equal(app.requests.filter(r => r.path.includes('/filings/') && r.path.endsWith('/context')).length, 0);
  assert.equal(app.requests.filter(r => r.path === '/companies/AAPL/context').length, 1);
  await app.change(app.select('Evidence search scope'), 'filing');
  assert.deepEqual(app.evidence(), []);
  assert.equal(app.select('Indexed SEC filing').value, filing('AAPL').accession_number);
  await app.release(await app.search('AAPL'), context('AAPL'));
  assert.match(app.host.textContent, /Selected filing only/);
  assert.ok([...app.host.querySelectorAll('button')].some(b => b.textContent === 'Generate AI analysis'));
  assert.equal(app.requests.filter(r => r.path.endsWith('/answer')).length, 0);
});

test('mounted scope switch discards a delayed company-wide response', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const delayed = await startCompanySearch(app);
  await app.change(app.select('Evidence search scope'), 'filing');
  assert.equal(delayed.init.signal.aborted, true);
  await app.release(delayed, companyContext('AAPL'));
  assert.deepEqual(app.evidence(), []);
  assert.doesNotMatch(app.host.textContent, /verified published filings searched/);
});

test('mounted company switch discards company-wide evidence and restores default scope', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const delayed = await startCompanySearch(app);
  await app.change(app.host.querySelector('#company'), 'JPM');
  assert.equal(delayed.init.signal.aborted, true);
  await app.release(delayed, companyContext('AAPL'));
  await app.completeCompany('JPM', '2000000000');
  assert.equal(app.select('Evidence search scope').value, 'filing');
  assert.deepEqual(app.evidence(), []);
  assert.doesNotMatch(app.host.textContent, /AAPL test evidence/);
});

test('mounted company-wide evidence is invalidated by publication version changes', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const delayed = await startCompanySearch(app);
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(delayed.init.signal.aborted, true);
  await app.release(delayed, companyContext('AAPL'));
  assert.deepEqual(app.evidence(), []);
  assert.equal(app.select('Evidence search scope').value, 'company');
  assert.match(app.host.textContent, /Data updated; research this question again/);
});

test('mounted company-wide search presents honest insufficient evidence', async ctx => {
  const app = await mount(ctx, true);
  await app.completeCompany('AAPL', '1000000000');
  const request = await startCompanySearch(app);
  await app.release(request, { ...companyContext('AAPL'), evidence_status: 'insufficient', context: '', citations: [] });
  assert.match(app.host.textContent, /Insufficient evidence in published company filings/);
  assert.deepEqual(app.evidence(), []);
  assert.equal(app.requests.filter(r => r.path.endsWith('/answer')).length, 0);
});

test('mounted company-wide search cannot turn financial answer values into numeric proof marks', async ctx => {
  const app = await mount(ctx, true);
  await app.completeCompany('AAPL', '1000000000');
  await app.change(app.select('Evidence search scope'), 'company');
  await app.change(app.host.querySelector('textarea'), 'latest quarterly revenue');
  await app.click('Research question');
  const question = 'latest quarterly revenue';
  const direct = directAnswer('AAPL', question);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), direct);
  const evidence = companyContext('AAPL', question);
  evidence.context = companySource(evidence.citations[0], `Revenue USD ${direct.observation.value}.`);
  await app.release(app.request(companyPath('AAPL', 'context')), evidence);
  assert.equal(app.host.querySelectorAll('.evidence-card .value-match').length, 0);
  assert.ok(app.host.querySelector('.direct-answer'));
  assert.equal(app.requests.filter(r => r.path.endsWith('/answer')).length, 0);
});

async function mount(ctx, configured = false, catalog = companies, { initialVersion = 0, strict = false, catalogStatus = 200,
  capabilityPayload = { research_mode: true, ai_analysis_configured: configured, ai_analysis_enabled: configured, server_profile: 'development' }, capabilityStatus = 200 } = {}) {
  const requests = [];
  // Intentionally ignore AbortSignal when resolving: cancellation can race with
  // response delivery. This exercises rendered-state protection, not the mock.
  ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
    const url = new URL(input, 'http://finlens.test');
    assert.equal(url.origin, 'http://finlens.test', 'No external requests are allowed');
    assert.ok(url.pathname.startsWith('/api/finlens/'));
    let resolve, reject;
    const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
    requests.push({ path: url.pathname.slice('/api/finlens'.length), params: url.searchParams, init, resolve, reject, released: false });
    return promise;
  });
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  ctx.after(async () => { await act(async () => root.unmount()); host.remove(); localStorage.clear(); });
  await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, React.createElement(Home)) : React.createElement(Home)));
  function request(path, params = {}) {
    const found = requests.find(item => !item.released && !item.init.signal?.aborted && item.path === path && Object.entries(params).every(([key, value]) => item.params.get(key) === value));
    assert.ok(found, `Expected pending request ${path} ${JSON.stringify(params)}`);
    return found;
  }
  async function release(item, payload, status = 200, version = item.init.headers?.['X-FinLens-Data-Version'] ?? null) {
    assert.equal(item.released, false); item.released = true;
    await act(async () => item.resolve(new Response(JSON.stringify(payload), {
      status, headers: { 'Content-Type': 'application/json', ...(version !== null ? { 'X-FinLens-Data-Version': String(version) } : {}), ...(status === 502 ? { 'X-FinLens-Error-Code': 'UPSTREAM_FAILURE' } : {}), ...(status === 409 ? { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } : {}) },
    })));
  }
  function deliverBeforeCommit(item, payload, status = 200, version = item.init.headers?.['X-FinLens-Data-Version'] ?? null) {
    assert.equal(item.released, false); item.released = true;
    const response = new Response(null, {
      status, headers: { 'Content-Type': 'application/json', ...(version !== null ? { 'X-FinLens-Data-Version': String(version) } : {}), ...(status === 409 ? { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } : {}) },
    });
    // Resolve a parsed fixture without stream I/O or a nested act boundary. The
    // real API/effects run, but the enclosing act can hold React's commit while
    // freshness verification and an obsolete request's rejection interleave.
    response.json = async () => payload;
    item.resolve(response);
  }
  async function change(element, value) {
    assert.ok(element, 'Control must be rendered');
    await act(async () => {
      const prototype = element.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLSelectElement.prototype;
      Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
      element.dispatchEvent(new dom.window.Event(element.tagName === 'TEXTAREA' ? 'input' : 'change', { bubbles: true }));
    });
  }
  async function click(text) {
    const button = [...host.querySelectorAll('button')].find(item => item.textContent === text);
    assert.ok(button, `Button ${text} must be rendered`); assert.equal(button.disabled, false);
    await act(async () => button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
  }
  const select = name => [...host.querySelectorAll('label')].find(label => label.firstChild?.textContent?.trim() === name)?.querySelector('select');
  const snapshot = () => host.querySelector('[aria-labelledby="snapshot-title"]');
  const trends = () => host.querySelector('[aria-labelledby="history-title"]');
  const evidence = () => [...host.querySelectorAll('.evidence-card')].map(card => card.textContent);
  async function completeCompany(ticker, value) {
    if (!requests.some(item => !item.released && !item.init.signal.aborted && item.path === companyPath(ticker, 'financials/summary'))) {
      await release(request(companyPath(ticker, 'freshness')), freshnessFixture(ticker, 0));
    }
    await release(request(companyPath(ticker, 'financials/summary')), summary(ticker, value));
    await release(request(companyPath(ticker, 'financials/metrics/revenue')), history(ticker, value));
    await release(request(companyPath(ticker, 'sources')), [filing(ticker)]);
  }
  async function search(ticker, query = 'revenue growth', pendingAnswer = false) {
    await change(host.querySelector('textarea'), query);
    await click('Research question');
    if (!pendingAnswer) await release(request(companyPath(ticker, 'research-answer')), { ticker, question: query, matched: false, status: 'not_matched' });
    return request(companyPath(ticker, `filings/${filing(ticker).accession_number}/context`));
  }
  await release(request('/capabilities'), capabilityPayload, capabilityStatus);
  if (catalogStatus !== null) await release(request('/companies'), catalogStatus === 200 ? catalog : { detail: 'Catalog temporarily unavailable' }, catalogStatus);
  if (catalogStatus === 200 && initialVersion !== null) await release(request(companyPath(catalog[0].ticker, 'freshness')), freshnessFixture(catalog[0].ticker, initialVersion));
  return { host, requests, request, release, deliverBeforeCommit, change, click, select, snapshot, trends, evidence, completeCompany, search };
}

test('mounted company switch keeps B summary, history and filing after delayed A responses', async ctx => {
  const app = await mount(ctx);
  const lateSummary = app.request(companyPath('AAPL', 'financials/summary'));
  const lateHistory = app.request(companyPath('AAPL', 'financials/metrics/revenue'));
  const lateSources = app.request(companyPath('AAPL', 'sources'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  await app.completeCompany('JPM', '2000000000');
  const assertCurrent = () => {
    assert.equal(app.host.querySelector('#company-title').textContent, 'JPM fixture');
    assert.match(app.snapshot().textContent, /\$2B/); assert.doesNotMatch(app.snapshot().textContent, /AAPL test concept|\$1B/);
    assert.match(app.trends().textContent, /\$2B/); assert.doesNotMatch(app.trends().textContent, /AAPL revenue test concept|\$1B/);
    assert.equal(app.select('Indexed SEC filing').value, filing('JPM').accession_number);
    assert.doesNotMatch(app.host.querySelector('.filing-record').textContent, /AAPL-test-accession/);
  };
  assertCurrent();
  for (const [request, payload] of [[lateSummary, summary('AAPL', '1000000000')], [lateHistory, history('AAPL', '1000000000')], [lateSources, [filing('AAPL')]]]) {
    assert.equal(request.init.signal.aborted, true, 'Old company requests must be cancelled');
    await app.release(request, payload); assertCurrent();
  }
});

test('mounted company switch clears old scope and rejects pending old evidence', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const oldEvidence = await app.search('AAPL');
  await app.change(app.host.querySelector('#company'), 'JPM');
  // B sources are still pending: removing the page remount key would retain A's
  // filing/search controls here, even if later responses eventually correct it.
  assert.ok(!app.host.querySelector('.filing-record'), 'The old filing record must disappear immediately');
  assert.doesNotMatch(app.snapshot().textContent, /\$1B/);
  assert.equal(oldEvidence.init.signal.aborted, true);
  await app.release(oldEvidence, context('AAPL'));
  assert.deepEqual(app.evidence(), []);
  assert.doesNotMatch(app.host.textContent, /AAPL test evidence|AAPL-test-accession/);
  await app.completeCompany('JPM', '2000000000');
  await app.release(await app.search('JPM'), context('JPM'));
  assert.match(app.evidence().join(''), /JPM test evidence/);
  assert.doesNotMatch(app.evidence().join(''), /AAPL test evidence/);
});

test('mounted AI failure retains retrieved evidence and usable Research Mode', async ctx => {
  const app = await mount(ctx, true);
  await app.completeCompany('AAPL', '1000000000');
  await app.release(await app.search('AAPL'), context('AAPL'));
  const before = app.evidence(); assert.equal(before.length, 1);
  await app.click('Generate AI analysis');
  assert.deepEqual(app.evidence(), before, 'Evidence stays available during generation');
  await app.release(app.request(companyPath('AAPL', `filings/${filing('AAPL').accession_number}/answer`)), { detail: 'Provider quota fixture: private internal details' }, 502);
  assert.deepEqual(app.evidence(), before);
  assert.match(app.host.querySelector('.ai-panel').textContent, /AI analysis is currently unavailable.*SEC evidence.*still available/);
  assert.match(app.snapshot().textContent, /\$1B/);
  assert.match(app.trends().textContent, /\$1B/);
  assert.ok(!app.host.querySelector('[role="alert"]'), 'AI failure must not replace research with an application alert');
  assert.doesNotMatch(app.host.textContent, /quota|private internal details|Something went wrong/);
  assert.equal([...app.host.querySelectorAll('button')].find(button => button.textContent === 'Research question').disabled, false);
});

test('mounted no-key success renders summary, history, provenance and SEC evidence', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  assert.match(app.snapshot().textContent, /\$1B/);
  assert.match(app.snapshot().textContent, /Exact API value:.*1000000000 USD/);
  assert.match(app.trends().querySelector('table').textContent, /Direct quarter.*\$1B/);
  assert.equal(app.select('Indexed SEC filing').value, filing('AAPL').accession_number);
  await app.release(await app.search('AAPL'), context('AAPL'));
  assert.match(app.evidence().join(''), /AAPL test evidence/);
  assert.equal(app.host.querySelector('.evidence-card a').href, filing('AAPL').sec_url);
  assert.match(app.host.querySelector('.ai-panel').textContent, /Unavailable/);
  assert.equal([...app.host.querySelectorAll('button')].find(button => button.textContent === 'Generate AI analysis').disabled, true);
  assert.equal(app.requests.filter(request => request.path.endsWith('/answer')).length, 0);
});

for (const [name, capabilityPayload, capabilityStatus = 200] of [
  ['SEC-only effective denial', { research_mode: true, ai_analysis_configured: false, ai_analysis_enabled: false, server_profile: 'sec_readonly' }],
  ['key presence alone', { research_mode: true, ai_analysis_configured: true }],
  ['malformed capability', { research_mode: true, ai_analysis_configured: true, ai_analysis_enabled: 'true', server_profile: 'development' }],
  ['inconsistent release enablement', { research_mode: true, ai_analysis_configured: true, ai_analysis_enabled: true, server_profile: 'sec_readonly' }],
  ['capability failure', { detail: 'synthetic failure' }, 503],
]) test(`DEP-01A1 mounted ${name} keeps AI disabled and deterministic research usable`, async ctx => {
  const app = await mount(ctx, true, companies, { capabilityPayload, capabilityStatus });
  await app.completeCompany('AAPL', '1000000000');
  const query = "How much revenue did Apple report?";
  const pending = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  await app.release(pending, context('AAPL', query));
  assert.match(app.host.querySelector('.direct-answer').textContent, /\$109.42B/);
  assert.equal(app.evidence().length, 1);
  const button = [...app.host.querySelectorAll('button')].find(item => item.textContent === 'Generate AI analysis');
  assert.equal(button.disabled, true);
  await act(async () => button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
  assert.equal(app.requests.filter(item => item.path.endsWith('/answer')).length, 0);
});

test('mounted snapshot period change rejects a late response without relying on remounting', async ctx => {
  const app = await mount(ctx);
  const oldQuarter = app.request(companyPath('AAPL', 'financials/summary'), { period: 'quarter' });
  await app.change(app.select('Snapshot period'), 'annual');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), summary('AAPL', '4000000000', 'annual'));
  assert.equal(oldQuarter.init.signal.aborted, true);
  await app.release(oldQuarter, summary('AAPL', '1000000000'));
  assert.match(app.snapshot().textContent, /Annual.*\$4B/);
  assert.match(app.snapshot().querySelector('.period-label').textContent, /^Annual/);
  assert.doesNotMatch(app.snapshot().querySelector('.metric-grid').textContent, /Direct quarter|\$1B/);
});

test('mounted history metric change rejects the old series without relying on remounting', async ctx => {
  const app = await mount(ctx);
  const oldRevenue = app.request(companyPath('AAPL', 'financials/metrics/revenue'));
  await app.change(app.select('Metric'), 'net_income');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/net_income')), history('AAPL', '300000000', 'net_income'));
  assert.equal(oldRevenue.init.signal.aborted, true);
  await app.release(oldRevenue, history('AAPL', '1000000000'));
  assert.match(app.trends().querySelector('table').textContent, /Net income.*\$300M/);
  assert.doesNotMatch(app.trends().textContent, /AAPL revenue test concept|\$1B/);
});

test('mounted query edit invalidates pending evidence in the same filing scope', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const oldEvidence = await app.search('AAPL');
  await app.change(app.host.querySelector('textarea'), 'gross margin');
  assert.equal(oldEvidence.init.signal.aborted, true);
  await app.release(oldEvidence, context('AAPL'));
  assert.equal(app.host.querySelector('textarea').value, 'gross margin');
  assert.deepEqual(app.evidence(), []);
  assert.match(app.host.textContent, /Explore the filing evidence/);
  assert.doesNotMatch(app.host.textContent, /AAPL test evidence/);
});

function directAnswer(ticker, question, status = 'available') {
  const observation = point(ticker, '109417000000');
  if (status !== 'available') {
    observation.status = status; observation.value = null;
    observation.reason = 'Current/prior revenue economic bases are not explicitly comparable.';
    observation.provenance = [];
  }
  return { ticker, company_name: `${ticker} fixture`, question, matched: true, status,
    metric: 'revenue', metric_label: 'Revenue', period_intent: 'quarter',
    formatted_value: status === 'available' ? '$109.42B' : null,
    answer_text: status === 'available' ? `${ticker} fixture latest available quarterly revenue was $109.42B for the quarter ended March 31, 2025.` : `Quarterly revenue growth is unavailable. ${observation.reason}`,
    explanation: observation.reason, observation, comparability: null, selection_policy: 'fixture' };
}

function historicalAnswer(ticker, question, year = 2024, quarter = null) {
 const base = directAnswer(ticker, question);
 const observation = point(ticker, '100000000000', 'revenue', quarter ? 'quarter' : 'annual');
 observation.period.fiscal_year = year;
 observation.period.fiscal_period = quarter ? `Q${quarter}` : 'FY';
 observation.period.start = `${year}-${quarter === 2 ? '04' : '01'}-01`;
 observation.period.end = `${year}-${quarter === 2 ? '06-30' : '12-31'}`;
 observation.provenance[0] = { ...observation.provenance[0], fact_id: year,
   period_start: observation.period.start, period_end: observation.period.end,
   accession_number: `${ticker}-${year}-accession`, sec_url: `https://www.sec.gov/Archives/test/${ticker}/${year}` };
 return { ...base, answer_kind: 'historical_metric', requested_period: { fiscal_year: year, quarter },
   observation, formatted_value: '$100.00B', answer_text: `${ticker} fixture's ${quarter ? `Q${quarter} ` : ''}FY${year} revenue was $100.00B.` };
}

function comparisonAnswer(ticker, question, status = 'available') {
 const base = historicalAnswer(ticker, question);
 const earlier = base.observation;
 const later = historicalAnswer(ticker, question, 2025).observation;
 later.value = '110000000000'; later.provenance[0].value = later.value;
 if (status !== 'available') { later.status = status; later.value = null; later.provenance = []; later.reason = 'Incompatible revenue economic bases.'; }
 return { ...base, answer_kind: 'period_comparison', observation: null, status,
   formatted_value: status === 'available' ? '+10.00%' : null,
   formatted_absolute_change: status === 'available' ? '+$10.00B' : null,
   formatted_percentage_change: status === 'available' ? '+10.00%' : null,
   answer_text: status === 'available' ? `${ticker} revenue increased from $100.00B in FY2024 to $110.00B in FY2025 (+10.00%).` : 'Revenue comparison is unavailable. Incompatible revenue economic bases.',
   comparison: { status, reason: later.reason, earlier_period: { fiscal_year: 2024, quarter: null }, later_period: { fiscal_year: 2025, quarter: null }, earlier, later,
     absolute_change: status === 'available' ? '10000000000' : null, percentage_change: status === 'available' ? '0.1' : null,
     percentage_status: status === 'available' ? 'available' : 'unavailable', percentage_reason: null,
     direction: status === 'available' ? 'increase' : null, formula: 'absolute_change = later - earlier; percentage_change = (later - earlier) / earlier' } };
}

test('mounted historical annual and explicit-quarter answers show fiscal scope and provenance', async ctx => {
 const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
 for (const [query, year, quarter] of [['2024 revenue', 2024, null], ['Q2 2025 revenue', 2025, 2]]) {
  const evidence = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), historicalAnswer('AAPL', query, year, quarter));
  const answer = app.host.querySelector('.direct-answer');
  assert.match(answer.textContent, new RegExp(`${quarter ? 'Q2 ' : ''}FY${year}`));
  assert.equal(answer.querySelector('.metric-value').textContent, '$100.00B');
  assert.match(answer.querySelector('details').textContent, /Exact API value:.*100000000000 USD/);
  await app.release(evidence, context('AAPL', query));
 }
});

test('mounted comparison shows both periods, change and independent exact provenance', async ctx => {
 const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
 const query = '2024-2025 revenue growth'; const evidence = await app.search('AAPL', query, true);
 await app.release(app.request(companyPath('AAPL', 'research-answer')), comparisonAnswer('AAPL', query));
 const answer = app.host.querySelector('.direct-answer');
 assert.equal(answer.querySelector('.metric-value').textContent, '+10.00%');
 assert.match(answer.querySelector('dl').textContent, /FY2024\$100B.*FY2025\$110B.*Change\+\$10.00B/);
 const disclosure = answer.querySelector('.comparison-provenance'); assert.equal(disclosure.open, false);
 await act(async () => disclosure.querySelector('summary').click()); assert.equal(disclosure.open, true);
 const sides = [...disclosure.querySelectorAll('details')]; assert.equal(sides.length, 2);
 for (const [index, value] of ['100000000000', '110000000000'].entries()) {
  await act(async () => sides[index].querySelector('summary').click());
  assert.match(sides[index].textContent, new RegExp(`Exact API value:.*${value} USD`));
  assert.equal(sides[index].querySelector('a').href, `https://www.sec.gov/Archives/test/AAPL/${2024 + index}`);
 }
 await app.release(evidence, presentationContext('AAPL', query, ['Revenue $100,000 million in another filing period.']));
 assert.equal(app.host.querySelectorAll('mark.value-match').length, 0);
 assert.equal(app.requests.filter(r => r.path.endsWith('/research-answer')).length, 1);
});

test('mounted unavailable comparison keeps the reason and never fabricates a zero', async ctx => {
 const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
 const query = '2024 vs 2025 revenue'; const evidence = await app.search('AAPL', query, true);
 await app.release(app.request(companyPath('AAPL', 'research-answer')), comparisonAnswer('AAPL', query, 'unavailable'));
 const answer = app.host.querySelector('.direct-answer');
 assert.equal(answer.querySelector('.metric-value').textContent, 'Unavailable');
 assert.match(answer.textContent, /Incompatible revenue economic bases/);
 assert.doesNotMatch(answer.textContent, /\$0|\+10\.00%|Change/);
 assert.equal(answer.querySelectorAll('.comparison-provenance details').length, 2);
 await app.release(evidence, context('AAPL', query));
 assert.ok(app.host.querySelector('.direct-answer'));
});

test('mounted evidence failure preserves a completed comparison and both sources', async ctx => {
 const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
 const query = '2024-2025 revenue growth'; const evidence = await app.search('AAPL', query, true);
 await app.release(app.request(companyPath('AAPL', 'research-answer')), comparisonAnswer('AAPL', query));
 const before = app.host.querySelector('.direct-answer').textContent;
 await app.release(evidence, { detail: 'Evidence fixture failed' }, 503);
 assert.equal(app.host.querySelector('.direct-answer').textContent, before);
 assert.match(app.host.querySelector('[role="alert"]').textContent, /Evidence fixture failed/);
});

test('mounted AI failure preserves comparison, provenance and supporting evidence', async ctx => {
 const app = await mount(ctx, true); await app.completeCompany('AAPL', '1000000000');
 const query = '2024-2025 revenue growth'; const evidence = await app.search('AAPL', query, true);
 await app.release(app.request(companyPath('AAPL', 'research-answer')), comparisonAnswer('AAPL', query));
 await app.release(evidence, context('AAPL', query));
 const before = app.host.querySelector('.direct-answer').textContent, passages = app.evidence();
 await app.click('Generate AI analysis');
 await app.release(app.request(companyPath('AAPL', `filings/${filing('AAPL').accession_number}/answer`)), { detail: 'Private test-provider detail' }, 502);
 assert.equal(app.host.querySelector('.direct-answer').textContent, before);
 assert.deepEqual(app.evidence(), passages); assert.match(app.host.querySelector('.ai-panel').textContent, /AI analysis is currently unavailable/);
 assert.doesNotMatch(app.host.textContent, /Private test-provider/);
});

test('mounted company switch discards pending and completed comparison state', async ctx => {
 const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
 const query = '2024-2025 revenue growth'; const evidence = await app.search('AAPL', query, true);
 const old = app.request(companyPath('AAPL', 'research-answer'));
 await app.change(app.host.querySelector('#company'), 'JPM');
 await app.release(old, comparisonAnswer('AAPL', query)); await app.release(evidence, context('AAPL', query));
 assert.ok(!app.host.querySelector('.direct-answer')); await app.completeCompany('JPM', '2000000000');
 const currentEvidence = await app.search('JPM', query, true);
 await app.release(app.request(companyPath('JPM', 'research-answer')), comparisonAnswer('JPM', query));
 await app.release(currentEvidence, context('JPM', query));
 assert.match(app.host.querySelector('.direct-answer').textContent, /JPM revenue/);
 assert.doesNotMatch(app.host.querySelector('.direct-answer').textContent, /AAPL/);
 await app.change(app.host.querySelector('#company'), 'AAPL'); assert.ok(!app.host.querySelector('.direct-answer'));
});

test('mounted query edits clear completed comparison and reject delayed old responses', async ctx => {
 const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
 const query = '2024-2025 revenue growth'; let evidence = await app.search('AAPL', query, true);
 await app.release(app.request(companyPath('AAPL', 'research-answer')), comparisonAnswer('AAPL', query));
 await app.release(evidence, context('AAPL', query));
 await app.change(app.host.querySelector('textarea'), '2024 net income'); assert.ok(!app.host.querySelector('.direct-answer'));
 evidence = await app.search('AAPL', query, true); const old = app.request(companyPath('AAPL', 'research-answer'));
 await app.change(app.host.querySelector('textarea'), '2025 revenue');
 await app.release(old, comparisonAnswer('AAPL', query)); await app.release(evidence, context('AAPL', query));
 assert.ok(!app.host.querySelector('.direct-answer')); assert.deepEqual(app.evidence(), []);
});

test('mounted direct answer arrives before slow evidence, discloses exact provenance, and survives evidence failure', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const query = "What was Apple's latest quarterly revenue?";
  const pendingEvidence = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  const answer = app.host.querySelector('.direct-answer');
  assert.match(answer.textContent, /Research Answer.*\$109\.42B/);
  assert.deepEqual(app.evidence(), [], 'Direct answer is usable while evidence is still pending');
  const disclosure = answer.querySelector('details');
  assert.equal(disclosure.open, false);
  await act(async () => disclosure.querySelector('summary').click());
  assert.equal(disclosure.open, true);
  assert.match(disclosure.textContent, /Exact API value:.*109417000000 USD/);
  assert.match(disclosure.textContent, /Accession AAPL-test-accession/);
  assert.equal(disclosure.querySelector('a').href, filing('AAPL').sec_url);
  await app.release(pendingEvidence, { detail: 'Local evidence failure fixture' }, 500);
  assert.match(app.host.querySelector('.direct-answer').textContent, /\$109\.42B/);
  assert.match(app.host.querySelector('[role="alert"]').textContent, /Local evidence failure/);
  assert.equal(app.requests.filter(request => request.path.endsWith('/answer')).length, 0);
});

test('mounted unavailable answer explains source incompatibility before supporting evidence', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const query = 'latest quarterly revenue growth';
  const evidence = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query, 'unavailable'));
  await app.release(evidence, context('AAPL', query));
  const answer = app.host.querySelector('.direct-answer');
  assert.match(answer.textContent, /Unavailable.*economic bases are not explicitly comparable/);
  assert.doesNotMatch(answer.textContent, /\$0|\$109/);
  assert.ok(answer.compareDocumentPosition(app.host.querySelector('.evidence-card')) & Node.DOCUMENT_POSITION_FOLLOWING);
});

test('mounted answer failure preserves evidence fallback without a fabricated direct result', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const query = "What is Apple's main product?";
  const evidence = await app.search('AAPL', query, true);
  await app.release(evidence, context('AAPL', query));
  await app.release(app.request(companyPath('AAPL', 'research-answer')), { detail: 'Answer fixture unavailable' }, 503);
  assert.match(app.evidence().join(''), /AAPL test evidence/);
  assert.ok(!app.host.querySelector('.direct-answer'));
  assert.match(app.host.textContent, /Direct financial answer unavailable/);
});

test('mounted optional AI failure retains both deterministic answer and SEC evidence', async ctx => {
  const app = await mount(ctx, true);
  await app.completeCompany('AAPL', '1000000000');
  const query = 'latest quarterly revenue';
  const evidence = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  await app.release(evidence, context('AAPL', query));
  const priorAnswer = app.host.querySelector('.direct-answer').textContent;
  const priorEvidence = app.evidence();
  await app.click('Generate AI analysis');
  await app.release(app.request(companyPath('AAPL', `filings/${filing('AAPL').accession_number}/answer`)), { detail: 'Test provider failure' }, 502);
  assert.equal(app.host.querySelector('.direct-answer').textContent, priorAnswer);
  assert.deepEqual(app.evidence(), priorEvidence);
});

test('mounted company switch removes completed answer and rejects pending old answer even if cancellation is ignored', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const query = 'latest revenue';
  const evidence = await app.search('AAPL', query, true);
  await app.release(evidence, context('AAPL', query));
  const oldAnswer = app.request(companyPath('AAPL', 'research-answer'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  assert.equal(oldAnswer.init.signal.aborted, true);
  await app.release(oldAnswer, directAnswer('AAPL', query));
  assert.ok(!app.host.querySelector('.direct-answer'));
  await app.completeCompany('JPM', '2000000000');
  const newEvidence = await app.search('JPM', query, true);
  await app.release(app.request(companyPath('JPM', 'research-answer')), directAnswer('JPM', query));
  await app.release(newEvidence, context('JPM', query));
  assert.match(app.host.querySelector('.direct-answer').textContent, /JPM fixture/);
  assert.doesNotMatch(app.host.querySelector('.direct-answer').textContent, /AAPL/);
  await app.change(app.host.querySelector('#company'), 'AAPL');
  assert.ok(!app.host.querySelector('.direct-answer'), 'Completed answer disappears immediately on switch');
});

test('mounted query edit rejects late direct answer and company mismatch displays guidance', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const query = 'latest revenue';
  const evidence = await app.search('AAPL', query, true);
  const oldAnswer = app.request(companyPath('AAPL', 'research-answer'));
  await app.change(app.host.querySelector('textarea'), 'gross margin');
  await app.release(oldAnswer, directAnswer('AAPL', query));
  await app.release(evidence, context('AAPL', query));
  assert.ok(!app.host.querySelector('.direct-answer'));
  assert.deepEqual(app.evidence(), []);
  const mismatchQuery = "What was Microsoft's revenue?";
  const nextEvidence = await app.search('AAPL', mismatchQuery, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), { ticker: 'AAPL', question: mismatchQuery, matched: false, status: 'company_mismatch', explanation: 'This workspace is selected for Apple fixture. Select Microsoft to research it.' });
  await app.release(nextEvidence, context('AAPL', mismatchQuery));
  assert.ok(!app.host.querySelector('.direct-answer'));
  assert.match(app.host.textContent, /This workspace is selected for Apple/);
});

test('mounted company with no indexed filing can receive a direct answer without context or AI requests', async ctx => {
  const app = await mount(ctx, false, [{ ...companies[0], has_indexed_filing: false, indexed_filing_count: 0 }]);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), summary('AAPL', '1000000000'));
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '1000000000'));
  await app.release(app.request(companyPath('AAPL', 'sources')), []);
  assert.match(app.host.textContent, /Not indexed for filing research/);
  const query = 'latest quarterly revenue';
  await app.change(app.host.querySelector('textarea'), query);
  await app.click('Research question');
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  assert.match(app.host.querySelector('.direct-answer').textContent, /\$109\.42B/);
  assert.equal(app.requests.filter(request => /\/context$|\/answer$/.test(request.path)).length, 0);
});


function freshnessFixture(ticker, version, evidenceVersion = 0) {
  const stream = { status: "current", last_checked_at: "2026-10-08T06:00:00Z", last_successful_sync_at: "2026-10-08T06:00:00Z",
    latest_source_filing_date: "2025-05-01", pending_targets: [], inventory_complete: true, last_error: null, failure_stage: null };
  return { ticker, data_version: version, facts_version: version, evidence_version: evidenceVersion,
    status: "current", facts: stream, evidence: stream, latest_indexed_filing: null, migration_required: false,
    scope: "Synthetic offline latest-Q/K test inventory" };
}
async function focusCheck() {
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  await act(async () => window.dispatchEvent(new Event('focus')));
}
const latestRequest = (app, path) => app.requests.filter(item => !item.released && item.path === path).at(-1);

const dependentRequests = app => app.requests.filter(item => item.path.startsWith('/companies/') && !item.path.endsWith('/freshness'));

for (const strict of [false, true]) for (const version of [1, 0]) {
  test(`mounted initialization waits for actual version ${version}${strict ? ' under StrictMode' : ''}`, async ctx => {
    const app = await mount(ctx, false, companies, { initialVersion: null, strict });
    assert.equal(dependentRequests(app).length, 0, 'UNKNOWN must never invent a version-0 pin');
    assert.match(app.host.querySelector('[aria-label="Data freshness"]').textContent, /Stored data · unknown/);
    await app.change(app.select('Snapshot period'), 'annual');
    await app.change(app.select('Metric'), 'net_income');
    await app.change(app.select('Evidence search scope'), 'company');
    const textarea = app.host.querySelector('textarea');
    assert.ok(textarea, 'Question can be prepared while freshness is pending');
    await app.change(textarea, '2024 revenue');
    const button = app.host.querySelector('.search-form button.primary-button');
    assert.equal(button.disabled, true);
    await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    await focusCheck(); await focusCheck();
    assert.equal(dependentRequests(app).length, 0, 'Delayed freshness also gates user-submitted requests');
    assert.equal(app.requests.filter(r => r.path.endsWith('/freshness') && !r.init.signal.aborted).length, 1);
    await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version));
    assert.equal(dependentRequests(app).length, 3, 'One snapshot, history and sources fan-out');
    assert.ok(dependentRequests(app).every(r => r.init.headers['X-FinLens-Data-Version'] === String(version)));
    await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), summary('AAPL', '4000000000', 'annual'));
    await app.release(app.request(companyPath('AAPL', 'financials/metrics/net_income')), history('AAPL', '300000000', 'net_income'));
    await app.release(app.request(companyPath('AAPL', 'sources')), [filing('AAPL')]);
    assert.match(app.snapshot().textContent, /\$4B/); assert.match(app.trends().textContent, /\$300M/);
    await app.click('Research question');
    assert.equal(app.request(companyPath('AAPL', 'research-answer')).init.headers['X-FinLens-Data-Version'], String(version));
    assert.equal(app.request(companyPath('AAPL', 'context')).init.headers['X-FinLens-Data-Version'], String(version));
    const count = dependentRequests(app).length;
    await focusCheck();
    await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version));
    assert.equal(dependentRequests(app).length, count, 'Unchanged freshness must not duplicate or abort research');
    assert.equal(app.request(companyPath('AAPL', 'research-answer')).init.signal.aborted, false);
  });
}

test('mounted failed initial freshness stays unpinned until a later check succeeds', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null });
  await app.release(app.request(companyPath('AAPL', 'freshness')), { detail: 'private failure' }, 503);
  assert.equal(dependentRequests(app).length, 0);
  assert.match(app.host.textContent, /Freshness check unavailable/);
  assert.doesNotMatch(app.host.textContent, /private failure|version 0/);
  await app.change(app.select('Snapshot period'), 'half_year');
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), { detail: 'still unavailable' }, 503);
  assert.equal(dependentRequests(app).length, 0, 'Failure cannot authorize an invented fallback');
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(dependentRequests(app).length, 3);
  assert.equal(app.request(companyPath('AAPL', 'financials/summary')).params.get('period'), 'half_year');
  assert.ok(dependentRequests(app).every(r => r.init.headers['X-FinLens-Data-Version'] === '1'));
});

for (const version of [null, undefined, -1, '1', 1.5]) test(`mounted invalid initial publication version ${JSON.stringify(version)} remains unknown`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null });
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version));
  assert.equal(dependentRequests(app).length, 0);
  assert.match(app.host.textContent, /Freshness check unavailable/);
});

test('mounted rapid company switches establish fresh pins and discard cancelled initial checks', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null, strict: true });
  const oldApple = app.request(companyPath('AAPL', 'freshness'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  const oldJpm = app.request(companyPath('JPM', 'freshness'));
  await app.change(app.host.querySelector('#company'), 'AAPL');
  const apple = app.request(companyPath('AAPL', 'freshness'));
  assert.equal(dependentRequests(app).length, 0);
  assert.equal(oldApple.init.signal.aborted, true); assert.equal(oldJpm.init.signal.aborted, true);
  await app.release(oldApple, freshnessFixture('AAPL', 9));
  await app.release(oldJpm, freshnessFixture('JPM', 7));
  assert.equal(dependentRequests(app).length, 0);
  await focusCheck();
  assert.equal(app.request(companyPath('AAPL', 'freshness')), apple, 'Cancelled completion must not unlock active check');
  await app.release(apple, freshnessFixture('AAPL', 1));
  await app.completeCompany('AAPL', '1000000000');
  assert.ok(dependentRequests(app).every(r => r.path.includes('/AAPL/') && r.init.headers['X-FinLens-Data-Version'] === '1'));
  assert.match(app.snapshot().textContent, /\$1B/);
  assert.doesNotMatch(app.host.querySelector('[aria-label="Data freshness"]').textContent, /version [79]/);
});

test('mounted company switch does not borrow the previous known publication version', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: 1 });
  const old = dependentRequests(app);
  await app.change(app.host.querySelector('#company'), 'JPM');
  assert.ok(old.every(r => r.init.signal.aborted));
  assert.equal(dependentRequests(app).length, 3, 'New company stays unknown until its own freshness resolves');
  await app.release(app.request(companyPath('JPM', 'freshness')), freshnessFixture('JPM', 0));
  assert.equal(dependentRequests(app).length, 6);
  assert.ok(dependentRequests(app).slice(3).every(r => r.path.includes('/JPM/') && r.init.headers['X-FinLens-Data-Version'] === '0'));
  await app.completeCompany('JPM', '2000000000');
  for (const req of old) await app.release(req, { detail: 'Obsolete response' }, 409, 9);
  assert.match(app.snapshot().textContent, /\$2B/);
  assert.equal(app.requests.filter(r => !r.released && !r.init.signal.aborted && r.path.endsWith('/freshness')).length, 0, 'Cancelled mismatches do not refresh the new company');
});

test('mounted concurrent 409 responses coalesce reconciliation and never retry the obsolete pin', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: 1 });
  const old = dependentRequests(app);
  for (const req of old) await app.release(req, { detail: 'Published data changed' }, 409, 2);
  assert.equal(app.requests.filter(r => !r.released && r.path.endsWith('/freshness')).length, 1);
  assert.equal(dependentRequests(app).length, 3, 'No unpinned or obsolete immediate retry');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 2));
  // The first 409 settled before cancellation; its transport listener was removed.
  assert.equal(old[0].init.signal.aborted, false);
  assert.ok(old.slice(1).every(r => r.init.signal.aborted));
  assert.equal(dependentRequests(app).length, 6);
  assert.ok(dependentRequests(app).slice(3).every(r => r.init.headers['X-FinLens-Data-Version'] === '2'));
  await app.completeCompany('AAPL', '2000000000');
  assert.match(app.snapshot().textContent, /\$2B/); assert.match(app.trends().textContent, /\$2B/);
  const count = dependentRequests(app).length;
  for (const payload of [freshnessFixture('JPM', 8), freshnessFixture('AAPL', 1)]) {
    await focusCheck(); await app.release(app.request(companyPath('AAPL', 'freshness')), payload);
    assert.equal(dependentRequests(app).length, count, 'Wrong company or regressed versions cannot refetch research');
    assert.match(app.host.querySelector('[aria-label="Data freshness"]').textContent, /version 2/);
  }
});

const cashMetrics = ['operating_cash_flow', 'capital_expenditures', 'free_cash_flow'];
function cashSnapshot(ticker, kind = 'quarter', values = {}) {
  const result = summary(ticker, '1000000000', kind);
  result.period = { ...result.period, end: { quarter: '2025-03-31', half_year: '2025-06-30', nine_months: '2025-09-30', annual: '2025-12-31' }[kind] };
  result.metrics.revenue.period = result.period;
  for (const metric of cashMetrics) {
    const value = values[metric];
    result.metrics[metric] = { ...point(ticker, value ?? null, metric, kind), period: result.period,
      status: value == null ? 'unavailable' : 'available', reason: value == null ? 'No compatible inputs for this period.' : null };
  }
  return result;
}
const cashHints = app => [...app.snapshot().querySelectorAll('.cash-flow-alternative')];

test('mounted cash-flow alternatives confirm YTD, preserve quarter values and reuse the existing selector/cache', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  assert.equal(cashHints(app).length, 0, 'No speculative hints before the response');
  const half = app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' });
  assert.equal(half.init.headers['X-FinLens-Data-Version'], '0');
  await app.release(half, cashSnapshot('AAPL', 'half_year', { operating_cash_flow: '800000000', capital_expenditures: '200000000', free_cash_flow: '600000000' }), 200, 0);
  assert.equal(cashHints(app).length, 3);
  assert.match(cashHints(app)[0].textContent, /Operating cash flow.*Half-year YTD.*Jun 30, 2025/);
  assert.match(app.snapshot().querySelector('.period-label').textContent, /^Direct quarter/);
  assert.match(app.snapshot().querySelector('.secondary-metrics:last-child').textContent, /Free cash flowUnavailable/);
  assert.match(app.snapshot().querySelector('.metric-grid').textContent, /Revenue\$1B/);
  assert.deepEqual([...app.select('Snapshot period').options].map(option => option.value), ['quarter', 'half_year', 'nine_months', 'annual']);
  const count = app.requests.length;
  await app.change(app.select('Snapshot period'), 'half_year');
  assert.equal(app.requests.length, count, 'Selecting a confirmed mode reuses its snapshot');
  assert.equal(cashHints(app).length, 0);
  assert.match(app.snapshot().querySelector('.period-label').textContent, /^Half-year YTD.*Jun 30, 2025/);
  assert.match(app.snapshot().querySelector('.secondary-metrics:last-child').textContent, /Free cash flow\$600M/);
  await app.change(app.select('Snapshot period'), 'quarter');
  assert.equal(app.requests.length, count, 'Returning to quarter does not refetch or rediscover');
  assert.equal(cashHints(app).length, 3);
  assert.match(app.snapshot().querySelector('.secondary-metrics:last-child').textContent, /Free cash flowUnavailable/);
});

test('mounted cash-flow alternatives ignore invalid values/units/periods and failed or wrong-company responses', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  const invalid = cashSnapshot('AAPL', 'half_year', { operating_cash_flow: 'NaN', capital_expenditures: '20', free_cash_flow: '60' });
  invalid.metrics.capital_expenditures.unit = 'USD/shares';
  invalid.metrics.free_cash_flow.period = { ...invalid.period, kind: 'quarter' };
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' }), invalid);
  assert.equal(cashHints(app).length, 0);
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'nine_months' }), cashSnapshot('JPM', 'nine_months', { free_cash_flow: '99' }));
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), { detail: 'Unavailable' }, 503);
  assert.equal(cashHints(app).length, 0);
  assert.match(app.snapshot().querySelector('.secondary-metrics:last-child').textContent, /Free cash flowUnavailable/);
  assert.match(app.snapshot().textContent, /Revenue\$1B/);
  assert.ok(!app.snapshot().querySelector('[role="alert"]'), 'Optional lookup failure preserves the main snapshot');
});

test('mounted cash-flow alternatives find annual data only after unavailable YTD modes without automatically switching', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL', 'quarter', { operating_cash_flow: '80', capital_expenditures: '20' }));
  for (const mode of ['half_year', 'nine_months']) {
    await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: mode }), cashSnapshot('AAPL', mode));
    assert.equal(cashHints(app).length, 0);
  }
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), cashSnapshot('AAPL', 'annual', { free_cash_flow: '600000000' }));
  assert.equal(cashHints(app).length, 1);
  assert.match(cashHints(app)[0].textContent, /Free cash flow.*Annual.*Dec 31, 2025/);
  assert.equal(app.select('Snapshot period').value, 'quarter');
  const count = app.requests.length;
  await app.change(app.select('Snapshot period'), 'annual');
  assert.equal(app.requests.length, count);
  assert.match(app.snapshot().querySelector('.period-label').textContent, /^Annual/);
});

test('mounted available cash-flow metrics do not trigger alternative requests', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL', 'quarter', { operating_cash_flow: '80', capital_expenditures: '20', free_cash_flow: '60' }));
  assert.equal(cashHints(app).length, 0);
  assert.equal(app.requests.filter(item => item.path.endsWith('/financials/summary')).length, 1);
});

test('mounted cash-flow alternatives require a confirmed published version', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  for (const mode of ['half_year', 'nine_months', 'annual']) {
    await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: mode }), cashSnapshot('AAPL', mode, { operating_cash_flow: '80', capital_expenditures: '20', free_cash_flow: '60' }), 200, null);
  }
  assert.equal(cashHints(app).length, 0);
  assert.match(app.snapshot().querySelector('.secondary-metrics:last-child').textContent, /Free cash flowUnavailable/);
});

test('mounted selecting an alternative while discovery is pending shares its request without stale hints', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  const pending = app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' });
  const count = app.requests.length;
  await app.change(app.select('Snapshot period'), 'half_year');
  assert.equal(app.requests.length, count);
  assert.equal(pending.init.signal.aborted, false);
  await app.release(pending, cashSnapshot('AAPL', 'half_year', { operating_cash_flow: '800000000', capital_expenditures: '200000000', free_cash_flow: '600000000' }));
  assert.match(app.snapshot().querySelector('.period-label').textContent, /^Half-year YTD/);
  assert.equal(cashHints(app).length, 0);
  assert.match(app.snapshot().querySelector('.secondary-metrics:last-child').textContent, /Operating cash flow\$800M.*Capital expenditures\$200M.*Free cash flow\$600M/);
});

test('mounted delayed alternative responses cannot cross companies', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  const old = app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' });
  await app.change(app.host.querySelector('#company'), 'JPM');
  await app.completeCompany('JPM', '2000000000');
  assert.equal(old.init.signal.aborted, true);
  await app.release(old, cashSnapshot('AAPL', 'half_year', { operating_cash_flow: '80', capital_expenditures: '20', free_cash_flow: '60' }));
  assert.equal(cashHints(app).length, 0);
  assert.match(app.snapshot().textContent, /Revenue\$2B/);
});

test('mounted alternative hints and cache invalidate on version changes and reject delayed old responses', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' }), cashSnapshot('AAPL', 'half_year', { operating_cash_flow: '80' }), 200, 0);
  assert.equal(cashHints(app).length, 1);
  const old = app.request(companyPath('AAPL', 'financials/summary'), { period: 'nine_months' });
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(cashHints(app).length, 0);
  assert.equal(old.init.signal.aborted, true);
  await app.release(old, cashSnapshot('AAPL', 'nine_months', { capital_expenditures: '20', free_cash_flow: '60' }), 200, 0);
  const freshQuarter = app.request(companyPath('AAPL', 'financials/summary'), { period: 'quarter' });
  assert.equal(freshQuarter.init.headers['X-FinLens-Data-Version'], '1');
  await app.release(freshQuarter, cashSnapshot('AAPL'), 200, 1);
  for (const mode of ['half_year', 'nine_months', 'annual']) {
    const request = app.request(companyPath('AAPL', 'financials/summary'), { period: mode });
    assert.equal(request.init.headers['X-FinLens-Data-Version'], '1');
    await app.release(request, cashSnapshot('AAPL', mode), 200, 1);
  }
  assert.equal(cashHints(app).length, 0, 'Old confirmed availability is not reused for version 1');
});

test('mounted alternative responses with a different published version cannot confirm hints', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' }), cashSnapshot('AAPL', 'half_year', { operating_cash_flow: '80', capital_expenditures: '20', free_cash_flow: '60' }), 200, 1);
  assert.equal(cashHints(app).length, 0);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(cashHints(app).length, 0);
});

test('mounted published-version change rejects delayed old summary history and sources', async ctx => {
  const app = await mount(ctx);
  const oldSummary = app.request(companyPath('AAPL', 'financials/summary'));
  const oldHistory = app.request(companyPath('AAPL', 'financials/metrics/revenue'));
  const oldSources = app.request(companyPath('AAPL', 'sources'));
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  await app.release(latestRequest(app, companyPath('AAPL', 'financials/summary')), summary('AAPL', '2000000000'), 200, 1);
  await app.release(latestRequest(app, companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '2000000000'), 200, 1);
  await app.release(latestRequest(app, companyPath('AAPL', 'sources')), [filing('AAPL')], 200, 1);
  for (const [pending, value] of [[oldSummary, summary('AAPL', '1000000000')], [oldHistory, history('AAPL', '1000000000')], [oldSources, [filing('AAPL')]]]) {
    assert.equal(pending.init.signal.aborted, true);
    await app.release(pending, value, 200, 0);
    assert.match(app.snapshot().textContent, /\$2B/); assert.doesNotMatch(app.snapshot().textContent, /\$1B/);
    assert.match(app.trends().textContent, /\$2B/);
  }
  assert.match(app.host.querySelector('[aria-label="Data freshness"]').textContent, /version 1/);
});

test('mounted version invalidation preserves query while clearing answer evidence and pending AI', async ctx => {
  const app = await mount(ctx, true);
  await app.completeCompany('AAPL', '1000000000');
  const question = 'latest quarterly revenue';
  const evidenceRequest = await app.search('AAPL', question, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', question));
  await app.release(evidenceRequest, context('AAPL', question));
  await app.click('Generate AI analysis');
  const oldAI = app.request(companyPath('AAPL', `filings/${filing('AAPL').accession_number}/answer`));
  const before = app.requests.filter(item => item.path.endsWith('/research-answer')).length;
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(app.host.querySelector('textarea').value, question);
  assert.deepEqual(app.evidence(), []); assert.ok(!app.host.querySelector('.direct-answer'));
  assert.match(app.host.textContent, /Data updated; research this question again/);
  assert.equal(oldAI.init.signal.aborted, true);
  await app.release(oldAI, { answer: 'OLD AI MUST NOT RENDER', claims: [], citations: [], evidence_status: 'sufficient' }, 200, 0);
  assert.doesNotMatch(app.host.textContent, /OLD AI MUST NOT RENDER/);
  assert.equal(app.requests.filter(item => item.path.endsWith('/research-answer')).length, before, 'No auto-answer or AI replay');
});

test('mounted pending answer and evidence cannot cross a same-company data version', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const question = 'latest quarterly revenue';
  const oldContext = await app.search('AAPL', question, true);
  const oldAnswer = app.request(companyPath('AAPL', 'research-answer'));
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 2));
  assert.equal(oldContext.init.signal.aborted, true); assert.equal(oldAnswer.init.signal.aborted, true);
  await app.release(oldAnswer, directAnswer('AAPL', question), 200, 0);
  await app.release(oldContext, context('AAPL', question), 200, 0);
  assert.deepEqual(app.evidence(), []);
  assert.doesNotMatch(app.host.textContent, /AAPL test evidence/);
  assert.ok(!app.host.querySelector('.direct-answer'));
});

test('mounted no-change freshness and failed checks preserve usable research without duplicate fan-out', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const previous = app.requests.filter(item => !item.path.endsWith('/freshness')).length;
  await focusCheck(); await focusCheck();
  assert.equal(app.requests.filter(item => !item.released && item.path.endsWith('/freshness')).length, 1, 'Focus checks coalesce');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
  assert.equal(app.requests.filter(item => !item.path.endsWith('/freshness')).length, previous);
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), { detail: 'private failure' }, 503);
  assert.match(app.snapshot().textContent, /\$1B/);
  assert.match(app.host.textContent, /Freshness check unavailable/);
  assert.doesNotMatch(app.host.textContent, /private failure/);
});

test('mounted version refresh preserves period metric and explicit filing controls', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  await app.change(app.select('Snapshot period'), 'annual');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), summary('AAPL', '4000000000', 'annual'));
  await app.change(app.select('Metric'), 'net_income');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/net_income')), history('AAPL', '300000000', 'net_income'));
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(app.select('Snapshot period').value, 'annual'); assert.equal(app.select('Metric').value, 'net_income');
  const pendingSummary = latestRequest(app, companyPath('AAPL', 'financials/summary'));
  assert.equal(pendingSummary.params.get('period'), 'annual');
  assert.equal(pendingSummary.init.headers['X-FinLens-Data-Version'], '1');
  await app.release(pendingSummary, summary('AAPL', '5000000000', 'annual'), 200, 1);
  await app.release(latestRequest(app, companyPath('AAPL', 'sources')), [filing('AAPL')], 200, 1);
  assert.equal(app.select('Indexed SEC filing').value, filing('AAPL').accession_number);
  assert.match(app.snapshot().textContent, /\$5B/);
});

test('mounted delayed freshness from a previous company cannot replace current version', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null });
  const old = app.request(companyPath('AAPL', 'freshness'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  await app.completeCompany('JPM', '2000000000');
  assert.equal(old.init.signal.aborted, true);
  await app.release(old, freshnessFixture('AAPL', 9));
  assert.match(app.host.querySelector('#company-title').textContent, /JPM/);
  assert.match(app.snapshot().textContent, /\$2B/);
  assert.doesNotMatch(app.host.querySelector('[aria-label="Data freshness"]').textContent, /version 9/);
});

test('mounted StrictMode freshness cleanup restarts checking and stale completions do not unlock a newer request', async ctx => {
  const previousFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = (url, init) => new Promise(resolve => requests.push({url, init, resolve}));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  ctx.after(async () => { await act(async () => root.unmount()); host.remove(); globalThis.fetch = previousFetch; });
  await act(async () => root.render(React.createElement(React.StrictMode, null,
    React.createElement(ResearchFreshness, {ticker:'AAPL',catalogChanged:()=>{}}, 'Stored research'))));
  assert.equal(requests.length, 2, 'StrictMode setup after cleanup must immediately recheck');
  assert.equal(requests[0].init.signal.aborted, true);
  const finish = async (request, version) => act(async () => request.resolve(new Response(
    JSON.stringify(freshnessFixture('AAPL', version)), {status:200,headers:{'Content-Type':'application/json'}})));
  await finish(requests[1], 1);
  assert.match(host.textContent, /version 1/);
  await focusCheck(); assert.equal(requests.length, 3);
  await finish(requests[0], 9); // Transport deliberately ignores cancellation.
  await focusCheck(); assert.equal(requests.length, 3, 'Old finally must not release current admission');
  await finish(requests[2], 2);
  assert.match(host.textContent, /version 2/); assert.doesNotMatch(host.textContent, /version 9/);
});

test('mounted first published evidence version reconciles stale catalog readiness exactly once', async ctx => {
  const app = await mount(ctx, false, [{...companies[0],has_indexed_filing:false,indexed_filing_count:0}]);
  await app.completeCompany('AAPL','1000000000');
  assert.match(app.host.textContent, /Not indexed for filing research/);
  await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',1,1));
  await app.release(app.request('/companies'), [companies[0]]);
  await app.release(latestRequest(app,companyPath('AAPL','sources')), [filing('AAPL')],200,1);
  assert.equal(app.select('Indexed SEC filing').disabled,false);
  assert.equal(app.select('Indexed SEC filing').value,filing('AAPL').accession_number);
  assert.match(app.host.textContent, /1 indexed filing/);
  await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',1,1));
  assert.equal(app.requests.filter(r=>r.path==='/companies').length,2,'Only initial load plus one reconciliation');
});

test('mounted failed catalog reconciliation retries the same version and preserves company and question', async ctx => {
  const app = await mount(ctx, false, [{...companies[0],has_indexed_filing:false,indexed_filing_count:0}]);
  await app.release(app.request(companyPath('AAPL','financials/summary')), summary('AAPL','1000000000'));
  await app.release(app.request(companyPath('AAPL','financials/metrics/revenue')), history('AAPL','1000000000'));
  await app.release(app.request(companyPath('AAPL','sources')), []);
  await app.change(app.host.querySelector('textarea'), 'How much revenue did Apple report?');
  await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',1,1));
  await app.release(app.request('/companies'), {detail:'private transient failure'},503);
  await app.release(latestRequest(app,companyPath('AAPL','sources')), [filing('AAPL')],200,1);
  assert.equal(app.select('Indexed SEC filing').disabled,true);
  assert.match(app.host.textContent,/Filing availability check pending/);
  assert.doesNotMatch(app.host.textContent,/private transient failure/);
  assert.equal(app.requests.filter(r=>r.path==='/companies').length,2,'No immediate retry loop');
  await focusCheck(); await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',1,1));
  const retry = app.request('/companies');
  await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',1,1));
  assert.equal(app.requests.filter(r=>r.path==='/companies').length,3,'One catalog reconciliation in flight');
  await app.release(retry,[companies[0]]);
  assert.equal(app.select('Indexed SEC filing').disabled,false);
  assert.equal(app.select('Indexed SEC filing').value,filing('AAPL').accession_number);
  assert.equal(app.host.querySelector('#company').value,'AAPL');
  assert.equal(app.host.querySelector('textarea').value,'How much revenue did Apple report?');
  assert.doesNotMatch(app.host.textContent,/Filing availability check pending|Not indexed for filing research/);
  await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',1,1));
  assert.equal(app.requests.filter(r=>r.path==='/companies').length,3,'Successful reconciliation is acknowledged');
});

test('mounted catalog reconciliation from an old company cannot overwrite a newer catalog', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL','1000000000');
  await focusCheck();
  await app.release(app.request(companyPath('AAPL','freshness')),freshnessFixture('AAPL',1,1));
  const oldCatalog = app.request('/companies');
  await app.change(app.host.querySelector('#company'),'JPM');
  assert.equal(oldCatalog.init.signal.aborted,true);
  await app.completeCompany('JPM','2000000000');
  await focusCheck();
  await app.release(app.request(companyPath('JPM','freshness')),freshnessFixture('JPM',1,1));
  await app.release(latestRequest(app,'/companies'),companies);
  await app.release(oldCatalog,[{...companies[0],name:'STALE CATALOG MUST NOT RENDER'}]);
  assert.equal(app.host.querySelector('#company').value,'JPM');
  assert.match(app.host.querySelector('#company-title').textContent,/JPM/);
  assert.doesNotMatch(app.host.textContent,/STALE CATALOG MUST NOT RENDER/);
  await focusCheck();
  await app.release(app.request(companyPath('JPM','freshness')),freshnessFixture('JPM',1,1));
  assert.equal(app.requests.filter(r=>r.path==='/companies').length,3);
});

// FR-01: controlled failures and manually admitted recovery, with no live services.
async function retryTwice(app, label) {
  const button = [...app.host.querySelectorAll('button')].find(item => item.textContent === label);
  assert.ok(button, `${label} is rendered`);
  assert.equal(button.type, 'button'); assert.equal(button.tabIndex, 0); assert.equal(button.disabled, false);
  button.focus(); assert.equal(document.activeElement, button);
  await act(async () => { button.click(); button.click(); });
}

for (const strict of [false, true]) test(`FR-01 catalog manual retry is bounded and does not reload capabilities${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mount(ctx, false, companies, { catalogStatus: 503, strict });
  assert.match(app.host.textContent, /Could not load the company list/);
  assert.equal(dependentRequests(app).length, 0);
  const capabilitiesCount = app.requests.filter(r => r.path === '/capabilities').length;
  const catalogCount = app.requests.filter(r => r.path === '/companies').length;
  await retryTwice(app, 'Retry companies');
  assert.equal(app.requests.filter(r => r.path === '/companies').length, catalogCount + 1);
  assert.equal(app.requests.filter(r => r.path === '/capabilities').length, capabilitiesCount);
  await app.release(app.request('/companies'), companies);
  assert.equal(app.host.querySelector('#company').value, 'AAPL');
  assert.equal(app.host.querySelector('#company').disabled, false);
  assert.equal(dependentRequests(app).length, 0, 'Catalog recovery does not invent a pin');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  await app.completeCompany('AAPL', '1000000000');
  assert.match(app.snapshot().textContent, /\$1B/);
});

test('FR-01 cancelled StrictMode catalog completion cannot replace retry or unlock another attempt', async ctx => {
  const app = await mount(ctx, false, companies, { catalogStatus: 503, strict: true });
  const obsolete = app.requests.find(r => r.path === '/companies' && r.init.signal.aborted);
  await retryTwice(app, 'Retry companies');
  const retry = app.request('/companies');
  await app.release(obsolete, [companies[1]]);
  assert.equal(app.host.querySelector('#company').value, '');
  await app.release(retry, { detail: 'Still unavailable' }, 503);
  await retryTwice(app, 'Retry companies');
  await app.release(app.request('/companies'), companies);
  assert.equal(app.host.querySelector('#company').value, 'AAPL');
});

for (const strict of [false, true]) for (const version of [0, 1]) test(`FR-01 freshness manual recovery verifies ${version}${strict ? ' in StrictMode' : ''} before fan-out`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null, strict });
  await app.release(app.request(companyPath('AAPL', 'freshness')), { detail: 'Private fixture' }, 503);
  assert.match(app.host.textContent, /Could not verify this company’s data version/);
  assert.doesNotMatch(app.host.textContent, /Already loaded research remains available|Previously stored research remains usable/);
  await app.change(app.select('Snapshot period'), 'annual');
  await app.change(app.select('Metric'), 'net_income');
  const textarea = app.host.querySelector('textarea');
  await app.change(textarea, '2024 revenue');
  await retryTwice(app, 'Retry data check');
  const pending = app.request(companyPath('AAPL', 'freshness'));
  await focusCheck(); await focusCheck();
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(dependentRequests(app).length, 0);
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness') && !r.released && !r.init.signal.aborted).length, 1);
  await app.release(pending, freshnessFixture('AAPL', version));
  assert.equal(dependentRequests(app).length, 3);
  assert.ok(dependentRequests(app).every(r => r.init.headers['X-FinLens-Data-Version'] === String(version)));
  assert.equal(app.select('Snapshot period').value, 'annual');
  assert.equal(app.select('Metric').value, 'net_income');
  assert.equal(app.host.querySelector('textarea'), textarea);
  assert.equal(textarea.value, '2024 revenue');
});

for (const invalid of [null, undefined, -1, '1', 1.5, Number.MAX_SAFE_INTEGER + 1, 'wrong-company']) test(`FR-01 manual freshness retry remains closed for ${String(invalid)}`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null });
  const bad = invalid === 'wrong-company' ? freshnessFixture('JPM', 1) : freshnessFixture('AAPL', invalid);
  await app.release(app.request(companyPath('AAPL', 'freshness')), bad);
  await retryTwice(app, 'Retry data check');
  await app.release(app.request(companyPath('AAPL', 'freshness')), bad);
  assert.equal(dependentRequests(app).length, 0);
  assert.equal(app.host.querySelector('.search-form button.primary-button').disabled, true);
  assert.match(app.host.textContent, /Could not verify this company’s data version/);
  await app.click('Retry data check');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
  assert.ok(dependentRequests(app).every(r => r.init.headers['X-FinLens-Data-Version'] === '0'));
});

test('FR-01 freshness retry cannot cross rapid company switching', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: null });
  await app.release(app.request(companyPath('AAPL', 'freshness')), {}, 503);
  await app.click('Retry data check');
  const old = app.request(companyPath('AAPL', 'freshness'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  assert.equal(old.init.signal.aborted, true);
  await app.release(old, freshnessFixture('AAPL', 7));
  assert.equal(dependentRequests(app).length, 0);
  await app.release(app.request(companyPath('JPM', 'freshness')), freshnessFixture('JPM', 1));
  assert.ok(dependentRequests(app).every(r => r.path.includes('/JPM/') && r.init.headers['X-FinLens-Data-Version'] === '1'));
});

test('FR-01 a mismatch supersedes an earlier freshness check and cannot replay a rejected pin', async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: 1 });
  await focusCheck();
  const beforeMismatch = app.request(companyPath('AAPL', 'freshness'));
  const oldSources = app.request(companyPath('AAPL', 'sources'));
  await app.release(oldSources, { detail: 'Publication changed' }, 409, 2);
  assert.equal(beforeMismatch.init.signal.aborted, true);
  const reconciliation = app.request(companyPath('AAPL', 'freshness'));
  await app.release(beforeMismatch, freshnessFixture('AAPL', 1));
  const count = dependentRequests(app).length;
  await app.change(app.host.querySelector('textarea'), 'latest revenue');
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  await focusCheck();
  assert.equal(dependentRequests(app).length, count);
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness') && !r.released && !r.init.signal.aborted).length, 1);
  await app.release(reconciliation, {}, 503);
  await retryTwice(app, 'Retry data check');
  assert.equal(dependentRequests(app).length, count);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 2));
  assert.ok(dependentRequests(app).slice(count).every(r => r.init.headers['X-FinLens-Data-Version'] === '2'));
  assert.equal(app.host.querySelector('textarea').value, 'latest revenue');
});

for (const version of [0, 1]) test(`FR-01 snapshot network failure and manual retry retain period and pin ${version}`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: version });
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '900000000'));
  await app.release(app.request(companyPath('AAPL', 'sources')), []);
  await app.change(app.select('Snapshot period'), 'annual');
  const failed = app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' });
  await act(async () => { failed.released = true; failed.reject(new TypeError('Synthetic network failure')); });
  const count = app.requests.length;
  await retryTwice(app, 'Retry snapshot');
  assert.equal(app.requests.length, count + 1, 'Only the selected snapshot retries');
  const retry = app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' });
  assert.equal(retry.init.headers['X-FinLens-Data-Version'], String(version));
  await app.release(retry, summary('AAPL', '4000000000', 'annual'));
  assert.match(app.snapshot().textContent, /\$4B/);
  assert.match(app.trends().textContent, /\$900M/);
  assert.equal(app.select('Snapshot period').value, 'annual');
  const successful = app.requests.length;
  await app.change(app.select('Snapshot period'), 'quarter');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'quarter' }), summary('AAPL', '1000000000'));
  await app.change(app.select('Snapshot period'), 'annual');
  assert.equal(app.requests.length, successful + 1, 'Successful annual cache is reused');
});

test('FR-01 failed snapshot can recover by returning to its period without automatic eviction requests', async ctx => {
  const app = await mount(ctx);
  const failed = app.request(companyPath('AAPL', 'financials/summary'));
  const count = app.requests.length;
  await app.release(failed, { detail: 'Temporary snapshot failure' }, 503);
  assert.equal(app.requests.length, count, 'Eviction alone cannot fetch');
  await app.change(app.select('Snapshot period'), 'annual');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), summary('AAPL', '4000000000', 'annual'));
  await app.change(app.select('Snapshot period'), 'quarter');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'quarter' }), summary('AAPL', '2000000000'));
  assert.match(app.snapshot().textContent, /\$2B/);
});

test('FR-01 older rejected snapshot cannot evict a pending replacement shared with alternatives', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), cashSnapshot('AAPL'));
  const old = app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' });
  await app.change(app.select('Snapshot period'), 'half_year');
  await app.change(app.select('Snapshot period'), 'quarter');
  const replacement = app.request(companyPath('AAPL', 'financials/summary'), { period: 'half_year' });
  assert.notEqual(old, replacement); assert.equal(old.init.signal.aborted, true);
  await app.release(old, { detail: 'Late rejected old request' }, 503);
  const count = app.requests.length;
  await app.change(app.select('Snapshot period'), 'half_year');
  assert.equal(app.requests.length, count, 'Existing pending replacement must be shared');
  await app.release(replacement, cashSnapshot('AAPL', 'half_year', { operating_cash_flow: '800000000', capital_expenditures: '200000000', free_cash_flow: '600000000' }));
  assert.match(app.snapshot().textContent, /\$800M/);
});

test('FR-01 financially unavailable observations do not acquire transport retry controls', async ctx => {
  const app = await mount(ctx);
  const result = summary('AAPL', null); result.metrics.revenue.status = 'unavailable'; result.metrics.revenue.reason = 'No compatible source';
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), result);
  assert.match(app.snapshot().textContent, /Unavailable/);
  assert.ok(![...app.snapshot().querySelectorAll('button')].some(button => button.textContent === 'Retry snapshot'));
});

for (const strict of [false, true]) for (const version of [0, 1]) test(`FR-01 source failure and recovery preserve direct answer with pin ${version}${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mount(ctx, true, companies, { initialVersion: version, strict });
  await app.release(app.request(companyPath('AAPL', 'sources')), { detail: 'Source discovery failed' }, 503);
  assert.match(app.host.textContent, /Could not load the filing list/);
  assert.doesNotMatch(app.host.textContent, /Not indexed for filing research/);
  const textarea = app.host.querySelector('textarea'); const query = 'latest quarterly revenue';
  await app.change(textarea, query);
  await act(async () => { const form = app.host.querySelector('.search-form'); form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
  assert.equal(app.requests.filter(r => r.path.endsWith('/research-answer')).length, 1);
  const direct = app.request(companyPath('AAPL', 'research-answer'));
  assert.equal(direct.init.headers['X-FinLens-Data-Version'], String(version));
  await app.release(direct, directAnswer('AAPL', query));
  const answer = app.host.querySelector('.direct-answer');
  const disclosure = answer.querySelector('details'); await act(async () => disclosure.querySelector('summary').click());
  const count = app.requests.length;
  await retryTwice(app, 'Retry filing list');
  assert.equal(app.requests.length, count + 1);
  const retry = app.request(companyPath('AAPL', 'sources'));
  assert.equal(retry.init.headers['X-FinLens-Data-Version'], String(version));
  await app.release(retry, [filing('AAPL')]);
  assert.equal(app.host.querySelector('.direct-answer'), answer);
  assert.equal(disclosure.open, true);
  assert.equal(app.host.querySelector('textarea'), textarea); assert.equal(textarea.value, query);
  assert.equal(app.select('Indexed SEC filing').value, filing('AAPL').accession_number);
  assert.equal(app.requests.filter(r => /\/context$|\/answer$/.test(r.path)).length, 0, 'Recovery cannot retrieve or generate');
});

test('FR-01 empty successful source retry is distinct from failure and keeps direct research', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'sources')), {}, 503);
  await app.change(app.host.querySelector('textarea'), 'latest revenue');
  await app.click('Retry filing list');
  await app.release(app.request(companyPath('AAPL', 'sources')), []);
  assert.match(app.host.textContent, /Not indexed for filing research/);
  assert.doesNotMatch(app.host.textContent, /Could not load the filing list/);
  assert.equal(app.host.querySelector('textarea').value, 'latest revenue');
  await app.click('Research question');
  assert.equal(app.requests.filter(r => /\/context$|\/answer$/.test(r.path)).length, 0);
});

test('FR-01 filing change cancels dependent evidence and AI while retaining a direct answer', async ctx => {
  const app = await mount(ctx, true);
  const second = { ...filing('AAPL'), accession_number: 'AAPL-second-accession' };
  await app.release(app.request(companyPath('AAPL', 'sources')), [filing('AAPL'), second]);
  const query = 'latest revenue';
  const evidence = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  await app.release(evidence, context('AAPL', query));
  const answer = app.host.querySelector('.direct-answer');
  await app.click('Generate AI analysis');
  const oldAI = app.request(companyPath('AAPL', `filings/${filing('AAPL').accession_number}/answer`));
  const count = app.requests.length;
  await app.change(app.select('Indexed SEC filing'), second.accession_number);
  assert.equal(oldAI.init.signal.aborted, true);
  assert.deepEqual(app.evidence(), []); assert.ok(!app.host.querySelector('.ai-panel'));
  assert.equal(app.host.querySelector('.direct-answer'), answer);
  assert.equal(app.requests.length, count);
  await app.release(oldAI, { evidence_status: 'sufficient', answer: 'OBSOLETE AI', claims: [], citations: [] });
  assert.doesNotMatch(app.host.textContent, /OBSOLETE AI/);
  await app.click('Research question');
  const pendingEvidence = app.request(companyPath('AAPL', `filings/${second.accession_number}/context`));
  const pendingDirect = app.request(companyPath('AAPL', 'research-answer'));
  await app.change(app.select('Indexed SEC filing'), filing('AAPL').accession_number);
  assert.equal(pendingEvidence.init.signal.aborted, true);
  assert.equal(pendingDirect.init.signal.aborted, false, 'Independent answer still owns a valid company/query/version');
  await app.release(pendingDirect, directAnswer('AAPL', query));
  await app.release(pendingEvidence, { ...context('AAPL', query), accession_number: second.accession_number });
  assert.deepEqual(app.evidence(), []); assert.ok(app.host.querySelector('.direct-answer'));
});

test('FR-01 source recovery cannot revive a direct answer after query, company or publication changes', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'sources')), {}, 503);
  await app.change(app.host.querySelector('textarea'), 'latest revenue'); await app.click('Research question');
  const oldDirect = app.request(companyPath('AAPL', 'research-answer'));
  await app.click('Retry filing list'); const oldSources = app.request(companyPath('AAPL', 'sources'));
  await app.change(app.host.querySelector('textarea'), 'net income');
  await app.release(oldDirect, directAnswer('AAPL', 'latest revenue'));
  assert.ok(!app.host.querySelector('.direct-answer'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  await app.release(oldSources, [filing('AAPL')]);
  assert.ok(!app.host.querySelector('.direct-answer')); assert.doesNotMatch(app.host.textContent, /AAPL-test-accession/);
  await app.release(app.request(companyPath('JPM', 'freshness')), freshnessFixture('JPM', 0));
  await app.release(app.request(companyPath('JPM', 'sources')), {}, 503);
  await app.change(app.host.querySelector('textarea'), 'latest revenue'); await app.click('Research question');
  const oldVersionAnswer = app.request(companyPath('JPM', 'research-answer'));
  await focusCheck(); await app.release(app.request(companyPath('JPM', 'freshness')), freshnessFixture('JPM', 1));
  await app.release(oldVersionAnswer, directAnswer('JPM', 'latest revenue'));
  assert.ok(!app.host.querySelector('.direct-answer'));
});

test('FR-01 source-independent direct responses still require matching company and question', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'sources')), {}, 503);
  for (const [ticker, question] of [['JPM', 'latest revenue'], ['AAPL', 'wrong question']]) {
    await app.change(app.host.querySelector('textarea'), 'latest revenue'); await app.click('Research question');
    await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer(ticker, question));
    assert.ok(!app.host.querySelector('.direct-answer'));
  }
});

for (const version of [0, 1]) test(`FR-01 reconciliation cannot reuse rejected publication ${version}`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: version });
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), {}, 409, version + 1);
  const count = dependentRequests(app).length;
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version));
  assert.match(app.host.textContent, /Could not verify this company’s data version/);
  assert.equal(dependentRequests(app).length, count);
  await app.change(app.host.querySelector('textarea'), 'latest revenue');
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(dependentRequests(app).length, count, 'Rejected pin remains closed without a retry loop');
  await retryTwice(app, 'Retry data check');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version + 1));
  assert.ok(dependentRequests(app).slice(count).every(r => r.init.headers['X-FinLens-Data-Version'] === String(version + 1)));
});

test('FR-01 an ordinary freshness outage preserves verified research through same-pin manual recovery', async ctx => {
  const app = await mount(ctx);
  await app.completeCompany('AAPL', '1000000000');
  const query = 'latest revenue';
  const evidence = await app.search('AAPL', query, true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  await app.release(evidence, context('AAPL', query));
  const answer = app.host.querySelector('.direct-answer'); const snapshot = app.snapshot().textContent;
  const passages = app.evidence();
  await focusCheck(); await app.release(app.request(companyPath('AAPL', 'freshness')), {}, 503);
  assert.match(app.host.textContent, /Already loaded research remains available/);
  const count = app.requests.length;
  await retryTwice(app, 'Retry data check');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
  assert.equal(app.requests.length, count + 1);
  assert.equal(app.host.querySelector('.direct-answer'), answer);
  assert.equal(app.snapshot().textContent, snapshot); assert.deepEqual(app.evidence(), passages);
});

test('FR-01 company-wide scope cannot retrieve unverified sources and recovery preserves a pending direct answer', async ctx => {
  const app = await mount(ctx, true);
  await app.release(app.request(companyPath('AAPL', 'sources')), {}, 503);
  await app.change(app.select('Evidence search scope'), 'company');
  const query = 'latest revenue';
  await app.change(app.host.querySelector('textarea'), query); await app.click('Research question');
  const direct = app.request(companyPath('AAPL', 'research-answer'));
  assert.equal(app.requests.filter(r => /\/context$|\/answer$/.test(r.path)).length, 0);
  const count = app.requests.length;
  await retryTwice(app, 'Retry filing list');
  await app.release(app.request(companyPath('AAPL', 'sources')), [filing('AAPL')]);
  assert.equal(app.requests.length, count + 1);
  assert.equal(direct.init.signal.aborted, false);
  assert.equal(app.select('Evidence search scope').value, 'company');
  await app.release(direct, directAnswer('AAPL', query));
  assert.ok(app.host.querySelector('.direct-answer'));
  await app.click('Research question');
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  await app.release(app.request(companyPath('AAPL', 'context')), companyContext('AAPL', query));
  assert.ok(app.evidence().length > 0);
  assert.equal(app.requests.filter(r => r.path.endsWith('/answer')).length, 0);
});

async function drainResponseMicrotasks() {
  // The immediate json fixture and API promise chains use only microtasks.
  // Never yield to a timer/scheduler or exit act before the second delivery.
  for (let turn = 0; turn < 20; turn++) await Promise.resolve();
}

const discoveryGroups = {
  Income: { revenue: 'Revenue', gross_profit: 'Gross profit', operating_income: 'Operating income', net_income: 'Net income', diluted_eps: 'Diluted EPS' },
  'Growth and margins': { revenue_growth_yoy: 'Revenue YoY', gross_margin: 'Gross margin', operating_margin: 'Operating margin', net_margin: 'Net margin' },
  'Balance sheet': { cash_and_equivalents: 'Cash and equivalents', total_assets: 'Total assets', total_liabilities: 'Total liabilities' },
  'Cash flow': { operating_cash_flow: 'Operating cash flow', capital_expenditures: 'Capital expenditures', free_cash_flow: 'Free cash flow' },
};
const discoveryMetrics = Object.keys(Object.assign({}, ...Object.values(discoveryGroups)));
const balanceMetrics = Object.keys(discoveryGroups['Balance sheet']);
function discoverySnapshot(ticker) {
  const result = summary(ticker, '0');
  for (const metric of discoveryMetrics) {
    const observation = point(ticker, metric === 'net_income' ? '-123456789.0123' : '1000000000', metric);
    if (balanceMetrics.includes(metric)) {
      observation.period = { ...observation.period, kind: 'instant', start: null };
      observation.provenance = observation.provenance.map(source => ({ ...source, period_start: null }));
    }
    if (metric.includes('margin') || metric === 'revenue_growth_yoy') observation.unit = 'ratio';
    if (metric === 'diluted_eps') { observation.unit = 'USD/share'; observation.value = '1.2345'; }
    result.metrics[metric] = observation;
  }
  result.metrics.revenue.value = '0';
  result.metrics.gross_margin = { ...result.metrics.gross_margin, value: null, status: 'not_applicable', reason: 'Gross margin is not applicable on this economic revenue basis.' };
  result.metrics.gross_profit = { ...result.metrics.gross_profit, value: null, status: 'unavailable', reason: 'No compatible reported gross profit for this interval.' };
  return result;
}
function metricCard(app, label) {
  return [...app.snapshot().querySelectorAll('.metric-card')].find(card => card.querySelector('h3').textContent === label);
}
function discoveryHistory(metric, kind = balanceMetrics.includes(metric) ? 'instant' : 'quarter') {
  const result = history('AAPL', '0', metric);
  result.requested_period = kind;
  const end = { annual: '2025-12-31', half_year: '2025-06-30', nine_months: '2025-09-30' }[kind] ?? '2025-03-31';
  result.history[0].period = { ...result.history[0].period, kind, start: kind === 'instant' ? null : '2025-01-01', end };
  result.history[0].provenance[0].period_start = result.history[0].period.start;
  result.history[0].provenance[0].period_end = end;
  return result;
}

test('FD-01 mounted snapshot keeps six primary cards and discovers all 15 with original statuses and provenance', async ctx => {
  const app = await mount(ctx);
  const payload = discoverySnapshot('AAPL'); const original = structuredClone(payload);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), payload);
  const primary = [...app.snapshot().querySelector('.metric-grid').querySelectorAll('h3')].map(node => node.textContent);
  assert.deepEqual(primary, ['Revenue', 'Revenue YoY', 'Net income', 'Diluted EPS', 'Operating income', 'Net margin']);
  assert.equal(app.snapshot().querySelectorAll('.metric-card').length, 15);
  const labels = Object.values(discoveryGroups).flatMap(group => Object.values(group));
  assert.deepEqual([...app.snapshot().querySelectorAll('.metric-card h3')].map(node => node.textContent).sort(), labels.sort());
  assert.equal(metricCard(app, 'Revenue').querySelector('.metric-value').textContent, '$0');
  assert.equal(metricCard(app, 'Net income').querySelector('.metric-value').textContent, '-$123.46M');
  assert.match(metricCard(app, 'Net income').querySelector('.provenance').textContent, /-123456789\.0123 USD/);
  assert.equal(metricCard(app, 'Diluted EPS').querySelector('.metric-value').textContent, '$1.2345');
  for (const [label, status, reason] of [['Gross profit', 'Unavailable', payload.metrics.gross_profit.reason], ['Gross margin', 'Not applicable', payload.metrics.gross_margin.reason]]) {
    const card = metricCard(app, label);
    assert.equal(card.querySelector('.metric-value').textContent, status);
    assert.equal(card.querySelector('.metric-reason').textContent, reason);
    assert.ok(card.querySelector('.provenance').textContent.includes(reason));
    assert.doesNotMatch(card.querySelector('.metric-value').textContent, /\$0/);
  }
  for (const label of Object.values(discoveryGroups['Balance sheet'])) {
    const card = metricCard(app, label);
    assert.match(card.querySelector('.metric-period').textContent, /^As of date · Mar 31, 2025/);
    assert.doesNotMatch(card.querySelector('.metric-period').textContent, /quarter|annual|YTD|Jan 1/);
    assert.match(card.querySelector('.provenance').textContent, /As of Mar 31, 2025/);
  }
  for (const detail of app.snapshot().querySelectorAll('.secondary-metrics')) {
    assert.equal(detail.open, false); detail.querySelector('summary').focus();
    assert.equal(document.activeElement, detail.querySelector('summary'));
    await act(async () => detail.querySelector('summary').click()); assert.equal(detail.open, true);
  }
  assert.equal(app.requests.filter(item => item.path.endsWith('/financials/summary')).length, 1, 'Discovery adds no snapshot fan-out');
  assert.deepEqual(payload, original);
});

test('FD-01 missing snapshot metrics remain named and cannot fabricate available values', async ctx => {
  const app = await mount(ctx); const payload = summary('AAPL', '0');
  payload.metrics.total_liabilities = point('AAPL', '900', 'total_assets');
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), payload);
  const card = metricCard(app, 'Total liabilities');
  assert.match(card.textContent, /Status unavailable.*not returned/); assert.doesNotMatch(card.textContent, /900|\$/);
  assert.equal(app.snapshot().querySelectorAll('.metric-card').length, 15);
});

test('FD-01 mounted history groups all 15 metrics with instant dates and direct duration requests', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const picker = app.select('Metric');
  assert.equal(picker.options.length, 15);
  assert.deepEqual([...picker.querySelectorAll('optgroup')].map(group => [group.label, [...group.querySelectorAll('option')].map(option => [option.value, option.textContent])]), Object.entries(discoveryGroups).map(([label, group]) => [label, Object.entries(group)]));
  for (const metric of discoveryMetrics.filter(metric => metric !== 'revenue')) {
    const count = app.requests.length;
    await app.change(picker, metric);
    const kind = balanceMetrics.includes(metric) ? 'instant' : 'quarter';
    assert.equal(app.select('History period').value, kind);
    assert.deepEqual([...app.select('History period').options].map(option => option.value), kind === 'instant' ? ['instant'] : ['quarter', 'annual', 'half_year', 'nine_months']);
    const pending = app.request(companyPath('AAPL', `financials/metrics/${metric}`), { period: kind });
    assert.equal(pending.init.headers['X-FinLens-Data-Version'], '0');
    assert.equal(app.requests.length, count + 1);
    await app.release(pending, discoveryHistory(metric));
    assert.equal(app.trends().querySelectorAll('tbody tr').length, 1);
    if (kind === 'instant') {
      assert.match(app.trends().textContent, /Bars are values as of each date/);
      assert.match(app.trends().querySelector('tbody td').textContent, /^As of date · Mar 31, 2025/);
    }
  }
  await app.change(picker, 'gross_profit');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/gross_profit')), discoveryHistory('gross_profit'));
  await app.change(app.select('History period'), 'annual');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/gross_profit'), { period: 'annual' }), discoveryHistory('gross_profit', 'annual'));
  await app.change(picker, 'operating_income');
  assert.equal(app.select('History period').value, 'annual', 'Compatible chosen period is retained');
  assert.equal(app.request(companyPath('AAPL', 'financials/metrics/operating_income')).params.get('period'), 'annual');
});

test('FD-01 history availability is independent and missing/not-applicable reasons remain visible', async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), discoverySnapshot('AAPL'));
  await app.change(app.select('Metric'), 'gross_profit');
  const available = discoveryHistory('gross_profit');
  const missing = { ...available.history[0], value: null, status: 'unavailable', reason: 'No direct-quarter source; annual data is not substituted.' };
  const inapplicable = { ...missing, status: 'not_applicable', reason: 'Not applicable for this filing basis.' };
  available.history.push(missing, inapplicable);
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/gross_profit')), available);
  assert.equal(app.trends().querySelectorAll('tbody tr').length, 3);
  assert.deepEqual([...app.trends().querySelectorAll('tbody .metric-reason')].map(item => item.textContent), [missing.reason, inapplicable.reason]);
  assert.match(app.trends().textContent, /\$0/);
  await app.change(app.select('Metric'), 'gross_margin');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/gross_margin')), { ...discoveryHistory('gross_margin'), history: [], status: 'not_applicable', reason: inapplicable.reason });
  assert.match(app.trends().textContent, /Gross margin is not applicable/);
  assert.ok(app.trends().textContent.includes(inapplicable.reason));
});

for (const [field, value] of [['ticker', 'JPM'], ['company_cik', '0000019617'], ['metric', 'total_assets'], ['requested_period', 'annual']]) test(`FD-01 history rejects mismatched ${field}`, async ctx => {
  const app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), { ...discoveryHistory('revenue'), [field]: value });
  assert.ok(app.trends().querySelector('[role="alert"]')); assert.ok(!app.trends().querySelector('tbody'));
});

test('FD-01 ignored-abort instant history and filing records cannot cross companies or control selections', async ctx => {
  const app = await mount(ctx);
  const sources = app.request(companyPath('AAPL', 'sources'));
  await app.change(app.select('Metric'), 'total_liabilities');
  const old = app.request(companyPath('AAPL', 'financials/metrics/total_liabilities'));
  await app.change(app.select('Metric'), 'gross_profit');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/gross_profit')), discoveryHistory('gross_profit'));
  await app.release(old, discoveryHistory('total_liabilities'));
  assert.equal(old.init.signal.aborted, true); assert.equal(app.select('Metric').value, 'gross_profit');
  assert.doesNotMatch(app.trends().querySelector('tbody').textContent, /As of date/);
  await app.change(app.host.querySelector('#company'), 'JPM');
  await app.completeCompany('JPM', '2000000000');
  await app.release(sources, [{ ...filing('AAPL'), has_filing_chunks: false }]);
  assert.doesNotMatch(app.host.textContent, /AAPL-test-accession/);
  assert.ok(!app.host.querySelector('.recorded-filings'));
});

for (const version of [0, 1]) test(`FD-01 guided questions prepare without requests and submit explicitly at pin ${version}`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: version });
  await app.release(app.request(companyPath('AAPL', 'sources')), [], 200, version);
  const guide = app.select('Question metric');
  assert.equal(guide.options.length, 15);
  const count = app.requests.length;
  await app.change(app.select('Question reporting scope'), 'annual');
  await app.change(guide, 'gross_profit');
  await app.click('Use question');
  assert.equal(app.host.querySelector('textarea').value, 'What is the latest annual gross profit?');
  assert.equal(document.activeElement, app.host.querySelector('textarea'));
  await app.change(guide, 'total_liabilities');
  assert.deepEqual([...app.select('Question reporting scope').options].map(option => option.value), ['latest_available']);
  assert.equal(app.select('Question reporting scope').value, 'latest_available');
  assert.match(app.host.querySelector('.question-guide').textContent, /as of a date, not a reporting-interval flow/);
  await app.click('Use question');
  const question = 'What is the latest available total liabilities?';
  assert.equal(app.host.querySelector('textarea').value, question);
  assert.equal(app.requests.length, count, 'Selection and preparation never fetch');
  await app.click('Research question');
  const pending = app.request(companyPath('AAPL', 'research-answer'));
  assert.equal(pending.init.headers['X-FinLens-Data-Version'], String(version));
  assert.equal(JSON.parse(pending.init.body).question, question);
  assert.equal(app.requests.length, count + 1, 'No indexed evidence exists, so only direct research runs');
  await app.release(pending, directAnswer('AAPL', question), 200, version);
  assert.ok(app.host.querySelector('.direct-answer'));
});

test('FD-01 preparation with unknown publication stays editable but cannot submit unpinned requests', async ctx => {
  const app = await mount(ctx, true, companies, { initialVersion: null });
  await app.click('Use question');
  assert.equal(app.host.querySelector('textarea').value, 'What is the latest available revenue?');
  assert.equal(app.requests.filter(item => /research-answer|\/context$|\/answer$|\/sources$|financials/.test(item.path)).length, 0);
  assert.equal([...app.host.querySelectorAll('button')].find(button => button.textContent === 'Research question').disabled, true);
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(dependentRequests(app).length, 0);
});

test('FD-01 Use question cancels pending direct/evidence and discards late responses', async ctx => {
  const app = await mount(ctx, true); await app.completeCompany('AAPL', '1000000000');
  const evidence = await app.search('AAPL', 'old question', true);
  const answer = app.request(companyPath('AAPL', 'research-answer'));
  const count = app.requests.length;
  await app.change(app.select('Question metric'), 'operating_income'); await app.click('Use question');
  assert.equal(evidence.init.signal.aborted, true); assert.equal(answer.init.signal.aborted, true);
  assert.equal(app.requests.length, count);
  await app.release(evidence, context('AAPL', 'old question'));
  await app.release(answer, directAnswer('AAPL', 'old question'));
  assert.ok(!app.host.querySelector('.direct-answer')); assert.deepEqual(app.evidence(), []);
  assert.equal(app.host.querySelector('textarea').value, 'What is the latest available operating income?');
});

test('FD-01 Use question clears resolved answer/evidence and cancels pending AI without generating', async ctx => {
  const app = await mount(ctx, true); await app.completeCompany('AAPL', '1000000000');
  const pending = await app.search('AAPL', 'latest revenue', true);
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', 'latest revenue'));
  await app.release(pending, context('AAPL', 'latest revenue'));
  await app.click('Generate AI analysis');
  const ai = app.request(companyPath('AAPL', `filings/${filing('AAPL').accession_number}/answer`));
  const count = app.requests.length;
  await app.click('Use question');
  assert.equal(ai.init.signal.aborted, true); assert.equal(app.requests.length, count);
  assert.ok(!app.host.querySelector('.direct-answer')); assert.ok(!app.host.querySelector('.ai-panel'));
  assert.deepEqual(app.evidence(), []);
  await app.release(ai, { evidence_status: 'sufficient', answer: 'OBSOLETE AI', claims: [], citations: [] });
  assert.doesNotMatch(app.host.textContent, /OBSOLETE AI/);
});

test('FD-01 filing discovery retains metadata/unknown records, strict selection, verified links and progressive disclosure', async ctx => {
  const app = await mount(ctx, true);
  const metadata = Array.from({ length: 12 }, (_, index) => ({ ...filing('AAPL'), accession_number: `metadata-${index}`, form: '10-K', has_filing_chunks: false,
    sec_url: index === 0 ? 'https://www.sec.gov/Archives/metadata' : index === 1 ? 'https://sec.gov.evil.test/filing' : index === 2 ? 'javascript:alert(1)' : '' }));
  const unknown = [undefined, null, 'true', 'false', 1, 0, {}].map((flag, index) => ({ ...filing('AAPL'), accession_number: `unknown-${index}`, has_filing_chunks: flag, sec_url: 'http://www.sec.gov/Archives/unknown' }));
  const records = [filing('AAPL'), ...metadata, ...unknown]; const original = structuredClone(records);
  await app.release(app.request(companyPath('AAPL', 'sources')), records);
  assert.deepEqual([...app.select('Indexed SEC filing').options].map(option => option.value), [filing('AAPL').accession_number]);
  const lists = [...app.host.querySelectorAll('.recorded-filings')]; assert.equal(lists.length, 2);
  assert.match(lists[0].querySelector('summary').textContent, /metadata only \(12\)/);
  assert.match(lists[1].querySelector('summary').textContent, /unverified \(7\)/);
  assert.equal(lists[0].querySelectorAll('li').length, 10); assert.equal(lists[1].querySelectorAll('li').length, 7);
  assert.equal(lists[0].querySelectorAll('a').length, 1); assert.equal(lists[1].querySelectorAll('a').length, 0);
  assert.equal(lists[0].querySelector('a').href, metadata[0].sec_url);
  assert.equal(lists[0].querySelector('a').rel, 'noopener noreferrer');
  assert.doesNotMatch(lists[0].textContent, /Jan 1|Mar 31|AI-ready/);
  const count = app.requests.length;
  await act(async () => lists[0].querySelector('summary').click());
  await app.click('Show more recorded filings (2)');
  assert.equal(lists[0].querySelectorAll('li').length, 12);
  assert.equal(app.requests.length, count); assert.deepEqual(records, original);
  assert.ok(!lists[0].querySelector('select')); assert.ok(!lists[1].querySelector('select'));
  assert.equal(app.requests.filter(item => /\/text$|\/chunks$|\/context$|\/answer$/.test(item.path)).length, 0);
});

for (const retrievalScope of ['filing', 'company']) test(`FD-01 metadata-only and malformed readiness cannot authorize ${retrievalScope} evidence or AI`, async ctx => {
  const app = await mount(ctx, true);
  await app.release(app.request(companyPath('AAPL', 'sources')), [false, 'true', null].map((flag, index) => ({ ...filing('AAPL'), accession_number: `ineligible-${index}`, has_filing_chunks: flag })));
  assert.equal(app.select('Indexed SEC filing').disabled, true);
  await app.change(app.select('Evidence search scope'), retrievalScope);
  await app.click('Use question'); await app.click('Research question');
  const question = app.host.querySelector('textarea').value;
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', question));
  assert.ok(app.host.querySelector('.direct-answer'));
  assert.ok(!app.host.querySelector('.ai-panel')); assert.deepEqual(app.evidence(), []);
  assert.equal(app.requests.filter(item => /\/context$|\/answer$|\/text$/.test(item.path)).length, 0);
});

test('FD-01 failed discovery differs from verified empty and guide/direct answer survive source retry', async ctx => {
  const app = await mount(ctx, true);
  await app.release(app.request(companyPath('AAPL', 'sources')), {}, 503);
  const panel = app.host.querySelector('.filing-panel');
  assert.match(panel.textContent, /Indexed evidence list unavailable/);
  assert.doesNotMatch(panel.textContent, /No recorded filings were returned|Indexed searchable SEC evidence \(0\)/);
  await app.change(app.select('Question metric'), 'net_income'); await app.click('Use question'); await app.click('Research question');
  const question = 'What is the latest available net income?';
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', question));
  const answer = app.host.querySelector('.direct-answer'); const count = app.requests.length;
  await app.click('Retry filing list'); await app.release(app.request(companyPath('AAPL', 'sources')), []);
  assert.equal(app.requests.length, count + 1); assert.equal(app.host.querySelector('.direct-answer'), answer);
  assert.equal(app.select('Question metric').value, 'net_income'); assert.equal(app.host.querySelector('textarea').value, question);
  assert.match(panel.textContent, /No recorded filings were returned/);
  assert.match(panel.textContent, /Indexed searchable SEC evidence \(0\)/);
  assert.ok(!panel.querySelector('[role="alert"]'));
});

test('FD-01 malformed filing lists fail visibly and recover through one explicit retry', async ctx => {
  const app = await mount(ctx, true);
  await app.release(app.request(companyPath('AAPL', 'sources')), [null]);
  const panel = app.host.querySelector('.filing-panel');
  assert.ok(panel.querySelector('[role="alert"]'));
  assert.doesNotMatch(panel.textContent, /No recorded filings were returned/);
  assert.ok(!panel.querySelector('.recorded-filings'));
  const count = app.requests.length;
  await app.click('Retry filing list');
  await app.release(app.request(companyPath('AAPL', 'sources')), [{ ...filing('AAPL'), has_filing_chunks: false }]);
  assert.equal(app.requests.length, count + 1);
  assert.ok(!panel.querySelector('[role="alert"]')); assert.ok(panel.querySelector('.recorded-filings'));
  assert.equal(app.select('Indexed SEC filing').disabled, true);
});

test('FD-01 metadata disclosure resets at new verified publication and isolates company switching', async ctx => {
  const app = await mount(ctx);
  const metadata = Array.from({ length: 12 }, (_, index) => ({ ...filing('AAPL'), accession_number: `old-metadata-${index}`, has_filing_chunks: false }));
  await app.release(app.request(companyPath('AAPL', 'sources')), metadata);
  await app.click('Show more recorded filings (2)');
  assert.equal(app.host.querySelectorAll('.recorded-filings li').length, 12);
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.ok(!app.host.querySelector('.recorded-filings'), 'Older publication records vanish while new sources load');
  const fresh = app.request(companyPath('AAPL', 'sources'));
  assert.equal(fresh.init.headers['X-FinLens-Data-Version'], '1');
  await app.release(fresh, metadata.map(item => ({ ...item, accession_number: item.accession_number.replace('old-', 'new-') })), 200, 1);
  assert.equal(app.host.querySelectorAll('.recorded-filings li').length, 10);
  assert.doesNotMatch(app.host.textContent, /old-metadata/);
  await app.change(app.host.querySelector('#company'), 'JPM');
  assert.ok(!app.host.querySelector('.recorded-filings'));
  assert.doesNotMatch(app.host.textContent, /new-metadata|old-metadata/);
  await app.completeCompany('JPM', '2000000000');
  assert.ok(!app.host.querySelector('.recorded-filings'));
});

for (const strict of [false, true]) for (const version of [0, 1]) test(`FR-01 P2 obsolete ${version} 409 cannot reject verified ${version + 1}${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: version, strict });
  const obsolete = dependentRequests(app);
  const oldSnapshot = app.request(companyPath('AAPL', 'financials/summary'));
  assert.equal(oldSnapshot.init.headers['X-FinLens-Data-Version'], String(version));
  await focusCheck();
  const check = app.request(companyPath('AAPL', 'freshness'));
  const freshnessCount = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await act(async () => {
    app.deliverBeforeCommit(check, freshnessFixture('AAPL', version + 1, 1));
    await drainResponseMicrotasks();
    // Catalog reconciliation is invoked after latest.current has been set, so
    // this proves verification has completed while the DOM/cancellation has not.
    assert.ok(app.request('/companies'));
    assert.match(app.host.querySelector('[aria-label="Data freshness"]').textContent, new RegExp(`version ${version}(?![0-9])`));
    assert.ok(obsolete.every(r => !r.init.signal.aborted), 'Old controllers must still be live at the raced delivery');
    app.deliverBeforeCommit(oldSnapshot, {}, 409, version + 1);
    await drainResponseMicrotasks();
    assert.ok(obsolete.every(r => !r.init.signal.aborted), 'Both response callbacks ran before React cancellation');
  });
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, freshnessCount, 'Obsolete mismatch must not start reconciliation');
  // Settled transports detach from caller cancellation; pending siblings abort.
  assert.equal(oldSnapshot.init.signal.aborted, false);
  assert.ok(obsolete.filter(r => r !== oldSnapshot).every(r => r.init.signal.aborted));
  const current = dependentRequests(app).slice(obsolete.length);
  assert.equal(current.length, 3);
  assert.ok(current.every(r => r.init.headers['X-FinLens-Data-Version'] === String(version + 1)));
  await app.release(app.request('/companies'), companies);
  await app.completeCompany('AAPL', '2000000000');
  assert.match(app.snapshot().textContent, /\$2B/);
  // Ignored-abort old responses stay isolated after the newer publication commits.
  for (const item of obsolete.filter(r => !r.released)) await app.release(item, {}, 409, version + 1);
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, freshnessCount);
  assert.match(app.snapshot().textContent, /\$2B/);
  const count = app.requests.length;
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version + 1, 1));
  assert.equal(app.requests.length, count + 1, 'Same verified pin remains usable without duplicate fan-out');
  await app.change(app.host.querySelector('textarea'), 'latest revenue'); await app.click('Research question');
  const currentAnswer = app.request(companyPath('AAPL', 'research-answer'));
  assert.equal(currentAnswer.init.headers['X-FinLens-Data-Version'], String(version + 1));
  const currentChecks = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await app.release(currentAnswer, {}, 409, version + 2);
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, currentChecks + 1, 'The callback for the newly committed pin must still invalidate it');
  assert.equal(app.host.querySelector('.search-form button.primary-button').disabled, true);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version + 1, 1));
  assert.match(app.host.textContent, /Could not verify this company’s data version/, 'The new pin is rejected only by its own mismatch');
});

for (const strict of [false, true]) for (const version of [0, 1]) test(`FR-01 P2 current publication ${version} still fails closed and coalesces 409s${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mount(ctx, false, companies, { initialVersion: version, strict });
  const current = dependentRequests(app);
  const freshnessCount = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await act(async () => {
    for (const request of current) {
      assert.equal(request.init.signal.aborted, false);
      app.deliverBeforeCommit(request, {}, 409, version + 1);
    }
    await drainResponseMicrotasks();
    assert.ok(current.every(r => !r.init.signal.aborted), 'All mismatches arrive before cancellation commits');
    assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, freshnessCount + 1);
  });
  // All three transports settled inside act before React cancelled the caller scopes.
  assert.ok(current.every(r => r.released && !r.init.signal.aborted));
  assert.match(app.host.textContent, /Published data changed.*Research waits/);
  await app.change(app.host.querySelector('textarea'), 'latest revenue');
  await act(async () => app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(dependentRequests(app).length, current.length, 'Current rejection exposes null and cannot replay the pin');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version));
  assert.match(app.host.textContent, /Could not verify this company’s data version/);
  await retryTwice(app, 'Retry data check');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version));
  assert.equal(dependentRequests(app).length, current.length, 'Manual recovery must retain the rejected-version guard');
  const count = app.requests.length;
  await retryTwice(app, 'Retry data check');
  assert.equal(app.requests.length, count + 1);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', version + 1));
  const recovered = dependentRequests(app).slice(current.length);
  assert.equal(recovered.length, 3);
  assert.ok(recovered.every(r => r.init.headers['X-FinLens-Data-Version'] === String(version + 1)));
});


// UX-01A adds presentation acceptance without changing existing assertions.
test('UX-01A history region is labelled and focusable with unchanged values, dates and sources', async ctx => {
  const app = await mount(ctx);
  const data = history('AAPL', '0');
  data.history.push(point('AAPL', '-123456789.0123'), { ...point('AAPL', null), status: 'unavailable', reason: 'No compatible quarterly observation.', provenance: [] });
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), data);
  const region = app.trends().querySelector('[role="region"]');
  assert.equal(region.getAttribute('aria-label'), 'Revenue historical observations and SEC sources');
  assert.equal(region.tabIndex, 0);
  const help = document.getElementById(region.getAttribute('aria-describedby'));
  assert.match(help.textContent, /scroll horizontally.*arrow keys/);
  region.focus(); assert.equal(document.activeElement, region);
  assert.equal(region.querySelector('table caption').textContent, 'Revenue · Direct quarter');
  assert.deepEqual([...region.querySelectorAll('th')].map(th => [th.textContent, th.scope]), [['Period', 'col'], ['Reported value', 'col'], ['Provenance', 'col']]);
  const rows = region.querySelectorAll('tbody tr');
  assert.equal(rows.length, 3);
  assert.match(rows[0].textContent, /Jan 1, 2025.*Mar 31, 2025.*\$0/);
  assert.match(rows[1].textContent, /-\$123\.46M/);
  assert.match(rows[2].textContent, /Unavailable.*No compatible quarterly observation/);
  const count = app.requests.length;
  const disclosure = rows[1].querySelector('summary');
  disclosure.focus(); assert.equal(document.activeElement, disclosure);
  await act(async () => disclosure.click());
  assert.equal(disclosure.parentElement.open, true);
  assert.match(rows[1].textContent, /-123456789\.0123 USD/);
  assert.equal(rows[1].querySelector('a').href, filing('AAPL').sec_url);
  assert.equal(app.requests.length, count, 'Focus and source disclosure must not request data');
});

test('UX-01A historical navigation resolves to the existing trends section without fetching', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const link = [...app.host.querySelectorAll('nav a')].find(item => item.textContent === 'Historical trends');
  assert.equal(link.getAttribute('href'), '#history-title');
  assert.equal(document.getElementById('history-title').textContent, 'Reported financial trends');
  const count = app.requests.length;
  link.focus(); assert.equal(document.activeElement, link);
  await act(async () => link.click());
  assert.equal(app.requests.length, count);
  assert.equal(app.select('Company').value, 'AAPL');
});

for (const indexed of [true, false]) test(`UX-01A filing readiness explicitly qualifies indexing for ${indexed}`, async ctx => {
  const catalog = [{ ...companies[0], has_indexed_filing: indexed, indexed_filing_count: indexed ? 1 : 0 }];
  const app = await mount(ctx, false, catalog);
  const overview = app.host.querySelector('.company-overview');
  assert.equal(overview.querySelector('.badge').textContent, indexed ? 'Ready for filing research' : 'Not indexed for filing research');
  assert.match(overview.textContent, /Filing indexing does not establish financial completeness or data freshness/);
  assert.equal(app.select('Company').value, 'AAPL');
});

for (const retrievalScope of ['filing', 'company']) test(`UX-01A ${retrievalScope} empty guidance follows verified searchable availability without requests`, async ctx => {
  const app = await mount(ctx, true);
  const panel = app.host.querySelector('.filing-panel');
  await app.release(app.request(companyPath('AAPL', 'sources')), [false, 'true', null].map((flag, index) => ({ ...filing('AAPL'), accession_number: `ineligible-${index}`, has_filing_chunks: flag })));
  await app.change(app.select('Evidence search scope'), retrievalScope);
  assert.match(panel.textContent, /Explore financial questions/);
  assert.match(panel.textContent, /Searchable filing evidence is unavailable.*direct answers.*may be unavailable/);
  assert.doesNotMatch(panel.textContent, /Explore the filing evidence/);
  const count = app.requests.length;
  await app.click('Use question');
  assert.equal(app.requests.length, count, 'Guidance and preparation must not retrieve or generate');
  await app.click('Research question');
  assert.equal(app.requests.length, count + 1, 'Only the existing direct financial request is authorized');
  assert.equal(app.requests.at(-1).path, companyPath('AAPL', 'research-answer'));
  assert.equal(app.requests.at(-1).init.headers['X-FinLens-Data-Version'], '0');
  assert.equal(app.requests.filter(item => /\/context$|\/answer$/.test(item.path)).length, 0);
});

test('UX-01A both eligible evidence scopes retain filing exploration guidance', async ctx => {
  const app = await mount(ctx); await app.completeCompany('AAPL', '1000000000');
  const count = app.requests.length;
  for (const retrievalScope of ['filing', 'company']) {
    await app.change(app.select('Evidence search scope'), retrievalScope);
    const panel = app.host.querySelector('.filing-panel');
    assert.match(panel.textContent, /Explore the filing evidence/);
    assert.doesNotMatch(panel.textContent, /Explore financial questions/);
  }
  assert.equal(app.requests.length, count);
});

// DEP-01A2 Increment 1: only synthetic fetch + mocked deadline timers.
function researchDeadlineClock(ctx) {
  ctx.mock.timers.enable({ apis: ['setTimeout'] });
  return async () => { await act(async () => ctx.mock.timers.tick(30_000)); };
}

function submitTwice(app) {
  return act(async () => {
    for (let i = 0; i < 2; i++) app.host.querySelector('.search-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
}

test('DEP-01A2 catalog timeout releases pending guard and allows one explicit retry without late replacement', async ctx => {
  const expire = researchDeadlineClock(ctx);
  const app = await mount(ctx, false, companies, { catalogStatus: null, initialVersion: null });
  const old = app.request('/companies'), count = app.requests.length;
  await expire();
  assert.match(app.host.textContent, /Could not load the company list/);
  assert.equal(old.init.signal.aborted, true);
  assert.equal(app.requests.length, count, 'No automatic retry');
  await retryTwice(app, 'Retry companies');
  assert.equal(app.requests.length, count + 1);
  const retry = app.request('/companies');
  await app.release(old, [{ ...companies[1], name: 'Late catalog must not render' }]);
  assert.doesNotMatch(app.host.textContent, /Late catalog must not render/);
  assert.equal(app.host.querySelector('#company').value, '');
  await app.release(retry, companies);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
  await app.completeCompany('AAPL', '1000000000');
  assert.match(app.snapshot().textContent, /\$1B/);
  assert.equal(app.requests.filter(r => r.path === '/capabilities').length, 1);
});

test('DEP-01A2 freshness timeout stays closed until manual retry verifies its own version', async ctx => {
  const expire = researchDeadlineClock(ctx);
  const app = await mount(ctx, false, companies, { initialVersion: null });
  const old = app.request(companyPath('AAPL', 'freshness')), count = app.requests.length;
  await expire();
  assert.match(app.host.textContent, /Could not verify this company’s data version/);
  assert.equal(app.requests.length, count);
  await retryTwice(app, 'Retry data check');
  await focusCheck(); await focusCheck();
  assert.equal(app.requests.length, count + 1, 'Pending recovery coalesces repeated focus/retry');
  const retry = app.request(companyPath('AAPL', 'freshness'));
  await app.release(old, freshnessFixture('AAPL', 9));
  assert.equal(dependentRequests(app).length, 0);
  await app.release(retry, freshnessFixture('AAPL', 0));
  assert.equal(dependentRequests(app).length, 3);
  assert.ok(dependentRequests(app).every(r => r.init.headers['X-FinLens-Data-Version'] === '0'));
});

test('DEP-01A2 stalled snapshot body times out, preserves siblings and recovers with one pinned manual retry', async ctx => {
  const expire = researchDeadlineClock(ctx), app = await mount(ctx);
  const old = app.request(companyPath('AAPL', 'financials/summary'));
  let finishBody;
  const response = new Response(null, { headers: { 'X-FinLens-Data-Version': '9' } });
  response.json = () => new Promise(resolve => { finishBody = resolve; });
  await act(async () => { old.released = true; old.resolve(response); });
  assert.equal(typeof finishBody, 'function');
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '900000000'));
  await app.release(app.request(companyPath('AAPL', 'sources')), [filing('AAPL')]);
  const count = app.requests.length;
  await expire();
  assert.match(app.snapshot().textContent, /took too long/);
  assert.match(app.trends().textContent, /\$900M/);
  assert.equal(app.requests.length, count);
  await retryTwice(app, 'Retry snapshot');
  assert.equal(app.requests.length, count + 1);
  const retry = app.request(companyPath('AAPL', 'financials/summary'));
  assert.equal(retry.init.headers['X-FinLens-Data-Version'], '0');
  await act(async () => finishBody(summary('AAPL', '99000000000')));
  assert.equal(app.requests.length, count + 1, 'Late version mismatch cannot reconcile publication');
  assert.doesNotMatch(app.snapshot().textContent, /\$99B/);
  await app.release(retry, summary('AAPL', '2000000000'));
  assert.match(app.snapshot().textContent, /\$2B/);
  assert.match(app.trends().textContent, /\$900M/);
});

test('DEP-01A2 timed-out snapshot cache evicts and permits recovery through period reselection', async ctx => {
  const expire = researchDeadlineClock(ctx), app = await mount(ctx);
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '1000000000'));
  await app.release(app.request(companyPath('AAPL', 'sources')), []);
  await expire();
  assert.match(app.snapshot().textContent, /took too long/);
  await app.change(app.select('Snapshot period'), 'annual');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'annual' }), summary('AAPL', '4000000000', 'annual'));
  const count = app.requests.length;
  await app.change(app.select('Snapshot period'), 'quarter');
  assert.equal(app.requests.length, count + 1, 'Failed cache cannot retain the timeout');
  await app.release(app.request(companyPath('AAPL', 'financials/summary'), { period: 'quarter' }), summary('AAPL', '2000000000'));
  assert.match(app.snapshot().textContent, /\$2B/);
  await app.change(app.select('Snapshot period'), 'annual');
  assert.equal(app.requests.length, count + 1, 'Successful cache is reused');
  assert.match(app.snapshot().textContent, /\$4B/);
});

for (const profile of ['development', 'sec_readonly']) test(`DEP-01A2 source timeout and manual recovery preserve independent direct answer in ${profile}`, async ctx => {
  const expire = researchDeadlineClock(ctx);
  const app = await mount(ctx, false, companies, { capabilityPayload: { research_mode: true, ai_analysis_configured: true, ai_analysis_enabled: false, server_profile: profile } });
  const old = app.request(companyPath('AAPL', 'sources'));
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), summary('AAPL', '1000000000'));
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '1000000000'));
  const query = 'latest revenue';
  await app.change(app.host.querySelector('textarea'), query); await app.click('Research question');
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  const answer = app.host.querySelector('.direct-answer'), count = app.requests.length;
  await expire();
  assert.match(app.host.querySelector('.filing-panel').textContent, /took too long/);
  assert.equal(app.host.querySelector('.direct-answer'), answer);
  await retryTwice(app, 'Retry filing list');
  assert.equal(app.requests.length, count + 1);
  await app.release(old, {}, 409, 9);
  assert.equal(app.requests.length, count + 1, 'Late discovery cannot invalidate the current pin');
  await app.release(app.request(companyPath('AAPL', 'sources')), [filing('AAPL')]);
  assert.equal(app.host.querySelector('.direct-answer'), answer);
  assert.equal(app.host.querySelector('textarea').value, query);
  assert.equal(app.requests.filter(r => /\/context$|\/answer$/.test(r.path)).length, 0);
});

for (const retrievalScope of ['filing', 'company']) for (const failed of ['direct', 'evidence']) {
  test(`DEP-01A2 ${retrievalScope} ${failed} timeout preserves independent successful branch and resets submit guard`, async ctx => {
    const expire = researchDeadlineClock(ctx), app = await mount(ctx);
    await app.completeCompany('AAPL', '1000000000');
    await app.change(app.select('Evidence search scope'), retrievalScope);
    const query = 'latest revenue';
    await app.change(app.host.querySelector('textarea'), query);
    const count = app.requests.length;
    await submitTwice(app);
    assert.equal(app.requests.length, count + 2, 'Pending guards admit one request per branch');
    const direct = app.request(companyPath('AAPL', 'research-answer'));
    const evidencePath = companyPath('AAPL', retrievalScope === 'company' ? 'context' : `filings/${filing('AAPL').accession_number}/context`);
    const evidence = app.request(evidencePath);
    const payload = retrievalScope === 'company' ? companyContext('AAPL', query) : context('AAPL', query);
    if (failed === 'direct') await app.release(evidence, payload);
    else await app.release(direct, directAnswer('AAPL', query));
    await expire();
    assert.match(app.host.textContent, /took too long/);
    if (failed === 'direct') { assert.equal(app.evidence().length, 1); assert.ok(!app.host.querySelector('.direct-answer')); }
    else { assert.ok(app.host.querySelector('.direct-answer')); assert.deepEqual(app.evidence(), []); }
    assert.equal(app.requests.length, count + 2, 'No automatic replay');
    await submitTwice(app);
    assert.equal(app.requests.length, count + 4, 'Timeout releases guard for exactly one explicit resubmission');
    const old = failed === 'direct' ? direct : evidence;
    await app.release(old, {}, 409, 9);
    assert.equal(app.requests.length, count + 4, 'Late old branch cannot invalidate or unlock replacement');
    await submitTwice(app);
    assert.equal(app.requests.length, count + 4, 'Replacement still owns the pending guards');
    await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
    await app.release(app.request(evidencePath), payload);
    assert.ok(app.host.querySelector('.direct-answer')); assert.equal(app.evidence().length, 1);
  });
}

test('DEP-01A2 expired old publication cannot invalidate a newer verified version', async ctx => {
  const expire = researchDeadlineClock(ctx), app = await mount(ctx, false, companies, { initialVersion: 1 });
  const old = dependentRequests(app);
  await expire();
  assert.ok(old.every(r => r.init.signal.aborted));
  await focusCheck();
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 2));
  await app.completeCompany('AAPL', '2000000000');
  const count = app.requests.length;
  for (const request of old) await app.release(request, {}, 409, 3);
  assert.equal(app.requests.length, count);
  assert.match(app.snapshot().textContent, /\$2B/);
  assert.match(app.host.querySelector('[aria-label="Data freshness"]').textContent, /version 2/);
  await app.change(app.host.querySelector('textarea'), 'latest revenue'); await app.click('Research question');
  assert.equal(app.request(companyPath('AAPL', 'research-answer')).init.headers['X-FinLens-Data-Version'], '2');
});

// UX-01B: history-only manual recovery through the real panel and shared transport.
for (const strict of [false, true]) for (const version of [0, 2]) {
  for (const failure of ['network', 'http', 'timeout', 'body-timeout']) {
    test(`UX-01B ${failure} manual retry retains selection and pin ${version}${strict ? ' in StrictMode' : ''}`, async ctx => {
      const expire = researchDeadlineClock(ctx), ticker = strict ? 'JPM' : 'AAPL';
      const app = await mount(ctx, false, companies.filter(company => company.ticker === ticker), { initialVersion: version, strict });
      await app.completeCompany(ticker, '1000000000');
      const snapshot = app.snapshot().querySelector('.metric-grid'), editor = app.host.querySelector('textarea');
      const path = companyPath(ticker, 'financials/metrics/net_income');
      await app.change(app.select('Metric'), 'net_income');
      await app.change(app.select('History period'), 'annual');
      const failed = app.request(path, { period: 'annual' });
      let finishBody;
      if (failure === 'network') await act(async () => { failed.released = true; failed.reject(new TypeError('Synthetic offline')); });
      if (failure === 'http') await app.release(failed, { detail: 'Synthetic history outage' }, 503);
      if (failure === 'body-timeout') {
        const response = new Response(null, { headers: { 'X-FinLens-Data-Version': String(version + 1) } });
        response.json = () => new Promise(resolve => { finishBody = resolve; });
        await act(async () => { failed.released = true; failed.resolve(response); });
        assert.equal(typeof finishBody, 'function');
      }
      const count = app.requests.length;
      if (failure.includes('timeout')) {
        await expire();
        assert.equal(failed.init.signal.aborted, true);
        assert.match(app.trends().textContent, /took too long/);
      }
      assert.ok(app.trends().querySelector('[role="alert"]'));
      assert.equal(app.trends().querySelector('[aria-live]').getAttribute('aria-busy'), 'false');
      assert.ok(!app.trends().querySelector('tbody'));
      assert.equal(app.requests.length, count, 'Failure does not automatically retry');
      await retryTwice(app, 'Retry history');
      assert.equal(app.requests.length, count + 1, 'Rapid clicks admit exactly one history request');
      const retry = app.request(path, { period: 'annual' });
      assert.equal(retry.init.headers['X-FinLens-Data-Version'], String(version));
      assert.equal(retry.params.get('limit'), '12');
      assert.equal(app.host.querySelector('#company').value, ticker);
      assert.equal(app.select('Metric').value, 'net_income');
      assert.equal(app.select('History period').value, 'annual');
      assert.equal(app.trends().querySelector('[aria-live]').getAttribute('aria-busy'), 'true');
      assert.ok(!app.trends().querySelector('[role="alert"]'));
      if (failure === 'timeout') await app.release(failed, {}, 409, version + 1);
      if (finishBody) await act(async () => finishBody(history(ticker, '99000000000', 'net_income')));
      assert.equal(app.requests.length, count + 1, 'Expired responses cannot reconcile or replay');
      assert.equal(retry.init.signal.aborted, false);
      assert.equal(app.trends().querySelector('[aria-live]').getAttribute('aria-busy'), 'true');
      // A second failure must release this attempt's guard for another explicit retry.
      await app.release(retry, { detail: 'Synthetic retry outage' }, 503);
      assert.equal(app.requests.length, count + 1, 'A failed retry is not replayed automatically');
      await retryTwice(app, 'Retry history');
      assert.equal(app.requests.length, count + 2);
      const recovered = { ...history(ticker, '300000000', 'net_income'), requested_period: 'annual',
        history: [point(ticker, '300000000', 'net_income', 'annual')] };
      await app.release(app.request(path, { period: 'annual' }), recovered);
      assert.match(app.trends().querySelector('table').textContent, /Net income.*\$300M/);
      assert.equal(app.trends().querySelector('[aria-live]').getAttribute('aria-busy'), 'false');
      assert.ok(!app.trends().querySelector('[role="alert"]'));
      assert.ok(![...app.trends().querySelectorAll('button')].some(button => button.textContent === 'Retry history'));
      assert.equal(app.snapshot().querySelector('.metric-grid'), snapshot);
      assert.equal(app.host.querySelector('textarea'), editor);
      assert.ok(app.requests.slice(count).every(request => request.path === path), 'No snapshot, freshness or sibling refetch');
    });
  }
}

for (const strict of [false, true]) for (const selection of ['metric', 'period', 'company']) {
  test(`UX-01B ${selection} change during retry isolates cancellation and the replacement guard${strict ? ' in StrictMode' : ''}`, async ctx => {
    const app = await mount(ctx, false, companies, { strict });
    const oldPath = companyPath('AAPL', 'financials/metrics/revenue');
    await app.release(app.request(oldPath), { detail: 'Synthetic outage' }, 503);
    await retryTwice(app, 'Retry history');
    const oldRetry = app.request(oldPath);
    let ticker = 'AAPL', metric = 'revenue', period = 'quarter';
    if (selection === 'metric') { metric = 'net_income'; await app.change(app.select('Metric'), metric); }
    if (selection === 'period') { period = 'annual'; await app.change(app.select('History period'), period); }
    if (selection === 'company') {
      ticker = 'JPM';
      await app.change(app.host.querySelector('#company'), ticker);
      await app.release(app.request(companyPath(ticker, 'freshness')), freshnessFixture(ticker, 0));
    }
    const path = companyPath(ticker, `financials/metrics/${metric}`);
    const replacement = app.request(path, { period });
    assert.equal(oldRetry.init.signal.aborted, true);
    const count = app.requests.length;
    await app.release(oldRetry, {}, 409, 9);
    assert.equal(app.requests.length, count, 'Cancelled retry cannot invalidate the replacement pin');
    assert.equal(replacement.init.signal.aborted, false);
    assert.equal(app.trends().querySelector('[aria-live]').getAttribute('aria-busy'), 'true');
    assert.ok(!app.trends().querySelector('[role="alert"]'));
    assert.ok(!app.trends().querySelector('tbody'));
    await app.release(replacement, { detail: 'Synthetic replacement outage' }, 503);
    await retryTwice(app, 'Retry history');
    assert.equal(app.requests.length, count + 1, 'Only the replacement releases its pending guard');
    const retry = app.request(path, { period });
    assert.equal(retry.init.headers['X-FinLens-Data-Version'], '0');
    await app.release(retry, { ...history(ticker, '2000000000', metric), requested_period: period,
      history: [point(ticker, '2000000000', metric, period)] });
    assert.match(app.trends().querySelector('table').textContent, /\$2B/);
    assert.equal(app.select('Metric').value, metric);
    assert.equal(app.select('History period').value, period);
  });
}

for (const strict of [false, true]) test(`UX-01B retry publication mismatch waits for existing freshness reconciliation${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mount(ctx, false, companies, { strict });
  await app.completeCompany('AAPL', '1000000000');
  await app.change(app.select('Metric'), 'net_income');
  const path = companyPath('AAPL', 'financials/metrics/net_income');
  await app.release(app.request(path), { detail: 'Synthetic outage' }, 503);
  await retryTwice(app, 'Retry history');
  const count = dependentRequests(app).length;
  await app.release(app.request(path), {}, 409, 1);
  assert.match(app.trends().textContent, /Waiting for publication version/);
  assert.ok([...app.trends().querySelectorAll('button')].every(button => button.disabled));
  assert.equal(dependentRequests(app).length, count, 'No immediate retry using the rejected pin');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
  assert.equal(dependentRequests(app).length, count, 'Rejected version zero remains closed');
  await retryTwice(app, 'Retry data check');
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1));
  assert.equal(dependentRequests(app).length, count + 3, 'Existing reconciliation reloads each dependent once');
  const recovered = app.request(path);
  assert.equal(recovered.init.headers['X-FinLens-Data-Version'], '1');
  await app.release(recovered, history('AAPL', '300000000', 'net_income'));
  assert.match(app.trends().querySelector('table').textContent, /Net income.*\$300M/);
  assert.equal(app.select('Metric').value, 'net_income');
});

for (const status of ['unavailable', 'not_applicable']) for (const afterRetry of [false, true]) {
  test(`UX-01B successful ${status} history has no retry${afterRetry ? ' after recovery' : ''}`, async ctx => {
    const app = await mount(ctx), path = companyPath('AAPL', 'financials/metrics/revenue');
    if (afterRetry) {
      await app.release(app.request(path), { detail: 'Synthetic outage' }, 503);
      await retryTwice(app, 'Retry history');
    }
    const reason = 'Synthetic successful history availability reason.';
    await app.release(app.request(path), { ...history('AAPL', null), history: [], status, reason });
    assert.ok(app.trends().textContent.includes(reason));
    assert.ok(!app.trends().querySelector('[role="alert"]'));
    assert.equal(app.trends().querySelector('[aria-live]').getAttribute('aria-busy'), 'false');
    assert.ok(![...app.trends().querySelectorAll('button')].some(button => button.textContent === 'Retry history'));
  });
}

// SEC-NLP-01B fixtures use canonical source identities. Existing fixtures and
// assertions above are preserved; all requests still use mount's synthetic fetch.
const toneAccession = '0000320193-26-000020';
function toneSecUrl(accession = toneAccession) {
  return `https://www.sec.gov/Archives/edgar/data/320193/${accession.replaceAll('-', '')}/${accession}-index.html`;
}
function toneResponse(version = 0, chunk = 'chunk_0000') {
  return { ticker: 'AAPL', company_cik: '0000320193', company_name: 'Synthetic Apple fixture', data_version: version, evidence_version: 0,
    publication: { accession_number: toneAccession, data_version: 0, content_digest: 'a'.repeat(64) },
    source: { chunk_id: chunk, form: '10-Q', filed: '2026-07-31', filename: 'report.htm', sec_url: toneSecUrl() },
    scope: 'published_chunk', offsets: 'unicode_code_point', text: '  📈\r\nSTRONG no loss; weak <script>unsafe()</script> e\u0301',
    tone: { method_version: 'sec-filing-tone-v1', lexicon_version: 'authored-finance-tone-v1', status: 'scored', reason: null,
      score: { numerator: 0, denominator: 1 }, token_count: 8, positive_count: 1, negative_count: 1, negated_count: 1,
      matches: [{ text: 'STRONG', term: 'strong', start: 5, end: 11, polarity: 'positive', negator_span: null },
        { text: 'loss', term: 'loss', start: 15, end: 19, polarity: 'negative', negator_span: [12, 14] },
        { text: 'weak', term: 'weak', start: 21, end: 25, polarity: 'negative', negator_span: null }] } };
}
const toneRequests = app => app.requests.filter(request => request.path.endsWith('/tone'));
const tonePath = (chunk = 'chunk_0000') => `/companies/AAPL/filings/${toneAccession}/chunks/${chunk}/tone`;
async function toneDeliver(app, request, value, status = 200, code = null) {
  assert.equal(request.released, false); request.released = true;
  await act(async () => request.resolve(new Response(JSON.stringify(value), { status, headers: {
    'X-FinLens-Data-Version': request.init.headers['X-FinLens-Data-Version'], ...(code ? { 'X-FinLens-Error-Code': code } : {}),
  } })));
}
async function mountToneEvidence(ctx, { strict = false, version = 0, scope = 'filing', passages = 1, badSource = null } = {}) {
  const app = await mount(ctx, false, companies, { initialVersion: version, strict });
  await app.release(app.request(companyPath('AAPL', 'financials/summary')), summary('AAPL', '1000000000'));
  await app.release(app.request(companyPath('AAPL', 'financials/metrics/revenue')), history('AAPL', '1000000000'));
  const source = { ...filing('AAPL'), accession_number: toneAccession, filed: '2026-07-31', sec_url: toneSecUrl() };
  await app.release(app.request(companyPath('AAPL', 'sources')), [source, { ...source, accession_number: '0000320193-25-000001', sec_url: toneSecUrl('0000320193-25-000001') }]);
  if (scope === 'company') await app.change(app.select('Evidence search scope'), 'company');
  const query = 'tone fixture research';
  await app.change(app.host.querySelector('textarea'), query); await app.click('Research question');
  await app.release(app.request(companyPath('AAPL', 'research-answer')), directAnswer('AAPL', query));
  const citations = Array.from({ length: passages }, (_, index) => ({ ...context('AAPL').citations[0], accession_number: toneAccession,
    company_cik: scope === 'company' ? '0000320193' : undefined, chunk_id: `chunk_${String(index).padStart(4, '0')}`,
    filename: 'report.htm', filed: source.filed, sec_url: toneSecUrl(), citation_id: `source_${index + 1}`, start_char: 9000 + index * 3000, end_char: 12000 + index * 3000 }));
  if (badSource) Object.assign(citations[0], badSource);
  const text = 'Search serialization is separate from the exact tone response. Strong no loss; weak.';
  const evidence = { ticker: 'AAPL', company_name: 'Synthetic Apple fixture', query, evidence_status: 'sufficient', citations,
    context: citations.map(citation => scope === 'company' ? companySource(citation, text)
      : `[SOURCE ${citation.citation_id}]\ntext: |-\n  ${text}\n[END SOURCE ${citation.citation_id}]`).join('\n\n'),
    ...(scope === 'company' ? { retrieval_scope: 'company', company_cik: '0000320193', data_version: version, evidence_version: 0,
      searched_accessions: [toneAccession], excluded_publication_count: 0 } : { accession_number: toneAccession }) };
  await app.release(app.request(scope === 'company' ? companyPath('AAPL', 'context') : companyPath('AAPL', `filings/${toneAccession}/context`)), evidence);
  return app;
}

for (const strict of [false, true]) for (const version of [0, 1]) for (const scope of ['filing', 'company']) {
  test(`SEC-NLP-01B mounted ${scope} tone at pin ${version}${strict ? ' in StrictMode' : ''} is explicit, source-bound and accessible`, async ctx => {
    const app = await mountToneEvidence(ctx, { strict, version, scope, passages: 2 });
    assert.equal(toneRequests(app).length, 0);
    await act(async () => app.host.querySelector('.evidence-card details summary').click());
    assert.equal(toneRequests(app).length, 0, 'Evidence expansion must not inspect tone');
    const controls = [...app.host.querySelectorAll('.passage-tone > button')];
    assert.equal(new Set(controls.map(button => button.getAttribute('aria-controls'))).size, 2);
    const trigger = controls[0]; trigger.focus();
    assert.equal(document.activeElement, trigger);
    await act(async () => { trigger.click(); trigger.click(); });
    await act(async () => trigger.click());
    assert.equal(toneRequests(app).length, 1, 'Synchronous and post-render duplicate clicks cannot cancel or duplicate');
    const request = app.request(tonePath());
    assert.equal(request.init.signal.aborted, false);
    assert.deepEqual(request.init.headers, { 'X-FinLens-Data-Version': String(version) });
    assert.equal(request.params.size, 0); assert.equal(request.init.body, undefined);
    const panel = app.host.querySelector('.passage-tone section');
    assert.equal(panel.hidden, false); assert.equal(panel.getAttribute('aria-busy'), 'true');
    assert.equal(trigger.getAttribute('aria-disabled'), 'true');
    assert.match(panel.querySelector('[role="status"]').textContent, /Inspecting/);
    await app.release(request, toneResponse(version));
    assert.equal(panel.getAttribute('aria-busy'), 'false');
    assert.equal(panel.querySelector('.tone-passage').textContent, toneResponse(version).text);
    assert.deepEqual([...panel.querySelectorAll('.tone-passage mark')].map(mark => mark.textContent), ['STRONG', 'loss', 'weak']);
    assert.equal(panel.querySelectorAll('script').length, 0);
    assert.match(panel.textContent, /<script>unsafe\(\)<\/script>/);
    assert.match(panel.textContent, /Passage lexical tone proxy/);
    assert.match(panel.textContent, /not predictive sentiment, confidence, market risk, investment advice or a whole-filing conclusion/);
    assert.match(panel.textContent, /0\/1/); assert.match(panel.textContent, /Negated, excluded: 1/);
    assert.match(panel.textContent, /negator \[12, 14\)/);
    assert.match(panel.textContent, /CIK 0000320193/); assert.match(panel.textContent, /Filing publication 0/);
    const link = panel.querySelector('a'); assert.equal(link.href, toneSecUrl()); assert.equal(link.hash, '');
    assert.equal(link.rel, 'noopener noreferrer');
    assert.ok(app.host.querySelector('.direct-answer'), 'Tone must preserve the independent answer');
    await app.click('Close passage tone');
    assert.equal(panel.hidden, true); assert.equal(document.activeElement, trigger);
    assert.equal(toneRequests(app).length, 1);
  });
}

for (const badSource of [{ sec_url: 'https://www.sec.gov/other' }, { company_cik: '0000019617' }, { filename: '../report.htm' }, { accession_number: '0000320193-25-000001' }]) {
  test(`SEC-NLP-01B mounted unverified source ${JSON.stringify(badSource)} cannot request tone`, async ctx => {
    const app = await mountToneEvidence(ctx, { badSource });
    assert.equal(app.host.querySelector('.passage-tone button').disabled, true);
    assert.match(app.host.querySelector('.passage-tone').textContent, /verified passage source/);
    assert.equal(toneRequests(app).length, 0);
  });
}

for (const strict of [false, true]) test(`SEC-NLP-01B cancel and stale callbacks cannot unlock a replacement${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mountToneEvidence(ctx, { strict });
  await app.click('Inspect passage tone'); const old = app.request(tonePath());
  await app.click('Cancel passage tone'); assert.equal(old.init.signal.aborted, true);
  await app.click('Inspect passage tone'); const current = app.request(tonePath());
  const count = app.requests.length;
  await app.release(old, {}, 409, 1);
  assert.equal(app.requests.length, count, 'Cancelled mismatch cannot reconcile or unlock the current request');
  assert.equal(current.init.signal.aborted, false);
  await app.click('Inspecting passage tone…'); assert.equal(toneRequests(app).length, 2);
  await app.release(current, toneResponse());
  assert.match(app.host.querySelector('.tone-summary').textContent, /0\/1/);
});

for (const strict of [false, true]) test(`SEC-NLP-01B transient failures and timeout allow only explicit bounded retry${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mountToneEvidence(ctx, { strict }); const expire = researchDeadlineClock(ctx);
  try {
  await app.click('Inspect passage tone'); const old = app.request(tonePath());
  await expire();
  assert.equal(old.init.signal.aborted, true);
  assert.match(app.host.querySelector('.passage-tone [role="alert"]').textContent, /too long/);
  assert.equal(toneRequests(app).length, 1);
  await retryTwice(app, 'Retry passage tone'); const retry = app.request(tonePath());
  assert.equal(toneRequests(app).length, 2);
  await app.release(old, toneResponse());
  assert.equal(app.host.querySelector('.tone-summary'), null);
  assert.equal(retry.init.signal.aborted, false);
  await toneDeliver(app, retry, { detail: 'Do not surface internal diagnostics' }, 503, 'DATABASE_BUSY');
  assert.match(app.host.querySelector('.passage-tone [role="alert"]').textContent, /database is busy/);
  assert.doesNotMatch(app.host.textContent, /Do not surface internal diagnostics/);
  assert.equal(toneRequests(app).length, 2);
  await retryTwice(app, 'Retry passage tone'); assert.equal(toneRequests(app).length, 3);
  await app.release(app.request(tonePath()), toneResponse());
  assert.ok(app.host.querySelector('.tone-summary'));
  assert.ok(app.host.querySelector('.direct-answer'));
  } finally { ctx.mock.timers.reset(); }
});

for (const [code, status, message] of [
  ['TONE_INPUT_UNSUPPORTED', 409, /unsupported/], ['EVIDENCE_PENDING', 409, /incomplete or changed/],
  ['SEARCH_SCOPE_TOO_LARGE', 409, /resource limit/], ['TONE_CHUNK_NOT_FOUND', 404, /no longer available/], ['TONE_INVALID_INPUT', 422, /could not be verified/],
]) test(`SEC-NLP-01B ${code} has an explicit outcome without blind retry`, async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone');
  await toneDeliver(app, app.request(tonePath()), { detail: 'Private fixture detail must not render' }, status, code);
  const panel = app.host.querySelector('.passage-tone');
  assert.match(panel.querySelector('[role="alert"]').textContent, message);
  assert.ok(![...panel.querySelectorAll('button')].some(button => button.textContent === 'Retry passage tone'));
  assert.equal(toneRequests(app).length, 1); assert.ok(app.host.querySelector('.direct-answer'));
});

test('SEC-NLP-01B malformed successful source fails closed without tone attribution and permits explicit recovery', async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone');
  const bad = toneResponse(); bad.source.sec_url += '#invented-passage';
  await app.release(app.request(tonePath()), bad);
  const panel = app.host.querySelector('.passage-tone');
  assert.match(panel.querySelector('[role="alert"]').textContent, /source could not be verified/);
  assert.equal(panel.querySelector('a'), null); assert.equal(panel.querySelector('.tone-passage'), null);
  await retryTwice(app, 'Retry passage tone'); await app.release(app.request(tonePath()), toneResponse());
  assert.equal(panel.querySelector('a').href, toneSecUrl());
});

test('P2 token_count rejects eight-token Unicode response claiming forty before rendering attribution', async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone');
  const value = toneResponse(); value.tone.token_count = 40;
  await app.release(app.request(tonePath()), value);
  const panel = app.host.querySelector('.passage-tone');
  const alert = panel.querySelector('[role="alert"]');
  assert.ok(alert, 'Contradictory token_count must fail before showing Tokens: 40');
  assert.match(alert.textContent, /could not be verified/);
  assert.equal(panel.querySelector('.tone-summary'), null);
  assert.equal(panel.querySelector('.tone-passage'), null);
  assert.equal(panel.querySelector('a'), null);
  assert.doesNotMatch(panel.textContent, /Tokens: 40/);
  assert.ok(app.host.querySelector('.direct-answer'));
});

for (const reason of ['no_tokens', 'no_lexicon_matches', 'all_matches_negated']) test(`SEC-NLP-01B ${reason} is an explained success, never balanced zero or retry`, async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone');
  const value = toneResponse(); const negated = reason === 'all_matches_negated';
  value.text = negated ? 'not strong' : reason === 'no_tokens' ? '...' : '2026';
  Object.assign(value.tone, { status: 'unscorable', reason, score: null, token_count: negated ? 2 : reason === 'no_tokens' ? 0 : 1,
    positive_count: 0, negative_count: 0, negated_count: negated ? 1 : 0,
    matches: negated ? [{ text: 'strong', term: 'strong', start: 4, end: 10, polarity: 'positive', negator_span: [0, 3] }] : [] });
  await app.release(app.request(tonePath()), value);
  const panel = app.host.querySelector('.passage-tone');
  assert.match(panel.querySelector('.tone-summary').textContent, /No score is available/);
  assert.doesNotMatch(panel.querySelector('.tone-summary').textContent, /0\/1/);
  assert.equal(panel.querySelector('[role="alert"]'), null);
  assert.ok(![...panel.querySelectorAll('button')].some(button => button.textContent === 'Retry passage tone'));
});

for (const selection of ['query', 'scope', 'company', 'filing', 'version']) test(`SEC-NLP-01B ${selection} change cancels tone and rejects ignored-abort success`, async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone'); const old = app.request(tonePath());
  if (selection === 'query') await app.change(app.host.querySelector('textarea'), 'new query');
  if (selection === 'scope') await app.change(app.select('Evidence search scope'), 'company');
  if (selection === 'company') await app.change(app.host.querySelector('#company'), 'JPM');
  if (selection === 'filing') await app.change(app.select('Indexed SEC filing'), '0000320193-25-000001');
  if (selection === 'version') { await focusCheck(); await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 1)); }
  assert.equal(old.init.signal.aborted, true);
  await app.release(old, toneResponse());
  assert.equal(app.host.querySelector('.tone-passage'), null); assert.equal(toneRequests(app).length, 1);
});

test('SEC-NLP-01B hiding extra evidence cancels its passage request without requesting siblings', async ctx => {
  const app = await mountToneEvidence(ctx, { passages: 3 });
  await app.click('Show more evidence (1)');
  await act(async () => app.host.querySelectorAll('.passage-tone > button')[2].click());
  const pending = app.request(tonePath('chunk_0002'));
  await app.click('Show less evidence'); assert.equal(pending.init.signal.aborted, true);
  await app.release(pending, toneResponse(0, 'chunk_0002'));
  await app.click('Show more evidence (1)');
  assert.equal(app.host.querySelector('.tone-passage'), null); assert.equal(toneRequests(app).length, 1);
});

for (const strict of [false, true]) for (const version of [0, 1]) test(`SEC-NLP-01B obsolete tone ${version} 409 cannot reject verified ${version + 1}${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mountToneEvidence(ctx, { strict, version });
  await app.click('Inspect passage tone'); const old = app.request(tonePath());
  await focusCheck(); const check = app.request(companyPath('AAPL', 'freshness'));
  const checks = app.requests.filter(request => request.path.endsWith('/freshness')).length;
  await act(async () => {
    app.deliverBeforeCommit(check, freshnessFixture('AAPL', version + 1, 1));
    await drainResponseMicrotasks();
    assert.ok(app.request('/companies'), 'Newer freshness is verified before React commits cancellation');
    assert.equal(old.init.signal.aborted, false);
    app.deliverBeforeCommit(old, {}, 409, version + 1);
    await drainResponseMicrotasks();
  });
  assert.equal(app.requests.filter(request => request.path.endsWith('/freshness')).length, checks);
  assert.equal(toneRequests(app).length, 1, 'Version advancement does not replay tone');
  assert.equal(app.host.querySelector('.tone-passage'), null);
  assert.match(app.host.querySelector('[aria-label="Data freshness"]').textContent, new RegExp(`version ${version + 1}`));
});

test('SEC-NLP-01B current tone 409 invalidates its pin and never automatically replays tone', async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone');
  const checks = app.requests.filter(request => request.path.endsWith('/freshness')).length;
  await app.release(app.request(tonePath()), {}, 409, 1);
  assert.equal(app.requests.filter(request => request.path.endsWith('/freshness')).length, checks + 1);
  assert.match(app.host.textContent, /Published data changed/);
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
  assert.match(app.host.textContent, /Could not verify this company’s data version/);
  assert.equal(toneRequests(app).length, 1);
});

test('SEC-NLP-01B long match lists disclose progressively without requests or text loss', async ctx => {
  const app = await mountToneEvidence(ctx); await app.click('Inspect passage tone');
  const value = toneResponse(); value.text = 'strong '.repeat(25);
  Object.assign(value.tone, { token_count: 25, positive_count: 25, negative_count: 0, negated_count: 0,
    score: { numerator: 1, denominator: 1 }, matches: Array.from({ length: 25 }, (_, index) => ({ text: 'strong', term: 'strong',
      start: index * 7, end: index * 7 + 6, polarity: 'positive', negator_span: null })) });
  await app.release(app.request(tonePath()), value);
  assert.equal(app.host.querySelectorAll('.tone-matches li').length, 20);
  const count = app.requests.length;
  await app.click('Show more matched terms');
  assert.equal(app.host.querySelectorAll('.tone-matches li').length, 25);
  assert.equal(app.host.querySelector('.tone-passage').textContent, value.text);
  assert.equal(app.requests.length, count);
});

for (const strict of [false, true]) for (const action of ['close', 'edit']) test(`SEC-NLP-01B parsed tone success before ${action} commit cannot survive${strict ? ' in StrictMode' : ''}`, async ctx => {
  const app = await mountToneEvidence(ctx, { strict }); await app.click('Inspect passage tone');
  const request = app.request(tonePath());
  await act(async () => {
    app.deliverBeforeCommit(request, toneResponse());
    await drainResponseMicrotasks();
    assert.equal(request.init.signal.aborted, false, 'Response validation and transport cleanup have already completed');
    assert.equal(app.host.querySelector('.tone-passage'), null, 'React has not committed the queued success');
    if (action === 'close') [...app.host.querySelectorAll('button')].find(button => button.textContent === 'Cancel passage tone').click();
    else {
      const editor = app.host.querySelector('textarea');
      Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set.call(editor, 'changed before commit');
      editor.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    }
  });
  assert.equal(app.host.querySelector('.tone-passage'), null);
  assert.equal(toneRequests(app).length, 1);
  if (action === 'close') {
    await app.click('Inspect passage tone'); assert.equal(toneRequests(app).length, 2);
    await app.release(app.request(tonePath()), toneResponse());
    assert.ok(app.host.querySelector('.tone-passage'));
  }
});
