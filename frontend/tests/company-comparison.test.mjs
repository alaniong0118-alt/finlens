import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

const require = createRequire(import.meta.url);
let dom, createRoot, Comparison, contract, api;
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent']) {
    Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import('react-dom/client'));
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const exports = {}; cache.set(path, exports);
    const output = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
    } }).outputText;
    const localRequire = name => {
      if (!name.startsWith('@/')) return require(name);
      const base = fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url));
      return load(['.tsx', '.ts'].map(extension => base + extension).find(existsSync));
    };
    new Function('require', 'exports', output)(localRequire, exports);
    return exports;
  }
  Comparison = load(fileURLToPath(new URL('../components/company-comparison.tsx', import.meta.url))).default;
  contract = load(fileURLToPath(new URL('../lib/company-comparison.ts', import.meta.url)));
  api = load(fileURLToPath(new URL('../lib/finlens-api.ts', import.meta.url)));
});
after(() => dom.window.close());

const companies = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map((ticker, i) => ({
  ticker, cik: `000000000${i + 1}`, id: i + 1, name: `${ticker} synthetic issuer`, exchange: 'NYSE',
  has_indexed_filing: false, indexed_filing_count: 0,
}));
const company = ticker => companies.find(c => c.ticker === ticker);
function response(ticker, year = null, options = {}) {
  const period = year === null ? null : { kind: 'annual', start: `${year}-01-01`, end: `${year}-12-31`,
    fiscal_year: year, fiscal_period: 'FY', fiscal_label_basis: 'annual_period_end_year', ...options.period };
  const metrics = {};
  if (year !== null) for (const [i, name] of contract.COMPARISON_METRICS.entries()) {
    const unit = ['revenue_growth_yoy', 'operating_margin', 'net_margin'].includes(name) ? 'ratio' : 'USD';
    const available = ['revenue', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow'].includes(name);
    const value = name === 'revenue' ? '1000000000' : name === 'capital_expenditures' ? '3' : name === 'free_cash_flow' ? '-10' : '-7';
    metrics[name] = { metric: name, unit, status: available ? 'available' : 'unavailable', value: available ? value : null,
      reason: available ? null : 'No compatible inputs or approved denominator.', period, formula: null,
      ...(name === 'revenue' ? { revenue_basis: options.basis ?? 'total_revenue' } : {}),
      alternatives: [], inputs: [], provenance: !available ? [] : [{ fact_id: i+1, company_cik: company(ticker).cik,
        original_concept: `${ticker} ${name}`, value, unit: 'USD', period_start: period.start, period_end: period.end,
        form: '10-K', filed: `${year + 1}-02-01`, accession_number: `${company(ticker).cik}-26-000001`,
        sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(company(ticker).cik)}/filing.htm`,
        source_fiscal_year: year + 1, source_fiscal_period: 'FY' }] };
  }
  return { ticker, company_cik: company(ticker).cik, company_name: company(ticker).name,
    requested_period: 'annual', requested_fiscal_year: year, fiscal_years: options.years ?? [2025, 2024], period,
    period_reason: null, selection_policy: 'Existing deterministic selection', metrics };
}
function missing(ticker, year, reason = 'No stored annual reporting window.') {
  const result = response(ticker, year); result.period = null; result.period_reason = reason;
  for (const p of Object.values(result.metrics)) Object.assign(p, { period: null, value: null, status: 'unavailable', reason, provenance: [], inputs: [] });
  return result;
}

async function mount(ctx) {
  const requests = [];
  ctx.mock.method(globalThis, 'fetch', (url, options) => new Promise(resolve => requests.push({ path: String(url), options, resolve })));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(React.createElement(Comparison, { companies })));
  ctx.after(async () => { await act(async () => root.unmount()); host.remove(); });
  const release = async (req, body, version = req.options.headers?.['X-FinLens-Data-Version'], status = 200) => {
    assert.ok(req, 'Expected pending request');
    await act(async () => req.resolve(new Response(JSON.stringify(body), { status, headers: version === null || version === undefined ? {} : { 'X-FinLens-Data-Version': String(version) } })));
  };
  const request = (ticker, suffix) => requests.findLast(r => r.path === `/api/finlens/companies/${ticker}/${suffix}`);
  const change = async (selector, value) => { await act(async () => {
    const control = host.querySelector(selector); control.value = String(value); control.dispatchEvent(new Event('change', { bubbles: true }));
  }); };
  const click = async label => { const button = [...host.querySelectorAll('button')].find(b => b.textContent === label); assert.ok(button); await act(async () => button.click()); };
  const select = async (a = 'AAA', b = 'BBB') => { await change('#comparison-company-0', a); await change('#comparison-company-1', b); };
  const discovery = async (tickers = ['AAA', 'BBB'], years = [2025, 2024]) => {
    for (const [index, ticker] of tickers.entries()) await release(request(ticker, 'freshness'), { ticker, data_version: index + 2, facts_version: 0, evidence_version: 1 });
    for (const ticker of tickers) await release(request(ticker, 'financials/annual'), response(ticker, null, { years }));
  };
  return { host, requests, release, request, change, click, select, discovery };
}

test('selection limits, duplicate prevention and accessible native controls include unindexed companies', async ctx => {
  const app = await mount(ctx);
  assert.equal(app.requests.length, 0);
  const select = app.host.querySelector('#comparison-company-0'); select.focus(); assert.equal(document.activeElement, select);
  assert.equal(app.host.querySelector('label[for="comparison-company-0"]').textContent, 'Company 1');
  await app.change('#comparison-company-0', 'AAA');
  assert.ok(app.host.querySelector('#comparison-company-1 option[value="AAA"]').disabled);
  await app.change('#comparison-company-1', 'AAA');
  assert.equal(app.host.querySelector('#comparison-company-1').value, '');
  assert.equal(app.requests.length, 0);
  await app.click('Add company'); await app.click('Add company');
  assert.equal(app.host.querySelectorAll('.comparison-picker').length, 4);
  assert.ok([...app.host.querySelectorAll('button')].find(b => b.textContent === 'Add company').disabled);
  const remove = app.host.querySelector('button[aria-label="Remove company 4"]');
  await act(async () => remove.click());
  assert.equal(app.host.querySelectorAll('.comparison-picker').length, 3);
  assert.equal(document.activeElement.id, 'comparison-company-2');
  assert.equal(contract.validCompanySelection(['AAA', 'BBB']), true);
  assert.equal(contract.validCompanySelection(['AAA', 'AAA']), false);
  assert.equal(contract.validCompanySelection(['AAA', 'BBB', 'CCC', 'DDD', 'EEE']), false);
});

test('annual table retains actual windows, units, bases, negative cash flow, unavailable and SEC provenance', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025, { basis: 'customer_contract', period: { start: '2024-09-29', end: '2025-09-27' } }));
  assert.match(app.host.textContent, /Reporting windows differ/);
  assert.match(app.host.textContent, /Revenue economic bases differ/);
  assert.match(app.host.textContent, /Sep 29, 2024 – Sep 27, 2025/);
  assert.match(app.host.textContent, /Jan 1, 2025 – Dec 31, 2025/);
  assert.match(app.host.textContent, /Unavailable/); assert.match(app.host.textContent, /-\$10/);
  assert.equal(app.host.querySelectorAll('tbody tr').length, 7);
  assert.equal(app.host.querySelectorAll('th[scope="row"]').length, 7);
  const scroll = app.host.querySelector('[role="region"]'); scroll.focus(); assert.equal(document.activeElement, scroll);
  assert.equal(scroll.getAttribute('tabindex'), '0');
  const sources = app.host.querySelector('tbody td details'); assert.match(sources.querySelector('summary').textContent, /AAA Revenue sources/);
  sources.querySelector('summary').focus(); assert.equal(document.activeElement, sources.querySelector('summary'));
  assert.match(sources.textContent, /Exact API value: 1000000000 USD/);
  assert.match(sources.querySelector('a').href, /sec.gov/);
  assert.equal(app.requests.length, 6, 'One freshness, discovery and selected-year request per company');
  assert.equal(app.request('AAA', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '2');
  assert.equal(app.request('BBB', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '3');
  assert.ok(app.requests.every(r => !r.options.method && !r.options.body));
  const css = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(css, /comparison-scroll/); assert.match(css, /comparison-controls \{ grid-template-columns:minmax\(0,1fr\)/);
});

test('four-company comparison stays bounded with distinct provenance and not-applicable presentation', async ctx => {
  const app = await mount(ctx); await app.click('Add company'); await app.click('Add company');
  const tickers = ['AAA', 'BBB', 'CCC', 'DDD'];
  for (const [i, ticker] of tickers.entries()) await app.change(`#comparison-company-${i}`, ticker);
  await app.discovery(tickers);
  for (const ticker of tickers) {
    const result = response(ticker, 2025);
    if (ticker === 'DDD') result.metrics.operating_margin.status = 'not_applicable';
    await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), result);
  }
  assert.equal(app.requests.length, 12);
  assert.equal(app.host.querySelectorAll('thead th').length, 5);
  assert.equal(app.host.querySelectorAll('tbody td').length, 28);
  assert.match(app.host.textContent, /Not applicable/);
  assert.doesNotMatch(app.host.textContent, /Reporting windows differ/);
  for (const [i, ticker] of tickers.entries()) {
    const source = app.host.querySelector(`tbody tr td:nth-child(${i+2}) details`);
    assert.match(source.textContent, new RegExp(`${company(ticker).cik}-26-000001`));
    assert.equal(source.querySelector('a').href, `https://www.sec.gov/Archives/edgar/data/${i+1}/filing.htm`);
  }
});

test('fiscal year change clears old values and rejects late responses, missing window remains explicit', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const oldA = app.request('AAA', 'financials/annual?fiscal_year=2025');
  const oldB = app.request('BBB', 'financials/annual?fiscal_year=2025');
  await app.change('#comparison-year', 2024);
  assert.ok(oldA.options.signal.aborted && oldB.options.signal.aborted);
  await app.release(oldA, response('AAA', 2025)); await app.release(oldB, response('BBB', 2025));
  assert.equal(app.host.querySelector('table'), null);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2024'), response('AAA', 2024));
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2024'), missing('BBB', 2024, 'Ambiguous annual window.'));
  assert.match(app.host.querySelector('caption').textContent, /FY2024/);
  assert.match(app.host.textContent, /missing or ambiguous/); assert.match(app.host.textContent, /Ambiguous annual window/);
  assert.doesNotMatch(app.host.querySelector('table').textContent, /FY2025/);
  assert.equal(app.requests.filter(r => r.path.endsWith('financials/annual')).length, 2, 'Year changes reuse version-pinned discovery');
});

