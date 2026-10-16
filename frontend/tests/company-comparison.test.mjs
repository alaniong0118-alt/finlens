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
let dom, createRoot, Comparison, contract, api, browserData;
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
  browserData = load(fileURLToPath(new URL('../e2e/fixtures/data.ts', import.meta.url)));
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
    const unit = ['revenue_growth_yoy', 'operating_margin', 'net_margin', 'gross_margin'].includes(name) ? 'ratio' : 'USD';
    const available = ['revenue', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow', 'gross_profit', 'operating_income', 'net_income'].includes(name);
    const value = name === 'revenue' ? '1000000000' : name === 'capital_expenditures' ? '3' : name === 'free_cash_flow' ? '-10'
      : name === 'gross_profit' ? '40' : name === 'operating_income' ? '0' : name === 'net_income' ? '-10' : '-7';
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

function backendAnnual(factory, year) {
  const backend = fileURLToPath(new URL('../../backend/', import.meta.url));
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].map(p => fileURLToPath(new URL(`../../backend/${p}`, import.meta.url))).find(existsSync) ?? 'python';
  const serialized = spawnSync(python, ['-B', '-c', `
import sys, socket
from contextlib import ExitStack
from unittest.mock import Mock, patch
from sqlalchemy.engine import Engine
sys.path.insert(0, 'tests')
from test_company_comparison import ${factory}
forbidden = Mock(side_effect=AssertionError('Live database/network/model dependency forbidden'))
with ExitStack() as stack:
    for target in ('app.sec_client._sec_get', 'app.answer_service._get_openai_client',
                   'app.embedding_service._get_model', 'app.embedding_service._load_model'):
        stack.enter_context(patch(target, forbidden))
    for obj, name in ((Engine, 'connect'), (Engine, 'raw_connection'), (socket, 'create_connection'), (socket.socket, 'connect')):
        stack.enter_context(patch.object(obj, name, forbidden))
    print(${factory}().annual_comparison(${year}).model_dump_json())
`], { cwd: backend, encoding: 'utf8', timeout: 30000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(serialized.status, 0, serialized.stderr || serialized.error?.message);
  return JSON.parse(serialized.stdout);
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
  const discovery = async (tickers = ['AAA', 'BBB'], years = [2025, 2024], versions = tickers.map((_, i) => i + 2)) => {
    for (const [index, ticker] of tickers.entries()) await release(request(ticker, 'freshness'), { ticker, data_version: versions[index], facts_version: 0, evidence_version: Math.min(1, versions[index]) });
    for (const ticker of tickers) await release(request(ticker, 'financials/annual'), response(ticker, null, { years }));
  };
  return { host, requests, release, request, change, click, select, discovery };
}

async function focusTable(ctx, count = 2) {
  const app = await mount(ctx);
  if (count === 4) { await app.click('Add company'); await app.click('Add company'); }
  const tickers = ['AAA', 'BBB', 'CCC', 'DDD'].slice(0, count);
  for (const [i, ticker] of tickers.entries()) await app.change(`#comparison-company-${i}`, ticker);
  await app.discovery(tickers, [2025, 2024], tickers.map((_, i) => i));
  for (const ticker of tickers) {
    const result = response(ticker, 2025);
    if (ticker === 'AAA') result.metrics.revenue.alternatives = [{ ...result.metrics.revenue.provenance[0], fact_id: 101, value: '900000000' }];
    await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), result);
  }
  return { ...app, scroller: app.host.querySelector('.comparison-scroll') };
}

