import { test, expect } from './fixtures/browser';
import * as riskData from './fixtures/data';
import type { Locator } from '@playwright/test';

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
