import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

const require=createRequire(import.meta.url), Publication=React.createContext({version:null,changed(){}});
const company={id:1,ticker:'AAA',cik:'0000000001',name:'Synthetic proportions',exchange:'TEST',has_indexed_filing:false,indexed_filing_count:0};
const other={...company,ticker:'BBB',cik:'0000000002'};
let dom,createRoot,FinancialResearch,helper,canonical;
const previous=new Map();
before(async()=>{
 dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://finlens.test'});
 for(const name of ['window','document','HTMLElement','Node','Event','MouseEvent','IS_REACT_ACT_ENVIRONMENT']){
  previous.set(name,Object.getOwnPropertyDescriptor(globalThis,name));
  Object.defineProperty(globalThis,name,{configurable:true,value:name==='IS_REACT_ACT_ENVIRONMENT'?true:dom.window[name]});
 }
 ({createRoot}=await import('react-dom/client'));
 const cache=new Map();
 function load(path){
  if(cache.has(path))return cache.get(path);const exports={};cache.set(path,exports);
  const output=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
  function localRequire(name){
   if(name==='@/components/research-freshness')return {useResearchVersion:()=>React.useContext(Publication)};
   if(!name.startsWith('@/')&&!name.startsWith('./'))return require(name);
   const base=name.startsWith('@/')?fileURLToPath(new URL('../'+name.slice(2),import.meta.url)):fileURLToPath(new URL(name,'file:///'+path.replaceAll('\\','/')));
   const resolved=['.tsx','.ts'].map(ext=>base+ext).find(existsSync);assert.ok(resolved,name);return load(resolved);
  }
  new Function('require','exports',output)(localRequire,exports);return exports;
 }
 helper=load(fileURLToPath(new URL('../lib/balance-sheet-ratios.ts',import.meta.url)));
 FinancialResearch=load(fileURLToPath(new URL('../components/financial-research.tsx',import.meta.url))).default;
 canonical=pythonPayloads();
});
after(()=>{dom?.window.close();for(const [name,descriptor] of previous){if(descriptor)Object.defineProperty(globalThis,name,descriptor);else delete globalThis[name];}});

function pythonPayloads(){
 const backend=fileURLToPath(new URL('../../backend/',import.meta.url));
 const python=['.venv/Scripts/python.exe','.venv/bin/python'].map(path=>fileURLToPath(new URL(`../../backend/${path}`,import.meta.url))).find(existsSync);
 assert.ok(python,'The existing backend virtualenv is required for canonical serialization controls');
 const run=spawnSync(python,['-B','-c',`
import json, sys
from pathlib import Path
def forbidden(*args, **kwargs):
    raise AssertionError('Live dependencies and private configuration forbidden')
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = Path(args[0]).name.lower()
        if name == '.env' or name.startswith('.env.'): forbidden()
    if event in ('socket.connect', 'socket.getaddrinfo'): forbidden()
    if event == 'import' and args[0] in ('app.database', 'app.config', 'torch', 'sentence_transformers', 'transformers'): forbidden()
sys.addaudithook(guard)
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
with patch('sqlalchemy.engine.Engine.connect', side_effect=forbidden), patch('socket.socket.connect', side_effect=forbidden), patch('socket.create_connection', side_effect=forbidden):
    from app.financial_metrics_service import FinancialMetrics
    company = SimpleNamespace(ticker='AAA', cik='0000000001', name='Synthetic proportions')
    facts = []
    for concept, value in [('Liabilities','100'), ('Assets','300'), ('CashAndCashEquivalentsAtCarryingValue','0')]:
        facts.append(SimpleNamespace(id=len(facts)+1, company_cik=company.cik, metric=concept, value=Decimal(value), unit='USD',
            period_start=None, period_end=date(2025,12,31), period_type='instant', fiscal_year=2025, fiscal_period='FY', frame=None,
            form='10-K', filed=date(2026,2,1), accession_number='0000000001-26-000001', source='SEC Company Facts API: '+concept, created_at=datetime(2026,2,1)))
    available = FinancialMetrics(company, facts).summary(include_balance_ratios=True).model_dump(mode='json')
    unavailable = FinancialMetrics(company, [f for f in facts if f.metric!='Assets']).summary(include_balance_ratios=True).model_dump(mode='json')
    print(json.dumps({'available':available, 'unavailable':unavailable}))
`],{cwd:backend,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},timeout:15000,maxBuffer:128*1024});
 assert.equal(run.status,0,run.stderr||run.error?.message);
 return JSON.parse(run.stdout);
}

