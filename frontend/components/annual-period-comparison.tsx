"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { describeApiError, getAnnualFinancials, versionedController, type Company } from "@/lib/finlens-api";
import { COMPARISON_METRICS } from "@/lib/company-comparison";
import { annualPeriodResponse, annualRowWarnings, validAnnualSelection, verifyAnnualSourceIdentities,
  type AnnualPeriodColumn } from "@/lib/annual-period-comparison";
import { formatMetric, METRIC_LABELS, periodLabel } from "@/lib/research";
import { MetricProvenance } from "@/components/financial-research";
import { useResearchVersion } from "@/components/research-freshness";

type Operation = { controller: AbortController };
type Discovery = { years: number[]; error?: string };

// A new company, publication or refresh gets a new session before effects run.
// Returning A -> B -> A cannot restore A's previous selection or request results.
export default function AnnualPeriodComparison({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const [refresh, setRefresh] = useState(0);
  return <section className="panel company-comparison" aria-labelledby="annual-period-title">
    <div className="section-heading"><div><p className="eyebrow">One company over time</p>
      <h2 id="annual-period-title">Annual period comparison</h2></div><span className="muted small">2–4 annual periods · Read only</span></div>
    <p className="muted small">{company.ticker} · {company.name}. Choose a company in Company research above, then choose stored annual fiscal end-years here.
      Available years do not guarantee complete metrics. No other years, quarters or YTD values are substituted.</p>
    {version === null || !Number.isSafeInteger(version) || version < 0
      ? <p role="status">Waiting for a verified company publication. Use the data freshness check to retry.</p>
      : <AnnualSession key={`${company.ticker}:${company.cik}:${version}:${refresh}`} company={company} version={version}
          changed={changed} refresh={() => setRefresh(value => value + 1)} />}
  </section>;
}

function AnnualSession({ company, version, changed, refresh }: { company: Company; version: number; changed: () => void; refresh: () => void }) {
  const [discovery, setDiscovery] = useState<Discovery | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [columns, setColumns] = useState<AnnualPeriodColumn[] | null>(null);
  const [busy, setBusy] = useState(true);
  const [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState("Discovering stored annual periods…");
  const operation = useRef<Operation | null>(null);
  const alive = useRef(false);
  const changedCallback = useRef(changed); changedCallback.current = changed;

  function current(owner: Operation) { return alive.current && operation.current === owner && !owner.controller.signal.aborted; }
  function pinned(owner: Operation) {
    const controller = versionedController(version, () => {
      if (!current(owner)) return;
      owner.controller.abort(); operation.current = null;
      setColumns(null); setInvalid(true); setBusy(false);
      setMessage("Published data changed. This entire grid is hidden until the company publication is verified again.");
      changedCallback.current();
    });
    owner.controller.signal.addEventListener("abort", () => controller.abort(), { once: true });
    if (owner.controller.signal.aborted) controller.abort();
    return controller.signal;
  }

  useEffect(() => {
    alive.current = true;
    const owner = { controller: new AbortController() }; operation.current = owner;
    getAnnualFinancials(company.ticker, null, pinned(owner)).then(value => {
      if (!current(owner)) return;
      const response = annualPeriodResponse(value, company, null);
      setDiscovery({ years: [...response.fiscal_years].sort((a, b) => b - a) });
      setBusy(false); setMessage(response.fiscal_years.length < 2
        ? "Fewer than two stored annual periods are available. No additional periods are invented."
        : "Choose two to four annual periods, then compare.");
    }).catch(error => {
      if (!current(owner)) return;
      setDiscovery({ years: [], error: describeApiError(error) }); setBusy(false);
      setMessage("Annual coverage could not be verified. Refresh annual periods to retry.");
    });
    return () => { alive.current = false; operation.current?.controller.abort(); operation.current = null; };
    // Session key owns company identity, publication pin and refresh generation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function choose(year: number, checked: boolean) {
    operation.current?.controller.abort(); operation.current = null;
    setSelected(previous => checked ? [...previous, year].sort((a, b) => b - a) : previous.filter(value => value !== year));
    setColumns(null); setBusy(false); setMessage("Selection changed. Choose two to four annual periods, then compare.");
  }
  function cancel() {
    operation.current?.controller.abort(); operation.current = null;
    setBusy(false); setColumns(null);
    if (!discovery) setDiscovery({ years: [], error: "Annual discovery cancelled." });
    setMessage("Annual comparison cancelled. Compare again or refresh annual periods to retry.");
  }
  async function compare(event: FormEvent) {
    event.preventDefault();
    if (invalid || busy || !discovery || !validAnnualSelection(selected, discovery.years)) return;
    operation.current?.controller.abort();
    const owner = { controller: new AbortController() }; operation.current = owner;
    setColumns(null); setBusy(true); setMessage("Loading selected annual periods…");
    const next = await Promise.all(selected.map(async (year: number): Promise<AnnualPeriodColumn> => {
      try {
        const value = await getAnnualFinancials(company.ticker, year, pinned(owner));
        if (!current(owner)) return { year };
        return { year, result: annualPeriodResponse(value, company, year, discovery.years) };
      } catch (error) { return { year, error: describeApiError(error) }; }
    }));
    if (!current(owner)) return;
    try {
      verifyAnnualSourceIdentities(next);
      setColumns(next); setMessage(next.some(column => !column.result)
        ? "Some annual periods could not be verified. Failed columns contain no financial values."
        : "Annual period comparison ready. Inspect each period’s sources and limitations.");
    } catch (error) { setColumns(null); setMessage(describeApiError(error)); }
    setBusy(false);
  }

  const valid = !!discovery && validAnnualSelection(selected, discovery.years);
  return <>
    <p className="small muted">Publication version {version}. Values are reported as filed; this is not a historical as-of or original-vintage view.</p>
    <form onSubmit={compare}>
      <fieldset disabled={invalid || !discovery || !!discovery.error} aria-describedby="annual-period-help">
        <legend>Annual fiscal end-years for {company.ticker}</legend>
        <p id="annual-period-help" className="small muted">Select 2–4 available years. Every selected period retains its exact dates and sources.</p>
        <div className="comparison-controls">{discovery?.years.map(year => <label key={year} className="comparison-picker">
          <input type="checkbox" value={year} checked={selected.includes(year)} disabled={selected.length >= 4 && !selected.includes(year)}
            onChange={event => choose(year, event.target.checked)} /> FY{year}
        </label>)}</div>
      </fieldset>
      <div className="comparison-actions">
        <button type="submit" className="primary-button" disabled={!valid || busy || invalid}>Compare selected annual periods</button>
        <button type="button" className="secondary-button" onClick={() => { operation.current?.controller.abort(); operation.current = null; refresh(); }}>Refresh annual periods</button>
        {busy && <button type="button" className="secondary-button" onClick={cancel}>Cancel annual comparison</button>}
      </div>
    </form>
    <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
    {discovery?.error && <p className="error-message">{discovery.error}</p>}
    {columns && !busy && !invalid && <>
      <p className="notice" role="note">Actual reporting dates differ across years. Matching units, fiscal labels or revenue bases do not establish equivalent accounting scope.
        Values are not ranked, converted between currencies or normalized. Revenue YoY is the server’s existing prior-year measure, not a calculation between selected columns.</p>
      <p className="small muted table-scroll-help" id="annual-period-scroll-help">On narrow screens, scroll horizontally to inspect each year. Keyboard users can focus the table region and use arrow keys.</p>
      <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Selected company annual period metrics" aria-describedby="annual-period-scroll-help">
        <table className="comparison-table"><caption>{company.ticker} · Annual financial metrics · Publication version {version}</caption>
          <thead><tr><th scope="col">Metric and limitations</th>{columns.map(column => <th scope="col" key={column.year}>
            <strong>FY{column.year}</strong><span>{column.result ? periodLabel(column.result.period) : "Reporting period not verified"}</span>
            {column.result?.period_reason && <span>{column.result.period_reason}</span>}
          </th>)}</tr></thead>
          <tbody>{COMPARISON_METRICS.map(metric => <tr key={metric}><th scope="row">{METRIC_LABELS[metric]}
            {annualRowWarnings(metric, columns).map(warning => <p className="small" key={warning}>{warning}</p>)}
          </th>{columns.map(column => {
            const point = column.result?.metrics[metric];
            return <td key={column.year}>{point ? <>
              <p className={`metric-value ${point.status !== "available" ? "missing-value" : ""}`}>{formatMetric(point)}</p>
              <p className="small">{point.status === "not_applicable" ? "Not applicable — excluded" : point.status === "unavailable" ? "Unavailable — no value included" : "Available"}</p>
              {point.reason && <p className="small metric-reason">{point.reason}</p>}
              <p className="small muted">{point.unit === "ratio" ? "ratio · displayed as percent" : `${point.unit} · rounded for display`} · no currency conversion</p>
              <p className="small">Revenue basis: {point.revenue_basis ?? "Not supplied for this metric"}</p>
              <MetricProvenance point={point} summary={`${METRIC_LABELS[metric]} FY${column.year}: sources and details`} />
              {point.inputs.length > 0 && <details className="provenance"><summary>{METRIC_LABELS[metric]} FY{column.year}: operand periods and bases</summary>
                <div className="details-body">{point.inputs.map((input, index) => <p key={index}>{input.role} · {input.metric}: {periodLabel(input.period ?? null)}
                  {` · ${input.unit} · Revenue basis: ${input.revenue_basis ?? "Not supplied"} · Facts: ${input.fact_ids.join(", ")}`}</p>)}</div>
              </details>}
            </> : <p>Financial evidence not verified: {column.error ?? "No verified response available."} No value is included for this period.</p>}</td>;
          })}</tr>)}</tbody>
        </table>
      </div>
    </>}
  </>;
}
