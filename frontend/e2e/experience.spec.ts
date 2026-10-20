import { test, expect } from './fixtures/browser';
import * as riskData from './fixtures/data';
import type { Locator } from '@playwright/test';
import type { CompanyContext } from '../lib/finlens-api';

// SEC-RISK-CC01 fixtures use canonical source identity/framing for BOTH issuers.
// Keep these spec-local; generic financial fixtures intentionally have other shapes.
function ccBrowserEvidence(ticker: string, query: string, version: number, count = 3): CompanyContext {
  const issuer = riskData.company(ticker), accession = riskData.accession(ticker);
  const text = `${issuer.name}: ${query} synthetic disclosure. 😀 <script>literal()</script>\n\n  Original source wording.`;
  const citations = Array.from({ length: count }, (_, index) => ({ company_cik: issuer.cik, citation_id: `source_${index + 1}`,
    chunk_id: `chunk_${String(index).padStart(4, '0')}`, accession_number: accession, form: ticker === 'AAA' ? '10-K' : '10-Q',
    filed: ticker === 'AAA' ? '2025-10-01' : '2026-02-01', filename: 'synthetic.htm', start_char: index * 3000,
    end_char: index * 3000 + Array.from(text).length, similarity: 0.9, semantic_similarity: 0.9, lexical_score: 1, hybrid_score: 1.54,
    evidence_reason: 'strong_lexical', sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(issuer.cik)}/${accession.replaceAll('-', '')}/${accession}-index.html` }));
  return { ticker, company_name: issuer.name, query, retrieval_scope: 'company', company_cik: issuer.cik,
    data_version: version, evidence_version: version, searched_accessions: [accession], excluded_publication_count: 0,
    evidence_status: count ? 'sufficient' : 'insufficient', citations, context: citations.map(c => {
      const metadata = Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, c[key as keyof typeof c]]));
      return `[SOURCE ${c.citation_id}]\nmetadata: ${JSON.stringify(metadata)}\ntext: |-\n${text.split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE ${c.citation_id}]`;
    }).join('\n\n') };
}

test('SEC-RISK-CC01 independent evidence, three disclosure targets, layout and keyboard focus', async ({ page, scenario }, info) => {
  scenario.overrides.push(request => request.path.endsWith('/context')
    ? { body: ccBrowserEvidence(request.ticker!, request.query.get('q')!, Number(request.pin)) } : undefined);
  await scenario.open(); await scenario.ready();
  // Keep the existing single-company evidence visible alongside both new columns.
  await page.getByRole('combobox', { name: 'Research purpose', exact: true }).selectOption('risk');
  await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption('company');
  await page.getByRole('button', { name: 'Use risk topic', exact: true }).click();
  await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
  await expect(page.locator('.research-grid .evidence-card')).toHaveCount(2);
  const panel = page.getByRole('region', { name: 'Compare SEC risk evidence', exact: true });
  const beforeSelection = scenario.ledger.length;
  await panel.getByRole('combobox', { name: 'Issuer A', exact: true }).selectOption('AAA');
  await panel.getByRole('combobox', { name: 'Issuer B', exact: true }).selectOption('BBB');
  await panel.getByRole('combobox', { name: 'Comparison risk topic', exact: true }).selectOption('competition');
  expect(scenario.ledger.length).toBe(beforeSelection);
  const start = scenario.ledger.length;
  await panel.getByRole('button', { name: 'Compare SEC evidence', exact: true }).click();
  await expect(panel.locator('.evidence-card')).toHaveCount(4);
  const columns = panel.locator('.risk-comparison-column');
  await expect(columns.nth(0)).toContainText('Data version 0 · Evidence version 0');
  await expect(columns.nth(1)).toContainText('Data version 1 · Evidence version 1');
  for (const [index, ticker] of ['AAA', 'BBB'].entries()) {
    const column = columns.nth(index), expected = ccBrowserEvidence(ticker, 'competition', index);
    await expect(column.locator('.source-link').first()).toHaveAttribute('href', expected.citations[0].sec_url);
    await expect(column.locator('.evidence-card').first()).toContainText('<script>literal()</script>');
    await expect(column.locator('script')).toHaveCount(0);
  }
  const ledger = scenario.ledger.slice(start);
  expect(ledger.map(r => [r.method, r.path, r.pin, r.query.toString()])).toEqual(expect.arrayContaining([
    ['GET', '/companies/AAA/freshness', undefined, ''], ['GET', '/companies/BBB/freshness', undefined, ''],
    ['GET', '/companies/AAA/context', '0', 'q=competition&limit=5'], ['GET', '/companies/BBB/context', '1', 'q=competition&limit=5'],
  ]));
  expect(ledger).toHaveLength(4);
  const toggles = page.locator('.evidence-toggle'); await expect(toggles).toHaveCount(3);
  const controls = await toggles.evaluateAll(nodes => nodes.map(n => n.getAttribute('aria-controls')));
  expect(new Set(controls).size).toBe(3);
  await toggles.nth(1).click();
  await expect(page.locator('.research-grid .evidence-card')).toHaveCount(2);
  await expect(columns.nth(0).locator('.evidence-card')).toHaveCount(3);
  await expect(columns.nth(1).locator('.evidence-card')).toHaveCount(2);
  expect(await page.locator('[id]').evaluateAll(nodes => { const ids = nodes.map(n => n.id); return ids.length === new Set(ids).size; })).toBe(true);
  await page.getByRole('link', { name: 'Compare SEC risk evidence', exact: true }).click();
  await page.keyboard.press('Tab');
  const geometry = [];
  for (const control of [panel.getByRole('combobox', { name: 'Issuer A', exact: true }), panel.getByRole('combobox', { name: 'Issuer B', exact: true }),
    panel.getByRole('combobox', { name: 'Comparison risk topic', exact: true }), panel.getByRole('button', { name: 'Compare SEC evidence', exact: true }),
    columns.nth(0).getByText('Read full evidence passage', { exact: true }).first(), toggles.nth(1), toggles.nth(2)]) {
    geometry.push(await riskFocusGeometry(control));
  }
  const a = await columns.nth(0).boundingBox(), b = await columns.nth(1).boundingBox(); expect(a).not.toBeNull(); expect(b).not.toBeNull();
  if (page.viewportSize()!.width === 390) { expect(b!.y).toBeGreaterThan(a!.y + a!.height - 1); expect(Math.abs(a!.x - b!.x)).toBeLessThan(1); }
  else { expect(b!.x).toBeGreaterThan(a!.x + a!.width); expect(Math.abs(a!.y - b!.y)).toBeLessThan(1); }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(panel.locator('.ai-panel,.passage-tone,.direct-answer')).toHaveCount(0);
  expect(scenario.ledger.slice(start).filter(r => /research-answer|\/answer$|\/tone$/.test(r.path))).toHaveLength(0);
  await info.attach('cc01-layout-focus-ledger', { body: JSON.stringify({ viewport: page.viewportSize(), geometry, columns: [a, b], controls,
    ledger: ledger.map(r => ({ path: r.path, pin: r.pin, query: r.query.toString() })), violations: scenario.violations }), contentType: 'application/json' });
  await panel.scrollIntoViewIfNeeded(); await info.attach('cc01-layout', { body: await page.screenshot(), contentType: 'image/png' });
});

test('SEC-RISK-CC01 partial results, cancellation, exact failure states and explicit retry', async ({ page, scenario }, info) => {
  let mode: 'valid' | 'no_publications' | 'insufficient' | 'mismatch' | 'missing_header' = 'valid';
  scenario.overrides.push(request => {
    if (!request.path.endsWith('/context')) return undefined;
    const body = ccBrowserEvidence(request.ticker!, request.query.get('q')!, Number(request.pin));
    if (request.ticker === 'AAA') {
      if (mode === 'no_publications' || mode === 'insufficient') { body.citations = []; body.context = ''; body.evidence_status = 'insufficient'; if (mode === 'no_publications') body.searched_accessions = []; }
      if (mode === 'mismatch') body.company_cik = '0000900002';
      if (mode === 'missing_header') return { body, version: null };
    }
    return { body };
  });
  await scenario.open(); await scenario.ready();
  const held = scenario.hold(r => r.path === '/companies/AAA/freshness');
  const panel = page.getByRole('region', { name: 'Compare SEC risk evidence', exact: true });
  await panel.getByRole('combobox', { name: 'Issuer A', exact: true }).selectOption('AAA');
  await panel.getByRole('combobox', { name: 'Issuer B', exact: true }).selectOption('BBB');
  const start = scenario.ledger.length;
  await panel.getByRole('button', { name: 'Compare SEC evidence', exact: true }).click();
  await expect(panel.locator('.risk-comparison-column').nth(1).locator('.evidence-card')).toHaveCount(2);
  await expect(panel.locator('.risk-comparison-column').nth(0)).toHaveAttribute('aria-busy', 'true');
  expect(scenario.ledger.slice(start)).toHaveLength(3);
  await panel.getByRole('button', { name: 'Cancel evidence comparison', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Compare SEC evidence', exact: true })).toBeFocused();
  await expect(panel).toContainText('Comparison incomplete');
  await expect(panel.locator('.risk-comparison-column').nth(1).locator('.evidence-card')).toHaveCount(2);
  held.release();
  // Remove only the test-owned held override; no default routes or isolation change.
  scenario.overrides.pop();
  const outcomes = [];
  for (mode of ['no_publications', 'insufficient', 'mismatch', 'missing_header', 'valid'] as const) {
    const count = scenario.ledger.length;
    await panel.getByRole('button', { name: 'Compare SEC evidence', exact: true }).click();
    await expect(panel.getByRole('button', { name: 'Cancel evidence comparison', exact: true })).toHaveCount(0);
    const a = panel.locator('.risk-comparison-column').nth(0), b = panel.locator('.risk-comparison-column').nth(1);
    await expect(b.locator('.evidence-card')).toHaveCount(2);
    await expect(a.locator('.evidence-card')).toHaveCount(mode === 'valid' ? 2 : 0);
    if (mode !== 'valid') await expect(a).toContainText(mode === 'no_publications' ? 'No qualifying published evidence available to search.'
      : mode === 'insufficient' ? 'Insufficient topic evidence.' : 'Evidence unavailable or unverified.');
    const ledger = scenario.ledger.slice(count); expect(ledger).toHaveLength(4);
    expect(ledger.every(r => r.method === 'GET' && /\/(freshness|context)$/.test(r.path))).toBe(true);
    outcomes.push({ mode, requests: ledger.length });
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await info.attach('cc01-partial-retry-ledger', { body: JSON.stringify({ outcomes, violations: scenario.violations }), contentType: 'application/json' });
});

test('SEC-RISK-CC01 late ignored-abort success and 409 cannot replace a new topic', async ({ page, scenario }, info) => {
  const path = '/companies/AAA/context'; await scenario.ignoreTransportAbort(path);
  let obsoleteStatus = 200;
  const held = scenario.hold(r => r.path === path && r.query.get('q') === 'supply chain', r => obsoleteStatus === 409
    ? { status: 409, version: '1', code: 'DATA_VERSION_CHANGED' } : { body: ccBrowserEvidence('AAA', 'supply chain', Number(r.pin)), version: r.pin });
  scenario.overrides.push(r => r.path.endsWith('/context') ? { body: ccBrowserEvidence(r.ticker!, r.query.get('q')!, Number(r.pin)) } : undefined);
  await scenario.open(); await scenario.ready();
  const panel = page.getByRole('region', { name: 'Compare SEC risk evidence', exact: true });
  await panel.getByRole('combobox', { name: 'Issuer A', exact: true }).selectOption('AAA');
  await panel.getByRole('combobox', { name: 'Issuer B', exact: true }).selectOption('BBB');
  const before = scenario.ledger.length;
  await panel.getByRole('button', { name: 'Compare SEC evidence', exact: true }).click();
  await expect.poll(() => scenario.count(path)).toBe(1);
  await panel.getByRole('combobox', { name: 'Comparison risk topic', exact: true }).selectOption('competition');
  await expect(panel.locator('.evidence-card')).toHaveCount(0);
  await panel.getByRole('button', { name: 'Compare SEC evidence', exact: true }).click();
  await expect(panel.locator('.evidence-card')).toHaveCount(4);
  obsoleteStatus = info.project.name === 'desktop-chromium' ? 409 : 200;
  held.release();
  await expect.poll(() => scenario.abortedDeliveries(path, '0', obsoleteStatus, '?q=supply+chain&limit=5')).toBe(1);
  await expect(panel.locator('.evidence-results').first()).toContainText('Search: “competition”');
  await expect(panel.getByRole('alert')).toHaveCount(0);
  expect(scenario.ledger.slice(before).filter(r => r.path === path)).toHaveLength(2);
  await info.attach('cc01-stale-delivery', { body: JSON.stringify({ obsoleteStatus, abortedDeliveries: 1, currentTopic: 'competition', violations: scenario.violations }), contentType: 'application/json' });
});

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

// RISK-SEC-01 only. Existing harness/fixtures remain unchanged; these overrides
// reproduce the inspected backend URL/citation/framing contract, not real data.
const riskSyntheticUrl = (accession = riskData.accession('AAA')) => `https://www.sec.gov/Archives/edgar/data/900001/${accession.replaceAll('-', '')}/${accession}-index.html`;
type RiskCitation = ReturnType<typeof riskData.evidence>['citations'][number];
const riskText = 'Synthetic issuer: supply chain disruption may affect operations. 😀 <script>literal()</script>';
function riskBlock(scope: 'filing' | 'company', citation: RiskCitation) {
  const headers = scope === 'company'
    ? `metadata: ${JSON.stringify(Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, citation[key as keyof typeof citation]])))}`
    : `chunk_id: ${citation.chunk_id}\naccession_number: ${citation.accession_number}\nform: ${citation.form}\nsimilarity: ${citation.similarity.toFixed(6)}`;
  return `[SOURCE ${citation.citation_id}]\n${headers}\ntext: |-\n  ${riskText}\n[END SOURCE ${citation.citation_id}]`;
}
function riskSyntheticEvidence(scope: 'filing' | 'company', query: string, version: number) {
  const original = riskData.evidence('AAA', query, version).citations[0];
  const citation = { ...original, chunk_id: 'chunk_0000', sec_url: riskSyntheticUrl(), end_char: Array.from(riskText).length, evidence_reason: 'strong_lexical' };
  const base = { ticker: 'AAA', company_name: 'Synthetic Alpha', query, evidence_status: 'sufficient' as 'sufficient' | 'insufficient',
    citations: [citation], context: riskBlock(scope, citation) };
  return scope === 'filing' ? { ...base, accession_number: riskData.accession('AAA') }
    : { ...base, retrieval_scope: 'company', company_cik: '0000900001', data_version: version, evidence_version: version,
      searched_accessions: [riskData.accession('AAA')], excluded_publication_count: 0 };
}

// Probe the real focused element and ancestor clipping rectangles, without CSS
// overrides. Keyboard modality is established by each caller before focusing.
async function riskFocusGeometry(control: Locator) {
  // Reserve viewport space for the outline itself. Minimal element scrolling
  // can place a fully visible border at the viewport edge and crop its outline.
  await control.evaluate(element => element.scrollIntoView({ block: 'center', inline: 'nearest' }));
  await control.focus();
  await expect(control).toBeFocused();
  const geometry = await control.evaluate(element => {
    const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
    const gutter = parseFloat(style.outlineWidth) + Math.max(0, parseFloat(style.outlineOffset));
    const bounds = { left: rect.left - gutter, top: rect.top - gutter, right: rect.right + gutter, bottom: rect.bottom + gutter };
    let clipped = bounds.left < 0 || bounds.top < 0 || bounds.right > innerWidth || bounds.bottom > innerHeight;
    for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
      const a = ancestor.getBoundingClientRect(), css = getComputedStyle(ancestor);
      if (/(hidden|clip|auto|scroll)/.test(css.overflowX) && (bounds.left < a.left || bounds.right > a.right)) clipped = true;
      if (/(hidden|clip|auto|scroll)/.test(css.overflowY) && (bounds.top < a.top || bounds.bottom > a.bottom)) clipped = true;
    }
    const usable = [0.2, 0.5, 0.8].every(x => [0.2, 0.5, 0.8].every(y => {
      const hit = document.elementFromPoint(rect.left + rect.width * x, rect.top + rect.height * y);
      return hit === element || element.contains(hit);
    }));
    return { height: rect.height, width: rect.width, left: rect.left, right: rect.right, outline: style.outlineStyle,
      outlineWidth: parseFloat(style.outlineWidth), focusVisible: element.matches(':focus-visible'), clipped, usable };
  });
  await test.info().attach('focused-control-geometry', { body: JSON.stringify(geometry), contentType: 'application/json' });
  expect(geometry.height).toBeGreaterThanOrEqual(44);
  expect(geometry.focusVisible).toBe(true); expect(geometry.outline).not.toBe('none');
  expect(geometry.outlineWidth).toBeGreaterThan(0); expect(geometry.clipped).toBe(false); expect(geometry.usable).toBe(true);
  return geometry;
}

test('RISK-SEC-01 purpose selector smoke verifies unique accessible names and default', async ({ page, scenario }) => {
  await scenario.open(); await scenario.ready();
  const purpose = page.getByRole('combobox', { name: 'Research purpose', exact: true });
  await expect(purpose).toHaveCount(1); await expect(purpose).toHaveValue('general');
  await purpose.selectOption('risk'); await expect(purpose).toHaveValue('risk');
  const topics = page.getByRole('combobox', { name: 'Risk topic', exact: true });
  await expect(topics).toHaveCount(1);
  await expect(topics.locator('option')).toHaveText(['Supply-chain disruption', 'Competition and demand', 'Cybersecurity',
    'Legal and regulatory exposure', 'Liquidity and financing', 'Foreign-exchange exposure']);
  await expect(page.getByRole('combobox', { name: 'Evidence search scope', exact: true })).toHaveCount(1);
  await topics.selectOption('competition');
  await page.getByRole('button', { name: 'Use risk topic', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Research question or search', exact: true })).toHaveValue('competition');
  expect(scenario.ledger.filter(r => r.path.endsWith('/context') || r.method === 'POST')).toHaveLength(0);
});

test('RISK-SEC-01 guided evidence has native focus, exact sources and one request in both scopes', async ({ page, scenario }, info) => {
  scenario.overrides.push(request => {
    if (request.ticker !== 'AAA') return;
    if (request.path.endsWith('/sources')) return { body: riskData.sources('AAA').map(source => ({ ...source, sec_url: riskSyntheticUrl(source.accession_number) })) };
    if (request.path.endsWith('/context')) return { body: riskSyntheticEvidence(request.path.includes('/filings/') ? 'filing' : 'company', request.query.get('q')!, Number(request.pin)) };
  });
  await scenario.open(); await scenario.ready();
  for (const theme of ['light', 'dark', 'system']) {
    await page.getByLabel('Theme', { exact: true }).selectOption(theme);
    await page.getByRole('combobox', { name: 'Research purpose', exact: true }).selectOption('risk');
    await page.getByRole('combobox', { name: 'Risk topic', exact: true }).selectOption('competition');
    const contexts = scenario.ledger.filter(r => r.path.endsWith('/context')).length;
    const use = page.getByRole('button', { name: 'Use risk topic', exact: true });
    await use.focus(); await page.keyboard.press('Enter');
    const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
    await expect(editor).toBeFocused(); await expect(editor).toHaveValue('competition');
    expect(scenario.ledger.filter(r => r.path.endsWith('/context')).length).toBe(contexts);
    for (const scope of ['filing', 'company']) {
      await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption(scope);
      const before = scenario.ledger.filter(r => r.path.endsWith('/context')).length;
      await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Candidate SEC passages', exact: true })).toBeVisible();
      expect(scenario.ledger.filter(r => r.path.endsWith('/context')).length).toBe(before + 1);
      expect(scenario.ledger.filter(r => r.path.endsWith('/context')).at(-1)!.pin).toBe('0');
      await expect(page.locator('.evidence-card .source-link')).toHaveAttribute('href', riskSyntheticUrl());
      await expect(page.locator('.evidence-results')).toHaveAttribute('aria-live', 'polite');
      await expect(page.getByText(/CIK 0000900001 · Publication 0/)).toBeVisible();
      await expect(page.getByText(/Filing dates describe the returned sources/)).toBeVisible();
      const disclosure = page.getByText('Read full evidence passage', { exact: true });
      await disclosure.focus(); await page.keyboard.press('Enter');
      await expect(page.locator('.evidence-card details').first()).toHaveAttribute('open', '');
      await expect(page.locator('.evidence-card .details-body').first()).toContainText('<script>literal()</script>');
      expect(await page.locator('.evidence-card script').count()).toBe(0);
      const metadata = page.getByText('Filing and retrieval details', { exact: true });
      await metadata.focus(); await page.keyboard.press('Enter');
      await expect(metadata.locator('..')).toHaveAttribute('open', '');
      await expect(metadata.locator('..')).toContainText(`source_1 · chunk_0000 · synthetic.htm`);
      await expect(metadata.locator('..')).toContainText(`Accession ${riskData.accession('AAA')}`);
      await expect(metadata.locator('..')).toContainText('CIK 0000900001');
      await expect(page.locator('.evidence-heading')).toContainText('Feb 1, 2026');
      await expect(page.locator('.ai-panel, .passage-tone, .direct-answer')).toHaveCount(0);
    }
    const geometry = [];
    for (const label of ['Research purpose', 'Risk topic', 'Evidence search scope']) {
      geometry.push({ label, ...await riskFocusGeometry(page.getByRole('combobox', { name: label, exact: true })) });
    }
    geometry.push({ label: 'Use risk topic', ...await riskFocusGeometry(use) });
    // Native sequential navigation from topic preparation reaches the editor.
    await page.keyboard.press('Tab'); await expect(editor).toBeFocused();
    geometry.push({ label: 'Research editor', ...await riskFocusGeometry(editor) });
    geometry.push({ label: 'Search risk topic', ...await riskFocusGeometry(page.getByRole('button', { name: 'Search risk topic', exact: true })) });
    geometry.push({ label: 'Full passage disclosure', ...await riskFocusGeometry(page.getByText('Read full evidence passage', { exact: true })) });
    geometry.push({ label: 'Official SEC source', ...await riskFocusGeometry(page.locator('.evidence-card .source-link')) });
    geometry.push({ label: 'Metadata disclosure', ...await riskFocusGeometry(page.getByText('Filing and retrieval details', { exact: true })) });
    await info.attach(`geometry-${theme}`, { body: JSON.stringify(geometry, null, 2), contentType: 'application/json' });
    await info.attach(`risk-${theme}`, { body: await page.screenshot(), contentType: 'image/png' });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  expect(scenario.ledger.filter(r => /research-answer|\/answer$|\/tone$/.test(r.path))).toHaveLength(0);
  await info.attach('synthetic-request-ledger', { body: JSON.stringify({ requests: scenario.ledger.map(({ path, pin, query }) => ({ path, pin, query: query.toString() })), violations: scenario.violations }), contentType: 'application/json' });
});

test('RISK-SEC-01 insufficient evidence differs from unverified responses and explicit retry', async ({ page, scenario }) => {
  let mode: 'empty' | 'malformed' | 'missing-header' | 'valid' = 'empty';
  scenario.overrides.push(request => {
    if (request.path.endsWith('/sources') && request.ticker === 'AAA') return { body: riskData.sources('AAA').map(source => ({ ...source, sec_url: riskSyntheticUrl(source.accession_number) })) };
    if (!request.path.endsWith('/context')) return;
    const body = riskSyntheticEvidence('filing', request.query.get('q')!, Number(request.pin));
    if (mode === 'empty') { body.citations = []; body.context = ''; body.evidence_status = 'insufficient'; }
    if (mode === 'malformed') body.citations[0].sec_url = 'https://invalid.test/source';
    return { body, ...(mode === 'missing-header' ? { version: null } : {}) };
  });
  await scenario.open(); await scenario.ready();
  await page.getByRole('combobox', { name: 'Research purpose', exact: true }).selectOption('risk');
  await page.getByRole('button', { name: 'Use risk topic', exact: true }).click();
  await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Insufficient topic evidence in the searched scope', exact: true })).toBeVisible();
  await expect(page.locator('.evidence-results')).toContainText('does not mean no risk');
  for (mode of ['malformed', 'missing-header'] as const) {
    await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
    await expect(page.locator('.search-form').locator('..').getByRole('alert')).toBeVisible();
    await expect(page.locator('.evidence-card')).toHaveCount(0);
  }
  const before = scenario.ledger.filter(r => r.path.endsWith('/context')).length;
  mode = 'valid';
  await page.getByRole('button', { name: 'Retry risk-topic search', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Candidate SEC passages', exact: true })).toBeVisible();
  expect(scenario.ledger.filter(r => r.path.endsWith('/context')).length).toBe(before + 1);
});

test('RISK-SEC-01 impossible Unicode spans and conflicting same-accession metadata fail closed', async ({ page, scenario }, info) => {
  let fault: 'valid' | 'span' | 'form' | 'filed' | 'filename' = 'valid';
  scenario.overrides.push(request => {
    if (request.path.endsWith('/sources') && request.ticker === 'AAA') return { body: riskData.sources('AAA').map(source => ({ ...source, sec_url: riskSyntheticUrl(source.accession_number) })) };
    if (!request.path.endsWith('/context')) return;
    const scope = request.path.includes('/filings/') ? 'filing' : 'company';
    const body = riskSyntheticEvidence(scope, request.query.get('q')!, Number(request.pin));
    if (fault === 'span') body.citations[0].end_char = Array.from(riskText).length - 1;
    else if (fault !== 'valid') {
      const second = { ...body.citations[0], citation_id: 'source_2', chunk_id: 'chunk_0001' };
      if (fault === 'form') second.form = '10-Q';
      if (fault === 'filed') second.filed = '2026-02-02';
      if (fault === 'filename') second.filename = 'different.htm';
      body.citations.push(second);
    }
    // Rebuild both SOURCE blocks from the altered citation identities, including
    // company metadata. Rejection must catch the span/filing contradiction itself.
    body.context = body.citations.map(citation => riskBlock(scope, citation)).join('\n\n');
    return { body };
  });
  await scenario.open(); await scenario.ready();
  await page.getByRole('combobox', { name: 'Research purpose', exact: true }).selectOption('risk');
  await page.getByRole('button', { name: 'Use risk topic', exact: true }).click();
  const outcomes = [];
  for (const scope of ['filing', 'company']) {
    await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption(scope);
    fault = 'valid';
    await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
    await expect(page.locator('.evidence-card')).toHaveCount(1);
    for (fault of ['span', 'form', 'filed', 'filename'] as const) {
      const before = scenario.ledger.filter(r => r.path.endsWith('/context')).length;
      await Promise.all([page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/context')),
        page.getByRole('button', { name: 'Search risk topic', exact: true }).click()]);
      const alert = page.locator('.search-form').locator('..').getByRole('alert');
      await expect(alert).toHaveText('The evidence response could not be verified. No candidate passages were shown.');
      await expect(page.getByRole('button', { name: 'Retry risk-topic search', exact: true })).toBeEnabled();
      await expect(page.locator('.evidence-card, .evidence-results .source-link')).toHaveCount(0);
      await expect(page.getByRole('heading', { name: 'Candidate SEC passages', exact: true })).toHaveCount(0);
      await expect(page.getByText(/CIK 0000900001 · Publication 0/)).toHaveCount(0);
      expect(scenario.ledger.filter(r => r.path.endsWith('/context')).length).toBe(before + 1);
      outcomes.push({ scope, fault, rejected: true, cards: 0, trustedRiskAttribution: false });
    }
  }
  expect(scenario.ledger.filter(r => /research-answer|\/answer$|\/tone$/.test(r.path))).toHaveLength(0);
  await info.attach('provenance-outcomes', { body: JSON.stringify(outcomes), contentType: 'application/json' });
});

test('RISK-SEC-01 topic change rejects a delivered old response when transport ignores abort', async ({ page, scenario }, info) => {
  const path = '/companies/AAA/context';
  await scenario.ignoreTransportAbort(path);
  const old = scenario.hold(request => request.path === path && request.query.get('q') === 'supply chain',
    request => ({ body: riskSyntheticEvidence('company', request.query.get('q')!, 0), version: '0' }));
  scenario.overrides.push(request => {
    if (request.path.endsWith('/sources') && request.ticker === 'AAA') return { body: riskData.sources('AAA').map(source => ({ ...source, sec_url: riskSyntheticUrl(source.accession_number) })) };
    if (request.path === path) return { body: riskSyntheticEvidence('company', request.query.get('q')!, 0), version: '0' };
  });
  await scenario.open(); await scenario.ready();
  await page.getByRole('combobox', { name: 'Research purpose', exact: true }).selectOption('risk');
  await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption('company');
  await page.getByRole('button', { name: 'Use risk topic', exact: true }).click();
  await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
  await expect.poll(() => scenario.count(path)).toBe(1);
  await expect(page.getByText('Finding relevant passages in published company filings…', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Risk topic', exact: true }).selectOption('competition');
  await expect(page.getByRole('textbox', { name: 'Research question or search', exact: true })).toHaveValue('competition');
  await expect(page.locator('.evidence-card')).toHaveCount(0);
  expect(scenario.count(path)).toBe(1);
  await page.getByRole('button', { name: 'Search risk topic', exact: true }).click();
  await expect(page.locator('.evidence-results')).toContainText('Search: “competition”');
  old.release();
  await expect.poll(() => scenario.abortedDeliveries(path, '0', 200, '?q=supply+chain&limit=5')).toBe(1);
  await expect(page.locator('.evidence-results')).toContainText('Search: “competition”');
  await expect(page.locator('.evidence-results')).not.toContainText('Search: “supply chain”');
  await expect(page.locator('.evidence-card')).toHaveCount(1);
  await expect(page.locator('.search-form').locator('..').getByRole('alert')).toHaveCount(0);
  expect(scenario.count(path)).toBe(2);
  expect(scenario.ledger.filter(r => /research-answer|\/answer$|\/tone$/.test(r.path))).toHaveLength(0);
  await info.attach('ignored-abort-proof', { body: JSON.stringify({ deliveredAbortedOldResponse: await scenario.abortedDeliveries(path, '0', 200, '?q=supply+chain&limit=5'),
    currentQuery: 'competition', contextRequests: scenario.count(path), violations: scenario.violations }), contentType: 'application/json' });
});
