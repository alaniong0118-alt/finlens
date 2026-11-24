import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';

const issuer = (ticker, id) => ({ ticker, name: 'Synthetic ' + ticker, cik: String(id).padStart(10, '0') });
const a = issuer('AAA', 900001), b = issuer('BBB', 900002), c = issuer('CCC', 900003);
const id = (company, suffix) => company.cik + '-25-' + suffix;
const ids = [id(a, '000009'), id(a, '000002')];
const peerIds = [id(b, '000006'), id(b, '000001')];
const topic = 'supply chain';

function evidence(company, searched, citation = false) {
  const accession = searched[0], text = 'Supply chain may affect operations.';
  const source = citation ? { citation_id: 'source_1', chunk_id: 'chunk_0001', company_cik: company.cik,
    accession_number: accession, form: '10-K', filed: '2025-10-01', filename: 'synthetic.htm',
    start_char: 0, end_char: text.length, sec_url: 'https://www.sec.gov/Archives/edgar/data/' +
      Number(company.cik) + '/' + accession.replaceAll('-', '') + '/' + accession + '-index.html',
    similarity: 0.9, semantic_similarity: 0.9, lexical_score: 1, hybrid_score: 1.54, evidence_reason: 'strong_lexical' } : null;
  const metadata = source && Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id',
    'form', 'filed', 'start_char', 'end_char'].map(key => [key, source[key]]));
  return { ticker: company.ticker, company_name: company.name, retrieval_scope: 'company', company_cik: company.cik,
    data_version: 0, evidence_version: 0, query: topic, searched_accessions: searched, excluded_publication_count: 0,
    evidence_status: citation ? 'sufficient' : 'insufficient', citations: source ? [source] : [],
    context: source ? '[SOURCE source_1]\nmetadata: ' + JSON.stringify(metadata) + '\ntext: |-\n  ' + text + '\n[END SOURCE source_1]' : '' };
}

test('SEC_RISK_SEARCHED_SCOPE keeps issuer-specific verified accessions without extra requests', async ctx => {
  const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://finlens.test' });
  const globals = new Map();
  for (const [name, value] of Object.entries({ window: dom.window, document: dom.window.document, Event: dom.window.Event,
    HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true })) {
    globals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, value, writable: true });
  }
  let root;
  ctx.after(async () => {
    if (root) await act(async () => root.unmount());
    dom.window.close();
    for (const [name, property] of globals) {
      if (property) Object.defineProperty(globalThis, name, property);
      else delete globalThis[name];
    }
  });
  const requests = [], rejected = [];
  const route = /^(?:\/api\/finlens\/companies\/(AAA|BBB)\/(freshness|context))(?:\?q=supply\+chain&limit=5)?$/;
  ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
    const match = typeof input === 'string' && route.exec(input);
    const context = match && match[2] === 'context';
    if (!match || (init.method ?? 'GET') !== 'GET' || init.body != null ||
        (context ? input !== '/api/finlens/companies/' + match[1] + '/context?q=supply+chain&limit=5' ||
          new Headers(init.headers).get('X-FinLens-Data-Version') !== '0' :
          input !== '/api/finlens/companies/' + match[1] + '/freshness' ||
          new Headers(init.headers).has('X-FinLens-Data-Version'))) {
      rejected.push('unexpected fixture transport'); throw new Error('unexpected fixture transport');
    }
    return new Promise(resolve => requests.push({ ticker: match[1], kind: match[2], resolve, sent: false }));
  });
  const { createRoot } = await import('react-dom/client');
  const frontend = fileURLToPath(new URL('..', import.meta.url));
  const Comparison = componentLoader(frontend)(fileURLToPath(new URL('../components/sec-risk-comparison.tsx', import.meta.url))).default;
  const host = document.querySelector('#root');
  root = createRoot(host);
  await act(async () => root.render(React.createElement(Comparison, { companies: [a, b, c] })));
  const selects = host.querySelectorAll('select');
  async function change(control, value) {
    await act(async () => { control.value = value; control.dispatchEvent(new Event('change', { bubbles: true })); });
  }
  const submit = () => act(async () => host.querySelector('button.primary-button').click());
  async function deliver(company, kind, value, status = 200) {
    const entry = requests.find(x => !x.sent && x.kind === kind && x.ticker === company.ticker);
    assert.ok(entry, company.ticker + ' ' + kind);
    entry.sent = true;
    await act(async () => entry.resolve(new Response(JSON.stringify(value), { status,
      headers: kind === 'context' ? { 'X-FinLens-Data-Version': '0' } : {} })));
  }
  const fresh = company => deliver(company, 'freshness', { ticker: company.ticker, data_version: 0, facts_version: 0, evidence_version: 0 });
  const columns = () => [...host.querySelectorAll('.risk-comparison-column')];
  const disclosure = column => [...column.querySelectorAll('details')].find(node => node.querySelector('summary')?.textContent.trim() === 'Filings searched');
  const ledger = () => requests.map(x => x.ticker + ':' + x.kind).sort();
  await change(selects[0], a.ticker); await change(selects[1], b.ticker);
  assert.equal(requests.length, 0);
  await submit();
  assert.equal(columns().length, 2);
  assert.ok(columns().every(column => !disclosure(column)));
  await fresh(a); await fresh(b);
  await deliver(a, 'context', evidence(a, ids));
  assert.match(columns()[0].textContent, /Insufficient topic evidence/);
  assert.equal(disclosure(columns()[1]), undefined);
  const first = disclosure(columns()[0]);
  await deliver(b, 'context', evidence(b, peerIds, true));
  assert.match(columns()[1].textContent, /Supply chain may affect operations/);
  const second = disclosure(columns()[1]);
  const firstLedger = ['AAA:context', 'AAA:freshness', 'BBB:context', 'BBB:freshness'];
  assert.deepEqual(ledger(), firstLedger);
  await change(selects[0], c.ticker);
  assert.equal(columns().length, 0);
  assert.deepEqual(ledger(), firstLedger);
  await change(selects[0], a.ticker);
  await submit(); await fresh(a); await fresh(b);
  await deliver(a, 'context', evidence(a, []));
  await deliver(b, 'context', {}, 500);
  assert.match(columns()[0].textContent, /No qualifying published evidence/);
  assert.match(columns()[1].textContent, /Evidence unavailable or unverified/);
  assert.ok(columns().every(column => !disclosure(column)));
  assert.deepEqual(ledger(), [...firstLedger, ...firstLedger].sort());
  assert.deepEqual(rejected, []);
  assert.equal(Boolean(first && second), true, 'settled issuer disclosures exist');
  for (const [node, expected] of [[first, ids], [second, peerIds]]) {
    assert.equal(node.open, false);
    assert.deepEqual([...node.querySelectorAll('li')].map(item => item.textContent.trim()), expected);
    assert.equal(node.querySelectorAll('a').length, 0);
  }
});
