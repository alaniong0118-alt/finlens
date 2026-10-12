"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { describeApiError, FinLensApiError, getAnnualFinancials, getFreshness, versionedController,
  type AnnualFinancialComparison, type Company } from "@/lib/finlens-api";
import { COMPARISON_METRICS, comparisonYears, reportingWindowsDiffer, validCompanySelection, validateAnnualResponse } from "@/lib/company-comparison";
import { formatMetric, METRIC_LABELS, periodLabel } from "@/lib/research";
import { MetricProvenance } from "@/components/financial-research";

type CompanyScope = { company: Company; version: number | null; years: number[]; error?: string };
type Column = CompanyScope & { result?: AnnualFinancialComparison };

export default function CompanyComparison({ companies }: { companies: Company[] }) {
  const [selection, setSelection] = useState<string[]>(["", ""]);
  const [refresh, setRefresh] = useState(0);
  const [requestedYear, setRequestedYear] = useState<number | null>(null);
  const [discovery, setDiscovery] = useState<{ key: string; scopes: CompanyScope[]; cancelled?: boolean } | null>(null);
  const [data, setData] = useState<{ key: string; columns: Column[]; cancelled?: boolean } | null>(null);
  const controllers = useRef<AbortController[]>([]);
  const selected = useMemo(() => selection.map(t => companies.find(c => c.ticker === t)).filter((c): c is Company => !!c), [companies, selection]);
  const valid = validCompanySelection(selection) && selected.length === selection.length
    && new Set(selected.map(c => c.cik)).size === selected.length;
  const key = `${selected.map(c => `${c.ticker}:${c.cik}`).join("|")}:${refresh}`;
  const scopes = valid && discovery?.key === key ? discovery.scopes : null;
  const { years, preferred } = comparisonYears(scopes?.map(s => s.years) ?? []);
  const year = requestedYear !== null && years.includes(requestedYear) ? requestedYear : preferred;
  const requestKey = `${key}:${scopes?.map(s => s.version).join("|")}:${year}`;
  const columns = data?.key === requestKey ? data.columns : null;
  const cancelled = !!(discovery?.key === key && discovery.cancelled) || !!(data?.key === requestKey && data.cancelled);
  const loading = valid && !cancelled && (!scopes || (year !== null && !columns));

  useEffect(() => {
    if (!valid) return;
    const active: AbortController[] = [];
    const root = new AbortController(); active.push(root); controllers.current = active;
    const pinned = (version: number) => {
      const controller = versionedController(version, () => {});
      root.signal.addEventListener("abort", () => controller.abort(), { once: true });
      active.push(controller); return controller;
    };
    Promise.all(selected.map(async company => {
      try {
        const freshness = await getFreshness(company.ticker, root.signal);
        if (root.signal.aborted) throw new DOMException("Cancelled", "AbortError");
        if (freshness.ticker !== company.ticker || !Number.isSafeInteger(freshness.data_version) || freshness.data_version < 0
            || !Number.isSafeInteger(freshness.facts_version) || freshness.facts_version < 0 || freshness.facts_version > freshness.data_version
            || !Number.isSafeInteger(freshness.evidence_version) || freshness.evidence_version < 0 || freshness.evidence_version > freshness.data_version) {
          throw new FinLensApiError("Company publication could not be verified.", 502, "INVALID_RESPONSE");
        }
        const response = validateAnnualResponse(await getAnnualFinancials(company.ticker, null, pinned(freshness.data_version).signal), company, null);
        return { company, version: freshness.data_version, years: response.fiscal_years };
      } catch (error) {
        return { company, version: null, years: [], error: describeApiError(error) };
      }
    })).then(next => { if (!root.signal.aborted) setDiscovery({ key, scopes: next }); });
    return () => root.abort();
    // key includes all requested ticker/CIK identities. Object-only catalog changes
    // must not refetch an unchanged financial scope.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, valid]);

  useEffect(() => {
    if (!valid || !scopes || year === null) return;
    const active: AbortController[] = [];
    const root = new AbortController(); active.push(root); controllers.current = active;
    Promise.all(scopes.map(async scope => {
      if (scope.version === null) return scope;
      const controller = versionedController(scope.version, () => {}); active.push(controller);
      root.signal.addEventListener("abort", () => controller.abort(), { once: true });
      try {
        const result = validateAnnualResponse(await getAnnualFinancials(scope.company.ticker, year, controller.signal), scope.company, year);
        return { ...scope, result };
      } catch (error) {
        return { ...scope, error: describeApiError(error) };
      }
    })).then(next => { if (!root.signal.aborted) setData({ key: requestKey, columns: next }); });
    return () => root.abort();
    // requestKey binds the selection, discovery generation, per-company versions and year.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey, valid]);

  function cancel() {
    controllers.current.forEach(c => c.abort());
    if (!scopes) setDiscovery({ key, scopes: [], cancelled: true });
    else setData({ key: requestKey, columns: [], cancelled: true });
  }
  const results = columns?.flatMap(c => c.result ? [c.result] : []) ?? [];
  const bases = new Set(results.flatMap(r => r.metrics.revenue.revenue_basis ? [r.metrics.revenue.revenue_basis] : []));
  return <section className="panel company-comparison" aria-labelledby="comparison-title">
    <div className="section-heading"><div><p className="eyebrow">Reported annual financials</p><h2 id="comparison-title">Company comparison</h2></div>
      <span className="muted small">2–4 companies · Read only</span></div>
    <p className="muted small" id="comparison-help">Compare the same fiscal end-year label. Each issuer retains its actual reporting dates and economic basis; a shared label does not establish equivalent accounting periods.</p>
    <div className="comparison-controls" aria-describedby="comparison-help">
      {selection.map((ticker, i) => <div className="comparison-picker" key={i}>
        <label htmlFor={`comparison-company-${i}`}>Company {i + 1}</label>
        <select id={`comparison-company-${i}`} value={ticker} onChange={e => {
          const next = selection.map((item, index) => index === i ? e.target.value : item);
          if (new Set(next.filter(Boolean)).size === next.filter(Boolean).length) setSelection(next);
        }}><option value="">Select a company</option>{companies.map(c => <option key={c.cik} value={c.ticker} disabled={selection.some((t, index) => index !== i && t === c.ticker)}>{c.ticker} · {c.name}</option>)}</select>
        {selection.length > 2 && <button className="comparison-remove" type="button" aria-label={`Remove company ${i + 1}`} onClick={() => {
          setSelection(selection.filter((_, index) => index !== i));
          document.getElementById(`comparison-company-${Math.max(0, i - 1)}`)?.focus();
        }}>Remove</button>}
      </div>)}
    </div>
    <div className="comparison-actions">
      <button className="secondary-button" type="button" disabled={selection.length === 4 || companies.length <= selection.length} onClick={() => setSelection([...selection, ""])}>Add company</button>
      <label htmlFor="comparison-year">Annual fiscal end-year<select id="comparison-year" value={year ?? ""} disabled={!valid || loading && !scopes || !years.length} onChange={e => setRequestedYear(Number(e.target.value))}>
        {!years.length && <option value="">No observed years</option>}{years.map(y => <option value={y} key={y}>FY{y} · annual end-year</option>)}
      </select></label>
      <button className="secondary-button" type="button" disabled={!valid || loading} onClick={() => setRefresh(value => value + 1)}>Refresh comparison</button>
      {loading && <button className="secondary-button" type="button" onClick={cancel}>Cancel comparison</button>}
    </div>
    <div aria-live="polite" role="status">{!valid ? <div className="empty-state"><strong>Select 2–4 distinct companies</strong><p>Annual metrics use existing SEC observations. No missing values are estimated.</p></div>
      : cancelled ? <p className="notice">Comparison cancelled. Refresh comparison to try again.</p>
      : loading ? <p className="loading-state">Loading verified annual observations…</p>
      : scopes && !years.length ? <p className="notice">{scopes.every(s => s.error)
        ? "Annual coverage could not be verified. Refresh comparison to try again."
        : "No observed annual fiscal years are available in the verified responses."}</p> : null}</div>
    {!cancelled && scopes?.filter(s => s.error).map(s => <p className="error-state" role="alert" key={s.company.cik}>{s.company.ticker}: {s.error}</p>)}
    {valid && !cancelled && columns && columns.length > 0 && <>
      {reportingWindowsDiffer(results) && <p className="notice" role="note">Reporting windows differ. These fiscal-year labels represent different accounting date ranges; compare them with care.</p>}
      {results.some(r => r.period === null) && <p className="notice" role="note">A requested annual window is missing or ambiguous for at least one company. No other reporting period has been substituted.</p>}
      {bases.size > 1 && <p className="notice" role="note">Revenue economic bases differ. Cross-company equivalence has not been established.</p>}
      <p className="muted small" id="comparison-scroll-help">On narrow screens, scroll the table horizontally. Sources and exact values are available in each cell.</p>
      <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Annual company comparison table" aria-describedby="comparison-scroll-help">
        <table className="comparison-table"><caption>Annual financial metrics · FY{year}. Company publications are independently versioned.</caption>
          <thead><tr><th scope="col">Metric</th>{columns.map(column => <th scope="col" key={column.company.cik}><strong>{column.company.ticker}</strong><span>{column.company.name}</span>
            <span>CIK {column.company.cik}</span>
            <span>{column.result ? periodLabel(column.result.period) : "Annual period not verified"}</span>
            {column.result?.period_reason && <span>{column.result.period_reason}</span>}
            {column.version !== null && <span>Publication {column.version}</span>}
          </th>)}</tr></thead>
          <tbody>{COMPARISON_METRICS.map(metric => <tr key={metric}><th scope="row">{METRIC_LABELS[metric]}</th>{columns.map(column => {
            const point = column.result?.metrics[metric];
            return <td key={column.company.cik}>{point ? <>
              <p className={`metric-value ${point.status !== "available" ? "missing-value" : ""}`}>{formatMetric(point)}</p>
              <p className="muted small">{point.unit === "ratio" ? "Ratio · shown as percent" : "USD · rounded for display"}</p>
              {point.revenue_basis && <p className="basis-label small">{point.revenue_basis.replaceAll("_", " ")} basis</p>}
              {point.reason && <p className="small">{point.reason}</p>}
              <MetricProvenance point={point} summary={`${column.company.ticker} ${METRIC_LABELS[metric]} sources and details`} />
            </> : <p className="error-state">{column.error ?? "Financial evidence could not be verified."}</p>}</td>;
          })}</tr>)}</tbody>
        </table>
      </div>
    </>}
  </section>;
}
