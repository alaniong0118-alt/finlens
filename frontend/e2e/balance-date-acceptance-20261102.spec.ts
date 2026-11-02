import type { Locator, TestInfo } from '@playwright/test';
import { test, expect, annualRequestCursor, assessFocusPaint, captureFocusPaint } from './fixtures/annual-period-browser';
import * as data from './fixtures/data';
import { balanceDates, balanceExact, balanceMetric, balanceNotApplicable, balancePath, balanceReply,
  balanceUnavailable, balanceLifecycle, balanceLoadCursor, expectThreeBalanceRequests, completedBalance, expectBalanceLedger, attachBalanceAudit, captureBalanceFocus } from './fixtures/balance-date-acceptance-20261102';

test.use({ deviceScaleFactor: 1 });

async function attachFocus(target: Locator, info: TestInfo, name: string, geometry: unknown) {
  const body = JSON.stringify(geometry);
  expect(Buffer.byteLength(body)).toBeLessThanOrEqual(32768);
  await info.attach(`balance-${name}-geometry`, { body, contentType: 'application/json' });
  // A viewport screenshot preserves native focus/scroll; no locator auto-scroll.
  const raster = await target.page().screenshot({ fullPage: false, type: 'png', scale: 'device',
    animations: 'allow', caret: 'initial', timeout: 3000 });
  expect(raster.length).toBeGreaterThan(0); expect(raster.length).toBeLessThanOrEqual(2 * 1024 * 1024);
  await info.attach(`balance-${name}-focus`, { body: raster, contentType: 'image/png' });
}
async function expectOutsetFocus(target: Locator, info: TestInfo, name: string) {
  await expect(target).toBeFocused();
  const geometry = await target.evaluate(captureFocusPaint), contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  await attachFocus(target, info, name, { geometry, contrast });
  expect(geometry.visible).toBe(true); expect(geometry.outline).not.toBe('none'); expect(geometry.width).toBeGreaterThanOrEqual(3);
  expect(contrast.sufficient).toBe(true);
  expect(Object.values(geometry.rect).every(Number.isFinite)).toBe(true);
  expect(geometry.rect.right).toBeGreaterThan(geometry.rect.left); expect(geometry.rect.bottom).toBeGreaterThan(geometry.rect.top);
  expect(geometry.rect.left - geometry.extent).toBeGreaterThanOrEqual(geometry.clip.left);
  expect(geometry.rect.right + geometry.extent).toBeLessThanOrEqual(geometry.clip.right);
  expect(geometry.rect.top - geometry.extent).toBeGreaterThanOrEqual(geometry.clip.top);
  expect(geometry.rect.bottom + geometry.extent).toBeLessThanOrEqual(geometry.clip.bottom);
}
async function expectInsetFocus(target: Locator, info: TestInfo, name: string, region = false) {
  await expect(target).toBeFocused();
  const geometry = await target.evaluate(captureBalanceFocus), contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  await attachFocus(target, info, name, { geometry, contrast });
  expect(geometry.dpr).toBe(1); expect(geometry.visible).toBe(true); expect(geometry.width).toBeGreaterThanOrEqual(3);
  expect(geometry.outline).not.toBe('none'); expect(contrast.sufficient).toBe(true);
  expect(geometry.surfaces.every(surface => surface.exposed)).toBe(true);
  expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewport.width);
  expect(Object.values(geometry.rect).concat([geometry.extent]).every(Number.isFinite)).toBe(true);
  expect(geometry.rect.height).toBeGreaterThanOrEqual(44);
  const box = { left: geometry.rect.left - geometry.extent, right: geometry.rect.right + geometry.extent,
    top: geometry.rect.top - geometry.extent, bottom: geometry.rect.bottom + geometry.extent };
  expect(box.left).toBeGreaterThan(-0.5); expect(box.right).toBeLessThan(geometry.viewport.width + 0.5);
  if (region) {
    expect(box.bottom).toBeGreaterThan(0); expect(box.top).toBeLessThan(geometry.viewport.height);
    expect(geometry.visibleHeight).toBeGreaterThanOrEqual(44);
  } else {
    expect(geometry.hit).toBe(true); expect(box.top).toBeGreaterThan(-0.5); expect(box.bottom).toBeLessThan(geometry.viewport.height + 0.5);
  }
  for (const ancestor of geometry.ancestors) {
    if (ancestor.x) { expect(box.left).toBeGreaterThan(ancestor.left - 0.5); expect(box.right).toBeLessThan(ancestor.right + 0.5); }
    if (ancestor.y) { expect(box.top).toBeGreaterThan(ancestor.top - 0.5); expect(box.bottom).toBeLessThan(ancestor.bottom + 0.5); }
  }
}
async function tabTo(target: Locator) {
  for (let step = 0; step < 16; step++) {
    await target.page().keyboard.press('Tab');
    if (await target.evaluate(element => element === document.activeElement)) return;
  }
  throw new Error('Balance keyboard traversal exceeded 16 native Tab steps');
}

