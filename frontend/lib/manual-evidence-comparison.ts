export const MANUAL_COMPARISON_LIMIT = 32 * 1024;

export const MANUAL_COMPARISON_FIELD_LIMITS = {
  question: 2000, reference: 2048, passage: 4000, locator: 240, reasoning: 1500,
} as const;

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

function comparisonReference(value: string): string {
  const label = value.trim();
  try {
    const url = new URL(label);
    if (url.protocol === "http:" || url.protocol === "https:") return url.href;
  } catch { /* Not a URL; compare the plain reference below. Never retrieve it. */ }
  return label.toLowerCase();
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