function fixture(issuer=company){
 const period={kind:'instant',start:null,end:'2025-12-31',fiscal_year:null,fiscal_period:null,fiscal_label_basis:'unknown'};
 const definitions=helper.BALANCE_SHEET_RATIOS,concepts={total_assets:'Assets',total_liabilities:'Liabilities',cash_and_equivalents:'CashAndCashEquivalentsAtCarryingValue'};
 const values={total_assets:'300',total_liabilities:'100',cash_and_equivalents:'0'},ids={total_assets:2,total_liabilities:1,cash_and_equivalents:3};
 const source=name=>({fact_id:ids[name],canonical_metric:name,company_cik:issuer.cik,stored_metric:concepts[name],original_concept:concepts[name],value:values[name],unit:'USD',
  period_start:null,period_end:period.end,stored_period_type:'instant',source_fiscal_year:2025,source_fiscal_period:'FY',frame:null,filed:'2026-02-01',form:'10-K',
  accession_number:issuer.cik+'-26-000001',source:'SEC Company Facts API: '+concepts[name],stored_at:'2026-02-01T00:00:00',
  sec_url:'https://www.sec.gov/Archives/edgar/data/'+Number(issuer.cik)+'/'+issuer.cik+'26000001/report.htm'});
 return Object.fromEntries(definitions.map(definition=>[definition.id,{metric:definition.id,unit:'ratio',status:'available',value:definition.id.startsWith('total')?'0.3333333333333333333333333333':'0',reason:null,
  period:{...period},formula:definition.inputs.join(' / '),provenance:definition.inputs.map(source),alternatives:[],
  inputs:definition.inputs.map(name=>({role:name,metric:name,value:values[name],unit:'USD',period:{...period},fact_ids:[ids[name]]}))}]));
}
const first=points=>points.total_liabilities_to_total_assets;
test('canonical same-date Decimal strings, complete lineage and zero cash are accepted unchanged',()=>{
 const value=fixture();assert.equal(helper.balanceSheetRatios(value,company.cik),value);
 assert.equal(first(value).value,'0.3333333333333333333333333333');
});
test('a distinct older source alternative remains diagnostic while selected filing inputs agree',()=>{
 const value=fixture(),p=first(value);const alternative={...p.provenance[1],fact_id:900,value:'250',filed:'2026-01-15',accession_number:company.cik+'-26-000002'};
 alternative.sec_url='https://www.sec.gov/Archives/edgar/data/1/'+alternative.accession_number.replaceAll('-','')+'/report.htm';p.alternatives=[alternative];
 assert.equal(helper.balanceSheetRatios(value,company.cik),value);
});
for(const [name,mutate] of [
 ['company',p=>p.provenance[0].company_cik=other.cik],['date',p=>p.provenance[0].period_end='2025-09-30'],
 ['currency',p=>p.provenance[0].unit='EUR'],['scope',p=>p.provenance[0].accession_number=company.cik+'-26-000002'],
 ['SEC path',p=>p.provenance[0].sec_url='https://www.sec.gov/Archives/edgar/data/2/000000000226000001/report.htm'],
 ['missing operand',p=>p.inputs.pop()],['duplicate role',p=>p.inputs[1].role=p.inputs[0].role],
 ['wrong operand metric',p=>p.inputs[0].metric='revenue'],['wrong source concept',p=>p.provenance[0].original_concept='Revenues'],
 ['unbound ID',p=>p.inputs[0].fact_ids=[900]],['input value',p=>p.inputs[0].value='999'],
 ['input date',p=>p.inputs[0].period.end='2024-12-31'],['negative numerator',p=>p.inputs[0].value='-1'],['zero denominator',p=>p.inputs[1].value='0'],
 ['negative result',p=>p.value='-0.1'],['nonfinite',p=>p.value='NaN'],['formula',p=>p.formula='debt / assets'],
 ['selected/alternative identity',p=>p.alternatives=[{...p.provenance[0],value:'999'}]],
 ['duplicate source',p=>p.alternatives=[{...p.provenance[0]}]],
 ['same-scope conflict',p=>p.alternatives=[{...p.provenance[0],fact_id:900,value:'999'}]],
])test('balance ratio validator rejects '+name,()=>{const value=fixture();mutate(first(value));assert.equal(helper.balanceSheetRatios(value,company.cik),null);});
test('one immutable source ID cannot change between the two ratio cards',()=>{
 const value=fixture();value.cash_and_equivalents_to_total_liabilities.provenance[1].value='101';
 value.cash_and_equivalents_to_total_liabilities.inputs[1].value='101';
 assert.equal(helper.balanceSheetRatios(value,company.cik),null);
});
test('unavailable carries a reason and formula without invented operands; legacy absence stays unverified',()=>{
 const value=fixture();Object.assign(first(value),{status:'unavailable',value:null,reason:'No admitted USD assets at this date.',provenance:[],inputs:[]});
 assert.equal(helper.balanceSheetRatios(value,company.cik),value);
 assert.equal(helper.balanceSheetRatios(undefined,company.cik),null);
 first(value).reason='';assert.equal(helper.balanceSheetRatios(value,company.cik),null);
});

