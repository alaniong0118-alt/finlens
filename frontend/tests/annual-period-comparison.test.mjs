import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

// Installed modules only. Real ReactDOM, API transport, validators, formatting and
// MetricProvenance; only the publication provider and fetch boundary are doubles.
// No child process, browser, service, fixture backend, socket or network call.
const require = createRequire(import.meta.url);
const Publication = React.createContext({ version: null, changed() {} });
let dom, createRoot, Comparison, helper, metrics;
const previousGlobals = new Map();
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const name of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent']) {
    previousGlobals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] });
  }
  previousGlobals.set('IS_REACT_ACT_ENVIRONMENT', Object.getOwnPropertyDescriptor(globalThis, 'IS_REACT_ACT_ENVIRONMENT'));
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import('react-dom/client'));
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const exports = {}; cache.set(path, exports);
    const compiled = ts.transpileModule(readFileSync(path, 'utf8'), { reportDiagnostics: true, compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
    } });
    assert.deepEqual(compiled.diagnostics, [], `Syntax diagnostics for ${path}`);
    const localRequire = name => {
      if (name === '@/components/research-freshness') return { useResearchVersion: () => React.useContext(Publication) };
      if (!name.startsWith('@/') && !name.startsWith('./')) return require(name);
      const base = name.startsWith('@/') ? fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url))
        : fileURLToPath(new URL(name, `file:///${path.replaceAll('\\', '/')}`));
      const dependency = ['.tsx', '.ts'].map(extension => base + extension).find(existsSync);
      assert.ok(dependency, `Known local dependency ${name}`);
      return load(dependency);
    };
    new Function('require', 'exports', compiled.outputText)(localRequire, exports);
    return exports;
  }
  Comparison = load(fileURLToPath(new URL('../components/annual-period-comparison.tsx', import.meta.url))).default;
  helper = load(fileURLToPath(new URL('../lib/annual-period-comparison.ts', import.meta.url)));
  metrics = load(fileURLToPath(new URL('../lib/company-comparison.ts', import.meta.url))).COMPARISON_METRICS;
});
after(() => {
  dom?.window.close();
  for (const [name, descriptor] of previousGlobals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
  }
});

const company = { id: 1, ticker: 'AAA', name: 'Synthetic annual issuer', cik: '0000000001', exchange: 'TEST',
  has_indexed_filing: false, indexed_filing_count: 0 };
