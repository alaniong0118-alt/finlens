import type { BrowserContext, Locator, Page } from '@playwright/test';
import { test, expect, origin, type ApiRequest, type Scenario } from './fixtures/browser';
import * as data from './fixtures/data';

async function selectPair(page: import('@playwright/test').Page) {
  await page.getByLabel('Company 1', { exact: true }).selectOption('AAA');
  await page.getByLabel('Company 2', { exact: true }).selectOption('BBB');
}
function metricRow(page: Page, label: string) {
  return page.getByRole('region', { name: 'Annual company comparison table', exact: true })
    .getByRole('row').filter({ has: page.getByRole('button', { name: `Copy research note for ${label}`, exact: true }) });
}
const revenueCopy = (page: Page) => page.getByRole('button', { name: 'Copy research note for Revenue', exact: true });
const copyFeedback = (page: Page) => metricRow(page, 'Revenue').getByRole('status');

function inspector(page: Page, label: string) {
  return metricRow(page, label).getByRole('rowheader').locator('details').first();
}
function comparisonResponses(scenario: Scenario) {
  scenario.overrides.push(request => {
    if (!['AAA', 'BBB'].includes(request.ticker ?? '') || request.path !== `/companies/${request.ticker}/financials/annual`) return;
    return { body: data.comparisonAnnual(request.ticker!, request.query.has('fiscal_year') ? Number(request.query.get('fiscal_year')) : null) };
  });
}
function consoleErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  return errors;
}
async function tabTo(page: Page, target: Locator) {
  // The caller anchors on the scroll region, never on the target control.
  for (let step = 0; step < 80; step++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate(element => element === document.activeElement)) return;
  }
  throw new Error('Comparison control was not reachable through native Tab navigation');
}
async function expectComparisonFocus(control: Locator) {
  await expect(control).toBeFocused();
  const focused = await control.evaluate(element => {
    const style = getComputedStyle(element), rect = element.getBoundingClientRect();
    const scroller = element.closest('.comparison-scroll')!;
    const bounds = scroller.getBoundingClientRect();
    const extent = parseFloat(style.outlineWidth) + Math.max(0, parseFloat(style.outlineOffset));
    const top = visualViewport?.offsetTop ?? 0, bottom = top + (visualViewport?.height ?? innerHeight);
    return { visible: element.matches(':focus-visible'), outline: style.outlineStyle,
      width: parseFloat(style.outlineWidth), distinct: style.outlineColor !== style.backgroundColor,
      unclipped: rect.left - extent >= Math.max(0, bounds.left + scroller.clientLeft)
        && rect.right + extent <= Math.min(innerWidth, bounds.left + scroller.clientLeft + scroller.clientWidth)
        && rect.top - extent >= top && rect.bottom + extent <= bottom };
  });
  expect(focused.visible).toBe(true); expect(focused.width).toBeGreaterThan(0);
  expect(focused.outline).not.toBe('none'); expect(focused.distinct).toBe(true); expect(focused.unclipped).toBe(true);
}
async function expectComparisonTextReadable(text: Locator) {
  await text.scrollIntoViewIfNeeded();
  // Reveal the whole paragraph around a wrapped inline reason before measuring
  // the original span. Native nearest-edge scrolling can leave it at the edge.
  await text.evaluate(element => {
    if (element.matches('p > span')) element.closest('p')!.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
  });
  await expect(text).toBeVisible();
  const geometry = await text.evaluate(element => {
    const rect = element.getBoundingClientRect(), scroller = element.closest('.comparison-scroll')!;
    const bounds = scroller.getBoundingClientRect();
    const clip = { left: Math.max(0, bounds.left + scroller.clientLeft),
      right: Math.min(innerWidth, bounds.left + scroller.clientLeft + scroller.clientWidth), top: 0, bottom: innerHeight };
    const checks = { positiveWidth: rect.width > 0, positiveHeight: rect.height > 0,
      withinLeft: rect.left >= clip.left, withinRight: rect.right <= clip.right,
      withinTop: rect.top >= clip.top, withinBottom: rect.bottom <= clip.bottom };
    const namedRect = (value: DOMRect) => ({ left: value.left, right: value.right, top: value.top,
      bottom: value.bottom, width: value.width, height: value.height });
    const style = getComputedStyle(element);
    return { textRect: namedRect(rect), scrollerRect: namedRect(bounds), clip,
      viewport: { width: innerWidth, height: innerHeight, visual: visualViewport && {
        offsetLeft: visualViewport.offsetLeft, offsetTop: visualViewport.offsetTop,
        width: visualViewport.width, height: visualViewport.height, scale: visualViewport.scale } },
      scroll: { x: scrollX, y: scrollY, left: scroller.scrollLeft, top: scroller.scrollTop },
      textStyle: { fontFamily: style.fontFamily, fontSize: style.fontSize, lineHeight: style.lineHeight,
        whiteSpace: style.whiteSpace, overflowWrap: style.overflowWrap }, checks,
      failedChecks: Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name) };
  });
  expect(geometry.failedChecks, `Comparison text must be fully contained: ${JSON.stringify(geometry)}`).toEqual([]);
}

