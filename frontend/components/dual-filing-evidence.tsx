"use client";
import { useLayoutEffect, useId, useRef, useState, type FormEvent } from "react";
import { getFilingContext, versionedController, FinLensApiError, type Company, type FilingContext, type FilingSource } from "@/lib/finlens-api";
import { comparisonFilings, validateComparisonEvidence, type ComparisonFiling } from "@/lib/dual-filing-evidence";
import { evidencePassages, formatDate } from "@/lib/research";
import { useResearchVersion } from "@/components/research-freshness";
import FilingPassageComparison from "@/components/filing-passage-comparison";

type Column = { filing: ComparisonFiling; status: "pending" | "ready" | "error"; result?: FilingContext; message?: string };
type Snapshot = { owner: string; generation: number; columns: Column[] };

export default function DualFilingEvidence({ company, sources }: { company: Company; sources: FilingSource[] }) {
  const { version, changed } = useResearchVersion();
  const id = useId();
  const choices = comparisonFilings(company, sources);
  const [selection, setSelection] = useState<[string, string] | null>(null);
  const [query, setQuery] = useState("");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const selected = selection ?? [choices?.[0]?.accession_number ?? "", choices?.[1]?.accession_number ?? ""];
  const filings = selected.map(acc => choices?.find(item => item.accession_number === acc));
  const owner = JSON.stringify([company.ticker, company.cik, company.name, version, choices, selected, query]);
  const live = useRef({ owner, generation: 0, mounted: true, transport: null as AbortController | null });
  const invalidate = () => { live.current.generation++; live.current.transport?.abort(); live.current.transport = null; };
  // Revoke ownership during render as well as input events, before passive cleanup.
  if (live.current.owner !== owner) { invalidate(); live.current.owner = owner; }
  useLayoutEffect(() => {
    const lifecycle = live.current; lifecycle.mounted = true;
    return () => { lifecycle.mounted = false; lifecycle.generation++; lifecycle.transport?.abort(); lifecycle.transport = null; };
  }, []);
  const visible = snapshot?.owner === owner && snapshot.generation === live.current.generation ? snapshot : null;
  const pending = visible?.columns.some(column => column.status === "pending") ?? false;
  const ready = version !== null && Number.isSafeInteger(version) && version >= 0 && !Object.is(version, -0)
    && choices !== null && filings.every(Boolean) && selected[0] !== selected[1] && query.trim().length > 0 && query.length <= 2000;
  function editSelection(index: number, value: string) {
    invalidate(); setSnapshot(null); live.current.owner = ""; const next: [string, string] = [...selected]; next[index] = value; setSelection(next);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (live.current.owner !== owner || !ready || version === null || live.current.transport || !filings[0] || !filings[1]) return;
    const generation = ++live.current.generation, captured = filings as ComparisonFiling[], question = query.trim();
    const current = () => live.current.mounted && live.current.owner === owner && live.current.generation === generation && !transport.signal.aborted;
    const transport = versionedController(version, () => {
      if (!current()) return;
      // A stale publication makes both sides unusable, including an already settled side.
      invalidate(); setSnapshot(null); changed();
    });
    live.current.transport = transport; // Reserve synchronously before any promise or render.
    setSnapshot({ owner, generation, columns: captured.map(filing => ({ filing, status: "pending" })) });
    await Promise.allSettled(captured.map(async (filing, index) => {
      let column: Column;
      try {
        const result = await getFilingContext(company.ticker, filing.accession_number, question, transport.signal, true);
        if (!current()) return;
        validateComparisonEvidence(result, company, filing, question, version);
        column = { filing, status: "ready", result };
      } catch (failure) {
        if (!current()) return;
        column = { filing, status: "error", message: failure instanceof FinLensApiError && failure.code === "REQUEST_TIMEOUT"
          ? "This filing search timed out. Submit again to retry both filings."
          : "Evidence for this filing is unavailable or could not be verified. Submit again to retry both filings." };
      }
      if (current()) setSnapshot(previous => previous?.owner === owner && previous.generation === generation
        ? { ...previous, columns: previous.columns.map((item, position) => position === index ? column : item) } : previous);
    }));
    if (current()) live.current.transport = null;
  }
  return <section className="dual-filing-evidence" aria-labelledby={`${id}-title`}>
    <div className="section-heading"><h3 id={`${id}-title`}>Compare two filing sources</h3><span className="badge">No AI required</span></div>
    <p id={`${id}-help`} className="muted small">Ask one question of two indexed filings for {company.name}. Read the original excerpts independently. Retrieval does not establish a change, cause, amendment relationship or aligned reporting periods. Filing dates are not reporting periods.</p>
    <form onSubmit={submit} aria-describedby={`${id}-help`}>
      <div className="dual-filing-controls">{selected.map((value, index) => <div key={index}><label>Filing {index === 0 ? "A" : "B"}<select value={value} aria-describedby={`${id}-selected-accession-${index}`} disabled={!choices || choices.length < 2 || version === null}
        onChange={event => editSelection(index, event.target.value)}>
        <option value="">Select an indexed filing</option>{choices?.map(item => <option key={item.accession_number} value={item.accession_number}>{item.form} · {formatDate(item.filed)} · {item.accession_number}</option>)}
      </select></label><p id={`${id}-selected-accession-${index}`} className="dual-filing-selection small mono wrap-anywhere">{version !== null && choices && choices.length >= 2 && filings[index]
        ? `Accession ${filings[index]?.accession_number}` : "No verified indexed filing selected."}</p></div>)}</div>
      <label className="filing-select">Question for both filings<textarea value={query} maxLength={2000} rows={3} onChange={event => { invalidate(); setSnapshot(null); live.current.owner = ""; setQuery(event.target.value); }} /></label>
      <p className="small muted">Up to five bounded excerpts of stored cleaned text per filing; these are not complete filings. Retrieval thresholds may omit relevant passages. Source references are local to each accession; matching ranks do not imply equivalent disclosures or factual support.</p>
      {version === null ? <p className="notice">Verify the company’s published data before comparing filings.</p>
        : choices === null ? <p className="notice">The indexed filing list could not be verified within the comparison limits (100 indexed filings). Comparison is unavailable.</p>
          : choices.length < 2 ? <p className="notice">Two indexed filings are required for this company. No filings will be downloaded by this view.</p>
            : selected[0] === selected[1] && <p className="notice">Choose two distinct indexed filings.</p>}
      <div className="dual-filing-actions"><button className="primary-button" disabled={!ready || pending}>Compare filing evidence</button>
        <button className="secondary-button" type="button" aria-disabled={!pending} onClick={() => { if (pending) { invalidate(); setSnapshot(null); } }}>Cancel filing comparison</button></div>
    </form>
    <div className="small" role="status" aria-live="polite">{pending ? "Searching both selected filings. Results settle independently." : visible ? "Filing searches settled. Inspect each source separately; no comparison conclusion is generated." : "Select two filings and submit a question. Edits clear both results; searches run only on submit."}</div>
    {visible && <><p className="small wrap-anywhere">{company.ticker} · CIK {company.cik} · Publication {version} · Question: “{query.trim()}”</p>
      {visible.columns[0]?.status === "ready" && visible.columns[1]?.status === "ready"
        && visible.columns[0].result && visible.columns[1].result
        && <FilingPassageComparison key={visible.generation} results={[visible.columns[0].result, visible.columns[1].result]} />}
      <div className="dual-filing-columns">{visible.columns.map((column, index) => <section className="dual-filing-column" key={column.filing.accession_number} aria-labelledby={`${id}-filing-${index}`} aria-busy={column.status === "pending"}>
        <h4 id={`${id}-filing-${index}`}>Filing {index === 0 ? "A" : "B"} · {column.filing.form}</h4>
        <p className="small">Filed {formatDate(column.filing.filed)}</p><p className="small mono wrap-anywhere">Accession {column.filing.accession_number}</p>
        <a className="source-link" href={column.filing.sec_url} target="_blank" rel="noopener noreferrer">Open official SEC filing index ↗</a>
        {column.status === "pending" && <p role="status">Searching this filing…</p>}
        {column.message && <p role="alert" className="error-state">{column.message}</p>}
        {column.result?.evidence_status === "insufficient" && <p className="notice">Insufficient evidence in this filing. No qualifying excerpts were returned. This does not establish absence from the complete filing.</p>}
        {column.result && evidencePassages(column.result).map(({ citation, text, rank }) => <article className="evidence-card" key={`${citation.accession_number}/${citation.citation_id}`}>
          <h5>Excerpt {rank}</h5><p className="excerpt">{text}</p>
          <details className="provenance"><summary>Filing {index === 0 ? "A" : "B"} excerpt {rank} source details</summary><div className="details-body wrap-anywhere">
            <p>Reference {citation.accession_number}/{citation.citation_id}</p><p>{citation.chunk_id} · {citation.filename}</p>
            <p>CIK {company.cik} · {citation.form} · Filed {formatDate(citation.filed)}</p>
            <p>Cleaned text offsets: {citation.start_char}–{citation.end_char}</p><p>Retrieval rule: {citation.evidence_reason.replaceAll("_", " ")}. Scores describe ranking, not factual confidence.</p>
            <a className="source-link" href={citation.sec_url} target="_blank" rel="noopener noreferrer">Open official SEC source ↗</a>
          </div></details>
        </article>)}
      </section>)}</div>
    </>}
  </section>;
}