test('company change and incomplete selection hide previous table, with late results excluded', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const oldA = app.request('AAA', 'financials/annual?fiscal_year=2025'); const oldB = app.request('BBB', 'financials/annual?fiscal_year=2025');
  await app.change('#comparison-company-1', 'CCC');
  assert.ok(oldB.options.signal.aborted);
  await app.release(oldA, response('AAA', 2025)); await app.release(oldB, response('BBB', 2025));
  assert.equal(app.host.querySelector('table'), null);
  await app.discovery(['AAA', 'CCC']);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  await app.release(app.request('CCC', 'financials/annual?fiscal_year=2025'), response('CCC', 2025));
  assert.doesNotMatch(app.host.querySelector('table').textContent, /BBB/);
  await app.click('Add company');
  assert.equal(app.host.querySelector('table'), null);
  assert.match(app.host.textContent, /Select 2–4 distinct/);
});

test('cancel during discovery and financial requests cannot publish ignored-abort results; retry works', async ctx => {
  const app = await mount(ctx); await app.select();
  const pending = app.request('AAA', 'freshness'); await app.click('Cancel comparison');
  assert.ok(pending.options.signal.aborted); await app.release(pending, { ticker: 'AAA', data_version: 2, facts_version: 0, evidence_version: 1 });
  assert.match(app.host.textContent, /Comparison cancelled/); assert.equal(app.requests.length, 2);
  await app.click('Refresh comparison'); await app.discovery();
  const annual = app.request('AAA', 'financials/annual?fiscal_year=2025'); const other = app.request('BBB', 'financials/annual?fiscal_year=2025');
  await app.click('Cancel comparison'); assert.ok(annual.options.signal.aborted);
  await app.release(annual, response('AAA', 2025)); await app.release(other, response('BBB', 2025));
  assert.equal(app.host.querySelector('table'), null); assert.match(app.host.textContent, /Comparison cancelled/);
  await app.click('Refresh comparison'); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  assert.ok(app.host.querySelector('table'));
});

