import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import postcss from 'postcss';

// Static presentation contracts only. These do not establish rendered geometry,
// actual touch sizes or unobscured keyboard focus; those remain browser gates.
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

test('UX-01A financial tables and provenance have readable text at desktop and 390px', () => {
  for (const width of [1440, 390]) {
    for (const selector of ['table', '.details-body', '.small']) {
      assert.ok(parseFloat(declaration(selector, 'font-size', width)) >= 13, selector);
    }
    assert.equal(declaration('.details-body .mono', 'font-size', width), 'inherit');
    assert.equal(declaration('td', 'font-variant-numeric', width), 'tabular-nums');
  }
});

test('UX-01A frequent disclosures, sources, topics and navigation target at least 44px', () => {
  for (const width of [1440, 390]) {
    for (const selector of ['summary', '.details-body a', '.filing-record a', '.question-chips button', '.comparison-remove', '.workspace-nav a', 'select']) {
      assert.ok(parseFloat(declaration(selector, 'min-height', width)) >= 44, selector);
    }
  }
});

test('UX-01A 390px controls and snapshot cards use the available panel width', () => {
  assert.equal(declaration('.history-controls', 'grid-template-columns', 390), 'minmax(0,1fr)');
  assert.equal(declaration('.metric-grid', 'grid-template-columns', 390), 'minmax(0,1fr)');
  assert.equal(declaration('.comparison-controls', 'grid-template-columns', 390), 'minmax(0,1fr)');
  assert.notEqual(declaration('.history-controls', 'grid-template-columns', 1440), 'minmax(0,1fr)');
  assert.notEqual(declaration('.metric-grid', 'grid-template-columns', 1440), 'minmax(0,1fr)');
});

test('UX-01A comparison retains non-sticky horizontal scrolling and table context', () => {
  for (const width of [1440, 390, 320]) {
    assert.equal(declaration('.table-scroll', 'overflow-x', width), 'auto');
    assert.equal(declaration('.table-scroll', 'max-width', width), '100%');
    assert.equal(declaration('.comparison-scroll', 'overflow', width), undefined);
    assert.equal(declaration('.comparison-scroll', 'max-height', width), undefined);
    assert.equal(declaration('.comparison-scroll', 'isolation', width), undefined);
    assert.equal(declaration('.comparison-table', 'min-width', width), '640px');
    assert.equal(declaration('table', 'border-collapse', width), 'collapse');
    assert.equal(declaration('.comparison-table', 'border-collapse', width), undefined);
    assert.equal(declaration('.comparison-table thead', 'background', width), 'var(--surface)');
    assert.equal(declaration('.comparison-table th:first-child', 'width', width), '160px');
    for (const selector of ['.comparison-table thead th', '.comparison-table tr > th:first-child', '.comparison-table thead tr > th:first-child']) {
      for (const property of ['position', 'top', 'left', 'z-index']) {
        assert.equal(declaration(selector, property, width), undefined, `${selector} ${property}`);
      }
    }
  }
});

test('UX-01A comparison uses the shared focus outline without source overlay workarounds', () => {
  // Static removal guard only; native Tab/Shift+Tab visibility needs Chromium.
  for (const width of [1440, 390, 320]) {
    assert.equal(declaration(':focus-visible', 'outline', width), '3px solid var(--accent)');
    assert.equal(declaration(':focus-visible', 'outline-offset', width), '3px');
  }
  stylesheet.walkRules(rule => {
    if (!rule.selector.includes('.comparison-')) return;
    assert.doesNotMatch(rule.selector, /:focus(?:-visible|-within)?|:has\(/, 'No comparison-specific focus layers');
    rule.walkDecls(entry => {
      assert.doesNotMatch(entry.prop, /^(?:z-index|scroll-padding(?:-.+)?|scroll-margin(?:-.+)?)$/, 'No obsolete stacking or scroll offsets');
      if (entry.prop === 'position') assert.notEqual(entry.value, 'sticky', 'No sticky comparison overlay');
    });
  });
});
