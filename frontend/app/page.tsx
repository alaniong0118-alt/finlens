"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { describeApiError, firstReadyCompany, getCapabilities, getHomeCatalog, type Company, type Capabilities } from "@/lib/finlens-api";
import CompanyOverview from "@/components/company-overview";
import FinancialResearch from "@/components/financial-research";
import FinancialInsights from "@/components/financial-insights";
import FilingResearch from "@/components/filing-research";
import ThemeControl from "@/components/theme-control";
import ResearchFreshness from "@/components/research-freshness";
import CompanyComparison from "@/components/company-comparison";
import SecRiskComparison from "@/components/sec-risk-comparison";
import AnnualPeriodComparison from "@/components/annual-period-comparison";
import QuarterWindowComparison from "@/components/quarter-window-comparison";
import FinancialCoverage from "@/components/financial-coverage";
import BalanceDateComparison from "@/components/balance-date-comparison";
import CashFlowWindowComparison from "@/components/cash-flow-window-comparison";

import { catalogMayContainNintendo, matchesNintendoIrQuestion } from "@/lib/nintendo-ir-reference";

function NintendoIrReference() {
  return <>
    <p>Nintendo’s Investor Relations site lists its six-month earnings release of <time dateTime="2026-11-05">5 November 2026</time> under “Six Months Earnings” for the fiscal year ending March 2027.</p>
    <p className="small muted">Use this guide to find the source. Opening the issuer’s site does not add Nintendo or its figures to your research.</p>
    <p><a className="source-link" href="https://www.nintendo.co.jp/ir/pdf/2026/261105e.pdf" referrerPolicy="no-referrer">Nintendo six-month earnings release, 5 November 2026 (official PDF)</a></p>
    <a className="source-link" href="https://www.nintendo.co.jp/ir/en/index.html" referrerPolicy="no-referrer">Nintendo Investor Relations (official site)</a>
  </>;
}

