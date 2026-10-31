import type { Locator, Page } from '@playwright/test';
import { test, expect, annualPeriods, missingAnnualReason, expectedRequest,
  selectedRequests, expectFullLedger, completedRequests, publicationCompletions, publicationHeaderCancellations, replayCancellations,
  expectReplayGenerations, waitForCompletedRequest, assessFocusPaint, captureFocusPaint, type ExpectedLedger } from './fixtures/annual-period-browser';
import { type Scenario } from './fixtures/browser';

const panel = (page: Page) => page.getByRole('region', { name: 'Annual period comparison', exact: true });
const grid = (page: Page) => panel(page).getByRole('region', { name: 'Selected company annual period metrics', exact: true });
const choose = (page: Page, year: number) => panel(page).getByRole('checkbox', { name: `FY${year}`, exact: true });
const compare = (page: Page) => panel(page).getByRole('button', { name: 'Compare selected annual periods', exact: true });
const row = (page: Page, name: string) => grid(page).getByRole('row').filter({ has: page.getByRole('rowheader').filter({ hasText: new RegExp(`^${name}(?:$|Annual|Fiscal|Revenue|[0-9])`) }) });
const disclosure = (page: Page, metric: string, year: number, operands = false) => grid(page).locator('summary')
  .filter({ hasText: `${metric} FY${year}: ${operands ? 'operand periods and bases' : 'sources and details'}` });

async function open(page: Page, scenario: Scenario) {
  await scenario.open(); await scenario.ready();
  await expect(panel(page).getByRole('status')).toHaveText('Choose two to four annual periods, then compare.');
  const expected: ExpectedLedger = { completed: [...completedRequests([expectedRequest('/companies'), expectedRequest('/capabilities')]),
    ...publicationCompletions()], cancelled: replayCancellations(), pending: [], cancelledAfterHeaders: [] };
  await expectFullLedger(scenario, expected); expectReplayGenerations(scenario, 0);
  await expect(panel(page)).toContainText('Publication version 0');
  expect(await panel(page).getByRole('checkbox').evaluateAll(elements => elements.map(element => (element as HTMLInputElement).value)))
    .toEqual(['2025', '2024', '2023', '2022']);
  await expect(grid(page)).toHaveCount(0); return expected;
}
async function expectFullFocus(control: Locator) {
  const geometry = await control.evaluate(captureFocusPaint);
  const contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  const diagnostic = JSON.stringify({ geometry, contrast }, null, 2);
  expect(Buffer.byteLength(diagnostic)).toBeLessThanOrEqual(65536);
  await test.info().attach(`annual-focus-${test.info().attachments.length}`, { body: diagnostic, contentType: 'application/json' });
  await expect(control).toBeFocused();
  expect(geometry.visible).toBe(true); expect(geometry.outline).not.toBe('none'); expect(geometry.width).toBeGreaterThan(0);
  expect(geometry.rect.left - geometry.extent, JSON.stringify(geometry)).toBeGreaterThanOrEqual(geometry.clip.left);
  expect(geometry.rect.right + geometry.extent, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clip.right);
  expect(geometry.rect.top - geometry.extent, JSON.stringify(geometry)).toBeGreaterThanOrEqual(geometry.clip.top);
  expect(geometry.rect.bottom + geometry.extent, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clip.bottom);
  expect(contrast.sufficient, diagnostic).toBe(true);
}
async function tabTo(page: Page, target: Locator, maximum = 18) {
  for (let step = 0; step < maximum; step++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate(element => element === document.activeElement)) { await expectFullFocus(target); return; }
  }
  throw new Error('Native Tab did not reach the expected annual-grid control');
}
async function selectPair(page: Page) { await choose(page, 2025).check(); await choose(page, 2024).check(); }

