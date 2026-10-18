import test from "node:test";
import assert from "node:assert/strict";
import { getEventListeners } from "node:events";
import {
  FinLensApiError,
  citationForClaim,
  describeApiError,
  firstReadyCompany,
  getAnswer,
  getCompanies,
  getCapabilities,
  getFreshness,
  getFinancialSummary,
  getAnnualFinancials,
  getMetricHistory,
  getFilingContext,
  getFilingSources,
  getCompanyContext,
  getResearchAnswer,
  readyCompanyCount,
  searchableFilings,
  filingReadiness,
  versionedController,
  getPassageTone,
  filingToneIdentity,
} from "../lib/finlens-api.ts";

test('DEP-01A1 accepts effective backend capabilities for each profile', async ctx => {
  for (const [profile, enabled] of [['development', true], ['development', false], ['sec_readonly', false]]) {
    const payload = { research_mode: true, ai_analysis_configured: enabled, ai_analysis_enabled: enabled, server_profile: profile };
    ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(payload)));
    assert.deepEqual(await getCapabilities(), payload);
  }
});

test('DEP-01A1 unverified and inconsistent capability payloads fail closed', async ctx => {
  const valid = { research_mode: true, ai_analysis_configured: true, ai_analysis_enabled: true, server_profile: 'development' };
  for (const payload of [null, {}, { research_mode: true, ai_analysis_configured: true },
    { ...valid, ai_analysis_enabled: 'true' }, { ...valid, ai_analysis_enabled: 1 },
    { ...valid, ai_analysis_configured: 'true' }, { ...valid, research_mode: 'true' },
    { ...valid, server_profile: 'unknown' }, { ...valid, server_profile: 'sec_readonly' },
    { ...valid, ai_analysis_configured: false }]) {
    ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(payload)));
    await assert.rejects(getCapabilities(), error => error.code === 'INVALID_RESPONSE');
  }
});

test('DEP-01A1 capability transport failure cannot enable AI', async ctx => {
  ctx.mock.method(globalThis, 'fetch', async () => { throw new Error('offline'); });
  await assert.rejects(getCapabilities(), error => error.code === 'NETWORK_ERROR');
});

test('FD-01 filing readiness requires exact booleans and preserves the complete input', () => {
  const flags = [true, false, undefined, null, 'true', 'false', 1, 0, {}, []];
  const records = flags.map((flag, index) => ({ accession_number: `fixture-${index}`, ...(flag === undefined ? {} : { has_filing_chunks: flag }) }));
  const original = structuredClone(records);
  assert.deepEqual(records.map(filingReadiness), ['indexed', 'metadata_only', ...Array(8).fill('unknown')]);
  assert.deepEqual(searchableFilings(records), [records[0]]);
  assert.deepEqual(records, original);
});

function companyEvidence(overrides = {}) {
  return { ticker: 'AAPL', company_cik: '0000320193', company_name: 'Apple', retrieval_scope: 'company',
    query: 'revenue', data_version: 2, evidence_version: 1, searched_accessions: ['filing-a'],
    excluded_publication_count: 0, evidence_status: 'insufficient', context: '', citations: [], ...overrides };
}

test('company evidence uses one version-bound retrieval GET and no provider input', async ctx => {
  let calls = 0;
  const controller = versionedController(2, () => assert.fail('unexpected version change'));
  ctx.mock.method(globalThis, 'fetch', async (url, options) => {
    calls++;
    assert.equal(url, '/api/finlens/companies/AAPL/context?q=revenue&limit=5');
    assert.equal(options.headers['X-FinLens-Data-Version'], '2');
    assert.notEqual(options.signal, controller.signal);
    assert.equal(options.signal.aborted, false);
    assert.equal(options.cache, 'no-store');
    assert.equal(options.body, undefined);
    return new Response(JSON.stringify(companyEvidence()), { headers: { 'X-FinLens-Data-Version': '2' } });
  });
  assert.equal((await getCompanyContext('AAPL', '0000320193', 'revenue', controller.signal)).retrieval_scope, 'company');
  assert.equal(calls, 1);
});

