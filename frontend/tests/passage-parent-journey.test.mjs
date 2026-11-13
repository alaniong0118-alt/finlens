// Public parent integration with explicitly synthetic sources; all fetches are
// deferred fixtures. No provider, database, worker, server or browser is started.
import test, { describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';

describe('public filing parent passage journey', { concurrency: false }, () => {
  const keys = ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
  let descriptors, dom, createRoot, Research, Freshness;
  before(async () => {
    descriptors = new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
    dom = new JSDOM('<!doctype html><body></body>', { url: 'http://finlens.test', pretendToBeVisual: true });
    for (const key of keys) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
      value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[key] });
    ({ createRoot } = await import('react-dom/client'));
    const frontend = fileURLToPath(new URL('..', import.meta.url));
    const load = componentLoader(frontend);
    Research = load(resolve(frontend, 'components/filing-research.tsx')).default;
    Freshness = load(resolve(frontend, 'components/research-freshness.tsx')).default;
  });
  after(() => {
    dom.window.close();
    for (const [key, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key];
    }
  });
  const company = { id: 1, ticker: 'AAA', name: 'Synthetic Parent Issuer', cik: '0000900001', exchange: 'TEST',
    has_indexed_filing: true, indexed_filing_count: 2 };
  const sources = [1, 2].map(index => {
    const accession_number = `0000900001-25-00000${index}`;
    return { accession_number, form: '10-K', filed: `2025-02-0${index}`, period_start: null, period_end: null,
      metrics: [], has_filing_chunks: true,
      sec_url: `https://www.sec.gov/Archives/edgar/data/900001/${accession_number.replaceAll('-', '')}/${accession_number}-index.html` };
  });
  const texts = ['Synthetic retained source A.\n  Qualification 😀 e\u0301 <script>literal()</script>',
    'Synthetic retained source B.\n Qualification 😀 e\u0301 <script>literal()</script>'];
  const fresh = pin => {
    const stream = { status: 'current', last_checked_at: null, last_successful_sync_at: null,
      latest_source_filing_date: null, pending_targets: [], inventory_complete: false, last_error: null, failure_stage: null };
    return { ticker: company.ticker, data_version: pin, facts_version: 0, evidence_version: pin, status: 'current',
      facts: stream, evidence: stream, latest_indexed_filing: null, migration_required: false, scope: 'Synthetic parent fixture' };
  };
  function evidence(index, query) {
    const source = sources[index], text = texts[index];
    return { ticker: company.ticker, company_name: company.name, accession_number: source.accession_number, query,
      evidence_status: 'sufficient', citations: [{ accession_number: source.accession_number, form: source.form,
        filed: source.filed, sec_url: source.sec_url, filename: 'synthetic.htm', citation_id: 'source_1',
        chunk_id: 'chunk_0000', start_char: 0, end_char: Array.from(text).length, similarity: .8,
        semantic_similarity: .8, lexical_score: 1, hybrid_score: 1, evidence_reason: 'strong_lexical' }],
      context: `[SOURCE source_1]\nchunk_id: chunk_0000\naccession_number: ${source.accession_number}\nform: 10-K\nsimilarity: 0.800000\ntext: |-\n${text.split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE source_1]` };
  }
  async function mount(ctx, strict = false) {
    assert.equal(document, dom.window.document);
    const requests = [], unexpected = [];
    ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
      const url = new URL(input, dom.window.location.href);
      if (url.origin !== 'http://finlens.test' || !/^\/api\/finlens\/companies\/AAA\/(?:freshness|sources|filings\/0000900001-25-00000[12]\/context)$/.test(url.pathname)) {
        unexpected.push(url.pathname); return Promise.reject(new Error('Unexpected synthetic transport'));
      }
      let resolve; const promise = new Promise(done => { resolve = done; });
      requests.push({ url, init, resolve, done: false }); return promise;
    });
    const host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    ctx.after(async () => {
      await act(async () => root.unmount()); host.remove();
      assert.deepEqual(unexpected, [], 'caught transport errors cannot conceal an unexpected request');
    });
    const child = React.createElement(Freshness, { ticker: company.ticker, catalogChanged: async () => true },
      React.createElement(Research, { company, configured: false, filingResearchEnabled: true }));
    await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, child) : child));
    async function release(request, body, status = 200) {
      assert.ok(request); request.done = true;
      const pin = request.init.headers?.['X-FinLens-Data-Version'];
      await act(async () => request.resolve(new Response(JSON.stringify(body), { status,
        headers: { 'Content-Type': 'application/json', ...(pin === undefined ? {} : { 'X-FinLens-Data-Version': pin }) } })));
    }
    const pending = suffix => requests.filter(r => !r.done && !r.init.signal.aborted && r.url.pathname.endsWith(suffix));
    async function inventory(body = sources, status = 200) {
      for (const request of pending('/sources')) await release(request, body, status);
    }
    async function change(node, value) {
      assert.ok(node); const select = node.tagName === 'SELECT';
      await act(async () => {
        Object.getOwnPropertyDescriptor(select ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLTextAreaElement.prototype, 'value').set.call(node, value);
        node.dispatchEvent(new Event(select ? 'change' : 'input', { bubbles: true }));
      });
    }
    async function click(label) {
      const button = [...host.querySelectorAll('button')].find(n => n.textContent === label);
      assert.ok(button, label); assert.equal(button.disabled, false); await act(async () => button.click());
    }
    return { host, requests, pending, release, inventory, change, click };
  }
  for (const strict of [false, true]) for (const pin of [0, 7]) test(`inventory to explicit wording and source reset, strict=${strict} pin=${pin}`, async ctx => {
    const app = await mount(ctx, strict);
    await app.release(app.pending('/freshness')[0], fresh(pin)); await app.inventory();
    const dual = app.host.querySelector('.dual-filing-evidence'); assert.ok(dual);
    const query = dual.querySelector('textarea');
    assert.equal(dual.querySelectorAll('select').length, 2, 'existing native filing selects remain');
    await app.change(query, 'liquidity'); await app.click('Compare filing evidence');
    const pair = app.pending('/context'); assert.equal(pair.length, 2);
    for (const [index, request] of pair.entries()) {
      assert.equal(request.url.pathname, `/api/finlens/companies/AAA/filings/${sources[index].accession_number}/context`);
      assert.equal(request.url.search, '?q=liquidity&limit=5');
      assert.deepEqual(request.init.headers, { 'X-FinLens-Data-Version': String(pin) });
      await app.release(request, evidence(index, 'liquidity'));
      if (index === 0) assert.equal(dual.querySelector('.filing-passage-comparison'), null);
    }
    const panel = dual.querySelector('.filing-passage-comparison'); assert.ok(panel);
    assert.match(panel.textContent, /not paired automatically/); assert.equal(panel.querySelector('button').disabled, true);
    const selects = panel.querySelectorAll('select');
    for (const select of selects) { assert.equal(select.value, ''); assert.equal(select.closest('label').contains(select), true); }
    const beforeLocal = app.requests.length;
    await app.change(selects[0], 'source_1'); await app.change(selects[1], 'source_1');
    await app.click('Compare selected wording');
    const aligned = [...panel.querySelectorAll('.passage-alignment-text')].map(node => [...node.children]
      .map(span => span.dataset.wording === 'shared' ? span.textContent : span.querySelector('[data-wording-text]').textContent).join(''));
    assert.deepEqual(aligned, texts); assert.deepEqual([...panel.querySelectorAll('.passage-original')].map(n => n.textContent), texts);
    assert.deepEqual([...panel.querySelectorAll('a')].map(n => n.href), sources.map(s => s.sec_url));
    for (const [index, detail] of [...panel.querySelectorAll('details')].entries()) {
      assert.match(detail.textContent, new RegExp(`${sources[index].accession_number}/source_1`));
      assert.ok(detail.textContent.includes(`0–${Array.from(texts[index]).length}`));
    }
    assert.equal(panel.querySelectorAll('script').length, 0); assert.ok(panel.querySelector('[role="status"][aria-live="polite"]'));
    assert.ok(panel.querySelector('.passage-wording-label').textContent.includes('-only'));
    assert.equal(app.requests.length, beforeLocal, 'selecting/comparing does not acquire new evidence');
    await app.change(query, 'new question'); assert.equal(dual.querySelector('.filing-passage-comparison'), null);
    assert.equal(app.requests.length, beforeLocal, 'editing revokes the pair without another request');
  });
  test('source-list failure keeps comparison unavailable until an explicit successful retry', async ctx => {
    const app = await mount(ctx);
    await app.release(app.pending('/freshness')[0], fresh(3)); await app.inventory({}, 503);
    assert.equal(app.host.querySelector('.filing-passage-comparison'), null);
    assert.equal([...app.host.querySelectorAll('button')].find(n => n.textContent === 'Compare filing evidence').disabled, true);
    assert.ok([...app.host.querySelectorAll('[role="alert"]')].some(n => n.textContent.includes('Could not load the filing list')));
    const count = app.requests.length; assert.equal(app.pending('/sources').length, 0);
    await app.click('Retry filing list'); assert.ok(app.requests.length > count); await app.inventory();
    const query = app.host.querySelector('.dual-filing-evidence textarea'); await app.change(query, 'liquidity');
    await app.click('Compare filing evidence'); assert.equal(app.pending('/context').length, 2);
    await app.release(app.pending('/context')[0], evidence(0, 'liquidity'));
    await app.release(app.pending('/context')[0], {}, 503);
    assert.equal(app.host.querySelector('.filing-passage-comparison'), null);
    assert.match(app.host.querySelector('.dual-filing-evidence [role="alert"]').textContent, /unavailable or could not be verified/);
  });
});
