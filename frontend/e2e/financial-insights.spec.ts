import type { Locator, Page, Worker } from '@playwright/test';
import { test, expect, origin } from './fixtures/browser';
import type { Scenario } from './fixtures/browser';

test('FIN-DEPTH-01 real Worker annual discovery comparison and evidence navigation', async ({ page, scenario }, info) => {
  // Two separate <=30s initializations plus bounded page operations. Production
  // deadlines, clocks, constructor, Worker scripts and transport stay untouched.
  test.setTimeout(90_000);
  const workers: { worker: Worker; url: string; closed: boolean }[] = [];
  page.on('worker', worker => {
    const entry = { worker, url: worker.url(), closed: false };
    workers.push(entry); worker.on('close', () => { entry.closed = true; });
  });
  const path = '/companies/AAA/financials/insights';
  const requests = () => scenario.ledger.filter(request => request.path === path);
  const panel = page.getByRole('region', { name: 'Annual financial insights', exact: true });
  const status = panel.locator('.insights-status');
  const scope = '0000900001:0:0:0:2024:2025';
  const window = '2025-01-01/2025-12-31/annual';
  const values = [
    ['revenue', 'Revenue', '100 USD', '120 USD', 'Reported'],
    ['operating_income', 'Operating income', '10 USD', '18 USD', 'Reported'],
    ['net_income', 'Net income', '8 USD', '12 USD', 'Reported'],
    ['operating_margin', 'Operating margin', '10%', '15%', 'Calculated'],
    ['net_margin', 'Net margin', '8%', '10%', 'Calculated'],
    ['operating_cash_flow', 'Operating cash flow', '14 USD', '20 USD', 'Reported'],
    ['free_cash_flow', 'Free cash flow', '10 USD', '15 USD', 'Calculated'],
  ]; // Independent fixed expectations; never derived through the fixture adapter.

  // Passive, bounded diagnostics only. Never replace Worker/focus or fetch, and
  // never record editor values or arbitrary typed keys. Cleanup also runs on fail.
  await page.addInitScript(() => {
    let trigger: HTMLElement | null = null, activatedWhileFocused = false, intentRevoked = false, publication = '';
    const samples: unknown[] = [];
    const describe = (node: EventTarget | null) => node instanceof HTMLElement ? {
      tag: node.tagName, id: node.id.slice(0, 80), key: node.dataset.insightKey?.slice(0, 192),
      control: node.matches('button,summary') ? node.textContent?.trim().slice(0, 96) : node.getAttribute('aria-label')?.slice(0, 96),
      record: node.closest<HTMLElement>('[data-insight-key]')?.dataset.insightKey?.slice(0, 192),
      metric: node.closest<HTMLElement>('[data-insight-metric]')?.dataset.insightMetric?.slice(0, 64),
      connected: node.isConnected, disabled: node.matches(':disabled'),
    } : null;
    const sample = (event: string, target: EventTarget | null) => {
      if (samples.length === 64) samples.shift();
      samples.push({ event, target: describe(target), active: describe(document.activeElement), trigger: describe(trigger), intentRevoked });
    };
    const observer = new MutationObserver(() => sample('trigger-disabled-change', trigger));
    const listener = (event: Event) => {
      const element = event.target instanceof Element ? event.target : null;
      const button = element?.closest<HTMLElement>('.financial-insights button');
      if (event.type === 'click' && button?.closest('.insights-links,.insights-collections,.insights-pagination')) {
        observer.disconnect(); trigger = button; activatedWhileFocused = document.activeElement === trigger; intentRevoked = false;
        publication = document.querySelector('.insights-result > .mono')?.textContent?.slice(0, 192) ?? '';
        observer.observe(trigger, { attributes: true, attributeFilter: ['disabled'] });
      } else if (trigger) {
        const atTrigger = event.target instanceof Node && trigger.contains(event.target);
        if (event.type === 'focusin' && !atTrigger || event.type === 'pointerdown' && !atTrigger
          || event.type === 'keydown' && (!atTrigger || !['Enter', ' '].includes((event as KeyboardEvent).key))) intentRevoked = true;
      }
      if (trigger) sample(event.type, event.target);
    };
    const types = ['click', 'pointerdown', 'keydown', 'focusin', 'focusout'];
    types.forEach(type => document.addEventListener(type, listener, true));
    const api = {
      snapshot(key: string | null) {
        const target = key ? Array.from(document.querySelectorAll<HTMLElement>('[data-insight-key]')).find(n => n.dataset.insightKey === key)
          : document.querySelector<HTMLElement>('.insights-viewport');
        const box = target?.getBoundingClientRect(), style = target ? getComputedStyle(target) : null;
        const currentPublication = document.querySelector('.insights-result > .mono')?.textContent?.slice(0, 192) ?? '';
        return { active: describe(document.activeElement), documentFocused: document.hasFocus(), trigger: describe(trigger), target: describe(target ?? null),
          targetRendered: Boolean(box && box.width && box.height && style?.display !== 'none' && style?.visibility !== 'hidden'),
          targetInViewport: Boolean(box && box.top < innerHeight && box.bottom > 0),
          page: document.querySelector('.insights-pagination span')?.textContent,
          busy: document.querySelector('.insights-status')?.getAttribute('aria-busy'),
          observedOwnership: { activatedWhileFocused, intentRevoked, publicationUnchanged: publication === currentPublication,
            note: 'DOM observations only; internal generation/handle are not exposed.' }, samples };
      },
      dispose() { observer.disconnect(); types.forEach(type => document.removeEventListener(type, listener, true)); },
    };
    Object.assign(window, { qaInsightsFocus: api });
  });
  let requestedFocusKey: string | null = null;
  try {
  await scenario.open(); await scenario.ready();
  await expect(panel.getByRole('combobox', { name: 'Earlier fiscal year', exact: true })).toHaveValue('2024');
  await expect(panel.getByRole('combobox', { name: 'Later fiscal year', exact: true })).toHaveValue('2025');
  for (const label of ['Earlier fiscal year', 'Later fiscal year']) {
    expect(await panel.getByRole('combobox', { name: label, exact: true }).locator('option').evaluateAll(options =>
      options.map(option => (option as HTMLOptionElement).value))).toEqual(['', '2025', '2024']);
  }
  const discovery = requests();
  expect(discovery.length).toBeGreaterThanOrEqual(1); expect(discovery.length).toBeLessThanOrEqual(2);
  expect(discovery.every(r => r.method === 'GET' && r.pin === '0' && r.body === null && r.query.toString() === 'mode=discover')).toBe(true);
  await expect(panel.locator('.insights-result')).toHaveCount(0);
  await expect(status).toHaveText('Choose Compare annual periods to request this comparison.');
  await panel.getByText('Publication and selection policy', { exact: true }).click();
  await expect(panel.locator('.insights-policy')).toContainText('AAA · CIK 0000900001 · publication 0 · facts 0 · evidence 0');
  await expect.poll(() => workers.filter(w => w.closed).length).toBeGreaterThanOrEqual(1);
  const beforeCompare = workers.length;
  await panel.getByRole('button', { name: 'Compare annual periods', exact: true }).click();
  await expect(status).toHaveText('Annual comparison ready. Evidence can be examined below.', { timeout: 35_000 });
  expect(requests().filter(r => r.query.get('mode') === 'compare').map(r => [r.method, r.pin, r.body, r.query.toString()])).toEqual([
    ['GET', '0', null, 'mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025'],
  ]);
  expect(workers.length).toBeGreaterThan(beforeCompare); expect(workers.length).toBeLessThanOrEqual(4);
  for (const entry of workers) {
    const url = new URL(entry.url); expect(url.origin).toBe(origin); expect(url.pathname.startsWith('/_next/')).toBe(true);
  }
  const comparisonWorker = workers.at(-1)!;
  expect(await comparisonWorker.worker.evaluate(() => ({ kind: self.constructor.name, origin: self.location.origin, document: typeof document })))
    .toEqual({ kind: 'DedicatedWorkerGlobalScope', origin, document: 'undefined' });
  await expect(panel.locator('.insights-completeness')).toHaveText('Five headline comparisons: complete. Revenue, operating margin, net margin, operating cash flow and free cash flow.');
  await expect(panel.locator('.insights-result')).toContainText('Earlier: 2024-01-01 – 2024-12-31 · annual · fiscal year 2024');
  await expect(panel.locator('.insights-result')).toContainText('Later: 2025-01-01 – 2025-12-31 · annual · fiscal year 2025');
  await panel.getByText('Seven comparison metrics and their evidence', { exact: true }).click();
  await expect(panel.locator('[data-insight-metric]')).toHaveCount(7);
  async function exactMetrics() {
    for (const [id, label, earlier, later, kind] of values) {
      const card = panel.locator(`[data-insight-metric="${id}"]`);
      await expect(card.getByRole('heading', { name: label, exact: true })).toBeVisible();
      await expect(card.locator('.insights-values dd')).toHaveText([earlier, later]);
      await expect(card.getByText(kind, { exact: true })).toBeVisible();
    }
  }
  await exactMetrics();
  const fetches = requests().length;
  const viewport = panel.locator('.insights-viewport');
  const visited: string[] = [];
  async function ownerAndPage(category: 'F' | 'D') {
    await expect(page.getByRole('combobox', { name: 'Company', exact: true })).toHaveValue('AAA');
    await expect(panel.locator('.insights-result > .mono')).toHaveText(`Publication 0 · facts 0 · evidence 0 · ${scope}`);
    await expect(viewport).toHaveAttribute('aria-busy', 'false');
    const records = viewport.locator('.insights-record');
    const keys = await records.evaluateAll(nodes => nodes.map(node => node.getAttribute('data-insight-key')));
    expect(keys.length).toBeGreaterThan(0); expect(keys.length).toBeLessThanOrEqual(25);
    expect(keys.every(key => key?.startsWith(`${category}|`))).toBe(true);
    for (const record of await records.all()) await expect(record.locator('.mono').nth(1)).toHaveText(`Scope: ${scope}`);
    expect(requests()).toHaveLength(fetches); expect(comparisonWorker.closed).toBe(false);
    return keys;
  }
  async function destination(key: string) {
    requestedFocusKey = key;
    const record = viewport.locator(`[data-insight-key="${key}"]`);
    await expect(record).toBeFocused(); await ownerAndPage('F'); visited.push(key);
    await record.getByText('Exact fields and source metadata', { exact: true }).click();
    await expect(record.getByText(`Reference: ${key}`, { exact: true })).toBeVisible();
    return record;
  }
  async function field(record: Locator, name: string, value: string) {
    const entry = record.locator('.insights-fields > div').filter({ has: page.getByText(name, { exact: true }) });
    await expect(entry.locator('dd')).toHaveText(value);
  }
  const fcf = panel.locator('[data-insight-metric="free_cash_flow"]');
  const statement = fcf.locator('.insights-statement').filter({ has: page.getByText('Free cash flow: 15 USD, later FY2025 2025-01-01/2025-12-31/annual; calculated.', { exact: true }) });
  await statement.getByRole('button', { name: 'Financial evidence 1', exact: true }).click();
  let record = await destination(`F|observation|free_cash_flow|later||${window}|`);
  await field(record, 'data.canonical.value', '15');
  await field(record, 'data.admitted', 'true');
  await record.getByRole('button', { name: 'Examine operand · free cash flow · capital expenditures · later', exact: true }).click();
  record = await destination(`F|operand|free_cash_flow|later|capital_expenditures|${window}|`);
  await field(record, 'data.required_metric', 'capital_expenditures');
  await record.getByRole('button', { name: 'Examine observation · capital expenditures · later', exact: true }).click();
  record = await destination(`F|observation|capital_expenditures|later||${window}|`);
  await field(record, 'data.canonical.value', '5');
  await field(record, 'data.canonical.provenance[0].fact_id', '10');
  await record.getByRole('button', { name: 'Examine source', exact: true }).click();
  record = await destination('F|source|||||10');
  await field(record, 'data.company_cik', '0000900001');
  await field(record, 'data.value', '5');
  await field(record, 'data.original_concept', 'PaymentsToAcquirePropertyPlantAndEquipment');
  await field(record, 'data.accession_number', '0000900001-26-100001');
  await field(record, 'data.period_start', '2025-01-01'); await field(record, 'data.period_end', '2025-12-31');
  const link = record.getByRole('link', { name: 'Open official SEC filing', exact: true });
  await expect(link).toHaveAttribute('href', 'https://www.sec.gov/Archives/edgar/data/900001/000090000126100001/0000900001-26-100001-index.html');
  await expect(link).toHaveAttribute('target', '_blank'); await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  // Inspect source attributes only; never navigate to SEC.
  requestedFocusKey = null;
  await panel.getByRole('button', { name: 'Examine financial evidence', exact: true }).click();
  await expect(viewport).toBeFocused(); const first = await ownerAndPage('F');
  await expect(panel.getByRole('button', { name: 'Previous evidence page', exact: true })).toBeDisabled();
  await panel.getByRole('button', { name: 'Next evidence page', exact: true }).click();
  await expect(panel.locator('.insights-pagination span')).toHaveText(/^F · page 2 of \d+$/);
  await expect(viewport).toBeFocused(); const second = await ownerAndPage('F');
  expect(second).not.toEqual(first); expect(second.some(key => first.includes(key))).toBe(false);
  await panel.getByRole('button', { name: 'Previous evidence page', exact: true }).click();
  await expect(panel.locator('.insights-pagination span')).toHaveText(/^F · page 1 of \d+$/);
  await expect(viewport).toBeFocused(); expect(await ownerAndPage('F')).toEqual(first);
  await panel.getByRole('button', { name: 'Examine diagnostic inputs', exact: true }).click();
  await expect(viewport).toBeFocused(); await ownerAndPage('D');
  await expect(viewport.getByRole('heading', { level: 3 })).toHaveText('Inputs examined and reasons not used — D');
  await expect(panel.getByText('Diagnostic values are not admitted financial results.', { exact: false })).toBeVisible();
  await exactMetrics();
  expect(scenario.failures.every(failure => failure.includes('ERR_ABORTED'))).toBe(true);
  expect(scenario.violations).toEqual([]);
  await info.attach('financial-insights-worker-navigation', { contentType: 'application/json', body: JSON.stringify({
    workers: workers.map(({ url, closed }) => ({ url, closed })), scope, visited, first, second,
    requests: requests().map(r => ({ method: r.method, path: r.path, pin: r.pin, query: r.query.toString() })),
    failures: scenario.failures, violations: scenario.violations,
  }) });
  } catch (error) {
    const diagnostics = await page.evaluate(key => (window as unknown as {
      qaInsightsFocus?: { snapshot(key: string | null): unknown };
    }).qaInsightsFocus?.snapshot(key), requestedFocusKey).catch(() => ({ unavailable: true }));
    await info.attach('financial-insights-focus-failure', { contentType: 'application/json', body: JSON.stringify(diagnostics ?? { unavailable: true }) });
    throw error;
  } finally {
    await page.evaluate(() => (window as unknown as { qaInsightsFocus?: { dispose(): void } }).qaInsightsFocus?.dispose()).catch(() => {});
  }
});