for (const [name, overrides, header, code] of [
  ['company', { ticker: 'JPM' }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['CIK', { company_cik: '0000019617' }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['scope', { retrieval_scope: 'filing' }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['mixed scope', { accession_number: 'filing-a' }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['evidence version', { evidence_version: 3 }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['question', { query: 'other' }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['body version', { data_version: 1 }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['citation CIK', { citations: [{ company_cik: '0000019617', accession_number: 'filing-a' }] }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['citation accession', { citations: [{ company_cik: '0000320193', accession_number: 'not-searched' }] }, '2', 'EVIDENCE_SCOPE_MISMATCH'],
  ['stale header', {}, '3', 'DATA_VERSION_CHANGED'],
  ['missing header', {}, null, 'INVALID_RESPONSE'],
]) test(`company evidence rejects mismatched ${name}`, async ctx => {
  const controller = versionedController(2, () => {});
  ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(companyEvidence(overrides)), {
    headers: header === null ? {} : { 'X-FinLens-Data-Version': header },
  }));
  await assert.rejects(() => getCompanyContext('AAPL', '0000320193', 'revenue', controller.signal), error => error.code === code);
});

test("version disagreement rejects a response and asks for one scope refresh", async context => {
  let changes = 0;
  const controller = versionedController(2, () => changes++);
  context.mock.method(globalThis, "fetch", async (_, options) => {
    assert.equal(options.headers['X-FinLens-Data-Version'], '2');
    return new Response(JSON.stringify({ ticker: 'AAPL', matched: true }), { headers: { 'X-FinLens-Data-Version': '3' } });
  });
  await assert.rejects(() => getResearchAnswer('AAPL', '2024 revenue', controller.signal), error => error.code === 'DATA_VERSION_CHANGED');
  assert.equal(changes, 1);
});

test("requests one company-scoped deterministic answer with cancellation and no filing or provider input", async context => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options }); return jsonResponse({ ticker: "AAPL", matched: true });
  });
  const controller = new AbortController();
  const question = "latest quarterly revenue";
  await getResearchAnswer("AAPL", question, controller.signal);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/finlens/companies/AAPL/research-answer");
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), { question });
  assert.notEqual(calls[0].options.signal, controller.signal);
  assert.equal(calls[0].options.signal.aborted, false);
});

function jsonResponse(body, status = 200, code = null) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...(code ? { "X-FinLens-Error-Code": code } : {}),
    },
  });
}

test("loads companies from the live API path", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return jsonResponse([{ id: 1, ticker: "AAPL", name: "Apple Inc.", cik: "0000320193", exchange: "NASDAQ", has_indexed_filing: true, indexed_filing_count: 1 }]);
  });
  const companies = await getCompanies();
  assert.equal(companies[0].ticker, "AAPL");
  assert.equal(companies[0].has_indexed_filing, true);
  assert.equal(companies[0].indexed_filing_count, 1);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/finlens/companies");
  assert.equal(calls[0].options.cache, "no-store");
});

test("selects the first Ready company in stable order and counts readiness", () => {
  const companies = [
    { ticker: "MSFT", has_indexed_filing: false, indexed_filing_count: 0 },
    { ticker: "AAPL", has_indexed_filing: true, indexed_filing_count: 1 },
    { ticker: "NVDA", has_indexed_filing: true, indexed_filing_count: 2 },
  ];
  assert.equal(firstReadyCompany(companies).ticker, "AAPL");
  assert.equal(readyCompanyCount(companies), 2);
  assert.equal(firstReadyCompany([companies[0]]).ticker, "MSFT");
  assert.equal(readyCompanyCount([companies[0]]), 0);
  assert.equal(firstReadyCompany([]), undefined);
});

test("uses the existing source API and keeps only searchable filings", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    calls.push(url);
    return jsonResponse([
      { accession_number: "indexed", has_filing_chunks: true },
      { accession_number: "facts-only", has_filing_chunks: false },
    ]);
  });
  const filings = await getFilingSources("AAPL & Co");
  assert.equal(calls[0], "/api/finlens/companies/AAPL%20%26%20Co/sources");
  assert.deepEqual(searchableFilings(filings).map((filing) => filing.accession_number), ["indexed"]);
  assert.deepEqual(searchableFilings([]), []);
});

test("submits the selected company, filing, and question to answer API", async (context) => {
  let call;
  const citation = {
    citation_id: "source_1",
    sec_url: "https://www.sec.gov/Archives/official-index.html",
    accession_number: "filing-1",
    chunk_id: "chunk_0018",
  };
  context.mock.method(globalThis, "fetch", async (url, options) => {
    call = { url, options };
    return jsonResponse({
      evidence_status: "sufficient",
      answer: "Margin rose. [source_1]",
      claims: [{ text: "Margin rose.", citation_ids: ["source_1"] }],
      citations: [citation],
    });
  });
  const result = await getAnswer("AAPL", "filing-1", "gross margin", 3);
  assert.equal(call.url, "/api/finlens/companies/AAPL/filings/filing-1/answer");
  assert.equal(call.options.method, "POST");
  assert.deepEqual(JSON.parse(call.options.body), { question: "gross margin", limit: 3 });
  assert.equal(result.evidence_status, "sufficient");
  assert.equal(citationForClaim("source_1", result.citations).sec_url, citation.sec_url);
  assert.equal(citationForClaim("source_99", result.citations), undefined);
});

