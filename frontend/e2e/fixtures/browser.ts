import { test as base, expect, type BrowserContext, type Page, type Request } from '@playwright/test';
import * as data from './data';
import type { PeriodKind } from '../../lib/finlens-api';
import { installIgnoredAbort, type IgnoredAbortDelivery } from './ignored-abort';
import { browserFinancialInsights, supportsInsightsPublication } from './financial-insights-browser';

export { expect };
export const origin = 'http://127.0.0.1:3107';
export type ApiRequest = { method: string; path: string; ticker?: string; pin: string | undefined; query: URLSearchParams; body: unknown; request: Request };
export type Reply = { body?: unknown; status?: number; version?: string | null; code?: string; abort?: boolean };
export type Override = (request: ApiRequest) => Reply | undefined | Promise<Reply | undefined>;
export function gate() {
  let resolve!: () => void;
  const promise = new Promise<void>(done => { resolve = done; });
  return { promise, release: resolve };
}

export class Scenario {
  versions: Record<string, number> = { AAA: 0, BBB: 1 };
  overrides: Override[] = [];
  ledger: ApiRequest[] = [];
  violations: string[] = [];
  failures: string[] = [];
  private fourCompanyComparison = false;
  private gates: ReturnType<typeof gate>[] = [];
  private violate(message: string) {
    if (this.violations.length < 100) this.violations.push(message);
    else this.violations[99] = 'Violation diagnostic limit exceeded';
  }
  constructor(private context: BrowserContext, readonly page: Page) {}
  enableFourCompanyComparison() {
    if (this.ledger.length || this.fourCompanyComparison) throw new Error('Enable the comparison inventory once, before navigation');
    this.fourCompanyComparison = true;
    this.versions = { ...data.comparisonPins };
  }
  count(path: string) { return this.ledger.filter(item => item.path === path).length; }
  hold(predicate: (request: ApiRequest) => boolean, reply?: (request: ApiRequest) => Reply) {
    const barrier = gate(); this.gates.push(barrier);
    this.overrides.push(async request => {
      if (!predicate(request)) return undefined;
      await barrier.promise;
      return reply ? reply(request) : this.defaultReply(request);
    });
    return barrier;
  }
  releaseAll() { this.gates.forEach(item => item.release()); }
  // Only named ignored-abort cases use this transport seam. The real request
  // signal and all production response/lifecycle guards are left untouched.
  async ignoreTransportAbort(path: string) {
    await this.context.addInitScript(installIgnoredAbort, { path });
  }
  async abortedDeliveries(path: string, pin: string, status: number, query = '') {
    const fullPath = path.startsWith('/api/finlens/') ? path : `/api/finlens${path}`;
    return this.page.evaluate(({ fullPath, pin, status, query }) =>
      (window as unknown as { qaDeliveries: IgnoredAbortDelivery[] }).qaDeliveries.filter(item =>
        item.path === fullPath && item.query === query && item.pin === pin && item.status === status && item.signalAborted).length,
    { fullPath, pin, status, query });
  }
  async open() { await this.page.goto('/'); }
  async ready(ticker = 'AAA') {
    await expect(this.page.getByRole('combobox', { name: 'Company', exact: true })).toHaveValue(ticker);
    await expect(this.page.getByRole('region', { name: 'Financial snapshot', exact: true }).getByRole('heading', { name: 'Revenue', exact: true })).toBeVisible();
    await expect(this.page.getByRole('combobox', { name: 'Indexed SEC filing', exact: true })).toBeEnabled();
    // Settle only automatic discovery before existing tests capture request-count
    // baselines. No comparison is requested, and current-pin fixture-unavailable
    // recovery scenarios may finish with the existing explicit error UI.
    const discoveryTerminal = supportsInsightsPublication(ticker, this.versions[ticker])
      ? 'Choose Compare annual periods to request this comparison.'
      : 'Annual financial insights could not be loaded or verified. Retry explicitly.';
    await expect(this.page.getByRole('region', { name: 'Annual financial insights', exact: true }).locator('.insights-status'))
      .toHaveText(discoveryTerminal, { timeout: 35_000 });
  }
  async install() {
    await this.context.routeWebSocket('**/*', socket => {
      const url = new URL(socket.url());
      if (url.origin === origin.replace('http:', 'ws:') && url.pathname === '/_next/webpack-hmr') socket.connectToServer();
      else { this.violate(`Blocked WebSocket ${url.origin}${url.pathname}`); socket.close(); }
    });
    this.page.on('pageerror', error => this.violate(`Page error: ${error.message}`));
    this.context.on('requestfailed', request => {
      const error = request.failure()?.errorText ?? 'unknown';
      if (this.failures.length < 100) this.failures.push(`${request.method()} ${new URL(request.url()).pathname}: ${error}`);
      else this.violate('Request-failure diagnostic limit exceeded');
      // Native cancellations and deliberately injected network failures only.
      if (!error.includes('ERR_ABORTED') && !this.ledger.some(item => item.request === request && (item as ApiRequest & { injectedAbort?: boolean }).injectedAbort)) this.violate(`Unexpected request failure: ${error}`);
    });
    await this.context.route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== origin) { this.violate(`Blocked external destination ${url.origin}`); await route.abort('blockedbyclient'); return; }
      if (!url.pathname.startsWith('/api/finlens')) {
        if (request.method() === 'GET' && (url.pathname === '/' || url.pathname.startsWith('/_next/') || url.pathname === '/favicon.ico')) { await route.continue(); return; }
        this.violate(`Blocked non-application route ${url.pathname}`); await route.abort('blockedbyclient'); return;
      }
      let item: ApiRequest | undefined;
      try {
        item = { method: request.method(), path: url.pathname.slice('/api/finlens'.length), ticker: url.pathname.split('/')[4], pin: request.headers()['x-finlens-data-version'], query: url.searchParams, body: request.postData() ? request.postDataJSON() : null, request };
        if (this.ledger.length >= 200) throw new Error('API request limit exceeded (possible retry loop)');
        this.ledger.push(item);
        this.validateRequest(item);
        let reply: Reply | undefined;
        for (const override of this.overrides) { reply = await override(item); if (reply) break; }
        reply ??= this.defaultReply(item);
        if (reply.abort) { Object.assign(item, { injectedAbort: true }); await route.abort('failed'); return; }
        const version = reply.version === undefined && item.ticker ? String(this.versions[item.ticker]) : reply.version;
        await route.fulfill({ status: reply.status ?? 200, contentType: 'application/json', headers: { ...(version != null ? { 'X-FinLens-Data-Version': version } : {}), ...(reply.code ? { 'X-FinLens-Error-Code': reply.code } : {}) }, body: JSON.stringify(reply.body ?? { detail: 'Synthetic failure' }) });
      } catch (error) {
        // A late native route may already have been cancelled. Never count that
        // as proof of delivered stale responses; ignored-abort tests count delivery.
        if (!String(error).includes('Target page, context or browser has been closed') && !String(error).includes('Invalid InterceptionId')) this.violate(String(error));
        await route.abort('blockedbyclient').catch(() => {});
      }
    });
  }
  private validateRequest(item: ApiRequest) {
    const { path, method, query, pin, body, ticker } = item;
    const params = [...query.keys()].sort().join(',');
    if (path === '/companies' || path === '/capabilities') {
      if (method !== 'GET' || params || pin !== undefined || body !== null) throw new Error(`Invalid unpinned request ${path}`);
      return;
    }
    if (!ticker) throw new Error(`Unknown API route ${path}`);
    if (this.fourCompanyComparison && (ticker === 'CCC' || ticker === 'DDD')) {
      // Extra issuers have no snapshot/evidence/insights/research routes. Exact
      // identity, query and independently declared pin checks precede overrides.
      if (method !== 'GET' || body !== null) throw new Error('Invalid comparison-only request method/body');
      if (path === `/companies/${ticker}/freshness` && !params && pin === undefined) return;
      if (path === `/companies/${ticker}/financials/annual`
          && (!params || params === 'fiscal_year' && ['2025', '2024'].includes(query.get('fiscal_year')!))
          && Number.isSafeInteger(this.versions[ticker]) && this.versions[ticker] >= 0
          && pin === String(this.versions[ticker])) return;
      throw new Error(`Invalid comparison-only route, query or publication pin ${path}`);
    }
    data.company(ticker);
    const suffix = path.slice(`/companies/${ticker}/`.length);
    if (suffix === 'freshness') {
      if (method !== 'GET' || params || pin !== undefined || body !== null) throw new Error('Invalid freshness request');
      return;
    }
    if (pin === undefined || !/^(0|[1-9]\d*)$/.test(pin)) throw new Error(`Missing/invalid publication pin ${path}`);
    // Known obsolete pins are permitted as requests; server state determines 409.
    if (Number(pin) > this.versions[ticker]) throw new Error(`Invented future pin ${path}`);
    if (suffix === 'research-answer') {
      if (method !== 'POST' || params || !body || typeof body !== 'object' || Object.keys(body).join(',') !== 'question' || typeof (body as { question: unknown }).question !== 'string') throw new Error('Invalid deterministic research request');
      return;
    }
    if (method !== 'GET' || body !== null) throw new Error(`Invalid method/body ${path}`);
    if (suffix === 'financials/insights') {
      if (path !== `/companies/${ticker}/financials/insights` || !Number.isSafeInteger(Number(pin))
        || String(Number(pin)) !== pin || (item.request.postData?.() ?? null) !== null) throw new Error('Invalid insights issuer path, publication pin or body');
      if (params === 'mode' && query.get('mode') === 'discover') return;
      if (params === 'earlier_fiscal_year,later_fiscal_year,mode' && query.get('mode') === 'compare'
        && query.get('earlier_fiscal_year') === '2024' && query.get('later_fiscal_year') === '2025') return;
      throw new Error(`Invalid insights query ${query}`);
    }
    if (suffix === 'sources' && !params) return;
    if (suffix === 'financials/annual' && (!params || params === 'fiscal_year' && ['2025', '2024'].includes(query.get('fiscal_year')!))) return;
    const metric = suffix.match(/^financials\/metrics\/([^/]+)$/)?.[1];
    if (suffix === 'financials/summary' || metric) {
      const validKinds = metric && ['cash_and_equivalents', 'total_assets', 'total_liabilities'].includes(metric) ? ['instant'] : ['quarter', 'annual', 'half_year', 'nine_months'];
      if (params === (metric ? 'limit,period' : 'period') && validKinds.includes(query.get('period')!) && (!metric || data.metrics.includes(metric as typeof data.metrics[number]) && query.get('limit') === '12')) return;
    }
    if ((suffix === 'context' || suffix === `filings/${data.accession(ticker)}/context`) && params === 'limit,q' && query.get('limit') === '5' && query.get('q')?.trim()) return;
    throw new Error(`Unknown API route or parameters ${path}?${query}`);
  }
  defaultReply(item: ApiRequest): Reply {
    const { path, ticker, query, pin, body } = item;
    if (path === '/companies') return { body: this.fourCompanyComparison ? data.comparisonCompanies : data.companies };
    if (path === '/capabilities') return { body: { research_mode: true, ai_analysis_configured: false, ai_analysis_enabled: false, server_profile: 'sec_readonly' } };
    const issuer = ticker!;
    const version = this.versions[issuer];
    if (this.fourCompanyComparison && (issuer === 'CCC' || issuer === 'DDD')) {
      this.validateRequest(item);
      if (path === `/companies/${issuer}/freshness`) return { body: data.comparisonFreshness(issuer, version), version: null };
      return { body: data.comparisonAnnual(issuer, query.has('fiscal_year') ? Number(query.get('fiscal_year')) : null) };
    }
    if (path.endsWith('/freshness')) return { body: data.freshness(issuer, version), version: null };
    if (pin !== String(version)) return { status: 409, code: 'DATA_VERSION_CHANGED', version: String(version) };
    if (path === `/companies/${issuer}/financials/insights`) {
      // Existing generic recovery cases may advance publications; never manufacture
      // successful insights for versions outside the two authorized fixture inputs.
      if (!supportsInsightsPublication(issuer, version)) return { status: 503, code: 'QA01_INSIGHTS_PUBLICATION_UNAVAILABLE', version: String(version) };
      return { body: browserFinancialInsights(issuer, version, query.get('mode') as 'discover' | 'compare'), version: String(version) };
    }
    if (path.endsWith('/sources')) return { body: data.sources(issuer) };
    if (path.endsWith('/summary')) return { body: data.summary(issuer, query.get('period') as PeriodKind) };
    if (path.includes('/metrics/')) return { body: data.history(issuer, path.split('/').at(-1)!, query.get('period') as PeriodKind) };
    if (path.endsWith('/annual')) return { body: data.annual(issuer, query.has('fiscal_year') ? Number(query.get('fiscal_year')) : null) };
    if (path.endsWith('/research-answer')) return { body: data.answer(issuer, (body as { question: string }).question) };
    if (path.endsWith('/context')) return { body: data.evidence(issuer, query.get('q')!, version, path.includes('/filings/') ? data.accession(issuer) : undefined) };
    throw new Error(`No synthetic reply ${path}`);
  }
}

