import { test, expect } from '@playwright/test';

const source = 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020-index.html';
const accession = '0000320193-26-000020';
const app = 'http://127.0.0.1:3000';

test('fresh Apple no-key Home shows the exact financial observation and the selected filing evidence', async ({ page, context }) => {
  const external: string[] = [];
  // Do not synthesize or intercept same-origin API responses.
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === app) return route.continue();
    external.push(url.href);
    return route.abort('blockedbyclient');
  });
  await page.goto('/');
  const company = page.getByLabel('Company', { exact: true });
  await expect(company).toBeEnabled();
  await company.selectOption('AAPL');
  const area = page.getByRole('region', { name: 'Financial questions', exact: true });
  const editor = area.getByLabel('Research question or search', { exact: true });
  const ask = area.getByRole('button', { name: 'Research question', exact: true });
  const selected = area.getByLabel('Indexed SEC filing', { exact: true });
  await expect(selected).toBeEnabled();
  await selected.selectOption(accession);

  await editor.fill("What was Apple's latest quarterly revenue?");
  await ask.click();
  const answer = area.getByRole('region', { name: 'Research Answer', exact: true });
  await expect(answer).toContainText('Deterministic');
  await answer.getByText('View provenance', { exact: true }).click();
  await expect(answer).toContainText(/Exact API value:\s*109417000000(?:\.0+)? USD\b/);
  await expect(answer).toContainText(/(?:Jun(?:e)? 27, 2026|27 Jun(?:e)? 2026)/);
  await expect(answer).toContainText(accession);
  await expect(answer.getByRole('link', { name: /Open official SEC filing/ }).first()).toHaveAttribute('href', source);

  await editor.fill('services net sales');
  await ask.click();
  await expect(area.getByRole('heading', { name: /SEC evidence passages/ })).toBeVisible();
  await expect(area.getByText('Search: “services net sales”', { exact: false })).toBeVisible();
  const evidence = area.locator('article.evidence-card').first();
  await expect(evidence).toBeVisible();
  await evidence.getByText('Filing and retrieval details', { exact: true }).click();
  await expect(evidence).toContainText('aapl-20260627.htm');
  await expect(evidence).toContainText(accession);
  const link = evidence.getByRole('link', { name: /Open official SEC source/ });
  await expect(link).toHaveAttribute('href', source);
  expect(external).toEqual([]);
  await link.press('Enter');
  await expect.poll(() => external).toEqual([source]);
  // The request target and user activation are observed; the page is not loaded.
});
