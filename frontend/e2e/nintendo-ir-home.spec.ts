import { expect, test } from './fixtures/browser';

const pdf = 'https://www.nintendo.co.jp/ir/pdf/2026/261105e.pdf';
const pageTitle = 'Synthetic Nintendo publication response';

test('HOME_NINTENDO_RELEASE follows the contextual dated PDF link without external transport @desktop-only', async ({ page, scenario }) => {
  const navigation: { method: string; document: boolean; referrer: string | null }[] = [];
  // This one exact URL is fulfilled inside Playwright. The ordinary fixture
  // still denies all other non-loopback destinations; no PDF bytes are fetched.
  await page.route(url => url.href === pdf, async route => {
    const request = route.request();
    const headers = await request.allHeaders();
    const document = request.isNavigationRequest() && request.frame() === page.mainFrame();
    navigation.push({ method: request.method(), document, referrer: headers.referer ?? null });
    if (navigation.length !== 1 || !document || request.method() !== 'GET') {
      await route.abort('blockedbyclient');
      return;
    }
    await route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8',
      body: '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><title>' +
        pageTitle + '</title><h1>' + pageTitle + '</h1>' });
  });

  await scenario.open();
  await page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true })
    .fill('What did Nintendo report on 5 November 2026?');
  const region = page.getByRole('region', { name: 'Nintendo external source', exact: true });
  await expect(region).toHaveCount(0);
  await page.getByRole('button', { name: 'Keep research draft', exact: true }).click();
  const link = region.getByRole('link', { name: 'Nintendo six-month earnings release, 5 November 2026 (official PDF)', exact: true });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('href', pdf);
  await expect(link).toHaveAttribute('referrerpolicy', 'no-referrer');
  expect(navigation).toEqual([]);

  await Promise.all([page.waitForURL(pdf, { waitUntil: 'domcontentloaded' }), link.click()]);
  await expect(page.getByRole('heading', { name: pageTitle, exact: true })).toBeVisible();
  expect(navigation).toEqual([{ method: 'GET', document: true, referrer: null }]);
  expect(scenario.ledger.filter(request => request.method === 'POST')).toEqual([]);
});
