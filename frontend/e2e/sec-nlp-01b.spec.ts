import { test, expect, gate, type ApiRequest, type Scenario } from './fixtures/browser';
import * as data from './fixtures/data';
import type { BrowserContext, Page, TestInfo } from '@playwright/test';
import type { FilingToneResponse } from '../lib/finlens-api';

// Dedicated synthetic acceptance only. Shared QA-01 route/isolation/cleanup
// fixtures and all application/configuration sources are used unchanged.
const text = "  📈\r\nSTRONG no loss; weak <script>unsafe()</script> e\u0301 CAN’T";
const path = (ticker = 'AAA', chunk = 'chunk_0000') => `/companies/${ticker}/filings/${data.accession(ticker)}/chunks/${chunk}/tone`;
const sourceUrl = (ticker = 'AAA', accession = data.accession(ticker)) => `https://www.sec.gov/Archives/edgar/data/${Number(data.company(ticker).cik)}/${accession.replaceAll('-', '')}/${accession}-index.html`;
type Mode = 'valid' | 'long' | 'bad-count' | 'bad-source' | 'unsupported' | 'pending' | 'network' | 'no-tokens' | 'no-matches' | 'negated' | 'hold' | 'late409';

function response(ticker: string, pin: number, chunk: string, mode: Mode): FilingToneResponse {
  const value: FilingToneResponse = {
    ticker, company_cik: data.company(ticker).cik, company_name: data.company(ticker).name,
    data_version: pin, evidence_version: 0,
    publication: { accession_number: data.accession(ticker), data_version: 0, content_digest: 'a'.repeat(64) },
    source: { chunk_id: chunk, form: '10-K', filed: '2026-02-01', filename: 'synthetic.htm', sec_url: sourceUrl(ticker) },
    scope: 'published_chunk', offsets: 'unicode_code_point', text,
    tone: { method_version: 'sec-filing-tone-v1', lexicon_version: 'authored-finance-tone-v1', status: 'scored', reason: null,
      score: { numerator: 0, denominator: 1 }, token_count: 9, positive_count: 1, negative_count: 1, negated_count: 1,
      matches: [{ text: 'STRONG', term: 'strong', start: 5, end: 11, polarity: 'positive', negator_span: null },
        { text: 'loss', term: 'loss', start: 15, end: 19, polarity: 'negative', negator_span: [12, 14] },
        { text: 'weak', term: 'weak', start: 21, end: 25, polarity: 'negative', negator_span: null }] },
  };
  if (mode === 'long') { value.text += ' ' + 'x'.repeat(3000 - Array.from(text).length - 1); value.tone.token_count = 10; }
  if (mode === 'bad-count') { value.text = text.slice(0, -6); value.tone.token_count = 40; }
  if (mode === 'bad-source') value.source.sec_url += '#invented-passage';
  if (['no-tokens', 'no-matches', 'negated'].includes(mode)) {
    value.text = mode === 'negated' ? 'not strong' : mode === 'no-tokens' ? '...' : '2026';
    Object.assign(value.tone, { status: 'unscorable', score: null,
      reason: mode === 'negated' ? 'all_matches_negated' : mode === 'no-tokens' ? 'no_tokens' : 'no_lexicon_matches',
      token_count: mode === 'negated' ? 2 : mode === 'no-tokens' ? 0 : 1, positive_count: 0, negative_count: 0,
      negated_count: mode === 'negated' ? 1 : 0,
      matches: mode === 'negated' ? [{ text: 'strong', term: 'strong', start: 4, end: 10, polarity: 'positive', negator_span: [0, 3] }] : [] });
  }
  return value;
}

