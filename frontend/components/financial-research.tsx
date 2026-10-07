"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { describeApiError, getFinancialSummary, getMetricHistory, type Company, type FinancialSummary,
  type MetricHistory, type NormalizedMetric, type PeriodKind } from "@/lib/finlens-api";
import { epsWarning, formatDate, formatMetric, historyChartRows, METRIC_LABELS, officialSecUrl,
  periodLabel, PERIOD_LABELS, SNAPSHOT_METRICS } from "@/lib/research";

export function MetricProvenance({ point }: { point: NormalizedMetric }) {
  return <details className="provenance"><summary>Sources and details</summary>
    <div className="details-body">
      <p>{periodLabel(point.period)}</p>
      {point.value !== null && <p>Exact API value: <span className="mono">{point.value} {point.unit}</span></p>}
      {point.reason && <p>{point.reason.replaceAll("_", " ")}</p>}
      {point.formula && <p>Calculation: <span className="mono">{point.formula}</span></p>}
      {point.revenue_basis && <p>Revenue basis: {point.revenue_basis.replaceAll("_", " ")}</p>}
      {point.inputs.map((input) => <p key={input.role}>{input.role.replaceAll("_", " ")}: {input.value} {input.unit}{input.revenue_basis ? ` · ${input.revenue_basis.replaceAll("_", " ")}` : ""}</p>)}
      {point.provenance.length === 0 && <p>No compatible source selected for this period.</p>}
      {point.provenance.map((source) => <div className="source-record" key={source.fact_id}>
        <p className="wrap-anywhere"><strong>{source.original_concept}</strong></p>
        <p>{source.period_start ? `${formatDate(source.period_start)} – ` : "As of "}{formatDate(source.period_end)}</p>
        <p>{source.form} · Filed {formatDate(source.filed)}</p>
        <p className="mono wrap-anywhere">Accession {source.accession_number} · Fact {source.fact_id}</p>
        <p>Source filing context: {source.source_fiscal_year ?? "Year unknown"} / {source.source_fiscal_period ?? "Period unknown"} (may describe a comparative filing).</p>
        {officialSecUrl(source.sec_url) && <a href={officialSecUrl(source.sec_url)} target="_blank" rel="noopener noreferrer">Open official SEC filing ↗</a>}
      </div>)}
      {point.alternatives.length > 0 && <details><summary>{point.alternatives.length} alternative source observations</summary>
        {point.alternatives.map((source) => <p key={source.fact_id} className="source-record wrap-anywhere">{source.original_concept} · {source.value} {source.unit} · {source.form} · Filed {formatDate(source.filed)} · {source.accession_number}{officialSecUrl(source.sec_url) && <> · <a href={officialSecUrl(source.sec_url)} target="_blank" rel="noopener noreferrer">SEC source ↗</a></>}</p>)}
      </details>}
    </div>
  </details>;
}

export function MetricCard({ point }: { point: NormalizedMetric }) {
  return <article className="metric-card">
    <h3>{METRIC_LABELS[point.metric] ?? point.metric}</h3>
    <p className={`metric-value ${point.status !== "available" ? "missing-value" : ""}`}>{formatMetric(point)}</p>
    <p className="muted small">{point.unit === "ratio" ? "Ratio shown as percent" : point.unit === "USD/share" ? "USD per diluted share · reported as filed" : "USD · rounded for display"}</p>
    {point.revenue_basis && <p className="small basis-label">{point.revenue_basis.replaceAll("_", " ")} basis</p>}
    <MetricProvenance point={point} />
  </article>;
}

