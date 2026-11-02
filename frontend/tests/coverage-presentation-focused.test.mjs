import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

const require = createRequire(import.meta.url), Publication = React.createContext({ version: null, changed() {} });
let dom, createRoot, Comparison, helper, presentation, metrics;
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
  Comparison = load(fileURLToPath(new URL('../components/financial-coverage.tsx', import.meta.url))).default;
  helper = load(fileURLToPath(new URL('../lib/financial-coverage.ts', import.meta.url)));
  presentation = load(fileURLToPath(new URL('../lib/coverage-presentation.ts', import.meta.url)));
  metrics = load(fileURLToPath(new URL('../lib/company-comparison.ts', import.meta.url))).COMPARISON_METRICS;
});
after(() => { dom?.window.close(); for (const [name, descriptor] of previous) {
  if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
} });

const company = { id: 1, ticker: 'AAA', cik: '0000000001', name: 'Synthetic coverage', exchange: 'TEST', has_indexed_filing: false, indexed_filing_count: 0 };
const other = { ...company, ticker: 'BBB', cik: '0000000002' };
function coverage(kind = 'annual', issuer = company, pin = 0) {
  const windows = kind === 'annual' ? [{ start: '2025-01-01', end: '2025-12-31' }, { start: '2025-01-02', end: '2025-12-31' }]
    : [{ start: '2025-04-01', end: '2025-06-30' }, { start: '2025-01-01', end: '2025-03-31' }];
  const columns = windows.map((window,index) => ({ window, metrics: Object.fromEntries(metrics.map(metric => {
    const revenue = metric === 'revenue', accession = issuer.cik + '-26-000001';
    const point = { metric, unit: ['revenue_growth_yoy','gross_margin','operating_margin','net_margin'].includes(metric) ? 'ratio' : 'USD',
      status: revenue ? 'available' : metric === 'gross_margin' ? 'not_applicable' : 'unavailable', value: revenue ? '10' : null,
      reason: revenue ? null : 'Synthetic_original_missing_rule__v1 <em>literal</em>.',
      period: { kind, ...window, fiscal_year: null, fiscal_period: null, fiscal_label_basis: 'unknown' },
      formula: null, inputs: [], alternatives: [], provenance: revenue ? [{ fact_id: index + 1, canonical_metric: 'revenue', original_concept: 'Revenues',
        value: '10', unit: 'USD', company_cik: issuer.cik, period_start: window.start, period_end: window.end, form: '10-K', filed: '2026-02-01',
        accession_number: accession, sec_url: 'https://www.sec.gov/Archives/edgar/data/' + Number(issuer.cik) + '/' + accession.replaceAll('-','') + '/report.htm',
        source_fiscal_year: 2025, source_fiscal_period: null }] : [] };
    return [metric,point];
  })) }));
  return { ticker: issuer.ticker, company_cik: issuer.cik, company_name: issuer.name, requested_period: kind,
    coverage_scope: 'stored_reported_windows', selection_policy: 'Synthetic stored coverage', data_version: pin, facts_version: pin,
    evidence_version: pin, window_count: 2, cell_count: 22, source_reference_count: 2, columns };
}
async function mount(ctx, initial = 0) {
  const requests = [], changed = ctx.mock.fn(); let issuer = company, version = initial;
  ctx.mock.method(globalThis,'fetch',(path,init) => {
    assert.match(String(path),/^\/api\/finlens\/companies\/(AAA|BBB)\/financials\/coverage\?period=(annual|quarter)(&end_from=\d{4}-\d{2}-\d{2}&end_to=\d{4}-\d{2}-\d{2})?$/);
    return new Promise(resolve => requests.push({path:String(path),init,resolve}));
  });
  const host=document.createElement('div'); document.body.append(host); const root=createRoot(host);
  async function render(next={}) { if('company' in next)issuer=next.company; if('version' in next)version=next.version;
    await act(async()=>root.render(React.createElement(Publication.Provider,{value:{version,changed}},React.createElement(Comparison,{company:issuer})))); }
  async function release(request,body,pin=0,status=200) { await act(async()=>request.resolve(new Response(JSON.stringify(body),{status,headers:{'X-FinLens-Data-Version':String(pin)}}))); }
  async function click(name) { const button=[...host.querySelectorAll('button')].find(b=>b.textContent===name); assert.ok(button,name); await act(async()=>button.click()); }
  async function period(value) { await act(async()=>{const select=host.querySelector('select');select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));}); }
  async function dates(from,to) { for(const [index,value] of [from,to].entries()) await act(async()=>{
    const input=host.querySelectorAll('input[type=date]')[index];
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input,value);
    input.dispatchEvent(new Event('change',{bubbles:true}));
  }); }
  await render();ctx.after(async()=>{await act(async()=>root.unmount());host.remove();});
  return {host,requests,changed,render,release,click,period,dates};
}


