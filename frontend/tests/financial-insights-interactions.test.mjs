import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

// Offline only: real ReactDOM, freshness/API/client/worker runtime and synthetic
// HTTP bodies. Adapt the bundler's import promise and Worker boundary, not finance.
const require = createRequire(import.meta.url), cache = new Map();
let dom, createRoot, Insights, Freshness, Home, runtime, fixtureFactory, active;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const actualNow = performance.now.bind(performance);
const company = { id: 1, ticker: 'TEST', cik: '0000000001', name: 'Synthetic company', exchange: 'TEST', has_indexed_filing: false, indexed_filing_count: 0 };
const otherCompany = { ...company, id: 2, ticker: 'OTHER', cik: '0000000002', name: 'Other synthetic company' };

class Clock {
  time = 0; sequence = 0; timers = new Map();
  now = () => this.time;
  timer = (fn, ms) => { const id = ++this.sequence; this.timers.set(id, { at: this.time + ms, fn }); return id; };
  clear = id => this.timers.delete(id);
  advance(ms) {
    const end = this.time + ms;
    for (;;) {
      const next = [...this.timers].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      this.time = next[1].at; this.timers.delete(next[0]); next[1].fn();
    }
    this.time = end;
  }
}
class WorkerDouble {
  listeners = new Map(); sent = []; received = []; held = []; terminated = 0;
  hold = () => false;
  constructor(clock) {
    this.runtime = runtime.createInsightsWorkerRuntime({ postMessage: message => {
      const copy = structuredClone(message); this.sent.push(copy);
      if (this.hold(copy)) this.held.push(copy); else queueMicrotask(() => this.emit('message', copy));
    } }, clock.now);
  }
  postMessage(message, transfer = []) {
    const copy = structuredClone(message, { transfer }); this.received.push(copy);
    if (!this.terminated) queueMicrotask(() => { void this.runtime.handle(copy); });
  }
  addEventListener(type, listener) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(listener); }
  removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
  emit(type, data) { if (!this.terminated) for (const listener of this.listeners.get(type) ?? []) listener({ data }); }
  flush() { for (const message of this.held.splice(0)) this.emit('message', message); }
  terminate() { this.terminated++; this.runtime.dispose(); }
}
function load(path) {
  if (cache.has(path)) return cache.get(path);
  const exports = {}; cache.set(path, exports);
  let source = readFileSync(path, 'utf8').replaceAll('import.meta.url', JSON.stringify(pathToFileURL(path).href));
  // A bundler import is an asynchronous boundary. Keep it controllable for
  // cancellation/failure tests; return the actual committed library by default.
  if (path.endsWith('components\\financial-insights.tsx') || path.endsWith('components/financial-insights.tsx'))
    source = source.replace('import("@/lib/financial-insights")', '__insightsImport()');
  const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  const localRequire = name => {
    if (name === 'next/link') return { __esModule: true, default: props => React.createElement('a', props) };
    if (name.startsWith('@/') || name.startsWith('./')) {
      const base = name.startsWith('@/') ? fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url))
        : fileURLToPath(new URL(name, pathToFileURL(path)));
      return load(['.tsx', '.ts'].map(extension => base + extension).find(existsSync));
    }
    return require(name);
  };
  new Function('require', 'exports', '__insightsImport', output)(localRequire, exports, () => {
    active.imports++;
    if (active.importFailure) return Promise.reject(new Error('Synthetic import failure'));
    if (active.importGate) return active.importGate;
    return Promise.resolve(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url))));
  });
  if (path.endsWith('lib\\financial-insights.ts') || path.endsWith('lib/financial-insights.ts')) {
    const Base = exports.InsightsPanel;
    exports.InsightsPanel = class extends Base {
      constructor() {
        const state = active;
        super({ now: state.clock.now, timer: state.clock.timer, clear: state.clock.clear, worker: () => {
          if (state.constructFailure) throw new Error('Synthetic Worker construction failure');
          const worker = new WorkerDouble(state.clock); state.workers.push(worker); return worker;
        } });
        state.panels.push(this);
      }
      start(request) { return super.start(request).then(delivery => { if (delivery.mode === 'compare') active.handles.push(delivery.handle); return delivery; }); }
    };
  }
  return exports;
}
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const key of ['window', 'document', 'HTMLElement', 'SVGElement', 'Node', 'Event', 'MouseEvent'])
    Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(globalThis, 'Worker', { configurable: true, writable: true, value: undefined });
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  dom.window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  globalThis.matchMedia = dom.window.matchMedia; globalThis.localStorage = dom.window.localStorage;
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  ({ createRoot } = await import('react-dom/client'));
  runtime = load(fileURLToPath(new URL('../lib/financial-insights.worker.ts', import.meta.url)));
  fixtureFactory = load(fileURLToPath(new URL('../e2e/fixtures/financial-insights.ts', import.meta.url))).financialInsightsFixture;
  Insights = load(fileURLToPath(new URL('../components/financial-insights.tsx', import.meta.url))).default;
  Freshness = load(fileURLToPath(new URL('../components/research-freshness.tsx', import.meta.url))).default;
  Home = load(fileURLToPath(new URL('../app/page.tsx', import.meta.url))).default;
});
after(() => dom.window.close());

