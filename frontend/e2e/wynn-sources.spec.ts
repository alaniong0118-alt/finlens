import { test, expect } from './fixtures/browser';

test('Wynn official-source guide keeps the confirmed issuer notice independent from the licence register', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  const draft = page.getByRole('textbox', {name: 'Event, question or reference URL', exact: true});
  const question = 'Can a Wynn Macau announcement tell me who holds the gaming concession?';
  const confirm = page.getByRole('button',{name: 'Confirm Wynn Macau, Limited (HKEX 1128)', exact: true});
  const guide = page.getByRole('region',{name: 'Wynn Macau official source guide', exact: true});
  const before = scenario.ledger.length;
  await draft.fill(question);
  await draft.press('Enter');
  await expect(confirm).toBeVisible();
  await expect(guide).toHaveCount(0);
  await expect(draft).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button',{name:'Keep research draft',exact:true})).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(confirm).toBeFocused();
  await page.keyboard.press('Enter');
  const cancel = page.getByRole('button',{name: 'Cancel issuer confirmation', exact: true});
  await expect(cancel).toBeFocused();
  await expect(cancel).toHaveAttribute('aria-expanded','true');
  await expect(guide).toBeVisible();
  await expect(page.locator('#research-draft-premise')).toHaveText(question);
  const notice = guide.getByRole('region',{name: 'Listed issuer notice', exact: true});
  await expect(notice).toContainText('Document date: 27 April 2026');
  await expect(notice).toContainText('does not establish who holds a gaming concession');
  await expect(notice.getByRole('link')).toHaveAttribute('href','https://www.hkexnews.hk/listedco/listconews/sehk/2026/0424/2026042401631_c.pdf');
  const registry = guide.getByRole('region',{name: 'Check the licence holder', exact: true});
  await expect(registry.getByRole('link')).toHaveAttribute('href','https://www.dicj.gov.mo/web/EN/information/contacts_casino/content.html');
  await expect(registry).toContainText('did not verify the licence holder');
  expect(scenario.ledger).toHaveLength(before);
  await page.keyboard.press('Tab');
  await expect(notice.getByRole('link')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(cancel).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(confirm).toBeFocused();
  await expect(guide).toHaveCount(0);
  await confirm.click();
  const handoff = guide.getByRole('button', {name: 'Add issuer notice link to comparison', exact: true});
  await handoff.click();
  const manual = page.getByRole('region', {name: 'Manual evidence comparison', exact: true});
  await expect(manual.getByLabel('Source reference A', {exact: true})).toHaveValue(
    'https://www.hkexnews.hk/listedco/listconews/sehk/2026/0424/2026042401631_c.pdf');
  await expect(manual.getByLabel('Publication date A', {exact: true})).toHaveValue('');
  expect(scenario.ledger).toHaveLength(before);
  await draft.fill('Can a Wynn Resorts (NASDAQ: WYNN) announcement tell me who holds the gaming concession?');
  await draft.press('Enter');
  await expect(confirm).toHaveCount(0);
  await expect(guide).toHaveCount(0);
});

