// Dedicated frontend-only entry point. No mixed research suite, Python helper,
// child process, backend import, service startup or real transport is imported.
import test, { describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';
import { readEvidenceCsv } from './helpers/evidence-csv.mjs';

// File-local hooks must not become shared root hooks under --test-isolation=none.
describe('evidence report export', { concurrency: false }, () => {
const frontend = fileURLToPath(new URL('..', import.meta.url));
const globalKeys = ['window', 'document', 'HTMLElement', 'SVGElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
let previousGlobals;
let dom, createRoot, FilingResearch, Freshness, ReportExport, createEvidenceReport, evidenceReportText, evidenceReportHtml, evidenceReportCsv;
before(async () => {
  previousGlobals = new Map(globalKeys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test', pretendToBeVisual: true });
  for (const key of ['window', 'document', 'HTMLElement', 'SVGElement', 'Node', 'Event', 'MouseEvent'])
    Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, writable: true, value: true });
  ({ createRoot } = await import('react-dom/client'));
  const load = componentLoader(frontend);
  FilingResearch = load(resolve(frontend, 'components/filing-research.tsx')).default;
  Freshness = load(resolve(frontend, 'components/research-freshness.tsx')).default;
  ReportExport = load(resolve(frontend, 'components/evidence-report-export.tsx')).default;
  ({ createEvidenceReport, evidenceReportText, evidenceReportHtml, evidenceReportCsv } = load(resolve(frontend, 'lib/evidence-report.ts')));
});
after(() => {
  dom.window.close();
  for (const [key, descriptor] of previousGlobals) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
});
const company = { id: 1, ticker: 'AAA', name: 'Synthetic Alpha', cik: '0000900001', exchange: 'TEST', has_indexed_filing: true, indexed_filing_count: 2 };
const other = { ...company, id: 2, ticker: 'BBB', cik: '0000900002', name: 'Synthetic Beta' };
const accession = (issuer = company, suffix = '000001') => `${issuer.cik}-25-${suffix}`;
function filing(issuer = company, suffix = '000001') {
  const acc = accession(issuer, suffix);
  return { accession_number: acc, form: '10-K', filed: '2025-02-01', period_start: null, period_end: null, metrics: [], has_filing_chunks: true,
    sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${acc.replaceAll('-', '')}/${acc}-index.html` };
}
const originals = Array.from({ length: 5 }, (_, index) => `Synthetic passage ${index + 1}. ` + 'Original retained source wording. '.repeat(8)
  + '\n\n  Unicode 😀 e\u0301, literal <script>doNotRun()</script>, [SOURCE source_9] and javascript:evil are quoted data.');
function evidence({ issuer = company, scope = 'filing', query = 'supply chain', version = 0, count = 5, suffix = '000001', evidenceVersion = 0 } = {}) {
  const f = filing(issuer, suffix);
  const citations = originals.slice(0, count).map((text, index) => ({ citation_id: `source_${index + 1}`, chunk_id: `chunk_${String(index).padStart(4, '0')}`,
    accession_number: f.accession_number, form: f.form, filed: f.filed, filename: scope === 'company' ? 'synthetic.htm' : 'synthetic+legacy.htm',
    start_char: index * 3000, end_char: index * 3000 + Array.from(text).length, sec_url: f.sec_url,
    similarity: .8, semantic_similarity: .8, lexical_score: 1, hybrid_score: 1, evidence_reason: 'strong_lexical',
    ...(scope === 'company' ? { company_cik: issuer.cik } : {}) }));
  const context = citations.map((citation, index) => {
    const head = scope === 'company' ? `metadata: ${JSON.stringify(Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, citation[key]])))}`
      : `chunk_id: ${citation.chunk_id}\naccession_number: ${citation.accession_number}\nform: ${citation.form}\nsimilarity: ${citation.similarity.toFixed(6)}`;
    return `[SOURCE ${citation.citation_id}]\n${head}\ntext: |-\n${originals[index].split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE ${citation.citation_id}]`;
  }).join('\n\n');
  return { ticker: issuer.ticker, company_name: issuer.name, query, context, citations, evidence_status: count ? 'sufficient' : 'insufficient',
    ...(scope === 'company' ? { retrieval_scope: 'company', company_cik: issuer.cik, data_version: version, evidence_version: evidenceVersion,
      searched_accessions: [f.accession_number, accession(issuer, '000002')], excluded_publication_count: 1 } : { accession_number: f.accession_number }) };
}
function fresh(issuer, version) {
  const stream = { status: 'current', last_checked_at: null, last_successful_sync_at: null, latest_source_filing_date: null, pending_targets: [], inventory_complete: false, last_error: null, failure_stage: null };
  return { ticker: issuer.ticker, data_version: version, facts_version: 0, evidence_version: 0, status: 'current', facts: stream, evidence: stream, latest_indexed_filing: null, migration_required: false, scope: 'Synthetic frontend-only fixture' };
}
const path = (issuer, suffix) => `/companies/${issuer.ticker}/${suffix}`;
async function mount(ctx, { strict = false, exportOnly = null } = {}) {
  assert.ok(document === dom.window.document, 'Report mounts and download mocks must own the same DOM realm');
  const requests = [], urls = [], revoked = [], downloads = [];
  let serial = 0, failCreate = false, failClick = false;
  ctx.mock.method(URL, 'createObjectURL', blob => { if (failCreate) throw new Error('Synthetic allocation failure'); const url = `blob:finlens.test/${++serial}`; urls.push({ url, blob }); return url; });
  ctx.mock.method(URL, 'revokeObjectURL', url => revoked.push(url));
  ctx.mock.method(dom.window.HTMLAnchorElement.prototype, 'click', function () {
    if (failClick) throw new Error('Synthetic click failure');
    assert.equal(this.isConnected, true); downloads.push({ url: this.href, filename: this.download });
  });
  // All transports are deferred fixtures; ignore abort during later delivery to
  // exercise actual application ownership guards, never native network calls.
  ctx.mock.method(globalThis, 'fetch', (input, init = {}) => {
    const url = new URL(input, 'http://finlens.test');
    assert.equal(url.origin, 'http://finlens.test'); assert.ok(url.pathname.startsWith('/api/finlens/companies/'));
    assert.ok(!/answer$/.test(url.pathname) || /research-answer$/.test(url.pathname), 'No AI/provider route');
    let resolve; const promise = new Promise(done => { resolve = done; });
    requests.push({ path: url.pathname.slice('/api/finlens'.length), params: url.searchParams, init, resolve, released: false });
    return promise;
  });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  let issuer = company, enabled = true, unmounted = false;
  const catalogChanged = async () => true;
  async function render(next = issuer, capability = enabled) {
    issuer = next; enabled = capability;
    const content = exportOnly ? React.createElement(ReportExport, exportOnly) : React.createElement(Freshness, { key: issuer.cik, ticker: issuer.ticker, catalogChanged },
      React.createElement(FilingResearch, { company: issuer, configured: false, filingResearchEnabled: enabled }));
    await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, content) : content));
  }
  async function unmount() { if (unmounted) return; unmounted = true; await act(async () => root.unmount()); host.remove(); }
  ctx.after(unmount);
  await render();
  function request(suffix, forIssuer = issuer) {
    const item = requests.find(item => !item.released && !item.init.signal.aborted && item.path === path(forIssuer, suffix));
    assert.ok(item, `Expected pending ${path(forIssuer, suffix)}`); return item;
  }
  async function release(item, value, status = 200, pin = item.init.headers?.['X-FinLens-Data-Version']) {
    assert.equal(item.released, false); item.released = true;
    await act(async () => item.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json',
      ...(pin !== undefined ? { 'X-FinLens-Data-Version': String(pin) } : {}), ...(status === 409 ? { 'X-FinLens-Error-Code': 'DATA_VERSION_CHANGED' } : {}) } })));
  }
  async function ready(version = 0) { await release(request('freshness'), fresh(issuer, version)); await release(request('sources'), [filing(issuer), filing(issuer, '000002')]); }
  async function change(element, value) {
    assert.ok(element);
    await act(async () => {
      const prototype = element.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLSelectElement.prototype;
      Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
      element.dispatchEvent(new dom.window.Event(element.tagName === 'TEXTAREA' ? 'input' : 'change', { bubbles: true }));
    });
  }
  async function click(label) {
    const button = [...host.querySelectorAll('button')].find(button => button.textContent === label);
    assert.ok(button, label); assert.equal(button.disabled, false);
    await act(async () => button.click());
  }
  const select = label => [...host.querySelectorAll('label')].find(item => item.firstChild?.textContent?.trim() === label)?.querySelector('select');
  async function search(query = 'supply chain', { settleDirect = true, scope = 'filing', suffix = '000001' } = {}) {
    await change(host.querySelector('#research-query'), query); await click('Research question');
    const direct = request('research-answer');
    if (settleDirect) await release(direct, { ticker: issuer.ticker, question: query, matched: false, status: 'not_matched' });
    return { direct, context: request(scope === 'company' ? 'context' : `filings/${accession(issuer, suffix)}/context`) };
  }
  const report = () => host.querySelector('.evidence-report');
  const preview = () => report()?.querySelector('textarea')?.value;
  async function json() { await click('Download evidence data (.json)'); return JSON.parse(await urls.at(-1).blob.text()); }
  return { host, requests, urls, revoked, downloads, render, unmount, request, release, ready, change, click, select, search, report, preview, json,
    failCreate: value => { failCreate = value; }, failClick: value => { failClick = value; } };
}

test('report serializers retain all exact passages, source lineage, version zero and explicit absent selected metadata', () => {
  const result = evidence(); result.ignored_private_object = 'MUST NOT EXPORT'; result.citations[0].ignored_token = 'MUST NOT EXPORT';
  const report = createEvidenceReport(company, result, 0, false), text = evidenceReportText(report);
  assert.equal(report.search.data_version, 0); assert.equal(report.search.evidence_version, null);
  assert.equal(report.search.data_version_basis, 'request_pin_only');
  assert.equal(report.search.searched_accessions, null); assert.equal(report.search.excluded_publication_count, null);
  assert.equal(report.search.accession_number, accession()); assert.equal(report.passages[0].source.company_cik, null);
  assert.deepEqual(report.passages.map(item => item.text), originals);
  assert.doesNotMatch(JSON.stringify(report), /ignored|MUST NOT EXPORT/);
  assert.equal(report.passages[0].source.filename, 'synthetic+legacy.htm');
  for (const { source, text: passage } of report.passages) {
    assert.ok(text.includes(passage)); assert.ok(text.includes(source.sec_url)); assert.ok(text.includes(source.chunk_id));
    assert.ok(text.includes(`${source.start_char}-${source.end_char}`));
  }
  assert.match(text, /not complete original filings/); assert.match(text, /not a durable source pin or a replay guarantee/);
  assert.equal(evidenceReportText(JSON.parse(JSON.stringify(report))), text);
});
test('company report preserves returned searched inventory and evidence version zero without inferring completeness', () => {
  const report = createEvidenceReport(company, evidence({ scope: 'company', version: 7 }), 7, true, true);
  assert.equal(report.search.evidence_version, 0); assert.equal(report.search.data_version, 7);
  assert.equal(report.search.data_version_basis, 'response_matches_request_pin');
  assert.deepEqual(report.search.searched_accessions, [accession(), accession(company, '000002')]);
  assert.equal(report.search.excluded_publication_count, 1); assert.equal(report.search.accession_number, null);
  assert.equal(report.search.reference_only, true); assert.equal(report.search.purpose, 'risk_topic');
  assert.equal(report.passages[0].source.company_cik, company.cik);
  assert.match(report.limitations.join(' '), /does not support a different/); assert.match(report.limitations.join(' '), /No result does not mean no risk/);
});
for (const scope of ['filing', 'company']) test(`insufficient ${scope} report records empty retrieval honestly`, () => {
  const report = createEvidenceReport(company, evidence({ scope, count: 0 }), 0, false);
  assert.deepEqual(report.passages, []); assert.equal(report.search.evidence_status, 'insufficient');
  assert.match(evidenceReportText(report), /No qualifying passages returned/);
});
const malformed = {
  'wrong issuer': result => { result.ticker = 'BBB'; },
  'wrong source company': result => { result.citations[0].company_cik = other.cik; },
  'wrong accession': result => { result.citations[0].accession_number = accession(other); },
  'unsafe URL': result => { result.citations[0].sec_url = 'https://www.sec.gov.evil.test/'; },
  'SEC URL query substitution': result => { result.citations[0].sec_url += '?next=evil'; },
  'path filename': result => { result.citations[0].filename = '../secret.htm'; },
  'control filename': result => { result.citations[0].filename = 'bad\u0085file.htm'; },
  'missing text': result => { result.context = ''; },
  'unframed extra text': result => { result.context += '\nExtra unframed content'; },
  'mismatched block': result => { result.context = result.context.replace('chunk_0000', 'chunk_9999'); },
  'duplicate chunk': result => { result.citations[1].chunk_id = result.citations[0].chunk_id; },
  'incorrect rank': result => { result.citations[0].citation_id = 'source_5'; },
  'invalid offsets': result => { result.citations[0].end_char = 1; },
  'nonfinite score': result => { result.citations[0].hybrid_score = NaN; },
  'false sufficient state': result => { result.evidence_status = 'insufficient'; },
};
for (const [name, mutate] of Object.entries(malformed)) test(`source-backed report rejects ${name} without silently dropping data`, () => {
  const result = evidence(); mutate(result); assert.throws(() => createEvidenceReport(company, result, 0, false));
});
test('company report rejects version, inventory, metadata and count inconsistencies', () => {
  for (const mutate of [r => { r.data_version = 9; }, r => { r.evidence_version = 8; }, r => { r.searched_accessions = []; },
    r => { r.searched_accessions.push(r.searched_accessions[0]); }, r => { r.excluded_publication_count = 21; },
    r => { r.context = r.context.replace('"filename":"synthetic.htm"', '"filename":"wrong.htm"'); }]) {
    const result = evidence({ scope: 'company', version: 7 }); mutate(result);
    assert.throws(() => createEvidenceReport(company, result, 7, false));
  }
});
for (const strict of [false, true]) {
  for (const scope of ['filing', 'company']) test(`mounted ${scope} search exports exact full text/JSON with no added requests strict ${strict}`, async ctx => {
    const app = await mount(ctx, { strict }); assert.equal(app.report(), null); await app.ready(scope === 'filing' ? 0 : 7);
    if (scope === 'company') await app.change(app.select('Evidence search scope'), 'company');
    const query = 'supply chain\n<script>draft literal</script>';
    const pending = await app.search(query, { scope }); assert.equal(app.report(), null);
    const value = evidence({ scope, query, version: scope === 'filing' ? 0 : 7 }); await app.release(pending.context, value);
    const before = app.requests.length;
    assert.equal(app.host.querySelectorAll('.evidence-card').length, 2);
    const summary = app.report().querySelector('summary'); summary.focus(); await act(async () => summary.click());
    assert.equal(summary.parentElement.open, true); assert.equal(document.activeElement, summary);
    assert.equal(app.report().querySelector('textarea').readOnly, true);
    await app.click('Download evidence report (.txt)'); const plain = await app.urls.at(-1).blob.text();
    const data = await app.json(); assert.equal(plain, evidenceReportText(data)); assert.equal(plain, app.preview());
    assert.equal(data.search.query, query); assert.deepEqual(data.passages.map(p => p.text), originals);
    assert.equal(data.search.reference_only, false); assert.equal(data.search.data_version, scope === 'filing' ? 0 : 7);
    assert.equal(data.search.evidence_version, scope === 'filing' ? null : 0);
    assert.ok(app.revoked.includes(app.urls[0].url)); assert.equal(app.urls[0].blob.type, 'text/plain;charset=utf-8');
    assert.equal(app.urls[1].blob.type, 'application/json;charset=utf-8');
    assert.match(app.downloads[0].filename, /^finlens-AAA-evidence-v[07]\.txt$/);
    assert.equal(app.host.querySelectorAll('a[download]').length, 0); assert.equal(app.host.querySelector('script'), null);
    assert.match(app.report().textContent, /cannot confirm a saved file/);
    await app.click('Show more evidence (3)'); assert.equal(app.host.querySelectorAll('.evidence-card').length, 5);
    assert.deepEqual(await app.json(), data); assert.equal(app.requests.length, before);
    await app.unmount(); assert.deepEqual([...new Set(app.revoked)].sort(), app.urls.map(u => u.url).sort());
    assert.equal(app.revoked.length, app.urls.length, 'Each URL is released once');
  });
  test(`mounted original-query report survives draft pending failed and ignored-abort flows strict ${strict}`, async ctx => {
    const app = await mount(ctx, { strict }); await app.ready();
    const first = await app.search(); await app.release(first.context, evidence());
    await app.change(app.host.querySelector('#research-query'), 'competition');
    let data = await app.json(); assert.equal(data.search.query, 'supply chain'); assert.equal(data.search.reference_only, true);
    const abandoned = await app.search('competition');
    data = await app.json(); assert.equal(data.search.reference_only, true); assert.equal(data.search.query, 'supply chain');
    const current = await app.search('regulatory'); assert.equal(abandoned.context.init.signal.aborted, true);
    await app.release(abandoned.context, evidence({ query: 'competition' }));
    assert.equal((await app.json()).search.query, 'supply chain');
    await app.release(current.context, { detail: 'Synthetic retrieval failure' }, 503);
    data = await app.json(); assert.equal(data.search.query, 'supply chain'); assert.equal(data.search.reference_only, true);
    assert.match(app.report().textContent, /not a different draft or pending question/);
    const retry = await app.search('regulatory'); await app.release(retry.context, evidence({ query: 'regulatory' }));
    data = await app.json(); assert.equal(data.search.query, 'regulatory'); assert.equal(data.search.reference_only, false);
    assert.doesNotMatch(app.preview(), /Completed query \(quoted\): "supply chain"/);
  });
  for (const boundary of ['company', 'filing', 'scope', 'publication', 'restriction', 'unmount'])
    test(`mounted ${boundary} change revokes report and late source delivery strict ${strict}`, async ctx => {
      const app = await mount(ctx, { strict }); await app.ready();
      const first = await app.search(); await app.release(first.context, evidence()); await app.json();
      const delayed = await app.search('competition');
      if (boundary === 'company') await app.render(other);
      if (boundary === 'filing') await app.change(app.select('Indexed SEC filing'), accession(company, '000002'));
      if (boundary === 'scope') await app.change(app.select('Evidence search scope'), 'company');
      if (boundary === 'publication') {
        await act(async () => window.dispatchEvent(new dom.window.Event('focus')));
        await app.release(app.request('freshness'), fresh(company, 7));
      }
      if (boundary === 'restriction') await app.render(company, false);
      if (boundary === 'unmount') await app.unmount();
      assert.equal(app.report(), null); assert.ok(app.revoked.includes(app.urls[0].url));
      assert.equal(delayed.context.init.signal.aborted, true);
      await app.release(delayed.context, evidence({ query: 'competition' })); assert.equal(app.report(), null);
    });
}
for (const failure of ['allocation', 'click']) test(`mounted ${failure} download failure retains evidence and allows explicit retry with cleanup`, async ctx => {
  const app = await mount(ctx); await app.ready(); const pending = await app.search(); await app.release(pending.context, evidence());
  const before = app.requests.length, preview = app.preview();
  if (failure === 'allocation') app.failCreate(true); else app.failClick(true);
  await app.click('Download evidence report (.txt)');
  assert.match(app.report().querySelector('[role="alert"]').textContent, /evidence is unchanged/);
  assert.equal(app.preview(), preview); assert.equal(app.host.querySelectorAll('a[download]').length, 0);
  if (failure === 'click') assert.deepEqual(app.revoked, [app.urls[0].url]);
  app.failCreate(false); app.failClick(false); await app.click('Download evidence report (.txt)');
  assert.equal(await app.urls.at(-1).blob.text(), preview); assert.equal(app.requests.length, before);
  assert.equal(app.report().querySelector('[role="alert"]'), null);
  await app.unmount(); assert.equal(app.revoked.length, app.urls.length);
});
test('mounted URL expiry releases an idle report URL once without a state change', async ctx => {
  const app = await mount(ctx); await app.ready(); const pending = await app.search(); await app.release(pending.context, evidence());
  const native = globalThis.setTimeout, timers = [];
  ctx.mock.method(globalThis, 'setTimeout', (callback, delay, ...args) => {
    if (delay === 1000) { timers.push(callback); return native(() => {}, 10000); }
    return native(callback, delay, ...args);
  });
  await app.json(); assert.equal(timers.length, 1); timers[0](); assert.deepEqual(app.revoked, [app.urls[0].url]);
  await app.unmount(); assert.equal(app.revoked.length, 1);
});
test('mounted malformed completed data disables only export and does not create a partial report', async ctx => {
  const result = evidence(); result.citations[0].sec_url = 'https://evil.test/';
  const app = await mount(ctx, { exportOnly: { company, result, dataVersion: 0, referenceOnly: false } });
  assert.match(app.report().querySelector('[role="alert"]').textContent, /No file was prepared/);
  assert.equal(app.report().querySelector('button'), null); assert.equal(app.report().querySelector('textarea'), null);
  assert.deepEqual(app.urls, []); assert.deepEqual(app.requests, []);
});
for (const scope of ['filing', 'company']) test(`mounted ${scope} insufficient search exports no invented passages or conclusion`, async ctx => {
  const app = await mount(ctx); await app.ready();
  if (scope === 'company') await app.change(app.select('Evidence search scope'), 'company');
  const pending = await app.search('supply chain', { scope }); await app.release(pending.context, evidence({ scope, count: 0 }));
  const data = await app.json(); assert.deepEqual(data.passages, []); assert.equal(data.search.evidence_status, 'insufficient');
  assert.match(app.preview(), /does not establish absence/);
});
test('mounted stale publication response blocks exports until new source research succeeds', async ctx => {
  const app = await mount(ctx); await app.ready(); const initial = await app.search(); await app.release(initial.context, evidence());
  await app.json(); const stale = await app.search('competition'); await app.release(stale.context, {}, 409, 7);
  assert.equal(app.report(), null); assert.ok(app.revoked.includes(app.urls[0].url));
  await app.release(app.request('freshness'), fresh(company, 7)); await app.release(app.request('sources'), [filing()]);
  assert.equal(app.report(), null); const renewed = await app.search('competition');
  await app.release(renewed.context, evidence({ query: 'competition', version: 7 }));
  const data = await app.json(); assert.equal(data.search.data_version, 7); assert.equal(data.search.query, 'competition');
});

for (const scope of ['filing', 'company']) test(`mounted ${scope} risk-topic report retains source limitations without financial or AI calls`, async ctx => {
  const app = await mount(ctx); await app.ready();
  await app.change(app.select('Research purpose'), 'risk');
  if (scope === 'company') await app.change(app.select('Evidence search scope'), 'company');
  await app.click('Use risk topic'); await app.click('Search risk topic');
  const pending = app.request(scope === 'company' ? 'context' : `filings/${accession()}/context`);
  const result = evidence({ scope });
  for (const citation of result.citations) citation.filename = 'synthetic.htm';
  if (scope === 'company') result.context = evidence({ scope }).context;
  await app.release(pending, result);
  const data = await app.json(); assert.equal(data.search.purpose, 'risk_topic');
  assert.match(data.limitations.join(' '), /No result does not mean no risk/);
  assert.equal(app.requests.filter(item => item.path.endsWith('/research-answer') || item.path.endsWith('/answer') || item.path.endsWith('/tone')).length, 0);
});
test('mounted repeated same-query submission cannot duplicate work and retained report stays reference-only while pending', async ctx => {
  const app = await mount(ctx); await app.ready(); const first = await app.search(); await app.release(first.context, evidence());
  const before = app.requests.length, button = [...app.host.querySelectorAll('button')].find(item => item.textContent === 'Research question');
  await act(async () => { button.click(); button.click(); });
  assert.equal(app.requests.length, before + 2, 'One direct and one selected-filing request');
  assert.equal((await app.json()).search.reference_only, true);
  await app.release(app.request('research-answer'), { detail: 'Synthetic independent direct failure' }, 503);
  await app.release(app.request(`filings/${accession()}/context`), evidence());
  assert.equal((await app.json()).search.reference_only, false);
  assert.equal(app.host.querySelectorAll('.evidence-card').length, 2);
});

for (const scope of ['filing', 'company']) for (const referenceOnly of [false, true]) for (const count of [0, 5])
test(`printable report preserves exact admitted text ${scope} reference ${referenceOnly} passages ${count}`, () => {
  const report = createEvidenceReport(company, evidence({ scope, count }), 0, referenceOnly, true);
  const html = evidenceReportHtml(report), printed = new JSDOM(html);
  try {
    const doc = printed.window.document;
    assert.equal(doc.querySelector('#report-text').textContent, evidenceReportText(report));
    assert.equal(doc.querySelectorAll('a').length, count);
    assert.deepEqual([...doc.querySelectorAll('a')].map(link => link.getAttribute('href')), report.passages.map(item => item.source.sec_url));
    assert.equal(doc.querySelectorAll('script, iframe, object, embed, img, link, form').length, 0);
    assert.equal(doc.querySelectorAll('[onclick], [onload], [onerror]').length, 0);
    assert.match(doc.querySelector('meta[http-equiv="Content-Security-Policy"]').content, /default-src 'none'/);
    assert.equal(doc.querySelector('meta[name="referrer"]').content, 'no-referrer');
    assert.match(doc.querySelector('style').textContent, /@media print/);
    assert.ok(new TextEncoder().encode(html).byteLength <= 256 * 1024);
  } finally { printed.window.close(); }
});

function reportWithPassageText(text) {
  const result = evidence({ count: 1 }), citation = result.citations[0];
  citation.end_char = citation.start_char + Array.from(text).length;
  result.context = `[SOURCE source_1]\nchunk_id: ${citation.chunk_id}\naccession_number: ${citation.accession_number}\nform: ${citation.form}\nsimilarity: ${citation.similarity.toFixed(6)}\ntext: |-\n${text.split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE source_1]`;
  return { result, report: createEvidenceReport(company, result, 0, false) };
}

test('printable text preserves leading/trailing newlines, CRLF, Unicode and hostile markup as exact quoted data', () => {
  const text = '\n\r\nUnicode 😀 e\u0301\r\n</pre><script>steal()</script><img src="https://evil.invalid" onerror="steal()">\n\n';
  const { report } = reportWithPassageText(text); assert.equal(report.passages[0].text, text);
  report.company.name = '<title>untrusted & company</title>';
  report.search.query = '<iframe src="https://evil.invalid">private</iframe>';
  const printed = new JSDOM(evidenceReportHtml(report));
  try {
    assert.equal(printed.window.document.querySelector('#report-text').textContent, evidenceReportText(report));
    assert.equal(printed.window.document.querySelectorAll('script, img, iframe').length, 0);
    assert.equal(printed.window.document.querySelectorAll('title').length, 1);
    assert.equal(printed.window.document.querySelectorAll('a').length, 1, 'Quoted URLs never become links');
  } finally { printed.window.close(); }
});

for (const text of ['Source with NUL \u0000 inside.', 'Source with unpaired surrogate \ud800 inside.'])
test(`printable HTML refuses unrepresentable text ${text.includes('\u0000') ? 'NUL' : 'surrogate'} while preserving text/JSON`, () => {
  const { report } = reportWithPassageText(text);
  assert.throws(() => evidenceReportHtml(report));
  assert.ok(evidenceReportText(report).includes(text));
  assert.equal(JSON.parse(JSON.stringify(report)).passages[0].text, text);
});

for (const url of ['javascript:alert(1)', 'https://evil.invalid/filing', 'https:sec.gov/Archives/filing', 'https://www.sec.gov/Archives/other', 'https://www.sec.gov/?query=1'])
test(`printable HTML refuses changed source metadata ${url}`, () => {
  const report = createEvidenceReport(company, evidence({ count: 1 }), 0, false);
  report.passages[0].source.sec_url = url;
  assert.throws(() => evidenceReportHtml(report), 'Withhold the entire document instead of repairing a link');
});

test('printable document output is bounded before browser handoff', () => {
  const report = createEvidenceReport(company, evidence({ count: 1 }), 0, false);
  report.passages[0].text = '&'.repeat(300000);
  assert.throws(() => evidenceReportHtml(report));
});

for (const strict of [false, true]) for (const scope of ['filing', 'company'])
test(`mounted printable ${scope} report includes collapsed evidence and makes no request strict ${strict}`, async ctx => {
  const app = await mount(ctx, { strict }); await app.ready();
  if (scope === 'company') await app.change(app.select('Evidence search scope'), 'company');
  const pending = await app.search('supply chain', { scope }); await app.release(pending.context, evidence({ scope }));
  assert.equal(app.host.querySelectorAll('.evidence-card').length, 2);
  const before = app.requests.length, preview = app.preview();
  await app.click('Download printable report (.html)');
  assert.equal(app.urls[0].blob.type, 'text/html;charset=utf-8');
  assert.equal(app.downloads[0].filename, 'finlens-AAA-evidence-v0.html');
  const printed = new JSDOM(await app.urls[0].blob.text());
  try {
    assert.equal(printed.window.document.querySelector('#report-text').textContent, preview);
    for (const text of originals) assert.ok(preview.includes(text));
    assert.equal(printed.window.document.querySelectorAll('a').length, 5);
  } finally { printed.window.close(); }
  assert.match(app.report().querySelector('[role="status"]').textContent, /Open the saved file in a browser and choose Print/);
  assert.match(app.report().textContent, /cannot confirm a saved file/);
  assert.equal(app.requests.length, before); assert.equal(app.host.querySelectorAll('a[download]').length, 0);
  await app.unmount(); assert.deepEqual(app.revoked, [app.urls[0].url]);
});

for (const boundary of ['company', 'unmount'])
test(`printable original-query report remains reference-only during interruption and releases on ${boundary}`, async ctx => {
  const app = await mount(ctx); await app.ready(); const first = await app.search(); await app.release(first.context, evidence());
  const delayed = await app.search('competition');
  const before = app.requests.length, preview = app.preview();
  await app.click('Download printable report (.html)');
  const printed = new JSDOM(await app.urls[0].blob.text());
  try {
    assert.equal(printed.window.document.querySelector('#report-text').textContent, preview);
    assert.match(preview, /Completed query \(quoted\): "supply chain"/);
    assert.match(preview, /Reference only: true/); assert.doesNotMatch(preview, /"competition"/);
  } finally { printed.window.close(); }
  assert.equal(app.requests.length, before);
  if (boundary === 'company') await app.render(other); else await app.unmount();
  assert.equal(app.report(), null); assert.equal(delayed.context.init.signal.aborted, true);
  await app.release(delayed.context, evidence({ query: 'competition' })); assert.equal(app.report(), null);
  assert.deepEqual(app.revoked, [app.urls[0].url]);
});

for (const failure of ['allocation', 'click'])
test(`printable ${failure} failure retains evidence and retries without another request`, async ctx => {
  const app = await mount(ctx); await app.ready(); const pending = await app.search(); await app.release(pending.context, evidence());
  const before = app.requests.length, preview = app.preview();
  if (failure === 'allocation') app.failCreate(true); else app.failClick(true);
  await app.click('Download printable report (.html)');
  assert.match(app.report().querySelector('[role="alert"]').textContent, /evidence is unchanged/);
  assert.equal(app.preview(), preview); assert.equal(app.host.querySelectorAll('a[download]').length, 0);
  assert.deepEqual(app.revoked, app.urls.map(item => item.url));
  app.failCreate(false); app.failClick(false); await app.click('Download printable report (.html)');
  assert.equal(app.report().querySelector('[role="alert"]'), null);
  const printed = new JSDOM(await app.urls.at(-1).blob.text());
  try { assert.equal(printed.window.document.querySelector('#report-text').textContent, preview); }
  finally { printed.window.close(); }
  assert.equal(app.requests.length, before);
  await app.unmount(); assert.deepEqual(app.revoked, app.urls.map(item => item.url));
});

test('unrepresentable printable text refuses only HTML and keeps text and JSON usable', async ctx => {
  const text = 'Quoted NUL \u0000 remains data.', { result } = reportWithPassageText(text);
  const app = await mount(ctx, { exportOnly: { company, result, dataVersion: 0, referenceOnly: false } });
  const preview = app.preview(); assert.ok(preview.includes('\u0000'));
  await app.click('Download printable report (.html)');
  assert.equal(app.downloads.length, 0); assert.equal(app.urls.length, 0);
  assert.match(app.report().querySelector('[role="alert"]').textContent, /evidence is unchanged/);
  assert.match(app.report().querySelector('[role="alert"]').textContent, /Download evidence data \(\.json\)/);
  await app.click('Download evidence report (.txt)'); assert.equal(await app.urls[0].blob.text(), preview);
  assert.equal((await app.json()).passages[0].text, text);
  assert.equal(app.requests.length, 0); assert.equal(app.preview(), preview);
});

for (const text of ['High surrogate \ud800 is source data.', 'Low surrogate \udfff is source data.'])
test(`lossy UTF-8 text download is refused with JSON recovery ${text.startsWith('High') ? 'high' : 'low'}`, async ctx => {
  const { result } = reportWithPassageText(text);
  const app = await mount(ctx, { exportOnly: { company, result, dataVersion: 0, referenceOnly: false } });
  const preview = app.preview(); assert.ok(preview.includes(text));
  const lossy = await new Blob([preview]).text();
  assert.notEqual(lossy, preview, 'The real Blob encoder would change the admitted evidence');
  assert.ok(lossy.includes('\ufffd'));
  await app.click('Download evidence report (.txt)');
  assert.equal(app.downloads.length, 0, 'Do not hand off altered source text');
  assert.equal(app.urls.length, 0, 'Refuse before allocating an object URL');
  assert.match(app.report().querySelector('[role="alert"]').textContent, /Download evidence data \(\.json\)/);
  assert.equal(app.preview(), preview);
  const data = await app.json(); assert.equal(data.passages[0].text, text);
  assert.equal(app.report().querySelector('[role="alert"]'), null);
  assert.equal(app.downloads[0].filename, 'finlens-AAA-evidence-v0.json');
  await app.click('Download evidence report (.txt)');
  assert.equal(app.downloads.length, 1); assert.equal(app.urls.length, 1);
  assert.deepEqual(app.revoked, [app.urls[0].url]);
  assert.equal(app.requests.length, 0); assert.equal(app.preview(), preview);
});

for (const text of ['Unicode 😀 e\u0301 \ufeff text.', 'Literal replacement \ufffd is original evidence.', 'NUL \u0000 and CRLF\r\nremain exact.'])
test(`well-formed source text retains exact UTF-8 bytes ${JSON.stringify(text)}`, async ctx => {
  const { result, report } = reportWithPassageText(text);
  const app = await mount(ctx, { exportOnly: { company, result, dataVersion: 0, referenceOnly: false } });
  const expected = evidenceReportText(report);
  // The textarea DOM normalizes line endings; the file must keep source CRLF.
  assert.equal(app.preview(), expected.replace(/\r\n?/g, '\n'));
  await app.click('Download evidence report (.txt)');
  assert.equal(app.downloads.length, 1); assert.equal(app.urls[0].blob.type, 'text/plain;charset=utf-8');
  assert.equal(await app.urls[0].blob.text(), expected);
  assert.deepEqual(new Uint8Array(await app.urls[0].blob.arrayBuffer()), new TextEncoder().encode(expected));
  assert.equal(app.report().querySelector('[role="alert"]'), null); assert.equal(app.requests.length, 0);
});

for (const scope of ['filing', 'company']) for (const count of [0, 5]) for (const referenceOnly of [false, true])
test(`CSV reconstructs every admitted field ${scope} passages ${count} reference ${referenceOnly}`, () => {
  const report = createEvidenceReport(company, evidence({ scope, count }), 0, referenceOnly, true);
  const original = structuredClone(report);
  report.ignored_private = 'MUST NOT EXPORT'; report.company.ignored_secret = 'MUST NOT EXPORT';
  report.search.ignored_draft = 'MUST NOT EXPORT';
  report.passages.forEach(item => { item.ignored = 'MUST NOT EXPORT'; item.source.ignored = 'MUST NOT EXPORT'; });
  const csv = evidenceReportCsv(report);
  assert.deepEqual(readEvidenceCsv(csv), original);
  assert.equal(evidenceReportCsv(report), csv); assert.doesNotMatch(csv, /MUST NOT EXPORT|ignored/);
  assert.ok(Buffer.byteLength(csv) < 256 * 1024);
});

test('CSV retains exact comma quote CRLF Unicode, empty arrays and signed numeric scores', () => {
  const { report } = reportWithPassageText('\nOriginal, "quoted" 😀 e\u0301\r\nsecond line\n');
  report.passages[0].source.similarity = -.125; report.passages[0].source.semantic_similarity = -.125;
  report.passages[0].source.lexical_score = -0;
  assert.deepEqual(readEvidenceCsv(evidenceReportCsv(report)), report);
  const empty = createEvidenceReport(company, evidence({ scope: 'company', count: 0 }), 0, false);
  empty.search.searched_accessions = [];
  assert.deepEqual(readEvidenceCsv(evidenceReportCsv(empty)), empty);
});

for (const text of ['=1+1', '+cmd', '-bullet source', '@SUM(1)', '\t\r\n =1', '\u200b\ufeff@SUM(1)',
  '\uff1d1+1', '\uff0b1', '\uff0d1', '\uff20SUM(1)', 'NUL\u0000 text', 'Escape\u001b text', 'High\ud800', 'Low\udfff'])
test(`CSV refuses unsafe literal source without rewriting ${JSON.stringify(text)}`, () => {
  const { report } = reportWithPassageText(text);
  const original = structuredClone(report);
  assert.throws(() => evidenceReportCsv(report), error => error.name === 'EvidenceReportFormatError' && /CSV.*Download evidence data/.test(error.message));
  assert.deepEqual(report, original);
  assert.deepEqual(JSON.parse(JSON.stringify(report)), original);
});

test('CSV refusal covers query company and source metadata, and refuses unsafe links', () => {
  for (const mutate of [r => { r.search.query = ' =1'; }, r => { r.company.name = '+name'; },
    r => { r.passages[0].source.evidence_reason = '\ufeff@SUM(1)'; }, r => { r.passages[0].source.sec_url += '?substitute'; }]) {
    const report = createEvidenceReport(company, evidence(), 0, false); mutate(report);
    assert.throws(() => evidenceReportCsv(report), { name: 'EvidenceReportFormatError' });
  }
});

test('mounted CSV downloads exact typed bytes, reuses owner disposal and makes no request', async ctx => {
  const { result, report } = reportWithPassageText('Original, "quoted" 😀\r\nsource.');
  const app = await mount(ctx, { exportOnly: { company, result, dataVersion: 0, referenceOnly: false } });
  await app.click('Download typed evidence (.csv)');
  assert.equal(app.downloads[0].filename, 'finlens-AAA-evidence-v0.csv');
  assert.equal(app.urls[0].blob.type, 'text/csv;charset=utf-8');
  const bytes = new Uint8Array(await app.urls[0].blob.arrayBuffer());
  assert.deepEqual(bytes, new TextEncoder().encode(evidenceReportCsv(report)));
  assert.deepEqual(readEvidenceCsv(await app.urls[0].blob.text()), report);
  assert.match(app.report().querySelector('[role="status"]').textContent, /CSV download requested/);
  await app.json(); assert.deepEqual(app.revoked, [app.urls[0].url]);
  assert.equal(app.requests.length, 0);
});

for (const text of ['=HYPERLINK("https://evil.invalid")', 'Original\ud800', 'Original\u0000'])
test(`mounted CSV refusal allocates no URL and preserves JSON recovery ${JSON.stringify(text)}`, async ctx => {
  const { result } = reportWithPassageText(text);
  const app = await mount(ctx, { exportOnly: { company, result, dataVersion: 0, referenceOnly: false } });
  const preview = app.preview(); await app.click('Download typed evidence (.csv)');
  assert.equal(app.urls.length, 0); assert.equal(app.downloads.length, 0);
  assert.match(app.report().querySelector('[role="alert"]').textContent, /CSV.*Download evidence data/);
  assert.equal((await app.json()).passages[0].text, text);
  assert.equal(app.report().querySelector('[role="alert"]'), null);
  assert.equal(app.requests.length, 0); assert.equal(app.preview(), preview);
});
});