test("maps missing AI capability into neutral Research Mode fallback", async (context) => {
  context.mock.method(globalThis, "fetch", async () => jsonResponse(
    { detail: "OPENAI_API_KEY is required to generate an answer." },
    503,
    "LLM_UNAVAILABLE",
  ));
  await assert.rejects(
    () => getAnswer("AAPL", "filing-1", "gross margin"),
    (error) => {
      assert.ok(error instanceof FinLensApiError);
      assert.equal(error.status, 503);
      assert.equal(error.code, "LLM_UNAVAILABLE");
      assert.match(describeApiError(error), /SEC evidence remains available/);
      assert.doesNotMatch(describeApiError(error), /OPENAI_API_KEY/);
      return true;
    },
  );
});

test("distinguishes citation validation and network errors", async (context) => {
  context.mock.method(globalThis, "fetch", async () => jsonResponse(
    { detail: "Invalid citation" }, 502, "MALFORMED_MODEL_OUTPUT",
  ));
  await assert.rejects(
    () => getAnswer("AAPL", "filing-1", "question"),
    (error) => {
      assert.match(describeApiError(error), /citation checks/);
      return true;
    },
  );
  context.mock.restoreAll();
  context.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("network down");
  });
  await assert.rejects(
    () => getCompanies(),
    (error) => {
      assert.ok(error instanceof FinLensApiError);
      assert.equal(error.code, "NETWORK_ERROR");
      assert.match(describeApiError(error), /Cannot reach/);
      return true;
    },
  );
});

test("insufficient evidence response has no invented answer or sources", async (context) => {
  context.mock.method(globalThis, "fetch", async () => jsonResponse({
    evidence_status: "insufficient",
    answer: "The filing evidence retrieved does not provide enough support.",
    claims: [],
    citations: [],
  }));
  const answer = await getAnswer("AAPL", "filing-1", "unsupported topic");
  assert.equal(answer.evidence_status, "insufficient");
  assert.deepEqual(answer.claims, []);
  assert.deepEqual(answer.citations, []);
});

// DEP-01A2 Increment 1: deterministic clocks and deferred transports, no services.
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function deadlineClock(ctx) {
  let now = 0, next = 0;
  const timers = new Map(), cleared = [];
  ctx.mock.method(performance, 'now', () => now);
  ctx.mock.method(globalThis, 'setTimeout', (callback, delay) => {
    assert.equal(delay, 30_000);
    const id = ++next;
    timers.set(id, { callback, at: now + delay });
    return id;
  });
  ctx.mock.method(globalThis, 'clearTimeout', id => { cleared.push(id); timers.delete(id); });
  return {
    timers, cleared,
    elapseWithoutTimers(ms) { now += ms; },
    advance(ms) {
      now += ms;
      for (const [id, timer] of [...timers]) if (timer.at <= now && timers.delete(id)) timer.callback();
    },
  };
}

const isTimeout = error => error instanceof FinLensApiError && error.status === 0 && error.code === 'REQUEST_TIMEOUT';
const isCancelled = error => error.name === 'AbortError' && !(error instanceof FinLensApiError);
const flushTransport = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };

for (const phase of ['fetch', 'body']) for (const cause of ['timeout', 'caller']) {
  test(`DEP-01A2 stalled ${phase} ignores abort but settles on ${cause} and blocks late publication callbacks`, async ctx => {
    const clock = deadlineClock(ctx), pending = deferred();
    let changed = 0, delivered = false, bodyReads = 0, transportSignal;
    const caller = versionedController(2, () => changed++);
    const response = {
      ok: true, status: 200, headers: new Headers({ 'X-FinLens-Data-Version': '3' }),
      json() { bodyReads++; return phase === 'body' ? pending.promise : Promise.resolve([]); },
    };
    ctx.mock.method(globalThis, 'fetch', (_, init) => {
      transportSignal = init.signal;
      assert.notEqual(transportSignal, caller.signal);
      assert.equal(init.headers['X-FinLens-Data-Version'], '2');
      return phase === 'fetch' ? pending.promise : Promise.resolve(response);
    });
    const request = getCompanies(caller.signal);
    request.then(() => { delivered = true; }, () => {});
    await flushTransport();
    assert.equal(bodyReads, phase === 'body' ? 1 : 0);
    clock.advance(29_999);
    assert.equal(transportSignal.aborted, false);
    if (cause === 'timeout') clock.advance(1);
    else caller.abort('custom caller reason');
    await assert.rejects(request, cause === 'timeout' ? isTimeout : isCancelled);
    assert.equal(transportSignal.aborted, true);
    assert.equal(caller.signal.aborted, cause === 'caller');
    assert.equal(clock.timers.size, 0);
    assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
    pending.resolve(phase === 'fetch' ? response : []);
    await flushTransport();
    assert.equal(changed, 0);
    assert.equal(delivered, false);
    assert.equal(bodyReads, phase === 'body' ? 1 : 0, 'Late fetch is never consumed');
  });
}