test('annual periods: two/four years, shared sources and native keyboard @desktop-only', async ({ page, annualScenario: scenario }, info) => {
  const expected = await open(page, scenario);
  await expect(panel(page).getByRole('checkbox')).toHaveCount(4); await expect(compare(page)).toBeDisabled();
  await page.getByRole('link', { name: 'Annual period comparison', exact: true }).click();
  await choose(page, 2025).focus(); await page.keyboard.press('Tab'); await expectFullFocus(choose(page, 2024));
  await page.keyboard.press('Space'); await page.keyboard.press('Shift+Tab'); await expectFullFocus(choose(page, 2025));
  await page.keyboard.press('Space'); await expect(compare(page)).toBeEnabled();
  await expectFullLedger(scenario, expected);
  await tabTo(page, compare(page)); await page.keyboard.press('Space'); expected.completed.push(...completedRequests(selectedRequests([2025, 2024])));
  await expect(grid(page).getByRole('rowheader')).toHaveCount(11); await expectFullLedger(scenario, expected);
  await expect(row(page, 'Revenue').locator('.metric-value')).toHaveText(['$5B', '$4B']);
  await expect(row(page, 'Revenue YoY').locator('.metric-value')).toHaveText(['25%', '100%']);
  // Only native Tab controls scrolling after activation; no injected focus fix.
  await tabTo(page, disclosure(page, 'Revenue', 2025)); await page.keyboard.press('Space');
  await expect(disclosure(page, 'Revenue', 2025).locator('..')).toHaveAttribute('open', '');
  const firstLink = disclosure(page, 'Revenue', 2025).locator('..').getByRole('link', { name: /Open official SEC filing/ });
  await page.keyboard.press('Tab'); await expectFullFocus(firstLink);
  await expect(firstLink).toHaveAttribute('href', annualPeriods('AAA', 2025).metrics.revenue.provenance[0].sec_url);
  await tabTo(page, disclosure(page, 'Revenue YoY', 2025)); await page.keyboard.press('Space');
  const shared = annualPeriods('AAA', 2024).metrics.revenue.provenance[0];
  await expect(disclosure(page, 'Revenue YoY', 2025).locator('..')).toContainText(`Fact ${shared.fact_id}`);
  await tabTo(page, disclosure(page, 'Revenue YoY', 2025, true)); await page.keyboard.press('Space');
  const operands = disclosure(page, 'Revenue YoY', 2025, true).locator('..');
  await expect(operands.locator('.details-body > p').nth(0)).toContainText('current · revenue: Annual');
  await expect(operands.locator('.details-body > p').nth(0)).toContainText('FY2025');
  await expect(operands.locator('.details-body > p').nth(1)).toContainText('prior · revenue: Annual');
  await expect(operands.locator('.details-body > p').nth(1)).toContainText('FY2024');
  await expect(operands).toContainText('Revenue basis: total_revenue');
  await tabTo(page, disclosure(page, 'Revenue YoY', 2024)); await page.keyboard.press('Space');
  await expect(disclosure(page, 'Revenue YoY', 2024).locator('..')).toContainText(`Fact ${shared.fact_id}`);
  await tabTo(page, disclosure(page, 'Revenue YoY', 2024, true)); await page.keyboard.press('Space');
  const earlierOperands = disclosure(page, 'Revenue YoY', 2024, true).locator('..').locator('.details-body > p');
  await expect(earlierOperands.nth(0)).toContainText('FY2024'); await expect(earlierOperands.nth(1)).toContainText('FY2023');
  await expect(earlierOperands.nth(0)).toContainText('Revenue basis: total_revenue');
  await expect(earlierOperands.nth(1)).toContainText('Revenue basis: total_revenue');
  await expectFullLedger(scenario, expected);
  await choose(page, 2023).check(); await choose(page, 2022).check(); await expect(grid(page)).toHaveCount(0);
  await compare(page).click(); expected.completed.push(...completedRequests(selectedRequests([2025, 2024, 2023, 2022])));
  await expect(grid(page).getByRole('columnheader')).toHaveCount(5); await expectFullLedger(scenario, expected);
  await expect(row(page, 'Revenue').getByRole('cell').nth(3)).toContainText(missingAnnualReason);
  await expect(row(page, 'Gross margin').getByRole('cell').nth(2)).toContainText('Not applicable — excluded');
  await expect(grid(page)).toContainText('Jan 1, 2025'); await expect(grid(page)).toContainText('Dec 31, 2024');
  await expect(compare(page)).toBeEnabled();
  await info.attach('annual-period-desktop', { body: await page.screenshot(), contentType: 'image/png' });
});

