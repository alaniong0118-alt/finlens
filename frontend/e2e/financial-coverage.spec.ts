import type { Locator } from '@playwright/test';
import { test, expect, lifecycle, replayCancellations, annualRequestCursor, assessFocusPaint } from './fixtures/annual-period-browser';
import * as data from './fixtures/data';

test.use({ deviceScaleFactor: 1 });

// Exact accepted quarter focus oracle; no test scrolling or alternate tolerance.
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


test('stored coverage: explicit requests, source keyboard and stale isolation', async ({ page, scenario }, info) => {
  scenario.versions.BBB = 1;
  const endpoint = (ticker: string) => `/companies/${ticker}/financials/coverage`;
  await scenario.ignoreTransportAbort(endpoint('BBB'));
  let holdAlpha = false;
  const alpha = scenario.hold(request => holdAlpha && request.path === endpoint('AAA'));
  const beta = scenario.hold(request => request.path === endpoint('BBB'));
  const panel = page.getByRole('region', { name: 'Financial coverage map', exact: true });
  const grid = panel.getByRole('region', { name: 'Stored financial coverage matrix', exact: true });
  const load = panel.getByRole('button', { name: 'Load stored coverage', exact: true });
  const kind = panel.getByRole('combobox', { name: 'Coverage period type', exact: true });
  const coverageRequests = () => scenario.ledger.filter(request => request.path.endsWith('/financials/coverage'));
  const snapshot = () => lifecycle(scenario, [...replayCancellations('AAA', 0), ...replayCancellations('BBB', 1)]);
  const coverageRows = () => snapshot().rows.filter(row => JSON.parse(row.request)[1].endsWith('/financials/coverage'));
  async function completed(count: number) {
    await expect.poll(() => coverageRows().filter(row => row.state === 'completed').length).toBe(count);
  }
  try {
    await scenario.open(); await scenario.ready();
    await expect(panel).toContainText('Publication version 0');
    await expect(panel).toContainText('No acquisition starts here.');
    expect(coverageRequests()).toHaveLength(0); expect(coverageRows()).toHaveLength(0);
    await kind.selectOption('quarter'); await kind.selectOption('annual');
    expect(coverageRequests()).toHaveLength(0); await expect(grid).toHaveCount(0);
    await load.click(); await expect(grid.locator('tbody > tr')).toHaveCount(2); await completed(1);
    expect(coverageRequests()).toHaveLength(1);
    expect(coverageRequests()[0].pin).toBe('0'); expect(coverageRequests()[0].query.toString()).toBe('period=annual');
    await expect(grid.locator('thead th')).toHaveCount(12);
    await expect(grid).toContainText('Jan 1, 2025 – Dec 31, 2025');
    await expect(grid).toContainText('Feb 5, 2025 – Dec 31, 2025');
    await expect(grid).toContainText('Synthetic industry exclusion for this observation.');
    await expect(grid).toContainText('Synthetic compatible direct-period operands are missing.');
    const cells = grid.locator('tbody > tr').first().locator('td');
    await expect(cells.nth(6).locator(':scope > p').first()).toHaveText('Available');
    await expect(cells.nth(1).locator(':scope > p').first()).toHaveText('Unavailable');
    await expect(cells.nth(10).locator(':scope > p').first()).toHaveText('Not applicable');
    const noExtra = scenario.ledger.length;
    async function capture(control: Locator, name: string, region = false) {
      await expect(control).toBeFocused();
      const geometry = await control.evaluate(focusGeometry);
      const contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
      await info.attach(`coverage-${name}-geometry`, { body: JSON.stringify({ geometry, contrast }), contentType: 'application/json' });
      await info.attach(`coverage-${name}`, { body: await page.screenshot(), contentType: 'image/png' });
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
        // An expanded matrix can be taller than the viewport. Its
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

    await panel.getByRole('button', { name: 'Clear coverage', exact: true }).focus();
    await page.keyboard.press('Tab'); await capture(grid, 'region', true);
    await page.keyboard.press('ArrowRight');
    const details = cells.first().locator('details.provenance'), toggle = details.locator(':scope > summary');
    await page.keyboard.press('Tab'); await capture(toggle, 'summary'); await page.keyboard.press('Space');
    const source = details.getByRole('link', { name: 'Open official SEC filing ↗', exact: true });
    await page.keyboard.press('Tab'); await capture(source, 'source');
    await expect(source).toHaveAttribute('href', data.secUrl('AAA'));
    const alternatives = details.locator('details'), alternativeToggle = alternatives.locator(':scope > summary');
    await page.keyboard.press('Tab'); await capture(alternativeToggle, 'alternative-summary'); await page.keyboard.press('Space');
    await page.keyboard.press('Tab'); await capture(alternatives.getByRole('link', { name: 'SEC source ↗', exact: true }), 'alternative-source');
    const fcf = cells.nth(6).locator('details.provenance'), fcfToggle = fcf.locator(':scope > summary');
    // Reach the far column through actual keyboard order and product reveal behavior.
    let steps = 0;
    while (!await fcfToggle.evaluate(element => element === document.activeElement) && steps++ < 16) await page.keyboard.press('Tab');
    await capture(fcfToggle, 'fcf-summary'); await page.keyboard.press('Space');
    await expect(fcf).toContainText('operating cash flow: 1000000000 USD');
    await expect(fcf).toContainText('capital expenditures: 1000000000 USD');
    await expect(fcf).toContainText('Exact API value: 0 USD');
    await page.keyboard.press('Tab'); await capture(fcf.getByRole('link', { name: 'Open official SEC filing ↗', exact: true }).first(), 'fcf-source');
    const readable = await fcf.evaluate(element => {
      const s = getComputedStyle(element);
      return { width: element.getBoundingClientRect().width, scroll: element.scrollWidth, client: element.clientWidth,
        wordBreak: s.wordBreak, page: document.documentElement.scrollWidth, viewport: innerWidth };
    });
    // Existing 200px cells have 16px padding per side on desktop (12px narrow).
    // Preserve that layout; test the actual content box and absence of clipping.
    expect(readable.width).toBeGreaterThanOrEqual(168); expect(readable.scroll).toBeLessThanOrEqual(readable.client + 1);
    expect(readable.wordBreak).not.toBe('break-all'); expect(readable.page).toBeLessThanOrEqual(readable.viewport);
    await info.attach('coverage-grid', { body: await page.screenshot(), contentType: 'image/png' });
    expect(scenario.ledger).toHaveLength(noExtra);
    await load.click(); await expect(grid.locator('tbody > tr')).toHaveCount(2); await completed(2);
    expect(coverageRequests()).toHaveLength(2);
    const clear = panel.getByRole('button', { name: 'Clear coverage', exact: true });
    await clear.click(); await expect(grid).toHaveCount(0); await expect(clear).toBeFocused();
    expect(coverageRequests()).toHaveLength(2);
    await kind.selectOption('quarter'); await expect(grid).toHaveCount(0); expect(coverageRequests()).toHaveLength(2);
    await load.click(); await expect(grid.locator('tbody > tr')).toHaveCount(4); await completed(3);
    await expect(grid).toContainText('Jan 16, 2025 – Mar 31, 2025'); await expect(grid).toContainText('Jan 1, 2025 – Mar 31, 2025');
    expect(coverageRequests()).toHaveLength(3);
    holdAlpha = true; await load.click();
    await expect.poll(() => coverageRequests().length).toBe(4); await expect(grid).toHaveCount(0);
    await panel.getByRole('button', { name: 'Cancel coverage request', exact: true }).click();
    await expect(panel.getByRole('status')).toContainText('cancelled');
    await expect.poll(() => coverageRows().filter(row => row.state === 'cancelled').length).toBe(1);
    holdAlpha = false; alpha.release();
    await load.click(); await expect(grid.locator('tbody > tr')).toHaveCount(4); await completed(4);
    expect(coverageRequests()).toHaveLength(5);
    annualRequestCursor(scenario);
    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB');
    await expect(grid).toHaveCount(0); await scenario.ready('BBB');
    await expect(panel).toContainText('Publication version 1'); expect(coverageRequests()).toHaveLength(5);
    await kind.selectOption('annual'); expect(coverageRequests()).toHaveLength(5); await load.click();
    await expect.poll(() => coverageRequests().length).toBe(6);
    expect(coverageRequests()[5].pin).toBe('1');
    annualRequestCursor(scenario);
    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('AAA');
    await expect(grid).toHaveCount(0); await scenario.ready();
    beta.release();
    await expect.poll(() => scenario.abortedDeliveries(endpoint('BBB'), '1', 200, '?period=annual')).toBe(1);
    await completed(5); await expect(grid).toHaveCount(0); await expect(panel).toContainText('Publication version 0');
    expect(coverageRequests()).toHaveLength(6);
    await load.click(); await expect(grid.locator('tbody > tr')).toHaveCount(2); await completed(6);
    expect(coverageRequests()).toHaveLength(7);
    const result = snapshot(), observed = coverageRows();
    expect(result.bindingErrors).toEqual([]); expect(result.rejectedUnbound).toEqual([]);
    expect(observed).toHaveLength(7);
    expect(observed.map(row => row.state)).toEqual(['completed', 'completed', 'completed', 'cancelled', 'completed', 'completed', 'completed']);
    const expected = [
      ['AAA', '0', 'annual'], ['AAA', '0', 'annual'], ['AAA', '0', 'quarter'], ['AAA', '0', 'quarter'],
      ['AAA', '0', 'quarter'], ['BBB', '1', 'annual'], ['AAA', '0', 'annual'],
    ];
    for (const [index, row] of observed.entries()) {
      const [ticker, pin, period] = expected[index];
      expect(row.request).toBe(JSON.stringify(['GET', endpoint(ticker), `period=${period}`, pin, null]));
      expect(row.routed).toBe(true); expect(row.bodyAbsent).toBe(true);
      if (row.state === 'completed') expect(row.response).toEqual({ status: 200, version: pin, code: null });
      else { expect(row.response).toBeNull(); expect(row.error).toBe('net::ERR_ABORTED'); }
    }
    expect(scenario.violations).toEqual([]);
  } finally {
    const result = snapshot(), audit = JSON.stringify({ synthetic: true, rows: coverageRows(),
      bindingErrors: result.bindingErrors, rejectedUnbound: result.rejectedUnbound, violations: scenario.violations });
    expect(Buffer.byteLength(audit)).toBeLessThanOrEqual(32768);
    await info.attach('coverage-request-audit', { body: audit, contentType: 'application/json' });
  }
});
