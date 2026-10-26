import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';

const require = createRequire(import.meta.url), modules = new Map();
function load(relative) {
  const path = fileURLToPath(new URL(relative, import.meta.url));
  if (modules.has(path)) return modules.get(path);
  const exports = {}; modules.set(path, exports);
  const source = readFileSync(path, 'utf8').replaceAll('import.meta.url', JSON.stringify(new URL(relative, import.meta.url).href));
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const localRequire = name => name === './financial-insights' ? load('../lib/financial-insights.ts') : require(name);
  new Function('require', 'exports', code)(localRequire, exports); return exports;
}
const lib = load('../lib/financial-insights.ts'), worker = load('../lib/financial-insights.worker.ts');
const fixtures = load('../e2e/fixtures/financial-insights.ts'), api = load('../lib/finlens-api.ts');
const fixture = kind => fixtures.financialInsightsFixture(kind);
const identity = (mode = 'compare') => ({ ticker: 'TEST', cik: '0000000001', pin: 0, selection: mode === 'discover' ? { mode } : { mode, earlier: 2024, later: 2025 } });
const request = (mode = 'compare', overrides = {}) => ({ ...identity(mode), signal: new AbortController().signal, current: () => true, changed: () => assert.fail('unexpected reconciliation'), ...overrides });
const encoded = value => new TextEncoder().encode(typeof value === 'string' ? value : JSON.stringify(value));
const rejectCode = code => error => error.code === code;
let backendCases;
const freshBudget = () => new lib.InsightBudget();
async function admit(value, mode = 'compare') { await lib.preflightInsightsJson(JSON.stringify(value)); return lib.validateInsights(value, identity(mode)); }
class Clock {
  time = 0; next = 0; timers = new Map();
  now = () => this.time;
  timer = (fn, ms) => { const id = ++this.next; this.timers.set(id, { at: this.time + ms, fn }); return id; };
  clear = id => { this.timers.delete(id); };
  advance(ms) { const end = this.time + ms; for (;;) { const next = [...this.timers].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0]; if (!next) break; this.time = next[1].at; this.timers.delete(next[0]); next[1].fn(); } this.time = end; }
}
class WorkerDouble {
  listeners = new Map(); terminated = 0; sent = []; received = []; dropIn = () => false; dropOut = () => false;
  constructor(clock) {
    this.runtime = worker.createInsightsWorkerRuntime({ postMessage: (message, transfer = []) => {
      const copy = structuredClone(message, { transfer }); this.sent.push(copy);
      if (!this.dropOut(copy)) queueMicrotask(() => this.emit('message', copy));
    } }, clock.now);
  }
  postMessage(message, transfer = []) { const copy = structuredClone(message, { transfer }); this.received.push(copy); if (!this.terminated && !this.dropIn(copy)) queueMicrotask(() => { void this.runtime.handle(copy); }); }
  addEventListener(type, fn) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(fn); }
  removeEventListener(type, fn) { this.listeners.get(type)?.delete(fn); }
  emit(type, data) { if (!this.terminated) for (const fn of this.listeners.get(type) ?? []) fn({ data }); }
  terminate() { this.terminated++; this.runtime.dispose(); }
}
function harness(body = fixture(), options = {}) {
  const clock = new Clock(), fake = new WorkerDouble(clock), calls = [], lifecycle = new EventTarget();
  const environment = { now: clock.now, timer: clock.timer, clear: clock.clear, worker: () => fake,
    fetch: async (url, init) => { calls.push({ url, init }); return new Response(body instanceof Uint8Array ? body : JSON.stringify(body), { headers: { 'X-FinLens-Data-Version': '0', ...options.headers } }); },
    window: lifecycle, document: lifecycle, ...options.environment };
  const panel = new lib.InsightsPanel(environment);
  return { clock, fake, calls, lifecycle, panel };
}
async function until(h, promise) {
  let done = false, value, failure;
  promise.then(v => { value = v; done = true; }, e => { failure = e; done = true; });
  const stop = performance.now() + 15000;
  while (!done && performance.now() < stop) { h.clock.advance(0); await new Promise(resolve => setTimeout(resolve, 1)); }
  assert.ok(done, 'offline protocol settled'); if (failure) throw failure; return value;
}
async function ready(options = {}) { const h = harness(options.body ?? fixture(), options); const delivery = await until(h, h.panel.start(request())); assert.equal(delivery.mode, 'compare'); return { ...h, handle: delivery.handle }; }

test('guarded committed Backend 1A serialization matches every synthetic fixture', () => {
  const python = fileURLToPath(new URL('../../backend/.venv/Scripts/python.exe', import.meta.url));
  const code = `from pathlib import Path
runner=Path('tests/run_financial_insights.py').resolve()
ns={'__file__':str(runner),'__name__':'guarded_serialization'}
exec(compile(runner.read_text().split('\\nimport pytest\\nraise SystemExit')[0],str(runner),'exec'),ns)
from test_financial_insights import COMPANY,dataset,fact
from app.financial_insights_contract import Budget
from app.financial_insights_service import compose
from app.financial_metrics_service import FinancialMetrics
from types import SimpleNamespace
from decimal import Decimal
import json
out={}
for kind in ('compare','discover','conflict','nonfinite'):
 rows=dataset()
 if kind=='conflict':
  duplicate=vars(rows[-1]).copy();duplicate.update(id=11,value=Decimal('7'));rows.append(SimpleNamespace(**duplicate))
 if kind=='nonfinite': rows.append(fact('PaymentsToAcquirePropertyPlantAndEquipment','NaN',2025,id=11))
 b=Budget();m=FinancialMetrics(COMPANY,rows,budget=b);d=kind=='discover'
 out[kind]=compose(m,(0,0,0),'discover' if d else 'compare',None if d else 2024,None if d else 2025,b).model_dump(mode='json')
print(json.dumps(out,separators=(',',':')))`;
  const run = spawnSync(python, ['-I', '-S', '-B', '-'], { input: code, cwd: fileURLToPath(new URL('../../backend/', import.meta.url)), encoding: 'utf8', timeout: 30000, maxBuffer: 4 * 1024 * 1024 });
  assert.equal(run.status, 0, run.stderr); const actual = JSON.parse(run.stdout);
  for (const kind of Object.keys(actual)) assert.deepEqual(fixture(kind), actual[kind]);
});