test('version changes reject stale financial column without hiding verified independent company', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025), '9');
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  const first = app.host.querySelector('tbody td'); assert.match(first.textContent, /Published data changed/);
  assert.ok(!first.querySelector('details')); assert.match(app.host.querySelector('tbody td:nth-child(3)').textContent, /\$1B/);
  await app.click('Refresh comparison'); assert.equal(app.host.querySelector('table'), null);
});

test('no observed years and network/identity errors remain honest and retryable', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery(['AAA', 'BBB'], []);
  assert.match(app.host.textContent, /No observed annual fiscal years/); assert.equal(app.host.querySelector('table'), null);
  await app.click('Refresh comparison');
  await app.release(app.request('AAA', 'freshness'), { ticker: 'BBB', data_version: 2, facts_version: 0, evidence_version: 1 });
  await app.release(app.request('BBB', 'freshness'), { detail: 'Synthetic failure' }, null, 503);
  assert.match(app.host.textContent, /could not be verified/); assert.match(app.host.textContent, /Synthetic failure/);
  assert.equal(app.host.querySelector('table'), null);
});

test('union choices prefer a genuinely shared fiscal label but retain missing coverage', () => {
  assert.deepEqual(contract.comparisonYears([[2025, 2024], [2024, 2023]]), { years: [2025, 2024, 2023], preferred: 2024 });
  assert.deepEqual(contract.comparisonYears([[2025], [2024]]), { years: [2025, 2024], preferred: 2025 });
  assert.equal(contract.reportingWindowsDiffer([response('AAA', 2025), response('BBB', 2025)]), false);
});

