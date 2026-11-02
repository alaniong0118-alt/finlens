import type { Locator, Page, TestInfo } from '@playwright/test';
import { test, expect, expectedRequest, completedRequests, publicationCompletions, publicationHeaderCancellations,
  replayCancellations, expectFullLedger, lifecycle, annualRequestCursor, captureFocusPaint, assessFocusPaint,
  type ExpectedLedger } from './fixtures/annual-period-browser';
import { captureBalanceFocus } from './fixtures/balance-date-acceptance-20261102';
import type { Scenario } from './fixtures/browser';
import * as data from './fixtures/data';
import { cashMetrics, cashWindows, cashExact, cashMissingReason, cashPath, cashMetric, cashReply, cashRequests } from './fixtures/cash-flow-window-acceptance';

test.use({ deviceScaleFactor: 1 });
const panel = (page: Page) => page.getByRole('region', { name: 'Cash flow by reported duration', exact: true });
const grid = (page: Page) => panel(page).getByRole('region', { name: 'Cash flow metrics by exact reported window', exact: true });
const load = (page: Page) => panel(page).getByRole('button', { name: 'Load cash flow histories', exact: true });
const duration = (page: Page) => panel(page).getByRole('combobox', { name: 'Duration', exact: true });
const choose = (page: Page, w: { start: string; end: string }) => panel(page).getByRole('checkbox', { name: `${w.start} – ${w.end}`, exact: true });
async function open(page: Page, scenario: Scenario): Promise<ExpectedLedger> {
  await scenario.open(); await scenario.ready(); await expect(panel(page)).toContainText('Publication version 0');
  const expected: ExpectedLedger = { completed: [...completedRequests([expectedRequest('/companies'), expectedRequest('/capabilities')]),
    ...publicationCompletions()], cancelled: replayCancellations(), pending: [], cancelledAfterHeaders: [] };
  await expectFullLedger(scenario, expected); return expected;
}
async function addLoad(page: Page, expected: ExpectedLedger, ticker = 'AAA', kind: 'half_year' | 'nine_months' = 'half_year', pin = 0) {
  await load(page).click(); expected.completed.push(...completedRequests(cashRequests(ticker, kind, pin)));
  await expect(panel(page).getByRole('checkbox')).toHaveCount(5);
}
async function attachFocus(target: Locator, info: TestInfo, name: string, geometry: unknown) {
  const body = JSON.stringify(geometry);
  expect(Buffer.byteLength(body)).toBeLessThanOrEqual(32768);
  await info.attach(`cash-flow-${name}-geometry`, { body, contentType: 'application/json' });
  // A viewport screenshot preserves native focus/scroll; no locator auto-scroll.
  const raster = await target.page().screenshot({ fullPage: false, type: 'png', scale: 'device',
    animations: 'allow', caret: 'initial', timeout: 3000 });
  expect(raster.length).toBeGreaterThan(0); expect(raster.length).toBeLessThanOrEqual(2 * 1024 * 1024);
  await info.attach(`cash-flow-${name}-focus`, { body: raster, contentType: 'image/png' });
}
async function expectOutsetFocus(target: Locator, info: TestInfo, name: string) {
  await expect(target).toBeFocused();
  const geometry = await target.evaluate(captureFocusPaint), contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  await attachFocus(target, info, name, { geometry, contrast });
  expect(geometry.visible).toBe(true); expect(geometry.outline).not.toBe('none'); expect(geometry.width).toBeGreaterThanOrEqual(3);
  expect(contrast.sufficient).toBe(true);
  expect(Object.values(geometry.rect).every(Number.isFinite)).toBe(true);
  expect(geometry.rect.right).toBeGreaterThan(geometry.rect.left); expect(geometry.rect.bottom).toBeGreaterThan(geometry.rect.top);
  expect(geometry.rect.left - geometry.extent).toBeGreaterThanOrEqual(geometry.clip.left);
  expect(geometry.rect.right + geometry.extent).toBeLessThanOrEqual(geometry.clip.right);
  expect(geometry.rect.top - geometry.extent).toBeGreaterThanOrEqual(geometry.clip.top);
  expect(geometry.rect.bottom + geometry.extent).toBeLessThanOrEqual(geometry.clip.bottom);
}
async function expectInsetFocus(target: Locator, info: TestInfo, name: string, region = false) {
  await expect(target).toBeFocused();
  const geometry = await target.evaluate(captureBalanceFocus), contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  await attachFocus(target, info, name, { geometry, contrast });
  expect(geometry.dpr).toBe(1); expect(geometry.visible).toBe(true); expect(geometry.width).toBeGreaterThanOrEqual(3);
  expect(geometry.outline).not.toBe('none'); expect(contrast.sufficient).toBe(true);
  expect(geometry.surfaces.every(surface => surface.exposed)).toBe(true);
  expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewport.width);
  expect(Object.values(geometry.rect).concat([geometry.extent]).every(Number.isFinite)).toBe(true);
  expect(geometry.rect.height).toBeGreaterThanOrEqual(44);
  const box = { left: geometry.rect.left - geometry.extent, right: geometry.rect.right + geometry.extent,
    top: geometry.rect.top - geometry.extent, bottom: geometry.rect.bottom + geometry.extent };
  expect(box.left).toBeGreaterThan(-0.5); expect(box.right).toBeLessThan(geometry.viewport.width + 0.5);
  if (region) {
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
async function tabTo(target: Locator) {
  for (let i = 0; i < 28; i++) { await target.page().keyboard.press('Tab'); if (await target.evaluate(e => e === document.activeElement)) return; }
  throw new Error('Cash flow keyboard traversal exceeded 28 native Tab steps');
}

// Two explicit viewports under desktop-chromium: six bounded cases without a shared Playwright config change.
for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test.describe(`cash-flow window acceptance · ${viewport.width}px`, () => {
    test.use({ viewport, isMobile: viewport.width === 390, hasTouch: viewport.width === 390 });
    test('exact half-year windows, selection and keyboard sources', async ({ page, annualScenario: scenario }, info) => {
      scenario.overrides.push(request => cashReply(request, scenario));
      const expected = await open(page, scenario), windows = cashWindows('half_year');
      await addLoad(page, expected); await expectFullLedger(scenario, expected);
      await choose(page, windows[0]).focus(); await page.keyboard.press('Tab');
      await expectOutsetFocus(choose(page, windows[1]), info, 'window-selector'); await page.keyboard.press('Space');
      await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Space');
      await expect(grid(page).locator('thead th')).toHaveCount(3);
      await expect(grid(page).locator('thead th').nth(1)).toHaveText(`${windows[0].start} – ${windows[0].end}`);
      await expect(grid(page).locator('thead th').nth(2)).toHaveText(`${windows[1].start} – ${windows[1].end}`);
      await expect(grid(page).locator('tbody tr').first().locator('td').first()).toContainText('Not present in loaded history');
      await expect(grid(page).locator('tbody tr').first().locator('td').nth(1)).toContainText(cashExact.AAA);
      await choose(page, windows[2]).check(); await choose(page, windows[3]).check();
      await expect(grid(page).locator('thead th')).toHaveCount(5); await expect(choose(page, windows[4])).toBeDisabled();
      await choose(page, windows[3]).uncheck(); await expect(choose(page, windows[4])).toBeEnabled();
      await choose(page, windows[2]).uncheck();
      await choose(page, windows[4]).focus(); await page.keyboard.press('Tab'); await expectInsetFocus(grid(page), info, 'table-region', true);
      const scroll = await grid(page).evaluate(e => ({ initial: e.scrollLeft, overflow: e.scrollWidth > e.clientWidth }));
      await page.keyboard.press('ArrowRight');
      if (viewport.width === 390) expect(scroll.overflow).toBe(true);
      if (scroll.overflow) await expect.poll(() => grid(page).evaluate(e => e.scrollLeft)).toBeGreaterThan(scroll.initial);
      const source = grid(page).locator('tbody tr').first().locator('td').nth(1).locator('details.provenance');
      await tabTo(source.locator(':scope > summary')); await expectInsetFocus(source.locator(':scope > summary'), info, 'source-summary');
      await page.keyboard.press('Space'); await expect(source).toHaveAttribute('open', '');
      await expect(source).toContainText(`Exact API value: ${cashExact.AAA} USD`); await expect(source).toContainText(`Accession ${data.accession('AAA')}`);
      const link = source.getByRole('link', { name: 'Open official SEC filing ↗', exact: true }); await tabTo(link);
      await expectInsetFocus(link, info, 'source-link'); await expect(link).toHaveAttribute('href', data.secUrl('AAA')); await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
      const fcf = grid(page).locator('tbody tr').last().locator('td').nth(1).locator('details.provenance');
      await fcf.locator(':scope > summary').click(); await expect(fcf).toContainText('operating cash flow: ' + cashExact.AAA + ' USD');
      await expect(fcf).toContainText('capital expenditures: 10.0000000000001 USD');
      const layout = await panel(page).evaluate(e => { const r = e.getBoundingClientRect(), table = e.querySelector('.comparison-scroll')!; return {
        width: innerWidth, pageWidth: document.documentElement.scrollWidth, left: r.left, right: r.right,
        overflowValues: [...e.querySelectorAll('.metric-value')].filter(v => v.scrollWidth > v.clientWidth + 1).length,
        scrollWidth: table.scrollWidth, clientWidth: table.clientWidth }; });
      expect(layout.width).toBe(viewport.width); expect(layout.pageWidth).toBeLessThanOrEqual(viewport.width);
      expect(layout.left).toBeGreaterThanOrEqual(0); expect(layout.right).toBeLessThanOrEqual(viewport.width); expect(layout.overflowValues).toBe(0);
      await info.attach('cash-flow-layout', { body: JSON.stringify(layout), contentType: 'application/json' });
      await info.attach('cash-flow-comparison', { body: await page.screenshot({ fullPage: false }), contentType: 'image/png' });
      await expectFullLedger(scenario, expected);
    });

    test('missing, failed and missing-pin histories; clear, retry and publication mismatch', async ({ page, annualScenario: scenario }) => {
      let phase: 'failure' | 'cancel' | 'missing' | 'normal' | 'mismatch' = 'failure', mismatchCursor = 0;
      const held = scenario.hold(request => phase === 'cancel' && !!cashMetric(request), request => cashReply(request, scenario)!);
      scenario.overrides.push(async request => {
        if (!cashMetric(request)) return;
        if (request.ticker === 'AAA' && cashMetric(request) === 'free_cash_flow') {
          if (phase === 'failure') return { status: 503, body: { detail: 'Synthetic history failure.' }, version: '0' };
          if (phase === 'missing') return { ...cashReply(request, scenario), version: null };
          if (phase === 'mismatch') {
            await expect.poll(() => lifecycle(scenario).rows.filter(row => row.id > mismatchCursor
              && cashRequests().slice(0, 2).includes(row.request) && row.state === 'completed' && row.response?.status === 200).length).toBe(2);
            scenario.versions.AAA = 1;
            return { ...cashReply(request, { versions: { AAA: 0 } }), version: '1' };
          }
        }
        return cashReply(request, scenario);
      });
      const expected = await open(page, scenario), windows = cashWindows('half_year');
      await load(page).click(); expected.completed.push(...completedRequests(cashRequests().slice(0, 2)),
        ...completedRequests([cashRequests()[2]], 503, '0'));
      await expect(panel(page).getByRole('checkbox')).toHaveCount(5);
      await choose(page, windows[0]).check(); await choose(page, windows[1]).check();
      const rows = grid(page).locator('tbody tr');
      await expect(rows.nth(0).locator('td').first()).toContainText('Not present in loaded history');
      await expect(rows.nth(1).locator('td').first()).toContainText(cashMissingReason);
      await expect(rows.nth(1).locator('em')).toHaveCount(0); await expect(rows.nth(2)).toContainText('History not verified');
      await expect(rows.nth(2)).toContainText('Synthetic history failure.'); await expectFullLedger(scenario, expected);
      await panel(page).getByRole('button', { name: 'Clear cash flow comparison', exact: true }).focus(); await page.keyboard.press('Enter');
      await expect(grid(page)).toHaveCount(0); await expectFullLedger(scenario, expected);
      phase = 'cancel'; await load(page).click(); expected.pending.push(...cashRequests()); await expectFullLedger(scenario, expected);
      await panel(page).getByRole('button', { name: 'Cancel cash flow request', exact: true }).click();
      phase = 'missing'; held.release(); expected.cancelled.push(...expected.pending.splice(0)); await expectFullLedger(scenario, expected);
      await load(page).click(); expected.completed.push(...completedRequests(cashRequests().slice(0, 2)),
        ...completedRequests([cashRequests()[2]], 200, '0').map(item => ({ ...item, version: null })));
      await expect(panel(page).getByText('1 metric history could not be verified.', { exact: false })).toBeVisible();
      await choose(page, windows[0]).check(); await choose(page, windows[1]).check(); await expect(grid(page).locator('tbody tr').last()).toContainText('History not verified');
      await expectFullLedger(scenario, expected);
      phase = 'normal'; await addLoad(page, expected); await expectFullLedger(scenario, expected);
      await choose(page, windows[0]).check(); await choose(page, windows[1]).check(); await expect(grid(page).locator('tbody tr').last()).not.toContainText('History not verified');
      phase = 'mismatch'; mismatchCursor = annualRequestCursor(scenario); await load(page).click();
      expected.completed.push(...completedRequests(cashRequests().slice(0, 2)), ...completedRequests([cashRequests()[2]], 200, '1'));
      expected.completed.push(...publicationCompletions('AAA', 1), ...completedRequests([expectedRequest('/companies')]));
      expected.cancelledAfterHeaders.push(...publicationHeaderCancellations('AAA', 1)); expected.cancelled.push(...replayCancellations('AAA', 1, false));
      await expect(panel(page)).toContainText('Publication version 1'); await expect(grid(page)).toHaveCount(0);
      await expect(panel(page).getByRole('checkbox')).toHaveCount(0); await expectFullLedger(scenario, expected);
      expect(annualRequestCursor(scenario)).toBeGreaterThan(mismatchCursor);
    });

    test('nine-month and company switches ignore late stale responses', async ({ page, annualScenario: scenario }) => {
      const path = cashPath('AAA', cashMetrics[0]); await scenario.ignoreTransportAbort(path);
      let holdHalf = true, holdNine = true;
      const half = scenario.hold(r => holdHalf && r.path === path && r.query.get('period') === 'half_year',
        () => ({ status: 409, code: 'DATA_VERSION_CHANGED', version: '9', body: { detail: 'Retired half-year response' } }));
      const nine = scenario.hold(r => holdNine && r.path === path && r.query.get('period') === 'nine_months',
        () => ({ status: 409, code: 'DATA_VERSION_CHANGED', version: '9', body: { detail: 'Retired nine-month response' } }));
      scenario.overrides.push(request => cashReply(request, scenario));
      try {
        const expected = await open(page, scenario);
        await load(page).click(); expected.pending.push(cashRequests()[0]); expected.completed.push(...completedRequests(cashRequests().slice(1)));
        await expectFullLedger(scenario, expected);
        await duration(page).selectOption('nine_months'); await expect(grid(page)).toHaveCount(0); await expectFullLedger(scenario, expected);
        await load(page).click(); expected.pending.push(cashRequests('AAA', 'nine_months')[0]); expected.completed.push(...completedRequests(cashRequests('AAA', 'nine_months').slice(1)));
        await expectFullLedger(scenario, expected);
        annualRequestCursor(scenario); await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB'); await scenario.ready('BBB');
        expected.completed.push(...publicationCompletions('BBB')); expected.cancelled.push(...replayCancellations('BBB'));
        expected.cancelledAfterHeaders.push(...publicationHeaderCancellations('BBB')); await expectFullLedger(scenario, expected);
        await duration(page).selectOption('nine_months'); await addLoad(page, expected, 'BBB', 'nine_months');
        const b = cashWindows('nine_months'); await choose(page, b[0]).check(); await choose(page, b[1]).check();
        await expect(grid(page).locator('caption')).toContainText('BBB'); await expect(grid(page)).toContainText(cashExact.BBB);
        await expect(grid(page).locator('thead th').nth(2)).toContainText(`${b[1].start} – ${b[1].end}`); await expectFullLedger(scenario, expected);
        annualRequestCursor(scenario); await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('AAA'); await scenario.ready();
        expected.completed.push(...publicationCompletions()); expected.cancelled.push(...replayCancellations());
        holdHalf = false; holdNine = false; await addLoad(page, expected);
        const a = cashWindows('half_year'); await choose(page, a[0]).check(); await choose(page, a[1]).check();
        half.release(); nine.release();
        await expect.poll(() => scenario.abortedDeliveries(path, '0', 409, '?period=half_year&limit=12')).toBe(1);
        await expect.poll(() => scenario.abortedDeliveries(path, '0', 409, '?period=nine_months&limit=12')).toBe(1);
        expected.completed.push(...completedRequests(expected.pending.splice(0), 409, '9', 'DATA_VERSION_CHANGED'));
        await expect(grid(page).locator('caption')).toContainText('AAA'); await expect(grid(page)).toContainText(cashExact.AAA);
        await expect(grid(page)).not.toContainText(cashExact.BBB); await expect(panel(page)).toContainText('Publication version 0');
        await expectFullLedger(scenario, expected);
      } finally { half.release(); nine.release(); }
    });
  });
}
