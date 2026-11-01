import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { mountedDataLedger, assertPendingDataScope } from './mounted-data-ledger.mjs';
import { componentLoader } from './component-loader.mjs';

function fixture({ replay = false, edit = () => {}, lateAbort = false, settledReplay = false } = {}) {
  const ledger = mountedDataLedger(), records = [], controllers = new Map();
  function add(suffix, query = '') {
    const controller = new AbortController();
    const request = { path: `/companies/AAPL/${suffix}`, params: new URLSearchParams(query),
      init: { signal: controller.signal, headers: { 'X-FinLens-Data-Version': '0' } }, released: false };
    const url = new URL(`http://finlens.test/api/finlens${request.path}?${query}`);
    edit(request, url);
    url.pathname = '/api/finlens' + request.path; url.search = request.params.toString();
    ledger.started(request, url); records.push(request); controllers.set(request, controller);
    return request;
  }
  const retired = replay ? [add('financials/annual'), add('financials/quarters')] : [];
  if (settledReplay) { ledger.responded(retired[0], new Response()); retired[0].released = true; }
  if (!lateAbort) retired.forEach(request => controllers.get(request).abort());
  add('financials/annual'); add('financials/quarters');
  if (lateAbort) retired.forEach(request => controllers.get(request).abort());
  add('financials/metrics/revenue', 'period=quarter&limit=12');
  add('financials/summary', 'period=quarter'); add('sources');
  return { ledger, records, controllers, check: () => assertPendingDataScope(records, { version: 0, replay }) };
}

for (const replay of [false, true]) test(`ledger admits exactly bound version-zero owners replay ${replay}`, () => {
  const app = fixture({ replay }), scope = app.check();
  assert.equal(scope.active.length, 5); assert.equal(scope.retired.length, replay ? 2 : 0);
  assert.equal(scope.discovery.length, 2); assert.equal(scope.siblings.length, 3);
});
for (const [name, edit] of [
  ['wrong company', request => { request.path = request.path.replace('/AAPL/', '/JPM/'); }],
  ['unknown endpoint', request => { if (request.path.endsWith('/quarters')) request.path += '/unknown'; }],
  ['wrong pin', request => { request.init.headers['X-FinLens-Data-Version'] = '1'; }],
  ['noncanonical pin', request => { request.init.headers['X-FinLens-Data-Version'] = '00'; }],
  ['missing pin', request => { delete request.init.headers['X-FinLens-Data-Version']; }],
  ['method', request => { request.init.method = 'POST'; }],
  ['null body', request => { request.init.body = null; }],
  ['raw JSON body', request => { request.init.body = 'null'; }],
  ['undefined body property', request => { request.init.body = undefined; }],
  ['discovery query', request => { if (request.path.endsWith('/quarters')) request.params.set('period', '2025-01-01,2025-03-31'); }],
  ['duplicate query', request => { if (request.path.endsWith('/summary')) request.params.append('period', 'quarter'); }],
  ['snapshot period', request => { if (request.path.endsWith('/summary')) request.params.set('period', 'annual'); }],
  ['history limit', request => { if (request.path.includes('/metrics/')) request.params.set('limit', '99'); }],
  ['history metric', request => { request.path = request.path.replace('/metrics/revenue', '/metrics/net_income'); }],
  ['foreign origin', (_request, url) => { url.hostname = 'foreign.test'; }],
]) test(`ledger rejects ${name} captured at start`, () => {
  assert.throws(() => fixture({ edit }).check(), assert.AssertionError);
});
for (const [name, change] of [
  ['cloned identity', app => { app.records[0] = { ...app.records[0] }; }],
  ['duplicate identity', app => { app.records.push(app.records[0]); }],
  ['duplicate request', app => { const other = fixture(); app.records.push(other.records[0]); }],
  ['mixed ownership', app => { app.records[0] = fixture().records[0]; }],
  ['rewritten query', app => { app.records[0].params.set('fiscal_year', '2025'); }],
  ['rewritten headers', app => { app.records[0].init.headers['X-FinLens-Data-Version'] = '1'; }],
  ['replaced signal', app => { app.records[0].init.signal = new AbortController().signal; }],
  ['cancelled current owner', app => { app.controllers.get(app.records.at(-1)).abort(); }],
  ['missing owner', app => { app.records.pop(); }],
  ['reordered raw identities', app => { app.records.reverse(); }],
]) test(`ledger rejects ${name} after a valid control`, () => {
  const app = fixture(); app.check(); change(app); assert.throws(app.check, assert.AssertionError);
});
test('ledger rejects a row misbound to an otherwise valid raw URL', () => {
  const app = fixture(), row = app.records[0];
  const clone = { ...row };
  assert.throws(() => mountedDataLedger().started(clone, new URL('http://finlens.test/api/finlens/companies/JPM/financials/annual')), assert.AssertionError);
  assert.throws(() => mountedDataLedger().started(clone, new URL('http://finlens.test/api/finlens/companies/AAPL/financials/annual?fiscal_year=2025')), assert.AssertionError);
});
test('ledger rejects cancellation after its replacement starts', () => assert.throws(() => fixture({ replay: true, lateAbort: true }).check(), assert.AssertionError));
test('ledger rejects delivered retired replay', () => assert.throws(() => fixture({ replay: true, settledReplay: true }).check(), assert.AssertionError));
test('ledger rejects replay without explicit admission', () => assert.throws(() => assertPendingDataScope(fixture({ replay: true }).records, { version: 0 }), assert.AssertionError));
test('ledger permits cross-request notifications and late cancelled delivery, but rejects duplicate settlements', () => {
  const app = fixture(), scope = app.check();
  // Creation order is A,Q,H,S,F; notification order is F,A,H,Q,S.
  app.ledger.responded(scope.active[4], new Response());
  app.controllers.get(scope.active[0]).abort();
  app.ledger.failed(scope.active[2]);
  app.ledger.responded(scope.active[1], new Response());
  app.ledger.responded(scope.active[3], new Response());
  app.ledger.responded(scope.active[0], new Response());
  assert.throws(() => app.ledger.responded(scope.active[0], new Response()), assert.AssertionError);
  assert.throws(() => app.ledger.failed(scope.active[4]), assert.AssertionError);
  assert.throws(() => app.ledger.responded({ ...scope.active[4] }, new Response()), assert.AssertionError);
  assert.throws(() => app.ledger.started(scope.active[4], new URL('http://finlens.test')), assert.AssertionError);
});

