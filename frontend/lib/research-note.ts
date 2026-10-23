import type { AnnualFinancialComparison, Company, FactProvenance, FinancialPeriod, NormalizedMetric } from "@/lib/finlens-api";
import { COMPARISON_METRICS, reportingWindowsDiffer, validateAnnualResponse } from "@/lib/company-comparison";
import { METRIC_LABELS, officialSecUrl } from "@/lib/research";

export type ResearchNoteColumn = Readonly<{
  company: Company; version: number; result: AnnualFinancialComparison;
}>;

function requireField(condition: unknown): asserts condition {
  if (!condition) throw new Error("This research note could not be prepared from the verified comparison.");
}
function text(value: unknown): asserts value is string {
  requireField(typeof value === "string" && value.trim().length > 0);
}
function optionalText(value: unknown) {
  if (value !== null && value !== undefined) text(value);
}
function decimal(value: unknown): asserts value is string {
  text(value);
  requireField(value === value.trim() && /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value));
}
function date(value: unknown) {
  text(value);
  requireField(/^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(`${value}T00:00:00Z`))
    && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value);
}
function fiscalYear(value: unknown) {
  requireField(value === null || Number.isInteger(value) && Number(value) >= 1900 && Number(value) <= 2099);
}

// Encode Markdown punctuation/whitespace as text entities; decimal punctuation
// stays literal so the original decimal string remains exact in the Markdown.
// Entities are rendered as text, not reparsed as Markdown/HTML or link syntax.
// Controls are shown visibly so they cannot hide or reorder source attribution.
function safe(value: string | number): string {
  const raw = String(value);
  if (raw === raw.trim() && /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(raw)) return raw;
  // Dots in arbitrary text are encoded too, preventing bare-domain autolinks.
  return raw.replace(/[^\p{L}\p{N} +\-]/gu, char => {
    const cp = char.codePointAt(0)!;
    return /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/u.test(char)
      ? `&#91;U+${cp.toString(16).toUpperCase().padStart(4, "0")}&#93;`
      : `&#${cp};`;
  });
}
function line(label: string, value: string | number) { return `- ${label}: ${safe(value)}`; }
function periodLines(period: FinancialPeriod | null, label: string): string[] {
  if (period === null) return [line(label, "Unavailable; no substitute period used")];
  requireField(period && typeof period === "object" && period.kind === "annual");
  date(period.start); date(period.end); fiscalYear(period.fiscal_year);
  optionalText(period.fiscal_period); text(period.fiscal_label_basis);
  return [line(label, `${period.start} to ${period.end}`), line("Period kind", period.kind),
    line("Fiscal year", period.fiscal_year ?? "Unknown"), line("Fiscal period", period.fiscal_period ?? "Unknown"),
    line("Fiscal label basis", period.fiscal_label_basis)];
}
function secMarkdownDestination(supplied: string): string | undefined {
  // Native URL parsing alone accepts relative-looking schemes and normalizes
  // Unicode/encoded hosts differently from Markdown consumers. Admit only a
  // literal lowercase HTTPS scheme and exact ASCII SEC authority, with no
  // credentials, port, trailing dot or alternative authority separators. The
  // remaining spelling is ASCII URI characters stable under CommonMark URL
  // encoding. Unusual path characters must already be percent-encoded.
  if (!/^https:\/\/(?:www\.sec\.gov|sec\.gov)(?=[/?#]|$)/.test(supplied)
      || /[^A-Za-z0-9\-._~!$&'()*+,;=:@/?#%]/.test(supplied)
      || /%(?![0-9A-Fa-f]{2})/.test(supplied)) return undefined;
  const admitted = officialSecUrl(supplied);
  if (!admitted) return undefined;
  try {
    // Escape ampersands so Markdown's single
    // character-reference pass cannot reinterpret a supplied query or fragment.
    const markdown = admitted.replace(/&/g, "&amp;");
    // Every literal '&' was escaped above. One pass therefore recovers exactly
    // the target a Markdown consumer receives, including literal entity text.
    const destination = markdown.replace(/&amp;/g, "&");
    const original = new URL(admitted);
    const final = new URL(destination, "https://research-note.invalid/notes/");
    // Check both the emitted spelling and the actual decoded target. Comparing
    // complete parsed URLs also protects path, query and fragment identity.
    if (!officialSecUrl(markdown) || !officialSecUrl(destination) || final.href !== original.href) return undefined;
    return markdown;
  } catch { return undefined; }
}
function sourceLines(source: FactProvenance, cik: string): string[] {
  requireField(source && typeof source === "object" && source.company_cik === cik
    && Number.isSafeInteger(source.fact_id) && source.fact_id > 0
    && typeof source.accession_number === "string" && /^\d{10}-\d{2}-\d{6}$/.test(source.accession_number));
  text(source.original_concept); decimal(source.value); text(source.unit); text(source.form);
  date(source.period_start); date(source.period_end); date(source.filed);
  fiscalYear(source.source_fiscal_year); optionalText(source.source_fiscal_period);
  requireField(typeof source.sec_url === "string");
  const destination = secMarkdownDestination(source.sec_url);
  return [line("Source CIK", source.company_cik), line("Fact identity", source.fact_id),
    line("Original concept", source.original_concept), line("Original source value", source.value), line("Original source unit", source.unit),
    line("Source reporting window", `${source.period_start} to ${source.period_end}`),
    line("Accession", source.accession_number), line("Form", source.form), line("Filed", source.filed),
    line("Source fiscal year", source.source_fiscal_year ?? "Unknown"), line("Source fiscal period", source.source_fiscal_period ?? "Unknown"),
    destination ? `- Official SEC filing: [Open supplied SEC link](<${destination}>)` : "- SEC link omitted: no supplied link admitted by the existing destination policy."];
}
function metricLines(point: NormalizedMetric, cik: string): string[] {
  requireField(point && ["available", "unavailable", "not_applicable"].includes(point.status));
  text(point.metric); text(point.unit); optionalText(point.reason); optionalText(point.formula); optionalText(point.revenue_basis);
  if (point.status === "available") decimal(point.value);
  else requireField(point.value === null && typeof point.reason === "string" && point.reason.trim().length > 0);
  requireField(Array.isArray(point.inputs) && Array.isArray(point.provenance) && Array.isArray(point.alternatives));
  const lines = [line("Status", { available: "Available", unavailable: "Unavailable", not_applicable: "Not applicable" }[point.status]),
    line("Exact normalized value", point.value ?? (point.status === "not_applicable" ? "Not applicable" : "Unavailable")), line("Unit", point.unit),
    ...periodLines(point.period, "Observation reporting window")];
  if (point.unit === "ratio") lines.push("- Exact ratio retained; no rounded percentage conversion.");
  if (point.reason) lines.push(line("Reason / limitation", point.reason));
  if (point.revenue_basis) lines.push(line("Revenue economic basis", point.revenue_basis));
  if (point.formula) lines.push(line("Server-supplied formula", point.formula));
  for (const [i, input] of point.inputs.entries()) {
    requireField(input && typeof input === "object");
    text(input.role); text(input.metric); decimal(input.value); text(input.unit); optionalText(input.revenue_basis);
    requireField(Array.isArray(input.fact_ids) && input.fact_ids.length > 0
      && input.fact_ids.every(id => Number.isSafeInteger(id) && id > 0)
      && input.fact_ids.every(id => point.provenance.some(source => source.fact_id === id)));
    lines.push("", `#### Formula operand ${i + 1}`, line("Role", input.role), line("Metric", input.metric),
      line("Exact operand value", input.value), line("Operand unit", input.unit), line("Source fact identities", input.fact_ids.join(", ")),
      ...periodLines(input.period ?? null, "Operand reporting window"));
    if (input.revenue_basis) lines.push(line("Operand revenue economic basis", input.revenue_basis));
  }
  lines.push("", "### Selected source observations");
  if (!point.provenance.length) lines.push("No compatible source selected for this period.");
  point.provenance.forEach((source, i) => lines.push("", `#### Selected source ${i + 1}`, ...sourceLines(source, cik)));
  lines.push("", "### Alternative source observations", "Alternatives are not the selected support for the normalized value.");
  if (!point.alternatives.length) lines.push("No alternative observations supplied.");
  point.alternatives.forEach((source, i) => lines.push("", `#### Alternative observation ${i + 1}`, ...sourceLines(source, cik)));
  return lines;
}

/** Pure export of one admitted annual row. No calculation, fetching or raw-object serialization. */
export function serializeResearchNote(metric: string, year: number, columns: readonly ResearchNoteColumn[]): string {
  requireField(COMPARISON_METRICS.some(name => name === metric) && Number.isInteger(year) && year >= 1900 && year <= 2099
    && Boolean(Array.isArray(columns)) && columns.length >= 2 && columns.length <= 4);
  const seen = new Set<string>();
  const tickers = new Set<string>();
  const sections = columns.map(({ company, version, result }) => {
    requireField(company && result && typeof company.cik === "string" && /^\d{10}$/.test(company.cik)
      && Number.isSafeInteger(version) && version >= 0 && !seen.has(company.cik) && !tickers.has(company.ticker));
    seen.add(company.cik); tickers.add(company.ticker);
    text(company.name); text(company.ticker); text(result.company_name); text(result.selection_policy);
    requireField(result.company_name === company.name);
    optionalText(result.period_reason);
    validateAnnualResponse(result, company, year);
    optionalText(result.metrics.revenue.revenue_basis);
    const point = result.metrics[metric];
    return ["", "## Company", line("Company", company.name), line("Ticker", company.ticker), line("CIK", company.cik),
      line("Requested fiscal end-year", year), line("Independent publication version", version),
      ...periodLines(result.period, "Actual annual reporting window"),
      ...(result.period_reason ? [line("Annual period limitation", result.period_reason)] : []),
      line("Source selection policy", result.selection_policy), ...metricLines(point, company.cik)];
  });
  const bases = new Set(columns.flatMap(({ result }) => {
    const point = result.metrics[metric];
    return [result.metrics.revenue.revenue_basis, point.revenue_basis, ...point.inputs.map(input => input.revenue_basis)].filter(Boolean);
  }));
  return ["# FinLens research note", line("Metric", METRIC_LABELS[metric]), line("Comparison", `Annual fiscal end-year ${year}`),
    "", "## Scope and limitations",
    "- A shared fiscal end-year does not establish equivalent accounting periods or cross-company comparability.",
    ...(reportingWindowsDiffer(columns.map(column => column.result)) ? ["- Reporting windows differ; each issuer's actual dates are retained below."] : []),
    ...(columns.some(column => column.result.period === null) ? ["- At least one requested annual window is missing or ambiguous. No other period was substituted."] : []),
    ...(bases.size > 1 ? ["- Revenue economic bases differ. Cross-company equivalence has not been established."] : []),
    "- Stored research snapshot. Data currency and completeness are not established by this note; publication versions are not freshness guarantees.",
    "- Source fiscal labels may describe later comparative filings; an original-filing or as-of series is not established.",
    "- SEC link policy checks destinations, not financial evidentiary support. Copying does not independently verify filings.",
    "- Financial selection and calculations remain server-owned. No cross-company calculation or causal explanation is added.",
    ...sections.flat(), ""].join("\n");
}
