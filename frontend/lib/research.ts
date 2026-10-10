import type { FilingContext, FinancialPeriod, MetricHistory, NormalizedMetric, PeriodKind } from "./finlens-api";

export const METRIC_LABELS: Record<string, string> = {
  revenue: "Revenue", revenue_growth_yoy: "Revenue YoY", net_income: "Net income",
  diluted_eps: "Diluted EPS", operating_income: "Operating income", net_margin: "Net margin",
  operating_margin: "Operating margin", total_assets: "Total assets",
  cash_and_equivalents: "Cash and equivalents", free_cash_flow: "Free cash flow",
  operating_cash_flow: "Operating cash flow", capital_expenditures: "Capital expenditures",
};
export const PERIOD_LABELS: Record<PeriodKind, string> = {
  quarter: "Direct quarter", annual: "Annual", half_year: "Half-year YTD",
  nine_months: "Nine-month YTD", instant: "As of date",
};
export const SNAPSHOT_METRICS = ["revenue", "revenue_growth_yoy", "net_income", "diluted_eps", "operating_income", "net_margin"];
export const AI_UNAVAILABLE = "AI analysis is currently unavailable. The SEC evidence and any direct financial answer are still available in Research Mode.";

export function formatDate(value: string | null): string {
  if (!value) return "Unknown date";
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? "Unknown date" : new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  }).format(parsed);
}
export function periodLabel(period: FinancialPeriod | null): string {
  if (!period) return "Period unavailable";
  const dates = period.start ? `${formatDate(period.start)} – ${formatDate(period.end)}` : formatDate(period.end);
  const fiscal = period.fiscal_year !== null ? ` · FY${period.fiscal_year}${period.fiscal_period ? ` ${period.fiscal_period}` : ""}` : "";
  return `${PERIOD_LABELS[period.kind]} · ${dates}${fiscal}`;
}
export function formatMetric(point: Pick<NormalizedMetric, "status" | "value" | "unit">): string {
  if (point.status !== "available" || point.value === null) return point.status === "not_applicable" ? "Not applicable" : "Unavailable";
  const value = Number(point.value);
  if (!Number.isFinite(value)) return "Unavailable";
  if (point.unit === "ratio") return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 }).format(value);
  if (point.unit === "USD/share") return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2 }).format(value);
}
export function officialSecUrl(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:" && ["www.sec.gov", "sec.gov"].includes(parsed.hostname) && !parsed.username && !parsed.password) return url;
  } catch { /* Invalid source links are not displayed. */ }
  return undefined;
}
export function historyChartRows(history: MetricHistory) {
  // Display conversion only. Financial formulas/period selection remain on the server.
  return history.history.map((point) => ({
    date: point.period?.end ?? "Unknown",
    value: point.status === "available" && point.value !== null && point.period?.kind === history.requested_period
      && Number.isFinite(Number(point.value)) ? Number(point.value) : null,
    label: formatMetric(point), point,
  }));
}
export function epsWarning(history: MetricHistory): string | null {
  return history.comparability ? "Reported as filed · comparability unverified. Split/restatement share bases may differ between periods." : null;
}
export function evidencePassages(result: FilingContext) {
  const blocks = new Map<string, string>();
  const pattern = /^\[SOURCE (source_[1-9]\d*)\]\n[\s\S]*?^text: \|-\n([\s\S]*?)^\[END SOURCE \1\](?=\n|$)/gm;
  for (const match of result.context.matchAll(pattern)) {
    if (!blocks.has(match[1])) blocks.set(match[1], match[2].replace(/\n$/, "").split("\n").map((line) => line.startsWith("  ") ? line.slice(2) : line).join("\n"));
  }
  return result.citations.flatMap((citation, index) => {
    const text = blocks.get(citation.citation_id);
    return text === undefined ? [] : [{ citation, text, rank: index + 1 }];
  });
}
export function parseTheme(value: string | null): "light" | "dark" | "system" {
  return value === "light" || value === "dark" ? value : "system";
}
export function resolveTheme(preference: string | null, systemDark: boolean): "light" | "dark" {
  const theme = parseTheme(preference);
  return theme === "system" ? systemDark ? "dark" : "light" : theme;
}
export function persistTheme(value: string, storage: Pick<Storage, "setItem">): "light" | "dark" | "system" {
  const theme = parseTheme(value);
  try { storage.setItem("finlens-theme", theme); } catch { /* Blocked storage does not block the current theme. */ }
  return theme;
}

// Monotonic scopes guard responses even when fetch cancellation arrives late.
export function createRequestScope() {
  let version = 0;
  return { start: () => ++version, invalidate: () => { version += 1; }, current: (id: number) => id === version };
}