function fixture(kind = 'compare', issuer = company, version = 0) {
  const input = fixtureFactory(kind);
  function rewrite(value, key = '') {
    if (Array.isArray(value)) return value.map(item => rewrite(item));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, rewrite(v, k)]));
    if (key === 'ticker') return issuer.ticker;
    if (key === 'company_cik') return issuer.cik;
    if (key === 'data_version') return version;
    if (typeof value === 'string') return value.replaceAll('0000000001:0:0:0:', `${issuer.cik}:${version}:0:0:`).replaceAll('/data/1/', `/data/${Number(issuer.cik)}/`);
    return value;
  }
  return rewrite(input);
}
function freshness(issuer = company, version = 0) {
  const stream = { status: 'current', last_checked_at: null, last_successful_sync_at: null, latest_source_filing_date: null,
    pending_targets: [], inventory_complete: true, last_error: null, failure_stage: null };
  return { ticker: issuer.ticker, data_version: version, facts_version: 0, evidence_version: 0, status: 'current', facts: stream,
    evidence: stream, latest_indexed_filing: null, migration_required: false, scope: 'Synthetic offline inventory' };
}
async function mount(ctx, { strict = false, home = false, supported = true, importFailure = false, importGate = null, constructFailure = false, pin = 0 } = {}) {
  const focusListeners = new Map(['pointerdown', 'keydown', 'focusin'].map(type => [type, new Set()]));
  const nativeAdd = document.addEventListener.bind(document), nativeRemove = document.removeEventListener.bind(document);
  ctx.mock.method(document, 'addEventListener', (type, listener, options) => {
    if (options === true) focusListeners.get(type)?.add(listener);
    return nativeAdd(type, listener, options);
  });
  ctx.mock.method(document, 'removeEventListener', (type, listener, options) => {
    if (options === true) focusListeners.get(type)?.delete(listener);
    return nativeRemove(type, listener, options);
  });
  const focusListenerCount = () => [...focusListeners.values()].reduce((sum, group) => sum + group.size, 0);
  const state = { clock: new Clock(), workers: [], panels: [], handles: [], imports: 0, importFailure, importGate, constructFailure };
  active = state;
  ctx.mock.property(globalThis, 'Worker', supported ? class {} : undefined);
  const requests = [];
  ctx.mock.method(globalThis, 'fetch', (url, init = {}) => {
    const parsed = new URL(url, 'http://finlens.test');
    assert.equal(parsed.origin, 'http://finlens.test'); assert.ok(parsed.pathname.startsWith('/api/finlens/'));
    let resolve, reject;
    const promise = new Promise((a, b) => { resolve = a; reject = b; });
    requests.push({ path: parsed.pathname.slice('/api/finlens'.length), params: parsed.searchParams, init, resolve, reject, released: false });
    return promise; // Deliberately ignore abort to exercise actual owner guards.
  });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  let mounted = true, issuer = company;
  const catalogChanged = async () => true;
  async function render(next = issuer) {
    issuer = next;
    const content = home ? React.createElement(Home) : React.createElement(React.Fragment, null,
      React.createElement(Freshness, { key: issuer.ticker, ticker: issuer.ticker, catalogChanged }, React.createElement(Insights, { company: issuer })),
      React.createElement('button', { id: 'other-focus' }, 'Other focus'));
    await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, content) : content));
  }
  async function unmount() {
    if (mounted) { mounted = false; await act(async () => root.unmount()); host.remove(); localStorage.clear(); }
  }
  ctx.after(async () => {
    await unmount(); await delay(5);
    assert.equal(focusListenerCount(), 0, 'No document navigation-focus listeners survive cleanup');
    assert.ok(state.workers.every(worker => worker.terminated === 1), 'Every constructed Worker terminates exactly once');
    assert.equal(state.clock.timers.size, 0, 'No insights lifetime/request timers survive cleanup');
    for (const handle of state.handles) assert.equal(handle.inspect().parentBytes, 0);
  });
  async function until(predicate, label = 'offline operation') {
    const deadline = actualNow() + 10000;
    while (!predicate() && actualNow() < deadline) await act(async () => { state.clock.advance(0); await delay(1); });
    assert.ok(predicate(), label);
  }
  const request = (mode = 'discover', ticker = issuer.ticker) => requests.find(r => !r.released && !r.init.signal?.aborted
    && r.path === `/companies/${ticker}/financials/insights` && r.params.get('mode') === mode);
  const freshRequest = () => requests.find(r => !r.released && !r.init.signal?.aborted && r.path === `/companies/${issuer.ticker}/freshness`);
  async function release(item, payload, { status = 200, version = item?.init.headers?.['X-FinLens-Data-Version'] ?? null } = {}) {
    assert.ok(item, 'Expected pending request'); item.released = true;
    await act(async () => item.resolve(new Response(JSON.stringify(payload), { status, headers: {
      ...(version === null ? {} : { 'X-FinLens-Data-Version': String(version) }),
      ...(status === 409 ? { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } : {}),
    } })));
  }
  const panel = () => host.querySelector('.financial-insights');
  const button = text => [...host.querySelectorAll('button')].find(node => node.textContent === text);
  async function click(text) { const target = typeof text === 'string' ? button(text) : text; assert.ok(target, `Control ${text}`); assert.equal(target.disabled, false); await act(async () => target.click()); }
  const select = name => [...host.querySelectorAll('label')].find(node => node.firstChild?.textContent === name)?.querySelector('select');
  async function change(name, value) {
    const target = typeof name === 'string' ? select(name) : name; assert.ok(target); assert.equal(target.disabled, false);
    await act(async () => { Object.getOwnPropertyDescriptor(dom.window.HTMLSelectElement.prototype, 'value').set.call(target, value); target.dispatchEvent(new Event('change', { bubbles: true })); });
  }
  async function discover(years) {
    await until(() => request('discover'), 'Discovery request');
    const payload = fixture('discover', issuer, Number(request().init.headers['X-FinLens-Data-Version']));
    if (years) payload.fiscal_years = years;
    await release(request(), payload);
    await until(() => !panel().querySelector('[role="status"]').getAttribute('aria-busy').includes('true'), 'Discovery settlement');
  }
  async function compare(kind = 'compare') {
    await click('Compare annual periods'); await until(() => request('compare'), 'Explicit compare request');
    await release(request('compare'), fixture(kind, issuer, Number(request('compare').init.headers['X-FinLens-Data-Version'])));
    await until(() => panel().querySelector('.insights-result'), 'Comparison presentation');
  }
  async function page(text = 'Examine financial evidence') {
    await click(text); await until(() => !state.handles.at(-1).inspect().pendingPages && !panel().querySelector('[role="status"]').getAttribute('aria-busy').includes('true'), 'Evidence page committed');
  }
  async function checkVersion(version) {
    await act(async () => window.dispatchEvent(new Event('focus')));
    await release(freshRequest(), freshness(issuer, version));
  }
  await render();
  if (!home && pin !== null) await release(freshRequest(), freshness(issuer, pin));
  return { ...state, get imports() { return state.imports; }, state, host, panel, render, unmount, request, freshRequest, requests, release, until, button, click, select, change, discover, compare, page, checkVersion, focusListenerCount };
}

function initialTimers(ctx) {
  const nativeSet = globalThis.setTimeout, nativeClear = globalThis.clearTimeout, timers = [];
  ctx.mock.method(globalThis, 'setTimeout', (fn, ms, ...args) => {
    if (ms !== 30000) return nativeSet(fn, ms, ...args);
    const entry = { fired: false, cleared: false, id: null };
    entry.id = nativeSet(() => { entry.fired = true; fn(...args); }, ms); timers.push(entry); return entry.id;
  });
  ctx.mock.method(globalThis, 'clearTimeout', id => {
    const entry = timers.find(timer => timer.id === id); if (entry) entry.cleared = true;
    return nativeClear(id);
  });
  return timers;
}
const insightsRequests = app => app.requests.filter(request => request.path.endsWith('/financials/insights'));
function assertExpiredImport(app, timers) {
  assert.equal(app.panels.length, 0, 'Expired import must not construct a panel');
  assert.equal(app.workers.length, 0, 'Expired import must construct zero Workers');
  assert.equal(insightsRequests(app).length, 0, 'Expired import must start zero insights HTTP requests');
  assert.equal(app.handles.length, 0); assert.equal(app.panel().querySelector('.insights-result'), null);
  assert.equal(app.button('Cancel annual insights'), undefined); assert.equal(app.button('Compare annual periods').disabled, true);
  assert.equal(app.select('Earlier fiscal year').options.length, 1, 'No discovery READY publication');
  assert.match(app.panel().textContent, /timed out/); assert.ok(app.button('Retry year discovery'));
  assert.ok(timers.every(timer => timer.cleared || timer.fired), 'No stale UI deadline timer');
  assert.equal(app.clock.timers.size, 0);
}

