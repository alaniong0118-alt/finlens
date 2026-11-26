"use client";
import { useId, useImperativeHandle, useLayoutEffect, useRef, useState, type Ref } from "react";
import { downloadEvidenceReport } from "@/lib/evidence-report";
import { MANUAL_COMPARISON_ASSESSMENTS, MANUAL_COMPARISON_FIELD_LIMITS, MANUAL_COMPARISON_LIMIT,
  canEditReopenedComparison, comparisonReference, fitsManualFilingPassage, recordManualComparison, reopenManualComparison, type ManualFilingPassage, type ManualSourceDraft } from "@/lib/manual-evidence-comparison";

const blankSource = (): ManualSourceDraft => ({ reference: "", passage: "", locator: "", date: "", assessment: "", rationale: "" });

export type ManualComparisonController = {
  hasNotes: () => boolean;
  invalidate: () => void;
  addPassage: (source: ManualFilingPassage) => void;
  addReference: (reference: string, publicationDate: string, origin?: "official" | "pasted") => void;
};

type ReopenedComparison = ReturnType<typeof reopenManualComparison>;
type FilePreview = { kind: "loading" } | { kind: "error"; message: string } |
  { kind: "ready"; comparison: ReopenedComparison; read: number };

function ReopenedPreview({ comparison, standalone }: { comparison: ReopenedComparison; standalone: boolean }) {
  const Title = standalone ? "h3" : "h5";
  const Detail = standalone ? "h4" : "h6";
  return <section aria-label="Reopened comparison preview">
    <Title>Recorded comparison preview · not verified</Title>
    <p>Read-only preview. The current draft and its download are unchanged.</p>
    <Detail>Recorded question</Detail>
    <p className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>{comparison.question}</p>
    {comparison.sources.map((source, index) => <section key={index === 0 ? "A" : "B"}>
      <Detail>{index === 0 ? "Manual source A" : "Manual source B"} · not verified</Detail>
      <dl className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>
        <dt>Source reference</dt><dd>{source.reference}</dd>
        <dt>Passage</dt><dd>{source.passage}</dd>
        <dt>Locator</dt><dd>{source.locator || "Not recorded"}</dd>
        <dt>Publication date</dt><dd>{source.date ?? "Not recorded"}</dd>
        <dt>Assessment</dt><dd>{source.assessment}</dd>
        <dt>Assessment rationale</dt><dd>{source.rationale}</dd>
      </dl>
    </section>)}
    <dl className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>
      <dt>Provisional judgment</dt><dd>{comparison.provisional_judgment}</dd>
      <dt>Evidence that would change the judgment</dt><dd>{comparison.evidence_that_would_change_judgment}</dd>
    </dl>
  </section>;
}

export function RecordedComparisonPicker({ controllerRef, standalone = false, onContinue }: {
  controllerRef?: Ref<{ invalidate: () => void }>;
  standalone?: boolean;
  onContinue?: (comparison: ReopenedComparison) => void;
}) {
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null);
  const fileRead = useRef(0);
  useLayoutEffect(() => () => { fileRead.current += 1; }, []);
  useImperativeHandle(controllerRef, () => ({
    invalidate: () => { fileRead.current += 1; setFilePreview(null); },
  }), []);

  async function previewFile(file: File | null) {
    const read = ++fileRead.current;
    if (file === null) { setFilePreview(null); return; }
    if (file.size > MANUAL_COMPARISON_LIMIT) {
      setFilePreview({ kind: "error", message: "Choose a comparison file of 32 KiB or less." });
      return;
    }
    setFilePreview({ kind: "loading" });
    try {
      const buffer = await file.arrayBuffer();
      if (read !== fileRead.current) return;
      const comparison = reopenManualComparison(new Uint8Array(buffer));
      setFilePreview({ kind: "ready", comparison, read });
    } catch {
      if (read === fileRead.current) setFilePreview({
        kind: "error", message: "Could not open this file. Choose an original FinLens comparison JSON download.",
      });
    }
  }
  return <div>
    <label>Open a recorded comparison (.json)<input type="file" accept=".json,application/json"
      onChange={event => {
        const input = event.currentTarget;
        const file = input.files?.[0] ?? null;
        input.value = "";
        void previewFile(file);
      }} /></label>
    {filePreview?.kind === "loading" && <p role="status">Reading the local comparison file…</p>}
    {filePreview?.kind === "error" && <p role="alert">{filePreview.message}</p>}
    {filePreview?.kind === "ready" && <>
      <ReopenedPreview comparison={filePreview.comparison} standalone={standalone} />
      {standalone && onContinue && (canEditReopenedComparison(filePreview.comparison)
        ? <button type="button" className="secondary-button" onClick={() => {
            if (fileRead.current !== filePreview.read) return;
            fileRead.current += 1;
            onContinue(filePreview.comparison);
          }}>Continue as an editable copy</button>
        : <p className="small muted">This comparison stays read-only because editing would change its original text.</p>)}
    </>}
  </div>;
}

