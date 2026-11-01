import type { Locator, Page, TestInfo } from '@playwright/test';
import { test, expect, lifecycle, annualRequestCursor, expectedRequest, completedRequests,
  publicationCompletions, publicationHeaderCancellations, replayCancellations,
  captureFocusPaint, assessFocusPaint, type ExpectedLedger } from './fixtures/annual-period-browser';
import type { Scenario } from './fixtures/browser';
import { supportsInsightsPublication } from './fixtures/financial-insights-browser';
import * as data from './fixtures/data';

test.use({ deviceScaleFactor: 1 });
const capability = (enabled: boolean) => ({ research_mode: true, ai_analysis_configured: false,
  ai_analysis_enabled: false, server_profile: 'sec_readonly', filing_research_enabled: enabled });
const endpoint = (ticker: string) => `/companies/${ticker}/research-answer`;
const answerRequest = (ticker: string, pin: number, question: string) =>
  JSON.stringify(['POST', endpoint(ticker), '', String(pin), { question }]);
type FinancialDelivery = { requestId: number; method: string; path: string; query: string; pin: string | null;
  body: string | null; status: number; signalAborted: boolean; stage: 'headers_returned' };
// One installation per document, one store for all selected synthetic routes.
// HTTP body completion is independently checked by the request-object ledger.
function installFinancialObserver({ paths }: { paths: string[] }) {
  const target = window as Window & { qaFinancialOnlyDeliveries?: FinancialDelivery[] };
  if ('qaFinancialOnlyDeliveries' in target) throw new Error('Financial observer already installed');
  const methods: Record<string, string> = { '/api/finlens/companies/AAA/research-answer': 'POST',
    '/api/finlens/companies/BBB/research-answer': 'POST', '/api/finlens/companies/BBB/financials/summary': 'GET' };
  const selected = new Set(paths.map(path => path.startsWith('/api/finlens/') ? path : `/api/finlens${path}`));
  if (!paths.length || paths.length > 3 || selected.size !== paths.length || [...selected].some(path => !methods[path])) throw new Error('Invalid financial observer routes');
  const nativeFetch = window.fetch.bind(window), deliveries: FinancialDelivery[] = [];
  target.qaFinancialOnlyDeliveries = deliveries;
  let started = 0;
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href);
    if (url.origin !== location.origin || !selected.has(url.pathname)) return nativeFetch(input, init);
    const request = input instanceof Request ? input : null;
    const method = (init?.method ?? request?.method ?? 'GET').toUpperCase();
    const body = init?.body ?? null;
    if (method !== methods[url.pathname] || request?.body
      || (body !== null && (typeof body !== 'string' || new TextEncoder().encode(body).length > 8192))
      || (method === 'GET' && body !== null) || started >= 200) throw new Error('Unsupported financial observer request');
    const signal = init?.signal === undefined ? request?.signal : init.signal;
    const headers = new Headers(init?.headers ?? request?.headers);
    const identity = { requestId: ++started, method, path: url.pathname, query: url.search,
      pin: headers.get('X-FinLens-Data-Version'), body: body as string | null };
    const response = await nativeFetch(input, { ...init, signal: null });
    deliveries.push(Object.freeze({ ...identity, status: response.status, signalAborted: signal?.aborted ?? false,
      stage: 'headers_returned' as const }));
    return response;
  };
}
async function abortedFinancialReturns(page: Page, ticker: string, pin: number, question: string) {
  return page.evaluate(({ path, pin, body }) => {
    const rows = (window as Window & { qaFinancialOnlyDeliveries?: FinancialDelivery[] }).qaFinancialOnlyDeliveries;
    if (!Array.isArray(rows)) throw new Error('Financial observer is unavailable');
    return rows.filter(row => row.method === 'POST' && row.path === path && row.query === '' && row.pin === pin
      && row.body === body && row.status === 200 && row.signalAborted && row.stage === 'headers_returned').length;
  },
  { path: `/api/finlens${endpoint(ticker)}`, pin: String(pin), body: JSON.stringify({ question }) });
}
type Ledger = ExpectedLedger & { phases: { after: number; native: string[] }[] };
function ledger(capabilityPending = false): Ledger {
  return { completed: completedRequests([expectedRequest('/companies'), ...(!capabilityPending ? [expectedRequest('/capabilities')] : [])]),
    pending: capabilityPending ? [expectedRequest('/capabilities')] : [], cancelled: [], cancelledAfterHeaders: [], phases: [] };
}
function publication(expected: Ledger, ticker: string, pin: number, period = 'quarter') {
  expected.completed.push(...publicationCompletions(ticker, pin).filter(row => !JSON.parse(row.request)[1].endsWith('/sources'))
    .map(row => JSON.parse(row.request)[1].endsWith('/financials/summary')
      ? { ...row, request: expectedRequest(`/companies/${ticker}/financials/summary`, pin, `period=${period}`) } : row));
  expected.cancelledAfterHeaders.push(...publicationHeaderCancellations(ticker, pin));
}
function phase(scenario: Scenario, expected: Ledger, ticker: string, pin: number, initial = false, freshness = true) {
  expected.phases.push({ after: initial ? 0 : annualRequestCursor(scenario), native: replayCancellations(ticker, pin, freshness) });
}
// Keep the existing observed-request-first recorder. Only the three exact
// declared startup replay signatures may have zero/one headerless cancellation
// per phase, paired with a distinct successful same-generation request.
async function exactLedger(scenario: Scenario, expected: Ledger) {
  const intended = [
    ...expected.completed.map(row => JSON.stringify([row.request, 'completed', { status: row.status, version: row.version, code: row.code }, null])),
    ...expected.cancelledAfterHeaders.map(row => JSON.stringify([row.request, 'cancelled', { status: row.status, version: row.version, code: row.code }, 'net::ERR_ABORTED'])),
    ...expected.pending.map(request => JSON.stringify([request, 'pending', null, null])),
  ].sort();
  await expect.poll(() => {
    const snapshot = lifecycle(scenario, expected.phases.flatMap(item => item.native)), errors: string[] = [], seen = new Set<string>();
    const native = snapshot.rows.filter(row => row.state === 'cancelled' && row.response === null);
    for (const row of native) {
      const owner = expected.phases.findLast(item => row.id > item.after), key = `${owner?.after}:${row.request}`;
      const peers = snapshot.rows.filter(candidate => candidate.generation === row.generation && candidate.request === row.request);
      const other = peers.find(candidate => candidate.id !== row.id), pin = JSON.parse(row.request)[3];
      if (!owner?.native.includes(row.request) || seen.has(key) || !row.bodyAbsent || row.error !== 'net::ERR_ABORTED'
        || peers.length !== 2 || !other?.routed || !other.bodyAbsent || other.state !== 'completed'
        || other.response?.status !== 200 || other.response.version !== pin || other.response.code !== null || other.error !== null) errors.push(`Invalid replay ${row.id}`);
      seen.add(key);
    }
    return { binding: snapshot.bindingErrors, unbound: snapshot.rejectedUnbound, errors,
      rows: snapshot.rows.filter(row => !native.includes(row)).map(row => JSON.stringify([row.request, row.state, row.response, row.error])).sort(),
      violations: scenario.violations };
  }).toEqual({ binding: [], unbound: [], errors: [], rows: intended, violations: [] });
}
async function audit(scenario: Scenario, expected: Ledger, info: TestInfo) {
  const observer = await scenario.page.evaluate(() =>
    (window as Window & { qaFinancialOnlyDeliveries?: FinancialDelivery[] }).qaFinancialOnlyDeliveries ?? []);
  const body = JSON.stringify({ synthetic: true, phases: expected.phases,
    lifecycle: lifecycle(scenario, expected.phases.flatMap(item => item.native)), observer, violations: scenario.violations });
  expect(Buffer.byteLength(body)).toBeLessThanOrEqual(32768);
  await info.attach('financial-only-request-audit', { body, contentType: 'application/json' });
}
function blockUnverifiedRetrieval(scenario: Scenario, enabled: () => boolean) {
  scenario.overrides.unshift(request => {
    if (!enabled() && (/\/sources$|\/context$|\/filings\//.test(request.path))) throw new Error('Filing request before capability verification');
    return undefined;
  });
}
async function financialReady(page: Page, ticker: string, pin: number) {
  await expect(page.getByRole('combobox', { name: 'Company', exact: true })).toHaveValue(ticker);
  await expect(page.getByRole('region', { name: 'Data freshness', exact: true })).toContainText(`version ${pin}`);
  await expect(page.getByRole('region', { name: 'Financial snapshot', exact: true }).locator('.metric-value').first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Reported quarter-duration windows', exact: true }).getByRole('status'))
    .toHaveText('Select two to four reported windows.');
  await expect(page.getByRole('region', { name: 'Annual financial insights', exact: true }).locator('.insights-status')).toHaveText(
    supportsInsightsPublication(ticker, pin) ? 'Choose Compare annual periods to request this comparison.'
      : 'Annual financial insights could not be loaded or verified. Retry explicitly.', { timeout: 35_000 });
}
// Use the established outward-outline paint oracle for these ordinary form
// controls, with extra ancestor/occlusion guards. No focus/scroll adjustment.
async function capture(control: Locator, name: string, page: Page, info: TestInfo) {
  await expect(control).toBeFocused();
  const geometry = await control.evaluate(captureFocusPaint);
  const visibility = await control.evaluate((element, points) => {
    const r = element.getBoundingClientRect(), ancestors = [];
    for (let node = element.parentElement; node; node = node.parentElement) {
      const s = getComputedStyle(node), b = node.getBoundingClientRect();
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') ancestors.push({
        left: b.left + node.clientLeft, right: b.left + node.clientLeft + node.clientWidth,
        top: b.top + node.clientTop, bottom: b.top + node.clientTop + node.clientHeight,
        x: s.overflowX !== 'visible', y: s.overflowY !== 'visible' });
    }
    const hit = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
    return { dpr: devicePixelRatio, height: r.height, pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth,
      center: !!hit && (hit === element || element.contains(hit)), ancestors,
      perimeter: points.every(point => !!document.elementFromPoint(point.x, point.y)?.contains(element)) };
  }, geometry.surfaces);
  const contrast = assessFocusPaint(geometry.outlineColor, geometry.surfaces);
  await info.attach(`${name}-geometry`, { body: JSON.stringify({ geometry, visibility, contrast }), contentType: 'application/json' });
  await info.attach(name, { body: await page.screenshot(), contentType: 'image/png' });
  expect(visibility.dpr).toBe(1); expect(visibility.center).toBe(true); expect(visibility.perimeter).toBe(true);
  expect(visibility.height).toBeGreaterThanOrEqual(44); expect(visibility.pageWidth).toBeLessThanOrEqual(visibility.viewportWidth);
  expect(geometry.offset).toBeGreaterThanOrEqual(0); expect(geometry.width).toBeGreaterThanOrEqual(3);
  expect(geometry.visible).toBe(true); expect(geometry.outline).not.toBe('none'); expect(contrast.sufficient).toBe(true);
  const box = { left: geometry.rect.left - geometry.extent, right: geometry.rect.right + geometry.extent,
    top: geometry.rect.top - geometry.extent, bottom: geometry.rect.bottom + geometry.extent };
  for (const number of [...Object.values(box), ...Object.values(geometry.clip)]) expect(Number.isFinite(number)).toBe(true);
  expect(box.left).toBeGreaterThan(geometry.clip.left - 0.5); expect(box.right).toBeLessThan(geometry.clip.right + 0.5);
  expect(box.top).toBeGreaterThan(geometry.clip.top - 0.5); expect(box.bottom).toBeLessThan(geometry.clip.bottom + 0.5);
  for (const ancestor of visibility.ancestors) {
    if (ancestor.x) { expect(box.left).toBeGreaterThan(ancestor.left - 0.5); expect(box.right).toBeLessThan(ancestor.right + 0.5); }
    if (ancestor.y) { expect(box.top).toBeGreaterThan(ancestor.top - 0.5); expect(box.bottom).toBeLessThan(ancestor.bottom + 0.5); }
  }
}
async function submit(page: Page, question: string, focused?: () => Promise<void>) {
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  await editor.fill(question);
  await editor.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Research question', exact: true })).toBeFocused();
  if (focused) await focused();
  await page.keyboard.press('Enter');
}

test('financial-only: explicit questions and company/publication stale isolation', async ({ page, scenario }, info) => {
  scenario.versions.BBB = 1;
  blockUnverifiedRetrieval(scenario, () => false);
  scenario.overrides.push(request => request.path === '/capabilities' ? { body: capability(false) } : undefined);
  await page.addInitScript(installFinancialObserver, { paths: [endpoint('AAA'), endpoint('BBB'), '/companies/BBB/financials/summary'] });
  const companyQuestion = 'What was the latest revenue?', publicationQuestion = 'Latest revenue';
  const oldCompany = scenario.hold(request => request.path === endpoint('AAA') && (request.body as { question?: string })?.question === companyQuestion,
    () => ({ body: { ...data.answer('AAA', companyQuestion), answer_text: 'OBSOLETE COMPANY ANSWER' }, version: '0' }));
  const oldPublication = scenario.hold(request => request.path === endpoint('BBB') && request.pin === '1' && (request.body as { question?: string })?.question === publicationQuestion,
    () => ({ body: { ...data.answer('BBB', publicationQuestion), answer_text: 'OBSOLETE PUBLICATION ANSWER' }, version: '1' }));
  const expected = ledger(); publication(expected, 'AAA', 0); phase(scenario, expected, 'AAA', 0, true);
  try {
    await scenario.open(); await financialReady(page, 'AAA', 0); await exactLedger(scenario, expected);
    await expect(page.getByRole('status').filter({ hasText: 'Financial-only capability restriction is active.' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Financial questions', exact: true })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Research purpose', exact: true })).toHaveCount(0);
    await submit(page, 'revenue', () => capture(page.getByRole('button', { name: 'Research question', exact: true }), 'restricted-submit', page, info));
    expected.completed.push(...completedRequests([answerRequest('AAA', 0, 'revenue')]));
    await expect(page.locator('.direct-answer')).toContainText('$1B'); await exactLedger(scenario, expected);
    await submit(page, companyQuestion); expected.pending.push(answerRequest('AAA', 0, companyQuestion)); await exactLedger(scenario, expected);
    phase(scenario, expected, 'BBB', 1);
    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('BBB');
    publication(expected, 'BBB', 1); expected.completed.push(...completedRequests([expectedRequest('/companies')]));
    await financialReady(page, 'BBB', 1); oldCompany.release();
    await expect.poll(() => abortedFinancialReturns(page, 'AAA', 0, companyQuestion)).toBe(1);
    expected.pending.splice(expected.pending.indexOf(answerRequest('AAA', 0, companyQuestion)), 1);
    expected.completed.push(...completedRequests([answerRequest('AAA', 0, companyQuestion)]));
    await expect(page.locator('.direct-answer')).toHaveCount(0); await exactLedger(scenario, expected);
    await submit(page, 'revenue'); expected.completed.push(...completedRequests([answerRequest('BBB', 1, 'revenue')]));
    await expect(page.locator('.direct-answer')).toContainText('$2B');
    await submit(page, publicationQuestion); expected.pending.push(answerRequest('BBB', 1, publicationQuestion)); await exactLedger(scenario, expected);
    phase(scenario, expected, 'BBB', 2, false, false); scenario.versions.BBB = 2;
    await page.getByRole('combobox', { name: 'Snapshot period', exact: true }).selectOption('annual');
    expected.completed.push(...completedRequests([expectedRequest('/companies/BBB/financials/summary', 1, 'period=annual')], 409, '2', 'DATA_VERSION_CHANGED'));
    publication(expected, 'BBB', 2, 'annual'); expected.completed.push(...completedRequests([expectedRequest('/companies')]));
    await financialReady(page, 'BBB', 2); oldPublication.release();
    await expect.poll(() => abortedFinancialReturns(page, 'BBB', 1, publicationQuestion)).toBe(1);
    expected.pending.splice(expected.pending.indexOf(answerRequest('BBB', 1, publicationQuestion)), 1);
    expected.completed.push(...completedRequests([answerRequest('BBB', 1, publicationQuestion)]));
    await expect(page.locator('.direct-answer')).toHaveCount(0);
    await submit(page, 'revenue'); expected.completed.push(...completedRequests([answerRequest('BBB', 2, 'revenue')]));
    await expect(page.locator('.direct-answer')).toContainText('$2B');
    await expect(page.locator('.direct-answer')).not.toContainText('OBSOLETE');
    await page.getByRole('textbox', { name: 'Research question or search', exact: true }).click();
    await capture(page.getByRole('textbox', { name: 'Research question or search', exact: true }), 'restricted-current-editor', page, info);
    expect(scenario.ledger.filter(request => request.path.endsWith('/research-answer'))).toHaveLength(5);
    await exactLedger(scenario, expected);
  } finally { await audit(scenario, expected, info); }
});

test('financial-only: delayed full capability preserves pending and completed financial ownership', async ({ page, scenario }, info) => {
  let navigation = 0, enabled = false;
  blockUnverifiedRetrieval(scenario, () => enabled);
  const caps = [0, 1].map(index => scenario.hold(request => request.path === '/capabilities' && navigation === index, () => ({ body: capability(true) })));
  const answer = scenario.hold(request => navigation === 0 && request.path === endpoint('AAA'));
  await page.addInitScript(installFinancialObserver, { paths: [endpoint('AAA')] });
  const expected = ledger(true); publication(expected, 'AAA', 0); phase(scenario, expected, 'AAA', 0, true);
  try {
    for (const completed of [false, true]) {
      if (completed) {
        navigation = 1; enabled = false; phase(scenario, expected, 'AAA', 0);
        expected.pending.push(expectedRequest('/capabilities'));
        expected.completed.push(...completedRequests([expectedRequest('/companies')])); publication(expected, 'AAA', 0);
        await page.reload();
      } else await scenario.open();
      await financialReady(page, 'AAA', 0);
      expect(scenario.ledger.filter(request => /\/sources$|\/context$|\/filings\//.test(request.path))).toHaveLength(completed ? 1 : 0);
      await submit(page, 'revenue');
      const signature = answerRequest('AAA', 0, 'revenue');
      if (completed) { expected.completed.push(...completedRequests([signature])); await expect(page.locator('.direct-answer')).toContainText('$1B'); }
      else expected.pending.push(signature);
      await exactLedger(scenario, expected);
      const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
      await editor.click();
      const editorNode = await editor.elementHandle(), form = await editor.locator('xpath=ancestor::form').elementHandle();
      const oldAnswer = completed ? await page.locator('.direct-answer').elementHandle() : null;
      enabled = true; caps[navigation].release();
      expected.pending.splice(expected.pending.indexOf(expectedRequest('/capabilities')), 1);
      expected.completed.push(...completedRequests([expectedRequest('/capabilities'), expectedRequest('/companies/AAA/sources', 0)]));
      await expect(page.getByRole('combobox', { name: 'Indexed SEC filing', exact: true })).toBeEnabled();
      await expect(page.getByRole('combobox', { name: 'Research purpose', exact: true })).toBeVisible();
      expect(await editor.evaluate((node, saved) => node === saved, editorNode)).toBe(true);
      expect(await editor.locator('xpath=ancestor::form').evaluate((node, saved) => node === saved, form)).toBe(true);
      await expect(editor).toHaveValue('revenue'); await expect(editor).toBeFocused();
      if (completed) expect(await page.locator('.direct-answer').evaluate((node, saved) => node === saved, oldAnswer)).toBe(true);
      await capture(editor, completed ? 'completed-editor-retained' : 'pending-editor-retained', page, info);
      if (!completed) {
        answer.release(); expected.pending.splice(expected.pending.indexOf(signature), 1);
        expected.completed.push(...completedRequests([signature]));
      }
      await expect(page.locator('.direct-answer')).toContainText('$1B');
      expect(scenario.ledger.filter(request => request.path === endpoint('AAA'))).toHaveLength(navigation + 1);
      expect(scenario.ledger.some(request => request.path.endsWith('/context') || request.path.endsWith('/search'))).toBe(false);
      expect(await abortedFinancialReturns(page, 'AAA', 0, 'revenue')).toBe(0);
      expect(await page.evaluate(() => (window as Window & { qaFinancialOnlyDeliveries?: FinancialDelivery[] }).qaFinancialOnlyDeliveries?.length)).toBe(1);
      await exactLedger(scenario, expected);
    }
  } finally { await audit(scenario, expected, info); }
});