for (const [label, mutate] of [
  ['ticker', r => { r.ticker = 'BBB'; }], ['CIK', r => { r.company_cik = company('BBB').cik; }],
  ['requested FY', r => { r.requested_fiscal_year = 2024; }], ['period FY', r => { r.period.fiscal_year = 2024; }],
  ['YTD', r => { r.period.kind = 'half_year'; }], ['falsely labeled YTD', r => { r.period.start = '2025-07-01'; }],
  ['missing metric', r => { delete r.metrics.net_margin; }], ['wrong unit', r => { r.metrics.revenue.unit = 'EUR'; }],
  ['source CIK', r => { r.metrics.revenue.provenance[0].company_cik = company('BBB').cik; }],
  ['source period', r => { r.metrics.revenue.provenance[0].period_end = '2024-12-31'; }],
  ['source accession', r => { r.metrics.revenue.provenance[0].accession_number = 'untrusted'; }],
  ['nonfinite value', r => { r.metrics.revenue.value = 'NaN'; }],
  ['duplicate years', r => { r.fiscal_years = [2025, 2025]; }],
  ['missing window with amount', r => { r.period = null; }],
]) test(`annual client scope validator rejects ${label}`, () => {
  const result = response('AAA', 2025); mutate(result);
  assert.throws(() => contract.validateAnnualResponse(result, company('AAA'), 2025), e => e.code === 'INVALID_RESPONSE');
});

test('available, unavailable and not-applicable are preserved, including week calendars', () => {
  const result = response('AAA', 2025, { period: { start: '2024-09-22', end: '2025-09-27' } });
  result.metrics.net_margin.status = 'not_applicable';
  assert.equal(contract.validateAnnualResponse(result, company('AAA'), 2025), result);
});

test('annual API requires explicit publication version and rejects missing version header', async ctx => {
  ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(response('AAA', null))));
  await assert.rejects(api.getAnnualFinancials('AAA', null, new AbortController().signal), e => e.code === 'INVALID_RESPONSE');
  await assert.rejects(api.getAnnualFinancials('AAA', null, api.versionedController(2, () => {}).signal), e => e.code === 'INVALID_RESPONSE');
});

