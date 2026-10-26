"use client";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { getFinancialInsights, versionedController, type Company } from "@/lib/finlens-api";
import type { DisplayRecord, InsightsPanel, InsightsPresentation, InsightsResultHandle } from "@/lib/financial-insights";
import { officialSecUrl } from "@/lib/research";
import { useResearchVersion } from "@/components/research-freshness";

const METRICS = [
  ["revenue", "Revenue"], ["operating_income", "Operating income"], ["net_income", "Net income"],
  ["operating_margin", "Operating margin"], ["net_margin", "Net margin"],
  ["operating_cash_flow", "Operating cash flow"], ["free_cash_flow", "Free cash flow"],
] as const;
type Target = { collection: string; page: number; key?: string };
type View = { owner: string; generation: number; discovery: InsightsPresentation | null; handle: InsightsResultHandle | null;
  phase: "waiting" | "loading" | "ready" | "error" | "closed" | "unsupported";
  operation: "discover" | "compare"; message: string | null };
type Flight = { collection: string; page: number; promise: Promise<void> };
const collectionLabel = (id: string) => id === "F" ? "Financial evidence used — F" : "Inputs examined and reasons not used — D";
const words = (text: string) => text.replaceAll("_", " ");
function periodText(value: unknown) {
  if (!value || typeof value !== "object") return "Annual reporting window unavailable";
  const p = value as Record<string, unknown>;
  return `${p.start} – ${p.end} · ${p.kind} · fiscal year ${p.fiscal_year}`;
}

function EvidenceRecord({ record, disabled, navigate }: { record: DisplayRecord; disabled: boolean;
  navigate: (target: Target, trigger: HTMLElement) => void }) {
  const title = [record.ref.kind, record.ref.metric, record.ref.side, record.ref.role].filter(Boolean).map(v => words(v!)).join(" · ");
  return <article className="insights-record" data-insight-key={record.ref.key} tabIndex={-1}>
    <h4>{title}</h4>
    <p className="small">{collectionLabel(record.ref.category)}</p>
    <details><summary>Exact fields and source metadata</summary>
      <p className="mono">Reference: {record.ref.key}</p><p className="mono">Scope: {record.ref.scope}</p>
      <dl className="insights-fields">{record.fields.map(([path, value]) => <div key={path}>
        <dt>{path}</dt><dd>{value === null ? "Not supplied (null)" : String(value)}
          {path.endsWith(".sec_url") && typeof value === "string" && officialSecUrl(value) && <>
            {" · "}<a href={officialSecUrl(value)} target="_blank" rel="noopener noreferrer">Open official SEC filing</a>
          </>}
        </dd>
      </div>)}</dl>
    </details>
    {record.links.length > 0 && <div className="insights-links" aria-label="Operand and source lineage">
      {record.links.map(link => <button type="button" className="secondary-button" disabled={disabled} key={link.key}
        onClick={event => navigate(link, event.currentTarget)}>
        Examine {words(link.kind)}{link.metric ? ` · ${words(link.metric)}` : ""}{link.role ? ` · ${words(link.role)}` : ""}{link.side ? ` · ${link.side}` : ""}
      </button>)}
    </div>}
  </article>;
}

