"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { describeApiError, firstReadyCompany, getCapabilities, getHomeCatalog, type Company, type Capabilities } from "@/lib/finlens-api";
import CompanyOverview from "@/components/company-overview";
import FinancialResearch from "@/components/financial-research";
import FinancialInsights from "@/components/financial-insights";
import FilingResearch from "@/components/filing-research";
import ManualEvidenceComparison, { RecordedComparisonPicker, type ManualComparisonController } from "@/components/manual-evidence-comparison";
import { unverifiedPastedReference } from "@/lib/manual-evidence-comparison";
import ThemeControl from "@/components/theme-control";
import ResearchFreshness from "@/components/research-freshness";
import CompanyComparison from "@/components/company-comparison";
import SecRiskComparison from "@/components/sec-risk-comparison";
import AnnualPeriodComparison from "@/components/annual-period-comparison";
import QuarterWindowComparison from "@/components/quarter-window-comparison";
import FinancialCoverage from "@/components/financial-coverage";
import BalanceDateComparison from "@/components/balance-date-comparison";
import CashFlowWindowComparison from "@/components/cash-flow-window-comparison";

import { catalogMayContainNintendo, getNintendoInterimNetSales, matchesNintendoIrQuestion, matchesNintendoOperatingProfitQuestion, nintendoSecondQuarterProfit } from "@/lib/nintendo-ir-reference";

import { catalogMayContainWynnMacau, supportsWynnMacauNoticeQuestion, wynnMacauReferences } from "@/lib/wynn-macau-reference";

const nintendoReleaseUrl = "https://www.nintendo.co.jp/ir/pdf/2026/261105e.pdf";
const nintendoReleaseDate = "2026-11-05";

function NintendoIrReference({ keptReference = "", onAddQ1 }: { keptReference?: string; onAddQ1?: () => void }) {
  const report = getNintendoInterimNetSales(keptReference);
  const formatDate = (date: string) => new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" }).format(new Date(date));
  return <>
    <p>Nintendo’s Investor Relations site lists its six-month earnings release of <time dateTime={nintendoReleaseDate}>5 November 2026</time> under “Six Months Earnings” for the fiscal year ending March 2027.</p>
    {report && <section aria-label="Curated Nintendo net sales">
      <h4>What Nintendo reported</h4>
      <p>{report.issuer} · Curated from the original release, not fetched live.</p>
      <dl>
        <dt>Actual consolidated net sales</dt>
        <dd>{report.currency} {report.actual.amount} {report.unit} · Six months ended {formatDate(report.actual.periodEnd)}</dd>
        <dt>Nintendo full-year forecast at publication (not actual)</dt>
        <dd>{report.currency} {report.forecast.amount} {report.unit} · Year ending {formatDate(report.forecast.periodEnd)}</dd>
      </dl>
      <p>This release does not establish full-year actual sales or prove why sales changed.</p>
      <a className="source-link" href={`${report.pdf}#page=${report.page}`} referrerPolicy="no-referrer">Nintendo release, page {report.page} (official PDF)</a>
    </section>}
    {matchesNintendoOperatingProfitQuestion(keptReference) && <section aria-label="Nintendo operating profit source notes">
      <h4>What this release says about operating profit</h4>
      <dl>
        <dt>Reported results</dt>
        <dd>For the six months ended 30 September 2026, Nintendo reported that consolidated net sales fell 12.1% and operating profit rose 49.1% year over year.</dd>
        <dt>Management explanation</dt>
        <dd>Nintendo attributed the operating profit increase to software making up a larger share of sales and a first-quarter U.S. tariff refund.</dd>
        <dt>What remains unknown</dt>
        <dd>This section does not quantify how much each factor contributed. The explanation is the issuer’s account, not independent proof.</dd>
      </dl>
      <p><a className="source-link" href={nintendoReleaseUrl + "#page=3"} referrerPolicy="no-referrer">Management discussion, page 3 (official PDF)</a></p>
      <p><a className="source-link" href={nintendoReleaseUrl + "#page=1"} referrerPolicy="no-referrer">Reported figures, page 1 (official PDF)</a></p>
      <section aria-label="Second-quarter profit check">
        <h5>Did higher profit persist into the second quarter?</h5>
        <p>Subtracting first-quarter operating profit from the half-year result yields JPY {nintendoSecondQuarterProfit.current.toLocaleString("en-GB")} million for July to September 2026, versus JPY {nintendoSecondQuarterProfit.prior.toLocaleString("en-GB")} million a year earlier. That is down {Math.abs(nintendoSecondQuarterProfit.changePct).toFixed(1)}% year over year.</p>
        <p>The half-year increase did not persist in that quarter. This calculation does not prove what caused the difference or independently verify Nintendo’s explanation.</p>
        <p><a className="source-link" href={nintendoSecondQuarterProfit.reportedQ1 + "#page=1"} referrerPolicy="no-referrer">First-quarter figures, page 1 (official PDF)</a></p>
        {onAddQ1 && <button type="button" className="secondary-button" onClick={onAddQ1}>
          Add first-quarter reference to comparison
        </button>}
      </section>
    </section>}
    <p className="small muted">Use this guide to find the source. Opening the issuer’s site does not add Nintendo or its figures to your research.</p>
    <p><a className="source-link" href={nintendoReleaseUrl} referrerPolicy="no-referrer">Nintendo six-month earnings release, 5 November 2026 (official PDF)</a></p>
    <a className="source-link" href="https://www.nintendo.co.jp/ir/en/index.html" referrerPolicy="no-referrer">Nintendo Investor Relations (official site)</a>
  </>;
}