async function mount(ctx,{issuer=company,pin=0}={}){
 const requests=[],changed=[];
 ctx.mock.method(globalThis,'fetch',(input,init={})=>{
  const url=new URL(input,'http://finlens.test');assert.equal(url.origin,'http://finlens.test');assert(url.pathname.startsWith('/api/finlens/'));
  let resolve;const promise=new Promise(done=>resolve=done);requests.push({path:url.pathname.slice('/api/finlens'.length),params:url.searchParams,init,resolve});return promise;
 });
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const change=()=>changed.push(true);
 async function render(nextIssuer=issuer,nextPin=pin){issuer=nextIssuer;pin=nextPin;await act(async()=>root.render(React.createElement(Publication.Provider,{value:{version:pin,changed:change}},React.createElement(FinancialResearch,{company:issuer}))));}
 function request(ticker=issuer.ticker,kind='quarter'){const row=requests.findLast(r=>!r.released&&r.path===`/companies/${ticker}/financials/summary`&&r.params.get('period')===kind);assert(row);return row;}
 function summary(next=issuer,kind='quarter'){
  const period={kind,start:'2025-01-01',end:kind==='annual'?'2025-12-31':'2025-03-31',fiscal_year:2025,fiscal_period:kind==='annual'?'FY':'Q1',fiscal_label_basis:'synthetic'};
  return {ticker:next.ticker,company_cik:next.cik,company_name:next.name,requested_period:kind,period,metrics:{},selection_policy:'Synthetic admitted data',balance_sheet_ratios:fixture(next)};
 }
 async function release(row,payload,version=row.init.headers['X-FinLens-Data-Version']){row.released=true;await act(async()=>row.resolve(new Response(JSON.stringify(payload),{status:200,headers:{'Content-Type':'application/json','X-FinLens-Data-Version':String(version)}})));}
 async function period(kind){await act(async()=>{const select=host.querySelector('select');select.value=kind;select.dispatchEvent(new Event('change',{bubbles:true}));});}
 await render();ctx.after(async()=>{await act(async()=>root.unmount());host.remove();});
 return {host,requests,changed,render,request,summary,release,period,ratios:()=>host.querySelector('.balance-sheet-ratios')};
}
for(const pin of [0,7])test(`mounted ratios reuse one pinned summary at publication ${pin} with accessible evidence and explicit meaning`,async ctx=>{
 const app=await mount(ctx,{pin});const pending=app.request();assert.equal(pending.init.headers['X-FinLens-Data-Version'],String(pin));
 await app.release(pending,app.summary());const region=app.ratios();assert(region);assert.match(region.textContent,/33.33%/);assert.match(region.textContent,/0%/);
 assert.match(region.textContent,/Dec 31, 2025/);assert.match(region.textContent,/independent of the income reporting interval/);
 assert.match(region.textContent,/Total liabilities includes more than debt/);assert.match(region.textContent,/not current liabilities/);
 const count=app.requests.length;await act(async()=>region.querySelector('summary').click());region.querySelector('summary').focus();assert.equal(document.activeElement,region.querySelector('summary'));
 await act(async()=>region.querySelector('.provenance summary').click());assert.match(region.textContent,/total_liabilities \/ total_assets/);
 assert.equal(region.querySelectorAll('a[href^="https://www.sec.gov/Archives/"]').length,4);
 assert.equal(app.requests.length,count);assert.equal(app.requests.filter(r=>r.path.endsWith('/financials/summary')).length,1);
 assert.equal(app.requests.filter(r=>/ratios|context|research-answer|\/answer/.test(r.path)).length,0);
});
test('mounted company switch hides completed ratios and ignores an aborted earlier company response',async ctx=>{
 const app=await mount(ctx);await app.release(app.request(),app.summary());assert(app.ratios());
 await app.period('annual');const old=app.request(company.ticker,'annual');assert.equal(app.ratios(),null);
 await app.render(other,0);assert(old.init.signal.aborted);await app.release(old,app.summary(company,'annual'));assert.equal(app.ratios(),null);
 await app.release(app.request(other.ticker,'annual'),app.summary(other,'annual'));assert(app.ratios());
 assert([...app.ratios().querySelectorAll('a')].every(a=>a.href.includes('/data/2/')));
});
test('mounted publication changes discard ignored-abort ratios; stale response headers cannot publish values',async ctx=>{
 const app=await mount(ctx);const old=app.request();await app.render(company,7);assert(old.init.signal.aborted);
 await app.release(old,app.summary(),0);assert.equal(app.ratios(),null);
 await app.release(app.request(),app.summary(),8);assert.equal(app.ratios(),null);assert.equal(app.changed.length,1);
});
test('mounted period edits synchronously remove ratios until the new scoped summary settles',async ctx=>{
 const app=await mount(ctx);await app.release(app.request(),app.summary());assert(app.ratios());
 await app.period('annual');assert.equal(app.ratios(),null);
 await app.release(app.request(company.ticker,'annual'),app.summary(company,'annual'));assert(app.ratios());
});
test('malformed ratio lineage refuses only that block without displaying unverified numbers',async ctx=>{
 const app=await mount(ctx);const value=app.summary();first(value.balance_sheet_ratios).inputs=[];
 await app.release(app.request(),value);assert.match(app.ratios().textContent,/could not be verified/);assert.equal(app.ratios().querySelector('.metric-value'),null);
});
test('mounted balance-only inventory displays proportions without a revenue reporting anchor',async ctx=>{
 const app=await mount(ctx);const value=app.summary();value.period=null;
 await app.release(app.request(),value);assert.match(app.ratios().textContent,/33.33%/);
 assert.match(app.ratios().textContent,/Dec 31, 2025/);
});

