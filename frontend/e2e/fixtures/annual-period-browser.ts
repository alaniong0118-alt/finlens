import type { BrowserContext, Request, Response, TestInfo } from '@playwright/test';
import { test as base, expect, type ApiRequest, type Scenario, type Reply } from './browser';
import { supportsInsightsPublication } from './financial-insights-browser';
import * as data from './data';
import type { AnnualFinancialComparison, NormalizedMetric } from '../../lib/finlens-api';

export { expect };
export const annualYears = [2025, 2024, 2023, 2022];
export const missingAnnualReason = 'Synthetic ambiguous annual window for FY2022; no substitute period.';
type Rgba = [number, number, number, number];
function focusColor(value: string): Rgba | null {
  if (value === 'transparent') return [0, 0, 0, 0];
  const match = /^rgba?\(([^)]+)\)$/.exec(value);
  if (!match) return null;
  const tokens = match[1].replaceAll(',', ' ').replaceAll('/', ' ').trim().split(/\s+/);
  if (tokens.length !== 3 && tokens.length !== 4) return null;
  const channels = tokens.slice(0, 3).map(token => token.endsWith('%') ? Number(token.slice(0, -1)) * 255 / 100 : Number(token));
  const alpha = tokens[3] === undefined ? 1 : tokens[3].endsWith('%') ? Number(tokens[3].slice(0, -1)) / 100 : Number(tokens[3]);
  return channels.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 255)
    && Number.isFinite(alpha) && alpha >= 0 && alpha <= 1 ? [...channels, alpha] as Rgba : null;
}
function over(foreground: Rgba, background: Rgba): Rgba {
  const alpha = foreground[3] + background[3] * (1 - foreground[3]);
  return [...foreground.slice(0, 3).map((value, index) => alpha === 0 ? 0
    : (value * foreground[3] + background[index] * background[3] * (1 - foreground[3])) / alpha), alpha] as Rgba;
}
export function assessFocusPaint(outlineColor: string, surfaces: { layers: { color: string }[]; unsupported: string[] }[]) {
  const outline = focusColor(outlineColor), ratios: number[] = [];
  if (!outline || surfaces.length !== 4) return { sufficient: false, ratios, reason: 'Missing or unsupported outline/surfaces' };
  const luminance = (color: Rgba) => color.slice(0, 3).map(channel => channel / 255)
    .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
  for (const surface of surfaces) {
    if (surface.unsupported.length) return { sufficient: false, ratios, reason: surface.unsupported.join('; ') };
    let background: Rgba = [0, 0, 0, 0];
    for (const layer of [...surface.layers].reverse()) {
      const color = focusColor(layer.color);
      if (!color) return { sufficient: false, ratios, reason: 'Unsupported adjacent color' };
      background = over(color, background);
    }
    if (background[3] !== 1) return { sufficient: false, ratios, reason: 'Adjacent painted surface is not resolved' };
    const a = luminance(over(outline, background)), b = luminance(background);
    ratios.push((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05));
  }
  return { sufficient: ratios.every(ratio => ratio >= 3), ratios, reason: ratios.every(ratio => ratio >= 3) ? null : 'Outline contrast below 3:1' };
}