for (const first of ['timeout', 'caller']) test(`DEP-01A2 first terminal cause ${first} survives the other cause and late rejection`, async ctx => {
  const clock = deadlineClock(ctx), pending = deferred(), caller = new AbortController();
  ctx.mock.method(globalThis, 'fetch', () => pending.promise);
  const request = getCompanies(caller.signal);
  if (first === 'timeout') { clock.advance(30_000); caller.abort(); }
  else { caller.abort(); clock.advance(30_000); }
  await assert.rejects(request, first === 'timeout' ? isTimeout : isCancelled);
  pending.reject(new TypeError('Late network error'));
  await flushTransport();
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
});

test('DEP-01A2 pre-cancelled requests never fetch and remove timer/listener', async ctx => {
  const clock = deadlineClock(ctx), caller = new AbortController();
  caller.abort(new Error('arbitrary caller reason'));
  ctx.mock.method(globalThis, 'fetch', () => assert.fail('Pre-cancelled request fetched'));
  await assert.rejects(getCompanies(caller.signal), isCancelled);
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
});

for (const phase of ['fetch', 'body']) test(`DEP-01A2 abort-aware ${phase} rejection cannot replace timeout with a transport error`, async ctx => {
  const clock = deadlineClock(ctx);
  ctx.mock.method(globalThis, 'fetch', (_, init) => {
    const pending = new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }));
    return phase === 'fetch' ? pending : Promise.resolve({ json: () => pending });
  });
  const request = getCompanies();
  await flushTransport();
  clock.advance(30_000);
  await assert.rejects(request, isTimeout);
  assert.equal(clock.timers.size, 0);
});

test('DEP-01A2 body receives the remaining deadline rather than a fresh 30 seconds', async ctx => {
  const clock = deadlineClock(ctx), fetched = deferred(), body = deferred();
  ctx.mock.method(globalThis, 'fetch', () => fetched.promise);
  const request = getCompanies();
  clock.advance(20_000);
  fetched.resolve({ json: () => body.promise });
  await flushTransport();
  clock.advance(9_999);
  assert.equal(clock.timers.size, 1);
  clock.advance(1);
  await assert.rejects(request, isTimeout);
  body.resolve([]);
  await flushTransport();
});

test('DEP-01A2 delayed timer cannot let validation return data or change a publication after expiry', async ctx => {
  const clock = deadlineClock(ctx);
  let changed = 0;
  const caller = versionedController(2, () => changed++);
  ctx.mock.method(globalThis, 'fetch', async () => ({
    ok: true, status: 200, json: async () => [],
    headers: { get() { clock.elapseWithoutTimers(30_000); return '3'; } },
  }));
  await assert.rejects(getCompanies(caller.signal), isTimeout);
  assert.equal(changed, 0);
  assert.equal(caller.signal.aborted, false);
  assert.equal(clock.timers.size, 0);
});

test('DEP-01A2 validation failure after a delayed deadline is still a timeout', async ctx => {
  const clock = deadlineClock(ctx);
  ctx.mock.method(globalThis, 'fetch', async () => ({
    status: 503, headers: new Headers(), json: async () => ({}),
    get ok() { clock.elapseWithoutTimers(30_000); return false; },
  }));
  await assert.rejects(getCompanies(), isTimeout);
  assert.equal(clock.timers.size, 0);
});

test('DEP-01A2 cancellation during metadata validation blocks changed and data delivery', async ctx => {
  const clock = deadlineClock(ctx);
  let changed = 0;
  const caller = versionedController(2, () => changed++);
  ctx.mock.method(globalThis, 'fetch', async () => ({
    ok: true, status: 200, json: async () => [],
    headers: { get() { caller.abort(); return '3'; } },
  }));
  await assert.rejects(getCompanies(caller.signal), isCancelled);
  assert.equal(changed, 0);
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
});

