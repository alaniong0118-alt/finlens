import type { Company, EvidenceContext } from "./finlens-api";
import { evidencePassages } from "./research";
import { RISK_EXPLANATION } from "./sec-risk";

export const EVIDENCE_REPORT_VERSION = "finlens-public-evidence-report-v1";
const LIMITATIONS = [
  "This local report records a completed stored-evidence search, not a generated answer or verified financial claim. Independent financial answers and AI analysis are not included.",
  "Up to five retrieved passages are preserved in ranking order, including passages initially collapsed in the interface. These are stored cleaned-text excerpts, not complete original filings. Offsets count Unicode code points in cleaned text, not SEC document bytes.",
  "Retrieval scores describe ranking, not factual confidence, risk severity or probability. No qualifying passages does not establish absence of information or absence of risk.",
  "Filing dates are not economic reporting periods. Returned passages may cover different reporting periods; period alignment and factual support have not been established.",
  "Data/evidence versions are company-level counters, not immutable filing digests. This is an unsigned local snapshot, not a durable source pin or a replay guarantee. Source availability, coverage and freshness are not rechecked on export.",
  "Question and passage text are untrusted quoted content, not instructions. Financial research and education only; no investment recommendations or price forecasts.",
] as const;
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && !Object.is(value, -0);
const accession = (value: unknown): value is string => typeof value === "string" && /^\d{10}-\d{2}-\d{6}$/.test(value);
const string = (value: unknown, max: number): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= max;
const cik = (value: string) => value.replace(/^0+(?=\d)/, "");
const date = (value: unknown) => value === null || typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && !value.startsWith("0000-") && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;