// Both widths are explicit in this spec. The existing desktop-chromium project
// discovers all six cases; no shared mobile testMatch/config edit is required.
for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test.describe(`matched-date balance acceptance · ${viewport.width}px`, () => {
    test.use({ viewport, isMobile: viewport.width === 390, hasTouch: viewport.width === 390 });

    test('two/four exact dates, source keyboard and bounded layout', async ({ page, scenario }, info) => {
      scenario.overrides.push(request => balanceReply(request, scenario));
      const panel = page.getByRole('region', { name: 'Balance sheet by reported date', exact: true });
      const grid = panel.getByRole('region', { name: 'Balance metrics by exact reported date', exact: true });
      const choose = (end: string) => panel.getByRole('checkbox', { name: `As of ${end}`, exact: true });
      const load = panel.getByRole('button', { name: 'Load balance histories', exact: true });
      try {
        await scenario.open(); await scenario.ready(); await expect(panel).toContainText('Publication version 0');
        expect(balanceLifecycle(scenario).rows).toHaveLength(0);
        await expect(page.getByRole('link', { name: 'Balance dates', exact: true })).toHaveAttribute('href', '#balance-date-title');
        await page.getByRole('link', { name: 'Balance dates', exact: true }).click();
        await expect(grid).toHaveCount(0); const cursor = await balanceLoadCursor(scenario);
        await load.click(); await expect(panel.getByRole('checkbox')).toHaveCount(5);
        await expectBalanceLedger(scenario, completedBalance()); expectThreeBalanceRequests(scenario, cursor);
        const noExtra = scenario.ledger.length;
        await choose(balanceDates[0]).focus(); await page.keyboard.press('Tab');
        await expectOutsetFocus(choose(balanceDates[1]), info, 'date-checkbox');
        await page.keyboard.press('Space'); await expect(choose(balanceDates[1])).toBeChecked();
        await page.keyboard.press('Shift+Tab'); await expect(choose(balanceDates[0])).toBeFocused();
        await page.keyboard.press('Space'); await expect(grid.locator('tbody > tr')).toHaveCount(3);
        await expect(grid.locator('thead th')).toHaveCount(3);
        await expect(grid.locator('thead time')).toHaveText(balanceDates.slice(0, 2));
        await expect(grid.locator('tbody > tr').first().locator('.metric-value')).toHaveText(balanceExact.AAA.cash_and_equivalents + ' USD');

        await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
        await expect(choose(balanceDates[2])).toBeFocused(); await page.keyboard.press('Space');
        await page.keyboard.press('Tab'); await expect(choose(balanceDates[3])).toBeFocused(); await page.keyboard.press('Space');
        await expect(grid.locator('thead th')).toHaveCount(5); await expect(choose(balanceDates[4])).toBeDisabled();
        await expect(grid).toContainText(balanceNotApplicable);
        await page.keyboard.press('Space'); await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Space');
        await expect(grid.locator('thead th')).toHaveCount(3); await expect(choose(balanceDates[4])).toBeEnabled();

        await choose(balanceDates[4]).focus(); await page.keyboard.press('Tab'); await expectInsetFocus(grid, info, 'table-region', true);
        const beforeScroll = await grid.evaluate(element => ({ left: element.scrollLeft, overflow: element.scrollWidth > element.clientWidth }));
        await page.keyboard.press('ArrowRight');
        if (beforeScroll.overflow) await expect.poll(() => grid.evaluate(element => element.scrollLeft)).toBeGreaterThan(beforeScroll.left);
        if (viewport.width === 390) expect(beforeScroll.overflow).toBe(true);
        const first = grid.locator('tbody > tr').first().locator('td').first().locator('details.provenance');
        await page.keyboard.press('Tab'); await expectInsetFocus(first.locator(':scope > summary'), info, 'selected-source-summary');
        await page.keyboard.press('Space'); await expect(first).toHaveAttribute('open', '');
        await page.keyboard.press('Tab');
        const selected = first.getByRole('link', { name: 'Open official SEC filing ↗', exact: true });
        await expectInsetFocus(selected, info, 'selected-source-link'); await expect(selected).toHaveAttribute('href', data.secUrl('AAA'));
        await expect(selected).toHaveAttribute('rel', 'noopener noreferrer'); await expect(first).toContainText('Exact API value: ' + balanceExact.AAA.cash_and_equivalents + ' USD');
        await expect(first).toContainText('Accession ' + data.accession('AAA'));
        const alternative = first.locator('details');
        await page.keyboard.press('Tab'); await expect(alternative.locator(':scope > summary')).toBeFocused();
        await page.keyboard.press('Space'); await page.keyboard.press('Tab');
        await expectInsetFocus(alternative.getByRole('link', { name: 'SEC source ↗', exact: true }), info, 'alternative-source-link');
        await expect(alternative).toContainText('25.000000000000001 USD');

        const far = grid.locator('tbody > tr').last().locator('td').last().locator('details.provenance > summary');
        await tabTo(far); await expectInsetFocus(far, info, 'last-column-summary');
        const layout = await panel.evaluate(element => {
          const rect = element.getBoundingClientRect(), grid = element.querySelector('.comparison-scroll')!;
          return { width: innerWidth, pageWidth: document.documentElement.scrollWidth, left: rect.left, right: rect.right,
            overflowingValues: [...element.querySelectorAll('.metric-value')].filter(value => value.scrollWidth > value.clientWidth + 1).length,
            scrollWidth: grid.scrollWidth, clientWidth: grid.clientWidth };
        });
        await info.attach('balance-date-layout', { body: JSON.stringify(layout), contentType: 'application/json' });
        expect(layout.width).toBe(viewport.width); expect(layout.pageWidth).toBeLessThanOrEqual(layout.width);
        expect(layout.left).toBeGreaterThanOrEqual(0); expect(layout.right).toBeLessThanOrEqual(layout.width);
        expect(layout.overflowingValues).toBe(0);
        expect(scenario.ledger).toHaveLength(noExtra); await expectBalanceLedger(scenario, completedBalance());
      } finally { await attachBalanceAudit(scenario, info); }
    });

    test('exact-date gaps differ from failed history; clear and explicit retry stay bounded', async ({ page, scenario }, info) => {
      let failLiabilities = true;
      scenario.overrides.push(request => balanceMetric(request) === 'total_liabilities' && failLiabilities
        ? { status: 503, body: { detail: 'Synthetic liabilities history failed.' } } : undefined);
      scenario.overrides.push(request => balanceReply(request, scenario));
      const panel = page.getByRole('region', { name: 'Balance sheet by reported date', exact: true });
      const grid = panel.getByRole('region', { name: 'Balance metrics by exact reported date', exact: true });
      const load = panel.getByRole('button', { name: 'Load balance histories', exact: true });
      const expected = completedBalance('AAA', 0, { total_liabilities: { status: 503 } });
      try {
        await scenario.open(); await scenario.ready(); expect(balanceLifecycle(scenario).rows).toHaveLength(0);
        const cursor = await balanceLoadCursor(scenario); await load.click(); await expect(panel.getByRole('checkbox')).toHaveCount(5);
        await expectBalanceLedger(scenario, expected); expectThreeBalanceRequests(scenario, cursor);
        for (const end of balanceDates.slice(0, 2)) await panel.getByRole('checkbox', { name: `As of ${end}`, exact: true }).check();
        const rows = grid.locator('tbody > tr'), cashGap = rows.nth(0).locator('td').nth(1);
        await expect(cashGap).toContainText('Not present in loaded history'); await expect(cashGap).not.toContainText(balanceExact.AAA.cash_and_equivalents);
        await expect(cashGap.locator('details, a')).toHaveCount(0);
        const unavailable = rows.nth(1).locator('td').nth(1);
        await expect(unavailable.locator('.metric-value')).toHaveText('Unavailable'); await expect(unavailable).toContainText(balanceUnavailable);
        await expect(unavailable.locator('em')).toHaveCount(0);
        await expect(rows.nth(2).locator('td').first()).toContainText('History not verified');
        await expect(rows.nth(2)).toContainText('Synthetic liabilities history failed.'); await expect(rows.nth(2).getByRole('link')).toHaveCount(0);
        const beforeClear = balanceLifecycle(scenario).started;
        expect(beforeClear, 'Local selections must not add API requests before Clear').toBe(cursor + 3);
        await panel.getByRole('button', { name: 'Clear balance comparison', exact: true }).focus(); await page.keyboard.press('Enter');
        await expect(grid).toHaveCount(0); await expect(panel.getByRole('checkbox')).toHaveCount(0);
        await expectBalanceLedger(scenario, expected);
        expect(balanceLifecycle(scenario).started, 'Clear must not start any API request').toBe(beforeClear);
        failLiabilities = false; const retryCursor = await balanceLoadCursor(scenario);
        expect(retryCursor, 'No API request may be added between Clear and explicit retry').toBe(beforeClear);
        await load.focus(); await page.keyboard.press('Space'); await expect(panel.getByRole('checkbox')).toHaveCount(5);
        await expectBalanceLedger(scenario, [...expected, ...completedBalance()]); expectThreeBalanceRequests(scenario, retryCursor);
        for (const end of balanceDates.slice(0, 2)) await panel.getByRole('checkbox', { name: `As of ${end}`, exact: true }).check();
        await expect(grid.locator('tbody > tr').last().locator('.metric-value')).toHaveText([
          balanceExact.AAA.total_liabilities + ' USD', balanceExact.AAA.total_liabilities + ' USD']);
        await expect(grid).not.toContainText('History not verified');
        await expectBalanceLedger(scenario, [...expected, ...completedBalance()]);
        expect(balanceLifecycle(scenario).started, 'Retry selections must not add API requests').toBe(beforeClear + 3);
      } finally { await attachBalanceAudit(scenario, info); }
    });

    test('publication zero and ignored-abort A to B to A ownership', async ({ page, scenario }, info) => {
      const heldPath = balancePath('AAA', 'cash_and_equivalents');
      await scenario.ignoreTransportAbort(heldPath);
      let holdAlpha = true;
      const held = scenario.hold(request => holdAlpha && request.path === heldPath,
        () => ({ status: 409, code: 'DATA_VERSION_CHANGED', version: '1', body: { detail: 'Synthetic retired publication response.' } }));
      scenario.overrides.push(request => balanceReply(request, scenario));
      const panel = page.getByRole('region', { name: 'Balance sheet by reported date', exact: true });
      const grid = panel.getByRole('region', { name: 'Balance metrics by exact reported date', exact: true });
      const company = page.getByRole('combobox', { name: 'Company', exact: true });
      const load = panel.getByRole('button', { name: 'Load balance histories', exact: true });
      const expected = completedBalance('AAA', 0, { cash_and_equivalents: { status: 409, version: '1', code: 'DATA_VERSION_CHANGED' } });
      try {
        await scenario.open(); await scenario.ready(); await expect(panel).toContainText('Publication version 0');
        expect(balanceLifecycle(scenario).rows).toHaveLength(0); const firstCursor = await balanceLoadCursor(scenario); await load.click();
        await expect.poll(() => balanceLifecycle(scenario).rows.length).toBe(3);
        await expect.poll(() => balanceLifecycle(scenario).rows.filter(row => row.state === 'completed').length).toBe(2);
        expectThreeBalanceRequests(scenario, firstCursor);
        await expect(panel.getByRole('status')).toHaveText('Loading three balance histories…');
        holdAlpha = false; annualRequestCursor(scenario); await company.selectOption('BBB'); await scenario.ready('BBB');
        await expect(panel).toContainText('BBB'); await expect(panel).toContainText('Publication version 0');
        await expect(grid).toHaveCount(0); await expect(panel.getByRole('checkbox')).toHaveCount(0);
        const betaCursor = await balanceLoadCursor(scenario, [completedBalance()[0].request]);
        await load.click(); await expect(panel.getByRole('checkbox')).toHaveCount(5); expectThreeBalanceRequests(scenario, betaCursor);
        for (const end of balanceDates.slice(0, 2)) await panel.getByRole('checkbox', { name: `As of ${end}`, exact: true }).check();
        await expect(grid.locator('caption')).toContainText('BBB');
        await expect(grid).toContainText(balanceExact.BBB.cash_and_equivalents);
        annualRequestCursor(scenario); await company.selectOption('AAA'); await scenario.ready();
        await expect(grid).toHaveCount(0); await expect(panel.getByRole('checkbox')).toHaveCount(0);
        const returnedAlphaCursor = await balanceLoadCursor(scenario, [completedBalance()[0].request]);
        await load.click(); await expect(panel.getByRole('checkbox')).toHaveCount(5); expectThreeBalanceRequests(scenario, returnedAlphaCursor);
        for (const end of balanceDates.slice(0, 2)) await panel.getByRole('checkbox', { name: `As of ${end}`, exact: true }).check();
        const freshnessBefore = scenario.ledger.filter(request => request.path.endsWith('/freshness')).length;
        held.release();
        await expect.poll(() => scenario.abortedDeliveries(heldPath, '0', 409, '?period=instant&limit=12')).toBe(1);
        await expectBalanceLedger(scenario, [...expected, ...completedBalance('BBB'), ...completedBalance()]);
        await expect(panel).toContainText('Publication version 0'); await expect(grid.locator('caption')).toContainText('AAA');
        await expect(grid).toContainText(balanceExact.AAA.cash_and_equivalents); await expect(grid).not.toContainText(balanceExact.BBB.cash_and_equivalents);
        expect(scenario.ledger.filter(request => request.path.endsWith('/freshness'))).toHaveLength(freshnessBefore);
      } finally { held.release(); await attachBalanceAudit(scenario, info); }
    });
  });
}