test('DEP-01A2 timeout leaves caller usable for an independent request and manual recovery at the same pin', async ctx => {
  const clock = deadlineClock(ctx), pending = deferred();
  let changed = 0;
  const caller = versionedController(2, () => changed++), calls = [];
  ctx.mock.method(globalThis, 'fetch', (_, init) => {
    calls.push(init);
    return calls.length === 1 ? pending.promise : Promise.resolve(new Response('[]', { headers: { 'X-FinLens-Data-Version': '2' } }));
  });
  const expired = getCompanies(caller.signal);
  clock.advance(30_000);
  await assert.rejects(expired, isTimeout);
  assert.equal(caller.signal.aborted, false);
  assert.deepEqual(await getFilingSources('AAPL', caller.signal), []);
  assert.deepEqual(await getCompanies(caller.signal), []);
  assert.ok(calls.every(init => init.headers['X-FinLens-Data-Version'] === '2'));
  assert.notEqual(calls[0].signal, calls[1].signal);
  pending.resolve(new Response('{}', { status: 409, headers: { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } }));
  await flushTransport();
  assert.equal(changed, 0);
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
});

for (const [name, response, code, status] of [
  ['malformed JSON', () => new Response('{'), 'INVALID_RESPONSE', 502],
  ['null JSON', () => new Response('null'), 'INVALID_RESPONSE', 502],
  ['broken stream', () => new Response(new ReadableStream({ start(controller) { controller.error(new TypeError('Broken stream')); } })), 'BODY_READ_ERROR', 0],
  ['network', () => { throw new TypeError('Network failed'); }, 'NETWORK_ERROR', 0],
  ['server', () => jsonResponse({ detail: 'Server unavailable' }, 503, 'SERVICE_UNAVAILABLE'), 'SERVICE_UNAVAILABLE', 503],
  ['non-JSON server', () => new Response('<html>Unavailable</html>', { status: 503 }), null, 503],
  ['version validation', () => new Response('[]', { headers: { 'X-FinLens-Data-Version': '3' } }), 'DATA_VERSION_CHANGED', 409],
]) test(`DEP-01A2 ${name} remains distinct from timeout and cleans up`, async ctx => {
  const clock = deadlineClock(ctx);
  let changed = 0;
  const caller = versionedController(2, () => changed++);
  ctx.mock.method(globalThis, 'fetch', async () => response());
  await assert.rejects(getCompanies(caller.signal), error => error instanceof FinLensApiError && error.code === code && error.status === status);
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
  clock.advance(30_000); caller.abort();
  assert.equal(changed, code === 'DATA_VERSION_CHANGED' ? 1 : 0);
});

for (const [name, invoke] of [
  ['catalog', signal => getCompanies(signal)],
  ['capabilities', signal => getCapabilities(signal)],
  ['freshness', signal => getFreshness('AAPL', signal)],
  ['snapshot', signal => getFinancialSummary('AAPL', 'quarter', signal)],
  ['annual comparison', signal => getAnnualFinancials('AAPL', null, signal)],
  ['history', signal => getMetricHistory('AAPL', 'revenue', 'quarter', signal)],
  ['filing discovery', signal => getFilingSources('AAPL', signal)],
  ['direct answer', signal => getResearchAnswer('AAPL', 'revenue', signal)],
  ['filing evidence', signal => getFilingContext('AAPL', 'filing-a', 'revenue', signal)],
  ['company evidence', signal => getCompanyContext('AAPL', '0000320193', 'revenue', signal)],
]) test(`DEP-01A2 ${name} has a 30-second deadline`, async ctx => {
  const clock = deadlineClock(ctx), caller = versionedController(2, () => assert.fail('Timed out scope changed'));
  ctx.mock.method(globalThis, 'fetch', () => new Promise(() => {}));
  const request = invoke(caller.signal);
  clock.advance(30_000);
  await assert.rejects(request, isTimeout);
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
});

test('DEP-01A2 AI generation retains its existing timeout policy and caller cancellation', async ctx => {
  const clock = deadlineClock(ctx), pending = deferred(), caller = new AbortController();
  let transport;
  ctx.mock.method(globalThis, 'fetch', (_, init) => { transport = init.signal; return pending.promise; });
  const request = getAnswer('AAPL', 'filing-a', 'revenue', 5, caller.signal);
  clock.advance(60_000);
  assert.equal(clock.timers.size, 0);
  assert.equal(transport.aborted, false);
  caller.abort();
  await assert.rejects(request, isCancelled);
  pending.reject(new Error('Late ignored abort'));
  await flushTransport();
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
});

