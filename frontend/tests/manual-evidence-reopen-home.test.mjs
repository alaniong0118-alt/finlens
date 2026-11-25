import assert from 'node:assert/strict';
import test from 'node:test';

const question = 'Could the decline be explained by a temporary disruption?';
const a = { reference: 'Issuer report, page 10', passage: 'Shipments moved to the following quarter.',
  locator: 'Page 10', date: '2025-02-19', assessment: 'supports', rationale: 'A timing shift fits.' };
const b = { reference: 'Industry survey, page 4', passage: 'Orders fell before the disruption.',
  locator: 'Page 4', date: '', assessment: 'challenges', rationale: 'Demand may have weakened first.' };
const draft = { question, sources: [a, b], judgment: 'Timing alone is not established.',
  change: 'Comparable monthly orders and shipments.' };

test('REOPEN_HOME opens its own V1 download without replacing notes or reviving stale export', async ctx => {
  const [{ readFileSync }, { createRequire }, { fileURLToPath }, { JSDOM }, { default: ts }, { componentLoader }] = await Promise.all([
    import('node:fs'), import('node:module'), import('node:url'), import('jsdom'), import('typescript'), import('./component-loader.mjs'),
  ]);
  const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://finlens.test' });
  const previous = new Map(), requests = [], forbidden = [], blobs = [], downloads = [], revocations = [];
  const set = (key, value) => {
    previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  };
  const deny = key => { forbidden.push(key); throw new Error(key); };
  let root, act;
  ctx.after(async () => {
    try { if (root) await act(async () => root.unmount()); assert.deepEqual(forbidden, []); }
    finally {
      dom.window.close();
      for (const [key, desc] of previous) { if (desc) Object.defineProperty(globalThis, key, desc); else delete globalThis[key]; }
    }
  });
  for (const key of ['window', 'document', 'HTMLElement', 'Event', 'MouseEvent']) set(key, dom.window[key]);
  set('IS_REACT_ACT_ENVIRONMENT', true);
  for (const key of ['indexedDB', 'localStorage', 'sessionStorage']) {
    previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    for (const target of [globalThis, dom.window]) Object.defineProperty(target, key, { configurable: true, get: () => deny(key) });
  }
  const NativeURL = globalThis.URL;
  const createObjectURL = blob => { blobs.push(blob); return 'blob:http://finlens.test/synthetic-' + blobs.length; };
  const revokeObjectURL = url => revocations.push(url);
  set('URL', class extends NativeURL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  Object.assign(dom.window.URL, { createObjectURL, revokeObjectURL });
  dom.window.HTMLAnchorElement.prototype.click = function () { downloads.push([this.download, this.href]); };
  const fetch = async (path, init) => {
    requests.push([path, init?.method ?? 'GET']);
    if ((init?.method ?? 'GET') !== 'GET') return deny('non-GET');
    if (path === '/api/finlens/companies') return Response.json([]);
    if (path === '/api/finlens/capabilities') return Response.json({ research_mode: true, ai_analysis_configured: false,
      ai_analysis_enabled: false, server_profile: 'sec_readonly', filing_research_enabled: false });
    return deny('unexpected request');
  };
  set('fetch', fetch); dom.window.fetch = fetch;
  const { default: React, act: reactAct } = await import('react'); act = reactAct;
  const { createRoot } = await import('react-dom/client');
  const dir = fileURLToPath(new URL('..', import.meta.url));
  const filename = fileURLToPath(new URL('../app/page.tsx', import.meta.url));
  const load = componentLoader(dir), require = createRequire(filename), exports = {};
  const related = new Set(['company-overview', 'manual-evidence-comparison']);
  const output = ts.transpileModule(readFileSync(filename, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, esModuleInterop: true,
  } }).outputText;
  new Function('require', 'exports', output)(name => {
    if (name === 'next/link') return props => React.createElement('a', props);
    if (name.startsWith('@/components/') && !related.has(name.split('/').at(-1))) return () => null;
    if (name.startsWith('@/')) return load(fileURLToPath(new URL('../' + name.slice(2) + (name.startsWith('@/components/') ? '.tsx' : '.ts'), import.meta.url)));
    return require(name);
  }, exports);
  const doc = dom.window.document;
  root = createRoot(doc.querySelector('#root'));
  await act(async () => root.render(React.createElement(exports.default)));
  const button = label => [...doc.querySelectorAll('button')].find(node => node.textContent === label && !node.closest('[hidden]'));
  async function change(control, value) {
    assert.ok(control, 'Missing input control');
    await act(async () => {
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(control), 'value').set.call(control, value);
      control.dispatchEvent(new dom.window.Event(control.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    });
  }
  const controlFor = name => [...doc.querySelectorAll('label')].find(x => x.firstChild?.textContent === name)?.control;
  const fill = (name, value) => change(controlFor(name), value);
  const click = async label => { const node = button(label); assert.ok(node, label); await act(async () => node.click()); };
  const before = requests.length;
  const original = 'Which explanation fits the original research question?';
  const delayedText = 'Synthetic REOPEN_STALE fixture that must not appear';
  const control = doc.querySelector('#research-draft-input');
  const preview = () => doc.querySelector('[aria-label="Reopened comparison preview"]');
  await change(control, original);
  await click('Keep research draft');
  await click('Compare two manual sources');
  for (const [slot, source] of [['A', a], ['B', b]]) {
    await fill('Source reference ' + slot, source.reference);
    await fill('Passage ' + slot, source.passage);
    await fill('Locator ' + slot, source.locator);
    await fill('Publication date ' + slot, source.date);
    await fill('Assessment ' + slot, source.assessment);
    await fill('Assessment rationale ' + slot, source.rationale);
  }
  await fill('Provisional judgment', draft.judgment);
  await fill('Evidence that would change the judgment', draft.change);
  await click('Record provisional judgment');
  await click('Download recorded comparison (.json)');
  assert.equal(downloads.length, 1);
  assert.equal(downloads[0][0], 'finlens-manual-comparison-v1.json');
  const downloaded = await blobs[0].arrayBuffer();

  await fill('Assessment rationale A', 'Unrecorded live rationale A');
  await fill('Assessment rationale B', 'Unrecorded live rationale B');
  await fill('Provisional judgment', 'Unrecorded live provisional judgment');
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  async function selectFile(bytes, awaitBuffer) {
    const file = new dom.window.File([bytes], 'manual-comparison.json', { type: 'application/json' });
    Object.defineProperty(file, 'arrayBuffer', { value: () => awaitBuffer(bytes) });
    const input = controlFor('Open a recorded comparison (.json)');
    assert.ok(input);
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    await act(async () => input.dispatchEvent(new dom.window.Event('change', { bubbles: true })));
  }
  await selectFile(downloaded, async buffer => buffer);
  assert.equal(Boolean(preview()?.textContent.includes(draft.judgment)), true, 'Reopen must preview bytes from Home’s actual V1 download');
  assert.equal(controlFor('Provisional judgment').value, 'Unrecorded live provisional judgment');
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  const { recordManualComparison } = await import('../lib/manual-evidence-comparison.ts');
  const delayed = new TextEncoder().encode(recordManualComparison({ ...draft, question: delayedText })).buffer;
  let release;
  await selectFile(delayed, buffer => new Promise(resolve => { release = () => resolve(buffer); }));
  assert.equal(typeof release, 'function', 'The second file read really began before question edit');
  assert.ok(doc.body.textContent.includes('Reading the local comparison file'));
  await change(control, 'A different question, not yet kept');
  assert.equal(button('Compare two manual sources') === undefined, true);
  await click('Restore previous question');
  assert.equal(control.value, original);
  await act(async () => release());
  assert.equal(preview() === null, true, 'Neither old nor delayed preview should survive question invalidation');
  assert.equal(doc.body.textContent.includes(delayedText), false);
  assert.equal(doc.body.textContent.includes('Reading the local comparison file'), false);
  assert.equal(controlFor('Assessment rationale A').value, 'Unrecorded live rationale A');
  assert.equal(controlFor('Assessment rationale B').value, 'Unrecorded live rationale B');
  assert.equal(controlFor('Provisional judgment').value, 'Unrecorded live provisional judgment');
  assert.equal(button('Download recorded comparison (.json)') === undefined, true);
  assert.equal(downloads.length, 1);
  assert.equal(blobs.length, 1);
  assert.deepEqual(requests.slice(before), []);
});