test('annual periods: cancel, company scope and actual publication invalidation @desktop-only', async ({ page, annualScenario: scenario }) => {
  const expected = await open(page, scenario); await selectPair(page);
  let holding = true;
  const held = scenario.hold(request => holding && request.path.endsWith('/financials/annual') && request.query.size === 1,
    request => ({ body: annualPeriods(request.ticker!, Number(request.query.get('fiscal_year'))), version: request.pin }));
  await compare(page).click(); expected.pending.push(...selectedRequests([2025, 2024])); await expectFullLedger(scenario, expected);
  await panel(page).getByRole('button', { name: 'Cancel annual comparison', exact: true }).click();
  holding = false; held.release(); expected.cancelled.push(...expected.pending.splice(0)); await expect(grid(page)).toHaveCount(0);
  await expect(panel(page).getByRole('status')).toContainText('cancelled'); await expectFullLedger(scenario, expected);
  const betaStart = scenario.ledger.length;
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB');
  await scenario.ready('BBB'); expected.completed.push(...publicationCompletions('BBB')); expected.cancelled.push(...replayCancellations('BBB'));
  expected.cancelledAfterHeaders.push(...publicationHeaderCancellations('BBB'));
  await expectFullLedger(scenario, expected); expectReplayGenerations(scenario, betaStart, 'BBB');
  await expect(panel(page).getByRole('checkbox', { checked: true })).toHaveCount(0);
  let holdingOther = true;
  const otherHeld = scenario.hold(request => holdingOther && request.ticker === 'BBB' && request.path.endsWith('/financials/annual') && request.query.size === 1,
    request => ({ body: annualPeriods('BBB', Number(request.query.get('fiscal_year'))), version: '0' }));
  await selectPair(page); await compare(page).click(); expected.pending.push(...selectedRequests([2025, 2024], 'BBB'));
  await expectFullLedger(scenario, expected);
  const alphaStart = scenario.ledger.length;
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('AAA');
  holdingOther = false; otherHeld.release(); expected.cancelled.push(...expected.pending.splice(0));
  expected.completed.push(...publicationCompletions()); expected.cancelled.push(...replayCancellations()); await scenario.ready();
  await expect(panel(page).getByRole('status')).toHaveText('Choose two to four annual periods, then compare.');
  await expect(grid(page)).toHaveCount(0); await expectFullLedger(scenario, expected); expectReplayGenerations(scenario, alphaStart);
  let mismatch = true;
  scenario.overrides.unshift(async request => {
    if (!mismatch || request.ticker !== 'AAA' || !request.path.endsWith('/financials/annual') || request.query.get('fiscal_year') !== '2024') return;
    // Deliver one verified old-pin column before rejection. The actual provider
    // must still hide it and reconcile; do not race two different HTTP outcomes.
    await waitForCompletedRequest(scenario, selectedRequests([2025])[0]);
    mismatch = false; scenario.versions.AAA = 1;
    return { status: 409, code: 'DATA_VERSION_CHANGED', version: '1' };
  });
  await selectPair(page); const repinStart = scenario.ledger.length; await compare(page).click();
  expected.completed.push(...completedRequests(selectedRequests([2025])), ...completedRequests(selectedRequests([2024]), 409, '1', 'DATA_VERSION_CHANGED'));
  expected.completed.push(...publicationCompletions('AAA', 1), ...completedRequests([expectedRequest('/companies')]));
  expected.cancelledAfterHeaders.push(...publicationHeaderCancellations('AAA', 1));
  expected.cancelled.push(...replayCancellations('AAA', 1, false));
  await expect(page.getByRole('region', { name: 'Data freshness', exact: true })).toContainText('version 1');
  await expect(panel(page).getByRole('status')).toHaveText('Choose two to four annual periods, then compare.');
  await expect(grid(page)).toHaveCount(0); await expect(panel(page).getByRole('checkbox', { checked: true })).toHaveCount(0);
  await expectFullLedger(scenario, expected); expectReplayGenerations(scenario, repinStart, 'AAA', 1, false);
});

