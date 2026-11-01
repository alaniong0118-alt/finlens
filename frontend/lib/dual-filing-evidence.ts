import type { Company, FilingContext, FilingSource } from "./finlens-api";
import { validateRiskEvidence } from "@/lib/sec-risk";

const accession = (value: unknown): value is string => typeof value === "string" && /^\d{10}-\d{2}-\d{6}$/.test(value);
const date = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && !value.startsWith("0000-") && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
export const DUAL_FILING_LIMIT = 100;
export type ComparisonFiling = Pick<FilingSource, "accession_number" | "form" | "filed" | "sec_url">;

/** Validate the existing server-owned inventory; URLs are checked, never manufactured for display. */
export function comparisonFilings(company: Company, sources: FilingSource[]): ComparisonFiling[] | null {
  if (typeof company.ticker !== "string" || typeof company.cik !== "string" || !/^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(company.ticker) || !/^\d{10}$/.test(company.cik) || Number(company.cik) === 0
      || typeof company.name !== "string" || !company.name.trim() || company.name.length > 300
      || company.has_indexed_filing !== true || !Array.isArray(sources) || sources.length > 10000) return null;
  const seen = new Set<string>();
  const choices: ComparisonFiling[] = [];
  for (const item of sources) {
    // Unselected/metadata-only records still participate in identity and readiness checks.
    if (!item || typeof item !== "object" || Array.isArray(item) || !accession(item.accession_number) || seen.has(item.accession_number)
        || typeof item.has_filing_chunks !== "boolean"
        || !(item.form === null || typeof item.form === "string" && item.form === item.form.trim() && item.form.length > 0 && item.form.length <= 80 && !/[\u0000-\u001f\u007f]/.test(item.form))
        || !(item.filed === null || date(item.filed))
        || item.sec_url !== `https://www.sec.gov/Archives/edgar/data/${Number(company.cik)}/${item.accession_number.replaceAll("-", "")}/${item.accession_number}-index.html`) return null;
    seen.add(item.accession_number);
    if (!item.has_filing_chunks) continue;
    if (!["10-K", "10-K/A", "10-Q", "10-Q/A"].includes(item.form ?? "") || !date(item.filed) || choices.length >= DUAL_FILING_LIMIT) return null;
    choices.push({ accession_number: item.accession_number, form: item.form, filed: item.filed, sec_url: item.sec_url });
  }
  return choices;
}

export function validateComparisonEvidence(value: unknown, company: Company, filing: ComparisonFiling, query: string, pin: number): asserts value is FilingContext {
  validateRiskEvidence(value, { ticker: company.ticker, cik: company.cik, scope: "filing", accession: filing.accession_number, version: pin, query });
  const result = value as FilingContext;
  // The shared display parser recognizes these as line boundaries, while the
  // SOURCE contract is LF-delimited. Reject rather than drop a qualification.
  if (/[\r\u2028\u2029]/.test(result.context)) throw new Error("Noncanonical source separators.");
  if (result.company_name !== company.name || result.citations.some(c => c.form !== filing.form || c.filed !== filing.filed || c.sec_url !== filing.sec_url)) {
    throw new Error("Evidence does not match the selected filing metadata.");
  }
}
