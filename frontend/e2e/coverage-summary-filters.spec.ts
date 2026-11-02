import type { Locator } from '@playwright/test';
import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';
import { validateCoverage } from '../lib/financial-coverage';

// Test-only fixed synthetic observations. Validation runs at discovery time as
// well as through the actual client response path; this is not live SEC data.
function maximumCoverage() {
  const result = data.storedCoverage('AAA', 'annual', 0);
  const template = result.columns[0];
  result.columns = Array.from({ length: 64 }, (_, index) => {
    const column = structuredClone(template), year = 1962 + index;
    column.window = { start: `${year}-01-01`, end: `${year}-12-31` };
    for (const [metric, point] of Object.entries(column.metrics)) {
      point.period = { kind: 'annual', ...column.window, fiscal_year: null, fiscal_period: null, fiscal_label_basis: 'unknown' };
      point.inputs = []; point.alternatives = [];
      if (metric === 'revenue') {
        point.provenance = [{ ...point.provenance[0], fact_id: index + 1,
          period_start: column.window.start, period_end: column.window.end }];
      } else {
        Object.assign(point, { status: metric === 'gross_margin' ? 'not_applicable' : 'unavailable', value: null,
          reason: 'Synthetic reason <em>literal</em>.', provenance: [] });
      }
    }
    return column;
  });
  Object.assign(result, { window_count: 64, cell_count: 704, source_reference_count: 64 });
  return validateCoverage(result, data.company('AAA'), 'annual', 0);
}
const maximum = maximumCoverage();
test.use({ deviceScaleFactor: 1 });

test('coverage summary and local filters on synthetic 704-cell response', async ({ page, scenario }, info) => {
  const endpoint = '/companies/AAA/financials/coverage';
  scenario.overrides.push(request => request.path === endpoint && request.query.toString() === 'period=annual'
    ? { body: maximum, version: '0' } : undefined);
  const panel = page.getByRole('region', { name: 'Financial coverage map', exact: true });
  const grid = panel.getByRole('region', { name: 'Stored financial coverage matrix', exact: true });
  const load = panel.getByRole('button', { name: 'Load stored coverage', exact: true });
  const clear = panel.getByRole('button', { name: 'Clear coverage', exact: true });
  const metric = panel.getByRole('combobox', { name: 'Metric', exact: true });
  const status = panel.getByRole('combobox', { name: 'Status', exact: true });
  const total = '704 total cells · 64 available · 576 unavailable · 64 not applicable.';
  const matching = (count: number) => `${count} matching cells in these loaded windows.`;
  async function focusCheck(control: Locator, name: string) {
    await expect(control).toBeFocused();
    const geometry = await control.evaluate(element => {
      const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
      const center = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, height: rect.height,
        viewportWidth: innerWidth, viewportHeight: innerHeight, pageWidth: document.documentElement.scrollWidth,
        focused: element.matches(':focus-visible'), outline: style.outlineStyle, outlineWidth: parseFloat(style.outlineWidth),
        hit: !!center && (center === element || element.contains(center)) };
    });
    await info.attach(`coverage-filter-${name}-focus`, { body: JSON.stringify(geometry), contentType: 'application/json' });
    expect(geometry.focused).toBe(true); expect(geometry.outline).not.toBe('none'); expect(geometry.outlineWidth).toBeGreaterThan(0);
    expect(geometry.height).toBeGreaterThanOrEqual(44); expect(geometry.hit).toBe(true);
    expect(geometry.left).toBeGreaterThanOrEqual(0); expect(geometry.right).toBeLessThanOrEqual(geometry.viewportWidth);
    expect(geometry.top).toBeGreaterThanOrEqual(0); expect(geometry.bottom).toBeLessThanOrEqual(geometry.viewportHeight);
    expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewportWidth + 1);
  }
  await scenario.open(); await scenario.ready();
  expect(scenario.count(endpoint)).toBe(0); await load.click();
  await expect(grid.locator('tbody tr')).toHaveCount(64);
  await expect(grid.locator('tbody td')).toHaveCount(704);
  await expect(panel).toContainText(total); await expect(panel).toContainText(matching(704));
  expect(scenario.count(endpoint)).toBe(1);
  const before = scenario.ledger.length;
  // Tab into each labelled filter using the real keyboard, retaining focus.
  await clear.focus(); await page.keyboard.press('Tab'); await focusCheck(metric, 'metric');
  await page.keyboard.press('Tab'); await focusCheck(status, 'status');
  for (const [value, count] of [['available', 64], ['unavailable', 576], ['not_applicable', 64], ['all', 704]] as const) {
    await status.selectOption(value); await expect(status).toBeFocused();
    await expect(panel).toContainText(matching(count)); await expect(panel).toContainText(total);
  }
  await metric.selectOption('gross_margin'); await status.selectOption('not_applicable');
  await expect(panel).toContainText(matching(64)); await expect(grid.locator('thead th')).toHaveCount(2);
  await expect(grid).toContainText('Synthetic reason <em>literal</em>.'); await expect(grid.locator('em')).toHaveCount(0);
  await metric.selectOption('revenue'); await expect(panel).toContainText(matching(0));
  await expect(panel).toContainText('No cells match these filters.'); await expect(grid).toHaveCount(0);
  await expect(metric).toBeVisible(); await expect(status).toBeVisible();
  await status.selectOption('available'); await expect(panel).toContainText(matching(64));
  const details = grid.locator('tbody tr').first().locator('details.provenance');
  await details.locator(':scope > summary').click();
  await expect(details.getByRole('link', { name: 'Open official SEC filing ↗', exact: true })).toHaveAttribute('href', data.secUrl('AAA'));
  expect(scenario.ledger).toHaveLength(before);
  const layout = await panel.evaluate(element => ({ page: document.documentElement.scrollWidth, viewport: innerWidth,
    panel: element.clientWidth, panelScroll: element.scrollWidth }));
  expect(layout.page).toBeLessThanOrEqual(layout.viewport + 1); expect(layout.panelScroll).toBeLessThanOrEqual(layout.panel + 1);
  await info.attach('coverage-filters-layout', { body: await page.screenshot(), contentType: 'image/png' });
  await load.click(); await expect(panel).toContainText(matching(704));
  await expect(metric).toHaveValue('all'); await expect(status).toHaveValue('all'); expect(scenario.count(endpoint)).toBe(2);
  await status.selectOption('unavailable');
  await panel.getByLabel('Period end from', { exact: true }).fill('2025-01-01');
  await panel.getByLabel('Period end to', { exact: true }).fill('2025-12-31');
  await expect(grid).toHaveCount(0); expect(scenario.count(endpoint)).toBe(2);
  await load.click(); await expect(panel).toContainText(matching(22));
  await expect(panel).toContainText('period ends 2025-01-01 through 2025-12-31, inclusive');
  await expect(metric).toHaveValue('all'); await expect(status).toHaveValue('all');
  expect(scenario.count(endpoint)).toBe(3); expect(scenario.violations).toEqual([]);
});