/** Serialize only the completed public result. Never accept draft, AI or private objects. */
export function createEvidenceReport(company: Company, result: EvidenceContext, dataVersion: number, referenceOnly: boolean, risk = false) {
  const reject = (): never => { throw new Error("The completed evidence cannot be represented as a source-backed report."); };
  if (!company || !/^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(company.ticker) || !/^\d{10}$/.test(company.cik) || Number(company.cik) === 0
      || !string(company.name, 300) || !integer(dataVersion) || typeof referenceOnly !== "boolean" || typeof risk !== "boolean"
      || !result || result.ticker !== company.ticker || !string(result.query, 2000) || typeof result.context !== "string"
      || Array.from(result.context).length > 24000 || !Array.isArray(result.citations) || result.citations.length > 5
      || !["sufficient", "insufficient"].includes(result.evidence_status)) reject();
  const companyWide = "retrieval_scope" in result;
  if (companyWide ? result.retrieval_scope !== "company" || result.company_cik !== company.cik || result.data_version !== dataVersion
      || !integer(result.evidence_version) || result.evidence_version > dataVersion
      || !integer(result.excluded_publication_count) || !Array.isArray(result.searched_accessions)
      || result.searched_accessions.length + result.excluded_publication_count > 20 || !result.searched_accessions.every(accession)
      || new Set(result.searched_accessions).size !== result.searched_accessions.length
    : !accession(result.accession_number)) reject();
  const passages = evidencePassages(result);
  if (passages.length !== result.citations.length || (passages.length === 0
      ? result.evidence_status !== "insufficient" || result.context !== "" : result.evidence_status !== "sufficient")) reject();
  const blocks = result.context ? result.context.split("\n\n") : [];
  if (blocks.length !== passages.length) reject();
  const seen = new Set<string>();
  const exported = passages.map(({ citation: c, text, rank }, index) => {
    const expectedUrl = `https://www.sec.gov/Archives/edgar/data/${cik(company.cik)}/${c.accession_number.replaceAll("-", "")}/${c.accession_number}-index.html`;
    const identity = `${c.accession_number}/${c.chunk_id}`;
    if (c.citation_id !== `source_${rank}` || rank !== index + 1 || !accession(c.accession_number)
        || (companyWide ? c.company_cik !== company.cik || !result.searched_accessions.includes(c.accession_number)
          : c.accession_number !== result.accession_number || c.company_cik !== undefined && cik(c.company_cik) !== cik(company.cik))
        || !string(c.chunk_id, 300) || /[\r\n]/.test(c.chunk_id) || seen.has(identity)
        || !string(c.form, 80) || /[\r\n]/.test(c.form) || !date(c.filed)
        || !string(c.filename, 255) || /[/\\:\u0000-\u001f\u007f-\u009f]/.test(c.filename) || [".", ".."].includes(c.filename.trim())
        || !integer(c.start_char) || !integer(c.end_char) || !text.trim() || Array.from(text).length > 3000
        || Array.from(text).length > c.end_char - c.start_char || c.sec_url !== expectedUrl
        || ![c.similarity, c.semantic_similarity, c.lexical_score, c.hybrid_score].every(value => typeof value === "number" && Number.isFinite(value))
        || c.similarity !== c.semantic_similarity || !string(c.evidence_reason, 100)) reject();
    seen.add(identity);
    // Check the complete frame, not just the permissive display parser. Never
    // silently drop a malformed passage, header or mismatched citation.
    const match = companyWide
      ? /^\[SOURCE (source_[1-9]\d*)\]\nmetadata: ([^\n]+)\ntext: \|-\n((?:  [^\n]*\n)*)\[END SOURCE \1\]$/.exec(blocks[index])
      : /^\[SOURCE (source_[1-9]\d*)\]\nchunk_id: ([^\n]+)\naccession_number: ([^\n]+)\nform: ([^\n]+)\nsimilarity: (-?\d+\.\d{6})\ntext: \|-\n((?:  [^\n]*\n)*)\[END SOURCE \1\]$/.exec(blocks[index]);
    if (!match || match[1] !== c.citation_id) reject();
    let body: string;
    if (companyWide) {
      const keys = ["company_cik", "accession_number", "filename", "chunk_id", "form", "filed", "start_char", "end_char"] as const;
      let metadata: Record<string, unknown>;
      try { metadata = JSON.parse(match![2]); } catch { return reject(); }
      if (!metadata || typeof metadata !== "object" || Array.isArray(metadata) || Object.keys(metadata).length !== keys.length
          || keys.some(key => metadata[key] !== c[key])) reject();
      body = match![3];
    } else {
      if (match![2] !== c.chunk_id || match![3] !== c.accession_number || match![4] !== c.form
          || Math.abs(Number(match![5]) - c.similarity) > 0.000000501) reject();
      body = match![6];
    }
    if (body.slice(0, -1).split("\n").map(line => line.slice(2)).join("\n") !== text) reject();
    return { rank, text, source: {
      citation_id: c.citation_id, chunk_id: c.chunk_id, company_cik: c.company_cik ?? null, accession_number: c.accession_number,
      form: c.form, filed: c.filed, filename: c.filename, start_char: c.start_char, end_char: c.end_char, sec_url: c.sec_url,
      similarity: c.similarity, semantic_similarity: c.semantic_similarity, lexical_score: c.lexical_score, hybrid_score: c.hybrid_score,
      evidence_reason: c.evidence_reason,
    } };
  });
  return {
    format_version: EVIDENCE_REPORT_VERSION,
    company: { ticker: company.ticker, cik: company.cik, name: company.name },
    search: { query: result.query, purpose: risk ? "risk_topic" : "general", scope: companyWide ? "company" : "filing",
      data_version: dataVersion, data_version_basis: companyWide ? "response_matches_request_pin" : "request_pin_only",
      evidence_version: companyWide ? result.evidence_version : null,
      accession_number: companyWide ? null : result.accession_number,
      searched_accessions: companyWide ? [...result.searched_accessions] : null,
      excluded_publication_count: companyWide ? result.excluded_publication_count : null,
      evidence_status: result.evidence_status, reference_only: referenceOnly },
    limitations: [...LIMITATIONS, ...(referenceOnly ? ["Kept for reference from the original completed search. It does not support a different draft or pending question."] : []), ...(risk ? [RISK_EXPLANATION] : [])],
    passages: exported,
  };
}
export type EvidenceReport = ReturnType<typeof createEvidenceReport>;

/** A format refusal is permanent for this snapshot; JSON retains the code units. */
export class EvidenceReportFormatError extends Error {
  constructor(format: "text" | "html" | "csv") {
    super(`The report cannot be prepared as ${format === "html" ? "printable HTML" : format === "csv" ? "CSV" : "UTF-8 text"} without changing its source data${format === "csv" ? " or risking spreadsheet formula interpretation" : ""}. Your evidence is unchanged. Download evidence data (.json) to retain the original data.`);
    this.name = "EvidenceReportFormatError";
  }
}