test('backend-calculated Revenue YoY retains the isolated prior annual operand; mismatched inputs are rejected', () => {
  const result = response('AAA', 2025);
  const current = result.metrics.revenue.provenance[0];
  const prior = { ...current, fact_id: 100, value: '800000000', period_start: '2024-01-01', period_end: '2024-12-31' };
  const period = { ...result.period, start: prior.period_start, end: prior.period_end, fiscal_year: 2024 };
  result.metrics.revenue_growth_yoy = { ...result.metrics.revenue_growth_yoy, status: 'available', reason: null,
    value: '0.25', provenance: [current, prior], inputs: [
      { role: 'current', metric: 'revenue', value: current.value, unit: 'USD', period: result.period, fact_ids: [current.fact_id] },
      { role: 'prior', metric: 'revenue', value: prior.value, unit: 'USD', period, fact_ids: [prior.fact_id] },
    ] };
  assert.equal(contract.validateAnnualResponse(result, company('AAA'), 2025).metrics.revenue_growth_yoy.value, '0.25');
  for (const mutate of [r => { r.metrics.revenue_growth_yoy.inputs[1].period.kind = 'half_year'; },
    r => { r.metrics.revenue_growth_yoy.inputs[1].unit = 'EUR'; },
    r => { r.metrics.revenue_growth_yoy.provenance[1].company_cik = company('BBB').cik; },
    r => { r.metrics.revenue_growth_yoy.inputs[1].fact_ids = [999]; }]) {
    const invalid = structuredClone(result); mutate(invalid);
    assert.throws(() => contract.validateAnnualResponse(invalid, company('AAA'), 2025), e => e.code === 'INVALID_RESPONSE');
  }
});

test('serialized backend 52/53-week rollover response passes the client without relaxing incompatible prior periods', () => {
  // Requires the ordinary backend test environment. No persisted JSON, live DB,
  // network or hand-authored replacement of the backend response is involved.
  const backend = fileURLToPath(new URL('../../backend/', import.meta.url));
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].map(p => fileURLToPath(new URL(`../../backend/${p}`, import.meta.url))).find(existsSync) ?? 'python';
  const serialized = spawnSync(python, ['-B', '-c', `
import sys
from unittest.mock import Mock, patch
sys.path.insert(0, 'tests')
from test_company_comparison import rollover_view
with patch('app.database.engine.connect', Mock(side_effect=AssertionError('Live database forbidden'))), \\
     patch('app.sec_client._sec_get', Mock(side_effect=AssertionError('SEC requests forbidden'))), \\
     patch('app.answer_service._get_openai_client', Mock(side_effect=AssertionError('AI requests forbidden'))):
    print(rollover_view().annual_comparison(2024).model_dump_json())
`], { cwd: backend, encoding: 'utf8', timeout: 30000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(serialized.status, 0, serialized.stderr || serialized.error?.message);
  const result = JSON.parse(serialized.stdout);
  const issuer = { ...company('AAA'), ticker: 'TEST', name: 'Synthetic company' };
  assert.equal(result.metrics.revenue_growth_yoy.value, '0.25');
  assert.equal(result.metrics.revenue_growth_yoy.inputs[1].period.fiscal_year, 2022);
  assert.equal(contract.validateAnnualResponse(result, issuer, 2024), result);

  const shift = (value, days) => new Date(Date.parse(`${value}T00:00:00Z`) - days * 86400000).toISOString().slice(0, 10);
  const withPriorGaps = (startGap, endGap) => {
    const changed = structuredClone(result);
    const point = changed.metrics.revenue_growth_yoy;
    const prior = point.inputs.find(i => i.role === 'prior');
    prior.period.start = shift(changed.period.start, startGap);
    prior.period.end = shift(changed.period.end, endGap);
    prior.period.fiscal_year = Number(prior.period.end.slice(0, 4));
    for (const source of point.provenance.filter(s => prior.fact_ids.includes(s.fact_id))) {
      source.period_start = prior.period.start; source.period_end = prior.period.end;
    }
    return changed;
  };
  for (const gaps of [[357, 357], [378, 378]]) {
    assert.doesNotThrow(() => contract.validateAnnualResponse(withPriorGaps(...gaps), issuer, 2024));
  }
  // Preserve exact input/source linkage in these negatives: only the date
  // comparability rule is violated, not a convenient identity mismatch.
  for (const gaps of [[356, 365], [379, 370], [365, 356], [370, 379], [360, 370]]) {
    assert.throws(() => contract.validateAnnualResponse(withPriorGaps(...gaps), issuer, 2024), e => e.code === 'INVALID_RESPONSE');
  }
  const mislabeled = structuredClone(result);
  mislabeled.metrics.revenue_growth_yoy.inputs[1].period.fiscal_year = 2023;
  assert.throws(() => contract.validateAnnualResponse(mislabeled, issuer, 2024), e => e.code === 'INVALID_RESPONSE');
});