test('DEP-01A2 successful validation clears the timer and detaches cancellation forwarding', async ctx => {
  const clock = deadlineClock(ctx), caller = new AbortController();
  let transport;
  ctx.mock.method(globalThis, 'fetch', async (_, init) => { transport = init.signal; return jsonResponse([]); });
  assert.deepEqual(await getCompanies(caller.signal), []);
  assert.equal(clock.timers.size, 0);
  assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
  clock.advance(30_000); caller.abort();
  assert.equal(transport.aborted, false, 'Finished transport has no remaining cancellation listener');
});

// P2: endpoint validators must share the original request's deadline and cleanup.
function endpointValidationFixture(ctx, endpoint, duringValidation, { invalid = false, version = 2 } = {}) {
  let changed = 0, transport;
  const caller = versionedController(version, () => changed++);
  const removeListener = ctx.mock.method(caller.signal, 'removeEventListener');
  const payload = endpoint === 'capabilities'
    ? { research_mode: true, ai_analysis_configured: false, ai_analysis_enabled: false }
    : companyEvidence({ data_version: version, evidence_version: 0 });
  Object.defineProperty(payload, endpoint === 'capabilities' ? 'server_profile' : 'citations', {
    enumerable: true,
    get() {
      duringValidation();
      return endpoint === 'capabilities'
        ? (invalid ? 'unknown' : 'development')
        : (invalid ? [{ company_cik: 'wrong-company', accession_number: 'filing-a' }] : []);
    },
  });
  ctx.mock.method(globalThis, 'fetch', async (_, init) => {
    transport = init.signal;
    assert.equal(init.headers['X-FinLens-Data-Version'], String(version));
    const response = new Response(null, { headers: { 'X-FinLens-Data-Version': String(version) } });
    // Keep getters intact so the real endpoint validator advances the clock.
    response.json = async () => payload;
    return response;
  });
  return {
    caller, payload,
    get changed() { return changed; },
    run: () => endpoint === 'capabilities' ? getCapabilities(caller.signal) : getCompanyContext('AAPL', '0000320193', 'revenue', caller.signal),
    assertCleanup(clock, aborted) {
      assert.equal(clock.timers.size, 0);
      assert.equal(clock.cleared.length, 1, 'Deadline is cleared exactly once');
      assert.equal(removeListener.mock.calls.filter(call => call.arguments[0] === 'abort').length, 1, 'Caller listener is removed exactly once');
      assert.equal(getEventListeners(caller.signal, 'abort').length, 0);
      assert.equal(transport.aborted, aborted);
      assert.equal(changed, 0, 'Endpoint validation cannot invalidate publication ownership');
    },
  };
}

for (const [endpoint, invalid] of [['capabilities', false], ['company evidence', false], ['company evidence', true], ['capabilities', true]]) {
  test(`DEP-01A2 P2 ${invalid ? 'invalid' : 'valid'} ${endpoint} crossing the deadline rejects with REQUEST_TIMEOUT`, async ctx => {
    const clock = deadlineClock(ctx);
    const fixture = endpointValidationFixture(ctx, endpoint, () => clock.elapseWithoutTimers(30_000), { invalid });
    await assert.rejects(fixture.run(), isTimeout);
    assert.equal(fixture.caller.signal.aborted, false, 'Deadline never aborts the caller');
    fixture.assertCleanup(clock, true);
    clock.advance(30_000); fixture.caller.abort();
    fixture.assertCleanup(clock, true);
  });
}

for (const endpoint of ['capabilities', 'company evidence']) {
  for (const invalid of [false, true]) test(`DEP-01A2 P2 ${invalid ? 'invalid' : 'valid'} ${endpoint} before deadline preserves validation and cleans up once`, async ctx => {
    const clock = deadlineClock(ctx);
    const fixture = endpointValidationFixture(ctx, endpoint, () => {
      assert.equal(clock.timers.size, 1, 'Original deadline remains armed during endpoint validation');
      assert.equal(getEventListeners(fixture.caller.signal, 'abort').length, 1, 'Caller cancellation remains connected during endpoint validation');
      clock.elapseWithoutTimers(29_999);
    }, { invalid, version: 0 });
    if (invalid) {
      await assert.rejects(fixture.run(), error => error instanceof FinLensApiError
        && error.code === (endpoint === 'capabilities' ? 'INVALID_RESPONSE' : 'EVIDENCE_SCOPE_MISMATCH')
        && error.status === (endpoint === 'capabilities' ? 502 : 409));
    } else assert.equal(await fixture.run(), fixture.payload);
    fixture.assertCleanup(clock, false);
    clock.advance(30_000); fixture.caller.abort();
    fixture.assertCleanup(clock, false);
  });

  for (const first of ['timeout', 'caller']) for (const invalid of [false, true]) {
    test(`DEP-01A2 P2 ${endpoint} ${invalid ? 'failure' : 'success'} preserves ${first} as first terminal cause during validation`, async ctx => {
      const clock = deadlineClock(ctx);
      const fixture = endpointValidationFixture(ctx, endpoint, () => {
        if (first === 'timeout') { clock.advance(30_000); fixture.caller.abort('Later cancellation'); }
        else { fixture.caller.abort('First cancellation'); clock.advance(30_000); }
      }, { invalid });
      await assert.rejects(fixture.run(), first === 'timeout' ? isTimeout : isCancelled);
      fixture.assertCleanup(clock, true);
    });
  }
}

