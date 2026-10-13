import { test, expect } from './fixtures/browser';

test('light and dark themes persist across reload with responsive contained layout', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  for (const theme of ['dark', 'light']) {
    await page.getByLabel('Theme', { exact: true }).selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await page.reload(); await scenario.ready();
    await expect(page.getByLabel('Theme', { exact: true })).toHaveValue(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
  }
  for (const label of ['Company', 'Snapshot period', 'History period', 'Research question or search']) {
    const control = label === 'Research question or search'
      ? page.getByRole('textbox', { name: label, exact: true })
      : page.getByRole('combobox', { name: label, exact: true });
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('keyboard skip link, native disclosures and guided editor focus are operable', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  // Start from browser document focus; exercise real sequential keyboard order.
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to research workspace', exact: true })).toBeFocused();
  await page.keyboard.press('Enter'); await expect(page).toHaveURL(/#research-workspace$/);
  const disclosure = page.getByText('More income and profitability', { exact: true });
  await disclosure.focus(); await page.keyboard.press('Enter');
  await expect(disclosure.locator('..')).toHaveAttribute('open', '');
  await expect(page.getByRole('heading', { name: 'Gross profit', exact: true })).toBeVisible();
  await page.keyboard.press('Space'); await expect(disclosure.locator('..')).not.toHaveAttribute('open');
  const use = page.getByRole('button', { name: 'Use question', exact: true });
  await use.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('textbox', { name: 'Research question or search', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'revenue growth', exact: true })).toBeFocused();
  expect(scenario.ledger.some(item => item.method === 'POST')).toBe(false);
});