test('actual Python summary serialization accepts available and unavailable ratio payloads unchanged',()=>{
 for(const kind of ['available','unavailable']){
  const value=canonical[kind];assert.equal(first(value.balance_sheet_ratios).status,kind);
  assert.equal(helper.balanceSheetRatios(value.balance_sheet_ratios,company.cik),value.balance_sheet_ratios);
 }
});

function addAlternative(p){
 const alternative={...p.provenance[1],fact_id:900,value:'250',filed:'2026-01-15',accession_number:'0000000001-26-000002',
  sec_url:'https://www.sec.gov/Archives/edgar/data/1/000000000126000002/report.htm'};
 p.alternatives=[alternative];return alternative;
}
for(const [name,kind,mutate] of [
 ['available point revenue_basis','available',p=>p.revenue_basis={}],
 ['unavailable point revenue_basis','unavailable',p=>p.revenue_basis={}],
 ['numerator revenue_basis','available',p=>p.inputs[0].revenue_basis={}],
 ['denominator revenue_basis','available',p=>p.inputs[1].revenue_basis={}],
 ['selected source_fiscal_year','available',p=>p.provenance[1].source_fiscal_year={}],
 ['selected source_fiscal_period','available',p=>p.provenance[1].source_fiscal_period={}],
 ['alternative source_fiscal_year','available',p=>addAlternative(p).source_fiscal_year={}],
 ['alternative source_fiscal_period','available',p=>addAlternative(p).source_fiscal_period={}],
])test(`Python payload with object ${name} renders an unverified block without a React exception`,async ctx=>{
 const value=structuredClone(canonical[kind]);mutate(first(value.balance_sheet_ratios));
 assert.equal(helper.balanceSheetRatios(value.balance_sheet_ratios,company.cik),null);
 const app=await mount(ctx);await assert.doesNotReject(()=>app.release(app.request(),value));
 assert.match(app.ratios().textContent,/could not be verified/);assert.equal(app.ratios().querySelector('.metric-value'),null);
});

