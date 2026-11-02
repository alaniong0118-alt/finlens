import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

// Installed modules only. Real ReactDOM, API transport, validators, formatting and
// MetricProvenance; only the publication provider and fetch boundary are doubles.
// No child process, browser, service, fixture backend, socket or network call.
const require = createRequire(import.meta.url);
const Publication = React.createContext({ version: null, changed() {} });
let dom, createRoot, Comparison, helper, metrics, loadChartProjection;
const previousGlobals = new Map();
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const name of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent']) {
    previousGlobals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] });
  }
  previousGlobals.set('IS_REACT_ACT_ENVIRONMENT', Object.getOwnPropertyDescriptor(globalThis, 'IS_REACT_ACT_ENVIRONMENT'));
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import('react-dom/client'));
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const exports = {}; cache.set(path, exports);
    const compiled = ts.transpileModule(readFileSync(path, 'utf8'), { reportDiagnostics: true, compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
    } });
    assert.deepEqual(compiled.diagnostics, [], `Syntax diagnostics for ${path}`);
    const localRequire = name => {
      if (name === '@/components/research-freshness') return { useResearchVersion: () => React.useContext(Publication) };
      if (!name.startsWith('@/') && !name.startsWith('./')) return require(name);
      const base = name.startsWith('@/') ? fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url))
        : fileURLToPath(new URL(name, `file:///${path.replaceAll('\\', '/')}`));
      const dependency = ['.tsx', '.ts'].map(extension => base + extension).find(existsSync);
      assert.ok(dependency, `Known local dependency ${name}`);
      return load(dependency);
    };
    new Function('require', 'exports', compiled.outputText)(localRequire, exports);
    return exports;
  }
  Comparison = load(fileURLToPath(new URL('../components/annual-period-comparison.tsx', import.meta.url))).default;
  helper = load(fileURLToPath(new URL('../lib/annual-period-comparison.ts', import.meta.url)));
  metrics = load(fileURLToPath(new URL('../lib/company-comparison.ts', import.meta.url))).COMPARISON_METRICS;
  loadChartProjection = () => load(fileURLToPath(new URL('../components/annual-comparison-chart.tsx', import.meta.url))).annualChartProjection;
});
after(() => {
  dom?.window.close();
  for (const [name, descriptor] of previousGlobals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
  }
});

const company = { id: 1, ticker: 'AAA', name: 'Synthetic annual issuer', cik: '0000000001', exchange: 'TEST',
  has_indexed_filing: false, indexed_filing_count: 0 };