function focusGeometry(ctx, scroller, target, { initial = 0, x = 206, width = 216, total = 640, visible = true,
  top = 200, height = 44, initialY = 0, pageX = 0, maxY = 5000, viewportHeight = 844, viewportTop = 0, visual = true } = {}) {
  let position = initial, writes = 0, pageY = initialY;
  const verticalWrites = [];
  const property = (object, key, descriptor) => {
    const before = Object.getOwnPropertyDescriptor(object, key);
    Object.defineProperty(object, key, { configurable: true, ...descriptor });
    ctx.after(() => { if (before) Object.defineProperty(object, key, before); else delete object[key]; });
  };
  property(window, 'scrollY', { get: () => pageY });
  property(window, 'scrollX', { value: pageX });
  property(window, 'visualViewport', { value: visual ? { offsetTop: viewportTop, height: viewportHeight } : null });
  property(document, 'scrollingElement', { value: document.documentElement });
  property(document.documentElement, 'clientHeight', { value: viewportHeight });
  property(document.documentElement, 'scrollHeight', { value: maxY + viewportHeight });
  Object.defineProperties(scroller, {
    clientLeft: { configurable: true, value: 1 }, clientWidth: { configurable: true, value: 322 },
    scrollWidth: { configurable: true, value: total },
    scrollLeft: { configurable: true, get: () => position, set: value => { position = value; writes++; } },
  });
  scroller.scrollTop = 17;
  ctx.mock.method(scroller, 'getBoundingClientRect', () => ({ left: 33, right: 357, width: 324 }));
  ctx.mock.method(target, 'getBoundingClientRect', () => ({ left: x + initial - position, right: x + initial - position + width, width, top: top + initialY - pageY, bottom: top + initialY - pageY + height, height }));
  const matches = target.matches.bind(target), style = window.getComputedStyle.bind(window);
  ctx.mock.method(target, 'matches', selector => selector === ':focus-visible' ? visible : matches(selector));
  ctx.mock.method(window, 'getComputedStyle', element => element === target ? { outlineWidth: '3px', outlineOffset: '3px' } : style(element));
  ctx.mock.method(window, 'scrollTo', options => {
    assert.equal(options.left, pageX); assert.equal(options.behavior, 'instant');
    verticalWrites.push(options.top); pageY = options.top;
  });
  return { position: () => position, writes: () => writes, verticalWrites, pageY: () => pageY };
}

