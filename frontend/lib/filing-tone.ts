import type { FilingToneResponse, ToneMatch } from "./finlens-api";

export type ToneIdentity = {
  ticker: string; company_cik: string; accession_number: string; chunk_id: string;
  form: string; filed: string; filename: string; sec_url: string;
};

export type TonePart = { text: string; match: ToneMatch | null };

// Python offsets count code points; String.slice counts UTF-16 code units.
// Iterate the untouched response text, preserving CRLF and combining characters.
export function codePointBoundaries(text: string): number[] {
  const boundaries = [0];
  for (const point of text) boundaries.push(boundaries[boundaries.length - 1] + point.length);
  return boundaries;
}

export function toneParts(result: FilingToneResponse): TonePart[] {
  const boundaries = codePointBoundaries(result.text);
  const parts: TonePart[] = [];
  let previous = 0;
  for (const match of result.tone.matches) {
    if (previous < match.start) parts.push({ text: result.text.slice(boundaries[previous], boundaries[match.start]), match: null });
    parts.push({ text: result.text.slice(boundaries[match.start], boundaries[match.end]), match });
    previous = match.end;
  }
  if (previous < boundaries.length - 1) parts.push({ text: result.text.slice(boundaries[previous]), match: null });
  return parts;
}
