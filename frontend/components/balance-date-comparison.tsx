"use client";
import { useEffect, useId, useRef, useState } from "react";
import { describeApiError, FinLensApiError, getMetricHistory, versionedController, type Company } from "@/lib/finlens-api";
import { BALANCE_HISTORY_LIMIT, BALANCE_METRICS, balanceCell, balanceDates, checkBalanceSources, validBalanceDates, validateBalanceHistory, type BalanceSeries } from "@/lib/balance-date-comparison";
import { METRIC_LABELS } from "@/lib/research";
import { MetricProvenance, revealHistorySourceFocus } from "@/components/financial-research";
import { useResearchVersion } from "@/components/research-freshness";

const availability = (status: string) => status === "available" ? "Available" : status === "not_applicable" ? "Not applicable" : "Unavailable";

export default function BalanceDateComparison({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const verified = version !== null && Number.isSafeInteger(version) && version >= 0 && !Object.is(version, -0);
  return <section className="panel company-comparison quarter-comparison balance-date-comparison" aria-labelledby="balance-date-title">
    <div className="section-heading"><div><p className="eyebrow">One company over time</p>
      <h2 id="balance-date-title">Balance sheet by reported date</h2></div><span className="small muted">3 measures · 2–4 dates · Read only</span></div>
    <p>{company.ticker} · {company.name}</p>
    <p className="small muted">Compare cash and equivalents, total assets and total liabilities at exact reported dates.
      This selected metric set is not a complete balance sheet.</p>
    {verified ? <BalanceSession key={`${company.ticker}:${company.cik}:${version}`} company={company} version={version!} changed={changed} />
      : <><button type="button" className="primary-button" disabled>Load balance histories</button><p role="status">Waiting for a verified company publication.</p></>}
  </section>;
}

function BalanceSession({ company, version, changed }: { company: Company; version: number; changed: () => void }) {
  const [series, setSeries] = useState<BalanceSeries[] | null>(null), [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false), [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState("Load balance histories to choose reported dates. Nothing is fetched automatically.");
  const alive = useRef(false), operation = useRef<AbortController | null>(null), changedRef = useRef(changed);
  const scrollHelp = useId(), selectionHelp = useId();
  changedRef.current = changed;
  useEffect(() => { alive.current = true; return () => { alive.current = false; operation.current?.abort(); operation.current = null; }; }, []);
  function clear() {
    operation.current?.abort(); operation.current = null; setSeries(null); setSelected([]); setBusy(false);
    setMessage(busy ? "Balance history request cancelled. Load explicitly to retry." : "Balance comparison cleared. Load explicitly to choose dates again.");
  }
  async function load() {
    if (!alive.current || invalid || operation.current) return;
    const controller = versionedController(version, () => {
      if (!alive.current || operation.current !== controller || controller.signal.aborted) return;
      controller.abort(); operation.current = null; setSeries(null); setSelected([]); setBusy(false); setInvalid(true);
      setMessage("Published data changed. Verify the company publication before loading balance histories again."); changedRef.current();
    });
    operation.current = controller; setBusy(true); setSeries(null); setSelected([]); setMessage("Loading three balance histories…");
    const current = () => alive.current && operation.current === controller && !controller.signal.aborted;
    try {
      const responses = await Promise.allSettled(BALANCE_METRICS.map(async metric =>
        validateBalanceHistory(await getMetricHistory(company.ticker, metric, "instant", controller.signal), company, metric)));
      if (!current()) return;
      const next = checkBalanceSources(responses.map((response, index): BalanceSeries => response.status === "fulfilled"
        ? { metric: BALANCE_METRICS[index], data: response.value, error: null }
        : { metric: BALANCE_METRICS[index], data: null, error: response.reason instanceof FinLensApiError
          ? describeApiError(response.reason) : "This balance history could not be verified. Load histories explicitly to retry." }));
      setSeries(next);
      const failed = next.filter(item => !item.data).length, count = balanceDates(next).length;
      setMessage(failed === 3 ? "No balance histories could be verified. Load explicitly to retry."
        : `${count} distinct reported dates in the loaded histories.${failed ? ` ${failed} metric ${failed === 1 ? "history" : "histories"} could not be verified.` : ""} ${count < 2 ? "Fewer than two dates are available for comparison." : "Select two to four exact dates."}`);
    } finally {
      if (current()) { operation.current = null; setBusy(false); }
    }
  }
  const dates = series ? balanceDates(series) : [];
  const ready = validBalanceDates(selected, dates);
  function choose(end: string, checked: boolean) {
    if (invalid || busy || !dates.includes(end)) return;
    const next = (checked ? [...selected, end] : selected.filter(date => date !== end)).sort().reverse();
    if (next.length > 4 || new Set(next).size !== next.length) return;
    setSelected(next); setMessage(next.length < 2 ? `${next.length} ${next.length === 1 ? "date" : "dates"} selected. Select two to four exact dates.`
      : `Comparison ready for ${next.length} selected dates. Inspect each exact value and its sources.`);
  }
  return <>
    <p className="small muted">Publication version {version} · USD · Up to {BALANCE_HISTORY_LIMIT} observations per metric.
      Dates come from these loaded windows only, which may differ by metric; older dates may be outside a window.</p>
    <p className="small muted">Current reported-as-filed selections. These dates identify balances, not what was known historically.
      Accounting scope and filing revisions may differ; comparability is unverified. Values are shown exactly as returned.</p>
    <div className="comparison-actions"><button type="button" className="primary-button" disabled={busy || invalid} onClick={load}>Load balance histories</button>
      <button type="button" className="secondary-button" disabled={invalid} onClick={clear}>{busy ? "Cancel balance request" : "Clear balance comparison"}</button></div>
    <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
    {series && <>
      <details><summary>Loaded metric availability and limits</summary><ul>{series.map(item => <li key={item.metric}>
        <strong>{METRIC_LABELS[item.metric]}</strong>: {item.data ? <>{availability(item.data.status)} · {item.data.history.length} observations loaded
          {item.data.reason && <p className="small metric-reason">{item.data.reason}</p>}
          {item.data.comparability?.reason && <p className="small">{item.data.comparability.reason}</p>}
          {item.data.history.filter(point => !point.period).map((point, index) => <p className="small" key={index}>
            Undated observation · {availability(point.status)}: {point.reason}</p>)}
        </> : <p className="small error-state">History not verified: {item.error}</p>}
      </li>)}</ul></details>
      {dates.length > 0 && <fieldset disabled={invalid || busy} aria-describedby={selectionHelp}><legend>Reported dates for {company.ticker}</legend>
        <p className="small muted" id={selectionHelp}>Select 2–4 distinct dates. Only an observation at the exact date is shown; another date is never substituted.
          Selecting dates and opening sources use the histories already loaded.</p>
        <div className="comparison-controls">{dates.map(end => <label key={end} className="comparison-picker"><input type="checkbox"
          checked={selected.includes(end)} disabled={selected.length >= 4 && !selected.includes(end)}
          onChange={event => choose(end, event.target.checked)} /> As of <time dateTime={end}>{end}</time></label>)}</div>
      </fieldset>}
      {ready && <>
        <p className="small muted table-scroll-help" id={scrollHelp}>On narrow screens, scroll horizontally to inspect every date.
          Keyboard users can focus the table region and use arrow keys. Open a cell’s sources for its accession, filing date and exact source value.</p>
        <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Balance metrics by exact reported date"
          aria-describedby={scrollHelp} onFocus={revealHistorySourceFocus}>
          <table className="comparison-table"><caption>{company.ticker} · Selected balance measures · Publication version {version} · USD</caption>
            <thead><tr><th scope="col">Metric</th>{selected.map(end => <th scope="col" key={end}>As of <time dateTime={end}>{end}</time></th>)}</tr></thead>
            <tbody>{series.map(item => <tr key={item.metric}><th scope="row">{METRIC_LABELS[item.metric]}</th>{selected.map(end => {
              const cell = balanceCell(item, end);
              return <td key={end}>{cell.kind === "observation" ? <>
                <p className={`metric-value mono wrap-anywhere ${cell.point.status === "available" ? "" : "missing-value"}`}>
                  {cell.point.status === "available" ? `${cell.point.value} ${cell.point.unit}` : availability(cell.point.status)}</p>
                <p className="small">{availability(cell.point.status)}</p>
                {cell.point.reason && <p className="small metric-reason">{cell.point.reason}</p>}
                <MetricProvenance point={cell.point} summary={`${METRIC_LABELS[item.metric]} as of ${end}: sources and details`} />
              </> : <><p className="missing-value">{cell.kind === "error" ? "History not verified" : "Not present in loaded history"}</p>
                <p className="small metric-reason">{cell.reason}</p></>}</td>;
            })}</tr>)}</tbody>
          </table></div>
      </>}
    </>}
  </>;
}