// Serialized into the page by locator.evaluate. Read-only: never focuses, scrolls,
// changes styles or substitutes a shadow/ring for the required actual outline.
export function captureFocusPaint(element: Element) {
  const rect = element.getBoundingClientRect(), style = getComputedStyle(element), scroller = element.closest('.comparison-scroll');
  const bounds = scroller?.getBoundingClientRect(), width = parseFloat(style.outlineWidth), offset = parseFloat(style.outlineOffset);
  const extent = width + Math.max(0, offset), distance = Math.max(0, offset) + width / 2;
  const top = visualViewport?.offsetTop ?? 0, bottom = top + (visualViewport?.height ?? innerHeight);
  const points = [[rect.left - distance, (rect.top + rect.bottom) / 2], [rect.right + distance, (rect.top + rect.bottom) / 2],
    [(rect.left + rect.right) / 2, rect.top - distance], [(rect.left + rect.right) / 2, rect.bottom + distance]];
  const surfaces = points.map(([x, y]) => {
    const layers: { tag: string; color: string; image: string }[] = [], unsupported: string[] = [];
    if (offset < 0) unsupported.push('Inset outline requires a different paint model');
    if (style.boxShadow !== 'none') unsupported.push('Target shadow/ring paint is not resolved');
    if (style.opacity !== '1' || style.filter !== 'none') unsupported.push('Target outline compositing is not resolved');
    let node = document.elementFromPoint(x, y), opaque = false, depth = 0;
    if (!node || node === element || element.contains(node)) unsupported.push('Adjacent paint sample is not outside the control');
    while (node && depth++ < 64) {
      const paint = getComputedStyle(node);
      if (paint.opacity !== '1' || paint.filter !== 'none' || paint.mixBlendMode !== 'normal'
          || paint.backdropFilter !== 'none') unsupported.push('Composited adjacent surface is not resolved');
      if (!opaque) {
        if (paint.backgroundImage !== 'none') unsupported.push('Adjacent background image is not resolved');
        layers.push({ tag: node.tagName, color: paint.backgroundColor, image: paint.backgroundImage });
        opaque = /^rgb\([^/]*\)$/.test(paint.backgroundColor) || /^rgba\([^,]+,[^,]+,[^,]+,\s*1\)$/.test(paint.backgroundColor);
      }
      node = node.parentElement;
    }
    if (node) unsupported.push('Adjacent ancestor bound exceeded');
    return { x, y, layers, unsupported };
  });
  return { label: `${element.tagName} ${element.textContent?.slice(0, 160) ?? ''}`, visible: element.matches(':focus-visible'),
    outline: style.outlineStyle, width, offset, outlineColor: style.outlineColor, backgroundColor: style.backgroundColor,
    boxShadow: style.boxShadow, filter: style.filter, opacity: style.opacity, extent, surfaces,
    rect: { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom },
    clip: { left: Math.max(0, bounds ? bounds.left + scroller!.clientLeft : 0),
      right: Math.min(innerWidth, bounds ? bounds.left + scroller!.clientLeft + scroller!.clientWidth : innerWidth), top, bottom } };
}
const fixedRevenue: Record<number, string> = { 2025: '5000000000', 2024: '4000000000', 2023: '2000000000' };

// Synthetic protocol inputs only. No finance formula, upstream or production data.
export function annualPeriods(ticker: string, year: number | null): AnnualFinancialComparison {
  const issuer = data.company(ticker);
  if (year !== null && !annualYears.includes(year)) throw new Error('Undeclared synthetic annual year');
  const result: AnnualFinancialComparison = { ticker, company_name: issuer.name, company_cik: issuer.cik,
    requested_period: 'annual', requested_fiscal_year: year, fiscal_years: [...annualYears], period: null,
    period_reason: null, metrics: {}, selection_policy: 'Test-local fixed annual responses; no production data.' };
  if (year === null) return result;
  const missing = year === 2022;
  const period = missing ? null : data.period('annual', year);
  result.period = period; result.period_reason = missing ? missingAnnualReason : null;
  for (const [index, metric] of data.annualMetrics.entries()) {
    const ratio = ['revenue_growth_yoy', 'operating_margin', 'net_margin', 'gross_margin'].includes(metric);
    const value = metric === 'revenue' ? fixedRevenue[year] : metric === 'net_income' ? '-40000000' : '3000000';
    const excluded = metric === 'gross_margin' && year === 2023;
    const point: NormalizedMetric = { metric, unit: ratio ? 'ratio' : 'USD',
      status: excluded ? 'not_applicable' : missing || ratio ? 'unavailable' : 'available',
      value: missing || ratio ? null : value, period, formula: null,
      reason: missing ? missingAnnualReason : excluded ? 'Synthetic industry exclusion; retain this reason.'
        : ratio ? 'Synthetic compatible ratio inputs unavailable.' : null,
      inputs: [], alternatives: [], provenance: [], ...(metric === 'revenue' ? { revenue_basis: 'total_revenue' } : {}) };
    if (point.status === 'available') point.provenance = [{ fact_id: issuer.id * 10000 + year * 100 + index,
      original_concept: `Synthetic_${metric}`, value, unit: 'USD', company_cik: issuer.cik,
      period_start: period!.start, period_end: period!.end, form: '10-K', filed: '2026-02-01',
      accession_number: data.accession(ticker), sec_url: data.secUrl(ticker),
      source_fiscal_year: year, source_fiscal_period: 'FY' }];
    result.metrics[metric] = point;
  }
  if (year === 2025 || year === 2024) {
    const prior = annualPeriods(ticker, year - 1), revenue = result.metrics.revenue;
    Object.assign(result.metrics.revenue_growth_yoy, { status: 'available', value: year === 2025 ? '0.25' : '1',
      reason: null, formula: '(current - prior) / prior', revenue_basis: 'total_revenue',
      provenance: [structuredClone(revenue.provenance[0]), structuredClone(prior.metrics.revenue.provenance[0])],
      inputs: [result, prior].map((response, index) => ({ role: index ? 'prior' : 'current', metric: 'revenue',
        value: response.metrics.revenue.value!, unit: 'USD', period: structuredClone(response.period!),
        fact_ids: [response.metrics.revenue.provenance[0].fact_id], revenue_basis: 'total_revenue' })) });
  }
  return result;
}

