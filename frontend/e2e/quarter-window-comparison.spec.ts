import type { Locator } from '@playwright/test';
import { test, expect, lifecycle, replayCancellations, annualRequestCursor, assessFocusPaint } from './fixtures/annual-period-browser';
import * as data from './fixtures/data';

test.use({ deviceScaleFactor: 1 });

// Observe actual focus paint and clipping, without changing scroll or focus.
function focusGeometry(element: Element) {
  const r = element.getBoundingClientRect(), style = getComputedStyle(element);
  const width = parseFloat(style.outlineWidth), offset = parseFloat(style.outlineOffset);
  const ancestors = [], unsupported: string[] = [];
  let node: Element | null = element, depth = 0;
  while (node && depth++ < 32) {
    const s = getComputedStyle(node), box = node.getBoundingClientRect();
    if (s.opacity !== '1' || s.filter !== 'none' || s.mixBlendMode !== 'normal') unsupported.push('Unsupported composite paint');
    if (node !== element && (s.overflowX !== 'visible' || s.overflowY !== 'visible')) ancestors.push({
      left: box.left + node.clientLeft, right: box.left + node.clientLeft + node.clientWidth,
      top: box.top + node.clientTop, bottom: box.top + node.clientTop + node.clientHeight,
      x: s.overflowX !== 'visible', y: s.overflowY !== 'visible' });
    if (s.clipPath !== 'none' || /paint|strict|content/.test(s.contain)) unsupported.push('Unsupported paint clipping');
    node = node.parentElement;
  }
  if (node) unsupported.push('Ancestor bound exceeded');
  const visibleTop = Math.max(0, r.top), visibleBottom = Math.min(innerHeight, r.bottom);
  const visibleHeight = Math.max(0, visibleBottom - visibleTop), distance = offset + width / 2;
  // Probe two visible positions on each actual side-outline segment. A tall
  // region's offscreen center cannot establish its visible perimeter exposure.
  const points = [r.left - distance, r.right + distance].flatMap(x => [0.25, 0.75]
    .map(fraction => ({ x, y: visibleTop + visibleHeight * fraction })));
  const surfaces = points.map(point => {
    const hit = document.elementFromPoint(point.x, point.y);
    const exposed = !!hit && (hit === element || element.contains(hit));
    const layers: { color: string }[] = [], issues = [...unsupported];
    let paint = hit, paintDepth = 0, opaque = false;
    while (paint && paintDepth++ < 32) {
      const s = getComputedStyle(paint);
      if (s.opacity !== '1' || s.filter !== 'none' || s.mixBlendMode !== 'normal') issues.push('Unsupported sampled composite paint');
      if (!opaque) {
        if (s.backgroundImage !== 'none') issues.push('Unsupported sampled background image');
        layers.push({ color: s.backgroundColor });
        opaque = /^rgb\([^/]*\)$/.test(s.backgroundColor) || /^rgba\([^,]+,[^,]+,[^,]+,\s*1\)$/.test(s.backgroundColor);
      }
      paint = paint.parentElement;
    }
    if (paint) issues.push('Sampled ancestor bound exceeded');
    if (!exposed) issues.push('Visible side-outline sample is occluded');
    return { ...point, exposed, layers, unsupported: issues };
  });
  const center = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
  return { rect: { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height },
    viewport: { width: innerWidth, height: innerHeight }, dpr: devicePixelRatio,
    width, offset, extent: Math.max(0, width + offset), outline: style.outlineStyle, outlineColor: style.outlineColor,
    visible: element.matches(':focus-visible'), hit: !!center && (center === element || element.contains(center)),
    ancestors, surfaces, visibleHeight,
    pageWidth: document.documentElement.scrollWidth };
}

