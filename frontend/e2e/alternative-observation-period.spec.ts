import type { Locator, Page } from '@playwright/test';
import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

// Test-only overlays reuse the established synthetic issuer, provenance and
// deny-all transport. No shared fixture or application behavior is changed.
function syntheticAlternatives() {
  const source = data.observation('AAA', 'revenue').provenance[0];
  return [
    { ...source, fact_id: 910001, original_concept: `Synthetic_Duration_${'LongConcept'.repeat(12)}`,
      value: '123456789.01234567890123456789', period_start: '2024-04-01', period_end: '2024-06-30',
      sec_url: `${data.secUrl('AAA')}?observation=duration#synthetic` },
    { ...source, fact_id: 910002, original_concept: 'Synthetic_AsOf', value: '-9.876E+8',
      period_start: null, period_end: '2023-09-30', accession_number: data.accession('AAA', '000002'), sec_url: data.secUrl('AAA', '000002') },
    { ...source, fact_id: 910003, original_concept: 'Synthetic_InvalidCalendarDate', value: '0',
      period_start: '2025-02-29', period_end: '2025-03-31', sec_url: `${data.secUrl('AAA')}?observation=invalid` },
    { ...source, fact_id: 910004, original_concept: 'Synthetic_MissingDates', value: '42.0000',
      period_start: undefined, period_end: undefined, sec_url: `${data.secUrl('AAA')}?observation=missing` },
  ];
}

// Serialized into the page. Observation only: no focus, scroll, DOM text, URLs,
// attributes or arbitrary CSS values. Bounds keep every attachment below 32 KiB.
function captureAlternativeFocus(element: Element) {
  const style = getComputedStyle(element), rect = element.getBoundingClientRect();
  const extent = parseFloat(style.outlineWidth) + Math.max(0, parseFloat(style.outlineOffset));
  const geometry = (node: Element, box = node.getBoundingClientRect()) => {
    return { tag: node.localName.replace(/[^a-z0-9-]/gi, '').slice(0, 16),
      rect: { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height },
      scroll: { left: node.scrollLeft, top: node.scrollTop, width: node.scrollWidth, height: node.scrollHeight },
      client: { left: node.clientLeft, top: node.clientTop, width: node.clientWidth, height: node.clientHeight } };
  };
  const overflow = (value: string) => ['visible', 'hidden', 'clip', 'scroll', 'auto', 'overlay'].includes(value) ? value : 'unknown';
  const ancestors = [];
  let ancestor = element.parentElement, depth = 0, clippingCount = 0;
  while (ancestor && depth < 32) {
    const parentStyle = getComputedStyle(ancestor);
    const overflowX = overflow(parentStyle.overflowX), overflowY = overflow(parentStyle.overflowY);
    const paintContainment = parentStyle.contain.split(/\s+/).some(value => ['paint', 'strict', 'content'].includes(value));
    const clipPath = parentStyle.clipPath !== 'none';
    if (overflowX !== 'visible' || overflowY !== 'visible' || paintContainment || clipPath) {
      clippingCount++;
      if (ancestors.length < 16) ancestors.push({ depth, ...geometry(ancestor), overflowX, overflowY, paintContainment, clipPath });
    }
    ancestor = ancestor.parentElement; depth++;
  }
  const focusedGeometry = geometry(element, rect);
  const validGeometry = (item: ReturnType<typeof geometry>) => [
    ...Object.values(item.rect), ...Object.values(item.scroll), ...Object.values(item.client),
  ].every(Number.isFinite) && item.rect.right >= item.rect.left && item.rect.bottom >= item.rect.top
    && item.rect.width >= 0 && item.rect.height >= 0 && item.scroll.width >= 0 && item.scroll.height >= 0
    && item.client.width >= 0 && item.client.height >= 0;
  const geometryValid = validGeometry(focusedGeometry) && ancestors.every(validGeometry)
    && [innerWidth, innerHeight, scrollX, scrollY, parseFloat(style.outlineWidth), parseFloat(style.outlineOffset), extent].every(Number.isFinite)
    && innerWidth > 0 && innerHeight > 0 && rect.width > 0 && rect.height > 0 && parseFloat(style.outlineWidth) > 0;
  const dpr = devicePixelRatio, dprValid = Number.isFinite(dpr) && dpr === 1;
  const overflowCssPixels = { left: Math.max(0, extent - rect.left), right: Math.max(0, rect.right + extent - innerWidth),
    top: Math.max(0, extent - rect.top), bottom: Math.max(0, rect.bottom + extent - innerHeight) };
  const overflowPhysicalPixels = { left: overflowCssPixels.left * dpr, right: overflowCssPixels.right * dpr,
    top: overflowCssPixels.top * dpr, bottom: overflowCssPixels.bottom * dpr };
  const rasterContained = geometryValid && dprValid
    && Object.values(overflowPhysicalPixels).every(value => Number.isFinite(value) && value >= 0 && value < 0.5);
  return { visible: element.matches(':focus-visible'), outline: style.outlineStyle,
    width: parseFloat(style.outlineWidth), offset: parseFloat(style.outlineOffset), extent,
    contained: rect.left - extent >= 0 && rect.right + extent <= innerWidth
      && rect.top - extent >= 0 && rect.bottom + extent <= innerHeight,
    dpr, dprValid, geometryValid, overflowCssPixels, overflowPhysicalPixels, rasterContained,
    element: focusedGeometry, viewport: { width: innerWidth, height: innerHeight, scrollX, scrollY },
    clippingAncestors: ancestors, ancestorLimitReached: ancestor !== null, clippingAncestorLimitReached: clippingCount > 16 };
}

