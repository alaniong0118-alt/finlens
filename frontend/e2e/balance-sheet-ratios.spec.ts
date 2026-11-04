import type { Locator, Page, TestInfo } from '@playwright/test';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { test, expect, lifecycle, annualRequestCursor, expectedRequest, completedRequests,
  publicationCompletions, publicationHeaderCancellations, replayCancellations,
  captureFocusPaint, assessFocusPaint, type ExpectedLedger } from './fixtures/annual-period-browser';
import type { Scenario } from './fixtures/browser';
import { supportsInsightsPublication } from './fixtures/financial-insights-browser';
import * as data from './fixtures/data';
import { balanceSheetRatios } from '../lib/balance-sheet-ratios';
import fixtures from './fixtures/balance-sheet-ratios.json';

// PNG is already bundled in the pinned Playwright dependency; no package install.
const decoderRequire = createRequire(join(process.cwd(), 'package.json'));
const decoderPackage = decoderRequire.resolve('playwright-core/package.json');
if ((decoderRequire(decoderPackage) as { version: string }).version !== '1.64.0') throw new Error('Unreviewed PNG decoder version');
const { PNG } = decoderRequire(join(dirname(decoderPackage), 'lib/utilsBundle.js')) as {
  PNG: { sync: { read: (bytes: Buffer) => { width: number; height: number; data: Buffer } } };
};

test.use({ deviceScaleFactor: 1 });

type Ledger = ExpectedLedger & { phases: { after: number; native: string[] }[] };
function ledger(publicationState: { evidence_version: number }, capabilityPending = false): Ledger {
  // ResearchFreshness reconciles the catalog once for the first nonzero evidence publication.
  // Facts-only publication changes do not trigger this additional unpinned GET.
  return { completed: completedRequests([expectedRequest('/companies'),
    ...(publicationState.evidence_version > 0 ? [expectedRequest('/companies')] : []),
    ...(!capabilityPending ? [expectedRequest('/capabilities')] : [])]),
    pending: capabilityPending ? [expectedRequest('/capabilities')] : [], cancelled: [], cancelledAfterHeaders: [], phases: [] };
}
function publication(expected: Ledger, ticker: string, pin: number, period = 'quarter') {
  expected.completed.push(...publicationCompletions(ticker, pin).filter(row => !JSON.parse(row.request)[1].endsWith('/sources'))
    .map(row => JSON.parse(row.request)[1].endsWith('/financials/summary')
      ? { ...row, request: expectedRequest(`/companies/${ticker}/financials/summary`, pin, `period=${period}`) } : row));
  expected.cancelledAfterHeaders.push(...publicationHeaderCancellations(ticker, pin));
}
function phase(scenario: Scenario, expected: Ledger, ticker: string, pin: number, initial = false, freshness = true) {
  expected.phases.push({ after: initial ? 0 : annualRequestCursor(scenario), native: replayCancellations(ticker, pin, freshness) });
}
// Keep the existing observed-request-first recorder. Only the three exact
// declared startup replay signatures may have zero/one headerless cancellation
// per phase, paired with a distinct successful same-generation request.
async function exactLedger(scenario: Scenario, expected: Ledger) {
  const intended = [
    ...expected.completed.map(row => JSON.stringify([row.request, 'completed', { status: row.status, version: row.version, code: row.code }, null])),
    ...expected.cancelledAfterHeaders.map(row => JSON.stringify([row.request, 'cancelled', { status: row.status, version: row.version, code: row.code }, 'net::ERR_ABORTED'])),
    ...expected.pending.map(request => JSON.stringify([request, 'pending', null, null])),
  ].sort();
  await expect.poll(() => {
    const snapshot = lifecycle(scenario, expected.phases.flatMap(item => item.native)), errors: string[] = [], seen = new Set<string>();
    const native = snapshot.rows.filter(row => row.state === 'cancelled' && row.response === null);
    for (const row of native) {
      const owner = expected.phases.findLast(item => row.id > item.after), key = `${owner?.after}:${row.request}`;
      const peers = snapshot.rows.filter(candidate => candidate.generation === row.generation && candidate.request === row.request);
      const other = peers.find(candidate => candidate.id !== row.id), pin = JSON.parse(row.request)[3];
      if (!owner?.native.includes(row.request) || seen.has(key) || !row.bodyAbsent || row.error !== 'net::ERR_ABORTED'
        || peers.length !== 2 || !other?.routed || !other.bodyAbsent || other.state !== 'completed'
        || other.response?.status !== 200 || other.response.version !== pin || other.response.code !== null || other.error !== null) errors.push(`Invalid replay ${row.id}`);
      seen.add(key);
    }
    return { binding: snapshot.bindingErrors, unbound: snapshot.rejectedUnbound, errors,
      rows: snapshot.rows.filter(row => !native.includes(row)).map(row => JSON.stringify([row.request, row.state, row.response, row.error])).sort(),
      violations: scenario.violations };
  }).toEqual({ binding: [], unbound: [], errors: [], rows: intended, violations: [] });
}

