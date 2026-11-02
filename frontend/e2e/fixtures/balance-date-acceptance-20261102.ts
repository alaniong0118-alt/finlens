import type { TestInfo } from '@playwright/test';
import type { MetricHistory, NormalizedMetric } from '../../lib/finlens-api';
import type { ApiRequest, Reply, Scenario } from './browser';
import { expect, expectedRequest, lifecycle, replayCancellations, annualRequestCursor } from './annual-period-browser';
import * as data from './data';

// Test-only fixed protocol inputs. Not actual issuer facts or source coverage.
export const balanceMetrics = ['cash_and_equivalents', 'total_assets', 'total_liabilities'] as const;
export type BalanceBrowserMetric = typeof balanceMetrics[number];
export const balanceDates = ['2025-12-31', '2025-09-30', '2025-06-30', '2025-03-31', '2024-12-31'] as const;
export const balanceExact = {
  AAA: { cash_and_equivalents: '9007199254740993.1234567890123456789012345', total_assets: '123456.00000000000001', total_liabilities: '420.1000000000001' },
  BBB: { cash_and_equivalents: '2000000000000001.000000000000000000001', total_assets: '456789.00000000000002', total_liabilities: '840.2000000000002' },
};
export const balanceUnavailable = 'Synthetic_original_reason__v1 <em>literal</em>.';
export const balanceNotApplicable = 'Synthetic not-applicable discriminant; not a claim of industry coverage.';

export function balanceHistory(ticker: string, metric: BalanceBrowserMetric): MetricHistory {
  if (!balanceMetrics.includes(metric) || !['AAA', 'BBB'].includes(ticker)) throw new Error('Unknown synthetic balance series');
  const issuer = data.company(ticker), metricIndex = balanceMetrics.indexOf(metric);
  const history: NormalizedMetric[] = balanceDates.filter(end => metric !== 'cash_and_equivalents' || end !== '2025-09-30').map((end, index) => {
    const point = structuredClone(data.observation(ticker, metric, 'instant'));
    const value = metric === 'total_assets' && end === '2024-12-31' ? '0' : balanceExact[ticker as 'AAA' | 'BBB'][metric];
    const period = { kind: 'instant' as const, start: null, end, fiscal_year: null, fiscal_period: null, fiscal_label_basis: 'unknown' };
    const source = { ...point.provenance[0], canonical_metric: metric, fact_id: (ticker === 'AAA' ? 110000 : 210000) + metricIndex * 1000 + index,
      value, period_start: null, period_end: end, company_cik: issuer.cik };
    Object.assign(point, { period, value, provenance: [source], alternatives: [] });
    if (metric === 'total_assets' && end === '2025-09-30') Object.assign(point,
      { status: 'unavailable', value: null, reason: balanceUnavailable, provenance: [] });
    if (metric === 'total_liabilities' && end === '2025-06-30') Object.assign(point,
      { status: 'not_applicable', value: null, reason: balanceNotApplicable, provenance: [] });
    if (metric === 'cash_and_equivalents' && index === 0) point.alternatives = [{ ...source, fact_id: source.fact_id + 100,
      original_concept: 'Synthetic_alternative_cash', value: '25.000000000000001' }];
    return point;
  });
  return { ticker, company_cik: issuer.cik, metric, unit: 'USD', requested_period: 'instant', status: 'available', reason: null, history };
}

export const balancePath = (ticker: string, metric: BalanceBrowserMetric) => `/companies/${ticker}/financials/metrics/${metric}`;
export function balanceMetric(request: ApiRequest): BalanceBrowserMetric | null {
  const metric = request.path.split('/').at(-1);
  return balanceMetrics.includes(metric as BalanceBrowserMetric) && request.path === balancePath(request.ticker ?? '', metric as BalanceBrowserMetric)
    ? metric as BalanceBrowserMetric : null;
}
export function balanceReply(request: ApiRequest, scenario: Pick<Scenario, 'versions'>): Reply | undefined {
  const metric = balanceMetric(request);
  if (!metric) return;
  if (!request.ticker || !['AAA', 'BBB'].includes(request.ticker) || request.method !== 'GET' || request.body !== null
      || request.request.postData() !== null || request.query.toString() !== 'period=instant&limit=12'
      || request.pin === undefined || !/^(0|[1-9]\d*)$/.test(request.pin) || !Number.isSafeInteger(Number(request.pin))) {
    throw new Error('Unexpected synthetic balance request');
  }
  const version = String(scenario.versions[request.ticker]);
  return request.pin === version ? { body: balanceHistory(request.ticker, metric), version }
    : { status: 409, code: 'DATA_VERSION_CHANGED', version };
}

