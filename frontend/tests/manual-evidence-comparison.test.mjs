import assert from 'node:assert/strict';
import test from 'node:test';

const question = 'Could the decline be explained by a temporary disruption?';
const a = { reference: 'Issuer report, page 10', passage: 'Shipments moved to the following quarter.',
  locator: 'Page 10', date: '2025-02-19', assessment: 'supports', rationale: 'A timing shift fits.' };
const b = { reference: 'Industry survey, page 4', passage: 'Orders fell before the disruption.',
  locator: 'Page 4', date: '', assessment: 'challenges', rationale: 'Demand may have weakened first.' };
const draft = { question, sources: [a, b], judgment: 'Timing alone is not established.',
  change: 'Comparable monthly orders and shipments.' };

test('MANUAL_COMPARISON_CONTRACT exports only the recorded manual evidence and researcher judgment', async () => {
  const { recordManualComparison } = await import('../lib/manual-evidence-comparison.ts');
  const recorded = JSON.parse(recordManualComparison({ ...draft, secret: 'omit me' }));
  assert.deepEqual(recorded, { schema_version: 1, kind: 'manual_evidence_comparison', question,
    sources: [a, b].map(row => ({ kind: 'manual_unverified', ...row, date: row.date || null })),
    provisional_judgment: draft.judgment, evidence_that_would_change_judgment: draft.change });
});

test('MANUAL_COMPARISON_CONTRACT rejects duplicate references, impossible dates, and excessive UTF-8 bytes', async () => {
  const { recordManualComparison } = await import('../lib/manual-evidence-comparison.ts');
  assert.throws(() => recordManualComparison({ ...draft, sources: [a, { ...b, reference: ' issuer report, page 10 ' }] }), /distinct/);
  assert.throws(() => recordManualComparison({ ...draft, sources: [{ ...a, date: '2025-02-30' }, b] }), /date/);
  const large = '📘'.repeat(2000);
  assert.throws(() => recordManualComparison({ question, sources: [a, b].map(row => ({ ...row, passage: large, rationale: '證'.repeat(1500) })),
    judgment: '證'.repeat(1500), change: '證'.repeat(1500) }), /32 KiB/);
});