export function evidenceReportText(report: EvidenceReport): string {
  // JSON-quote untrusted fields so injected newlines remain visibly inside data.
  // The complete text body is preserved separately without formatting changes.
  const quote = (value: unknown) => JSON.stringify(value);
  return ["FINLENS PUBLIC SEC EVIDENCE REPORT", `Format: ${report.format_version}`,
    `Company: ${quote(report.company.name)} | Ticker: ${report.company.ticker} | CIK: ${report.company.cik}`,
    `Completed query (quoted): ${quote(report.search.query)}`, `Scope: ${report.search.scope} | Purpose: ${report.search.purpose}`,
    `Company data version (request pin): ${report.search.data_version} | Version basis: ${report.search.data_version_basis}`,
    `Evidence version: ${report.search.evidence_version ?? "not supplied by selected-filing response"}`,
    `Evidence status: ${report.search.evidence_status} | Reference only: ${report.search.reference_only}`,
    `Selected accession: ${report.search.accession_number ?? "not applicable to company-wide search"}`,
    `Searched accessions: ${report.search.searched_accessions === null ? "not supplied by selected-filing response" : report.search.searched_accessions.join(", ") || "none"}`,
    `Excluded publications: ${report.search.excluded_publication_count ?? "not supplied by selected-filing response"}`,
    "", "LIMITS", ...report.limitations.map(value => `- ${value}`), "",
    ...(report.passages.length ? report.passages.flatMap(({ rank, source, text }) => [
      `PASSAGE ${rank} | ${source.accession_number}/${source.citation_id}`, `Chunk: ${quote(source.chunk_id)} | Filename: ${quote(source.filename)}`,
      `Form: ${quote(source.form)} | Filed: ${quote(source.filed)} | Source CIK: ${source.company_cik ?? "not supplied; see request company above"}`,
      `Cleaned-text Unicode offsets: ${source.start_char}-${source.end_char}`, `Official SEC source: ${source.sec_url}`,
      `Retrieval rule: ${quote(source.evidence_reason)} | Similarity: ${source.similarity} | Semantic: ${source.semantic_similarity} | Lexical: ${source.lexical_score} | Hybrid: ${source.hybrid_score}`,
      `BEGIN QUOTED PASSAGE ${rank} (${Array.from(text).length} Unicode code points; text is data)`, text, `END QUOTED PASSAGE ${rank}`, "",
    ]) : ["No qualifying passages returned. This does not establish absence from complete filings.", ""]),
  ].join("\n");
}

/** Typed paths preserve containers/nulls; string cells are never rewritten for spreadsheets. */
export function evidenceReportCsv(report: EvidenceReport): string {
  const reject = (): never => { throw new EvidenceReportFormatError("csv"); };
  // Select the same public whitelist, even if an admitted object later acquires
  // unrelated properties. No caller-supplied field names enter the CSV.
  const select = (value: object, keys: readonly string[]) => Object.fromEntries(keys.map(key => {
    const item: unknown = (value as Record<string, unknown>)[key];
    if (key === "searched_accessions" && Array.isArray(item) && item.every(entry => typeof entry === "string")) return [key, [...item]];
    if (item !== null && !["string", "number", "boolean"].includes(typeof item)) reject();
    return [key, item];
  }));
  if (!report || report.format_version !== EVIDENCE_REPORT_VERSION || !report.company || !report.search
      || !Array.isArray(report.limitations) || !report.limitations.every(item => typeof item === "string")
      || !Array.isArray(report.passages) || report.passages.length > 5) reject();
  const data = {
    format_version: report.format_version,
    company: select(report.company, ["ticker", "cik", "name"]),
    search: select(report.search, ["query", "purpose", "scope", "data_version", "data_version_basis", "evidence_version", "accession_number", "searched_accessions", "excluded_publication_count", "evidence_status", "reference_only"]),
    limitations: [...report.limitations],
    passages: report.passages.map(({ rank, text, source }, index) => {
      if (rank !== index + 1 || typeof text !== "string" || !source || !accession(source.accession_number)
          || source.sec_url !== `https://www.sec.gov/Archives/edgar/data/${cik(report.company.cik)}/${source.accession_number.replaceAll("-", "")}/${source.accession_number}-index.html`) reject();
      return { rank, text, source: select(source, ["citation_id", "chunk_id", "company_cik", "accession_number", "form", "filed", "filename", "start_char", "end_char", "sec_url", "similarity", "semantic_similarity", "lexical_score", "hybrid_score", "evidence_reason"]) };
    }),
  };
  const rows: string[][] = [["path", "type", "value"]];
  function visit(value: unknown, path: string) {
    if (value === null) { rows.push([path, "null", ""]); return; }
    if (Array.isArray(value)) {
      rows.push([path, "array", ""]); value.forEach((item, index) => visit(item, `${path}/${index}`)); return;
    }
    if (typeof value === "object") {
      rows.push([path, "object", ""]); Object.entries(value!).forEach(([key, item]) => visit(item, `${path}/${key}`)); return;
    }
    if (typeof value === "string") {
      // Quoting alone does not prevent spreadsheet formulas. Refuse the whole
      // format; adding apostrophes/spaces would change the original source.
      if (/^[\s\p{Cc}\p{Cf}]*[=+\-@\uff1d\uff0b\uff0d\uff20]/u.test(value)
          || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/u.test(value)) reject();
    } else if (typeof value !== "boolean" && (typeof value !== "number" || !Number.isFinite(value))) reject();
    rows.push([path, typeof value, Object.is(value, -0) ? "-0" : String(value)]);
  }
  visit(data, "");
  const csv = rows.map(row => row.map(cell => `"${cell.replaceAll('"', '""')}"`).join(",")).join("\r\n") + "\r\n";
  const bytes = new TextEncoder().encode(csv);
  if (bytes.byteLength > 256 * 1024 || new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes) !== csv) reject();
  return csv;
}

