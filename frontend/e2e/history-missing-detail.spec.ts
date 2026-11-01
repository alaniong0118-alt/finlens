import type { Locator, Page, Request, TestInfo } from '@playwright/test';
import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

// Existing synthetic observations only; no source value, date or identity changes.
function missingHistory() {
  const first = data.observation('AAA', 'revenue', 'quarter', 2024);
  const second = data.observation('AAA', 'revenue', 'quarter', 2025);
  first.status = second.status = 'unavailable'; first.value = second.value = null;
  first.reason = 'Synthetic 2024 source bases are incompatible.';
  second.reason = 'Synthetic 2025 compatible input is missing.';
  second.provenance = [];
  second.alternatives = data.observation('AAA', 'revenue', 'annual', 2024).provenance;
  return { ...data.history('AAA', 'revenue', 'quarter'), status: 'unavailable' as const,
    reason: 'Synthetic returned history has no compatible values.', history: [first, second] };
}

type HistoryRequest = { request: Request; method: string; url: string; pin: string | undefined; bodyAbsent: boolean;
  start: number; finished?: number; status?: number; version?: string; failed?: number; error?: string };

// This test only permits the two observed startup cancellations. A
// request's identity and terminal event must bind to its own successful peer.
function checkInitialHistoryRequests(records: HistoryRequest[], boundary: number, violations: string[] = []): string[] {
  if (violations.length) throw new Error('Unbound request lifecycle event');
  const scopes = [
    { path: '/api/finlens/companies/AAA/freshness', pin: undefined },
    { path: '/api/finlens/companies/AAA/financials/annual', pin: '0' },
  ];
  const allowed: string[] = [];
  for (const scope of scopes) {
    const relevant = records.filter(item => new URL(item.url).pathname === scope.path);
    if (relevant.some(item => item.method !== 'GET' || item.pin !== scope.pin || !item.bodyAbsent
        || new URL(item.url).origin !== 'http://127.0.0.1:3107' || new URL(item.url).search !== ''
        || item.start >= boundary)) throw new Error('Unexpected scoped initial request');
    const failed = relevant.filter(item => item.failed !== undefined);
    const completed = relevant.filter(item => item.finished !== undefined);
    if (failed.length > 1 || completed.length !== 1 || relevant.length !== failed.length + 1
        || completed[0].status !== 200 || completed[0].version !== scope.pin
        || completed[0].finished! >= boundary) throw new Error('Invalid initial replacement');
    if (failed.length) {
      const old = failed[0];
      if (old.error !== 'net::ERR_ABORTED' || old.status !== undefined || old.failed! >= boundary
          || old.request === completed[0].request) throw new Error('Unexpected initial cancellation');
      allowed.push(`${old.method} ${scope.path}: ${old.error}`);
    }
  }
  if (records.filter(item => item.failed !== undefined).length !== allowed.length) throw new Error('Unexpected request failure');
  return allowed;
}

function recordHistoryRequests(page: Page) {
  const records: HistoryRequest[] = [], byRequest = new Map<Request, HistoryRequest>();
  const violations: string[] = [];
  const scoped = (request: Request) => {
    const path = new URL(request.url()).pathname;
    return path === '/api/finlens/companies/AAA/freshness'
      || path === '/api/finlens/companies/AAA/financials/annual';
  };
  let sequence = 0;
  page.on('request', request => {
    if (byRequest.has(request)) { violations.push('duplicate request'); return; }
    const row = { request, method: request.method(), url: request.url(), pin: request.headers()['x-finlens-data-version'],
      bodyAbsent: request.postData() === null, start: ++sequence };
    records.push(row); byRequest.set(request, row);
  });
  page.on('response', response => { const request = response.request(), row = byRequest.get(request);
    if (row && row.status === undefined && row.failed === undefined && row.finished === undefined) {
      row.status = response.status(); row.version = response.headers()['x-finlens-data-version'];
    } else if (row || scoped(request)) violations.push('invalid or unbound scoped response'); });
  page.on('requestfinished', request => { const row = byRequest.get(request);
    if (row && row.status !== undefined && row.failed === undefined && row.finished === undefined) row.finished = ++sequence;
    else if (row || scoped(request)) violations.push('invalid or unbound scoped finish'); });
  page.on('requestfailed', request => { const row = byRequest.get(request);
    if (row && row.failed === undefined && row.finished === undefined) { row.failed = ++sequence; row.error = request.failure()?.errorText ?? 'unknown'; }
    else violations.push('unbound request failure'); });
  return { records, violations, boundary: () => ++sequence };
}