for (const mode of ['monotonic-boundary', 'monotonic-delayed', 'wall-fallback', 'wall-regressed', 'monotonic-regressed', 'import-rejection'])
  test(`P2 elapsed import before timeout dispatch: ${mode}`, async ctx => {
    let mono = 100, wall = 1000000, resolveImport, rejectImport;
    ctx.mock.method(performance, 'now', () => mono); ctx.mock.method(Date, 'now', () => wall);
    const timers = initialTimers(ctx);
    const app = await mount(ctx, { importGate: new Promise((resolve, reject) => { resolveImport = resolve; rejectImport = reject; }) });
    const overdue = timers.at(-1); app.button('Cancel annual insights').focus();
    if (mode === 'monotonic-regressed') mono--;
    else if (mode === 'wall-fallback') wall += 31004;
    else { mono += mode === 'monotonic-boundary' ? 30000 : 31004; if (mode === 'wall-regressed') wall -= 1000; }
    await act(async () => {
      if (mode === 'import-rejection') rejectImport(new Error('Late import rejection'));
      else resolveImport(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url))));
      for (let i = 0; i < 40; i++) await Promise.resolve();
      assert.equal(overdue.fired, false, 'Import continuation delivered before timer callback');
    });
    assertExpiredImport(app, timers);
    assert.equal(document.activeElement, app.button('Retry year discovery'));
    app.state.importGate = null;
    await app.click('Retry year discovery'); await app.discover();
    assert.equal(app.workers.length, 1); assert.equal(insightsRequests(app).length, 1);
    assert.equal(app.button('Compare annual periods').disabled, false, 'Fresh retry owns a new budget');
  });

test('P2 real 31,004 ms event-loop delay delivers production import continuation before overdue timer', async ctx => {
  const timers = initialTimers(ctx); let finish;
  const app = await mount(ctx, { importGate: new Promise(resolve => { finish = resolve; }) });
  const overdue = timers.at(-1), start = actualNow(); let observation;
  app.button('Cancel annual insights').focus();
  await act(async () => {
    // Deliberately stall this isolated Node test's event loop. No timer callback
    // can run; import/Worker microtasks then run before the overdue timer task.
    while (actualNow() - start < 31004) { /* bounded real event-loop delay */ }
    finish(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url))));
    for (let i = 0; i < 40; i++) await Promise.resolve();
    observation = { elapsed: actualNow() - start, workers: app.workers.length, http: insightsRequests(app).length, timerFired: overdue.fired };
  });
  ctx.diagnostic(`Real delayed-import observation: ${JSON.stringify(observation)}`);
  assert.ok(observation.elapsed >= 31004); assert.equal(observation.timerFired, false);
  assertExpiredImport(app, timers);
  app.state.importGate = null; await app.click('Retry year discovery'); await app.discover();
  assert.equal(app.workers.length, 1); assert.equal(insightsRequests(app).length, 1);
});

test('P2 import time is not reset when request initialization starts', async ctx => {
  let mono = 100, finish;
  ctx.mock.method(performance, 'now', () => mono);
  const timers = initialTimers(ctx), app = await mount(ctx, { importGate: new Promise(resolve => { finish = resolve; }) });
  const overdue = timers.at(-1); mono += 20000;
  await act(async () => finish(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url)))));
  await app.until(() => app.request()); const request = app.request(); assert.equal(app.workers.length, 1);
  mono += 11004; await app.release(request, fixture('discover'));
  await app.until(() => app.button('Retry year discovery'));
  assert.equal(overdue.fired, false); assert.equal(request.init.signal.aborted, true);
  assert.equal(app.workers[0].terminated, 1); assert.equal(app.clock.timers.size, 0);
  assert.equal(app.select('Earlier fiscal year').options.length, 1); assert.equal(app.panel().querySelector('.insights-result'), null);
  assert.match(app.panel().textContent, /timed out/);
  await app.click('Retry year discovery'); await app.discover(); assert.equal(insightsRequests(app).length, 2);
});

test('P2 overdue initial comparison cannot publish READY after request initiation', async ctx => {
  let mono = 100; ctx.mock.method(performance, 'now', () => mono);
  const timers = initialTimers(ctx), app = await mount(ctx); await app.discover();
  await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const overdue = timers.at(-1), worker = app.workers.at(-1), request = app.request('compare');
  worker.hold = message => message.type === 'OP_COMPLETE' && message.operation === 0;
  await app.release(request, fixture()); await app.until(() => worker.held.length);
  const other = app.host.querySelector('#other-focus'); other.focus(); mono += 30000;
  await act(async () => worker.flush()); await app.until(() => app.button('Reload annual comparison'));
  assert.equal(overdue.fired, false); assert.equal(app.handles.length, 0, 'No initial READY delivery');
  assert.equal(worker.terminated, 1); assert.equal(worker.runtime.inspect().nodes, 0);
  assert.equal(request.init.signal.aborted, true); assert.equal(app.clock.timers.size, 0);
  assert.ok([...worker.listeners.values()].every(listeners => listeners.size === 0));
  assert.equal(app.panel().querySelector('.insights-result'), null); assert.equal(document.activeElement, other);
  assert.match(app.panel().textContent, /timed out/);
  await app.click('Reload annual comparison'); await app.until(() => app.request('compare'));
  await app.release(app.request('compare'), fixture()); await app.until(() => app.panel().querySelector('.insights-result'));
});

test('P2 synchronous panel setup cannot spend the budget and then allocate a Worker', async ctx => {
  let mono = 100, finish; ctx.mock.method(performance, 'now', () => mono);
  const app = await mount(ctx, { importGate: new Promise(resolve => { finish = resolve; }) });
  const library = load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url))), Base = library.InsightsPanel;
  ctx.mock.method(library, 'InsightsPanel', class extends Base { constructor() { super(); mono += 30000; } });
  await act(async () => finish(library));
  assert.equal(app.panels.length, 1); assert.equal(app.workers.length, 0); assert.equal(insightsRequests(app).length, 0);
  assert.match(app.panel().textContent, /timed out/);
  await app.click('Retry year discovery'); await app.discover(); assert.equal(app.workers.length, 1);
});

test('P2 Worker allocation rechecks after synchronous listener registration crosses the deadline', async ctx => {
  let mono = 100, finish; ctx.mock.method(performance, 'now', () => mono);
  const app = await mount(ctx, { importGate: new Promise(resolve => { finish = resolve; }) });
  const nativeAdd = window.addEventListener;
  const spy = ctx.mock.method(window, 'addEventListener', function (type, ...args) {
    const value = nativeAdd.call(this, type, ...args); if (type === 'focus') mono += 30000; return value;
  });
  await act(async () => finish(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url)))));
  assert.equal(app.workers.length, 0); assert.equal(insightsRequests(app).length, 0); assert.equal(app.clock.timers.size, 0);
  assert.match(app.panel().textContent, /timed out/); spy.mock.restore();
  await app.click('Retry year discovery'); await app.discover(); assert.equal(app.workers.length, 1);
});

