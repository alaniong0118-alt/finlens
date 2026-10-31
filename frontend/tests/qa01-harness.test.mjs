import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const frontend = fileURLToPath(new URL('../', import.meta.url));
const cache = new Map();
function load(file) {
  const absolute = resolve(frontend, file);
  if (cache.has(absolute)) return cache.get(absolute);
  const exports = {}; cache.set(absolute, exports);
  const source = readFileSync(absolute, 'utf8').replaceAll('import.meta.url', JSON.stringify(pathToFileURL(absolute).href));
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  new Function('require', 'exports', output)(name => {
    if (!name.startsWith('@/') && !name.startsWith('.')) return require(name);
    const base = name.startsWith('@/') ? resolve(frontend, name.slice(2)) : resolve(dirname(absolute), name);
    return load(['.ts', '.tsx'].map(extension => base + extension).find(existsSync));
  }, exports);
  return exports;
}
const data = load('e2e/fixtures/data.ts');
const api = load('lib/finlens-api.ts');
const contract = load('lib/company-comparison.ts');
const presentation = load('lib/research.ts');
const { installIgnoredAbort } = load('e2e/fixtures/ignored-abort.ts');
const insights = load('lib/financial-insights.ts');
const { financialInsightsFixture } = load('e2e/fixtures/financial-insights.ts');
const { browserFinancialInsights } = load('e2e/fixtures/financial-insights-browser.ts');
const { Scenario } = load('e2e/fixtures/browser.ts');

// Exercise the actual browser helper without importing/registering Playwright
// tests. Synthetic rectangles verify its predicate and diagnostics, not layout.
const comparisonSpec = ts.createSourceFile('comparison.spec.ts',
  readFileSync(resolve(frontend, 'e2e/comparison.spec.ts'), 'utf8'), ts.ScriptTarget.Latest, true);
const readabilityHelper = comparisonSpec.statements.find(statement => ts.isFunctionDeclaration(statement)
  && statement.name?.text === 'expectComparisonTextReadable');