function assessOutlinePixels(bytes: Buffer, geometry: ReturnType<typeof captureFocusPaint>,
  visibility: { dpr: number; viewportWidth: number; viewportHeight: number; radii: string[] }) {
  const refuse = (reason: string) => ({ valid: false, reason, bands: [] as { side: string; pixels: number; matched: number }[] });
  if (visibility.dpr !== 1 || !Number.isInteger(visibility.viewportWidth) || !Number.isInteger(visibility.viewportHeight)
    || visibility.viewportWidth < 1 || visibility.viewportHeight < 1 || visibility.viewportWidth > 2048 || visibility.viewportHeight > 1600) return refuse('INVALID_SCALE_OR_VIEWPORT');
  if (bytes.length < 24 || bytes.length > 8 * 1024 * 1024 || bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a'
    || bytes.readUInt32BE(16) !== visibility.viewportWidth || bytes.readUInt32BE(20) !== visibility.viewportHeight) return refuse('PNG_DIMENSIONS_OR_FORMAT');
  const { rect, width, offset, extent } = geometry;
  if (![...Object.values(rect), width, offset, extent].every(Number.isFinite) || width < 3 || width > 12 || offset < 0
    || extent !== width + offset || rect.right <= rect.left || rect.bottom <= rect.top
    || rect.left - extent < 0 || rect.right + extent > visibility.viewportWidth
    || rect.top - extent < 0 || rect.bottom + extent > visibility.viewportHeight) return refuse('INVALID_OUTLINE_COORDINATES');
  const rgb = /^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/.exec(geometry.outlineColor)?.slice(1).map(Number);
  if (!rgb || rgb.some(channel => channel > 255)) return refuse('UNSUPPORTED_OUTLINE_COLOR');
  if (visibility.radii.length !== 4 || visibility.radii.some(radius => !/^\d+(?:\.\d+)?px$/.test(radius))) return refuse('UNSUPPORTED_CORNER_RADIUS');
  const corner = Math.ceil(Math.max(...visibility.radii.map(parseFloat)) + extent + 1);
  const xStart = Math.ceil(rect.left + corner), xEnd = Math.floor(rect.right - corner);
  const yStart = Math.ceil(rect.top + corner), yEnd = Math.floor(rect.bottom - corner);
  if (xEnd - xStart < 8 || yEnd - yStart < 8) return refuse('NO_BOUNDED_STRAIGHT_OUTLINE');
  let image: { width: number; height: number; data: Buffer };
  try { image = PNG.sync.read(bytes); } catch { return refuse('PNG_DECODE_FAILED'); }
  if (image.width !== visibility.viewportWidth || image.height !== visibility.viewportHeight
    || image.data.length !== image.width * image.height * 4) return refuse('DECODED_DIMENSIONS_OR_SCALE');
  const distance = offset + width / 2;
  const edges = [
    { side: 'left', horizontal: false, center: rect.left - distance, start: yStart, end: yEnd },
    { side: 'right', horizontal: false, center: rect.right + distance, start: yStart, end: yEnd },
    { side: 'top', horizontal: true, center: rect.top - distance, start: xStart, end: xEnd },
    { side: 'bottom', horizontal: true, center: rect.bottom + distance, start: xStart, end: xEnd },
  ];
  const bands = edges.map(edge => {
    let pixels = 0, matched = 0;
    // Two adjacent physical rows/columns around the band center, continuous
    // between the rounded corners. Every sampled pixel must be outline paint.
    const first = Math.floor(edge.center - 0.5);
    for (let normal = first; normal <= first + 1; normal++) for (let along = edge.start; along < edge.end; along++) {
      const x = edge.horizontal ? along : normal, y = edge.horizontal ? normal : along;
      pixels++;
      if (x < 0 || y < 0 || x >= image.width || y >= image.height) continue;
      const at = (y * image.width + x) * 4;
      if (rgb.every((channel, index) => image.data[at + index] === channel) && image.data[at + 3] === 255) matched++;
    }
    return { side: edge.side, pixels, matched };
  });
  return { valid: bands.every(band => band.pixels >= 16 && band.matched === band.pixels),
    reason: bands.every(band => band.matched === band.pixels) ? null : 'OUTLINE_PAINT_MISSING_OR_COVERED', bands };
}