async function select(app, label, value) {
  const control = [...app.host.querySelectorAll('label')].find(node => node.firstChild?.textContent === label)?.querySelector('select');
  assert.ok(control, label);
  await act(async () => { control.value = value; control.dispatchEvent(new Event('change', { bubbles: true })); });
  return control;
}

test('projection counts all 704 cells and preserves overlapping windows and original references', () => {
  const input = coverage();
  input.columns = Array.from({ length: 64 }, (_, i) => {
    const column = structuredClone(input.columns[i % 2]);
    const year = 1962 + i;
    column.window = { start: `${year}-01-01`, end: `${year}-12-31` };
    for (const point of Object.values(column.metrics)) point.period = { ...point.period, ...column.window };
    Object.assign(column.metrics.revenue.provenance[0], { fact_id: i + 1, period_start: column.window.start, period_end: column.window.end });
    return column;
  });
  input.window_count = 64; input.cell_count = 704; input.source_reference_count = 64;
  helper.validateCoverage(input, company, 'annual', 0);
  const all = presentation.presentCoverage(input, 'all', 'all');
  assert.deepEqual(all.totals, { available: 64, unavailable: 576, not_applicable: 64 });
  assert.equal(all.visibleCount, 704); assert.equal(all.columns.length, 64);
  const gap = presentation.presentCoverage(input, 'gross_margin', 'not_applicable');
  assert.equal(gap.visibleCount, 64); assert.equal(gap.columns[0], input.columns[0]);
  assert.equal(gap.columns[0].metrics.gross_margin.reason, 'Synthetic_original_missing_rule__v1 <em>literal</em>.');
  assert.equal(presentation.presentCoverage(input, 'revenue', 'unavailable').visibleCount, 0);
  const verified = helper.validateCoverage(coverage(), company, 'annual', 0);
  const overlapping = presentation.presentCoverage(verified, 'revenue', 'available');
  assert.equal(overlapping.columns.length, 2); assert.notDeepEqual(overlapping.columns[0].window, overlapping.columns[1].window);
  assert.equal(overlapping.columns[0].metrics.revenue.provenance[0], verified.columns[0].metrics.revenue.provenance[0]);
});

