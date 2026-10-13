"use client";
import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { describeApiError, FinLensApiError, versionedController, getFinancialSummary, getMetricHistory, type Company, type FinancialSummary,
  type MetricHistory, type NormalizedMetric, type PeriodKind } from "@/lib/finlens-api";
import { epsWarning, formatDate, formatMetric, historyChartRows, METRIC_LABELS, officialSecUrl,
  periodLabel, PERIOD_LABELS, SNAPSHOT_METRICS, METRIC_CATALOG, METRIC_GROUPS } from "@/lib/research";

import { useResearchVersion } from "@/components/research-freshness";

const CASH_FLOW_METRICS = ["operating_cash_flow", "capital_expenditures", "free_cash_flow"];
const ALTERNATIVE_PERIODS: PeriodKind[] = ["half_year", "nine_months", "annual"];
type SnapshotScope = {
  ticker: string; cik: string; version: number; controller: AbortController;
  changed: () => void;
  responses: Map<PeriodKind, { response: Promise<FinancialSummary>; controller: AbortController; settled: boolean }>;
};
function snapshotFor(scope: SnapshotScope, period: PeriodKind) {
  let entry = scope.responses.get(period);
  if (!entry) {
    const controller = versionedController(scope.version, scope.changed);
    scope.controller.signal.addEventListener("abort", () => controller.abort(), { once: true });
    const created = { controller, settled: false, response: getFinancialSummary(scope.ticker, period, controller.signal, true).then(result => {
      if (controller.signal.aborted) throw new DOMException("Request cancelled", "AbortError");
      if (result.ticker !== scope.ticker || result.company_cik !== scope.cik || result.requested_period !== period) {
        throw new Error("Financial snapshot does not match this company and period.");
      }
      return result;
    }).catch(failure => {
      // A cancelled older request must not evict its replacement for this period.
      if (scope.responses.get(period) === created) scope.responses.delete(period);
      throw failure;
    }).finally(() => { created.settled = true; }) };
    entry = created;
    scope.responses.set(period, entry);
  }
  return entry.response;
}

export function MetricProvenance({ point, summary = "Sources and details" }: { point: NormalizedMetric; summary?: string }) {
  return <details className="provenance"><summary>{summary}</summary>
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
    <p className="small muted metric-description">{METRIC_CATALOG.find(metric => metric.id === point.metric)?.description}</p>
    <p className="small metric-period">{periodLabel(point.period)}</p>
    {point.status !== "available" && <p className="small metric-reason">{point.reason ?? "No compatible observation returned for this selection."}</p>}
    <p className="muted small">{point.unit === "ratio" ? "Ratio shown as percent" : point.unit === "USD/share" ? "USD per diluted share · reported as filed" : "USD · rounded for display"}</p>
    {point.revenue_basis && <p className="small basis-label">{point.revenue_basis.replaceAll("_", " ")} basis</p>}
    <MetricProvenance point={point} />
  </article>;
}

