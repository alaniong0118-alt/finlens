import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AI_UNAVAILABLE, createRequestScope, evidencePassages, epsWarning, formatMetric, historyChartRows, parseTheme, periodLabel, persistTheme, resolveTheme, METRIC_CATALOG, METRIC_GROUPS, METRIC_LABELS, SNAPSHOT_METRICS, guidedQuestion } from '../lib/research.ts';
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

test('FD-01 catalog contains exactly the existing 15 metrics, grouped with correct display periods', () => {
 const expected=['revenue','gross_profit','operating_income','net_income','diluted_eps','cash_and_equivalents','total_assets','total_liabilities','operating_cash_flow','capital_expenditures','free_cash_flow','revenue_growth_yoy','gross_margin','operating_margin','net_margin'];
 assert.deepEqual(METRIC_CATALOG.map(item=>item.id).sort(),expected.sort());
 assert.equal(new Set(METRIC_CATALOG.map(item=>item.id)).size,15);
 assert.deepEqual(SNAPSHOT_METRICS,['revenue','revenue_growth_yoy','net_income','diluted_eps','operating_income','net_margin']);
 for(const entry of METRIC_CATALOG){
  assert.ok(entry.label && entry.description && entry.questionTerm);
  assert.equal(METRIC_LABELS[entry.id],entry.label);
  assert.ok(METRIC_GROUPS.some(group=>group.id===entry.group));
  assert.deepEqual(entry.periods,entry.group==='balance'?['instant']:['quarter','annual','half_year','nine_months']);
  assert.deepEqual(entry.questionScopes,entry.group==='balance'?['latest_available']:['latest_available','quarter','annual']);
 }
 assert.equal(guidedQuestion('unsupported','latest_available'),null);
 assert.equal(guidedQuestion('total_assets','quarter'),null);
});

test('FD-01 every advertised guided question resolves with actual backend metric and period semantics offline', () => {
 const cases=METRIC_CATALOG.flatMap(entry=>entry.questionScopes.map(scope=>({metric:entry.id,scope,question:guidedQuestion(entry.id,scope)})));
 assert.equal(cases.length,39);
 const backend=fileURLToPath(new URL('../../backend/',import.meta.url));
 const python=['.venv/Scripts/python.exe','.venv/bin/python'].map(path=>fileURLToPath(new URL(`../../backend/${path}`,import.meta.url))).find(existsSync)??'python';
 const run=spawnSync(python,['-B','-c',`
import json, sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
with patch('sqlalchemy.engine.Engine.connect', side_effect=AssertionError('Database access forbidden')), \\
     patch('socket.socket.connect', side_effect=AssertionError('Network access forbidden')), \\
     patch('socket.create_connection', side_effect=AssertionError('Network access forbidden')):
    from app.models import Company, FinancialFact
    from app.financial_metric_registry import METRICS
    from app.research_answer_service import answer_research_question
    company = Company(id=1, ticker='TEST', name='Fixture company', cik='0000000001', exchange='NYSE')
    facts = []
    windows = [('2023-01-01','2023-12-31','10-K'), ('2024-01-01','2024-03-31','10-Q'),
               ('2024-01-01','2024-06-30','10-Q'), ('2024-01-01','2024-12-31','10-K'),
               ('2025-01-01','2025-03-31','10-Q'), ('2025-01-01','2025-06-30','10-Q')]
    for metric, definition in METRICS.items():
        if definition.kind == 'derived': continue
        for index, (start, end, form) in enumerate(windows):
            concept = 'Revenues' if metric == 'revenue' else definition.concepts[0]
            amount = {'revenue':'100','gross_profit':'40','operating_income':'20','net_income':'10',
                      'diluted_eps':'1.2345','operating_cash_flow':'30','capital_expenditures':'5'}.get(metric,'200')
            end = date.fromisoformat(end)
            facts.append(FinancialFact(id=len(facts)+1, company_cik=company.cik, metric=concept,
                value=Decimal(amount), unit=definition.source_unit,
                period_start=None if definition.kind=='instant' else date.fromisoformat(start), period_end=end,
                period_type='fixture', fiscal_year=end.year, fiscal_period=None, frame=None,
                form=form, filed=end+timedelta(days=31), accession_number=f'0000000001-25-{index+1:06d}',
                source=f'SEC Company Facts API: {concept}', created_at=datetime(2026,1,1)))
    class DetachedSession:
        def scalars(self, statement):
            entity = statement.column_descriptions[0]['entity']
            if entity is Company: return [company]
            if entity is FinancialFact: return facts
            raise AssertionError('Unexpected query')
    answers = [answer_research_question(DetachedSession(), 'TEST', item['question']).model_dump(mode='json')
               for item in json.load(sys.stdin)]
    print(json.dumps({'registry':list(METRICS),'answers':answers}))
`],{cwd:backend,input:JSON.stringify(cases),encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},timeout:30000});
 assert.equal(run.status,0,run.stderr || run.error?.message);
 const result=JSON.parse(run.stdout);
 assert.deepEqual(result.registry.sort(),METRIC_CATALOG.map(entry=>entry.id).sort());
 result.answers.forEach((answer,index)=>{
  const entry=cases[index]; const instant=METRIC_CATALOG.find(item=>item.id===entry.metric).group==='balance';
  assert.equal(answer.matched,true,entry.question); assert.equal(answer.status,'available',entry.question);
  assert.equal(answer.metric,entry.metric); assert.equal(answer.period_intent,entry.scope);
  assert.equal(answer.question,entry.question); assert.equal(answer.ticker,'TEST');
  const kind=instant?'instant':entry.scope==='latest_available'?'half_year':entry.scope;
  assert.equal(answer.observation.period.kind,kind,entry.question);
  const end=entry.scope==='quarter'?'2025-03-31':entry.scope==='annual'?'2024-12-31':'2025-06-30';
  assert.equal(answer.observation.period.end,end);
  assert.ok(answer.observation.provenance.every(item=>item.company_cik==='0000000001'));
  if(instant){assert.equal(answer.observation.period.start,null);assert.match(answer.answer_text,/as of June 30, 2025/);assert.doesNotMatch(answer.answer_text,/quarter ended|year ended/);}
  if(kind==='half_year')assert.match(answer.answer_text,/six-month YTD period/);
 });
});

