import { expect, test } from '@playwright/test';

const localHome = 'http://127.0.0.1:3000/';
const fakeSource = 'https://filings.invalid/example';
const stamp = (step: string) => console.log('FINLENS_CHROMIUM_SMOKE: ' + step);

test('pinned default Chromium launches and keyboard-opened popup is intercepted', async ({ page, context }) => {
  stamp('browser_ready');
  const attempted: string[] = [];
  await context.route('**/*', (route) => {
    const url = route.request().url();
    if (url === localHome) {
      return route.fulfill({ contentType: 'text/html', body:
        '<main><a href="https://filings.invalid/example" target="_blank" rel="noopener noreferrer">Open official source</a></main>' });
    }
    attempted.push(url);
    return route.abort('blockedbyclient');
  });
  stamp('fixture_navigation');
  await page.goto('/');
  const citation = page.getByRole('link', { name: 'Open official source', exact: true });
  await expect(citation).toBeVisible();
  await expect(citation).toHaveAttribute('href', fakeSource);
  expect(attempted).toEqual([]);
  stamp('citation_activation');
  await citation.press('Enter');
  await expect.poll(() => attempted).toEqual([fakeSource]);
  stamp('complete');
});
