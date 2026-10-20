"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import type { Company } from "@/lib/finlens-api";
import { RISK_EXPLANATION, RISK_TOPICS } from "@/lib/sec-risk";
import { comparisonChoices, comparisonIssuers, createRiskComparison, preferredRiskSelection, type RiskComparisonSnapshot } from "@/lib/sec-risk-comparison";
import { EvidenceResults } from "@/components/filing-research";

export default function SecRiskComparison({ companies }: { companies: Company[] }) {
  const [selection, setSelection] = useState<[string, string] | null>(null);
  const [topic, setTopic] = useState("supply_chain");
  const [snapshot, setSnapshot] = useState<RiskComparisonSnapshot | null>(null);
  const submitButton = useRef<HTMLButtonElement | null>(null);
  const cancelButton = useRef<HTMLButtonElement | null>(null);
  const focusRun = useRef<{ owner: string; generation: number; pending: boolean } | null>(null);
  const restoreSubmitFocus = useRef<{ owner: string; generation: number; document: Document } | null>(null);
  const tickers = selection ?? preferredRiskSelection(companies);
  const issuers = comparisonIssuers(companies, tickers);
  const owner = JSON.stringify([tickers, issuers, topic]);
  const liveOwner = useRef(owner);
  // Catalog changes can render before passive cleanup; callbacks lose ownership now.
  liveOwner.current = owner;
  const [comparison] = useState(() => createRiskComparison({ currentOwner: () => liveOwner.current, publish: setSnapshot }));
  useEffect(() => {
    comparison.activate();
    return () => { restoreSubmitFocus.current = null; comparison.deactivate(); };
  }, [comparison]);
  useEffect(() => { comparison.reconcile(); }, [comparison, owner]);
  const visible = snapshot?.owner === owner ? snapshot : null;
  const pending = visible?.columns.some(column => column.status === "pending") ?? false;
  const focusGeneration = visible?.generation;
  focusRun.current = visible ? { owner, generation: visible.generation, pending } : null;
  const cancelRef = useCallback((node: HTMLButtonElement | null) => {
    const previous = cancelButton.current, run = focusRun.current;
    // Ref detachment observes focus before DOM removal. Only a settlement of
    // this attached button's current run can request a transfer after commit.
    if (!node && previous?.isConnected && previous.ownerDocument.activeElement === previous
        && run && !run.pending && run.owner === owner && run.generation === focusGeneration && liveOwner.current === owner) {
      restoreSubmitFocus.current = { owner, generation: run.generation, document: previous.ownerDocument };
    }
    cancelButton.current = node;
  }, [owner, focusGeneration]);
  useLayoutEffect(() => {
    const transfer = restoreSubmitFocus.current, run = focusRun.current, target = submitButton.current;
    restoreSubmitFocus.current = null;
    if (transfer && run && !run.pending && run.owner === transfer.owner && run.generation === transfer.generation
        && liveOwner.current === transfer.owner && target?.isConnected && !target.disabled
        && target.ownerDocument === transfer.document && transfer.document.activeElement === transfer.document.body) target.focus();
  }, [pending, owner, focusGeneration]);
  const incomplete = visible?.columns.some(column => ["error", "timeout", "cancelled", "no_publications"].includes(column.status));
  function edit(next: [string, string], nextTopic = topic) {
    // Revoke synchronously, including callbacks interleaved before React commits.
    liveOwner.current = JSON.stringify([next, comparisonIssuers(companies, next), nextTopic]);
    restoreSubmitFocus.current = null;
    comparison.invalidate(); setSelection(next); setTopic(nextTopic);
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (issuers) comparison.submit(issuers, topic, owner);
  }
  return <section className="panel sec-risk-comparison" aria-labelledby="risk-comparison-title">
    <div className="section-heading"><div><p className="eyebrow">Stored issuer disclosures</p><h2 id="risk-comparison-title">Compare SEC risk evidence</h2></div><span className="badge">Research Mode</span></div>
    <p className="muted small" id="risk-comparison-help">Compare source passages for one topic. Published filings may cover different dates, forms and periods; reporting-period alignment has not been established. Filing date is not the economic reporting period.</p>
    <p className="muted small">{RISK_EXPLANATION}</p>
    <form onSubmit={submit} aria-describedby="risk-comparison-help" className="risk-comparison-form">
      <div className="risk-comparison-controls">{tickers.map((ticker, index) => <label key={index}>{`Issuer ${index === 0 ? "A" : "B"}`}<select value={ticker} onChange={event => {
        const next: [string, string] = [...tickers]; next[index] = event.target.value; edit(next);
      }}><option value="">Select an issuer</option>{comparisonChoices(companies).map(issuer => <option key={issuer.ticker} value={issuer.ticker}>{issuer.ticker} · {issuer.name}</option>)}</select></label>)}
        <label>Comparison risk topic<select value={topic} onChange={event => edit([...tickers], event.target.value)}>{RISK_TOPICS.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label>
      </div>
      <p className="small">Search scope: <strong>Company-wide published filings</strong> · Up to five passages per issuer, initially showing two.</p>
      {!issuers && <p className="notice">Select exactly two distinct issuers with verified catalog identities. Ticker aliases for the same CIK cannot be compared.</p>}
      <div className="risk-comparison-actions"><button ref={submitButton} className="primary-button" disabled={!issuers || pending}>Compare SEC evidence</button>
        {pending && <button ref={cancelRef} className="secondary-button" type="button" onClick={() => comparison.cancel()}>Cancel evidence comparison</button>}</div>
    </form>
    <div role="status" aria-live="polite" className="risk-comparison-status">{visible ? pending
      ? "Comparison in progress. Each issuer's verified result appears independently."
      : incomplete ? "Comparison incomplete. Verified results remain available; submit again to retry."
      : "Topic searches completed for both issuers. This is a source comparison, not a comparative risk assessment."
      : "Choose two issuers and a topic, then submit to search. Selection changes do not run searches."}</div>
    {visible && <>
      <p className="small muted">Requested {visible.capturedAt}. Each company has an independent data snapshot. These versions are company-level data/evidence versions, not individual filing digests or publication versions. Submit again to reverify; subsequent data changes are not monitored here.</p>
      <p className="small muted">Passage ranks are local to each issuer. Matching rank numbers do not establish equivalent disclosures, risk severity, probability, relative safety or factual confidence.</p>
      <div className="risk-comparison-columns">{visible.columns.map((column, index) => <section key={`${visible.generation}-${index}`} className="risk-comparison-column" aria-labelledby={`risk-comparison-issuer-${index}`} aria-busy={column.status === "pending"}>
        <h3 id={`risk-comparison-issuer-${index}`}>Issuer {index === 0 ? "A" : "B"} · {column.issuer.ticker}</h3>
        <p className="small">{column.issuer.name} · CIK {column.issuer.cik}</p>
        {column.pin && <p className="small mono">Data version {column.pin.dataVersion} · Evidence version {column.pin.evidenceVersion}</p>}
        {column.status === "pending" && <p role="status">Verifying stored evidence for {column.issuer.ticker}…</p>}
        {column.message && <p className="error-state" role={column.status === "cancelled" ? "status" : "alert"}>{column.message}</p>}
        {column.result && <>
          <p className="small muted">{column.result.searched_accessions.length} eligible published filings searched. {column.result.excluded_publication_count} publications excluded by the eligibility checks. This is not a complete count of pending or unpublished filings; zero exclusions does not establish complete source coverage.</p>
          {column.status === "no_publications" ? <p className="notice">No qualifying published evidence available to search. This does not establish that the issuer has no filings or no business risk.</p>
            : column.status === "insufficient" ? <p className="notice">Insufficient topic evidence. No qualifying passages were returned in the searched scope. No result does not mean no risk.</p>
            : <EvidenceResults result={column.result} risk={true} />}
        </>}
      </section>)}</div>
    </>}
  </section>;
}