// 1B.3 helpers stay spec-local. Geometry is observational: never repair an
// evidence destination with focus(), scrolling, CSS or a substituted Worker.
const insightsPath = '/companies/AAA/financials/insights';
const insightsScope = '0000900001:0:0:0:2024:2025';
const insightsWindow = '2025-01-01/2025-12-31/annual';
// Unchanged AAA/publication-0 fixture, packed by prepareInsights with its byte,
// structural-entry and record budgets (not simply ceil(records / 25)).
const insightsFPageSizes = [2, 2, 2, 4, 4, 6, 17, 8] as const;
const insightsPanel = (page: Page) => page.getByRole('region', { name: 'Annual financial insights', exact: true });

async function insightsLayout(panel: Locator, width: number) {
  const geometry = await panel.evaluate(element => {
    const rect = element.getBoundingClientRect();
    const rendered = (node: Element) => { const box = node.getBoundingClientRect(); return box.width > 0 && box.height > 0; };
    const nodes = Array.from(element.querySelectorAll<HTMLElement>('button,select,summary,.insights-fields dt,.insights-fields dd,.insights-record'))
      .filter(rendered);
    const bad = nodes.filter(node => {
      const box = node.getBoundingClientRect();
      return box.left < rect.left - 1 || box.right > rect.right + 1 || node.scrollWidth > node.clientWidth + 1;
    }).map(node => ({ tag: node.tagName, text: node.textContent?.trim().slice(0, 80) })).slice(0, 16);
    return { width: innerWidth, documentWidth: document.documentElement.scrollWidth, left: rect.left, right: rect.right,
      panelWidth: element.clientWidth, panelScrollWidth: element.scrollWidth, inspected: nodes.length, bad,
      grids: Array.from(element.querySelectorAll('.insights-controls,.insights-metric-grid,.insights-collections')).filter(rendered)
        .map(node => getComputedStyle(node).gridTemplateColumns.split(' ').length),
      valueColumns: Array.from(element.querySelectorAll('.insights-values')).filter(rendered)
        .map(node => getComputedStyle(node).gridTemplateColumns.split(' ').length),
      controls: nodes.filter(node => node.matches('button,select,summary')).map(node => ({
        height: node.getBoundingClientRect().height, wraps: getComputedStyle(node).whiteSpace !== 'nowrap',
      })),
      evidenceOverflowY: element.querySelector('.insights-viewport') ? getComputedStyle(element.querySelector('.insights-viewport')!).overflowY : null };
  });
  await test.info().attach(`insights-layout-${width}`, { contentType: 'application/json', body: JSON.stringify(geometry) });
  expect(geometry.width).toBe(width); expect(geometry.documentWidth).toBeLessThanOrEqual(width + 1);
  expect(geometry.left).toBeGreaterThanOrEqual(0); expect(geometry.right).toBeLessThanOrEqual(width + 1);
  expect(geometry.panelScrollWidth).toBeLessThanOrEqual(geometry.panelWidth + 1);
  expect(geometry.inspected).toBeGreaterThan(0); expect(geometry.bad).toEqual([]);
  expect(geometry.grids.length).toBeGreaterThan(0); expect(geometry.grids.every(columns => columns === 1)).toBe(true);
  expect(geometry.valueColumns).toHaveLength(7);
  expect(geometry.valueColumns.every(columns => columns === (width <= 480 ? 1 : 2))).toBe(true);
  expect(geometry.controls.every(control => control.height >= 44 && control.wraps)).toBe(true);
  // evidenceOverflowY is recorded, not used to invent an independent scroll box.
}