assert.ok(readabilityHelper, 'Expected the actual comparison readability helper');
const readabilityCode = ts.transpileModule(readabilityHelper.getText(comparisonSpec), {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText;
function readabilityFixture({ inline = true, visible = true, rect = {} } = {}) {
  const calls = [], messages = [];
  const textRect = { left: 110, right: 200, top: 350, bottom: 400, width: 90, height: 50, ...rect };
  const paragraph = { scrollIntoView: options => calls.push(['center-paragraph', JSON.parse(JSON.stringify(options))]) };
  const scroller = { clientLeft: 1, clientWidth: 244, scrollLeft: 0, scrollTop: 0,
    getBoundingClientRect: () => ({ left: 100, right: 346, top: -1000, bottom: 5000, width: 246, height: 6000 }) };
  const element = { matches: selector => { assert.equal(selector, 'p > span'); return inline; },
    closest: selector => selector === 'p' ? paragraph : selector === '.comparison-scroll' ? scroller : null,
    getBoundingClientRect: () => { calls.push(['measure-original']); return textRect; } };
  const locator = { scrollIntoViewIfNeeded: async () => { calls.push(['native-scroll']); },
    evaluate: async callback => callback(element) };
  const context = { innerWidth: 390, innerHeight: 844, scrollX: 0, scrollY: 9882,
    visualViewport: { offsetLeft: 0, offsetTop: 0, width: 390, height: 844, scale: 1 },
    getComputedStyle: () => ({ fontFamily: 'synthetic-font', fontSize: '13px', lineHeight: '22.75px',
      whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }),
    expect: (value, message) => ({
      toBeVisible: async () => { assert.equal(value, locator); calls.push(['visible']); assert.ok(visible, 'Hidden text must fail'); },
      toEqual: expected => { messages.push(message); assert.deepEqual(JSON.parse(JSON.stringify(value)), JSON.parse(JSON.stringify(expected)), message); },
    }) };
  runInNewContext(`${readabilityCode}\nglobalThis.checkReadability = expectComparisonTextReadable;`, context);
  return { run: () => context.checkReadability(locator), calls, messages, textRect };
}
test('QA-01 readability helper centers the containing paragraph and measures the original inline reason', async () => {
  const fixture = readabilityFixture(); await fixture.run();
  assert.deepEqual(fixture.calls, [['native-scroll'], ['center-paragraph', { block: 'center', inline: 'nearest', behavior: 'instant' }],
    ['visible'], ['measure-original']]);
});
test('QA-01 readability helper preserves native scrolling for existing block text', async () => {
  const fixture = readabilityFixture({ inline: false }); await fixture.run();
  assert.deepEqual(fixture.calls, [['native-scroll'], ['visible'], ['measure-original']]);
});
test('QA-01 readability helper accepts exact containment boundaries', async () => {
  await readabilityFixture({ rect: { left: 101, right: 345, top: 0, bottom: 844, width: 244, height: 844 } }).run();
});
for (const [name, rect] of [
  ['positiveWidth', { width: 0 }], ['positiveHeight', { height: 0 }],
  ['withinLeft', { left: 100.999 }], ['withinRight', { right: 345.001 }],
  ['withinTop', { top: -0.001 }], ['withinBottom', { bottom: 844.001 }],
]) test(`QA-01 readability helper still rejects ${name} without tolerance`, async () => {
  const fixture = readabilityFixture({ rect });
  await assert.rejects(fixture.run(), error => {
    const geometry = JSON.parse(fixture.messages[0].split('fully contained: ')[1]);
    assert.deepEqual(geometry.failedChecks, [name]); assert.equal(geometry.checks[name], false);
    return error.code === 'ERR_ASSERTION';
  });
});
test('QA-01 readability failures retain named rectangles, viewport, scroll, font and every failed inequality', async () => {
  const fixture = readabilityFixture({ rect: { right: 400, bottom: 845 } });
  await assert.rejects(fixture.run());
  const geometry = JSON.parse(fixture.messages[0].split('fully contained: ')[1]);
  assert.deepEqual(geometry.textRect, fixture.textRect);
  assert.equal(geometry.scrollerRect.left, 100);
  assert.deepEqual(geometry.clip, { left: 101, right: 345, top: 0, bottom: 844 });
  assert.deepEqual(geometry.failedChecks, ['withinRight', 'withinBottom']);
  assert.equal(geometry.viewport.height, 844); assert.equal(geometry.viewport.visual.height, 844);
  assert.equal(geometry.scroll.y, 9882); assert.equal(geometry.textStyle.fontFamily, 'synthetic-font');
});
test('QA-01 readability helper cannot make hidden text pass by centering it', async () => {
  const fixture = readabilityFixture({ visible: false });
  await assert.rejects(fixture.run(), /Hidden text must fail/);
  assert.equal(fixture.calls.some(([name]) => name === 'measure-original'), false);
});

const insightsRequest = (ticker = 'AAA', pin = '0', query = 'mode=discover', changes = {}) => ({
  path: `/companies/${ticker}/financials/insights`, ticker, pin, query: new URLSearchParams(query), method: 'GET', body: null, request: {}, ...changes,
});
const insightsIdentity = (ticker, pin, mode) => ({ ticker, cik: data.company(ticker).cik, pin,
  publication: { facts: pin, evidence: pin }, selection: mode === 'discover' ? { mode } : { mode, earlier: 2024, later: 2025 } });

// Run the serialized function exactly as addInitScript does. No module closure,
// browser, server or network is available in this VM.
function install(path) {
  const pending = [];
  const window = { fetch: (input, init) => new Promise(done => pending.push({ input, init, done })) };
  const context = { window, location: { origin: 'http://127.0.0.1:3107', href: 'http://127.0.0.1:3107/' }, URL, Request, Headers };
  runInNewContext(`(${installIgnoredAbort.toString()})(${JSON.stringify({ path })})`, context);
  return { window, pending };
}
for (const [name, path, pin, query, status] of [
  ['rapid company switch', '/companies/AAA/financials/summary', '0', '?period=quarter', 200],
  ['comparison cancellation', '/companies/AAA/financials/annual', '0', '?fiscal_year=2025', 200],
  ['obsolete publication 0 to 1', '/companies/AAA/financials/summary', '0', '?period=quarter', 409],
  ['obsolete publication 1 to 2', '/companies/AAA/financials/summary', '1', '?period=quarter', 409],
]) test(`QA-01 serialized ignored-abort helper: ${name} reaches the full production API URL`, async () => {
  const { window, pending } = install(path);
  const controller = new AbortController();
  const response = window.fetch(`/api/finlens${path}${query}`, { signal: controller.signal, headers: { 'X-FinLens-Data-Version': pin } });
  assert.equal(pending.length, 1);
  assert.equal(pending[0].init.signal, null);
  controller.abort();
  assert.equal(window.qaDelivered, 0);
  const body = new Response('{}', { status }); pending[0].done(body);
  assert.equal(await response, body);
  assert.equal(window.qaDelivered, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(window.qaDeliveries)), [{ path: `/api/finlens${path}`, query, pin, status, signalAborted: true }]);
});

test('QA-01 ignored-abort matching handles URL/Request inputs and leaves other routes and origins cancellable', async () => {
  for (const inputKind of ['URL', 'Request']) {
    const { window, pending } = install('/api/finlens/companies/AAA/financials/summary');
    const controller = new AbortController();
    const url = 'http://127.0.0.1:3107/api/finlens/companies/AAA/financials/summary?period=quarter';
    const input = inputKind === 'URL' ? new URL(url) : new Request(url, { signal: controller.signal, headers: { 'X-FinLens-Data-Version': '0' } });
    const response = window.fetch(input, inputKind === 'URL' ? { signal: controller.signal, headers: { 'X-FinLens-Data-Version': '0' } } : undefined);
    assert.equal(pending[0].init.signal, null); controller.abort(); pending[0].done(new Response('{}'));
    await response; assert.equal(window.qaDeliveries[0].signalAborted, true); assert.equal(window.qaDeliveries[0].pin, '0');
  }
  for (const url of ['/companies/AAA/financials/summary', '/api/finlens/companies/BBB/financials/summary', '/api/finlens/companies/AAA/freshness', 'https://example.invalid/api/finlens/companies/AAA/financials/summary']) {
    const { window, pending } = install('/companies/AAA/financials/summary');
    const controller = new AbortController(); const init = { signal: controller.signal };
    const response = window.fetch(url, init);
    assert.equal(pending[0].init, init); controller.abort(); pending[0].done(new Response('{}'));
    await response; assert.equal(window.qaDelivered, 0); assert.equal(pending[0].init.signal.aborted, true);
  }
  const { window, pending } = install('/companies/AAA/financials/summary');
  const controller = new AbortController(); controller.abort();
  const input = new Request('http://127.0.0.1:3107/api/finlens/companies/AAA/financials/summary', { signal: controller.signal });
  const response = window.fetch(input, { signal: null }); pending[0].done(new Response('{}'));
  await response; assert.equal(window.qaDeliveries[0].signalAborted, false);
});

test('QA-01 real API mismatch validation remains active behind the installed helper', async ctx => {
  for (const [pin, aborted] of [[0, true], [1, true], [0, false], [1, false]]) {
    const { window, pending } = install('/companies/AAA/financials/summary');
    const mock = ctx.mock.method(globalThis, 'fetch', window.fetch);
    let mismatches = 0;
    const controller = api.versionedController(pin, () => { mismatches++; });
    const request = api.getFinancialSummary('AAA', 'quarter', controller.signal, true);
    assert.equal(pending[0].input, '/api/finlens/companies/AAA/financials/summary?period=quarter');
    assert.equal(new Headers(pending[0].init.headers).get('X-FinLens-Data-Version'), String(pin));
    if (aborted) controller.abort();
    pending[0].done(new Response(JSON.stringify({ detail: 'Synthetic mismatch' }), { status: 409, headers: { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED', 'X-FinLens-Data-Version': String(pin + 1) } }));
    await assert.rejects(request);
    assert.equal(mismatches, aborted ? 0 : 1);
    assert.equal(window.qaDeliveries[0].signalAborted, aborted);
    mock.mock.restore();
  }
});

test('QA-01 synthetic annual responses pass the real validator with distinct issuers and years', () => {
  const expected = { AAA: ['5000000000', '4000000000'], BBB: ['9000000000', '7000000000'] };
  for (const c of data.companies) {
    contract.validateAnnualResponse(data.annual(c.ticker, null), c, null);
    for (const [index, year] of [2025, 2024].entries()) {
      const response = data.annual(c.ticker, year);
      contract.validateAnnualResponse(response, c, year);
      assert.equal(response.metrics.revenue.value, expected[c.ticker][index]);
      assert.equal(response.period.start, `${year}-01-01`); assert.equal(response.period.end, `${year}-12-31`);
      for (const point of Object.values(response.metrics)) for (const source of point.provenance) {
        assert.equal(source.company_cik, c.cik); assert.equal(source.period_start, point.period.start); assert.equal(source.period_end, point.period.end);
      }
      for (const mutate of [r => { r.company_cik = '0000000000'; }, r => { r.metrics.revenue.provenance[0].company_cik = '0000000000'; }, r => { r.metrics.revenue.period.kind = 'half_year'; }, r => { delete r.metrics.free_cash_flow; }]) {
        const invalid = structuredClone(response); mutate(invalid);
        assert.throws(() => contract.validateAnnualResponse(invalid, c, year));
      }
      assert.throws(() => contract.validateAnnualResponse(response, c, year === 2025 ? 2024 : 2025));
    }
  }
});

test('QA-01 snapshots/history have exact period-specific values, zero and unavailable observations', () => {
  assert.deepEqual([...data.metrics].sort(), presentation.METRIC_CATALOG.map(metric => metric.id).sort());
  for (const [kind, end, alpha, beta] of [
    ['quarter', '03-31', '$1B', '$2B'], ['half_year', '06-30', '$2.4B', '$4.2B'],
    ['nine_months', '09-30', '$3.7B', '$6.5B'], ['annual', '12-31', '$5B', '$9B'],
  ]) for (const [ticker, value] of [['AAA', alpha], ['BBB', beta]]) {
    const response = data.summary(ticker, kind);
    assert.equal(Object.keys(response.metrics).length, 15);
    assert.equal(presentation.formatMetric(response.metrics.revenue), value);
    assert.equal(response.period.end, `2025-${end}`);
    for (const metric of data.metrics) {
      const periodKind = ['total_assets', 'total_liabilities', 'cash_and_equivalents'].includes(metric) ? 'instant' : kind;
      const history = data.history(ticker, metric, periodKind);
      assert.equal(history.company_cik, data.company(ticker).cik); assert.equal(history.requested_period, periodKind);
      for (const point of history.history) {
        assert.equal(point.period.kind, periodKind);
        for (const source of point.provenance) {
          assert.equal(source.company_cik, history.company_cik); assert.equal(source.value, point.value);
          assert.equal(source.period_start, point.period.start); assert.equal(source.period_end, point.period.end);
        }
      }
    }
    for (const metric of ['revenue', 'operating_cash_flow', 'diluted_eps']) {
      const [missing, zero, current] = data.history(ticker, metric, kind).history;
      assert.equal(missing.value, null); assert.equal(missing.status, 'unavailable'); assert.ok(missing.reason); assert.deepEqual(missing.provenance, []);
      assert.equal(zero.value, '0'); assert.equal(zero.status, 'available');
      assert.equal(current.value, response.metrics[metric].value);
      assert.deepEqual([missing, zero, current].map(point => [point.period.start, point.period.end]), [2023, 2024, 2025].map(year => [`${year}-01-01`, `${year}-${end}`]));
    }
  }
  assert.equal(presentation.formatMetric(data.history('AAA', 'total_assets', 'instant').history[2]), '$750M');
});

test('QA-01 evidence fixtures pass real pin/identity checks; malformed identity stays rejected', async ctx => {
  for (const c of data.companies) for (const version of [0, 1]) {
    const payload = data.evidence(c.ticker, 'revenue', version);
    const mock = ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(payload), { headers: { 'X-FinLens-Data-Version': String(version) } }));
    const scope = () => api.versionedController(version, () => assert.fail('Unexpected invalidation')).signal;
    const result = await api.getCompanyContext(c.ticker, c.cik, 'revenue', scope());
    assert.equal(presentation.evidencePassages(result).length, 1);
    payload.citations[0].company_cik = '0000000000';
    await assert.rejects(() => api.getCompanyContext(c.ticker, c.cik, 'revenue', scope()), /Evidence does not match/);
    mock.mock.restore();
  }
});

test('QA-01 request allowlist preserves independent pins and rejects provider/unknown paths', () => {
  const scenario = new (load('e2e/fixtures/browser.ts').Scenario)({}, {});
  const req = (path, pin, query = '', method = 'GET', body = null, ticker = 'AAA') => ({ path, pin, query: new URLSearchParams(query), method, body, ticker, request: {} });
  for (const r of [req('/companies', undefined, '', 'GET', null, undefined), req('/companies/AAA/freshness', undefined), req('/companies/AAA/sources', '0'), req('/companies/BBB/financials/annual', '1', 'fiscal_year=2025', 'GET', null, 'BBB'), req('/companies/AAA/financials/summary', '0', 'period=quarter'), req('/companies/AAA/financials/metrics/revenue', '0', 'limit=12&period=annual'), req('/companies/AAA/research-answer', '0', '', 'POST', { question: 'revenue' })]) scenario.validateRequest(r);
  for (const r of [req('/companies/AAA/sources', undefined), req('/companies/AAA/sources', 'null'), req('/companies/AAA/sources', '1'), req('/companies/AAA/refresh', '0', '', 'POST'), req('/companies/AAA/financials/summary', '0', 'period=instant'), req('/companies/AAA/financials/metrics/unsupported', '0', 'limit=12&period=annual'), req('/companies/AAA/research-answer', '0', '', 'POST', { question: 'revenue', limit: 5 }), req('/companies/AAA/filings/0000900001-25-000001/answer', '0', '', 'POST', { question: 'revenue' })]) assert.throws(() => scenario.validateRequest(r));
  const old = req('/companies/AAA/financials/summary', '0', 'period=quarter');
  scenario.versions.AAA = 1; scenario.validateRequest(old);
  assert.deepEqual([scenario.defaultReply(old).status, scenario.defaultReply(old).version, scenario.defaultReply(old).code], [409, '1', 'DATA_VERSION_CHANGED']);
  assert.equal(scenario.versions.BBB, 1);
});

const comparisonRequest = (ticker, pin, query = 'fiscal_year=2025', suffix = 'financials/annual', changes = {}) => ({
  path: `/companies/${ticker}/${suffix}`, ticker, pin, query: new URLSearchParams(query), method: 'GET', body: null, request: {}, ...changes,
});

test('QA-01 opt-in comparison fixtures pass the actual annual validator with distinct identities and honest gaps', () => {
  const expected = { AAA: ['5000000000', '4000000000'], BBB: ['9000000000', '7000000000'], CCC: ['3000000000', '2500000000'], DDD: [null, null] };
  for (const issuer of data.comparisonCompanies) {
    contract.validateAnnualResponse(data.comparisonAnnual(issuer.ticker, null), issuer, null);
    for (const [index, year] of [2025, 2024].entries()) {
      const response = data.comparisonAnnual(issuer.ticker, year);
      assert.equal(contract.validateAnnualResponse(response, issuer, year), response);
      assert.equal(response.metrics.revenue.value, expected[issuer.ticker][index]);
      for (const point of Object.values(response.metrics)) for (const source of point.provenance) {
        assert.equal(source.company_cik, issuer.cik);
        assert.equal(source.value, point.value);
        assert.equal(source.period_start, response.period.start); assert.equal(source.period_end, response.period.end);
        assert.ok(source.accession_number.startsWith(`${issuer.cik}-`));
        assert.equal(new URL(source.sec_url).hostname, 'www.sec.gov');
      }
    }
  }
  const alpha = data.comparisonAnnual('AAA', 2025), beta = data.comparisonAnnual('BBB', 2025);
  assert.equal(contract.reportingWindowsDiffer([alpha, beta]), true);
  assert.equal(contract.metricComparability('revenue', [alpha, beta]).basesDiffer, true);
  assert.equal(data.comparisonAnnual('CCC', 2025).metrics.revenue.revenue_basis, undefined);
  assert.equal(contract.metricComparability('revenue', [data.comparisonAnnual('CCC', 2025)]).basisUnknown, true);
  const delta = data.comparisonAnnual('DDD', 2025);
  assert.equal(delta.period, null); assert.equal(delta.period_reason, data.comparisonPeriodReason);
  assert.ok(Object.values(delta.metrics).every(p => p.status === 'unavailable' && p.value === null && p.period === null && p.provenance.length === 0));
  assert.equal(alpha.metrics.gross_margin.status, 'unavailable');
  assert.equal(alpha.metrics.gross_margin.reason, data.comparisonUnknownReason);
  assert.equal(beta.metrics.gross_margin.status, 'not_applicable');
  assert.throws(() => contract.validateAnnualResponse(data.comparisonAnnual('CCC', 2025), data.comparisonCompany('DDD'), 2025));
  alpha.metrics.gross_margin.reason = 'mutated test response';
  assert.equal(data.comparisonAnnual('AAA', 2025).metrics.gross_margin.reason, data.comparisonUnknownReason);
  assert.throws(() => data.comparisonAnnual('EEE', 2025));
  assert.throws(() => data.comparisonAnnual('CCC', 2023));
});

test('QA-01 comparison inventory is opt-in per scenario and cannot reset recorded traffic or default behavior', () => {
  const ordinary = new Scenario({}, {}), enabled = new Scenario({}, {});
  const catalog = structuredClone(ordinary.defaultReply({ path: '/companies' }).body);
  const pins = { ...ordinary.versions }, annual = structuredClone(data.annual('AAA', 2025));
  enabled.enableFourCompanyComparison();
  assert.deepEqual(ordinary.defaultReply({ path: '/companies' }).body, catalog);
  assert.deepEqual(data.companies, catalog); assert.deepEqual(ordinary.versions, pins);
  assert.deepEqual(data.annual('AAA', 2025), annual);
  assert.equal(enabled.defaultReply({ path: '/companies' }).body.length, 4);
  assert.throws(() => data.company('CCC')); assert.throws(() => data.annual('CCC', 2025));
  ordinary.versions.CCC = 4; // A pin alone must not grant catalog/route admission.
  assert.throws(() => ordinary.validateRequest(comparisonRequest('CCC', '4')));
  assert.throws(() => enabled.enableFourCompanyComparison());
  const late = new Scenario({}, {}); late.ledger.push(comparisonRequest('AAA', '0'));
  assert.throws(() => late.enableFourCompanyComparison());
  assert.equal(late.ledger.length, 1); assert.deepEqual(late.versions, pins);
});

test('QA-01 extra comparison issuers admit only exact freshness/annual routes and their independent current pins', () => {
  const scenario = new Scenario({}, {}); scenario.enableFourCompanyComparison();
  for (const [ticker, pin, otherPin] of [['CCC', '4', '7'], ['DDD', '7', '4']]) {
    scenario.validateRequest(comparisonRequest(ticker, undefined, '', 'freshness'));
    for (const query of ['', 'fiscal_year=2025', 'fiscal_year=2024']) {
      const current = comparisonRequest(ticker, pin, query);
      scenario.validateRequest(current);
      contract.validateAnnualResponse(scenario.defaultReply(current).body, data.comparisonCompany(ticker), query ? Number(new URLSearchParams(query).get('fiscal_year')) : null);
    }
    for (const invalid of [undefined, null, '', 'null', '0', '1', otherPin, `0${pin}`, `${pin}.0`, `+${pin}`, `${pin} `, '-1']) {
      assert.throws(() => scenario.validateRequest(comparisonRequest(ticker, invalid)), `${ticker} must reject pin ${invalid}`);
    }
    for (const request of [
      comparisonRequest(ticker, pin, 'fiscal_year=2023'), comparisonRequest(ticker, pin, 'fiscal_year=2025&fiscal_year=2025'),
      comparisonRequest(ticker, pin, 'period=annual'), comparisonRequest(ticker, pin, '', 'sources'),
      comparisonRequest(ticker, pin, 'period=annual', 'financials/summary'), comparisonRequest(ticker, pin, 'mode=discover', 'financials/insights'),
      comparisonRequest(ticker, pin, 'limit=5&q=test', 'context'), comparisonRequest(ticker, pin, '', 'research-answer', { method: 'POST', body: { question: 'test' } }),
      comparisonRequest(ticker, pin, '', 'refresh', { method: 'POST' }), comparisonRequest(ticker, pin, '', 'anything'),
      comparisonRequest(ticker, pin, '', 'freshness'), comparisonRequest(ticker, undefined, 'unexpected=1', 'freshness'),
      comparisonRequest(ticker, pin, 'fiscal_year=2025', 'financials/annual', { method: 'POST' }),
      comparisonRequest(ticker, pin, 'fiscal_year=2025', 'financials/annual', { body: {} }),
    ]) assert.throws(() => scenario.validateRequest(request), request.path);
    assert.throws(() => scenario.defaultReply(comparisonRequest(ticker, otherPin)), 'Default extra-issuer reply also rejects a mismatched pin');
  }
  scenario.versions.EEE = 9;
  assert.throws(() => scenario.validateRequest(comparisonRequest('EEE', '9')));
  // Extra issuer admission cannot change the existing AAA/BBB stale-pin policy.
  const beta = comparisonRequest('BBB', '0'); scenario.validateRequest(beta);
  assert.deepEqual(scenario.defaultReply(beta), { status: 409, code: 'DATA_VERSION_CHANGED', version: '1' });
});

test('QA-01 installed opt-in comparison routes return independent headers and block pin reuse without concealing requests', async () => {
  let intercept;
  const context = { on() {}, async routeWebSocket() {}, async route(pattern, handler) { intercept = handler; } };
  const scenario = new Scenario(context, { on() {} }); scenario.enableFourCompanyComparison(); await scenario.install();
  async function deliver(ticker, suffix, pin) {
    const result = {};
    const request = { url: () => `http://127.0.0.1:3107/api/finlens/companies/${ticker}/${suffix}`, method: () => 'GET',
      headers: () => pin === undefined ? {} : { 'x-finlens-data-version': pin }, postData: () => null, postDataJSON: () => null };
    await intercept({ request: () => request, async fulfill(reply) { result.reply = reply; }, async abort(reason) { result.abort = reason; } });
    return result;
  }
  for (const [ticker, pin] of [['AAA', '0'], ['BBB', '1'], ['CCC', '4'], ['DDD', '7']]) {
    const annual = await deliver(ticker, 'financials/annual?fiscal_year=2025', pin);
    assert.equal(annual.reply.status, 200); assert.equal(annual.reply.headers['X-FinLens-Data-Version'], pin);
    contract.validateAnnualResponse(JSON.parse(annual.reply.body), data.comparisonCompany(ticker), 2025);
    if (ticker === 'CCC' || ticker === 'DDD') {
      const fresh = await deliver(ticker, 'freshness');
      assert.equal(JSON.parse(fresh.reply.body).data_version, Number(pin));
      assert.equal(fresh.reply.headers['X-FinLens-Data-Version'], undefined);
    }
  }
  assert.equal(scenario.ledger.length, 6); assert.deepEqual(scenario.violations, []);
  for (const [ticker, suffix, pin] of [['CCC', 'financials/annual?fiscal_year=2025', '7'], ['DDD', 'financials/annual?fiscal_year=2025', '4'],
    ['CCC', 'financials/summary?period=annual', '4'], ['EEE', 'financials/annual?fiscal_year=2025', '4']]) {
    assert.equal((await deliver(ticker, suffix, pin)).abort, 'blockedbyclient');
  }
  assert.equal(scenario.ledger.length, 10); assert.equal(scenario.violations.length, 4);
});

function verifyInsightsFixtureChecksum(bytes) {
  // Accept only LF or CRLF representation changes. Preserve every other byte;
  // never decode/re-encode, trim, or derive the expected digest from this input.
  const canonical = Buffer.alloc(bytes.length); let length = 0;
  for (let index = 0; index < bytes.length; index++) {
    if (bytes[index] === 13) {
      assert.equal(bytes[index + 1], 10, 'Unexpected standalone carriage return in insights fixture');
    } else canonical[length++] = bytes[index];
  }
  const lf = canonical.subarray(0, length);
  assert.equal(createHash('sha256').update(lf).digest('hex'), 'afad566f1ee89ba285f51559bc60ce439d50d2580327ffe1776e2a02ef35b27b', 'Canonical LF insights fixture checksum');
  return lf;
}

test('QA-01 insights checksum accepts the canonical LF representation', () => {
  const lf = Buffer.from(readFileSync(resolve(frontend, 'e2e/fixtures/financial-insights.ts'), 'utf8').replaceAll('\r\n', '\n'));
  assert.deepEqual(verifyInsightsFixtureChecksum(lf), lf);
});

test('QA-01 insights checksum accepts equivalent CRLF without changing content', () => {
  const text = readFileSync(resolve(frontend, 'e2e/fixtures/financial-insights.ts'), 'utf8').replaceAll('\r\n', '\n');
  const crlf = Buffer.from(text.replaceAll('\n', '\r\n')), before = Buffer.from(crlf);
  assert.deepEqual(verifyInsightsFixtureChecksum(crlf), Buffer.from(text));
  assert.deepEqual(crlf, before);
});

test('QA-01 insights checksum rejects a modified non-newline byte', () => {
  const mutated = Buffer.from(readFileSync(resolve(frontend, 'e2e/fixtures/financial-insights.ts')));
  mutated[0] ^= 1;
  assert.throws(() => verifyInsightsFixtureChecksum(mutated), /Canonical LF insights fixture checksum/);
});

test('QA-01 insights checksum rejects standalone CR and malformed CRCRLF or LFCR', () => {
  const lf = Buffer.from(readFileSync(resolve(frontend, 'e2e/fixtures/financial-insights.ts'), 'utf8').replaceAll('\r\n', '\n'));
  const newline = lf.indexOf(10); assert.ok(newline >= 0);
  for (const malformed of [
    Buffer.concat([Buffer.from('\r'), lf]), Buffer.concat([lf, Buffer.from('\r')]),
    Buffer.concat([lf.subarray(0, newline), Buffer.from('\r\r\n'), lf.subarray(newline + 1)]),
    Buffer.concat([lf.subarray(0, newline), Buffer.from('\n\r'), lf.subarray(newline + 1)]),
  ]) assert.throws(() => verifyInsightsFixtureChecksum(malformed), /Unexpected standalone carriage return/);
});

test('QA-01 insights rebasing preserves the committed fixture content and original graph', () => {
  const bytes = readFileSync(resolve(frontend, 'e2e/fixtures/financial-insights.ts'));
  verifyInsightsFixtureChecksum(bytes);
  const original = financialInsightsFixture();
  for (const [ticker, pin] of [['AAA', 0], ['BBB', 1]]) {
    const body = browserFinancialInsights(ticker, pin, 'compare');
    assert.deepEqual(body.evidence.map(n => [n.ref.key, n.ref.category, n.edges.map(e => e.key)]),
      original.evidence.map(n => [n.ref.key, n.ref.category, n.edges.map(e => e.key)]));
    assert.deepEqual(body.statements.map(s => [s.key, s.text, s.financial.map(r => r.key), s.diagnostic.map(r => r.key)]),
      original.statements.map(s => [s.key, s.text, s.financial.map(r => r.key), s.diagnostic.map(r => r.key)]));
    for (const metric of insights.INSIGHT_METRICS) for (const side of ['earlier', 'later']) {
      for (const field of ['value', 'formula', 'status']) assert.equal(body.comparisons[metric][side][field], original.comparisons[metric][side][field]);
    }
    for (const metric of insights.INSIGHT_METRICS) for (const field of ['absolute_change', 'percentage_change', 'percentage_status', 'percentage_reason', 'direction', 'formula', 'status', 'reason']) {
      assert.equal(body.comparisons[metric][field], original.comparisons[metric][field]);
    }
    assert.equal(body.evidence.filter(n => n.ref.category === 'F').length, 45);
    assert.equal(body.evidence.filter(n => n.ref.category === 'D').length, 55);
    body.evidence[0].ref.scope = 'changed clone';
    assert.equal(browserFinancialInsights(ticker, pin, 'compare').evidence[0].ref.scope, `${data.company(ticker).cik}:${pin}:${pin}:${pin}:2024:2025`);
  }
  assert.deepEqual(financialInsightsFixture(), original);
  for (const [ticker, version, mode] of [['AAA', 1, 'discover'], ['AAA', -0, 'discover'], ['BBB', 0, 'compare'], ['TEST', 0, 'discover'], ['AAA', 0, 'unknown']]) {
    assert.throws(() => browserFinancialInsights(ticker, version, mode));
  }
});

for (const [ticker, pin] of [['AAA', 0], ['BBB', 1]]) for (const mode of ['discover', 'compare']) {
  test(`QA-01 adapted insights admit exact ${ticker}/${pin}/${mode} identity and complete references`, async () => {
    const body = browserFinancialInsights(ticker, pin, mode), identity = insightsIdentity(ticker, pin, mode);
    await insights.preflightInsightsJson(JSON.stringify(body));
    const admitted = await insights.validateInsights(body, identity);
    const prepared = await insights.prepareInsights(admitted, new insights.InsightBudget());
    assert.deepEqual([body.ticker, body.company_name, body.company_cik, body.data_version, body.facts_version, body.evidence_version],
      [ticker, data.company(ticker).name, data.company(ticker).cik, pin, pin, pin]);
    assert.deepEqual(body.fiscal_years, [2025, 2024]);
    const scope = `${identity.cik}:${pin}:${pin}:${pin}:${mode === 'discover' ? 'None:None' : '2024:2025'}`;
    assert.equal(body.scope, scope);
    for (const node of body.evidence) {
      assert.equal(node.ref.scope, scope);
      for (const edge of node.edges) assert.equal(edge.scope, scope);
      if (node.ref.kind === 'source') {
        assert.equal(node.data.company_cik, identity.cik);
        assert.match(node.data.accession_number, new RegExp(`^${identity.cik}-(25|26)-100001$`));
        assert.equal(node.data.sec_url, `https://www.sec.gov/Archives/edgar/data/${Number(identity.cik)}/${node.data.accession_number.replaceAll('-', '')}/${node.data.accession_number}-index.html`);
      }
    }
    for (const statement of body.statements) for (const ref of [...statement.financial, ...statement.diagnostic]) assert.equal(ref.scope, scope);
    if (mode === 'discover') {
      assert.equal(prepared.initial.completeness, null);
      assert.deepEqual(prepared.initial.collections, [{ id: 'F', pages: 0, records: 0 }, { id: 'D', pages: 0, records: 0 }]);
    } else {
      assert.equal(prepared.initial.completeness, 'complete');
      assert.deepEqual([body.comparisons.revenue.earlier.value, body.comparisons.revenue.later.value], ['100', '120']);
      assert.deepEqual([body.comparisons.free_cash_flow.earlier.value, body.comparisons.free_cash_flow.later.value], ['10', '15']);
      for (const collection of prepared.initial.collections) {
        assert.ok(collection.pages > 1);
        for (const page of prepared.pages.get(collection.id)) {
          assert.ok(page.length > 0 && page.length <= 25);
          for (const index of page) for (const link of prepared.record(index).links) {
            assert.ok(prepared.pages.get(link.collection)[link.page].some(i => prepared.record(i).ref.key === link.key));
          }
        }
      }
    }
  });
}

for (const [label, mutate] of [
  ['nested provenance CIK', r => { r.comparisons.revenue.earlier.provenance[0].company_cik = '0000000001'; }],
  ['raw source CIK', r => { r.evidence.find(n => n.ref.kind === 'source').data.company_cik = '0000000001'; }],
  ['source URL', r => { r.comparisons.revenue.earlier.provenance[0].sec_url = 'https://www.sec.gov/Archives/edgar/data/1/wrong'; }],
  ['graph edge scope', r => { r.evidence.find(n => n.edges.length).edges[0].scope = 'wrong'; }],
  ['statement target scope', r => { r.statements[0].financial[0].scope = 'wrong'; }],
  ['publication header/body identity', r => { r.data_version++; }],
  ['facts publication identity', r => { r.facts_version = 0; }],
]) test(`QA-01 real insights admission rejects invalid ${label}`, async () => {
  const body = browserFinancialInsights('BBB', 1, 'compare'); mutate(body);
  await assert.rejects(insights.validateInsights(body, insightsIdentity('BBB', 1, 'compare')));
});

test('QA-01 insights admission accepts only the two exact query forms and independent canonical pins', () => {
  const scenario = new Scenario({}, {});
  for (const [ticker, pin] of [['AAA', '0'], ['BBB', '1']]) for (const query of [
    'mode=discover', 'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025',
    'later_fiscal_year=2025&mode=compare&earlier_fiscal_year=2024',
  ]) scenario.validateRequest(insightsRequest(ticker, pin, query));
  for (const query of [
    '', 'mode=unknown', 'mode=compare', 'mode=discover&mode=discover', 'mode=discover&extra=1',
    'mode=discover&earlier_fiscal_year=2024', 'mode=compare&earlier_fiscal_year=2025&later_fiscal_year=2024',
    'mode=compare&earlier_fiscal_year=2023&later_fiscal_year=2025', 'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2024',
    'mode=compare&earlier_fiscal_year=02024&later_fiscal_year=2025', 'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2026',
    'mode=compare&earlier_fiscal_year=2024&earlier_fiscal_year=2024&later_fiscal_year=2025',
    'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025&later_fiscal_year=2025',
    'mode=compare&mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025',
    'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025&extra=1',
  ]) assert.throws(() => scenario.validateRequest(insightsRequest('AAA', '0', query)), query);
  for (const pin of [undefined, null, 0, '', 'null', '-1', '-0', '00', '0.0', '0\n', ' 0', '1', '9007199254740992']) {
    assert.throws(() => scenario.validateRequest(insightsRequest('AAA', '0', 'mode=discover', { pin })), String(pin));
  }
  for (const changes of [
    { method: 'POST' }, { method: 'HEAD' }, { method: 'PUT' }, { body: {} }, { body: '' },
    { ticker: 'TEST' }, { ticker: undefined }, { path: '/companies/BBB/financials/insights' },
    { path: '/companies/AAA/financials/insights/' }, { path: '/companies/AAA/financials/insights/extra' },
    { path: '/companies/AAA/financials/unknown' },
    { request: { postData: () => 'null' } }, { request: { postData: () => '' } },
  ]) assert.throws(() => scenario.validateRequest(insightsRequest('AAA', '0', 'mode=discover', changes)));
});

test('QA-01 insights obsolete pins return independent 409 before fixture generation; recovery versions stay bounded', () => {
  const scenario = new Scenario({}, {});
  const old = insightsRequest('BBB', '0'); scenario.validateRequest(old);
  assert.deepEqual(scenario.defaultReply(old), { status: 409, code: 'DATA_VERSION_CHANGED', version: '1' });
  for (const version of [1, 2]) {
    scenario.versions.AAA = version;
    const obsolete = insightsRequest('AAA', String(version - 1)); scenario.validateRequest(obsolete);
    assert.deepEqual(scenario.defaultReply(obsolete), { status: 409, code: 'DATA_VERSION_CHANGED', version: String(version) });
    const current = insightsRequest('AAA', String(version)); scenario.validateRequest(current);
    assert.deepEqual(scenario.defaultReply(current), { status: 503, code: 'QA01_INSIGHTS_PUBLICATION_UNAVAILABLE', version: String(version) });
    assert.deepEqual(scenario.defaultReply({ ...current, path: '/companies/AAA/financials/summary', query: new URLSearchParams('period=quarter') }).body, data.summary('AAA', 'quarter'));
  }
  assert.equal(scenario.versions.BBB, 1);
});

test('QA-01 capabilities satisfy the actual disabled-AI client contract', async ctx => {
  const scenario = new Scenario({}, {}), reply = scenario.defaultReply({ path: '/capabilities' });
  assert.deepEqual(reply.body, { research_mode: true, ai_analysis_configured: false, ai_analysis_enabled: false, server_profile: 'sec_readonly' });
  const mock = ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(reply.body)));
  assert.deepEqual(await api.getCapabilities(), reply.body);
  mock.mock.restore();
});

for (const version of [1, 2]) test(`QA-01 current insights 503 preserves AAA/${version} snapshot and never reconciles or retries`, async ctx => {
  // Offline protocol seam uses the committed runtime; no global Worker is
  // replaced and the browser spec continues to use the native constructor.
  const runtime = load('lib/financial-insights.worker.ts');
  const listeners = new Map(); let terminated = 0, changed = 0;
  const workerRuntime = runtime.createInsightsWorkerRuntime({ postMessage(message) {
    const copy = structuredClone(message);
    queueMicrotask(() => { for (const listener of listeners.get('message') ?? []) listener({ data: copy }); });
  } });
  const worker = {
    postMessage(message, transfer = []) {
      const copy = structuredClone(message, { transfer }); queueMicrotask(() => { void workerRuntime.handle(copy); });
    },
    addEventListener(type, listener) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(listener); },
    removeEventListener(type, listener) { listeners.get(type)?.delete(listener); },
    terminate() { terminated++; workerRuntime.dispose(); },
  };
  const scenario = new Scenario({}, {}); scenario.versions.AAA = version;
  const calls = [];
  async function transport(url, init = {}) {
    const parsed = new URL(url, 'http://127.0.0.1:3107');
    assert.equal(parsed.origin, 'http://127.0.0.1:3107');
    const request = { path: parsed.pathname.slice('/api/finlens'.length), ticker: 'AAA', method: init.method ?? 'GET',
      pin: new Headers(init.headers).get('X-FinLens-Data-Version'), query: parsed.searchParams, body: null, request: {} };
    scenario.validateRequest(request); calls.push(request);
    const reply = scenario.defaultReply(request);
    return new Response(JSON.stringify(reply.body ?? { detail: 'Synthetic failure' }), { status: reply.status ?? 200,
      headers: { 'X-FinLens-Data-Version': reply.version ?? String(scenario.versions.AAA), ...(reply.code ? { 'X-FinLens-Error-Code': reply.code } : {}) } });
  }
  const mock = ctx.mock.method(globalThis, 'fetch', transport);
  const controller = () => api.versionedController(version, () => { changed++; });
  const before = await api.getFinancialSummary('AAA', 'quarter', controller().signal, true);
  const panel = new insights.InsightsPanel({ worker: () => worker, fetch: transport });
  try {
    await assert.rejects(api.getFinancialInsights(data.company('AAA'), { mode: 'discover' }, controller().signal, panel, () => true),
      error => error.code === 'QA01_INSIGHTS_PUBLICATION_UNAVAILABLE' && error.status === 503);
    const after = await api.getFinancialSummary('AAA', 'quarter', controller().signal, true);
    assert.deepEqual(before, data.summary('AAA', 'quarter')); assert.deepEqual(after, before);
    assert.equal(calls.filter(r => r.path.endsWith('/insights')).length, 1);
    assert.equal(calls.length, 3); assert.ok(calls.every(r => r.pin === String(version)));
    assert.equal(changed, 0); assert.equal(scenario.versions.AAA, version); assert.equal(terminated, 1);
    assert.ok([...listeners.values()].every(group => group.size === 0));
    assert.equal(workerRuntime.inspect().nodes, 0);
  } finally { panel.dispose(); mock.mock.restore(); }
});