function historyRequestAudit(records: HistoryRequest[], violations: string[], boundary: number | null) {
  const rows = records.filter(row => {
    const path = new URL(row.url).pathname;
    return path === '/api/finlens/companies/AAA/freshness' || path === '/api/finlens/companies/AAA/financials/annual';
  }).map(row => {
    const url = new URL(row.url);
    return { method: row.method, url: url.origin + url.pathname, query: url.search.slice(0, 256).replace(/[^\x20-\x7e]/g, '?'),
      pin: row.pin, bodyAbsent: row.bodyAbsent, start: row.start, finished: row.finished,
      status: row.status, version: row.version, failed: row.failed, error: row.error };
  });
  return { boundary, rows, violations };
}

// D10 observation pattern, with explicit per-axis clipping and conservative
// clip-path rejection. Finite coordinates may be negative; sizes may not.
function captureHistoryFocus(element: Element) {
  const style = getComputedStyle(element), rect = element.getBoundingClientRect();
  const width = parseFloat(style.outlineWidth), offset = parseFloat(style.outlineOffset);
  const extent = Math.max(0, width + offset);
  const geometry = (node: Element, box = node.getBoundingClientRect()) => ({
    tag: node.localName.replace(/[^a-z0-9-]/gi, '').slice(0, 16),
    rect: { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height },
    scroll: { left: node.scrollLeft, top: node.scrollTop, width: node.scrollWidth, height: node.scrollHeight },
    client: { left: node.clientLeft, top: node.clientTop, width: node.clientWidth, height: node.clientHeight },
  });
  const knownOverflow = (value: string) => ['visible', 'hidden', 'clip', 'scroll', 'auto', 'overlay'].includes(value);
  const ancestors = [];
  let ancestor = element.parentElement, depth = 0, clippingCount = 0, unknownOverflow = false;
  while (ancestor && depth < 32) {
    const parentStyle = getComputedStyle(ancestor);
    const overflowX = knownOverflow(parentStyle.overflowX) ? parentStyle.overflowX : 'unknown';
    const overflowY = knownOverflow(parentStyle.overflowY) ? parentStyle.overflowY : 'unknown';
    const paintContainment = parentStyle.contain.split(/\s+/).some(value => ['paint', 'strict', 'content'].includes(value));
    const clipPath = parentStyle.clipPath !== 'none';
    unknownOverflow ||= overflowX === 'unknown' || overflowY === 'unknown';
    if (overflowX !== 'visible' || overflowY !== 'visible' || paintContainment || clipPath) {
      clippingCount++;
      if (ancestors.length < 16) {
        const box = geometry(ancestor);
        const clipX = overflowX !== 'visible' || paintContainment;
        const clipY = overflowY !== 'visible' || paintContainment;
        const left = box.rect.left + box.client.left, top = box.rect.top + box.client.top;
        const right = left + box.client.width, bottom = top + box.client.height;
        ancestors.push({ depth, ...box, overflowX, overflowY, paintContainment, clipPath, clipX, clipY,
          overflowCssPixels: {
            left: clipX ? Math.max(0, left - (rect.left - extent)) : 0,
            right: clipX ? Math.max(0, rect.right + extent - right) : 0,
            top: clipY ? Math.max(0, top - (rect.top - extent)) : 0,
            bottom: clipY ? Math.max(0, rect.bottom + extent - bottom) : 0,
          } });
      }
    }
    ancestor = ancestor.parentElement; depth++;
  }
  const focused = geometry(element);
  const validGeometry = (item: ReturnType<typeof geometry>) => [
    ...Object.values(item.rect), ...Object.values(item.scroll), ...Object.values(item.client),
  ].every(Number.isFinite) && item.rect.right >= item.rect.left && item.rect.bottom >= item.rect.top
    && item.rect.width >= 0 && item.rect.height >= 0 && item.scroll.width >= 0 && item.scroll.height >= 0
    && item.client.width >= 0 && item.client.height >= 0 && item.client.left >= 0 && item.client.top >= 0;
  const geometryValid = validGeometry(focused) && ancestors.every(validGeometry)
    && [innerWidth, innerHeight, scrollX, scrollY, width, offset, extent].every(Number.isFinite)
    && innerWidth > 0 && innerHeight > 0 && rect.width > 0 && rect.height > 0 && width > 0;
  const dpr = devicePixelRatio, dprValid = Number.isFinite(dpr) && dpr === 1;
  const overflowCssPixels = { left: Math.max(0, extent - rect.left), right: Math.max(0, rect.right + extent - innerWidth),
    top: Math.max(0, extent - rect.top), bottom: Math.max(0, rect.bottom + extent - innerHeight) };
  const overflowPhysicalPixels = Object.fromEntries(Object.entries(overflowCssPixels).map(([edge, value]) => [edge, value * dpr]));
  const belowRasterTolerance = (values: Record<string, number>) => Object.values(values).every(value => Number.isFinite(value) && value >= 0 && value < 0.5);
  const clipPathSupported = ancestors.every(item => !item.clipPath); // No arbitrary path geometry is inferred.
  const ancestryComplete = ancestor === null && clippingCount <= 16 && !unknownOverflow;
  const clippingContained = ancestryComplete && clipPathSupported && ancestors.every(item =>
    belowRasterTolerance(Object.fromEntries(Object.entries(item.overflowCssPixels).map(([edge, value]) => [edge, value * dpr]))));
  const rasterContained = geometryValid && dprValid && belowRasterTolerance(overflowPhysicalPixels) && clippingContained;
  return { visible: element.matches(':focus-visible'), outline: style.outlineStyle, width, offset, extent,
    strictViewportContained: Object.values(overflowCssPixels).every(value => value === 0),
    strictClippingContained: ancestryComplete && clipPathSupported && ancestors.every(item => Object.values(item.overflowCssPixels).every(value => value === 0)),
    geometryValid, dpr, dprValid, overflowCssPixels, overflowPhysicalPixels, rasterContained,
    clippingContained, clipPathSupported, ancestryComplete, element: focused,
    viewport: { width: innerWidth, height: innerHeight, scrollX, scrollY }, clippingAncestors: ancestors,
    ancestorLimitReached: ancestor !== null, clippingAncestorLimitReached: clippingCount > 16, unknownOverflow };
}

