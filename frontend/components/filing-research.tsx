"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { citationForClaim, describeApiError, FinLensApiError, versionedController, getAnswer, getFilingContext, getFilingSources, getResearchAnswer, searchableFilings, filingReadiness,
  getCompanyContext, type Company, type FilingAnswer, type FilingContext, type EvidenceContext, type FilingSource, type ResearchAnswer } from "@/lib/finlens-api";
import { AI_UNAVAILABLE, createRequestScope, evidencePassages, formatDate, officialSecUrl, METRIC_CATALOG, METRIC_GROUPS, QUESTION_SCOPE_LABELS, guidedQuestion, type QuestionScope } from "@/lib/research";
import DirectResearchAnswer from "@/components/research-answer";
import { evidenceExcerpt } from "@/lib/evidence-presentation";

import { useResearchVersion } from "@/components/research-freshness";

const EXAMPLES = ["revenue growth", "gross margin", "supply constraints", "artificial intelligence"];

export function EvidenceResults({ result, answer }: { result: EvidenceContext; answer?: ResearchAnswer | null }) {
  const [expanded, setExpanded] = useState(false);
  const passages = evidencePassages(result);
  const previews = passages.map(passage => ({ ...passage, excerpt: evidenceExcerpt(passage.text, result.query, answer, passages.map(item => item.text)) }));
  return <div className="evidence-results" aria-live="polite">
    <div className="section-heading"><h3>{passages.length ? `${passages.length} SEC evidence passages` : "retrieval_scope" in result ? "Insufficient evidence in published company filings" : "Insufficient evidence in this filing"}</h3><span className="badge">Research Mode</span></div>
    <p className="muted small">Search: “{result.query}” · Highlights mark matching text, not verified claim support. Excerpts retain the source wording.</p>
    {passages.length === 0 && <div className="empty-state"><p>Try a more specific financial topic. FinLens does not substitute model knowledge when filing evidence is weak.</p></div>}
    <div id="ranked-evidence">{previews.slice(0, expanded ? previews.length : 2).map(({ citation, text, rank, excerpt }) => <article className="evidence-card" key={citation.citation_id}>
      <div className="evidence-heading"><h4>Evidence {rank} <span className="muted">· {citation.form}</span></h4><span className="small muted">Filed {formatDate(citation.filed)}</span></div>
      <p className="excerpt evidence-preview">{excerpt.start > 0 && "… "}{excerpt.parts.map((part, index) => part.kind ? <mark key={index} className={`evidence-highlight ${part.kind === "value" ? "value-match" : ""}`}>{part.text}</mark> : part.text)}{excerpt.end < text.length && " …"}</p>
      <details className="provenance"><summary>Read full evidence passage</summary><p className="excerpt details-body">{text}</p></details>
      {officialSecUrl(citation.sec_url) && <a className="source-link" href={officialSecUrl(citation.sec_url)} target="_blank" rel="noopener noreferrer">Open official SEC source ↗</a>}
      <details className="provenance"><summary>Filing and retrieval details</summary><div className="details-body wrap-anywhere">
        <p>{citation.citation_id} · {citation.chunk_id} · {citation.filename}</p>
        <p className="mono">Accession {citation.accession_number}</p>
        {citation.company_cik && <p className="mono">CIK {citation.company_cik}</p>}
        <p>Cleaned text offsets: {citation.start_char.toLocaleString()}–{citation.end_char.toLocaleString()}</p>
        <p>Hybrid rank {rank} · Retrieval rule: {citation.evidence_reason.replaceAll("_", " ")}</p>
        <p>Scores describe retrieval ranking, not factual confidence.</p>
      </div></details>
    </article>)}</div>
    {passages.length > 2 && <button type="button" className="secondary-button evidence-toggle" aria-expanded={expanded} aria-controls="ranked-evidence" onClick={() => setExpanded(!expanded)}>{expanded ? "Show less evidence" : `Show more evidence (${passages.length - 2})`}</button>}
  </div>;
}