function WynnMacauOfficialGuide({ onAddNotice }: { onAddNotice: () => void }) {
  return <section aria-label="Wynn Macau official source guide">
    <h4>Official sources for Wynn Macau, Limited (HKEX 1128)</h4>
    <section aria-label="Listed issuer notice">
      <h5>Listed issuer notice</h5>
      <p>Wynn Macau, Limited · hosted by HKEXnews · Document date: <time dateTime={wynnMacauReferences.documentDate}>27 April 2026</time>.</p>
      <p>This shareholder communications notice does not establish who holds a gaming concession.</p>
      <a className="source-link" href={wynnMacauReferences.disclosure} referrerPolicy="no-referrer">Open the issuer notice on HKEXnews</a>
      <p><button type="button" className="secondary-button" onClick={onAddNotice}>Add issuer notice link to comparison</button></p>
      <p>Only the link is added. Check when the notice was published before adding a publication date.</p>
    </section>
    <section aria-label="Check the licence holder">
      <h5>Check the licence holder separately</h5>
      <p>Do not assume the listed issuer and the licensed company are the same. The regulator’s directory opens separately; FinLens did not verify the licence holder or its current status.</p>
      <a className="source-link" href={wynnMacauReferences.regulator} referrerPolicy="no-referrer">Open the Macao regulator’s casino directory</a>
    </section>
  </section>;
}

