import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
'use strict';
// D10's bounded synthetic observation checks, narrowed to this one history spec.
// No browser, application, process or network execution.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const text = fs.readFileSync(new URL('../e2e/history-missing-detail.spec.ts', import.meta.url), 'utf8');
const source = ts.createSourceFile('history.spec.ts', text, ts.ScriptTarget.Latest, true);
const fn = name => { const node = source.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === name); assert(node, name); return node.getText(source); };
const compile = code => ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const box = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, width, height });
function element(rect, style = {}, parentElement = null) {
  const node = { localName: 'summary', parentElement, clientLeft: 0, clientTop: 0, clientWidth: rect.width, clientHeight: rect.height,
    scrollLeft: 0, scrollTop: 0, scrollWidth: rect.width, scrollHeight: rect.height,
    style: { outlineStyle: 'solid', outlineWidth: '3px', outlineOffset: '3px', overflowX: 'visible', overflowY: 'visible', contain: 'none', clipPath: 'none', ...style },
    getBoundingClientRect: () => rect, matches: value => value === ':focus-visible' };
  for (const key of ['textContent', 'innerHTML', 'outerHTML', 'href']) Object.defineProperty(node, key, { get() { throw new Error('Raw DOM read forbidden'); } });
  node.focus = node.scrollIntoView = () => { throw new Error('Focus/scroll mutation forbidden'); };
  return node;
}
const context = vm.createContext({ getComputedStyle: node => node.style, innerWidth: 390, innerHeight: 844,
  scrollX: 0, scrollY: 0, devicePixelRatio: 1, Number, Object, Math, parseFloat });
