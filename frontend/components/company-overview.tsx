import { readyCompanyCount, type Company } from "@/lib/finlens-api";

export default function CompanyOverview({ companies, company, ticker, loading, error, onChange, onRetry }: {
  companies: Company[]; company: Company | undefined; ticker: string;
  loading: boolean; error: string | null; onChange: (ticker: string) => void; onRetry: () => void;
}) {
  return <section className="company-overview panel" aria-labelledby="company-title">
    <div className="company-picker"><label htmlFor="company">Company<select id="company" value={ticker} disabled={loading || !!error} onChange={(event) => onChange(event.target.value)}>
      {loading && <option value="">Loading companies…</option>}{!loading && !companies.length && <option value="">No companies available</option>}
      {companies.map((item) => <option key={item.id} value={item.ticker}>{item.ticker} — {item.name}</option>)}
    </select></label><p className="muted small">{readyCompanyCount(companies)} of {companies.length} companies ready for filing research</p></div>
    {company ? <div className="company-identity"><p className="eyebrow">{company.ticker} · {company.exchange}</p><h2 id="company-title">{company.name}</h2><div className="overview-status"><span className="badge">{company.has_indexed_filing ? "Ready for filing research" : "Not indexed for filing research"}</span><span className="muted small">{company.indexed_filing_count} indexed {company.indexed_filing_count === 1 ? "filing" : "filings"} · Financial availability shown in snapshot. Filing indexing does not establish financial completeness or data freshness.</span></div></div> : <h2 id="company-title">Choose a company</h2>}
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p className="loading-state">Loading companies…</p>}
      {error && <><p role="alert" className="error-state">Could not load the company list. {error}</p>
        <button type="button" className="secondary-button" disabled={loading} onClick={onRetry}>Retry companies</button></>}
    </div>
  </section>;
}
