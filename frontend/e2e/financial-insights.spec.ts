import type { Locator, Worker } from '@playwright/test';
import { test, expect, origin } from './fixtures/browser';

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
});
