import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';
import { componentLoader } from './component-loader.mjs';

let dom, createRoot, Workspace, client;
const previous = new Map();
const company = { id: 1, ticker: 'AAA', name: 'Synthetic issuer', cik: '0000000001', exchange: 'TEST', has_indexed_filing: true, indexed_filing_count: 1 };
const identity = { status: 'authenticated', owner_key: 'alice', csrf: 'a'.repeat(43), expires_in: 300 };
const source = { schema_version: 1, record: { kind: 'database_publication', entity_key: { namespace: 'sec_cik', id: company.cik },
  origin: 'sec', owner_key: null, session_key: null, source_descriptor_key: null, source_revision_key: null, rights_policy_key: null,
  admission_record_key: null, public_available_at: { kind: 'unknown' }, retrieved_at: { kind: 'unknown' },
  accession: '0000000001-25-000001', data_version: 0, evidence_version: 0, publication_data_version: 0, manifest_sha256: 'a'.repeat(64), chunk_id: null } };
const note = { schema_version: 1, owner_key: { namespace: 'principal', id: 'alice' }, session_key: { namespace: 'session', id: 's1' },
  artifact_key: { namespace: 'artifact', id: 'a1' }, session_revision: 1, artifact_revision: 1,
  body: 'Private synthetic note <script>do not execute</script>', source, source_verification: 'unverified_reference', original_availability: 'not_checked' };
const item = { session_key: 's1', session_revision: 1, artifact_key: 'a1', artifact_revision: 1,
  preview: note.body, source_cik: company.cik, source_accession: source.record.accession };
const listing = items => ({ schema_version: 1, owner_key: 'alice', items, next_cursor: null });
const response = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'https://finlens.test' });
  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT', 'fetch']) {
    previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    if (key !== 'fetch') Object.defineProperty(globalThis, key, { configurable: true, value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[key] });
  }
  ({ createRoot } = await import('react-dom/client'));
  const load = componentLoader(fileURLToPath(new URL('../', import.meta.url)));
  Workspace = load(fileURLToPath(new URL('../components/private-workspace.tsx', import.meta.url))).default;
  client = load(fileURLToPath(new URL('../lib/private-workspace.ts', import.meta.url)));
});
after(() => { dom.window.close(); for (const [key, descriptor] of previous) {
  if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key];
} });
async function mount(ctx, handler = () => undefined) {
  const calls = [], host = document.createElement('div'); document.body.append(host);
  globalThis.fetch = async (url, init = {}) => {
    const path = String(url).replace('/api/finlens', ''), call = { path, init, body: init.body ? JSON.parse(init.body) : null }; calls.push(call);
    const custom = handler(call); if (custom !== undefined) return await custom;
    if (path === '/private-research/state') return response(identity);
    if (path === '/private-research/notes') return response(listing([]));
    if (path === '/companies') return response([company]);
    if (path.startsWith('/private-research/sources?')) return response({ schema_version: 1, owner_key: 'alice', sources: [source],
      source_verification: 'unverified_reference', original_availability: 'not_checked' });
    if (path.startsWith('/private-research/note?') || path.startsWith('/private-research/export?')) return response(note);
    throw new Error('Unexpected request: ' + path);
  };
  const root = createRoot(host); let mounted = true;
  async function unmount() { if (mounted) { await act(async () => root.unmount()); host.remove(); mounted = false; } }
  ctx.after(unmount);
  await act(async () => { root.render(React.createElement(Workspace)); });
  async function settle() { await act(async () => { await new Promise(resolve => setImmediate(resolve)); }); }
  await settle();
  const button = text => [...host.querySelectorAll('button')].find(node => node.textContent === text);
  async function click(text) { const target = button(text); assert.ok(target, text); assert.equal(target.disabled, false);
    await act(async () => target.click()); await settle(); }
  async function edit(selector, value) { const target = host.querySelector(selector); assert.ok(target, selector);
    await act(async () => { const prototype = target.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLSelectElement.prototype;
      Object.getOwnPropertyDescriptor(prototype, 'value').set.call(target, value);
      target.dispatchEvent(new dom.window.Event(target.tagName === 'TEXTAREA' ? 'input' : 'change', { bubbles: true })); }); await settle(); }
  async function draft() { await edit('select', company.cik);
    const selects = host.querySelectorAll('select'); await act(async () => { selects[1].value = source.record.accession; selects[1].dispatchEvent(new dom.window.Event('change', { bubbles: true })); });
    await edit('textarea', note.body); }
  return { host, calls, click, edit, draft, settle, unmount, button };
}