async function expectKeyboardFocus(target: Locator) {
  const info = test.info();
  const rasterIndex = info.attachments.filter(attachment => attachment.name.startsWith('d10-focus-raster-')).length;
  if (rasterIndex >= 7) throw new Error('D10 focus raster limit exceeded: seven existing focus points per case');
  // Page viewport capture avoids locator screenshot auto-scrolling. Keep native
  // focus, caret and animations intact, and retain pixels even if assertions fail.
  const raster = await target.page().screenshot({ type: 'png', fullPage: false, timeout: 3000,
    scale: 'device', animations: 'allow', caret: 'initial' });
  if (raster.length === 0 || raster.length > 2 * 1024 * 1024) throw new Error('D10 focus raster must be nonempty and at most 2 MiB');
  await info.attach(`d10-focus-raster-${rasterIndex}`, { body: raster, contentType: 'image/png' });
  await expect(target).toBeFocused();
  await expect(target).toBeVisible();
  const paint = await target.evaluate(captureAlternativeFocus);
  const diagnostic = JSON.stringify(paint);
  if (Buffer.byteLength(diagnostic) > 32768) throw new Error('Bounded D10 focus diagnostic exceeded 32 KiB');
  await test.info().attach(`d10-focus-${test.info().attachments.length}`, { body: diagnostic, contentType: 'application/json' });
  expect(paint.visible, JSON.stringify(paint)).toBe(true);
  expect(paint.outline).not.toBe('none'); expect(paint.width).toBeGreaterThan(0);
  expect(paint.dpr).toBe(1);
  expect(paint.rasterContained, diagnostic).toBe(true);
}

async function tabTo(page: Page, target: Locator, maximum = 80) {
  for (let step = 0; step < maximum; step++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate(element => element === document.activeElement)) {
      await expectKeyboardFocus(target); return;
    }
  }
  throw new Error('Native Tab did not reach the expected provenance control');
}

