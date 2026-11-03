import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { componentLoader } from './component-loader.mjs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AI_UNAVAILABLE, createRequestScope, evidencePassages, epsWarning, formatMetric, historyChartRows, officialSecUrl, parseTheme, periodLabel, persistTheme, resolveTheme, METRIC_CATALOG, METRIC_GROUPS, METRIC_LABELS, SNAPSHOT_METRICS, guidedQuestion, fiscalQuestionPeriods, guidedFiscalQuestion } from '../lib/research.ts';
import { describeApiError, getAnswer, getCapabilities, getFinancialSummary, getFilingContext, getMetricHistory } from '../lib/finlens-api.ts';

// Compile the actual TSX components with the existing TypeScript dependency.
// No snapshot files, browser DOM shim or new testing framework.
const component = componentLoader(fileURLToPath(new URL('../', import.meta.url)));
const finance = component(fileURLToPath(new URL('../components/financial-research.tsx', import.meta.url)));
const filing = component(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url)));
const overview = component(fileURLToPath(new URL('../components/company-overview.tsx', import.meta.url)));
const period = {kind:'quarter',start:'2025-01-01',end:'2025-03-31',fiscal_year:2025,fiscal_period:'Q1',fiscal_label_basis:'test fixture'};
const source = {fact_id:1, original_concept:'Revenues',value:'1000000000',unit:'USD',period_start:period.start,period_end:period.end,form:'10-Q',filed:'2025-05-01',accession_number:'0000000001-25-000001',sec_url:'https://www.sec.gov/Archives/fixture',source_fiscal_year:2025,source_fiscal_period:'Q1'};
const point = {metric:'revenue',unit:'USD',status:'available',value:'1000000000',reason:null,period,formula:null,provenance:[source],alternatives:[],inputs:[],revenue_basis:'total_revenue'};
const context = {ticker:'TEST',query:'revenue',evidence_status:'sufficient',accession_number:source.accession_number,context:'[SOURCE source_1]\nchunk_id: chunk_0001\ntext: |-\n  Actual fixture excerpt <script> is untrusted text.\n[END SOURCE source_1]',citations:[{citation_id:'source_1',chunk_id:'chunk_0001',form:'10-Q',filed:source.filed,sec_url:source.sec_url,accession_number:source.accession_number,start_char:0,end_char:60,filename:'fixture.htm',evidence_reason:'lexical_support'}]};

test('SEC-LINK-01 returns absolute SEC destinations independent of the document base', () => {
 const cases = [
  ['https:sec.gov/Archives/filing.htm', 'https://sec.gov/Archives/filing.htm'],
  ['https:/www.sec.gov/Archives/filing.htm', 'https://www.sec.gov/Archives/filing.htm'],
  ['https://sec.gov/Archives/filing.htm', 'https://sec.gov/Archives/filing.htm'],
  ['https://www.sec.gov/Archives/filing.htm', 'https://www.sec.gov/Archives/filing.htm'],
  ['https://WWW.SEC.GOV/Archives/filing.htm', 'https://www.sec.gov/Archives/filing.htm'],
 ];
 for (const [supplied, expected] of cases) {
  const actual = officialSecUrl(supplied);
  assert.equal(actual, expected);
  for (const base of ['https://finlens.test/research/company/', 'http://127.0.0.1:3000/research/company/']) {
   assert.equal(new URL(actual, base).href, expected);
  }
 }
});

test('SEC-LINK-01 preserves query and fragment semantics when canonicalizing', () => {
 const expected = 'https://www.sec.gov/Archives/filing.htm?view=inline&doc=a%26b&doc=c+d#section%202';
 for (const supplied of [expected, 'https:/www.sec.gov/Archives/filing.htm?view=inline&doc=a%26b&doc=c+d#section%202']) {
  const actual = officialSecUrl(supplied);
  assert.equal(actual, expected);
  const destination = new URL(actual, 'https://finlens.test/research/');
  assert.equal(destination.href, expected);
  assert.deepEqual([...destination.searchParams], [['view', 'inline'], ['doc', 'a&b'], ['doc', 'c d']]);
  assert.equal(destination.hash, '#section%202');
 }
});

test('SEC-LINK-01 retains HTTPS, exact hostname and credential rejection rules', () => {
 for (const supplied of [
  'https.gov/Archives/filing.htm', 'not a url', '',
  'https://sec.gov.evil.test/filing.htm', 'https://www.sec.gov.evil.test/filing.htm',
  'https://evil.test/sec.gov/filing.htm', 'https://evilsec.gov/filing.htm',
  'javascript:alert(1)', 'http://sec.gov/filing.htm', 'http://www.sec.gov/filing.htm',
  'https://user@sec.gov/filing.htm', 'https://:password@www.sec.gov/filing.htm',
  'https://user:password@www.sec.gov/filing.htm',
 ]) assert.equal(officialSecUrl(supplied), undefined, supplied);
});

