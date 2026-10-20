"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { describeApiError, firstReadyCompany, getCapabilities, getCompanies, type Company } from "@/lib/finlens-api";
import CompanyOverview from "@/components/company-overview";
import FinancialResearch from "@/components/financial-research";
import FilingResearch from "@/components/filing-research";
import ThemeControl from "@/components/theme-control";
import ResearchFreshness from "@/components/research-freshness";
import CompanyComparison from "@/components/company-comparison";
import SecRiskComparison from "@/components/sec-risk-comparison";

export default function Home() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [configured, setConfigured] = useState(false);
  const initialCatalogController = useRef<AbortController | null>(null);
  const loadCatalog = useCallback(() => {
    if (initialCatalogController.current && !initialCatalogController.current.signal.aborted) return;
    const controller = new AbortController(); initialCatalogController.current = controller;
    setLoading(true); setError(null);
    getCompanies(controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      setCompanies(data);
      setTicker(previous => data.some(item => item.ticker === previous) ? previous : firstReadyCompany(data)?.ticker ?? "");
    }).catch((failure) => { if (!controller.signal.aborted) setError(describeApiError(failure)); })
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
      const next = await getCompanies(controller.signal);
      if (signal.aborted || controller.signal.aborted) return false;
      setCompanies(next);
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
    setConfigured(false);
    getCapabilities(controller.signal).then((data) => {
      if (!controller.signal.aborted) setConfigured(data.ai_analysis_enabled === true);
    }).catch(() => { if (!controller.signal.aborted) setConfigured(false); });
    return () => controller.abort();
  }, []);
  const company = companies.find((item) => item.ticker === ticker);
  return <>
    <a className="skip-link" href="#research-workspace">Skip to research workspace</a>
    <header className="app-header"><div className="header-inner">
      <Link href="/" className="brand" aria-label="FinLens home"><span className="brand-mark" aria-hidden="true">F</span><span>FinLens<span className="brand-dot">.</span><small>Evidence-based financial research</small></span></Link>
      <ThemeControl />
    </div></header>
    <main className="workspace" id="research-workspace">
      <div className="hero"><p className="eyebrow">Company data. Official evidence.</p><h1>Understand the numbers.<br className="hero-break" /> Follow the source.</h1>
        <p>Explore reported financials and SEC filings. Research Mode works without AI; grounded analysis is an optional next step.</p>
        <ul className="hero-badges" aria-label="Research capabilities">{["SEC-sourced", "Deterministic metrics", "Hybrid evidence search", "Traceable sources"].map((label) => <li key={label}>{label}</li>)}</ul>
      </div>
      <CompanyOverview companies={companies} company={company} ticker={ticker} loading={loading} error={error} onChange={setTicker} onRetry={loadCatalog} />
      <nav className="workspace-nav" aria-label="Research sections"><a href="#snapshot-title">Company research</a><a href="#history-title">Historical trends</a><a href="#filing-title">SEC research</a><a href="#comparison-title">Company comparison</a><a href="#risk-comparison-title">Compare SEC risk evidence</a><span>AI Analysis · optional</span></nav>
      {company && <ResearchFreshness key={company.ticker} ticker={company.ticker} catalogChanged={catalogChanged}>
        <div className="research-grid"><FinancialResearch company={company} /><FilingResearch company={company} configured={configured} /></div>
      </ResearchFreshness>}
      <CompanyComparison companies={companies} />
      <SecRiskComparison companies={companies} />
      <footer>Financial research and education. No investment recommendations or price forecasts. Reported values and available coverage vary by issuer and period.</footer>
    </main>
  </>;
}
