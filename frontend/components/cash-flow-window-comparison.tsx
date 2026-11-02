"use client";
import { useEffect, useId, useRef, useState } from "react";
import { describeApiError, FinLensApiError, getMetricHistory, versionedController, type Company, type ReportedWindow } from "@/lib/finlens-api";
import { CASH_FLOW_HISTORY_LIMIT, CASH_FLOW_METRICS, cashFlowCell, cashFlowWindows, cashFlowWindowKey, checkCashFlowSources, validCashFlowWindows, validateCashFlowHistory, type CashFlowKind, type CashFlowSeries } from "@/lib/cash-flow-window-comparison";
import { METRIC_LABELS } from "@/lib/research";
import { MetricProvenance, revealHistorySourceFocus } from "@/components/financial-research";
import { useResearchVersion } from "@/components/research-freshness";

const availability = (status: string) => status === "available" ? "Available" : status === "not_applicable" ? "Not applicable" : "Unavailable";
const label = (w: ReportedWindow) => `${w.start} – ${w.end}`;
export default function CashFlowWindowComparison({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [kind, setKind] = useState<CashFlowKind>("half_year");
  const verified = version !== null && Number.isSafeInteger(version) && version >= 0 && !Object.is(version, -0);
  return <section className="panel company-comparison quarter-comparison" aria-labelledby="cash-flow-window-title">
    <div className="section-heading"><div><p className="eyebrow">One company over time</p>
      <h2 id="cash-flow-window-title">Cash flow by reported duration</h2></div><span className="small muted">3 measures · 2–4 windows · Read only</span></div>
    <p>{company.ticker} · {company.name}</p>
    <p className="small muted">Compare operating cash flow, capital expenditures and free cash flow over exact reported windows. Free cash flow is calculated by FinLens from reported inputs; capital expenditures use a positive outflow convention.</p>
    <label>Duration <select value={kind} onChange={event => setKind(event.target.value as CashFlowKind)}>
      <option value="half_year">Half-year duration</option><option value="nine_months">Nine-month duration</option></select></label>
    {verified ? <CashFlowSession key={`${company.ticker}:${company.cik}:${version}:${kind}`} company={company} version={version!} changed={changed} kind={kind} />
      : <><button type="button" className="primary-button" disabled>Load cash flow histories</button><p role="status">Waiting for a verified company publication.</p></>}
  </section>;
}
function CashFlowSession({ company, version, changed, kind }: { company: Company; version: number; changed: () => void; kind: CashFlowKind }) {
  const [series, setSeries] = useState<CashFlowSeries[] | null>(null), [selected, setSelected] = useState<ReportedWindow[]>([]);
  const [busy, setBusy] = useState(false), [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState("Load cash flow histories to choose reported windows. Nothing is fetched automatically.");
  const alive = useRef(false), operation = useRef<AbortController | null>(null), changedRef = useRef(changed);
  const scrollHelp = useId(), selectionHelp = useId(); changedRef.current = changed;
  useEffect(() => { alive.current = true; return () => { alive.current = false; operation.current?.abort(); operation.current = null; }; }, []);
  function clear() {
    operation.current?.abort(); operation.current = null; setSeries(null); setSelected([]); setBusy(false);
    setMessage(busy ? "Cash flow request cancelled. Load explicitly to retry." : "Cash flow comparison cleared. Load explicitly to choose windows again.");
  }
  async function load() {
    if (!alive.current || invalid || operation.current) return;
    const controller = versionedController(version, () => {
      if (!alive.current || operation.current !== controller || controller.signal.aborted) return;
      controller.abort(); operation.current = null; setSeries(null); setSelected([]); setBusy(false); setInvalid(true);
      setMessage("Published data changed. Verify the company publication before loading cash flow histories again."); changedRef.current();
    });
    operation.current = controller; setBusy(true); setSeries(null); setSelected([]); setMessage("Loading three cash flow histories…");
    const current = () => alive.current && operation.current === controller && !controller.signal.aborted;
    try {
      const responses = await Promise.allSettled(CASH_FLOW_METRICS.map(async metric =>
        validateCashFlowHistory(await getMetricHistory(company.ticker, metric, kind, controller.signal, true), company, metric, kind)));
      if (!current()) return;
      const next = checkCashFlowSources(responses.map((response, index): CashFlowSeries => response.status === "fulfilled"
        ? { metric: CASH_FLOW_METRICS[index], data: response.value, error: null }
        : { metric: CASH_FLOW_METRICS[index], data: null, error: response.reason instanceof FinLensApiError
          ? describeApiError(response.reason) : "This cash flow history could not be verified. Load histories explicitly to retry." }));
      setSeries(next);
      const failed = next.filter(item => !item.data).length, count = cashFlowWindows(next).length;
      setMessage(failed === 3 ? "No cash flow histories could be verified. Load explicitly to retry."
        : `${count} distinct reported windows in the loaded histories.${failed ? ` ${failed} metric ${failed === 1 ? "history" : "histories"} could not be verified.` : ""} ${count < 2 ? "Fewer than two windows are available for comparison." : "Select two to four exact windows."}`);
    } finally { if (current()) { operation.current = null; setBusy(false); } }
  }
  const windows = series ? cashFlowWindows(series) : [], ready = validCashFlowWindows(selected, windows);
  function choose(window: ReportedWindow, checked: boolean) {
    if (invalid || busy || !windows.some(w => cashFlowWindowKey(w) === cashFlowWindowKey(window))) return;
    const next = (checked ? [...selected, window] : selected.filter(w => cashFlowWindowKey(w) !== cashFlowWindowKey(window)))
      .sort((a, b) => cashFlowWindowKey(b).localeCompare(cashFlowWindowKey(a)));
    if (next.length > 4 || new Set(next.map(cashFlowWindowKey)).size !== next.length) return;
    setSelected(next); setMessage(next.length < 2 ? `${next.length} ${next.length === 1 ? "window" : "windows"} selected. Select two to four exact windows.`
      : `Comparison ready for ${next.length} selected windows. Inspect each exact value and its sources.`);
  }
  return <>
    <p className="small muted">Publication version {version} · USD · Up to {CASH_FLOW_HISTORY_LIMIT} observations per metric. Windows come from loaded histories only; older windows may fall outside a metric’s limit.</p>
    <p className="small muted">Current reported-as-filed selections, not a historical as-of view. Different or overlapping intervals, accounting scope and filing revisions may not be comparable. No quarters are derived, dates substituted or currencies converted.</p>
    <div className="comparison-actions"><button type="button" className="primary-button" disabled={busy || invalid} onClick={load}>Load cash flow histories</button>
      <button type="button" className="secondary-button" disabled={invalid} onClick={clear}>{busy ? "Cancel cash flow request" : "Clear cash flow comparison"}</button></div>
    <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
    {series && <>
      <details><summary>Loaded metric availability and limits</summary><ul>{series.map(item => <li key={item.metric}>
        <strong>{METRIC_LABELS[item.metric]}</strong>: {item.data ? <>{availability(item.data.status)} · {item.data.history.length} observations loaded
          {item.data.reason && <p className="small metric-reason">{item.data.reason}</p>}</> : <p className="small error-state">History not verified: {item.error}</p>}
      </li>)}</ul></details>
      {windows.length > 0 && <fieldset disabled={invalid || busy} aria-describedby={selectionHelp}><legend>Reported windows for {company.ticker}</legend>
        <p className="small muted" id={selectionHelp}>Select 2–4 exact start and end dates. Selection and source controls use the histories already loaded.</p>
        <div className="comparison-controls">{windows.map(w => <label key={cashFlowWindowKey(w)} className="comparison-picker"><input type="checkbox"
          checked={selected.some(item => cashFlowWindowKey(item) === cashFlowWindowKey(w))} disabled={selected.length >= 4 && !selected.some(item => cashFlowWindowKey(item) === cashFlowWindowKey(w))}
          onChange={event => choose(w, event.target.checked)} /> <time dateTime={w.start}>{w.start}</time> – <time dateTime={w.end}>{w.end}</time></label>)}</div>
      </fieldset>}
      {ready && <>
        <p className="small muted table-scroll-help" id={scrollHelp}>On narrow screens, scroll horizontally to inspect every window. Keyboard users can focus the table region and use arrow keys. Open sources for exact values and filing details.</p>
        <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Cash flow metrics by exact reported window" aria-describedby={scrollHelp} onFocus={revealHistorySourceFocus}>
          <table className="comparison-table"><caption>{company.ticker} · {kind === "half_year" ? "Half-year" : "Nine-month"} duration · Publication version {version} · USD</caption>
            <thead><tr><th scope="col">Metric</th>{selected.map(w => <th scope="col" key={cashFlowWindowKey(w)}>{label(w)}</th>)}</tr></thead>
            <tbody>{series.map(item => <tr key={item.metric}><th scope="row">{METRIC_LABELS[item.metric]}</th>{selected.map(w => {
              const cell = cashFlowCell(item, w);
              return <td key={cashFlowWindowKey(w)}>{cell.kind === "observation" ? <>
                <p className={`metric-value mono wrap-anywhere ${cell.point.status === "available" ? "" : "missing-value"}`}>{cell.point.status === "available" ? `${cell.point.value} ${cell.point.unit}` : availability(cell.point.status)}</p>
                <p className="small">{availability(cell.point.status)}</p>{cell.point.reason && <p className="small metric-reason">{cell.point.reason}</p>}
                <MetricProvenance point={cell.point} summary={`${METRIC_LABELS[item.metric]} ${label(w)}: sources and details`} />
              </> : <><p className="missing-value">{cell.kind === "error" ? "History not verified" : "Not present in loaded history"}</p><p className="small metric-reason">{cell.reason}</p></>}</td>;
            })}</tr>)}</tbody>
          </table></div>
      </>}
    </>}
  </>;
}