export function validateAnnualRequest(request: ApiRequest, scenario: Pick<Scenario, 'versions'>): void {
  const { ticker, method, body, path, pin, query } = request;
  if (!ticker || !['AAA', 'BBB'].includes(ticker) || method !== 'GET' || body !== null
      || path !== `/companies/${ticker}/financials/annual`
      || (query.size !== 0 && !(query.size === 1 && [...query.keys()][0] === 'fiscal_year'
        && annualYears.some(year => String(year) === query.get('fiscal_year'))))
      || pin === undefined || !/^(0|[1-9]\d*)$/.test(pin) || !Number.isSafeInteger(Number(pin))
      || Number(pin) > scenario.versions[ticker]) throw new Error('Invalid test-local annual route, selector or pin');
}
export function annualReply(request: ApiRequest, scenario: Pick<Scenario, 'versions'>): Reply {
  validateAnnualRequest(request, scenario);
  const version = String(scenario.versions[request.ticker!]);
  return request.pin !== version ? { status: 409, code: 'DATA_VERSION_CHANGED', version }
    : { body: annualPeriods(request.ticker!, request.query.size ? Number(request.query.get('fiscal_year')) : null), version };
}
export function signature(request: Pick<ApiRequest, 'method' | 'path' | 'pin' | 'query' | 'body'>): string {
  return JSON.stringify([request.method, request.path, request.query.toString(), request.pin ?? null, request.body]);
}
export function expectedRequest(path: string, pin?: number, query = ''): string {
  return JSON.stringify(['GET', path, query, pin === undefined ? null : String(pin), null]);
}
export function publicationRequests(ticker = 'AAA', pin = 0): string[] {
  return [expectedRequest(`/companies/${ticker}/freshness`),
    expectedRequest(`/companies/${ticker}/financials/insights`, pin, 'mode=discover'),
    expectedRequest(`/companies/${ticker}/financials/annual`, pin),
    expectedRequest(`/companies/${ticker}/financials/summary`, pin, 'period=quarter'),
    expectedRequest(`/companies/${ticker}/financials/metrics/revenue`, pin, 'period=quarter&limit=12'),
    expectedRequest(`/companies/${ticker}/sources`, pin)];
}
export const selectedRequests = (selected: number[], ticker = 'AAA', pin = 0) => selected.map(year =>
  expectedRequest(`/companies/${ticker}/financials/annual`, pin, `fiscal_year=${year}`));