test('SEC-LINK-01 financial provenance and filing evidence render canonical anchor destinations', () => {
 for (const [supplied, expected] of [
  ['https:sec.gov/Archives/filing.htm', 'https://sec.gov/Archives/filing.htm'],
  ['https:/www.sec.gov/Archives/filing.htm', 'https://www.sec.gov/Archives/filing.htm'],
 ]) {
  const provenance = { ...source, sec_url: supplied };
  const metric = { ...point, provenance: [provenance], alternatives: [{ ...provenance, fact_id: 2 }] };
  const evidence = { ...context, citations: [{ ...context.citations[0], sec_url: supplied }] };
  const before = JSON.stringify({ metric, evidence });
  const financialHtml = renderToStaticMarkup(React.createElement(finance.MetricProvenance, { point: metric }));
  const evidenceHtml = renderToStaticMarkup(React.createElement(filing.EvidenceResults, { result: evidence }));
  for (const [html, count] of [[financialHtml, 2], [evidenceHtml, 1]]) {
   const destinations = [...html.matchAll(/<a\b[^>]*\bhref="([^"]*)"/g)].map(match => match[1]);
   assert.deepEqual(destinations, Array(count).fill(expected));
   for (const destination of destinations) assert.equal(new URL(destination, 'https://finlens.test/research/').href, expected);
  }
  assert.match(financialHtml, /1000000000 USD/);
  assert.match(financialHtml, /Revenues/);
  assert.ok(financialHtml.includes(source.accession_number));
  assert.match(evidenceHtml, /Actual fixture excerpt &lt;script&gt; is untrusted text\./);
  assert.ok(evidenceHtml.includes(source.accession_number));
  assert.equal(JSON.stringify({ metric, evidence }), before);
 }
});

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

test('guided fiscal preparation rejects invalid years and unsupported combinations without changing latest templates', () => {
 for (const year of ['', '1899', '2100', '024', '20245', '2024.0', ' 2024', '2024 ', '20e2', '２０２４', 2024, null, undefined]) {
  assert.equal(guidedFiscalQuestion('revenue', 'annual', year), null, String(year));
  assert.equal(guidedFiscalQuestion('revenue', 'q1', '2024', year === undefined ? '' : year), null, String(year));
 }
 for (const [first, last] of [['2024','2024'], ['2025','2024']]) assert.equal(guidedFiscalQuestion('revenue','annual',first,last),null);
 for (const metric of ['cash_and_equivalents','total_assets','total_liabilities']) {
  assert.deepEqual(fiscalQuestionPeriods(metric).map(item=>item.id),['annual']);
  assert.deepEqual(fiscalQuestionPeriods(metric,true),[]);
  assert.equal(guidedFiscalQuestion(metric,'q1','2024'),null);
  assert.equal(guidedFiscalQuestion(metric,'annual','2024','2025'),null);
 }
 assert.equal(METRIC_CATALOG.filter(item=>fiscalQuestionPeriods(item.id,true).length).length,11);
 assert.equal(guidedFiscalQuestion('revenue_growth_yoy','annual','2024','2025'),null);
 for (const period of ['quarter','instant','half_year','nine_months','q0','q5','Q1',null]) assert.equal(guidedFiscalQuestion('revenue',period,'2024'),null);
 assert.equal(guidedFiscalQuestion('unsupported','annual','2024'),null);
 assert.equal(guidedFiscalQuestion('operating_margin','annual','2024','2025'),'Compare FY2024 and FY2025 operating margin.');
 assert.equal(guidedFiscalQuestion('diluted_eps','q2','2024','2025'),'Compare Q2 FY2024 and Q2 FY2025 diluted eps.');
 assert.equal(guidedFiscalQuestion('revenue','annual','1900'),'What was FY1900 revenue?');
 assert.equal(guidedFiscalQuestion('revenue','annual','2099'),'What was FY2099 revenue?');
});

