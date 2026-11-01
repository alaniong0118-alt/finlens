import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

const require = createRequire(import.meta.url), Publication = React.createContext({ version: null, changed() {} });
let dom, createRoot, Comparison, helper, metrics;
const previous = new Map();
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const name of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent']) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] });
  }
  previous.set('IS_REACT_ACT_ENVIRONMENT', Object.getOwnPropertyDescriptor(globalThis, 'IS_REACT_ACT_ENVIRONMENT'));
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import('react-dom/client'));
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const exports = {}; cache.set(path, exports);
    const output = ts.transpileModule(readFileSync(path, 'utf8'), { reportDiagnostics: true, compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
    } });
    assert.deepEqual(output.diagnostics, []);
    function localRequire(name) {
      if (name === '@/components/research-freshness') return { useResearchVersion: () => React.useContext(Publication) };
      if (!name.startsWith('@/') && !name.startsWith('./')) return require(name);
      const base = name.startsWith('@/') ? fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url))
        : fileURLToPath(new URL(name, `file:///${path.replaceAll('\\', '/')}`));
      const resolved = ['.tsx', '.ts'].map(ext => base + ext).find(existsSync);
      assert.ok(resolved, `Local dependency ${name}`); return load(resolved);
    }
    new Function('require', 'exports', output.outputText)(localRequire, exports); return exports;
  }
  Comparison = load(fileURLToPath(new URL('../components/quarter-window-comparison.tsx', import.meta.url))).default;
  helper = load(fileURLToPath(new URL('../lib/quarter-window-comparison.ts', import.meta.url)));
  metrics = load(fileURLToPath(new URL('../lib/company-comparison.ts', import.meta.url))).COMPARISON_METRICS;
});
after(() => { dom?.window.close(); for (const [name, descriptor] of previous) {
  if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
} });

const company = { id: 1, ticker: 'AAA', cik: '0000000001', name: 'Synthetic', exchange: 'TEST', has_indexed_filing: false, indexed_filing_count: 0 };
const other = { ...company, ticker: 'BBB', cik: '0000000002' };
const windows = [{ start: '2025-01-01', end: '2025-03-31' }, { start: '2025-04-01', end: '2025-06-30' }];
function response(selected = [], issuer = company) {
  return { ticker: issuer.ticker, company_name: issuer.name, company_cik: issuer.cik, requested_period: 'quarter', selection_policy: 'fixture',
    available_windows: windows.map(window => ({ ...window })), columns: selected.map(window => ({ window: { ...window }, metrics: Object.fromEntries(metrics.map(metric => [metric, {
      metric, unit: ['revenue_growth_yoy', 'gross_margin', 'operating_margin', 'net_margin'].includes(metric) ? 'ratio' : 'USD',
      status: metric === 'gross_margin' ? 'not_applicable' : 'unavailable', value: null, reason: 'No compatible evidence',
      period: { kind: 'quarter', start: window.start, end: window.end, fiscal_year: null, fiscal_period: null, fiscal_label_basis: 'unknown' },
      formula: null, provenance: [], alternatives: [], inputs: [],
    }])) })) };
}
function derivedResponse() {
  const body = response(windows);
  const definitions = {
    revenue_growth_yoy: ['1', [['current', 'revenue'], ['prior', 'revenue']]],
    gross_margin: ['0.5', [['gross_profit', 'gross_profit'], ['revenue', 'revenue']]],
    operating_margin: ['0.2', [['operating_income', 'operating_income'], ['revenue', 'revenue']]],
    net_margin: ['0.1', [['net_income', 'net_income'], ['revenue', 'revenue']]],
    free_cash_flow: ['4', [['operating_cash_flow', 'operating_cash_flow'], ['capital_expenditures', 'capital_expenditures']]],
  };
  const values = { revenue: '10', gross_profit: '5', operating_income: '2', net_income: '1', operating_cash_flow: '7', capital_expenditures: '3' };
  for (const [columnIndex, column] of body.columns.entries()) for (const [metric, [value, roles]] of Object.entries(definitions)) {
    const point = column.metrics[metric];
    Object.assign(point, { status: 'available', reason: null, value, provenance: [], inputs: [] });
    for (const [role, operand] of roles) {
      const period = { ...point.period }, prior = role === 'prior';
      if (prior) { period.start = period.start.replace('2025', '2024'); period.end = period.end.replace('2025', '2024'); }
      const accession = '0000000001-25-000001', id = 1 + columnIndex * 100 + Object.keys(values).indexOf(operand) + (prior ? 1000 : 0);
      const source = { fact_id: id, original_concept: `Synthetic_${operand}`, value: prior ? '5' : values[operand], unit: 'USD',
        company_cik: company.cik, period_start: period.start, period_end: period.end, form: '10-Q', filed: '2025-08-01',
        accession_number: accession, sec_url: `https://www.sec.gov/Archives/edgar/data/1/${accession.replaceAll('-', '')}/report.htm`,
        source_fiscal_year: 2025, source_fiscal_period: null };
      point.provenance.push(source); point.inputs.push({ role, metric: operand, value: source.value, unit: 'USD', period, fact_ids: [id] });
    }
  }
  return body;
}
async function mount(ctx, initial = 0) {
  const requests = [], changed = ctx.mock.fn(); let issuer = company, version = initial;
  ctx.mock.method(globalThis, 'fetch', (path, init) => new Promise(resolve => requests.push({ path: String(path), init, resolve })));
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  async function render(next = {}) { if ('company' in next) issuer = next.company; if ('version' in next) version = next.version;
    await act(async () => root.render(React.createElement(Publication.Provider, { value: { version, changed } }, React.createElement(Comparison, { company: issuer })))); }
  async function release(request, body, pin = 0) { await act(async () => request.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'X-FinLens-Data-Version': String(pin) } }))); }
  async function click(button) { await act(async () => button.click()); }
  await render(); ctx.after(async () => { await act(async () => root.unmount()); host.remove(); });
  return { requests, host, render, release, click, changed };
}

