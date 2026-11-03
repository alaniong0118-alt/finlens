import type { Locator, Page, TestInfo } from '@playwright/test';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { test, expect, lifecycle, annualRequestCursor, expectedRequest, completedRequests,
  publicationCompletions, publicationHeaderCancellations, replayCancellations,
  captureFocusPaint, assessFocusPaint, type ExpectedLedger } from './fixtures/annual-period-browser';
import type { Scenario } from './fixtures/browser';
import { supportsInsightsPublication } from './fixtures/financial-insights-browser';
import fixtures from './fixtures/guided-fiscal-answers.json';
import { freshness } from './fixtures/data';

// PNG is already bundled in the pinned Playwright dependency; no package install.
const decoderRequire = createRequire(join(process.cwd(), 'package.json'));
const decoderPackage = decoderRequire.resolve('playwright-core/package.json');
if ((decoderRequire(decoderPackage) as { version: string }).version !== '1.64.0') throw new Error('Unreviewed PNG decoder version');
const { PNG } = decoderRequire(join(dirname(decoderPackage), 'lib/utilsBundle.js')) as {
  PNG: { sync: { read: (bytes: Buffer) => { width: number; height: number; data: Buffer } } };
};

// Canonical backend serialization of detached synthetic facts, never live data.
// The fixture provenance file records its exact guarded generator and inputs.
test.use({ deviceScaleFactor: 1 });
const endpoint = '/companies/AAA/research-answer';
const requestSignature = (pin: number, question: string) => JSON.stringify(['POST', endpoint, '', String(pin), { question }]);

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

async function ready(page: Page, pin: number) {
  await expect(page.getByRole('region', { name: 'Data freshness', exact: true })).toContainText(`version ${pin}`);
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-value').first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Reported quarter-duration windows', exact: true }).getByRole('status'))
    .toHaveText('Select two to four reported windows.');
  await expect(page.getByRole('region', { name: 'Annual financial insights', exact: true }).locator('.insights-status'))
    .toHaveText(supportsInsightsPublication('AAA', pin) ? 'Choose Compare annual periods to request this comparison.'
      : 'Annual financial insights could not be loaded or verified. Retry explicitly.', { timeout: 35_000 });
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