test('Wynn source links and competing assessments survive download and a fresh Home reopen', async ({ page, scenario }) => {
  await scenario.open();
  await scenario.ready();
  const question = 'Can a Wynn Macau announcement tell me who holds the gaming concession?';
  const issuer = 'https://www.hkexnews.hk/listedco/listconews/sehk/2026/0424/2026042401631_c.pdf';
  const regulator = 'https://www.dicj.gov.mo/web/EN/information/contacts_casino/content.html';
  const draft = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  const manual = page.getByRole('region', { name: 'Manual evidence comparison', exact: true });
  const field = (name: string) => manual.getByLabel(name, { exact: true });
  const button = (name: string) => page.getByRole('button', { name, exact: true });
  const before = scenario.ledger.length;
  await draft.fill(question);
  await draft.press('Enter');
  await button('Confirm Wynn Macau, Limited (HKEX 1128)').press('Enter');
  await button('Add issuer notice link to comparison').press('Enter');
  await expect(field('Source reference A')).toHaveValue(issuer);
  await expect(field('Publication date A')).toHaveValue('');
  await expect(field('Source reference B')).toHaveValue('');
  const syntheticA = 'Synthetic issuer extract: an operator is named.';
  const syntheticB = 'Synthetic check: the directory does not establish the event date.';
  const support = 'The named operator is relevant but requires independent verification.';
  const challenge = 'The directory cannot establish when the concession began.';
  const judgment = 'The operator may be identifiable; the historical start date is still uncertain.';
  const change = 'A dated official award notice naming the same operator.';
  for (const [name, value] of [
    ['Passage A', syntheticA], ['Locator A', 'Fixture locator A'], ['Assessment rationale A', support],
    ['Source reference B', regulator], ['Passage B', syntheticB],
    ['Locator B', 'Fixture locator B'], ['Assessment rationale B', challenge],
    ['Provisional judgment', judgment], ['Evidence that would change the judgment', change],
  ]) await field(name).fill(value);
  await field('Assessment A').selectOption('supports');
  await field('Assessment B').selectOption('challenges');
  await button('Record provisional judgment').press('Enter');
  const [file] = await Promise.all([
    page.waitForEvent('download'), button('Download recorded comparison (.json)').press('Enter'),
  ]);
  expect(file.suggestedFilename()).toBe('finlens-manual-comparison-v1.json');
  expect(await file.failure()).toBeNull();
  const path = await file.path();
  expect(scenario.ledger.slice(before)).toEqual([]);
  await page.reload();
  await scenario.ready();
  await expect.poll(() => [scenario.count('/companies'), scenario.count('/capabilities')]).toEqual([2, 2]);
  const after = scenario.ledger.length;
  await expect(draft).toHaveValue('');
  await expect(manual).toHaveCount(0);
  await page.getByLabel('Open a recorded comparison (.json)', { exact: true }).setInputFiles(path);
  const preview = page.getByRole('region', { name: 'Reopened comparison preview', exact: true });
  for (const value of [question, judgment, change]) await expect(preview).toContainText(value);
  for (const [slot, fields] of [
    ['A', [issuer, syntheticA, 'Fixture locator A', 'Not recorded', 'supports', support]],
    ['B', [regulator, syntheticB, 'Fixture locator B', 'Not recorded', 'challenges', challenge]],
  ] as const) {
    const source = preview.locator(':scope > section').filter({
      has: page.getByRole('heading', { name: 'Manual source ' + slot + ' · not verified', exact: true }),
    });
    await expect(source.locator('dt')).toHaveText(['Source reference', 'Passage', 'Locator', 'Publication date', 'Assessment', 'Assessment rationale']);
    await expect(source.locator('dd')).toHaveText([...fields]);
  }
  await expect(preview.locator('input, textarea, select, button, a')).toHaveCount(0);
  await expect(draft).toHaveValue('');
  await expect(button('Download recorded comparison (.json)')).toHaveCount(0);
  expect(scenario.ledger.slice(after)).toEqual([]);
  expect(scenario.violations).toEqual([]);
});

test('Wynn Traditional Chinese question stays scoped to the confirmed issuer and separates the regulator', async ({ page, scenario }) => {
  await scenario.open();
  await scenario.ready();
  const before = scenario.ledger.length;
  const draft = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  const confirm = page.getByRole('button', { name: 'Confirm Wynn Macau, Limited (HKEX 1128)', exact: true });
  const guide = page.getByRole('region', { name: 'Wynn Macau official source guide', exact: true });
  await draft.fill('永利澳門的公告能告訴我誰持有博彩經營批給嗎？');
  await draft.press('Enter');
  await expect(confirm).toBeVisible();
  await expect(guide).toHaveCount(0);
  await confirm.press('Enter');
  await expect(guide.getByRole('region', { name: 'Listed issuer notice' })).toContainText('does not establish who holds a gaming concession');
  await expect(guide.getByRole('region', { name: 'Check the licence holder' })).toContainText('did not verify the licence holder');
  await draft.fill('永利度假村的公告能告訴我誰持有博彩經營批給嗎？');
  await draft.press('Enter');
  await expect(confirm).toHaveCount(0);
  await expect(guide).toHaveCount(0);
  expect(scenario.ledger.slice(before)).toEqual([]);
  expect(scenario.violations).toEqual([]);
});