type Evidence = { info: TestInfo; attempts: number };
async function captureFocusEvidence(page: Page, evidence: Evidence, checkpoint: string) {
  const index = evidence.attempts++;
  if (index >= 9) throw new Error('INCOMPLETE_FOCUS_EVIDENCE: nine-pair bound exceeded');
  const errors: string[] = [];
  const name = `${index}-${checkpoint}`;
  try {
    // Viewport capture preserves native focus/scroll, caret and animations.
    const png = await page.screenshot({ type: 'png', fullPage: false, timeout: 3000,
      scale: 'device', animations: 'allow', caret: 'initial' });
    if (png.length === 0 || png.length > 2 * 1024 * 1024) throw new Error('PNG must be nonempty and <=2 MiB');
    await evidence.info.attach(`history-focus-raster-${name}`, { body: png, contentType: 'image/png' });
  } catch (error) { errors.push(`raster: ${String(error).slice(0, 256)}`); }
  let paint: ReturnType<typeof captureHistoryFocus> | null = null;
  try {
    const focus = page.locator(':focus').first();
    const actual = await focus.count() ? focus : page.locator('body');
    paint = await actual.evaluate(captureHistoryFocus);
  } catch (error) { errors.push(`geometry: ${String(error).slice(0, 256)}`); }
  try {
    const json = JSON.stringify({ checkpoint, paint, evidenceComplete: errors.length === 0, errors });
    if (Buffer.byteLength(json) > 32768) throw new Error('JSON exceeds 32 KiB');
    await evidence.info.attach(`history-focus-${name}`, { body: json, contentType: 'application/json' });
  } catch (error) { errors.push(`attachment: ${String(error).slice(0, 256)}`); }
  if (errors.length || !paint) throw new Error(`INCOMPLETE_FOCUS_EVIDENCE: ${errors.join('; ')}`);
  return paint;
}

async function expectKeyboardFocus(target: Locator, evidence: Evidence, checkpoint: string) {
  const paint = await captureFocusEvidence(target.page(), evidence, checkpoint);
  await expect(target).toBeFocused(); await expect(target).toBeVisible();
  expect(paint.visible).toBe(true); expect(paint.outline).not.toBe('none'); expect(paint.width).toBeGreaterThan(0);
  expect(paint.geometryValid).toBe(true); expect(paint.dpr).toBe(1);
  expect(paint.ancestryComplete).toBe(true); expect(paint.clipPathSupported).toBe(true);
  expect(paint.clippingContained).toBe(true); expect(paint.rasterContained).toBe(true);
}

