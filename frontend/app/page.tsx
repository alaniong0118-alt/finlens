"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  citationForClaim,
  describeApiError,
  getAnswer,
  getCompanies,
  getFilingSources,
  searchableFilings,
  type Company,
  type FilingAnswer,
  type FilingSource,
} from "@/lib/finlens-api";

const EXAMPLE_QUESTIONS = [
  "revenue growth",
  "services revenue",
  "gross margin",
  "supply constraints",
  "artificial intelligence",
];

function formatDate(value: string | null): string {
  if (!value) return "Date unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export default function Home() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [ticker, setTicker] = useState("");
  const [companyLoading, setCompanyLoading] = useState(true);
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [filings, setFilings] = useState<FilingSource[]>([]);
  const [accession, setAccession] = useState("");
  const [filingLoading, setFilingLoading] = useState(false);
  const [filingError, setFilingError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<FilingAnswer | null>(null);
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const requestId = useRef(0);
  const questionInput = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let active = true;
    getCompanies()
      .then((data) => {
        if (!active) return;
        setCompanies(data);
        setTicker(data[0]?.ticker ?? "");
      })
      .catch((error: unknown) => {
        if (active) setCompanyError(describeApiError(error));
      })
      .finally(() => {
        if (active) setCompanyLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setFilings([]);
    setAccession("");
    setFilingError(null);
    if (!ticker) {
      setFilingLoading(false);
      return;
    }
    setFilingLoading(true);
    getFilingSources(ticker)
      .then((data) => {
        if (!active) return;
        setFilings(data);
        setAccession(searchableFilings(data)[0]?.accession_number ?? "");
      })
      .catch((error: unknown) => {
        if (active) setFilingError(describeApiError(error));
      })
      .finally(() => {
        if (active) setFilingLoading(false);
      });
    return () => { active = false; };
  }, [ticker]);

  const company = useMemo(
    () => companies.find((item) => item.ticker === ticker),
    [companies, ticker],
  );
  const indexedFilings = useMemo(() => searchableFilings(filings), [filings]);
  const filing = useMemo(
    () => indexedFilings.find((item) => item.accession_number === accession),
    [indexedFilings, accession],
  );
  const canAsk = Boolean(accession && question.trim() && !askLoading && !filingLoading);

  function resetAnswer() {
    requestId.current += 1;
    setAskLoading(false);
    setAskError(null);
    setAnswer(null);
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentQuestion = question.trim();
    if (!accession || !ticker || !currentQuestion || askLoading) return;

    const thisRequest = ++requestId.current;
    setAskLoading(true);
    setAskError(null);
    setAnswer(null);
    try {
      const result = await getAnswer(ticker, accession, currentQuestion);
      if (requestId.current === thisRequest) setAnswer(result);
    } catch (error) {
      if (requestId.current === thisRequest) {
        setAskError(describeApiError(error));
      }
    } finally {
      if (requestId.current === thisRequest) setAskLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f7f7] text-slate-900">
      <header className="border-b border-slate-800 bg-[#102a35] text-white">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-teal-300/25 bg-teal-300/10 text-xl font-semibold text-teal-200 shadow-sm" aria-hidden="true">
              F
            </span>
            <div>
              <p className="text-xl font-semibold tracking-tight">FinLens<span className="ml-1 text-teal-300" aria-hidden="true">.</span></p>
              <p className="mt-0.5 text-xs tracking-wide text-slate-300">SEC filing research</p>
            </div>
          </div>
          <p className="hidden rounded-full border border-slate-500/60 px-3 py-1.5 text-xs font-medium text-slate-200 sm:block">
            Evidence-led Q&amp;A
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-[1320px] px-5 pb-16 pt-9 sm:px-8 sm:pt-11">
        <div className="mb-8 max-w-4xl sm:mb-10">
          <p className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-teal-700"><span className="h-px w-6 bg-teal-700" aria-hidden="true" />Research workspace</p>
          <h1 className="text-4xl font-semibold leading-tight tracking-[-0.035em] text-[#102a35] sm:text-5xl">
            Ask the filing. Follow the evidence.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            Select a company and an indexed SEC filing, then ask a question.
            Every supported claim links back to the filing record.
          </p>
          <ul aria-label="Research capabilities" className="mt-5 flex flex-wrap gap-2 text-xs font-medium text-slate-700">
            {["SEC-sourced", "Hybrid retrieval", "Traceable citations", "Abstains on insufficient evidence"].map((label) => (
              <li key={label} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-teal-700" aria-hidden="true" />{label}
              </li>
            ))}
          </ul>
        </div>

        <div className="grid items-stretch gap-6 lg:grid-cols-[minmax(320px,390px)_minmax(0,1fr)] lg:gap-8">
          <section className="rounded-2xl border border-slate-200/90 bg-white shadow-[0_4px_24px_rgba(16,42,53,0.06)] transition-shadow focus-within:shadow-[0_8px_32px_rgba(16,42,53,0.09)]" aria-labelledby="research-input-title">
            <div className="rounded-t-2xl border-b border-slate-100 bg-slate-50/50 px-5 py-5 sm:px-6">
              <h2 id="research-input-title" className="text-lg font-semibold text-[#102a35]">Build your question</h2>
              <p className="mt-1 text-sm text-slate-500">Choose the exact filing you want to examine.</p>
            </div>

            <form onSubmit={ask} className="space-y-6 p-5 sm:p-6">
              <div>
                <label htmlFor="company" className="mb-2 block text-sm font-semibold text-slate-800">
                  <span className="mr-2 text-teal-700">01</span> Company
                </label>
                <select
                  id="company"
                  value={ticker}
                  onChange={(event) => {
                    resetAnswer();
                    setTicker(event.target.value);
                  }}
                  disabled={companyLoading || Boolean(companyError)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15 disabled:bg-slate-100"
                >
                  {companyLoading && <option value="">Loading companies…</option>}
                  {!companyLoading && companies.length === 0 && <option value="">No companies available</option>}
                  {companies.map((item) => (
                    <option key={item.id} value={item.ticker}>{item.ticker} — {item.name}</option>
                  ))}
                </select>
                {company && (
                  <p className="mt-2 text-xs text-slate-500">
                    {company.exchange} · CIK {company.cik}
                  </p>
                )}
                {companyError && <p role="alert" className="mt-2 text-sm text-red-700">{companyError}</p>}
              </div>

              <div>
                <label htmlFor="filing" className="mb-2 block text-sm font-semibold text-slate-800">
                  <span className="mr-2 text-teal-700">02</span> Filing
                </label>
                <select
                  id="filing"
                  value={accession}
                  onChange={(event) => {
                    resetAnswer();
                    setAccession(event.target.value);
                  }}
                  disabled={filingLoading || indexedFilings.length === 0}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15 disabled:bg-slate-100"
                >
                  {filingLoading && <option value="">Loading filings…</option>}
                  {!filingLoading && indexedFilings.length === 0 && <option value="">No indexed filing available</option>}
                  {indexedFilings.map((item) => (
                    <option key={item.accession_number} value={item.accession_number}>
                      {item.form ?? "SEC filing"} · {formatDate(item.filed)} · {item.accession_number}
                    </option>
                  ))}
                </select>
                {!filingLoading && !filingError && filings.length > 0 && (
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {indexedFilings.length} of {filings.length} filings have searchable text.
                    Only indexed filings can answer questions.
                  </p>
                )}
                {filingError && <p role="alert" className="mt-2 text-sm text-red-700">{filingError}</p>}
                {filing && (
                  <p className="mt-2 text-xs text-slate-500">
                    Available record: {filing.form ?? "SEC filing"} filed {formatDate(filing.filed)}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="question" className="mb-2 block text-sm font-semibold text-slate-800">
                  <span className="mr-2 text-teal-700">03</span> Question
                </label>
                <textarea
                  id="question"
                  ref={questionInput}
                  value={question}
                  maxLength={2000}
                  rows={5}
                  placeholder="What drove revenue growth in this filing?"
                  onChange={(event) => {
                    resetAnswer();
                    setQuestion(event.target.value);
                  }}
                  className="w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
                />
                <p className="mt-3 text-xs font-medium uppercase tracking-wide text-slate-500">Try a question</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {EXAMPLE_QUESTIONS.map((example) => (
                    <button
                      key={example}
                      type="button"
                      onClick={() => {
                        resetAnswer();
                        setQuestion(example);
                        questionInput.current?.focus();
                      }}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={!canAsk}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#126a67] px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-[#0e5552] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {askLoading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/50 border-t-white" aria-hidden="true" />
                    Reviewing evidence…
                  </>
                ) : "Ask FinLens"}
              </button>
              <p className="text-center text-xs leading-5 text-slate-500">
                Financial research and education. No investment recommendations or price forecasts.
              </p>
            </form>
          </section>

          <section className="flex min-h-[540px] flex-col rounded-2xl border border-slate-200/90 bg-white shadow-[0_4px_24px_rgba(16,42,53,0.06)]" aria-labelledby="answer-title">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-t-2xl border-b border-slate-100 bg-slate-50/50 px-5 py-5 sm:px-6">
              <h2 id="answer-title" className="text-lg font-semibold text-[#102a35]">Research answer</h2>
              {answer && (
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${answer.evidence_status === "sufficient" ? "bg-teal-50 text-teal-800" : "bg-amber-50 text-amber-800"}`}>
                  {answer.evidence_status === "sufficient" ? "Evidence found" : "Insufficient evidence"}
                </span>
              )}
            </div>

            <div className="flex-1 p-5 sm:p-8" aria-live="polite">
              {askError && (
                <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm leading-6 text-red-800">
                  <p className="font-semibold">Unable to produce a verified answer</p>
                  <p className="mt-1">{askError}</p>
                </div>
              )}

              {askLoading && (
                <div role="status" className="space-y-4">
                  <p className="text-sm font-medium text-slate-700">Searching filing evidence and validating citations…</p>
                  <div className="h-4 w-3/4 animate-pulse rounded bg-slate-100" />
                  <div className="h-4 w-5/6 animate-pulse rounded bg-slate-100" />
                  <div className="h-4 w-1/2 animate-pulse rounded bg-slate-100" />
                </div>
              )}

              {!answer && !askLoading && !askError && (
                <div className="flex h-full min-h-[430px] flex-col items-center justify-center text-center">
                  <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-teal-100 bg-teal-50 text-teal-700" aria-hidden="true">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
                      <path d="M14 3v6h6M8 13h8M8 17h5" />
                    </svg>
                  </div>
                  <h3 className="text-2xl font-semibold tracking-tight text-[#102a35]">Ask a filing question</h3>
                  <p className="mt-3 max-w-sm text-sm leading-6 text-slate-600">
                    Start with an SEC filing. Follow each answer back to the evidence it cites.
                  </p>
                  <ol aria-label="How to use FinLens" className="mt-8 grid w-full max-w-lg grid-cols-1 gap-3 border-y border-slate-100 py-5 min-[480px]:grid-cols-3">
                    {["Select filing", "Ask question", "Trace evidence"].map((step, index) => (
                      <li key={step} className="flex items-center justify-center gap-2 text-xs font-medium text-slate-700">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-teal-800">{index + 1}</span>
                        {step}
                      </li>
                    ))}
                  </ol>
                  <p className="mt-5 max-w-sm text-xs leading-5 text-slate-500">When the retrieved evidence is insufficient, FinLens abstains rather than generating an answer.</p>
                  {!filingLoading && ticker && indexedFilings.length === 0 && (
                    <p className="mt-5 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
                      This company has no filing text indexed for Q&amp;A yet. Select a company with an indexed filing.
                    </p>
                  )}
                </div>
              )}

              {answer && answer.evidence_status === "insufficient" && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-6 text-amber-950">
                  <p className="text-xs font-bold uppercase tracking-widest text-amber-700">Insufficient evidence</p>
                  <h3 className="mt-2 text-lg font-semibold">This filing does not provide enough support for an answer.</h3>
                  <p className="mt-2 text-sm leading-6 text-amber-900">{answer.answer}</p>
                  <p className="mt-3 text-xs text-amber-800">
                    Try a narrower question or choose another indexed filing.
                  </p>
                </div>
              )}

              {answer && answer.evidence_status === "sufficient" && (
                <>
                  <div className="border-b border-slate-100 pb-6">
                    <p className="text-xs font-bold uppercase tracking-widest text-teal-700">Grounded answer</p>
                    <p className="mt-2 text-sm text-slate-500">{answer.question}</p>
                    <p className="mt-5 whitespace-pre-line text-base leading-8 text-[#17313a]">{answer.answer}</p>
                    <p className="mt-4 text-xs text-slate-500">
                      {answer.company_name} · {filing?.form ?? "SEC filing"} · accession {answer.accession_number} · model {answer.model}
                    </p>
                  </div>

                  <div className="pt-7">
                    <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">Claims and sources</h3>
                    <p className="mt-2 text-sm text-slate-500">Each claim is linked to the retrieved filing record below.</p>
                    <div className="mt-5 space-y-5">
                      {answer.claims.map((claim, index) => (
                        <article key={index} className="rounded-xl border border-slate-200 bg-[#fafcfb] p-5">
                          <p className="text-xs font-bold uppercase tracking-widest text-teal-700">Claim {index + 1}</p>
                          <p className="mt-2 text-sm leading-7 text-slate-900">{claim.text}</p>
                          <div className="mt-4 space-y-3 border-t border-slate-200 pt-4">
                            {claim.citation_ids.map((citationId) => {
                              const citation = citationForClaim(citationId, answer.citations);
                              if (!citation) return null;
                              return (
                                <div key={citationId} className="rounded-lg border border-slate-200 bg-white p-4">
                                  <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                      <p className="text-xs font-bold uppercase tracking-wide text-teal-700">{citationId} · {citation.form}</p>
                                      <p className="mt-1 text-sm font-semibold text-slate-800">{answer.company_name} · filed {formatDate(citation.filed)}</p>
                                    </div>
                                    <a
                                      href={citation.sec_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-sm font-semibold text-teal-800 underline decoration-teal-300 underline-offset-4 hover:text-teal-950"
                                    >
                                      Open SEC filing ↗
                                    </a>
                                  </div>
                                  <p className="mt-3 break-all font-mono text-xs leading-5 text-slate-500">
                                    {citation.accession_number} · {citation.filename} · {citation.chunk_id}
                                  </p>
                                  <p className="mt-1 text-xs text-slate-500">
                                    Extracted text characters {citation.start_char.toLocaleString()}–{citation.end_char.toLocaleString()}
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </article>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