test('annual comparability inspector: native disclosure, keyboard and readable limits @desktop-only', async ({ page, scenario }) => {
  const errors = consoleErrors(page); comparisonResponses(scenario);
  await scenario.open(); await scenario.ready(); await selectPair(page);
  await expect(revenueCopy(page)).toBeEnabled(); // Selected annual responses have settled.
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  const revenue = inspector(page, 'Revenue'), summary = revenue.locator('summary');
  const before = scenario.ledger.length;
  await expect(revenue).not.toHaveAttribute('open');
  await table.focus(); await page.keyboard.press('Tab');
  await expectComparisonFocus(summary);
  await page.keyboard.press('Enter'); await expect(revenue).toHaveAttribute('open', '');
  await expect(revenue).toContainText('Reported date ranges differ within this row.');
  await expect(revenue).toContainText('Reported revenue-basis labels differ within this row.');
  const issuers = revenue.locator('.source-record');
  await expect(issuers).toHaveCount(2);
  for (const [index, dates, basis] of [
    [0, '2025-01-01 – 2025-12-31', 'total_revenue'],
    [1, '2024-09-29 – 2025-09-27', 'customer_contract'],
  ] as const) {
    await expectComparisonTextReadable(issuers.nth(index).getByText(`Reporting period: ${dates} · FY2025 FY`, { exact: true }));
    await expectComparisonTextReadable(issuers.nth(index).getByText(`Metric revenue basis: ${basis}`, { exact: true }));
  }
  await table.focus(); await page.keyboard.press('Tab'); await expectComparisonFocus(summary);
  await page.keyboard.press('Space'); await expect(revenue).not.toHaveAttribute('open');
  await page.keyboard.press('Tab'); await expect(revenueCopy(page)).toBeFocused();
  await page.keyboard.press('Shift+Tab'); await expectComparisonFocus(summary);
  await summary.click(); await expect(revenue).toHaveAttribute('open', '');
  await summary.click(); await expect(revenue).not.toHaveAttribute('open');
  const margin = inspector(page, 'Gross margin'), marginSummary = margin.locator('summary');
  await table.focus(); await tabTo(page, marginSummary); await expectComparisonFocus(marginSummary);
  await page.keyboard.press('Enter'); await expect(margin).toHaveAttribute('open', '');
  await expectComparisonTextReadable(margin.getByText('Revenue basis is unknown for at least one company or revenue operand.', { exact: true }));
  const reason = margin.locator('.source-record').nth(0).locator('p > span');
  await expectComparisonTextReadable(reason);
  expect(await reason.textContent()).toBe(data.comparisonUnknownReason);
  await expect(margin.locator('em, script, img')).toHaveCount(0);
  await expectComparisonTextReadable(margin.getByText('Not applicable — excluded', { exact: true }));
  await expect(metricRow(page, 'Gross margin').getByRole('cell').nth(0).locator('.metric-value')).toHaveText('Unavailable');
  await expect(metricRow(page, 'Gross margin').getByRole('cell').nth(1).locator('.metric-value')).toHaveText('Not applicable');
  expect(scenario.ledger).toHaveLength(before);
  expect(errors).toEqual([]); expect(scenario.violations).toEqual([]);
});

test('annual comparability inspector: four-company scrolling and touch at 390px @mobile-only', async ({ page, scenario }) => {
  scenario.enableFourCompanyComparison(); comparisonResponses(scenario);
  const errors = consoleErrors(page);
  await scenario.open(); await scenario.ready();
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 });
  const selectionStart = scenario.ledger.length;
  await page.getByRole('button', { name: 'Add company', exact: true }).click();
  await page.getByRole('button', { name: 'Add company', exact: true }).click();
  for (const [index, ticker] of ['AAA', 'BBB', 'CCC', 'DDD'].entries()) await page.getByLabel(`Company ${index + 1}`, { exact: true }).selectOption(ticker);
  await expect(revenueCopy(page)).toBeEnabled();
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  await expect(table.getByRole('columnheader')).toHaveCount(5);
  for (const [index, ticker] of ['AAA', 'BBB', 'CCC', 'DDD'].entries()) {
    await expect(table.getByRole('columnheader').nth(index + 1)).toContainText(`Publication ${data.comparisonPins[ticker]}`);
    const calls = scenario.ledger.slice(selectionStart).filter(call => call.ticker === ticker);
    expect(calls.map(call => [call.path, call.pin, call.query.toString()])).toEqual([
      [`/companies/${ticker}/freshness`, undefined, ''],
      [`/companies/${ticker}/financials/annual`, String(data.comparisonPins[ticker]), ''],
      [`/companies/${ticker}/financials/annual`, String(data.comparisonPins[ticker]), 'fiscal_year=2025'],
    ]);
  }
  const before = scenario.ledger.length;
  const revenue = inspector(page, 'Revenue'), summary = revenue.locator('summary');
  await summary.tap(); await expect(revenue).toHaveAttribute('open', '');
  await expect(revenue.locator('.source-record')).toHaveCount(4);
  await expectComparisonTextReadable(revenue.locator('.source-record').nth(0).getByText('Metric revenue basis: total_revenue', { exact: true }));
  const firstY = await page.evaluate(() => scrollY);
  await expectComparisonTextReadable(revenue.locator('.source-record').nth(2).getByText('Metric revenue basis: Unknown — not supplied for this metric', { exact: true }));
  const delta = revenue.locator('.source-record').nth(3);
  await expectComparisonTextReadable(delta.getByText('Reporting period: Unknown — no reporting period supplied', { exact: true }));
  const periodReason = delta.locator('p > span').first();
  await expectComparisonTextReadable(periodReason); expect(await periodReason.textContent()).toBe(data.comparisonPeriodReason);
  expect(await page.evaluate(() => scrollY)).toBeGreaterThan(firstY);
  await table.scrollIntoViewIfNeeded();
  expect(await table.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
  // Exercise horizontal scroll positioning, then native operation in the last
  // company column. This does not claim physical-device swipe acceptance.
  await table.evaluate(element => { element.scrollLeft = element.scrollWidth; });
  expect(await table.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  const lastSource = metricRow(page, 'Revenue').getByRole('cell').nth(3).locator('details');
  await lastSource.locator('summary').tap(); await expect(lastSource).toHaveAttribute('open', '');
  await expectComparisonTextReadable(lastSource.getByText('No compatible source selected for this period.', { exact: true }));
  await lastSource.locator('summary').tap(); await expect(lastSource).not.toHaveAttribute('open');
  await table.focus(); await page.keyboard.press('Tab'); await expectComparisonFocus(summary);
  await page.keyboard.press('Space'); await expect(revenue).not.toHaveAttribute('open');
  await summary.tap(); await expect(revenue).toHaveAttribute('open', '');
  await summary.tap(); await expect(revenue).not.toHaveAttribute('open');
  const margin = inspector(page, 'Gross margin');
  await margin.locator('summary').tap();
  const unknown = margin.locator('.source-record').nth(0).locator('p > span');
  await expectComparisonTextReadable(unknown); expect(await unknown.textContent()).toBe(data.comparisonUnknownReason);
  await expect(margin.locator('em, script, img')).toHaveCount(0);
  await expectComparisonTextReadable(margin.getByText('Not applicable — excluded', { exact: true }));
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  expect(scenario.ledger).toHaveLength(before);
  expect(errors).toEqual([]); expect(scenario.violations).toEqual([]);
});

