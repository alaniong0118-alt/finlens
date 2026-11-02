"use client";
import { useEffect, useRef, useState } from "react";
import { describeApiError, FinLensApiError, getStoredCoverage, versionedController, type Company, type CoverageEndDateRange, type StoredFinancialCoverage } from "@/lib/finlens-api";
import { COMPARISON_METRICS } from "@/lib/company-comparison";
import { coverageRange, validateCoverage } from "@/lib/financial-coverage";
import { presentCoverage, type CoverageMetricFilter, type CoverageStatusFilter } from "@/lib/coverage-presentation";
import { formatDate, METRIC_LABELS } from "@/lib/research";
import { MetricProvenance, revealHistorySourceFocus } from "@/components/financial-research";
import { useResearchVersion } from "@/components/research-freshness";

export default function FinancialCoverage({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [kind, setKind] = useState<"annual" | "quarter">("annual");
  const [from, setFrom] = useState(""), [to, setTo] = useState("");
  let range: CoverageEndDateRange | null = null, rangeError = "";
  try { range = coverageRange(from, to); } catch (error) { rangeError = (error as Error).message; }
  const verified = version !== null && Number.isSafeInteger(version) && version >= 0 && !Object.is(version, -0);
  return <section className="panel company-comparison financial-coverage" aria-labelledby="coverage-title">
    <div className="section-heading"><div><p className="eyebrow">Stored evidence</p><h2 id="coverage-title">Financial coverage map</h2></div>
      <span className="small muted">Read only · 11 metrics</span></div>
    <p>{company.ticker} · {company.name}</p>
    <p className="small muted">Inspect existing reported windows before comparing. Missing compatible values do not establish missing filings or complete SEC coverage. No acquisition starts here.</p>
    <label>Coverage period type <select value={kind} onChange={event => setKind(event.target.value as "annual" | "quarter")}>
      <option value="annual">Annual durations</option><option value="quarter">Reported quarter durations</option></select></label>
    <fieldset><legend>Reported period end dates (inclusive)</legend>
      <p className="small muted">Leave both dates blank for all stored windows, or enter both to inspect a bounded range. Existing resource limits still apply.</p>
      <div className="comparison-actions"><label>Period end from <input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label>
        <label>Period end to <input type="date" value={to} onChange={event => setTo(event.target.value)} /></label></div>
    </fieldset>
    {verified && !rangeError ? <CoverageSession key={`${company.ticker}:${company.cik}:${version}:${kind}:${from}:${to}`} company={company} kind={kind} version={version!} range={range} changed={changed} />
      : <><button type="button" className="secondary-button" disabled>Load stored coverage</button><p role="status">{rangeError || "Waiting for a verified company publication."}</p></>}
  </section>;
}

function CoverageSession({ company, kind, version, range, changed }: { company: Company; kind: "annual" | "quarter"; version: number; range: CoverageEndDateRange | null; changed: () => void }) {
  const [data, setData] = useState<StoredFinancialCoverage | null>(null), [busy, setBusy] = useState(false), [invalid, setInvalid] = useState(false);
  const [metricFilter, setMetricFilter] = useState<CoverageMetricFilter>("all"), [statusFilter, setStatusFilter] = useState<CoverageStatusFilter>("all");
  const presentation = data ? presentCoverage(data, metricFilter, statusFilter) : null;
  function resetFilters() { setMetricFilter("all"); setStatusFilter("all"); }
  const [message, setMessage] = useState("Choose Load stored coverage to inspect this publication. Nothing is fetched automatically.");
  const alive = useRef(false), operation = useRef<AbortController | null>(null), changedRef = useRef(changed);
  changedRef.current = changed;
  useEffect(() => { alive.current = true; return () => { alive.current = false; operation.current?.abort(); operation.current = null; }; }, []);
  function cancel() {
    operation.current?.abort(); operation.current = null; setData(null); setBusy(false); resetFilters();
    setMessage(busy ? "Coverage request cancelled. Load explicitly to retry." : "Coverage cleared. Load explicitly to inspect again.");
  }
  async function load() {
    if (invalid || operation.current || !alive.current) return;
    const controller = versionedController(version, () => {
      if (!alive.current || operation.current !== controller || controller.signal.aborted) return;
      controller.abort(); operation.current = null; setData(null); setBusy(false); setInvalid(true);
      setMessage("Published data changed. Verify the company publication before loading coverage again."); changedRef.current();
    });
    operation.current = controller; setData(null); resetFilters(); setBusy(true); setMessage("Loading stored financial coverage…");
    const current = () => alive.current && operation.current === controller && !controller.signal.aborted;
    try {
      const response = await getStoredCoverage(company.ticker, kind, controller.signal, range);
      if (!current()) return;
      const result = validateCoverage(response, company, kind, version, range);
      setData(result); setMessage(result.window_count ? `Coverage ready: ${result.window_count} stored windows, ${result.cell_count} metric cells.`
        : "No supported stored windows were found for this metric set. This does not establish absence of filings.");
    } catch (error) {
      if (current()) { setData(null); setMessage(error instanceof FinLensApiError ? describeApiError(error) : "Stored coverage could not be verified. Load explicitly to retry."); }
    } finally { if (current()) { operation.current = null; setBusy(false); } }
  }
  return <>
    <p className="small muted">Publication version {version} · {kind === "annual" ? "Annual" : "Reported quarter"} durations · Existing stored observations only</p>
    <p className="small muted">{range ? `Reported period ends ${range.from_date} through ${range.to_date}, inclusive. Complete within this selected scope only; not complete historical coverage.` : "All supported stored period ends requested; no date filter or silent truncation."}</p>
    <div className="comparison-actions"><button type="button" className="primary-button" disabled={busy || invalid} onClick={load}>Load stored coverage</button>
      <button type="button" className="secondary-button" disabled={invalid} onClick={cancel}>{busy ? "Cancel coverage request" : "Clear coverage"}</button></div>
    <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
    {data && <><p className="small muted">Facts version {data.facts_version} · Evidence version {data.evidence_version}. Dates identify observed durations, not verified fiscal labels or historical as-of snapshots.</p>
      {presentation && <>
        <p>In these loaded windows{data.end_date_range ? ` (period ends ${data.end_date_range.from_date} through ${data.end_date_range.to_date}, inclusive)` : ""}: {data.cell_count} total cells · {presentation.totals.available} available · {presentation.totals.unavailable} unavailable · {presentation.totals.not_applicable} not applicable.</p>
        <fieldset><legend>Filter loaded coverage</legend>
          <div className="comparison-actions"><label>Metric <select style={{ scrollMargin: "8px" }} value={metricFilter} onChange={event => setMetricFilter(event.target.value as CoverageMetricFilter)}>
            <option value="all">All metrics</option>{COMPARISON_METRICS.map(metric => <option key={metric} value={metric}>{METRIC_LABELS[metric]}</option>)}</select></label>
          <label>Status <select style={{ scrollMargin: "8px" }} value={statusFilter} onChange={event => setStatusFilter(event.target.value as CoverageStatusFilter)}>
            <option value="all">All statuses</option><option value="available">Available</option><option value="unavailable">Unavailable</option><option value="not_applicable">Not applicable</option></select></label></div>
        </fieldset>
        <p role="status" aria-live="polite" aria-atomic="true">{presentation.visibleCount} matching cells in these loaded windows.</p>
        {data.columns.length > 0 && presentation.visibleCount === 0 && <p>No cells match these filters. Change the metric or status to see more.</p>}
      </>}
      {presentation && presentation.visibleCount > 0 && <>
        <p id="coverage-scroll-help" className="small muted">Scroll horizontally to inspect all metrics. Keyboard users can focus the table region and use arrow keys. Open a cell’s details for its original reason and source evidence.</p>
        <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Stored financial coverage matrix" aria-describedby="coverage-scroll-help" onFocus={revealHistorySourceFocus}>
          <table className="comparison-table"><caption>{company.ticker} · {kind} stored coverage · Publication {version}{data.end_date_range ? ` · Period ends ${data.end_date_range.from_date} through ${data.end_date_range.to_date} (inclusive)` : ""}</caption>
            <thead><tr><th scope="col">Actual reported dates</th>{presentation.metrics.map(metric => <th scope="col" key={metric}>{METRIC_LABELS[metric]}</th>)}</tr></thead>
            <tbody>{presentation.columns.map(column => {
              const dates = `${formatDate(column.window.start)} – ${formatDate(column.window.end)}`;
              return <tr key={`${column.window.start},${column.window.end}`}><th scope="row">{dates}</th>{presentation.metrics.map(metric => {
                const point = column.metrics[metric];
                if (statusFilter !== "all" && point.status !== statusFilter) return <td key={metric}><span className="small muted">Filtered out</span></td>;
                return <td key={metric}><p>{point.status === "available" ? "Available" : point.status === "not_applicable" ? "Not applicable" : "Unavailable"}</p>
                  {point.reason && <p className="small metric-reason">{point.reason}</p>}
                  <MetricProvenance point={point} summary={`${METRIC_LABELS[metric]} ${dates}: details`} /></td>;
              })}</tr>;
            })}</tbody></table>
        </div>
      </>}
    </>}
  </>;
}