export const test = base.extend<{ scenario: Scenario }>({
  scenario: [async ({ context, page }, use, info) => {
    const scenario = new Scenario(context, page);
    await scenario.install();
    try { await use(scenario); }
    finally {
      if ((info.status !== info.expectedStatus || scenario.violations.length) && !page.isClosed()) {
        await page.screenshot({ timeout: 3000 }).then(body => info.attach('failure-screenshot', { body, contentType: 'image/png' })).catch(() => {});
      }
      scenario.releaseAll();
      // Close the page before removing interception: releasing a held response
      // must not trigger an unmocked follow-on request during teardown.
      await page.close();
      await context.unrouteAll({ behavior: 'wait' });
      // Test-runner-only health probe: never proxy to a financial backend. A
      // missed interception/SSR upstream request stops the owned server and must
      // fail the suite even if its UI error satisfied a negative test.
      try {
        const status = await fetch('http://127.0.0.1:3108/__qa_status', { signal: AbortSignal.timeout(2000) });
        if (!status.ok || (await status.json()).healthy !== true) scenario.violations.push('Deny-all upstream is unhealthy');
      } catch { scenario.violations.push('Owned deny-all upstream stopped or was unavailable'); }
      const diagnostics = { requests: scenario.ledger.map(({ method, path, pin, query }) => ({ method, path, pin, query: query.toString() })), failures: scenario.failures, violations: scenario.violations };
      if (info.status !== info.expectedStatus || scenario.violations.length) await info.attach('bounded-network-ledger', { body: JSON.stringify(diagnostics, null, 2), contentType: 'application/json' });
      expect(scenario.violations, 'Synthetic isolation and page errors').toEqual([]);
    }
  }, { auto: true }],
});
