import { test, expect } from './fixtures/browser';

const original = 'What did Nintendo report on 5 November 2026?';
const alternate = 'Which different hypothesis should we test next?';
const filename = 'finlens-manual-comparison-v1.json';
const expected = {
  schema_version: 1, kind: 'manual_evidence_comparison', question: original,
  sources: [
    { kind: 'manual_unverified', reference: 'Issuer report, page 10', passage: 'Shipments moved to the following quarter.', locator: 'Page 10', date: '2025-02-19', assessment: 'supports', rationale: 'A timing shift fits.' },
    { kind: 'manual_unverified', reference: 'Industry survey, page 4', passage: 'Orders fell before the disruption.', locator: 'Page 4', date: null, assessment: 'challenges', rationale: 'Demand may have weakened first.' },
  ],
  provisional_judgment: 'Timing alone is not established.',
  evidence_that_would_change_judgment: 'Comparable monthly orders and shipments.',
};

test('manual competing evidence through normal Home, local download, and explicit restoration', async ({ page, scenario }, info) => {
  if (page.viewportSize()?.width === 1440) await page.setViewportSize({ width: 1440, height: 900 });
  expect([1440, 390]).toContain(page.viewportSize()?.width);
  const downloads: string[] = [];
  page.on('download', item => downloads.push(item.suggestedFilename()));
  scenario.overrides.push(req => req.path === '/companies' ? { body: [] } :
    req.path === '/capabilities' ? { body: { research_mode: true, ai_analysis_configured: false, ai_analysis_enabled: false, server_profile: 'sec_readonly', filing_research_enabled: false } } : undefined);
  await scenario.open();
  await expect.poll(() => [scenario.count('/companies'), scenario.count('/capabilities')]).toEqual([1, 1]);
  await expect(page.getByText('Financial-only capability restriction is active.', { exact: false })).toBeVisible();
  const baseline = scenario.ledger.length;
  const outer = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  const btn = (name: string) => page.getByRole('button', { name, exact: true });
  const panel = page.getByRole('region', { name: 'Manual evidence comparison', exact: true });
  const field = (name: string) => panel.getByLabel(name, { exact: true });
  const toggle = btn('Compare two manual sources');
  const download = btn('Download recorded comparison (.json)');
  const record = btn('Record provisional judgment');
  const keep = btn('Keep research draft');
  const restore = btn('Restore previous question');
  const nintendo = page.getByRole('region', { name: 'Nintendo external source', exact: true });
  const officialPdf = nintendo.getByRole('link', { name: 'Nintendo six-month earnings release, 5 November 2026 (official PDF)', exact: true });
  const officialIr = nintendo.getByRole('link', { name: 'Nintendo Investor Relations (official site)', exact: true });
  async function tabTo(target: ReturnType<typeof btn>) {
    await page.keyboard.press('Tab');
    await expect(target).toBeFocused();
  }
  await expect(nintendo).toHaveCount(0);
  await outer.fill(original);
  await expect(outer).toBeFocused();
  await tabTo(keep);
  await page.keyboard.press('Enter');
  await expect(officialPdf).toHaveAttribute('href', 'https://www.nintendo.co.jp/ir/pdf/2026/261105e.pdf');
  await expect(officialPdf).toHaveAttribute('referrerpolicy', 'no-referrer');
  await expect(nintendo.locator('time')).toHaveAttribute('datetime', '2026-11-05');
  await expect(keep).toBeFocused();
  await tabTo(officialPdf);
  await tabTo(officialIr);
  await tabTo(toggle);
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.keyboard.press('Enter');
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Space');
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.keyboard.press('Enter');
  await expect(toggle).toBeFocused();
  for (const [i, s] of expected.sources.entries()) {
    const k = i ? 'B' : 'A';
    await field('Source reference ' + k).fill(s.reference);
    await field('Passage ' + k).fill(s.passage);
    await field('Locator ' + k).fill(s.locator);
    if (s.date) await field('Publication date ' + k).fill(s.date);
    await field('Assessment ' + k).selectOption(s.assessment);
    await field('Assessment rationale ' + k).fill(s.rationale);
  }
  await field('Provisional judgment').fill(expected.provisional_judgment);
  await field('Evidence that would change the judgment').fill(expected.evidence_that_would_change_judgment);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  expect(downloads).toEqual([]);
  await expect(download).toHaveCount(0);
  async function downloadJson() {
    const [file] = await Promise.all([page.waitForEvent('download'), download.press('Enter')]);
    expect(file.suggestedFilename()).toBe(filename);
    expect(await file.failure()).toBeNull();
    const stream = await file.createReadStream();
    const chunks: Buffer[] = [];
    let size = 0;
    for await (const chunk of stream) {
      const bytes = Buffer.from(chunk); size += bytes.length;
      expect(size).toBeLessThanOrEqual(32_768);
      chunks.push(bytes);
    }
    expect(size).toBeGreaterThan(0);
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)));
  }
  await record.press('Enter');
  expect(await downloadJson()).toStrictEqual(expected);
  await field('Publication date B').fill('2025-02-20');
  await expect(download).toHaveCount(0);
  expect(downloads).toEqual([filename]);
  await record.press('Enter');
  const revised = { ...expected, sources: [expected.sources[0], { ...expected.sources[1], date: '2025-02-20' }] };
  expect(await downloadJson()).toStrictEqual(revised);
  await outer.fill(alternate);
  await expect(toggle).toHaveCount(0);
  await expect(download).toHaveCount(0);
  await expect(outer).toBeFocused();
  await tabTo(keep);
  await tabTo(restore);
  // Real sequential keyboard navigation, not locator.focus/press. Close one
  // bounded Tab cycle to prove the old export and hidden panel are unreachable.
  let wrapped = false;
  for (let step = 0; step < 48; step++) {
    await page.keyboard.press('Tab');
    const focus = await page.evaluate(() => {
      const active = document.activeElement;
      return {
        outer: active?.id === 'research-draft-input',
        oldManual: Boolean(active?.closest('section[aria-label="Manual evidence comparison"]')),
        download: active?.textContent?.trim() === 'Download recorded comparison (.json)',
      };
    });
    expect(focus.oldManual || focus.download).toBe(false);
    if (focus.outer) { wrapped = true; break; }
  }
  expect(wrapped, 'bounded Tab cycle returns to the outer input').toBe(true);
  await tabTo(keep);
  await tabTo(restore);
  await page.keyboard.press('Enter');
  await expect(outer).toHaveValue(original);
  await expect(outer).toBeFocused();
  await expect(field('Assessment rationale B')).toHaveValue(expected.sources[1].rationale);
  await expect(field('Evidence that would change the judgment')).toHaveValue(expected.evidence_that_would_change_judgment);
  await expect(download).toHaveCount(0);
  await record.press('Enter');
  await expect(download).toBeVisible();
  expect(downloads).toEqual([filename, filename]);
  await outer.fill(alternate);
  await expect(download).toHaveCount(0);
  await tabTo(keep);
  await page.keyboard.press('Enter');
  await expect(btn('Cancel replacement')).toBeVisible();
  await btn('Cancel replacement').press('Enter');
  await expect(outer).toHaveValue(original);
  await expect(outer).toBeFocused();
  await expect(field('Provisional judgment')).toHaveValue(expected.provisional_judgment);
  await expect(download).toHaveCount(0);
  await outer.fill(alternate);
  await btn('Keep research draft').press('Enter');
  await btn('Discard previous comparison and keep new question').press('Enter');
  await toggle.press('Enter');
  await expect(field('Source reference A')).toHaveValue('');
  await expect(field('Source reference B')).toHaveValue('');
  await expect(field('Provisional judgment')).toHaveValue('');
  await expect(download).toHaveCount(0);
  expect(downloads).toEqual([filename, filename]);
  expect(scenario.ledger.slice(baseline)).toEqual([]);
  expect(scenario.violations).toEqual([]);
  await info.attach('manual-browser-verdict', { body: JSON.stringify({ project: info.project.name, viewport: page.viewportSize(), apiCallsDuringManualFlow: 0, localDownloads: downloads.length }), contentType: 'application/json' });
});

