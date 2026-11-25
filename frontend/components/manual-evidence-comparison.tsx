"use client";
import { useId, useImperativeHandle, useLayoutEffect, useRef, useState, type Ref } from "react";
import { downloadEvidenceReport } from "@/lib/evidence-report";
import { MANUAL_COMPARISON_ASSESSMENTS, MANUAL_COMPARISON_FIELD_LIMITS, MANUAL_COMPARISON_LIMIT,
  recordManualComparison, reopenManualComparison, type ManualSourceDraft } from "@/lib/manual-evidence-comparison";

const blankSource = (): ManualSourceDraft => ({ reference: "", passage: "", locator: "", date: "", assessment: "", rationale: "" });

export type ManualComparisonController = { hasNotes: () => boolean; invalidate: () => void };

type ReopenedComparison = ReturnType<typeof reopenManualComparison>;
type FilePreview = { kind: "loading" } | { kind: "error"; message: string } |
  { kind: "ready"; comparison: ReopenedComparison };

function ReopenedPreview({ comparison }: { comparison: ReopenedComparison }) {
  return <section aria-label="Reopened comparison preview">
    <h5>Recorded comparison preview · not verified</h5>
    <p>Read-only preview. The current draft and its download are unchanged.</p>
    <h6>Recorded question</h6>
    <p className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>{comparison.question}</p>
    {comparison.sources.map((source, index) => <section key={index === 0 ? "A" : "B"}>
      <h6>{index === 0 ? "Manual source A" : "Manual source B"} · not verified</h6>
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

export default function ManualEvidenceComparison({ question, isCurrent, controllerRef }: {
  question: string; isCurrent: boolean; controllerRef: Ref<ManualComparisonController>;
}) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const [sources, setSources] = useState(() => [blankSource(), blankSource()]);
  const [judgment, setJudgment] = useState("");
  const [change, setChange] = useState("");
  const [recorded, setRecorded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsReview, setNeedsReview] = useState(false);
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null);
  const fileRead = useRef(0);
  const active = useRef<string | null>(null);
  const revoke = useRef<(() => void) | null>(null);
  function dispose() {
    revoke.current?.();
    revoke.current = null;
  }
  useLayoutEffect(() => () => {
    active.current = null;
    revoke.current?.();
    revoke.current = null;
  }, []);
  useLayoutEffect(() => () => { fileRead.current += 1; }, [question, isCurrent]);
  const limits = MANUAL_COMPARISON_FIELD_LIMITS;

  async function previewFile(file: File | null) {
    const read = ++fileRead.current;
    if (!isCurrent || file === null) { setFilePreview(null); return; }
    if (file.size > MANUAL_COMPARISON_LIMIT) {
      setFilePreview({ kind: "error", message: "Choose a comparison file of 32 KiB or less." });
      return;
    }
    setFilePreview({ kind: "loading" });
    try {
      const buffer = await file.arrayBuffer();
      if (read !== fileRead.current) return;
      const comparison = reopenManualComparison(new Uint8Array(buffer));
      setFilePreview({ kind: "ready", comparison });
    } catch {
      if (read === fileRead.current) setFilePreview({
        kind: "error", message: "Could not open this file. Choose an original FinLens comparison JSON download.",
      });
    }
  }
  function clearRecord() {
    if (active.current !== null) setNeedsReview(true);
    active.current = null;
    dispose();
    setRecorded(null);
    setError(null);
  }
  useImperativeHandle(controllerRef, () => ({
    hasNotes: () => judgment !== "" || change !== "" || sources.some(source => Object.values(source).some(value => value !== "")),
    invalidate: () => { fileRead.current += 1; setFilePreview(null); clearRecord(); },
  }));
  function updateSource(index: number, key: keyof ManualSourceDraft, value: string) {
    clearRecord();
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
      <h4>Compare evidence for and against an explanation</h4>
      <p>Enter two passages yourself. FinLens does not open references or verify these sources. Keep the source’s publication date separate from the event date.</p>
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
      {isCurrent && <div>
        <label>Open a recorded comparison (.json)<input type="file" accept=".json,application/json"
          onChange={event => {
            const input = event.currentTarget;
            const file = input.files?.[0] ?? null;
            input.value = "";
            void previewFile(file);
          }} /></label>
        {filePreview?.kind === "loading" && <p role="status">Reading the local comparison file…</p>}
        {filePreview?.kind === "error" && <p role="alert">{filePreview.message}</p>}
        {filePreview?.kind === "ready" && <ReopenedPreview comparison={filePreview.comparison} />}
      </div>}
    </div>
  </section>;
}