for(const kind of ['available','unavailable'])for(const mode of ['omitted','null','typed'])
 test(`Python ${kind} payload preserves ${mode} optional display metadata`,async ctx=>{
  const value=structuredClone(canonical[kind]);
  for(const p of Object.values(value.balance_sheet_ratios)){
   const set=(record,key,typed)=>{if(mode==='omitted')delete record[key];else record[key]=mode==='null'?null:typed;};
   set(p,'revenue_basis','as_reported');
   for(const input of p.inputs)set(input,'revenue_basis','as_reported');
   for(const source of [...p.provenance,...p.alternatives]){set(source,'source_fiscal_year',2025);set(source,'source_fiscal_period','FY');}
  }
  assert.equal(helper.balanceSheetRatios(value.balance_sheet_ratios,company.cik),value.balance_sheet_ratios);
  const app=await mount(ctx);await assert.doesNotReject(()=>app.release(app.request(),value));
  assert.doesNotMatch(app.ratios().textContent,/could not be verified/);assert(app.ratios().querySelector('.metric-value'));
 });

function operand(p,index,value){p.inputs[index].value=value;p.provenance[index].value=value;}
for(const value of ['-1e-400','-.1e-400','-0.00001e-400']){
 test(`exact negative result ${value} is rejected despite Number underflow`,()=>{
  assert(Object.is(Number(value),-0));const points=structuredClone(canonical.available.balance_sheet_ratios);
  first(points).value=value;assert.equal(helper.balanceSheetRatios(points,company.cik),null);
 });
 test(`exact negative numerator ${value} is rejected with matching source lineage`,()=>{
  const points=structuredClone(canonical.available.balance_sheet_ratios);operand(points.cash_and_equivalents_to_total_liabilities,0,value);
  assert.equal(helper.balanceSheetRatios(points,company.cik),null);
 });
}
for(const value of ['0','-0e-400','-1e-400'])test(`denominator ${value} is not strictly positive`,()=>{
 const points=structuredClone(canonical.available.balance_sheet_ratios);operand(first(points),1,value);
 assert.equal(helper.balanceSheetRatios(points,company.cik),null);
});
for(const value of ['0e-400','-0e-400','+0.000e+400'])test(`exact numerator/result zero ${value} stays valid`,()=>{
 const points=structuredClone(canonical.available.balance_sheet_ratios),p=points.cash_and_equivalents_to_total_liabilities;
 operand(p,0,value);p.value=value;assert.equal(helper.balanceSheetRatios(points,company.cik),points);
});
for(const index of [0,1])test(`tiny positive operand ${index} is not mistaken for zero`,()=>{
 const points=structuredClone(canonical.available.balance_sheet_ratios);
 const p=index===0?points.cash_and_equivalents_to_total_liabilities:first(points);operand(p,index,'1e-400');
 assert.equal(helper.balanceSheetRatios(points,company.cik),points);
});