type InsightsRect = { left: number; right: number; top: number; bottom: number };
type InsightsClip = { bounds: InsightsRect; overflowX: string; overflowY: string };
type InsightsFocusSample = { target: InsightsRect; focal: InsightsRect; viewport: InsightsRect;
  focalClips: InsightsClip[]; indicatorClips: InsightsClip[]; destination: boolean;
  outlineWidth: number; outlineOffset: number; outline: string };

// Pure assessment is shared by real read-only DOM measurements and deterministic
// offline adversarial checks. Focal geometry never stands in for outline geometry.
function assessInsightsFocus(sample: InsightsFocusSample) {
  const valid = (box: InsightsRect) => Object.values(box).every(Number.isFinite) && box.right > box.left && box.bottom > box.top;
  const contained = (box: InsightsRect, clip: InsightsRect, x = true, y = true) =>
    (!x || box.left >= clip.left && box.right <= clip.right) && (!y || box.top >= clip.top && box.bottom <= clip.bottom);
  const visible = (box: InsightsRect, clips: InsightsClip[]) => valid(box) && contained(box, sample.viewport)
    && clips.every(clip => contained(box, clip.bounds, /^(hidden|clip|auto|scroll)$/.test(clip.overflowX), /^(hidden|clip|auto|scroll)$/.test(clip.overflowY)));
  const expand = (amount: number): InsightsRect => ({ left: sample.target.left - amount, right: sample.target.right + amount,
    top: sample.target.top - amount, bottom: sample.target.bottom + amount });
  const outer = expand(sample.outlineOffset + sample.outlineWidth), inner = expand(sample.outlineOffset);
  // Controls require all four outline bands. Destinations require the actual
  // top band and both side bands through the heading's bottom. This arrival
  // indicator can fit even when a tall record's bottom is below the viewport.
  const sideBottom = sample.destination ? Math.min(inner.bottom, sample.focal.bottom) : inner.bottom;
  const segments = [
    { left: outer.left, right: outer.right, top: outer.top, bottom: inner.top },
    { left: outer.left, right: inner.left, top: inner.top, bottom: sideBottom },
    { left: inner.right, right: outer.right, top: inner.top, bottom: sideBottom },
    ...sample.destination ? [] : [{ left: outer.left, right: outer.right, top: inner.bottom, bottom: outer.bottom }],
  ];
  return { focalVisible: visible(sample.focal, sample.focalClips), outer, segments,
    indicatorVisible: valid(sample.target) && Number.isFinite(sample.outlineOffset) && sample.outlineWidth > 0
      && Number.isFinite(sample.outlineWidth) && !['none', 'hidden'].includes(sample.outline)
      && segments.every(segment => visible(segment, sample.indicatorClips)) };
}