async function capture(control: Locator, name: string, page: Page, info: TestInfo) {
  await expect(control).toBeFocused();
  const geometry = await control.evaluate(captureFocusPaint);
  const visibility = await control.evaluate((element, points) => {
    const r = element.getBoundingClientRect(), style = getComputedStyle(element), ancestors = [];
    for (let node = element.parentElement; node; node = node.parentElement) {
      const s = getComputedStyle(node), b = node.getBoundingClientRect();
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') ancestors.push({
        left: b.left + node.clientLeft, right: b.left + node.clientLeft + node.clientWidth,
        top: b.top + node.clientTop, bottom: b.top + node.clientTop + node.clientHeight,
        x: s.overflowX !== 'visible', y: s.overflowY !== 'visible' });
    }
    const hit = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
    return { dpr: devicePixelRatio, height: r.height, pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth, viewportHeight: innerHeight,
      radii: [style.borderTopLeftRadius, style.borderTopRightRadius, style.borderBottomLeftRadius, style.borderBottomRightRadius],
      center: !!hit && (hit === element || element.contains(hit)), ancestors,
      perimeter: points.every(point => !!document.elementFromPoint(point.x, point.y)?.contains(element)) };
  }, geometry.surfaces);
  const contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  const screenshot = await page.screenshot(), pixels = assessOutlinePixels(screenshot, geometry, visibility);
  await info.attach(`${name}-geometry`, { body: JSON.stringify({ geometry, visibility, contrast, pixels }), contentType: 'application/json' });
  await info.attach(name, { body: screenshot, contentType: 'image/png' });
  // elementFromPoint ancestry remains diagnostic: transparent siblings can be
  // hit targets without covering the outline actually painted above them.
  expect(visibility.dpr).toBe(1); expect(visibility.center).toBe(true);
  expect(visibility.height).toBeGreaterThanOrEqual(44); expect(visibility.pageWidth).toBeLessThanOrEqual(visibility.viewportWidth);
  expect(geometry.offset).toBeGreaterThanOrEqual(0); expect(geometry.width).toBeGreaterThanOrEqual(3);
  expect(geometry.visible).toBe(true); expect(geometry.outline).not.toBe('none'); expect(contrast.sufficient).toBe(true);
  const box = { left: geometry.rect.left - geometry.extent, right: geometry.rect.right + geometry.extent,
    top: geometry.rect.top - geometry.extent, bottom: geometry.rect.bottom + geometry.extent };
  for (const number of [...Object.values(box), ...Object.values(geometry.clip)]) expect(Number.isFinite(number)).toBe(true);
  expect(box.left).toBeGreaterThan(geometry.clip.left - 0.5); expect(box.right).toBeLessThan(geometry.clip.right + 0.5);
  expect(box.top).toBeGreaterThan(geometry.clip.top - 0.5); expect(box.bottom).toBeLessThan(geometry.clip.bottom + 0.5);
  for (const ancestor of visibility.ancestors) {
    if (ancestor.x) { expect(box.left).toBeGreaterThan(ancestor.left - 0.5); expect(box.right).toBeLessThan(ancestor.right + 0.5); }
    if (ancestor.y) { expect(box.top).toBeGreaterThan(ancestor.top - 0.5); expect(box.bottom).toBeLessThan(ancestor.bottom + 0.5); }
  }
  expect(pixels.valid).toBe(true);
}

