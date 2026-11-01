"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { describeApiError, getQuarterFinancials, versionedController, type Company, type QuarterComparison, type ReportedWindow } from "@/lib/finlens-api";
import { COMPARISON_METRICS } from "@/lib/company-comparison";
import { validateQuarterResponse, windowKey } from "@/lib/quarter-window-comparison";
import { formatDate, formatMetric, METRIC_LABELS } from "@/lib/research";
import { MetricProvenance, revealHistorySourceFocus } from "@/components/financial-research";
import { useResearchVersion } from "@/components/research-freshness";

const label = (window: ReportedWindow) => `${formatDate(window.start)} – ${formatDate(window.end)}`;
type Operation = { controller: AbortController };

export default function QuarterWindowComparison({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [refresh, setRefresh] = useState(0);
  return <section className="panel company-comparison quarter-comparison" aria-labelledby="quarter-window-title">
    <div className="section-heading"><div><p className="eyebrow">One company over time</p>
      <h2 id="quarter-window-title">Reported quarter-duration windows</h2></div><span className="small muted">2–4 windows · Read only</span></div>
    <p className="small muted">{company.ticker} · {company.name}. Windows are directly reported durations of 75–105 days, not verified fiscal-quarter labels.
      Coverage may be incomplete; annual and year-to-date values are never substituted.</p>
    {version === null || !Number.isSafeInteger(version) || version < 0 || Object.is(version, -0)
      ? <p role="status">Waiting for a verified company publication.</p>
      : <Session key={`${company.ticker}:${company.cik}:${version}:${refresh}`} company={company} version={version} changed={changed}
          refresh={() => setRefresh(value => value + 1)} />}
  </section>;
}

function Session({ company, version, changed, refresh }: { company: Company; version: number; changed: () => void; refresh: () => void }) {
  const [windows, setWindows] = useState<ReportedWindow[] | null>(null);
  const [selected, setSelected] = useState<ReportedWindow[]>([]);
  const [result, setResult] = useState<QuarterComparison | null>(null);
  const [busy, setBusy] = useState(true);
  const [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState("Discovering directly reported windows…");
  const operation = useRef<Operation | null>(null), alive = useRef(false), changedRef = useRef(changed);
  changedRef.current = changed;
  function current(owner: Operation) { return alive.current && operation.current === owner && !owner.controller.signal.aborted; }
  function pinned(owner: Operation) {
    const controller = versionedController(version, () => {
      if (!current(owner)) return;
      owner.controller.abort(); operation.current = null; setWindows(null); setResult(null); setInvalid(true); setBusy(false);
      setMessage("Published data changed. Refresh the company publication before comparing."); changedRef.current();
    });
    owner.controller.signal.addEventListener("abort", () => controller.abort(), { once: true });
    if (owner.controller.signal.aborted) controller.abort();
    return controller.signal;
  }
  useEffect(() => {
    alive.current = true;
    const owner = { controller: new AbortController() }; operation.current = owner;
    getQuarterFinancials(company.ticker, [], pinned(owner)).then(value => {
      if (!current(owner)) return;
      const valid = validateQuarterResponse(value, company, []);
      setWindows(valid.available_windows); setBusy(false);
      setMessage(valid.available_windows.length < 2 ? "Fewer than two reported windows are available." : "Select two to four reported windows.");
    }).catch(error => { if (current(owner)) { setWindows(null); setBusy(false); setMessage(describeApiError(error)); } });
    return () => { alive.current = false; operation.current?.controller.abort(); operation.current = null; };
    // This session is keyed by company, publication and refresh generation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  function choose(window: ReportedWindow, checked: boolean) {
    operation.current?.controller.abort(); operation.current = null; setResult(null); setBusy(false);
    setSelected(previous => checked ? [...previous, window] : previous.filter(item => windowKey(item) !== windowKey(window)));
    setMessage("Selection changed. Compare two to four windows.");
  }
  async function compare(event: FormEvent) {
    event.preventDefault();
    if (busy || invalid || !windows || selected.length < 2 || selected.length > 4) return;
    operation.current?.controller.abort();
    const owner = { controller: new AbortController() }; operation.current = owner;
    setResult(null); setBusy(true); setMessage("Loading selected windows…");
    try {
      const data = await getQuarterFinancials(company.ticker, selected, pinned(owner));
      if (!current(owner)) return;
      setResult(validateQuarterResponse(data, company, selected, windows));
      setMessage("Comparison ready. Inspect each reported period and its sources.");
    } catch (error) { if (current(owner)) { setResult(null); setMessage(describeApiError(error)); } }
    finally { if (current(owner)) setBusy(false); }
  }
  return <>
    <p className="small muted">Publication version {version}. Reported values are not a historical as-of view.</p>
    <form onSubmit={compare}><fieldset disabled={!windows || invalid}>
      <legend>Reported durations for {company.ticker}</legend>
      <p className="small muted">Select 2–4 exact date ranges. Overlapping ranges remain separate.</p>
      <div className="comparison-controls">{windows?.map(window => {
        const checked = selected.some(item => windowKey(item) === windowKey(window));
        return <label key={windowKey(window)} className="comparison-picker"><input type="checkbox" checked={checked}
          disabled={selected.length >= 4 && !checked} onChange={event => choose(window, event.target.checked)} /> {label(window)}</label>;
      })}</div></fieldset>
      <div className="comparison-actions"><button type="submit" className="primary-button" disabled={busy || invalid || selected.length < 2 || selected.length > 4}>Compare reported windows</button>
        <button type="button" className="secondary-button" onClick={() => { operation.current?.controller.abort(); refresh(); }}>Refresh reported windows</button>
        {busy && <button type="button" className="secondary-button" onClick={() => { operation.current?.controller.abort(); operation.current = null; setBusy(false); setResult(null); setMessage("Comparison cancelled. Refresh to retry discovery."); }}>Cancel</button>}</div>
    </form>
    <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
    {result && !invalid && !busy && <>
      <p className="notice" role="note">Different or overlapping intervals and accounting bases may not be comparable. No currency conversion or period arithmetic is performed. Revenue growth uses the engine’s compatible prior-year period, not another selected column.</p>
      <p className="small muted table-scroll-help" id="quarter-scroll-help">Scroll horizontally to inspect each window. Keyboard users can focus the table region and use arrow keys.</p>
      <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Reported window financial metrics" aria-describedby="quarter-scroll-help" onFocus={revealHistorySourceFocus}>
        <table className="comparison-table"><caption>{company.ticker} · Reported duration metrics · Publication version {version}</caption>
          <thead><tr><th scope="col">Metric</th>{result.columns.map(column => <th scope="col" key={windowKey(column.window)}>{label(column.window)}</th>)}</tr></thead>
          <tbody>{COMPARISON_METRICS.map(metric => <tr key={metric}><th scope="row">{METRIC_LABELS[metric]}</th>{result.columns.map(column => {
            const point = column.metrics[metric]; return <td key={windowKey(column.window)}>
              <p className={`metric-value ${point.status !== "available" ? "missing-value" : ""}`}>{formatMetric(point)}</p>
              <p className="small">{point.status === "available" ? "Available" : point.status === "not_applicable" ? "Not applicable" : "Unavailable"}</p>
              {point.reason && <p className="small metric-reason">{point.reason}</p>}
              <p className="small muted">{point.unit === "ratio" ? "ratio · displayed as percent" : point.unit} · no currency conversion</p>
              <p className="small">Revenue basis: {point.revenue_basis ?? "Not supplied for this metric"}</p>
              <MetricProvenance point={point} summary={`${METRIC_LABELS[metric]} ${label(column.window)}: sources and details`} />
            </td>;
          })}</tr>)}</tbody>
        </table></div>
    </>}
  </>;
}
