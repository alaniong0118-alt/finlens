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

test('valid annual and quarter maps preserve overlaps and original states without fiscal-label inference',()=>{
  for(const kind of ['annual','quarter']) {
    const value=coverage(kind);assert.equal(helper.validateCoverage(value,company,kind,0).columns.length,2);
    assert.equal(value.columns[0].metrics.gross_margin.status,'not_applicable');
  }
});
test('coverage response rejects identity, publication, period, count, lineage and source-path mismatches',()=>{
  for(const mutate of [
    v=>{v.company_cik=other.cik;},v=>{v.ticker=other.ticker;},v=>{v.data_version=1;},v=>{v.facts_version=1;},
    v=>{v.evidence_version=-1;},v=>{v.requested_period='quarter';},v=>{v.coverage_scope='complete_sec';},
    v=>{v.window_count=3;},v=>{v.cell_count=21;},v=>{v.source_reference_count=3;},v=>{v.columns[1].window={...v.columns[0].window};},
    v=>{delete v.columns[0].metrics.revenue;},v=>{v.columns[0].metrics.revenue.provenance[0].sec_url='https://www.sec.gov/Archives/edgar/data/2/000000000226000001/report.htm';},
    v=>{v.columns[1].metrics.revenue.provenance[0].fact_id=1;},
    v=>{const p=v.columns[0].metrics.free_cash_flow;p.status='available';p.value='5';p.reason=null;p.provenance=[{...v.columns[0].metrics.revenue.provenance[0]}];}
  ]) { const value=coverage();mutate(value);assert.throws(()=>helper.validateCoverage(value,company,'annual',0)); }
});
// Literal source/operand projections; expected finance values are fixed fixtures,
// never calculated by the client validator.
function completeCoverage(kind) {
  const body=coverage(kind);
  const values={revenue:'10',gross_profit:'5',operating_income:'2',net_income:'1',operating_cash_flow:'7',capital_expenditures:'3'};
  const definitions={revenue_growth_yoy:['1',[['current','revenue'],['prior','revenue']]],
    gross_margin:['0.5',[['gross_profit','gross_profit'],['revenue','revenue']]],
    operating_margin:['0.2',[['operating_income','operating_income'],['revenue','revenue']]],
    net_margin:['0.1',[['net_income','net_income'],['revenue','revenue']]],
    free_cash_flow:['4',[['operating_cash_flow','operating_cash_flow'],['capital_expenditures','capital_expenditures']]]};
  for(const [index,column] of body.columns.entries()) {
    column.window={start:`${2025-index}-01-01`,end:`${2025-index}-${kind==='annual'?'12-31':'03-31'}`};
    for(const point of Object.values(column.metrics))point.period={...point.period,...column.window};
    for(const [metric,value] of Object.entries(values)) {
      const point=column.metrics[metric],source=structuredClone(column.metrics.revenue.provenance[0]);
      Object.assign(source,{fact_id:index*100+Object.keys(values).indexOf(metric)+1,canonical_metric:metric,
        original_concept:metric,value:index===1&&metric==='revenue'?'5':value,
        period_start:column.window.start,period_end:column.window.end});
      Object.assign(point,{status:'available',value:source.value,reason:null,provenance:[source]});
    }
  }
  const latest=body.columns[0];
  for(const [metric,[value,roles]] of Object.entries(definitions)) {
    const point=latest.metrics[metric], inputs=roles.map(([role,name])=>{
      const base=(role==='prior'?body.columns[1]:latest).metrics[name];
      return {role,metric:name,value:base.value,unit:base.unit,period:structuredClone(base.period),fact_ids:base.provenance.map(source=>source.fact_id)};
    });
    Object.assign(point,{status:'available',value,reason:null,inputs,provenance:inputs.flatMap(input=>
      (input.role==='prior'?body.columns[1]:latest).metrics[input.metric].provenance.map(source=>structuredClone(source)))});
  }
  recount(body);return body;
}
function recount(body) { body.source_reference_count=body.columns.reduce((n,column)=>n+Object.values(column.metrics).reduce((sum,point)=>
  sum+point.provenance.length+point.alternatives.length+point.inputs.reduce((k,input)=>k+input.fact_ids.length,0),0),0); }

