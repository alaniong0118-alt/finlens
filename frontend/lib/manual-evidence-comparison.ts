export const MANUAL_COMPARISON_LIMIT = 32 * 1024;

export const MANUAL_COMPARISON_FIELD_LIMITS = {
  question: 2000, reference: 2048, passage: 4000, locator: 240, reasoning: 1500,
} as const;

// Classification for a text-only handoff, not verification or permission to fetch.
export function unverifiedPastedReference(value: string | null): string | null {
  if (!value || value.length > MANUAL_COMPARISON_FIELD_LIMITS.reference
      || !value.startsWith("https://") || /[\s\\?#\u0000-\u001f\u007f-\u009f\p{Cf}]/u.test(value)
      || /%(?![0-9a-f]{2})/i.test(value)
      || /%(?:0[0-9a-f]|1[0-9a-f]|7f)/i.test(value)) return null;
  const host = value.slice("https://".length).split("/", 1)[0];
  const labels = host.toLowerCase().split(".");
  const tld = labels.at(-1) || "";
  if (host.length > 253 || labels.length < 2
      || !/^[a-z]{2,63}$/.test(tld)
      || ["local", "internal", "localhost", "onion", "invalid", "test"].includes(tld)
      || labels.some(label => label.startsWith("xn--") || !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" || parsed.hostname !== host.toLowerCase()
        || parsed.username || parsed.password || parsed.port || parsed.search || parsed.hash) return null;
    return value;
  } catch {
    return null;
  }
}

export const MANUAL_COMPARISON_ASSESSMENTS = ["supports", "challenges", "does not distinguish"] as const;

export type ManualSourceDraft = {
  reference: string; passage: string; locator: string; date: string; assessment: string; rationale: string;
};

type Draft = {
  question: string; sources: readonly ManualSourceDraft[]; judgment: string; change: string;
};

function text(value: string, limit: number, label: string, required = true): string {
  if (typeof value !== "string" || value.length > limit || (required && !value.trim())
      || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/.test(value)) {
    throw new Error("Enter a valid " + label + ".");
  }
  for (const character of value) {
    if (character.length === 1 && /[\ud800-\udfff]/.test(character)) throw new Error("Enter valid Unicode text.");
  }
  return value;
}

function date(value: string): string | null {
  if (value === "") return null;
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error("Enter a valid publication date.");
  const time = new Date(value + "T00:00:00.000Z");
  if (!Number.isFinite(time.valueOf()) || time.toISOString().slice(0, 10) !== value || value.startsWith("0000-")) {
    throw new Error("Enter a valid publication date.");
  }
  return value;
}

export function comparisonReference(value: string): string {
  const label = value.trim();
  try {
    const url = new URL(label);
    if (url.protocol === "http:" || url.protocol === "https:") return url.href;
  } catch { /* Not a URL; compare the plain reference below. Never retrieve it. */ }
  return label.toLowerCase();
}

export type ManualFilingPassage = Pick<ManualSourceDraft, "reference" | "passage" | "locator">;

export function fitsManualFilingPassage(source: ManualFilingPassage): boolean {
  try {
    const limits = MANUAL_COMPARISON_FIELD_LIMITS;
    text(source.reference, limits.reference, "source reference");
    text(source.passage, limits.passage, "passage");
    text(source.locator, limits.locator, "locator");
    // A textarea normalizes CR; do not offer a handoff that alters the passage.
    return !source.passage.includes("\r");
  } catch { return false; }
}

export function recordManualComparison(draft: Draft): string {
  const limits = MANUAL_COMPARISON_FIELD_LIMITS;
  if (draft.sources.length !== 2) throw new Error("Provide two manual sources.");
  const sources = draft.sources.map((source, index) => {
    const slot = index === 0 ? "A" : "B";
    const assessment = MANUAL_COMPARISON_ASSESSMENTS.find(value => value === source.assessment);
    if (!assessment) throw new Error("Select an assessment for source " + slot + ".");
    return {
      kind: "manual_unverified",
      reference: text(source.reference, limits.reference, "reference for source " + slot),
      passage: text(source.passage, limits.passage, "passage for source " + slot),
      locator: text(source.locator, limits.locator, "locator for source " + slot, false),
      date: date(source.date),
      assessment,
      rationale: text(source.rationale, limits.reasoning, "assessment rationale for source " + slot),
    };
  });
  if (comparisonReference(sources[0].reference) === comparisonReference(sources[1].reference)) {
    throw new Error("Use two distinct source references.");
  }
  const payload = {
    schema_version: 1,
    kind: "manual_evidence_comparison",
    question: text(draft.question, limits.question, "kept question"),
    sources,
    provisional_judgment: text(draft.judgment, limits.reasoning, "provisional judgment"),
    evidence_that_would_change_judgment: text(draft.change, limits.reasoning, "description of evidence that would change your judgment"),
  };
  const json = JSON.stringify(payload, null, 2) + "\n";
  if (new TextEncoder().encode(json).byteLength > MANUAL_COMPARISON_LIMIT) {
    throw new Error("This comparison exceeds 32 KiB when exported. Shorten the passages or notes.");
  }
  return json;
}

type ReopenedManualComparison = {
  schema_version: 1;
  kind: "manual_evidence_comparison";
  question: string;
  sources: [ReopenedManualSource, ReopenedManualSource];
  provisional_judgment: string;
  evidence_that_would_change_judgment: string;
};

type ReopenedManualSource = Omit<ManualSourceDraft, "date" | "assessment"> & {
  kind: "manual_unverified";
  date: string | null;
  assessment: typeof MANUAL_COMPARISON_ASSESSMENTS[number];
};

function reopenRecord(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("This is not a FinLens manual comparison file.");
  }
  return value as Record<string, unknown>;
}

function reopenText(value: unknown): string {
  if (typeof value !== "string") throw new Error("This comparison file does not contain the required text fields.");
  return value;
}

/** Reads only the exact V1 format generated by recordManualComparison; all source content is unverified text. */
export function reopenManualComparison(selectedBytes: Uint8Array): ReopenedManualComparison {
  if (selectedBytes.byteLength > MANUAL_COMPARISON_LIMIT) throw new Error("This comparison file exceeds 32 KiB.");
  let raw: string;
  let parsed: unknown;
  try {
    raw = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(selectedBytes);
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("This file is not valid UTF-8 FinLens comparison JSON.");
  }
  const envelope = reopenRecord(parsed);
  const { schema_version, kind, question, sources, provisional_judgment, evidence_that_would_change_judgment } = envelope;
  if (schema_version !== 1 || kind !== "manual_evidence_comparison" || !Array.isArray(sources) || sources.length !== 2) {
    throw new Error("This is not a FinLens V1 manual comparison file.");
  }
  const canonical = recordManualComparison({
    question: reopenText(question),
    sources: sources.map((value: unknown): ManualSourceDraft => {
      const { kind, reference, passage, locator, date, assessment, rationale } = reopenRecord(value);
      if (kind !== "manual_unverified") throw new Error("Only unverified manual source records can be reopened.");
      return { reference: reopenText(reference), passage: reopenText(passage), locator: reopenText(locator),
        date: date === null ? "" : reopenText(date), assessment: reopenText(assessment), rationale: reopenText(rationale) };
    }),
    judgment: reopenText(provisional_judgment),
    change: reopenText(evidence_that_would_change_judgment),
  });
  // The exporter is the single schema authority. Exact comparison also rejects
  // extra or duplicate members even though JSON.parse would collapse duplicates.
  if (canonical !== raw) throw new Error("This file is not in the original FinLens manual comparison format.");
  return parsed as ReopenedManualComparison;
}
