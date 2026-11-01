import { expect, test, type ApiRequest } from './fixtures/browser';
import * as data from './fixtures/data';

test.use({ deviceScaleFactor: 1 });

// Synthetic responses exercise display and identity checks, not actual coverage.
test('snapshot gaps: current scope, keyboard and no extra requests', async ({ page, scenario }, info) => {
  const isSummary = (request: ApiRequest, ticker: string, period: string) =>
    request.path === `/companies/${ticker}/financials/summary` && request.query.get('period') === period;
  scenario.overrides.push(request => {
    if (!isSummary(request, 'AAA', 'quarter')) return;
    const body = data.summary('AAA', 'quarter');
    // The fixture's default instant observations use year end; this synthetic
    // snapshot supplies the same as-of date as its selected quarter instead.
    for (const metric of ['cash_and_equivalents', 'total_assets', 'total_liabilities']) {
      const point = body.metrics[metric];
      if (!body.period || !point.period) throw new Error('Synthetic period missing');
      point.period.end = body.period.end;
      for (const source of point.provenance) source.period_end = body.period.end;
    }
    Object.assign(body.metrics.gross_profit, { status: 'unavailable', value: null,
      reason: 'Synthetic source evidence is unavailable for this reporting window.', provenance: [] });
    Object.assign(body.metrics.operating_income, { status: 'not_applicable', value: null,
      reason: 'Synthetic metric does not apply to this company.', provenance: [] });
    body.metrics.net_income.provenance[0].company_cik = data.company('BBB').cik;
    delete (body.metrics as Partial<typeof body.metrics>).diluted_eps;
    return { body };
  });
  const annual = scenario.hold(request => isSummary(request, 'AAA', 'annual'));
  const beta = scenario.hold(request => isSummary(request, 'BBB', 'quarter'));
  await scenario.open();
  await scenario.ready();
  const panel = page.getByRole('region', { name: 'Financial snapshot', exact: true });
  const disclosure = panel.locator('details').filter({ has: page.getByText(/^Snapshot coverage gaps \(/) });
  const toggle = disclosure.locator(':scope > summary');
  await expect(toggle).toHaveText('Snapshot coverage gaps (6)');
  const initial = scenario.ledger.filter(request => isSummary(request, 'AAA', 'quarter'));
  expect(initial.length).toBeGreaterThan(0);
  expect(initial.every(request => request.method === 'GET' && request.pin === '0')).toBe(true);

  // Start at the preceding control; the actual move and activation are native keyboard actions.
  const period = panel.getByRole('combobox', { name: 'Snapshot period' });
  await period.focus();
  await page.keyboard.press('Tab');
  await expect(toggle).toBeFocused();
  const focus = await toggle.evaluate(element => {
    const r = element.getBoundingClientRect(), style = getComputedStyle(element);
    const extent = Math.max(0, parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset));
    const middle = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return { left: r.left - extent, right: r.right + extent, top: r.top - extent, bottom: r.bottom + extent,
      width: innerWidth, height: innerHeight, dpr: devicePixelRatio, targetHeight: r.height,
      outline: style.outlineStyle, outlineWidth: parseFloat(style.outlineWidth), visible: element.matches(':focus-visible'),
      hit: !!middle && (middle === element || element.contains(middle)) };
  });
  await info.attach('snapshot-focus-geometry', { body: JSON.stringify(focus), contentType: 'application/json' });
  await info.attach('snapshot-focus', { body: await page.screenshot(), contentType: 'image/png' });
  expect(focus.dpr).toBe(1); expect(focus.visible).toBe(true); expect(focus.hit).toBe(true);
  expect(focus.outline).not.toBe('none'); expect(focus.outlineWidth).toBeGreaterThan(0);
  expect(focus.targetHeight).toBeGreaterThanOrEqual(44);
  for (const value of [focus.left, focus.right, focus.top, focus.bottom]) expect(Number.isFinite(value)).toBe(true);
  expect(focus.left).toBeGreaterThanOrEqual(-0.49); expect(focus.top).toBeGreaterThanOrEqual(-0.49);
  expect(focus.right).toBeLessThan(focus.width + 0.5); expect(focus.bottom).toBeLessThan(focus.height + 0.5);
  const before = scenario.ledger.length;
  await page.keyboard.press('Space');
  await expect(disclosure).toHaveAttribute('open', '');
  await expect(disclosure).toContainText('Gross profit: Unavailable — Synthetic source evidence is unavailable for this reporting window.');
  await expect(disclosure).toContainText('Operating income: Not applicable — Synthetic metric does not apply to this company.');
  await expect(disclosure).toContainText('Net income: Unverified');
  await expect(disclosure).toContainText('Diluted EPS: Unverified');
  const layout = await disclosure.evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth,
    document: document.documentElement.scrollWidth, viewport: innerWidth }));
  expect(layout.scroll).toBeLessThanOrEqual(layout.client + 1);
  expect(layout.document).toBeLessThanOrEqual(layout.viewport + 1);
  await info.attach('snapshot-open', { body: await page.screenshot(), contentType: 'image/png' });
  await page.keyboard.press('Space');
  await expect(disclosure).not.toHaveAttribute('open', '');
  expect(scenario.ledger).toHaveLength(before);

  await period.selectOption('annual');
  await expect(toggle).toHaveCount(0);
  await expect.poll(() => scenario.ledger.some(request => isSummary(request, 'AAA', 'annual') && request.pin === '0')).toBe(true);
  annual.release();
  await expect(toggle).toBeVisible();
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB');
  await expect(toggle).toHaveCount(0);
  await expect.poll(() => scenario.ledger.some(request => isSummary(request, 'BBB', 'quarter') && request.pin === '1')).toBe(true);
  beta.release();
  await scenario.ready('BBB');
  await expect(toggle).toBeVisible();
  await expect(disclosure).not.toContainText('Synthetic source evidence is unavailable for this reporting window.');
  expect(scenario.violations).toEqual([]);
});