async function tabTo(page: Page, target: Locator, evidence: Evidence, checkpoint: string, maximum = 8) {
  try {
    for (let step = 0; step < maximum; step++) {
      await page.keyboard.press('Tab');
      if (await target.evaluate(element => element === document.activeElement)) {
        await expectKeyboardFocus(target, evidence, checkpoint); return;
      }
    }
  } catch (error) {
    // Includes failed key delivery, detached target and failed focus assertions.
    await captureFocusEvidence(page, evidence, `${checkpoint}-failure`); throw error;
  }
  await captureFocusEvidence(page, evidence, `${checkpoint}-tab-limit`);
  throw new Error(`Native Tab did not reach ${checkpoint}; evidence retained`);
}

async function toggleWithKeyboard(summary: Locator, details: Locator, key: 'Space' | 'Enter', open: boolean, evidence: Evidence, checkpoint: string) {
  try {
    await summary.page().keyboard.press(key);
    if (open) await expect(details).toHaveAttribute('open', '');
    else await expect(details).not.toHaveAttribute('open', '');
    await expect(summary).toBeFocused();
  } catch (error) {
    await captureFocusEvidence(summary.page(), evidence, `${checkpoint}-key-failure`); throw error;
  }
}

async function expectReadableHistorySummary(summary: Locator) {
  const result = await summary.evaluate(element => {
    const cell = element.closest('td');
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const splitWords: string[] = [];
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const text = node.textContent ?? '';
      for (const match of text.matchAll(/\S+/g)) {
        const range = document.createRange();
        range.setStart(node, match.index!); range.setEnd(node, match.index! + match[0].length);
        const lines = new Set(Array.from(range.getClientRects(), rect => rect.top));
        if (lines.size > 1) splitWords.push(match[0]);
      }
    }
    return { cellWidth: cell?.getBoundingClientRect().width ?? 0, splitWords };
  });
  expect(result.cellWidth).toBeGreaterThanOrEqual(220);
  expect(result.splitWords).toEqual([]);
}

