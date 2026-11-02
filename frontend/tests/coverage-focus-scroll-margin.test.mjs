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
  Comparison = load(fileURLToPath(new URL('../components/financial-coverage.tsx', import.meta.url))).default;
  helper = load(fileURLToPath(new URL('../lib/financial-coverage.ts', import.meta.url)));
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
async function mount(ctx, initial = 0, strict = false) {
  const requests = [], changed = ctx.mock.fn(); let issuer = company, version = initial;
  ctx.mock.method(globalThis,'fetch',(path,init) => {
    assert.match(String(path),/^\/api\/finlens\/companies\/(AAA|BBB)\/financials\/coverage\?period=(annual|quarter)(&end_from=\d{4}-\d{2}-\d{2}&end_to=\d{4}-\d{2}-\d{2})?$/);
    return new Promise(resolve => requests.push({path:String(path),init,resolve}));
  });
  const host=document.createElement('div'); document.body.append(host); const root=createRoot(host);
  async function render(next={}) { if('company' in next)issuer=next.company; if('version' in next)version=next.version;
    const panel=React.createElement(Publication.Provider,{value:{version,changed}},React.createElement(Comparison,{company:issuer})); await act(async()=>root.render(strict?React.createElement(React.StrictMode,null,panel):panel)); }
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

test('coverage filters reserve focus scroll space without changing load or filter behavior', async ctx => {
  const app = await mount(ctx); await app.click('Load stored coverage'); await app.release(app.requests[0], coverage());
  const filters = [...app.host.querySelectorAll('fieldset')].find(node => node.querySelector('legend')?.textContent === 'Filter loaded coverage');
  assert.ok(filters); const selects = [...filters.querySelectorAll('select')]; assert.equal(selects.length, 2);
  for (const select of selects) {
    assert.equal(select.style.scrollMargin, '8px');
    assert.ok(parseFloat(select.style.scrollMargin) >= 6, 'Scroll margin covers the existing 3px outline and 3px offset');
    await act(async () => select.focus()); assert.equal(document.activeElement, select);
  }
  const css = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(css, /:focus-visible\s*\{\s*outline:3px solid var\(--accent\);\s*outline-offset:3px;/);
  const status = selects[1];
  await act(async () => { status.value = 'not_applicable'; status.dispatchEvent(new Event('change', { bubbles: true })); });
  assert.match(app.host.textContent, /2 matching cells in these loaded windows/);
  assert.equal(app.requests.length, 1, 'Focus and filtering do not fetch');
});
