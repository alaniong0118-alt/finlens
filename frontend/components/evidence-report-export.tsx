"use client";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { Company, EvidenceContext } from "@/lib/finlens-api";
import { createEvidenceReport, downloadEvidenceReport, EvidenceReportFormatError, evidenceReportCsv, evidenceReportHtml, evidenceReportText } from "@/lib/evidence-report";

export default function EvidenceReportExport({ company, result, dataVersion, referenceOnly, risk = false }: {
  company: Company; result: EvidenceContext; dataVersion: number; referenceOnly: boolean; risk?: boolean;
}) {
  const id = useId();
  const report = useMemo(() => {
    try { return createEvidenceReport(company, result, dataVersion, referenceOnly, risk); } catch { return null; }
  }, [company, result, dataVersion, referenceOnly, risk]);
  const text = report ? evidenceReportText(report) : "";
  const owner = report ? JSON.stringify(report) : "unavailable";
  const [notice, setNotice] = useState<{ owner: string; message: string; error: boolean } | null>(null);
  const download = useRef<(() => void) | null>(null);
  useEffect(() => () => { download.current?.(); download.current = null; }, [owner]);
  function save(format: "text" | "json" | "html" | "csv") {
    if (!report) return;
    download.current?.(); download.current = null;
    try {
      const contents = format === "csv" ? evidenceReportCsv(report) : format === "html" ? evidenceReportHtml(report) : format === "json" ? JSON.stringify(report, null, 2) + "\n" : text;
      download.current = downloadEvidenceReport(contents,
        `finlens-${company.ticker}-evidence-v${dataVersion}.${format === "text" ? "txt" : format}`, format === "html" || format === "csv" ? format : format === "json");
      setNotice({ owner, error: false, message: `${format === "html" ? "Printable HTML" : format === "csv" ? "CSV" : format === "json" ? "JSON" : "Text"} download requested. ${format === "html" ? "Open the saved file in a browser and choose Print. " : ""}Your browser controls saving; this app cannot confirm a saved file.` });
    } catch (error) {
      setNotice({ owner, error: true, message: error instanceof EvidenceReportFormatError ? error.message
        : "The report download could not be prepared. Your evidence is unchanged. Try the download again or select the text in the report preview." });
    }
  }
  return <section className="evidence-report" aria-labelledby={`${id}-title`}>
    <h4 id={`${id}-title`}>Keep an evidence report</h4>
    <p className="small muted">Local text, JSON, CSV or printable HTML of the original completed search and all returned full passages, including collapsed evidence. No AI, financial answer or new source check is included. This is an unsigned snapshot, not guaranteed replay or complete filing coverage.</p>
    {referenceOnly && <p className="notice">Reference only: this report belongs to “{result.query}”, not a different draft or pending question.</p>}
    {!report ? <p role="alert" className="notice">This evidence cannot be represented as a source-backed report. No file was prepared. Search again to obtain verified source details.</p> : <>
      <div className="dual-filing-actions"><button type="button" className="secondary-button" onClick={() => save("text")}>Download evidence report (.txt)</button>
        <button type="button" className="secondary-button" onClick={() => save("json")}>Download evidence data (.json)</button>
        <button type="button" className="secondary-button" onClick={() => save("html")}>Download printable report (.html)</button>
        <button type="button" className="secondary-button" onClick={() => save("csv")}>Download typed evidence (.csv)</button></div>
      <p className="small muted">CSV lists fields by path, type and value. Import columns as text to preserve identifiers and dates. Some source text cannot be safely offered as CSV; JSON retains the original typed data.</p>
      <details className="provenance"><summary>Inspect complete evidence report</summary><div className="details-body">
        <label htmlFor={`${id}-preview`}>Read-only report text</label><textarea id={`${id}-preview`} readOnly value={text} rows={12} style={{ width: "100%", maxWidth: "100%" }} />
      </div></details>
    </>}
    {notice?.owner === owner && <p className={notice.error ? "notice" : "small"} role={notice.error ? "alert" : "status"}>{notice.message}</p>}
  </section>;
}
