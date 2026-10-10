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
  return { ticker, metric, unit: 'USD', requested_period: 'quarter', status: 'available', reason: null,
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

async function mount(ctx, configured = false, catalog = companies) {
  const requests = [];
  // Intentionally ignore AbortSignal when resolving: cancellation can race with
  // response delivery. This exercises rendered-state protection, not the mock.
  ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
    const url = new URL(input, 'http://finlens.test');
    assert.equal(url.origin, 'http://finlens.test', 'No external requests are allowed');
    assert.ok(url.pathname.startsWith('/api/finlens/'));
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    requests.push({ path: url.pathname.slice('/api/finlens'.length), params: url.searchParams, init, resolve, released: false });
    return promise;
  });
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  ctx.after(async () => { await act(async () => root.unmount()); host.remove(); localStorage.clear(); });
  await act(async () => root.render(React.createElement(Home)));
  function request(path, params = {}) {
    const found = requests.find(item => !item.released && item.path === path && Object.entries(params).every(([key, value]) => item.params.get(key) === value));
    assert.ok(found, `Expected pending request ${path} ${JSON.stringify(params)}`);
    return found;
  }
  async function release(item, payload, status = 200, version = item.init.headers?.['X-FinLens-Data-Version'] ?? null) {
    assert.equal(item.released, false); item.released = true;
    await act(async () => item.resolve(new Response(JSON.stringify(payload), {
      status, headers: { 'Content-Type': 'application/json', ...(version !== null ? { 'X-FinLens-Data-Version': String(version) } : {}), ...(status === 502 ? { 'X-FinLens-Error-Code': 'UPSTREAM_FAILURE' } : {}) },
    })));
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
  await release(request('/capabilities'), { research_mode: true, ai_analysis_configured: configured });
  await release(request('/companies'), catalog);
  return { host, requests, request, release, change, click, select, snapshot, trends, evidence, completeCompany, search };
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
  assert.match(app.host.querySelector('.ai-panel').textContent, /Not configured/);
  assert.equal([...app.host.querySelectorAll('button')].find(button => button.textContent === 'Generate AI analysis').disabled, true);
  assert.equal(app.requests.filter(request => request.path.endsWith('/answer')).length, 0);
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
  assert.match(app.snapshot().querySelector('.secondary-metrics').textContent, /Free cash flowUnavailable/);
  assert.match(app.snapshot().querySelector('.metric-grid').textContent, /Revenue\$1B/);
  assert.deepEqual([...app.select('Snapshot period').options].map(option => option.value), ['quarter', 'half_year', 'nine_months', 'annual']);
  const count = app.requests.length;
  await app.change(app.select('Snapshot period'), 'half_year');
  assert.equal(app.requests.length, count, 'Selecting a confirmed mode reuses its snapshot');
  assert.equal(cashHints(app).length, 0);
  assert.match(app.snapshot().querySelector('.period-label').textContent, /^Half-year YTD.*Jun 30, 2025/);
  assert.match(app.snapshot().querySelector('.secondary-metrics').textContent, /Free cash flow\$600M/);
  await app.change(app.select('Snapshot period'), 'quarter');
  assert.equal(app.requests.length, count, 'Returning to quarter does not refetch or rediscover');
  assert.equal(cashHints(app).length, 3);
  assert.match(app.snapshot().querySelector('.secondary-metrics').textContent, /Free cash flowUnavailable/);
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
  assert.match(app.snapshot().querySelector('.secondary-metrics').textContent, /Free cash flowUnavailable/);
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
  assert.match(app.snapshot().querySelector('.secondary-metrics').textContent, /Free cash flowUnavailable/);
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
  assert.match(app.snapshot().querySelector('.secondary-metrics').textContent, /Operating cash flow\$800M.*Capital expenditures\$200M.*Free cash flow\$600M/);
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  await app.release(app.request(companyPath('AAPL', 'freshness')), freshnessFixture('AAPL', 0));
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
  const app = await mount(ctx);
  const old = app.request(companyPath('AAPL', 'freshness'));
  await app.change(app.host.querySelector('#company'), 'JPM');
  await app.completeCompany('JPM', '2000000000');
  await app.release(app.request(companyPath('JPM', 'freshness')), freshnessFixture('JPM', 0));
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
  await app.release(app.request(companyPath('AAPL','freshness')), freshnessFixture('AAPL',0));
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
  await app.release(app.request(companyPath('AAPL','freshness')),freshnessFixture('AAPL',1,1));
  const oldCatalog = app.request('/companies');
  await app.change(app.host.querySelector('#company'),'JPM');
  assert.equal(oldCatalog.init.signal.aborted,true);
  await app.completeCompany('JPM','2000000000');
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
