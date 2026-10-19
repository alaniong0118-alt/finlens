import type { EvidenceContext } from "./finlens-api";

// Search vocabulary only: neither disclosure classification nor a risk model.
export const RISK_TOPICS = Object.freeze([
  Object.freeze({ id: "supply_chain", label: "Supply-chain disruption", query: "supply chain" }),
  Object.freeze({ id: "competition", label: "Competition and demand", query: "competition" }),
  Object.freeze({ id: "cybersecurity", label: "Cybersecurity", query: "cybersecurity" }),
  Object.freeze({ id: "regulation", label: "Legal and regulatory exposure", query: "regulatory" }),
  Object.freeze({ id: "liquidity", label: "Liquidity and financing", query: "liquidity" }),
  Object.freeze({ id: "foreign_exchange", label: "Foreign-exchange exposure", query: "foreign exchange" }),
]);

export const RISK_EXPLANATION = "These are retrieved issuer statements from stored SEC filings. Search relevance is not risk severity or probability, and retrieval does not establish a complete risk assessment. Background matches may not constitute actual risk disclosures. No result does not mean no risk. FinLens makes no investment recommendation.";

export function riskTopic(id: string) {
  return RISK_TOPICS.find(topic => topic.id === id) ?? null;
}

export function riskQueryLabel(query: string): string {
  return RISK_TOPICS.find(topic => topic.query === query.trim())?.label ?? "Custom risk-topic search";
}

export type RiskRequest = Readonly<{
  ticker: string; cik: string; scope: "filing" | "company";
  accession: string | null; version: number; query: string;
}>;

export class RiskEvidenceError extends Error {
  constructor() { super("The evidence response could not be verified. No candidate passages were shown."); }
}

const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && !Object.is(value, -0);
const accession = (value: unknown): value is string => typeof value === "string" && /^[0-9]{10}-[0-9]{2}-[0-9]{6}$/.test(value);
const date = (value: unknown): value is string => typeof value === "string" && /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value)
  && !value.startsWith("0000-") && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
const finite = (value: unknown, max: number): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= max;
const keys = (value: Record<string, unknown>, required: readonly string[], optional: readonly string[] = []) => required.every(key => Object.hasOwn(value, key))
  && Object.keys(value).every(key => required.includes(key) || optional.includes(key));