const other = { ...company, id: 2, ticker: 'BBB', name: 'Second synthetic issuer', cik: '0000000002' };
const years = [2025, 2024, 2023, 2022, 2021];
function annual(year = null, issuer = company, options = {}) {
  const period = year === null ? null : { kind: 'annual', start: `${year}-01-01`, end: `${year}-12-31`,
    fiscal_year: year, fiscal_period: 'FY', fiscal_label_basis: 'annual_period_end_year', ...options.period };
  const rows = {};
  if (year !== null) for (const [index, metric] of metrics.entries()) {
    const ratio = ['revenue_growth_yoy', 'operating_margin', 'net_margin', 'gross_margin'].includes(metric);
    const value = metric === 'revenue' ? year === 2024 ? '0' : String((year - 2020) * 1000000000)
      : metric === 'net_income' ? '-1000000' : '3000000';
    const accession = `${issuer.cik}-26-000001`;
    rows[metric] = { metric, unit: ratio ? 'ratio' : 'USD', status: ratio ? 'unavailable' : 'available',
      value: ratio ? null : value, reason: ratio ? 'No compatible approved denominator.' : null,
      period, formula: null, ...(metric === 'revenue' ? { revenue_basis: options.basis ?? 'total_revenue' } : {}),
      inputs: [], alternatives: [], provenance: ratio ? [] : [{ fact_id: (year - 1900) * 100 + index + 1,
        company_cik: issuer.cik, original_concept: `us-gaap:${metric}`, value, unit: 'USD',
        period_start: period.start, period_end: period.end, form: '10-K', filed: `${year + 1}-02-01`,
        accession_number: accession, sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${accession.replaceAll('-', '')}/annual.htm`,
        source_fiscal_year: year + 1, source_fiscal_period: 'FY' }] };
  }
  return { ticker: issuer.ticker, company_name: issuer.name, company_cik: issuer.cik, requested_period: 'annual',
    requested_fiscal_year: year, fiscal_years: options.years ?? years, period, period_reason: null,
    selection_policy: 'Existing server annual selection policy', metrics: rows };
}
function missing(year) {
  const value = annual(year); value.period = null; value.period_reason = 'Ambiguous stored annual reporting windows.';
  for (const point of Object.values(value.metrics)) Object.assign(point, { period: null, status: 'unavailable',
    value: null, reason: value.period_reason, inputs: [], provenance: [] });
  return value;
}
async function mount(ctx, options = {}) {
  const requests = [], changed = ctx.mock.fn();
  let issuer = options.company ?? company, version = options.version === undefined ? 0 : options.version;
  ctx.mock.method(globalThis, 'fetch', (path, init) => {
    assert.match(String(path), /^\/api\/finlens\/companies\/(AAA|BBB)\/financials\/annual(?:\?fiscal_year=\d{4})?$/,
      'Only the existing stored annual API is permitted');
    return new Promise(resolve => requests.push({ path: String(path), init, resolve }));
  });
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const render = async (next = {}) => {
    if ('company' in next) issuer = next.company;
    if ('version' in next) version = next.version;
    await act(async () => root.render(React.createElement(Publication.Provider, { value: { version, changed } },
      React.createElement(Comparison, { company: issuer }))));
  };
  await render();
  let unmounted = false;
  const unmount = async () => { if (!unmounted) { unmounted = true; await act(async () => root.unmount()); host.remove(); } };
  ctx.after(unmount);
  const request = (year = null, ticker = issuer.ticker) => requests.findLast(item => item.path ===
    `/api/finlens/companies/${ticker}/financials/annual${year === null ? '' : `?fiscal_year=${year}`}`);
  const release = async (req, body, pin = req?.init.headers?.['X-FinLens-Data-Version'], status = 200) => {
    assert.ok(req, 'Expected pending annual request');
    await act(async () => req.resolve(new Response(JSON.stringify(body), { status,
      headers: pin === null ? {} : { 'X-FinLens-Data-Version': String(pin) } })));
  };
  const discover = async (available = years) => release(request(), annual(null, issuer, { years: available }));
  const toggle = async year => { const checkbox = host.querySelector(`input[value="${year}"]`); assert.ok(checkbox);
    await act(async () => checkbox.click()); };
  const click = async text => { const button = [...host.querySelectorAll('button')].find(item => item.textContent === text);
    assert.ok(button, `Button ${text}`); await act(async () => button.click()); };
  const select = async (chosen = [2025, 2024]) => { for (const year of chosen) await toggle(year); };
  const compare = () => click('Compare selected annual periods');
  const button = () => host.querySelector('button[type="submit"]');
  const row = metric => [...host.querySelectorAll('tbody tr')].find(item => item.querySelector('th')?.textContent.startsWith(metric));
  return { host, requests, request, release, render, changed, discover, toggle, click, select, compare, button, row, unmount };
}

test('annual selection requires 2–4 distinct discovered years, with no fallback', () => {
  for (const selected of [[], [2025], [2025, 2025], [2025, 2020], years, [2025, NaN]])
    assert.equal(helper.validAnnualSelection(selected, years), false);
  assert.equal(helper.validAnnualSelection([2025, 2024], years), true);
  assert.equal(helper.validAnnualSelection(years.slice(0, 4), years), true);
});

test('response boundary rejects malformed identity, year, window, units, fields and source lineage', () => {
  const mutations = [
    result => { result.company_cik = other.cik; },
    result => { result.ticker = other.ticker; },
    result => { result.requested_fiscal_year = 2023; },
    result => { result.period.kind = 'quarter'; },
    result => { result.period.start = '2025-04-01'; },
    result => { result.metrics.revenue.unit = 'EUR'; },
    result => { delete result.metrics.gross_margin; },
    result => { result.metrics.revenue.value = 'NaN'; },
    result => { result.metrics.revenue.reason = { unsafe: true }; },
    result => { result.metrics.revenue.formula = []; },
    result => { result.metrics.revenue.revenue_basis = {}; },
    result => { result.metrics.revenue.provenance[0].fact_id = 0; },
    result => { result.metrics.revenue.provenance[0].company_cik = other.cik; },
    result => { result.metrics.revenue.provenance[0].period_end = '2024-12-31'; },
    result => { result.metrics.revenue.provenance[0].original_concept = {}; },
    result => { result.metrics.revenue.provenance[0].sec_url = {}; },
    result => { result.metrics.revenue.provenance[0].filed = '2026-02-30'; },
    result => { result.metrics.revenue.provenance[0].value = 'Infinity'; },
    result => { result.fiscal_years = [2025, 2024]; },
    result => { result.metrics.revenue.inputs = [{ metric: 'revenue', role: 'current', value: '5', unit: 'USD',
      period: result.period, fact_ids: [9999999] }]; },
  ];
  for (const mutate of mutations) { const result = annual(2025); mutate(result);
    assert.throws(() => helper.annualPeriodResponse(result, company, 2025, years)); }
  assert.equal(helper.annualPeriodResponse(annual(2025), company, 2025, years).metrics.revenue.value, '5000000000');
  assert.throws(() => helper.annualPeriodResponse(annual(null, company, { years: [2025, 2025] }), company, null));
});

test('no request without a verified publication; publication zero pins discovery and explicit years', async ctx => {
  const app = await mount(ctx, { version: null });
  assert.equal(app.requests.length, 0); assert.match(app.host.textContent, /Waiting for a verified/);
  await app.render({ version: 0 });
  assert.equal(app.request().init.headers['X-FinLens-Data-Version'], '0');
  await app.discover();
  assert.equal(app.host.querySelectorAll('input:checked').length, 0);
  assert.equal(app.button().disabled, true); assert.equal(app.requests.length, 1);
  await app.select(); await app.compare();
  assert.equal(app.requests.length, 3);
  for (const year of [2025, 2024]) assert.equal(app.request(year).init.headers['X-FinLens-Data-Version'], '0');
  await app.release(app.request(2025), annual(2025)); await app.release(app.request(2024), annual(2024));
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11);
  assert.match(app.row('Revenue').textContent, /\$5B/); assert.match(app.row('Revenue').textContent, /\$0/);
  assert.match(app.row('Net income').textContent, /-\$1M/);
  assert.match(app.host.textContent, /Publication version 0/);
});

test('four-year grid enforces maximum, explicit selection and accessible table/disclosures', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(years.slice(0, 4));
  assert.equal(app.host.querySelector('input[value="2021"]').disabled, true);
  assert.equal(app.host.querySelector('input[value="2025"]').disabled, false);
  await app.compare();
  for (const year of years.slice(0, 4)) await app.release(app.request(year), annual(year));
  assert.equal(app.host.querySelectorAll('thead th[scope="col"]').length, 5);
  assert.equal(app.host.querySelectorAll('tbody th[scope="row"]').length, 11);
  assert.equal(app.host.querySelector('[role="region"]').tabIndex, 0);
  assert.equal(app.host.querySelectorAll('details.provenance').length, 44);
  assert.ok(app.host.querySelector('fieldset legend').textContent.includes('AAA'));
  assert.match(app.host.textContent, /2025-01-01|Jan 1, 2025/);
  assert.match(app.host.textContent, /not a historical as-of or original-vintage view/);
  assert.match(app.host.textContent, /not ranked, converted between currencies or normalized/);
});

test('empty, single-year and failed discovery never invent a selectable period', async ctx => {
  const app = await mount(ctx); await app.discover([]);
  assert.equal(app.host.querySelectorAll('input').length, 0); assert.equal(app.button().disabled, true);
  await app.click('Refresh annual periods'); await app.discover([2023]);
  await app.select([2023]); assert.equal(app.button().disabled, true);
  await app.click('Refresh annual periods');
  await app.release(app.request(), { detail: 'Stored coverage unavailable.' }, '0', 503);
  assert.match(app.host.textContent, /coverage could not be verified/);
  assert.match(app.host.textContent, /Stored coverage unavailable/);
  assert.equal(app.host.querySelector('table'), null);
});

test('missing and excluded reasons, original values, alternatives and official sources remain visible', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const result = annual(2025);
  result.metrics.revenue.alternatives = [{ ...result.metrics.revenue.provenance[0], fact_id: 999999, value: '4000000000' }];
  result.metrics.net_margin.status = 'not_applicable'; result.metrics.net_margin.reason = 'Industry measure excluded.';
  await app.release(app.request(2025), result); await app.release(app.request(2024), missing(2024));
  assert.match(app.row('Net margin').textContent, /Not applicable — excluded/);
  assert.match(app.host.textContent, /Industry measure excluded/);
  assert.match(app.host.textContent, /Ambiguous stored annual reporting windows/);
  assert.match(app.row('Revenue').textContent, /Exact API value: 5000000000 USD/);
  assert.match(app.row('Revenue').textContent, /1 alternative source observations/);
  const links = [...app.host.querySelectorAll('a')]; assert.ok(links.length > 0);
  for (const link of links) { assert.match(link.href, /^https:\/\/www\.sec\.gov\/Archives\//); assert.equal(link.rel, 'noopener noreferrer'); }
  assert.match(app.host.textContent, /Source filing context: 2026 \/ FY/);
  assert.match(app.host.textContent, /No compatible source selected/);
});

test('off-origin source URLs are never turned into links by the reused source display', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const result = annual(2025); result.metrics.revenue.provenance[0].sec_url = 'https://evil.test/filing';
  await app.release(app.request(2025), result); await app.release(app.request(2024), annual(2024));
  assert.equal(app.row('Revenue').querySelectorAll('a').length, 1);
  assert.equal([...app.host.querySelectorAll('a')].some(link => link.href.includes('evil.test')), false);
});

test('unequal duration and revenue-basis warnings preserve operand periods and exact server values', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const result = annual(2025, company, { basis: 'net_revenue', period: { start: '2024-12-30', end: '2025-12-28' } });
  const margin = result.metrics.net_margin, revenue = result.metrics.revenue.provenance[0];
  Object.assign(margin, { status: 'available', value: '0.123456789', reason: null, formula: 'Existing server ratio',
    provenance: [revenue], inputs: [{ role: 'denominator', metric: 'revenue', value: revenue.value, unit: 'USD',
      fact_ids: [revenue.fact_id], revenue_basis: 'net_revenue', period: result.period }] });
  await app.release(app.request(2025), result); await app.release(app.request(2024), annual(2024));
  assert.match(app.row('Revenue').textContent, /durations differ/);
  assert.match(app.row('Revenue').textContent, /Fiscal boundaries differ/);
  assert.match(app.row('Revenue').textContent, /Revenue-basis labels differ/);
  assert.match(app.row('Net margin').textContent, /Exact API value: 0.123456789 ratio/);
  assert.match(app.row('Net margin').textContent, /operand periods and bases/);
  assert.match(app.row('Net margin').textContent, /net_revenue/);
  assert.match(app.row('Net margin').textContent, /denominator/);
});

test('adjacent-year Revenue YoY keeps an unchanged shared fact and distinct operand lineage', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const later = annual(2025), earlier = annual(2024), prior = annual(2023);
  earlier.metrics.revenue.value = '4000000000';
  earlier.metrics.revenue.provenance[0].value = '4000000000';
  prior.metrics.revenue.value = '2000000000';
  prior.metrics.revenue.provenance[0].value = '2000000000';
  const shared = structuredClone(earlier.metrics.revenue.provenance[0]);
  const operand = (role, result) => ({ role, metric: 'revenue', value: result.metrics.revenue.value, unit: 'USD',
    fact_ids: [result.metrics.revenue.provenance[0].fact_id], period: structuredClone(result.period),
    revenue_basis: result.metrics.revenue.revenue_basis });
  // Valid positive-baseline examples keep compatible economic bases. Each operand
  // nevertheless owns its role, exact window, basis and source IDs independently.
  for (const [current, previous, suppliedRatio] of [[later, earlier, '0.25'], [earlier, prior, '1']]) {
    Object.assign(current.metrics.revenue_growth_yoy, { status: 'available', value: suppliedRatio, reason: null,
      formula: '(current - prior) / prior', revenue_basis: 'total_revenue',
      inputs: [operand('current', current), operand('prior', previous)],
      provenance: [structuredClone(current.metrics.revenue.provenance[0]), structuredClone(previous.metrics.revenue.provenance[0])] });
  }
  const laterYoY = later.metrics.revenue_growth_yoy, earlierYoY = earlier.metrics.revenue_growth_yoy;
  assert.deepEqual(laterYoY.provenance[1], shared);
  assert.deepEqual(earlierYoY.provenance[0], shared);
  assert.deepEqual(laterYoY.inputs.map(input => [input.role, input.period.fiscal_year, input.revenue_basis]),
    [['current', 2025, 'total_revenue'], ['prior', 2024, 'total_revenue']]);
  assert.deepEqual(earlierYoY.inputs.map(input => [input.role, input.period.fiscal_year, input.revenue_basis]),
    [['current', 2024, 'total_revenue'], ['prior', 2023, 'total_revenue']]);
  await app.release(app.request(2025), later); await app.release(app.request(2024), earlier);
  const row = app.row('Revenue YoY'), cells = row.querySelectorAll('td');
  assert.equal(cells.length, 2); assert.match(app.host.textContent, /comparison ready/);
  for (const [cell, result, previousYear, ratio, percent] of [
    [cells[0], later, 2024, '0.25', '25%'], [cells[1], earlier, 2023, '1', '100%'],
  ]) {
    assert.equal(cell.querySelector('.metric-value').textContent, percent);
    assert.match(cell.textContent, new RegExp(`Exact API value: ${ratio.replace('.', '\\.')} ratio`));
    const operandDetails = [...cell.querySelectorAll('details')].find(details => details.querySelector('summary')?.textContent.includes('operand periods and bases'));
    assert.ok(operandDetails);
    const operands = operandDetails.querySelectorAll('.details-body > p');
    assert.equal(operands.length, 2);
    for (const [index, role, year] of [[0, 'current', result.period.fiscal_year], [1, 'prior', previousYear]]) {
      assert.match(operands[index].textContent, new RegExp(`^${role} · revenue:`));
      assert.match(operands[index].textContent, new RegExp(`FY${year}`));
      assert.match(operands[index].textContent, /USD · Revenue basis: total_revenue/);
      assert.match(operands[index].textContent, new RegExp(`Facts: ${result.metrics.revenue_growth_yoy.inputs[index].fact_ids[0]}`));
    }
    assert.match(cell.textContent, new RegExp(`Fact ${shared.fact_id}`));
    assert.ok([...cell.querySelectorAll('a')].some(link => link.href === shared.sec_url));
  }
  assert.equal(app.changed.mock.callCount(), 0);
});

test('partial request failures publish only verified columns and never substitute another year', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  await app.release(app.request(2025), annual(2025));
  assert.equal(app.host.querySelector('table'), null, 'Wait for all selected requests');
  await app.release(app.request(2024), { detail: 'Period request failed.' }, '0', 503);
  assert.equal(app.host.querySelectorAll('tbody td').length, 22);
  assert.match(app.host.textContent, /Some annual periods could not be verified/);
  assert.match(app.row('Revenue').textContent, /Period request failed/);
  assert.match(app.row('Revenue').textContent, /\$5B/);
  assert.equal(app.requests.length, 3);
});

test('malformed selected-year bodies and missing pin headers remain unverified columns', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const malformed = annual(2025); malformed.metrics.revenue.formula = {};
  await app.release(app.request(2025), malformed); await app.release(app.request(2024), annual(2024), null);
  assert.match(app.host.textContent, /Annual period evidence could not be verified/);
  assert.match(app.host.textContent, /Published response version could not be verified/);
  assert.equal(app.host.querySelectorAll('.metric-value').length, 0);
});

test('mismatched publication hides every column and notifies the owning freshness scope once', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  await app.release(app.request(2025), annual(2025));
  await app.release(app.request(2024), annual(2024), '1');
  assert.equal(app.host.querySelector('table'), null); assert.equal(app.changed.mock.callCount(), 1);
  assert.match(app.host.textContent, /entire grid is hidden/);
  assert.equal(app.button().disabled, true);
  await app.render({ version: 1 });
  assert.equal(app.request().init.headers['X-FinLens-Data-Version'], '1');
  assert.equal(app.host.querySelectorAll('input:checked').length, 0);
});

test('conflicting fact identities across periods reject the entire grid', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const earlier = annual(2024);
  earlier.metrics.revenue.provenance[0].fact_id = annual(2025).metrics.revenue.provenance[0].fact_id;
  await app.release(app.request(2025), annual(2025)); await app.release(app.request(2024), earlier);
  assert.equal(app.host.querySelector('table'), null); assert.match(app.host.textContent, /evidence could not be verified/);
});

test('selection A -> B -> A discards pending responses even when fetch ignores cancellation', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const old = [app.request(2025), app.request(2024)];
  await app.toggle(2024); await app.toggle(2024);
  assert.ok(old.every(request => request.init.signal.aborted));
  await app.release(old[0], annual(2025)); await app.release(old[1], annual(2024));
  assert.equal(app.host.querySelector('table'), null);
  await app.compare();
  assert.notEqual(app.request(2025), old[0]);
  await app.release(app.request(2024), annual(2024)); await app.release(app.request(2025), annual(2025));
  assert.match(app.host.textContent, /comparison ready/);
});

test('company A -> B -> A rejects stale discovery and resets selections without cross-company requests', async ctx => {
  const app = await mount(ctx); const first = app.request();
  await app.render({ company: other }); const second = app.request();
  await app.render({ company }); const third = app.request();
  assert.notEqual(first, third); assert.equal(first.init.signal.aborted, true);
  assert.equal(second.init.signal.aborted, true);
  await app.release(first, annual(null)); await app.release(second, annual(null, other));
  assert.equal(app.host.querySelectorAll('input').length, 0);
  await app.release(third, annual(null)); assert.equal(app.host.querySelectorAll('input').length, 5);
  assert.equal(app.host.querySelectorAll('input:checked').length, 0);
});

test('pin invalidation and unmount abort pending requests and late mismatches cannot notify new scope', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.select(); await app.compare();
  const pending = [app.request(2025), app.request(2024)];
  await app.render({ version: null });
  assert.ok(pending.every(request => request.init.signal.aborted));
  for (const [index, req] of pending.entries()) await app.release(req, annual([2025, 2024][index]), '9');
  assert.equal(app.changed.mock.callCount(), 0); assert.equal(app.host.querySelector('table'), null);
  await app.render({ version: 2 }); const discovery = app.request();
  await app.unmount(); assert.equal(discovery.init.signal.aborted, true);
  await app.release(discovery, annual(null), '3'); assert.equal(app.changed.mock.callCount(), 0);
});

test('cancel discovery/comparison and refresh abort ownership and allow explicit retries', async ctx => {
  const app = await mount(ctx); const first = app.request();
  await app.click('Cancel annual comparison'); assert.equal(first.init.signal.aborted, true);
  await app.release(first, annual(null)); assert.equal(app.host.querySelectorAll('input').length, 0);
  await app.click('Refresh annual periods'); await app.discover(); await app.select(); await app.compare();
  const old = app.request(2025); await app.click('Cancel annual comparison');
  await app.release(old, annual(2025)); assert.equal(app.host.querySelector('table'), null);
  await app.compare(); await app.release(app.request(2025), annual(2025)); await app.release(app.request(2024), annual(2024));
  assert.ok(app.host.querySelector('table'));
  await app.click('Refresh annual periods'); assert.equal(app.host.querySelector('table'), null);
  assert.equal(app.host.querySelectorAll('input:checked').length, 0);
});

test('home connects the new grid inside the selected-company publication provider and links its section', () => {
  const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
  const provider = page.slice(page.indexOf('{company && <ResearchFreshness'), page.indexOf('</ResearchFreshness>}'));
  assert.match(provider, /<AnnualPeriodComparison company=\{company\} \/>/);
  assert.match(page, /href="#annual-period-title"/);
});