test('response rejects incorrect company, windows, metrics, units and missing reasons', () => {
  assert.equal(helper.validateQuarterResponse(response(windows), company, windows, windows).columns.length, 2);
  for (const mutate of [v => { v.company_cik = other.cik; }, v => { v.available_windows.push(windows[0]); },
    v => { v.columns[0].window = windows[1]; }, v => { delete v.columns[0].metrics.revenue; },
    v => { v.columns[0].metrics.revenue.unit = 'EUR'; }, v => { v.columns[0].metrics.revenue.reason = null; },
    v => { v.columns[0].metrics.revenue.period.fiscal_year = 2025; }]) {
    const value = response(windows); mutate(value); assert.throws(() => helper.validateQuarterResponse(value, company, windows, windows));
  }
});

test('selected financial evidence must belong to the company and exact window', () => {
  const value = response(windows), point = value.columns[0].metrics.revenue;
  const accession = '0000000001-25-000001';
  Object.assign(point, { status: 'available', value: '5', reason: null, provenance: [{ fact_id: 1, company_cik: company.cik,
    original_concept: 'Revenues', value: '5', unit: 'USD', period_start: windows[0].start, period_end: windows[0].end,
    form: '10-Q', filed: '2025-05-01', accession_number: accession,
    sec_url: `https://www.sec.gov/Archives/edgar/data/1/${accession.replaceAll('-', '')}/report.htm`,
    source_fiscal_year: 2025, source_fiscal_period: 'Q1' }] });
  assert.equal(helper.validateQuarterResponse(value, company, windows, windows).columns[0].metrics.revenue.value, '5');
  point.provenance[0].period_start = '2024-01-01'; point.provenance[0].period_end = '2024-03-31';
  assert.throws(() => helper.validateQuarterResponse(value, company, windows, windows));
});

test('all five available derived metrics require exact roles, operands and complete source references', () => {
  assert.equal(helper.validateQuarterResponse(derivedResponse(), company, windows, windows).columns.length, 2);
  const missing = derivedResponse(), growth = missing.columns[0].metrics.revenue_growth_yoy;
  growth.value = '0.2'; growth.inputs = []; growth.provenance = growth.provenance.slice(0, 1);
  assert.throws(() => helper.validateQuarterResponse(missing, company, windows, windows));
  for (const metric of ['revenue_growth_yoy', 'gross_margin', 'operating_margin', 'net_margin', 'free_cash_flow']) {
    for (const mutate of [p => { p.inputs = []; }, p => { p.inputs.pop(); }, p => { p.inputs[1].role = p.inputs[0].role; },
      p => { p.inputs[0].metric = 'wrong'; }, p => { p.inputs[0].fact_ids = [9999]; },
      p => { p.inputs[0].fact_ids.push(p.inputs[0].fact_ids[0]); }, p => { p.provenance.pop(); },
      p => { p.inputs[0].value = '999'; }, p => { p.provenance.push({ ...p.provenance[0], fact_id: 9999 }); }]) {
      const body = derivedResponse(); mutate(body.columns[0].metrics[metric]);
      assert.throws(() => helper.validateQuarterResponse(body, company, windows, windows), metric);
    }
  }
});

test('SEC archive URL binds both stated company and accession without replacing server URLs', () => {
  const control = derivedResponse(), supplied = 'https://www.sec.gov/Archives/edgar/data/1/000000000125000001/report.htm?context=test#raw';
  for (const column of control.columns) for (const point of Object.values(column.metrics))
    for (const source of point.provenance) if (source.fact_id === 1) source.sec_url = supplied;
  assert.equal(helper.validateQuarterResponse(control, company, windows, windows).columns[0].metrics.revenue_growth_yoy.provenance[0].sec_url, supplied);
  const body = derivedResponse(), source = body.columns[0].metrics.revenue_growth_yoy.provenance[0];
  source.sec_url = 'https://www.sec.gov/Archives/edgar/data/2/000000000225000099/report.htm';
  assert.throws(() => helper.validateQuarterResponse(body, company, windows, windows));
  for (const path of ['1/000000000125000099/report.htm', '2/000000000125000001/report.htm']) {
    const value = derivedResponse(); value.columns[0].metrics.net_margin.provenance[0].sec_url = `https://www.sec.gov/Archives/edgar/data/${path}`;
    assert.throws(() => helper.validateQuarterResponse(value, company, windows, windows));
  }
});

