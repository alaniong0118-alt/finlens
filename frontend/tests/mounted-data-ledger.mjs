import assert from 'node:assert/strict';

const observations = new WeakMap();
const signature = (request, origin) => JSON.stringify([origin, request.init.method ?? 'GET', request.path,
  request.params.toString(), Object.hasOwn(request.init, 'body'), request.init.body ?? null,
  new Headers(request.init.headers).get('X-FinLens-Data-Version')]);

// Record raw identities before React can cancel or settle them. Notifications
// are ordered per request; unrelated requests may interleave freely.
export function mountedDataLedger() {
  let sequence = 0;
  const owner = {};
  const state = request => {
    const value = observations.get(request);
    assert.ok(value && value.owner === owner, 'Notification must bind to its observed request identity');
    return value;
  };
  return {
    started(request, url) {
      assert.ok(!observations.has(request), 'Request identity cannot start twice');
      assert.ok(url.pathname.startsWith('/api/finlens/'), 'Observed API prefix');
      assert.equal(request.path, url.pathname.slice('/api/finlens'.length), 'Row path binds to the actual URL');
      assert.equal(request.params.toString(), url.searchParams.toString(), 'Row query binds to the actual URL');
      const value = { owner, origin: url.origin, signal: request.init.signal,
        signature: signature(request, url.origin), started: ++sequence, events: [] };
      observations.set(request, value);
      const abort = () => value.events.push({ kind: 'abort', at: ++sequence });
      assert.ok(value.signal && !value.signal.aborted, 'Request starts with a live transport');
      value.signal.addEventListener('abort', abort, { once: true });
    },
    responded(request, response) {
      const value = state(request);
      assert.ok(!value.events.some(event => event.kind === 'response' || event.kind === 'failure'), 'One transport settlement per request');
      value.events.push({ kind: 'response', at: ++sequence, status: response.status,
        pin: response.headers.get('X-FinLens-Data-Version') });
    },
    failed(request) {
      const value = state(request);
      assert.ok(!value.events.some(event => event.kind === 'response' || event.kind === 'failure'), 'One transport settlement per request');
      value.events.push({ kind: 'failure', at: ++sequence });
    },
  };
}

export function assertPendingDataScope(records, { ticker = 'AAPL', version, metric = 'revenue',
  snapshotPeriod = 'quarter', historyPeriod = 'quarter', replay = false } = {}) {
  assert.ok(Number.isSafeInteger(version) && version >= 0);
  const base = `/companies/${ticker}/`;
  const shapes = [
    ['financials/annual', '', true], ['financials/quarters', '', true],
    [`financials/metrics/${metric}`, `period=${historyPeriod}&limit=12`, false],
    ['financials/summary', `period=${snapshotPeriod}`, false], ['sources', '', false],
  ];
  assert.equal(new Set(records).size, records.length, 'Raw request identities are unique');
  assert.equal(records.length, shapes.length + (replay ? 2 : 0), 'Exactly the declared endpoint owners and replays');
  const states = records.map(request => {
    const value = observations.get(request);
    assert.ok(value, 'Each row must be the original observed request object');
    assert.equal(signature(request, value.origin), value.signature, 'Raw request metadata cannot be rewritten');
    assert.equal(request.init.signal, value.signal, 'Transport identity cannot be replaced');
    assert.equal(value.origin, 'http://finlens.test');
    assert.equal(request.init.method ?? 'GET', 'GET');
    assert.equal(Object.hasOwn(request.init, 'body'), false, 'GET body must be absent, including raw null');
    assert.equal(new Headers(request.init.headers).get('X-FinLens-Data-Version'), String(version));
    assert.ok(value.events.every((event, index) => event.at > (index ? value.events[index - 1].at : value.started)), 'Per-request lifecycle order');
    assert.equal(value.events.some(event => event.kind === 'abort'), value.signal.aborted);
    return value;
  });
  assert.ok(states.every(value => value.owner === states[0].owner), 'One mounted scope owns every row');
  assert.ok(states.every((value, index) => !index || value.started > states[index - 1].started), 'Raw creation order is retained');
  assert.equal(new Set(states.map(value => value.signal)).size, records.length, 'Distinct transport controllers');
  const active = [], retired = [], discovery = [];
  for (const [suffix, query, isDiscovery] of shapes) {
    const matches = records.filter(request => request.path === base + suffix && request.params.toString() === query);
    assert.equal(matches.length, isDiscovery && replay ? 2 : 1, `Exact company/path/query for ${suffix}`);
    if (isDiscovery && replay) {
      const old = observations.get(matches[0]), replacement = observations.get(matches[1]);
      assert.equal(old.events.length, 1, 'Retired replay was only cancelled, never delivered');
      assert.equal(old.events[0].kind, 'abort');
      assert.ok(old.events[0].at < replacement.started, 'Cancellation precedes its own replacement');
      assert.equal(matches[0].released, false);
      retired.push(matches[0]);
    }
    const current = matches.at(-1), value = observations.get(current);
    assert.equal(value.events.length, 0, 'Current owner is live and pending');
    assert.equal(current.released, false);
    active.push(current);
    if (isDiscovery) discovery.push(current);
  }
  return { owner: discovery[0], discovery, siblings: active.filter(request => !discovery.includes(request)), active, retired };
}