test('manual evidence Reopen previews an actual V1 download without replacing the draft or export', async ({ page, scenario }) => {
  expect([1440, 390]).toContain(page.viewportSize()?.width);
  const downloads: string[] = [];
  page.on('download', item => downloads.push(item.suggestedFilename()));
  scenario.overrides.push(req => req.path === '/companies' ? { body: [] } :
    req.path === '/capabilities' ? { body: { research_mode: true, ai_analysis_configured: false,
      ai_analysis_enabled: false, server_profile: 'sec_readonly', filing_research_enabled: false } } : undefined);
  await scenario.open();
  await expect.poll(() => [scenario.count('/companies'), scenario.count('/capabilities')]).toEqual([1, 1]);
  await expect(page.getByText('Financial-only capability restriction is active.', { exact: false })).toBeVisible();
  const baseline = scenario.ledger.length;
  const outer = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  const btn = (name: string) => page.getByRole('button', { name, exact: true });
  const panel = page.getByRole('region', { name: 'Manual evidence comparison', exact: true });
  const field = (name: string) => panel.getByLabel(name, { exact: true });
  const download = btn('Download recorded comparison (.json)');
  const picker = field('Open a recorded comparison (.json)');
  const preview = panel.getByRole('region', { name: 'Reopened comparison preview', exact: true });

  await outer.fill(original);
  await outer.press('Enter');
  await btn('Compare two manual sources').press('Enter');
  for (const [i, s] of expected.sources.entries()) {
    const slot = i ? 'B' : 'A';
    await field('Source reference ' + slot).fill(s.reference);
    await field('Passage ' + slot).fill(s.passage);
    await field('Locator ' + slot).fill(s.locator);
    if (s.date) await field('Publication date ' + slot).fill(s.date);
    await field('Assessment ' + slot).selectOption(s.assessment);
    await field('Assessment rationale ' + slot).fill(s.rationale);
  }
  const judgment = field('Provisional judgment');
  await judgment.fill(expected.provisional_judgment);
  await field('Evidence that would change the judgment').fill(expected.evidence_that_would_change_judgment);
  await btn('Record provisional judgment').press('Enter');
  const [file] = await Promise.all([page.waitForEvent('download'), download.press('Enter')]);
  expect(file.suggestedFilename()).toBe(filename);
  expect(await file.failure()).toBeNull();
  const saved = await file.path();

  const live = 'Unrecorded live judgment must survive reopening.';
  await judgment.fill(live);
  await expect(download).toHaveCount(0);
  async function choose(input: Parameters<import('@playwright/test').FileChooser['setFiles']>[0], target = picker) {
    await expect(target).toBeVisible();
    await target.focus();
    await expect(target).toBeFocused();
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.keyboard.press('Space')]);
    expect(await chooser.element().getAttribute('type')).toBe('file');
    expect(await chooser.element().evaluate(element =>
      (element as HTMLInputElement).labels?.[0]?.firstChild?.textContent)).toBe('Open a recorded comparison (.json)');
    await chooser.setFiles(input);
  }
  async function expectPreserved() {
    await expect(outer).toHaveValue(original);
    await expect(judgment).toHaveValue(live);
    for (const [i, source] of expected.sources.entries())
      await expect(field('Assessment rationale ' + (i ? 'B' : 'A'))).toHaveValue(source.rationale);
    await expect(download).toHaveCount(0);
    expect(downloads).toEqual([filename]);
  }
  await choose(saved);
  await expect(preview.getByRole('heading', { name: 'Recorded comparison preview · not verified', exact: true })).toBeVisible();
  await expect(preview).toContainText(expected.provisional_judgment);
  await expect(preview).toContainText('Read-only preview');
  await expect(preview.locator('input, textarea, select, button, a')).toHaveCount(0);
  await expectPreserved();

  await choose({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from('{') });
  await expect(panel.getByRole('alert')).toContainText('Could not open this file.');
  await expect(preview).toHaveCount(0);
  await expectPreserved();

  await choose(saved);
  await expect(preview).toBeVisible();
  await outer.fill(alternate);
  await expect(preview).toHaveCount(0);
  await expect(download).toHaveCount(0);
  await btn('Restore previous question').press('Enter');
  await expect(preview).toHaveCount(0);
  await expectPreserved();
  expect(scenario.ledger.slice(baseline)).toEqual([]);
  await page.reload();
  await expect.poll(() => [scenario.count('/companies'), scenario.count('/capabilities')]).toEqual([2, 2]);
  await expect(page.getByText('Financial-only capability restriction is active.', { exact: false })).toBeVisible();
  const reopenedBaseline = scenario.ledger.length;
  const coldPicker = page.getByLabel('Open a recorded comparison (.json)', { exact: true });
  const coldPreview = page.getByRole('region', { name: 'Reopened comparison preview', exact: true });
  await expect(outer).toHaveValue('');
  await expect(panel).toHaveCount(0);
  await btn('Keep research draft').focus();
  await page.keyboard.press('Tab');
  await expect(coldPicker).toBeFocused();
  await choose(saved, coldPicker);
  await expect(coldPreview).toContainText(original);
  for (const source of expected.sources) await expect(coldPreview).toContainText(source.passage);
  await expect(coldPreview).toContainText(expected.provisional_judgment);
  await expect(outer).toHaveValue('');
  await expect(panel).toHaveCount(0);
  await expect(download).toHaveCount(0);
  await choose({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from('{') }, coldPicker);
  const coldError = page.getByRole('alert').filter({ hasText: 'Could not open this file.' });
  await expect(coldError).toHaveCount(1);
  await expect(coldError).toBeVisible();
  await expect(coldPreview).toHaveCount(0);
  expect(downloads).toEqual([filename]);
  expect(scenario.ledger.slice(reopenedBaseline)).toEqual([]);
  expect(scenario.violations).toEqual([]);
});
