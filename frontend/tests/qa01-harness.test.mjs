import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const frontend = fileURLToPath(new URL('../', import.meta.url));
const cache = new Map();
function load(file) {
  const absolute = resolve(frontend, file);
  if (cache.has(absolute)) return cache.get(absolute);
  const exports = {}; cache.set(absolute, exports);
  const output = ts.transpileModule(readFileSync(absolute, 'utf8'), {
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
