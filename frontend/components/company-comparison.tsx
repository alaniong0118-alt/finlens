"use client";
import { useEffect, useMemo, useRef, useState, type FocusEvent } from "react";
import { describeApiError, FinLensApiError, getAnnualFinancials, getFreshness, versionedController,
  type AnnualFinancialComparison, type Company, type FinancialPeriod } from "@/lib/finlens-api";
import { COMPARISON_METRICS, comparisonYears, metricComparability, reportingWindowsDiffer, validCompanySelection, validateAnnualResponse } from "@/lib/company-comparison";
import { formatMetric, METRIC_LABELS, periodLabel } from "@/lib/research";
import { MetricProvenance } from "@/components/financial-research";
import { serializeResearchNote } from "@/lib/research-note";

type CompanyScope = { company: Company; version: number | null; years: number[]; error?: string };
type Column = CompanyScope & { result?: AnnualFinancialComparison };

function inspectionPeriod(period: FinancialPeriod | null | undefined): string {
  return period ? `${period.start ?? "Unknown start"} – ${period.end} · FY${period.fiscal_year ?? "unknown"} ${period.fiscal_period ?? ""}`
    : "Unknown — no reporting period supplied";
}

function ComparabilityInspector({ metric, columns }: { metric: typeof COMPARISON_METRICS[number]; columns: Column[] }) {
  const diagnostics = metricComparability(metric, columns.map(column => column.result));
  return <details className="provenance">
    <summary>Inspect {METRIC_LABELS[metric]} comparability</summary>
    <div className="details-body">
      {diagnostics.windowsDiffer && <p>Reported date ranges differ within this row.</p>}
      {diagnostics.missingWindow && <p>A reporting period is missing. No substitute window is used.</p>}
      {diagnostics.basesDiffer && <p>Reported revenue-basis labels differ within this row. Equivalence is not established.</p>}
      {diagnostics.basisUnknown && <p>Revenue basis is unknown for at least one company or revenue operand.</p>}
      {diagnostics.excluded > 0 && <p>{diagnostics.excluded} of {columns.length} companies have unavailable or not-applicable values. Their reasons remain below.</p>}
      {diagnostics.unverified > 0 && <p>{diagnostics.unverified} of {columns.length} company responses could not be verified. Their comparability is unknown.</p>}
      <p>Matching dates, units or basis labels do not establish equivalent accounting scope. Industry and share-basis eligibility are not established by this response.</p>
      {columns.map(column => {
        const result = column.result;
        const point = result?.metrics[metric];
        return <div className="source-record" key={column.company.cik}>
          <strong>{column.company.ticker}</strong>
          {point && result ? <>
            <p>{point.status === "available" ? "Available" : point.status === "not_applicable" ? "Not applicable — excluded" : "Unavailable — no value included"}</p>
            <p className="wrap-anywhere">Reporting period: {inspectionPeriod(point.period)}</p>
            {result.period_reason && <p>Period reason: <span style={{ whiteSpace: "pre-wrap" }}>{result.period_reason}</span></p>}
            {point.reason && <p>Metric reason: <span style={{ whiteSpace: "pre-wrap" }}>{point.reason}</span></p>}
            <p>Reported unit: {point.unit}{point.unit === "ratio" ? " · displayed as percent; no currency conversion" : " · no currency conversion"}</p>
            <p>Metric revenue basis: {point.revenue_basis || "Unknown — not supplied for this metric"}</p>
            {point.inputs.map((input, index) => <div key={index}>
              <p>Operand: {input.role} · {input.metric}</p>
              <p className="wrap-anywhere">Operand reporting period: {inspectionPeriod(input.period)}</p>
              <p>Operand unit: {input.unit}</p>
              {(input.metric === "revenue" || input.revenue_basis) && <p>Operand revenue basis: {input.revenue_basis || "Unknown — not supplied for this operand"}</p>}
            </div>)}
            <p>Selected and alternative observations remain in this company&apos;s sources and details.</p>
          </> : <p>Financial evidence not verified: {column.error ?? "No verified response available."}</p>}
        </div>;
      })}
    </div>
  </details>;
}