export function AIAnalysis({ result, configured }: { result: FilingContext; configured: boolean }) {
  const { version, changed } = useResearchVersion();
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
    if (version === null || !configured || result.evidence_status !== "sufficient" || loading) return;
    controller.current?.abort(); controller.current = versionedController(version, changed);
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
    <button type="button" className="secondary-button" onClick={analyze} disabled={version === null || !configured || loading || result.evidence_status !== "sufficient"}>{loading ? "Preparing optional analysis…" : "Generate AI analysis"}</button>
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

function FilingSearch({ company, filing, configured, query, setQuery, retrievalScope, companyEvidenceReady }: {
  company: Company; filing: FilingSource | null; configured: boolean;
  retrievalScope: "filing" | "company";
  query: string; setQuery: (value: string) => void;
  companyEvidenceReady: boolean;
}) {
  const { version, changed } = useResearchVersion();
  const [result, setResult] = useState<EvidenceContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<ResearchAnswer | null>(null);
  const [answerLoading, setAnswerLoading] = useState(false);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [guideMetric, setGuideMetric] = useState("revenue");
  const [guideScope, setGuideScope] = useState<QuestionScope>("latest_available");
  const questionInput = useRef<HTMLTextAreaElement | null>(null);
  const presentation = METRIC_CATALOG.find(item => item.id === guideMetric)!;
  const preparedQuestion = guidedQuestion(guideMetric, guideScope);
  const controller = useRef<AbortController | null>(null);
  const scope = useRef(createRequestScope());
  const evidenceController = useRef<AbortController | null>(null);
  const evidenceScope = useRef(createRequestScope());
  const answerPending = useRef(false);
  const evidencePending = useRef(false);
  const evidenceIdentity = retrievalScope === "company" ? (companyEvidenceReady ? "company" : "company-unavailable") : filing?.accession_number ?? "";
  const [searchedEvidence, setSearchedEvidence] = useState(evidenceIdentity);
  useEffect(() => {
    const currentScope = scope.current;
    const currentEvidenceScope = evidenceScope.current;
    return () => {
      currentScope.invalidate(); controller.current?.abort();
      currentEvidenceScope.invalidate(); evidenceController.current?.abort();
    };
  }, []);
  const [searchedVersion, setSearchedVersion] = useState(version);
  useEffect(() => {
    scope.current.invalidate(); controller.current?.abort();
    evidenceScope.current.invalidate(); evidenceController.current?.abort();
    answerPending.current = false; evidencePending.current = false;
    setResult(null); setAnswer(null); setLoading(false); setAnswerLoading(false);
    setError(null); setAnswerError(null);
  }, [version]);
  useEffect(() => {
    // Filing/scope changes cannot erase a valid independent financial answer.
    evidenceScope.current.invalidate(); evidenceController.current?.abort();
    evidencePending.current = false;
    setResult(null); setLoading(false); setError(null);
  }, [evidenceIdentity]);
  function edit(value: string) {
    scope.current.invalidate(); controller.current?.abort();
    evidenceScope.current.invalidate(); evidenceController.current?.abort();
    answerPending.current = false; evidencePending.current = false;
    setQuery(value); setResult(null); setLoading(false); setError(null);
    setAnswer(null); setAnswerLoading(false); setAnswerError(null);
  }
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (version === null || !query.trim() || answerPending.current || evidencePending.current) return;
    setSearchedVersion(version);
    const id = scope.current.start();
    controller.current?.abort(); controller.current = versionedController(version, changed);
    const evidenceId = evidenceScope.current.start();
    evidenceController.current?.abort(); evidenceController.current = versionedController(version, changed);
    const companyWide = retrievalScope === "company" && companyEvidenceReady;
    const selectedFiling = retrievalScope === "filing" ? filing : null;
    answerPending.current = true; evidencePending.current = companyWide || Boolean(selectedFiling);
    setSearchedEvidence(evidenceIdentity);
    setLoading(companyWide || Boolean(selectedFiling)); setError(null); setResult(null);
    setAnswerLoading(true); setAnswerError(null); setAnswer(null);
    const signal = controller.current.signal;
    const evidenceSignal = evidenceController.current.signal;
    const question = query.trim();
    // Settle each branch independently: a slow/failed context must never delay
    // or erase a valid direct answer, and answer failure cannot erase evidence.
    const direct = getResearchAnswer(company.ticker, question, signal).then(response => {
      if (scope.current.current(id) && response.ticker === company.ticker && response.question === question) setAnswer(response);
    }).catch(failure => { if (scope.current.current(id)) setAnswerError(describeApiError(failure)); })
      .finally(() => { if (scope.current.current(id)) { answerPending.current = false; setAnswerLoading(false); } });
    const evidence = companyWide ? getCompanyContext(company.ticker, company.cik, question, evidenceSignal).then(response => {
      if (evidenceScope.current.current(evidenceId)) setResult(response);
    }).catch(failure => { if (evidenceScope.current.current(evidenceId)) setError(describeApiError(failure)); })
      .finally(() => { if (evidenceScope.current.current(evidenceId)) { evidencePending.current = false; setLoading(false); } }) : selectedFiling ? getFilingContext(company.ticker, selectedFiling.accession_number, question, evidenceSignal).then(response => {
      if (evidenceScope.current.current(evidenceId) && response.ticker === company.ticker && response.accession_number === selectedFiling.accession_number && response.query === question) setResult(response);
    }).catch(failure => { if (evidenceScope.current.current(evidenceId)) setError(describeApiError(failure)); })
      .finally(() => { if (evidenceScope.current.current(evidenceId)) { evidencePending.current = false; setLoading(false); } }) : Promise.resolve();
    await Promise.all([direct, evidence]);
  }
  return <>
    {retrievalScope === "filing" && filing && <div className="filing-record"><strong>{filing.form ?? "SEC filing"}</strong><span>Filed {formatDate(filing.filed)}</span>
      <p className="mono small wrap-anywhere">Accession {filing.accession_number}</p>
      {officialSecUrl(filing.sec_url) && <a href={officialSecUrl(filing.sec_url)} target="_blank" rel="noopener noreferrer">Open official filing ↗</a>}
    </div>}
    <form onSubmit={search} className="search-form">
      <fieldset className="question-guide">
        <legend>Prepare a financial question</legend>
        <div className="guide-controls">
          <label>Question metric<select value={guideMetric} onChange={event => {
            const next = METRIC_CATALOG.find(item => item.id === event.target.value)!;
            setGuideMetric(next.id);
            if (!next.questionScopes.includes(guideScope)) setGuideScope("latest_available");
          }}>{METRIC_GROUPS.map(group => <optgroup key={group.id} label={group.label}>{METRIC_CATALOG.filter(item => item.group === group.id).map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</optgroup>)}</select></label>
          <label>Question reporting scope<select value={guideScope} onChange={event => setGuideScope(event.target.value as QuestionScope)}>{presentation.questionScopes.map(item => <option key={item} value={item}>{QUESTION_SCOPE_LABELS[item]}</option>)}</select></label>
        </div>
        <p className="muted small">{presentation.description} {presentation.group === "balance" ? "This is a value as of a date, not a reporting-interval flow." : "Latest available may be an annual or YTD interval. A direct quarter requires a reported quarter observation."} Availability is checked only when you submit.</p>
        <p className="question-preview">{preparedQuestion}</p>
        <button type="button" className="secondary-button" disabled={!preparedQuestion} onClick={() => {
          if (preparedQuestion) { edit(preparedQuestion); questionInput.current?.focus(); }
        }}>Use question</button>
        <p className="muted small">Fills the editor below. Review or edit it, then submit explicitly.</p>
      </fieldset>
      <label htmlFor="research-query">Research question or search<textarea ref={questionInput} id="research-query" value={query} maxLength={2000} onChange={(event) => edit(event.target.value)} placeholder="What was the latest quarterly revenue?" rows={3} /></label>
      <div className="question-chips" aria-label="Example research topics">{EXAMPLES.map((example) => <button type="button" key={example} onClick={() => edit(example)}>{example}</button>)}</div>
      <button className="primary-button" disabled={version === null || !query.trim() || loading || answerLoading}>{loading || answerLoading ? "Researching stored SEC data…" : "Research question"}</button>
      <p className="muted small">Ask for a latest value, a fiscal year or quarter (2024 revenue, Q2 2025 revenue), or a comparison (2024–2025 revenue growth). {(retrievalScope === "filing" ? !filing : !companyEvidenceReady) ? "Filing evidence is unavailable for this selection; only direct financial answers can be requested." : "Other questions search SEC evidence."} No AI generation.</p>
    </form>
    {searchedVersion !== version && <p className="notice">Data updated; research this question again.</p>}
    <div aria-live="polite" aria-busy={answerLoading}>
      {answerLoading && <p className="loading-state">Checking stored financial observations…</p>}
      {answerError && <p className="notice">Direct financial answer unavailable: {answerError} {(retrievalScope === "company" ? companyEvidenceReady : filing) && "SEC evidence research continues independently."}</p>}
      {searchedVersion === version && answer?.matched && <DirectResearchAnswer answer={answer} />}
      {searchedVersion === version && answer?.status === "company_mismatch" && <p className="notice">{answer.explanation}</p>}
      {searchedVersion === version && answer?.status === "not_matched" && <p className="muted small">This question is outside supported direct financial answers.{(retrievalScope === "company" ? companyEvidenceReady : filing) && " SEC evidence research continues independently."}</p>}
    </div>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p className="loading-state">{retrievalScope === "company" ? "Finding relevant passages in published company filings…" : "Finding relevant passages in this filing…"}</p>}
      {error && <p role="alert" className="error-state">{error}</p>}
      {!result && !answer && !loading && !answerLoading && !error && <div className="empty-state"><h3>Explore the filing evidence</h3><p>Choose a topic, read the retrieved passages, and follow the official SEC links. No OpenAI access is required.</p></div>}
    </div>
    {searchedVersion === version && searchedEvidence === evidenceIdentity && result && <><h3>Supporting SEC evidence</h3>
      <p className="small muted">{"retrieval_scope" in result ? `Company-wide · ${result.searched_accessions.length} verified published filings searched. ${result.excluded_publication_count ? `${result.excluded_publication_count} ineligible publications excluded. ` : ""}` : `Selected filing only · accession ${result.accession_number}. `}Passages may describe different periods and are research, not validation of the structured answer.</p>
      <EvidenceResults key={`evidence-${result.query}-${retrievalScope}`} result={result} answer={"retrieval_scope" in result ? null : answer} />
      {"retrieval_scope" in result ? <p className="muted small">Company-wide search provides stored evidence only. AI generation is unavailable in this scope.</p> : <AIAnalysis key={`${result.query}-${result.accession_number}`} result={result} configured={configured} />}
    </>}
  </>;
}