test('P2 elapsed guard prevents HTTP after a delayed Worker STARTED continuation', async ctx => {
  let mono = 100; ctx.mock.method(performance, 'now', () => mono);
  const original = WorkerDouble.prototype.emit;
  const spy = ctx.mock.method(WorkerDouble.prototype, 'emit', function (type, data) {
    if (type === 'message' && data.type === 'STARTED') mono += 30000;
    return original.call(this, type, data);
  });
  const app = await mount(ctx); await app.until(() => app.button('Retry year discovery'));
  assert.equal(app.workers.length, 1); assert.equal(app.workers[0].terminated, 1); assert.equal(insightsRequests(app).length, 0);
  assert.equal(app.clock.timers.size, 0); assert.match(app.panel().textContent, /timed out/); spy.mock.restore();
  await app.click('Retry year discovery'); await app.discover(); assert.equal(insightsRequests(app).length, 1);
});

test('P2 expiry between initial promise settlement and React commit cannot publish financial UI', async ctx => {
  let mono = 100; ctx.mock.method(performance, 'now', () => mono);
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const worker = app.workers.at(-1); worker.hold = message => message.type === 'OP_COMPLETE' && message.operation === 0;
  await app.release(app.request('compare'), fixture()); await app.until(() => worker.held.length);
  const other = app.host.querySelector('#other-focus'); other.focus();
  await act(async () => {
    worker.flush(); for (let i = 0; i < 40; i++) await Promise.resolve();
    assert.equal(app.handles.length, 1, 'Promise delivered within the budget, before commit'); mono += 30000;
  });
  assert.equal(app.panel().querySelector('.insights-result'), null); assert.equal(app.handles[0].snapshot, null);
  assert.equal(app.clock.timers.size, 0); assert.match(app.panel().textContent, /timed out/); assert.equal(document.activeElement, other);
  await app.click('Reload annual comparison'); await app.until(() => app.request('compare'));
  await app.release(app.request('compare'), fixture()); await app.until(() => app.panel().querySelector('.insights-result'));
});

for (const strict of [false, true]) test(`1B.2A version zero, explicit compare and seven server-authored metrics strict ${strict}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.discover();
  assert.equal(app.request('compare'), undefined); assert.equal(app.select('Earlier fiscal year').value, '2024');
  assert.deepEqual([...app.select('Later fiscal year').options].map(o => o.value), ['', '2025', '2024']);
  await app.compare();
  assert.deepEqual([...app.panel().querySelectorAll('[data-insight-metric]')].map(node => node.dataset.insightMetric),
    ['revenue', 'operating_income', 'net_income', 'operating_margin', 'net_margin', 'operating_cash_flow', 'free_cash_flow']);
  assert.match(app.panel().textContent, /Five headline comparisons: complete/);
  assert.match(app.panel().textContent, /Publication 0 · facts 0 · evidence 0/);
  assert.match(app.panel().textContent, /2024-01-01 – 2024-12-31/);
  const model = app.handles.at(-1).snapshot;
  for (const statement of model.statements) assert.ok(app.panel().textContent.includes(statement.text), statement.key);
  for (const value of model.metrics) assert.ok(app.panel().textContent.includes(value.formatted));
  assert.equal(app.panels.length, 1, 'One panel survives StrictMode effect replay');
  assert.equal(app.panel().querySelector('.insights-metrics').open, false, 'Details do not bury sibling research');
});

test('1B.2A Home mounts inside freshness before the research grid and preserves every research link', async ctx => {
  const app = await mount(ctx, { home: true, supported: false });
  await app.release(app.requests.find(r => r.path === '/companies'), [company, otherCompany]);
  await app.release(app.requests.find(r => r.path === '/capabilities'), { ai_analysis_enabled: false });
  await app.release(app.freshRequest(), freshness());
  assert.ok(app.panel()); assert.equal(app.panel().nextElementSibling.className, 'research-grid');
  for (const id of ['insights-title', 'snapshot-title', 'history-title', 'filing-title', 'comparison-title', 'risk-comparison-title']) {
    assert.ok(app.host.querySelector(`.workspace-nav a[href="#${id}"]`)); assert.ok(app.host.querySelector(`#${id}`));
  }
  assert.match(app.panel().textContent, /require browser Worker support/); assert.equal(app.imports, 0);
  assert.ok(app.requests.some(r => r.path.endsWith('/financials/summary')));
  assert.ok(app.requests.some(r => r.path.endsWith('/financials/metrics/revenue')));
  assert.ok(app.requests.some(r => r.path.endsWith('/sources')));
});

test('1B.2A supported Home loads insights while snapshot, history and SEC research settle independently', async ctx => {
  const app = await mount(ctx, { home: true });
  await app.release(app.requests.find(r => r.path === '/companies'), [company, otherCompany]);
  await app.release(app.requests.find(r => r.path === '/capabilities'), { ai_analysis_enabled: false });
  await app.release(app.freshRequest(), freshness()); await app.discover();
  await app.release(app.requests.find(r => r.path.endsWith('/financials/summary')), {
    ticker: company.ticker, company_cik: company.cik, requested_period: 'quarter', period: null, metrics: {}, selection_policy: 'Synthetic empty snapshot',
  });
  await app.release(app.requests.find(r => r.path.endsWith('/financials/metrics/revenue')), {
    ticker: company.ticker, company_cik: company.cik, metric: 'revenue', unit: 'USD', requested_period: 'quarter',
    status: 'unavailable', reason: 'Synthetic history unavailable', history: [],
  });
  await app.release(app.requests.find(r => r.path.endsWith('/sources')), []);
  await app.compare();
  assert.match(app.host.querySelector('[aria-labelledby="snapshot-title"]').textContent, /No compatible metrics/);
  assert.match(app.host.querySelector('[aria-labelledby="history-title"]').textContent, /Synthetic history unavailable/);
  assert.match(app.host.querySelector('[aria-labelledby="filing-title"]').textContent, /Not indexed for filing research/);
  assert.ok(app.panel().querySelector('.insights-result'));
  const handle = app.handles.at(-1);
  await app.change(app.host.querySelector('#company'), otherCompany.ticker);
  assert.equal(handle.snapshot, null); assert.equal(app.panel().querySelector('.insights-result'), null);
});

test('1B.2A null publication cannot import or request; zero is admitted after verification', async ctx => {
  const app = await mount(ctx, { pin: null }); assert.equal(app.imports, 0); assert.equal(app.request(), undefined);
  assert.match(app.panel().textContent, /Waiting for a verified publication/);
  await app.release(app.freshRequest(), freshness()); await app.discover(); assert.equal(app.imports, 1);
});