for (const width of [1440, 390]) test.describe(`History missing-detail at ${width}px`, () => {
  test.use({ deviceScaleFactor: 1, viewport: { width, height: width === 390 ? 844 : 1000 } });
  test('all-unavailable rows retain evidence and native keyboard focus @desktop-only', async ({ page, scenario }, info) => {
    const body = missingHistory(), evidence = { info, attempts: 0 }, audit = recordHistoryRequests(page);
    let initialBoundary: number | null = null;
    try {
    scenario.overrides.push(request => request.path === '/companies/AAA/financials/metrics/revenue'
      && request.query.get('period') === 'quarter' ? { body, version: '0' } : undefined);
    await scenario.open(); await scenario.ready();
    const history = page.getByRole('region', { name: 'Reported financial trends', exact: true });
    await expect(history.locator('.empty-state')).toContainText(body.reason);
    await expect(history.locator('.financial-chart')).toHaveCount(0);
    const rows = history.locator('tbody tr'); await expect(rows).toHaveCount(2);
    for (const [index, row] of body.history.entries()) {
      await expect(rows.nth(index).locator('td').first()).toContainText(`Jan 1, ${row.period!.fiscal_year} – Mar 31, ${row.period!.fiscal_year}`);
      await expect(rows.nth(index).locator('td').nth(1)).toContainText('Unavailable');
      await expect(rows.nth(index).locator('td').nth(1)).toContainText(row.reason!);
      await expect(rows.nth(index).locator('td').nth(1)).not.toContainText(body.history[1 - index].reason!);
    }
    // Wait for observed initial requests to settle as well as both 200 peers.
    // Cross-request event delivery order does not establish browser start order.
    await expect.poll(() => ['/api/finlens/companies/AAA/freshness', '/api/finlens/companies/AAA/financials/annual']
      .every(path => audit.records.some(row => new URL(row.url).pathname === path
        && row.method === 'GET' && row.pin === (path.endsWith('/annual') ? '0' : undefined)
        && row.status === 200 && row.finished !== undefined)
        && audit.records.filter(row => new URL(row.url).pathname === path)
          .every(row => row.finished !== undefined || row.failed !== undefined)), { timeout: 5000 }).toBe(true);
    initialBoundary = audit.boundary();
    const requests = scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin, query: query.toString() }));
    const table = history.locator('.history-table'), outer = table.locator(':scope > summary');
    await tabTo(page, outer, evidence, 'outer-summary', 80);
    await toggleWithKeyboard(outer, table, 'Space', false, evidence, 'outer-collapse');
    await toggleWithKeyboard(outer, table, 'Enter', true, evidence, 'outer-open');
    const region = table.locator('.table-scroll');
    await tabTo(page, region, evidence, 'table-region');
    await expect(region).toHaveAttribute('aria-describedby', 'history-scroll-help');
    if (width === 390) {
      const before = await region.evaluate(element => ({ left: element.scrollLeft, width: element.scrollWidth, client: element.clientWidth }));
      expect(before.width).toBeGreaterThan(before.client);
      try {
        await page.keyboard.press('ArrowRight');
        await expect.poll(() => region.evaluate(element => element.scrollLeft)).toBeGreaterThan(before.left);
        await expectKeyboardFocus(region, evidence, 'table-region-after-arrow');
      } catch (error) { await captureFocusEvidence(page, evidence, 'table-region-arrow-failure'); throw error; }
    }
    const selected = rows.nth(0).locator('details.provenance'), selectedSummary = selected.locator(':scope > summary');
    await tabTo(page, selectedSummary, evidence, 'selected-summary');
    await expectReadableHistorySummary(selectedSummary);
    await toggleWithKeyboard(selectedSummary, selected, 'Space', true, evidence, 'selected-open');
    await expect(selected.locator('.details-body > .source-record')).toContainText('Jan 1, 2024 – Mar 31, 2024');
    const selectedLink = selected.getByRole('link', { name: 'Open official SEC filing', exact: false });
    await tabTo(page, selectedLink, evidence, 'selected-sec-link');
    const missing = rows.nth(1).locator('details.provenance'), missingSummary = missing.locator(':scope > summary');
    await tabTo(page, missingSummary, evidence, 'missing-summary');
    await toggleWithKeyboard(missingSummary, missing, 'Enter', true, evidence, 'missing-open');
    await expect(missing).toContainText('No compatible source selected for this period.');
    const alternatives = missing.locator('details'), alternativeSummary = alternatives.locator(':scope > summary');
    await tabTo(page, alternativeSummary, evidence, 'alternative-summary');
    await expectReadableHistorySummary(alternativeSummary);
    await toggleWithKeyboard(alternativeSummary, alternatives, 'Space', true, evidence, 'alternatives-open');
    await expect(alternatives.locator('.source-record')).toContainText('Period: Jan 1, 2024 – Dec 31, 2024');
    const alternativeLink = alternatives.getByRole('link', { name: 'SEC source', exact: false });
    await tabTo(page, alternativeLink, evidence, 'alternative-sec-link');
    for (const [link, source] of [[selectedLink, body.history[0].provenance[0]], [alternativeLink, body.history[1].alternatives[0]]] as const) {
      await expect(link).toHaveAttribute('href', source.sec_url);
      await expect(link).toHaveAttribute('target', '_blank'); await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
    const layout = await region.evaluate(element => ({ width: innerWidth, document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth, client: element.clientWidth, scroll: element.scrollWidth }));
    expect(layout.width).toBe(width); expect(layout.document).toBeLessThanOrEqual(width); expect(layout.body).toBeLessThanOrEqual(width);
    expect(evidence.attempts).toBe(width === 390 ? 8 : 7);
    expect(scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin, query: query.toString() }))).toEqual(requests);
    await expect(history.locator('.financial-chart')).toHaveCount(0);
    await expect(history.locator('.empty-state')).toContainText(body.reason);
    expect(scenario.violations).toEqual([]);
    expect(scenario.failures.slice().sort()).toEqual(checkInitialHistoryRequests(audit.records, initialBoundary, audit.violations).sort());
    } finally {
      const data = JSON.stringify(historyRequestAudit(audit.records, audit.violations, initialBoundary));
      if (Buffer.byteLength(data) > 32768) throw new Error('History request audit exceeds 32 KiB');
      await info.attach('history-request-audit', { body: data, contentType: 'application/json' });
    }
  });
});
