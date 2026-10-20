import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

const require = createRequire(import.meta.url), cache = new Map();
function load(path) {
  if (cache.has(path)) return cache.get(path);
  const exports = {}; cache.set(path, exports);
  const output = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function('require', 'exports', output)(name => name.startsWith('.')
    ? load(fileURLToPath(new URL(`${name}.ts`, pathToFileURL(path)))) : require(name), exports);
  return exports;
}
const lib = load(fileURLToPath(new URL('../lib/sec-risk-comparison.ts', import.meta.url)));
const { comparisonIssuers, comparisonChoices, preferredRiskSelection, comparisonFreshness, comparisonEvidence, createRiskComparison } = lib;
const issuers = [{ ticker: 'AAA', cik: '0000900001', name: 'Synthetic Alpha' }, { ticker: 'BBB', cik: '0000900002', name: 'Synthetic Beta' }];
const fresh = (issuer, version = 0, evidence = version) => ({ ticker: issuer.ticker, data_version: version, facts_version: version, evidence_version: evidence });
function evidence(issuer = issuers[0], version = 0, { count = 3, searched = true, topic = 'supply chain', evidenceVersion = version } = {}) {
  const accession = `${issuer.cik}-25-000001`;
  const text = `${issuer.name}: ${topic} may affect operations. 😀 <script>literal()</script>\n\n  Original wording.`;
  const citations = Array.from({ length: count }, (_, index) => ({ citation_id: `source_${index + 1}`, chunk_id: `chunk_${String(index).padStart(4, '0')}`,
    company_cik: issuer.cik, accession_number: accession, form: issuer.ticker === 'AAA' ? '10-K' : '10-Q', filed: issuer.ticker === 'AAA' ? '2025-10-01' : '2026-02-01',
    filename: 'synthetic.htm', start_char: index * 3000, end_char: index * 3000 + Array.from(text).length,
    sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${accession.replaceAll('-', '')}/${accession}-index.html`,
    similarity: 0.9, semantic_similarity: 0.9, lexical_score: 1, hybrid_score: 1.54, evidence_reason: 'strong_lexical' }));
  return { ticker: issuer.ticker, company_name: issuer.name, retrieval_scope: 'company', company_cik: issuer.cik, data_version: version, evidence_version: evidenceVersion,
    query: topic, searched_accessions: searched ? [accession] : [], excluded_publication_count: 0,
    evidence_status: count ? 'sufficient' : 'insufficient', citations, context: citations.map(c => {
      const metadata = Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, c[key]]));
      return `[SOURCE ${c.citation_id}]\nmetadata: ${JSON.stringify(metadata)}\ntext: |-\n${text.split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE ${c.citation_id}]`;
    }).join('\n\n') };
}
const pin = (version = 0, evidenceVersion = version) => ({ dataVersion: version, factsVersion: version, evidenceVersion });
const drain = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function machine() {
  let time = 0, owner = 'first', snapshot = null, active = 0, peak = 0;
  const requests = [], timers = new Map(), callbacks = [], snapshots = [];
  let timerId = 0;
  const request = (kind, ticker, signal, extra = {}) => {
    active++; peak = Math.max(peak, active); const result = deferred();
    const entry = { kind, ticker, signal, ...extra, ...result, settled: false };
    const settle = () => { if (!entry.settled) { active--; entry.settled = true; } };
    signal.addEventListener('abort', settle, { once: true });
    requests.push(entry); return result.promise.finally(settle);
  };
  const controller = createRiskComparison({ currentOwner: () => owner, publish: value => { snapshot = value; snapshots.push(value); }, now: () => time,
    schedule: (callback, delay) => { const id = ++timerId; timers.set(id, { callback, delay }); return id; }, unschedule: id => timers.delete(id),
    services: { freshness: (ticker, signal) => request('freshness', ticker, signal),
      context: (ticker, cik, query, signal) => request('context', ticker, signal, { cik, query }),
      pinned: (version, changed) => { const transport = new AbortController(); callbacks.push({ version, changed, transport }); return transport; } } });
  controller.activate();
  return { controller, requests, timers, callbacks, snapshots, get snapshot() { return snapshot; }, get peak() { return peak; },
    setOwner(value) { owner = value; }, setTime(value) { time = value; },
    submit() { return controller.submit(issuers, 'supply_chain', owner); },
    next(kind, ticker) { const value = requests.find(r => r.kind === kind && r.ticker === ticker && !r.delivered); assert.ok(value, `${kind} ${ticker}`); value.delivered = true; return value; },
    async freshness(index, version = index, evidenceVersion = version) { this.next('freshness', issuers[index].ticker).resolve(fresh(issuers[index], version, evidenceVersion)); await drain(); },
    async result(index, version = index, options) { this.next('context', issuers[index].ticker).resolve(evidence(issuers[index], version, options)); await drain(); },
    cleanup() { controller.deactivate(); assert.equal(timers.size, 0); },
  };
}

test('SEC-RISK-CC01 captures immutable identities and prefers AAPL/COST without readiness assumptions', () => {
  const pair = comparisonIssuers(issuers, ['AAA', 'BBB']); assert.ok(pair); assert.ok(Object.isFrozen(pair)); assert.ok(Object.isFrozen(pair[0]));
  assert.notEqual(pair[0], issuers[0]);
  assert.deepEqual(preferredRiskSelection(issuers), ['', '']);
  assert.deepEqual(preferredRiskSelection([{ ...issuers[0], ticker: 'AAPL' }, { ...issuers[1], ticker: 'COST', has_indexed_filing: false }]), ['AAPL', 'COST']);
});
for (const [name, catalog, selection] of [
  ['duplicate ticker', issuers, ['AAA', 'AAA']], ['same CIK alias', [issuers[0], { ...issuers[1], cik: issuers[0].cik }], ['AAA', 'BBB']],
  ['ambiguous catalog ticker', [...issuers, issuers[0]], ['AAA', 'BBB']], ['missing catalog entry', issuers, ['AAA', 'COST']],
  ['empty selection', issuers, ['', 'BBB']], ['too many', issuers, ['AAA', 'BBB', 'CCC']],
  ['lowercase ticker', [{ ...issuers[0], ticker: 'aaa' }, issuers[1]], ['aaa', 'BBB']],
  ['zero CIK', [{ ...issuers[0], cik: '0000000000' }, issuers[1]], ['AAA', 'BBB']],
  ['short CIK', [{ ...issuers[0], cik: '900001' }, issuers[1]], ['AAA', 'BBB']],
  ['empty name', [{ ...issuers[0], name: ' ' }, issuers[1]], ['AAA', 'BBB']],
]) test(`SEC-RISK-CC01 rejects ${name}`, () => assert.equal(comparisonIssuers(catalog, selection), null));
test('SEC-RISK-CC01 choices omit malformed or ambiguous catalog identities', () => {
  assert.deepEqual(comparisonChoices(null), []);
  assert.deepEqual(comparisonChoices([issuers[0], issuers[0], null, { ...issuers[0], ticker: 'bad' }, issuers[1]]), [issuers[1]]);
});
for (const version of [0, 1, Number.MAX_SAFE_INTEGER]) test(`SEC-RISK-CC01 valid pin ${version}`, () => {
  assert.deepEqual(comparisonFreshness(fresh(issuers[0], version), issuers[0]), pin(version));
  const response = evidence(issuers[0], version); const original = structuredClone(response);
  assert.equal(comparisonEvidence(response, issuers[0], pin(version), 'supply_chain'), response); assert.deepEqual(response, original);
});
for (const field of ['data_version', 'facts_version', 'evidence_version']) for (const value of [-1, -0, 0.5, NaN, Infinity, '0', true, null, undefined, Number.MAX_SAFE_INTEGER + 1]) {
  test(`SEC-RISK-CC01 malformed freshness ${field} ${String(value)} ${Object.is(value, -0)}`, () => {
    assert.throws(() => comparisonFreshness({ ...fresh(issuers[0]), [field]: value }, issuers[0]));
  });
}
for (const change of [{ ticker: 'BBB' }, { facts_version: 2 }, { evidence_version: 2 }]) test(`SEC-RISK-CC01 freshness binding ${JSON.stringify(change)}`, () => {
  assert.throws(() => comparisonFreshness({ ...fresh(issuers[0], 1), ...change }, issuers[0]));
});
const mutations = [
  ['ticker', v => { v.ticker = 'BBB'; }], ['CIK', v => { v.company_cik = issuers[1].cik; }], ['name', v => { v.company_name = issuers[1].name; }],
  ['body pin', v => { v.data_version = 1; }], ['evidence pin', v => { v.evidence_version = 1; }],
  ['query', v => { v.query = 'competition'; }], ['citation CIK', v => { v.citations[0].company_cik = issuers[1].cik; }],
  ['source URL', v => { v.citations[0].sec_url = 'https://www.sec.gov/Archives/other'; }],
  ['span', v => { v.citations[0].end_char = 1; }], ['body metadata', v => { v.context = v.context.replace('"form":"10-K"', '"form":"10-Q"'); }],
  ['orphan body', v => { v.context += '\n\n' + v.context; }], ['body missing', v => { v.context = ''; }],
  ['too many passages', v => { v.citations.push(...v.citations); }], ['unsearched source', v => { v.searched_accessions = []; }],
];
for (const [name, mutate] of mutations) test(`SEC-RISK-CC01 rejects entire ${name} response`, () => {
  const value = evidence(); mutate(value); assert.throws(() => comparisonEvidence(value, issuers[0], pin(), 'supply_chain'));
});
test('SEC-RISK-CC01 exact evidence version equality closes composition gap below data version', () => {
  const value = evidence(issuers[0], 3, { evidenceVersion: 1 });
  assert.throws(() => comparisonEvidence(value, issuers[0], pin(3, 2), 'supply_chain'));
  assert.equal(comparisonEvidence(value, issuers[0], pin(3, 1), 'supply_chain'), value);
});
test('SEC-RISK-CC01 swapped issuer payloads fail while local source IDs and Unicode remain independent', () => {
  const a = evidence(), b = evidence(issuers[1], 1); assert.equal(a.citations[0].citation_id, b.citations[0].citation_id);
  assert.equal(a.citations[0].chunk_id, b.citations[0].chunk_id);
  assert.throws(() => comparisonEvidence(b, issuers[0], pin(), 'supply_chain'));
  assert.throws(() => comparisonEvidence(a, issuers[1], pin(1), 'supply_chain'));
  comparisonEvidence(a, issuers[0], pin(), 'supply_chain'); comparisonEvidence(b, issuers[1], pin(1), 'supply_chain');
});
test('SEC-RISK-CC01 synchronous reservation, four GET chains and independent 0/positive results', async () => {
  const m = machine(); assert.equal(m.submit(), true); assert.equal(m.submit(), false); assert.equal(m.requests.length, 2);
  await m.freshness(1); await m.result(1); assert.equal(m.snapshot.columns[1].status, 'evidence'); assert.equal(m.snapshot.columns[0].status, 'pending');
  await m.freshness(0); await m.result(0); assert.deepEqual(m.snapshot.columns.map(c => c.pin.dataVersion), [0, 1]);
  assert.equal(m.requests.length, 4); assert.equal(m.peak, 2); assert.equal(m.timers.size, 0); m.cleanup();
});
for (const [kind, count, searched, expected] of [['no eligible', 0, false, 'no_publications'], ['no match', 0, true, 'insufficient']]) {
  test(`SEC-RISK-CC01 ${kind} distinct from failures`, async () => { const m = machine(); m.submit(); await m.freshness(0); await m.result(0, 0, { count, searched }); assert.equal(m.snapshot.columns[0].status, expected); m.cleanup(); });
}
test('SEC-RISK-CC01 one malformed freshness cannot block the other chain', async () => {
  const m = machine(); m.submit(); m.next('freshness', 'AAA').resolve({ ...fresh(issuers[0]), ticker: 'BBB' }); await drain();
  await m.freshness(1); await m.result(1); assert.deepEqual(m.snapshot.columns.map(c => c.status), ['error', 'evidence']); assert.equal(m.requests.length, 3); m.cleanup();
});
test('SEC-RISK-CC01 one rejected context preserves peer without fallback or replay', async () => {
  const m = machine(); m.submit(); await m.freshness(0); await m.freshness(1);
  m.next('context', 'AAA').reject(new Error('private underlying message')); await drain(); await m.result(1);
  assert.deepEqual(m.snapshot.columns.map(c => c.status), ['error', 'evidence']); assert.equal(m.snapshot.columns[0].message, 'Evidence unavailable or unverified.'); assert.equal(m.requests.length, 4); m.cleanup();
});
test('SEC-RISK-CC01 current changed callback invalidates only its issuer and pin', async () => {
  const m = machine(); m.submit(); await m.freshness(0); await m.freshness(1); await m.result(1);
  m.callbacks[0].changed(); assert.equal(m.snapshot.columns[0].status, 'error'); assert.equal(m.snapshot.columns[0].pin, undefined);
  assert.equal(m.snapshot.columns[1].status, 'evidence'); m.next('context', 'AAA').resolve(evidence()); await drain();
  assert.equal(m.snapshot.columns[0].status, 'error'); assert.equal(m.requests.length, 4); m.cleanup();
});
for (const at of [29999, 30000, 30001]) test(`SEC-RISK-CC01 commit boundary at ${at}ms covers validation and both chains`, async () => {
  const m = machine(); m.submit(); await m.freshness(0); m.setTime(at); await m.result(0);
  assert.equal(m.snapshot.columns[0].status, at < 30000 ? 'evidence' : 'timeout'); m.cleanup();
});
test('SEC-RISK-CC01 freshness consuming the total budget cannot dispatch context', async () => {
  const m = machine(); m.submit(); m.setTime(30000); await m.freshness(0);
  assert.equal(m.requests.length, 2); assert.deepEqual(m.snapshot.columns.map(c => c.status), ['timeout', 'timeout']); assert.equal(m.timers.size, 0); m.cleanup();
});
test('SEC-RISK-CC01 deadline includes synchronous validation before result commitment', async () => {
  const m = machine(); m.submit(); await m.freshness(0); const response = evidence();
  Object.defineProperty(response, 'company_name', { enumerable: true, get() { m.setTime(30000); return issuers[0].name; } });
  m.next('context', 'AAA').resolve(response); await drain(); assert.equal(m.snapshot.columns[0].status, 'timeout'); m.cleanup();
});
test('SEC-RISK-CC01 deadline preserves completed peer and rejects ignored-abort late result', async () => {
  const m = machine(); m.submit(); await m.freshness(0); await m.freshness(1); await m.result(1);
  const late = m.next('context', 'AAA'); m.setTime(30000); [...m.timers.values()][0].callback();
  assert.deepEqual(m.snapshot.columns.map(c => c.status), ['timeout', 'evidence']); assert.equal(late.signal.aborted, true);
  late.resolve(evidence()); await drain(); assert.equal(m.snapshot.columns[0].status, 'timeout'); m.cleanup();
});
test('SEC-RISK-CC01 early timer firing does not restart or shorten monotonic deadline', () => {
  const m = machine(); m.submit(); const first = [...m.timers.values()][0]; m.timers.clear(); m.setTime(10000); first.callback();
  assert.equal(m.snapshot.columns[0].status, 'pending'); assert.equal([...m.timers.values()][0].delay, 20000);
  m.setTime(30000); [...m.timers.values()][0].callback(); assert.equal(m.snapshot.columns[0].status, 'timeout'); m.cleanup();
});
for (const action of ['invalidate', 'cancel', 'deactivate', 'owner']) test(`SEC-RISK-CC01 ${action} guards stale success, changed and finalizers`, async () => {
  const m = machine(); m.submit(); await m.freshness(0); const old = m.next('context', 'AAA'), changed = m.callbacks[0].changed;
  if (action === 'owner') m.setOwner('catalog changed before cleanup'); else m.controller[action]();
  const before = m.snapshot; changed(); old.resolve(evidence()); await drain(); assert.equal(m.snapshot, before);
  m.controller.reconcile(); m.controller.activate(); m.setOwner('new'); m.controller.invalidate(); assert.equal(m.submit(), true);
  await m.freshness(0, 1); const newRequest = m.next('context', 'AAA'); changed(); assert.equal(newRequest.signal.aborted, false);
  newRequest.resolve(evidence(issuers[0], 1)); await drain(); assert.equal(m.snapshot.columns[0].status, 'evidence'); m.cleanup();
});
test('SEC-RISK-CC01 StrictMode setup/cleanup does not submit, and inactive controller refuses submissions', () => {
  const m = machine(); m.controller.deactivate(); assert.equal(m.submit(), false); m.controller.activate(); assert.equal(m.requests.length, 0);
  assert.equal(m.submit(), true); m.cleanup(); m.controller.activate(); assert.equal(m.requests.length, 2); m.cleanup();
});

for (const [name, header, bodyVersion] of [['missing', null, 0], ['malformed', '00', 0], ['wrong', '1', 0], ['body mismatch', '0', 1], ['duplicate', '0, 0', 0]]) {
  test(`SEC-RISK-CC01 real transport rejects ${name} context header/body pin`, async t => {
    const previous = globalThis.fetch; t.after(() => { globalThis.fetch = previous; });
    globalThis.fetch = async url => {
      const freshness = String(url).endsWith('/freshness');
      return new Response(JSON.stringify(freshness ? fresh(issuers[0]) : evidence(issuers[0], bodyVersion)),
        { headers: { 'Content-Type': 'application/json', ...(!freshness && header !== null ? { 'X-FinLens-Data-Version': header } : {}) } });
    };
    let snapshot; const controller = createRiskComparison({ currentOwner: () => 'real', publish: s => { snapshot = s; } });
    controller.activate(); t.after(() => controller.deactivate()); controller.submit(issuers, 'supply_chain', 'real');
    for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));
    assert.equal(snapshot.columns[0].status, 'error'); assert.equal(snapshot.columns[0].result, undefined);
  });
}