test('coverage accepts complete raw and all five derived source projections for both duration kinds',()=>{
  for(const kind of ['annual','quarter']) {
    const body=completeCoverage(kind);assert.equal(helper.validateCoverage(body,company,kind,0),body);
  }
});
test('coverage rejects raw value/source mismatch or missing/wrong selected canonical metric',()=>{
  for(const kind of ['annual','quarter'])for(const mutate of [
    point=>{point.value='999';},point=>{point.provenance[0].canonical_metric='net_income';},
    point=>{delete point.provenance[0].canonical_metric;},point=>{point.provenance[0].unit='USD/share';}
  ]){const body=completeCoverage(kind);mutate(body.columns[0].metrics.revenue);assert.throws(()=>helper.validateCoverage(body,company,kind,0));}
});
test('coverage binds every derived operand to its corresponding raw period/metric/value/unit and selected facts',()=>{
  for(const kind of ['annual','quarter'])for(const metric of ['revenue_growth_yoy','gross_margin','operating_margin','net_margin','free_cash_flow'])
    for(const failure of ['source-metric','base-value','base-unavailable','base-fact','operand-unit']) {
      const body=completeCoverage(kind), point=body.columns[0].metrics[metric],input=point.inputs[0],base=body.columns[0].metrics[input.metric];
      if(failure==='source-metric')point.provenance.find(source=>input.fact_ids.includes(source.fact_id)).canonical_metric='wrong_metric';
      if(failure==='base-value') {base.value='999';base.provenance[0].value='999';
        for(const p of Object.values(body.columns[0].metrics))for(const source of p.provenance)if(source.fact_id===base.provenance[0].fact_id)source.value='999';}
      if(failure==='base-unavailable')Object.assign(base,{status:'unavailable',value:null,reason:'No verified raw projection',provenance:[]});
      if(failure==='base-fact')base.provenance[0].fact_id+=9999;
      if(failure==='operand-unit')input.unit='USD/share';
      recount(body);assert.throws(()=>helper.validateCoverage(body,company,kind,0),`${kind}:${metric}:${failure}`);
    }
});
test('coverage rejects FCF roles referencing revenue facts even when IDs/counts and supplied values agree',()=>{
  for(const kind of ['annual','quarter']) {
    const body=completeCoverage(kind),column=body.columns[0],point=column.metrics.free_cash_flow;
    point.provenance=[structuredClone(column.metrics.revenue.provenance[0]),structuredClone(column.metrics.gross_profit.provenance[0])];
    point.inputs.forEach((input,index)=>{input.fact_ids=[point.provenance[index].fact_id];input.value=point.provenance[index].value;});
    recount(body);assert.throws(()=>helper.validateCoverage(body,company,kind,0));
  }
});

