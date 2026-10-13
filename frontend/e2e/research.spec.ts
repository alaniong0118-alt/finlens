import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

test('snapshot exposes six primary and all fifteen metrics with honest states and provenance', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  await expect(snapshot.locator('.metric-grid').first().locator('.metric-card')).toHaveCount(6);
  await expect(snapshot.locator('.metric-card').filter({ has: page.getByRole('heading', { name: 'Operating income', exact: true }) }).locator('.metric-value')).toHaveText('$0');
  await expect(snapshot.locator('.metric-card').filter({ has: page.getByRole('heading', { name: 'Net income', exact: true }) }).locator('.metric-value')).toHaveText('-$25M');
  await expect(snapshot.getByText('Not applicable', { exact: true })).toBeVisible();
  for (const name of ['More income and profitability', 'Balance sheet · as of the reporting date', 'Cash flow · reported intervals']) await snapshot.getByText(name, { exact: true }).click();
  await expect(snapshot.locator('.metric-card')).toHaveCount(15);
  await expect(snapshot.getByRole('heading', { level: 3 })).toHaveCount(15);
  await expect(snapshot.getByText('Synthetic compatible gross-profit evidence is missing.', { exact: true }).first()).toBeVisible();
  const revenue = snapshot.locator('.metric-card').filter({ has: page.getByRole('heading', { name: 'Revenue', exact: true }) });
  await revenue.getByText('Sources and details', { exact: true }).click();
  await expect(revenue.getByText('Synthetic_revenue', { exact: true })).toBeVisible();
  await expect(revenue.getByText('1000000000 USD', { exact: true })).toBeVisible();
  await expect(revenue.getByRole('link', { name: 'Open official SEC filing' })).toHaveAttribute('href', data.secUrl('AAA'));
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB'); await scenario.ready('BBB');
  await expect(page.getByRole('heading', { name: 'Synthetic Beta', exact: true })).toBeVisible();
  await expect(snapshot.locator('.metric-grid').first().locator('.metric-card').first().locator('.metric-value')).toHaveText('$2B');
});

test('history controls keep quarter annual YTD and instant requests distinct', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  const history = page.getByRole('region', { name: 'Reported financial trends', exact: true });
  for (const [kind, label, end, value] of [
    ['annual', 'Annual', 'Dec 31', '$5B'], ['half_year', 'Half-year YTD', 'Jun 30', '$2.4B'],
    ['nine_months', 'Nine-month YTD', 'Sep 30', '$3.7B'], ['quarter', 'Direct quarter', 'Mar 31', '$1B'],
  ]) {
    await page.getByRole('combobox', { name: 'History period', exact: true }).selectOption(kind);
    await expect(history.getByRole('table')).toBeVisible();
    await expect.poll(() => scenario.ledger.filter(item => item.path.endsWith('/metrics/revenue')).at(-1)?.query.get('period')).toBe(kind);
    const rows = history.getByRole('table').getByRole('row');
    await expect(rows).toHaveCount(4);
    await expect(rows.nth(1).getByRole('cell').nth(0)).toContainText(`${label} · Jan 1, 2023 – ${end}, 2023`);
    await expect(rows.nth(1).getByRole('cell').nth(1)).toContainText('Unavailable');
    await expect(rows.nth(1).getByRole('cell').nth(1)).toContainText('Synthetic source evidence is unavailable');
    await expect(rows.nth(2).getByRole('cell').nth(0)).toContainText(`${label} · Jan 1, 2024 – ${end}, 2024`);
    await expect(rows.nth(2).getByRole('cell').nth(1)).toHaveText('$0');
    await expect(rows.nth(3).getByRole('cell').nth(0)).toContainText(`${label} · Jan 1, 2025 – ${end}, 2025`);
    await expect(rows.nth(3).getByRole('cell').nth(1)).toHaveText(value);
    await page.getByRole('combobox', { name: 'Snapshot period', exact: true }).selectOption(kind);
    const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
    await expect(snapshot.locator('.metric-card').first().locator('.metric-value')).toHaveText(value);
    await expect(snapshot.locator('.period-label').first()).toContainText(`Jan 1, 2025 – ${end}, 2025`);
  }
  await page.getByRole('combobox', { name: 'Metric', exact: true }).selectOption('total_assets');
  await expect(page.getByRole('combobox', { name: 'History period', exact: true })).toHaveValue('instant');
  await expect(history.getByRole('row').nth(3).getByRole('cell').first()).toContainText('As of date · Dec 31, 2025');
  await expect(history.getByRole('row').nth(3).getByRole('cell').nth(1)).toHaveText('$750M');
  await expect(page.getByRole('combobox', { name: 'History period', exact: true }).locator('option')).toHaveCount(1);
  await page.getByRole('combobox', { name: 'Metric', exact: true }).selectOption('diluted_eps');
  await expect(history.getByRole('note')).toContainText('comparability unverified');
});