type Completion = { request: string; status: number; version: string; code: string | null };
export function completedBalance(ticker = 'AAA', pin = 0, overrides: Partial<Record<BalanceBrowserMetric,
  Partial<Pick<Completion, 'status' | 'version' | 'code'>>>> = {}): Completion[] {
  return balanceMetrics.map(metric => ({ request: expectedRequest(balancePath(ticker, metric), pin, 'period=instant&limit=12'),
    status: 200, version: String(pin), code: null, ...overrides[metric] }));
}
export function balanceLifecycle(scenario: Scenario) {
  const snapshot = lifecycle(scenario, [...replayCancellations('AAA', 0), ...replayCancellations('BBB', 0)]);
  return { ...snapshot, rows: snapshot.rows.filter(row => /^\/companies\/(AAA|BBB)\/financials\/metrics\/(cash_and_equivalents|total_assets|total_liabilities)$/.test(JSON.parse(row.request)[1])) };
}
export async function expectBalanceLedger(scenario: Scenario, expected: Completion[]) {
  await expect.poll(() => {
    const snapshot = balanceLifecycle(scenario);
    return { bindingErrors: snapshot.bindingErrors, rejectedUnbound: snapshot.rejectedUnbound,
      rows: snapshot.rows.map(row => JSON.stringify([row.request, row.origin, row.bodyAbsent, row.routed, row.state,
        row.response, row.error])).sort() };
  }).toEqual({ bindingErrors: [], rejectedUnbound: [], rows: expected.map(item => JSON.stringify([item.request,
    'http://127.0.0.1:3107', true, true, 'completed', { status: item.status, version: item.version, code: item.code }, null])).sort() });
  expect(scenario.violations).toEqual([]);
}
// Capture every API owner, not only the three expected balance paths. Only an
// explicitly declared held request may remain pending at a load boundary.
export async function balanceLoadCursor(scenario: Scenario, held: string[] = []): Promise<number> {
  await expect.poll(() => lifecycle(scenario, [...replayCancellations('AAA', 0), ...replayCancellations('BBB', 0)])
    .rows.filter(row => row.state === 'pending').map(row => row.request).sort()).toEqual([...held].sort());
  return annualRequestCursor(scenario);
}
export function expectThreeBalanceRequests(scenario: Scenario, cursor: number) {
  const snapshot = balanceLifecycle(scenario);
  expect(snapshot.started - cursor, 'Exactly three total API starts per explicit load').toBe(3);
  expect(snapshot.rows.filter(row => row.id > cursor)).toHaveLength(3);
}
export async function attachBalanceAudit(scenario: Scenario, info: TestInfo) {
  const snapshot = balanceLifecycle(scenario), body = JSON.stringify({ synthetic: true, requestLimit: 200,
    bindingErrors: snapshot.bindingErrors, rejectedUnbound: snapshot.rejectedUnbound, rows: snapshot.rows, violations: scenario.violations });
  expect(Buffer.byteLength(body)).toBeLessThanOrEqual(32768);
  await info.attach('balance-date-request-audit', { body, contentType: 'application/json' });
}

// The existing quarter spec's inset focus oracle is appended unchanged below.
// It is file-local there; keeping this copy here avoids editing frozen/shared
// files or importing a spec (which would register its tests a second time).
export function captureBalanceFocus(element: Element) {
  const r = element.getBoundingClientRect(), style = getComputedStyle(element);
  const width = parseFloat(style.outlineWidth), offset = parseFloat(style.outlineOffset);
  const ancestors = [], unsupported: string[] = [];
  let node: Element | null = element, depth = 0;
  while (node && depth++ < 32) {
    const s = getComputedStyle(node), box = node.getBoundingClientRect();
    if (s.opacity !== '1' || s.filter !== 'none' || s.mixBlendMode !== 'normal') unsupported.push('Unsupported composite paint');
    if (node !== element && (s.overflowX !== 'visible' || s.overflowY !== 'visible')) ancestors.push({
      left: box.left + node.clientLeft, right: box.left + node.clientLeft + node.clientWidth,
      top: box.top + node.clientTop, bottom: box.top + node.clientTop + node.clientHeight,
      x: s.overflowX !== 'visible', y: s.overflowY !== 'visible' });
    if (s.clipPath !== 'none' || /paint|strict|content/.test(s.contain)) unsupported.push('Unsupported paint clipping');
    node = node.parentElement;
  }
  if (node) unsupported.push('Ancestor bound exceeded');
  const visibleTop = Math.max(0, r.top), visibleBottom = Math.min(innerHeight, r.bottom);
  const visibleHeight = Math.max(0, visibleBottom - visibleTop), distance = offset + width / 2;
  // Probe two visible positions on each actual side-outline segment. A tall
  // region's offscreen center cannot establish its visible perimeter exposure.
  const points = [r.left - distance, r.right + distance].flatMap(x => [0.25, 0.75]
    .map(fraction => ({ x, y: visibleTop + visibleHeight * fraction })));
  const surfaces = points.map(point => {
    const hit = document.elementFromPoint(point.x, point.y);
    const exposed = !!hit && (hit === element || element.contains(hit));
    const layers: { color: string }[] = [], issues = [...unsupported];
    let paint = hit, paintDepth = 0, opaque = false;
    while (paint && paintDepth++ < 32) {
      const s = getComputedStyle(paint);
      if (s.opacity !== '1' || s.filter !== 'none' || s.mixBlendMode !== 'normal') issues.push('Unsupported sampled composite paint');
      if (!opaque) {
        if (s.backgroundImage !== 'none') issues.push('Unsupported sampled background image');
        layers.push({ color: s.backgroundColor });
        opaque = /^rgb\([^/]*\)$/.test(s.backgroundColor) || /^rgba\([^,]+,[^,]+,[^,]+,\s*1\)$/.test(s.backgroundColor);
      }
      paint = paint.parentElement;
    }
    if (paint) issues.push('Sampled ancestor bound exceeded');
    if (!exposed) issues.push('Visible side-outline sample is occluded');
    return { ...point, exposed, layers, unsupported: issues };
  });
  const center = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
  return { rect: { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height },
    viewport: { width: innerWidth, height: innerHeight }, dpr: devicePixelRatio,
    width, offset, extent: Math.max(0, width + offset), outline: style.outlineStyle, outlineColor: style.outlineColor,
    visible: element.matches(':focus-visible'), hit: !!center && (center === element || element.contains(center)),
    ancestors, surfaces, visibleHeight,
    pageWidth: document.documentElement.scrollWidth };
}