test('window/cell/reference bounds reject rather than partially accept a response',()=>{
  const value=coverage();value.columns=Array.from({length:65},()=>structuredClone(value.columns[0]));
  value.window_count=65;value.cell_count=715;assert.throws(()=>helper.validateCoverage(value,company,'annual',0));
  const refs=coverage();refs.columns[0].metrics.revenue.alternatives=Array.from({length:4097},()=>({}));
  assert.throws(()=>helper.validateCoverage(refs,company,'annual',0));
});
test('no startup or scope-change fetch; publication zero requires one explicit load',async ctx=>{
  const app=await mount(ctx,null);assert.equal(app.requests.length,0);
  await app.render({version:0});await app.period('quarter');assert.equal(app.requests.length,0);
  await app.click('Load stored coverage');await app.click('Load stored coverage');assert.equal(app.requests.length,1);
  assert.equal(app.requests[0].init.headers['X-FinLens-Data-Version'],'0');
  await app.release(app.requests[0],coverage('quarter'));
  assert.equal(app.host.querySelectorAll('tbody tr').length,2);assert.equal(app.host.querySelectorAll('tbody td').length,22);
  assert.match(app.host.textContent,/Publication version 0/);assert.match(app.host.textContent,/Facts version 0/);
  const summary=app.host.querySelector('tbody td summary');await act(async()=>{summary.focus();summary.click();});
  assert.equal(document.activeElement,summary);assert.equal(app.requests.length,1);
  assert.match(app.host.textContent,/Synthetic_original_missing_rule__v1 <em>literal<\/em>\./);
  assert.equal(app.host.querySelector('em'),null);
  const clear=[...app.host.querySelectorAll('button')].find(b=>b.textContent==='Clear coverage');clear.focus();
  await app.click('Clear coverage');assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.requests.length,1);
  assert.equal(document.activeElement,clear,'Clearing must not remove the focused control');
});
test('period change synchronously discards loaded and pending results without automatic requests',async ctx=>{
  const app=await mount(ctx);await app.click('Load stored coverage');await app.release(app.requests[0],coverage());
  await app.period('quarter');assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.requests.length,1);
  await app.click('Load stored coverage');const old=app.requests[1];await app.period('annual');assert.ok(old.init.signal.aborted);
  await app.release(old,coverage('quarter'));assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.requests.length,2);
});
test('company A-B-A and publication changes cannot restore old or ignored-abort responses',async ctx=>{
  const app=await mount(ctx);await app.click('Load stored coverage');const old=app.requests[0];
  await app.render({company:other});assert.ok(old.init.signal.aborted);assert.equal(app.requests.length,1);
  await app.render({company});await app.release(old,coverage());assert.equal(app.host.querySelector('tbody'),null);
  await app.click('Load stored coverage');await app.release(app.requests[1],coverage());
  await app.render({version:1});assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.requests.length,2);
});
test('cancel hides all output and permits an explicit successor without stale completion',async ctx=>{
  const app=await mount(ctx);await app.click('Load stored coverage');const old=app.requests[0];
  await app.click('Cancel coverage request');assert.ok(old.init.signal.aborted);await app.click('Load stored coverage');
  await app.release(old,coverage());assert.equal(app.host.querySelector('tbody'),null);
  await app.release(app.requests[1],coverage());assert.ok(app.host.querySelector('tbody'));
});
test('publication mismatch invalidates all output and calls freshness once without automatic retry',async ctx=>{
  const app=await mount(ctx);await app.click('Load stored coverage');await app.release(app.requests[0],coverage('annual',company,1),1);
  assert.equal(app.changed.mock.callCount(),1);assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.requests.length,1);
  assert.ok(app.host.querySelector('button').disabled);assert.match(app.host.textContent,/Published data changed/);
});
test('empty response preserves an honest empty state; failed or malformed reload never retains old cells',async ctx=>{
  const app=await mount(ctx);await app.click('Load stored coverage');
  const empty=coverage();Object.assign(empty,{columns:[],window_count:0,cell_count:0,source_reference_count:0});await app.release(app.requests[0],empty);
  assert.match(app.host.textContent,/does not establish absence of filings/);assert.equal(app.host.querySelector('tbody'),null);
  await app.click('Load stored coverage');await app.release(app.requests[1],coverage());assert.ok(app.host.querySelector('tbody'));
  await app.click('Load stored coverage');assert.equal(app.host.querySelector('tbody'),null);
  await app.release(app.requests[2],{detail:'Stored coverage is unavailable for this configuration.'},0,503);
  assert.equal(app.host.querySelector('tbody'),null);assert.match(app.host.textContent,/unavailable for this configuration/);
});

