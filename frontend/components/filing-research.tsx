"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { citationForClaim, describeApiError, getAnswer, getFilingContext, getFilingSources, getResearchAnswer, searchableFilings,
  type Company, type FilingAnswer, type FilingContext, type FilingSource, type ResearchAnswer } from "@/lib/finlens-api";
import { AI_UNAVAILABLE, createRequestScope, evidencePassages, formatDate, officialSecUrl } from "@/lib/research";
import DirectResearchAnswer from "@/components/research-answer";

const EXAMPLES = ["revenue growth", "gross margin", "supply constraints", "artificial intelligence"];

export function EvidenceResults({ result }: { result: FilingContext }) {
  const passages = evidencePassages(result);
  return <div className="evidence-results" aria-live="polite">
    <div className="section-heading"><h3>{passages.length ? `${passages.length} SEC evidence passages` : "Insufficient evidence in this filing"}</h3><span className="badge">Research Mode</span></div>
    <p className="muted small">Search: “{result.query}” · Evidence is retrieved text, not an AI answer or a guarantee of claim support.</p>
    {passages.length === 0 && <div className="empty-state"><p>Try a more specific financial topic. FinLens does not substitute model knowledge when filing evidence is weak.</p></div>}
    {passages.map(({ citation, text, rank }) => <article className="evidence-card" key={citation.citation_id}>
      <div className="evidence-heading"><h4>Evidence {rank} <span className="muted">· {citation.form}</span></h4><span className="small muted">Filed {formatDate(citation.filed)}</span></div>
      <p className="excerpt">{text.length > 650 ? `${text.slice(0, 650)}…` : text}</p>
      {text.length > 650 && <details className="provenance"><summary>Read full evidence passage</summary><p className="excerpt details-body">{text}</p></details>}
      {officialSecUrl(citation.sec_url) && <a className="source-link" href={officialSecUrl(citation.sec_url)} target="_blank" rel="noopener noreferrer">Open official SEC source ↗</a>}
      <details className="provenance"><summary>Filing and retrieval details</summary><div className="details-body wrap-anywhere">
        <p>{citation.citation_id} · {citation.chunk_id} · {citation.filename}</p>
        <p className="mono">Accession {citation.accession_number}</p>
        <p>Cleaned text offsets: {citation.start_char.toLocaleString()}–{citation.end_char.toLocaleString()}</p>
        <p>Hybrid rank {rank} · Retrieval rule: {citation.evidence_reason.replaceAll("_", " ")}</p>
        <p>Scores describe retrieval ranking, not factual confidence.</p>
      </div></details>
    </article>)}
  </div>;
}

