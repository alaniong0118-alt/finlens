import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

// Extract the actual self-contained browser initializers, not a rewritten model.
function declaration(file, name) {
  const source = ts.createSourceFile(file, readFileSync(new URL(file, import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true);
  const node = source.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === name);
  assert.ok(node, name);
  return ts.transpileModule(node.getText(source).replace(/^export /, ''), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
}
const spec = '../e2e/financial-only-capability.spec.ts';
const AAA = '/api/finlens/companies/AAA/research-answer', BBB = '/api/finlens/companies/BBB/research-answer';
const SUMMARY = '/api/finlens/companies/BBB/financials/summary';
function setup(paths = [AAA, BBB, SUMMARY]) {
  const calls = [], window = { fetch: (input, init) => new Promise(resolve => calls.push({ input, init, resolve })) };
  const context = { window, location: { href: 'http://127.0.0.1:3107/', origin: 'http://127.0.0.1:3107' },
    URL, Request, Headers, TextEncoder, endpoint: ticker => `/companies/${ticker}/research-answer` };
  const install = runInNewContext(declaration(spec, 'installFinancialObserver') + ';installFinancialObserver', context);
  const count = runInNewContext(declaration(spec, 'abortedFinancialReturns') + ';abortedFinancialReturns', context);
  install({ paths });
  return { window, calls, context, install, records: window.qaFinancialOnlyDeliveries,
    count: (ticker = 'AAA', pin = 0, question = 'revenue') => count({ evaluate: (fn, arg) => fn(arg) }, ticker, pin, question) };
}

test('financial observer: three route identities survive later installation and out-of-order returns', async () => {
  const app = setup(), controllers = [new AbortController(), new AbortController(), new AbortController()];
  const input = [
    [AAA, { method: 'POST', headers: { 'X-FinLens-Data-Version': '0' }, body: '{"question":"revenue"}' }],
    [BBB, { method: 'POST', headers: { 'X-FinLens-Data-Version': '1' }, body: '{"question":"Latest revenue"}' }],
    [SUMMARY + '?period=annual', { headers: { 'X-FinLens-Data-Version': '1' } }],
  ];
  const pending = input.map(([path, init], index) => app.window.fetch(path, { ...init, signal: controllers[index].signal }));
  assert.equal(app.calls.length, 3); assert.ok(app.calls.every(call => call.init.signal === null));
  controllers.forEach(controller => controller.abort());
  app.calls[0].resolve(new Response('fixture', { status: 200 })); await pending[0];
  const first = app.records[0];
  const legacy = runInNewContext(declaration('../e2e/fixtures/ignored-abort.ts', 'installIgnoredAbort') + ';installIgnoredAbort', app.context);
  legacy({ path: AAA }); // Overwrites only the legacy global, never our store.
  assert.equal(app.window.qaFinancialOnlyDeliveries, app.records);
  assert.equal(app.records[0], first); assert.equal(app.records.length, 1);
  const fetchAfterLegacy = app.window.fetch;
  assert.throws(() => app.install({ paths: [BBB] }), /already installed/);
  assert.equal(app.window.fetch, fetchAfterLegacy); assert.equal(app.records[0], first);
  app.calls[2].resolve(new Response('fixture', { status: 200 })); await pending[2];
  app.calls[1].resolve(new Response('fixture', { status: 200 })); await pending[1];
  assert.deepEqual(Array.from(app.records, row => row.requestId), [1, 3, 2]);
  assert.deepEqual(Array.from(app.records, row => [row.method, row.path, row.query, row.pin, row.body]), [
    ['POST', AAA, '', '0', '{"question":"revenue"}'],
    ['GET', SUMMARY, '?period=annual', '1', null],
    ['POST', BBB, '', '1', '{"question":"Latest revenue"}'],
  ]);
  assert.ok(app.records.every(row => row.signalAborted && row.stage === 'headers_returned' && Object.isFrozen(row)));
  assert.equal(await app.count(), 1); assert.equal(await app.count('BBB', 1, 'Latest revenue'), 1);
  assert.equal(app.calls[0].init.body, input[0][1].body);
});

for (const [name, path, pin, body, status, aborted] of [
  ['wrong query', AAA + '?unexpected=true', '0', '{"question":"revenue"}', 200, true],
  ['wrong pin', AAA, '1', '{"question":"revenue"}', 200, true],
  ['wrong body', AAA, '0', '{"question":"other"}', 200, true],
  ['raw JSON null', AAA, '0', 'null', 200, true],
  ['wrong status', AAA, '0', '{"question":"revenue"}', 503, true],
  ['not aborted', AAA, '0', '{"question":"revenue"}', 200, false],
]) test(`financial observer: ${name} cannot satisfy an exact aborted-return assertion`, async () => {
  const app = setup(), controller = new AbortController();
  const pending = app.window.fetch(path, { method: 'POST', body, headers: { 'X-FinLens-Data-Version': pin }, signal: controller.signal });
  if (aborted) controller.abort();
  app.calls[0].resolve(new Response('fixture', { status })); await pending;
  assert.equal(await app.count(), 0); assert.equal(app.records[0].body, body);
});

test('financial observer: unrelated origin/path keep native signals and never enter the store', async () => {
  const app = setup(), signal = new AbortController().signal;
  for (const path of ['https://example.invalid' + AAA, '/api/finlens/companies/CCC/research-answer']) {
    const pending = app.window.fetch(path, { signal });
    const call = app.calls.at(-1); assert.equal(call.init.signal, signal);
    call.resolve(new Response('unrelated')); await pending;
  }
  assert.equal(app.records.length, 0);
});

test('financial observer: wrong method/body streams fail before native fetch', async () => {
  const app = setup();
  await assert.rejects(app.window.fetch(AAA, { method: 'GET' }), /Unsupported/);
  await assert.rejects(app.window.fetch(SUMMARY, { body: 'null' }), /Unsupported/);
  const request = new Request('http://127.0.0.1:3107' + AAA, { method: 'POST', body: 'fixture' });
  await assert.rejects(app.window.fetch(request, { body: null }), /Unsupported/);
  assert.equal(app.calls.length, 0);
});

test('financial observer: unsupported or duplicate routes cannot install', () => {
  for (const paths of [[], [AAA, AAA], ['/companies/AAA/context']]) {
    assert.throws(() => setup(paths), /Invalid financial observer routes/);
  }
});

test('financial observer: missing store cannot masquerade as zero aborted responses', async () => {
  const app = setup();
  app.window.qaFinancialOnlyDeliveries = undefined;
  await assert.rejects(app.count(), /observer is unavailable/);
});