for (const terminal of ['timeout', 'caller']) test(`DEP-01A2 P2 endpoint ${terminal} blocks late 409 publication callbacks on a sibling request`, async ctx => {
  const clock = deadlineClock(ctx), sibling = deferred();
  const fixture = endpointValidationFixture(ctx, 'company evidence', () => {
    if (terminal === 'timeout') clock.elapseWithoutTimers(30_000);
    else fixture.caller.abort();
  });
  const endpointFetch = globalThis.fetch;
  ctx.mock.method(globalThis, 'fetch', (url, init) => url.endsWith('/sources') ? sibling.promise : endpointFetch(url, init));
  const old = getFilingSources('AAPL', fixture.caller.signal);
  const oldRejection = assert.rejects(old, terminal === 'timeout' ? isTimeout : isCancelled);
  const endpointResult = fixture.run();
  try {
    await assert.rejects(endpointResult, terminal === 'timeout' ? isTimeout : isCancelled);
  } finally {
    sibling.resolve(new Response('{}', { status: 409, headers: { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } }));
    await oldRejection;
  }
  await flushTransport();
  assert.equal(clock.timers.size, 0);
  assert.equal(clock.cleared.length, 2, 'Each request clears its own deadline once');
  // Both requests remove their own listener from the shared caller signal.
  assert.equal(getEventListeners(fixture.caller.signal, 'abort').length, 0);
  assert.equal(fixture.changed, 0);
});

