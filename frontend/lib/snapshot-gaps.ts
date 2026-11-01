import { METRIC_CATALOG, officialSecUrl } from './research';
import type { NormalizedMetric, PeriodKind } from './finlens-api';

type Status = 'available' | 'unavailable' | 'not_applicable' | 'unverified';
export type SnapshotGap = { metric: string; label: string; status: Status; reason: string | null };
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const nullableText = (value: unknown) => value === null || typeof value === 'string';
const decimal = (value: unknown) => typeof value === 'string' && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value) && Number.isFinite(Number(value));
const date = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && Number.isFinite(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
function financialPeriod(value: unknown): boolean {
  if (!record(value) || !date(value.end) || !(value.fiscal_year === null || Number.isSafeInteger(value.fiscal_year))
      || !nullableText(value.fiscal_period) || typeof value.fiscal_label_basis !== 'string') return false;
  if (value.kind === 'instant') return value.start === null;
  if (!['quarter', 'annual', 'half_year', 'nine_months'].includes(String(value.kind)) || !date(value.start)) return false;
  const days = (Date.parse(value.end) - Date.parse(value.start)) / 86400000 + 1;
  return value.kind === 'quarter' ? days >= 75 && days <= 105
    : value.kind === 'half_year' ? days >= 165 && days <= 200
      : value.kind === 'nine_months' ? days >= 245 && days <= 295 : days >= 330 && days <= 390;
}
function unitFor(metric: string) {
  return ['revenue_growth_yoy', 'gross_margin', 'operating_margin', 'net_margin'].includes(metric) ? 'ratio'
    : metric === 'diluted_eps' ? 'USD/share' : 'USD';
}
function source(value: unknown, cik: string): boolean {
  return record(value) && Number.isSafeInteger(value.fact_id) && value.company_cik === cik
    && typeof value.original_concept === 'string' && decimal(value.value) && typeof value.unit === 'string'
    && (value.period_start === null || (date(value.period_start) && date(value.period_end) && value.period_start <= value.period_end)) && date(value.period_end) && date(value.filed)
    && typeof value.form === 'string' && typeof value.accession_number === 'string' && typeof value.sec_url === 'string' && !!officialSecUrl(value.sec_url)
    && (value.source_fiscal_year === null || Number.isSafeInteger(value.source_fiscal_year)) && nullableText(value.source_fiscal_period);
}
// Alternatives are display-only diagnostics, never selected inputs. Their own
// dates may be unknown or malformed; the provenance view labels them unknown.
// An untrusted URL remains text metadata and is never rendered as a link.
function diagnosticSource(value: unknown, cik: string): boolean {
  return record(value) && Number.isSafeInteger(value.fact_id) && value.company_cik === cik
    && typeof value.original_concept === 'string' && decimal(value.value) && typeof value.unit === 'string'
    && date(value.filed) && typeof value.form === 'string' && typeof value.accession_number === 'string'
    && typeof value.sec_url === 'string'
    && (value.source_fiscal_year === null || Number.isSafeInteger(value.source_fiscal_year)) && nullableText(value.source_fiscal_period);
}
export function snapshotPoint(value: unknown, metric: string, cik: string, period: PeriodKind, anchor: unknown): value is NormalizedMetric {
  if (!record(value) || value.metric !== metric || value.unit !== unitFor(metric)
      || !['available', 'unavailable', 'not_applicable'].includes(String(value.status))
      || !nullableText(value.reason) || !nullableText(value.formula)
      || !(value.revenue_basis === undefined || typeof value.revenue_basis === 'string')
      || !(value.period === null || (financialPeriod(value.period) && record(value.period)
        && record(anchor) && value.period.end === anchor.end
        && value.period.kind === (['cash_and_equivalents', 'total_assets', 'total_liabilities'].includes(metric) ? 'instant' : period)
        && (value.period.kind === 'instant' || (value.period.start === anchor.start
          && value.period.fiscal_year === anchor.fiscal_year && value.period.fiscal_period === anchor.fiscal_period))))
      || (value.status === 'available' ? !decimal(value.value) || value.period === null : value.value !== null)
      || !Array.isArray(value.provenance) || (value.status === 'available' && value.provenance.length === 0)
      || !value.provenance.every(item => source(item, cik))
      || !Array.isArray(value.alternatives) || !value.alternatives.every(item => diagnosticSource(item, cik))
      || !Array.isArray(value.inputs)) return false;
  return value.inputs.every(item => record(item) && typeof item.role === 'string' && typeof item.metric === 'string'
    && decimal(item.value) && typeof item.unit === 'string' && Array.isArray(item.fact_ids)
    && item.fact_ids.every((id: unknown) => Number.isSafeInteger(id))
    && (item.revenue_basis === undefined || typeof item.revenue_basis === 'string')
    && (item.period === undefined || financialPeriod(item.period)));
}
export function snapshotGaps(value: unknown, ticker: string, cik: string, period: PeriodKind): SnapshotGap[] | null {
  if (!record(value) || value.ticker !== ticker || value.company_cik !== cik || value.requested_period !== period
      || !record(value.metrics) || !(value.period === null || (financialPeriod(value.period)
        && record(value.period) && value.period.kind === period))) return null;
  const metrics = value.metrics;
  return METRIC_CATALOG.map(({ id, label }) => {
    const point = metrics[id];
    if (!snapshotPoint(point, id, cik, period, value.period)) return { metric: id, label, status: 'unverified', reason: null };
    return { metric: id, label, status: point.status, reason: point.reason };
  });
}