const other = { ...company, id: 2, ticker: 'BBB', name: 'Second synthetic issuer', cik: '0000000002' };
const years = [2025, 2024, 2023, 2022, 2021];
function annual(year = null, issuer = company, options = {}) {
  const period = year === null ? null : { kind: 'annual', start: `${year}-01-01`, end: `${year}-12-31`,
    fiscal_year: year, fiscal_period: 'FY', fiscal_label_basis: 'annual_period_end_year', ...options.period };
  const rows = {};
  if (year !== null) for (const [index, metric] of metrics.entries()) {
    const ratio = ['revenue_growth_yoy', 'operating_margin', 'net_margin', 'gross_margin'].includes(metric);
    const value = metric === 'revenue' ? year === 2024 ? '0' : String((year - 2020) * 1000000000)
      : metric === 'net_income' ? '-1000000' : '3000000';
    const accession = `${issuer.cik}-26-000001`;
    rows[metric] = { metric, unit: ratio ? 'ratio' : 'USD', status: ratio ? 'unavailable' : 'available',
      value: ratio ? null : value, reason: ratio ? 'No compatible approved denominator.' : null,
      period, formula: null, ...(metric === 'revenue' ? { revenue_basis: options.basis ?? 'total_revenue' } : {}),
      inputs: [], alternatives: [], provenance: ratio ? [] : [{ fact_id: (year - 1900) * 100 + index + 1,
        company_cik: issuer.cik, original_concept: `us-gaap:${metric}`, value, unit: 'USD',
        period_start: period.start, period_end: period.end, form: '10-K', filed: `${year + 1}-02-01`,
        accession_number: accession, sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${accession.replaceAll('-', '')}/annual.htm`,
        source_fiscal_year: year + 1, source_fiscal_period: 'FY' }] };
  }
  return { ticker: issuer.ticker, company_name: issuer.name, company_cik: issuer.cik, requested_period: 'annual',
    requested_fiscal_year: year, fiscal_years: options.years ?? years, period, period_reason: null,
    selection_policy: 'Existing server annual selection policy', metrics: rows };
}
function missing(year) {
  const value = annual(year); value.period = null; value.period_reason = 'Ambiguous stored annual reporting windows.';
  for (const point of Object.values(value.metrics)) Object.assign(point, { period: null, status: 'unavailable',
    value: null, reason: value.period_reason, inputs: [], provenance: [] });
  return value;
}
async function mount(ctx, options = {}) {
  const requests = [], changed = ctx.mock.fn();
  let issuer = options.company ?? company, version = options.version === undefined ? 0 : options.version;
  ctx.mock.method(globalThis, 'fetch', (path, init) => {
    assert.match(String(path), /^\/api\/finlens\/companies\/(AAA|BBB)\/financials\/annual(?:\?fiscal_year=\d{4})?$/,
      'Only the existing stored annual API is permitted');
    return new Promise(resolve => requests.push({ path: String(path), init, resolve }));
  });
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const render = async (next = {}) => {
    if ('company' in next) issuer = next.company;
    if ('version' in next) version = next.version;
    await act(async () => root.render(React.createElement(Publication.Provider, { value: { version, changed } },
      React.createElement(Comparison, { company: issuer }))));
  };
  await render();
  let unmounted = false;
  const unmount = async () => { if (!unmounted) { unmounted = true; await act(async () => root.unmount()); host.remove(); } };
  ctx.after(unmount);
  const request = (year = null, ticker = issuer.ticker) => requests.findLast(item => item.path ===
    `/api/finlens/companies/${ticker}/financials/annual${year === null ? '' : `?fiscal_year=${year}`}`);
  const release = async (req, body, pin = req?.init.headers?.['X-FinLens-Data-Version'], status = 200) => {
    assert.ok(req, 'Expected pending annual request');
    await act(async () => req.resolve(new Response(JSON.stringify(body), { status,
      headers: pin === null ? {} : { 'X-FinLens-Data-Version': String(pin) } })));
  };
  const discover = async (available = years) => release(request(), annual(null, issuer, { years: available }));
  const toggle = async year => { const checkbox = host.querySelector(`input[value="${year}"]`); assert.ok(checkbox);
    await act(async () => checkbox.click()); };
  const click = async text => { const button = [...host.querySelectorAll('button')].find(item => item.textContent === text);
    assert.ok(button, `Button ${text}`); await act(async () => button.click()); };
  const select = async (chosen = [2025, 2024]) => { for (const year of chosen) await toggle(year); };
  const compare = () => click('Compare selected annual periods');
  const button = () => host.querySelector('button[type="submit"]');
  const row = metric => [...host.querySelectorAll('tbody tr')].find(item => item.querySelector('th')?.textContent.startsWith(metric));
  return { host, requests, request, release, render, changed, discover, toggle, click, select, compare, button, row, unmount };
}

test('selected metric plots only validated observations, keeps the table, and makes no extra requests', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  await app.release(app.request(2025), annual(2025)); await app.release(app.request(2024), annual(2024));
  const before = app.requests.length;
  const select = app.host.querySelector('#annual-chart-metric');
  assert.ok(select); assert.equal(app.host.querySelector('svg'), null);
  await act(async () => { select.value = 'revenue'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  assert.equal(app.requests.length, before);
  const chart = app.host.querySelector('section[aria-labelledby="annual-chart-title"]');
  assert.equal(chart.querySelectorAll('circle').length, 2);
  assert.equal(chart.querySelectorAll('polyline, path').length, 0);
  assert.match(chart.textContent, /FY2025.*\$5B/); assert.match(chart.textContent, /FY2024.*\$0/);
  assert.match(chart.querySelector('svg').getAttribute('aria-label'), /Exact values, dates and sources/);
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11);
  assert.match(app.row('Revenue').textContent, /Exact API value: 5000000000 USD/);
  await app.toggle(2024); assert.equal(app.host.querySelector('#annual-chart-metric'), null);
});

test('failed and excluded columns remain gaps, and conflicting bases refuse a shared plot', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  await app.release(app.request(2025), annual(2025));
  await app.release(app.request(2024), { detail: 'Period request failed.' }, '0', 503);
  const select = app.host.querySelector('#annual-chart-metric');
  await act(async () => { select.value = 'revenue'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  let chart = app.host.querySelector('section[aria-labelledby="annual-chart-title"]');
  assert.equal(chart.querySelectorAll('circle').length, 1); assert.match(chart.textContent, /No value/);
  assert.match(chart.textContent, /Period request failed/); assert.match(chart.textContent, /basis is unknown/);
  await act(async () => { select.value = 'net_margin'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  assert.match(chart.textContent, /No available observations/); assert.match(chart.textContent, /Unavailable/);
  await app.compare();
  await app.release(app.request(2025), annual(2025, company, { basis: 'net_revenue' }));
  await app.release(app.request(2024), annual(2024));
  const next = app.host.querySelector('#annual-chart-metric');
  await act(async () => { next.value = 'revenue'; next.dispatchEvent(new Event('change', { bubbles: true })); });
  chart = app.host.querySelector('section[aria-labelledby="annual-chart-title"]');
  assert.match(chart.textContent, /Revenue-basis labels differ/); assert.match(chart.textContent, /not plotted on a shared axis/);
  assert.equal(chart.querySelector('svg'), null); assert.equal(app.requests.length, 5);
});

test('chart projection preserves order, signs, zero, and refuses unsafe conversion or mixed units', () => {
  const project = loadChartProjection();
  const column = (year, value, unit = 'USD', status = 'available') => ({ year, result: { metrics: {
    net_income: { value, unit, status, inputs: [], revenue_basis: null, period: null },
  }, period: null } });
  let result = project('net_income', [column(2025, '-1e308'), column(2024, '0'), column(2023, '1e308')]);
  assert.deepEqual(result.rows.map(row => row.value), [-1e308, 0, 1e308]); assert.equal(result.reason, null);
  result = project('net_income', [column(2025, '1e309')]); assert.match(result.reason, /cannot be represented/);
  result = project('net_income', [column(2025, '1e-999')]); assert.match(result.reason, /cannot be represented/);
  result = project('net_income', [column(2025, '1', 'USD'), column(2024, '1', 'EUR')]);
  assert.match(result.reason, /Units differ/);
});
test('not-applicable points remain gaps and publication changes remove the chart', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const earlier = annual(2024); const point = earlier.metrics.net_income;
  Object.assign(point, { status: 'not_applicable', value: null, reason: 'Excluded for this issuer.', provenance: [] });
  await app.release(app.request(2025), annual(2025)); await app.release(app.request(2024), earlier);
  const select = app.host.querySelector('#annual-chart-metric');
  await act(async () => { select.value = 'net_income'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  const chart = app.host.querySelector('section[aria-labelledby="annual-chart-title"]');
  assert.equal(chart.querySelectorAll('circle').length, 1);
  assert.match(chart.textContent, /Not applicable.*Excluded for this issuer/);
  assert.match(chart.textContent, /Vertical scale: -\$1M to -\$1M/);
  await app.render({ version: null });
  assert.equal(app.host.querySelector('#annual-chart-metric'), null);
  assert.equal(app.host.querySelector('table'), null);
});

test('large opposite-signed and zero values render as separate finite points in selected order', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select([2025, 2024, 2023]); await app.compare();
  for (const [year, value] of [[2025, '-1e308'], [2024, '0'], [2023, '1e308']]) {
    const result = annual(year); result.metrics.net_income.value = value;
    result.metrics.net_income.provenance[0].value = value;
    await app.release(app.request(year), result);
  }
  const select = app.host.querySelector('#annual-chart-metric');
  await act(async () => { select.value = 'net_income'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  const chart = app.host.querySelector('section[aria-labelledby="annual-chart-title"]');
  const dots = [...chart.querySelectorAll('circle')];
  assert.equal(dots.length, 3);
  assert.deepEqual(dots.map(dot => Number(dot.getAttribute('cy'))), [170, 100, 30]);
  assert.deepEqual([...chart.querySelectorAll('svg text')].map(node => node.textContent), ['FY2025', 'FY2024', 'FY2023']);
});

test('chart retains unscaled labels as its measured width changes and confines very narrow layouts', async ctx => {
  let width = 324, observer;
  const prior = Object.getOwnPropertyDescriptor(globalThis, 'ResizeObserver');
  class TestObserver {
    constructor(callback) { this.callback = callback; this.disconnected = false; observer = this; }
    observe(node) { this.node = node; }
    disconnect() { this.disconnected = true; }
  }
  Object.defineProperty(globalThis, 'ResizeObserver', { configurable: true, value: TestObserver });
  ctx.after(() => { if (prior) Object.defineProperty(globalThis, 'ResizeObserver', prior); else delete globalThis.ResizeObserver; });
  ctx.mock.method(dom.window.SVGElement.prototype, 'getBoundingClientRect', () => ({ width }));
  const app = await mount(ctx); await app.discover(); await app.select([2025, 2024, 2023, 2022]); await app.compare();
  for (const year of [2025, 2024, 2023, 2022]) await app.release(app.request(year), annual(year));
  const before = app.requests.length, table = app.host.querySelector('table').outerHTML;
  const select = app.host.querySelector('#annual-chart-metric');
  await act(async () => { select.value = 'revenue'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  const svg = app.host.querySelector('svg'), region = svg.parentElement;
  assert.equal(observer.node, svg); assert.equal(svg.getAttribute('viewBox'), '0 0 324 220');
  assert.equal(svg.getAttribute('height'), '220'); assert.equal(svg.style.minWidth, '240px');
  assert.equal(region.style.overflowX, 'auto'); assert.equal(region.tabIndex, 0);
  assert.equal(region.getAttribute('aria-label'), 'Annual observation chart');
  assert.deepEqual([...svg.querySelectorAll('circle')].map(dot => Number(dot.getAttribute('cx'))), [40, 121.33333333333333, 202.66666666666666, 284]);
  width = 240; await act(async () => observer.callback());
  assert.equal(svg.getAttribute('viewBox'), '0 0 240 220');
  assert.deepEqual([...svg.querySelectorAll('circle')].map(dot => Number(dot.getAttribute('cx'))), [40, 93.33333333333334, 146.66666666666669, 200]);
  width = 1326; await act(async () => observer.callback());
  assert.equal(svg.getAttribute('viewBox'), '0 0 1326 220');
  width = 0; await act(async () => observer.callback());
  assert.equal(svg.getAttribute('viewBox'), '0 0 1326 220');
  assert.equal(app.requests.length, before); assert.equal(app.host.querySelector('table').outerHTML, table);
  await app.unmount(); assert.equal(observer.disconnected, true);
});