async function install(context: BrowserContext, page: Page, scenario: Scenario) {
  const state = { mode: 'valid' as Mode, barrier: null as ReturnType<typeof gate> | null, requests: [] as ApiRequest[] };
  scenario.overrides.push(request => {
    if (request.path === '/capabilities') return { body: { research_mode: true, ai_analysis_configured: false, ai_analysis_enabled: false, server_profile: 'development' } };
    if (request.path.endsWith('/sources')) return { body: data.sources(request.ticker!).map(item => ({ ...item, form: '10-K', has_filing_chunks: true, sec_url: sourceUrl(request.ticker!, item.accession_number) })) };
    if (!request.path.endsWith('/context')) return;
    const body = data.evidence(request.ticker!, request.query.get('q')!, Number(request.pin), request.path.includes('/filings/') ? data.accession(request.ticker!) : undefined);
    body.citations = Array.from({ length: 3 }, (_, index) => ({ ...body.citations[0], citation_id: `source_${index + 1}`, chunk_id: `chunk_${String(index).padStart(4, '0')}`, sec_url: sourceUrl(request.ticker!), start_char: 9000 + index * 3000, end_char: 12000 + index * 3000 }));
    body.context = body.citations.map(citation => {
      const metadata = Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, citation[key as keyof typeof citation]]));
      return `[SOURCE ${citation.citation_id}]\nmetadata: ${JSON.stringify(metadata)}\ntext: |-\n  Search preview is separate from exact tone text.\n[END SOURCE ${citation.citation_id}]`;
    }).join('\n\n');
    return { body };
  });
  await context.addInitScript(() => { Object.assign(window, { toneMarkupExecutions: 0, unsafe: () => { (window as unknown as { toneMarkupExecutions: number }).toneMarkupExecutions++; } }); });
  // Use the existing ignored-abort seam; no production signal/guard is disabled.
  await scenario.ignoreTransportAbort(path());
  await context.route('**/api/finlens/companies/*/filings/*/chunks/*/tone', async route => {
    const request = route.request(), url = new URL(request.url());
    const match = url.pathname.match(/^\/api\/finlens\/companies\/(AAA|BBB)\/filings\/([0-9-]+)\/chunks\/(chunk_000[0-2])\/tone$/);
    expect(match, 'Only named synthetic tone selectors').not.toBeNull();
    const ticker = match![1], chunk = match![3], pin = request.headers()['x-finlens-data-version'];
    expect(url.origin).toBe('http://127.0.0.1:3107'); expect(url.search).toBe('');
    expect(request.method()).toBe('GET'); expect(request.postData()).toBeNull();
    expect(match![2]).toBe(data.accession(ticker)); expect(pin).toMatch(/^(0|[1-9][0-9]*)$/);
    expect(Number(pin)).toBeLessThanOrEqual(scenario.versions[ticker]);
    expect((await request.headersArray()).filter(header => header.name.toLowerCase() === 'x-finlens-data-version')).toHaveLength(1);
    const item = { method: 'GET', path: url.pathname.slice('/api/finlens'.length), ticker, pin, query: url.searchParams, body: null, request };
    const mode = state.mode, barrier = state.barrier, body = response(ticker, Number(pin), chunk, mode);
    state.requests.push(item); scenario.ledger.push(item);
    if (mode === 'network') { Object.assign(item, { injectedAbort: true }); await route.abort('failed'); return; }
    if (mode === 'hold' || mode === 'late409') { expect(barrier).not.toBeNull(); await barrier!.promise; }
    const code = mode === 'unsupported' ? 'TONE_INPUT_UNSUPPORTED' : mode === 'pending' ? 'EVIDENCE_PENDING' : mode === 'late409' ? 'DATA_VERSION_CHANGED' : null;
    await route.fulfill({ status: code ? 409 : 200, contentType: 'application/json',
      headers: { 'X-FinLens-Data-Version': mode === 'late409' ? String(Number(pin) + 1) : pin!, ...(code ? { 'X-FinLens-Error-Code': code } : {}) },
      body: JSON.stringify(code ? { detail: 'Synthetic controlled error' } : body) }).catch(error => {
        if (!String(error).includes('closed') && !String(error).includes('Invalid InterceptionId')) throw error;
      });
  });
  return { state, hold(mode: 'hold' | 'late409' = 'hold') { state.mode = mode; state.barrier = scenario.hold(() => false); return state.barrier; } };
}