test('FD-01 every advertised guided question resolves with actual backend metric, operation and period semantics offline', () => {
 const cases=METRIC_CATALOG.flatMap(entry=>entry.questionScopes.map(scope=>({metric:entry.id,scope,question:guidedQuestion(entry.id,scope)})));
 assert.equal(cases.length,39);
 const fiscal=METRIC_CATALOG.flatMap(entry=>fiscalQuestionPeriods(entry.id).map(period=>({
  metric:entry.id,period:period.id,question:guidedFiscalQuestion(entry.id,period.id,'2024'),year:2024,
 }))).concat(METRIC_CATALOG.flatMap(entry=>fiscalQuestionPeriods(entry.id,true).map(period=>({
  metric:entry.id,period:period.id,question:guidedFiscalQuestion(entry.id,period.id,'2024','2025'),year:2024,later:2025,
 }))));
 assert.equal(fiscal.length,118); // 63 historical + 55 comparisons, alongside the original 39.
 fiscal.push(...['1900','2099'].map(year=>({metric:'revenue',period:'annual',year:Number(year),question:guidedFiscalQuestion('revenue','annual',year),missing:true})),
  {metric:'revenue',period:'q2',year:2025,question:guidedFiscalQuestion('revenue','q2','2025'),missing:true},
  {metric:'revenue',period:'annual',year:2024,later:2025,question:guidedFiscalQuestion('revenue','annual','2024','2025'),missing:true},
  {metric:'revenue',period:'annual',year:1900,later:2099,question:guidedFiscalQuestion('revenue','annual','1900','2099'),missing:true},
  {metric:'revenue',period:'q3',year:2023,later:2025,question:guidedFiscalQuestion('revenue','q3','2023','2025')});
 const rejected=['Compare FY2024 and FY2025 revenue growth yoy.', 'Compare Q1 FY2024 and Q2 FY2025 revenue.',
  'Compare FY2024 and Q1 FY2025 revenue.', 'FY2024 to FY2025 revenue CAGR', 'FY1899 revenue', 'FY2100 revenue'];
 const backend=fileURLToPath(new URL('../../backend/',import.meta.url));
 const python=['.venv/Scripts/python.exe','.venv/bin/python'].map(path=>fileURLToPath(new URL(`../../backend/${path}`,import.meta.url))).find(existsSync)??'python';
 const run=spawnSync(python,['-B','-c',`
import json, sys
from pathlib import Path

def forbidden(*args, **kwargs):
    raise AssertionError('Database, network and private configuration access forbidden')
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)) and Path(args[0]).name.lower() == '.env':
        forbidden()
    if event in ('socket.connect', 'socket.getaddrinfo'):
        forbidden()
    if event == 'import' and args[0] in ('app.database', 'app.config'):
        forbidden()
sys.addaudithook(guard)
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
with patch('sqlalchemy.engine.Engine.connect', side_effect=AssertionError('Database access forbidden')), \\
     patch('socket.socket.connect', side_effect=AssertionError('Network access forbidden')), \\
     patch('socket.create_connection', side_effect=AssertionError('Network access forbidden')):
    from app.models import Company, FinancialFact
    from app.financial_metric_registry import METRICS
    from app.research_answer_service import answer_research_question, recognize_operation
    requests = json.load(sys.stdin)
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
               for item in requests['latest']]
    latest_operations = [recognize_operation(item['question'],company,[company])[0].operation for item in requests['latest']]
    facts = []
    for metric, definition in METRICS.items():
        if definition.kind == 'derived': continue
        for year in (2023, 2024, 2025):
            periods = [(date(year,1,1), date(year,12,31), 'FY')]
            if definition.kind != 'instant':
                periods += [(date(year,month,1), date(year,month+2,31 if month in (1,10) else 30), f'Q{q}')
                            for q,month in enumerate((1,4,7,10),1)]
            for start,end,label in periods:
                concept = 'Revenues' if metric == 'revenue' else definition.concepts[0]
                amount = {'revenue':'100','gross_profit':'40','operating_income':'20' if year<2025 else '30',
                          'net_income':'10','diluted_eps':'1.2345' if year<2025 else '2',
                          'operating_cash_flow':'30','capital_expenditures':'5'}.get(metric,'200')
                facts.append(FinancialFact(id=len(facts)+1,company_cik=company.cik,metric=concept,
                    value=Decimal(amount),unit=definition.source_unit,period_start=None if definition.kind=='instant' else start,
                    period_end=end,period_type='fixture',fiscal_year=year,fiscal_period=label,frame=None,
                    form='10-K' if label=='FY' else '10-Q',filed=end+timedelta(days=31),
                    accession_number=f'0000000001-{year%100:02d}-{0 if label=="FY" else int(label[1:]):06d}',source=f'SEC Company Facts API: {concept}',created_at=datetime(2026,1,1)))
    complete_facts = facts
    historical = []
    for item in requests['fiscal']:
        facts = [] if item.get('missing') else complete_facts
        operation, rejection = recognize_operation(item['question'],company,[company])
        historical.append({'operation':operation.operation,'metric':operation.metric,'status':operation.status,
            'periods':[p.model_dump(mode='json') for p in operation.periods], 'rejection':rejection,
            'answer':answer_research_question(DetachedSession(),'TEST',item['question']).model_dump(mode='json')})
    print(json.dumps({'registry':list(METRICS),'answers':answers,'latest_operations':latest_operations,'fiscal':historical,
        'rejected':[answer_research_question(DetachedSession(),'TEST',q).model_dump(mode='json') for q in requests['rejected']]}))
`],{cwd:backend,input:JSON.stringify({latest:cases,fiscal,rejected}),encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},timeout:30000,maxBuffer:8*1024*1024});
 assert.equal(run.status,0,run.stderr || run.error?.message);
 const result=JSON.parse(run.stdout);
 assert.deepEqual(result.registry.sort(),METRIC_CATALOG.map(entry=>entry.id).sort());
 result.answers.forEach((answer,index)=>{
  const entry=cases[index]; const instant=METRIC_CATALOG.find(item=>item.id===entry.metric).group==='balance';
  assert.equal(answer.matched,true,entry.question); assert.equal(answer.status,'available',entry.question);
  assert.equal(answer.metric,entry.metric); assert.equal(answer.period_intent,entry.scope);
  assert.equal(result.latest_operations[index],'latest_value');
  assert.equal(answer.question,entry.question); assert.equal(answer.ticker,'TEST');
  const kind=instant?'instant':entry.scope==='latest_available'?'half_year':entry.scope;
  assert.equal(answer.observation.period.kind,kind,entry.question);
  const end=entry.scope==='quarter'?'2025-03-31':entry.scope==='annual'?'2024-12-31':'2025-06-30';
  assert.equal(answer.observation.period.end,end);
  assert.ok(answer.observation.provenance.every(item=>item.company_cik==='0000000001'));
  if(instant){assert.equal(answer.observation.period.start,null);assert.match(answer.answer_text,/as of June 30, 2025/);assert.doesNotMatch(answer.answer_text,/quarter ended|year ended/);}
  if(kind==='half_year')assert.match(answer.answer_text,/six-month YTD period/);
 });
 result.fiscal.forEach(({operation,metric,status,periods,rejection,answer},index)=>{
  const entry=fiscal[index], quarter=entry.period==='annual'?null:Number(entry.period.slice(1));
  assert.equal(rejection,null,entry.question); assert.equal(status,'supported',entry.question);
  assert.equal(metric,entry.metric); assert.equal(answer.metric,entry.metric); assert.equal(answer.matched,true);
  assert.equal(operation,!entry.later?'historical_value':entry.metric.endsWith('_margin')?'percentage_point_difference':entry.metric==='revenue'?(entry.later-entry.year>1?'cumulative_period_growth':'revenue_level_comparison'):'metric_level_comparison');
  assert.deepEqual(periods,[{fiscal_year:entry.year,quarter},...(entry.later?[{fiscal_year:entry.later,quarter}]:[])]);
  assert.equal(answer.status,entry.missing?'unavailable':'available',entry.question);
  assert.equal(answer.answer_kind,entry.later?'period_comparison':'historical_metric');
  assert.equal(answer.period_intent,quarter?'quarter':'annual');
  assert.deepEqual(answer.requested_period,periods[0]);
  if(entry.missing){assert.ok(answer.explanation);assert.equal(answer.formatted_value,null);return;}
  const points=entry.later?[answer.comparison.earlier,answer.comparison.later]:[answer.observation];
  points.forEach((point,i)=>{
   const instant=METRIC_CATALOG.find(item=>item.id===entry.metric).group==='balance', year=i?entry.later:entry.year;
   assert.equal(point.metric,entry.metric);
   if(!instant)assert.equal(point.period.fiscal_year,year,entry.question);
   assert.equal(point.period.end,`${year}-${quarter?[null,'03-31','06-30','09-30','12-31'][quarter]:'12-31'}`);
   assert.equal(point.period.kind,instant?'instant':quarter?'quarter':'annual');
   if(instant)assert.equal(point.period.start,null);
   assert.ok(point.provenance.length);assert.ok(point.provenance.every(source=>source.company_cik==='0000000001'));
   if(quarter)assert.equal(point.period.fiscal_period,`Q${quarter}`);
  });
  if(entry.metric==='operating_margin'&&entry.later)assert.equal(answer.formatted_absolute_change,'+10.00 percentage points');
  if(entry.metric==='diluted_eps'){
   assert.equal(answer.comparability.value_basis,'reported_as_filed');
   if(entry.later){assert.equal(answer.comparison.percentage_status,'not_applicable');assert.match(answer.comparison.percentage_reason,/as filed.*unverified/);assert.equal(answer.formatted_percentage_change,null);assert.equal(answer.comparison.absolute_change,'0.7655');}
  }
 });
 for(const answer of result.rejected){assert.equal(answer.matched,false,answer.question);assert.equal(answer.status,'not_matched');}
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
