import type { Locator, Page } from '@playwright/test';
import { test, expect, dualSources, dualEvidence } from './fixtures/dual-filing-browser';
import { lifecycle, replayCancellations, annualRequestCursor, captureFocusPaint, assessFocusPaint,
  expectFullLedger, publicationCompletions, publicationHeaderCancellations, completedRequests, expectedRequest, type ExpectedLedger } from './fixtures/annual-period-browser';

// Reuse the strict shared focus-paint oracle, with native keyboard navigation.
async function focusEvidence(page: Page, control: Locator, name: string) {
  const paint = await control.evaluate(captureFocusPaint), contrast = assessFocusPaint(paint.outlineColor, paint.surfaces);
  await test.info().attach(`${name}-focus`, { body: JSON.stringify({ paint, contrast }), contentType: 'application/json' });
  await test.info().attach(`${name}-viewport`, { body: await page.screenshot({ fullPage: false, scale: 'device', caret: 'initial', animations: 'allow' }), contentType: 'image/png' });
  await expect(control).toBeFocused(); expect(paint.visible).toBe(true); expect(paint.outline).not.toBe('none'); expect(paint.width).toBeGreaterThan(0);
  expect(paint.rect.left - paint.extent).toBeGreaterThanOrEqual(paint.clip.left); expect(paint.rect.right + paint.extent).toBeLessThanOrEqual(paint.clip.right);
  expect(paint.rect.top - paint.extent).toBeGreaterThanOrEqual(paint.clip.top); expect(paint.rect.bottom + paint.extent).toBeLessThanOrEqual(paint.clip.bottom);
  expect(contrast.sufficient, JSON.stringify({ paint, contrast })).toBe(true);
}
async function tabTo(page: Page, control: Locator, name: string, maximum = 40) {
  for (let i = 0; i < maximum; i++) {
    await page.keyboard.press('Tab');
    if (await control.evaluate(element => element === document.activeElement)) { await focusEvidence(page, control, name); return; }
  }
  await test.info().attach(`${name}-tab-exhaustion`, { body: await page.screenshot({ fullPage: false }), contentType: 'image/png' });
  throw new Error('Native Tab did not reach dual-filing control');
}
const panel = (page: Page) => page.getByRole('region', { name: 'Compare two filing sources', exact: true });
const contextPath = (ticker: string, index: number) => `/companies/${ticker}/filings/${dualSources(ticker)[index].accession_number}/context`;
const pair = (ticker = 'AAA', pin = 0, question = 'supply chain') => [0, 1].map(index => expectedRequest(contextPath(ticker, index), pin, new URLSearchParams({ q: question, limit: '5' }).toString()));
function initial(): ExpectedLedger { return { completed: [...completedRequests([expectedRequest('/companies'), expectedRequest('/capabilities')]), ...publicationCompletions()],
  cancelled: replayCancellations(), pending: [], cancelledAfterHeaders: publicationHeaderCancellations() }; }

test('dual filing: original sources, strict pair accounting, native keyboard and responsive layout', async ({ page, dualScenario: scenario }) => {
  await scenario.open(); await scenario.ready(); const expected = initial(); await expectFullLedger(scenario, expected);
  const section = panel(page), input = section.getByRole('textbox', { name: 'Question for both filings', exact: true });
  await expect(section.getByRole('combobox', { name: 'Filing A', exact: true })).toHaveValue(dualSources('AAA')[0].accession_number);
  await expect(section.getByRole('combobox', { name: 'Filing B', exact: true })).toHaveValue(dualSources('AAA')[1].accession_number);
  await input.fill('supply chain'); await expectFullLedger(scenario, expected);
  // Pointer editing positions the form; all activation/disclosure focus checks use native Tab.
  await tabTo(page, section.getByRole('button', { name: 'Compare filing evidence', exact: true }), 'compare', 4);
  await page.keyboard.press('Enter'); expected.completed.push(...completedRequests(pair()));
  await expect(section.locator('article')).toHaveCount(4); await expectFullLedger(scenario, expected);
  await expect(section).toContainText('Publication 0'); await expect(section.locator('script')).toHaveCount(0);
  const disclosure = section.getByText('Filing A excerpt 1 source details', { exact: true });
  await tabTo(page, disclosure, 'source-details', 5); await page.keyboard.press('Space');
  await expect(disclosure.locator('..')).toHaveAttribute('open', ''); await expect(disclosure).toBeFocused();
  const source = disclosure.locator('..').getByRole('link', { name: 'Open official SEC source ↗', exact: true });
  await page.keyboard.press('Tab'); await focusEvidence(page, source, 'sec-link'); await expect(source).toHaveAttribute('href', dualSources('AAA')[0].sec_url);
  await expectFullLedger(scenario, expected);
  const layout = await section.evaluate(element => ({ width: document.documentElement.scrollWidth, viewport: innerWidth,
    columns: [...element.querySelectorAll('.dual-filing-column')].map(node => { const r = node.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top }; }) }));
  expect(layout.width).toBeLessThanOrEqual(layout.viewport); layout.columns.forEach(column => { expect(column.left).toBeGreaterThanOrEqual(0); expect(column.right).toBeLessThanOrEqual(layout.viewport); });
  if (layout.viewport === 390) expect(layout.columns[1].top).toBeGreaterThan(layout.columns[0].top); else expect(layout.columns[1].top).toBe(layout.columns[0].top);
  await input.fill('competition'); await expect(section.locator('article')).toHaveCount(0); await expectFullLedger(scenario, expected);
});