test('guarded backend loss/zero/tiny/ambiguous/scope and nonfinite-only serialization', async () => {
  const python = fileURLToPath(new URL('../../backend/.venv/Scripts/python.exe', import.meta.url));
  const code = `from pathlib import Path
runner=Path('tests/run_financial_insights.py').resolve()
ns={'__file__':str(runner),'__name__':'guarded_serialization'}
exec(compile(runner.read_text().split('\\nimport pytest\\nraise SystemExit')[0],str(runner),'exec'),ns)
from test_financial_insights import COMPANY,dataset,fact
from app.financial_insights_contract import Budget
from app.financial_insights_service import compose
from app.financial_metrics_service import FinancialMetrics
from decimal import Decimal
from datetime import date
import json
out={}
for kind in ('negative','zero','tiny','ambiguous','scope','NaN','sNaN','Infinity','-Infinity'):
 rows=dataset()
 if kind=='negative': rows[3].value=Decimal('-14');rows[8].value=Decimal('-10');rows[1].value=Decimal('-10');rows[6].value=Decimal('0')
 if kind=='zero': rows[3].value=Decimal('0');rows[8].value=Decimal('0')
 if kind=='tiny': rows[0].value=Decimal('1E-10');rows[5].value=Decimal('1.000000001E-10')
 if kind=='ambiguous': rows.append(fact('GrossProfit','30',2025,id=11,period_start=date(2025,1,2)))
 if kind=='scope': rows[5].metric='SalesRevenueNet';rows[5].source='SEC Company Facts API: SalesRevenueNet'
 if kind in ('NaN','sNaN','Infinity','-Infinity'): rows[-1].value=Decimal(kind)
 b=Budget();m=FinancialMetrics(COMPANY,rows,budget=b)
 out[kind]=compose(m,(0,0,0),'compare',2024,2025,b).model_dump(mode='json')
print(json.dumps(out,separators=(',',':')))`;
  const run = spawnSync(python, ['-I', '-S', '-B', '-'], { input: code, cwd: fileURLToPath(new URL('../../backend/', import.meta.url)), encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 });
  assert.equal(run.status, 0, run.stderr); backendCases = JSON.parse(run.stdout);
  for (const [kind, value] of Object.entries(backendCases)) { try { const admitted = await admit(value); await lib.prepareInsights(admitted, freshBudget()); assert.equal(admitted.data_version, 0, kind); } catch (error) { error.message = `${kind}: ${error.message}`; throw error; } }
});
for (const kind of ['compare', 'discover', 'conflict', 'nonfinite']) test(`exact Backend 1A admission: ${kind}, verified zero and None scope`, async () => {
  const r = await admit(fixture(kind), kind === 'discover' ? 'discover' : 'compare');
  assert.equal(r.data_version, 0);
  if (kind === 'discover') assert.ok(r.scope.endsWith(':None:None'));
  else { assert.equal(Object.keys(r.comparisons).length, 7); const prepared = await lib.prepareInsights(r, freshBudget()); assert.ok(prepared.pages.has('F')); assert.ok(prepared.pages.has('D')); }
  if (kind === 'conflict') { assert.equal(r.comparisons.free_cash_flow.status, 'unavailable'); assert.equal(r.statements.find(s => s.key === 'overall').outcome, 'not_assessable'); }
  if (kind === 'nonfinite') { assert.ok(r.evidence.some(n => n.ref.category === 'D' && n.data.value === 'NaN')); assert.ok(!r.evidence.some(n => n.ref.category === 'F' && n.data.value === 'NaN')); }
});
for (const [label, mutate] of [
  ['ticker', r => { r.ticker = 'OTHER'; }], ['CIK', r => { r.company_cik = '0000000002'; }], ['pin', r => { r.data_version = 1; }],
  ['scope', r => { r.scope += ':bad'; }], ['years', r => { r.earlier_fiscal_year = 2023; }],
  ['extra metric', r => { r.comparisons.eps = {}; }], ['null optional metadata', r => { r.comparisons.revenue.earlier.revenue_basis = null; }],
  ['reference identity', r => { r.statements[0].financial[0].side = 'later'; }],
  ['missing closure', r => { r.statements[0].financial.pop(); }], ['extra statement', r => { r.statements.push({ ...r.statements[0], key: 'invented' }); }],
  ['contradictory outcome', r => { r.statements.find(s => s.rule === 'OVERALL').outcome = 'mixed'; }],
  ['F/D crossing', r => { const n = r.evidence.find(n => n.ref.category === 'F' && n.edges.length); n.edges[0].category = 'D'; }],
  ['duplicate node', r => { r.evidence.push(structuredClone(r.evidence[0])); }],
]) test(`whole-response rejection: ${label}`, async () => { const r = fixture(); mutate(r); await assert.rejects(admit(r)); });

