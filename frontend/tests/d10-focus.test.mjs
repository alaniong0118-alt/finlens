import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

// Test the actual browser-spec geometry function without starting a browser.
const text = readFileSync(new URL('../e2e/alternative-observation-period.spec.ts', import.meta.url), 'utf8');
const source = ts.createSourceFile('d10.spec.ts', text, ts.ScriptTarget.Latest, true);
const fn = name => {
  const node = source.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === name);
  assert.ok(node, name); return node.getText(source);
};
const code = ts.transpileModule(fn('captureAlternativeFocus'), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const context = { getComputedStyle: node => node.style, innerWidth: 390, innerHeight: 844,
  scrollX: 0, scrollY: 0, devicePixelRatio: 1, Number, Object, Math, parseFloat };
const capture = runInNewContext(`${code}; captureAlternativeFocus;`, context);
const box = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, width, height });
function element(rect, style = {}, parentElement = null) {
  return { localName: 'a', parentElement, clientLeft: 0, clientTop: 0, clientWidth: rect.width, clientHeight: rect.height,
    scrollLeft: 0, scrollTop: 0, scrollWidth: rect.width, scrollHeight: rect.height,
    style: { outlineStyle: 'solid', outlineWidth: '3px', outlineOffset: '3px', overflowX: 'visible', overflowY: 'visible', contain: 'none', clipPath: 'none', ...style },
    getBoundingClientRect: () => rect, matches: selector => selector === ':focus-visible' };
}
test('D10 actual helper preserves outset failure and accepts a padded inset outline', () => {
  const target = box(20, 800, 100, 44);
  const outset = capture(element(target)), inset = capture(element(target, { outlineOffset: '-6px' }));
  assert.equal(outset.extent, 6); assert.equal(outset.rasterContained, false);
  assert.equal(inset.extent, 0); assert.equal(inset.rasterContained, true);
});
test('D10 actual helper rejects clipping ancestors even with inset', () => {
  const parent = element(box(0, 0, 100, 844), { overflowX: 'hidden' });
  const result = capture(element(box(20, 100, 100, 44), { outlineOffset: '-6px' }, parent));
  assert.equal(result.clippingContained, false); assert.equal(result.rasterContained, false);
});
test('D10 actual helper rejects missing width, nonfinite geometry and wrong DPR', () => {
  assert.equal(capture(element(box(20, 100, 100, 44), { outlineWidth: '0px' })).geometryValid, false);
  assert.equal(capture(element(box(20, NaN, 100, 44))).geometryValid, false);
  context.devicePixelRatio = 2;
  try { assert.equal(capture(element(box(20, 100, 100, 44))).rasterContained, false); }
  finally { context.devicePixelRatio = 1; }
  const noOutline = capture(element(box(20, 100, 100, 44), { outlineStyle: 'none' }));
  assert.equal(noOutline.outline, 'none');
  assert.match(fn('expectKeyboardFocus'), /expect\(paint\.outline\)\.not\.toBe\('none'\)/);
});
test('D10 physical-pixel tolerance stays strictly below one half', () => {
  assert.equal(capture(element(box(5.6, 100, 100, 44))).rasterContained, true);
  assert.equal(capture(element(box(5.5, 100, 100, 44))).rasterContained, false);
});
test('D10 unsupported clipping and incomplete ancestry fail closed', () => {
  const clip = element(box(0, 0, 390, 844), { clipPath: 'circle(10px)' });
  assert.equal(capture(element(box(20, 100, 100, 44), {}, clip)).rasterContained, false);
  let parent = null;
  for (let index = 0; index < 33; index++) parent = element(box(0, 0, 390, 844), {}, parent);
  assert.equal(capture(element(box(20, 100, 100, 44), {}, parent)).ancestryComplete, false);
});