function revealComparisonFocus(event: FocusEvent<HTMLDivElement>) {
  const scroller = event.currentTarget;
  const target = event.target;
  if (!(target instanceof HTMLElement) || !target.closest(".provenance")
      || !target.matches(":focus-visible") || !scroller.clientWidth) return;
  // Native focus scrolling has already run. Reveal residual outline clipping
  // without moving focus, intercepting keys or scheduling later adjustments.
  const style = window.getComputedStyle(target);
  const outline = Math.max(0, parseFloat(style.outlineWidth) || 0)
    + Math.max(0, parseFloat(style.outlineOffset) || 0);
  const gutter = outline + 1;
  const rect = target.getBoundingClientRect();
  const left = scroller.getBoundingClientRect().left + scroller.clientLeft;
  const right = left + scroller.clientWidth;
  const delta = rect.left - gutter < left ? rect.left - gutter - left
    : rect.right + gutter > right ? rect.right + gutter - right : 0;
  const next = Math.max(0, Math.min(scroller.scrollWidth - scroller.clientWidth, scroller.scrollLeft + delta));
  if (next !== scroller.scrollLeft) scroller.scrollLeft = next;

  const page = document.scrollingElement;
  if (!page) return;
  const viewport = window.visualViewport;
  const top = viewport?.offsetTop ?? 0;
  const bottom = top + (viewport?.height ?? document.documentElement.clientHeight);
  const focused = target.getBoundingClientRect();
  const deltaY = focused.top - outline < top ? focused.top - gutter - top
    : focused.bottom + outline > bottom ? focused.bottom + gutter - bottom : 0;
  if (!deltaY) return;
  // Round away from the clipped edge: integer scroll quantization must not
  // leave fractional outline paint outside the viewport.
  const movement = deltaY < 0 ? Math.floor(deltaY) : Math.ceil(deltaY);
  const nextY = Math.max(0, Math.min(Math.max(0, page.scrollHeight - page.clientHeight), window.scrollY + movement));
  if (nextY !== window.scrollY) window.scrollTo({ left: window.scrollX, top: nextY, behavior: "instant" });
}

