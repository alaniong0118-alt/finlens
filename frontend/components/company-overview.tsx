import { readyCompanyCount, type Company } from "@/lib/finlens-api";

export default function CompanyOverview({ companies, company, ticker, loading, error, onChange }: {
  companies: Company[]; company: Company | undefined; ticker: string;
  loading: boolean; error: string | null; onChange: (ticker: string) => void;
}) {
  return <section className="company-overview panel" aria-labelledby="company-title">
    <div className="company-picker"><label htmlFor="company">Company<select id="company" value={ticker} disabled={loading || !!error} onChange={(event) => onChange(event.target.value)}>
      {loading && <option value="">Loading companies…</option>}{!loading && !companies.length && <option value="">No companies available</option>}
      {companies.map((item) => <option key={item.id} value={item.ticker}>{item.ticker} — {item.name}</option>)}
    </select></label><p className="muted small">{readyCompanyCount(companies)} of {companies.length} companies ready for filing research</p></div>
    {company ? <div className="company-identity"><p className="eyebrow">{company.ticker} · {company.exchange}</p><h2 id="company-title">{company.name}</h2><div className="overview-status"><span className="badge">{company.has_indexed_filing ? "Ready" : "Not indexed"}</span><span className="muted small">{company.indexed_filing_count} indexed {company.indexed_filing_count === 1 ? "filing" : "filings"} · Financial availability shown in snapshot</span></div></div> : <h2 id="company-title">Choose a company</h2>}
    {error && <p role="alert" className="error-state">{error}</p>}
  </section>;
}