test('QA-01 browser fixed values and FCF-to-CapEx navigation match production presentation', async () => {
  const admitted = await insights.validateInsights(browserFinancialInsights('AAA', 0, 'compare'), insightsIdentity('AAA', 0, 'compare'));
  const prepared = await insights.prepareInsights(admitted, new insights.InsightBudget());
  for (const [metric, earlier, later] of [
    ['revenue', '100 USD', '120 USD'], ['operating_income', '10 USD', '18 USD'], ['net_income', '8 USD', '12 USD'],
    ['operating_margin', '10%', '15%'], ['net_margin', '8%', '10%'], ['operating_cash_flow', '14 USD', '20 USD'], ['free_cash_flow', '10 USD', '15 USD'],
  ]) assert.deepEqual(['earlier', 'later'].map(side => prepared.initial.metrics.find(m => m.metric === metric && m.side === side).formatted), [earlier, later]);
  const record = key => prepared.record(prepared.nodes.findIndex(node => node.ref.key === key));
  const statement = prepared.initial.statements.find(s => s.key === 'value:free_cash_flow:later');
  const target = statement.targets[0];
  assert.ok(prepared.pages.get(target.collection)[target.page].some(index => prepared.record(index).ref.key === target.key));
  const window = '2025-01-01/2025-12-31/annual';
  const keys = [`F|observation|free_cash_flow|later||${window}|`, `F|operand|free_cash_flow|later|capital_expenditures|${window}|`,
    `F|observation|capital_expenditures|later||${window}|`, 'F|source|||||10'];
  assert.equal(target.key, keys[0]);
  for (let i = 0; i < keys.length - 1; i++) assert.ok(record(keys[i]).links.some(link => link.key === keys[i + 1]));
  assert.equal(new Map(record(keys[2]).fields).get('data.canonical.provenance[0].fact_id'), 10);
  const source = new Map(record(keys[3]).fields);
  assert.equal(source.get('data.company_cik'), '0000900001'); assert.equal(source.get('data.value'), '5');
  assert.equal(source.get('data.accession_number'), '0000900001-26-100001');
  assert.equal(source.get('data.sec_url'), 'https://www.sec.gov/Archives/edgar/data/900001/000090000126100001/0000900001-26-100001-index.html');
});

