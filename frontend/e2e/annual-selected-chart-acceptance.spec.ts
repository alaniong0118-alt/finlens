import type { Locator, Page } from '@playwright/test';
import { test, expect, annualPeriods, missingAnnualReason, expectedRequest, selectedRequests,
  completedRequests, publicationCompletions, replayCancellations, expectFullLedger,
  captureFocusPaint, assessFocusPaint, type ExpectedLedger } from './fixtures/annual-period-browser';

const annual = (page: Page) => page.getByRole('region', { name: 'Annual period comparison', exact: true });
const table = (page: Page) => annual(page).getByRole('region', { name: 'Selected company annual period metrics', exact: true });
const chart = (page: Page) => annual(page).getByRole('region', { name: 'Visualize a selected metric', exact: true });
const selector = (page: Page) => chart(page).getByRole('combobox', { name: 'Metric to visualize', exact: true });
const compare = (page: Page) => annual(page).getByRole('button', { name: 'Compare selected annual periods', exact: true });

// Initial focus is placed on the existing comparison action; the tested control
// must then be reached and operated with native keyboard events.
async function keyboardRevenue(page: Page, control: Locator) {
  await compare(page).focus();
  for (let i = 0; i < 8 && !await control.evaluate(node => node === document.activeElement); i++) await page.keyboard.press('Tab');
  await expect(control).toBeFocused();
  const paint = await control.evaluate(captureFocusPaint);
  const contrast = assessFocusPaint(paint.outlineColor, paint.surfaces);
  await test.info().attach('annual-chart-focus', { body: JSON.stringify({ paint, contrast }), contentType: 'application/json' });
  expect(paint.visible).toBe(true); expect(paint.outline).not.toBe('none'); expect(paint.width).toBeGreaterThan(0);
  expect(contrast.sufficient, JSON.stringify({ paint, contrast })).toBe(true);
  expect(paint.rect.left - paint.extent).toBeGreaterThanOrEqual(paint.clip.left);
  expect(paint.rect.right + paint.extent).toBeLessThanOrEqual(paint.clip.right);
  expect(paint.rect.top - paint.extent).toBeGreaterThanOrEqual(paint.clip.top);
  expect(paint.rect.bottom + paint.extent).toBeLessThanOrEqual(paint.clip.bottom);
  await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await expect(control).toHaveValue('revenue');
}

