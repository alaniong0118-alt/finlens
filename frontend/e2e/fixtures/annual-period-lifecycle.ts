import type { Request, Response } from '@playwright/test';

type Receipt = { status: number; version: string | null; code: string | null };
type State = 'pending' | 'completed' | 'cancelled' | 'failed';
type RecordRow = { id: number; generation: number; request: string; origin: string; bodyAbsent: boolean; state: State; response: Receipt | null; error: string | null };
type Routed = { request: Request; method: string; path: string; pin: string | undefined; query: URLSearchParams; body: unknown };

export function annualSignature(request: Pick<Routed, 'method' | 'path' | 'pin' | 'query' | 'body'>): string {
  return JSON.stringify([request.method, request.path, request.query.toString(), request.pin ?? null, request.body]);
}

// Test-only recorder: observes every started request, including requests aborted
// before Playwright dispatches the corresponding route callback.
export class AnnualLifecycle {
  private readonly records = new Map<Request, RecordRow>();
  private generation = 0;
  constructor(private readonly invalid: (event: string) => void) {}
  private isApi(request: Request) {
    const url = new URL(request.url());
    return url.origin === 'http://127.0.0.1:3107' && url.pathname.startsWith('/api/finlens/');
  }
  private pending(request: Request, event: string) {
    if (!this.isApi(request)) return;
    const record = this.records.get(request);
    if (!record || record.state !== 'pending') { this.invalid(event); return; }
    return record;
  }
  started = (request: Request) => {
    const originCheck = new URL(request.url());
    if (originCheck.pathname.startsWith('/api/finlens/') && originCheck.origin !== 'http://127.0.0.1:3107') {
      this.invalid('unexpected API origin'); return;
    }
    if (!this.isApi(request)) return;
    if (this.records.has(request)) { this.invalid('duplicate request'); return; }
    const url = new URL(request.url()), raw = request.postData();
    let body: unknown = null;
    try { if (raw !== null) body = JSON.parse(raw); }
    catch { this.invalid('invalid request body'); body = raw; }
    const signature = annualSignature({ method: request.method(), path: url.pathname.slice('/api/finlens'.length),
      pin: request.headers()['x-finlens-data-version'], query: url.searchParams, body });
    this.records.set(request, { id: this.records.size + 1, generation: this.generation, request: signature, origin: url.origin, bodyAbsent: raw === null,
      state: 'pending', response: null, error: null });
  };
  responded = (response: Response) => {
    const request = response.request(), record = this.pending(request, 'response without pending request');
    if (!record) return;
    if (record.response || response.url() !== request.url()) { this.invalid('duplicate or misassociated response'); return; }
    const headers = response.headers();
    record.response = { status: response.status(), version: headers['x-finlens-data-version'] ?? null,
      code: headers['x-finlens-error-code'] ?? null };
  };
  finished = (request: Request) => {
    const record = this.pending(request, 'finish without pending request'); if (!record) return;
    if (!record.response) { this.invalid('finish before response headers'); return; }
    record.state = 'completed';
  };
  failed = (request: Request) => {
    const record = this.pending(request, 'failure without pending request'); if (!record) return;
    const error = request.failure()?.errorText ?? 'Unknown request failure';
    Object.assign(record, { state: error === 'net::ERR_ABORTED' ? 'cancelled' : 'failed', error });
  };
  cursor() { const boundary = this.records.size; this.generation++; return boundary; }
  snapshot(ledger: readonly Routed[], declaredCancellations: readonly string[]) {
    const bindingErrors: string[] = [];
    const rows = [...this.records.entries()].map(([request, record]) => {
      const matches = ledger.filter(item => item.request === request);
      if (matches.length > 1 || (matches.length === 1 && annualSignature(matches[0]) !== record.request))
        bindingErrors.push(`invalid route binding ${record.id}`);
      return { ...record, routed: matches.length === 1 };
    });
    if (ledger.some(item => !this.records.has(item.request))) bindingErrors.push('route without observed request');
    const rejectedUnbound = rows.filter(row => {
      if (row.routed) return false;
      const [method, pathname, query, pin, body] = JSON.parse(row.request);
      const peers = rows.filter(candidate => candidate.generation === row.generation && candidate.request === row.request);
      const companion = peers.find(candidate => candidate.id !== row.id);
      const freshness = /^\/companies\/(AAA|BBB)\/freshness$/.test(pathname) && pin === null;
      const annual = /^\/companies\/(AAA|BBB)\/financials\/annual$/.test(pathname)
        && typeof pin === 'string' && /^(0|[1-9]\d*)$/.test(pin);
      return !(row.origin === 'http://127.0.0.1:3107' && method === 'GET'
        && (freshness || annual) && query === '' && body === null && row.bodyAbsent
        && declaredCancellations.includes(row.request) && row.state === 'cancelled' && row.response === null
        && row.error === 'net::ERR_ABORTED' && peers.length === 2 && companion?.routed && companion.bodyAbsent
        && companion.state === 'completed' && companion.response?.status === 200
        && companion.response.version === pin && companion.response.code === null && companion.error === null);
    }).map(row => row.id);
    return { started: rows.length, rows, bindingErrors, rejectedUnbound };
  }
}
