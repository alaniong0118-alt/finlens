import type { ResearchAnswer } from "@/lib/finlens-api";
import { formatDate, PERIOD_LABELS } from "@/lib/research";
import { MetricProvenance } from "@/components/financial-research";

export default function DirectResearchAnswer({ answer }: { answer: ResearchAnswer }) {
  if (!answer.matched || !answer.observation) return null;
  const point = answer.observation;
  const source = point.provenance[0];
  return <section className="direct-answer" aria-labelledby="research-answer-title">
    <div className="section-heading"><h3 id="research-answer-title">Research Answer</h3><span className="badge">Deterministic · no AI</span></div>
    <p className={`metric-value ${answer.status === "available" ? "" : "missing-value"}`}>{answer.formatted_value ?? (answer.status === "not_applicable" ? "Not applicable" : "Unavailable")}</p>
    <p className="answer-text">{answer.answer_text}</p>
    {point.period && <p className="small muted">{PERIOD_LABELS[point.period.kind]} · {point.period.kind === "instant" ? "As of" : "Ended"} {formatDate(point.period.end)}{source ? ` · ${source.form} · filed ${formatDate(source.filed)}` : ""}</p>}
    {point.revenue_basis && <p className="small basis-label">Revenue basis: {point.revenue_basis.replaceAll("_", " ")}</p>}
    {answer.comparability && <p className="notice" role="note">Reported as filed · comparability unverified. {answer.comparability.reason}</p>}
    <MetricProvenance point={point} summary="View provenance" />
    <p className="small muted">Company: {answer.company_name} · Structured SEC financial observations. Supporting passages search the selected filing and may refer to a different period or accession.</p>
  </section>;
}