function inRange(body,from,to) {
  body.end_date_range={from_date:from,to_date:to};
  body.columns=body.columns.filter(column=>column.window.end>=from&&column.window.end<=to);
  body.window_count=body.columns.length;body.cell_count=body.window_count*metrics.length;recount(body);return body;
}
test('end-date ranges require paired real ISO dates in inclusive order',()=>{
  assert.equal(helper.coverageRange('',''),null);
  assert.deepEqual(helper.coverageRange('2024-02-29','2024-02-29'),{from_date:'2024-02-29',to_date:'2024-02-29'});
  for(const [from,to] of [['2025-01-01',''],['','2025-01-01'],['2025-02-29','2025-03-01'],
    ['0000-01-01','2025-03-01'],['2025-1-01','2025-03-01'],['2025-04-01','2025-03-01']])
    assert.throws(()=>helper.coverageRange(from,to));
});
test('range echo and every returned end date must match the requested scope',()=>{
  const range=helper.coverageRange('2025-01-01','2025-12-31');
  const value=inRange(coverage(),'2025-01-01','2025-12-31');
  assert.equal(helper.validateCoverage(value,company,'annual',0,range),value);
  for(const mutate of [v=>{delete v.end_date_range;},v=>{v.end_date_range=null;},
    v=>{v.end_date_range.to_date='2026-12-31';},v=>{v.end_date_range.extra=true;}]){
    const invalid=structuredClone(value);mutate(invalid);assert.throws(()=>helper.validateCoverage(invalid,company,'annual',0,range));
  }
  assert.throws(()=>helper.validateCoverage(value,company,'annual',0));
  const outside=inRange(completeCoverage('annual'),'2024-01-01','2025-12-31');
  outside.end_date_range=range;assert.throws(()=>helper.validateCoverage(outside,company,'annual',0,range));
});
test('filtered YoY retains independently bound prior revenue outside the map, without recalculation',()=>{
  for(const kind of ['annual','quarter']) {
    const range=helper.coverageRange('2025-01-01','2025-12-31');
    const value=inRange(completeCoverage(kind),range.from_date,range.to_date);
    assert.equal(helper.validateCoverage(value,company,kind,0,range),value);
    assert.equal(value.columns.length,1);assert.equal(value.columns[0].metrics.revenue_growth_yoy.value,'1');
    for(const mutate of [
      (s,i)=>{s.canonical_metric='net_income';},(s,i)=>{i.value='999';},(s,i)=>{s.value='999';},
      (s,i)=>{s.unit='USD/share';},(s,i)=>{s.company_cik=other.cik;},(s,i)=>{s.period_end='2024-02-29';},
      (s,i)=>{i.fact_ids=[999];},
    ]) {
      const bad=structuredClone(value),point=bad.columns[0].metrics.revenue_growth_yoy;
      const input=point.inputs.find(i=>i.role==='prior'),source=point.provenance.find(s=>input.fact_ids.includes(s.fact_id));
      mutate(source,input);assert.throws(()=>helper.validateCoverage(bad,company,kind,0,range));
    }
    const wider=helper.coverageRange('2024-01-01','2025-12-31');
    const missing=structuredClone(value);missing.end_date_range=wider;
    assert.throws(()=>helper.validateCoverage(missing,company,kind,0,wider),'prior within selected range must have raw projection');
  }
});
test('range change clears results, aborts pending requests and preserves native date input identity',async ctx=>{
  const app=await mount(ctx);await app.click('Load stored coverage');await app.release(app.requests[0],coverage());
  const input=app.host.querySelector('input[type=date]');input.focus();
  await app.dates('2025-01-01','2025-12-31');
  assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.requests.length,1);
  assert.equal(app.host.querySelector('input[type=date]'),input);assert.equal(document.activeElement,input);
  await app.click('Load stored coverage');const old=app.requests[1];
  assert.equal(old.path,'/api/finlens/companies/AAA/financials/coverage?period=annual&end_from=2025-01-01&end_to=2025-12-31');
  assert.equal(old.init.headers['X-FinLens-Data-Version'],'0');
  await app.dates('2024-01-01','2024-12-31');assert.ok(old.init.signal.aborted);
  await app.release(old,inRange(coverage(),'2025-01-01','2025-12-31'));assert.equal(app.host.querySelector('tbody'),null);
  assert.equal(app.requests.length,2);await app.click('Load stored coverage');
  const empty=inRange(coverage(),'2024-01-01','2024-12-31');await app.release(app.requests[2],empty);
  assert.match(app.host.textContent,/2024-01-01 through 2024-12-31, inclusive/);
  assert.match(app.host.textContent,/Complete within this selected scope only/);
  await app.dates('','');assert.equal(app.requests.length,3);
  await app.click('Load stored coverage');assert.equal(app.requests[3].path,'/api/finlens/companies/AAA/financials/coverage?period=annual');
});
test('incomplete/reversed ranges disable loading; safe limit detail is rendered literally with no partial map',async ctx=>{
  const app=await mount(ctx);await app.dates('2025-01-01','');
  assert.ok(app.host.querySelector('button').disabled);assert.match(app.host.textContent,/Enter both period-end dates/);
  await app.dates('2025-04-01','2025-03-31');assert.ok(app.host.querySelector('button').disabled);
  assert.equal(app.requests.length,0);await app.dates('2025-01-01','2025-12-31');await app.click('Load stored coverage');
  await app.release(app.requests[0],{detail:'Stored coverage exceeds the supported limits. No partial map is shown. Limit category: source-reference count. <script>literal</script>'},0,503);
  assert.equal(app.host.querySelector('tbody'),null);assert.equal(app.host.querySelector('script'),null);
  assert.match(app.host.textContent,/source-reference count\. <script>literal<\/script>/);
});
test('filtered publication mismatch still invalidates and never replays automatically',async ctx=>{
  const app=await mount(ctx);await app.dates('2025-01-01','2025-12-31');await app.click('Load stored coverage');
  await app.release(app.requests[0],inRange(coverage('annual',company,1),'2025-01-01','2025-12-31'),1);
  assert.equal(app.changed.mock.callCount(),1);assert.equal(app.host.querySelector('tbody'),null);
  assert.equal(app.requests.length,1);assert.ok(app.host.querySelector('button').disabled);
});
test('filtered company and nonzero publication changes discard ignored-abort completions',async ctx=>{
  const app=await mount(ctx);await app.dates('2025-01-01','2025-12-31');await app.click('Load stored coverage');
  const alpha=app.requests[0];await app.render({company:other,version:1});assert.ok(alpha.init.signal.aborted);
  await app.release(alpha,inRange(coverage(),'2025-01-01','2025-12-31'));assert.equal(app.host.querySelector('tbody'),null);
  assert.equal(app.requests.length,1);await app.click('Load stored coverage');const beta=app.requests[1];
  assert.match(beta.path,/companies\/BBB\/financials\/coverage/);assert.equal(beta.init.headers['X-FinLens-Data-Version'],'1');
  await app.release(beta,inRange(coverage('annual',other,1),'2025-01-01','2025-12-31'),1);
  assert.ok(app.host.querySelector('tbody'));await app.render({version:2});assert.equal(app.host.querySelector('tbody'),null);
  assert.equal(app.requests.length,2);
});
test('new date controls retain scoped responsive sizing and 44px target styles',()=>{
  const css=readFileSync(new URL('../app/globals.css',import.meta.url),'utf8');
  assert.match(css,/\.financial-coverage fieldset \{[^}]*min-width:0/);
  assert.match(css,/\.financial-coverage input\[type="date"\] \{[^}]*width:100%[^}]*max-width:100%[^}]*min-height:44px/);
  assert.match(css,/\.financial-coverage input\[type="date"\]:focus-visible \{ outline:3px solid var\(--accent\); outline-offset:-6px;/);
});

