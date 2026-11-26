import { expect, test } from './fixtures/browser';

test('Home keeps a pasted HTTPS reference inert and only adds it after explicit action', async ({ page, scenario }) => {
  await scenario.open();
  await scenario.ready();
  const before = scenario.ledger.length;
  const url = page.url();
  const savedState = () => page.evaluate(() => [localStorage, sessionStorage].map(store =>
    Object.keys(store).sort().map(key => [key, store.getItem(key)])));
  const savedBefore = await savedState();
  let downloads = 0;
  page.on('download', () => { downloads++; });
  const premise = page.locator('#research-draft-premise');
  const draft = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  const add = page.getByRole('button', { name: 'Add pasted link to comparison', exact: true });
  const comparison = page.getByRole('region', { name: 'Manual evidence comparison', exact: true });
  const sourceA = comparison.getByLabel('Source reference A', { exact: true });
  const rejected = 'https://example.org/report?signature=synthetic-only';
  await draft.fill(rejected);
  await draft.press('Enter');
  await expect(premise).toHaveText(rejected);
  await expect(add).toHaveCount(0);
  await expect(comparison.getByRole('button', { name: 'Compare two manual sources', exact: true })).toBeVisible();
  const userRef = 'https://example.org/reports/' + 'q'.repeat(180) + '.pdf';
  await draft.fill(userRef);
  await expect(add).toHaveCount(0);
  await draft.press('Enter');
  await expect(add).toBeVisible();
  await expect(page.locator('a[href="' + userRef + '"]')).toHaveCount(0);
  await expect(sourceA).toHaveValue('');
  const narrow = page.viewportSize()?.width === 390;
  if (narrow) {
    await expect(premise).toHaveText(userRef);
    const fit = await premise.evaluate(element => {
      const range = document.createRange();
      range.selectNodeContents(element);
      const lines = Array.from(range.getClientRects()).filter(rect => rect.width > 0);
      const box = element.getBoundingClientRect();
      return {
        width: window.innerWidth,
        lines: new Set(lines.map(rect => Math.round(rect.top))).size,
        inside: lines.length > 0 && lines.every(rect =>
          rect.left >= Math.max(0, box.left) - 1 && rect.right <= Math.min(window.innerWidth, box.right) + 1 &&
          rect.top >= box.top - 1 && rect.bottom <= box.bottom + 1),
        noOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      };
    });
    expect(fit).toMatchObject({ width: 390, inside: true, noOverflow: true });
    expect(fit.lines).toBeGreaterThan(1);
    await add.tap();
  } else {
    await add.press('Enter');
  }
  await expect(sourceA).toHaveValue(userRef);
  if (narrow) {
    const fit = await sourceA.evaluate(element => {
      const box = element.getBoundingClientRect();
      return {
        width: window.innerWidth,
        noOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
        inputFits: box.width > 0 && box.left >= -1 && box.right <= window.innerWidth + 1,
      };
    });
    expect(fit).toEqual({ width: 390, noOverflow: true, inputFits: true });
  }
  await expect(comparison.getByLabel('Publication date A', { exact: true })).toHaveValue('');
  await expect(comparison.getByLabel('Passage A', { exact: true })).toHaveValue('');
  await expect(comparison.getByRole('status')).toContainText('Unverified reference added as text only');
  await expect(comparison.getByRole('button', { name: 'Download recorded comparison (.json)', exact: true })).toHaveCount(0);
  expect(page.url()).toBe(url);
  expect(downloads).toBe(0);
  expect(await savedState()).toEqual(savedBefore);
  expect(scenario.ledger.slice(before)).toEqual([]);
  expect(scenario.violations).toEqual([]);
});
