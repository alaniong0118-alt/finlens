import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

// Exercise the exact test-local recorder, with fake Playwright request events.
const source = readFileSync(new URL('../e2e/fixtures/annual-period-lifecycle.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const exported = {};
new Function('exports', compiled)(exported);
const { AnnualLifecycle, annualSignature } = exported;

function request(path = '/companies/AAA/freshness', { method = 'GET', pin, query = '', body = null, rawBody, origin = 'http://127.0.0.1:3107' } = {}) {
  const url = `${origin}/api/finlens${path}${query ? `?${query}` : ''}`;
  return { url: () => url, method: () => method, headers: () => pin === undefined ? {} : { 'x-finlens-data-version': pin },
    postData: () => rawBody === undefined ? (body === null ? null : JSON.stringify(body)) : rawBody,
    failure: () => ({ errorText: 'net::ERR_ABORTED' }) };
}
function routed(req) {
  const url = new URL(req.url());
  return { request: req, method: req.method(), path: url.pathname.slice('/api/finlens'.length),
    pin: req.headers()['x-finlens-data-version'], query: url.searchParams,
    body: req.postData() === null ? null : JSON.parse(req.postData()) };
}
function completed(recorder, req, status = 200) {
  recorder.responded({ request: () => req, url: () => req.url(), status: () => status, headers: () => ({}) });
  recorder.finished(req);
}
function setup() {
  const invalid = [], recorder = new AnnualLifecycle(event => invalid.push(event));
  const first = request(), replacement = request(), ledger = [routed(replacement)];
  recorder.started(first); recorder.failed(first); recorder.started(replacement); completed(recorder, replacement);
  return { invalid, recorder, first, replacement, ledger, declared: [annualSignature(routed(first))] };
}

test('annual lifecycle retains pre-route freshness abort and its later routed completion', () => {
  const { recorder, ledger, declared, invalid } = setup(), result = recorder.snapshot(ledger, declared);
  assert.deepEqual(invalid, []); assert.deepEqual(result.bindingErrors, []); assert.deepEqual(result.rejectedUnbound, []);
  assert.deepEqual(result.rows.map(row => [row.id, row.routed, row.state]), [[1, false, 'cancelled'], [2, true, 'completed']]);
});
test('annual lifecycle keeps ordinary routed replay and completion', () => {
  const { recorder, ledger, declared, first } = setup(); ledger.unshift(routed(first));
  assert.deepEqual(recorder.snapshot(ledger, declared).rejectedUnbound, []);
  assert.equal(recorder.snapshot(ledger, declared).rows[0].routed, true);
});
test('annual lifecycle rejects undeclared, unknown, wrong-pin and wrong-method unbound cancellations', () => {
  for (const [path, changes, declare] of [
    ['/companies/AAA/freshness', {}, false], ['/companies/AAA/unknown', {}, true],
    ['/companies/AAA/freshness', { pin: '0' }, true], ['/companies/AAA/freshness', { method: 'POST' }, true],
    ['/companies/CCC/freshness', {}, true], ['/companies/AAA/freshness', { query: 'extra=1' }, true],
  ]) {
    const invalid = [], recorder = new AnnualLifecycle(event => invalid.push(event)), first = request(path, changes), later = request(path, changes);
    recorder.started(first); recorder.failed(first); recorder.started(later); completed(recorder, later);
    const result = recorder.snapshot([routed(later)], declare ? [annualSignature(routed(first))] : []);
    assert.deepEqual(result.rejectedUnbound, [1]); assert.deepEqual(invalid, []);
  }
});
test('annual lifecycle rejects successful unbound and missing or unsuccessful replacement', () => {
  for (const kind of ['success', 'missing', 'failed-replacement', 'unbound-replacement']) {
    const recorder = new AnnualLifecycle(() => {}), first = request(), replacement = request();
    recorder.started(first);
    if (kind === 'success') completed(recorder, first); else recorder.failed(first);
    const ledger = [];
    if (kind !== 'missing') {
      recorder.started(replacement); completed(recorder, replacement, kind === 'failed-replacement' ? 503 : 200);
      if (kind !== 'unbound-replacement') ledger.push(routed(replacement));
    }
    assert.ok(recorder.snapshot(ledger, [annualSignature(routed(first))]).rejectedUnbound.includes(1), kind);
  }
});
test('annual lifecycle rejects a pre-route abort after response headers', () => {
  const recorder = new AnnualLifecycle(() => {}), first = request(), replacement = request();
  recorder.started(first);
  recorder.responded({ request: () => first, url: () => first.url(), status: () => 200, headers: () => ({}) });
  recorder.failed(first); recorder.started(replacement); completed(recorder, replacement);
  assert.deepEqual(recorder.snapshot([routed(replacement)], [annualSignature(routed(first))]).rejectedUnbound, [1]);
});
test('annual lifecycle rejects a raw JSON null body on an unbound freshness abort', () => {
  for (const rawBody of ['null', ' null ']) {
    const recorder = new AnnualLifecycle(() => {}), first = request('/companies/AAA/freshness', { rawBody }), replacement = request();
    recorder.started(first); recorder.failed(first); recorder.started(replacement); completed(recorder, replacement);
    assert.deepEqual(recorder.snapshot([routed(replacement)], [annualSignature(routed(first))]).rejectedUnbound, [1]);
  }
});
test('annual lifecycle records a foreign API origin as a violation after a valid baseline', () => {
  const { recorder, ledger, declared, invalid } = setup();
  assert.deepEqual(recorder.snapshot(ledger, declared).rejectedUnbound, []);
  recorder.started(request('/companies/AAA/freshness', { origin: 'https://example.test' }));
  assert.deepEqual(invalid, ['unexpected API origin']);
  assert.equal(recorder.snapshot(ledger, declared).rows.length, 2);
});
test('annual lifecycle requires an exact distinct later replacement', () => {
  for (const kind of ['different-ticker', 'pin-header', 'duplicate-cancel']) {
    const recorder = new AnnualLifecycle(() => {}), first = request(), second = kind === 'different-ticker'
      ? request('/companies/BBB/freshness') : request();
    recorder.started(first); recorder.failed(first); recorder.started(second);
    if (kind === 'duplicate-cancel') recorder.failed(second);
    else {
      recorder.responded({ request: () => second, url: () => second.url(), status: () => 200,
        headers: () => kind === 'pin-header' ? { 'x-finlens-data-version': '0' } : {} });
      recorder.finished(second);
    }
    assert.ok(recorder.snapshot([routed(second)], [annualSignature(routed(first))]).rejectedUnbound.includes(1), kind);
  }
});
test('annual lifecycle detects duplicate events and invalid route binding', () => {
  const { recorder, invalid, first, replacement, ledger, declared } = setup();
  recorder.started(first); recorder.failed(first); completed(recorder, replacement);
  assert.deepEqual(invalid, ['duplicate request', 'failure without pending request', 'response without pending request', 'finish without pending request']);
  ledger.push(routed(replacement));
  assert.ok(recorder.snapshot(ledger, declared).bindingErrors.length);
  const mismatch = routed(first); mismatch.pin = '1';
  assert.ok(recorder.snapshot([mismatch, routed(replacement)], declared).bindingErrors.length);
});
test('annual lifecycle cursor tracks started identities, including late pre-route failures', () => {
  const { recorder, first, ledger, declared } = setup(), boundary = recorder.cursor();
  const late = request(), replacement = request(); recorder.started(late); recorder.started(replacement);
  recorder.failed(late); completed(recorder, replacement); ledger.push(routed(replacement));
  const result = recorder.snapshot(ledger, [...declared, annualSignature(routed(late))]);
  assert.deepEqual(result.rejectedUnbound, []);
  assert.deepEqual(result.rows.filter(row => row.id > boundary).map(row => [row.id, row.state]), [[3, 'cancelled'], [4, 'completed']]);
  assert.ok(result.rows.some(row => row.id === 1 && row.request === annualSignature(routed(first))));
});