for (const [label, text] of [['escaped duplicate', '{"x":1,"\\u0078":2}'], ['high surrogate', '{"x":"\\ud800"}'], ['low key', '{"\\udc00":0}'], ['depth', '['.repeat(34) + '0' + ']'.repeat(34)], ['members', JSON.stringify(Object.fromEntries(Array.from({ length: 65 }, (_, i) => [i, 0])))], ['array', '[' + '0,'.repeat(16384) + '0]'], ['number', '9007199254740992'], ['numeric token', '1'.repeat(18)], ['float', '1.5'], ['trailing comma', '{"x":1,}']]) test(`lexical preflight rejects ${label}`, async () => { await assert.rejects(lib.preflightInsightsJson(text)); });
test('Unicode scalar byte ceilings and valid supplementary pair', async () => {
  await lib.preflightInsightsJson('{"text":"\\ud83d\\ude00"}');
  await lib.preflightInsightsJson(JSON.stringify({ text: 'é'.repeat(1024) }));
  await assert.rejects(lib.preflightInsightsJson(JSON.stringify({ text: 'é'.repeat(1025) })), rejectCode('INSIGHTS_CLIENT_LIMIT'));
  await assert.rejects(lib.preflightInsightsJson('{"x":"' + '\ud800' + '"}'));
});
test('bounded work yields actual tasks and observes cancellation', async () => {
  let yields = 0; const b = new lib.InsightBudget(() => {}, () => 0, async () => { yields++; });
  for (let i = 0; i < 512; i++) await b.tick(); assert.equal(yields, 2);
  b.work = 2000000; await assert.rejects(b.tick(), rejectCode('INSIGHTS_CLIENT_LIMIT'));
  const stopped = new lib.InsightBudget(() => { throw new DOMException('Cancelled', 'AbortError'); });
  await assert.rejects(lib.preflightInsightsJson(' '.repeat(300) + '{}', stopped), { name: 'AbortError' });
});
for (const [raw, measure, expected] of [['9007199254740993.00', 'USD', '9,007,199,254,740,993.00 USD'], ['-0.00', 'USD', '-0.00 USD'], ['1.2300e-3', 'ratio', '0.12300%'], ['1e-10', 'USD', '0.0000000001 USD'], ['+1.00', 'USD', '+1.00 USD'], ['0.1000', 'ratio', '10.00%']]) test(`lossless decimal ${raw}`, () => assert.equal(lib.formatInsightDecimal(raw, measure), expected));
for (const raw of ['1e999999999999999999999', '0e-513', '1'.repeat(129), 'NaN', 'Infinity', '1e' + '9'.repeat(120)]) test(`decimal rejects ${raw.slice(0, 20)}`, () => assert.throws(() => lib.formatInsightDecimal(raw, 'USD')));