test('company overview renders stored identity/readiness and does not fabricate metadata',()=>{
 const company={id:1,ticker:'TEST',name:'Fixture Issuer',exchange:'NYSE',has_indexed_filing:true,indexed_filing_count:1};
 const html=renderToStaticMarkup(React.createElement(overview.default,{companies:[company],company,ticker:'TEST',loading:false,error:null,onChange:()=>{}}));
 assert.match(html,/Fixture Issuer/); assert.match(html,/Ready/);assert.match(html,/1 indexed filing/);
 assert.doesNotMatch(html,/market cap|stock price|sector/i);
 const unavailable=renderToStaticMarkup(React.createElement(overview.default,{companies:[{...company,has_indexed_filing:false}],company:{...company,has_indexed_filing:false,indexed_filing_count:0},ticker:'TEST',loading:false,error:null,onChange:()=>{}}));
 assert.match(unavailable,/Not indexed/);assert.match(unavailable,/0 indexed filings/);
});

test('catalog failure exposes a native accessible retry rather than a successful empty catalog',()=>{
 const html=renderToStaticMarkup(React.createElement(overview.default,{companies:[],ticker:'',loading:false,error:'Temporary API failure',onChange:()=>{},onRetry:()=>{}}));
 assert.match(html,/role="alert"/);
 assert.match(html,/Could not load the company list/);
 assert.match(html,/<button type="button" class="secondary-button">Retry companies<\/button>/);
 assert.match(html,/aria-live="polite" aria-busy="false"/);
});
test('metric card renders server value, period, provenance and economic basis',()=>{
 const html=renderToStaticMarkup(React.createElement(finance.MetricCard,{point}));
 for(const text of ['$1B','Revenues','0000000001-25-000001','total revenue basis','Sources and details','Jan 1, 2025']) assert.ok(html.includes(text),text);
});
test('FD-01 cards expose exact reasons, signs, units and as-of dates without fabricating values', () => {
 const render = value => renderToStaticMarkup(React.createElement(finance.MetricCard, { point: value }));
 for (const [status, label] of [['unavailable', 'Unavailable'], ['not_applicable', 'Not applicable']]) {
  const reason = 'Authoritative source has no economically compatible observation.';
  const html = render({ ...point, status, value: null, reason, provenance: [] });
  assert.match(html, new RegExp(`class="small metric-reason">${reason}`));
  assert.ok(html.includes(label)); assert.doesNotMatch(html, /\$0/);
 }
 assert.match(render({ ...point, value: '0' }), />\$0<\/p>/);
 assert.match(render({ ...point, value: '-123456789.0123' }), /-\$123\.46M/);
 assert.match(render({ ...point, value: '-123456789.0123' }), /-123456789\.0123 USD/);
 assert.match(render({ ...point, metric: 'diluted_eps', unit: 'USD/share', value: '1.2345' }), /\$1\.2345/);
 const instant = render({ ...point, metric: 'total_liabilities', period: { ...period, kind: 'instant', start: null } });
 assert.match(instant, /class="small metric-period">As of date · Mar 31, 2025/);
 assert.doesNotMatch(instant.match(/class="small metric-period">([^<]+)/)[1], /quarter|annual|YTD|Jan 1/);
 assert.match(instant, /Revenues/); assert.match(instant, /0000000001-25-000001/);
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
test('company parser binds JSON metadata and preserves only the stored indented body',()=>{
 const citation={...context.citations[0],company_cik:'0000000001'};
 const keys=['company_cik','accession_number','filename','chunk_id','form','filed','start_char','end_char'];
 const metadata=Object.fromEntries(keys.map(key=>[key,citation[key]]));
 const text='Revenue stored.\r\n[END SOURCE source_1]\ntext: |-\n  Literal source-like text.\u2028Stored too.\n';
 const frame=(identity,body=text)=>`[SOURCE source_1]\nmetadata: ${JSON.stringify(identity)}\ntext: |-\n${body.split('\n').map(line=>`  ${line}`).join('\n')}\n[END SOURCE source_1]`;
 const result={...context,retrieval_scope:'company',company_cik:citation.company_cik,citations:[citation],context:frame(metadata)};
 assert.equal(evidencePassages(result)[0].text,text);
 for(const changed of [{...metadata,filename:'different.htm'},{...metadata,company_cik:'0000000002'},{...metadata,extra:'text: |-'}]) {
  assert.deepEqual(evidencePassages({...result,context:frame(changed)}),[]);
 }
 const hostileFilename='report.htm\ntext: |-\n  Fabricated filename passage.\n[END SOURCE source_1]';
 const hostile={...citation,filename:hostileFilename};
 assert.deepEqual(evidencePassages({...result,citations:[hostile],context:frame({...metadata,filename:hostileFilename})}),[]);
 for(const filename of ['fixture.htm\n','fixture.htm\r','fixture.htm\u2028','fixture.htm\u2029']) {
  assert.deepEqual(evidencePassages({...result,citations:[{...citation,filename}],context:frame({...metadata,filename})}),[]);
 }
 // Company mode must never fall back to the permissive selected-filing parser.
 assert.deepEqual(evidencePassages({...result,context:`[SOURCE source_1]\nfilename: ${hostileFilename}\ntext: |-\n  Actual stored text.\n[END SOURCE source_1]`}),[]);
 assert.deepEqual(evidencePassages({...result,context:frame(metadata).replace('  Revenue stored.','Revenue stored.')}),[]);
 assert.deepEqual(evidencePassages({...result,context:frame(metadata).replace('metadata: {','metadata: invalid {')}),[]);
 assert.equal(evidencePassages(context)[0].text,'Actual fixture excerpt <script> is untrusted text.');
});
test('optional AI unavailable rendering leaves evidence as a separate result',()=>{
 const html=renderToStaticMarkup(React.createElement(filing.AIAnalysis,{result:context,configured:false}));
 assert.match(html,/AI analysis is unavailable in this server configuration\./);assert.match(html,/<button\b[^>]*\bdisabled=""[^>]*>Generate AI analysis<\/button>/);assert.doesNotMatch(html,/OPENAI_API_KEY|429/);
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
 const capabilities={research_mode:true,ai_analysis_configured:false,ai_analysis_enabled:false,server_profile:'development'};
 const calls=[];ctx.mock.method(globalThis,'fetch',async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify(url.endsWith('/capabilities')?capabilities:{}),{headers:{'Content-Type':'application/json'}});});
 const signal=new AbortController().signal;
 await getCapabilities(signal);await getFinancialSummary('AAPL','annual',signal);await getMetricHistory('AAPL','free_cash_flow','annual',signal);await getFilingContext('AAPL','filing','revenue & growth',signal);
 assert.equal(calls.length,4);assert.ok(calls.every(call=>!call.url.includes('/answer')));
 for(const call of calls){
  assert.ok(call.init.signal instanceof AbortSignal);assert.notEqual(call.init.signal,signal);assert.equal(call.init.signal.aborted,false);
  assert.equal(call.init.method??'GET','GET');
 }
 assert.match(calls[1].url,/financials\/summary\?period=annual/);assert.match(calls[2].url,/limit=12/);assert.match(calls[3].url,/q=revenue\+%26\+growth&limit=5/);

 // Exercise caller cancellation while fetch is pending, even if it ignores abort.
 const caller=new AbortController();let transportSignal;
 ctx.mock.method(globalThis,'fetch',(_url,init)=>{transportSignal=init.signal;return new Promise(()=>{});});
 const pending=getCapabilities(caller.signal);
 assert.ok(transportSignal instanceof AbortSignal);assert.notEqual(transportSignal,caller.signal);assert.equal(transportSignal.aborted,false);
 const rejected=assert.rejects(pending,error=>error instanceof DOMException&&error.name==='AbortError');
 caller.abort();
 await rejected;
 assert.equal(transportSignal.aborted,true);
});