test('comparison uses independent zero and one pins, distinct selections and annual switching', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready(); await selectPair(page);
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  await expect(table).toBeVisible();
  await expect(table.getByRole('rowheader')).toHaveCount(11);
  for (const label of ['Gross profit', 'Operating income', 'Net income', 'Gross margin']) {
    const row = metricRow(page, label);
    await expect(row).toHaveCount(1);
    await expect(row.getByRole('rowheader')).toContainText(label);
    await expect(row.getByRole('button', { name: `Copy research note for ${label}`, exact: true })).toBeVisible();
  }
  const grossProfit = metricRow(page, 'Gross profit');
  await expect(grossProfit.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  const grossMargin = metricRow(page, 'Gross margin');
  await expect(grossMargin.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('Unavailable');
  await expect(table.getByRole('columnheader').nth(1)).toContainText('Publication 0');
  await expect(table.getByRole('columnheader').nth(2)).toContainText('Publication 1');
  const revenue = metricRow(page, 'Revenue');
  await expect(revenue.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(revenue.getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$9B');
  await expect(table.getByRole('columnheader').nth(1)).toContainText('Jan 1, 2025 – Dec 31, 2025');
  await expect(table.getByRole('columnheader').nth(2)).toContainText('Jan 1, 2025 – Dec 31, 2025');
  await expect(page.getByLabel('Company 2', { exact: true }).locator('option[value="AAA"]')).toBeDisabled();
  await page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true }).selectOption('2024');
  await expect(table.getByRole('caption')).toContainText('FY2024');
  await expect(table.getByRole('columnheader').nth(1)).toContainText('FY2024');
  await expect(revenue.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$4B');
  await expect(revenue.getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$7B');
  for (const header of [1, 2]) await expect(table.getByRole('columnheader').nth(header)).toContainText('Jan 1, 2024 – Dec 31, 2024');
  await revenue.getByText('AAA Revenue sources and details', { exact: true }).click();
  await expect(revenue.getByRole('cell').nth(0).getByText('4000000000 USD', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true }).selectOption('2025');
  await expect(revenue.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(revenue.getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$9B');
  for (const ticker of ['AAA', 'BBB']) {
    const calls = scenario.ledger.filter(item => item.path === `/companies/${ticker}/financials/annual`);
    expect(calls.some(item => item.query.size === 0)).toBe(true);
    expect(calls.some(item => item.query.get('fiscal_year') === '2024')).toBe(true);
    expect(new Set(calls.map(item => item.pin))).toEqual(new Set([String(scenario.versions[ticker])]));
  }
});

test('malformed annual provenance fails only its column', async ({ page, scenario }) => {
  scenario.overrides.push(request => {
    if (request.path !== '/companies/BBB/financials/annual' || !request.query.has('fiscal_year')) return;
    const reply = data.annual('BBB', Number(request.query.get('fiscal_year')));
    reply.metrics.revenue.provenance[0].company_cik = data.company('AAA').cik;
    return { body: reply };
  });
  await scenario.open(); await scenario.ready(); await selectPair(page);
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  await expect(table).toBeVisible();
  const row = metricRow(page, 'Revenue');
  await expect(row.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(row.getByRole('cell').nth(1)).toContainText('Annual financial evidence does not match');
  await expect(revenueCopy(page)).toBeDisabled();
  await expect(copyFeedback(page)).toBeEmpty();
});

test('cancelled annual results delivered despite ignored abort cannot repopulate comparison', async ({ page, scenario }) => {
  await scenario.ignoreTransportAbort('/companies/AAA/financials/annual');
  const barrier = scenario.hold(request => request.path === '/companies/AAA/financials/annual' && request.query.get('fiscal_year') === '2025');
  await scenario.open(); await scenario.ready(); await selectPair(page);
  await expect.poll(() => scenario.ledger.some(item => item.path === '/companies/AAA/financials/annual' && item.query.has('fiscal_year'))).toBe(true);
  await expect(page.getByRole('button', { name: /^Copy research note for / })).toHaveCount(0);
  await page.getByRole('button', { name: 'Cancel comparison', exact: true }).click();
  await expect(page.getByText('Comparison cancelled. Refresh comparison to try again.', { exact: true })).toBeVisible();
  barrier.release();
  await expect.poll(() => scenario.abortedDeliveries('/companies/AAA/financials/annual', '0', 200, '?fiscal_year=2025')).toBeGreaterThan(0);
  await expect(page.getByRole('region', { name: 'Annual company comparison table', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Copy research note for / })).toHaveCount(0);
  await page.getByRole('button', { name: 'Refresh comparison', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Annual company comparison table', exact: true })).toBeVisible();
  const revenue = metricRow(page, 'Revenue');
  await expect(revenue.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(revenue.getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$9B');
  await expect(revenueCopy(page)).toBeEnabled();
});

// Independently hand-authored complete output for the fixed test responses.
// Never import/call the production serializer to create this expectation.
const EXPECTED_REVENUE_2025 = `# FinLens research note
- Metric: Revenue
- Comparison: Annual fiscal end-year 2025

## Scope and limitations
- A shared fiscal end-year does not establish equivalent accounting periods or cross-company comparability.
- Stored research snapshot. Data currency and completeness are not established by this note; publication versions are not freshness guarantees.
- Source fiscal labels may describe later comparative filings; an original-filing or as-of series is not established.
- SEC link policy checks destinations, not financial evidentiary support. Copying does not independently verify filings.
- Financial selection and calculations remain server-owned. No cross-company calculation or causal explanation is added.

## Company
- Company: Synthetic Alpha
- Ticker: AAA
- CIK: 0000900001
- Requested fiscal end-year: 2025
- Independent publication version: 0
- Actual annual reporting window: 2025-01-01 to 2025-12-31
- Period kind: annual
- Fiscal year: 2025
- Fiscal period: FY
- Fiscal label basis: synthetic&#95;reported
- Source selection policy: Synthetic fixed observations&#59; no production data&#46;
- Status: Available
- Exact normalized value: 5000000000.123456789
- Unit: USD
- Observation reporting window: 2025-01-01 to 2025-12-31
- Period kind: annual
- Fiscal year: 2025
- Fiscal period: FY
- Fiscal label basis: synthetic&#95;reported

### Selected source observations

#### Selected source 1
- Source CIK: 0000900001
- Fact identity: 900001
- Original concept: Synthetic&#95;revenue
- Original source value: 5000000000.123456789
- Original source unit: USD
- Source reporting window: 2025-01-01 to 2025-12-31
- Accession: 0000900001-25-000001
- Form: 10-K
- Filed: 2026-02-01
- Source fiscal year: 2025
- Source fiscal period: FY
- Official SEC filing: [Open supplied SEC link](<https://www.sec.gov/Archives/edgar/data/900001/000090000125000001/synthetic.htm>)

### Alternative source observations
Alternatives are not the selected support for the normalized value.
No alternative observations supplied.

## Company
- Company: Synthetic Beta
- Ticker: BBB
- CIK: 0000900002
- Requested fiscal end-year: 2025
- Independent publication version: 1
- Actual annual reporting window: 2025-01-01 to 2025-12-31
- Period kind: annual
- Fiscal year: 2025
- Fiscal period: FY
- Fiscal label basis: synthetic&#95;reported
- Source selection policy: Synthetic fixed observations&#59; no production data&#46;
- Status: Available
- Exact normalized value: 9000000000
- Unit: USD
- Observation reporting window: 2025-01-01 to 2025-12-31
- Period kind: annual
- Fiscal year: 2025
- Fiscal period: FY
- Fiscal label basis: synthetic&#95;reported

### Selected source observations

#### Selected source 1
- Source CIK: 0000900002
- Fact identity: 900002
- Original concept: Synthetic&#95;revenue
- Original source value: 9000000000
- Original source unit: USD
- Source reporting window: 2025-01-01 to 2025-12-31
- Accession: 0000900002-25-000001
- Form: 10-K
- Filed: 2026-02-01
- Source fiscal year: 2025
- Source fiscal period: FY
- Official SEC filing: [Open supplied SEC link](<https://www.sec.gov/Archives/edgar/data/900002/000090000225000001/synthetic.htm>)

### Alternative source observations
Alternatives are not the selected support for the normalized value.
No alternative observations supplied.
`;

async function openCopyComparison(page: Page, scenario: Scenario) {
  // Local response override only: no fixture library or financial calculation changes.
  scenario.overrides.push(request => {
    if (request.path !== '/companies/AAA/financials/annual' || request.query.get('fiscal_year') !== '2025') return;
    const body = data.annual('AAA', 2025);
    body.metrics.revenue.value = '5000000000.123456789';
    body.metrics.revenue.provenance[0].value = '5000000000.123456789';
    return { body };
  });
  await scenario.open(); await scenario.ready(); await selectPair(page);
  await expect(revenueCopy(page)).toBeEnabled();
}

async function nativeClipboard(context: BrowserContext, page: Page) {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
  await page.bringToFront();
  expect(await page.evaluate(() => ({ secure: isSecureContext, write: typeof navigator.clipboard?.writeText,
    read: typeof navigator.clipboard?.readText }))).toEqual({ secure: true, write: 'function', read: 'function' });
}

async function expectNativeCopy(page: Page, scenario: Scenario, expected: string, activate: () => Promise<unknown>) {
  // Replace a previous note before activation so stale clipboard content cannot pass.
  await page.evaluate(() => navigator.clipboard.writeText('QA-01 native clipboard sentinel'));
  const before = scenario.ledger.length;
  await activate();
  await expect(copyFeedback(page)).toHaveText('Research note copied.');
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(expected);
  expect(scenario.ledger).toHaveLength(before);
}

test('native Clipboard exact Markdown and keyboard Enter/Space @desktop-only', async ({ page, context, scenario }) => {
  await openCopyComparison(page, scenario); await nativeClipboard(context, page);
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  const button = revenueCopy(page);
  const inspectorSummary = inspector(page, 'Revenue').locator('summary');
  const enterCopyByKeyboard = async () => {
    await table.focus(); await page.keyboard.press('Tab');
    await expect(inspectorSummary).toBeFocused();
    await page.keyboard.press('Tab'); await expect(button).toBeFocused();
  };
  await enterCopyByKeyboard();
  const focus = await button.evaluate(element => {
    const style = getComputedStyle(element); const rect = element.getBoundingClientRect();
    const extent = parseFloat(style.outlineWidth) + Math.max(0, parseFloat(style.outlineOffset));
    return { visible: element.matches(':focus-visible'), style: style.outlineStyle, width: parseFloat(style.outlineWidth),
      color: style.outlineColor, background: style.backgroundColor,
      unclipped: rect.left - extent >= 0 && rect.top - extent >= 0 && rect.right + extent <= innerWidth && rect.bottom + extent <= innerHeight };
  });
  expect(focus.visible).toBe(true); expect(focus.width).toBeGreaterThan(0);
  expect(focus.style).not.toBe('none'); expect(focus.color).not.toBe(focus.background); expect(focus.unclipped).toBe(true);
  for (const key of ['Enter', 'Space']) {
    // Re-enter the table by native Tab after each write; temporary disabling
    // may release focus, so a second activation must not depend on retention.
    await enterCopyByKeyboard();
    await expectNativeCopy(page, scenario, EXPECTED_REVENUE_2025, () => page.keyboard.press(key));
  }
});

test('native Clipboard tap and reachable comparison control at 390px @mobile-only', async ({ page, context, scenario }) => {
  await openCopyComparison(page, scenario); await nativeClipboard(context, page);
  expect(page.viewportSize()?.width).toBe(390);
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  await table.scrollIntoViewIfNeeded();
  expect(await table.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
  await table.evaluate(element => { element.scrollLeft = element.scrollWidth; });
  await expectNativeCopy(page, scenario, EXPECTED_REVENUE_2025, () => revenueCopy(page).tap());
  const geometry = await revenueCopy(page).evaluate(element => {
    const rect = element.getBoundingClientRect(); const scroller = element.closest('.comparison-scroll')!;
    const bounds = scroller.getBoundingClientRect();
    return { reachable: rect.left >= Math.max(0, bounds.left) && rect.right <= Math.min(innerWidth, bounds.right)
      && rect.top >= 0 && rect.bottom <= innerHeight, pageOverflow: document.documentElement.scrollWidth - innerWidth };
  });
  expect(geometry.reachable).toBe(true); expect(geometry.pageOverflow).toBeLessThanOrEqual(1);
});

test('native Clipboard follows FY2025–FY2024–FY2025 and reordered companies', async ({ page, context, scenario, isMobile }) => {
  await openCopyComparison(page, scenario); await nativeClipboard(context, page);
  const activate = () => isMobile ? revenueCopy(page).tap() : revenueCopy(page).click();
  await expectNativeCopy(page, scenario, EXPECTED_REVENUE_2025, activate);
  const year = page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true });
  await year.selectOption('2024'); await expect(revenueCopy(page)).toBeEnabled();
  // Fixed literal substitutions on the independent oracle, never on production output.
  const expected2024 = EXPECTED_REVENUE_2025.replaceAll('2025', '2024')
    .replaceAll('5000000000.123456789', '4000000000').replaceAll('9000000000', '7000000000');
  await expectNativeCopy(page, scenario, expected2024, activate);
  await year.selectOption('2025'); await expect(revenueCopy(page)).toBeEnabled();
  await expectNativeCopy(page, scenario, EXPECTED_REVENUE_2025, activate);
  await page.getByLabel('Company 2', { exact: true }).selectOption('');
  await expect(revenueCopy(page)).toHaveCount(0);
  await page.getByLabel('Company 1', { exact: true }).selectOption('BBB');
  await page.getByLabel('Company 2', { exact: true }).selectOption('AAA');
  await expect(revenueCopy(page)).toBeEnabled();
  const [intro, alpha, beta] = EXPECTED_REVENUE_2025.split('\n## Company\n');
  const reordered = `${intro}\n## Company\n${beta.trimEnd()}\n\n## Company\n${alpha.trimEnd()}\n`;
  await expectNativeCopy(page, scenario, reordered, activate);
  expect(scenario.ledger.filter(item => item.path.endsWith('/financials/annual') && item.ticker === 'AAA').every(item => item.pin === '0')).toBe(true);
  expect(scenario.ledger.filter(item => item.path.endsWith('/financials/annual') && item.ticker === 'BBB').every(item => item.pin === '1')).toBe(true);
});

// Each barrier owns one request object, not just a ticker/year/pin tuple.
// Installing two identical barriers therefore separates consecutive visits.
function holdAnnualVisit(scenario: Scenario, year: string) {
  const visit = { request: null as ApiRequest | null, replies: 0 };
  const barrier = scenario.hold(request => {
    if (visit.request || request.path !== '/companies/BBB/financials/annual'
        || request.query.get('fiscal_year') !== year) return false;
    visit.request = request;
    return true;
  }, request => {
    visit.replies++;
    return scenario.defaultReply(request);
  });
  return { visit, release: barrier.release };
}

async function expectHeldVisit(scenario: Scenario, held: ReturnType<typeof holdAnnualVisit>, after: number) {
  await expect.poll(() => held.visit.request !== null).toBe(true);
  const request = held.visit.request!;
  const index = scenario.ledger.indexOf(request);
  expect(index).toBeGreaterThanOrEqual(after);
  expect(scenario.ledger[index].request).toBe(request.request);
  expect(request.pin).toBe('1');
  expect(held.visit.replies).toBe(0);
  return index;
}

async function expectCopyIneligible(page: Page) {
  // Observe the rendered control: an earlier table must not expose an enabled
  // copy even though its complete financial response is still stored in React.
  await expect(page.getByRole('button', { name: /^Copy research note for / }).and(page.locator(':enabled'))).toHaveCount(0);
  await expect(page.getByText('Loading verified annual observations…', { exact: true })).toBeVisible();
}

async function expectObsoleteDelivery(page: Page, scenario: Scenario, held: ReturnType<typeof holdAnnualVisit>, year: string) {
  await expect.poll(() => scenario.abortedDeliveries('/companies/BBB/financials/annual', '1', 200, `?fiscal_year=${year}`)).toBe(1);
  const response = await held.visit.request!.request.response();
  expect(response?.status()).toBe(200);
  expect(await response!.finished()).toBeNull();
  // Wait for the delivered body and product reactions before checking the
  // still-held replacement; fetch headers alone are not settlement evidence.
  await page.evaluate(() => new Promise<void>(done => requestAnimationFrame(() => requestAnimationFrame(() => done()))));
  expect(held.visit.replies).toBe(1);
}

function expectIndependentAnnualPins(scenario: Scenario) {
  for (const [ticker, pin] of [['AAA', '0'], ['BBB', '1']]) {
    const requests = scenario.ledger.filter(item => item.path === `/companies/${ticker}/financials/annual`);
    expect(requests.length).toBeGreaterThan(0);
    expect(new Set(requests.map(item => item.pin))).toEqual(new Set([pin]));
  }
}

test('year return keeps loaded FY2025 noncopyable until its replacement response @desktop-only', async ({ page, context, scenario }) => {
  const path = '/companies/BBB/financials/annual';
  await scenario.ignoreTransportAbort(path);
  await openCopyComparison(page, scenario); await nativeClipboard(context, page);
  const previous = scenario.ledger.find(item => item.path === path && item.query.get('fiscal_year') === '2025')!;
  expect(previous.pin).toBe('1');
  const before = scenario.ledger.length;
  const obsolete = holdAnnualVisit(scenario, '2024');
  const current = holdAnnualVisit(scenario, '2025');
  const year = page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true });
  await year.selectOption('2024');
  const obsoleteIndex = await expectHeldVisit(scenario, obsolete, before);
  await expectCopyIneligible(page);
  await year.selectOption('2025');
  const currentIndex = await expectHeldVisit(scenario, current, obsoleteIndex + 1);
  expect(current.visit.request!.request).not.toBe(previous.request);
  await expect(year).toHaveValue('2025');
  // Without annualGeneration in requestKey, the first visit's cached FY2025
  // columns would make this control eligible while the new response is held.
  await expectCopyIneligible(page);
  obsolete.release();
  await expectObsoleteDelivery(page, scenario, obsolete, '2024');
  expect(current.visit.replies).toBe(0);
  expect(scenario.ledger[currentIndex]).toBe(current.visit.request);
  await expectCopyIneligible(page);
  current.release();
  await expect(revenueCopy(page)).toBeEnabled();
  expect(current.visit.replies).toBe(1);
  await expectNativeCopy(page, scenario, EXPECTED_REVENUE_2025, () => revenueCopy(page).click());
  expectIndependentAnnualPins(scenario);
});

test('same ordered pair return cannot reuse an earlier visit while replacement is held @desktop-only', async ({ page, context, scenario }) => {
  const path = '/companies/BBB/financials/annual';
  await scenario.ignoreTransportAbort(path);
  await openCopyComparison(page, scenario); await nativeClipboard(context, page);
  const previous = scenario.ledger.find(item => item.path === path && item.query.get('fiscal_year') === '2025')!;
  const before = scenario.ledger.length;
  const obsolete = holdAnnualVisit(scenario, '2025');
  const current = holdAnnualVisit(scenario, '2025');
  const company1 = page.getByLabel('Company 1', { exact: true });
  const company2 = page.getByLabel('Company 2', { exact: true });
  const returnToPair = async () => {
    await company2.selectOption('');
    await expect(revenueCopy(page)).toHaveCount(0);
    await company2.selectOption('BBB');
    await expect(company1).toHaveValue('AAA');
    await expect(company2).toHaveValue('BBB');
  };
  // First return creates an abortable obsolete visit while retaining the
  // initially loaded data. The second return owns the replacement response.
  await returnToPair();
  const obsoleteIndex = await expectHeldVisit(scenario, obsolete, before);
  // Removing changeSelection's generation increment exposes the initial
  // AAA/BBB columns here; a reversed pair would not detect that regression.
  await expectCopyIneligible(page);
  await returnToPair();
  const currentIndex = await expectHeldVisit(scenario, current, obsoleteIndex + 1);
  const visits = [previous, obsolete.visit.request!, current.visit.request!];
  expect(new Set(visits.map(item => item.request)).size).toBe(3);
  expect(visits.map(item => ({ path: item.path, year: item.query.get('fiscal_year'), pin: item.pin })))
    .toEqual(Array.from({ length: 3 }, () => ({ path, year: '2025', pin: '1' })));
  await expectCopyIneligible(page);
  obsolete.release();
  await expectObsoleteDelivery(page, scenario, obsolete, '2025');
  expect(current.visit.replies).toBe(0);
  expect(scenario.ledger[currentIndex]).toBe(current.visit.request);
  await expectCopyIneligible(page);
  current.release();
  await expect(revenueCopy(page)).toBeEnabled();
  expect(current.visit.replies).toBe(1);
  await expectNativeCopy(page, scenario, EXPECTED_REVENUE_2025, () => revenueCopy(page).click());
  expectIndependentAnnualPins(scenario);
});

type ClipboardSeam = {
  calls: string[];
  settlements: { index: number; outcome: 'resolve' | 'reject' }[];
  settle: (index: number, outcome: 'resolve' | 'reject') => Promise<void>;
  restore: () => void;
};
declare global { interface Window { qaResearchNoteClipboard?: ClipboardSeam } }

// Browser-side failure/lifecycle seams ONLY. Native positive cases above never
// install these overrides and must read the actual Chromium clipboard.
async function installClipboardSeam(page: Page, mode: 'missing' | 'reject' | 'delayed') {
  await page.evaluate(mode => {
    const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    const pending: { resolve: () => void; reject: (error: Error) => void; settled: boolean }[] = [];
    const calls: string[] = [];
    const settlements: ClipboardSeam['settlements'] = [];
    const writeText = (text: string) => {
      calls.push(text);
      if (mode === 'reject') return Promise.reject(new DOMException('Synthetic clipboard permission denial', 'NotAllowedError'));
      return new Promise<void>((resolve, reject) => pending.push({ resolve, reject, settled: false }));
    };
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: mode === 'missing' ? undefined : { writeText } });
    window.qaResearchNoteClipboard = {
      calls, settlements,
      async settle(index, outcome) {
        const item = pending[index];
        if (!item || item.settled) throw new Error('Invalid synthetic clipboard settlement');
        item.settled = true;
        if (outcome === 'resolve') item.resolve(); else item.reject(new DOMException('Synthetic delayed denial', 'NotAllowedError'));
        // Drain the product Promise reaction and two browser paint boundaries;
        // assertions below observe committed feedback, without arbitrary sleeps.
        await Promise.resolve();
        await new Promise<void>(done => requestAnimationFrame(() => requestAnimationFrame(() => done())));
        settlements.push({ index, outcome });
      },
      restore() {
        if (original) Object.defineProperty(navigator, 'clipboard', original);
        else Reflect.deleteProperty(navigator, 'clipboard');
        delete window.qaResearchNoteClipboard;
      },
    };
  }, mode);
}
async function restoreClipboardSeam(page: Page) {
  if (!page.isClosed()) await page.evaluate(() => window.qaResearchNoteClipboard?.restore());
}

for (const outcome of ['resolve', 'reject'] as const) test(`obsolete clipboard ${outcome} before replacement copy leaves current feedback empty @desktop-only`, async ({ page, scenario }) => {
  await openCopyComparison(page, scenario); await installClipboardSeam(page, 'delayed');
  try {
    const beforeFirst = scenario.ledger.length;
    await revenueCopy(page).click();
    await expect(copyFeedback(page)).toHaveText('Copying research note…');
    await expect(revenueCopy(page)).toBeDisabled();
    expect(await page.evaluate(() => window.qaResearchNoteClipboard!.calls)).toEqual([EXPECTED_REVENUE_2025]);
    expect(scenario.ledger).toHaveLength(beforeFirst);
    await page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true }).selectOption('2024');
    await expect(revenueCopy(page)).toBeEnabled();
    await expect(copyFeedback(page)).toBeEmpty();
    const beforeCurrent = scenario.ledger.length;
    expect(await page.evaluate(() => window.qaResearchNoteClipboard!.settlements)).toEqual([]);
    // Settle and observe the obsolete Promise with NO replacement write yet.
    await page.evaluate(outcome => window.qaResearchNoteClipboard!.settle(0, outcome), outcome);
    expect(await page.evaluate(() => ({ calls: window.qaResearchNoteClipboard!.calls,
      settlements: window.qaResearchNoteClipboard!.settlements })))
      .toEqual({ calls: [EXPECTED_REVENUE_2025], settlements: [{ index: 0, outcome }] });
    await expect(copyFeedback(page)).toBeEmpty();
    await expect(revenueCopy(page)).toBeEnabled();
    const expected2024 = EXPECTED_REVENUE_2025.replaceAll('2025', '2024')
      .replaceAll('5000000000.123456789', '4000000000').replaceAll('9000000000', '7000000000');
    await revenueCopy(page).click();
    await expect(copyFeedback(page)).toHaveText('Copying research note…');
    expect(await page.evaluate(() => window.qaResearchNoteClipboard!.calls)).toEqual([EXPECTED_REVENUE_2025, expected2024]);
    await page.evaluate(() => window.qaResearchNoteClipboard!.settle(1, 'resolve'));
    await expect(copyFeedback(page)).toHaveText('Research note copied.');
    await expect(revenueCopy(page)).toBeEnabled();
    expect(scenario.ledger).toHaveLength(beforeCurrent);
  } finally { await restoreClipboardSeam(page); }
});

for (const mode of ['missing', 'reject'] as const) test(`clipboard failure seam: ${mode} API/write has accessible failure`, async ({ page, scenario, isMobile }) => {
  await openCopyComparison(page, scenario); await installClipboardSeam(page, mode);
  try {
    const before = scenario.ledger.length;
    if (isMobile) await revenueCopy(page).tap(); else await revenueCopy(page).click();
    await expect(copyFeedback(page)).toHaveAttribute('aria-live', 'polite');
    await expect(copyFeedback(page)).toHaveText(mode === 'missing'
      ? 'Could not copy research note. Clipboard access or verified export data is unavailable.'
      : 'Could not copy research note. Check clipboard permissions and try again.');
    await expect(copyFeedback(page)).not.toContainText('Research note copied.');
    await expect(revenueCopy(page)).toBeEnabled();
    expect(await page.evaluate(() => window.qaResearchNoteClipboard!.calls)).toEqual(mode === 'missing' ? [] : [EXPECTED_REVENUE_2025]);
    expect(scenario.ledger).toHaveLength(before);
  } finally { await restoreClipboardSeam(page); }
});

for (const mode of ['failed', 'unverified'] as const) test(`copy admission rejects a ${mode} annual column`, async ({ page, scenario }) => {
  scenario.overrides.push(request => {
    if (request.path !== '/companies/BBB/financials/annual' || !request.query.has('fiscal_year')) return;
    return mode === 'failed' ? { status: 503, body: { detail: 'Synthetic unavailable response' } }
      : { body: data.annual('BBB', Number(request.query.get('fiscal_year'))), version: null };
  });
  await scenario.open(); await scenario.ready(); await selectPair(page);
  await expect(metricRow(page, 'Revenue').getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(metricRow(page, 'Revenue').getByRole('cell').nth(1)).toContainText(mode === 'failed'
    ? 'Synthetic unavailable response' : 'Published response version could not be verified.');
  await expect(revenueCopy(page)).toBeDisabled();
  await installClipboardSeam(page, 'reject');
  try {
    const before = scenario.ledger.length;
    await revenueCopy(page).evaluate(element => (element as HTMLButtonElement).click());
    expect(await page.evaluate(() => window.qaResearchNoteClipboard!.calls)).toEqual([]);
    await expect(copyFeedback(page)).toBeEmpty();
    expect(scenario.ledger).toHaveLength(before);
  } finally { await restoreClipboardSeam(page); }
});

for (const change of ['year', 'company', 'publication-refresh'] as const) for (const outcome of ['resolve', 'reject'] as const) {
  test(`delayed clipboard seam: obsolete ${outcome} after ${change} cannot settle the current copy @desktop-only`, async ({ page, scenario }) => {
    await openCopyComparison(page, scenario); await installClipboardSeam(page, 'delayed');
    try {
      const beforeFirst = scenario.ledger.length;
      await revenueCopy(page).click();
      await expect(copyFeedback(page)).toHaveText('Copying research note…');
      await expect(revenueCopy(page)).toBeDisabled();
      expect(scenario.ledger).toHaveLength(beforeFirst);
      let expectedCurrent = EXPECTED_REVENUE_2025;
      if (change === 'year') {
        await page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true }).selectOption('2024');
        expectedCurrent = EXPECTED_REVENUE_2025.replaceAll('2025', '2024')
          .replaceAll('5000000000.123456789', '4000000000').replaceAll('9000000000', '7000000000');
      } else if (change === 'company') {
        await page.getByLabel('Company 2', { exact: true }).selectOption('');
        await page.getByLabel('Company 1', { exact: true }).selectOption('BBB');
        await page.getByLabel('Company 2', { exact: true }).selectOption('AAA');
        const [intro, alpha, beta] = EXPECTED_REVENUE_2025.split('\n## Company\n');
        expectedCurrent = `${intro}\n## Company\n${beta.trimEnd()}\n\n## Company\n${alpha.trimEnd()}\n`;
      } else {
        scenario.versions.AAA = 2; scenario.versions.BBB = 3;
        await page.getByRole('button', { name: 'Refresh comparison', exact: true }).click();
        expectedCurrent = EXPECTED_REVENUE_2025.replace('Independent publication version: 0', 'Independent publication version: 2')
          .replace('Independent publication version: 1', 'Independent publication version: 3');
      }
      await expect(revenueCopy(page)).toBeEnabled();
      await expect(copyFeedback(page)).toBeEmpty();
      const beforeCurrent = scenario.ledger.length;
      await revenueCopy(page).click();
      await expect(copyFeedback(page)).toHaveText('Copying research note…');
      expect(await page.evaluate(() => window.qaResearchNoteClipboard!.calls)).toEqual([EXPECTED_REVENUE_2025, expectedCurrent]);
      await page.evaluate(outcome => window.qaResearchNoteClipboard!.settle(0, outcome), outcome);
      await expect(copyFeedback(page)).toHaveText('Copying research note…');
      await expect(revenueCopy(page)).toBeDisabled();
      await page.evaluate(() => window.qaResearchNoteClipboard!.settle(1, 'resolve'));
      await expect(copyFeedback(page)).toHaveText('Research note copied.');
      await expect(revenueCopy(page)).toBeEnabled();
      expect(scenario.ledger).toHaveLength(beforeCurrent);
    } finally { await restoreClipboardSeam(page); }
  });
}