/** Response consistency only. Publication eligibility/digests remain server-owned. */
export function validateRiskEvidence(value: unknown, expected: RiskRequest): asserts value is EvidenceContext {
  function reject(): never { throw new RiskEvidenceError(); }
  if (!/^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(expected.ticker) || !/^[0-9]{10}$/.test(expected.cik) || Number(expected.cik) === 0
      || !integer(expected.version) || !["filing", "company"].includes(expected.scope)
      || (expected.scope === "filing" ? !accession(expected.accession) : expected.accession !== null)
      || !expected.query.trim() || expected.query !== expected.query.trim() || expected.query.length > 2000 || !record(value)) reject();
  const common = ["ticker", "company_name", "query", "context", "citations", "evidence_status"];
  if (!keys(value, [...common, ...(expected.scope === "filing" ? ["accession_number"]
    : ["retrieval_scope", "company_cik", "data_version", "evidence_version", "searched_accessions", "excluded_publication_count"])])
      || value.ticker !== expected.ticker || value.query !== expected.query
      || typeof value.company_name !== "string" || !value.company_name.trim()
      || typeof value.context !== "string" || value.context.length > 24000
      || !Array.isArray(value.citations) || value.citations.length > 5
      || (value.evidence_status !== "sufficient" && value.evidence_status !== "insufficient")) reject();
  let searched: string[] = [];
  if (expected.scope === "company") {
    if (value.retrieval_scope !== "company" || value.company_cik !== expected.cik || value.data_version !== expected.version
        || !integer(value.evidence_version) || value.evidence_version > expected.version
        || !integer(value.excluded_publication_count) || !Array.isArray(value.searched_accessions)
        || value.excluded_publication_count + value.searched_accessions.length > 20
        || value.searched_accessions.length > 20 || !value.searched_accessions.every(accession)
        || new Set(value.searched_accessions).size !== value.searched_accessions.length) reject();
    searched = value.searched_accessions as string[];
  } else if (value.accession_number !== expected.accession) reject();
  const citations = value.citations as unknown[];
  if (!citations.length) {
    if (value.evidence_status !== "insufficient" || value.context !== "") reject();
    return;
  }
  if (value.evidence_status !== "sufficient") reject();
  const blocks = (value.context as string).split("\n\n");
  if (blocks.length !== citations.length) reject();
  const seen = new Set<string>();
  const filingMetadata = new Map<string, { form: string; filed: string; filename: string }>();
  const fields = ["citation_id", "chunk_id", "accession_number", "form", "filed", "filename", "start_char", "end_char", "sec_url",
    "similarity", "semantic_similarity", "lexical_score", "hybrid_score", "evidence_reason"];
  const identityKeys = ["company_cik", "accession_number", "filename", "chunk_id", "form", "filed", "start_char", "end_char"];
  for (let index = 0; index < citations.length; index++) {
    const citation = citations[index];
    if (!record(citation) || !keys(citation, fields, ["company_cik"])) reject();
    const c = citation as Record<string, unknown>;
    if (c.citation_id !== `source_${index + 1}` || !accession(c.accession_number)
        || (expected.scope === "company" ? c.company_cik !== expected.cik || !searched.includes(c.accession_number)
          : c.accession_number !== expected.accession || Object.hasOwn(c, "company_cik") && c.company_cik !== expected.cik)
        || typeof c.chunk_id !== "string" || !/^chunk_[0-9]{4}$/.test(c.chunk_id)
        || typeof c.form !== "string" || !["10-K", "10-K/A", "10-Q", "10-Q/A"].includes(c.form) || !date(c.filed)
        || typeof c.filename !== "string" || !/^[A-Za-z0-9_.-]{1,255}$/.test(c.filename) || [".", ".."].includes(c.filename)
        || !integer(c.start_char) || !integer(c.end_char) || c.end_char <= c.start_char
        || !finite(c.similarity, 1) || !finite(c.semantic_similarity, 1) || !finite(c.lexical_score, 1) || !finite(c.hybrid_score, 1.6)
        || typeof c.evidence_reason !== "string" || !["strong_lexical", "strong_semantic", "combined"].includes(c.evidence_reason)) reject();
    const key = `${c.accession_number}/${c.chunk_id}`;
    if (seen.has(key)) reject();
    seen.add(key);
    // Distinct chunks of one publication share this backend filing identity.
    const metadata = { form: c.form as string, filed: c.filed as string, filename: c.filename as string };
    const previous = filingMetadata.get(c.accession_number as string);
    if (previous && (previous.form !== metadata.form || previous.filed !== metadata.filed || previous.filename !== metadata.filename)) reject();
    filingMetadata.set(c.accession_number as string, metadata);
    // Exact existing sec_client.build_filing_url contract, checked statically.
    // This expectation is never substituted for the returned clickable URL.
    const url = `https://www.sec.gov/Archives/edgar/data/${Number(expected.cik)}/${(c.accession_number as string).replaceAll("-", "")}/${c.accession_number}-index.html`;
    if (c.sec_url !== url) reject();
    const match = expected.scope === "company"
      ? /^\[SOURCE (source_[1-9][0-9]*)\]\nmetadata: ([^\n]+)\ntext: \|-\n((?:  [^\n]*\n)*)\[END SOURCE \1\]$/.exec(blocks[index])
      : /^\[SOURCE (source_[1-9][0-9]*)\]\nchunk_id: ([^\n]+)\naccession_number: ([^\n]+)\nform: ([^\n]+)\nsimilarity: ((?:0|1)\.[0-9]{6})\ntext: \|-\n((?:  [^\n]*\n)*)\[END SOURCE \1\]$/.exec(blocks[index]);
    if (!match || match[1] !== c.citation_id) reject();
    let body: string;
    if (expected.scope === "company") {
      let metadata: unknown;
      try { metadata = JSON.parse(match![2]); } catch { reject(); }
      if (!record(metadata) || !keys(metadata, identityKeys) || identityKeys.some(key => metadata[key] !== c[key])) reject();
      body = match![3];
    } else {
      if (match![2] !== c.chunk_id || match![3] !== c.accession_number || match![4] !== c.form
          || Math.abs(Number(match![5]) - (c.similarity as number)) > 0.000000501) reject();
      body = match![6];
    }
    const text = body.slice(0, -1).split("\n").map(line => line.slice(2)).join("\n");
    // Python source offsets count code points. Serialization can return fewer
    // characters (e.g. selected-filing CRLF handling), so equality is not required.
    const textLength = Array.from(text).length;
    if (!text.trim() || textLength > 3000 || textLength > (c.end_char as number) - (c.start_char as number)) reject();
  }
}