export function AIAnalysis({ result, configured }: { result: FilingContext; configured: boolean }) {
  const [answer, setAnswer] = useState<FilingAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const scope = useRef(createRequestScope());
  useEffect(() => {
    const currentScope = scope.current;
    return () => { currentScope.invalidate(); controller.current?.abort(); };
  }, []);
  async function analyze() {
    if (!configured || result.evidence_status !== "sufficient" || loading) return;
    controller.current?.abort(); controller.current = new AbortController();
    const id = scope.current.start();
    setLoading(true); setMessage(null); setAnswer(null);
    try {
      const response = await getAnswer(result.ticker, result.accession_number, result.query, 5, controller.current.signal);
      if (scope.current.current(id)) setAnswer(response);
    } catch {
      if (scope.current.current(id)) setMessage(AI_UNAVAILABLE);
    } finally { if (scope.current.current(id)) setLoading(false); }
  }
  return <section className="ai-panel" aria-labelledby="ai-title">
    <div className="section-heading"><div><p className="eyebrow">Optional enhancement</p><h3 id="ai-title">AI Analysis</h3></div><span className="badge neutral">{configured ? "Configured · availability may vary" : "Not configured"}</span></div>
    <p className="muted small">Generate a grounded explanation from the filing evidence. Research Mode works independently.</p>
    {!configured && <p className="notice">AI analysis is not configured. Financial data and SEC evidence remain available.</p>}
    <button type="button" className="secondary-button" onClick={analyze} disabled={!configured || loading || result.evidence_status !== "sufficient"}>{loading ? "Preparing optional analysis…" : "Generate AI analysis"}</button>
    <div aria-live="polite" aria-busy={loading}>
      {message && <p className="notice">{message}</p>}
      {answer?.evidence_status === "insufficient" && <p className="notice">Insufficient evidence for a generated answer. The retrieved passages and any direct financial answer remain available.</p>}
      {answer?.evidence_status === "sufficient" && <div className="ai-answer">
        <h4>Answer</h4><p className="excerpt">{answer.answer}</p>
        <h4>Claims and citations</h4><ol className="claims">{answer.claims.map((claim, index) => <li key={index}><p>{claim.text}</p><div className="citation-links">{claim.citation_ids.map((id) => {
          const citation = citationForClaim(id, answer.citations);
          return citation && officialSecUrl(citation.sec_url) ? <a key={id} href={`#ai-${id}`}>{id}</a> : null;
        })}</div></li>)}</ol>
        <h4>Sources</h4>{answer.citations.map((citation) => <div className="source-record" id={`ai-${citation.citation_id}`} key={citation.citation_id}>
          <p>{citation.citation_id} · {citation.form} · Filed {formatDate(citation.filed)}</p><p className="small mono wrap-anywhere">{citation.accession_number} · {citation.chunk_id}</p>
          {officialSecUrl(citation.sec_url) && <a href={officialSecUrl(citation.sec_url)} target="_blank" rel="noopener noreferrer">Open official SEC filing ↗</a>}
        </div>)}<p className="muted small">Generated by {answer.model}. Verify factual claims against the supplied sources.</p>
      </div>}
    </div>
  </section>;
}

function FilingSearch({ company, filing, configured }: { company: Company; filing: FilingSource | null; configured: boolean }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<FilingContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<ResearchAnswer | null>(null);
  const [answerLoading, setAnswerLoading] = useState(false);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const scope = useRef(createRequestScope());
  useEffect(() => {
    const currentScope = scope.current;
    return () => { currentScope.invalidate(); controller.current?.abort(); };
  }, []);
  function edit(value: string) {
    scope.current.invalidate(); controller.current?.abort();
    setQuery(value); setResult(null); setLoading(false); setError(null);
    setAnswer(null); setAnswerLoading(false); setAnswerError(null);
  }
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!query.trim() || answerLoading || loading) return;
    const id = scope.current.start();
    controller.current?.abort(); controller.current = new AbortController();
    setLoading(Boolean(filing)); setError(null); setResult(null);
    setAnswerLoading(true); setAnswerError(null); setAnswer(null);
    const signal = controller.current.signal;
    const question = query.trim();
    // Settle each branch independently: a slow/failed context must never delay
    // or erase a valid direct answer, and answer failure cannot erase evidence.
    const direct = getResearchAnswer(company.ticker, question, signal).then(response => {
      if (scope.current.current(id) && response.ticker === company.ticker && response.question === question) setAnswer(response);
    }).catch(failure => { if (scope.current.current(id)) setAnswerError(describeApiError(failure)); })
      .finally(() => { if (scope.current.current(id)) setAnswerLoading(false); });
    const evidence = filing ? getFilingContext(company.ticker, filing.accession_number, question, signal).then(response => {
      if (scope.current.current(id) && response.ticker === company.ticker && response.accession_number === filing.accession_number && response.query === question) setResult(response);
    }).catch(failure => { if (scope.current.current(id)) setError(describeApiError(failure)); })
      .finally(() => { if (scope.current.current(id)) setLoading(false); }) : Promise.resolve();
    await Promise.all([direct, evidence]);
  }
  return <>
    {filing && <div className="filing-record"><strong>{filing.form ?? "SEC filing"}</strong><span>Filed {formatDate(filing.filed)}</span>
      <p className="mono small wrap-anywhere">Accession {filing.accession_number}</p>
      {officialSecUrl(filing.sec_url) && <a href={officialSecUrl(filing.sec_url)} target="_blank" rel="noopener noreferrer">Open official filing ↗</a>}
    </div>}
    <form onSubmit={search} className="search-form">
      <label htmlFor="research-query">Research question or search<textarea id="research-query" value={query} maxLength={2000} onChange={(event) => edit(event.target.value)} placeholder="What was the latest quarterly revenue?" rows={3} /></label>
      <div className="question-chips" aria-label="Example research topics">{EXAMPLES.map((example) => <button type="button" key={example} onClick={() => edit(example)}>{example}</button>)}</div>
      <button className="primary-button" disabled={!query.trim() || loading || answerLoading}>{loading || answerLoading ? "Researching stored SEC data…" : "Research question"}</button>
      <p className="muted small">Clear latest quarterly, annual or latest available financial values can receive a direct answer. Other questions search SEC evidence. No AI generation.</p>
    </form>
    <div aria-live="polite" aria-busy={answerLoading}>
      {answerLoading && <p className="loading-state">Checking stored financial observations…</p>}
      {answerError && <p className="notice">Direct financial answer unavailable: {answerError} SEC evidence research continues independently.</p>}
      {answer?.matched && <DirectResearchAnswer answer={answer} />}
      {answer?.status === "company_mismatch" && <p className="notice">{answer.explanation}</p>}
      {answer?.status === "not_matched" && <p className="muted small">SEC evidence research · this question is outside supported direct financial answers.</p>}
    </div>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p className="loading-state">Finding relevant passages in this filing…</p>}
      {error && <p role="alert" className="error-state">{error}</p>}
      {!result && !answer && !loading && !answerLoading && !error && <div className="empty-state"><h3>Explore the filing evidence</h3><p>Choose a topic, read the retrieved passages, and follow the official SEC links. No OpenAI access is required.</p></div>}
    </div>
    {result && <><h3>Supporting SEC evidence</h3><p className="small muted">Selected filing only · accession {result.accession_number}. Passages are supporting research, not validation of the structured answer.</p><EvidenceResults result={result} /><AIAnalysis key={`${result.query}-${result.accession_number}`} result={result} configured={configured} /></>}
  </>;
}