test('MANUAL_COMPARISON_HOME records once, downloads locally, and invalidates on evidence or question edits', async ctx => {
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
  const nintendoQuestion = 'What did Nintendo report on 5 November 2026?';
  const nintendoRegion = () => doc.querySelector('[aria-label="Nintendo external source"]');
  const nintendoPdf = () => nintendoRegion()?.querySelector('a');
  assert.equal(nintendoRegion(), null);
  await change(doc.querySelector('#research-draft-input'), nintendoQuestion);
  await click('Keep research draft');
  const issuerLink = nintendoPdf();
  assert.equal(issuerLink?.href, 'https://www.nintendo.co.jp/ir/pdf/2026/261105e.pdf');
  assert.equal(issuerLink.referrerPolicy || issuerLink.getAttribute('referrerpolicy'), 'no-referrer');
  assert.equal(nintendoRegion().querySelector('time').getAttribute('datetime'), '2026-11-05');
  const disclosure = button('Compare two manual sources');
  assert.ok(disclosure);
  const panel = doc.getElementById(disclosure.getAttribute('aria-controls'));
  assert.ok(panel);
  assert.equal(disclosure.getAttribute('aria-expanded'), 'false');
  assert.equal(panel.hidden, true);
  disclosure.focus();
  await click('Compare two manual sources');
  assert.equal(doc.activeElement, disclosure);
  assert.equal(disclosure.getAttribute('aria-expanded'), 'true');
  assert.equal(panel.hidden, false);
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  for (const [letter, source] of [['A', a], ['B', b]]) for (const [key, label] of Object.entries({
    reference: 'Source reference ', passage: 'Passage ', locator: 'Locator ', date: 'Publication date ',
    assessment: 'Assessment ', rationale: 'Assessment rationale ',
  })) await fill(label + letter, source[key]);
  disclosure.focus();
  await click('Compare two manual sources');
  assert.equal(doc.activeElement, disclosure);
  assert.equal(disclosure.getAttribute('aria-expanded'), 'false');
  assert.equal(panel.hidden, true);
  await click('Compare two manual sources');
  assert.equal(doc.activeElement, disclosure);
  assert.equal(disclosure.getAttribute('aria-expanded'), 'true');
  assert.equal(panel.hidden, false);
  assert.equal(controlFor('Passage A').value, a.passage);
  assert.equal(controlFor('Assessment B').value, b.assessment);
  assert.equal(nintendoPdf(), issuerLink);
  await fill('Provisional judgment', draft.judgment);
  await fill('Evidence that would change the judgment', draft.change);
  await click('Record provisional judgment');
  await click('Download recorded comparison (.json)');
  assert.deepEqual(downloads, [['finlens-manual-comparison-v1.json', 'blob:http://finlens.test/synthetic-1']]);
  assert.equal(blobs.length, 1);
  assert.deepEqual(JSON.parse(await blobs[0].text()), JSON.parse((await import('../lib/manual-evidence-comparison.ts')).recordManualComparison({ ...draft, question: nintendoQuestion })));
  await fill('Publication date B', '2025-02-20');
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  assert.equal(controlFor('Assessment B').value, b.assessment);
  assert.equal(controlFor('Assessment rationale B').value, b.rationale);
  assert.equal(controlFor('Provisional judgment').value, draft.judgment);
  assert.equal(controlFor('Evidence that would change the judgment').value, draft.change);
  assert.match(doc.querySelector('[aria-label="Manual evidence comparison"]').textContent, /Review your notes and record the comparison again/);
  assert.deepEqual(revocations, ['blob:http://finlens.test/synthetic-1']);
  await fill('Source reference B', 'Different notebook');
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  await click('Record provisional judgment');
  await click('Download recorded comparison (.json)');
  assert.equal(downloads.length, 2);
  assert.equal(blobs.length, 2);
  assert.equal(JSON.parse(await blobs[1].text()).sources[1].reference, 'Different notebook');
  assert.equal(JSON.parse(await blobs[1].text()).sources[1].date, '2025-02-20');
  const outerInput = doc.querySelector('#research-draft-input');
  const replacement = 'A different question';
  const discardLabel = 'Discard previous comparison and keep new question';
  await change(outerInput, replacement);
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  assert.equal(button('Compare two manual sources'), undefined);
  assert.equal(nintendoRegion(), null);
  assert.deepEqual(revocations, ['blob:http://finlens.test/synthetic-1', 'blob:http://finlens.test/synthetic-2']);
  await change(outerInput, nintendoQuestion);
  assert.equal(button('Compare two manual sources'), undefined, 'Typing the original wording must not restore it');
  await click('Keep research draft');
  assert.ok(nintendoRegion());
  assert.equal(button('Compare two manual sources'), disclosure);
  assert.equal(controlFor('Source reference B').value, 'Different notebook');
  assert.equal(controlFor('Provisional judgment').value, draft.judgment);
  assert.equal(button('Download recorded comparison (.json)'), undefined, 'Re-keeping must not restore an invalidated export');
  await click('Record provisional judgment');
  assert.ok(button('Download recorded comparison (.json)'));
  await change(outerInput, replacement);
  const restore = button('Restore previous question');
  assert.ok(restore);
  restore.focus();
  await click('Restore previous question');
  assert.equal(doc.activeElement, outerInput);
  assert.equal(outerInput.value, nintendoQuestion);
  assert.equal(doc.querySelector('#research-draft-premise').textContent, nintendoQuestion);
  assert.equal(controlFor('Provisional judgment').value, draft.judgment);
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  assert.ok(nintendoRegion());
  await click('Record provisional judgment');
  assert.ok(button('Download recorded comparison (.json)'));
  await change(outerInput, replacement);
  await click('Keep research draft');
  assert.ok(button(discardLabel));
  assert.equal(doc.querySelector('#research-draft-premise'), null);
  assert.equal(button('Compare two manual sources'), undefined);
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  await click('Cancel replacement');
  assert.equal(button(discardLabel), undefined);
  assert.equal(doc.activeElement, outerInput);
  assert.equal(outerInput.value, nintendoQuestion);
  assert.equal(doc.querySelector('#research-draft-premise').textContent, nintendoQuestion);
  assert.equal(controlFor('Source reference B').value, 'Different notebook');
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  assert.ok(nintendoRegion());
  await change(outerInput, replacement);
  await click('Keep research draft');
  await click(discardLabel);
  assert.equal(doc.activeElement, outerInput);
  assert.equal(doc.querySelector('#research-draft-premise').textContent, replacement);
  assert.equal(nintendoRegion(), null);
  assert.equal(button('Download recorded comparison (.json)'), undefined);
  await click('Compare two manual sources');
  assert.equal(controlFor('Source reference B').value, '');
  assert.equal(controlFor('Provisional judgment').value, '');
  await change(outerInput, 'A third question with no previous notes to discard');
  assert.equal(button('Restore previous question'), undefined);
  await click('Keep research draft');
  assert.equal(button(discardLabel), undefined);
  assert.equal(doc.querySelector('#research-draft-premise').textContent, outerInput.value);
  assert.equal(blobs.length, 2);
  assert.equal(downloads.length, 2);
  assert.equal(requests.length, before);
});