for (const years of [[], [2025], [2025, 2024, 2023]]) test(`1B.2A exact discovered year list ${years}`, async ctx => {
  const app = await mount(ctx); await app.discover(years);
  assert.deepEqual([...app.select('Earlier fiscal year').options].slice(1).map(o => Number(o.value)), years);
  assert.equal(app.button('Compare annual periods').disabled, years.length < 2);
  if (years.length > 1) {
    await app.change('Earlier fiscal year', '2025'); assert.equal(app.select('Later fiscal year').value, '2025');
    assert.equal(app.button('Compare annual periods').disabled, true); assert.match(app.panel().textContent, /never swapped/);
  } else assert.match(app.panel().textContent, years.length ? /Only one supported fiscal year/ : /No supported annual fiscal years/);
});

for (const failure of ['import', 'construction']) test(`1B.2A ${failure} failure is recoverable without crashing siblings`, async ctx => {
  const app = await mount(ctx, { importFailure: failure === 'import', constructFailure: failure === 'construction' });
  await app.until(() => app.button('Retry year discovery'));
  assert.match(app.panel().textContent, /could not be loaded or verified/);
  app.state.importFailure = false; app.state.constructFailure = false;
  await app.click('Retry year discovery'); await app.discover(); assert.equal(app.button('Compare annual periods').disabled, false);
});

for (const leave of ['cancel', 'company', 'unmount']) test(`1B.2A deferred import cannot start after ${leave}`, async ctx => {
  let finish; const gate = new Promise(resolve => { finish = resolve; });
  const app = await mount(ctx, { importGate: gate }); assert.equal(app.imports, 1);
  if (leave === 'cancel') await app.click('Cancel annual insights');
  if (leave === 'company') await app.render(otherCompany);
  if (leave === 'unmount') await app.unmount();
  await act(async () => finish(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url)))));
  assert.equal(app.workers.length, 0); assert.equal(app.request(), undefined);
});

test('1B.2A conflict diagnostics never populate F values; exact nested fields remain available', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.compare('conflict');
  const fcf = app.panel().querySelector('[data-insight-metric="free_cash_flow"]');
  assert.match(fcf.textContent, /No admitted financial value/); assert.doesNotMatch(fcf.querySelector('.insights-values').textContent, /15/);
  assert.match(fcf.textContent, /Required operand is not admitted: capital_expenditures/);
  assert.match(app.panel().textContent, /Five headline comparisons: partial/);
  await app.page('Examine diagnostic inputs');
  assert.ok([...app.panel().querySelectorAll('.insights-record')].every(node => node.dataset.insightKey.startsWith('D|')));
  assert.match(app.panel().textContent, /Diagnostic values are not admitted financial results/);
  const page = app.handles.at(-1).page;
  for (const record of page.records) for (const [path, value] of record.fields) {
    const card = [...app.panel().querySelectorAll('.insights-record')].find(node => node.dataset.insightKey === record.ref.key);
    assert.ok(card.textContent.includes(path)); assert.ok(card.textContent.includes(value === null ? 'Not supplied (null)' : String(value)));
  }
});

test('1B.2A statement targets and full FCF → CapEx → source lineage cross bounded pages', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.compare();
  const fcf = app.panel().querySelector('[data-insight-metric="free_cash_flow"]');
  const trigger = [...fcf.querySelectorAll('button')].at(-1); trigger.focus(); await app.page(trigger);
  const handle = app.handles.at(-1);
  let card = [...app.panel().querySelectorAll('.insights-record')].find(node => node.dataset.insightKey.startsWith('F|comparison|free_cash_flow|'));
  assert.equal(document.activeElement, card);
  const follow = async (prefix, text) => {
    const node = [...app.panel().querySelectorAll('.insights-record')].find(item => item.dataset.insightKey.startsWith(prefix));
    assert.ok(node, prefix); const link = [...node.querySelectorAll('button')].find(item => item.textContent.includes(text));
    link.focus(); await app.page(link);
  };
  await follow('F|comparison|free_cash_flow|', 'earlier');
  await follow('F|observation|free_cash_flow|earlier|', 'capital expenditures');
  await follow('F|operand|free_cash_flow|earlier|capital_expenditures|', 'capital expenditures');
  assert.match(document.activeElement.dataset.insightKey, /^F\|observation\|capital_expenditures/);
  await follow('F|observation|capital_expenditures|earlier|', 'source');
  card = document.activeElement; assert.match(card.dataset.insightKey, /^F\|source\|/);
  assert.ok(card.querySelector('a[href^="https://www.sec.gov/Archives/edgar/data/"]'));
  assert.match(card.textContent, /PaymentsToAcquirePropertyPlantAndEquipment/);
  assert.match(card.textContent, /data.value/); assert.match(card.textContent, /data.accession_number/);
  assert.ok(handle.inspect().retainedPages <= 1); assert.ok(app.panel().querySelectorAll('.insights-record').length <= 25);
  assert.ok(app.workers.at(-1).received.filter(m => m.type === 'PAGE').some(m => m.page > 0));
});

test('1B.2A page operations coalesce duplicate clicks, reject busy changes and publish only on completion', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.compare();
  const worker = app.workers.at(-1), handle = app.handles.at(-1); worker.hold = m => m.type === 'OP_COMPLETE' && m.operation > 0;
  const target = app.button('Examine financial evidence');
  await act(async () => { target.click(); target.click(); });
  await app.until(() => worker.held.length === 1);
  assert.equal(worker.received.filter(m => m.type === 'PAGE').length, 1); assert.equal(handle.page, null);
  assert.equal(app.button('Examine diagnostic inputs').disabled, true);
  await assert.rejects(handle.requestPage('D', 0), error => error.code === 'PAGE_BUSY');
  const a = handle.requestPage('F', 0), b = handle.requestPage('F', 0); assert.equal(a, b);
  await act(async () => worker.flush()); await app.until(() => app.panel().querySelector('.insights-viewport'));
  assert.equal(handle.page.collection, 'F'); assert.equal(handle.inspect().retainedPages, 1);
});

for (const strict of [false, true]) for (const settlement of ['success', '409', 'failure']) test(`1B.2A year round trip rejects old ${settlement} and finalizer strict ${strict}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.discover([2025, 2024, 2023]);
  const form = app.panel().querySelector('form');
  await act(async () => { form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
  await app.until(() => app.request('compare')); const old = app.request('compare');
  assert.equal(app.requests.filter(r => r.params.get('mode') === 'compare').length, 1);
  await app.change('Earlier fiscal year', '2023'); await app.change('Earlier fiscal year', '2024');
  assert.equal(old.init.signal.aborted, true); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const replacement = app.request('compare'), cancel = app.button('Cancel annual insights'); cancel.focus();
  const freshCount = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  if (settlement === 'failure') await act(async () => old.reject(new Error('Obsolete private detail')));
  else await app.release(old, settlement === '409' ? {} : fixture(), settlement === '409' ? { status: 409, version: 1 } : {});
  assert.equal(document.activeElement, cancel); assert.equal(app.button('Compare annual periods').disabled, true);
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, freshCount);
  await app.release(replacement, fixture()); await app.until(() => app.panel().querySelector('.insights-result'));
  assert.equal(document.activeElement, app.button('Compare annual periods'));
  assert.equal(app.panel().querySelectorAll('.insights-result').length, 1);
});

for (const strict of [false, true]) test(`1B.2A company A-B-A suppresses ignored-abort success and 409 strict ${strict}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const old = app.request('compare'); await app.render(otherCompany); await app.release(app.freshRequest(), freshness(otherCompany)); await app.discover();
  await app.render(company); await app.release(app.freshRequest(), freshness()); await app.discover();
  const count = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await app.release(old, {}, { status: 409, version: 9 });
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, count); assert.equal(app.panel().querySelector('.insights-result'), null);
  await app.compare(); assert.equal(app.handles.at(-1).snapshot.ticker, 'TEST');
});

