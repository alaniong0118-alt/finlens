"""Derive bounded candidate tests from the repository's mounted harness."""
from pathlib import Path
import os
root=Path(__file__).resolve().parents[1]
primary=Path(os.environ.get("FINLENS_TEST_FRONTEND",root))
source=(primary/'tests/research-interactions.test.mjs').read_text(encoding='utf-8')
source=source.replace("from 'typescript'", "from '"+primary.as_uri()+"/node_modules/typescript/lib/typescript.js'")
source=source.replace("from 'react'", "from '"+primary.as_uri()+"/node_modules/react/index.js'")
source=source.replace("from 'jsdom'", "from '"+primary.as_uri()+"/node_modules/jsdom/lib/api.js'")
source=source.replace("from './mounted-data-ledger.mjs'", "from '"+primary.as_uri()+"/tests/mounted-data-ledger.mjs'")
source=source.replace("import('react-dom/client')", "import('"+primary.as_uri()+"/node_modules/react-dom/client.js')")
source=source.replace("import.meta.url", repr((primary/"tests/research-interactions.test.mjs").as_uri()))
needle="const output = ts.transpileModule(readFileSync(path, 'utf8'),"
replacement="const output = ts.transpileModule(readFileSync(path.replaceAll('\\\\', '/').endsWith('/components/research-answer.tsx') ? "+repr(str(root/'components/research-answer.tsx'))+" : path.replaceAll('\\\\', '/').endsWith('/components/filing-research.tsx') ? "+repr(str(root/'components/filing-research.tsx'))+" : path, 'utf8'),"
assert source.count(needle)==1
source=source.replace(needle,replacement)
source += r"""
function candidateMulti(ticker, query) {
  const available = historicalAnswer(ticker, query);
  const cik = companies.find(company => company.ticker === ticker).cik;
  const acc = `${cik}-25-000001`;
  available.observation.provenance[0] = {...available.observation.provenance[0], canonical_metric:'revenue', accession_number:acc,
    sec_url:`https://www.sec.gov/Archives/edgar/data/${Number(cik)}/${acc.replaceAll('-', '')}/${acc}-index.html`};
  const unavailable = {...historicalAnswer(ticker, query), metric:'net_income', metric_label:'Net income', status:'unavailable', formatted_value:null,
    answer_text:'Synthetic net income unavailable.', observation:{...historicalAnswer(ticker, query).observation, metric:'net_income', status:'unavailable', value:null, provenance:[], reason:'Synthetic source missing.'}};
  return {...available, company_cik:companies.find(company => company.ticker === ticker).cik, answer_kind:'multi_metric', window_status:'unverified', observation:null, formatted_value:null, metric:null, metric_label:null, metrics:[available, unavailable]};
}
test('CANDIDATE mixed metric rendering survives evidence failure', async ctx => {
  const app=await mount(ctx); await app.completeCompany('AAPL','1000000000');
  const query='revenue and net income for FY2024'; const evidence=await app.search('AAPL',query,true);
  await app.release(app.request(companyPath('AAPL','research-answer')),candidateMulti('AAPL',query));
  let answer=app.host.querySelector('.direct-answer');
  assert.match(answer.textContent,/Revenue/); assert.match(answer.textContent,/Net income/);
  assert.match(answer.textContent,/100000000000 USD/); assert.match(answer.textContent,/Unavailable/);
  assert.match(answer.textContent,/Synthetic source missing/);
  assert.equal(answer.querySelectorAll('details.provenance').length,2);
  const source=answer.querySelector('details.provenance'); await act(async()=>source.querySelector('summary').click());
  assert.match(source.textContent,/25-000001/);
  await app.release(evidence,{detail:'Synthetic evidence failure'},500);
  answer=app.host.querySelector('.direct-answer');assert.match(answer.textContent,/Net income/);assert.match(app.host.textContent,/Synthetic evidence failure/);
});
test('CANDIDATE company switching aborts and discards late multi response', async ctx => {
  const app=await mount(ctx); await app.completeCompany('AAPL','1000000000');
  const query='revenue and net income for FY2024'; const evidence=await app.search('AAPL',query,true);
  await app.release(evidence,context('AAPL',query)); const old=app.request(companyPath('AAPL','research-answer'));
  await app.change(app.host.querySelector('#company'),'JPM'); assert.equal(old.init.signal.aborted,true);
  await app.release(old,candidateMulti('AAPL',query)); assert.ok(!app.host.querySelector('.direct-answer'));
  await app.completeCompany('JPM','2000000000'); const next=await app.search('JPM',query,true);
  await app.release(app.request(companyPath('JPM','research-answer')),candidateMulti('JPM',query)); await app.release(next,context('JPM',query));
  assert.match(app.host.querySelector('.direct-answer').textContent,/JPM revenue test concept/); assert.doesNotMatch(app.host.querySelector('.direct-answer').textContent,/AAPL/);
  await app.change(app.host.querySelector('#company'),'AAPL'); assert.ok(!app.host.querySelector('.direct-answer'));
});
"""
(root/'tests/mounted-candidate.generated.mjs').write_text(source,encoding='utf-8',newline='')
