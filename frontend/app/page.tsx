"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  citationForClaim,
  describeApiError,
  getAnswer,
  getCompanies,
  getFilingSources,
  firstReadyCompany,
  readyCompanyCount,
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
  const sourceRequestId = useRef(0);
  const questionInput = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let active = true;
    getCompanies()
      .then((data) => {
        if (!active) return;
        setCompanies(data);
        setTicker(firstReadyCompany(data)?.ticker ?? "");
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
    const thisRequest = ++sourceRequestId.current;
    setFilings([]);
    setAccession("");
    setFilingError(null);
    const selectedCompany = companies.find((item) => item.ticker === ticker);
    if (!selectedCompany?.has_indexed_filing) {
      setFilingLoading(false);
      return;
    }
    setFilingLoading(true);
    getFilingSources(ticker)
      .then((data) => {
        if (!active || sourceRequestId.current !== thisRequest) return;
        setFilings(data);
        setAccession(searchableFilings(data)[0]?.accession_number ?? "");
      })
      .catch((error: unknown) => {
        if (active && sourceRequestId.current === thisRequest) setFilingError(describeApiError(error));
      })
      .finally(() => {
        if (active && sourceRequestId.current === thisRequest) setFilingLoading(false);
      });
    return () => { active = false; };
  }, [ticker, companies]);

  const company = useMemo(
    () => companies.find((item) => item.ticker === ticker),
    [companies, ticker],
  );
  const indexedFilings = useMemo(() => searchableFilings(filings), [filings]);
  const filing = useMemo(
    () => indexedFilings.find((item) => item.accession_number === accession),
    [indexedFilings, accession],
  );
  const canAsk = Boolean(company?.has_indexed_filing && filing && question.trim() && !askLoading && !filingLoading);

  function resetAnswer() {
    requestId.current += 1;
    setAskLoading(false);
    setAskError(null);
    setAnswer(null);
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentQuestion = question.trim();
    if (!company?.has_indexed_filing || !filing || !accession || !ticker || !currentQuestion || askLoading || filingLoading) return;

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
    <main className="min-h-screen bg-[#f3f6f5] text-slate-900">
      <header className="border-b border-[#284952] bg-[#102a35] text-white">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-3 px-4 py-3.5 sm:px-8">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-teal-300/30 bg-teal-300/10 text-lg font-semibold text-teal-200" aria-hidden="true">
              F
            </span>
            <div>
              <p className="text-lg font-semibold leading-5 tracking-tight sm:text-xl">FinLens<span className="ml-0.5 text-teal-300" aria-hidden="true">.</span></p>
              <p className="mt-0.5 text-[11px] tracking-wide text-slate-300">SEC filing research</p>
            </div>
          </div>
          <p className="rounded-full border border-teal-200/20 bg-white/5 px-2.5 py-1.5 text-[10px] font-medium tracking-wide text-slate-200 sm:px-3 sm:text-xs">
            Evidence-led <span className="hidden min-[380px]:inline">Q&amp;A</span>
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-[1320px] px-4 pb-14 pt-7 sm:px-8 sm:pt-9">
        <div className="mb-7 max-w-5xl sm:mb-8">
          <p className="mb-2.5 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] text-teal-800"><span className="h-px w-6 bg-teal-700" aria-hidden="true" />SEC-sourced financial research</p>
          <h1 className="max-w-4xl text-[2.35rem] font-semibold leading-[1.12] tracking-[-0.04em] text-[#102a35] sm:text-[3.1rem]">
            Ask the filing. Follow the evidence.
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 sm:text-base sm:leading-7">
            Ask a financial question about a public company&apos;s SEC filing. Trace supported claims to the official source.
          </p>
          <ul aria-label="Research capabilities" className="mt-4 flex flex-wrap gap-2 text-[11px] font-medium text-slate-700 sm:text-xs">
            {["Official SEC sources", "Semantic + keyword search", "Traceable citations", "Abstains on weak evidence"].map((label) => (
              <li key={label} className="inline-flex items-center gap-2 rounded-full border border-[#dce7e4] bg-white/90 px-2.5 py-1 shadow-[0_1px_2px_rgba(16,42,53,0.03)] sm:px-3">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-700" aria-hidden="true" />{label}
              </li>
            ))}
          </ul>
        </div>

        <div className="grid min-w-0 items-stretch gap-5 lg:grid-cols-[minmax(360px,440px)_minmax(0,1fr)] lg:gap-6">
          <section className="min-w-0 overflow-hidden rounded-2xl border border-[#dce6e4] bg-white shadow-[0_8px_32px_rgba(16,42,53,0.055)] transition-shadow focus-within:shadow-[0_10px_34px_rgba(16,42,53,0.085)]" aria-labelledby="research-input-title">
            <div className="border-b border-slate-100 bg-[#fafcfb] px-5 py-4 sm:px-6">
              <p className="text-[10px] font-bold uppercase tracking-[0.17em] text-teal-800">Research setup</p>
              <h2 id="research-input-title" className="mt-1 text-lg font-semibold tracking-tight text-[#102a35]">Ask about a filing</h2>
              <p className="mt-0.5 text-sm text-slate-500">Choose a company, filing, and question.</p>
            </div>

            <form onSubmit={ask} className="space-y-5 p-5 sm:p-6">
              <div>
                <label htmlFor="company" className="mb-2 flex items-center gap-2.5 text-sm font-semibold text-[#17313a]">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-50 text-[11px] font-bold text-teal-800">01</span> Company
                </label>
                <select
                  id="company"
                  value={ticker}
                  onChange={(event) => {
                    resetAnswer();
                    sourceRequestId.current += 1;
                    setFilings([]);
                    setAccession("");
                    setFilingError(null);
                    setFilingLoading(false);
                    setTicker(event.target.value);
                  }}
                  disabled={companyLoading || Boolean(companyError)}
                  className="w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm text-slate-900 shadow-sm outline-none transition-colors hover:border-slate-400 focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15 disabled:bg-slate-100"
                >
                  {companyLoading && <option value="">Loading companies…</option>}
                  {!companyLoading && companies.length === 0 && <option value="">No companies available</option>}
                  {companies.map((item) => (
                    <option key={item.id} value={item.ticker}>
                      {item.ticker} — {item.name} · {item.has_indexed_filing ? "Ready" : "Not indexed"}
                    </option>
                  ))}
                </select>
                {company && (
                  <div className="mt-2.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 text-xs text-slate-500">
                    <span>{company.exchange} <span aria-hidden="true">·</span> CIK {company.cik}</span>
                    <span className={`rounded-full px-2 py-0.5 font-semibold ${company.has_indexed_filing ? "bg-teal-50 text-teal-800" : "bg-slate-100 text-slate-600"}`}>
                      {company.has_indexed_filing ? "Ready" : "Not indexed"}
                    </span>
                  </div>
                )}
                {!companyLoading && !companyError && companies.length > 0 && (
                  <p className="mt-2 text-xs text-slate-500">
                    {readyCompanyCount(companies)} of {companies.length} companies ready for filing Q&amp;A
                  </p>
                )}
                {companyError && <p role="alert" className="mt-2 text-sm text-red-700">{companyError}</p>}
              </div>

              <div>
                <label htmlFor="filing" className="mb-2 flex items-center gap-2.5 text-sm font-semibold text-[#17313a]">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-50 text-[11px] font-bold text-teal-800">02</span> Filing
                </label>
                <select
                  id="filing"
                  value={accession}
                  onChange={(event) => {
                    resetAnswer();
                    setAccession(event.target.value);
                  }}
                  disabled={!company?.has_indexed_filing || filingLoading || indexedFilings.length === 0}
                  className="w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm text-slate-900 shadow-sm outline-none transition-colors hover:border-slate-400 focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15 disabled:bg-slate-100"
                >
                  {filingLoading && <option value="">Loading filings…</option>}
                  {!filingLoading && indexedFilings.length === 0 && <option value="">No indexed filing available</option>}
                  {indexedFilings.map((item) => (
                    <option key={item.accession_number} value={item.accession_number}>
                      {item.form ?? "SEC filing"} · {formatDate(item.filed)} · {item.accession_number}
                    </option>
                  ))}
                </select>
                {filingError && <p role="alert" className="mt-2 text-sm text-red-700">{filingError}</p>}
                {filing && (
                  <div className="mt-2.5 rounded-lg border border-[#e3ece9] bg-[#f8fbfa] px-3 py-2.5">
                    <p className="text-xs font-semibold text-[#17313a]">{filing.form ?? "SEC filing"} <span className="font-normal text-slate-500">· Filed {formatDate(filing.filed)}</span></p>
                    <p className="mt-1 break-all font-mono text-[11px] text-slate-500">Accession {filing.accession_number}</p>
                  </div>
                )}
                {!filingLoading && !filingError && filings.length > 0 && (
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {indexedFilings.length} of {filings.length} filings indexed for Q&amp;A
                  </p>
                )}
                {company && !company.has_indexed_filing && (
                  <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700">
                    <p className="font-semibold text-[#102a35]">Not indexed for filing Q&amp;A</p>
                    <p className="mt-1">Company data is available, but no SEC filing is prepared for evidence-grounded Q&amp;A yet.</p>
                    {firstReadyCompany(companies)?.has_indexed_filing && (
                      <button
                        type="button"
                        onClick={() => {
                          resetAnswer();
                          sourceRequestId.current += 1;
                          setFilings([]);
                          setAccession("");
                          setFilingError(null);
                          setFilingLoading(false);
                          setTicker(firstReadyCompany(companies)!.ticker);
                        }}
                        className="mt-1 inline-flex min-h-10 items-center font-semibold text-teal-800 underline decoration-teal-300 underline-offset-4 hover:text-teal-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
                      >
                        Choose a Ready company
                      </button>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label htmlFor="question" className="mb-2 flex items-center gap-2.5 text-sm font-semibold text-[#17313a]">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-50 text-[11px] font-bold text-teal-800">03</span> Question
                </label>
                <textarea
                  id="question"
                  ref={questionInput}
                  value={question}
                  maxLength={2000}
                  rows={4}
                  placeholder="What drove revenue growth in this filing?"
                  onChange={(event) => {
                    resetAnswer();
                    setQuestion(event.target.value);
                  }}
                  className="w-full min-w-0 resize-y rounded-xl border border-slate-300 bg-[#fcfefd] px-3.5 py-3.5 text-sm leading-6 text-slate-900 shadow-sm outline-none transition-colors placeholder:text-slate-400 hover:border-slate-400 focus:border-teal-700 focus:bg-white focus:ring-2 focus:ring-teal-700/15"
                />
                <p className="mt-3 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">Try a question</p>
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
                      className="min-h-10 rounded-full border border-slate-200 bg-slate-50/60 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={!canAsk}
                className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#126a67] px-5 py-3 text-sm font-semibold text-white shadow-[0_3px_9px_rgba(18,106,103,0.15)] transition-colors hover:bg-[#0e5552] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
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

          <section className="flex min-w-0 min-h-[540px] flex-col overflow-hidden rounded-2xl border border-[#dce6e4] bg-white shadow-[0_8px_32px_rgba(16,42,53,0.055)]" aria-labelledby="answer-title">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-[#fafcfb] px-5 py-4 sm:px-7">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.17em] text-teal-800">Evidence output</p>
                <h2 id="answer-title" className="mt-1 text-lg font-semibold tracking-tight text-[#102a35]">Research answer</h2>
                <p className="mt-0.5 text-sm text-slate-500">Claims linked to the filing record.</p>
              </div>
              {answer && (
                <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${answer.evidence_status === "sufficient" ? "bg-teal-50 text-teal-800" : "bg-slate-100 text-slate-700"}`}>
                  {answer.evidence_status === "sufficient" ? "Evidence found" : "Insufficient evidence"}
                </span>
              )}
            </div>

            <div className="flex min-w-0 flex-1 flex-col p-5 sm:p-7" aria-live="polite">
              {askError && (
                <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm leading-6 text-red-800">
                  <p className="font-semibold">Unable to produce a verified answer</p>
                  <p className="mt-1">{askError}</p>
                </div>
              )}

              {askLoading && (
                <div role="status" className="max-w-2xl space-y-5 rounded-xl border border-[#e3ece9] bg-[#f8fbfa] p-5 sm:p-6">
                  <div className="flex items-center gap-3">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-teal-700" aria-hidden="true" />
                    <p className="text-sm font-semibold text-[#17313a]">Searching filing evidence…</p>
                  </div>
                  <p className="text-sm text-slate-600">Reviewing supporting sources and checking citations.</p>
                  <div className="space-y-2.5" aria-hidden="true">
                    <div className="h-2.5 w-3/4 animate-pulse rounded bg-slate-200/70" />
                    <div className="h-2.5 w-5/6 animate-pulse rounded bg-slate-200/70" />
                    <div className="h-2.5 w-1/2 animate-pulse rounded bg-slate-200/70" />
                  </div>
                </div>
              )}

              {!answer && !askLoading && !askError && (
                <div className="flex min-h-[420px] flex-1 flex-col justify-between rounded-xl border border-[#e1ebe8] bg-[#f8fbfa] p-5 sm:p-8">
                  <div>
                    <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl border border-teal-100 bg-white text-teal-700 shadow-sm" aria-hidden="true">
                    <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
                      <path d="M14 3v6h6M8 13h8M8 17h5" />
                    </svg>
                    </div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-teal-800">Start here</p>
                    <h3 className="mt-2 text-2xl font-semibold tracking-tight text-[#102a35]">Ask a filing question</h3>
                    <p className="mt-2 max-w-lg text-sm leading-6 text-slate-600">Choose an indexed SEC filing, ask about its contents, and inspect the source behind each supported claim.</p>
                    <ol aria-label="How to use FinLens" className="mt-7 grid gap-2.5 sm:grid-cols-3">
                      {[
                        ["Select a filing", "Choose a Ready company."],
                        ["Ask a question", "Focus on the filing."],
                        ["Trace evidence", "Open the SEC source."],
                      ].map(([step, detail], index) => (
                        <li key={step} className="min-w-0 rounded-lg border border-[#e2ebe8] bg-white px-3.5 py-3.5 shadow-[0_1px_2px_rgba(16,42,53,0.03)]">
                          <span className="text-[11px] font-bold text-teal-800">0{index + 1}</span>
                          <p className="mt-2 text-xs font-semibold text-[#17313a]">{step}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
                        </li>
                      ))}
                    </ol>
                  </div>
                  <p className="mt-8 border-t border-[#dfe9e6] pt-4 text-xs leading-5 text-slate-600">If the filing evidence is too weak, FinLens withholds the answer.</p>
                </div>
              )}

              {answer && answer.evidence_status === "insufficient" && (
                <div className="max-w-2xl rounded-xl border border-[#dce8e5] bg-[#f8fbfa] px-5 py-6 sm:px-7">
                  <div className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#d7e7e2] bg-white text-teal-800" aria-hidden="true">
                      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M8 4h8l4 4v12H4V4h4Z" /><path d="M16 4v4h4M8 13h8M8 17h5" /></svg>
                    </span>
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-teal-800">Insufficient evidence</p>
                      <h3 className="mt-1.5 text-lg font-semibold leading-7 text-[#102a35]">No unsupported answer was generated.</h3>
                    </div>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-slate-700">{answer.answer}</p>
                  <p className="mt-3 text-xs leading-5 text-slate-600">Try a narrower question or choose another indexed filing.</p>
                </div>
              )}

              {answer && answer.evidence_status === "sufficient" && (
                <>
                  <div className="border-b border-slate-200 pb-7">
                    <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-teal-800">Question</p>
                    <h3 className="mt-2 text-lg font-semibold leading-7 text-[#102a35]">{answer.question}</h3>
                    <div className="mt-6 rounded-xl border border-[#e0eae7] bg-[#f8fbfa] px-5 py-5 sm:px-6">
                      <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-teal-800">Answer</p>
                      <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-[#17313a]">{answer.answer}</p>
                    </div>
                    <p className="mt-4 break-words text-xs leading-5 text-slate-500">
                      {answer.company_name} · {filing?.form ?? "SEC filing"} · accession {answer.accession_number} · model {answer.model}
                    </p>
                  </div>

                  <div className="pt-7">
                    <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-[#17313a]">Claims &amp; sources</h3>
                    <p className="mt-1.5 text-sm text-slate-500">Each claim points to evidence in the selected filing.</p>
                    <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
                      {answer.claims.map((claim, index) => (
                        <article key={index} className="py-5 first:pt-4">
                          <div className="flex items-start gap-3">
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-bold text-teal-800">{index + 1}</span>
                            <div className="min-w-0">
                              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">Claim {index + 1}</p>
                              <p className="mt-1 text-sm leading-7 text-slate-900">{claim.text}</p>
                            </div>
                          </div>
                          <div className="mt-4 space-y-3 pl-0 sm:pl-10">
                            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">Sources</p>
                            {claim.citation_ids.map((citationId) => {
                              const citation = citationForClaim(citationId, answer.citations);
                              if (!citation) return null;
                              return (
                                <div key={citationId} className="min-w-0 rounded-r-lg border-l-[3px] border-teal-600 bg-[#f8fbfa] px-4 py-3.5">
                                  <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                                    <div className="min-w-0">
                                      <p className="text-xs font-bold uppercase tracking-wide text-teal-800">{citationId} <span className="ml-1 font-medium normal-case tracking-normal text-slate-500">· {citation.form}</span></p>
                                      <p className="mt-1 text-sm font-semibold text-[#17313a]">{answer.company_name} <span className="font-normal text-slate-600">· Filed {formatDate(citation.filed)}</span></p>
                                    </div>
                                    <a
                                      href={citation.sec_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="shrink-0 text-xs font-semibold text-teal-800 underline decoration-teal-300 underline-offset-4 hover:text-teal-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
                                    >
                                      Open SEC filing ↗
                                    </a>
                                  </div>
                                  <p className="mt-2.5 break-all font-mono text-[11px] leading-5 text-slate-500">
                                    Accession {citation.accession_number} · {citation.filename} · {citation.chunk_id}
                                  </p>
                                  <p className="mt-0.5 text-[11px] text-slate-500">
                                    Text position {citation.start_char.toLocaleString()}–{citation.end_char.toLocaleString()}
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