test('1B.2A current 409 reconciles publication once and never replays Compare', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  await app.release(app.request('compare'), {}, { status: 409, version: 1 }); await app.until(() => app.freshRequest());
  assert.equal(app.select('Earlier fiscal year').disabled, true);
  await app.release(app.freshRequest(), freshness(company, 1)); await app.discover();
  assert.equal(app.requests.filter(r => r.params.get('mode') === 'compare').length, 1);
  await app.compare(); assert.equal(app.handles.at(-1).snapshot.data_version, 1);
});

test('1B.2A already verified newer publication rejects an old pre-commit 409 callback', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const old = app.request('compare');
  await act(async () => window.dispatchEvent(new Event('focus'))); const check = app.freshRequest();
  const count = app.requests.filter(r => r.path.endsWith('/freshness')).length;
  await act(async () => {
    check.released = true; const response = new Response('{}'); response.json = async () => freshness(company, 1); check.resolve(response);
    for (let i = 0; i < 30; i++) await Promise.resolve();
    old.released = true; old.resolve(new Response('{}', { status: 409, headers: { 'X-FinLens-Data-Version': '1', 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } }));
    for (let i = 0; i < 30; i++) await Promise.resolve();
  });
  assert.equal(app.requests.filter(r => r.path.endsWith('/freshness')).length, count);
  await app.discover(); assert.equal(app.select('Earlier fiscal year').disabled, false);
});

for (const outcome of ['cancel', 'success', 'failure']) test(`1B.2A ${outcome} preserves deliberately moved focus`, async ctx => {
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  app.button('Cancel annual insights').focus(); const other = app.host.querySelector('#other-focus'); other.focus();
  if (outcome === 'cancel') await app.click('Cancel annual insights');
  else { await app.release(app.request('compare'), outcome === 'success' ? fixture() : {}, { status: outcome === 'success' ? 200 : 503 }); await app.until(() => !app.button('Cancel annual insights')); }
  assert.equal(document.activeElement, other);
});

test('1B.2A Cancel and explicit retry cannot be unlocked by old finalizers', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const old = app.request('compare'); await app.click('Cancel annual insights'); await app.click('Reload annual comparison'); await app.until(() => app.request('compare'));
  await app.release(old, fixture()); assert.equal(app.button('Compare annual periods').disabled, true);
  const replacement = app.request('compare'); await app.release(replacement, fixture()); await app.until(() => app.panel().querySelector('.insights-result'));
});

for (const failure of ['timeout', 'invalid', 'network']) test(`1B.2A ${failure} permits an explicit compare retry`, async ctx => {
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const old = app.request('compare');
  if (failure === 'timeout') await act(async () => app.clock.advance(30000));
  else if (failure === 'network') await act(async () => old.reject(new Error('Private synthetic error')));
  else await app.release(old, {});
  await app.until(() => app.button('Reload annual comparison')); assert.equal(app.panel().querySelector('.insights-result'), null);
  assert.doesNotMatch(app.panel().textContent, /Private synthetic/);
  await app.click('Reload annual comparison'); await app.until(() => app.request('compare'));
  await app.release(app.request('compare'), fixture()); await app.until(() => app.panel().querySelector('.insights-result'));
});

for (const failure of ['idle', 'absolute', 'worker', 'page-timeout', 'pagehide']) test(`1B.2A ${failure} clears financial results and bounded retention`, async ctx => {
  const app = await mount(ctx); await app.discover(); await app.compare();
  const handle = app.handles.at(-1), worker = app.workers.at(-1);
  if (failure === 'idle') {
    for (let i = 0; i < 20; i++) await act(async () => { app.clock.advance(15000); await delay(1); });
  } else if (failure === 'absolute') {
    for (let i = 0; i < 60; i++) await act(async () => { handle.interact(); app.clock.advance(15000); await delay(1); });
  } else if (failure === 'worker') await act(async () => worker.emit('error'));
  else if (failure === 'pagehide') await act(async () => window.dispatchEvent(new Event('pagehide')));
  else {
    worker.hold = m => m.type === 'OP_COMPLETE' && m.operation > 0; await app.click('Examine financial evidence');
    await app.until(() => worker.held.length); await act(async () => app.clock.advance(5000));
  }
  await app.until(() => !app.panel().querySelector('.insights-result'));
  assert.equal(handle.snapshot, null); assert.equal(handle.page, null); assert.equal(handle.inspect().parentBytes, 0);
  assert.match(app.panel().textContent, /closed or expired/); assert.ok(app.button('Reload annual comparison'));
});

test('1B.2A pending page replacement cannot move focus or survive a year edit', async ctx => {
  const app = await mount(ctx); await app.discover([2025, 2024, 2023]); await app.compare();
  const worker = app.workers.at(-1); worker.hold = m => m.type === 'OP_COMPLETE' && m.operation > 0;
  const trigger = app.button('Examine financial evidence'); trigger.focus(); await app.click(trigger); await app.until(() => worker.held.length);
  await app.change('Earlier fiscal year', '2023'); const selector = app.select('Earlier fiscal year'); selector.focus();
  await act(async () => worker.flush()); assert.equal(document.activeElement, selector); assert.equal(app.panel().querySelector('.insights-result'), null);
});

test('1B.2A deferred import has a bounded deadline and cannot construct a Worker after expiry', async ctx => {
  const native = globalThis.setTimeout, deadlines = [];
  ctx.mock.method(globalThis, 'setTimeout', (fn, ms, ...args) => {
    if (ms === 30000) deadlines.push(fn);
    return native(fn, ms, ...args);
  });
  let finish; const app = await mount(ctx, { importGate: new Promise(resolve => { finish = resolve; }) });
  const deadline = deadlines.at(-1); assert.equal(typeof deadline, 'function');
  app.button('Cancel annual insights').focus(); await act(async () => deadline());
  assert.match(app.panel().textContent, /timed out/); assert.equal(document.activeElement, app.button('Retry year discovery'));
  await act(async () => finish(load(fileURLToPath(new URL('../lib/financial-insights.ts', import.meta.url)))));
  assert.equal(app.workers.length, 0); assert.equal(app.request(), undefined);
});