function RecordedFilings({ filings, unknown = false }: { filings: FilingSource[]; unknown?: boolean }) {
  const [visible, setVisible] = useState(10);
  if (!filings.length) return null;
  return <details className="recorded-filings">
    <summary>{unknown ? "Evidence status unverified" : "Other recorded filings · metadata only"} ({filings.length})</summary>
    <p className="muted small">{unknown ? "Indexed evidence availability could not be verified for these records." : "These records have no indexed searchable evidence."} They cannot be selected for filing search or filing-specific AI analysis. Follow an official SEC link where provided; stored full text is not guaranteed.</p>
    <ul className="filing-list">{filings.slice(0, visible).map(item => <li className="filing-record" key={item.accession_number}>
      <strong>{item.form ?? "SEC filing"}</strong><span>Filed {formatDate(item.filed)}</span>
      <p className="small mono wrap-anywhere">Accession {item.accession_number}</p>
      <p className="small muted">{unknown ? "Evidence status unverified" : "Metadata only"}</p>
      {officialSecUrl(item.sec_url) && <a className="source-link" href={officialSecUrl(item.sec_url)} target="_blank" rel="noopener noreferrer">Open official SEC filing ↗</a>}
    </li>)}</ul>
    {visible < filings.length && <button type="button" className="secondary-button" onClick={() => setVisible(count => count + 10)}>Show more recorded filings ({filings.length - visible})</button>}
  </details>;
}