function insightsFocusAdversarialChecks() {
  const sample: InsightsFocusSample = {
    target: { left: 20, right: 300, top: 20, bottom: 1200 }, focal: { left: 34, right: 286, top: 34, bottom: 60 },
    viewport: { left: 0, right: 390, top: 0, bottom: 844 }, focalClips: [], indicatorClips: [],
    destination: true, outlineWidth: 3, outlineOffset: 3, outline: 'solid',
  };
  const tall = assessInsightsFocus(sample);
  expect(tall.focalVisible).toBe(true); expect(tall.indicatorVisible).toBe(true);
  expect(sample.target.bottom).toBeGreaterThan(sample.viewport.bottom);
  // Heading fits in this overflow:hidden ancestor, but its padding edge clips
  // the focused record's real top/left/right outline. The old probe passed it.
  const hidden: InsightsClip = { bounds: { left: 20, right: 300, top: 20, bottom: 844 }, overflowX: 'hidden', overflowY: 'hidden' };
  const clipped = assessInsightsFocus({ ...sample, focalClips: [hidden], indicatorClips: [hidden] });
  expect(clipped.focalVisible).toBe(true); expect(clipped.indicatorVisible).toBe(false);
  const viewportClipped = assessInsightsFocus({ ...sample, viewport: { ...sample.viewport, left: 18 } });
  expect(viewportClipped.focalVisible).toBe(true); expect(viewportClipped.indicatorVisible).toBe(false);
  // Offset is independent of width: the border and width-only expansion fit,
  // while the real offset outline crosses the ancestor edge at x=16.
  const offsetClip: InsightsClip = { ...hidden, bounds: { left: 16, right: 384, top: 0, bottom: 844 }, overflowY: 'visible' };
  expect(assessInsightsFocus({ ...sample, outlineOffset: 0, indicatorClips: [offsetClip] }).indicatorVisible).toBe(true);
  expect(assessInsightsFocus({ ...sample, indicatorClips: [offsetClip] }).indicatorVisible).toBe(false);
  const control = { ...sample, destination: false, target: { ...sample.target, bottom: 100 }, focal: { ...sample.target, bottom: 100 } };
  expect(assessInsightsFocus(control).indicatorVisible).toBe(true);
  expect(assessInsightsFocus({ ...control, viewport: { ...sample.viewport, bottom: 104 } }).indicatorVisible).toBe(false);
  // Native Tab can leave Compare flush with the viewport bottom. Signed inset
  // geometry must pass there while the original outward outline still rejects.
  const boundaryControl = { ...control, target: { left: 20, right: 300, top: 956, bottom: 1000 },
    focal: { left: 20, right: 300, top: 956, bottom: 1000 }, viewport: { left: 0, right: 1440, top: 0, bottom: 1000 } };
  const inset = assessInsightsFocus({ ...boundaryControl, outlineOffset: -6 });
  expect(inset.focalVisible).toBe(true); expect(inset.indicatorVisible).toBe(true);
  expect(inset.outer).toEqual({ left: 23, right: 297, top: 959, bottom: 997 });
  expect(inset.segments).toHaveLength(4);
  const boundaryClipped = assessInsightsFocus(boundaryControl);
  expect(boundaryClipped.focalVisible).toBe(true); expect(boundaryClipped.indicatorVisible).toBe(false);
  expect(boundaryClipped.outer.bottom).toBe(1006);
  // Exact fractional Cancel geometry from run 40491981755 / artifact 12728434315.
  const recordedCancel = { ...boundaryControl,
    target: { left: 253.421875, top: 955.203125, right: 429.015625, bottom: 1000 },
    focal: { left: 253.421875, top: 955.203125, right: 429.015625, bottom: 1000 } };
  const cancelOutward = assessInsightsFocus(recordedCancel);
  expect(cancelOutward.focalVisible).toBe(true); expect(cancelOutward.indicatorVisible).toBe(false);
  expect(cancelOutward.outer.bottom).toBe(1006);
  const cancelInset = assessInsightsFocus({ ...recordedCancel, outlineOffset: -6 });
  expect(cancelInset.focalVisible).toBe(true); expect(cancelInset.indicatorVisible).toBe(true);
  expect(cancelInset.outer).toEqual({ left: 256.421875, top: 958.203125, right: 426.015625, bottom: 997 });
  expect(cancelInset.segments).toHaveLength(4);
  // Third CI: native reverse Tab reached the right control but put its border
  // fractionally above the viewport. Inset styling alone cannot repair that.
  const recordedFinancial = { ...boundaryControl,
    target: { left: 72, right: 275.09375, top: -0.0625, bottom: 44.734375 },
    focal: { left: 72, right: 275.09375, top: -0.0625, bottom: 44.734375 } };
  const financialOutward = assessInsightsFocus(recordedFinancial);
  expect(financialOutward.focalVisible).toBe(false); expect(financialOutward.indicatorVisible).toBe(false);
  expect(financialOutward.outer.top).toBe(-6.0625);
  const financialInset = assessInsightsFocus({ ...recordedFinancial, outlineOffset: -6 });
  expect(financialInset.focalVisible).toBe(false); expect(financialInset.indicatorVisible).toBe(true);
  // Mathematical clearance cases, NOT evidence that a browser applied CSS.
  // Include the recorded 1/16px rounding residue at both viewport boundaries.
  for (const [width, height] of [[1440, 1000], [720, 500]]) {
    for (const edge of ['top', 'bottom']) {
      const top = edge === 'top' ? 8 - 0.0625 : height - (8 - 0.0625) - 44.796875;
      const target = { ...recordedFinancial.target, top, bottom: top + 44.796875 };
      const clearance = assessInsightsFocus({ ...recordedFinancial, target, focal: target,
        viewport: { left: 0, right: width, top: 0, bottom: height } });
      expect(clearance.focalVisible).toBe(true); expect(clearance.indicatorVisible).toBe(true);
      expect(clearance.segments).toHaveLength(4);
      if (edge === 'top') expect(clearance.outer.top).toBe(1.9375);
      else expect(clearance.outer.bottom).toBe(height - 1.9375);
    }
  }
  return { cases: 17, hiddenAncestorRejected: !clipped.indicatorVisible, tallDestinationAccepted: tall.indicatorVisible,
    insetBoundaryAccepted: inset.indicatorVisible, outwardBoundaryRejected: !boundaryClipped.indicatorVisible,
    fractionalCancelOutwardRejected: !cancelOutward.indicatorVisible, fractionalCancelInsetAccepted: cancelInset.indicatorVisible,
    fractionalFinancialRejected: !financialOutward.focalVisible && !financialOutward.indicatorVisible,
    insetAloneInsufficient: !financialInset.focalVisible, clearanceCases: 4 };
}

