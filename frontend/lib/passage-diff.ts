export type PassageSpan = Readonly<{ kind: "shared" | "a_only" | "b_only"; text: string }>;
export type PassageDiff = Readonly<
  { status: "compared"; identical: boolean; spans: readonly PassageSpan[] }
  | { status: "unavailable"; reason: string }
>;

export const PASSAGE_DIFF_LIMITS = Object.freeze({ characters: 6000, tokens: 3000, cells: 1_000_000 });
const limitReason = "These excerpts exceed the local wording-comparison limit. Read their full originals below or select a shorter returned excerpt. No partial comparison was produced.";

/** Exact token alignment, not semantic matching. Every original character survives. */
export function comparePassageText(a: unknown, b: unknown): PassageDiff {
  if (typeof a !== "string" || typeof b !== "string") {
    return { status: "unavailable", reason: "Select a nonempty source excerpt from each filing." };
  }
  if (a.length > PASSAGE_DIFF_LIMITS.characters || b.length > PASSAGE_DIFF_LIMITS.characters) {
    return { status: "unavailable", reason: limitReason };
  }
  if (!a.trim() || !b.trim()) {
    return { status: "unavailable", reason: "Select a nonempty source excerpt from each filing." };
  }
  // Whitespace, punctuation, case and Unicode are never normalized. The final
  // alternative includes every remaining code point, including literal markup.
  const tokenize = (text: string) => text.match(/\s+|[\p{L}\p{N}\p{M}_]+|[^\s\p{L}\p{N}\p{M}_]/gu)!;
  const left = tokenize(a), right = tokenize(b);
  if (left.length > PASSAGE_DIFF_LIMITS.tokens || right.length > PASSAGE_DIFF_LIMITS.tokens) {
    return { status: "unavailable", reason: limitReason };
  }
  let prefix = 0, suffix = 0;
  while (prefix < left.length && prefix < right.length && left[prefix] === right[prefix]) prefix++;
  while (suffix < left.length - prefix && suffix < right.length - prefix
    && left[left.length - 1 - suffix] === right[right.length - 1 - suffix]) suffix++;
  const n = left.length - prefix - suffix, m = right.length - prefix - suffix, width = m + 1;
  const cells = (n + 1) * width;
  if (cells > PASSAGE_DIFF_LIMITS.cells) return { status: "unavailable", reason: limitReason };
  // At most 1,000,000 Uint16 cells (2 MB); token count bounds the LCS below 65535.
  const table = new Uint16Array(cells);
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) {
    table[i * width + j] = left[prefix + i] === right[prefix + j]
      ? 1 + table[(i + 1) * width + j + 1]
      : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
  }
  const spans: { kind: PassageSpan["kind"]; text: string }[] = [];
  function append(kind: PassageSpan["kind"], text: string) {
    if (!text) return;
    const previous = spans.at(-1);
    if (previous?.kind === kind) previous.text += text;
    else spans.push({ kind, text });
  }
  append("shared", left.slice(0, prefix).join(""));
  let i = 0, j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && left[prefix + i] === right[prefix + j]) {
      append("shared", left[prefix + i]); i++; j++;
    } else if (i < n && (j === m || table[(i + 1) * width + j] >= table[i * width + j + 1])) {
      // Stable tie rule: A-only before B-only. No chronological inference.
      append("a_only", left[prefix + i++]);
    } else append("b_only", right[prefix + j++]);
  }
  append("shared", suffix ? left.slice(left.length - suffix).join("") : "");
  return { status: "compared", identical: a === b, spans };
}