test('guided fiscal questions: explicit historical and comparison preparation, sources and keyboard geometry', async ({ page, scenario }, info) => {
  // Both publication zero and a nonzero publication are exercised across the two projects.
  const pin = info.project.name === 'mobile-width-chromium' ? 7 : 0;
  scenario.versions.AAA = pin;
  const expected = ledger(freshness('AAA', pin)); publication(expected, 'AAA', pin); phase(scenario, expected, 'AAA', pin, true);
  const payloads = new Map(fixtures.map(answer => [answer.question, answer]));
  scenario.overrides.unshift(request => {
    if (/\/sources$|\/context$|\/filings\//.test(request.path)) throw new Error('Financial-only guide attempted retrieval');
    if (request.path === '/capabilities') return { body: { research_mode: true, ai_analysis_configured: false,
      ai_analysis_enabled: false, server_profile: 'sec_readonly', filing_research_enabled: false } };
    if (request.path === endpoint) {
      const body = request.body as { question: string };
      const answer = payloads.get(body.question);
      if (request.method !== 'POST' || request.query.toString() !== '' || request.pin !== String(pin)
        || JSON.stringify(body) !== JSON.stringify({ question: body.question }) || !answer) throw new Error('Unexpected guided financial request');
      return { body: answer, version: String(pin) };
    }
    return undefined;
  });
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  const preparation = page.getByRole('combobox', { name: 'Question preparation', exact: true });
  const metric = page.getByRole('combobox', { name: 'Question metric', exact: true });
  const use = page.getByRole('button', { name: 'Use question', exact: true });
  const answer = page.locator('.direct-answer');
  async function prepare({ comparison = false, metricName = 'revenue', period = 'annual', year = '2024', later = '2025' } = {}) {
    const count = scenario.ledger.length, oldEditor = await editor.inputValue();
    await preparation.selectOption(comparison ? 'comparison' : 'historical');
    await metric.selectOption(metricName);
    await page.getByRole('combobox', { name: comparison ? 'Shared fiscal period' : 'Requested fiscal period', exact: true }).selectOption(period);
    await page.getByRole('textbox', { name: comparison ? 'Earlier fiscal year' : 'Fiscal year', exact: true }).fill(year);
    const last = page.getByRole('textbox', { name: comparison ? 'Later fiscal year' : 'Fiscal year', exact: true });
    if (comparison) await last.fill(later);
    expect(scenario.ledger.length).toBe(count); await expect(editor).toHaveValue(oldEditor);
    await exactLedger(scenario, expected);
    return last;
  }
  async function submit(question: string, focus = false) {
    await expect(page.locator('.question-preview')).toHaveText(question);
    const before = scenario.ledger.length;
    // Native tab from the last year field, Enter on Use question, then native tab to submit.
    await page.keyboard.press('Tab'); await expect(use).toBeFocused();
    if (focus) await capture(use, 'guided-use-focus', page, info);
    await page.keyboard.press('Enter'); await expect(editor).toBeFocused(); await expect(editor).toHaveValue(question);
    expect(scenario.ledger.length).toBe(before);
    if (focus) await capture(editor, 'guided-editor-focus', page, info);
    await tabTo(page, page.getByRole('button', { name: 'Research question', exact: true }));
    expected.completed.push(...completedRequests([requestSignature(pin, question)]));
    await page.keyboard.press('Enter');
    await expect(answer).toContainText('Research Answer');
    await exactLedger(scenario, expected);
    expect(scenario.ledger.length).toBe(before + 1);
  }
  try {
    await scenario.open(); await ready(page, pin); await exactLedger(scenario, expected);
    const startupCount = scenario.ledger.length;
    await expect(editor).toHaveValue('');
    await expect(page.getByRole('status').filter({ hasText: 'Financial-only capability restriction is active.' })).toBeVisible();
    await prepare();
    await submit('What was FY2024 revenue?', true);
    await expect(answer.locator('.metric-value')).toHaveText('$100.00');
    await expect(answer).toContainText('FY2024');
    const provenance = answer.getByText('View provenance', { exact: true });
    await tabTo(page, provenance); await expect(provenance).toBeFocused(); await page.keyboard.press('Enter');
    const source = answer.getByRole('link', { name: /Open official SEC filing/ }).first();
    await expect(source).toHaveAttribute('href', /^https:\/\/www\.sec\.gov\/Archives\/edgar\/data\/900001\/0000900001/);
    await tabTo(page, source); await expect(source).toBeFocused();
    await info.attach('guided-historical-source', { body: await page.screenshot(), contentType: 'image/png' });
    await prepare({ period: 'q2', year: '2025' });
    await submit('What was Q2 FY2025 revenue?');
    await expect(answer.locator('.metric-value')).toHaveText('Unavailable');
    await expect(answer).toContainText('Annual, YTD and unlabeled periods are not substituted.');
    await captureAnswerReading(page, answer.getByText('View provenance', { exact: true }), [
      { label: 'unavailable-value', locator: answer.locator('.metric-value') },
      { label: 'no-substitution-explanation', locator: answer.locator('.answer-text') },
    ], 'guided-quarter-unavailable', info);
    const last = await prepare({ comparison: true, metricName: 'operating_margin' });
    await expect(metric.locator('option')).toHaveCount(11);
    await last.press('Shift+Tab'); await page.keyboard.press('Shift+Tab');
    const shared = page.getByRole('combobox', { name: 'Shared fiscal period', exact: true });
    await capture(shared, 'guided-period-focus', page, info);
    await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Shift+Tab');
    await capture(preparation, 'guided-mode-focus', page, info);
    await tabTo(page, last); await capture(last, 'guided-year-focus', page, info);
    await submit('Compare FY2024 and FY2025 operating margin.');
    await expect(answer.locator('.metric-value')).toHaveText('+10.00 percentage points');
    await expect(answer).toContainText('FY2024'); await expect(answer).toContainText('FY2025');
    await expect(answer).toContainText('Ratio comparisons use percentage-point change, not percentage growth.');
    await prepare({ comparison: true, metricName: 'diluted_eps', period: 'q2' });
    await submit('Compare Q2 FY2024 and Q2 FY2025 diluted eps.');
    await expect(answer).toContainText('Reported as filed · comparability unverified.');
    await expect(answer).toContainText('stock-split/restatement share-basis comparability is unverified.');
    await expect(answer.locator('.comparison-values')).toContainText('Q2 FY2024');
    await expect(answer.locator('.comparison-values')).toContainText('Q2 FY2025');
    const comparisonDisclosure = answer.getByText('View comparison provenance', { exact: true });
    await captureAnswerReading(page, comparisonDisclosure, [
      { label: 'eps-change-value', locator: answer.locator('.metric-value') },
      { label: 'no-eps-percentage-explanation', locator: answer.locator('.comparison-values + [role="note"]') },
    ], 'guided-comparison-eps', info);
    // The as-filed note may be below the first view. Give it its own verified
    // reading frame instead of claiming the entire tall answer fits at once.
    await captureAnswerReading(page, comparisonDisclosure, [
      { label: 'eps-as-filed-basis', locator: answer.getByRole('note').filter({ hasText: 'Reported as filed · comparability unverified.' }) },
    ], 'guided-comparison-eps-basis', info);
    const count = scenario.ledger.length, question = await editor.inputValue();
    for (const year of ['', '1899', '2100', '2025', '2026']) {
      await page.getByRole('textbox', { name: 'Earlier fiscal year', exact: true }).fill(year);
      await expect(use).toBeDisabled(); await expect(editor).toHaveValue(question);
    }
    expect(scenario.ledger.length).toBe(count);
    expect(count).toBe(startupCount + 4);
    const layout = await page.locator('.question-guide').evaluate(element => {
      const box = (control: Element) => {
        const r = control.getBoundingClientRect(); return { left: r.left, right: r.right, width: r.width, font: parseFloat(getComputedStyle(control).fontSize) };
      };
      return { viewport: innerWidth, page: document.documentElement.scrollWidth,
        controls: [...element.querySelectorAll('input,select')].map(box),
        preview: box(element.querySelector('.question-preview')!),
      };
    });
    expect(layout.page).toBeLessThanOrEqual(layout.viewport);
    for (const control of [...layout.controls, layout.preview]) {
      expect(control.left).toBeGreaterThanOrEqual(0); expect(control.right).toBeLessThanOrEqual(layout.viewport);
      expect(control.width).toBeGreaterThan(0);
    }
    for (const control of layout.controls) expect(control.font).toBeGreaterThanOrEqual(14);
    expect(layout.preview.font).toBe(13);
    await info.attach('guided-layout', { body: JSON.stringify(layout), contentType: 'application/json' });
    await exactLedger(scenario, expected);
    expect(scenario.ledger.filter(request => /\/sources$|\/context$|\/filings\//.test(request.path))).toHaveLength(0);
  } finally {
    const body = JSON.stringify({ synthetic: true, pin, expected, lifecycle: lifecycle(scenario, expected.phases.flatMap(item => item.native)),
      violations: scenario.violations, failures: scenario.failures });
    expect(Buffer.byteLength(body)).toBeLessThanOrEqual(32768);
    await info.attach('guided-request-audit', { body, contentType: 'application/json' });
  }
});