test('dual filing: one empty/error side cannot borrow the other filing and duplicate selection disables submit', async ({ page, dualScenario: scenario }) => {
  let mode: 'empty' | 'error' = 'empty';
  scenario.overrides.push(item => item.path === contextPath('AAA', 1) ? mode === 'empty'
    ? { body: dualEvidence('AAA', dualSources('AAA')[1].accession_number, item.query.get('q')!, 0) } : { status: 503 } : undefined);
  await scenario.open(); await scenario.ready(); const expected = initial(); await expectFullLedger(scenario, expected);
  const section = panel(page); await section.getByRole('textbox').fill('supply chain'); await section.getByRole('button', { name: 'Compare filing evidence', exact: true }).click();
  expected.completed.push(...completedRequests(pair())); await expectFullLedger(scenario, expected);
  await expect(section.locator('.dual-filing-column').nth(1)).toContainText('Insufficient evidence in this filing'); await expect(section.locator('.dual-filing-column').nth(1).locator('article')).toHaveCount(0);
  mode = 'error'; await section.getByRole('button', { name: 'Compare filing evidence', exact: true }).click();
  expected.completed.push(...completedRequests([pair()[0]]), ...completedRequests([pair()[1]], 503)); await expectFullLedger(scenario, expected);
  await expect(section.locator('.dual-filing-column').nth(0).locator('article')).toHaveCount(2); await expect(section.locator('.dual-filing-column').nth(1).getByRole('alert')).toContainText('could not be verified');
  await section.getByRole('combobox', { name: 'Filing B', exact: true }).selectOption(dualSources('AAA')[0].accession_number);
  await expect(section.getByRole('button', { name: 'Compare filing evidence', exact: true })).toBeDisabled(); await expect(section.locator('article')).toHaveCount(0); await expectFullLedger(scenario, expected);
});

test('dual filing: cancel blocks deliberately delivered ignored-abort responses', async ({ page, dualScenario: scenario }) => {
  await scenario.ignoreTransportAbort(contextPath('AAA', 0));
  const hold = scenario.hold(item => item.path === contextPath('AAA', 0), item => ({ body: dualEvidence('AAA', item.path.split('/')[4], item.query.get('q')!) }));
  await scenario.open(); await scenario.ready(); const expected = initial(); await expectFullLedger(scenario, expected);
  const section = panel(page); await section.getByRole('textbox').fill('supply chain'); const cursor = annualRequestCursor(scenario);
  await section.getByRole('button', { name: 'Compare filing evidence', exact: true }).click();
  await expect.poll(() => lifecycle(scenario, replayCancellations()).rows.filter(row => row.id > cursor).length).toBe(2);
  await expect(section.locator('.dual-filing-column').nth(1).locator('article')).toHaveCount(2);
  await tabTo(page, section.getByRole('button', { name: 'Cancel filing comparison', exact: true }), 'cancel', 3); await page.keyboard.press('Space');
  await expect(section.locator('.dual-filing-column')).toHaveCount(0); hold.release();
  for (const path of [contextPath('AAA', 0)]) await expect.poll(() => scenario.abortedDeliveries(path, '0', 200, '?q=supply+chain&limit=5')).toBe(1);
  expected.completed.push(...completedRequests(pair())); await expectFullLedger(scenario, expected);
  await expect(section.locator('article')).toHaveCount(0); await expect(section.getByRole('button', { name: 'Cancel filing comparison', exact: true })).toBeFocused();
});
