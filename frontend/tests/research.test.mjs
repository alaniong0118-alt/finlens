import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AI_UNAVAILABLE, createRequestScope, evidencePassages, epsWarning, formatMetric, historyChartRows, parseTheme, periodLabel, persistTheme, resolveTheme } from '../lib/research.ts';
import { describeApiError, getAnswer, getCapabilities, getFinancialSummary, getFilingContext, getMetricHistory } from '../lib/finlens-api.ts';

// Compile the actual TSX components with the existing TypeScript dependency.
// No snapshot files, browser DOM shim or new testing framework.
const require = createRequire(import.meta.url);
const cache = new Map();
function component(path) {
  if (cache.has(path)) return cache.get(path);
  const exports = {};
  const output = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const localRequire = (name) => {
    if (!name.startsWith('@/')) return require(name);
    const base = fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url));
    return component(['.tsx', '.ts'].map(extension => base + extension).find(existsSync));
  };
  new Function('require', 'exports', output)(localRequire, exports);
  cache.set(path, exports);
  return exports;
}
const finance = component(fileURLToPath(new URL('../components/financial-research.tsx', import.meta.url)));
const filing = component(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url)));
const overview = component(fileURLToPath(new URL('../components/company-overview.tsx', import.meta.url)));
const period = {kind:'quarter',start:'2025-01-01',end:'2025-03-31',fiscal_year:2025,fiscal_period:'Q1',fiscal_label_basis:'test fixture'};
const source = {fact_id:1, original_concept:'Revenues',value:'1000000000',unit:'USD',period_start:period.start,period_end:period.end,form:'10-Q',filed:'2025-05-01',accession_number:'0000000001-25-000001',sec_url:'https://www.sec.gov/Archives/fixture',source_fiscal_year:2025,source_fiscal_period:'Q1'};
const point = {metric:'revenue',unit:'USD',status:'available',value:'1000000000',reason:null,period,formula:null,provenance:[source],alternatives:[],inputs:[],revenue_basis:'total_revenue'};
const context = {ticker:'TEST',query:'revenue',evidence_status:'sufficient',accession_number:source.accession_number,context:'[SOURCE source_1]\nchunk_id: chunk_0001\ntext: |-\n  Actual fixture excerpt <script> is untrusted text.\n[END SOURCE source_1]',citations:[{citation_id:'source_1',chunk_id:'chunk_0001',form:'10-Q',filed:source.filed,sec_url:source.sec_url,accession_number:source.accession_number,start_char:0,end_char:60,filename:'fixture.htm',evidence_reason:'lexical_support'}]};

test('company overview renders stored identity/readiness and does not fabricate metadata',()=>{
 const company={id:1,ticker:'TEST',name:'Fixture Issuer',exchange:'NYSE',has_indexed_filing:true,indexed_filing_count:1};
 const html=renderToStaticMarkup(React.createElement(overview.default,{companies:[company],company,ticker:'TEST',loading:false,error:null,onChange:()=>{}}));
 assert.match(html,/Fixture Issuer/); assert.match(html,/Ready/);assert.match(html,/1 indexed filing/);
 assert.doesNotMatch(html,/market cap|stock price|sector/i);
 const unavailable=renderToStaticMarkup(React.createElement(overview.default,{companies:[{...company,has_indexed_filing:false}],company:{...company,has_indexed_filing:false,indexed_filing_count:0},ticker:'TEST',loading:false,error:null,onChange:()=>{}}));
 assert.match(unavailable,/Not indexed/);assert.match(unavailable,/0 indexed filings/);
});
test('metric card renders server value, period, provenance and economic basis',()=>{
 const html=renderToStaticMarkup(React.createElement(finance.MetricCard,{point}));
 for(const text of ['$1B','Revenues','0000000001-25-000001','total revenue basis','Sources and details','Jan 1, 2025']) assert.ok(html.includes(text),text);
});
test('unavailable and not-applicable metrics remain distinct, never substitute zero',()=>{
 for(const [status,label] of [['unavailable','Unavailable'],['not_applicable','Not applicable']]) {
  const html=renderToStaticMarkup(React.createElement(finance.MetricCard,{point:{...point,status,value:null,provenance:[]}}));
  assert.ok(html.includes(label));assert.doesNotMatch(html,/\$0/);
 }
 assert.equal(formatMetric({...point,value:'0'}),'$0');
 assert.equal(formatMetric({...point,unit:'ratio',value:'0.25'}),'25%');
 assert.equal(formatMetric({...point,unit:'USD/share',value:'2.0200'}),'$2.02');
});
test('history preserves missing/signs and refuses plotting incompatible periods',()=>{
 const history={requested_period:'quarter',history:[point,{...point,status:'unavailable',value:null},{...point,value:'-10'},{...point,period:{...period,kind:'annual'}}]};
 assert.deepEqual(historyChartRows(history).map(row=>row.value),[1e9,null,-10,null]);
 assert.equal(historyChartRows(history)[0].point,point);
 assert.match(periodLabel({...period,fiscal_year:null}),/Direct quarter/);assert.doesNotMatch(periodLabel({...period,fiscal_year:null}),/FYnull|FY2025/);
});
test('EPS warning exposes as-filed comparability uncertainty',()=>{
 assert.match(epsWarning({comparability:{value_basis:'reported_as_filed',status:'unverified'}}),/Reported as filed.*comparability unverified/);
 assert.equal(epsWarning({}),null);
});
test('evidence passages follow source IDs and render filing text safely',()=>{
 const passages=evidencePassages(context);assert.equal(passages.length,1);assert.equal(passages[0].rank,1);
 const html=renderToStaticMarkup(React.createElement(filing.EvidenceResults,{result:context}));
 assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);assert.match(html,/Open official SEC source/);
 assert.equal(evidencePassages({...context,citations:[{...context.citations[0],citation_id:'source_2'}]}).length,0);
 const insufficient=renderToStaticMarkup(React.createElement(filing.EvidenceResults,{result:{...context,context:'',citations:[],evidence_status:'insufficient'}}));
 assert.match(insufficient,/Insufficient evidence in this filing/);
});
test('optional AI unavailable rendering leaves evidence as a separate result',()=>{
 const html=renderToStaticMarkup(React.createElement(filing.AIAnalysis,{result:context,configured:false}));
 assert.match(html,/not configured/);assert.match(html,/disabled/);assert.doesNotMatch(html,/OPENAI_API_KEY|429/);
 assert.match(AI_UNAVAILABLE,/SEC evidence.*still available/);
 assert.equal(evidencePassages(context)[0].text,'Actual fixture excerpt <script> is untrusted text.');
});

