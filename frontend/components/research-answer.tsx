import type { ResearchAnswer, FiscalPeriodRequest } from "@/lib/finlens-api";
import { formatDate, formatMetric, PERIOD_LABELS } from "@/lib/research";
import { MetricProvenance } from "@/components/financial-research";

export default function DirectResearchAnswer({ answer }: { answer: ResearchAnswer }) {
  if (!answer.matched || (!answer.observation && !answer.comparison)) return null;
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
