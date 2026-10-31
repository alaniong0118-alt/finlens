import type { Locator, Page } from '@playwright/test';
import { test, expect, type ApiRequest, type Scenario } from './fixtures/browser';
import * as data from './fixtures/data';

const desktopTitles = {
  gaps: 'coverage gaps: counts, keyboard, sources and company scope @desktop-only',
  empty: 'coverage gaps: zero/reset and unverified response @desktop-only',
};
const view = (page: Page) => page.getByRole('combobox', { name: 'Metric rows', exact: true });
const count = (page: Page) => page.locator('#comparison-coverage-count');
const table = (page: Page) => page.getByRole('region', { name: 'Annual company comparison table', exact: true });
const rows = (page: Page) => table(page).getByRole('rowheader');
const copy = (page: Page, label: string) => page.getByRole('button', { name: `Copy research note for ${label}`, exact: true });
const row = (page: Page, label: string) => table(page).getByRole('row').filter({ has: copy(page, label) });
const summary = (shown: number, unavailable: number, unverified = 0) =>
  `Showing ${shown} of 11 metric rows. Rows with unavailable or not-applicable values: ${unavailable}. Unverified company responses: ${unverified}.`;

// Test-only all-available protocol response, explicitly authorized for this spec.
// Existing constructors supply every value, period, source identity and pin shape.
// Reuse their synthetic zero-ratio observation for the four ratio slots. This
// exercises UI availability, not real financial formula/eligibility acceptance.
function syntheticAllAvailable(ticker: string, year: number) {
  const result = data.annual(ticker, year);
  for (const point of Object.values(result.metrics)) if (point.status !== 'available') {
    const zero = data.observation(ticker, 'operating_margin', 'annual', year);
    Object.assign(point, { status: zero.status, value: zero.value, reason: zero.reason,
      provenance: zero.provenance, inputs: zero.inputs, alternatives: zero.alternatives });
  }
  return result;
}
function annualRequest(request: ApiRequest) {
  if (request.method !== 'GET' || !['AAA', 'BBB'].includes(request.ticker ?? '')
      || request.path !== `/companies/${request.ticker}/financials/annual`
      || request.pin !== String(data.comparisonPins[request.ticker!])) return false;
  return request.query.size === 0 || request.query.size === 1
    && ['2024', '2025'].includes(request.query.get('fiscal_year') ?? '');
}
function useComparisonResponses(scenario: Scenario) {
  scenario.overrides.push(request => annualRequest(request)
    ? { body: data.comparisonAnnual(request.ticker!, request.query.size ? Number(request.query.get('fiscal_year')) : null) }
    : undefined);
}
async function selectPair(page: Page, scenario: Scenario) {
  await scenario.open(); await scenario.ready();
  await page.getByLabel('Company 1', { exact: true }).selectOption('AAA');
  await page.getByLabel('Company 2', { exact: true }).selectOption('BBB');
  await expect(view(page)).toHaveValue('all');
  await expect(rows(page)).toHaveCount(11);
}
async function expectReadable(text: Locator) {
  await text.scrollIntoViewIfNeeded();
  await text.evaluate(element => (element.matches('p > span') ? element.closest('p')! : element)
    .scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }));
  await expect(text).toBeVisible();
  const geometry = await text.evaluate(element => {
    const rect = element.getBoundingClientRect(), scroller = element.closest('.comparison-scroll');
    const bounds = scroller?.getBoundingClientRect();
    const left = Math.max(0, bounds ? bounds.left + scroller!.clientLeft : 0);
    const right = Math.min(innerWidth, bounds ? bounds.left + scroller!.clientLeft + scroller!.clientWidth : innerWidth);
    const top = visualViewport?.offsetTop ?? 0, bottom = top + (visualViewport?.height ?? innerHeight);
    return { width: rect.width, height: rect.height, left: rect.left, right: rect.right,
      top: rect.top, bottom: rect.bottom, clip: { left, right, top, bottom } };
  });
  expect(geometry.width).toBeGreaterThan(0); expect(geometry.height).toBeGreaterThan(0);
  expect(geometry.left, JSON.stringify(geometry)).toBeGreaterThanOrEqual(geometry.clip.left);
  expect(geometry.right, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clip.right);
  expect(geometry.top, JSON.stringify(geometry)).toBeGreaterThanOrEqual(geometry.clip.top);
  expect(geometry.bottom, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clip.bottom);
}
async function expectKeyboardFocus(control: Locator) {
  await expect(control).toBeFocused();
  const focus = await control.evaluate(element => {
    const style = getComputedStyle(element), rect = element.getBoundingClientRect();
    const extent = parseFloat(style.outlineWidth) + Math.max(0, parseFloat(style.outlineOffset));
    return { visible: element.matches(':focus-visible'), outline: style.outlineStyle,
      width: parseFloat(style.outlineWidth), distinct: style.outlineColor !== style.backgroundColor,
      contained: rect.left - extent >= 0 && rect.right + extent <= innerWidth
        && rect.top - extent >= 0 && rect.bottom + extent <= innerHeight };
  });
  expect(focus.visible).toBe(true); expect(focus.outline).not.toBe('none');
  expect(focus.width).toBeGreaterThan(0); expect(focus.distinct).toBe(true); expect(focus.contained).toBe(true);
}