async function tabTo(page: Page, target: Locator) {
  for (let step = 0; step < 64; step++) {
    if (await target.evaluate(element => document.activeElement === element)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('Keyboard did not reach the intended native control within 64 tabs');
}

// Read-only geometry and text-interior exposure evidence, not decorative corners.
// Individual targets must still fit their complete viewport/ancestor clip.
function readableAnswerPaint(element: Element) {
  const r = element.getBoundingClientRect(), style = getComputedStyle(element);
  const viewport = { left: visualViewport?.offsetLeft ?? 0, top: visualViewport?.offsetTop ?? 0,
    right: (visualViewport?.offsetLeft ?? 0) + (visualViewport?.width ?? innerWidth),
    bottom: (visualViewport?.offsetTop ?? 0) + (visualViewport?.height ?? innerHeight) };
  const clip = { ...viewport };
  let painted = style.display !== 'none' && style.visibility === 'visible';
  for (let node: Element | null = element; node; node = node.parentElement) {
    const s = getComputedStyle(node), b = node.getBoundingClientRect();
    painted &&= s.visibility === 'visible' && s.display !== 'none' && s.opacity === '1';
    if (node !== element && s.overflowX !== 'visible') {
      clip.left = Math.max(clip.left, b.left + node.clientLeft);
      clip.right = Math.min(clip.right, b.left + node.clientLeft + node.clientWidth);
    }
    if (node !== element && s.overflowY !== 'visible') {
      clip.top = Math.max(clip.top, b.top + node.clientTop);
      clip.bottom = Math.min(clip.bottom, b.top + node.clientTop + node.clientHeight);
    }
  }
  const rect = { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  const font = parseFloat(style.fontSize);
  const finite = [...Object.values(rect), ...Object.values(clip), font].every(Number.isFinite);
  const contained = finite && r.width > 0 && r.height > 0 && r.right > r.left && r.bottom > r.top
    && Math.abs(r.right - r.left - r.width) < 0.01 && Math.abs(r.bottom - r.top - r.height) < 0.01
    && r.left >= clip.left && r.right <= clip.right
    && r.top >= clip.top && r.bottom <= clip.bottom;
  const textRects: typeof rect[] = [], probes: { line: number; x: number; y: number;
    hit: { tag: string; role: string | null; classes: string | null } | null;
    ownership: 'self' | 'descendant' | 'outside' | 'none'; owned: boolean }[] = [];
  let probeError: string | null = null, visitedTextNodes = 0;
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) {
    if (++visitedTextNodes > 32) { probeError = 'TEXT_NODE_LIMIT'; break; }
    if (!text.textContent?.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(text);
    const boxes = range.getClientRects();
    if (textRects.length + boxes.length > 64) { probeError = 'TEXT_RECT_LIMIT'; break; }
    for (const box of Array.from(boxes)) textRects.push({ left: box.left, right: box.right, top: box.top,
      bottom: box.bottom, width: box.width, height: box.height });
  }
  if (!probeError && !textRects.length) probeError = 'NO_TEXT_RECTS';
  for (const [line, box] of textRects.entries()) {
    if (![...Object.values(box)].every(Number.isFinite) || box.width <= 0 || box.height <= 0
      || Math.abs(box.right - box.left - box.width) >= 0.01 || Math.abs(box.bottom - box.top - box.height) >= 0.01
      || box.left < rect.left || box.right > rect.right || box.top < rect.top || box.bottom > rect.bottom) {
      probeError = 'INVALID_TEXT_RECT'; continue;
    }
    // Ten interior points per actual text fragment: both text-height bands and
    // five horizontal positions catch partial overlays without rounded padding.
    for (const fy of [0.35, 0.65]) for (const fx of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      const x = box.left + box.width * fx, y = box.top + box.height * fy;
      const hit = contained ? document.elementFromPoint(x, y) : null;
      const ownership = !hit ? 'none' : hit === element ? 'self' : element.contains(hit) ? 'descendant' : 'outside';
      probes.push({ line, x, y, hit: hit ? { tag: hit.tagName.toLowerCase(), role: hit.getAttribute('role')?.slice(0, 64) ?? null,
        classes: hit.getAttribute('class')?.slice(0, 120) ?? null } : null, ownership, owned: ownership === 'self' || ownership === 'descendant' });
    }
  }
  const exposed = contained && !probeError && probes.length > 0 && probes.every(probe => probe.owned);
  return { rect, viewport, clip, finite, contained, painted, exposed, font, textRects, probes, probeError, visitedTextNodes };
}

async function captureAnswerReading(page: Page, disclosure: Locator,
  targets: { label: string; locator: Locator }[], name: string, info: TestInfo) {
  // Reach the answer using the existing bounded native Tab path. Arrow keys are
  // ordinary reading navigation, with a strict bound; no DOM scroll/focus calls.
  await tabTo(page, disclosure); await expect(disclosure).toBeFocused();
  let geometry = await Promise.all(targets.map(async target => ({ label: target.label, ...await target.locator.evaluate(readableAnswerPaint) })));
  let keys = 0, navigationFailure: string | null = null;
  while (!geometry.every(item => item.contained) && keys < 32) {
    if (!geometry.every(item => item.finite && item.rect.width > 0 && item.rect.height > 0)) { navigationFailure = 'INVALID_TARGET_GEOMETRY'; break; }
    const top = Math.min(...geometry.map(item => item.rect.top)), bottom = Math.max(...geometry.map(item => item.rect.bottom));
    const clipTop = Math.max(...geometry.map(item => item.clip.top)), clipBottom = Math.min(...geometry.map(item => item.clip.bottom));
    if (bottom - top > clipBottom - clipTop) { navigationFailure = 'TARGET_GROUP_EXCEEDS_CLIP'; break; }
    if (top >= clipTop && bottom <= clipBottom) break; // Horizontal clipping is a failure, not a scroll workaround.
    await page.keyboard.press(top < clipTop ? 'ArrowUp' : 'ArrowDown'); keys++;
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())));
    geometry = await Promise.all(targets.map(async target => ({ label: target.label, ...await target.locator.evaluate(readableAnswerPaint) })));
  }
  // Retain labeled screenshot and every coordinate/hit/ownership result even
  // when a visibility assertion fails. These reads do not move focus or scroll.
  const screenshot = await page.screenshot();
  await info.attach(`${name}-geometry`, { body: JSON.stringify({ frame: name, nativeReadingKeys: keys, navigationFailure, targets: geometry }), contentType: 'application/json' });
  await info.attach(name, { body: screenshot, contentType: 'image/png' });
  expect(navigationFailure, name).toBe(null);
  for (const item of geometry) {
    expect(item.finite, item.label).toBe(true); expect(item.contained, item.label).toBe(true); expect(item.painted, item.label).toBe(true);
    expect(item.exposed, item.label).toBe(true); expect(item.font, item.label).toBeGreaterThan(0);
  }
}