test('mounted filters retain full totals, literal reasons, provenance, focus and do not fetch', async ctx => {
  const app = await mount(ctx); await app.click('Load stored coverage'); await app.release(app.requests[0], coverage());
  assert.match(app.host.textContent, /22 total cells · 2 available · 18 unavailable · 2 not applicable/);
  assert.match(app.host.textContent, /22 matching cells in these loaded windows/);
  await select(app, 'Status ', 'available');
  assert.equal(app.host.querySelectorAll('tbody td .muted').length, 20);
  assert.match(app.host.textContent, /2 matching cells/);
  const metric = await select(app, 'Metric ', 'gross_margin'); metric.focus();
  await select(app, 'Status ', 'not_applicable');
  assert.equal(document.activeElement, metric); assert.equal(app.host.querySelectorAll('tbody tr').length, 2);
  assert.equal(app.host.querySelectorAll('tbody td').length, 2);
  assert.match(app.host.textContent, /2 matching cells/); assert.match(app.host.textContent, /22 total cells/);
  assert.match(app.host.textContent, /Synthetic_original_missing_rule__v1 <em>literal<\/em>/);
  assert.equal(app.host.querySelector('em'), null);
  const detail = app.host.querySelector('tbody summary'); await act(async () => detail.click());
  assert.equal(app.requests.length, 1);
  await select(app, 'Metric ', 'revenue');
  assert.match(app.host.textContent, /0 matching cells/); assert.match(app.host.textContent, /No cells match these filters/);
  assert.equal(app.host.querySelector('tbody'), null); assert.ok(app.host.contains(metric));
  await select(app, 'Status ', 'available'); assert.equal(app.host.querySelectorAll('tbody td').length, 2);
  await act(async () => app.host.querySelector('tbody summary').click());
  assert.ok(app.host.querySelector('tbody a[href^="https://www.sec.gov/"]')); assert.equal(app.requests.length, 1);
});

test('reload, scope changes and failures clear filters and old results without hidden fetches', async ctx => {
  const app = await mount(ctx); await app.click('Load stored coverage'); await app.release(app.requests[0], coverage());
  await select(app, 'Status ', 'unavailable'); await app.click('Load stored coverage');
  assert.equal(app.host.querySelector('tbody'), null); await app.release(app.requests[1], coverage());
  assert.equal([...app.host.querySelectorAll('select')].find(s => s.value === 'all')?.value, 'all');
  assert.match(app.host.textContent, /22 matching cells/);
  await select(app, 'Metric ', 'revenue'); await app.period('quarter'); assert.equal(app.host.querySelector('tbody'), null);
  await app.click('Load stored coverage'); await app.release(app.requests[2], coverage('quarter'));
  assert.match(app.host.textContent, /22 matching cells/);
  await select(app, 'Status ', 'available'); await app.render({ company: other, version: 1 });
  assert.equal(app.host.querySelector('tbody'), null); await app.click('Load stored coverage');
  await app.release(app.requests[3], coverage('quarter', other, 1), 1); assert.match(app.host.textContent, /22 matching cells/);
  await select(app, 'Status ', 'unavailable'); await app.dates('2025-01-01', '2025-12-31');
  assert.equal(app.host.querySelector('tbody'), null); await app.click('Load stored coverage');
  await app.release(app.requests[4], { detail: 'Coverage failed' }, 1, 503);
  assert.match(app.host.textContent, /Coverage failed/); assert.equal(app.host.querySelector('tbody'), null);
  await app.click('Load stored coverage');
  const ranged = coverage('quarter', other, 1); ranged.end_date_range = { from_date: '2025-01-01', to_date: '2025-12-31' };
  await app.release(app.requests[5], ranged, 1); assert.match(app.host.textContent, /22 matching cells/);
  assert.equal(app.requests.length, 6);
});

test('inclusive date range and zero-cell result remain explicit', async ctx => {
  const app = await mount(ctx); await app.dates('2025-01-01', '2025-12-31'); await app.click('Load stored coverage');
  const value = coverage(); value.end_date_range = { from_date: '2025-01-01', to_date: '2025-12-31' };
  await app.release(app.requests[0], value);
  assert.match(app.host.textContent, /In these loaded windows \(period ends 2025-01-01 through 2025-12-31, inclusive\)/);
  await app.click('Load stored coverage'); const empty = coverage();
  Object.assign(empty, { end_date_range: value.end_date_range, columns: [], window_count: 0, cell_count: 0, source_reference_count: 0 });
  await app.release(app.requests[1], empty); assert.match(app.host.textContent, /0 total cells · 0 available · 0 unavailable · 0 not applicable/);
  assert.match(app.host.textContent, /does not establish absence of filings/);
});
