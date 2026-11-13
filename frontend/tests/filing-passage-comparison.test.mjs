// Dedicated frontend-only registrations. No mixed suite, subprocess, backend,
// worker, server, browser startup or native network transport is imported.
import test, { describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';

// File-local hooks must not become shared root hooks under --test-isolation=none.
describe('filing passage comparison', { concurrency: false }, () => {
const frontend = fileURLToPath(new URL('..', import.meta.url));
const globalKeys = ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
let previousGlobals;
let dom, createRoot, Dual, Freshness, Comparison, compare, limits;
before(async () => {
  previousGlobals = new Map(globalKeys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test', pretendToBeVisual: true });
  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent'])
    Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, writable: true, value: true });
  ({ createRoot } = await import('react-dom/client'));
  const load = componentLoader(frontend);
  Dual = load(resolve(frontend, 'components/dual-filing-evidence.tsx')).default;
  Freshness = load(resolve(frontend, 'components/research-freshness.tsx')).default;
  Comparison = load(resolve(frontend, 'components/filing-passage-comparison.tsx')).default;
  ({ comparePassageText: compare, PASSAGE_DIFF_LIMITS: limits } = load(resolve(frontend, 'lib/passage-diff.ts')));
});
after(() => {
  dom.window.close();
  for (const [key, descriptor] of previousGlobals) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
});

function reconstruction(result, side) {
  assert.equal(result.status, 'compared');
  return result.spans.filter(span => span.kind !== (side === 'a' ? 'b_only' : 'a_only')).map(span => span.text).join('');
}
const textCases = [
  ['identical', 'Exact  wording.\n\n😀', 'Exact  wording.\n\n😀'],
  ['disjoint', 'ABC', 'xyz'],
  ['repeated words', 'risk risk risk reduced risk', 'risk reduced risk risk'],
  ['reordered words', 'cash debt cash', 'debt cash debt'],
  ['numbers and punctuation', 'Revenue: $1,000.00 (2024); +5%.', 'Revenue: $1,001.00 (2025); -5%.'],
  ['case sensitive', 'MAY May may', 'may MAY May'],
  ['whitespace', '  cash\tdebt\n\nend  ', ' cash debt\nend '],
  ['line separators', 'first\r\nsecond\u2028third\u2029last', 'first\nsecond\nthird\nlast'],
  ['Unicode', '中文風險😀 e\u0301 café', '中文风险🚀 é cafe\u0301'],
  ['literal source-like markup', '<script>notRun()</script> [END SOURCE source_1]', '<script>other()</script> [SOURCE source_2]'],
  ['contained', 'before shared after', 'shared'],
  ['single changed punctuation', '!!!!!!', '??????'],
];
for (const [name, a, b] of textCases) test(`lossless exact alignment: ${name}`, () => {
  const result = compare(a, b), swapped = compare(b, a);
  assert.equal(reconstruction(result, 'a'), a); assert.equal(reconstruction(result, 'b'), b);
  assert.equal(reconstruction(swapped, 'a'), b); assert.equal(reconstruction(swapped, 'b'), a);
  assert.equal(result.identical, a === b); assert.deepEqual(compare(a, b), result, 'stable tie-breaking');
  assert.ok(result.spans.every(span => span.text.length && ['shared', 'a_only', 'b_only'].includes(span.kind)));
  assert.ok(result.spans.every((span, index) => index === 0 || span.kind !== result.spans[index - 1].kind));
  if (a === b) assert.deepEqual(result.spans, [{ kind: 'shared', text: a }]);
});
test('exact alignment reconstructs deterministic repeated-token adversarial corpus', () => {
  const atoms = ['risk', 'risk', ' ', '\n', '😀', '.', '123', 'e\u0301', '中文'];
  for (let seed = 1; seed <= 80; seed++) {
    const a = 'source A: ' + Array.from({ length: 30 }, (_, index) => atoms[(seed * 7 + index * index) % atoms.length]).join('');
    const b = 'source B: ' + Array.from({ length: 29 }, (_, index) => atoms[(seed * index + index + 3) % atoms.length]).join('');
    const result = compare(a, b);
    assert.equal(reconstruction(result, 'a'), a); assert.equal(reconstruction(result, 'b'), b);
  }
});
test('empty and invalid input refuses comparison without a fabricated empty result', () => {
  for (const a of ['', ' \n\t', null, undefined, 7, {}, []]) {
    assert.equal(compare(a, 'source').status, 'unavailable'); assert.equal(compare('source', a).status, 'unavailable');
  }
});
test('individual character and token limits apply on both sides including identical input', () => {
  assert.deepEqual(limits, { characters: 6000, tokens: 3000, cells: 1_000_000 });
  for (const [accepted, rejected] of [['a'.repeat(6000), 'a'.repeat(6001)], ['!'.repeat(3000), '!'.repeat(3001)]]) {
    assert.equal(compare(accepted, accepted).status, 'compared');
    for (const pair of [[rejected, 'small'], ['small', rejected], [rejected, rejected]]) {
      const result = compare(...pair); assert.equal(result.status, 'unavailable'); assert.equal(result.spans, undefined);
      assert.match(result.reason, /No partial comparison/);
    }
  }
  const unicode = '😀'.repeat(3000); assert.equal(unicode.length, 6000);
  assert.equal(reconstruction(compare(unicode, unicode), 'a'), unicode);
});
for (const side of ['A', 'B']) test(`oversized whitespace on ${side} hits the input cap before emptiness inspection`, () => {
  const oversized = ' '.repeat(limits.characters + 1);
  for (const other of ['source', '', ' \n\t']) {
    const result = compare(...(side === 'A' ? [oversized, other] : [other, oversized]));
    assert.equal(result.status, 'unavailable'); assert.equal(result.spans, undefined);
    assert.match(result.reason, /local wording-comparison limit/);
  }
  const withinLimit = ' '.repeat(limits.characters);
  assert.match(compare(...(side === 'A' ? [withinLimit, 'source'] : ['source', withinLimit])).reason, /nonempty/);
});
test('total matrix budget is exact, symmetric and independent of individual character limits', () => {
  const a = '!'.repeat(999), b = '?'.repeat(999);
  assert.equal(reconstruction(compare(a, b), 'a'), a); // exactly (999+1)^2 cells
  for (const pair of [['!'.repeat(1000), b], [b, '!'.repeat(1000)]]) {
    const result = compare(...pair); assert.equal(result.status, 'unavailable'); assert.equal(result.spans, undefined);
  }
  // Exact shared edges reduce work without discarding them from either output.
  const prefix = 'same '.repeat(600), suffix = ' ending'.repeat(300);
  const result = compare(prefix + 'A' + suffix, prefix + 'B' + suffix);
  assert.equal(reconstruction(result, 'a'), prefix + 'A' + suffix);
  assert.equal(reconstruction(result, 'b'), prefix + 'B' + suffix);
});

const company = { id: 1, ticker: 'AAA', cik: '0000900001', name: 'Synthetic Alpha', exchange: 'TEST', has_indexed_filing: true, indexed_filing_count: 2 };
const other = { ...company, ticker: 'BBB', cik: '0000900002', name: 'Synthetic Beta' };
function filing(index, issuer = company) {
  const accession_number = `${issuer.cik}-25-00000${index + 1}`;
  return { accession_number, form: index ? '10-Q' : '10-K', filed: index ? '2025-05-01' : '2025-02-01',
    period_start: null, period_end: null, metrics: [], has_filing_chunks: true,
    sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${accession_number.replaceAll('-', '')}/${accession_number}-index.html` };
}
const sources = issuer => [filing(0, issuer), filing(1, issuer)];
const originals = [
  ['Synthetic liquidity risk was 10%.\n  e\u0301 😀 <script>notRun()</script>', 'Repeated cash cash debt.'],
  ['Synthetic liquidity risk is 12%.\n e\u0301 😀 <script>notRun()</script>', 'Repeated debt cash cash.'],
];
function evidence(f, texts, query = 'liquidity', issuer = company) {
  const citations = texts.map((text, index) => ({ citation_id: `source_${index + 1}`, chunk_id: `chunk_${String(index).padStart(4, '0')}`,
    accession_number: f.accession_number, form: f.form, filed: f.filed, filename: 'synthetic.htm', start_char: index * 3000,
    end_char: index * 3000 + Array.from(text).length, sec_url: f.sec_url, similarity: .8, semantic_similarity: .8,
    lexical_score: 1, hybrid_score: 1, evidence_reason: 'strong_lexical' }));
  return { ticker: issuer.ticker, company_name: issuer.name, accession_number: f.accession_number, query, citations,
    evidence_status: texts.length ? 'sufficient' : 'insufficient', context: citations.map((c, index) => `[SOURCE ${c.citation_id}]\nchunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: 0.800000\ntext: |-\n${texts[index].split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE ${c.citation_id}]`).join('\n\n') };
}
function freshness(issuer, pin) {
  const stream = { status: 'current', last_checked_at: null, last_successful_sync_at: null, latest_source_filing_date: null, pending_targets: [], inventory_complete: false, last_error: null, failure_stage: null };
  return { ticker: issuer.ticker, data_version: pin, facts_version: 0, evidence_version: 0, status: 'current', facts: stream, evidence: stream,
    latest_indexed_filing: null, migration_required: false, scope: 'Synthetic frontend-only test fixture' };
}
async function mount(ctx, { strict = false, standalone = null } = {}) {
  assert.ok(document === dom.window.document, 'Passage mounts and event helpers must own the same DOM realm');
  const requests = [];
  ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
    const url = new URL(input, 'http://finlens.test'); assert.equal(url.origin, 'http://finlens.test');
    assert.match(url.pathname, /^\/api\/finlens\/companies\/(?:AAA|BBB)\/(?:freshness|filings\/\d{10}-25-00000[12]\/context)$/);
    let resolve; const promise = new Promise(done => { resolve = done; });
    requests.push({ url, init, resolve, released: false }); return promise; // ignored abort exercises ownership
  });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  let issuer = company, inventory = sources(company), unmounted = false;
  const catalogChanged = async () => true;
  async function render(next = issuer, nextSources = inventory) {
    issuer = next; inventory = nextSources;
    const child = standalone ? React.createElement(Comparison, { results: standalone })
      : React.createElement(Freshness, { key: issuer.cik, ticker: issuer.ticker, catalogChanged }, React.createElement(Dual, { company: issuer, sources: inventory }));
    await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, child) : child));
  }
  async function unmount() { if (!unmounted) { unmounted = true; await act(async () => root.unmount()); host.remove(); } }
  ctx.after(unmount); await render();
  const comparison = () => host.querySelector('.filing-passage-comparison');
  const button = label => [...host.querySelectorAll('button')].find(item => item.textContent === label);
  async function click(label) { const node = button(label); assert.ok(node, label); assert.equal(node.disabled, false); await act(async () => node.click()); }
  async function change(node, value) {
    assert.ok(node); const select = node.tagName === 'SELECT';
    await act(async () => {
      Object.getOwnPropertyDescriptor(select ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLTextAreaElement.prototype, 'value').set.call(node, value);
      node.dispatchEvent(new Event(select ? 'change' : 'input', { bubbles: true }));
    });
  }
  function pendingFreshness() { return requests.find(item => !item.released && !item.init.signal.aborted && item.url.pathname.endsWith('/freshness')); }
  async function release(request, value, { status = 200, header, changed = false } = {}) {
    assert.ok(request); assert.equal(request.released, false); request.released = true;
    if (header === undefined) header = request.init.headers?.['X-FinLens-Data-Version'];
    await act(async () => request.resolve(new Response(JSON.stringify(value), { status, headers: {
      ...(header === null || header === undefined ? {} : { 'X-FinLens-Data-Version': String(header) }),
      ...(changed ? { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } : {}),
    } })));
  }
  async function ready(pin = 0) { await release(pendingFreshness(), freshness(issuer, pin)); }
  const contexts = () => requests.filter(item => item.url.pathname.endsWith('/context'));
  async function search(query = 'liquidity') {
    await change(host.querySelector('textarea'), query); await click('Compare filing evidence'); return contexts().slice(-2);
  }
  async function settle(pair, texts = originals) {
    for (let index = 0; index < 2; index++) {
      const f = inventory.find(item => pair[index].url.pathname.includes(item.accession_number)); assert.ok(f);
      await release(pair[index], evidence(f, texts[index], pair[index].url.searchParams.get('q'), issuer));
    }
  }
  async function select(a = 'source_1', b = 'source_1') {
    const nodes = comparison().querySelectorAll('select'); await change(nodes[0], a); await change(nodes[1], b);
  }
  const alignment = () => comparison()?.querySelectorAll('.passage-alignment-text') ?? [];
  function visibleText(index) {
    return [...alignment()[index].children].map(node => node.dataset.wording === 'shared' ? node.textContent : node.querySelector('[data-wording-text]').textContent).join('');
  }
  return { host, requests, render, unmount, ready, release, search, settle, select, change, click, button, comparison, contexts, alignment, visibleText, pendingFreshness };
}
for (const strict of [false, true]) for (const pin of [0, 7]) test(`explicit source pair, lossless wording and local-only interactions, strict=${strict} pin=${pin}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.ready(pin); assert.equal(app.contexts().length, 0);
  const pair = await app.search(); assert.equal(app.contexts().length, 2);
  for (const [index, request] of pair.entries()) {
    assert.equal(request.url.pathname, `/api/finlens/companies/AAA/filings/${filing(index).accession_number}/context`);
    assert.equal(request.url.search, '?q=liquidity&limit=5');
    assert.deepEqual(request.init.headers, { 'X-FinLens-Data-Version': String(pin) });
  }
  await app.release(pair[0], evidence(filing(0), originals[0])); assert.equal(app.comparison(), null);
  await app.release(pair[1], evidence(filing(1), originals[1]));
  const selects = app.comparison().querySelectorAll('select'); assert.deepEqual([...selects].map(node => node.value), ['', '']);
  assert.equal(app.button('Compare selected wording').disabled, true); assert.equal(app.alignment().length, 0);
  for (const node of selects) assert.ok(node.closest('label').textContent.startsWith('Excerpt from filing'));
  await app.change(selects[0], 'source_1'); assert.equal(app.button('Compare selected wording').disabled, true);
  await app.change(selects[1], 'source_1'); assert.equal(app.alignment().length, 0);
  const count = app.requests.length; await app.click('Compare selected wording'); await app.click('Compare selected wording');
  assert.equal(app.requests.length, count); assert.equal(app.alignment().length, 2);
  assert.equal(app.visibleText(0), originals[0][0]); assert.equal(app.visibleText(1), originals[1][0]);
  assert.match(app.comparison().textContent, /A-only:/); assert.match(app.comparison().textContent, /B-only:/);
  assert.match(app.comparison().textContent, /not chronology/); assert.match(app.comparison().textContent, /not a verified substantive change/);
  assert.match(app.comparison().querySelector('[role="status"]').textContent, /alignment ready/);
  assert.equal(app.host.querySelectorAll('script').length, 0);
  assert.deepEqual([...app.comparison().querySelectorAll('.passage-original')].map(node => node.textContent), originals.map(items => items[0]));
  for (const [index, node] of [...app.comparison().querySelectorAll('details')].entries()) {
    assert.match(node.textContent, new RegExp(`${filing(index).accession_number}/source_1`));
    assert.match(node.textContent, /Cleaned source offsets 0/); assert.match(node.textContent, /not character offsets in the alignment/);
    assert.equal(node.querySelector('a').href, filing(index).sec_url); assert.equal(node.querySelector('a').rel, 'noopener noreferrer');
    const summary = node.querySelector('summary'); summary.focus(); await act(async () => summary.click());
    assert.equal(document.activeElement, summary); assert.equal(node.open, true);
  }
  assert.equal(app.requests.length, count);
  await app.change(selects[0], 'source_2'); assert.equal(app.alignment().length, 0);
  await app.click('Compare selected wording'); assert.equal(app.visibleText(0), originals[0][1]);
  assert.equal(app.visibleText(1), originals[1][0]); assert.equal(app.requests.length, count);
});
test('manual reverse filing selection keeps A/B direction instead of inferring chronology', async ctx => {
  const app = await mount(ctx); await app.ready();
  const filingSelects = app.host.querySelectorAll('select[aria-describedby*="-selected-accession-"]');
  await app.change(filingSelects[0], filing(1).accession_number); await app.change(filingSelects[1], filing(0).accession_number);
  const pair = await app.search(); await app.settle(pair, [originals[1], originals[0]]); await app.select(); await app.click('Compare selected wording');
  assert.equal(app.visibleText(0), originals[1][0]); assert.equal(app.visibleText(1), originals[0][0]);
  const details = app.comparison().querySelectorAll('details'); assert.match(details[0].textContent, new RegExp(filing(1).accession_number));
  assert.match(details[1].textContent, new RegExp(filing(0).accession_number)); assert.equal(app.contexts().length, 2);
});
test('identical wording is scoped to the selected pair, not the whole filings', async ctx => {
  const app = await mount(ctx); await app.ready(); await app.settle(await app.search(), [[originals[0][0]], [originals[0][0]]]);
  await app.select(); await app.click('Compare selected wording');
  assert.match(app.comparison().querySelector('[role="status"]').textContent, /identical wording, including whitespace/);
  assert.match(app.comparison().textContent, /does not establish that the filings are identical/);
  assert.equal(app.comparison().querySelectorAll('[data-wording="a_only"], [data-wording="b_only"]').length, 0);
});
for (const outcome of ['insufficient', 'error', 'invalid source', 'missing pin']) test(`partial ${outcome} cannot expose a passage pair`, async ctx => {
  const app = await mount(ctx); await app.ready(); const pair = await app.search();
  await app.release(pair[0], evidence(filing(0), originals[0]));
  if (outcome === 'error') await app.release(pair[1], {}, { status: 503 });
  else {
    const value = evidence(filing(1), outcome === 'insufficient' ? [] : originals[1]);
    if (outcome === 'invalid source') value.citations[0].sec_url = 'https://evil.test/';
    await app.release(pair[1], value, outcome === 'missing pin' ? { header: null } : {});
  }
  if (outcome === 'insufficient') {
    assert.ok(app.comparison()); assert.equal(app.button('Compare selected wording').disabled, true);
    assert.match(app.comparison().textContent, /Missing search evidence does not establish absence/);
  } else assert.equal(app.comparison(), null);
  assert.equal(app.alignment().length, 0); assert.equal(app.contexts().length, 2);
  assert.match(app.host.textContent, /Synthetic liquidity risk was 10%/);
});
for (const change of ['query', 'filing', 'company', 'inventory', 'publication']) test(`completed pair invalidates on ${change}, no extra search or stale resurrection`, async ctx => {
  const app = await mount(ctx); await app.ready(); await app.settle(await app.search()); await app.select(); await app.click('Compare selected wording');
  assert.equal(app.alignment().length, 2); const count = app.contexts().length;
  if (change === 'query') await app.change(app.host.querySelector('textarea'), 'other question');
  if (change === 'filing') await app.change(app.host.querySelector('select[aria-describedby*="-selected-accession-"]'), filing(1).accession_number);
  if (change === 'company') await app.render(other, sources(other));
  if (change === 'inventory') await app.render(company, [filing(0)]);
  if (change === 'publication') {
    await act(async () => window.dispatchEvent(new Event('focus'))); await app.ready(1);
  }
  assert.equal(app.comparison(), null); assert.equal(app.alignment().length, 0); assert.equal(app.contexts().length, count);
  if (change === 'inventory') { await app.render(company, sources(company)); assert.equal(app.comparison(), null); }
});
for (const change of ['edit', 'cancel', 'publication rejection', 'unmount']) test(`partial search ${change} discards old/late evidence before pairing`, async ctx => {
  const app = await mount(ctx); await app.ready(); const old = await app.search();
  await app.release(old[0], evidence(filing(0), originals[0])); assert.equal(app.comparison(), null);
  if (change === 'edit') await app.change(app.host.querySelector('textarea'), 'edited');
  if (change === 'cancel') await app.click('Cancel filing comparison');
  if (change === 'publication rejection') {
    await app.release(old[1], {}, { status: 409, changed: true }); assert.ok(app.pendingFreshness());
    await app.ready(1);
  }
  if (change === 'unmount') await app.unmount();
  if (change !== 'publication rejection') await app.release(old[1], evidence(filing(1), originals[1]));
  assert.equal(app.comparison(), null); assert.equal(app.alignment().length, 0); assert.equal(app.contexts().length, 2);
});
test('new explicit search resets selectors and cannot keep a comparison if its sibling later fails', async ctx => {
  const app = await mount(ctx); await app.ready(); await app.settle(await app.search()); await app.select(); await app.click('Compare selected wording');
  await app.click('Compare filing evidence'); assert.equal(app.comparison(), null); const pair = app.contexts().slice(-2);
  await app.release(pair[0], evidence(filing(0), originals[0])); await app.release(pair[1], {}, { status: 503 });
  assert.equal(app.comparison(), null); await app.click('Compare filing evidence'); await app.settle(app.contexts().slice(-2));
  assert.deepEqual([...app.comparison().querySelectorAll('select')].map(node => node.value), ['', '']); assert.equal(app.alignment().length, 0);
});
test('ignored-abort old response cannot replace the selected pair from a newer question', async ctx => {
  const app = await mount(ctx); await app.ready(); const old = await app.search();
  await app.release(old[0], evidence(filing(0), originals[0]));
  const current = await app.search('regulation');
  const newerText = [['New question source A 123.'], ['New question source B 456.']];
  await app.settle(current, newerText); await app.select(); await app.click('Compare selected wording');
  await app.release(old[1], evidence(filing(1), originals[1]));
  assert.equal(app.visibleText(0), newerText[0][0]); assert.equal(app.visibleText(1), newerText[1][0]);
  assert.doesNotMatch(app.comparison().textContent, /Synthetic liquidity/); assert.equal(app.contexts().length, 4);
});
test('resource refusal leaves both exact full originals and official links available', async ctx => {
  const texts = [['!'.repeat(1000)], ['?'.repeat(999)]];
  const app = await mount(ctx); await app.ready(); await app.settle(await app.search(), texts); await app.select(); await app.click('Compare selected wording');
  assert.match(app.comparison().querySelector('[role="status"]').textContent, /No partial comparison/); assert.equal(app.alignment().length, 0);
  assert.deepEqual([...app.comparison().querySelectorAll('.passage-original')].map(node => node.textContent), texts.flat());
  assert.deepEqual([...app.comparison().querySelectorAll('a')].map(node => node.href), sources(company).map(f => f.sec_url));
  assert.equal(app.contexts().length, 2);
});
test('standalone empty sides require explicit nonempty evidence instead of a fabricated comparison', async ctx => {
  const app = await mount(ctx, { standalone: [evidence(filing(0), []), evidence(filing(1), [])] });
  assert.equal(app.requests.length, 0); assert.equal(app.button('Compare selected wording').disabled, true);
  assert.ok([...app.comparison().querySelectorAll('select')].every(node => node.disabled));
  assert.equal(app.comparison().querySelectorAll('a').length, 0); assert.equal(app.alignment().length, 0);
});
});
