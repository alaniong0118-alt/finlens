import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

test('initial catalog network failure has bounded explicit retry', async ({ page, scenario }) => {
  let failing = true;
  scenario.overrides.push(request => request.path === '/companies' && failing ? { abort: true } : undefined);
  await scenario.open();
  await expect(page.getByRole('button', { name: 'Retry companies', exact: true })).toBeVisible();
  const attempts = scenario.count('/companies');
  expect(attempts).toBeLessThanOrEqual(2); // Development StrictMode may cancel its first mount.
  failing = false;
  await page.getByRole('button', { name: 'Retry companies', exact: true }).click();
  await scenario.ready();
  expect(scenario.count('/companies') - attempts).toBeLessThanOrEqual(2); // Retry plus evidence reconciliation.
});

for (const invalid of [null, -1, '1', 0.5]) {
  test(`unknown/malformed publication ${JSON.stringify(invalid)} waits unpinned until explicit retry`, async ({ page, scenario }) => {
    let failing = true;
    scenario.overrides.push(request => request.path.endsWith('/freshness') && failing ? { body: { ...data.freshness('AAA', 0), data_version: invalid }, version: null } : undefined);
    await scenario.open();
    await expect(page.getByRole('button', { name: 'Retry data check', exact: true })).toBeVisible();
    await expect(page.getByLabel('Data freshness')).toContainText('Could not verify this company’s data version');
    expect(scenario.ledger.filter(item => item.pin !== undefined)).toEqual([]);
    failing = false;
    await page.getByRole('button', { name: 'Retry data check', exact: true }).click();
    await scenario.ready();
    expect(scenario.ledger.filter(item => item.pin !== undefined).every(item => item.pin === '0')).toBe(true);
  });
}

test('initial freshness HTTP failure preserves unknown pin and permits explicit recovery', async ({ page, scenario }) => {
  let failing = true;
  scenario.overrides.push(request => request.path.endsWith('/freshness') && failing ? { status: 503, version: null } : undefined);
  await scenario.open();
  await expect(page.getByRole('button', { name: 'Retry data check', exact: true })).toBeVisible();
  expect(scenario.ledger.filter(item => item.pin !== undefined)).toHaveLength(0);
  failing = false;
  await page.getByRole('button', { name: 'Retry data check', exact: true }).click(); await scenario.ready();
});

test('delayed freshness makes no version-dependent request before a genuine pin', async ({ page, scenario }) => {
  scenario.versions.AAA = 1;
  const barrier = scenario.hold(request => request.path.endsWith('/freshness'));
  await scenario.open();
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true })).toContainText('Waiting for publication version');
  expect(scenario.ledger.filter(item => item.pin !== undefined)).toHaveLength(0);
  barrier.release(); await scenario.ready();
  expect(scenario.ledger.filter(item => item.pin !== undefined).every(item => item.pin === '1')).toBe(true);
});