async function research(page: Page, scope: 'filing' | 'company' = 'filing') {
  await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption(scope);
  await page.getByRole('textbox', { name: 'Research question or search', exact: true }).fill(`Inspect lexical fixture ${scope}`);
  await page.getByRole('button', { name: 'Research question', exact: true }).click();
  await expect(page.locator('.evidence-card')).toHaveCount(2);
  await expect(page.locator('.direct-answer')).toBeVisible();
}
async function geometry(page: Page) {
  return page.locator('.passage-tone').first().evaluate(root => {
    const panel = root.querySelector('section')!, passage = root.querySelector('.tone-passage')!;
    const rect = panel.getBoundingClientRect();
    const targets = Array.from(root.querySelectorAll('button,summary,a')).filter(element => (element as HTMLElement).offsetHeight > 0 && element.getClientRects().length > 0)
      .map(element => { const box = element.getBoundingClientRect(); return { label: element.textContent, width: box.width, height: box.height }; });
    return { viewport: { width: innerWidth, height: innerHeight }, documentWidth: document.documentElement.scrollWidth,
      panel: { x: rect.x, right: rect.right, width: panel.clientWidth, scrollWidth: panel.scrollWidth },
      passage: { width: passage.clientWidth, scrollWidth: passage.scrollWidth, whiteSpace: getComputedStyle(passage).whiteSpace }, targets };
  });
}
async function save(info: TestInfo, page: Page, scenario: Scenario, name: string, measurements: unknown) {
  await info.attach(name, { body: JSON.stringify({ browser: page.context().browser()!.version(), viewport: page.viewportSize(),
    theme: await page.locator('html').getAttribute('data-theme'), measurements,
    ledger: scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin, query: query.toString() })), violations: scenario.violations, failures: scenario.failures }, null, 2), contentType: 'application/json' });
  await info.attach(`${name}-screenshot`, { body: await page.screenshot(), contentType: 'image/png' });
}