test('real runtime publishes atomically, pages use credit-one ACK and bounded retention', async () => {
  const h = await ready(); try {
    assert.equal(h.handle.snapshot.data_version, 0); assert.equal(h.handle.snapshot.metrics.length, 14);
    assert.equal(h.calls[0].init.headers['X-FinLens-Data-Version'], '0');
    for (const collection of ['F', 'D']) {
      const result = await until(h, h.handle.requestPage(collection, 0)); assert.ok(result.records.length <= 25);
      assert.ok(h.handle.inspect().parentBytes <= 196608); assert.equal(h.handle.inspect().retainedPages, 1);
    }
    for (const m of h.fake.sent.filter(m => m.type === 'BATCH')) { assert.ok(m.bytes <= 32768); assert.ok(m.entries <= 1024); assert.equal(lib.encodedSize(m.payload), m.bytes); }
    assert.equal(h.fake.runtime.inspect().pageCache, 0); assert.equal(h.fake.runtime.inspect().outgoing, 0);
  } finally { h.panel.dispose(); }
  assert.equal(h.fake.terminated, 1); assert.equal(h.clock.timers.size, 0); assert.equal(h.handle.snapshot, null);
});
test('discovery worker terminates after acknowledged validated delivery', async () => {
  const h = harness(fixture('discover')); const result = await until(h, h.panel.start(request('discover')));
  assert.equal(result.mode, 'discover'); assert.equal(result.data.scope, '0000000001:0:0:0:None:None'); assert.equal(h.fake.terminated, 1); assert.equal(h.clock.timers.size, 0);
});
test('API wrapper rejects unpinned calls and retains verified zero', async () => {
  const h = harness(fixture('discover'));
  await assert.rejects(api.getFinancialInsights({ ticker: 'TEST', cik: '0000000001' }, { mode: 'discover' }, new AbortController().signal, h.panel, () => true), rejectCode('INVALID_RESPONSE'));
  const controller = api.versionedController(0, () => assert.fail('no change'));
  const result = await until(h, api.getFinancialInsights({ ticker: 'TEST', cik: '0000000001' }, { mode: 'discover' }, controller.signal, h.panel, () => true)); assert.equal(result.data.data_version, 0);
});
test('same-page requests coalesce and different requests reject without a queue', async () => {
  const h = await ready(); h.fake.dropIn = m => m.type === 'PAGE';
  const first = h.handle.requestPage('D', 0), same = h.handle.requestPage('D', 0); assert.equal(first, same);
  await assert.rejects(h.handle.requestPage('F', 0), rejectCode('PAGE_BUSY')); assert.equal(h.handle.inspect().pendingPages, 1);
  const rejected = assert.rejects(first, rejectCode('PAGE_TIMEOUT')); h.clock.advance(5000); await rejected; assert.equal(h.handle.state, 'DISPOSED'); assert.equal(h.clock.timers.size, 0);
});
test('page operation succeeds more than thirty seconds after publication', async () => {
  const h = await ready(); try { for (let i = 0; i < 3; i++) { h.clock.advance(15000); await new Promise(resolve => setTimeout(resolve, 0)); } const page = await until(h, h.handle.requestPage('D', 0)); assert.equal(page.collection, 'D'); } finally { h.panel.dispose(); }
});
test('missing page ACK settles by page watchdog, never commits staged result', async () => {
  const h = await ready(); h.fake.dropIn = m => m.type === 'ACK'; const p = h.handle.requestPage('D', 0); const rejection = assert.rejects(p, rejectCode('PAGE_TIMEOUT'));
  await new Promise(resolve => setTimeout(resolve, 15)); assert.equal(h.fake.runtime.inspect().outgoing, 1); assert.equal(h.handle.page, null);
  h.clock.advance(5000); await rejection; assert.equal(h.fake.terminated, 1);
});
test('missing OP_COMPLETE does not publish initial partial data', async () => {
  const h = harness(); h.fake.dropOut = m => m.type === 'OP_COMPLETE'; const p = h.panel.start(request()); const rejection = assert.rejects(p, rejectCode('REQUEST_TIMEOUT'));
  for (let i = 0; i < 1000 && !h.fake.sent.some(m => m.type === 'OP_COMPLETE'); i++) { h.clock.advance(0); await new Promise(resolve => setTimeout(resolve, 1)); }
  assert.ok(h.fake.sent.some(m => m.type === 'BATCH')); h.clock.advance(30000); await rejection; assert.equal(h.fake.terminated, 1);
});
for (const type of ['error', 'messageerror']) test(`worker ${type} releases handle and listeners`, async () => { const h = await ready(); h.fake.emit(type); assert.equal(h.handle.snapshot, null); assert.equal(h.fake.terminated, 1); assert.equal(h.clock.timers.size, 0); assert.ok([...h.fake.listeners.values()].every(s => s.size === 0)); });
test('worker construction failure settles initialization', async () => { const h = harness(undefined, { environment: { worker: () => { throw Error('construction'); } } }); await assert.rejects(h.panel.start(request()), rejectCode('WORKER_FAILED')); assert.equal(h.clock.timers.size, 0); });
test('silent worker termination expires heartbeat and releases result', async () => { const h = await ready(); h.fake.dropIn = m => m.type === 'PING'; h.clock.advance(20000); assert.equal(h.handle.state, 'DISPOSED'); assert.equal(h.clock.timers.size, 0); });
test('idle expiry and absolute expiry cannot be prolonged by interaction/heartbeat', async () => {
  const h = await ready();
  for (let i = 0; i < 59; i++) { h.clock.advance(15000); await new Promise(resolve => setTimeout(resolve, 0)); h.handle.interact(); }
  h.clock.advance(15000); assert.equal(h.handle.state, 'DISPOSED'); assert.equal(h.handle.snapshot, null);
  const idle = await ready(); for (let i = 0; i < 20; i++) { idle.clock.advance(15000); await new Promise(resolve => setTimeout(resolve, 0)); } assert.equal(idle.handle.state, 'DISPOSED');
});
for (const kind of ['owner', 'abort', 'pagehide', 'dispose']) test(`synchronous invalidation and idempotent cleanup: ${kind}`, async () => {
  let current = true; const controller = new AbortController(), h = harness();
  const delivery = await until(h, h.panel.start(request('compare', { signal: controller.signal, current: () => current }))); const handle = delivery.handle;
  if (kind === 'owner') current = false; else if (kind === 'abort') controller.abort(); else if (kind === 'pagehide') h.lifecycle.dispatchEvent(new Event('pagehide')); else handle.dispose();
  assert.equal(handle.snapshot, null); handle.dispose(); h.fake.emit('message', { type: 'OP_COMPLETE' }); assert.equal(h.fake.terminated, 1); assert.equal(h.clock.timers.size, 0);
});
test('duplicate and reordered active worker messages fail closed', async () => {
  for (const mutate of [m => ({ ...m, sequence: 1 }), m => m]) {
    const h = await ready(); const old = h.fake.sent.find(m => m.type === 'BATCH'); h.fake.emit('message', mutate(old)); assert.equal(h.handle.state, 'DISPOSED');
  }
});
test('actual byte limit includes exact 4MiB, misleading length and boundary overflow', async () => {
  const json = JSON.stringify(fixture('discover')), padded = encoded(json + ' '.repeat(4194304 - encoded(json).byteLength));
  const exact = harness(padded, { headers: { 'Content-Length': '1' } }); const result = await until(exact, exact.panel.start(request('discover'))); assert.equal(result.mode, 'discover');
  const over = harness(new Uint8Array(4194305), { headers: { 'Content-Length': '0' } }); await assert.rejects(until(over, over.panel.start(request('discover'))), rejectCode('INSIGHTS_CLIENT_LIMIT'));
  const labelled = harness(fixture('discover'), { headers: { 'Content-Length': '999999999' } }); assert.equal((await until(labelled, labelled.panel.start(request('discover')))).mode, 'discover');
});
for (const bytes of [new Uint8Array([0xc0, 0xaf]), new Uint8Array([0xe2, 0x82]), new Uint8Array([0xed, 0xa0, 0x80])]) test(`fatal UTF8 ${bytes}`, async () => { const h = harness(bytes); await assert.rejects(until(h, h.panel.start(request('discover'))), rejectCode('INVALID_RESPONSE')); });
test('initial timeout settles even when fetch ignores cancellation', async () => { const h = harness(undefined, { environment: { fetch: () => new Promise(() => {}) } }); const p = h.panel.start(request()); const rejection = assert.rejects(p, rejectCode('REQUEST_TIMEOUT')); await new Promise(resolve => setTimeout(resolve, 0)); h.clock.advance(30000); await rejection; assert.equal(h.fake.terminated, 1); });
test('old 409 cannot reconcile a replaced company/year/publication generation', async () => {
  let finish, changes = 0; const h = harness(undefined, { environment: { fetch: () => new Promise(resolve => { finish = resolve; }) } });
  const p = h.panel.start(request('compare', { changed: () => changes++ })); const rejected = assert.rejects(p, { name: 'AbortError' }); await new Promise(resolve => setTimeout(resolve, 0)); h.panel.dispose('replacement'); await rejected;
  finish(new Response('{}', { status: 409, headers: { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED', 'X-FinLens-Data-Version': '1' } })); await new Promise(resolve => setTimeout(resolve, 0)); assert.equal(changes, 0);
});
test('oversized individual complete evidence record prevents initial publication', async () => {
  const r = await admit(fixture()); const source = r.evidence.find(n => n.ref.kind === 'source'); source.data.extra = Array.from({ length: 901 }, () => 'x');
  await assert.rejects(lib.prepareInsights(r, freshBudget()), rejectCode('INSIGHTS_CLIENT_LIMIT'));
});

test('graph node, edge and per-statement reference ceilings reject before expansion', async () => {
  const nodes = fixture(); nodes.evidence = Array.from({ length: 8193 }, () => nodes.evidence[0]); await assert.rejects(lib.validateInsights(nodes, identity()), rejectCode('INSIGHTS_CLIENT_LIMIT'));
  const edges = fixture(); edges.evidence[0].edges = Array.from({ length: 16385 }, () => edges.evidence[1].ref); await assert.rejects(lib.validateInsights(edges, identity()), rejectCode('INSIGHTS_CLIENT_LIMIT'));
  const refs = fixture(); refs.statements[0].financial = Array.from({ length: 8193 }, () => refs.statements[0].financial[0]); await assert.rejects(lib.validateInsights(refs, identity()), rejectCode('INSIGHTS_CLIENT_LIMIT'));
});
test('cycle and same-category unrelated evidence do not admit a closure', async () => {
  const cyclic = fixture(); const node = cyclic.evidence.find(n => n.ref.kind === 'observation' && n.ref.category === 'D'); node.edges = [structuredClone(node.ref)]; await assert.rejects(lib.validateInsights(cyclic, identity()));
  const unrelated = fixture(); const root = unrelated.statements.find(s => s.rule === 'CHANGE'); const extra = unrelated.evidence.find(n => n.ref.category === 'F' && n.ref.metric === 'net_income'); root.financial.push(extra.ref); root.financial.sort((a,b) => a.key.localeCompare(b.key)); await assert.rejects(lib.validateInsights(unrelated, identity()));
});
test('complete source metadata reconciliation rejects a substituted stored timestamp', async () => {
  const r = fixture(); r.comparisons.revenue.earlier.provenance[0].stored_at = '2025-02-02T00:00:00'; await assert.rejects(lib.validateInsights(r, identity()));
});
test('whole-stream cancellation interrupts an ignored pending reader', async () => {
  const h = harness(undefined, { environment: { fetch: async () => ({ ok: true, headers: new Headers({ 'X-FinLens-Data-Version': '0' }), body: { getReader: () => ({ read: () => new Promise(() => {}), cancel: () => new Promise(() => {}), releaseLock() {} }) } }) } });
  const controller = new AbortController(), p = h.panel.start(request('compare', { signal: controller.signal })); const rejected = assert.rejects(p, { name: 'AbortError' });
  await new Promise(resolve => setTimeout(resolve, 0)); controller.abort(); await rejected; assert.equal(h.fake.terminated, 1); assert.equal(h.clock.timers.size, 0);
});
test('input slices own exact backing buffers and split UTF8 sequences decode correctly', async () => {
  const bytes = encoded({ ...fixture('discover'), company_name: 'Synthetic 😀 company' }); let offset = 0;
  const h = harness(undefined, { environment: { fetch: async () => new Response(new ReadableStream({ pull(controller) { if (offset === bytes.length) controller.close(); else controller.enqueue(bytes.slice(offset, ++offset)); } }), { headers: { 'X-FinLens-Data-Version': '0' } }) } });
  const result = await until(h, h.panel.start(request('discover'))); assert.ok(result.data.company_name.includes('😀'));
  for (const message of h.fake.received.filter(m => m.type === 'CHUNK')) assert.ok(message.buffer.byteLength > 0 && message.buffer.byteLength <= 16384);
  assert.ok(h.fake.runtime.inspect().textChunks <= 256); assert.ok(h.fake.runtime.inspect().tailUnits < 16384);
});
test('duplicate ACK is fatal and there is no queued worker output', async () => {
  const h = await ready(); const ack = h.fake.received.find(m => m.type === 'ACK'); h.fake.postMessage(ack); await new Promise(resolve => setTimeout(resolve, 1)); assert.equal(h.handle.state, 'DISPOSED'); assert.equal(h.fake.runtime.inspect().outgoing, 0);
});
test('missing initial ACK and page completion never publish partial results', async () => {
  const initial = harness(); initial.fake.dropIn = m => m.type === 'ACK'; const p = initial.panel.start(request()); const rejected = assert.rejects(p, rejectCode('REQUEST_TIMEOUT'));
  for (let i = 0; i < 5000 && !initial.fake.sent.some(m => m.type === 'BATCH'); i++) { initial.clock.advance(0); await new Promise(resolve => setTimeout(resolve, 1)); }
  assert.equal(initial.fake.runtime.inspect().outgoing, 1); assert.equal(initial.fake.sent.filter(m => m.type === 'BATCH').length, 1); initial.clock.advance(30000); await rejected;
  const page = await ready(); page.fake.dropOut = m => m.type === 'OP_COMPLETE'; const pending = page.handle.requestPage('D', 0), failure = assert.rejects(pending, rejectCode('PAGE_TIMEOUT'));
  await new Promise(resolve => setTimeout(resolve, 10)); assert.equal(page.handle.page, null); page.clock.advance(5000); await failure;
});
test('replacement constructs a fresh worker and late old messages cannot revive it', async () => {
  const h = await ready(), old = h.fake; const replacement = new WorkerDouble(h.clock); h.panel.environment.worker = () => replacement;
  const outcome = await until(h, h.panel.start(request())); assert.equal(old.terminated, 1); assert.equal(h.handle.snapshot, null);
  old.emit('message', old.sent.find(m => m.type === 'OP_COMPLETE')); assert.equal(outcome.handle.state, 'READY'); h.panel.dispose(); assert.equal(replacement.terminated, 1);
});
test('pagehide during page delivery and queued callbacks release all retention', async () => {
  const h = await ready(); h.fake.dropIn = m => m.type === 'ACK'; const page = h.handle.requestPage('D', 0); const rejected = assert.rejects(page, { name: 'AbortError' });
  await new Promise(resolve => setTimeout(resolve, 10)); h.lifecycle.dispatchEvent(new Event('pagehide')); await rejected;
  assert.deepEqual(h.handle.inspect(), { parentBytes: 0, stagedBytes: 0, pendingPages: 0, timers: 0, retainedPages: 0 });
});
test('heartbeat reply can overlap a page without corrupting its sequence', async () => {
  const h = await ready(); h.clock.advance(15000); const page = h.handle.requestPage('D', 0); await until(h, page); assert.equal(h.handle.state, 'READY'); h.panel.dispose();
});
test('current version mismatch reconciles once and old generation changes never reconcile', async () => {
  let changed = 0;
  const h = harness(undefined, { environment: { fetch: async () => new Response('{}', { status: 409, headers: { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED', 'X-FinLens-Data-Version': '1' } }) } });
  await assert.rejects(until(h, h.panel.start(request('compare', { changed: () => changed++ }))), rejectCode('DATA_VERSION_CHANGED')); assert.equal(changed, 1);
});
test('API compare requires current discovery and pins the complete publication tuple', async () => {
  const h = harness(); const controller = api.versionedController(0, () => assert.fail('no reconciliation'));
  await assert.rejects(api.getFinancialInsights({ ticker: 'TEST', cik: '0000000001' }, identity().selection, controller.signal, h.panel, () => true), rejectCode('INVALID_RESPONSE'));
  const discovery = fixture('discover'); const delivery = await until(h, api.getFinancialInsights({ ticker: 'TEST', cik: '0000000001' }, identity().selection, controller.signal, h.panel, () => true, discovery)); assert.equal(delivery.handle.snapshot.data_version, 0); h.panel.dispose();
  await assert.rejects(lib.validateInsights(fixture(), { ...identity(), publication: { facts: 1, evidence: 0 } }));
});
test('captured selection is immutable during asynchronous reading', async () => {
  const h = harness(), selected = request(); const p = h.panel.start(selected); selected.selection.earlier = 1900; const delivery = await until(h, p); assert.equal(delivery.handle.snapshot.earlier_fiscal_year, 2024); h.panel.dispose();
});
test('shared requestJson implementation remains byte-for-byte identical to HEAD', () => {
  const path = fileURLToPath(new URL('../lib/finlens-api.ts', import.meta.url)), current = readFileSync(path, 'utf8');
  const baseline = spawnSync('git', ['--no-optional-locks', 'show', 'HEAD:frontend/lib/finlens-api.ts'], { cwd: fileURLToPath(new URL('../../', import.meta.url)), encoding: 'utf8' }); assert.equal(baseline.status, 0);
  const body = text => text.slice(text.indexOf('async function requestJson'), text.indexOf('export function getCompanies')).replaceAll('\r\n', '\n'); assert.equal(body(current), body(baseline.stdout));
});
test('strict identity and decimal admission reject trailing-newline regex aliases', async () => {
  for (const invalid of [{ ...identity(), ticker: 'TEST\n' }, { ...identity(), cik: '0000000001\n' }, { ...identity(), pin: -0 }]) assert.throws(() => lib.validInsightIdentity(invalid));
  assert.throws(() => lib.formatInsightDecimal('1.00\n', 'USD'));
  const r = fixture(); r.comparisons.revenue.earlier.value = '100\n'; await assert.rejects(lib.validateInsights(r, identity()));
});
test('delayed page timer cannot admit a response after its deadline', async () => {
  const h = await ready(); h.fake.dropOut = m => m.type === 'OP_COMPLETE'; const pending = h.handle.requestPage('D', 0), rejection = assert.rejects(pending, rejectCode('PAGE_TIMEOUT'));
  await new Promise(resolve => setTimeout(resolve, 10)); h.clock.time += 5001; const complete = h.fake.sent.at(-1); h.fake.emit('message', complete); await rejection; assert.equal(h.handle.snapshot, null);
});
test('subscriber and page-index bounds remain fixed', async () => {
  const h = await ready(); try { for (let i = 0; i < 8; i++) h.handle.subscribe(() => {}); assert.throws(() => h.handle.subscribe(() => {}), rejectCode('INSIGHTS_CLIENT_LIMIT'));
    await assert.rejects(h.handle.requestPage('D', 8192), rejectCode('INVALID_PAGE')); await assert.rejects(h.handle.requestPage('D', -1), rejectCode('INVALID_PAGE')); assert.equal(h.handle.inspect().pendingPages, 0);
  } finally { h.panel.dispose(); }
});
test('JSON preflight accepts depth/member boundaries and rejects aggregate expansion', async () => {
  await lib.preflightInsightsJson('['.repeat(32) + '0' + ']'.repeat(32));
  await lib.preflightInsightsJson(JSON.stringify(Object.fromEntries(Array.from({ length: 64 }, (_, i) => ['k' + i, 0]))));
  const block = '[' + '0,'.repeat(16383) + '0]', many = '[' + Array.from({ length: 65 }, () => block).join(',') + ']';
  const budget = new lib.InsightBudget(() => {}, () => 0, async () => {});
  await assert.rejects(lib.preflightInsightsJson(many, budget), rejectCode('INSIGHTS_CLIENT_LIMIT'));
});

// P2 mutations keep all repeated provenance/raw-source records consistent so a
// rejection proves observation/admission binding, not an incidental broken edge.
function selectedObservation(r, name, side) {
  return r.evidence.find(n => n.ref.category === 'F' && n.ref.kind === 'observation' && n.ref.metric === name && n.ref.side === side);
}
function mutateSelectedSource(r, name, side, changes) {
  const factId = selectedObservation(r, name, side).data.canonical.provenance[0].fact_id;
  const pending = [r];
  while (pending.length) {
    const value = pending.pop();
    if (!value || typeof value !== 'object') continue;
    if (value.fact_id === factId) Object.assign(value, changes);
    pending.push(...Object.values(value));
  }
  for (const n of r.evidence) if (n.ref.kind === 'source' && n.data.id === String(factId)) Object.assign(n.data, changes);
  return r;
}
function conflictSelected(r, name, side) {
  const d = r.evidence.find(n => n.ref.category === 'D' && n.ref.kind === 'observation' && n.ref.metric === name && n.ref.side === side);
  const c = d.edges.map(e => r.evidence.find(n => n.ref.key === e.key)).find(n => n.ref.kind === 'candidate' && n.data.dispositions.includes('selected_by_existing_normalization'));
  c.data.dispositions.push('conflicting_value'); return r;
}
function addIdentityConflict(r, name, side, flagged = true) {
  const selected = selectedObservation(r, name, side).data.canonical.provenance[0];
  const source = structuredClone(r.evidence.find(n => n.ref.category === 'D' && n.ref.kind === 'source' && n.data.id === String(selected.fact_id)));
  source.data.id = '900'; source.data.value = '999'; source.ref.key = source.ref.key.slice(0, source.ref.key.lastIndexOf('|') + 1) + '900';
  const candidate = structuredClone(r.evidence.find(n => n.ref.category === 'D' && n.ref.kind === 'candidate' && n.ref.metric === name && n.ref.side === side));
  candidate.ref.key = candidate.ref.key.slice(0, candidate.ref.key.lastIndexOf('|') + 1) + '900'; candidate.edges = [source.ref];
  candidate.data.dispositions = flagged ? ['conflicting_value'] : ['alternative_candidate'];
  r.evidence.push(source, candidate); r.evidence.sort((a,b) => a.ref.key < b.ref.key ? -1 : a.ref.key > b.ref.key ? 1 : 0);
  const d = r.evidence.find(n => n.ref.category === 'D' && n.ref.kind === 'observation' && n.ref.metric === name && n.ref.side === side);
  d.edges.push(candidate.ref); d.edges.sort((a,b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0); return r;
}
for (const [label, mutate] of [
  ['amount 100 versus source 999', r => mutateSelectedSource(r, 'revenue', 'earlier', { value: '999' })],
  ['FY2024 versus source interval 2023', r => mutateSelectedSource(r, 'revenue', 'earlier', { period_start: '2023-01-01', period_end: '2023-12-31' })],
  ['selected CapEx conflict with FCF 15', r => conflictSelected(r, 'capital_expenditures', 'later')],
  ['margin denominator conflict', r => conflictSelected(r, 'revenue', 'earlier')],
  ['operating-margin numerator conflict', r => conflictSelected(r, 'operating_income', 'later')],
  ['net-margin numerator conflict', r => conflictSelected(r, 'net_income', 'earlier')],
  ['duplicate identity flagged conflict', r => addIdentityConflict(r, 'capital_expenditures', 'later')],
  ['duplicate identity without conflict flag', r => addIdentityConflict(r, 'revenue', 'earlier', false)],
]) test(`P2 regression rejects ${label}`, async () => {
  const r = mutate(fixture());
  assert.equal(r.comparisons.revenue.earlier.value, '100'); assert.equal(r.comparisons.free_cash_flow.later.value, '15');
  await assert.rejects(admit(r), rejectCode('INVALID_RESPONSE'));
});
test('P2 regression amount substitution cannot publish through production Worker and parent', async () => {
  const r = mutateSelectedSource(fixture(), 'revenue', 'earlier', { value: '999' }), h = harness(r);
  try { await assert.rejects(until(h, h.panel.start(request())), rejectCode('INVALID_RESPONSE'));
    assert.equal(h.fake.sent.filter(m => m.type === 'BATCH' || m.type === 'OP_COMPLETE').length, 0);
    assert.ok(h.fake.sent.some(m => m.type === 'FAIL' && m.code === 'INVALID_RESPONSE'));
    assert.equal(h.fake.terminated, 1); assert.equal(h.fake.runtime.inspect().nodes, 0); assert.equal(h.clock.timers.size, 0);
  } finally { h.panel.dispose(); }
});
test('P2 positive equivalent decimal spelling and filing-context metadata remain valid', async () => {
  const r = mutateSelectedSource(fixture(), 'revenue', 'earlier', { value: '1.000E+2' });
  for (const n of r.evidence) if (n.ref.kind === 'source' && n.data.id === '1') n.data.value = '100.000';
  const admitted = await admit(r); assert.equal(admitted.comparisons.revenue.earlier.value, '100');
  assert.equal(admitted.comparisons.revenue.earlier.period.fiscal_year, 2024);
  assert.equal(admitted.comparisons.revenue.earlier.provenance[0].source_fiscal_year, 2025);
});
test('P2 positive guarded alternatives, duplicates, unrelated inputs and comparative context', async () => {
  const python = fileURLToPath(new URL('../../backend/.venv/Scripts/python.exe', import.meta.url));
  const code = `from pathlib import Path
runner=Path('tests/run_financial_insights.py').resolve()
ns={'__file__':str(runner),'__name__':'guarded_p2_serialization'}
exec(compile(runner.read_text().split('\\nimport pytest\\nraise SystemExit')[0],str(runner),'exec'),ns)
from test_financial_insights import COMPANY,dataset
from app.financial_insights_contract import Budget
from app.financial_insights_service import compose
from app.financial_metrics_service import FinancialMetrics
from datetime import date
from decimal import Decimal
from copy import deepcopy
import json
out={}
for kind in ('vintage','duplicate','quarter','nonfinite','comparative','zero'):
 rows=dataset();extra=deepcopy(rows[-1]);extra.id=11
 if kind=='vintage': extra.value=Decimal('7');extra.filed=date(2026,1,1);extra.accession_number='0000000001-26-000002';rows.append(extra)
 if kind=='duplicate': extra.value=Decimal('5.000');rows.append(extra)
 if kind=='quarter': extra.value=Decimal('7');extra.period_start=date(2025,10,1);rows.append(extra)
 if kind=='nonfinite': extra.value=Decimal('NaN');rows.append(extra)
 if kind=='comparative':
  for f in rows:
   f.metric='canonical_storage_alias';f.fiscal_year=f.period_end.year+2;f.filed=date(f.fiscal_year,2,1);f.accession_number=f'0000000001-{str(f.fiscal_year)[-2:]}-000001'
 if kind=='zero': rows[3].value=Decimal('0')
 b=Budget();model=FinancialMetrics(COMPANY,rows,budget=b)
 out[kind]=compose(model,(0,0,0),'compare',2024,2025,b).model_dump(mode='json')
from app.financial_metric_registry import METRICS,REVENUE_CONCEPTS
contract={k:list(METRICS[k].concepts) for k in ('revenue','operating_income','net_income','operating_cash_flow','capital_expenditures')}
print(json.dumps({'cases':out,'base_concepts':contract,'revenue_bases':{k:v.basis for k,v in REVENUE_CONCEPTS.items()}},separators=(',',':')))`;
  const run = spawnSync(python, ['-I', '-S', '-B', '-'], { input: code, cwd: fileURLToPath(new URL('../../backend/', import.meta.url)), encoding: 'utf8', timeout: 30000, maxBuffer: 4 * 1024 * 1024 });
  assert.equal(run.status, 0, run.stderr);
  const serialized = JSON.parse(run.stdout);
  assert.deepEqual(serialized.base_concepts, lib.INSIGHT_BASE_CONCEPTS); assert.deepEqual(serialized.revenue_bases, lib.INSIGHT_REVENUE_BASES);
  for (const [kind, value] of Object.entries(serialized.cases)) {
    if (kind === 'zero') mutateSelectedSource(value, 'operating_cash_flow', 'earlier', { value: '-0.000E+2' });
    const admitted = await admit(value); assert.equal(admitted.comparisons.free_cash_flow.status, 'available', kind);
    const prepared = await lib.prepareInsights(admitted, freshBudget()); assert.ok(prepared.initial.metrics.some(m => m.metric === 'operating_margin' && m.calculated));
    const dispositions = admitted.evidence.filter(n => n.ref.kind === 'candidate').flatMap(n => n.data.dispositions);
    if (kind === 'vintage') assert.ok(dispositions.includes('alternative_vintage'));
    if (kind === 'duplicate') assert.ok(dispositions.includes('equivalent_duplicate'));
    if (kind === 'quarter') assert.ok(dispositions.includes('outside_selected_annual_window'));
  }
  const unavailable = await admit(fixture('conflict'));
  assert.equal(unavailable.comparisons.free_cash_flow.status, 'unavailable');
  assert.ok(unavailable.evidence.some(n => n.ref.kind === 'observation' && n.ref.category === 'D' && n.data.canonical.status === 'available' && n.data.admitted === false));
});
test('P2 regression rejects a consistently substituted canonical metric on selected provenance', async () => {
  const r = fixture(), pending = [r];
  while (pending.length) { const value = pending.pop(); if (!value || typeof value !== 'object') continue; if (value.fact_id === 1) value.canonical_metric = 'operating_income'; pending.push(...Object.values(value)); }
  await assert.rejects(admit(r), rejectCode('INVALID_RESPONSE'));
});