test('1B.2A page completion never steals focus deliberately moved to another control', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.compare();
  const worker = app.workers.at(-1); worker.hold = m => m.type === 'OP_COMPLETE' && m.operation > 0;
  const trigger = app.button('Examine financial evidence'); trigger.focus(); await app.click(trigger); await app.until(() => worker.held.length);
  const other = app.host.querySelector('#other-focus'); other.focus(); await act(async () => worker.flush());
  await app.until(() => app.panel().querySelector('.insights-viewport')); assert.equal(document.activeElement, other);
});

function disabledTriggerBlur(trigger) {
  assert.equal(trigger.isConnected, true); assert.equal(trigger.disabled, true);
  // JSDOM retains focus when disabled and refuses blur() on an already-disabled
  // control. Release its remembered focus while momentarily enabled, then restore
  // disabled before delivery. This models native loss only; never focus a target.
  trigger.disabled = false; trigger.blur(); trigger.disabled = true;
  assert.equal(document.activeElement, document.body);
}
async function focusPageSetup(ctx, strict = false) {
  const app = await mount(ctx, { strict }); await app.discover(); await app.compare();
  await act(async () => app.panel().querySelector('.insights-evidence > summary').click());
  const worker = app.workers.at(-1); worker.hold = m => m.type === 'OP_COMPLETE' && m.operation > 0;
  return { app, worker };
}
async function flushFocusPage(app, worker) {
  await act(async () => worker.flush());
  await app.until(() => !app.handles.at(-1).inspect().pendingPages && app.panel().querySelector('.insights-viewport')?.getAttribute('aria-busy') === 'false');
  assert.equal(app.focusListenerCount(), 0);
}

for (const strict of [false, true]) for (const activation of ['pointer', 'Enter', ' ']) {
  test(`1B.2B connected disabled-trigger blur recovers ${JSON.stringify(activation)} activation strict ${strict}`, async ctx => {
    const { app, worker } = await focusPageSetup(ctx, strict);
    const trigger = app.button('Examine financial evidence'); trigger.focus();
    await act(async () => {
      if (activation === 'pointer') {
        trigger.dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })); trigger.click();
      } else {
        const type = activation === 'Enter' ? 'keydown' : 'keyup';
        trigger.addEventListener(type, () => trigger.click(), { once: true });
        trigger.dispatchEvent(new dom.window.KeyboardEvent(type, { key: activation, bubbles: true }));
      }
    });
    await app.until(() => worker.held.length); assert.equal(app.focusListenerCount(), 3);
    disabledTriggerBlur(trigger); assert.equal(app.focusListenerCount(), 3);
    await flushFocusPage(app, worker);
    assert.equal(document.activeElement, app.panel().querySelector('.insights-viewport'));
    assert.equal(trigger.isConnected, true); assert.equal(trigger.disabled, false);
  });
}

for (const intent of ['focus-other', 'focus-other-then-body', 'pointer-elsewhere', 'Tab', 'Tab-from-trigger', 'keyboard-elsewhere', 'focus-body']) {
  test(`1B.2B genuine ${intent} permanently revokes page focus ownership`, async ctx => {
    const { app, worker } = await focusPageSetup(ctx);
    const trigger = app.button('Examine financial evidence'); trigger.focus(); await app.click(trigger);
    await app.until(() => worker.held.length); disabledTriggerBlur(trigger);
    const other = app.host.querySelector('#other-focus');
    if (intent === 'focus-other' || intent === 'focus-other-then-body') {
      other.focus(); if (intent.endsWith('then-body')) other.blur();
    } else if (intent === 'pointer-elsewhere') {
      document.body.dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true }));
    } else if (intent === 'focus-body') {
      document.body.tabIndex = -1; document.body.focus(); ctx.after(() => document.body.removeAttribute('tabindex'));
    } else {
      (intent === 'Tab-from-trigger' ? trigger : document.body).dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: intent.startsWith('Tab') ? 'Tab' : 'ArrowDown', bubbles: true }));
    }
    const active = document.activeElement; assert.equal(app.focusListenerCount(), 0);
    await flushFocusPage(app, worker); assert.equal(document.activeElement, active);
    assert.notEqual(document.activeElement, app.panel().querySelector('.insights-viewport'));
  });
}

test('1B.2B body alone never grants a navigation focus ticket', async ctx => {
  const { app, worker } = await focusPageSetup(ctx);
  assert.equal(document.activeElement, document.body);
  await app.click('Examine financial evidence'); await app.until(() => worker.held.length);
  assert.equal(app.focusListenerCount(), 0); await flushFocusPage(app, worker);
  assert.equal(document.activeElement, document.body);
});

test('1B.2B record lineage and Previous/Next retain focus ownership through page replacement', async ctx => {
  const { app, worker } = await focusPageSetup(ctx);
  await act(async () => app.panel().querySelector('.insights-metrics > summary').click());
  const fcf = app.panel().querySelector('[data-insight-metric="free_cash_flow"]');
  const statement = [...fcf.querySelectorAll('.insights-statement')].find(n => n.textContent.startsWith('Free cash flow: 15 USD,'));
  const window = '2025-01-01/2025-12-31/annual'; let removed = false;
  async function follow(trigger, key) {
    trigger.focus(); await app.click(trigger); await app.until(() => worker.held.length);
    disabledTriggerBlur(trigger); await flushFocusPage(app, worker);
    const target = key ? [...app.panel().querySelectorAll('[data-insight-key]')].find(n => n.dataset.insightKey === key) : app.panel().querySelector('.insights-viewport');
    assert.equal(document.activeElement, target); removed ||= !trigger.isConnected;
    return target;
  }
  let record = await follow(statement.querySelector('button'), `F|observation|free_cash_flow|later||${window}|`);
  record = await follow([...record.querySelectorAll('button')].find(n => n.textContent.includes('capital expenditures')), `F|operand|free_cash_flow|later|capital_expenditures|${window}|`);
  record = await follow(record.querySelector('button'), `F|observation|capital_expenditures|later||${window}|`);
  record = await follow(record.querySelector('button'), 'F|source|||||10');
  assert.ok(record.querySelector('a[href^="https://www.sec.gov/"]')); assert.equal(removed, true);
  await follow(app.button('Examine financial evidence'));
  const first = app.handles.at(-1).page.records.map(r => r.ref.key);
  await follow(app.button('Next evidence page')); assert.equal(app.handles.at(-1).page.page, 1);
  await follow(app.button('Previous evidence page')); assert.equal(app.handles.at(-1).page.page, 0);
  assert.deepEqual(app.handles.at(-1).page.records.map(r => r.ref.key), first);
});