for (const [ticker, version, terminal] of [
  ['AAA', 0, 'Choose Compare annual periods to request this comparison.'],
  ['BBB', 1, 'Choose Compare annual periods to request this comparison.'],
  ['AAA', 1, 'Annual financial insights could not be loaded or verified. Retry explicitly.'],
  ['AAA', 2, 'Annual financial insights could not be loaded or verified. Retry explicitly.'],
]) test(`QA-01 readiness waits only for terminal discovery for ${ticker}/${version}`, async () => {
  // Locator protocol stub only: invokes the real readiness method and installed
  // assertion library without a browser, DOM, server or HTTP. It tests the added
  // synchronization, not whether the application reaches this UI in Chromium.
  let enter, release;
  const entered = new Promise(done => { enter = done; }), barrier = new Promise(done => { release = done; });
  const checks = [];
  class Locator {
    _apiName = 'Locator';
    constructor(name) { this.name = name; }
    getByRole(role, options) { return new Locator(options.name); }
    locator(selector) { assert.equal(this.name, 'Annual financial insights'); assert.equal(selector, '.insights-status'); return new Locator(selector); }
    async _expect(expression, options) {
      checks.push([this.name, expression]);
      if (expression === 'to.have.text') {
        assert.equal(this.name, '.insights-status'); assert.equal(options.expectedText[0].string, terminal);
        assert.equal(options.timeout, 35000); enter(); await barrier;
      } else if (expression === 'to.have.value') assert.equal(options.expectedText[0].string, ticker);
      else assert.ok(['to.be.visible', 'to.be.enabled'].includes(expression));
      return { matches: true, received: expression === 'to.have.value' ? ticker : terminal, log: [] };
    }
  }
  const page = { getByRole(role, options) { return new Locator(options.name); } };
  const scenario = new Scenario({}, page); scenario.versions[ticker] = version;
  const unrelated = scenario.hold(() => false);
  let ready = false, unrelatedReleased = false;
  void unrelated.promise.then(() => { unrelatedReleased = true; });
  const pending = scenario.ready(ticker).then(() => { ready = true; });
  await entered; assert.equal(ready, false); release(); await pending;
  assert.equal(ready, true); assert.equal(unrelatedReleased, false);
  assert.deepEqual(checks.map(([, expression]) => expression), ['to.have.value', 'to.be.visible', 'to.be.enabled', 'to.have.text']);
  assert.deepEqual(scenario.ledger, []); scenario.releaseAll();
});