test('quarter windows: scope, provenance, keyboard and request ownership', async ({ page, scenario }, info) => {
  // The inherited annual fixture uses BBB0. This case explicitly exercises BBB1.
  scenario.versions.BBB = 1;
  const panel = page.getByRole('region', { name: 'Reported quarter-duration windows', exact: true });
  const grid = panel.getByRole('region', { name: 'Reported window financial metrics', exact: true });
  const endpoint = (ticker: string) => `/companies/${ticker}/financials/quarters`;
  const keys = data.reportedQuarterWindows.map(w => `${w.start},${w.end}`);
  let since = 0;
  const rows = () => lifecycle(scenario, [...replayCancellations('AAA', 0), ...replayCancellations('BBB', 1)]);
  async function settledDiscovery(ticker: string, pin: string) {
    await expect.poll(() => {
      const snapshot = rows(), requests = snapshot.rows.filter(row => row.id > since && JSON.parse(row.request)[1] === endpoint(ticker));
      return { invalid: snapshot.bindingErrors, unbound: snapshot.rejectedUnbound,
        completed: requests.filter(row => row.state === 'completed' && row.response?.status === 200 && row.response.version === pin && JSON.parse(row.request)[2] === '').length,
        bad: requests.filter(row => !['completed', 'cancelled'].includes(row.state)
          || JSON.parse(row.request)[2] !== '' || JSON.parse(row.request)[3] !== pin
          || row.state === 'completed' && (row.response?.status !== 200 || row.response.version !== pin || row.response.code !== null)
          || row.state === 'cancelled' && (row.error !== 'net::ERR_ABORTED' || row.response !== null)).length,
        cancels: requests.filter(row => row.state === 'cancelled').length > 1 };
    }).toEqual({ invalid: [], unbound: [], completed: 1, bad: 0, cancels: false });
  }
  let holdComparison = false;
  scenario.overrides.push(request => {
    if (request.path !== endpoint('AAA')) return;
    if (holdComparison && request.query.has('period')) return;
    const body = data.quarterWindows('AAA', request.query.getAll('period'));
    for (const column of body.columns) {
      const source = column.metrics.revenue.provenance[0];
      column.metrics.revenue.alternatives = [{ ...source, fact_id: source.fact_id + 5000,
        original_concept: 'Synthetic_RevenueAlternative', value: '123.45' }];
    }
    return { body };
  });
  const held = scenario.hold(request => holdComparison && request.path === endpoint('AAA') && request.query.has('period'));
  try {
    await scenario.open(); await scenario.ready(); await settledDiscovery('AAA', '0');
    await expect(panel).toContainText('Publication version 0');
    await expect(panel).toContainText('not verified fiscal-quarter labels');
    await expect(panel.getByRole('checkbox')).toHaveCount(4);
    await expect(grid).toHaveCount(0);
    const comparisonRequests = () => scenario.ledger.filter(r => r.path === endpoint('AAA') && r.query.has('period'));
    for (let i = 0; i < 4; i++) await panel.getByRole('checkbox').nth(i).check();
    const compare = panel.getByRole('button', { name: 'Compare reported windows', exact: true });
    await compare.click(); await expect(grid.locator('tbody > tr')).toHaveCount(11);
    expect(comparisonRequests()).toHaveLength(1); expect(comparisonRequests()[0].query.getAll('period')).toEqual(keys);
    expect(comparisonRequests()[0].pin).toBe('0');
    await expect(grid).toContainText('Synthetic industry exclusion for this observation.');
    await expect(grid).toContainText('Synthetic compatible direct-period operands are missing.');
    await expect(grid.locator('tbody > tr').filter({ has: page.getByRole('rowheader', { name: 'Free cash flow', exact: true }) }).locator('.metric-value').first()).toHaveText('$0');
    await expect(panel).toContainText('overlapping intervals');
    await expect(grid.locator('thead th')).toHaveCount(5);
    await expect(grid.locator('thead')).toContainText('Jan 16, 2025 – Mar 31, 2025');
    await expect(grid.locator('thead')).toContainText('Jan 1, 2025 – Mar 31, 2025');
    await panel.getByRole('checkbox').nth(3).uncheck(); await panel.getByRole('checkbox').nth(2).uncheck();
    await expect(grid).toHaveCount(0); expect(comparisonRequests()).toHaveLength(1);
    await compare.click(); await expect(grid.locator('tbody > tr')).toHaveCount(11);
    expect(comparisonRequests()).toHaveLength(2); expect(comparisonRequests()[1].query.getAll('period')).toEqual(keys.slice(0, 2));
    const noNewRequests = scenario.ledger.length;

    async function capture(control: Locator, name: string, region = false) {
      await expect(control).toBeFocused();
      const geometry = await control.evaluate(focusGeometry);
      const contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
      await info.attach(`quarter-${name}-geometry`, { body: JSON.stringify({ geometry, contrast }), contentType: 'application/json' });
      await info.attach(`quarter-${name}`, { body: await page.screenshot(), contentType: 'image/png' });
      expect(geometry.dpr).toBe(1); expect(geometry.visible).toBe(true); expect(geometry.width).toBeGreaterThanOrEqual(3);
      expect(geometry.outline).not.toBe('none'); expect(contrast.sufficient).toBe(true);
      expect(geometry.surfaces.every(surface => surface.exposed)).toBe(true);
      expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewport.width);
      for (const n of Object.values(geometry.rect).concat([geometry.extent])) expect(Number.isFinite(n)).toBe(true);
      expect(geometry.rect.height).toBeGreaterThanOrEqual(44);
      const box = { left: geometry.rect.left - geometry.extent, right: geometry.rect.right + geometry.extent,
        top: geometry.rect.top - geometry.extent, bottom: geometry.rect.bottom + geometry.extent };
      expect(box.left).toBeGreaterThan(-0.5); expect(box.right).toBeLessThan(geometry.viewport.width + 0.5);
      if (region) {
        // The 11-row region is intentionally taller than the viewport. Its
        // visible vertical perimeter must remain exposed; descendants fit fully.
        expect(box.bottom).toBeGreaterThan(0); expect(box.top).toBeLessThan(geometry.viewport.height);
        expect(geometry.visibleHeight).toBeGreaterThanOrEqual(44);
      } else {
        expect(geometry.hit).toBe(true); expect(box.top).toBeGreaterThan(-0.5); expect(box.bottom).toBeLessThan(geometry.viewport.height + 0.5);
      }
      for (const ancestor of geometry.ancestors) {
        if (ancestor.x) { expect(box.left).toBeGreaterThan(ancestor.left - 0.5); expect(box.right).toBeLessThan(ancestor.right + 0.5); }
        if (ancestor.y) { expect(box.top).toBeGreaterThan(ancestor.top - 0.5); expect(box.bottom).toBeLessThan(ancestor.bottom + 0.5); }
      }
    }
    await panel.getByRole('button', { name: 'Refresh reported windows', exact: true }).focus();
    await page.keyboard.press('Tab'); await capture(grid, 'region', true);
    await page.keyboard.press('ArrowRight');
    const revenue = grid.locator('tbody > tr').first(), details = revenue.locator('td').first().locator('details.provenance');
    const summary = details.locator(':scope > summary');
    await page.keyboard.press('Tab'); await capture(summary, 'summary'); await page.keyboard.press('Space');
    const selectedLink = details.getByRole('link', { name: 'Open official SEC filing ↗', exact: true });
    await page.keyboard.press('Tab'); await capture(selectedLink, 'source');
    await expect(selectedLink).toHaveAttribute('href', data.secUrl('AAA'));
    const alternatives = details.locator('details'), alternativeToggle = alternatives.locator(':scope > summary');
    await page.keyboard.press('Tab'); await capture(alternativeToggle, 'alternative-summary'); await page.keyboard.press('Space');
    await page.keyboard.press('Tab'); await capture(alternatives.getByRole('link', { name: 'SEC source ↗', exact: true }), 'alternative-source');
    const readability = await details.evaluate(element => {
      const box = element.getBoundingClientRect(), s = getComputedStyle(element);
      return { width: box.width, scroll: element.scrollWidth, client: element.clientWidth, wordBreak: s.wordBreak, overflowWrap: s.overflowWrap };
    });
    expect(readability.width).toBeGreaterThanOrEqual(176); expect(readability.scroll).toBeLessThanOrEqual(readability.client + 1);
    expect(readability.wordBreak).not.toBe('break-all');
    await info.attach('quarter-grid', { body: await page.screenshot(), contentType: 'image/png' });
    expect(scenario.ledger).toHaveLength(noNewRequests);

    holdComparison = true; await compare.click();
    await expect.poll(() => comparisonRequests().length).toBe(3);
    since = annualRequestCursor(scenario);
    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB');
    held.release(); await scenario.ready('BBB'); await settledDiscovery('BBB', '1');
    await expect(grid).toHaveCount(0); await expect(panel.getByRole('checkbox', { checked: true })).toHaveCount(0);
    await expect(panel).toContainText('Publication version 1');
    await expect.poll(() => rows().rows.filter(r => JSON.parse(r.request)[1] === endpoint('AAA') && JSON.parse(r.request)[2] !== '').map(r => r.state))
      .toEqual(['completed', 'completed', 'cancelled']);
    since = annualRequestCursor(scenario);
    await panel.getByRole('button', { name: 'Refresh reported windows', exact: true }).click();
    await expect(panel.getByRole('status')).toHaveText('Select two to four reported windows.'); await settledDiscovery('BBB', '1');
    await expect(panel.getByRole('checkbox', { checked: true })).toHaveCount(0);
    expect(scenario.violations).toEqual([]);
  } finally {
    const snapshot = rows(), audit = JSON.stringify({ synthetic: true, since, bindingErrors: snapshot.bindingErrors,
      rejectedUnbound: snapshot.rejectedUnbound, violations: scenario.violations,
      rows: snapshot.rows.filter(row => JSON.parse(row.request)[1].endsWith('/financials/quarters')) });
    expect(Buffer.byteLength(audit)).toBeLessThanOrEqual(32768);
    await info.attach('quarter-request-audit', { body: audit, contentType: 'application/json' });
  }
});
