export type NoteSelector = { session_key: string; session_revision: number; artifact_key: string; artifact_revision: number };
export type SourcePin = { schema_version: 1; record: { kind: "database_publication"; entity_key: { namespace: "sec_cik"; id: string };
  accession: string; data_version: number; evidence_version: number; publication_data_version: number; manifest_sha256: string;
  [key: string]: unknown } };
export type SavedNote = { schema_version: 1; owner_key: { namespace: "principal"; id: string };
  session_key: { namespace: "session"; id: string }; artifact_key: { namespace: "artifact"; id: string };
  session_revision: number; artifact_revision: number; body: string; source: SourcePin;
  source_verification: "unverified_reference"; original_availability: "not_checked" };
export type NoteIndex = { schema_version: 1; owner_key: string; items: (NoteSelector & { preview: string; source_cik: string; source_accession: string })[]; next_cursor: string | null };
export type BrowserIdentity = { status: "authenticated"; owner_key: string; csrf: string; expires_in: number };

export class PrivateWorkspaceError extends Error {
  constructor(public status: number, public code: string) { super("Private research request did not complete."); }
}
const key = (v: unknown): v is string => typeof v === "string" && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(v);
const version = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0;
function requireValue(value: unknown): asserts value { if (!value) throw new PrivateWorkspaceError(502, "INVALID_RESPONSE"); }
export function validatePin(value: unknown): asserts value is SourcePin {
  const v = value as SourcePin;
  requireValue(v?.schema_version === 1 && v.record?.kind === "database_publication"
    && v.record.entity_key?.namespace === "sec_cik" && /^\d{10}$/.test(v.record.entity_key.id)
    && /^\d{10}-\d{2}-\d{6}$/.test(v.record.accession) && /^[0-9a-f]{64}$/.test(v.record.manifest_sha256)
    && [v.record.data_version, v.record.evidence_version, v.record.publication_data_version].every(version)
    && v.record.publication_data_version <= v.record.evidence_version && v.record.evidence_version <= v.record.data_version);
}
function validateSelector(v: NoteSelector) {
  requireValue(key(v?.session_key) && key(v.artifact_key) && version(v.session_revision) && v.session_revision > 0
    && version(v.artifact_revision) && v.artifact_revision > 0);
}
export function noteSelector(note: SavedNote): NoteSelector {
  return { session_key: note.session_key.id, session_revision: note.session_revision,
    artifact_key: note.artifact_key.id, artifact_revision: note.artifact_revision };
}
export async function privateRequest(path: string, signal: AbortSignal, csrf?: string, body?: unknown): Promise<unknown> {
  const controller = new AbortController(), cancel = () => controller.abort();
  signal.addEventListener("abort", cancel, { once: true });
  if (signal.aborted) controller.abort();
  const timer = setTimeout(cancel, 10000);
  try {
    const response = await fetch(`/api/finlens/private-research${path}`, { method: csrf ? "POST" : "GET",
      credentials: "same-origin", cache: "no-store", signal: controller.signal,
      headers: { Accept: "application/json", ...(csrf ? { "Content-Type": "application/json", "X-FinLens-CSRF": csrf } : {}) },
      ...(csrf ? { body: JSON.stringify(body ?? {}) } : {}) });
    // Authentication status is authoritative even if the proxy/error body is
    // absent, malformed, oversized, non-JSON or cannot be read.
    if (response.status === 401 || response.status === 403) {
      void response.body?.cancel().catch(() => {});
      throw new PrivateWorkspaceError(response.status, response.headers.get("X-FinLens-Error-Code") ?? "AUTH_REQUIRED");
    }
    requireValue(response.headers.get("content-type")?.startsWith("application/json"));
    const reader = response.body?.getReader(); requireValue(reader);
    const chunks: Uint8Array[] = []; let size = 0;
    try {
      while (true) { const item = await reader.read(); if (item.done) break;
        size += item.value.length; requireValue(size <= 65536); chunks.push(item.value); }
    } finally { await reader.cancel(); reader.releaseLock(); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!response.ok) throw new PrivateWorkspaceError(response.status, response.headers.get("X-FinLens-Error-Code")
      ?? (typeof value?.code === "string" ? value.code : "REQUEST_FAILED"));
    return value;
  } finally { clearTimeout(timer); signal.removeEventListener("abort", cancel); }
}
export async function browserIdentity(signal: AbortSignal): Promise<BrowserIdentity> {
  const v = await privateRequest("/state", signal) as BrowserIdentity;
  requireValue(v?.status === "authenticated" && key(v.owner_key) && /^[A-Za-z0-9_-]{43}$/.test(v.csrf)
    && version(v.expires_in) && v.expires_in <= 300); return v;
}
export async function discoverNotes(owner: string, signal: AbortSignal, after?: string): Promise<NoteIndex> {
  const v = await privateRequest(`/notes${after ? `?after=${encodeURIComponent(after)}` : ""}`, signal) as NoteIndex;
  requireValue(v?.schema_version === 1 && v.owner_key === owner && Array.isArray(v.items) && v.items.length <= 20
    && (v.next_cursor === null || key(v.next_cursor)));
  const seen = new Set<string>();
  for (const item of v.items) { validateSelector(item); requireValue(!seen.has(item.artifact_key) && typeof item.preview === "string"
    && item.preview.length <= 320 && /^\d{10}$/.test(item.source_cik) && /^\d{10}-\d{2}-\d{6}$/.test(item.source_accession)); seen.add(item.artifact_key); }
  requireValue(v.next_cursor === null || v.next_cursor === v.items.at(-1)?.artifact_key); return v;
}
export async function discoverSources(owner: string, cik: string, signal: AbortSignal): Promise<SourcePin[]> {
  const v = await privateRequest(`/sources?cik=${encodeURIComponent(cik)}`, signal) as {
    owner_key: string; sources: SourcePin[]; source_verification: string; original_availability: string };
  requireValue(v?.owner_key === owner && Array.isArray(v.sources) && v.sources.length <= 100
    && v.source_verification === "unverified_reference" && v.original_availability === "not_checked");
  const seen = new Set<string>();
  for (const item of v.sources) { validatePin(item); requireValue(item.record.entity_key.id === cik && !seen.has(item.record.accession)); seen.add(item.record.accession); }
  return v.sources;
}
export function validateNote(value: unknown, owner: string, selector?: NoteSelector): asserts value is SavedNote {
  const v = value as SavedNote;
  requireValue(v?.schema_version === 1 && v.owner_key?.namespace === "principal" && v.owner_key.id === owner
    && v.session_key?.namespace === "session" && v.artifact_key?.namespace === "artifact"
    && typeof v.body === "string" && new TextEncoder().encode(v.body).length <= 16384
    && v.source_verification === "unverified_reference" && v.original_availability === "not_checked");
  validateSelector(noteSelector(v)); validatePin(v.source);
  if (selector) requireValue(JSON.stringify(noteSelector(v)) === JSON.stringify({ session_key: selector.session_key,
    session_revision: selector.session_revision, artifact_key: selector.artifact_key, artifact_revision: selector.artifact_revision }));
}
function exactJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "undefined";
  if (Array.isArray(value)) return `[${value.map(exactJson).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map(key => `${JSON.stringify(key)}:${exactJson(record[key])}`).join(",")}}`;
}
export function validateSavedSubmission(value: unknown, owner: string, submitted: { body: string; source: SourcePin }): asserts value is SavedNote {
  try { validateNote(value, owner); }
  catch (failure) {
    const candidate = value as SavedNote;
    if (candidate?.owner_key?.namespace === "principal" && candidate.owner_key.id === owner)
      throw new PrivateWorkspaceError(502, "SAVE_RESPONSE_MISMATCH");
    throw failure;
  }
  const saved = value as SavedNote;
  if (saved.body !== submitted.body || exactJson(saved.source) !== exactJson(submitted.source))
    throw new PrivateWorkspaceError(502, "SAVE_RESPONSE_MISMATCH");
}
export function notePath(selector: NoteSelector, exporting = false) {
  validateSelector(selector);
  return `${exporting ? "/export" : "/note"}?${new URLSearchParams({ session: selector.session_key,
    session_revision: String(selector.session_revision), artifact: selector.artifact_key, artifact_revision: String(selector.artifact_revision) })}`;
}