export default function FilingResearch({ company, configured }: { company: Company; configured: boolean }) {
  const { version, changed } = useResearchVersion();
  const [query, setQuery] = useState("");
  const [sourceVersion, setSourceVersion] = useState(-1);
  const [filings, setFilings] = useState<FilingSource[]>([]);
  const [accession, setAccession] = useState("");
  const [retrievalScope, setRetrievalScope] = useState<"filing" | "company">("filing");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [sourceAttempt, setSourceAttempt] = useState(0);
  const sourcePending = useRef(false);
  useEffect(() => {
    setLoading(true); setError(null); setErrorCode(null);
    if (version === null) return;
    sourcePending.current = true;
    const controller = versionedController(version, changed);
    getFilingSources(company.ticker, controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      if (!Array.isArray(data) || data.some(item => !item || typeof item.accession_number !== "string" || !item.accession_number.trim())) throw new Error("Invalid filing list response.");
      const indexed = searchableFilings(data); setFilings(data); setSourceVersion(version);
      setAccession(previous => indexed.some(item => item.accession_number === previous) ? previous : indexed[0]?.accession_number ?? "");
    }).catch((failure) => {
      if (!controller.signal.aborted) {
        setError(describeApiError(failure));
        setErrorCode(failure instanceof FinLensApiError ? failure.code : null);
      }
    }).finally(() => { if (!controller.signal.aborted) { sourcePending.current = false; setLoading(false); } });
    return () => { controller.abort(); sourcePending.current = false; };
  }, [company.ticker, company.cik, version, changed, sourceAttempt]);
  function retrySources() {
    if (version === null || sourcePending.current) return;
    if (errorCode === "DATA_VERSION_CHANGED") { changed(); return; }
    sourcePending.current = true;
    setSourceAttempt(attempt => attempt + 1);
  }
  const currentSources = sourceVersion === version ? filings : [];
  const indexed = searchableFilings(currentSources);
  const filing = indexed.find((item) => item.accession_number === accession);
  return <section className="panel filing-panel" aria-labelledby="filing-title">
    <div className="section-heading"><div><p className="eyebrow">SEC research</p><h2 id="filing-title">Read the evidence</h2></div><span className="badge">No AI required</span></div>
    <p className="muted small">Search a selected filing or published filings for this company. Metric snapshots may refer to a different period or accession.</p>
    <label className="filing-select">Evidence search scope<select value={retrievalScope} onChange={(event) => setRetrievalScope(event.target.value as "filing" | "company")}>
      <option value="filing">Selected filing</option><option value="company">Company-wide</option>
    </select></label>
    <p className="muted small">{loading ? "Checking indexed SEC evidence…" : error ? "Indexed evidence list unavailable." : `Indexed searchable SEC evidence (${indexed.length}).`} Searchable passages do not guarantee complete filing text or sufficient evidence for AI analysis.</p>
    {retrievalScope === "filing" && <label className="filing-select">Indexed SEC filing<select value={accession} onChange={(event) => setAccession(event.target.value)} disabled={loading || !indexed.length || !company.has_indexed_filing}>
      {loading && <option value="">Loading filings…</option>}
      {!loading && !indexed.length && <option value="">{error ? "Filing list unavailable" : "No indexed filing available"}</option>}
      {indexed.map((item) => <option key={item.accession_number} value={item.accession_number}>{item.form ?? "SEC filing"} · {formatDate(item.filed)} · {item.accession_number}</option>)}
    </select></label>}
    <div aria-live="polite" aria-busy={loading}>
      {error && <><p role="alert" className="error-state">Could not load the filing list. {error}</p>
        <button type="button" className="secondary-button" disabled={loading || version === null} onClick={retrySources}>{errorCode === "DATA_VERSION_CHANGED" ? "Retry data check" : "Retry filing list"}</button></>}
    </div>
    {retrievalScope === "filing" && !loading && !error && (!company.has_indexed_filing || !filing) && <div className="empty-state"><h3>Not indexed for filing research</h3><p>Financial research remains available. Choose a Ready company to search stored filing evidence.</p></div>}
    {!loading && !error && currentSources.length === 0 && <p className="muted small">No recorded filings were returned for this publication.</p>}
    {!loading && !error && <>
      <RecordedFilings key={`${company.ticker}-${company.cik}-${sourceVersion}-metadata`} filings={currentSources.filter(item => filingReadiness(item) === "metadata_only")} />
      <RecordedFilings key={`${company.ticker}-${company.cik}-${sourceVersion}-unknown`} unknown filings={currentSources.filter(item => filingReadiness(item) === "unknown")} />
    </>}
    <FilingSearch key={`${company.ticker}-${company.cik}`} company={company} filing={sourceVersion === version && company.has_indexed_filing ? filing ?? null : null} companyEvidenceReady={sourceVersion === version && company.has_indexed_filing && indexed.length > 0} configured={configured} query={query} setQuery={setQuery} retrievalScope={retrievalScope} />
  </section>;
}