export default function ManualEvidenceComparison({ question, isCurrent, controllerRef, editableCopy }: {
  question: string; isCurrent: boolean; controllerRef: Ref<ManualComparisonController>; editableCopy?: ReopenedComparison;
}) {
  const [expanded, setExpanded] = useState(Boolean(editableCopy));
  const panelId = useId();
  const [sourceNotice, setSourceNotice] = useState("");
  const [sources, setSources] = useState<ManualSourceDraft[]>(() => editableCopy
    ? editableCopy.sources.map(({ reference, passage, locator, date, assessment, rationale }) =>
      ({ reference, passage, locator, date: date ?? "", assessment, rationale }))
    : [blankSource(), blankSource()]);
  const currentSources = useRef(sources);
  currentSources.current = sources;
  const [judgment, setJudgment] = useState(editableCopy?.provisional_judgment ?? "");
  const [change, setChange] = useState(editableCopy?.evidence_that_would_change_judgment ?? "");
  const [recorded, setRecorded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsReview, setNeedsReview] = useState(false);
  const fileController = useRef<{ invalidate: () => void }>(null);
  const active = useRef<string | null>(null);
  const revoke = useRef<(() => void) | null>(null);
  const copyHeading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => { if (editableCopy) copyHeading.current?.focus(); }, [editableCopy]);
  function dispose() {
    revoke.current?.();
    revoke.current = null;
  }
  useLayoutEffect(() => () => {
    active.current = null;
    revoke.current?.();
    revoke.current = null;
  }, []);
  const limits = MANUAL_COMPARISON_FIELD_LIMITS;

  function clearRecord() {
    if (active.current !== null) setNeedsReview(true);
    active.current = null;
    dispose();
    setRecorded(null);
    setError(null);
  }
  useImperativeHandle(controllerRef, () => ({
    hasNotes: () => judgment !== "" || change !== "" || sources.some(source => Object.values(source).some(value => value !== "")),
    invalidate: () => { fileController.current?.invalidate(); clearRecord(); setSourceNotice(""); },
    addPassage: (passage) => {
      if (!isCurrent || !fitsManualFilingPassage(passage)) return;
      setExpanded(true);
      const rows = currentSources.current;
      if (rows.some(source => comparisonReference(source.reference) === comparisonReference(passage.reference))) {
        setSourceNotice("This reference is already in your comparison.");
        return;
      }
      const slot = rows.findIndex(source => Object.values(source).every(value => value === ""));
      if (slot < 0) {
        setSourceNotice("Both sources already contain notes. No notes were replaced.");
        return;
      }
      clearRecord();
      const next = rows.map((source, index) => index === slot ? { ...source, ...passage } : source);
      currentSources.current = next;
      setSources(next);
      setSourceNotice("Filing passage added for your own assessment. No judgment was recorded.");
    },
    addReference: (reference, publicationDate, origin = "official") => {
      if (!isCurrent) return;
      setExpanded(true);
      if (sources.some(source => source.reference.trim() === reference)) {
        setSourceNotice("This reference is already in your comparison.");
        return;
      }
      const slot = sources.findIndex(source => Object.values(source).every(value => value === ""));
      if (slot < 0) {
        setSourceNotice("Both sources already contain notes. No notes were replaced.");
        return;
      }
      clearRecord();
      setSources(previous => previous.map((source, index) => index === slot
        ? { ...source, reference, date: publicationDate } : source));
      setSourceNotice(origin === "pasted"
        ? "Unverified reference added as text only. Check the original and enter the passage and assessment yourself."
        : "Official reference added. Check the original and enter the passage and assessment yourself.");
    },
  }));
  function updateSource(index: number, key: keyof ManualSourceDraft, value: string) {
    clearRecord();
    setSourceNotice("");
    setSources(previous => previous.map((source, slot) => slot !== index ? source : { ...source, [key]: value }));
  }
  function record() {
    clearRecord();
    try {
      const snapshot = recordManualComparison({ question, sources, judgment, change });
      active.current = snapshot;
      setRecorded(snapshot);
      setNeedsReview(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not record this comparison.");
    }
  }
  function download() {
    if (!isCurrent || !recorded || active.current !== recorded) return;
    dispose();
    try {
      revoke.current = downloadEvidenceReport(recorded, "finlens-manual-comparison-v1.json", true);
      setError(null);
    } catch { setError("Could not prepare the download. Your recorded comparison is still here."); }
  }

  return <section className="notice" aria-label="Manual evidence comparison">
    <button type="button" className="secondary-button" aria-expanded={expanded} aria-controls={panelId}
      onClick={() => setExpanded(previous => !previous)}>Compare two manual sources</button>
    <div id={panelId} hidden={!expanded}>
      {sourceNotice && <p role="status">{sourceNotice}</p>}
      <h4 ref={copyHeading} tabIndex={editableCopy ? -1 : undefined}>Compare evidence for and against an explanation</h4>
      {editableCopy && <p>Editable copy from a local file · not verified. Review the earlier judgment and record it again before downloading. The original file is unchanged.</p>}
      <p>Compare two distinct sources. FinLens does not open references or verify the comparison. Keep the source’s publication date separate from the event date.</p>
      {sources.map((source, index) => {
        const slot = index === 0 ? "A" : "B";
        const passageLabel = "Passage " + slot;
        const assessmentLabel = "Assessment " + slot;
        const rationaleLabel = "Assessment rationale " + slot;
        return <fieldset key={slot}>
          <legend>{"Manual source " + slot + " · not verified"}</legend>
          <label>{"Source reference " + slot}<input maxLength={limits.reference} value={source.reference} onChange={event => updateSource(index, "reference", event.target.value)} /></label>
          <label>{passageLabel}<textarea aria-label={passageLabel} rows={3} maxLength={limits.passage} value={source.passage} onChange={event => updateSource(index, "passage", event.target.value)} /></label>
          <label>{"Locator " + slot}<input placeholder="Optional page or section" maxLength={limits.locator} value={source.locator} onChange={event => updateSource(index, "locator", event.target.value)} /></label>
          <label>{"Publication date " + slot}<input type="date" value={source.date} onChange={event => updateSource(index, "date", event.target.value)} /></label>
          <label>{assessmentLabel}<select aria-label={assessmentLabel} value={source.assessment} onChange={event => updateSource(index, "assessment", event.target.value)}>
            <option value="">Choose an assessment</option>
            {MANUAL_COMPARISON_ASSESSMENTS.map(value => <option key={value} value={value}>{value}</option>)}
          </select></label>
          <label>{rationaleLabel}<textarea aria-label={rationaleLabel} rows={2} maxLength={limits.reasoning} value={source.rationale} onChange={event => updateSource(index, "rationale", event.target.value)} /></label>
        </fieldset>;
      })}
      <label>Provisional judgment<textarea aria-label="Provisional judgment" rows={2} maxLength={limits.reasoning} value={judgment} onChange={event => { clearRecord(); setJudgment(event.target.value); }} /></label>
      <label>Evidence that would change the judgment<textarea aria-label="Evidence that would change the judgment" rows={2} maxLength={limits.reasoning} value={change} onChange={event => { clearRecord(); setChange(event.target.value); }} /></label>
      <p>Your assessment is not a verified finding. The current draft stays on this page and its download includes your notes. Nothing is uploaded.</p>
      <button type="button" className="secondary-button" onClick={record}>Record provisional judgment</button>
      {needsReview && <p role="status">This comparison changed. Review your notes and record the comparison again before downloading.</p>}
      {isCurrent && recorded && <><p role="status">Provisional judgment recorded for this draft.</p>
        <button type="button" className="secondary-button" onClick={download}>Download recorded comparison (.json)</button></>}
      {error && <p role="alert">{error}</p>}
      {isCurrent && <RecordedComparisonPicker controllerRef={fileController} />}
    </div>
  </section>;
}