test('annual periods: 390px touch, four-year missing data and horizontal scroll @mobile-only', async ({ page, annualScenario: scenario }, info) => {
  const expected = await open(page, scenario); expect(page.viewportSize()).toEqual({ width: 390, height: 844 });
  await choose(page, 2025).tap(); await choose(page, 2024).tap(); await compare(page).tap();
  expected.completed.push(...completedRequests(selectedRequests([2025, 2024]))); await expect(row(page, 'Revenue YoY').locator('.metric-value')).toHaveText(['25%', '100%']);
  await expectFullLedger(scenario, expected);
  await disclosure(page, 'Revenue', 2025).tap();
  await expect(disclosure(page, 'Revenue', 2025).locator('..')).toHaveAttribute('open', '');
  await expect(disclosure(page, 'Revenue', 2025).locator('..')).toContainText('Exact API value: 5000000000 USD');
  await expectFullLedger(scenario, expected);
  await choose(page, 2023).tap(); await choose(page, 2022).tap(); await compare(page).tap();
  expected.completed.push(...completedRequests(selectedRequests([2025, 2024, 2023, 2022])));
  await expect(grid(page).getByRole('columnheader')).toHaveCount(5); await expectFullLedger(scenario, expected);
  const scroller = grid(page), narrowTarget = disclosure(page, 'Revenue', 2024);
  const narrowBefore = await scroller.evaluate(element => {
    const box = element.getBoundingClientRect(); return { width: element.clientWidth, scrollWidth: element.scrollWidth,
      initial: element.scrollLeft, viewportRight: box.left + element.clientLeft + element.clientWidth };
  });
  expect(narrowBefore.scrollWidth).toBeGreaterThan(narrowBefore.width);
  expect(await narrowTarget.evaluate(element => element.getBoundingClientRect().right)).toBeGreaterThan(narrowBefore.viewportRight);
  // Start from the existing submit control. Only real Tab reveals the later
  // column; neither the target nor its scroller receives an injected focus fix.
  await compare(page).focus(); await tabTo(page, narrowTarget);
  await expect.poll(() => scroller.evaluate(element => element.scrollLeft)).toBeGreaterThan(narrowBefore.initial);
  await page.keyboard.press('Space'); await expect(narrowTarget.locator('..')).toHaveAttribute('open', '');
  await expectFullFocus(narrowTarget); await expectFullLedger(scenario, expected);
  await scroller.locator('thead').scrollIntoViewIfNeeded();
  const geometry = await scroller.evaluate(element => { const box = element.getBoundingClientRect(); return {
    x: box.x, y: box.y, width: element.clientWidth, scrollWidth: element.scrollWidth, initial: element.scrollLeft,
  }; });
  expect(geometry.scrollWidth).toBeGreaterThan(geometry.width);
  const client = await page.context().newCDPSession(page);
  try {
    const start = geometry.x + geometry.width * 0.8, end = geometry.x + geometry.width * 0.2;
    const y = Math.min(700, Math.max(120, geometry.y + 110));
    await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: start, y }] });
    for (let step = 1; step <= 8; step++) {
      await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: start + (end - start) * step / 8, y }] });
      await page.waitForTimeout(16);
    }
    await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await expect.poll(() => scroller.evaluate(element => element.scrollLeft)).toBeGreaterThan(geometry.initial);
  } finally { await client.detach(); }
  const lastCell = row(page, 'Revenue').getByRole('cell').nth(3);
  await lastCell.scrollIntoViewIfNeeded(); await expect(lastCell).toContainText(missingAnnualReason);
  const finalColumn = await lastCell.evaluate(element => {
    const box = element.getBoundingClientRect(), container = element.closest('.comparison-scroll')!;
    const outer = container.getBoundingClientRect();
    return { left: box.left, right: box.right, minimum: outer.left + container.clientLeft,
      maximum: outer.left + container.clientLeft + container.clientWidth };
  });
  expect(finalColumn.left).toBeGreaterThanOrEqual(finalColumn.minimum);
  expect(finalColumn.right).toBeLessThanOrEqual(finalColumn.maximum);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await expectFullLedger(scenario, expected);
  await info.attach('annual-period-390px', { body: await page.screenshot(), contentType: 'image/png' });
});