test('immutable fact identity includes selected and alternative references across columns', () => {
  const control = derivedResponse(), original = control.columns[0].metrics.net_margin.provenance[0];
  // Object field order and reference-specific projection do not change a fact.
  control.columns[1].metrics.net_income.alternatives = [{ canonical_metric: 'net_income', ...Object.fromEntries(Object.entries(original).reverse()) }];
  assert.equal(helper.validateQuarterResponse(control, company, windows, windows).columns.length, 2);
  for (const target of [control.columns[0].metrics.net_margin, control.columns[1].metrics.net_income]) {
    const value = derivedResponse(); const column = target === control.columns[0].metrics.net_margin ? 0 : 1;
    value.columns[column].metrics.net_income.alternatives = [{ ...original, value: '999' }];
    assert.throws(() => helper.validateQuarterResponse(value, company, windows, windows));
  }
});

test('version zero pins one discovery and one comparison; selection changes hide data', async ctx => {
  const app = await mount(ctx);
  assert.equal(app.requests.length, 1); assert.equal(app.requests[0].init.headers['X-FinLens-Data-Version'], '0');
  await app.release(app.requests[0], response());
  const checks = app.host.querySelectorAll('input[type=checkbox]'); await app.click(checks[0]); await app.click(checks[1]);
  await app.click(app.host.querySelector('button[type=submit]'));
  assert.equal(app.requests.length, 2); assert.equal(app.requests[1].init.headers['X-FinLens-Data-Version'], '0');
  assert.equal(new URL(app.requests[1].path, 'http://localhost').searchParams.getAll('period').length, 2);
  await app.release(app.requests[1], response(windows));
  assert.match(app.host.textContent, /Not applicable/); assert.match(app.host.textContent, /No compatible evidence/);
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11);
  await app.click(checks[0]); assert.equal(app.host.querySelector('tbody'), null); assert.equal(app.requests.length, 2);
});

test('ignored abort and company changes cannot publish stale values', async ctx => {
  const app = await mount(ctx); const old = app.requests[0];
  await app.render({ company: other }); assert.ok(old.init.signal.aborted); assert.equal(app.requests.length, 2);
  await app.release(old, response()); assert.doesNotMatch(app.host.textContent, /Select two to four reported windows/);
  await app.release(app.requests[1], response([], other)); assert.match(app.host.textContent, /Select two to four reported windows/);
  await app.render({ version: null }); assert.equal(app.host.querySelector('fieldset'), null);
});

test('changing selection cancels an in-flight comparison and ignores its late body', async ctx => {
  const app = await mount(ctx); await app.release(app.requests[0], response());
  const checks = app.host.querySelectorAll('input[type=checkbox]'); await app.click(checks[0]); await app.click(checks[1]);
  await app.click(app.host.querySelector('button[type=submit]')); const pending = app.requests[1];
  await app.click(checks[0]); assert.ok(pending.init.signal.aborted);
  await app.release(pending, response(windows)); assert.equal(app.host.querySelector('tbody'), null);
  assert.equal(app.requests.length, 2);
});

test('mismatched response version hides discovery and triggers publication refresh', async ctx => {
  const app = await mount(ctx); await app.release(app.requests[0], response(), 1);
  assert.equal(app.changed.mock.callCount(), 1); assert.equal(app.host.querySelectorAll('input').length, 0);
  assert.match(app.host.textContent, /Published data changed/);
});

test('empty or malformed discovery never invents periods', async ctx => {
  const app = await mount(ctx); const empty = response(); empty.available_windows = [];
  await app.release(app.requests[0], empty);
  assert.match(app.host.textContent, /Fewer than two reported windows/);
  assert.equal(app.host.querySelectorAll('input').length, 0);
  assert.ok(app.host.querySelector('button[type=submit]').disabled);
  const bad = response(); bad.available_windows = [{ start: '2025-02-30', end: '2025-06-01' }];
  assert.throws(() => helper.validateQuarterResponse(bad, company, []));
});

test('malformed or partial comparison clears the entire grid', async ctx => {
  const app = await mount(ctx); await app.release(app.requests[0], response());
  const checks = app.host.querySelectorAll('input[type=checkbox]'); await app.click(checks[0]); await app.click(checks[1]);
  await app.click(app.host.querySelector('button[type=submit]'));
  const partial = response(windows); partial.columns.pop(); await app.release(app.requests[1], partial);
  assert.equal(app.host.querySelector('tbody'), null); assert.equal(app.requests.length, 2);
});