function SnapshotMetric({ metric, point }: { metric: string; point: NormalizedMetric | undefined }) {
  if (point?.metric === metric) return <MetricCard point={point} />;
  return <article className="metric-card"><h3>{METRIC_LABELS[metric]}</h3>
    <p className="small muted metric-description">{METRIC_CATALOG.find(item => item.id === metric)?.description}</p>
    <p className="missing-value">Status unavailable</p><p className="small">This metric was not returned for this selection.</p>
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
    <p className="muted small">{PERIOD_LABELS[data.requested_period]} observations only · {unitLabel}. {data.requested_period === "instant" ? "Bars are values as of each date." : "Bars are reported intervals, not a continuous comparable series."} Basis changes and missing observations are preserved.</p>
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
        <p className="small muted table-scroll-help" id="history-scroll-help">On narrow screens, scroll horizontally to read values and sources. Keyboard users can focus the table region and use the arrow keys.</p>
        <div className="table-scroll" tabIndex={0} role="region" aria-label={`${METRIC_LABELS[data.metric]} historical observations and SEC sources`} aria-describedby="history-scroll-help"><table><caption className="sr-only">{METRIC_LABELS[data.metric]} · {PERIOD_LABELS[data.requested_period]}</caption>
          <thead><tr><th scope="col">Period</th><th scope="col">Reported value</th><th scope="col">Provenance</th></tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${row.date}-${index}`}>
            <td>{periodLabel(row.point.period)}</td><td>{row.label}{row.point.status !== "available" && row.point.reason && <p className="small metric-reason">{row.point.reason}</p>}{row.point.revenue_basis && <span className="small muted block">{row.point.revenue_basis.replaceAll("_", " ")}</span>}</td>
            <td><MetricProvenance point={row.point} /></td>
          </tr>)}</tbody>
        </table></div>
      </details>
    </> : <div className="empty-state"><h3>{data.status === "not_applicable" ? `${METRIC_LABELS[data.metric]} is not applicable` : "No compatible history for this selection"}</h3><p>{data.reason ?? "Try another metric or period. No values are substituted."}</p></div>}
  </>;
}

function MetricHistoryPanel({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [loadedVersion, setLoadedVersion] = useState(-1);
  const [metric, setMetric] = useState("revenue");
  const [period, setPeriod] = useState<PeriodKind>("quarter");
  const [data, setData] = useState<MetricHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const presentation = METRIC_CATALOG.find(item => item.id === metric)!;
  useEffect(() => {
    setLoading(true); setData(null); setError(null);
    if (version === null) return;
    const controller = versionedController(version, changed);
    getMetricHistory(company.ticker, metric, period, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      if (result.ticker !== company.ticker || result.company_cik !== company.cik || result.metric !== metric || result.requested_period !== period) {
        throw new Error("Financial history does not match this company, metric and period.");
      }
      if (!controller.signal.aborted) { setData(result); setLoadedVersion(version); }
    }).catch((failure) => { if (!controller.signal.aborted) setError(describeApiError(failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [company.ticker, company.cik, metric, period, version, changed]);
  // Changing controls clears the previous series synchronously, before the next effect.
  return <section className="panel" aria-labelledby="history-title">
    <div className="section-heading"><div><p className="eyebrow">Historical research</p><h2 id="history-title">Reported financial trends</h2></div><span className="badge">No AI required</span></div>
    <div className="history-controls">
      <label>Metric<select value={metric} onChange={(event) => {
        const next = event.target.value;
        setData(null); setLoading(true); setMetric(next);
        const periods = METRIC_CATALOG.find(item => item.id === next)!.periods;
        if (!periods.includes(period)) setPeriod(periods[0]);
      }}>
        {METRIC_GROUPS.map(group => <optgroup key={group.id} label={group.label}>{METRIC_CATALOG.filter(item => item.group === group.id).map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</optgroup>)}
      </select></label>
      <label>History period<select value={period} onChange={(event) => { setData(null); setLoading(true); setPeriod(event.target.value as PeriodKind); }}>
        {presentation.periods.map(kind => <option key={kind} value={kind}>{PERIOD_LABELS[kind]}</option>)}
      </select></label>
    </div>
    <p className="small muted metric-description">{presentation.description} {presentation.periods[0] === "instant" ? "Balance-sheet observations are values as of a date." : "Choose the reporting interval; annual and YTD values are not substituted for direct quarters."} History availability is checked separately from the snapshot.</p>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p className="loading-state">{version === null ? "Waiting for publication version…" : "Loading selected history…"}</p>}
      {error && <p role="alert" className="error-state">{error}</p>}
      {data && !loading && loadedVersion === version && <HistoryView data={data} />}
    </div>
  </section>;
}

export default function FinancialResearch({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [loadedVersion, setLoadedVersion] = useState(-1);
  const [period, setPeriod] = useState<PeriodKind>("quarter");
  const [summary, setSummary] = useState<FinancialSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [snapshotAttempt, setSnapshotAttempt] = useState(0);
  const snapshotPending = useRef(false);
  const scope = useRef<SnapshotScope | null>(null);
  const [alternatives, setAlternatives] = useState<{ ticker: string; version: number; hints: { metric: string; snapshot: FinancialSummary }[] } | null>(null);
  useEffect(() => {
    scope.current = null;
    setAlternatives(null);
    if (version === null) return;
    const current: SnapshotScope = { ticker: company.ticker, cik: company.cik, version, changed,
      controller: new AbortController(), responses: new Map() };
    scope.current = current;
    return () => current.controller.abort();
  }, [company.ticker, company.cik, version, changed]);
  useEffect(() => {
    setLoading(true); setSummary(null); setError(null); setErrorCode(null);
    const current = scope.current;
    if (version === null || !current) return;
    let active = true;
    snapshotPending.current = true;
    snapshotFor(current, period).then((result) => {
      if (active && !current.controller.signal.aborted) { setSummary(result); setLoadedVersion(version); }
    }).catch((failure) => {
      if (active && !current.controller.signal.aborted) {
        setError(describeApiError(failure));
        setErrorCode(failure instanceof FinLensApiError ? failure.code : null);
      }
    }).finally(() => {
      if (active && !current.controller.signal.aborted) { snapshotPending.current = false; setLoading(false); }
    });
    return () => {
      active = false;
      snapshotPending.current = false;
      const pending = current.responses.get(period);
      if (pending && !pending.settled) { pending.controller.abort(); current.responses.delete(period); }
    };
  }, [company.ticker, company.cik, period, version, changed, snapshotAttempt]);
  function retrySnapshot() {
    if (version === null || snapshotPending.current) return;
    if (errorCode === "DATA_VERSION_CHANGED") { changed(); return; }
    snapshotPending.current = true;
    setSnapshotAttempt(attempt => attempt + 1);
  }
  useEffect(() => {
    setAlternatives(null);
    if (version === null || period !== "quarter" || !summary || loadedVersion !== version
        || summary.ticker !== company.ticker || summary.company_cik !== company.cik || summary.requested_period !== period) return;
    const missing = CASH_FLOW_METRICS.filter(metric => summary.metrics[metric]?.status === "unavailable");
    if (!missing.length) return;
    const current = scope.current!;
    let active = true;
    const hints: { metric: string; snapshot: FinancialSummary }[] = [];
    async function discover() {
      // One shared snapshot per mode, only until each missing metric has a verified alternative.
      for (const mode of ALTERNATIVE_PERIODS) {
        if (!active || current.controller.signal.aborted || hints.length === missing.length) break;
        try {
          const alternative = await snapshotFor(current, mode);
          if (!active || current.controller.signal.aborted) break;
          for (const metric of missing) {
            const point = alternative.metrics[metric];
            if (!hints.some(hint => hint.metric === metric) && point?.status === "available"
                && point.value !== null && point.value.trim() !== "" && Number.isFinite(Number(point.value))
                && point.metric === metric && point.unit === summary!.metrics[metric].unit
                && alternative.period?.kind === mode && point.period?.kind === mode
                && point.period.start === alternative.period?.start && point.period.end === alternative.period?.end) {
              hints.push({ metric, snapshot: alternative });
            }
          }
          setAlternatives({ ticker: current.ticker, version: current.version, hints: [...hints] });
        } catch { /* An unverified alternative never replaces the quarterly unavailable state. */ }
      }
    }
    void discover();
    return () => { active = false; };
  }, [company.ticker, company.cik, period, summary, loadedVersion, version]);
  const available = summary ? Object.values(summary.metrics).filter((point) => point.status === "available").length : 0;
  return <div className="research-column">
    <section className="panel" aria-labelledby="snapshot-title">
      <div className="section-heading"><div><p className="eyebrow">Company research</p><h2 id="snapshot-title">Financial snapshot</h2></div>
        <label className="compact-label">Snapshot period<select value={period} onChange={(event) => { setSummary(null); setAlternatives(null); setLoading(true); setPeriod(event.target.value as PeriodKind); }}>{["quarter", ...ALTERNATIVE_PERIODS].map(mode => <option key={mode} value={mode}>{PERIOD_LABELS[mode as PeriodKind]}</option>)}</select></label>
      </div>
      <div aria-live="polite" aria-busy={loading}>
        {loading && <p className="loading-state">{version === null ? "Waiting for publication version…" : "Loading financial snapshot…"}</p>}
        {error && <><p role="alert" className="error-state">{error}</p>
          <button type="button" className="secondary-button" disabled={loading || version === null} onClick={retrySnapshot}>{errorCode === "DATA_VERSION_CHANGED" ? "Retry data check" : "Retry snapshot"}</button></>}
        {summary && !loading && loadedVersion === version && summary.ticker === company.ticker && summary.requested_period === period && <>
          <p className="period-label">{periodLabel(summary.period)}</p>
          <p className="muted small availability">Financial data: {available ? `${available} of ${Object.keys(summary.metrics).length} metrics available for this snapshot` : "No compatible metrics for this period"}. This snapshot is separate from the selected SEC research filing.</p>
          {period === "quarter" && alternatives?.ticker === company.ticker && alternatives.version === version && alternatives.hints.map(({ metric, snapshot }) =>
            <p className="small cash-flow-alternative" key={metric}>{METRIC_LABELS[metric]} is available for {periodLabel(snapshot.period)}. Choose {PERIOD_LABELS[snapshot.requested_period]} in Snapshot period to view it.</p>)}
          <div className="metric-grid">{SNAPSHOT_METRICS.map(key => <SnapshotMetric key={key} metric={key} point={summary.metrics[key]} />)}</div>
          {[
            { label: "More income and profitability", ids: METRIC_CATALOG.filter(item => ["income", "profitability"].includes(item.group) && !SNAPSHOT_METRICS.includes(item.id)).map(item => item.id) },
            { label: "Balance sheet · as of the reporting date", ids: METRIC_CATALOG.filter(item => item.group === "balance").map(item => item.id) },
            { label: "Cash flow · reported intervals", ids: METRIC_CATALOG.filter(item => item.group === "cash_flow").map(item => item.id) },
          ].map(group => <details className="secondary-metrics" key={group.label}><summary>{group.label}</summary><div className="metric-grid">{group.ids.map(key => <SnapshotMetric key={key} metric={key} point={summary.metrics[key]} />)}</div></details>)}
        </>}
      </div>
    </section>
    <MetricHistoryPanel company={company} />
  </div>;
}