for (const [label, geometry, expected] of [
  ['right clipping', {}, 73],
  ['left clipping after native scrolling', { initial: 318, x: -112 }, 165],
  ['four-company right clipping', { initial: 299, x: 307, width: 176, total: 960 }, 433],
  ['already visible', { initial: 318, x: 128 }, 318],
  ['left boundary clamping', { initial: 10, x: -200 }, 0],
  ['right boundary clamping', { initial: 310, x: 400 }, 318],
  ['pointer focus exclusion', { visible: false }, 0],
  ['touch focus exclusion', { visible: false }, 0],
]) test(`comparison keyboard focus reveal: ${label}`, async ctx => {
  const app = await focusTable(ctx, geometry.total === 960 ? 4 : 2);
  const target = app.scroller.querySelector('summary');
  const requestCount = app.requests.length;
  const beforeSelection = [...app.host.querySelectorAll('.comparison-picker select')].map(el => el.value);
  const geo = focusGeometry(ctx, app.scroller, target, geometry);
  await act(async () => target.focus());
  assert.equal(geo.position(), expected);
  assert.equal(geo.writes(), expected === (geometry.initial ?? 0) ? 0 : 1);
  assert.equal(document.activeElement, target);
  assert.equal(app.scroller.scrollTop, 17);
  assert.equal(window.scrollY, 0);
  assert.deepEqual(geo.verticalWrites, []);
  assert.deepEqual([...app.host.querySelectorAll('.comparison-picker select')].map(el => el.value), beforeSelection);
  assert.equal(app.host.querySelector('#comparison-year').value, '2025');
  assert.equal(app.requests.length, requestCount);
  assert.equal(app.request('AAA', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '0');
  assert.equal(app.request('BBB', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '1');
  if (!label.includes('boundary') && geometry.visible !== false) {
    const rect = target.getBoundingClientRect();
    assert.ok(rect.left - 6 >= 34 && rect.right + 6 <= 356, 'Whole control and 6px focus indicator fit');
  }
  // A repeated native focus event must not accumulate another adjustment.
  await act(async () => target.dispatchEvent(new Event('focusin', { bubbles: true })));
  assert.equal(geo.position(), expected);
  assert.equal(geo.writes(), expected === (geometry.initial ?? 0) ? 0 : 1);
});

for (const [label, selector] of [
  ['nested disclosure', '.provenance details summary'],
  ['source link', '.provenance .source-record a'],
]) test(`comparison focus reveal covers ${label} without moving focus or fetching`, async ctx => {
  const app = await focusTable(ctx);
  app.scroller.querySelector('.provenance').open = true;
  const target = app.scroller.querySelector(selector);
  assert.ok(target);
  const count = app.requests.length;
  const geo = focusGeometry(ctx, app.scroller, target, { top: -0.15625, initialY: 500 });
  await act(async () => target.focus());
  assert.equal(geo.position(), 73);
  assert.equal(geo.pageY(), 492);
  assert.equal(document.activeElement, target);
  assert.equal(app.requests.length, count);
  assert.equal(app.scroller.scrollTop, 17);
});

for (const [label, geometry, expectedY, expectedX = 0] of [
  ['top outline clipping', { top: 5.4375 }, 498],
  ['bottom control and outline clipping', { top: 956.359375, viewportHeight: 1000 }, 508],
  ['fractional top control clipping rounds outward', { top: -0.15625 }, 492],
  ['fractional bottom outline clipping rounds outward', { top: 954.25, viewportHeight: 1000 }, 506],
  ['top document clamp', { top: -20, initialY: 2 }, 0],
  ['bottom document clamp', { top: 840, initialY: 1998, maxY: 2000 }, 2000],
  ['no document scroll range', { top: 840, initialY: 0, maxY: 0 }, 0],
  ['already visible', {}, 500],
  ['visible outline needs no extra safety scroll', { top: 6.25 }, 500],
  ['visual viewport top boundary', { top: 122, viewportTop: 120, viewportHeight: 600 }, 495],
  ['visual viewport bottom boundary', { top: 680, viewportTop: 120, viewportHeight: 600 }, 511],
  ['layout viewport fallback', { top: 840, visual: false }, 547],
  ['pointer excludes both axes', { top: -20, x: 206, visible: false }, 500],
  ['touch excludes both axes', { top: 840, x: 206, visible: false }, 500],
  ['both axes reveal together', { top: -0.15625, x: 206, pageX: 19 }, 492, 73],
  ['four-company combined reveal', { top: 840, initial: 299, x: 307, width: 176, total: 960 }, 547, 433],
]) test(`comparison vertical keyboard reveal: ${label}`, async ctx => {
  const app = await focusTable(ctx, geometry.total === 960 ? 4 : 2);
  const target = app.scroller.querySelector('summary');
  const requestCount = app.requests.length;
  const selections = [...app.host.querySelectorAll('select')].map(el => el.value);
  const headers = [...app.scroller.querySelectorAll('thead th')].map(el => el.textContent);
  const disclosures = [...app.scroller.querySelectorAll('details')].map(el => el.open);
  const initialY = geometry.initialY ?? 500;
  const geo = focusGeometry(ctx, app.scroller, target, { x: 100, initialY, ...geometry });
  await act(async () => target.focus());
  assert.equal(document.activeElement, target);
  assert.equal(geo.pageY(), expectedY);
  assert.equal(geo.position(), expectedX);
  assert.equal(window.scrollX, geometry.pageX ?? 0);
  assert.equal(app.scroller.scrollTop, 17);
  assert.deepEqual(geo.verticalWrites, expectedY === initialY ? [] : [expectedY]);
  assert.deepEqual([...app.host.querySelectorAll('select')].map(el => el.value), selections);
  assert.deepEqual([...app.scroller.querySelectorAll('thead th')].map(el => el.textContent), headers);
  assert.deepEqual([...app.scroller.querySelectorAll('details')].map(el => el.open), disclosures);
  assert.match(headers[1], /Publication 0/); assert.match(headers[2], /Publication 1/);
  assert.equal(app.requests.length, requestCount);
  for (const ticker of ['AAA', 'BBB']) assert.equal(app.request(ticker, 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], ticker === 'AAA' ? '0' : '1');
  const before = [...geo.verticalWrites];
  await act(async () => target.dispatchEvent(new Event('focusin', { bubbles: true })));
  assert.deepEqual(geo.verticalWrites, before, 'Settled or clamped focus must not schedule repeated movement');
});

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
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11);
  assert.equal(app.host.querySelectorAll('th[scope="row"]').length, 11);
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

test('eleven rows render backend-calculated gross margin, signed income and provenance with independent zero and one pins', async ctx => {
  const result = backendAnnual('expanded_view', 2025);
  assert.deepEqual(Object.keys(result.metrics), [
    'revenue', 'revenue_growth_yoy', 'operating_margin', 'net_margin',
    'operating_cash_flow', 'capital_expenditures', 'free_cash_flow',
    'gross_profit', 'operating_income', 'net_income', 'gross_margin',
  ]);
  assert.deepEqual(contract.COMPARISON_METRICS, Object.keys(result.metrics));
  const issuer = { ...company('AAA'), ticker: 'TEST' };
  assert.equal(contract.validateAnnualResponse(result, issuer, 2025), result);
  assert.equal(result.metrics.gross_margin.value, '0.4');
  assert.deepEqual(result.metrics.gross_margin.inputs.map(i => i.fact_ids), [[2], [1]]);
  assert.equal(result.metrics.gross_profit.alternatives[0].value, '35');
  const app = await mount(ctx); await app.select(); await app.discovery(['AAA', 'BBB'], [2025, 2024], [0, 1]);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), { ...result, ticker: 'AAA' });
  const bank = response('BBB', 2025);
  for (const name of ['gross_profit', 'gross_margin']) Object.assign(bank.metrics[name], {
    value: null, status: 'not_applicable', reason: 'Observed net-interest revenue basis.', provenance: [], inputs: [],
  });
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), bank);
  const rows = [...app.host.querySelectorAll('tbody tr')];
  assert.equal(rows.length, 11);
  for (const [label, value] of [['Gross profit', '$40'], ['Operating income', '$0'], ['Net income', '-$10'], ['Gross margin', '40%']]) {
    const row = rows.find(r => r.querySelector('th').textContent === label);
    assert.equal(row.querySelector('.metric-value').textContent, value);
  }
  const margin = rows.at(-1).querySelector('td');
  assert.match(margin.textContent, /Ratio · shown as percent/);
  assert.match(margin.textContent, /gross_profit \/ revenue/);
  assert.equal(margin.querySelectorAll('.source-record').length, 2);
  assert.match(rows.at(-1).querySelectorAll('td')[1].textContent, /Not applicable/);
  const disclosure = margin.querySelector('summary'); disclosure.focus();
  assert.equal(document.activeElement, disclosure);
  assert.equal(app.requests.length, 6);
  assert.equal(app.request('AAA', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '0');
  assert.equal(app.request('BBB', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '1');
  assert.match(app.host.querySelector('thead').textContent, /Publication 0/);

  const oldContract = structuredClone(result);
  for (const name of ['gross_profit', 'operating_income', 'net_income', 'gross_margin']) delete oldContract.metrics[name];
  assert.throws(() => contract.validateAnnualResponse(oldContract, issuer, 2025), e => e.code === 'INVALID_RESPONSE');
  for (const name of ['gross_profit', 'operating_income', 'net_income', 'gross_margin']) {
    for (const corrupt of [
      r => { r.metrics[name].unit = name === 'gross_margin' ? 'USD' : 'ratio'; },
      r => { r.metrics[name].period = { ...r.period, start: '2025-07-01' }; },
      r => { r.metrics[name].provenance[0].company_cik = company('BBB').cik; },
      r => { r.metrics[name].provenance[0].period_end = '2024-12-31'; },
    ]) {
      const invalid = structuredClone(result); corrupt(invalid);
      assert.throws(() => contract.validateAnnualResponse(invalid, issuer, 2025), e => e.code === 'INVALID_RESPONSE');
    }
  }
  const wrongOperand = structuredClone(result);
  wrongOperand.metrics.gross_margin.inputs[0].unit = 'EUR';
  assert.throws(() => contract.validateAnnualResponse(wrongOperand, issuer, 2025), e => e.code === 'INVALID_RESPONSE');
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
  assert.equal(app.host.querySelectorAll('tbody td').length, 44);
  assert.match(app.host.textContent, /Not applicable/);
  assert.doesNotMatch(app.host.textContent, /Reporting windows differ/);
  for (const [i, ticker] of tickers.entries()) {
    const source = app.host.querySelector(`tbody tr td:nth-child(${i+2}) details`);
    assert.match(source.textContent, new RegExp(`${company(ticker).cik}-26-000001`));
    assert.equal(source.querySelector('a').href, `https://www.sec.gov/Archives/edgar/data/${i+1}/filing.htm`);
  }
});

test('browser annual fixtures match the expanded contract for both issuers and fiscal years', () => {
  assert.deepEqual(browserData.annualMetrics, contract.COMPARISON_METRICS);
  for (const ticker of ['AAA', 'BBB']) {
    for (const year of [null, 2024, 2025]) {
      const result = browserData.annual(ticker, year);
      assert.equal(contract.validateAnnualResponse(result, browserData.company(ticker), year), result);
      if (year !== null) {
        assert.equal(Object.keys(result.metrics).length, 11);
        assert.equal(result.metrics.gross_margin.unit, 'ratio');
        assert.equal(result.metrics.gross_margin.status, 'unavailable');
        assert.equal(result.metrics.net_income.value, '-40000000');
      }
    }
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
