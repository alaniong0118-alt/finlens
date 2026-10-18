"use client";
import { useEffect, useId, useRef, useState } from "react";
import { FinLensApiError, getPassageTone, versionedController, type FilingToneResponse } from "@/lib/finlens-api";
import { toneParts, type ToneIdentity } from "@/lib/filing-tone";
import { useResearchVersion } from "@/components/research-freshness";

function failureMessage(failure: unknown): { text: string; retry: boolean } {
  const error = failure instanceof FinLensApiError ? failure : null;
  switch (error?.code) {
    case "DATA_VERSION_CHANGED": return { text: "Published data changed. Wait for the data check, then research this passage again.", retry: false };
    case "EVIDENCE_PENDING": return { text: "This filing’s published evidence is incomplete or changed. Check the data and research again.", retry: false };
    case "SEARCH_SCOPE_TOO_LARGE": return { text: "This filing exceeds the tone analysis resource limit. Choose another filing.", retry: false };
    case "TONE_INPUT_UNSUPPORTED": return { text: "This stored passage contains text unsupported by this tone method.", retry: false };
    case "TONE_INVALID_INPUT": return { text: "The passage source or publication pin could not be verified. Research the passage again.", retry: false };
    case "TONE_CHUNK_NOT_FOUND": return { text: "This passage is no longer available in the selected filing. Research again.", retry: false };
    case "INVALID_RESPONSE": return { text: "Passage tone or its source could not be verified. No tone result was shown.", retry: true };
    case "REQUEST_TIMEOUT": return { text: "Passage tone took too long to respond. You can retry explicitly.", retry: true };
    case "DATABASE_TIMEOUT": return { text: "The research database could not complete this tone request in time.", retry: true };
    case "DATABASE_BUSY": return { text: "The research database is busy. Try this passage again later.", retry: true };
    case "DATABASE_UNAVAILABLE": return { text: "The research database is unavailable. Try this passage again later.", retry: true };
    case "NETWORK_ERROR": return { text: "Could not reach FinLens for passage tone. You can retry explicitly.", retry: true };
    case "BODY_READ_ERROR": return { text: "The passage tone response could not be read. You can retry explicitly.", retry: true };
    default: return { text: error?.status === 404 ? "The passage source was not found. Research again."
      : "Passage tone is unavailable. Your existing SEC evidence remains available.", retry: error?.status !== 404 && (error?.status ?? 0) >= 500 };
  }
}

const unscorable = {
  no_tokens: "No word tokens were found. No score is available.",
  no_lexicon_matches: "No terms from this method’s lexicon matched. No score is available.",
  all_matches_negated: "All matched terms were negated and excluded. No score is available.",
};