for (const width of [1440, 390]) {
  test(`selected annual chart: keyboard, gaps, comparability and geometry at ${width}px`, async ({ page, annualScenario: scenario }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    let mixedBasis = false;
    scenario.overrides.unshift(request => {
      if (!mixedBasis || request.path !== '/companies/AAA/financials/annual' || request.query.get('fiscal_year') !== '2024') return;
      const body = annualPeriods('AAA', 2024);
      body.metrics.revenue.revenue_basis = 'net_revenue';
      return { body, version: request.pin };
    });
    await scenario.open(); await scenario.ready();
    await expect(annual(page).getByRole('status')).toHaveText('Choose two to four annual periods, then compare.');
    const expected: ExpectedLedger = { completed: [...completedRequests([expectedRequest('/companies'), expectedRequest('/capabilities')]),
      ...publicationCompletions()], cancelled: replayCancellations(), pending: [], cancelledAfterHeaders: [] };
    await expectFullLedger(scenario, expected);
    for (const year of [2025, 2024, 2023, 2022]) await annual(page).getByRole('checkbox', { name: `FY${year}`, exact: true }).check();
    await compare(page).click(); expected.completed.push(...completedRequests(selectedRequests([2025, 2024, 2023, 2022])));
    await expect(table(page).getByRole('rowheader')).toHaveCount(11); await expectFullLedger(scenario, expected);
    const initialTable = await table(page).evaluate(element => element.innerHTML);
    const revenueRow = table(page).locator('tbody tr').first();
    await expect(revenueRow).toContainText('Exact API value: 5000000000 USD');
    await expect(revenueRow.getByRole('link', { name: /Open official SEC filing/, includeHidden: true }).first())
      .toHaveAttribute('href', annualPeriods('AAA', 2025).metrics.revenue.provenance[0].sec_url);
    await expect(table(page)).toContainText('Jan 1, 2025 – Dec 31, 2025');
    await expect(table(page)).toContainText('Jan 1, 2024 – Dec 31, 2024');
    await expect(table(page)).toContainText(missingAnnualReason);
    await expect(chart(page).getByRole('img')).toHaveCount(0);
    await keyboardRevenue(page, selector(page));
    await expectFullLedger(scenario, expected);
    const visual = chart(page).getByRole('img', { name: /Revenue observations/ });
    await expect(visual).toBeVisible();
    await expect(visual.locator('circle')).toHaveCount(3);
    await expect(visual.locator('path, polyline, line')).toHaveCount(0);
    await expect(visual.locator('text')).toHaveText(['No value', 'FY2025', 'FY2024', 'FY2023', 'FY2022']);
    await expect(chart(page)).toContainText('FY2025 · Annual · Jan 1, 2025 – Dec 31, 2025');
    await expect(chart(page)).toContainText('FY2024 · Annual · Jan 1, 2024 – Dec 31, 2024');
    await expect(chart(page)).toContainText(missingAnnualReason);
    await expect.poll(() => table(page).evaluate(element => element.innerHTML)).toBe(initialTable);
    const geometry = await visual.evaluate(element => {
      const svg = element.getBoundingClientRect();
      const labels = [...element.querySelectorAll('text')].map(text => {
        const rect = text.getBoundingClientRect();
        return { text: text.textContent, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, height: rect.height };
      });
      const dots = [...element.querySelectorAll('circle')].map(dot => {
        const rect = dot.getBoundingClientRect(); return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
      });
      return { svg: { left: svg.left, right: svg.right, top: svg.top, bottom: svg.bottom, width: svg.width, height: svg.height },
        labels, dots, viewport: innerWidth, pageWidth: document.documentElement.scrollWidth };
    });
    await info.attach(`annual-chart-${width}-geometry`, { body: JSON.stringify(geometry), contentType: 'application/json' });
    await visual.scrollIntoViewIfNeeded();
    await info.attach(`annual-chart-${width}`, { body: await page.screenshot(), contentType: 'image/png' });
    expect(geometry.svg.width).toBeGreaterThan(0); expect(geometry.svg.height).toBeGreaterThan(0);
    expect(geometry.svg.left).toBeGreaterThanOrEqual(0); expect(geometry.svg.right).toBeLessThanOrEqual(width + 1);
    expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewport + 1);
    for (const item of [...geometry.labels, ...geometry.dots]) {
      expect(item.left).toBeGreaterThanOrEqual(geometry.svg.left); expect(item.right).toBeLessThanOrEqual(geometry.svg.right);
      expect(item.top).toBeGreaterThanOrEqual(geometry.svg.top); expect(item.bottom).toBeLessThanOrEqual(geometry.svg.bottom);
    }
    // Rendered size, not the SVG's unscaled font-size attribute.
    for (const label of geometry.labels) expect(label.height, `Unreadably small ${label.text}`).toBeGreaterThanOrEqual(10);
    for (let i = 1; i < geometry.labels.length - 1; i++) expect(geometry.labels[i].right).toBeLessThan(geometry.labels[i + 1].left);
    await expectFullLedger(scenario, expected);

    mixedBasis = true;
    await compare(page).click(); expected.completed.push(...completedRequests(selectedRequests([2025, 2024, 2023, 2022])));
    await expect(table(page).getByRole('rowheader')).toHaveCount(11); await expectFullLedger(scenario, expected);
    await keyboardRevenue(page, selector(page));
    await expect(chart(page)).toContainText('Revenue-basis labels differ');
    await expect(chart(page)).toContainText('not plotted on a shared axis');
    await expect(chart(page).getByRole('img')).toHaveCount(0);
    await expect(table(page)).toContainText('Revenue basis: net_revenue');
    await expect(table(page)).toContainText('Jan 1, 2024 – Dec 31, 2024');
    await expectFullLedger(scenario, expected);
  });
}
