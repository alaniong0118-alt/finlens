"use client";
import { useEffect, useRef, useState } from "react";
import { describeApiError, FinLensApiError, getStoredCoverage, versionedController, type Company, type StoredFinancialCoverage } from "@/lib/finlens-api";
import { COMPARISON_METRICS } from "@/lib/company-comparison";
import { validateCoverage } from "@/lib/financial-coverage";
import { formatDate, METRIC_LABELS } from "@/lib/research";
import { MetricProvenance, revealHistorySourceFocus } from "@/components/financial-research";
import { useResearchVersion } from "@/components/research-freshness";

export default function FinancialCoverage({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [kind, setKind] = useState<"annual" | "quarter">("annual");
  const verified = version !== null && Number.isSafeInteger(version) && version >= 0 && !Object.is(version, -0);
  return <section className="panel company-comparison financial-coverage" aria-labelledby="coverage-title">
    <div className="section-heading"><div><p className="eyebrow">Stored evidence</p><h2 id="coverage-title">Financial coverage map</h2></div>
      <span className="small muted">Read only · 11 metrics</span></div>
    <p>{company.ticker} · {company.name}</p>
    <p className="small muted">Inspect existing reported windows before comparing. Missing compatible values do not establish missing filings or complete SEC coverage. No acquisition starts here.</p>
    <label>Coverage period type <select value={kind} onChange={event => setKind(event.target.value as "annual" | "quarter")}>
      <option value="annual">Annual durations</option><option value="quarter">Reported quarter durations</option></select></label>
    {verified ? <CoverageSession key={`${company.ticker}:${company.cik}:${version}:${kind}`} company={company} kind={kind} version={version!} changed={changed} />
      : <><button type="button" className="secondary-button" disabled>Load stored coverage</button><p role="status">Waiting for a verified company publication.</p></>}
  </section>;
}

function CoverageSession({ company, kind, version, changed }: { company: Company; kind: "annual" | "quarter"; version: number; changed: () => void }) {
  const [data, setData] = useState<StoredFinancialCoverage | null>(null), [busy, setBusy] = useState(false), [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState("Choose Load stored coverage to inspect this publication. Nothing is fetched automatically.");
  const alive = useRef(false), operation = useRef<AbortController | null>(null), changedRef = useRef(changed);
  changedRef.current = changed;
  useEffect(() => { alive.current = true; return () => { alive.current = false; operation.current?.abort(); operation.current = null; }; }, []);
  function cancel() {
    operation.current?.abort(); operation.current = null; setData(null); setBusy(false);
    setMessage(busy ? "Coverage request cancelled. Load explicitly to retry." : "Coverage cleared. Load explicitly to inspect again.");
  }
  async function load() {
    if (invalid || operation.current || !alive.current) return;
    const controller = versionedController(version, () => {
      if (!alive.current || operation.current !== controller || controller.signal.aborted) return;
      controller.abort(); operation.current = null; setData(null); setBusy(false); setInvalid(true);
      setMessage("Published data changed. Verify the company publication before loading coverage again."); changedRef.current();
    });
    operation.current = controller; setData(null); setBusy(true); setMessage("Loading stored financial coverage…");
    const current = () => alive.current && operation.current === controller && !controller.signal.aborted;
    try {
      const response = await getStoredCoverage(company.ticker, kind, controller.signal);
      if (!current()) return;
      const result = validateCoverage(response, company, kind, version);
      setData(result); setMessage(result.window_count ? `Coverage ready: ${result.window_count} stored windows, ${result.cell_count} metric cells.`
        : "No supported stored windows were found for this metric set. This does not establish absence of filings.");
    } catch (error) {
      if (current()) { setData(null); setMessage(error instanceof FinLensApiError ? describeApiError(error) : "Stored coverage could not be verified. Load explicitly to retry."); }
    } finally { if (current()) { operation.current = null; setBusy(false); } }
  }
  return <>
    <p className="small muted">Publication version {version} · {kind === "annual" ? "Annual" : "Reported quarter"} durations · Existing stored observations only</p>
    <div className="comparison-actions"><button type="button" className="primary-button" disabled={busy || invalid} onClick={load}>Load stored coverage</button>
      <button type="button" className="secondary-button" disabled={invalid} onClick={cancel}>{busy ? "Cancel coverage request" : "Clear coverage"}</button></div>
    <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
    {data && <><p className="small muted">Facts version {data.facts_version} · Evidence version {data.evidence_version}. Dates identify observed durations, not verified fiscal labels or historical as-of snapshots.</p>
      {data.columns.length > 0 && <>
        <p id="coverage-scroll-help" className="small muted">Scroll horizontally to inspect all metrics. Keyboard users can focus the table region and use arrow keys. Open a cell’s details for its original reason and source evidence.</p>
        <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Stored financial coverage matrix" aria-describedby="coverage-scroll-help" onFocus={revealHistorySourceFocus}>
          <table className="comparison-table"><caption>{company.ticker} · {kind} stored coverage · Publication {version}</caption>
            <thead><tr><th scope="col">Actual reported dates</th>{COMPARISON_METRICS.map(metric => <th scope="col" key={metric}>{METRIC_LABELS[metric]}</th>)}</tr></thead>
            <tbody>{data.columns.map(column => {
              const dates = `${formatDate(column.window.start)} – ${formatDate(column.window.end)}`;
              return <tr key={`${column.window.start},${column.window.end}`}><th scope="row">{dates}</th>{COMPARISON_METRICS.map(metric => {
                const point = column.metrics[metric];
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
