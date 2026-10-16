import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

async function selectPair(page: import('@playwright/test').Page) {
  await page.getByLabel('Company 1', { exact: true }).selectOption('AAA');
  await page.getByLabel('Company 2', { exact: true }).selectOption('BBB');
}
test('comparison uses independent zero and one pins, distinct selections and annual switching', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready(); await selectPair(page);
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  await expect(table).toBeVisible();
  await expect(table.getByRole('rowheader')).toHaveCount(11);
  for (const label of ['Gross profit', 'Operating income', 'Net income', 'Gross margin']) {
    await expect(table.getByRole('rowheader', { name: label, exact: true })).toBeVisible();
  }
  const grossProfit = table.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Gross profit', exact: true }) });
  await expect(grossProfit.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  const grossMargin = table.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Gross margin', exact: true }) });
  await expect(grossMargin.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('Unavailable');
  await expect(table.getByRole('columnheader').nth(1)).toContainText('Publication 0');
  await expect(table.getByRole('columnheader').nth(2)).toContainText('Publication 1');
  const revenue = table.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Revenue', exact: true }) });
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
  const row = table.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Revenue', exact: true }) });
  await expect(row.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(row.getByRole('cell').nth(1)).toContainText('Annual financial evidence does not match');
});

test('cancelled annual results delivered despite ignored abort cannot repopulate comparison', async ({ page, scenario }) => {
  await scenario.ignoreTransportAbort('/companies/AAA/financials/annual');
  const barrier = scenario.hold(request => request.path === '/companies/AAA/financials/annual' && request.query.get('fiscal_year') === '2025');
  await scenario.open(); await scenario.ready(); await selectPair(page);
  await expect.poll(() => scenario.ledger.some(item => item.path === '/companies/AAA/financials/annual' && item.query.has('fiscal_year'))).toBe(true);
  await page.getByRole('button', { name: 'Cancel comparison', exact: true }).click();
  await expect(page.getByText('Comparison cancelled. Refresh comparison to try again.', { exact: true })).toBeVisible();
  barrier.release();
  await expect.poll(() => scenario.abortedDeliveries('/companies/AAA/financials/annual', '0', 200, '?fiscal_year=2025')).toBeGreaterThan(0);
  await expect(page.getByRole('region', { name: 'Annual company comparison table', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Refresh comparison', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Annual company comparison table', exact: true })).toBeVisible();
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  const revenue = table.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Revenue', exact: true }) });
  await expect(revenue.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(revenue.getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$9B');
});
