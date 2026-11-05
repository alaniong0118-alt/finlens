import type { ResearchAnswer, FiscalPeriodRequest } from "@/lib/finlens-api";
import { formatDate, formatMetric, PERIOD_LABELS } from "@/lib/research";
import { MetricProvenance } from "@/components/financial-research";

export default function DirectResearchAnswer({ answer, companyCik }: { answer: ResearchAnswer; companyCik?: string }) {
  if (!answer.matched) return null;
  if (answer.answer_kind === "multi_metric") {
    if (typeof answer.question !== "string" || typeof answer.ticker !== "string" ||
      !Array.isArray(answer.metrics) || answer.metrics.length < 2 || answer.metrics.length > 3 ||
      !answer.requested_period || !Number.isInteger(answer.requested_period.fiscal_year) ||
      answer.requested_period.quarter !== null || typeof answer.company_cik !== "string" ||
      !/^\d{1,10}$/.test(answer.company_cik) || answer.company_cik !== companyCik ||
      !["incompatible", "unverified"].includes(answer.window_status ?? "")) return null;
    const cik = answer.company_cik;
    const definitions: Record<string, { label: string; unit: string; kind: "annual" | "instant" }> = {
      revenue: { label: "Revenue", unit: "USD", kind: "annual" },
      gross_profit: { label: "Gross profit", unit: "USD", kind: "annual" },
      operating_income: { label: "Operating income", unit: "USD", kind: "annual" },
      net_income: { label: "Net income", unit: "USD", kind: "annual" },
      total_assets: { label: "Total assets", unit: "USD", kind: "instant" },
      total_liabilities: { label: "Total liabilities", unit: "USD", kind: "instant" },
      operating_cash_flow: { label: "Operating cash flow", unit: "USD", kind: "annual" },
      diluted_eps: { label: "Diluted EPS", unit: "USD/share", kind: "annual" },
    };
    const validChild = (item: ResearchAnswer | null): boolean => {
      if (!item || typeof item !== "object" || !item.matched || typeof item.metric !== "string" ||
        !item.metric || typeof item.metric_label !== "string" || item.ticker !== answer.ticker || item.question !== answer.question || item.answer_kind !== "historical_metric" ||
        !["available", "unavailable", "not_applicable"].includes(item.status) ||
        (item.answer_text !== null && typeof item.answer_text !== "string") ||
        (item.formatted_value !== null && typeof item.formatted_value !== "string") ||
        (item.comparability != null && (typeof item.comparability !== "object" || typeof item.comparability.reason !== "string")) ||
        item.requested_period?.fiscal_year !== answer.requested_period?.fiscal_year ||
        item.requested_period?.quarter !== null || !item.observation || item.observation.metric !== item.metric ||
        item.status !== item.observation.status) return false;
      const definition = definitions[item.metric];
      if (!Object.prototype.hasOwnProperty.call(definitions, item.metric) || !definition || item.metric_label !== definition.label || item.observation.unit !== definition.unit) return false;
      const point = item.observation;
      if ((point.value !== null && typeof point.value !== "string") || typeof point.unit !== "string" ||
        (point.formula !== null && typeof point.formula !== "string") ||
        (point.reason != null && typeof point.reason !== "string") ||
        (point.revenue_basis != null && typeof point.revenue_basis !== "string") ||
        !Array.isArray(point.provenance) || !Array.isArray(point.alternatives) || !Array.isArray(point.inputs) ||
        point.provenance.length > 10000 || point.alternatives.length > 10000 || point.inputs.length > 10000 ||
        [...point.provenance, ...point.alternatives].some(source => !source || typeof source !== "object" ||
          source.company_cik !== cik || typeof source.original_concept !== "string" ||
          typeof source.period_end !== "string" || typeof source.filed !== "string" ||
          typeof source.accession_number !== "string" || !/^\d{10}-\d{2}-\d{6}$/.test(source.accession_number) ||
          typeof source.sec_url !== "string" || source.sec_url !== `https://www.sec.gov/Archives/edgar/data/${String(Number(cik))}/${source.accession_number.replaceAll("-", "")}/${source.accession_number}-index.html` ||
          typeof source.form !== "string" || typeof source.value !== "string" || typeof source.unit !== "string" ||
          typeof source.fact_id !== "number" || !Number.isSafeInteger(source.fact_id) ||
          (source.period_start !== null && typeof source.period_start !== "string") ||
          (source.source_fiscal_year != null && typeof source.source_fiscal_year !== "number") ||
          (source.source_fiscal_period != null && typeof source.source_fiscal_period !== "string")) ||
        point.inputs.some(input => !input || typeof input.role !== "string" || typeof input.value !== "string" ||
          typeof input.unit !== "string" || (input.revenue_basis != null && typeof input.revenue_basis !== "string"))) return false;
      const period = point.period;
      if (item.status === "available") {
        // This grammar admits only direct metrics; no derived or multi-source value.
        if (!period || period.kind !== definition.kind || point.provenance.length !== 1 || point.inputs.length !== 0 || point.formula !== null || point.value === null) return false;
        const selected = point.provenance[0];
        if (selected.canonical_metric !== item.metric || selected.value !== point.value ||
          selected.period_start !== period.start || selected.period_end !== period.end ||
          selected.unit !== (point.unit === "USD/share" ? "USD/shares" : point.unit)) return false;
      }
      if (period && (typeof period !== "object" || !["annual", "instant"].includes(period.kind) ||
        typeof period.end !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(period.end) ||
        Number(period.end.slice(0, 4)) !== answer.requested_period?.fiscal_year ||
        (period.fiscal_year !== null && (!Number.isInteger(period.fiscal_year) || period.fiscal_year !== answer.requested_period?.fiscal_year)) ||
        (period.fiscal_period !== null && typeof period.fiscal_period !== "string") ||
        (period.start !== null && (typeof period.start !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(period.start))))) return false;
      return true;
    };
    if (!answer.metrics.every(validChild) || new Set(answer.metrics.map(item => item.metric)).size !== answer.metrics.length) return null;
    return <section className="direct-answer" aria-labelledby="research-answer-title">
      <div className="section-heading"><h3 id="research-answer-title">Research Answer</h3><span className="badge">Deterministic · no AI</span></div>
      <p className="notice" role="note">{answer.window_status === "incompatible" ? "Reporting windows differ; these values are not directly comparable." : "Reporting-window comparability has not been verified."}</p>
      {answer.metrics.map(item => <div key={item.metric}>
        <h4>{item.metric_label}</h4>
        <p className={`metric-value ${item.status === "available" ? "" : "missing-value"}`}>{item.status === "available" ? `${item.observation?.value} ${item.observation?.unit}` : item.status === "not_applicable" ? "Not applicable" : "Unavailable"}</p>
        {item.status !== "available" && item.observation?.reason && <p className="answer-text">{item.observation.reason}</p>}
        {item.requested_period && <p className="small period-label">FY{item.requested_period.fiscal_year} · Fiscal period</p>}
        {item.observation?.period && <p className="small muted">{PERIOD_LABELS[item.observation.period.kind]} · {item.observation.period.start ? `${formatDate(item.observation.period.start)} – ` : "As of "}{formatDate(item.observation.period.end)}</p>}
        {item.observation?.revenue_basis && <p className="small basis-label">Revenue basis: {item.observation.revenue_basis.replaceAll("_", " ")}</p>}
        {item.comparability && <p className="notice" role="note">Reported as filed · comparability unverified. {item.comparability.reason}</p>}
        {item.observation && <MetricProvenance point={item.observation} summary={`${item.metric_label} sources and details`} />}
      </div>)}
    </section>;
  }
  if (!answer.observation && !answer.comparison) return null;
  const point = answer.observation;
  const source = point?.provenance[0];
  const comparison = answer.comparison;
  const label = (period: FiscalPeriodRequest) => `${period.quarter ? `Q${period.quarter} ` : ""}FY${period.fiscal_year}`;
  return <section className="direct-answer" aria-labelledby="research-answer-title">
    <div className="section-heading"><h3 id="research-answer-title">Research Answer</h3><span className="badge">Deterministic · no AI</span></div>
    <p className={`metric-value ${answer.status === "available" ? "" : "missing-value"}`}>{answer.formatted_value ?? (answer.status === "not_applicable" ? "Not applicable" : "Unavailable")}</p>
    <p className="answer-text">{answer.answer_text}</p>
    {answer.requested_period && !comparison && <p className="small period-label">{label(answer.requested_period)} · Fiscal period</p>}
    {point?.period && <p className="small muted">{PERIOD_LABELS[point.period.kind]} · {point.period.kind === "instant" ? "As of" : "Ended"} {formatDate(point.period.end)}{source ? ` · ${source.form} · filed ${formatDate(source.filed)}` : ""}</p>}
    {point?.revenue_basis && <p className="small basis-label">Revenue basis: {point.revenue_basis.replaceAll("_", " ")}</p>}
    {comparison && <>
      <dl className="comparison-values">
        {[{ period: comparison.earlier_period, point: comparison.earlier }, { period: comparison.later_period, point: comparison.later }].map(({ period, point: side }) => <div key={label(period)}><dt>{label(period)}</dt><dd>{formatMetric(side)}</dd>{side.revenue_basis && <p className="small muted">{side.revenue_basis.replaceAll("_", " ")} basis</p>}</div>)}
        {answer.formatted_absolute_change && <div><dt>Change</dt><dd>{answer.formatted_absolute_change}</dd></div>}
      </dl>
      {comparison.percentage_reason && <p className="small notice" role="note">{comparison.percentage_reason}</p>}
      <details className="provenance comparison-provenance"><summary>View comparison provenance</summary><div className="details-body">
        <p className="mono small wrap-anywhere">{comparison.formula}</p>
        {comparison.absolute_change !== null && <p>Exact change: {comparison.absolute_change} {comparison.earlier.unit}</p>}
        {comparison.percentage_change !== null && <p>Exact percentage-change ratio: {comparison.percentage_change}</p>}
        <MetricProvenance point={comparison.earlier} summary={`${label(comparison.earlier_period)} sources and details`} />
        <MetricProvenance point={comparison.later} summary={`${label(comparison.later_period)} sources and details`} />
      </div></details>
    </>}
    {answer.comparability && <p className="notice" role="note">Reported as filed · comparability unverified. {answer.comparability.reason}</p>}
    {point && <MetricProvenance point={point} summary="View provenance" />}
  </section>;
}