export default function Home() {
  const [researchInput, setResearchInput] = useState("");
  const [researchContext, setResearchContext] = useState<string | null>(null);
  const [researchDraftError, setResearchDraftError] = useState<string | null>(null);
  const [explicitCompanyChoice, setExplicitCompanyChoice] = useState(false);
  const [completeCatalog, setCompleteCatalog] = useState<Company[] | null>(null);
  const catalogRead = useRef(0);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const filingEnabled = capabilities?.research_mode === true && capabilities.filing_research_enabled === true;
  const configured = filingEnabled && capabilities?.ai_analysis_enabled === true;
  const initialCatalogController = useRef<AbortController | null>(null);
  const loadCatalog = useCallback(() => {
    if (initialCatalogController.current && !initialCatalogController.current.signal.aborted) return;
    const controller = new AbortController(); initialCatalogController.current = controller;
    const read = ++catalogRead.current;
    setCompleteCatalog(null);
    setLoading(true); setError(null);
    getHomeCatalog(controller.signal).then(({ companies: data, complete }) => {
      if (controller.signal.aborted || read !== catalogRead.current) return;
      setCompanies(data);
      if (complete) setCompleteCatalog(data);
      setTicker(previous => data.some(item => item.ticker === previous) ? previous : firstReadyCompany(data)?.ticker ?? "");
    }).catch((failure) => { if (!controller.signal.aborted && read === catalogRead.current) setError(describeApiError(failure)); })
      .finally(() => {
        if (initialCatalogController.current !== controller) return;
        initialCatalogController.current = null;
        if (!controller.signal.aborted) setLoading(false);
      });
  }, []);
  const catalogController = useRef<AbortController | null>(null);
  const catalogChanged = useCallback(async (signal: AbortSignal): Promise<boolean> => {
    catalogController.current?.abort();
    const controller = new AbortController(); catalogController.current = controller;
    const cancel = () => controller.abort();
    signal.addEventListener("abort", cancel, { once: true });
    try {
      if (signal.aborted) return false;
      const read = ++catalogRead.current;
      setCompleteCatalog(null);
      const { companies: next, complete } = await getHomeCatalog(controller.signal);
      if (signal.aborted || controller.signal.aborted || read !== catalogRead.current) return false;
      setCompanies(next);
      if (complete) setCompleteCatalog(next);
      return true;
    } catch {
      return false;
    } finally {
      signal.removeEventListener("abort", cancel);
    }
  }, []);
  useEffect(() => () => catalogController.current?.abort(), []);
  useEffect(() => {
    loadCatalog();
    return () => { initialCatalogController.current?.abort(); initialCatalogController.current = null; };
  }, [loadCatalog]);
  useEffect(() => {
    const controller = new AbortController();
    setCapabilities(null);
    getCapabilities(controller.signal).then((data) => {
      if (!controller.signal.aborted) setCapabilities(data);
    }).catch(() => { if (!controller.signal.aborted) setCapabilities(null); });
    return () => controller.abort();
  }, []);
  const company = companies.find((item) => item.ticker === ticker);
  const showNintendoReference = researchContext !== null && !loading && error === null
    && completeCatalog === companies && !explicitCompanyChoice
    && matchesNintendoIrQuestion(researchContext) && !catalogMayContainNintendo(companies);
  return <>
    <a className="skip-link" href="#research-workspace">Skip to research workspace</a>
    <header className="app-header"><div className="header-inner">
      <Link href="/" className="brand" aria-label="FinLens home"><span className="brand-mark" aria-hidden="true">F</span><span>FinLens<span className="brand-dot">.</span><small>Evidence-based financial research</small></span></Link>
      <ThemeControl />
    </div></header>
    <main className="workspace" id="research-workspace">
      <div className="hero"><p className="eyebrow">Company data. Official evidence.</p><h1>Understand the numbers.<br className="hero-break" /> Follow the source.</h1>
        <p>Explore reported financials and SEC filings. Research Mode works without AI; grounded analysis is an optional next step.</p>
        <ul className="hero-badges" aria-label="Research capabilities">{["SEC-sourced", "Deterministic metrics", ...(filingEnabled ? ["Hybrid evidence search"] : []), "Traceable sources"].map((label) => <li key={label}>{label}</li>)}</ul>
      </div>
      <details className="panel" style={{ borderStyle: "dashed" }}>
        <summary>Find external company sources</summary>
        <NintendoIrReference />
      </details>
      <section className="panel" aria-labelledby="research-draft-title">
        <h2 id="research-draft-title">Start with an event or question</h2>
        <p id="research-draft-help">Keep a question or reference before choosing a company. This draft stays on this page only.</p>
        <form onSubmit={event => {
          event.preventDefault();
          if (!researchInput.trim()) { setResearchDraftError("Enter an event, question or reference to keep a draft."); return; }
          setResearchContext(researchInput); setResearchDraftError(null);
        }}>
          <label htmlFor="research-draft-input">Event, question or reference URL</label>
          <input id="research-draft-input" type="text" aria-label="Event, question or reference URL" maxLength={2000}
            aria-describedby={`research-draft-help${researchDraftError ? " research-draft-error" : ""}`} aria-invalid={!!researchDraftError}
            value={researchInput} onChange={event => {
              const next = event.target.value;
              if (next.length > 2000) { setResearchDraftError("Use 2,000 characters or fewer. Your previous draft is unchanged."); return; }
              setResearchInput(next); setResearchContext(null); setResearchDraftError(null);
            }} />
          <p className="small muted">{researchInput.length}/2,000 characters</p>
          <button type="submit" className="secondary-button">Keep research draft</button>
          {researchDraftError && <p id="research-draft-error" role="alert">{researchDraftError}</p>}
        </form>
        {researchContext !== null && <div>
          <h3>Unverified research context</h3>
          <p id="research-draft-premise" className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>{researchContext}</p>
          <p>Your wording has not been checked against a source. This draft does not identify or verify a company.</p>
          <p>Check the original source, distinguish its publication date from the event date, and identify the affected company.
            Choose a company below to inspect its existing research. This draft does not start a search.</p>

          {showNintendoReference && <section aria-label="Nintendo external source"><NintendoIrReference /></section>}
        </div>}
      </section>
      <CompanyOverview companies={companies} company={company} ticker={ticker} loading={loading} error={error} onChange={value => { setExplicitCompanyChoice(true); setTicker(value); }} onRetry={loadCatalog} filingResearchEnabled={filingEnabled} />
      <p><Link href="/investigations">Saved investigations</Link></p>
      {!filingEnabled && <p role="status">{capabilities?.filing_research_enabled === false ? "Financial-only capability restriction is active." : "Filing research capabilities are not verified."} Stored financial research remains available. This does not verify runtime readiness or data completeness.</p>}
      <nav className="workspace-nav" aria-label="Research sections"><a href="#insights-title">Annual financial insights</a><a href="#annual-period-title">Annual period comparison</a><a href="#quarter-window-title">Reported windows</a><a href="#balance-date-title">Balance dates</a><a href="#snapshot-title">Company research</a><a href="#history-title">Historical trends</a><a href="#filing-title">SEC research</a><a href="#comparison-title">Company comparison</a><a href="#risk-comparison-title">Compare SEC risk evidence</a><span>AI Analysis · optional</span></nav>
      {company && <ResearchFreshness key={company.ticker} ticker={company.ticker} catalogChanged={catalogChanged}>
        <FinancialInsights company={company} />
        <AnnualPeriodComparison company={company} />
        <QuarterWindowComparison company={company} />
        <BalanceDateComparison company={company} />
        <CashFlowWindowComparison company={company} />
        <FinancialCoverage company={company} />
        <div className="research-grid"><FinancialResearch company={company} /><FilingResearch company={company} configured={configured} filingResearchEnabled={filingEnabled} /></div>
      </ResearchFreshness>}
      <CompanyComparison companies={companies} />
      {filingEnabled ? <SecRiskComparison companies={companies} /> : <section className="panel" aria-labelledby="risk-comparison-title"><h2 id="risk-comparison-title">SEC risk evidence unavailable</h2><p>Filing retrieval is not enabled in this workspace. No risk evidence requests are sent.</p></section>}
      <footer>Financial research and education. No investment recommendations or price forecasts. Reported values and available coverage vary by issuer and period.</footer>
    </main>
  </>;
}