const frontend = fileURLToPath(new URL('../', import.meta.url));
const load = componentLoader(frontend);
test('component loader renders actual TSX and resolves its actual relative TS dependency', () => {
  const finance = load(fileURLToPath(new URL('../components/financial-research.tsx', import.meta.url)));
  const gaps = load(fileURLToPath(new URL('../lib/snapshot-gaps.ts', import.meta.url)));
  assert.equal(load(fileURLToPath(new URL('../lib/snapshot-gaps.ts', import.meta.url))), gaps);
  assert.equal(typeof gaps.snapshotPoint, 'function');
  const html = renderToStaticMarkup(React.createElement(finance.MetricCard, { point: {
    metric: 'revenue', status: 'unavailable', value: null, unit: 'USD', period: null,
    reason: 'No compatible source', provenance: [], alternatives: [], inputs: [], formula: null,
  } }));
  assert.match(html, /Unavailable/); assert.match(html, /No compatible source/);
});
test('unavailable snapshot accepts absent provenance and rejects a null-valued source fact', () => {
  const { snapshotPoint } = load(fileURLToPath(new URL('../lib/snapshot-gaps.ts', import.meta.url)));
  const period = { kind: 'quarter', start: '2025-01-01', end: '2025-03-31', fiscal_year: 2025, fiscal_period: 'Q1', fiscal_label_basis: 'fixture' };
  const point = { metric: 'revenue', unit: 'USD', status: 'unavailable', value: null,
    reason: 'No compatible source', period, formula: null, provenance: [], alternatives: [], inputs: [] };
  const valid = value => snapshotPoint(value, 'revenue', '0000320193', 'quarter', period);
  assert.equal(valid(point), true);
  const source = { fact_id: 1, company_cik: '0000320193', original_concept: 'Revenues', value: '1', unit: 'USD',
    period_start: period.start, period_end: period.end, filed: '2025-05-01', form: '10-Q',
    accession_number: '0000320193-25-000001', sec_url: 'https://www.sec.gov/Archives/fixture.htm',
    source_fiscal_year: 2025, source_fiscal_period: 'Q1' };
  assert.equal(valid({ ...point, provenance: [source] }), true);
  assert.equal(valid({ ...point, provenance: [{ ...source, value: null }] }), false);
  assert.equal(valid(point), true);
});