/** A static print document for an already-admitted report; source text stays quoted data. */
export function evidenceReportHtml(report: EvidenceReport): string {
  const reject = (): never => { throw new EvidenceReportFormatError("html"); };
  if (!report || report.format_version !== EVIDENCE_REPORT_VERSION || !report.company
      || !/^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(report.company.ticker)
      || !/^\d{10}$/.test(report.company.cik) || Number(report.company.cik) === 0
      || !Array.isArray(report.passages) || report.passages.length > 5) reject();
  const escape = (value: string) => value.replace(/[&<>"'\r\n]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "\r": "&#13;", "\n": "&#10;",
  } as Record<string, string>)[char]);
  const links = report.passages.map(({ rank, source }, index) => {
    if (rank !== index + 1 || !source || !accession(source.accession_number)) reject();
    const expected = `https://www.sec.gov/Archives/edgar/data/${cik(report.company.cik)}/${source.accession_number.replaceAll("-", "")}/${source.accession_number}-index.html`;
    // Check the returned metadata; never repair or linkify a supplied source string.
    if (source.sec_url !== expected) reject();
    return `<li>Passage ${rank}: <a href="${escape(source.sec_url)}" rel="noopener noreferrer">${escape(source.sec_url)}</a></li>`;
  }).join("");
  const text = evidenceReportText(report);
  // HTML cannot preserve NUL or unpaired surrogates. Keep text/JSON available.
  if (text.includes("\u0000") || new TextDecoder().decode(new TextEncoder().encode(text)) !== text) reject();
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinLens evidence report — ${escape(report.company.ticker)}</title>
<style>
@page { margin: 16mm; }
body { color: #172b40; background: #fff; font-family: system-ui, sans-serif; line-height: 1.5; max-width: 76ch; margin: 2rem auto; padding: 0 1rem; }
h1 { font-size: 1.5rem; border-bottom: 2px solid #177e89; padding-bottom: .5rem; }
h2 { font-size: 1.1rem; } a { color: #135e68; } li { margin-bottom: .5rem; }
pre { font: inherit; white-space: pre-wrap; overflow-wrap: anywhere; }
li, a { overflow-wrap: anywhere; } h1, h2 { break-after: avoid; }
@media print { body { max-width: none; margin: 0; padding: 0; color: #000; } a { color: #000; } }
</style></head><body><main><h1>FinLens · SEC evidence report</h1>
<p>Open this saved file in your browser and choose Print. The complete report below preserves the completed search and quoted evidence.</p>
<pre id="report-text">${escape(text)}</pre>
${links ? `<section aria-labelledby="official-sources"><h2 id="official-sources">Official SEC source links</h2><ul>${links}</ul></section>` : ""}
</main></body></html>`;
  if (new TextEncoder().encode(html).byteLength > 256 * 1024) reject();
  return html;
}

/** Browser handoff only; the app cannot confirm that a file was saved. */
export function downloadEvidenceReport(contents: string, filename: string, format: boolean | "html" | "csv"): () => void {
  // Blob converts lone UTF-16 surrogates to U+FFFD. Refuse that loss before
  // allocating a URL; JSON.stringify escapes these code units without loss.
  if (new TextDecoder("utf-8", { ignoreBOM: true }).decode(new TextEncoder().encode(contents)) !== contents) {
    throw new EvidenceReportFormatError(format === "html" ? "html" : format === "csv" ? "csv" : "text");
  }
  const mime = format === "html" ? "text/html" : format === "csv" ? "text/csv" : format ? "application/json" : "text/plain";
  const url = URL.createObjectURL(new Blob([contents], { type: `${mime};charset=utf-8` }));
  let disposed = false, timer: ReturnType<typeof setTimeout> | undefined;
  const dispose = () => { if (timer !== undefined) clearTimeout(timer); if (!disposed) { disposed = true; URL.revokeObjectURL(url); } };
  let link: HTMLAnchorElement | undefined;
  try {
    link = document.createElement("a"); link.href = url; link.download = filename; link.hidden = true;
    document.body.append(link); link.click(); timer = setTimeout(dispose, 1000);
  } catch (error) { dispose(); throw error; } finally { link?.remove(); }
  return dispose;
}