for (const mobile of [false, true]) for (const theme of ['light', 'dark']) {
  test.describe(`${mobile ? 'mobile 390x844' : 'desktop 1440x900'} ${theme}`, () => {
    test.use({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 }, isMobile: mobile, hasTouch: mobile });
    test('tone presentation, Unicode, source, keyboard and 3000-point geometry', async ({ page, context, scenario }, info) => {
      const control = await install(context, page, scenario);
      await scenario.open(); await scenario.ready();
      await page.getByLabel('Theme', { exact: true }).selectOption(theme);
      const measurements = [];
      for (const scope of ['filing', 'company'] as const) {
        await research(page, scope); const start = control.state.requests.length;
        await page.locator('.evidence-card').first().getByText('Read full evidence passage', { exact: true }).click();
        expect(control.state.requests).toHaveLength(start);
        const trigger = page.getByRole('button', { name: 'Inspect passage tone', exact: true }).first();
        const barrier = control.hold();
        await trigger.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab');
        await expect(trigger).toBeFocused();
        const focus = await trigger.evaluate(element => ({ visible: element.matches(':focus-visible'), width: getComputedStyle(element).outlineWidth, style: getComputedStyle(element).outlineStyle }));
        expect(focus.visible).toBe(true); expect(focus.width).toBe('3px'); expect(focus.style).toBe('solid');
        await page.keyboard.press('Enter');
        await expect.poll(() => control.state.requests.length).toBe(start + 1);
        const panel = page.locator('.passage-tone section').first();
        await expect(panel).toHaveAttribute('aria-busy', 'true'); await expect(panel.getByRole('status')).toContainText('Inspecting');
        // aria-disabled is advisory in native HTML. Deliver real pointer events
        // deliberately so the production pending guard, not actionability, wins.
        await page.getByRole('button', { name: 'Inspecting passage tone…', exact: true }).dblclick({ force: true });
        expect(control.state.requests).toHaveLength(start + 1);
        expect(control.state.requests.at(-1)!.pin).toBe('0');
        barrier.release(); await expect(panel.locator('.tone-passage')).toBeVisible();
        expect(await panel.locator('.tone-passage').textContent()).toBe(text);
        await expect(panel.locator('.tone-summary')).toContainText('0/1'); await expect(panel.locator('.tone-summary')).toContainText('Tokens: 9');
        await expect(panel.getByRole('heading', { name: 'Passage lexical tone proxy' })).toBeVisible();
        await expect(panel).toContainText('not predictive sentiment, confidence, market risk, investment advice or a whole-filing conclusion');
        expect(await panel.locator('.tone-passage mark').allTextContents()).toEqual(['STRONG', 'loss', 'weak']);
        await panel.getByText('Matched terms and local spans (3)', { exact: true }).focus(); await page.keyboard.press('Enter');
        await expect(panel.locator('.tone-matches')).toContainText('positive'); await expect(panel.locator('.tone-matches')).toContainText('negative · negated, excluded');
        await expect(panel.locator('.tone-matches')).toContainText('[5, 11)'); await expect(panel.locator('.tone-matches')).toContainText('negator [12, 14)');
        await expect(panel.locator('.tone-summary')).toContainText('Negated, excluded: 1');
        await expect(panel.getByRole('link', { name: 'Open official SEC filing ↗', exact: true })).toHaveAttribute('href', sourceUrl());
        await expect(panel.locator('.tone-source')).toContainText('CIK 0000900001');
        expect(await panel.locator('script').count()).toBe(0); expect(await page.evaluate(() => (window as unknown as { toneMarkupExecutions: number }).toneMarkupExecutions)).toBe(0);
        const ids = await page.locator('.passage-tone > button').evaluateAll(buttons => buttons.map(button => button.getAttribute('aria-controls')));
        expect(new Set(ids).size).toBe(ids.length);
        measurements.push({ scope, focus, normal: await geometry(page) });
        await save(info, page, scenario, `${scope}-normal`, measurements.at(-1));
        await page.getByRole('button', { name: 'Close passage tone', exact: true }).click(); await expect(trigger).toBeFocused();
        control.state.mode = 'long'; await trigger.press('Enter'); await expect(panel.locator('.tone-passage')).toBeVisible();
        expect(await panel.locator('.tone-passage').textContent()).toBe(response('AAA', 0, 'chunk_0000', 'long').text);
        const layout = await geometry(page);
        expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport.width + 1);
        expect(layout.panel.x).toBeGreaterThanOrEqual(0); expect(layout.panel.right).toBeLessThanOrEqual(layout.viewport.width + 1);
        expect(layout.panel.scrollWidth).toBeLessThanOrEqual(layout.panel.width + 1);
        expect(layout.passage.scrollWidth).toBeLessThanOrEqual(layout.passage.width + 1);
        expect(layout.passage.whiteSpace).toBe('pre-wrap');
        for (const target of layout.targets) { expect(target.height, target.label ?? '').toBeGreaterThanOrEqual(44); expect(target.width).toBeGreaterThanOrEqual(44); }
        measurements.push({ scope, long: layout }); await panel.getByRole('heading').scrollIntoViewIfNeeded();
        await save(info, page, scenario, `${scope}-long`, layout);
        await page.getByRole('button', { name: 'Close passage tone', exact: true }).click();
        control.state.mode = 'valid';
      }
      await info.attach('complete-geometry', { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' });
    });

    test('tone fail-closed states, explicit retry, cancellation, stale delivery and unmount', async ({ page, context, scenario }, info) => {
      await page.clock.install();
      const control = await install(context, page, scenario);
      await scenario.open(); await scenario.ready(); await page.getByLabel('Theme', { exact: true }).selectOption(theme);
      await research(page);
      const widget = page.locator('.passage-tone').first(), panel = widget.locator('section');
      const trigger = widget.getByRole('button', { name: 'Inspect passage tone', exact: true });
      for (const [mode, message] of [['bad-count', 'could not be verified'], ['bad-source', 'could not be verified'], ['unsupported', 'unsupported'], ['pending', 'incomplete or changed'], ['network', 'Could not reach']] as const) {
        control.state.mode = mode; await trigger.click();
        await expect(panel.getByRole('alert')).toContainText(message);
        await expect(panel.locator('.tone-summary,.tone-passage,.tone-source')).toHaveCount(0);
        const count = control.state.requests.length;
        if (mode === 'bad-count' || mode === 'network') {
          control.state.mode = 'valid'; await panel.getByRole('button', { name: 'Retry passage tone', exact: true }).click();
          await expect(panel.locator('.tone-summary')).toBeVisible(); expect(control.state.requests).toHaveLength(count + 1);
        } else if (mode === 'unsupported' || mode === 'pending') await expect(panel.getByRole('button', { name: 'Retry passage tone', exact: true })).toHaveCount(0);
        await widget.getByRole('button', { name: 'Close passage tone', exact: true }).click();
      }
      for (const mode of ['no-tokens', 'no-matches', 'negated'] as const) {
        control.state.mode = mode; await trigger.click(); await expect(panel.locator('.tone-summary')).toContainText('No score is available');
        await expect(panel.getByRole('alert')).toHaveCount(0); await expect(panel.locator('.tone-summary')).not.toContainText('0/1');
        await widget.getByRole('button', { name: 'Close passage tone', exact: true }).click();
      }
      const expired = control.hold(); await trigger.click();
      await expect(panel).toHaveAttribute('aria-busy', 'true'); await page.clock.fastForward(31_000);
      await expect(panel.getByRole('alert')).toContainText('too long');
      const replacement = control.hold(); await panel.getByRole('button', { name: 'Retry passage tone', exact: true }).click();
      const count = control.state.requests.length; expired.release();
      await expect.poll(() => scenario.abortedDeliveries(path(), '0', 200)).toBeGreaterThan(0);
      await expect(panel.locator('.tone-summary')).toHaveCount(0); await expect(panel).toHaveAttribute('aria-busy', 'true');
      replacement.release(); await expect(panel.locator('.tone-summary')).toBeVisible(); expect(control.state.requests).toHaveLength(count);
      await widget.getByRole('button', { name: 'Close passage tone', exact: true }).click();
      const cancelled = control.hold(); await trigger.click(); await panel.getByRole('button', { name: 'Cancel passage tone', exact: true }).click();
      await expect(trigger).toBeFocused(); cancelled.release(); await expect(panel).toBeHidden();
      await page.getByRole('button', { name: 'Show more evidence (1)', exact: true }).click();
      const third = page.locator('.passage-tone').nth(2), hidden = control.hold();
      await third.getByRole('button', { name: 'Inspect passage tone', exact: true }).click();
      await page.getByRole('button', { name: 'Show less evidence', exact: true }).click(); hidden.release();
      await expect(page.locator('.passage-tone')).toHaveCount(2);
      const obsolete = control.hold('late409'); await trigger.click();
      await expect.poll(() => control.state.requests.at(-1)!.pin).toBe('0');
      scenario.versions.AAA = 1; await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(page.getByLabel('Data freshness')).toContainText('version 1');
      await expect(page.locator('.passage-tone')).toHaveCount(0);
      const checks = scenario.count('/companies/AAA/freshness'); obsolete.release();
      await expect.poll(() => scenario.abortedDeliveries(path(), '0', 409)).toBeGreaterThan(0);
      expect(scenario.count('/companies/AAA/freshness')).toBe(checks);
      await research(page); const switched = control.hold();
      await page.getByRole('button', { name: 'Inspect passage tone', exact: true }).first().click();
      await expect.poll(() => control.state.requests.at(-1)!.pin).toBe('1');
      await page.getByRole('combobox', { name: 'Indexed SEC filing', exact: true }).selectOption(data.accession('AAA', '000002'));
      await expect(page.locator('.passage-tone')).toHaveCount(0); switched.release();
      const picker = page.getByRole('combobox', { name: 'Company', exact: true });
      await picker.selectOption('BBB'); await picker.selectOption('AAA'); await picker.selectOption('BBB'); await scenario.ready('BBB');
      await expect(page.locator('.tone-passage')).toHaveCount(0);
      await save(info, page, scenario, 'failure-lifecycle-evidence', { toneRequests: control.state.requests.length, stale409Checks: checks });
    });
  });
}
