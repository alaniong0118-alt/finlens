import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { lstat, mkdir, readFile, realpath, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import type { Locator } from '@playwright/test';
import { test, expect, origin } from './fixtures/browser';
import * as data from './fixtures/data';

const label = 'SYNTHETIC TEST DATA — NOT REAL SEC FINANCIAL RESULTS';
const baseline = '2e45d04b2adec942d90c3548c3a104a990c7f249';
const bindingPaths = [
  'e2e/fixtures/data.ts', 'e2e/fixtures/browser.ts', 'e2e/fixtures/ignored-abort.ts',
  'playwright.config.ts', 'playwright.capture.config.ts', 'e2e/research-walkthrough.capture.ts',
];

test('portable synthetic research walkthrough', async ({ page, context, browser, scenario }, info) => {
  expect(process.platform).toBe('linux');
  expect(process.env.FINLENS_CAPTURE_AUTHORIZED).toBe('true');
  const sourceRevision = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  expect(sourceRevision).toBe(process.env.FINLENS_CAPTURE_REVISION);
  const admissionBytes = await readFile(resolve('test-results/research-walkthrough/source-admission.json'));
  const renderInventory = JSON.parse(admissionBytes.toString('utf8'));
  expect(renderInventory.source_revision).toBe(sourceRevision);
  const raw = resolve('test-results/research-walkthrough/raw');
  expect(await realpath(process.cwd())).toBe(process.cwd());
  for (const parent of ['test-results', 'test-results/research-walkthrough']) {
    await mkdir(resolve(parent)).catch(error => { if (error.code !== 'EEXIST') throw error; });
    const stat = await lstat(resolve(parent));
    expect(stat.isDirectory() && !stat.isSymbolicLink()).toBe(true);
  }
  // Fresh-run custody: refuse stale evidence instead of overwriting/cleaning it.
  await mkdir(raw);
  const startedAt = new Date().toISOString();
  const captures: { name: string; captured_at: string; full_page: boolean }[] = [];

  await scenario.open(); await scenario.ready();
  expect(page.viewportSize()).toEqual({ width: 1440, height: 1000 });
  expect(await page.evaluate(() => ({ scale: devicePixelRatio, locale: navigator.language,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    light: matchMedia('(prefers-color-scheme: light)').matches })))
    .toEqual({ scale: 1, locale: 'en-US', timezone: 'UTC', light: true });
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('AAA');
  await scenario.ready('AAA');
  await page.evaluate(text => {
    const banner = document.createElement('aside');
    banner.id = 'synthetic-capture-annotation';
    banner.setAttribute('role', 'note');
    banner.textContent = text;
    Object.assign(banner.style, { position: 'fixed', top: '0', left: '0', right: '0',
      zIndex: '2147483647', padding: '18px', background: '#fff3cd', color: '#402b00',
      font: 'bold 20px sans-serif', textAlign: 'center', borderBottom: '3px solid #886000' });
    document.body.append(banner);
  }, label);
  const capture = async (name: string, target: Locator, fullPage = false) => {
    await page.evaluate(async () => { await document.fonts.ready; });
    if (fullPage) await page.evaluate(() => window.scrollTo(0, 0));
    else await target.evaluate(element => window.scrollTo(0, window.scrollY + element.getBoundingClientRect().top - 90));
    await expect(page.locator('#synthetic-capture-annotation')).toHaveText(label);
    await expect(target).toBeVisible();
    await page.screenshot({ path: resolve(raw, name), fullPage, animations: 'disabled', caret: 'hide', scale: 'css' });
    captures.push({ name, captured_at: new Date().toISOString(), full_page: fullPage });
  };

  const snapshot = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  const revenue = snapshot.locator('.metric-card').filter({ has: page.getByRole('heading', { name: 'Revenue', exact: true }) });
  await expect(page.getByRole('heading', { name: 'Synthetic Alpha', exact: true })).toBeVisible();
  await expect(revenue.locator('.metric-value')).toHaveText('$1B');
  await expect(snapshot.locator('.period-label').first()).toContainText('Jan 1, 2025 – Mar 31, 2025');
  await capture('01-synthetic-company-revenue.png', page.locator('.company-overview'));
  await expect(revenue.locator('.metric-value')).toBeInViewport();

  await revenue.getByText('Sources and details', { exact: true }).click();
  await expect(revenue.getByText('Synthetic_revenue', { exact: true })).toBeVisible();
  await expect(revenue.getByText('1000000000 USD', { exact: true })).toBeVisible();
  await expect(revenue.getByText(data.accession('AAA'), { exact: false })).toBeVisible();
  await expect(revenue.getByRole('link', { name: 'Open official SEC filing' })).toHaveAttribute('href', data.secUrl('AAA'));
  await capture('02-synthetic-period-provenance.png', revenue);

  await page.getByLabel('Company 1', { exact: true }).selectOption('AAA');
  await page.getByLabel('Company 2', { exact: true }).selectOption('BBB');
  const table = page.getByRole('region', { name: 'Annual company comparison table', exact: true });
  await expect(page.getByRole('combobox', { name: 'Annual fiscal end-year', exact: true })).toHaveValue('2025');
  const copy = page.getByRole('button', { name: 'Copy research note for Revenue', exact: true });
  const row = table.getByRole('row').filter({ has: copy });
  await expect(copy).toBeEnabled();
  await expect(row.getByRole('cell').nth(0).locator('.metric-value')).toHaveText('$5B');
  await expect(row.getByRole('cell').nth(1).locator('.metric-value')).toHaveText('$9B');
  for (const [index, ticker, version] of [[1, 'AAA', 0], [2, 'BBB', 1]] as const) {
    const header = table.getByRole('columnheader').nth(index);
    await expect(header).toContainText(ticker);
    await expect(header).toContainText(`Publication ${version}`);
    await expect(header).toContainText('Jan 1, 2025 – Dec 31, 2025');
    expect(scenario.ledger.filter(item => item.path === `/companies/${ticker}/financials/annual`)
      .every(item => item.pin === String(version))).toBe(true);
  }
  await capture('03-synthetic-annual-comparison.png', page.locator('.company-comparison'));
  await expect(row).toBeInViewport();

  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
  await page.bringToFront();
  expect(await page.evaluate(() => isSecureContext && typeof navigator.clipboard?.readText === 'function'
    && typeof navigator.clipboard?.writeText === 'function')).toBe(true);
  await page.evaluate(() => navigator.clipboard.writeText('REL-PRODUCT-03 native clipboard sentinel'));
  const requestsBeforeCopy = scenario.ledger.length;
  await copy.click();
  await expect(row.getByRole('status')).toHaveText('Research note copied.');
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('# FinLens research note\n');
  const note = await page.evaluate(() => navigator.clipboard.readText());
  for (const text of ['- Ticker: AAA', '- Ticker: BBB', '- Exact normalized value: 5000000000\n',
    '- Exact normalized value: 9000000000\n', '- Independent publication version: 0',
    '- Independent publication version: 1', 'publication versions are not freshness guarantees.']) expect(note).toContain(text);
  expect(scenario.ledger).toHaveLength(requestsBeforeCopy);
  await writeFile(resolve(raw, 'synthetic-research-note.md'), Buffer.from(note, 'utf8'), { flag: 'wx' });
  const freshness = page.getByRole('region', { name: 'Data freshness', exact: true });
  await freshness.getByText('Freshness scope and synchronization', { exact: true }).click();
  await expect(freshness).toContainText('Synthetic publications only.');
  await expect(freshness).toContainText('A recent check does not guarantee complete SEC coverage.');
  await expect(page.locator('footer')).toContainText('No investment recommendations or price forecasts.');
  await expect(row.getByRole('status')).toHaveText('Research note copied.');
  await capture('04-synthetic-copy-freshness.png', freshness, true);
  expect(scenario.violations).toEqual([]);
  expect(scenario.ledger.every(item => item.method === 'GET')).toBe(true);

  const require = createRequire(resolve('package.json'));
  const bindings = Object.fromEntries(await Promise.all(bindingPaths.map(async name =>
    [`frontend/${name}`, createHash('sha256').update(await readFile(resolve(name))).digest('hex')])));
  const metadata = { schema_version: 1, label, expected_baseline: baseline, source_revision: sourceRevision,
    test: info.title, project: info.project.name, config: 'frontend/playwright.capture.config.ts',
    settings: { viewport: { width: 1440, height: 1000 }, theme: 'light', locale: 'en-US', timezone: 'UTC', scale: 1 },
    runtime: { node: process.version, platform: process.platform, arch: process.arch, chromium: browser.version(),
      playwright: require('@playwright/test/package.json').version, next: require('next/package.json').version },
    started_at: startedAt, completed_at: new Date().toISOString(), captures, bindings,
    render_inventory: renderInventory, admission_sha256: createHash('sha256').update(admissionBytes).digest('hex'),
    clipboard: { mechanism: 'native Chromium navigator.clipboard.readText', encoding: 'UTF-8',
      sha256: createHash('sha256').update(Buffer.from(note, 'utf8')).digest('hex') },
    network: { requests: scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin: pin ?? null, query: query.toString() })),
      failures: scenario.failures, violations: scenario.violations },
    // Test-body observations only. Packaging additionally requires a successful
    // runner result and workflow step exit, including fixture/server teardown.
    execution_scope: 'synthetic frontend only; live database NOT VERIFIED' };
  await writeFile(resolve(raw, 'capture.json'), `${JSON.stringify(metadata, null, 2)}\n`, { flag: 'wx' });
});