for (const width of [1440, 390]) test.describe(`D10 alternatives at ${width}px`, () => {
  // Both cases use the existing desktop project, so mobile project registration
  // and all earlier specs stay unchanged. The narrow case tests actual CSS wrap.
  test.use({ deviceScaleFactor: 1, viewport: { width, height: width === 390 ? 844 : 1000 } });
  test('own duration, as-of and unknown dates; native keyboard and source links @desktop-only', async ({ page, scenario }, info) => {
    const alternatives = syntheticAlternatives();
    scenario.overrides.push(request => {
      if (request.path !== '/companies/AAA/financials/summary' || request.query.get('period') !== 'quarter') return;
      const body = data.summary('AAA');
      return { body: { ...body, metrics: { ...body.metrics, revenue: { ...body.metrics.revenue, alternatives } } } };
    });
    await scenario.open(); await scenario.ready();
    const requests = scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin, query: query.toString() }));
    const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
    const revenue = snapshot.locator('.metric-card').filter({ has: page.getByRole('heading', { name: 'Revenue', exact: true }) });
    await expect(revenue.locator('.metric-value')).toHaveText('$1B');
    await expect(revenue.locator('.metric-period')).toContainText('Jan 1, 2025 – Mar 31, 2025');
    const provenance = revenue.locator('details.provenance');
    const outer = provenance.locator(':scope > summary');
    await tabTo(page, outer); await page.keyboard.press('Space');
    await expect(provenance).toHaveAttribute('open', '');
    const selectedSource = provenance.locator('.details-body > .source-record');
    await expect(selectedSource).toContainText('Jan 1, 2025 – Mar 31, 2025');
    const disclosure = provenance.locator('details');
    const toggle = disclosure.locator(':scope > summary');
    await expect(toggle).toHaveText('4 alternative source observations');
    await tabTo(page, toggle, 4); await page.keyboard.press('Space');
    await expect(disclosure).toHaveAttribute('open', '');
    const rows = disclosure.locator('.source-record');
    await expect(rows).toHaveCount(4);
    const labels = ['Period: Apr 1, 2024 – Jun 30, 2024', 'As of Sep 30, 2023', 'Period unknown', 'Period unknown'];
    for (const [index, source] of alternatives.entries()) {
      const row = rows.nth(index);
      await expect(row).toHaveText(`${source.original_concept} · ${source.value} ${source.unit} · ${labels[index]} · 10-K · Filed Feb 1, 2026 · ${source.accession_number} · SEC source ↗`);
      await expect(row).not.toContainText(/Jan 1, 2025|Mar 31, 2025|amendment|conflict|Invalid Date/);
      const link = row.getByRole('link', { name: 'SEC source ↗', exact: true });
      await expect(link).toHaveAttribute('href', source.sec_url);
      await expect(link).toHaveAttribute('target', '_blank');
      await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
      // Actual Tab reaches each source in supplied order. Never navigate to SEC.
      await page.keyboard.press('Tab'); await expectKeyboardFocus(link);
    }
    const geometry = await rows.first().evaluate(element => {
      const range = document.createRange(); range.selectNodeContents(element);
      return { lines: range.getClientRects().length, width: innerWidth,
        documentWidth: document.documentElement.scrollWidth, bodyWidth: document.body.scrollWidth,
        horizontalOverflow: element.scrollWidth > element.clientWidth };
    });
    expect(geometry.width).toBe(width);
    expect(geometry.documentWidth).toBeLessThanOrEqual(width);
    expect(geometry.bodyWidth).toBeLessThanOrEqual(width);
    expect(geometry.horizontalOverflow).toBe(false);
    if (width === 390) expect(geometry.lines).toBeGreaterThan(2);
    await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Shift+Tab');
    await expectKeyboardFocus(toggle); await page.keyboard.press('Space');
    await expect(disclosure).not.toHaveAttribute('open');
    expect(scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin, query: query.toString() }))).toEqual(requests);
    await info.attach('d10-synthetic-outcomes', { contentType: 'application/json', body: JSON.stringify({
      synthetic: true, width, labels, geometry, sourceUrls: alternatives.map(source => source.sec_url), requests,
    }, null, 2) });
  });
});
