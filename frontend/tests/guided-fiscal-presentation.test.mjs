import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import postcss from 'postcss';

// Same static PostCSS convention as ux01a-presentation.test.mjs; browser geometry
// remains a separate gate. These checks do not claim actual rendered dimensions.
const stylesheet = postcss.parse(readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8'));
function declaration(selector, property, width) {
  let value;
  stylesheet.walkRules(rule => {
    if (!rule.selector.split(',').map(item => item.trim()).includes(selector)) return;
    for (let parent = rule.parent; parent && parent !== stylesheet; parent = parent.parent) {
      if (parent.type !== 'atrule' || parent.name !== 'media') continue;
      const bound = parent.params.match(/^\((max|min)-width:\s*(\d+)px\)$/);
      if (!bound || (bound[1] === 'max' ? width > Number(bound[2]) : width < Number(bound[2]))) return;
    }
    rule.walkDecls(property, entry => { value = entry.value; });
  });
  return value;
}

test('Guided fiscal year text inputs reuse control appearance and sizing at desktop and narrow widths', () => {
  const selector = '.question-guide input[type="text"]';
  for (const width of [1440, 390, 320]) {
    for (const property of ['font', 'display', 'width', 'min-width', 'border', 'border-radius', 'background', 'color', 'padding', 'margin-top', 'min-height', 'font-size']) {
      assert.equal(declaration(selector, property, width), declaration('select', property, width), property);
    }
    assert.equal(declaration(selector, 'width', width), '100%');
    assert.equal(declaration(selector, 'min-height', width), '44px');
    assert.equal(declaration(selector, 'font-size', width), '14px');
    assert.equal(declaration(`${selector}:hover`, 'border-color', width), 'var(--accent)');
    assert.equal(declaration('.question-preview', 'font-size', width), '13px');
  }
});

test('Guided fiscal text-input styling is limited to the question guide and preserves other control selectors', () => {
  const target = '.question-guide input[type="text"]', selectors = [];
  stylesheet.walkRules(rule => {
    if (!rule.selector.includes(target)) return;
    const parts = rule.selector.split(',').map(item => item.trim()); selectors.push(parts);
    assert.ok(parts.every(part => ['button', 'select', 'textarea', target, 'select:hover', 'textarea:hover', `${target}:hover`].includes(part)));
  });
  assert.deepEqual(selectors, [
    ['button', 'select', 'textarea', target], ['select', 'textarea', target],
    ['select:hover', 'textarea:hover', `${target}:hover`],
  ]);
});

test('Guided controls reserve the 6px outset focus outline during native block-axis scrolling', () => {
  const selector = '.question-guide :is(input[type="text"],select,button)', rules = [];
  stylesheet.walkRules(rule => { if (rule.selector === selector) rules.push(rule); });
  assert.equal(rules.length, 1, 'One local rule covers the guided text inputs, selects and Use question button');
  assert.equal(rules[0].parent, stylesheet, 'The focus clearance applies at desktop and narrow widths');
  assert.deepEqual(rules[0].nodes.map(entry => [entry.prop, entry.value]), [['scroll-margin-block', '8px']]);
  for (const width of [1440, 390, 320]) {
    assert.equal(declaration(':focus-visible', 'outline', width), '3px solid var(--accent)');
    assert.equal(declaration(':focus-visible', 'outline-offset', width), '3px');
  }
});