export default function FinancialInsights({ company }: { company: Company }) {
  const { version, changed } = useResearchVersion();
  const owner = JSON.stringify([company.ticker, company.cik, version]);
  const [view, setView] = useState<View>({ owner, generation: 0, discovery: null, handle: null, phase: "waiting", operation: "discover", message: null });
  const [years, setYears] = useState({ owner, earlier: "", later: "" });
  const [, redraw] = useState(0);
  const [pageMessage, setPageMessage] = useState<string | null>(null);
  const panel = useRef<InsightsPanel | null>(null);
  const transport = useRef<Pick<InsightsPanel["environment"], "worker" | "fetch"> | null>(null);
  const live = useRef({ owner, generation: 0, mounted: false, controller: null as AbortController | null,
    handle: null as InsightsResultHandle | null, unsubscribe: null as (() => void) | null, pending: false,
    deadline: null as ReturnType<typeof setTimeout> | null, completeInitialization: null as (() => boolean) | null });
  const flight = useRef<Flight | null>(null);
  const pageFocus = useRef<{ target: Target; trigger: HTMLElement; generation: number; handle: InsightsResultHandle } | null>(null);
  const returnFocus = useRef<{ trigger: HTMLElement; generation: number } | null>(null);
  const compareButton = useRef<HTMLButtonElement | null>(null), cancelButton = useRef<HTMLButtonElement | null>(null);
  const retryButton = useRef<HTMLButtonElement | null>(null), viewport = useRef<HTMLDivElement | null>(null);
  const evidenceDetails = useRef<HTMLDetailsElement | null>(null);
  const uid = useId();
  const invalidate = useCallback(() => {
    const state = live.current;
    state.generation++; state.pending = false;
    state.completeInitialization = null;
    if (state.deadline !== null) clearTimeout(state.deadline); state.deadline = null;
    // Detach consumers before synchronous disposal, including render-time invalidation.
    state.unsubscribe?.(); state.unsubscribe = null; state.handle = null;
    state.controller?.abort(); state.controller = null; panel.current?.dispose();
    flight.current = null; pageFocus.current = null; returnFocus.current = null;
  }, []);
  if (live.current.owner !== owner) { invalidate(); live.current.owner = owner; }
  useLayoutEffect(() => {
    const lifecycle = live.current;
    lifecycle.mounted = true;
    return () => { lifecycle.mounted = false; invalidate(); };
  }, [owner, invalidate]);

  const begin = useCallback(async (operation: "discover" | "compare", discovery: InsightsPresentation | null,
    selection?: { earlier: number; later: number }) => {
    if (version === null || !live.current.mounted || live.current.owner !== owner || live.current.pending) return;
    const startedAt = performance.now(), startedWall = Date.now();
    invalidate();
    const state = live.current, generation = state.generation;
    let initializing = true, readyQueued = false;
    const owns = () => state.mounted && state.owner === owner && state.generation === generation
      && state.controller === controller && !controller.signal.aborted;
    const deadlineReached = () => {
      const now = performance.now(), wall = Date.now();
      // Wall time also bounds suspension where the monotonic clock stops ticking.
      // Invalid/regressed monotonic readings fail closed; a backward wall change
      // cannot extend a progressing monotonic budget.
      return !Number.isFinite(startedAt) || !Number.isFinite(now) || now < startedAt
        || now - startedAt >= 30000 || !Number.isFinite(startedWall) || !Number.isFinite(wall) || wall - startedWall >= 30000;
    };
    const current = () => {
      if (!owns()) return false;
      if (initializing && deadlineReached()) { expire(); return false; }
      return true;
    };
    const controller = versionedController(version, () => { if (current()) changed(); });
    state.controller = controller; state.pending = true; setPageMessage(null);
    setView({ owner, generation, discovery, handle: null, phase: "loading", operation, message: null });
    const prepareFocus = () => {
      if (owns() && cancelButton.current && document.activeElement === cancelButton.current)
        returnFocus.current = { trigger: cancelButton.current, generation };
    };
    // Include deferred module loading in the UI's initial 30-second budget.
    // The committed transport keeps its own independent deadline and cleanup.
    const expire = () => {
      if (!owns() || !initializing) return;
      prepareFocus(); const restore = returnFocus.current;
      invalidate();
      if (restore) returnFocus.current = { ...restore, generation: state.generation };
      setView({ owner, generation: state.generation, discovery, handle: null, phase: "error", operation,
        message: "Annual insights timed out after the bounded request deadline. Retry explicitly." });
    };
    state.deadline = setTimeout(expire, 30000);
    state.completeInitialization = () => {
      if (!current()) return false;
      initializing = false; state.pending = false; state.completeInitialization = null;
      if (state.deadline !== null) clearTimeout(state.deadline); state.deadline = null;
      return true;
    };
    try {
      if (!current()) return;
      if (typeof Worker === "undefined") {
        if (current()) setView({ owner, generation, discovery: null, handle: null, phase: "unsupported", operation,
          message: "Annual financial insights require browser Worker support. Snapshot, history and SEC research remain available below." });
        return;
      }
      // Keep the actual production Worker constructor in its committed module.
      // No runtime import occurs in a genuinely unsupported environment.
      const library = panel.current ? null : await import("@/lib/financial-insights");
      if (!current()) return;
      if (!panel.current) {
        panel.current = new library!.InsightsPanel();
        transport.current = { worker: panel.current.environment.worker, fetch: panel.current.environment.fetch };
      }
      if (!current()) return;
      // Use the existing environment seam to check immediately before allocation
      // and network work, even if synchronous setup consumed the remaining time.
      const base = transport.current!;
      panel.current.environment.worker = () => {
        if (!current()) throw new DOMException("Initialization cancelled", "AbortError");
        return base.worker();
      };
      panel.current.environment.fetch = (...args) => current() ? base.fetch(...args)
        : Promise.reject(new DOMException("Initialization cancelled", "AbortError"));
      // This same elapsed guard is passed through request.current: the committed
      // transport checks it before Worker/fetch work and each async continuation.
      const result = await getFinancialInsights({ ticker: company.ticker, cik: company.cik }, operation === "discover" ? { mode: "discover" }
        : { mode: "compare", earlier: selection!.earlier, later: selection!.later }, controller.signal, panel.current, current, discovery ?? undefined);
      if (!current()) { if (result.mode === "compare") result.handle.dispose(); return; }
      prepareFocus();
      if (result.mode === "discover") {
        readyQueued = true;
        setYears({ owner, earlier: result.data.fiscal_years[1]?.toString() ?? "", later: result.data.fiscal_years[0]?.toString() ?? "" });
        setView({ owner, generation, discovery: result.data, handle: null, phase: "ready", operation, message: null });
      } else {
        const handle = result.handle; state.handle = handle;
        state.unsubscribe = handle.subscribe(() => {
          // Getters can detect expiry during React's render. Notify outside that render.
          queueMicrotask(() => {
            if (!current() || state.handle !== handle) return;
            if (!handle.snapshot) {
              flight.current = null; pageFocus.current = null;
              setView(previous => current() && previous.handle === handle ? { ...previous, handle: null, phase: "closed", message: "Comparison closed or expired. Reload the comparison to continue." } : previous);
            }
            redraw(value => value + 1);
          });
        });
        if (!handle.snapshot) throw new Error("Closed comparison");
        if (!current()) return;
        readyQueued = true;
        setView({ owner, generation, discovery, handle, phase: "ready", operation, message: null });
      }
    } catch (failure) {
      if (!current()) return;
      prepareFocus();
      const code = (failure as { code?: string })?.code;
      setView({ owner, generation, discovery, handle: null, phase: "error", operation,
        message: code === "DATA_VERSION_CHANGED" ? "Published data changed. Wait for publication verification, then compare explicitly."
          : code === "REQUEST_TIMEOUT" ? "Annual insights timed out after the bounded request deadline. Retry explicitly."
            : "Annual financial insights could not be loaded or verified. Retry explicitly." });
    } finally {
      if (current() && !readyQueued) {
        state.pending = false;
        state.completeInitialization = null;
        if (state.deadline !== null) clearTimeout(state.deadline); state.deadline = null;
      }
    }
  }, [company.ticker, company.cik, owner, version, changed, invalidate]);

  useEffect(() => {
    if (version !== null) void begin("discover", null);
  }, [owner, version, begin]);

  const visible = view.owner === owner && view.generation === live.current.generation ? view : null;
  const discovery = visible?.discovery ?? null;
  const earlier = years.owner === owner ? years.earlier : "", later = years.owner === owner ? years.later : "";
  const valid = Boolean(discovery && earlier && later && Number(earlier) < Number(later)
    && discovery.fiscal_years.includes(Number(earlier)) && discovery.fiscal_years.includes(Number(later)));
  const loading = visible?.phase === "loading";
  const handle = visible?.handle ?? null, model = handle?.snapshot ?? null, page = model ? handle?.page ?? null : null;
  const paging = Boolean(flight.current);

  useLayoutEffect(() => {
    // Keep the initial budget active until READY actually commits, including a
    // delayed React commit after the request promise has already settled.
    if (visible?.phase === "ready" && live.current.completeInitialization && !live.current.completeInitialization()) return;
    const pending = returnFocus.current;
    if (pending && !loading) {
      returnFocus.current = null;
      if (pending.generation === live.current.generation && live.current.mounted && live.current.owner === owner
        && (document.activeElement === pending.trigger || !pending.trigger.isConnected && document.activeElement === document.body)) {
        const target = compareButton.current && !compareButton.current.disabled ? compareButton.current : retryButton.current;
        if (target?.isConnected && !target.disabled) target.focus();
      }
    }
    const destination = pageFocus.current;
    if (destination && handle === destination.handle && page?.collection === destination.target.collection && page.page === destination.target.page) {
      pageFocus.current = null;
      if (destination.generation !== live.current.generation || !live.current.mounted || live.current.owner !== owner || !handle.snapshot) return;
      if (evidenceDetails.current) evidenceDetails.current.open = true;
      if (document.activeElement !== destination.trigger && (destination.trigger.isConnected || document.activeElement !== document.body)) return;
      const target = destination.target.key ? Array.from(viewport.current?.querySelectorAll<HTMLElement>("[data-insight-key]") ?? [])
        .find(node => node.dataset.insightKey === destination.target.key) : viewport.current;
      target?.focus();
    }
  });

  function selectYear(side: "earlier" | "later", value: string) {
    invalidate(); setPageMessage(null); setYears({ owner, earlier, later, [side]: value });
    setView({ owner, generation: live.current.generation, discovery, handle: null, phase: "ready", operation: "compare", message: null });
  }
  function compare() {
    if (!valid || live.current.pending || flight.current) return;
    void begin("compare", discovery, { earlier: Number(earlier), later: Number(later) });
  }
  function cancel() {
    const focused = cancelButton.current && document.activeElement === cancelButton.current ? cancelButton.current : null;
    invalidate();
    if (focused) returnFocus.current = { trigger: focused, generation: live.current.generation };
    setView({ owner, generation: live.current.generation, discovery, handle: null, phase: "closed", operation: visible?.operation ?? "discover", message: "Annual insights cancelled. Retry explicitly when ready." });
  }
  function navigate(target: Target, trigger: HTMLElement) {
    if (!handle || !model || !handle.snapshot || live.current.handle !== handle) return;
    if (flight.current) {
      if (flight.current.collection === target.collection && flight.current.page === target.page) return flight.current.promise;
      setPageMessage("Another evidence page is loading. Wait for it to complete before navigating."); return;
    } // One viewport, no queue or visited-page cache.
    const generation = live.current.generation;
    const current = () => live.current.mounted && live.current.owner === owner && live.current.generation === generation
      && live.current.handle === handle && !live.current.controller?.signal.aborted;
    setPageMessage(null); handle.interact();
    const promise = handle.requestPage(target.collection, target.page).then(result => {
      if (!current() || !handle.snapshot || result.collection !== target.collection || result.page !== target.page) return;
      if (target.key && !result.records.some(record => record.ref.key === target.key)) { setPageMessage("The requested evidence reference is unavailable."); return; }
      pageFocus.current = { target, trigger, generation, handle };
    }).catch(() => { if (current()) setPageMessage("Evidence could not be loaded. Reload the comparison to continue."); })
      .finally(() => { if (current() && flight.current?.promise === promise) { flight.current = null; redraw(value => value + 1); } });
    flight.current = { collection: target.collection, page: target.page, promise }; redraw(value => value + 1);
    return promise;
  }
  function statement(statement: InsightsPresentation["statements"][number]) {
    return <div className="insights-statement" key={statement.key}><p>{statement.text}</p>
      {statement.targets.length > 0 && <div className="insights-links">{statement.targets.map((target, index) =>
        <button className="secondary-button" type="button" disabled={paging} key={target.key}
          onClick={event => navigate(target, event.currentTarget)}>{target.collection === "F" ? "Financial evidence" : "Diagnostic evidence"} {index + 1}</button>)}</div>}
    </div>;
  }
  return <section className="panel financial-insights" aria-labelledby="insights-title"
    onClick={() => handle?.interact()} onKeyDown={() => handle?.interact()}>
    <div className="section-heading"><div><p className="eyebrow">Annual research</p><h2 id="insights-title">Annual financial insights</h2></div><span className="badge">No AI required</span></div>
    <p className="small muted">Compare stored annual reporting periods. Supported fiscal years use the eleven-anchor discovery policy; availability does not guarantee complete financial coverage.</p>
    <p className="small"><a href="#snapshot-title">Financial snapshot</a>{" · "}<a href="#history-title">Historical trends</a>{" · "}<a href="#filing-title">SEC research</a></p>
    <form className="insights-form" onSubmit={event => { event.preventDefault(); compare(); }}>
      <div className="insights-controls">
        <label>Earlier fiscal year<select value={earlier} disabled={!discovery || loading && visible?.operation === "discover"} onChange={event => selectYear("earlier", event.target.value)}>
          <option value="">Select earlier year</option>{discovery?.fiscal_years.map(year => <option key={year} value={year}>{year}</option>)}
        </select></label>
        <label>Later fiscal year<select value={later} disabled={!discovery || loading && visible?.operation === "discover"} onChange={event => selectYear("later", event.target.value)}>
          <option value="">Select later year</option>{discovery?.fiscal_years.map(year => <option key={year} value={year}>{year}</option>)}
        </select></label>
      </div>
      <div className="insights-actions"><button ref={compareButton} className="primary-button" disabled={version === null || !valid || loading || paging}>Compare annual periods</button>
        {loading && <button ref={cancelButton} className="secondary-button" type="button" onClick={cancel}>Cancel annual insights</button>}
        {visible && ["error", "closed"].includes(visible.phase) && <button ref={retryButton} className="secondary-button" type="button" disabled={version === null || loading}
          onClick={() => { if (visible.operation === "compare" && valid) compare(); else void begin("discover", null); }}>
          {visible.operation === "compare" && valid ? "Reload annual comparison" : "Retry year discovery"}
        </button>}
      </div>
    </form>
    <div role="status" aria-live="polite" aria-busy={loading || paging} className="insights-status">
      {version === null ? "Waiting for a verified publication version…" : loading ? visible?.operation === "discover" ? "Discovering supported fiscal years…" : "Comparing annual periods…"
        : visible?.message ?? (model ? "Annual comparison ready. Evidence can be examined below." : discovery ? discovery.fiscal_years.length === 0 ? "No supported annual fiscal years were returned."
          : discovery.fiscal_years.length === 1 ? "Only one supported fiscal year was returned. Two distinct years are required."
            : !valid ? "Choose an earlier fiscal year before the later fiscal year. Years are never swapped automatically." : "Choose Compare annual periods to request this comparison." : "Preparing annual insights…")}
      {paging && <p>Loading the requested evidence page…</p>}{pageMessage && <p>{pageMessage}</p>}
    </div>
    {discovery && <details className="insights-policy"><summary>Publication and selection policy</summary>
      <p>{company.ticker} · CIK {company.cik} · publication {discovery.data_version} · facts {discovery.facts_version} · evidence {discovery.evidence_version}</p><p>{discovery.selection_policy}</p>
    </details>}
    {model && <div className="insights-result">
      <p className="insights-completeness">Five headline comparisons: {model.completeness}. Revenue, operating margin, net margin, operating cash flow and free cash flow.</p>
      <p className="small">Earlier: {periodText(model.periods.earlier)}<br />Later: {periodText(model.periods.later)}</p>
      <p className="mono">Publication {model.data_version} · facts {model.facts_version} · evidence {model.evidence_version} · {model.scope}</p>
      {model.statements.filter(s => s.rule === "OVERALL" || s.rule === "LIMITATION").map(statement)}
      <details className="insights-metrics"><summary>Seven comparison metrics and their evidence</summary>
        <div className="insights-metric-grid">{METRICS.map(([metric, label]) => {
          const calculated = model.metrics.find(item => item.metric === metric)?.calculated
            ?? ["operating_margin", "net_margin", "free_cash_flow"].includes(metric);
          return <article key={metric} data-insight-metric={metric}>
          <h3>{label}</h3><p className="small">{calculated ? "Calculated" : "Reported"}</p>
          <dl className="insights-values">{["earlier", "later"].map(side => {
            const value = model.metrics.find(item => item.metric === metric && item.side === side);
            return <div key={side}><dt>{side === "earlier" ? "Earlier" : "Later"}</dt><dd>{value?.formatted ?? "No admitted financial value"}</dd></div>;
          })}</dl>
          {model.statements.filter(s => s.metric === metric).map(statement)}
        </article>; })}</div>
      </details>
      <details ref={evidenceDetails} className="insights-evidence" open={Boolean(page)}><summary>Examine financial evidence and diagnostic inputs</summary>
        <div className="insights-collections">{model.collections.map(collection => <section key={collection.id}>
          <h3>{collectionLabel(collection.id)}</h3><p className="small">{collection.records} records · {collection.pages} pages.</p>
          <p className="small muted">{collection.id === "F" ? "Admitted financial observations and their source and operand lineage." : "Examined inputs include selected, rejected and alternative candidates. Diagnostic values are not admitted financial results."}</p>
          <button className="secondary-button" type="button" disabled={paging || collection.pages === 0} aria-pressed={page?.collection === collection.id}
            onClick={event => navigate({ collection: collection.id, page: 0 }, event.currentTarget)}>Examine {collection.id === "F" ? "financial evidence" : "diagnostic inputs"}</button>
        </section>)}</div>
        {page && <>
          <div className="insights-pagination" aria-label="Evidence pagination">
            <button className="secondary-button" type="button" disabled={paging || page.page === 0} onClick={event => navigate({ collection: page.collection, page: page.page - 1 }, event.currentTarget)}>Previous evidence page</button>
            <span>{page.collection} · page {page.page + 1} of {model.collections.find(c => c.id === page.collection)?.pages}</span>
            <button className="secondary-button" type="button" disabled={paging || page.page + 1 >= (model.collections.find(c => c.id === page.collection)?.pages ?? 0)} onClick={event => navigate({ collection: page.collection, page: page.page + 1 }, event.currentTarget)}>Next evidence page</button>
          </div>
          <div ref={viewport} className="insights-viewport" role="region" aria-labelledby={`${uid}-evidence-title`} aria-busy={paging} tabIndex={-1}>
            <h3 id={`${uid}-evidence-title`}>{collectionLabel(page.collection)}</h3>
            {page.records.map(record => <EvidenceRecord key={record.ref.key} record={record} disabled={paging} navigate={navigate} />)}
          </div>
        </>}
      </details>
    </div>}
  </section>;
}