export default function Home() {
  const [wynnConfirmation, setWynnConfirmation] = useState<string | null>(null);
  const [researchInput, setResearchInput] = useState("");
  const [researchContext, setResearchContext] = useState<string | null>(null);
  const [manualQuestion, setManualQuestion] = useState<string | null>(null);
  const [pendingReplacement, setPendingReplacement] = useState<string | null>(null);
  const [previousNotesAvailable, setPreviousNotesAvailable] = useState(false);
  const researchInputRef = useRef<HTMLInputElement>(null);
  const manualComparison = useRef<ManualComparisonController>(null);
  function keepQuestion(question: string) {
    setWynnConfirmation(null);
    setManualQuestion(question);
    setResearchContext(question);
    setResearchDraftError(null);
    setPendingReplacement(null);
    setPreviousNotesAvailable(false);
  }
  function restorePreviousQuestion() {
    if (manualQuestion === null) return;
    setResearchInput(manualQuestion);
    keepQuestion(manualQuestion);
    researchInputRef.current?.focus();
  }
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
    setWynnConfirmation(null);
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
      setWynnConfirmation(null);
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
  const pastedReference = unverifiedPastedReference(researchContext);
  const showWynnChoice = researchContext !== null && !loading && error === null
    && completeCatalog === companies && !explicitCompanyChoice
    && supportsWynnMacauNoticeQuestion(researchContext) && !catalogMayContainWynnMacau(companies);
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
          if (manualQuestion !== null && manualQuestion !== researchInput && manualComparison.current?.hasNotes()) {
            setPendingReplacement(researchInput);
            return;
          }
          keepQuestion(researchInput);
        }}>
          <label htmlFor="research-draft-input">Event, question or reference URL</label>
          <input ref={researchInputRef} id="research-draft-input" type="text" aria-label="Event, question or reference URL" maxLength={2000}
            aria-describedby={`research-draft-help${researchDraftError ? " research-draft-error" : ""}`} aria-invalid={!!researchDraftError}
            value={researchInput} onChange={event => {
              const next = event.target.value;
              if (next.length > 2000) { setResearchDraftError("Use 2,000 characters or fewer. Your previous draft is unchanged."); return; }
              setPreviousNotesAvailable(manualComparison.current?.hasNotes() ?? false);
              manualComparison.current?.invalidate();
              setWynnConfirmation(null);
              setResearchInput(next); setResearchContext(null); setResearchDraftError(null); setPendingReplacement(null);
            }} />
          <p className="small muted">{researchInput.length}/2,000 characters</p>
          <button type="submit" className="secondary-button">Keep research draft</button>
          {researchDraftError && <p id="research-draft-error" role="alert">{researchDraftError}</p>}
        </form>
        {researchContext === null && previousNotesAvailable && pendingReplacement === null &&
          <button type="button" className="secondary-button" onClick={restorePreviousQuestion}>Restore previous question</button>}
        {pendingReplacement !== null && <div className="notice" role="group" aria-labelledby="research-replacement-message">
          <p id="research-replacement-message" role="status">Keeping the new question would discard the previous comparison and its notes.
            Cancel to restore the previous question and its notes.</p>
          <button type="button" className="secondary-button" onClick={restorePreviousQuestion}>Cancel replacement</button>
          <button type="button" className="secondary-button" onClick={() => {
            if (researchInput !== pendingReplacement) return;
            keepQuestion(pendingReplacement);
            researchInputRef.current?.focus();
          }}>Discard previous comparison and keep new question</button>
        </div>}
        {researchContext !== null && <div>
          <h3>Unverified research context</h3>
          <p id="research-draft-premise" className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>{researchContext}</p>
          <p>Your wording has not been checked against a source. This draft does not identify or verify a company.</p>
          <p>Check the original source, distinguish its publication date from the event date, and identify the affected company.
            Choose a company below to inspect its existing research. This draft does not start a search.</p>

          {pastedReference && !showNintendoReference && researchContext === manualQuestion && <p>
            <button type="button" className="secondary-button" onClick={() => {
              manualComparison.current?.addReference(pastedReference, "", "pasted");
            }}>Add pasted link to comparison</button>
            <span className="small muted"> Add as unverified reference text only. FinLens will not open or check it.</span>
          </p>}
          {showWynnChoice && <>
            <button type="button" className="secondary-button"
              aria-expanded={wynnConfirmation === researchContext} aria-controls="wynn-official-source-guide"
              onClick={() => setWynnConfirmation(wynnConfirmation === researchContext ? null : researchContext)}>
              {wynnConfirmation === researchContext ? "Cancel issuer confirmation" : "Confirm Wynn Macau, Limited (HKEX 1128)"}
            </button>
            <div id="wynn-official-source-guide">
              {wynnConfirmation === researchContext && <WynnMacauOfficialGuide onAddNotice={() => {
                if (researchContext === manualQuestion) manualComparison.current?.addReference(wynnMacauReferences.disclosure, "");
              }} />}
            </div>
          </>}

          {showNintendoReference && <section aria-label="Nintendo external source">
            <NintendoIrReference keptReference={researchContext} onAddQ1={() => {
              if (researchContext === manualQuestion) {
                manualComparison.current?.addReference(nintendoSecondQuarterProfit.reportedQ1, nintendoSecondQuarterProfit.q1Published);
              }
            }} />
            <button type="button" className="secondary-button" onClick={() => {
              if (researchContext === manualQuestion) manualComparison.current?.addReference(nintendoReleaseUrl, nintendoReleaseDate);
            }}>Add official reference to comparison</button>
          </section>}
        </div>}
        {manualQuestion === null && researchInput === "" && <RecordedComparisonPicker standalone />}
        {manualQuestion !== null && <div hidden={researchContext !== manualQuestion}>
          <ManualEvidenceComparison key={manualQuestion} question={manualQuestion}
            isCurrent={researchContext === manualQuestion} controllerRef={manualComparison} />
        </div>}
      </section>
      <CompanyOverview companies={companies} company={company} ticker={ticker} loading={loading} error={error} onChange={value => { setExplicitCompanyChoice(true); setWynnConfirmation(null); setTicker(value); }} onRetry={loadCatalog} filingResearchEnabled={filingEnabled} />
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