// SEC-NLP-01B: the new endpoint shares existing transport semantics.
function passageToneFixture(version = 0) {
  const accession = '0000320193-26-000020';
  const secUrl = `https://www.sec.gov/Archives/edgar/data/320193/${accession.replaceAll('-', '')}/${accession}-index.html`;
  const source = { chunk_id: 'chunk_0000', form: '10-Q', filed: '2026-07-31', filename: 'report.htm', sec_url: secUrl };
  const identity = filingToneIdentity({ ticker: 'AAPL', cik: '0000320193' }, { ...source, accession_number: accession });
  return { identity, value: { ticker: 'AAPL', company_cik: '0000320193', company_name: 'Synthetic Apple fixture', data_version: version,
    evidence_version: 0, publication: { accession_number: accession, data_version: 0, content_digest: 'a'.repeat(64) }, source,
    scope: 'published_chunk', offsets: 'unicode_code_point', text: 'strong weak',
    tone: { method_version: 'sec-filing-tone-v1', lexicon_version: 'authored-finance-tone-v1', status: 'scored', reason: null,
      score: { numerator: 0, denominator: 1 }, token_count: 2, positive_count: 1, negative_count: 1, negated_count: 0,
      matches: [{ text: 'strong', term: 'strong', start: 0, end: 6, polarity: 'positive', negator_span: null },
        { text: 'weak', term: 'weak', start: 7, end: 11, polarity: 'negative', negator_span: null }] } } };
}
for (const version of [0, 2, Number.MAX_SAFE_INTEGER]) test(`SEC-NLP-01B tone GET sends exactly one canonical pin ${version} and selectors only`, async ctx => {
  const { identity, value } = passageToneFixture(version);
  const controller = versionedController(version, () => assert.fail('Unexpected reconciliation'));
  let calls = 0;
  ctx.mock.method(globalThis, 'fetch', async (url, init) => {
    calls++;
    assert.equal(url, `/api/finlens/companies/AAPL/filings/${identity.accession_number}/chunks/chunk_0000/tone`);
    assert.deepEqual(init.headers, { 'X-FinLens-Data-Version': String(version) });
    assert.equal(init.cache, 'no-store'); assert.equal(init.body, undefined); assert.equal(init.method, undefined);
    assert.notEqual(init.signal, controller.signal);
    return new Response(JSON.stringify(value), { headers: { 'X-FinLens-Data-Version': String(version) } });
  });
  assert.deepEqual(await getPassageTone(identity, controller.signal), value);
  assert.equal(calls, 1);
});
for (const pin of [null, undefined, -1, '0', 0.5, NaN, Number.MAX_SAFE_INTEGER + 1, -0]) {
  test(`SEC-NLP-01B tone rejects invalid pin ${String(pin)} before fetching`, async ctx => {
    ctx.mock.method(globalThis, 'fetch', () => assert.fail('Invalid pin fetched'));
    await assert.rejects(getPassageTone(passageToneFixture().identity, versionedController(pin, () => {}).signal), error => error.code === 'TONE_INVALID_INPUT');
  });
}
test('SEC-NLP-01B tone refuses unbound controllers and invalid source identity before fetching', async ctx => {
  ctx.mock.method(globalThis, 'fetch', () => assert.fail('Unverified source fetched'));
  const { identity } = passageToneFixture();
  await assert.rejects(getPassageTone(identity, new AbortController().signal), error => error.code === 'TONE_INVALID_INPUT');
  await assert.rejects(getPassageTone({ ...identity, sec_url: 'https://www.sec.gov/other' }, versionedController(0, () => {}).signal), error => error.code === 'TONE_INVALID_INPUT');
});
for (const [name, header, mutate, code, changedCount] of [
  ['missing header', null, () => {}, 'INVALID_RESPONSE', 0],
  ['different header', '1', () => {}, 'DATA_VERSION_CHANGED', 1],
  ['noncanonical header', '00', () => {}, 'DATA_VERSION_CHANGED', 1],
  ['duplicate header', '0, 0', () => {}, 'DATA_VERSION_CHANGED', 1],
  ['body pin', '0', value => { value.data_version = 1; }, 'INVALID_RESPONSE', 0],
  ['source substitution', '0', value => { value.source.filename = 'other.htm'; }, 'INVALID_RESPONSE', 0],
  ['malformed payload', '0', value => { value.tone = null; }, 'INVALID_RESPONSE', 0],
]) test(`SEC-NLP-01B tone rejects ${name}`, async ctx => {
  const { identity, value } = passageToneFixture(); mutate(value);
  let changed = 0;
  ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(value), { headers: header === null ? {} : { 'X-FinLens-Data-Version': header } }));
  await assert.rejects(getPassageTone(identity, versionedController(0, () => changed++).signal), error => error.code === code);
  assert.equal(changed, changedCount);
});
test('SEC-NLP-01B tone captures originating identity before an ignored-abort delayed response', async ctx => {
  const { identity, value } = passageToneFixture(); const pending = deferred();
  ctx.mock.method(globalThis, 'fetch', () => pending.promise);
  const result = getPassageTone(identity, versionedController(0, () => {}).signal);
  identity.filename = 'caller-mutated.htm'; identity.accession_number = '0000320193-25-000001';
  pending.resolve(new Response(JSON.stringify(value), { headers: { 'X-FinLens-Data-Version': '0' } }));
  assert.deepEqual(await result, value);
});
for (const cause of ['timeout', 'caller']) for (const phase of ['fetch', 'body', 'validation']) {
  test(`SEC-NLP-01B tone ${cause} during ${phase} retains the shared deadline and blocks late 409`, async ctx => {
    const clock = deadlineClock(ctx), pending = deferred(), { identity, value } = passageToneFixture();
    let changed = 0, transport;
    const controller = versionedController(0, () => changed++);
    const expire = () => cause === 'timeout' ? clock.advance(30_000) : controller.abort();
    ctx.mock.method(globalThis, 'fetch', (_, init) => {
      transport = init.signal;
      if (phase === 'fetch') return pending.promise;
      if (phase === 'validation') Object.defineProperty(value, 'text', { enumerable: true, get() { expire(); return 'strong weak'; } });
      const response = new Response(null, { headers: { 'X-FinLens-Data-Version': '0' } });
      response.json = () => phase === 'body' ? pending.promise : Promise.resolve(value);
      return Promise.resolve(response);
    });
    const running = getPassageTone(identity, controller.signal);
    const rejected = assert.rejects(running, cause === 'timeout' ? isTimeout : isCancelled);
    if (phase !== 'validation') { await flushTransport(); expire(); }
    await rejected;
    pending.resolve(phase === 'fetch' ? new Response('{}', { status: 409, headers: { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } }) : value);
    await flushTransport();
    assert.equal(changed, 0); assert.equal(transport.aborted, true);
    assert.equal(clock.timers.size, 0); assert.equal(getEventListeners(controller.signal, 'abort').length, 0);
  });
}
