import type { EvidenceContext, FinancialPeriod, MetricHistory, NormalizedMetric, PeriodKind } from "./finlens-api";

export type QuestionScope = "latest_available" | "quarter" | "annual";
export const QUESTION_SCOPE_LABELS: Record<QuestionScope, string> = {
  latest_available: "Latest available", quarter: "Latest direct quarter", annual: "Latest annual",
};
export const METRIC_GROUPS = [
  { id: "income", label: "Income" }, { id: "profitability", label: "Growth and margins" },
  { id: "balance", label: "Balance sheet" }, { id: "cash_flow", label: "Cash flow" },
] as const;
type MetricPresentation = {
  id: string; label: string; description: string; group: typeof METRIC_GROUPS[number]["id"];
  periods: readonly PeriodKind[]; questionTerm: string; questionScopes: readonly QuestionScope[];
};
const durationPeriods: readonly PeriodKind[] = ["quarter", "annual", "half_year", "nine_months"];
const durationQuestions: readonly QuestionScope[] = ["latest_available", "quarter", "annual"];
const instantPeriods: readonly PeriodKind[] = ["instant"];
const instantQuestions: readonly QuestionScope[] = ["latest_available"];
// Display vocabulary only. The server owns metric definitions, calculations,
// period selection and availability; supported does not mean available here.
export const METRIC_CATALOG: readonly MetricPresentation[] = [
  { id: "revenue", label: "Revenue", description: "Reported revenue on the source economic basis.", group: "income", periods: durationPeriods, questionTerm: "revenue", questionScopes: durationQuestions },
  { id: "gross_profit", label: "Gross profit", description: "Reported gross profit for the reporting interval.", group: "income", periods: durationPeriods, questionTerm: "gross profit", questionScopes: durationQuestions },
  { id: "operating_income", label: "Operating income", description: "Profit or loss from operations.", group: "income", periods: durationPeriods, questionTerm: "operating income", questionScopes: durationQuestions },
  { id: "net_income", label: "Net income", description: "Net profit or loss for the reporting interval.", group: "income", periods: durationPeriods, questionTerm: "net income", questionScopes: durationQuestions },
  { id: "diluted_eps", label: "Diluted EPS", description: "Earnings per diluted share, reported as filed.", group: "income", periods: durationPeriods, questionTerm: "diluted eps", questionScopes: durationQuestions },
  { id: "revenue_growth_yoy", label: "Revenue YoY", description: "Revenue change from a comparable prior-year period.", group: "profitability", periods: durationPeriods, questionTerm: "revenue growth yoy", questionScopes: durationQuestions },
  { id: "gross_margin", label: "Gross margin", description: "Gross profit as a share of compatible revenue.", group: "profitability", periods: durationPeriods, questionTerm: "gross margin", questionScopes: durationQuestions },
  { id: "operating_margin", label: "Operating margin", description: "Operating income as a share of compatible revenue.", group: "profitability", periods: durationPeriods, questionTerm: "operating margin", questionScopes: durationQuestions },
  { id: "net_margin", label: "Net margin", description: "Net income as a share of compatible revenue.", group: "profitability", periods: durationPeriods, questionTerm: "net margin", questionScopes: durationQuestions },
  { id: "cash_and_equivalents", label: "Cash and equivalents", description: "Cash and cash equivalents as of the reported date.", group: "balance", periods: instantPeriods, questionTerm: "cash and equivalents", questionScopes: instantQuestions },
  { id: "total_assets", label: "Total assets", description: "Reported assets as of the reported date.", group: "balance", periods: instantPeriods, questionTerm: "total assets", questionScopes: instantQuestions },
  { id: "total_liabilities", label: "Total liabilities", description: "Reported liabilities as of the reported date.", group: "balance", periods: instantPeriods, questionTerm: "total liabilities", questionScopes: instantQuestions },
  { id: "operating_cash_flow", label: "Operating cash flow", description: "Cash provided by or used in operations.", group: "cash_flow", periods: durationPeriods, questionTerm: "operating cash flow", questionScopes: durationQuestions },
  { id: "capital_expenditures", label: "Capital expenditures", description: "Payments for property, plant and equipment; positive outflows.", group: "cash_flow", periods: durationPeriods, questionTerm: "capital expenditures", questionScopes: durationQuestions },
  { id: "free_cash_flow", label: "Free cash flow", description: "Operating cash flow after capital expenditures.", group: "cash_flow", periods: durationPeriods, questionTerm: "free cash flow", questionScopes: durationQuestions },
];
export const METRIC_LABELS: Record<string, string> = Object.fromEntries(METRIC_CATALOG.map(metric => [metric.id, metric.label]));
export function guidedQuestion(metric: string, scope: QuestionScope): string | null {
  const entry = METRIC_CATALOG.find(item => item.id === metric);
  if (!entry?.questionScopes.includes(scope)) return null;
  const wording = { latest_available: "latest available", quarter: "latest quarterly", annual: "latest annual" };
  return `What is the ${wording[scope]} ${entry.questionTerm}?`;
}
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
    if (parsed.protocol === "https:" && ["www.sec.gov", "sec.gov"].includes(parsed.hostname) && !parsed.username && !parsed.password) return parsed.href;
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
export function evidencePassages(result: EvidenceContext) {
  if ("retrieval_scope" in result) {
    // Company metadata is one JSON line. Only fully indented body lines can be
    // displayed; filename/header text must never become a source's passage.
    const passages = new Map<string, string>();
    const pattern = /^\[SOURCE (source_[1-9]\d*)\]\nmetadata: ([^\n]+)\ntext: \|-\n((?:  [^\n]*\n)*)\[END SOURCE \1\](?=\n|$)/gm;
    const identityKeys = ["company_cik", "accession_number", "filename", "chunk_id", "form", "filed", "start_char", "end_char"] as const;
    for (const match of result.context.matchAll(pattern)) {
      const citation = result.citations.find(item => item.citation_id === match[1]);
      if (!citation || citation.company_cik !== result.company_cik || passages.has(match[1])) continue;
      try {
        const metadata: unknown = JSON.parse(match[2]);
        if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) continue;
        const identity = metadata as Record<string, unknown>;
        if (Object.keys(identity).length !== identityKeys.length
            || identityKeys.some(key => identity[key] !== citation[key])
            || citation.filename.length < 1 || citation.filename.length > 255
            || /[^A-Za-z0-9_.-]/.test(citation.filename) || [".", ".."].includes(citation.filename)) continue;
        passages.set(match[1], match[3].slice(0, -1).split("\n").map(line => line.slice(2)).join("\n"));
      } catch { /* Invalid metadata never establishes a source passage. */ }
    }
    return result.citations.flatMap((citation, index) => {
      const text = passages.get(citation.citation_id);
      return text === undefined ? [] : [{ citation, text, rank: index + 1 }];
    });
  }
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