test('wrong snapshot company and wrong history period are rejected by real component guards', async ({ page, scenario }) => {
  scenario.overrides.push(request => request.path.endsWith('/summary') ? { body: data.summary('BBB') } : request.path.includes('/metrics/') ? { body: data.history('AAA', 'revenue', 'annual') } : undefined);
  await scenario.open();
  const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  const history = page.getByRole('region', { name: 'Reported financial trends', exact: true });
  await expect(snapshot.getByRole('alert')).toBeVisible();
  await expect(history.getByRole('alert')).toBeVisible();
  await expect(snapshot.locator('.metric-card')).toHaveCount(0);
  await expect(history.getByRole('table')).toHaveCount(0);
});

test('guided question focuses editor, makes no request until explicit submit, and exposes SEC evidence', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  const before = scenario.ledger.length;
  await page.getByRole('button', { name: 'Use question', exact: true }).click();
  await expect(editor).toHaveValue('What is the latest available revenue?');
  await expect(editor).toBeFocused();
  expect(scenario.ledger.slice(before).filter(item => item.method === 'POST' || item.path.endsWith('/context'))).toEqual([]);
  await page.getByRole('button', { name: 'Research question', exact: true }).click();
  const answer = page.getByRole('region', { name: 'Research Answer', exact: true });
  await expect(answer.locator('.metric-value')).toHaveText('$1B');
  await expect(page.getByRole('heading', { name: '1 SEC evidence passages', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate AI analysis', exact: true })).toBeDisabled();
  expect(scenario.ledger.filter(item => item.path.endsWith('/research-answer')).at(-1)?.body).toEqual({ question: 'What is the latest available revenue?' });
  expect(scenario.ledger.some(item => item.path.endsWith('/answer'))).toBe(false);
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB'); await scenario.ready('BBB');
  await expect(editor).toHaveValue(''); await expect(answer).toHaveCount(0);
});

test('metadata-only and malformed readiness cannot enter searchable selector or unsafe source links', async ({ page, scenario }) => {
  scenario.overrides.push(request => request.path.endsWith('/sources') ? { body: [...data.sources('AAA'), { ...data.sources('AAA')[0], accession_number: data.accession('AAA', '000003'), has_filing_chunks: 'true', sec_url: 'javascript:alert(1)' }] } : undefined);
  await scenario.open(); await scenario.ready();
  const selector = page.getByRole('combobox', { name: 'Indexed SEC filing', exact: true });
  await expect(selector.locator('option')).toHaveCount(1);
  await expect(selector).toHaveValue(data.accession('AAA'));
  await page.getByText('Other recorded filings · metadata only (1)', { exact: true }).click();
  await expect(page.getByText('Metadata only', { exact: true })).toBeVisible();
  await page.getByText('Evidence status unverified (1)', { exact: true }).click();
  await expect(page.locator('.recorded-filings').last().getByRole('link')).toHaveCount(0);
  expect(await page.getByRole('link').evaluateAll(links => links.every(link => !link.getAttribute('href')?.startsWith('javascript:')))).toBe(true);
});

test('invalid company-wide provenance is refused without erasing an independent direct answer', async ({ page, scenario }) => {
  scenario.overrides.push(request => request.path === '/companies/AAA/context' ? { body: { ...data.evidence('AAA', request.query.get('q')!, 0), citations: [{ ...data.evidence('BBB', request.query.get('q')!, 0).citations[0] }] } } : undefined);
  await scenario.open(); await scenario.ready();
  await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption('company');
  await page.getByRole('button', { name: 'Use question', exact: true }).click();
  await page.getByRole('button', { name: 'Research question', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Read the evidence', exact: true }).getByRole('alert')).toContainText('Evidence does not match this company');
  await expect(page.getByRole('region', { name: 'Research Answer', exact: true }).locator('.metric-value')).toHaveText('$1B');
  await expect(page.getByRole('heading', { name: '1 SEC evidence passages', exact: true })).toHaveCount(0);
});