type Receipt = { status: number; version: string | null; code: string | null };
type Completion = Receipt & { request: string };
export type ExpectedLedger = { completed: Completion[]; cancelled: string[]; pending: string[]; cancelledAfterHeaders: Completion[] };
// A response event proves receipt of headers, never completion of its body.
type Outcome = { id: number; state: 'pending' | 'completed' | 'cancelled' | 'failed'; response: Receipt | null; error: string | null };
const outcomes = new WeakMap<Scenario, Map<Request, Outcome>>();
export const completedRequests = (requests: string[], status = 200, version?: string, code: string | null = null): Completion[] => requests.map(request => ({
  request, status, version: version ?? JSON.parse(request)[3], code,
}));
export const publicationCompletions = (ticker = 'AAA', pin = 0): Completion[] => publicationRequests(ticker, pin)
  .filter(request => !JSON.parse(request)[1].endsWith('/financials/insights') || supportsInsightsPublication(ticker, pin))
  .flatMap(request => completedRequests([request]));
export const publicationHeaderCancellations = (ticker = 'AAA', pin = 0): Completion[] => supportsInsightsPublication(ticker, pin) ? []
  : completedRequests([expectedRequest(`/companies/${ticker}/financials/insights`, pin, 'mode=discover')],
    503, String(pin), 'QA01_INSIGHTS_PUBLICATION_UNAVAILABLE');
export const replayCancellations = (ticker = 'AAA', pin = 0, freshness = true): string[] => [
  ...(freshness ? [expectedRequest(`/companies/${ticker}/freshness`)] : []),
  expectedRequest(`/companies/${ticker}/financials/annual`, pin),
];
function lifecycle(scenario: Scenario) {
  const records = outcomes.get(scenario)!;
  const rows = scenario.ledger.map(request => ({ request: signature(request), ...records.get(request.request) }));
  return { started: records.size, unledgered: [...records.keys()].filter(request => !scenario.ledger.some(item => item.request === request)).length,
    rows };
}
export async function expectFullLedger(scenario: Scenario, expected: ExpectedLedger): Promise<void> {
  const receipt = ({ status, version, code }: Receipt): Receipt => ({ status, version, code });
  const intended = [
    ...expected.completed.map(item => JSON.stringify([item.request, 'completed', receipt(item), null])),
    ...expected.cancelledAfterHeaders.map(item => JSON.stringify([item.request, 'cancelled', receipt(item), 'net::ERR_ABORTED'])),
    ...expected.cancelled.map(request => JSON.stringify([request, 'cancelled', null, 'net::ERR_ABORTED'])),
    ...expected.pending.map(request => JSON.stringify([request, 'pending', null, null])),
  ].sort();
  await expect.poll(() => {
    const actual = lifecycle(scenario);
    return { started: actual.started, unledgered: actual.unledgered, outcomes: actual.rows.map(item => JSON.stringify([
      item.request, item.state, item.response, item.error,
    ])).sort() };
  }).toEqual({ started: intended.length, unledgered: 0, outcomes: intended });
  expect(scenario.violations).toEqual([]);
}
export function expectReplayGenerations(scenario: Scenario, since: number, ticker = 'AAA', pin = 0, freshness = true) {
  const rows = lifecycle(scenario).rows.slice(since);
  for (const request of replayCancellations(ticker, pin, freshness)) {
    const generations = rows.filter(item => item.request === request);
    expect(generations).toHaveLength(2);
    expect(generations[0].state).toBe('cancelled'); expect(generations[1].state).toBe('completed');
    expect(generations[0].id).toBeLessThan(generations[1].id!);
  }
}
export async function waitForCompletedRequest(scenario: Scenario, request: string) {
  await expect.poll(() => lifecycle(scenario).rows.filter(item => item.request === request && item.state === 'completed')
    .map(item => item.response?.status)).toEqual([200]);
}