const capture = new vm.Script(compile(fn('captureHistoryFocus')) + ';captureHistoryFocus;').runInContext(context);
let checks = 0;
async function check(name, task) { await task(); checks++; console.log(`ok ${checks} - ${name}`); }
(async () => {
  await check('ordinary in-view focus passes while retaining strict results', () => {
    const value = capture(element(box(20, 30, 250, 30)));
    assert(value.geometryValid && value.rasterContained && value.strictViewportContained && value.strictClippingContained);
  });
  await check('inset envelope preserves viewport and ancestor clipping checks', () => {
    context.innerHeight = 1000;
    const rect = box(20, 970, 250, 30);
    const outset = capture(element(rect));
    assert.equal(outset.extent, 6);
    assert(!outset.rasterContained);
    const inset = capture(element(rect, { outlineOffset: '-6px' }));
    assert.equal(inset.extent, 0);
    assert(inset.geometryValid && inset.rasterContained);
    const parent = element(box(0, 0, 390, 990), { overflowY: 'hidden' });
    assert(!capture(element(rect, { outlineOffset: '-6px' }, parent)).clippingContained);
    assert(!capture(element(rect, { outlineWidth: '0px', outlineOffset: '-6px' })).geometryValid);
    assert.equal(capture(element(rect, { outlineStyle: 'none', outlineOffset: '-6px' })).outline, 'none');
    assert(!capture(element(box(20, NaN, 250, 30), { outlineOffset: '-6px' })).geometryValid);
    context.innerHeight = 844;
  });
  await check('negative ancestor coordinates are valid finite geometry', () => {
    const parent = element(box(-30, -100, 800, 1000), { overflowX: 'auto', overflowY: 'auto' });
    const value = capture(element(box(20, 30, 250, 30), {}, parent));
    assert(value.geometryValid && value.rasterContained);
  });
  await check('negative sizes and nonfinite coordinates fail closed', () => {
    assert(!capture(element(box(20, 30, -1, 30))).geometryValid);
    assert(!capture(element(box(Infinity, 30, 250, 30))).geometryValid);
  });
  await check('per-axis clipping ignores only the genuinely unclipped axis', () => {
    const parent = element(box(10, 100, 300, 20), { overflowX: 'hidden', overflowY: 'visible' });
    assert(capture(element(box(20, 30, 250, 30), {}, parent)).clippingContained);
    parent.style.overflowY = 'auto';
    assert(!capture(element(box(20, 30, 250, 30), {}, parent)).clippingContained);
  });
  await check('paint containment clips both axes and clip paths are unsupported', () => {
    const parent = element(box(10, 100, 300, 20), { contain: 'paint' });
    assert(!capture(element(box(20, 30, 250, 30), {}, parent)).clippingContained);
    parent.style.contain = 'none'; parent.style.clipPath = 'circle(20px)';
    assert(!capture(element(box(20, 30, 250, 30), {}, parent)).clipPathSupported);
  });
  await check('strict containment and less-than-half-physical-pixel rule stay separate', () => {
    const accepted = capture(element(box(5.6, 30, 250, 30)));
    assert(!accepted.strictViewportContained && accepted.rasterContained);
    assert(!capture(element(box(5.5, 30, 250, 30))).rasterContained);
    context.devicePixelRatio = 2;
    assert(!capture(element(box(20, 30, 250, 30))).rasterContained);
    context.devicePixelRatio = 1;
  });
  await check('unknown overflow and truncated ancestor inventory fail closed', () => {
    let parent = element(box(0, 0, 390, 844), { overflowX: 'unknown-css' });
    assert(!capture(element(box(20, 30, 250, 30), {}, parent)).rasterContained);
    parent = null;
    for (let index = 0; index < 33; index++) parent = element(box(0, 0, 390, 844), {}, parent);
    assert(!capture(element(box(20, 30, 250, 30), {}, parent)).ancestryComplete);
  });
  const helpers = new Function('Buffer', 'captureHistoryFocus', compile(fn('captureFocusEvidence') + '\n' + fn('tabTo')) + ';return {captureFocusEvidence,tabTo};')(Buffer, capture);
  function mock(screenshotError = false, attachmentError = false) {
    const operations = [], attachments = [];
    const actual = element(box(20, 30, 250, 30));
    const locator = { first() { return this; }, count: async () => 1, evaluate: async callback => callback(actual) };
    const page = { keyboard: { press: async key => operations.push('key:' + key) },
      screenshot: async options => { operations.push('screenshot'); assert.equal(options.fullPage, false); assert.equal(options.scale, 'device'); assert.equal(options.caret, 'initial'); assert.equal(options.animations, 'allow'); if (screenshotError) throw new Error('synthetic screenshot failure'); return Buffer.from('synthetic-png'); },
      locator: () => locator };
    const evidence = { attempts: 0, info: { attach: async (name, value) => { operations.push('attach:' + value.contentType); if (attachmentError && value.contentType === 'image/png') throw new Error('synthetic attachment failure'); attachments.push({ name, ...value }); } } };
    return { page, evidence, operations, attachments };
  }
  await check('Tab exhaustion captures actual focus PNG and geometry before rejection', async () => {
    const value = mock(), target = { evaluate: async () => false };
    await assert.rejects(helpers.tabTo(value.page, target, value.evidence, 'synthetic-limit', 2), /Native Tab/);
    assert.deepEqual(value.operations.slice(0, 3), ['key:Tab', 'key:Tab', 'screenshot']);
    assert.equal(value.attachments.length, 2);
    assert(value.attachments[0].name.includes('tab-limit'));
    assert(JSON.parse(value.attachments[1].body).paint.geometryValid);
  });
  for (const kind of ['screenshot', 'attachment']) await check(`${kind} failure remains incomplete even when geometry attaches`, async () => {
    const value = mock(kind === 'screenshot', kind === 'attachment');
    await assert.rejects(helpers.captureFocusEvidence(value.page, value.evidence, 'synthetic-failure'), /INCOMPLETE_FOCUS_EVIDENCE/);
    assert(value.attachments.some(row => row.contentType === 'application/json' && !JSON.parse(row.body).evidenceComplete));
  });
  await check('native sequencing and state retention are explicit in the concrete spec', () => {
    assert(text.includes('for (const width of [1440, 390])'));
    assert(text.includes("await page.keyboard.press('ArrowRight')"));
    const arrow = text.indexOf("await page.keyboard.press('ArrowRight')"), nextDisclosure = text.indexOf("await tabTo(page, selectedSummary");
    assert(arrow > 0 && nextDisclosure > arrow);
    assert(fn('toggleWithKeyboard').includes('await expect(summary).toBeFocused()'));
    assert(!/\.(?:focus|scrollIntoView)\s*\(/.test(text));
    assert(fn('tabTo').indexOf('tab-limit') < fn('tabTo').lastIndexOf('throw new Error'));
  });
  console.log(JSON.stringify({ checks, outcome: 'PASS_SYNTHETIC_STATIC_ONLY', browserExecuted: false }));
})().catch(error => { console.error(error); process.exitCode = 1; });