const liabilityRatio = 'total_liabilities_to_total_assets';
function ratioSummary(ticker: 'AAA' | 'BBB', kind: 'annual' | 'quarter') {
  const ratios = balanceSheetRatios(fixtures[ticker], data.company(ticker).cik);
  if (!ratios) throw new Error('Canonical Python ratio fixture refused');
  return { ...data.summary(ticker, kind), balance_sheet_ratios: ratios };
}

test('balance-sheet ratios: exact evidence, zero cash and mismatched-date refusal', async ({ page, scenario }, info) => {
  scenario.versions.AAA = 0; scenario.versions.BBB = 1;
  const expected = ledger(data.freshness('AAA', 0));
  publication(expected, 'AAA', 0); phase(scenario, expected, 'AAA', 0, true);
  const heldBeta = scenario.hold(request => request.path === '/companies/BBB/financials/summary'
    && request.query.toString() === 'period=quarter', () => ({ body: ratioSummary('BBB', 'quarter'), version: '1' }));
  scenario.overrides.push(request => {
    if (/\/sources$|\/context$|\/filings\//.test(request.path)) throw new Error('Ratio inspection attempted filing retrieval');
    if (request.path === '/capabilities') return { body: { research_mode: true, ai_analysis_configured: false,
      ai_analysis_enabled: false, server_profile: 'sec_readonly', filing_research_enabled: false } };
    if (request.path === '/companies/AAA/financials/summary' && request.query.toString() === 'period=quarter')
      return { body: ratioSummary('AAA', 'quarter'), version: '0' };
    return undefined;
  });
  const panel = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  const ratios = panel.locator('.balance-sheet-ratios');
  const disclosure = ratios.locator(':scope > summary');
  const card = (name: string) => ratios.locator('article').filter({ has: page.getByRole('heading', { name, exact: true }) });
  const liabilities = card('Total liabilities / total assets');
  const cash = card('Cash and equivalents / total liabilities');
  async function ready(ticker: 'AAA' | 'BBB', pin: number) {
    await expect(page.getByRole('region', { name: 'Data freshness', exact: true })).toContainText(`version ${pin}`);
    await expect(panel.locator('.metric-value').first()).toBeVisible();
    await expect(page.getByRole('region', { name: 'Reported quarter-duration windows', exact: true }).getByRole('status'))
      .toHaveText('Select two to four reported windows.');
    await expect(page.getByRole('region', { name: 'Annual financial insights', exact: true }).locator('.insights-status'))
      .toHaveText(supportsInsightsPublication(ticker, pin) ? 'Choose Compare annual periods to request this comparison.'
        : 'Annual financial insights could not be loaded or verified. Retry explicitly.', { timeout: 35_000 });
  }
  try {
    await scenario.open(); await ready('AAA', 0);
    await expect(ratios).toHaveCount(1);
    const beforeDisclosure = scenario.ledger.length;
    await tabTo(page, disclosure); await capture(disclosure, 'ratios-disclosure-focus', page, info);
    await page.keyboard.press('Enter'); await expect(ratios).toHaveAttribute('open', '');
    await expect(liabilities.locator('.metric-value')).toHaveText('33.33%');
    await expect(cash.locator('.metric-value')).toHaveText('0%');
    await expect(liabilities.locator('.metric-period')).toHaveText('As of date · Dec 31, 2025');
    const source = liabilities.locator('.provenance > summary');
    await tabTo(page, source); await expect(source).toBeFocused(); await page.keyboard.press('Enter');
    await captureAnswerReading(page, source, [
      { label: 'exact liabilities ratio', locator: liabilities.locator('.details-body > p').filter({ hasText: 'Exact API value:' }) },
      { label: 'formula', locator: liabilities.locator('.details-body > p').filter({ hasText: 'Calculation:' }) },
    ], 'ratios-formula', info);
    await expect(liabilities).toContainText('0.3333333333333333333333333333 ratio');
    await expect(liabilities).toContainText('total_liabilities / total_assets');
    await expect(liabilities).toContainText('total liabilities: 100 USD');
    await expect(liabilities).toContainText('total assets: 300 USD');
    await captureAnswerReading(page, source, [
      { label: 'liabilities operand', locator: liabilities.locator('.details-body > p').filter({ hasText: 'total liabilities: 100 USD' }) },
      { label: 'assets operand', locator: liabilities.locator('.details-body > p').filter({ hasText: 'total assets: 300 USD' }) },
    ], 'ratios-operands', info);
    const link = liabilities.getByRole('link', { name: 'Open official SEC filing ↗', exact: true }).first();
    await tabTo(page, link); await expect(link).toBeFocused();
    await expect(link).toHaveAttribute('href', fixtures.AAA[liabilityRatio].provenance[0].sec_url);
    await captureAnswerReading(page, link, [{ label: 'source fiscal context', locator: liabilities.locator('.source-record').first().locator('p').last() },
      { label: 'official source', locator: link }], 'ratios-source', info);
    const cashSource = cash.locator('.provenance > summary');
    await tabTo(page, cashSource); await expect(cashSource).toBeFocused(); await page.keyboard.press('Enter');
    await captureAnswerReading(page, cashSource, [{ label: 'zero cash', locator: cash.locator('.metric-value') },
      { label: 'zero cash date', locator: cash.locator('.metric-period') }], 'ratios-zero-cash', info);
    await expect(cash).toContainText('cash and equivalents: 0 USD');
    expect(scenario.ledger).toHaveLength(beforeDisclosure);
    await exactLedger(scenario, expected);

    const company = page.getByRole('combobox', { name: 'Company', exact: true });
    publication(expected, 'BBB', 1); phase(scenario, expected, 'BBB', 1);
    expected.completed.push(...completedRequests([expectedRequest('/companies')]));
    await company.selectOption('BBB');
    await expect(ratios).toHaveCount(0); // The held new summary cannot expose the old issuer's ratios.
    await expect.poll(() => scenario.count('/companies/BBB/financials/summary')).toBe(1);
    heldBeta.release(); await ready('BBB', 1);
    await tabTo(page, disclosure); await page.keyboard.press('Enter');
    await expect(liabilities.locator('.metric-value')).toHaveText('Unavailable');
    await expect(liabilities.locator('.metric-reason')).toHaveText(fixtures.BBB[liabilityRatio].reason!);
    await expect(liabilities.getByRole('link')).toHaveCount(0);
    const missingSource = liabilities.locator('.provenance > summary');
    await tabTo(page, missingSource); await expect(missingSource).toBeFocused();
    await captureAnswerReading(page, missingSource, [{ label: 'unavailable value', locator: liabilities.locator('.metric-value') },
      { label: 'mismatched-date reason', locator: liabilities.locator('.metric-reason') }], 'ratios-unavailable', info);
    await expect(cash.locator('.metric-value')).toHaveText('0%');
    const layout = await ratios.evaluate(element => ({ page: document.documentElement.scrollWidth, viewport: innerWidth,
      width: element.clientWidth, scrollWidth: element.scrollWidth,
      cards: Array.from(element.querySelectorAll('.metric-card')).map(card => ({ width: card.clientWidth, scrollWidth: card.scrollWidth })) }));
    await info.attach('ratios-layout', { body: JSON.stringify(layout), contentType: 'application/json' });
    expect(layout.page).toBeLessThanOrEqual(layout.viewport); expect(layout.scrollWidth).toBeLessThanOrEqual(layout.width);
    for (const item of layout.cards) expect(item.scrollWidth).toBeLessThanOrEqual(item.width);
    await exactLedger(scenario, expected);
    expect(scenario.ledger.filter(request => request.method !== 'GET' || /\/sources$|\/context$|\/filings\//.test(request.path))).toHaveLength(0);
  } finally {
    const audit = JSON.stringify({ synthetic: true, expected, lifecycle: lifecycle(scenario, expected.phases.flatMap(item => item.native)),
      violations: scenario.violations, failures: scenario.failures });
    expect(Buffer.byteLength(audit)).toBeLessThanOrEqual(32768);
    await info.attach('ratios-request-audit', { body: audit, contentType: 'application/json' });
  }
});