test('QA-01 installed HTTP/WebSocket routes preserve fail-closed boundaries with insights', async () => {
  let intercept, websocket;
  const context = { on() {}, async routeWebSocket(pattern, callback) { websocket = callback; }, async route(pattern, callback) { intercept = callback; } };
  const scenario = new Scenario(context, { on() {} }); await scenario.install();
  async function deliver(url, { method = 'GET', pin, body = null, rawBody } = {}) {
    const result = {};
    const request = { url: () => url, method: () => method, headers: () => pin === undefined ? {} : { 'x-finlens-data-version': pin },
      postData: () => rawBody === undefined ? body === null ? null : JSON.stringify(body) : rawBody, postDataJSON: () => body };
    await intercept({ request: () => request, async fulfill(reply) { result.reply = reply; }, async abort(reason) { result.abort = reason; }, async continue() { result.continued = true; } });
    return result;
  }
  for (const [ticker, pin] of [['AAA', '0'], ['BBB', '1']]) for (const mode of ['discover', 'compare']) {
    const query = mode === 'discover' ? 'mode=discover' : 'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025';
    const result = await deliver(`http://127.0.0.1:3107/api/finlens/companies/${ticker}/financials/insights?${query}`, { pin });
    assert.equal(result.reply.status, 200); assert.equal(result.reply.headers['X-FinLens-Data-Version'], pin);
    await insights.validateInsights(JSON.parse(result.reply.body), insightsIdentity(ticker, Number(pin), mode));
  }
  assert.deepEqual(scenario.violations, []);
  for (const url of ['http://127.0.0.1:3108/__qa_status', 'https://www.sec.gov/',
    'http://127.0.0.1:3107/api/finlens/companies/AAA/financials/insights?mode=discover&mode=discover',
    'http://127.0.0.1:3107/api/finlens/companies/AAA/financials/anything',
    'http://127.0.0.1:3107/api/finlens/companies/AAA/refresh',
    'http://127.0.0.1:3107/api/finlens/companies/AAA/answer', 'http://127.0.0.1:3107/unapproved']) {
    assert.equal((await deliver(url, { pin: '0' })).abort, 'blockedbyclient');
  }
  assert.equal(scenario.violations.length, 7);
  assert.equal((await deliver('http://127.0.0.1:3107/api/finlens/companies/AAA/financials/insights?mode=discover', { pin: '0', rawBody: 'null' })).abort, 'blockedbyclient');
  assert.equal((await deliver('http://127.0.0.1:3107/_next/static/chunks/financial-insights.worker.js')).continued, true);
  let connected = 0, closed = 0;
  for (const url of ['ws://127.0.0.1:3107/_next/webpack-hmr', 'ws://127.0.0.1:3107/other', 'wss://example.invalid/socket']) {
    websocket({ url: () => url, connectToServer() { connected++; }, close() { closed++; } });
  }
  assert.equal(connected, 1); assert.equal(closed, 2);
});