test('answer API sanitizes provider failure without mutating its caller fixture',async ctx=>{
 const before=JSON.stringify(context);
 ctx.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify({detail:'Provider quota fixture: internal details'}),{status:502,headers:{'Content-Type':'application/json','X-FinLens-Error-Code':'UPSTREAM_FAILURE'}}));
 await assert.rejects(()=>getAnswer('TEST',source.accession_number,'revenue'),error=>{
  assert.match(describeApiError(error),/SEC evidence remains available/);
  assert.doesNotMatch(describeApiError(error),/quota|internal details/);return true;
 });
 assert.equal(JSON.stringify(context),before);
 assert.equal(evidencePassages(context).length,1);
});

test('long passages have a compact preview and a complete accessible disclosure',()=>{
 const text='Stored SEC excerpt. '.repeat(70);
 const result={...context,context:`[SOURCE source_1]\ntext: |-\n  ${text}\n[END SOURCE source_1]`};
 const html=renderToStaticMarkup(React.createElement(filing.EvidenceResults,{result}));
 assert.match(html,/Read full evidence passage/);assert.ok(html.includes(text.trim()));
});
test('request-scope helper rejects an invalidated request ID',async()=>{
 const scope=createRequestScope();const old=scope.start();let shown=null;
 const late=Promise.resolve(context).then(result=>{if(scope.current(old))shown=result;});
 scope.invalidate();await late;assert.equal(shown,null);
 const next=scope.start();assert.equal(scope.current(next),true);assert.equal(scope.current(old),false);
});
test('theme parsing/system resolution/persistence remain safe when storage is blocked',()=>{
 assert.equal(parseTheme('unexpected'),'system');assert.equal(resolveTheme('system',true),'dark');assert.equal(resolveTheme('light',true),'light');
 const values={};assert.equal(persistTheme('dark',{setItem:(k,v)=>values[k]=v}),'dark');assert.equal(values['finlens-theme'],'dark');
 assert.equal(persistTheme('light',{setItem:()=>{throw Error('blocked');}}),'light');
});
test('Research Mode uses bounded GET requests and carries cancellation, with no answer call',async ctx=>{
 const calls=[];ctx.mock.method(globalThis,'fetch',async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({}),{headers:{'Content-Type':'application/json'}});});
 const signal=new AbortController().signal;
 await getCapabilities(signal);await getFinancialSummary('AAPL','annual',signal);await getMetricHistory('AAPL','free_cash_flow','annual',signal);await getFilingContext('AAPL','filing','revenue & growth',signal);
 assert.equal(calls.length,4);assert.ok(calls.every(call=>call.init.signal===signal&&!call.url.includes('/answer')));
 assert.match(calls[1].url,/financials\/summary\?period=annual/);assert.match(calls[2].url,/limit=12/);assert.match(calls[3].url,/q=revenue\+%26\+growth&limit=5/);
});