const insightsScrollTargets = '.financial-insights :is(button, select, summary, a[href], [tabindex="-1"]), '
  + 'section[aria-labelledby="snapshot-title"] .compact-label > select';

async function insightsFocus(target: Locator, keyboard = false, destination = false) {
  await expect(target).toBeFocused();
  const measured = await target.evaluate((element, options) => {
    const style = getComputedStyle(element);
    const focal = options.destination ? element.querySelector('h3,h4')! : element;
    const bounds = (node: Element): InsightsRect => {
      const box = node.getBoundingClientRect(); return { left: box.left, right: box.right, top: box.top, bottom: box.bottom };
    };
    const clips = (node: Element) => {
      const result: InsightsClip[] = [];
      for (let ancestor = node.parentElement; ancestor; ancestor = ancestor.parentElement) {
        const box = ancestor.getBoundingClientRect(), css = getComputedStyle(ancestor);
        // Overflow clips at the client/padding box, excluding borders/scrollbars.
        const left = box.left + ancestor.clientLeft, top = box.top + ancestor.clientTop;
        result.push({ bounds: { left, right: left + ancestor.clientWidth, top, bottom: top + ancestor.clientHeight },
          overflowX: css.overflowX, overflowY: css.overflowY });
      }
      return result;
    };
    const rect = bounds(focal), hit = document.elementFromPoint((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2);
    return { sample: { target: bounds(element), focal: rect, viewport: { left: 0, right: innerWidth, top: 0, bottom: innerHeight },
      focalClips: clips(focal), indicatorClips: clips(element), destination: options.destination,
      outlineWidth: parseFloat(style.outlineWidth), outlineOffset: parseFloat(style.outlineOffset), outline: style.outlineStyle },
      usable: hit === focal || focal.contains(hit), focusVisible: element.matches(':focus-visible'),
      target: { tag: element.tagName, text: element.textContent?.trim().slice(0, 160),
        key: element.getAttribute('data-insight-key') }, scroll: { x: scrollX, y: scrollY },
      scrollMargins: [style.scrollMarginTop, style.scrollMarginRight, style.scrollMarginBottom, style.scrollMarginLeft] };
  }, { destination });
  const geometry = { ...measured, ...assessInsightsFocus(measured.sample) };
  await test.info().attach('insights-natural-focus', { contentType: 'application/json', body: JSON.stringify(geometry) });
  expect(geometry.focalVisible).toBe(true); expect(geometry.usable).toBe(true);
  if (keyboard) expect(geometry.focusVisible).toBe(true);
  // Also validate a visible indicator after pointer activation if the browser
  // preserves keyboard modality; absence of pointer-only focus styling is valid.
  if (keyboard || geometry.focusVisible) expect(geometry.indicatorVisible).toBe(true);
  if (keyboard) expect(geometry.scrollMargins).toEqual(['8px', '8px', '8px', '8px']);
}

async function insightsTabTo(page: Page, target: Locator, direction: 'Tab' | 'Shift+Tab' = 'Tab') {
  // Native sequential navigation, bounded even if a regression traps focus.
  for (let step = 0; step < 120; step++) {
    if (await target.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press(direction);
    // Observe each native stop in the approved scope; never move focus/scroll.
    const stop = page.locator(':focus');
    if (await stop.count() === 1 && await stop.evaluate((element, selector) => element.matches(selector), insightsScrollTargets)) {
      await insightsFocus(stop, true, await stop.evaluate(element => element.matches('.insights-record,.insights-viewport')));
    }
  }
  await expect(target, `Reach target within 120 native ${direction} steps`).toBeFocused();
}

async function insightsPage(panel: Locator, category: 'F' | 'D') {
  const viewport = panel.locator('.insights-viewport');
  await expect(panel.locator('.insights-result > .mono')).toHaveText(`Publication 0 · facts 0 · evidence 0 · ${insightsScope}`);
  await expect(viewport).toHaveAttribute('aria-busy', 'false');
  const keys = await viewport.locator('.insights-record').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-insight-key')));
  expect(keys.length).toBeGreaterThan(0); expect(keys.length).toBeLessThanOrEqual(25);
  expect(new Set(keys).size).toBe(keys.length); expect(keys.every(key => key?.startsWith(`${category}|`))).toBe(true);
  return keys;
}

async function insightsLineage(page: Page, panel: Locator, keyboard: boolean, reverseStart = false) {
  const activate = async (control: Locator, key: 'Enter' | 'Space' = 'Enter', reverse = false) => {
    if (keyboard) {
      await insightsTabTo(page, control, reverse ? 'Shift+Tab' : 'Tab'); await insightsFocus(control, true);
      await page.keyboard.press(key);
    } else await control.tap();
  };
  const metrics = panel.locator('.insights-metrics');
  if (await metrics.getAttribute('open') === null) {
    await activate(metrics.locator(':scope > summary')); await expect(metrics).toHaveAttribute('open', '');
  }
  const statement = panel.locator('[data-insight-metric="free_cash_flow"] .insights-statement').filter({
    has: page.getByText('Free cash flow: 15 USD, later FY2025 2025-01-01/2025-12-31/annual; calculated.', { exact: true }),
  });
  // The explicit return leg walks backwards from Snapshot into Insights.
  await activate(statement.getByRole('button', { name: 'Financial evidence 1', exact: true }), 'Enter', reverseStart);
  const arrive = async (key: string) => {
    const record = panel.locator(`[data-insight-key="${key}"]`);
    await insightsFocus(record, keyboard, true); await insightsPage(panel, 'F');
    return record;
  };
  const field = async (record: Locator, name: string, value: string) => {
    if (await record.locator('details').getAttribute('open') === null) {
      await activate(record.locator('summary'), 'Space'); await expect(record.locator('details')).toHaveAttribute('open', '');
    }
    await expect(record.locator('.insights-fields > div').filter({ has: page.getByText(name, { exact: true }) }).locator('dd')).toHaveText(value);
  };
  let record = await arrive(`F|observation|free_cash_flow|later||${insightsWindow}|`);
  await expect(panel.locator('.insights-pagination span')).toHaveText('F · page 5 of 8');
  await field(record, 'data.canonical.value', '15');
  await activate(record.getByRole('button', { name: 'Examine operand · free cash flow · capital expenditures · later', exact: true }), 'Space');
  record = await arrive(`F|operand|free_cash_flow|later|capital_expenditures|${insightsWindow}|`);
  await field(record, 'data.required_metric', 'capital_expenditures');
  await activate(record.getByRole('button', { name: 'Examine observation · capital expenditures · later', exact: true }));
  record = await arrive(`F|observation|capital_expenditures|later||${insightsWindow}|`);
  await field(record, 'data.canonical.value', '5'); await field(record, 'data.canonical.provenance[0].fact_id', '10');
  await activate(record.getByRole('button', { name: 'Examine source', exact: true }), 'Space');
  record = await arrive('F|source|||||10');
  await field(record, 'data.value', '5'); await field(record, 'data.company_cik', '0000900001');
  await field(record, 'data.accession_number', '0000900001-26-100001');
  const link = record.getByRole('link', { name: 'Open official SEC filing', exact: true });
  await expect(link).toHaveAttribute('href', 'https://www.sec.gov/Archives/edgar/data/900001/000090000126100001/0000900001-26-100001-index.html');
  await expect(link).toHaveAttribute('target', '_blank'); await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  if (keyboard) { await insightsTabTo(page, link); await insightsFocus(link, true); }
  // Never activate the source link. All lineage values are fixed expectations.
}

function insightsRequests(scenario: Scenario) { return scenario.ledger.filter(request => request.path === insightsPath); }

test.describe('FIN-DEPTH-01 1B.3 mobile layout', () => {
  // Scoped overrides run once in the existing desktop project; no global mobile
  // testMatch changes or duplicate project executions are needed.
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  test('1B.3 A mobile 390/320 natural evidence focus and bounded pagination', async ({ page, scenario }) => {
    test.setTimeout(90_000);
    await scenario.open(); await scenario.ready();
    const panel = insightsPanel(page);
    await panel.getByRole('button', { name: 'Compare annual periods', exact: true }).tap();
    await expect(panel.locator('.insights-status')).toHaveText('Annual comparison ready. Evidence can be examined below.', { timeout: 35_000 });
    const fetches = insightsRequests(scenario).length;
    const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
    const snapshotText = await snapshot.innerText();
    let originalPages: (string | null)[][] | undefined;
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await insightsLineage(page, panel, false); await insightsLayout(panel, width);
      const viewport = panel.locator('.insights-viewport');
      await panel.getByRole('button', { name: 'Examine financial evidence', exact: true }).tap();
      await insightsFocus(viewport, false, true);
      const first = await insightsPage(panel, 'F');
      const pagination = panel.locator('.insights-pagination span');
      const total = insightsFPageSizes.length;
      await expect(pagination).toHaveText(`F · page 1 of ${total}`);
      expect(first).toHaveLength(insightsFPageSizes[0]);
      const previous = panel.getByRole('button', { name: 'Previous evidence page', exact: true });
      const next = panel.getByRole('button', { name: 'Next evidence page', exact: true });
      await expect(previous).toBeDisabled(); const pages = [first];
      for (let index = 1; index < total; index++) {
        await expect(next).toBeEnabled(); await next.tap(); await insightsFocus(viewport, false, true);
        await expect(pagination).toHaveText(`F · page ${index + 1} of ${total}`);
        const keys = await insightsPage(panel, 'F'); expect(keys).toHaveLength(insightsFPageSizes[index]);
        expect(keys.some(key => pages.flat().includes(key))).toBe(false); pages.push(keys);
      }
      expect(pages.flat()).toHaveLength(45);
      await expect(next).toBeDisabled();
      for (let index = total - 2; index >= 0; index--) {
        await previous.tap(); await insightsFocus(viewport, false, true);
        await expect(pagination).toHaveText(`F · page ${index + 1} of ${total}`);
        expect(await insightsPage(panel, 'F')).toEqual(pages[index]);
      }
      await expect(previous).toBeDisabled();
      if (originalPages) expect(pages).toEqual(originalPages); else originalPages = pages;
      await panel.getByRole('button', { name: 'Examine diagnostic inputs', exact: true }).tap();
      await insightsFocus(viewport, false, true); await insightsPage(panel, 'D');
      await expect(viewport.getByRole('heading', { level: 3 })).toHaveText('Inputs examined and reasons not used — D');
      await expect(panel.getByText('Diagnostic values are not admitted financial results.', { exact: false })).toBeVisible();
      await insightsLayout(panel, width);
      expect(await snapshot.innerText()).toBe(snapshotText);
      expect(insightsRequests(scenario)).toHaveLength(fetches);
    }
    expect(insightsRequests(scenario).filter(request => request.query.get('mode') === 'compare')).toHaveLength(1);
    expect(scenario.violations).toEqual([]);
  });
});

for (const { name, width, height } of [
  { name: 'B-desktop', width: 1440, height: 1000 },
  { name: 'B-reflow', width: 720, height: 500 },
])
test(`FIN-DEPTH-01 1B.3 ${name} native keyboard ${width}x${height} (NOT actual 200% browser zoom)`, async ({ page, scenario }) => {
  test.setTimeout(90_000);
  const adversarial = insightsFocusAdversarialChecks();
  await test.info().attach('insights-focus-adversarial', { contentType: 'application/json', body: JSON.stringify(adversarial) });
  await page.setViewportSize({ width, height });
  await scenario.open(); await scenario.ready();
  const panel = insightsPanel(page), earlier = panel.getByRole('combobox', { name: 'Earlier fiscal year', exact: true });
  const later = panel.getByRole('combobox', { name: 'Later fiscal year', exact: true });
  const compare = panel.getByRole('button', { name: 'Compare annual periods', exact: true });
  // Explicit starting points only. Neither seed is an evidence destination.
  await earlier.focus(); await insightsFocus(earlier, true);
  await page.keyboard.press('Tab'); await insightsFocus(later, true);
  await page.keyboard.press('Tab'); await insightsFocus(compare, true);
  await expect(compare).toHaveCSS('outline-width', '3px');
  await expect(compare).toHaveCSS('outline-style', 'solid');
  await expect(compare).toHaveCSS('outline-offset', '-6px');
  await expect(compare).toHaveCSS('outline-color', await compare.evaluate(element => getComputedStyle(element).color));
  await page.keyboard.press('Shift+Tab'); await insightsFocus(later, true);
  await page.keyboard.press('Shift+Tab'); await insightsFocus(earlier, true);
  await page.keyboard.press('Tab'); await insightsFocus(later, true);
  await page.keyboard.press('Tab'); await insightsFocus(compare, true);
  const held = scenario.hold(request => request.path === insightsPath && request.query.get('mode') === 'compare');
  try {
    await page.keyboard.press('Enter');
    await expect.poll(() => insightsRequests(scenario).filter(request => request.query.get('mode') === 'compare').length).toBe(1);
    await expect(panel.locator('.insights-status')).toHaveAttribute('aria-busy', 'true');
    await expect(compare).toBeDisabled();
    await later.focus(); await page.keyboard.press('Tab');
    const cancel = panel.getByRole('button', { name: 'Cancel annual insights', exact: true });
    await insightsFocus(cancel, true);
    await expect(cancel).toHaveCSS('outline-width', '3px');
    await expect(cancel).toHaveCSS('outline-style', 'solid');
    await expect(cancel).toHaveCSS('outline-offset', '-6px');
    await expect(cancel).toHaveCSS('outline-color', await cancel.evaluate(element => getComputedStyle(element).color));
    await page.keyboard.press('Shift+Tab'); await insightsFocus(later, true);
    held.release();
    await expect(panel.locator('.insights-status')).toHaveText('Annual comparison ready. Evidence can be examined below.', { timeout: 35_000 });
    await insightsFocus(later, true);
    const fetches = insightsRequests(scenario).length;
    const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
    const snapshotText = await snapshot.innerText();
    const policy = panel.locator('.insights-policy');
    await insightsTabTo(page, policy.locator('summary')); await insightsFocus(policy.locator('summary'), true);
    await page.keyboard.press('Enter'); await expect(policy).toHaveAttribute('open', '');
    await insightsFocus(policy.locator('summary'), true);
    await page.keyboard.press('Space'); await expect(policy).not.toHaveAttribute('open');
    await insightsFocus(policy.locator('summary'), true);
    // Each independently scheduled width covers forward arrival and a second
    // reverse arrival from Snapshot. Failure at one width cannot skip the other.
    for (const reverseStart of [false, true]) {
      await insightsLineage(page, panel, true, reverseStart);
      const financial = panel.getByRole('button', { name: 'Examine financial evidence', exact: true });
      await insightsTabTo(page, financial, 'Shift+Tab'); await insightsFocus(financial, true); await page.keyboard.press('Enter');
      const viewport = panel.locator('.insights-viewport'); await insightsFocus(viewport, true, true);
      const first = await insightsPage(panel, 'F');
      await expect(panel.locator('.insights-pagination span')).toHaveText('F · page 1 of 8');
      expect(first).toHaveLength(insightsFPageSizes[0]);
      const next = panel.getByRole('button', { name: 'Next evidence page', exact: true });
      await insightsTabTo(page, next, 'Shift+Tab'); await insightsFocus(next, true); await page.keyboard.press('Space');
      await insightsFocus(viewport, true, true);
      const second = await insightsPage(panel, 'F'); expect(second).not.toEqual(first);
      expect(second).toHaveLength(insightsFPageSizes[1]); expect(second.some(key => first.includes(key))).toBe(false);
      await expect(panel.locator('.insights-pagination span')).toHaveText('F · page 2 of 8');
      const previous = panel.getByRole('button', { name: 'Previous evidence page', exact: true });
      await insightsTabTo(page, previous, 'Shift+Tab'); await insightsFocus(previous, true); await page.keyboard.press('Enter');
      await insightsFocus(viewport, true, true); expect(await insightsPage(panel, 'F')).toEqual(first);
      await expect(previous).toBeDisabled();
      const diagnostic = panel.getByRole('button', { name: 'Examine diagnostic inputs', exact: true });
      await insightsTabTo(page, diagnostic, 'Shift+Tab'); await insightsFocus(diagnostic, true); await page.keyboard.press('Space');
      await insightsFocus(viewport, true, true); await insightsPage(panel, 'D');
      await expect(viewport.getByRole('heading', { level: 3 })).toHaveText('Inputs examined and reasons not used — D');
      await expect(panel.getByText('Diagnostic values are not admitted financial results.', { exact: false })).toBeVisible();
      await expect(diagnostic).toHaveAttribute('aria-pressed', 'true');
      await expect(financial).toHaveAttribute('aria-pressed', 'false');
      await insightsTabTo(page, financial, 'Shift+Tab'); await insightsFocus(financial, true); await page.keyboard.press('Enter');
      await insightsFocus(viewport, true, true); expect(await insightsPage(panel, 'F')).toEqual(first);
      await expect(panel.locator('.insights-pagination span')).toHaveText('F · page 1 of 8');
      await expect(financial).toHaveAttribute('aria-pressed', 'true');
      // Escape backwards to the evidence disclosure and forwards into the next
      // product panel. Native Tab must cross the boundary without a focus trap.
      await insightsTabTo(page, panel.locator('.insights-evidence > summary'), 'Shift+Tab');
      await insightsFocus(panel.locator('.insights-evidence > summary'), true);
      const snapshotPeriod = page.getByRole('combobox', { name: 'Snapshot period', exact: true });
      await insightsTabTo(page, snapshotPeriod); await insightsFocus(snapshotPeriod, true);
      if (width === 720) await insightsLayout(panel, width);
      expect(await snapshot.innerText()).toEqual(snapshotText);
      expect(insightsRequests(scenario)).toHaveLength(fetches);
    }
    expect(scenario.violations).toEqual([]);
  } finally {
    // Also runs on failed focus assertions/timeouts. Existing auto-fixture keeps
    // its page-close-before-unroute teardown and releases registered gates again.
    held.release();
  }
});