test(desktopTitles.gaps, async ({ page, scenario }) => {
  scenario.enableFourCompanyComparison(); useComparisonResponses(scenario);
  const held = scenario.hold(request => request.path === '/companies/CCC/financials/annual'
    && request.query.get('fiscal_year') === '2025');
  await selectPair(page, scenario);
  await expect(count(page)).toHaveText(summary(11, 4));
  await expect(copy(page, 'Revenue')).toBeEnabled();
  await expect(view(page)).toHaveAttribute('aria-describedby', 'comparison-coverage-help comparison-coverage-count');
  await expect(count(page)).toHaveAttribute('role', 'status');
  await expect(count(page)).toHaveAttribute('aria-live', 'polite');
  const before = scenario.ledger.length;
  // Reach the native select through normal Tab order, then change it by keyboard.
  const refresh = page.getByRole('button', { name: 'Refresh comparison', exact: true });
  await refresh.scrollIntoViewIfNeeded(); await refresh.focus(); await page.keyboard.press('Tab');
  await expectKeyboardFocus(view(page));
  await page.keyboard.press('End'); await page.keyboard.press('Enter');
  await expect(view(page)).toHaveValue('gaps'); await expect(rows(page)).toHaveCount(4);
  await expect(count(page)).toHaveText(summary(4, 4));
  for (const label of ['Revenue YoY', 'Operating margin', 'Net margin', 'Gross margin']) await expect(copy(page, label)).toBeEnabled();
  await expect(copy(page, 'Revenue')).toHaveCount(0);
  const margin = row(page, 'Gross margin').getByRole('rowheader').locator('details').first();
  await margin.locator('summary').click();
  const raw = margin.locator('.source-record').nth(0).locator('p > span');
  await expectReadable(raw); expect(await raw.textContent()).toBe(data.comparisonUnknownReason);
  await expectReadable(margin.getByText('Not applicable — excluded', { exact: true }));
  await expect(margin.locator('em, img, script')).toHaveCount(0);
  await row(page, 'Gross margin').getByRole('cell').nth(0).locator('details > summary').click();
  await expectReadable(row(page, 'Gross margin').getByRole('cell').nth(0)
    .getByText('No compatible source selected for this period.', { exact: true }));
  expect(scenario.ledger).toHaveLength(before);
  const changed = scenario.ledger.length;
  await page.getByLabel('Company 1', { exact: true }).selectOption('CCC');
  await expect.poll(() => scenario.ledger.some(request => request.path === '/companies/CCC/financials/annual'
    && request.query.get('fiscal_year') === '2025')).toBe(true);
  await expect(view(page)).toHaveCount(0); await expect(count(page)).toHaveCount(0);
  held.release();
  await expect(view(page)).toHaveValue('all'); await expect(count(page)).toHaveText(summary(11, 4));
  await expect(copy(page, 'Revenue')).toBeEnabled();
  await expect(row(page, 'Revenue').getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$3B');
  for (const ticker of ['CCC', 'BBB']) expect(scenario.ledger.slice(changed).filter(request => request.ticker === ticker)
    .map(request => [request.path, request.pin, request.query.toString()])).toEqual([
      [`/companies/${ticker}/freshness`, undefined, ''],
      [`/companies/${ticker}/financials/annual`, String(data.comparisonPins[ticker]), ''],
      [`/companies/${ticker}/financials/annual`, String(data.comparisonPins[ticker]), 'fiscal_year=2025'],
    ]);
  expect(scenario.violations).toEqual([]);
});

test(desktopTitles.empty, async ({ page, scenario }) => {
  let invalidateBeta = false;
  scenario.overrides.push(request => {
    if (!annualRequest(request) || !request.query.size) return;
    const result = syntheticAllAvailable(request.ticker!, Number(request.query.get('fiscal_year')));
    // Deliberately corrupt one source identity; actual client validation must
    // retain the whole issuer as unverified rather than accept an empty success.
    if (invalidateBeta && request.ticker === 'BBB') result.metrics.revenue.provenance[0].company_cik = data.company('AAA').cik;
    return { body: result };
  });
  await selectPair(page, scenario);
  await expect(count(page)).toHaveText(summary(11, 0)); await expect(copy(page, 'Revenue')).toBeEnabled();
  let before = scenario.ledger.length;
  await view(page).selectOption('gaps'); await expect(count(page)).toHaveText(summary(0, 0));
  await expect(rows(page)).toHaveCount(0);
  await expectReadable(page.getByText('No coverage gaps in the current validated responses. Select Show all metrics to inspect values and comparability.', { exact: true }));
  await expectReadable(page.locator('#comparison-coverage-help'));
  await expect(page.locator('#comparison-coverage-help')).toContainText('Availability alone does not establish comparability.');
  await view(page).evaluate(element => element.scrollIntoView({ block: 'center' })); await view(page).focus();
  await page.keyboard.press('Tab');
  const reset = page.getByRole('button', { name: 'Show all metrics', exact: true });
  await expectKeyboardFocus(reset); await page.keyboard.press('Space');
  await expect(view(page)).toHaveValue('all'); await expect(rows(page)).toHaveCount(11);
  await expect(copy(page, 'Revenue')).toBeEnabled(); expect(scenario.ledger).toHaveLength(before);
  invalidateBeta = true;
  await page.getByRole('button', { name: 'Refresh comparison', exact: true }).click();
  await expect(count(page)).toHaveText(summary(11, 0, 1));
  before = scenario.ledger.length;
  await view(page).selectOption('gaps'); await expect(rows(page)).toHaveCount(11);
  await expect(count(page)).toHaveText(summary(11, 0, 1));
  await expect(page.getByRole('button', { name: /^Copy research note for / })).toHaveCount(11);
  for (const button of await page.getByRole('button', { name: /^Copy research note for / }).all()) await expect(button).toBeDisabled();
  await expect(row(page, 'Revenue').getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(row(page, 'Revenue').getByRole('cell').nth(1)).toContainText('Annual financial evidence does not match');
  await expect(page.getByText(/^No coverage gaps in the current validated responses/)).toHaveCount(0);
  expect(scenario.ledger).toHaveLength(before); expect(scenario.violations).toEqual([]);
});

test('coverage gaps: readable filter, touch and zero/reset at 390px @mobile-only', async ({ page, scenario }) => {
  scenario.overrides.push(request => {
    if (!annualRequest(request)) return;
    const year = request.query.size ? Number(request.query.get('fiscal_year')) : null;
    return { body: year === 2024 ? syntheticAllAvailable(request.ticker!, year) : data.comparisonAnnual(request.ticker!, year) };
  });
  await selectPair(page, scenario);
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 });
  await expect(count(page)).toHaveText(summary(11, 4));
  let before = scenario.ledger.length;
  await expectReadable(view(page)); await view(page).selectOption('gaps');
  await expect(count(page)).toHaveText(summary(4, 4)); await expect(rows(page)).toHaveCount(4);
  await expectReadable(count(page)); await expectReadable(page.locator('#comparison-coverage-help'));
  await expect(copy(page, 'Gross margin')).toBeEnabled();
  const margin = row(page, 'Gross margin').getByRole('rowheader').locator('details').first();
  await margin.locator('summary').tap(); await expect(margin).toHaveAttribute('open', '');
  const reason = margin.locator('.source-record').nth(0).locator('p > span');
  await expectReadable(reason); expect(await reason.textContent()).toBe(data.comparisonUnknownReason);
  await expectReadable(margin.getByText('Not applicable — excluded', { exact: true }));
  await expect(margin.locator('em, img, script')).toHaveCount(0);
  expect(scenario.ledger).toHaveLength(before);
  await page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true }).selectOption('2024');
  await expect(view(page)).toHaveValue('all'); await expect(count(page)).toHaveText(summary(11, 0));
  before = scenario.ledger.length;
  await view(page).selectOption('gaps'); await expect(count(page)).toHaveText(summary(0, 0));
  await expectReadable(page.getByText(/^No coverage gaps in the current validated responses/));
  const reset = page.getByRole('button', { name: 'Show all metrics', exact: true });
  await expectReadable(reset);
  expect(await reset.evaluate(element => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
  await reset.tap(); await expect(view(page)).toHaveValue('all'); await expect(rows(page)).toHaveCount(11);
  await expect(copy(page, 'Revenue')).toBeEnabled();
  await expect(row(page, 'Revenue').getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$4B');
  await expect(row(page, 'Revenue').getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$7B');
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  expect(scenario.ledger).toHaveLength(before); expect(scenario.violations).toEqual([]);
});