function HistoryView({ data }: { data: MetricHistory }) {
  const rows = historyChartRows(data);
  const warning = epsWarning(data);
  const hasValues = rows.some((row) => row.value !== null);
  const unitLabel = data.unit === "USD" ? "USD billions" : data.unit === "ratio" ? "Percent" : "USD per share";
  const scale = data.unit === "USD" ? 1e9 : data.unit === "ratio" ? 0.01 : 1;
  return <>
    {warning && <p className="notice" role="note">{warning}</p>}
    <p className="muted small">{PERIOD_LABELS[data.requested_period]} observations only · {unitLabel}. Bars are reported periods, not a continuous comparable series. Basis changes and missing observations are preserved.</p>
    {hasValues ? <>
      <div className="financial-chart" role="img" aria-label={`${METRIC_LABELS[data.metric]} by ${PERIOD_LABELS[data.requested_period].toLowerCase()}. Exact observations and sources are in the table below.`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={rows} margin={{ top: 15, right: 12, bottom: 10, left: 0 }} accessibilityLayer>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" stroke="var(--muted)" tick={{ fontSize: 11 }} tickFormatter={(value: string) => value.slice(0, 7)} minTickGap={35} />
            <YAxis stroke="var(--muted)" tick={{ fontSize: 11 }} width={54} tickFormatter={(value: number) => (value / scale).toLocaleString("en-US", { maximumFractionDigits: 1 })} />
            <Tooltip contentStyle={{ background: "var(--card)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 10 }} formatter={(value) => formatMetric({ status: "available", value: String(value), unit: data.unit })} />
            <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} maxBarSize={38} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="history-table" open><summary>Observations and SEC sources ({rows.length})</summary>
        <div className="table-scroll"><table><caption className="sr-only">{METRIC_LABELS[data.metric]} · {PERIOD_LABELS[data.requested_period]}</caption>
          <thead><tr><th scope="col">Period</th><th scope="col">Reported value</th><th scope="col">Provenance</th></tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${row.date}-${index}`}>
            <td>{periodLabel(row.point.period)}</td><td>{row.label}{row.point.revenue_basis && <span className="small muted block">{row.point.revenue_basis.replaceAll("_", " ")}</span>}</td>
            <td><MetricProvenance point={row.point} /></td>
          </tr>)}</tbody>
        </table></div>
      </details>
    </> : <div className="empty-state"><h3>No compatible history for this selection</h3><p>{data.reason?.replaceAll("_", " ") ?? "Try another metric or period. No values are substituted."}</p></div>}
  </>;
}

function MetricHistoryPanel({ company }: { company: Company }) {
  const [metric, setMetric] = useState("revenue");
  const [period, setPeriod] = useState<PeriodKind>("quarter");
  const [data, setData] = useState<MetricHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setData(null); setError(null);
    getMetricHistory(company.ticker, metric, period, controller.signal).then((result) => {
      if (!controller.signal.aborted) setData(result);
    }).catch((failure) => { if (!controller.signal.aborted) setError(describeApiError(failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [company.ticker, metric, period]);
  // Changing controls clears the previous series synchronously, before the next effect.
  return <section className="panel" aria-labelledby="history-title">
    <div className="section-heading"><div><p className="eyebrow">Historical research</p><h2 id="history-title">Reported financial trends</h2></div><span className="badge">No AI required</span></div>
    <div className="history-controls">
      <label>Metric<select value={metric} onChange={(event) => {
        const next = event.target.value;
        setData(null); setLoading(true); setMetric(next);
        if (next === "total_assets" || next === "cash_and_equivalents") setPeriod("instant");
        else if (period === "instant") setPeriod("quarter");
      }}>
        {["revenue", "net_income", "diluted_eps", "revenue_growth_yoy", "net_margin", "operating_margin", "free_cash_flow", "total_assets", "cash_and_equivalents"].map((key) => <option key={key} value={key}>{METRIC_LABELS[key]}</option>)}
      </select></label>
      <label>History period<select value={period} onChange={(event) => { setData(null); setLoading(true); setPeriod(event.target.value as PeriodKind); }}>
        {(metric === "total_assets" || metric === "cash_and_equivalents" ? ["instant"] : ["quarter", "annual", "half_year", "nine_months"]).map((kind) => <option key={kind} value={kind}>{PERIOD_LABELS[kind as PeriodKind]}</option>)}
      </select></label>
    </div>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p className="loading-state">Loading selected history…</p>}
      {error && <p role="alert" className="error-state">{error}</p>}
      {data && !loading && <HistoryView data={data} />}
    </div>
  </section>;
}

export default function FinancialResearch({ company }: { company: Company }) {
  const [period, setPeriod] = useState<PeriodKind>("quarter");
  const [summary, setSummary] = useState<FinancialSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setSummary(null); setError(null);
    getFinancialSummary(company.ticker, period, controller.signal).then((result) => {
      if (!controller.signal.aborted) setSummary(result);
    }).catch((failure) => { if (!controller.signal.aborted) setError(describeApiError(failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [company.ticker, period]);
  const available = summary ? Object.values(summary.metrics).filter((point) => point.status === "available").length : 0;
  return <div className="research-column">
    <section className="panel" aria-labelledby="snapshot-title">
      <div className="section-heading"><div><p className="eyebrow">Company research</p><h2 id="snapshot-title">Financial snapshot</h2></div>
        <label className="compact-label">Snapshot period<select value={period} onChange={(event) => { setSummary(null); setLoading(true); setPeriod(event.target.value as PeriodKind); }}><option value="quarter">Direct quarter</option><option value="annual">Annual</option></select></label>
      </div>
      <div aria-live="polite" aria-busy={loading}>
        {loading && <p className="loading-state">Loading financial snapshot…</p>}
        {error && <p role="alert" className="error-state">{error}</p>}
        {summary && !loading && <>
          <p className="period-label">{periodLabel(summary.period)}</p>
          <p className="muted small availability">Financial data: {available ? `${available} of ${Object.keys(summary.metrics).length} metrics available for this snapshot` : "No compatible metrics for this period"}. This snapshot is separate from the selected SEC research filing.</p>
          <div className="metric-grid">{SNAPSHOT_METRICS.map((key) => summary.metrics[key] && <MetricCard key={key} point={summary.metrics[key]} />)}</div>
          <details className="secondary-metrics"><summary>Balance sheet and cash flow</summary><div className="metric-grid">{["total_assets", "cash_and_equivalents", "free_cash_flow"].map((key) => summary.metrics[key] && <MetricCard key={key} point={summary.metrics[key]} />)}</div></details>
        </>}
      </div>
    </section>
    <MetricHistoryPanel company={company} />
  </div>;
}