test('default-off UI sends only the availability request and offers no token entry', async ctx => {
  const app = await mount(ctx, call => call.path === '/private-research/state' ? response({ code: 'PRIVATE_WORKSPACE_UNAVAILABLE' }, 503) : undefined);
  assert.match(app.host.textContent, /not enabled on this server/);
  assert.deepEqual(app.calls.map(call => call.path), ['/private-research/state']);
  assert.equal(app.host.querySelectorAll('input,textarea,select').length, 0);
});
test('read-only admission is shown as unavailable rather than a working login', async ctx => {
  const app = await mount(ctx, call => call.path === '/private-research/state'
    ? new Response(JSON.stringify({ detail: 'Blocked' }), { status: 403,
      headers: { 'Content-Type': 'application/json', 'X-FinLens-Error-Code': 'RELEASE_MODE_BLOCKED' } }) : undefined);
  assert.match(app.host.textContent, /not enabled on this server/);
  assert.equal(app.calls.length, 1);
});
test('a failed source inventory is not presented as a verified empty inventory', async ctx => {
  const app = await mount(ctx, call => call.path.startsWith('/private-research/sources?')
    ? response({ code: 'PRIVATE_WORKSPACE_UNAVAILABLE' }, 503) : undefined);
  await app.edit('select', company.cik);
  assert.match(app.host.textContent, /could not be loaded/);
  assert.doesNotMatch(app.host.textContent, /No stored filing references are available/);
});
test('connected save keeps source pin, CSRF and request identity; explicit retry never autosaves', async ctx => {
  let saves = 0, saved = false;
  const app = await mount(ctx, call => {
    if (call.path === '/private-research/notes' && call.init.method === 'POST') {
      saves++; if (saves === 1) return response({ code: 'PRIVATE_WORKSPACE_UNAVAILABLE', commit_state: 'indeterminate' }, 503);
      saved = true; return response(note);
    }
    if (call.path === '/private-research/notes') return response(listing(saved ? [item] : []));
  });
  await app.draft(); await app.click('Save note'); assert.equal(saves, 1);
  assert.match(app.host.textContent, /may have completed/);
  await app.settle(); assert.equal(saves, 1);
  await app.click('Save note'); assert.equal(saves, 2);
  const writes = app.calls.filter(call => call.init.method === 'POST');
  assert.deepEqual(writes[0].body, writes[1].body);
  assert.deepEqual(writes[1].body.source, source);
  assert.equal(writes[1].init.headers['X-FinLens-CSRF'], identity.csrf);
  assert.equal(writes[1].init.credentials, 'same-origin'); assert.equal(writes[1].init.cache, 'no-store');
  assert.match(app.host.textContent, /Unverified source reference/);
  assert.equal(app.host.querySelectorAll('script').length, 0);
  assert.ok(app.host.querySelector('[aria-label="Opened research note"]'));
});
test('reload and a fresh mounted page discover and reopen persisted note; export reauthorizes', async ctx => {
  const handler = call => call.path === '/private-research/notes' ? response(listing([item])) : undefined;
  const app = await mount(ctx, handler); await app.click('Reload saved notes'); await app.click('Reopen note');
  assert.equal(app.host.querySelector('[aria-label="Opened research note"]').textContent.includes(note.body), true);
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL, originalClick = dom.window.HTMLAnchorElement.prototype.click;
  let blob, revoked;
  URL.createObjectURL = value => { blob = value; return 'blob:synthetic-note'; }; URL.revokeObjectURL = value => { revoked = value; };
  dom.window.HTMLAnchorElement.prototype.click = () => {};
  try { await app.click('Export note as JSON'); assert.deepEqual(JSON.parse(await blob.text()), note);
    await app.unmount(); assert.equal(revoked, 'blob:synthetic-note'); }
  finally { URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; dom.window.HTMLAnchorElement.prototype.click = originalClick; }
  assert.ok(app.calls.some(call => call.path.startsWith('/private-research/export?')));
  await app.unmount(); const reloaded = await mount(ctx, handler); await reloaded.click('Reopen note');
  assert.match(reloaded.host.textContent, /Original availability not checked/);
});
test('authorization denial removes note index, draft and opened content', async ctx => {
  const app = await mount(ctx, call => call.path === '/private-research/notes' ? response(listing([item]))
    : call.path.startsWith('/private-research/note?') ? response({ code: 'AUTH_REQUIRED' }, 401) : undefined);
  await app.draft(); await app.click('Reopen note');
  assert.match(app.host.textContent, /Sign-in expired or access changed/);
  assert.doesNotMatch(app.host.textContent, /Private synthetic note/); assert.equal(app.host.querySelectorAll('textarea,select').length, 0);
});
for (const status of [401, 403]) test(`malformed JSON ${status} still clears all private state`, async ctx => {
  let reads = 0;
  const app = await mount(ctx, call => call.path === '/private-research/notes' ? response(listing([item]))
    : call.path.startsWith('/private-research/note?') && ++reads > 1
      ? new Response('{', { status, headers: { 'Content-Type': 'application/json' } }) : undefined);
  await app.click('Reopen note'); await app.draft();
  assert.match(app.host.textContent, /Private synthetic note/);
  await app.click('Reopen note');
  assert.doesNotMatch(app.host.textContent, /Private synthetic note/);
  assert.equal(app.host.querySelectorAll('textarea,select').length, 0);
  assert.match(app.host.textContent, /Sign-in expired or access changed/);
});
for (const [name, altered] of [
  ['body', { ...note, body: 'A different same-owner note' }],
  ['source pin', { ...note, source: { ...source, record: { ...source.record, manifest_sha256: 'b'.repeat(64) } } }],
]) test(`a same-owner save response with a different ${name} retains the exact draft and retry identity`, async ctx => {
  let submissions = 0;
  const app = await mount(ctx, call => call.path === '/private-research/notes' && call.init.method === 'POST'
    ? response(++submissions === 1 ? altered : note) : undefined);
  await app.draft(); await app.click('Save note');
  assert.equal(app.host.querySelector('textarea')?.value, note.body);
  assert.doesNotMatch(app.host.textContent, /Note saved with its original source pin/);
  assert.equal(app.host.querySelector('[aria-label="Opened research note"]'), null);
  assert.match(app.host.textContent, /draft.*retained/i);
  await app.click('Save note');
  const writes = app.calls.filter(call => call.init.method === 'POST');
  assert.equal(writes.length, 2); assert.deepEqual(writes[0].body, writes[1].body);
  assert.match(app.host.textContent, /Note saved with its original source pin/);
});
test('wrong-owner responses are rejected and clear previously visible private content', async ctx => {
  let indexes = 0;
  const app = await mount(ctx, call => call.path === '/private-research/notes' ? response({ ...listing([item]), owner_key: ++indexes === 1 ? 'alice' : 'bob' }) : undefined);
  await app.click('Reopen note'); await app.click('Reload saved notes');
  assert.doesNotMatch(app.host.textContent, /Private synthetic note/);
  assert.match(app.host.textContent, /access changed/);
});
test('logout clears content before completion and offers explicit retry on error', async ctx => {
  let release, attempts = 0;
  const app = await mount(ctx, call => {
    if (call.path === '/private-research/notes') return response(listing([item]));
    if (call.path === '/private-research/logout') {
      attempts++; return attempts === 1 ? new Promise(resolve => { release = resolve; }) : response({ status: 'signed_out' });
    }
  });
  await app.click('Reopen note'); await app.click('Sign out');
  assert.doesNotMatch(app.host.textContent, /Private synthetic note/);
  await act(async () => release(response({ code: 'PRIVATE_WORKSPACE_UNAVAILABLE' }, 503))); await app.settle();
  assert.match(app.host.textContent, /Sign-out could not be confirmed/);
  await app.click('Retry sign out'); assert.equal(attempts, 2); assert.match(app.host.textContent, /Signed out/);
});
test('expired browser identity clears client state without another private request', async ctx => {
  const app = await mount(ctx, call => call.path === '/private-research/state' ? response({ ...identity, expires_in: 0 }) : undefined);
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
  assert.match(app.host.textContent, /Sign-in expired/); assert.equal(app.host.querySelectorAll('textarea').length, 0);
});
test('page history transitions discard private client state and require a fresh identity check', async ctx => {
  const app = await mount(ctx, call => call.path === '/private-research/notes' ? response(listing([item])) : undefined);
  await app.click('Reopen note');
  const count = app.calls.length;
  await act(async () => window.dispatchEvent(new dom.window.Event('pagehide')));
  assert.doesNotMatch(app.host.textContent, /Private synthetic note/);
  assert.match(app.host.textContent, /Check sign-in again/);
  assert.equal(app.calls.length, count);
});
test('malformed and oversized private responses fail closed', async () => {
  const controller = new AbortController();
  assert.throws(() => client.validateNote({ ...note, owner_key: { namespace: 'principal', id: 'bob' } }, 'alice'));
  globalThis.fetch = async () => response({ body: 'x'.repeat(65536) });
  await assert.rejects(client.privateRequest('/state', controller.signal), error => error.code === 'INVALID_RESPONSE');
});
test('auth status is preserved for empty, non-JSON, oversized and unreadable error bodies', async () => {
  for (const status of [401, 403]) for (const make of [
    () => new Response(null, { status }),
    () => new Response('<html>Unavailable</html>', { status, headers: { 'Content-Type': 'text/html' } }),
    () => new Response('x'.repeat(65537), { status, headers: { 'Content-Type': 'application/json' } }),
    () => new Response(new ReadableStream({ start(controller) { controller.error(new Error('Unreadable body')); } }), { status }),
  ]) {
    globalThis.fetch = async () => make();
    await assert.rejects(client.privateRequest('/note', new AbortController().signal), error => error.status === status);
  }
});
test('save binding compares the complete source envelope independently of object key order', () => {
  const reverse = value => value && typeof value === 'object' && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value).reverse().map(([key, item]) => [key, reverse(item)])) : value;
  assert.doesNotThrow(() => client.validateSavedSubmission({ ...note, source: reverse(source) }, 'alice', { body: note.body, source }));
  for (const changed of [
    { ...source, record: { ...source.record, admission_record_key: { namespace: 'admission_record', id: 'changed' } } },
    { ...source, record: { ...source.record, public_available_at: { kind: 'date', value: '2025-01-01' } } },
    { ...source, record: { ...source.record, manifest_sha256: 'invalid' } },
  ]) assert.throws(() => client.validateSavedSubmission({ ...note, source: changed }, 'alice', { body: note.body, source }),
    error => error.code === 'SAVE_RESPONSE_MISMATCH');
});
test('an unmounted page ignores a late private response when a different account opens', async ctx => {
  let release;
  const old = await mount(ctx, call => call.path === '/private-research/notes' ? response(listing([item]))
    : call.path.startsWith('/private-research/note?') ? new Promise(resolve => { release = resolve; }) : undefined);
  await old.click('Reopen note'); await old.unmount();
  const next = await mount(ctx, call => call.path === '/private-research/state'
    ? response({ ...identity, owner_key: 'bob' }) : call.path === '/private-research/notes' ? response({ ...listing([]), owner_key: 'bob' }) : undefined);
  await act(async () => release(response(note))); await next.settle();
  assert.doesNotMatch(next.host.textContent, /Private synthetic note/);
  assert.match(next.host.textContent, /No saved notes yet/);
});
