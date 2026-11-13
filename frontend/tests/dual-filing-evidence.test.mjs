import test, { describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

// Own the DOM only while this mounted suite is running.
describe('dual filing evidence', { concurrency: false }, () => {
const require = createRequire(import.meta.url), cache = new Map();
const globalKeys = ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
let previousGlobals;
let dom, createRoot, Component, version = 0, changes = 0;
const changed = () => { changes++; };
function load(path) {
  if (cache.has(path)) return cache.get(path);
  const exports = {}; cache.set(path, exports);
  const output = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function('require', 'exports', output)(name => {
    if (name === '@/components/research-freshness') return { useResearchVersion: () => ({ version, changed }) };
    if (name.startsWith('@/') || name.startsWith('.')) {
      const base = name.startsWith('@/') ? fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url))
        : fileURLToPath(new URL(name, pathToFileURL(path)));
      return load(['.tsx', '.ts'].map(ext => base + ext).find(existsSync));
    }
    return require(name);
  }, exports);
  return exports;
}
before(async () => {
  previousGlobals = new Map(globalKeys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent']) Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, writable: true, value: true });
  ({ createRoot } = await import('react-dom/client'));
  Component = load(fileURLToPath(new URL('../components/dual-filing-evidence.tsx', import.meta.url))).default;
});
after(() => {
  dom.window.close();
  for (const [key, descriptor] of previousGlobals) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
});
const company = { id: 1, ticker: 'AAA', cik: '0000900001', name: 'Synthetic Alpha', exchange: 'TEST', has_indexed_filing: true, indexed_filing_count: 2 };
const acc = suffix => `${company.cik}-25-${suffix}`;
const url = accession => `https://www.sec.gov/Archives/edgar/data/900001/${accession.replaceAll('-', '')}/${accession}-index.html`;
function filing(suffix = '000001') { const accession_number = acc(suffix); return { accession_number, sec_url: url(accession_number),
  form: suffix === '000001' ? '10-K' : '10-Q', filed: suffix === '000001' ? '2025-02-01' : '2025-05-01', period_start: null, period_end: null, metrics: [], has_filing_chunks: true }; }
const sources = () => [filing(), filing('000002')];
function evidence(f, query = 'supply chain', count = 1) {
  const text = `Synthetic ${f.accession_number} original supply chain wording. 😀 <script>literal()</script>\n\n  Unchanged text.`;
  const citations = Array.from({ length: count }, (_, index) => ({ citation_id: `source_${index + 1}`, chunk_id: `chunk_${String(index).padStart(4, '0')}`,
    accession_number: f.accession_number, form: f.form, filed: f.filed, filename: 'synthetic.htm', start_char: index * 3000,
    end_char: index * 3000 + Array.from(text).length, sec_url: f.sec_url, similarity: .8, semantic_similarity: .8, lexical_score: 1, hybrid_score: 1, evidence_reason: 'strong_lexical' }));
  return { ticker: company.ticker, company_name: company.name, accession_number: f.accession_number, query, citations,
    evidence_status: count ? 'sufficient' : 'insufficient', context: citations.map(c => `[SOURCE ${c.citation_id}]\nchunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: 0.800000\ntext: |-\n${text.split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE ${c.citation_id}]`).join('\n\n') };
}
async function mount(ctx, { strict = false, pin = 0, inventory = sources(), component = Component } = {}) {
  assert.equal(document, dom.window.document, 'Two-filing mounts must own the same DOM realm');
  version = pin; changes = 0;
  const requests = [];
  ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
    const u = new URL(input, 'http://finlens.test'); assert.equal(u.origin, 'http://finlens.test');
    let resolve, reject; const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
    requests.push({ url: u, init, resolve, reject }); return promise; // Intentionally ignore cancellation.
  });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  let props = { company, sources: inventory }, unmounted = false;
  const render = () => root.render(strict ? React.createElement(React.StrictMode, null, React.createElement(component, props)) : React.createElement(component, props));
  async function update(next = {}, pin = version) { version = pin; props = { ...props, ...next }; await act(async () => render()); }
  async function unmount() { if (!unmounted) { unmounted = true; await act(async () => root.unmount()); host.remove(); } }
  ctx.after(unmount); await update();
  async function change(node, value) { await act(async () => { Object.getOwnPropertyDescriptor(node.tagName === 'SELECT' ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLTextAreaElement.prototype, 'value').set.call(node, value); node.dispatchEvent(new Event(node.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); }); }
  async function submit() { await act(async () => host.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))); }
  async function release(request, body, { status = 200, header = request.init.headers['X-FinLens-Data-Version'] } = {}) {
    await act(async () => request.resolve(new Response(JSON.stringify(body), { status,
      headers: { ...(header === null ? {} : { 'X-FinLens-Data-Version': String(header) }) } })));
  }
  return { host, requests, update, change, submit, release, unmount,
    query: value => change(host.querySelector('textarea'), value), columns: () => [...host.querySelectorAll('.dual-filing-column')] };
}
for (const strict of [false, true]) for (const pin of [0, 7]) test(`dual filing mounted pin ${pin} strict ${strict}: exact pair, original text, namespaced sources and local disclosure`, async ctx => {
  const app = await mount(ctx, { strict, pin }); assert.equal(app.requests.length, 0);
  await app.query('  supply chain  '); assert.equal(app.requests.length, 0);
  const form = app.host.querySelector('form');
  await act(async () => { form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
  assert.equal(app.requests.length, 2);
  app.requests.forEach((request, index) => {
    assert.equal(request.url.pathname, `/api/finlens/companies/AAA/filings/${sources()[index].accession_number}/context`);
    assert.equal(request.url.search, '?q=supply+chain&limit=5');
    assert.deepEqual(request.init.headers, { 'X-FinLens-Data-Version': String(pin) }); assert.equal(request.init.body, undefined);
  });
  await app.release(app.requests[1], evidence(filing('000002'), 'supply chain', 5));
  assert.equal(app.columns()[0].querySelectorAll('article').length, 0); assert.equal(app.columns()[1].querySelectorAll('article').length, 5);
  await app.release(app.requests[0], evidence(filing(), 'supply chain', 5));
  assert.equal(app.host.querySelectorAll('article').length, 10); assert.equal(app.host.querySelectorAll('script').length, 0);
  assert.equal(app.columns()[0].querySelector('.excerpt').textContent, `Synthetic ${acc('000001')} original supply chain wording. 😀 <script>literal()</script>\n\n  Unchanged text.`);
  assert.match(app.host.textContent, new RegExp(`${acc('000001')}/source_1`)); assert.match(app.host.textContent, new RegExp(`${acc('000002')}/source_1`));
  const detail = app.host.querySelector('summary'); detail.focus(); await act(async () => detail.click());
  assert.equal(document.activeElement, detail); assert.equal(detail.parentElement.open, true); assert.equal(app.requests.length, 2);
  assert.deepEqual([...app.columns()[1].querySelectorAll('a')].map(a => a.href), Array(6).fill(filing('000002').sec_url));
});
test('dual filing independent empty/error sides never borrow evidence', async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  await app.release(app.requests[0], evidence(filing(), 'supply chain', 0)); await app.release(app.requests[1], {}, { status: 503 });
  assert.match(app.columns()[0].textContent, /Insufficient evidence/); assert.doesNotMatch(app.columns()[0].textContent, /could not be verified/);
  assert.match(app.columns()[1].textContent, /could not be verified/); assert.equal(app.host.querySelectorAll('article').length, 0);
  await app.submit(); await app.release(app.requests[2], evidence(filing())); await app.release(app.requests[3], {}, { status: 503 });
  assert.equal(app.columns()[0].querySelectorAll('article').length, 1); assert.equal(app.columns()[1].querySelectorAll('article').length, 0);
});
for (const edit of ['question', 'filing', 'publication', 'company', 'inventory', 'cancel', 'unmount']) test(`dual filing ${edit} revokes both results and ignores late delivery`, async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  await app.release(app.requests[0], evidence(filing())); assert.equal(app.host.querySelectorAll('article').length, 1);
  if (edit === 'question') await app.query('competition');
  if (edit === 'filing') await app.change(app.host.querySelectorAll('select')[1], acc('000001'));
  if (edit === 'publication') await app.update({}, 1);
  if (edit === 'company') await app.update({ company: { ...company, ticker: 'BBB', cik: '0000900002', name: 'Synthetic Beta' } });
  if (edit === 'inventory') await app.update({ sources: [] });
  if (edit === 'cancel') { const button = app.host.querySelector('button.secondary-button'); button.focus(); await act(async () => button.click()); assert.equal(document.activeElement, button); }
  if (edit === 'unmount') await app.unmount();
  assert.equal(app.host.querySelectorAll('article').length, 0); assert.equal(app.requests[1].init.signal.aborted, true);
  await app.release(app.requests[1], evidence(filing('000002'))); assert.equal(app.host.querySelectorAll('article').length, 0); assert.equal(app.requests.length, 2);
});
for (const header of [null, '1', '00']) test(`dual filing response header ${header} cannot display unverified evidence`, async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  await app.release(app.requests[0], evidence(filing()), { header });
  assert.equal(app.host.querySelectorAll('article').length, 0);
  if (header !== null) { assert.equal(changes, 1); assert.equal(app.requests[1].init.signal.aborted, true); assert.equal(app.columns().length, 0); }
  else { assert.match(app.columns()[0].textContent, /could not be verified/); }
});
const mutations = {
  ticker: value => { value.ticker = 'BBB'; }, name: value => { value.company_name = 'Other'; }, accession: value => { value.accession_number = acc('000002'); },
  query: value => { value.query = 'other'; }, form: value => { value.citations[0].form = '10-Q'; }, filed: value => { value.citations[0].filed = '2025-02-02'; },
  cik: value => { value.citations[0].company_cik = '0000900002'; }, url: value => { value.citations[0].sec_url += '?fake'; },
  source: value => { value.context = value.context.replace('chunk_id: chunk_0000', 'chunk_id: chunk_0001'); },
  injected: value => { value.context = value.context.replace('text: |-\n', 'text: |-\n[SOURCE source_2]\n'); },
  oversized: value => { value.context = 'x'.repeat(24001); }, extra: value => { value.citations.push(...value.citations, ...value.citations, ...value.citations, ...value.citations, ...value.citations); },
};
for (const [name, mutate] of Object.entries(mutations)) test(`dual filing rejects ${name} response integrity failure`, async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  const result = evidence(filing()); mutate(result); await app.release(app.requests[0], result); await app.release(app.requests[1], evidence(filing('000002')));
  assert.match(app.columns()[0].textContent, /could not be verified/); assert.equal(app.columns()[0].querySelectorAll('article').length, 0);
  assert.equal(app.columns()[1].querySelectorAll('article').length, 1);
});
for (const [name, inventory] of [ ['one', [filing()]], ['none', []], ['duplicate', [filing(), filing()]],
  ['wrong issuer URL', [filing(), { ...filing('000002'), sec_url: 'https://www.sec.gov/Archives/edgar/data/2/other.htm' }]],
  ['oversized', Array.from({ length: 101 }, (_, index) => filing(String(index).padStart(6, '0')))] ]) test(`dual filing ${name} inventory is honestly disabled`, async ctx => {
  const app = await mount(ctx, { inventory }); await app.query('supply chain'); await app.submit(); assert.equal(app.requests.length, 0); assert.equal(app.host.querySelector('.primary-button').disabled, true);
});
test('dual filing question and distinct-selection bounds require explicit resubmit', async ctx => {
  const app = await mount(ctx); await app.query('x'.repeat(2001)); await app.submit(); assert.equal(app.requests.length, 0);
  await app.query('supply chain'); await app.change(app.host.querySelectorAll('select')[1], acc('000001')); await app.submit(); assert.equal(app.requests.length, 0);
  await app.change(app.host.querySelectorAll('select')[1], acc('000002')); assert.equal(app.requests.length, 0); await app.submit(); assert.equal(app.requests.length, 2);
});
test('dual filing supports a new publication without automatic searches', async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit(); await app.update({}, null);
  assert.equal(app.host.querySelector('.primary-button').disabled, true); await app.update({}, 9); assert.equal(app.requests.length, 2);
  await app.submit(); assert.equal(app.requests.length, 4); assert.equal(app.requests[2].init.headers['X-FinLens-Data-Version'], '9');
  await app.release(app.requests[0], evidence(filing()), { header: '100' }); assert.equal(changes, 0);
  await app.release(app.requests[2], evidence(filing())); await app.release(app.requests[3], evidence(filing('000002')));
  assert.equal(app.host.querySelectorAll('article').length, 2);
});
test('dual filing fixture capability matches existing sec_readonly route admission', () => {
  const policy = readFileSync(new URL('../../backend/app/release_policy.py', import.meta.url), 'utf8');
  const readonly = policy.split('READONLY_ROUTES = frozenset({')[1].split('})')[0];
  assert(readonly.includes('("GET", "/companies/{ticker}/filings/{accession_number}/context")'));
  const main = readFileSync(new URL('../../backend/app/main.py', import.meta.url), 'utf8');
  const route = main.split('def get_company_filing_context(')[1].split('@app.post(')[0];
  assert.match(route, /with read_session\(HttpSessionLocal\)/); assert.match(route, /require_published\(session, company.cik, accession_number\)/);
});
test('dual filing same-tick question round trip cannot resurrect an old run', async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  await app.release(app.requests[0], evidence(filing()));
  const input = app.host.querySelector('textarea');
  const set = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set;
  await act(async () => {
    set.call(input, 'other'); input.dispatchEvent(new Event('input', { bubbles: true }));
    set.call(input, 'supply chain'); input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  assert.equal(app.requests.length, 2); assert.equal(app.host.querySelectorAll('article').length, 0);
  await app.release(app.requests[1], evidence(filing('000002'))); assert.equal(app.host.querySelectorAll('article').length, 0);
  await app.submit(); assert.equal(app.requests.length, 4);
});
test('dual filing timeout settles only that side and permits explicit two-request retry', async ctx => {
  const app = await mount(ctx); await app.query('supply chain');
  const timers = [];
  ctx.mock.method(globalThis, 'setTimeout', (callback, delay) => { assert.equal(delay, 30000); timers.push(callback); return timers.length; });
  ctx.mock.method(globalThis, 'clearTimeout', () => {});
  await app.submit(); assert.equal(timers.length, 2); await act(async () => timers[0]());
  assert.match(app.columns()[0].textContent, /timed out/); assert.equal(app.requests[1].init.signal.aborted, false);
  await app.release(app.requests[1], evidence(filing('000002'))); assert.equal(app.columns()[1].querySelectorAll('article').length, 1);
  await app.release(app.requests[0], evidence(filing()), { header: '100' }); assert.equal(changes, 0); assert.match(app.columns()[0].textContent, /timed out/);
  await app.submit(); assert.equal(app.requests.length, 4);
});
test('dual filing browser fixtures pass actual evidence validation for both filings and pins zero/nonzero', () => {
  const fixtures = load(fileURLToPath(new URL('../e2e/fixtures/dual-filing-browser.ts', import.meta.url)));
  const data = load(fileURLToPath(new URL('../e2e/fixtures/data.ts', import.meta.url)));
  const lib = load(fileURLToPath(new URL('../lib/dual-filing-evidence.ts', import.meta.url)));
  for (const ticker of ['AAA', 'BBB']) for (const pin of [0, 7]) {
    const company = data.company(ticker), sources = fixtures.dualSources(ticker);
    assert.equal(lib.comparisonFilings(company, sources).length, 2);
    for (const source of sources) {
      const result = fixtures.dualEvidence(ticker, source.accession_number, 'supply chain', 5);
      assert.doesNotThrow(() => lib.validateComparisonEvidence(result, company, source, 'supply chain', pin));
      assert.doesNotThrow(() => lib.validateComparisonEvidence(fixtures.dualEvidence(ticker, source.accession_number, 'supply chain', 0), company, source, 'supply chain', pin));
    }
  }
});
test('dual filing browser request admission rejects route/pin/query/body violations before overrides', () => {
  const { validateDualRequest, dualSources } = load(fileURLToPath(new URL('../e2e/fixtures/dual-filing-browser.ts', import.meta.url)));
  const expected = { versions: { AAA: 0, BBB: 7 } };
  const valid = () => ({ method: 'GET', path: `/companies/AAA/filings/${dualSources('AAA')[1].accession_number}/context`, ticker: 'AAA', pin: '0',
    query: new URLSearchParams({ q: 'supply chain', limit: '5' }), body: null, request: { postData: () => null } });
  assert.doesNotThrow(() => validateDualRequest(valid(), expected));
  for (const patch of [{ method: 'POST' }, { pin: undefined }, { pin: '00' }, { pin: '1' }, { ticker: 'BBB' }, { path: '/companies/AAA/context' },
    { body: {} }, { request: { postData: () => '' } }, { query: new URLSearchParams('q=hi&limit=5&limit=5') }, { query: new URLSearchParams('q=hi&limit=6') },
    { query: new URLSearchParams('q=%20hi&limit=5') }, { query: new URLSearchParams({ q: 'x'.repeat(2001), limit: '5' }) }]) {
    assert.throws(() => validateDualRequest({ ...valid(), ...patch }, expected));
  }
});
test('dual filing is connected to the existing FilingResearch version-scoped inventory without an extra list request', async ctx => {
  const component = load(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url))).default;
  const app = await mount(ctx, { component });
  assert.equal(app.requests.length, 1); assert.equal(app.requests[0].url.pathname, '/api/finlens/companies/AAA/sources');
  await app.release(app.requests[0], sources()); assert.equal(app.requests.length, 1);
  const section = app.host.querySelector('.dual-filing-evidence'); assert.ok(section);
  assert.equal(section.querySelectorAll('select')[1].value, acc('000002'));
  await app.change(section.querySelector('textarea'), 'supply chain');
  await act(async () => section.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(app.requests.length, 3); assert.ok(app.requests.slice(1).every(request => request.url.pathname.endsWith('/context')));
  await app.release(app.requests[1], evidence(filing())); await app.release(app.requests[2], evidence(filing('000002')));
  assert.equal(section.querySelectorAll('article').length, 2);
  await app.update({}, 1); assert.equal(section.querySelectorAll('article').length, 0); assert.equal(app.requests.length, 4);
  assert.equal(app.requests[3].url.pathname, '/api/finlens/companies/AAA/sources'); assert.equal(app.requests[3].init.headers['X-FinLens-Data-Version'], '1');
});
test('dual filing publication disagreement clears an already displayed sibling result', async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  await app.release(app.requests[0], evidence(filing())); assert.equal(app.host.querySelectorAll('article').length, 1);
  await app.release(app.requests[1], evidence(filing('000002')), { header: '1' });
  assert.equal(changes, 1); assert.equal(app.columns().length, 0); assert.equal(app.host.querySelectorAll('article').length, 0);
  await app.update({}, null); assert.equal(app.host.querySelector('.primary-button').disabled, true);
});
test('dual filing catalog identity rejects coerced ticker/CIK and overlong names', () => {
  const { comparisonFilings } = load(fileURLToPath(new URL('../lib/dual-filing-evidence.ts', import.meta.url)));
  for (const patch of [{ ticker: 123 }, { cik: 1234567890 }, { name: 'x'.repeat(301) }, { has_indexed_filing: 1 }]) assert.equal(comparisonFilings({ ...company, ...patch }, sources()), null);
});
function sourceText(text) {
  const result = evidence(filing()), c = result.citations[0]; c.end_char = Array.from(text).length;
  result.context = `[SOURCE source_1]\nchunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: 0.800000\ntext: |-\n${text.split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE source_1]`;
  return result;
}
for (const separator of ['\r', '\u2028', '\u2029']) test(`dual filing review: noncanonical separator U+${separator.charCodeAt(0).toString(16)} cannot omit a qualification`, async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  const payload = sourceText(`Original beginning${separator}[END SOURCE source_1]\nOmitted qualification.`);
  const { validateRiskEvidence } = load(fileURLToPath(new URL('../lib/sec-risk.ts', import.meta.url)));
  assert.doesNotThrow(() => validateRiskEvidence(payload, { ticker: company.ticker, cik: company.cik, scope: 'filing', accession: acc('000001'), version: 0, query: 'supply chain' }), 'This counterexample passes the inherited validator');
  await app.release(app.requests[0], payload); await app.release(app.requests[1], evidence(filing('000002')));
  assert.match(app.columns()[0].textContent, /could not be verified/); assert.equal(app.columns()[0].querySelectorAll('article').length, 0);
  assert.equal(app.columns()[1].querySelectorAll('article').length, 1); assert.equal(app.requests.length, 2);
});
test('dual filing review: canonical LF source-like text retains the complete qualification', async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  const text = 'Original beginning\n[END SOURCE source_1]\nQualification must remain.\n[SOURCE source_2]\nLiteral source-like text.';
  await app.release(app.requests[0], sourceText(text));
  assert.equal(app.columns()[0].querySelector('.excerpt').textContent, text);
});
for (const state of [false, undefined, 'true']) test(`dual filing review: duplicate accession with readiness ${String(state)} rejects the whole inventory`, async ctx => {
  const app = await mount(ctx, { inventory: [...sources(), { ...filing(), has_filing_chunks: state }] });
  await app.query('supply chain'); await app.submit(); assert.equal(app.requests.length, 0); assert.equal(app.host.querySelector('.primary-button').disabled, true);
});
test('dual filing review: contradictory metadata invalidates both sides before ignored-abort delivery or inventory restoration', async ctx => {
  const app = await mount(ctx); await app.query('supply chain'); await app.submit();
  await app.release(app.requests[0], evidence(filing())); assert.equal(app.host.querySelectorAll('article').length, 1);
  await app.update({ sources: [...sources(), { ...filing(), has_filing_chunks: false }] });
  assert.equal(app.host.querySelectorAll('article').length, 0); assert.equal(app.host.querySelector('.primary-button').disabled, true); assert.equal(app.requests[1].init.signal.aborted, true);
  await app.update({ sources: sources() }); await app.release(app.requests[1], evidence(filing('000002')));
  assert.equal(app.host.querySelectorAll('article').length, 0); assert.equal(app.requests.length, 2);
  await app.submit(); assert.equal(app.requests.length, 4);
});
test('dual filing review: distinct legitimate metadata-only forms remain outside the selectable indexed pair', async ctx => {
  const metadata = { ...filing('000003'), form: '8-K', has_filing_chunks: false };
  const unknown = { ...filing('000004'), form: null, filed: null, has_filing_chunks: false };
  const app = await mount(ctx, { inventory: [...sources(), metadata, unknown] }); await app.query('supply chain');
  assert.deepEqual([...app.host.querySelector('select').options].map(option => option.value), ['', acc('000001'), acc('000002')]);
  await app.submit(); assert.equal(app.requests.length, 2);
  await app.release(app.requests[0], evidence(filing())); await app.release(app.requests[1], evidence(filing('000002')));
  assert.equal(app.host.querySelectorAll('article').length, 2);
});
for (const pin of [0, 7]) for (const header of [null, String(pin)]) test(`dual filing review: existing inventory request pin ${pin} requires returned header ${header}`, async ctx => {
  const component = load(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url))).default;
  const app = await mount(ctx, { component, pin }); assert.equal(app.requests.length, 1);
  assert.equal(app.requests[0].init.headers['X-FinLens-Data-Version'], String(pin));
  await app.release(app.requests[0], sources(), { header });
  const section = app.host.querySelector('.dual-filing-evidence'); await app.change(section.querySelector('textarea'), 'supply chain');
  await act(async () => section.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  if (header === null) {
    assert.equal(app.requests.length, 1); assert.equal(section.querySelector('.primary-button').disabled, true); assert.equal(section.querySelectorAll('.dual-filing-column').length, 0);
    assert.match(app.host.textContent, /Could not load the filing list/);
    const retry = [...app.host.querySelectorAll('button')].find(button => button.textContent === 'Retry filing list');
    await act(async () => retry.click()); assert.equal(app.requests.length, 2);
    await app.release(app.requests[1], sources()); assert.equal(app.requests.length, 2);
    await act(async () => section.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(app.requests.length, 4, 'Explicit inventory retry plus exactly two context requests');
  } else assert.equal(app.requests.length, 3, 'One existing inventory request plus exactly two contexts');
});
test('dual filing review: ordinary source-list callers retain optional-header semantics', async ctx => {
  const app = await mount(ctx); const api = load(fileURLToPath(new URL('../lib/finlens-api.ts', import.meta.url)));
  const pending = api.getFilingSources(company.ticker); assert.equal(app.requests.length, 1);
  await app.release(app.requests[0], sources(), { header: null }); assert.deepEqual(await pending, sources());
});
test('dual filing review: sources backend already supplies verified pin headers including zero', () => {
  const main = readFileSync(new URL('../../backend/app/main.py', import.meta.url), 'utf8');
  const route = main.split('def get_company_sources(')[1].split('@app.')[0];
  assert.match(route, /with read_session\(HttpSessionLocal\)/);
  assert.match(main, /if ticker and scope\["version"\] is not None:\s+response.headers\["X-FinLens-Data-Version"\] = str\(scope\["version"\]\)/);
  const freshness = readFileSync(new URL('../../backend/app/freshness_service.py', import.meta.url), 'utf8');
  assert.match(freshness, /scope\["version"\] = version/); assert.match(freshness, /scope\["expected"\] != str\(version\)/);
  const context = readFileSync(new URL('../../backend/app/rag_context_service.py', import.meta.url), 'utf8');
});
test('dual filing P3: same-form same-date filings expose distinct complete accessions beside native selectors', async ctx => {
  const first = filing(), second = { ...filing('000002'), form: first.form, filed: first.filed };
  const app = await mount(ctx, { inventory: [first, second] });
  const selects = [...app.host.querySelectorAll('select')], labels = [...app.host.querySelectorAll('.dual-filing-selection')];
  assert.deepEqual(labels.map(label => label.textContent), [`Accession ${first.accession_number}`, `Accession ${second.accession_number}`]);
  assert.equal(new Set(labels.map(label => label.id)).size, 2);
  selects.forEach((select, index) => {
    assert.equal(select.tagName, 'SELECT'); assert.equal(select.getAttribute('aria-describedby'), labels[index].id);
    assert.equal(document.getElementById(select.getAttribute('aria-describedby')), labels[index]);
    assert.equal(select.labels.length, 1); assert.equal(select.labels[0].contains(labels[index]), false, 'Description remains outside the selector accessible name');
    assert.equal(labels[index].classList.contains('wrap-anywhere'), true); assert.equal(labels[index].hidden, false);
  });
  assert.equal(app.requests.length, 0);
  await app.change(selects[0], second.accession_number);
  assert.equal(labels[0].textContent, `Accession ${second.accession_number}`); assert.equal(app.requests.length, 0);
});
test('dual filing P3: invalid or incomplete inventory cannot retain old selected-accession labels', async ctx => {
  const app = await mount(ctx);
  const labels = () => [...app.host.querySelectorAll('.dual-filing-selection')].map(node => node.textContent);
  assert.deepEqual(labels(), sources().map(source => `Accession ${source.accession_number}`));
  await app.update({ sources: [...sources(), { ...filing(), has_filing_chunks: false }] });
  assert.deepEqual(labels(), Array(2).fill('No verified indexed filing selected.'));
  await app.update({ sources: [filing()] }); assert.deepEqual(labels(), Array(2).fill('No verified indexed filing selected.'));
  await app.update({ sources: sources() }); assert.deepEqual(labels(), sources().map(source => `Accession ${source.accession_number}`));
  assert.equal(app.requests.length, 0);
});
test('dual filing P3: unverified publication hides selected identities until the existing pinned inventory reloads', async ctx => {
  const component = load(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url))).default;
  const app = await mount(ctx, { component }); await app.release(app.requests[0], sources());
  const labels = () => [...app.host.querySelectorAll('.dual-filing-selection')].map(node => node.textContent);
  assert.deepEqual(labels(), sources().map(source => `Accession ${source.accession_number}`));
  await app.update({}, 1); assert.equal(app.requests.length, 2);
  assert.deepEqual(labels(), Array(2).fill('No verified indexed filing selected.'));
  await app.release(app.requests[1], sources()); assert.deepEqual(labels(), sources().map(source => `Accession ${source.accession_number}`));
  assert.equal(app.requests.length, 2, 'Only the existing automatic inventory request occurs; no context or extra list request');
});
test('dual filing P3: missing publication pin cannot expose stale accession descriptions', async ctx => {
  const app = await mount(ctx); await app.update({}, null);
  assert.deepEqual([...app.host.querySelectorAll('.dual-filing-selection')].map(node => node.textContent), Array(2).fill('No verified indexed filing selected.'));
  assert.equal(app.requests.length, 0);
});
});