export const test = base.extend<{ annualScenario: Scenario }>({
  annualScenario: [async ({ context, scenario }, use, info: TestInfo) => {
    // Same actual company/freshness components, both explicit publication zero.
    // BBB0 intentionally uses the existing insights-unavailable fixture, not a
    // newly manufactured insights publication or evidence reconciliation request.
    scenario.versions.BBB = 0;
    const records = new Map<Request, Outcome>(); outcomes.set(scenario, records);
    const isApi = (request: Request) => {
      const url = new URL(request.url());
      return url.origin === 'http://127.0.0.1:3107' && url.pathname.startsWith('/api/finlens/');
    };
    const invalid = (event: string) => { scenario.violations.push(`Invalid annual lifecycle event: ${event}`); };
    const pending = (request: Request, event: string) => {
      if (!isApi(request)) return;
      const record = records.get(request);
      if (!record || record.state !== 'pending') { invalid(event); return; }
      return record;
    };
    const started = (request: Request) => {
      if (!isApi(request)) return;
      if (records.has(request)) { invalid('duplicate request'); return; }
      records.set(request, {
        id: records.size + 1, state: 'pending', response: null, error: null,
      });
    };
    const responded = (response: Response) => {
      const request = response.request(), record = pending(request, 'response without pending request');
      if (!record) return;
      if (record.response || response.url() !== request.url()) { invalid('duplicate or misassociated response'); return; }
      const headers = response.headers();
      record.response = { status: response.status(), version: headers['x-finlens-data-version'] ?? null,
        code: headers['x-finlens-error-code'] ?? null };
    };
    const finished = (request: Request) => {
      const record = pending(request, 'finish without pending request'); if (!record) return;
      if (!record.response) { invalid('finish before response headers'); return; }
      record.state = 'completed';
    };
    const failed = (request: Request) => {
      const record = pending(request, 'failure without pending request'); if (!record) return;
      const error = request.failure()?.errorText ?? 'Unknown request failure';
      Object.assign(record, { state: error === 'net::ERR_ABORTED' ? 'cancelled' : 'failed', error });
    };
    context.on('request', started); context.on('response', responded);
    context.on('requestfinished', finished); context.on('requestfailed', failed);
    await installAnnualRoute(context, scenario);
    try { await use(scenario); }
    finally {
      await info.attach('annual-period-full-page-ledger', { contentType: 'application/json', body: JSON.stringify({
        lifecycle: lifecycle(scenario), requests: scenario.ledger.map(({ method, path, pin, query, body }) => ({ method, path, pin: pin ?? null,
          query: query.toString(), body })), violations: scenario.violations, failures: scenario.failures,
      }, null, 2) });
      context.off('request', started); context.off('response', responded);
      context.off('requestfinished', finished); context.off('requestfailed', failed);
    }
  }, { auto: true }],
});

async function installAnnualRoute(context: BrowserContext, scenario: Scenario) {
  // Last-installed route handles only annual URLs, with the same strict inventory
  // and shared ledger. All other application/static/egress routes retain QA guards.
  await context.route('**/api/finlens/companies/*/financials/annual*', async route => {
    const request = route.request(), url = new URL(request.url());
    try {
      if (url.origin !== 'http://127.0.0.1:3107') throw new Error('Nonlocal annual URL');
      const item: ApiRequest = { method: request.method(), path: url.pathname.slice('/api/finlens'.length),
        ticker: url.pathname.split('/')[4], pin: request.headers()['x-finlens-data-version'], query: url.searchParams,
        body: request.postData() ? request.postDataJSON() : null, request };
      if (scenario.ledger.length >= 200) throw new Error('Full-page request budget exceeded');
      scenario.ledger.push(item); validateAnnualRequest(item, scenario);
      let reply: Reply | undefined;
      for (const override of scenario.overrides) { reply = await override(item); if (reply) break; }
      reply ??= annualReply(item, scenario);
      if (reply.abort) throw new Error('Undeclared annual network-failure injection');
      const version = reply.version === undefined ? String(scenario.versions[item.ticker!]) : reply.version;
      await route.fulfill({ status: reply.status ?? 200, contentType: 'application/json', headers: {
        ...(version === null ? {} : { 'X-FinLens-Data-Version': version }),
        ...(reply.code ? { 'X-FinLens-Error-Code': reply.code } : {}),
      }, body: JSON.stringify(reply.body ?? { detail: 'Synthetic publication mismatch' }) });
    } catch (error) {
      if (!String(error).includes('Target page, context or browser has been closed')
          && !String(error).includes('Invalid InterceptionId')) scenario.violations.push(String(error));
      await route.abort('blockedbyclient').catch(() => {});
    }
  });
}