// Unlike release(), deliver headers now and hold the actual transport's JSON read.
// Deliberately ignore abort so the test proves body completion, not only cancellation.
async function coverageBody(ctx,app,request,conflict=false) {
  let resolve,reject,started=0,settled=0;
  const body=new Promise((yes,no)=>{resolve=yes;reject=no;});
  const response=new Response(null,{status:conflict?409:200,headers:{
    'X-FinLens-Data-Version':conflict?'1':'0',
    ...(conflict?{'X-FinLens-Error-Code':'DATA_VERSION_CHANGED'}:{}),
  }});
  ctx.mock.method(response,'json',async()=>{started++;try{return await body;}finally{settled++;}});
  await act(async()=>request.resolve(response));
  assert.equal(started,1,'Headers must reach an actively pending JSON read before scope changes');
  assert.equal(settled,0);
  return async(outcome,payload)=>{
    await act(async()=>{if(outcome==='body-error')reject(new Error('Obsolete body read failed'));else resolve(payload);});
    assert.equal(settled,1,'The ignored-abort body must actually finish before checking isolation');
  };
}

for(const strict of [false,true])for(const order of ['old-first','current-first'])
for(const outcome of ['success','publication-conflict','body-error']) {
  test(`coverage range A-B-A isolates started JSON ${outcome} ${order} strict ${strict}`,{timeout:5000},async ctx=>{
    const app=await mount(ctx,0,strict);
    await app.dates('2025-01-01','2025-12-31');
    await app.click('Load stored coverage');const old=app.requests[0];
    const finishOld=await coverageBody(ctx,app,old,outcome==='publication-conflict');
    assert.equal(app.changed.mock.callCount(),0,'Headers alone must not invalidate publication zero');

    await app.dates('2024-01-01','2024-12-31');
    await app.dates('2025-01-01','2025-12-31');
    assert.ok(old.init.signal.aborted);
    assert.equal(app.requests.length,1,'Range changes never start replacement requests');
    assert.equal(app.host.querySelector('tbody'),null);
    await app.click('Load stored coverage');const current=app.requests[1];
    assert.equal(current.path,old.path,'A-B-A intentionally restores identical URL scope');
    assert.equal(current.init.headers['X-FinLens-Data-Version'],'0');
    assert.notEqual(current.init.signal,old.init.signal);
    assert.equal(current.init.signal.aborted,false);

    const marked=marker=>{
      const value=inRange(coverage(),'2025-01-01','2025-12-31');
      for(const column of value.columns)column.metrics.gross_profit.reason=marker;
      helper.validateCoverage(value,company,'annual',0,helper.coverageRange('2025-01-01','2025-12-31'));
      return value;
    };
    const stale=outcome==='publication-conflict'?{detail:'Obsolete publication conflict'}:marked('Obsolete body marker');
    const load=()=>[...app.host.querySelectorAll('button')].find(button=>button.textContent==='Load stored coverage');
    const status=()=>app.host.querySelector('[role="status"]').textContent;
    if(order==='old-first') {
      await finishOld(outcome,stale);
      assert.equal(status(),'Loading stored financial coverage…','Old catch/finally cannot clear successor loading');
      assert.equal(load().disabled,true);
      assert.equal(current.init.signal.aborted,false);
      assert.equal(app.host.querySelector('tbody'),null);
      await app.click('Load stored coverage');assert.equal(app.requests.length,2,'Successor keeps its duplicate-load guard');
    }
    await app.release(current,marked('Current body marker'));
    const table=app.host.querySelector('table'),ready=status();assert.ok(table);
    if(order==='current-first')await finishOld(outcome,stale);
    assert.equal(app.host.querySelector('table'),table,'Old success/error cannot replace the current map');
    assert.equal(status(),ready);
    assert.match(app.host.textContent,/Current body marker/);
    assert.doesNotMatch(app.host.textContent,/Obsolete body marker|Obsolete body read failed|Obsolete publication conflict|Published data changed/);
    assert.match(app.host.textContent,/Publication version 0/);
    assert.equal(app.changed.mock.callCount(),0,'An obsolete 409 must not invalidate the replacement publication');
    assert.equal(load().disabled,false);
    assert.equal(app.requests.length,2,'No automatic replay or capability/evidence fan-out');
  });
}