export default function PassageTone({ identity }: { identity: ToneIdentity | null }) {
  const { version, changed } = useResearchVersion();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FilingToneResponse | null>(null);
  const [error, setError] = useState<ReturnType<typeof failureMessage> | null>(null);
  const [visibleMatches, setVisibleMatches] = useState(20);
  const generation = useRef({ value: 0 });
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const mounted = useRef(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const returnFocus = useRef(false);
  const scopeKey = JSON.stringify([identity, version]);
  const currentKey = useRef(scopeKey);
  // Render ownership closes the window before passive-effect cleanup commits.
  currentKey.current = scopeKey;
  const [displayKey, setDisplayKey] = useState(scopeKey);
  useEffect(() => {
    const ownedGeneration = generation.current;
    mounted.current = true;
    ownedGeneration.value++; controller.current?.abort(); pending.current = false;
    setOpen(false); setLoading(false); setResult(null); setError(null); setVisibleMatches(20); setDisplayKey(scopeKey);
    return () => { mounted.current = false; ownedGeneration.value++; controller.current?.abort(); pending.current = false; };
  }, [scopeKey]);
  useEffect(() => {
    if (!open && returnFocus.current) { returnFocus.current = false; trigger.current?.focus(); }
  }, [open]);

  function close() {
    generation.current.value++; controller.current?.abort(); pending.current = false;
    returnFocus.current = true;
    setOpen(false); setLoading(false); setResult(null); setError(null); setVisibleMatches(20);
  }
  async function inspect() {
    if (!identity || version === null || pending.current) return;
    pending.current = true;
    const attempt = ++generation.current.value;
    const key = scopeKey;
    const request = versionedController(version, changed);
    controller.current?.abort(); controller.current = request;
    const current = () => mounted.current && generation.current.value === attempt && currentKey.current === key && !request.signal.aborted;
    setDisplayKey(key); setOpen(true); setLoading(true); setResult(null); setError(null); setVisibleMatches(20);
    try {
      const response = await getPassageTone(identity, request.signal);
      if (current()) setResult(response);
    } catch (failure) {
      if (current()) setError(failureMessage(failure));
    } finally {
      if (current()) { pending.current = false; setLoading(false); }
    }
  }
  const showing = open && displayKey === scopeKey;
  const parts = result && showing ? toneParts(result) : [];
  return <div className="passage-tone">
    <button ref={trigger} type="button" className="secondary-button" aria-expanded={showing} aria-controls={`${id}-panel`}
      disabled={!showing && (!identity || version === null)} aria-disabled={showing && loading}
      onClick={() => { if (!pending.current) { if (showing) close(); else void inspect(); } }}>
      {showing ? loading ? "Inspecting passage tone…" : "Close passage tone" : "Inspect passage tone"}
    </button>
    {!identity && <p className="small muted">Tone inspection requires a verified passage source.</p>}
    {identity && version === null && <p className="small muted">Verify this company’s data version before inspecting tone.</p>}
    <section id={`${id}-panel`} hidden={!showing} aria-labelledby={`${id}-title`} aria-busy={showing && loading}>
      <h5 id={`${id}-title`}>Passage lexical tone proxy</h5>
      {showing && <>
        <p className="small muted">Deterministic lexical analysis of one stored passage. This is not predictive sentiment, confidence, market risk, investment advice or a whole-filing conclusion.</p>
        <div role="status" aria-live="polite">{loading && <p className="small">Inspecting the stored published passage…</p>}</div>
        {loading && <button type="button" className="secondary-button" onClick={close}>Cancel passage tone</button>}
        {error && <><p role="alert" className="error-state">{error.text}</p>
          {error.retry && <button type="button" className="secondary-button" disabled={loading || version === null} onClick={() => { trigger.current?.focus(); void inspect(); }}>Retry passage tone</button>}</>}
        {result && <>
          <div role="status" className="tone-summary">
            {result.tone.status === "scored" ? <p>Lexical balance: <strong>{result.tone.score!.numerator}/{result.tone.score!.denominator}</strong> · (positive − negative) / (positive + negative).</p>
              : <p>{unscorable[result.tone.reason!]}</p>}
            <p className="small">Active positive: {result.tone.positive_count} · Active negative: {result.tone.negative_count} · Negated, excluded: {result.tone.negated_count} · Tokens: {result.tone.token_count}</p>
          </div>
          <p className="small">Marks identify lexicon matches. Negated matches are excluded, never reversed. They do not verify factual claims.</p>
          <p className="excerpt tone-passage" aria-label="Exact passage with lexical matches">{parts.map((part, index) => part.match
            ? <mark key={index} className={`tone-match tone-${part.match.negator_span ? "negated" : part.match.polarity}`}>{part.text}</mark> : part.text)}</p>
          <details className="provenance"><summary>Matched terms and local spans ({result.tone.matches.length})</summary>
            <p className="small">Unicode code-point ranges include the start and exclude the end, relative only to the exact passage above.</p>
            <ol className="tone-matches">{result.tone.matches.slice(0, visibleMatches).map(match => <li key={`${match.start}-${match.end}`}>
              <q>{match.text}</q> · {match.polarity}{match.negator_span && " · negated, excluded"} · [{match.start}, {match.end})
              {match.negator_span && <> · negator [{match.negator_span[0]}, {match.negator_span[1]})</>}
            </li>)}</ol>
            {visibleMatches < result.tone.matches.length && <button type="button" className="secondary-button" onClick={() => setVisibleMatches(count => count + 20)}>Show more matched terms</button>}
          </details>
          <div className="tone-source small wrap-anywhere">
            <p>{result.ticker} · CIK {result.company_cik} · {result.source.form} · Filed {result.source.filed}</p>
            <p>Accession {result.publication.accession_number} · {result.source.chunk_id} · {result.source.filename}</p>
            <a className="source-link" href={result.source.sec_url} target="_blank" rel="noopener noreferrer">Open official SEC filing ↗</a>
          </div>
          <details className="provenance"><summary>Tone method and publication details</summary><div className="small wrap-anywhere">
            <p>Method {result.tone.method_version} · Lexicon {result.tone.lexicon_version}</p>
            <p>Company publication {result.data_version} · Evidence version {result.evidence_version} · Filing publication {result.publication.data_version}</p>
            <p>Server-provided publication digest: <span className="mono">{result.publication.content_digest}</span>. One passage does not independently verify this digest.</p>
          </div></details>
        </>}
      </>}
    </section>
  </div>;
}