export default function FilingResearch({ company, configured }: { company: Company; configured: boolean }) {
  const [filings, setFilings] = useState<FilingSource[]>([]);
  const [accession, setAccession] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    getFilingSources(company.ticker, controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      const indexed = searchableFilings(data); setFilings(indexed); setAccession(indexed[0]?.accession_number ?? "");
    }).catch((failure) => { if (!controller.signal.aborted) setError(describeApiError(failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [company.ticker]);
  const filing = filings.find((item) => item.accession_number === accession);
  return <section className="panel filing-panel" aria-labelledby="filing-title">
    <div className="section-heading"><div><p className="eyebrow">SEC research</p><h2 id="filing-title">Read the evidence</h2></div><span className="badge">No AI required</span></div>
    <p className="muted small">Search an indexed filing. Metric snapshots may refer to a different period or accession.</p>
    <label className="filing-select">Indexed SEC filing<select value={accession} onChange={(event) => setAccession(event.target.value)} disabled={loading || !filings.length || !company.has_indexed_filing}>
      {loading && <option value="">Loading filings…</option>}
      {!loading && !filings.length && <option value="">No indexed filing available</option>}
      {filings.map((item) => <option key={item.accession_number} value={item.accession_number}>{item.form ?? "SEC filing"} · {formatDate(item.filed)}</option>)}
    </select></label>
    {error && <p role="alert" className="error-state">{error}</p>}
    {!loading && !error && (!company.has_indexed_filing || !filing) && <div className="empty-state"><h3>Not indexed for filing research</h3><p>Financial research remains available. Choose a Ready company to search stored filing evidence.</p></div>}
    {!loading && <FilingSearch key={`${company.ticker}-${accession}`} company={company} filing={company.has_indexed_filing ? filing ?? null : null} configured={configured} />}
  </section>;
}