test('snapshot rejected cache entry is evicted; retry retains company and selected interval', async ({ page, scenario }) => {
  let failing = true;
  scenario.overrides.push(request => request.path.endsWith('/summary') && request.query.get('period') === 'annual' && failing ? { status: 503 } : undefined);
  await scenario.open(); await scenario.ready();
  await page.getByRole('combobox', { name: 'Snapshot period', exact: true }).selectOption('annual');
  await expect(page.getByRole('button', { name: 'Retry snapshot', exact: true })).toBeVisible();
  const count = scenario.count('/companies/AAA/financials/summary');
  failing = false;
  await page.getByRole('button', { name: 'Retry snapshot', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-card').first().locator('.metric-value')).toHaveText('$5B');
  await expect(page.getByRole('combobox', { name: 'Snapshot period', exact: true })).toHaveValue('annual');
  await expect(page.getByRole('combobox', { name: 'Company', exact: true })).toHaveValue('AAA');
  expect(scenario.count('/companies/AAA/financials/summary')).toBe(count + 1);
});

test('source failure keeps independent pinned direct research accessible and retry retains editor and answer', async ({ page, scenario }) => {
  let failing = true;
  scenario.overrides.push(request => request.path.endsWith('/sources') && failing ? { status: 503 } : undefined);
  await scenario.open();
  await expect(page.getByRole('button', { name: 'Retry filing list', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Use question', exact: true }).click();
  await page.getByRole('button', { name: 'Research question', exact: true }).click();
  const direct = page.getByRole('region', { name: 'Research Answer', exact: true });
  await expect(direct.locator('.metric-value')).toHaveText('$1B');
  expect(scenario.ledger.some(item => item.path.endsWith('/context') || item.path.endsWith('/answer'))).toBe(false);
  expect(scenario.ledger.filter(item => item.path.endsWith('/research-answer')).at(-1)?.pin).toBe('0');
  failing = false;
  const count = scenario.count('/companies/AAA/sources');
  await page.getByRole('button', { name: 'Retry filing list', exact: true }).click(); await scenario.ready();
  expect(scenario.count('/companies/AAA/sources')).toBe(count + 1);
  await expect(page.getByRole('textbox', { name: 'Research question or search', exact: true })).toHaveValue('What is the latest available revenue?');
  await expect(direct.locator('.metric-value')).toHaveText('$1B');
});

test('missing required publication header refuses snapshot without fabricated values', async ({ page, scenario }) => {
  scenario.overrides.push(request => request.path.endsWith('/summary') ? { body: data.summary('AAA'), version: null } : undefined);
  await scenario.open();
  const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  await expect(snapshot.getByRole('alert')).toContainText('Published response version could not be verified');
  await expect(snapshot.locator('.metric-card')).toHaveCount(0);
});

test('same-pin freshness outage retains loaded financial research and controls without fan-out', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  await page.getByRole('combobox', { name: 'Snapshot period', exact: true }).selectOption('annual');
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-card').first().locator('.metric-value')).toHaveText('$5B');
  const count = scenario.ledger.filter(item => item.pin !== undefined).length;
  let failing = true;
  scenario.overrides.push(request => request.path.endsWith('/freshness') && failing ? { status: 503, version: null } : undefined);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByLabel('Data freshness')).toContainText('Already loaded research remains available');
  await expect(page.getByRole('combobox', { name: 'Snapshot period', exact: true })).toHaveValue('annual');
  failing = false;
  await page.getByRole('button', { name: 'Retry data check', exact: true }).click();
  await expect(page.getByLabel('Data freshness')).not.toContainText('check unavailable');
  expect(scenario.ledger.filter(item => item.pin !== undefined)).toHaveLength(count);
});

test('current-pin mismatch fails closed, rejects same-pin retries and recovers only after reconciliation', async ({ page, scenario }) => {
  let mismatch = true;
  scenario.overrides.push(request => request.path.endsWith('/summary') && mismatch ? { body: data.summary('AAA'), version: '1' } : undefined);
  await scenario.open();
  await expect(page.getByRole('button', { name: 'Retry data check', exact: true })).toBeVisible();
  const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  await expect(snapshot.locator('.metric-card')).toHaveCount(0);
  const previous = scenario.ledger.filter(item => item.pin !== undefined).length;
  await page.getByRole('button', { name: 'Retry data check', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retry data check', exact: true })).toBeEnabled();
  expect(scenario.ledger.filter(item => item.pin !== undefined)).toHaveLength(previous);
  mismatch = false; scenario.versions.AAA = 1;
  await page.getByRole('button', { name: 'Retry data check', exact: true }).click(); await scenario.ready();
  await expect(page.getByLabel('Data freshness')).toContainText('version 1');
});

test('concurrent genuine 409s coalesce one pending freshness reconciliation', async ({ page, scenario }) => {
  const old = scenario.hold(request => request.pin === '0', () => ({ status: 409, version: '1', code: 'DATA_VERSION_CHANGED' }));
  await scenario.open();
  await expect.poll(() => scenario.ledger.filter(item => item.pin === '0').length).toBeGreaterThanOrEqual(3);
  const baseline = scenario.count('/companies/AAA/freshness');
  const reconcile = scenario.hold(request => request.path === '/companies/AAA/freshness');
  scenario.versions.AAA = 1; old.release();
  await expect(page.getByLabel('Data freshness')).toContainText('Research waits until');
  await expect.poll(() => scenario.count('/companies/AAA/freshness')).toBe(baseline + 1);
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-card')).toHaveCount(0);
  reconcile.release(); await scenario.ready();
  expect(scenario.count('/companies/AAA/freshness')).toBe(baseline + 1);
});

for (const from of [0, 1]) {
  test(`obsolete ${from} 409 delivered despite ignored abort preserves independently verified ${from + 1}`, async ({ page, scenario }) => {
    scenario.versions.AAA = from;
    await scenario.ignoreTransportAbort('/companies/AAA/financials/summary');
    const barrier = scenario.hold(request => request.path.endsWith('/summary') && request.pin === String(from), () => ({ status: 409, version: String(from + 1), code: 'DATA_VERSION_CHANGED' }));
    await scenario.open();
    await expect.poll(() => scenario.ledger.some(item => item.path.endsWith('/summary') && item.pin === String(from))).toBe(true);
    scenario.versions.AAA = from + 1;
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await scenario.ready();
    await expect(page.getByLabel('Data freshness')).toContainText(`version ${from + 1}`);
    const count = scenario.count('/companies/AAA/freshness');
    barrier.release();
    await expect.poll(() => scenario.abortedDeliveries('/companies/AAA/financials/summary', String(from), 409, '?period=quarter')).toBeGreaterThan(0);
    await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-card').first().locator('.metric-value')).toHaveText('$1B');
    await expect(page.getByLabel('Data freshness')).not.toContainText('Research waits until');
    expect(scenario.count('/companies/AAA/freshness')).toBe(count);
  });
}

test('rapid switching isolates old identity even when transport ignores abort', async ({ page, scenario }) => {
  await scenario.ignoreTransportAbort('/companies/AAA/financials/summary');
  const old = scenario.hold(request => request.path === '/companies/AAA/financials/summary', () => ({ body: data.summary('AAA'), version: '0' }));
  await scenario.open();
  await expect.poll(() => scenario.count('/companies/AAA/financials/summary')).toBeGreaterThan(0);
  const picker = page.getByRole('combobox', { name: 'Company', exact: true });
  await picker.selectOption('BBB'); await picker.selectOption('AAA'); await picker.selectOption('BBB');
  await scenario.ready('BBB'); old.release();
  await expect.poll(() => scenario.abortedDeliveries('/companies/AAA/financials/summary', '0', 200, '?period=quarter')).toBeGreaterThan(0);
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-card').first().locator('.metric-value')).toHaveText('$2B');
  await expect(page.getByRole('heading', { name: 'Synthetic Alpha', exact: true })).toHaveCount(0);
});