test('1B.2B duplicate and busy page attempts cannot overwrite the original focus ticket', async ctx => {
  const { app, worker } = await focusPageSetup(ctx);
  const trigger = app.button('Examine financial evidence'); trigger.focus();
  await act(async () => { trigger.click(); trigger.click(); app.button('Examine diagnostic inputs').click(); });
  await app.until(() => worker.held.length); assert.equal(app.focusListenerCount(), 3);
  assert.match(app.panel().textContent, /Another evidence page is loading/);
  const handle = app.handles.at(-1), original = handle.requestPage('F', 0);
  assert.equal(handle.requestPage('F', 0), original);
  await assert.rejects(handle.requestPage('D', 0), error => error.code === 'PAGE_BUSY');
  assert.equal(worker.received.filter(m => m.type === 'PAGE').length, 1);
  disabledTriggerBlur(trigger); await flushFocusPage(app, worker); await original;
  assert.equal(document.activeElement, app.panel().querySelector('.insights-viewport'));
});

for (const strict of [false, true]) for (const ending of ['year', 'company', 'publication', 'cancel', 'expiry', 'page-timeout', 'worker-failure', 'unmount']) {
  test(`1B.2B ${ending} releases page focus listeners and rejects stale focus strict ${strict}`, async ctx => {
    const { app, worker } = await focusPageSetup(ctx, strict);
    const trigger = app.button('Examine financial evidence'); trigger.focus(); await app.click(trigger);
    await app.until(() => worker.held.length); assert.equal(app.focusListenerCount(), 3);
    disabledTriggerBlur(trigger);
    if (ending === 'year') await app.change('Earlier fiscal year', '2025');
    else if (ending === 'company') await app.render(otherCompany);
    else if (ending === 'publication') await app.checkVersion(1);
    else if (ending === 'unmount') await app.unmount();
    else if (ending === 'page-timeout') await act(async () => app.clock.advance(5000));
    else if (ending === 'expiry') await act(async () => { app.clock.time += 300001; void app.handles.at(-1).snapshot; });
    else if (ending === 'worker-failure') await act(async () => worker.emit('error'));
    else await act(async () => app.handles.at(-1).dispose('cancelled'));
    await app.until(() => app.focusListenerCount() === 0, 'Focus listener cleanup');
    const external = document.createElement('button'); document.body.append(external); external.focus(); ctx.after(() => external.remove());
    await act(async () => worker.flush()); assert.equal(document.activeElement, external);
    assert.equal(app.focusListenerCount(), 0); assert.equal(app.handles.at(-1).inspect().parentBytes, 0);
  });
}

test('1B.2B synchronous paging failure releases focus ownership without moving focus', async ctx => {
  const { app } = await focusPageSetup(ctx);
  ctx.mock.method(app.handles.at(-1), 'requestPage', () => { throw new Error('Synthetic paging failure'); });
  const trigger = app.button('Examine financial evidence'); trigger.focus(); await app.click(trigger);
  assert.equal(app.focusListenerCount(), 0); assert.equal(document.activeElement, trigger);
  assert.match(app.panel().textContent, /Evidence could not be loaded/);
});

for (const strict of [false, true]) test(`1B.2A parsed success before year round trip cannot publish or move focus strict ${strict}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.discover([2025, 2024, 2023]); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const worker = app.workers.at(-1); worker.hold = m => m.type === 'OP_COMPLETE' && m.operation === 0;
  await app.release(app.request('compare'), fixture()); await app.until(() => worker.held.length);
  const selector = app.select('Earlier fiscal year'); selector.focus();
  await act(async () => {
    worker.flush();
    // Hold React's commit while production promise callbacks enqueue their result.
    for (let i = 0; i < 40; i++) await Promise.resolve();
    const set = Object.getOwnPropertyDescriptor(dom.window.HTMLSelectElement.prototype, 'value').set;
    set.call(selector, '2023'); selector.dispatchEvent(new Event('change', { bubbles: true }));
    set.call(selector, '2024'); selector.dispatchEvent(new Event('change', { bubbles: true }));
  });
  assert.equal(app.panel().querySelector('.insights-result'), null); assert.equal(document.activeElement, selector);
  await app.compare(); assert.ok(app.panel().querySelector('.insights-result'));
});

test('1B.2A backend markup is literal text and unsafe diagnostic URLs remain unlinked', async ctx => {
  const app = await mount(ctx); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const payload = fixture('nonfinite'); payload.statements.at(-1).text = '<script>synthetic()</script> Causality is not established.';
  const diagnostic = payload.evidence.find(n => n.ref.category === 'D' && n.ref.kind === 'source' && n.data.value === 'NaN');
  assert.ok(diagnostic); diagnostic.data.sec_url = 'javascript:synthetic()';
  await app.release(app.request('compare'), payload); await app.until(() => app.panel().querySelector('.insights-result'));
  assert.match(app.panel().textContent, /<script>synthetic\(\)<\/script>/); assert.equal(app.panel().querySelector('script'), null);
  await app.page('Examine diagnostic inputs');
  while (![...app.panel().querySelectorAll('.insights-record')].some(node => node.dataset.insightKey === diagnostic.ref.key)) {
    assert.equal(app.button('Next evidence page').disabled, false); await app.page('Next evidence page');
  }
  const card = [...app.panel().querySelectorAll('.insights-record')].find(node => node.dataset.insightKey === diagnostic.ref.key);
  assert.match(card.textContent, /javascript:synthetic\(\)/); assert.equal(card.querySelector('a'), null);
  for (const link of app.panel().querySelectorAll('.insights-record a')) {
    assert.equal(new URL(link.href).protocol, 'https:'); assert.ok(['sec.gov', 'www.sec.gov'].includes(new URL(link.href).hostname));
    assert.equal(link.rel, 'noopener noreferrer');
  }
});

for (const strict of [false, true]) for (const stage of ['compare', 'page']) test(`1B.2A unmount rejects delayed ${stage} callbacks strict ${strict}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.discover(); await app.click('Compare annual periods'); await app.until(() => app.request('compare'));
  const old = app.request('compare');
  if (stage === 'page') {
    await app.release(old, fixture()); await app.until(() => app.panel().querySelector('.insights-result'));
    const worker = app.workers.at(-1); worker.hold = m => m.type === 'OP_COMPLETE' && m.operation > 0;
    await app.click('Examine financial evidence'); await app.until(() => worker.held.length);
    await app.unmount(); await act(async () => worker.flush());
  } else { await app.unmount(); await app.release(old, fixture()); }
  assert.equal(app.host.isConnected, false); assert.ok(app.workers.every(worker => worker.terminated === 1));
});

test('1B.2A scoped responsive rules cover narrow controls, long values and visible focus inheritance', () => {
  const css = readFileSync(fileURLToPath(new URL('../app/globals.css', import.meta.url)), 'utf8');
  assert.match(css, /\.financial-insights[^\n]*overflow-wrap:anywhere/);
  assert.match(css, /@media \(max-width:480px\)[^\n]*\.financial-insights \.insights-values[^\n]*minmax\(0,1fr\)/);
  assert.match(css, /:focus-visible/);
  // Static evidence only; JSDOM does not establish 320px/zoom or NVDA acceptance.
});