export default function CompanyComparison({ companies }: { companies: Company[] }) {
  const [selection, setSelection] = useState<string[]>(["", ""]);
  const [refresh, setRefresh] = useState(0);
  const [requestedYear, setRequestedYear] = useState<number | null>(null);
  const [annualGeneration, setAnnualGeneration] = useState(0);
  const [discovery, setDiscovery] = useState<{ key: string; scopes: CompanyScope[]; cancelled?: boolean } | null>(null);
  const [data, setData] = useState<{ key: string; columns: Column[]; cancelled?: boolean } | null>(null);
  const [coverageFilter, setCoverageFilter] = useState<{ key: string; gapsOnly: boolean } | null>(null);
  const controllers = useRef<AbortController[]>([]);
  const selected = useMemo(() => selection.map(t => companies.find(c => c.ticker === t)).filter((c): c is Company => !!c), [companies, selection]);
  const valid = validCompanySelection(selection) && selected.length === selection.length
    && new Set(selected.map(c => c.cik)).size === selected.length;
  const key = `${selected.map(c => `${c.ticker}:${c.cik}`).join("|")}:${refresh}`;
  const scopes = valid && discovery?.key === key ? discovery.scopes : null;
  const { years, preferred } = comparisonYears(scopes?.map(s => s.years) ?? []);
  const year = requestedYear !== null && years.includes(requestedYear) ? requestedYear : preferred;
  const requestKey = `${key}:${scopes?.map(s => s.version).join("|")}:${year}:${annualGeneration}`;
  const columns = data?.key === requestKey ? data.columns : null;
  const cancelled = !!(discovery?.key === key && discovery.cancelled) || !!(data?.key === requestKey && data.cancelled);
  const loading = valid && !cancelled && (!scopes || (year !== null && !columns));
  const copyEligible = valid && !loading && !cancelled && year !== null
    && scopes?.length === selected.length && columns?.length === selected.length
    && columns.every((column, i) => {
      const scope = scopes[i];
      return !scope.error && !column.error && column.result && scope.version !== null
        && Number.isSafeInteger(scope.version) && scope.version >= 0 && column.version === scope.version
        && column.company.ticker === selected[i].ticker && column.company.cik === selected[i].cik
        && scope.company.ticker === selected[i].ticker && scope.company.cik === selected[i].cik;
    });
  const copyOwner = useMemo(() => ({ requestKey, data, discovery, cancelled, loading, valid }), [requestKey, data, discovery, cancelled, loading, valid]);
  const liveCopyOwner = useRef<typeof copyOwner | null>(copyOwner);
  liveCopyOwner.current = copyOwner; // Render ownership precedes passive-effect cancellation.
  const copySequence = useRef(0);
  const copyPending = useRef<object | null>(null);
  const mounted = useRef(false);
  const [copyFeedback, setCopyFeedback] = useState<{ owner: object; metric: string; message: string; pending: boolean } | null>(null);
  useEffect(() => {
    const sequence = copySequence;
    mounted.current = true;
    return () => { mounted.current = false; sequence.current++; copyPending.current = null; };
  }, []);
  function invalidateCopy() {
    liveCopyOwner.current = null;
    copySequence.current++; copyPending.current = null; setCopyFeedback(null);
  }
  function changeSelection(next: string[]) {
    invalidateCopy();
    // A -> B -> A must not reuse discovery/data from an earlier selection visit.
    setRefresh(value => value + 1); setSelection(next);
  }
  function copyNote(metric: string) {
    if (!mounted.current || liveCopyOwner.current !== copyOwner || !copyEligible || !columns || year === null || copyPending.current === copyOwner) return;
    const owner = copyOwner;
    const sequence = ++copySequence.current;
    const current = () => mounted.current && liveCopyOwner.current === owner && copySequence.current === sequence;
    const feedback = (message: string, pending = false) => {
      if (current()) setCopyFeedback({ owner, metric, message, pending });
    };
    try {
      // The immutable Markdown string captures this eligible scope synchronously.
      // No await/request precedes clipboard access: preserve user activation.
      const note = serializeResearchNote(metric, year, columns.map(column => ({
        company: column.company, version: column.version!, result: column.result!,
      })));
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      copyPending.current = owner;
      feedback("Copying research note…", true);
      const write = navigator.clipboard.writeText(note);
      void write.then(() => {
        if (current()) { copyPending.current = null; feedback("Research note copied."); }
      }, () => {
        if (current()) { copyPending.current = null; feedback("Could not copy research note. Check clipboard permissions and try again."); }
      });
    } catch {
      if (current()) { copyPending.current = null; feedback("Could not copy research note. Clipboard access or verified export data is unavailable."); }
    }
  }

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
    invalidateCopy();
    controllers.current.forEach(c => c.abort());
    if (!scopes) setDiscovery({ key, scopes: [], cancelled: true });
    else setData({ key: requestKey, columns: [], cancelled: true });
  }
  const results = columns?.flatMap(c => c.result ? [c.result] : []) ?? [];
  const bases = new Set(results.flatMap(r => r.metrics.revenue.revenue_basis ? [r.metrics.revenue.revenue_basis] : []));
  // Only current, validated columns supply statuses. Unverified columns keep all
  // rows in the gap view rather than turning unknown coverage into success.
  const unverifiedCompanies = columns?.filter(column => !column.result).length ?? 0;
  const unavailableMetrics = COMPARISON_METRICS.filter(metric => columns?.some(column => {
    const status = column.result?.metrics[metric].status;
    return status === "unavailable" || status === "not_applicable";
  }));
  const gapMetrics = unverifiedCompanies > 0 ? COMPARISON_METRICS : unavailableMetrics;
  // Scope generations reset the view, including A -> B -> A and refreshes.
  const gapsOnly = coverageFilter?.key === requestKey && coverageFilter.gapsOnly;
  const visibleMetrics = gapsOnly ? gapMetrics : COMPARISON_METRICS;
  return <section className="panel company-comparison" aria-labelledby="comparison-title">
    <div className="section-heading"><div><p className="eyebrow">Reported annual financials</p><h2 id="comparison-title">Company comparison</h2></div>
      <span className="muted small">2–4 companies · Read only</span></div>
    <p className="muted small" id="comparison-help">Compare the same fiscal end-year label. Each issuer retains its actual reporting dates and economic basis; a shared label does not establish equivalent accounting periods.</p>
    <div className="comparison-controls" aria-describedby="comparison-help">
      {selection.map((ticker, i) => <div className="comparison-picker" key={i}>
        <label htmlFor={`comparison-company-${i}`}>Company {i + 1}</label>
        <select id={`comparison-company-${i}`} value={ticker} onChange={e => {
          const next = selection.map((item, index) => index === i ? e.target.value : item);
          if (new Set(next.filter(Boolean)).size === next.filter(Boolean).length) changeSelection(next);
        }}><option value="">Select a company</option>{companies.map(c => <option key={c.cik} value={c.ticker} disabled={selection.some((t, index) => index !== i && t === c.ticker)}>{c.ticker} · {c.name}</option>)}</select>
        {selection.length > 2 && <button className="comparison-remove" type="button" aria-label={`Remove company ${i + 1}`} onClick={() => {
          changeSelection(selection.filter((_, index) => index !== i));
          document.getElementById(`comparison-company-${Math.max(0, i - 1)}`)?.focus();
        }}>Remove</button>}
      </div>)}
    </div>
    <div className="comparison-actions">
      <button className="secondary-button" type="button" disabled={selection.length === 4 || companies.length <= selection.length} onClick={() => changeSelection([...selection, ""])}>Add company</button>
      <label htmlFor="comparison-year">Annual fiscal end-year<select id="comparison-year" value={year ?? ""} disabled={!valid || loading && !scopes || !years.length} onChange={e => { invalidateCopy(); setAnnualGeneration(value => value + 1); setRequestedYear(Number(e.target.value)); }}>
        {!years.length && <option value="">No observed years</option>}{years.map(y => <option value={y} key={y}>FY{y} · annual end-year</option>)}
      </select></label>
      <button className="secondary-button" type="button" disabled={!valid || loading} onClick={() => { invalidateCopy(); setRefresh(value => value + 1); }}>Refresh comparison</button>
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
      <div className="comparison-actions">
        <label htmlFor="comparison-metric-view">Metric rows<select id="comparison-metric-view" value={gapsOnly ? "gaps" : "all"}
          aria-describedby="comparison-coverage-help comparison-coverage-count" onChange={event => setCoverageFilter({ key: requestKey, gapsOnly: event.target.value === "gaps" })}>
          <option value="all">All metrics ({COMPARISON_METRICS.length})</option>
          <option value="gaps">Coverage gaps ({gapMetrics.length})</option>
        </select></label>
        {gapsOnly && <button type="button" className="secondary-button" onClick={() => setCoverageFilter({ key: requestKey, gapsOnly: false })}>Show all metrics</button>}
      </div>
      <p className="muted small" id="comparison-coverage-help">Coverage gaps include unavailable, not-applicable and unverified values. Availability alone does not establish comparability.</p>
      <p className="muted small" id="comparison-coverage-count" role="status" aria-live="polite">Showing {visibleMetrics.length} of {COMPARISON_METRICS.length} metric rows. Rows with unavailable or not-applicable values: {unavailableMetrics.length}. Unverified company responses: {unverifiedCompanies}.</p>
      {visibleMetrics.length === 0 && <p className="notice">No coverage gaps in the current validated responses. Select Show all metrics to inspect values and comparability.</p>}
      <p className="muted small" id="comparison-scroll-help">On narrow screens, scroll the table horizontally. Sources and exact values are available in each cell.</p>
      <div className="table-scroll comparison-scroll" tabIndex={0} role="region" aria-label="Annual company comparison table" aria-describedby="comparison-scroll-help" onFocusCapture={revealComparisonFocus}>
        <table className="comparison-table"><caption>Annual financial metrics · FY{year}. Company publications are independently versioned.</caption>
          <thead><tr><th scope="col">Metric</th>{columns.map(column => <th scope="col" key={column.company.cik}><strong>{column.company.ticker}</strong><span>{column.company.name}</span>
            <span>CIK {column.company.cik}</span>
            <span>{column.result ? periodLabel(column.result.period) : "Annual period not verified"}</span>
            {column.result?.period_reason && <span>{column.result.period_reason}</span>}
            {column.version !== null && <span>Publication {column.version}</span>}
          </th>)}</tr></thead>
          <tbody>{visibleMetrics.map(metric => <tr key={metric}><th scope="row">{METRIC_LABELS[metric]}
            <ComparabilityInspector key={requestKey} metric={metric} columns={columns} />
            <button type="button" className="secondary-button" aria-label={`Copy research note for ${METRIC_LABELS[metric]}`}
              disabled={!copyEligible || copyFeedback?.owner === copyOwner && copyFeedback.pending} onClick={() => copyNote(metric)}>Copy Research Note</button>
            <span role="status" aria-live="polite">{copyFeedback?.owner === copyOwner && copyFeedback.metric === metric ? copyFeedback.message : ""}</span>
          </th>{columns.map(column => {
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
