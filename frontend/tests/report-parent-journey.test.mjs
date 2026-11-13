// Actual public parent, synthetic deferred API bodies and local file handoff.
// No backend, listener, native browser, external transport or provider runs.
import test, { describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';
import { readEvidenceCsv } from './helpers/evidence-csv.mjs';

describe('public report parent closure', { concurrency: false }, () => {
  const keys = ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
  let original, dom, createRoot, Research, Freshness;
  before(async () => {
    original = new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
    dom = new JSDOM('<!doctype html><body></body>', { url: 'http://finlens.test', pretendToBeVisual: true });
    for (const key of keys) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
      value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[key] });
    ({ createRoot } = await import('react-dom/client'));
    const root = fileURLToPath(new URL('..', import.meta.url)), load = componentLoader(root);
    Research = load(resolve(root, 'components/filing-research.tsx')).default;
    Freshness = load(resolve(root, 'components/research-freshness.tsx')).default;
  });
  after(() => {
    dom.window.close();
    for (const [key, descriptor] of original) {
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
  const filename = 'synthetic.htm';
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
        filed: source.filed, sec_url: source.sec_url, filename, citation_id: 'source_1', chunk_id: 'chunk_0000',
        start_char: 0, end_char: Array.from(text).length, similarity: .8, semantic_similarity: .8,
        lexical_score: 1, hybrid_score: 1, evidence_reason: 'strong_lexical' }],
      context: `[SOURCE source_1]\nchunk_id: chunk_0000\naccession_number: ${source.accession_number}\nform: 10-K\nsimilarity: 0.800000\ntext: |-\n${text.split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE source_1]` };
  }
  async function mount(ctx, strict, pin) {
    assert.equal(document, dom.window.document);
    const requests = [], unexpected = [], urls = [], revoked = [], handoffs = [];
    ctx.mock.method(URL, 'createObjectURL', blob => { const url = `blob:report/${urls.length}`; urls.push({ url, blob }); return url; });
    ctx.mock.method(URL, 'revokeObjectURL', url => revoked.push(url));
    ctx.mock.method(dom.window.HTMLAnchorElement.prototype, 'click', function () {
      assert.ok(this.isConnected); handoffs.push({ url: this.href, filename: this.download });
    });
    ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
      const url = new URL(input, dom.window.location.href);
      if (url.origin !== 'http://finlens.test' || !/^\/api\/finlens\/companies\/AAA\/(?:freshness|sources|research-answer|filings\/0000900001-25-00000[12]\/context)$/.test(url.pathname)) {
        unexpected.push(url.href); return Promise.reject(new Error('Unexpected fixture request'));
      }
      let resolve; const promise = new Promise(done => { resolve = done; });
      requests.push({ url, init, resolve, done: false }); return promise;
    });
    const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
    ctx.after(async () => {
      await act(async () => root.unmount()); host.remove();
      assert.deepEqual(unexpected, [], 'product catches cannot hide unexpected transport');
      assert.equal(revoked.length, urls.length); assert.deepEqual([...new Set(revoked)], urls.map(item => item.url));
      assert.equal(document.querySelector('a[download]'), null);
    });
    const child = React.createElement(Freshness, { ticker: company.ticker, catalogChanged: async () => true },
      React.createElement(Research, { company, configured: false, filingResearchEnabled: true }));
    await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, child) : child));
    const pending = suffix => requests.filter(r => !r.done && !r.init.signal.aborted && r.url.pathname.endsWith(suffix));
    async function release(r, body, status = 200) {
      assert.ok(r); r.done = true; const version = r.init.headers?.['X-FinLens-Data-Version'];
      await act(async () => r.resolve(new Response(JSON.stringify(body), { status,
        headers: { 'Content-Type': 'application/json', ...(version === undefined ? {} : { 'X-FinLens-Data-Version': version }) } })));
    }
    async function change(node, value) {
      assert.ok(node); const select = node.tagName === 'SELECT';
      await act(async () => {
        Object.getOwnPropertyDescriptor(select ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLTextAreaElement.prototype, 'value').set.call(node, value);
        node.dispatchEvent(new Event(select ? 'change' : 'input', { bubbles: true }));
      });
    }
    async function click(label) {
      const node = [...host.querySelectorAll('button')].find(n => n.textContent === label);
      assert.ok(node, label); assert.equal(node.disabled, false); await act(async () => node.click());
    }
    await release(pending('/freshness')[0], fresh(pin));
    for (const r of pending('/sources')) await release(r, sources);
    async function search(query) {
      await change(host.querySelector('#research-query'), query); await click('Research question');
      await release(pending('/research-answer')[0], { ticker: company.ticker, question: query, matched: false, status: 'not_matched' });
      return pending('/context')[0];
    }
    return { host, requests, urls, handoffs, pending, release, change, click, search };
  }
  for (const strict of [false, true]) for (const pin of [0, 7]) test(`pair and report coexist with exact local exports strict=${strict} pin=${pin}`, async ctx => {
    const app = await mount(ctx, strict, pin), dual = app.host.querySelector('.dual-filing-evidence');
    assert.equal(app.host.querySelector('.evidence-report'), null);
    await app.change(dual.querySelector('textarea'), 'liquidity'); await app.click('Compare filing evidence');
    for (const [index, r] of app.pending('/context').entries()) await app.release(r, evidence(index, 'liquidity'));
    const panel = dual.querySelector('.filing-passage-comparison'); assert.ok(panel);
    for (const select of panel.querySelectorAll('select')) await app.change(select, 'source_1');
    await app.click('Compare selected wording');
    const aligned = [...panel.querySelectorAll('.passage-original')].map(n => n.textContent); assert.deepEqual(aligned, texts);
    const response = await app.search('liquidity'); await app.release(response, evidence(0, 'liquidity'));
    const report = app.host.querySelector('.evidence-report'); assert.ok(report);
    assert.equal(report.getAttribute('aria-labelledby'), report.querySelector('h4').id);
    const preview = report.querySelector('textarea'), label = report.querySelector('label');
    assert.equal(label.htmlFor, preview.id); assert.ok(preview.readOnly);
    report.querySelector('summary').focus(); await act(async () => report.querySelector('summary').click());
    assert.equal(report.querySelector('details').open, true); assert.equal(document.activeElement, report.querySelector('summary'));
    const count = app.requests.length;
    for (const label of ['Download evidence data (.json)', 'Download evidence report (.txt)',
      'Download printable report (.html)', 'Download typed evidence (.csv)']) await app.click(label);
    const [json, txt, html, csv] = await Promise.all(app.urls.map(async item => item.blob.text()));
    const value = JSON.parse(json); assert.equal(value.search.query, 'liquidity'); assert.equal(value.search.data_version, pin);
    assert.equal(value.search.reference_only, false); assert.equal(value.search.evidence_version, null);
    assert.equal(value.passages[0].text, texts[0]);
    const source = value.passages[0].source;
    assert.equal(source.sec_url, sources[0].sec_url); assert.equal(source.accession_number, sources[0].accession_number);
    assert.equal(source.end_char, Array.from(texts[0]).length); assert.equal(source.filename, filename);
    assert.deepEqual(readEvidenceCsv(csv), value); assert.equal(txt, preview.value); assert.ok(txt.includes(texts[0]));
    const saved = new JSDOM(html); ctx.after(() => saved.window.close());
    assert.equal(saved.window.document.querySelector('#report-text').textContent, txt);
    assert.equal(saved.window.document.querySelector('script'), null); assert.equal(saved.window.document.querySelector('a').href, sources[0].sec_url);
    assert.deepEqual(app.handoffs.map(h => h.filename), ['json', 'txt', 'html', 'csv'].map(ext => `finlens-AAA-evidence-v${pin}.${ext}`));
    assert.equal(report.querySelector('[role="status"]').textContent.includes('cannot confirm a saved file'), true);
    assert.equal(app.requests.length, count); assert.deepEqual([...panel.querySelectorAll('.passage-original')].map(n => n.textContent), texts);
    assert.ok(app.host.querySelector('.evidence-results .passage-tone'));
    await app.change(app.host.querySelector('#research-query'), 'other topic');
    assert.match(report.textContent, /Reference only/); assert.equal(report.querySelector('textarea').value.includes(texts[0]), true);
    assert.equal(app.host.querySelector('.evidence-results .passage-tone'), null);
    assert.deepEqual([...panel.querySelectorAll('.passage-original')].map(n => n.textContent), texts);
  });
  for (const fault of ['form', 'filed', 'url']) test(`source inventory mismatch ${fault} refuses report until valid retry`, async ctx => {
    const app = await mount(ctx, false, 7), r = await app.search('liquidity'), bad = evidence(0, 'liquidity');
    if (fault === 'form') { bad.citations[0].form = '10-Q'; bad.context = bad.context.replace('form: 10-K', 'form: 10-Q'); }
    if (fault === 'filed') bad.citations[0].filed = '2025-02-02';
    if (fault === 'url') bad.citations[0].sec_url = sources[1].sec_url;
    await app.release(r, bad);
    assert.equal(Boolean(app.host.querySelector('.evidence-report')), false); assert.deepEqual(app.urls, []);
    assert.ok([...app.host.querySelectorAll('[role="alert"]')].some(n => /could not be verified/.test(n.textContent)));
    const retry = await app.search('liquidity'); await app.release(retry, evidence(0, 'liquidity'));
    assert.ok(app.host.querySelector('.evidence-report')); assert.equal(app.urls.length, 0);
  });
});
