import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';

const company = { id: 1, ticker: 'SYN', name: 'Synthetic issuer', cik: '0000900001',
  exchange: 'TEST', has_indexed_filing: false, indexed_filing_count: 0 };
const accession = '0000900001-25-000001';
const secUrl = 'https://www.sec.gov/Archives/edgar/data/900001/000090000125000001/0000900001-25-000001-index.html';
const period = { kind: 'quarter', start: '2025-01-01', end: '2025-03-31',
  fiscal_year: 2025, fiscal_period: 'Q1', fiscal_label_basis: 'test fixture' };
const prior = { ...period, start: '2024-10-01', end: '2024-12-31', fiscal_year: 2024, fiscal_period: 'Q4' };
const point = (value, proven = true, window = period) => ({
  metric: 'revenue', unit: 'USD', status: 'available', value, reason: null, period: window,
  formula: null, revenue_basis: 'total_revenue', inputs: [], alternatives: [],
  provenance: proven ? [{
    fact_id: 1, original_concept: 'Synthetic source revenue', value, unit: 'USD',
    period_start: window.start, period_end: window.end, form: '10-Q', filed: '2025-05-01',
    accession_number: accession, sec_url: secUrl, company_cik: company.cik,
    source_fiscal_year: 2025, source_fiscal_period: 'Q1',
  }] : [],
});
const history = (...observations) => ({
  ticker: company.ticker, company_cik: company.cik, metric: 'revenue', unit: 'USD', requested_period: 'quarter',
  status: 'available', reason: null, selection_policy: 'test fixture', history: observations,
});
const summary = { ticker: company.ticker, company_cik: company.cik, company_name: company.name,
  requested_period: 'quarter', period, metrics: { revenue: point('1000000000') }, selection_policy: 'test fixture' };
const stream = { status: 'current', last_checked_at: null, last_successful_sync_at: null,
  latest_source_filing_date: null, pending_targets: [], inventory_complete: false, last_error: null, failure_stage: null };
const freshness = { ticker: company.ticker, data_version: 7, facts_version: 0, evidence_version: 0, status: 'current',
  facts: stream, evidence: stream, latest_indexed_filing: null, migration_required: false, scope: 'Synthetic offline fixture' };
const base = '/api/finlens/companies/SYN/';
const freshnessPath = base + 'freshness';
const summaryPath = base + 'financials/summary?period=quarter';
const historyPath = base + 'financials/metrics/revenue?period=quarter&limit=12';

test('available financial history without selected provenance fails closed while verified retry and snapshot survive', async ctx => {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  const previous = new Map();
  for (const key of ['window', 'document', 'HTMLElement', 'SVGElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT']) {
    previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { configurable: true,
      value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[key] });
  }
  const resizeKey = 'ResizeObserver';
  previous.set(resizeKey, Object.getOwnPropertyDescriptor(globalThis, resizeKey));
  Object.defineProperty(globalThis, resizeKey, { configurable: true, value: class {
    constructor(callback) { this.callback = callback; }
    observe(target) { this.callback([{ target, contentRect: { width: 700, height: 250 } }]); }
    unobserve() {}
    disconnect() {}
  } });
  dom.window.HTMLElement.prototype.getBoundingClientRect = () => ({
    width: 700, height: 250, top: 0, left: 0, right: 700, bottom: 250,
  });
  let root;
  ctx.after(async () => {
    try { if (root) await act(async () => root.unmount()); } finally {
      dom.window.close();
      for (const [key, descriptor] of previous) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    }
  });
  const { createRoot } = await import('react-dom/client');
  const frontend = new URL('../', import.meta.url);
  const load = componentLoader(fileURLToPath(frontend));
  const FinancialResearch = load(fileURLToPath(new URL('components/financial-research.tsx', frontend))).default;
  const ResearchFreshness = load(fileURLToPath(new URL('components/research-freshness.tsx', frontend))).default;
  const requests = [];
  ctx.mock.method(globalThis, 'fetch', (url, init = {}) => {
    const entry = { url, method: init.method ?? 'GET', pin: new Headers(init.headers).get('X-FinLens-Data-Version'),
      body: Object.hasOwn(init, 'body'), signal: init.signal };
    requests.push(entry);
    if (entry.method !== 'GET' || entry.body || ![freshnessPath, summaryPath, historyPath].includes(url)
      || entry.pin !== (url === freshnessPath ? null : '7')) {
      entry.rejected = true;
      return Promise.reject(new Error('Unexpected synthetic endpoint or pin'));
    }
    return new Promise(resolve => { entry.resolve = resolve; });
  });
  const release = async (url, value, pin = null) => {
    const waiting = requests.filter(entry => entry.url === url && entry.resolve && !entry.settled && !entry.signal.aborted);
    assert.equal(waiting.length, 1, url);
    const [entry] = waiting;
    entry.settled = true;
    await act(async () => entry.resolve(new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json',
      ...(pin === null ? {} : { 'X-FinLens-Data-Version': String(pin) }) } })));
  };
  const host = document.body.appendChild(document.createElement('div'));
  root = createRoot(host);
  await act(async () => root.render(React.createElement(ResearchFreshness,
    { ticker: company.ticker, catalogChanged: async () => true }, React.createElement(FinancialResearch, { company }))));
  assert.deepEqual(requests.map(entry => entry.url), [freshnessPath]);
  await release(freshnessPath, freshness);
  await release(summaryPath, summary, 7);
  const snapshot = host.querySelector('[aria-labelledby="snapshot-title"]');
  const snapshotMetrics = snapshot.querySelector('.metric-grid');
  assert.match(snapshotMetrics.textContent, /\$1B/);
  const trends = host.querySelector('[aria-labelledby="history-title"]');
  const alternative = { ...point('250000000').provenance[0], fact_id: 2,
    accession_number: '0000900001-25-000002',
    sec_url: 'https://www.sec.gov/Archives/edgar/data/900001/000090000125000002/0000900001-25-000002-index.html' };
  const unsupported = { ...point('987654321', false), alternatives: [alternative] };
  await release(historyPath, history(point('100000000', true, prior), unsupported), 7);
  assert.match(trends.querySelector('[role="alert"]')?.textContent ?? '', /Financial history could not be verified/);
  assert.equal(trends.querySelector('table, .financial-chart, .source-record'), null);
  assert.equal(snapshot.querySelector('.metric-grid'), snapshotMetrics);
  const retry = [...trends.querySelectorAll('button')].find(button => button.textContent === 'Retry history');
  assert.ok(retry && !retry.disabled);
  await act(async () => retry.click());
  const unavailable = { ...point(null, false, prior), status: 'unavailable', reason: 'No selected source for prior quarter.' };
  await release(historyPath, history(unavailable, point('300000000')), 7);
  assert.equal(trends.querySelector('[role="alert"]'), null);
  assert.match(trends.querySelector('table').textContent, /No selected source for prior quarter/);
  assert.match(trends.querySelector('table').textContent, /\$300M/);
  assert.equal(trends.querySelector('table .source-record a').getAttribute('href'), secUrl);
  assert.equal(snapshot.querySelector('.metric-grid'), snapshotMetrics);
  assert.equal(requests.some(entry => entry.rejected), false);
  const signatures = requests.map(({ method, url, pin, body }) => [method, url, pin, body]);
  assert.deepEqual(signatures.slice(1, 3).sort(), [
    ['GET', historyPath, '7', false], ['GET', summaryPath, '7', false],
  ].sort());
  assert.deepEqual(signatures.at(-1), ['GET', historyPath, '7', false]);
  assert.equal(requests.length, 4);
});
