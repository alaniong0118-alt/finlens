"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { getCompanies, type Company } from "@/lib/finlens-api";
import { browserIdentity, discoverNotes, discoverSources, notePath, noteSelector, privateRequest, PrivateWorkspaceError,
  validateNote, validateSavedSubmission, type BrowserIdentity, type NoteIndex, type NoteSelector, type SavedNote, type SourcePin } from "@/lib/private-workspace";

const unavailable = "Private investigations are not enabled on this server. Public research remains available.";
export default function PrivateWorkspace() {
  const [identity, setIdentity] = useState<BrowserIdentity | null>(null);
  const [index, setIndex] = useState<NoteIndex | null>(null), [note, setNote] = useState<SavedNote | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]), [cik, setCik] = useState("");
  const [sources, setSources] = useState<SourcePin[]>([]), [accession, setAccession] = useState("");
  const [sourcesReady, setSourcesReady] = useState(false);
  const [body, setBody] = useState(""), [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Checking private research availability."), [error, setError] = useState("");
  const [logoutPending, setLogoutPending] = useState(false);
  const live = useRef({ generation: 0, mounted: true, controller: null as AbortController | null, pending: false });
  const session = useRef<BrowserIdentity | null>(null);
  const draft = useRef<{ request_key: string; body: string; source: SourcePin } | null>(null);
  const download = useRef<string | null>(null);
  function clearPrivate() { setIdentity(null); setIndex(null); setNote(null); setCompanies([]); setCik(""); setSources([]); setSourcesReady(false); setAccession(""); setBody(""); draft.current = null;
    if (download.current) { URL.revokeObjectURL(download.current); download.current = null; } }
  async function run(action: (signal: AbortSignal, current: () => boolean) => Promise<void>, kind: "read" | "save" | "logout" = "read") {
    if (live.current.pending) return;
    live.current.controller?.abort(); const controller = new AbortController(), generation = ++live.current.generation;
    live.current.controller = controller; live.current.pending = true; setBusy(true); setError("");
    const current = () => live.current.mounted && generation === live.current.generation && !controller.signal.aborted;
    try { await action(controller.signal, current); }
    catch (failure) {
      if (!current()) return;
      if (failure instanceof PrivateWorkspaceError && ([401, 403].includes(failure.status) || failure.code === "INVALID_RESPONSE")) {
        clearPrivate(); session.current = null; setLogoutPending(false);
        setMessage("Sign-in expired or access changed. Check sign-in again; no private content is retained on this page.");
      } else if (failure instanceof PrivateWorkspaceError && failure.code === "SAVE_RESPONSE_MISMATCH") {
        setMessage("Save not confirmed. Your draft is retained.");
        setError("The save response did not match the submitted text and source pin. Reload saved notes before retrying.");
      } else setError(kind === "logout" ? "Sign-out could not be confirmed. Retry sign out; private content has been cleared."
        : kind === "save" ? "The request did not complete. Reload saved notes before retrying a save; it may have completed."
          : "Private research could not be loaded. Retry explicitly; no source has been substituted.");
    } finally { if (current()) { live.current.pending = false; setBusy(false); } }
  }
  function check() {
    void run(async (signal, current) => {
      clearPrivate(); session.current = null; setMessage("Checking private research availability.");
      let next: BrowserIdentity;
      try { next = await browserIdentity(signal); }
      catch (failure) { if (!current()) return;
        if (failure instanceof PrivateWorkspaceError && [401, 403, 503].includes(failure.status)) {
          setMessage(failure.status === 503 || failure.code === "RELEASE_MODE_BLOCKED" ? unavailable : "Sign-in is required. No sign-in provider is connected by this page."); return;
        } setMessage("Private research availability could not be verified."); throw failure; }
      const saved = await discoverNotes(next.owner_key, signal);
      if (!current()) return;
      session.current = next; setIdentity(next); setIndex(saved); setMessage("Your saved investigations. Drafts stay only on this page until saved.");
      const catalog = await getCompanies(signal);
      if (current()) setCompanies(catalog);
    });
  }
  useEffect(() => {
    const lifecycle = live.current;
    lifecycle.mounted = true; check();
    const forget = () => { lifecycle.generation++; lifecycle.controller?.abort(); lifecycle.pending = false;
      clearPrivate(); session.current = null; setBusy(false); setLogoutPending(false);
      setMessage("Check sign-in again to reopen saved notes."); };
    const restored = (event: PageTransitionEvent) => { if (event.persisted) forget(); };
    window.addEventListener("pagehide", forget); window.addEventListener("pageshow", restored);
    return () => { lifecycle.mounted = false; lifecycle.generation++; lifecycle.controller?.abort();
      lifecycle.pending = false; session.current = null; draft.current = null;
      window.removeEventListener("pagehide", forget); window.removeEventListener("pageshow", restored);
      if (download.current) URL.revokeObjectURL(download.current); };
    // Initial bootstrap only; subsequent identity checks are explicit actions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!identity) return;
    const timer = setTimeout(() => {
      live.current.generation++; live.current.controller?.abort(); live.current.pending = false; setBusy(false);
      clearPrivate(); session.current = null; setMessage("Sign-in expired. Check sign-in again to reopen saved notes.");
    }, identity.expires_in * 1000);
    return () => clearTimeout(timer);
  }, [identity]);
  function refresh(after?: string) { const owner = session.current?.owner_key; if (!owner) return;
    void run(async (signal, current) => { const data = await discoverNotes(owner, signal, after);
      if (current()) { setIndex(previous => after && previous?.owner_key === owner
        ? { ...data, items: [...previous.items, ...data.items] } : data); setNote(null); } }); }
  function chooseCompany(value: string) {
    if (busy) return; setCik(value); setSources([]); setSourcesReady(false); setAccession(""); draft.current = null;
    const owner = session.current?.owner_key; if (!owner || !value) return;
    void run(async (signal, current) => { const data = await discoverSources(owner, value, signal); if (current()) { setSources(data); setSourcesReady(true); } });
  }
  function save(event: FormEvent) {
    event.preventDefault(); const active = session.current, source = sources.find(item => item.record.accession === accession);
    if (!active || !source || !body.trim() || new TextEncoder().encode(body).length > 16384) return;
    if (!draft.current) draft.current = { request_key: crypto.randomUUID(), body, source };
    const captured = draft.current;
    void run(async (signal, current) => {
      const result = await privateRequest("/notes", signal, active.csrf, captured); validateSavedSubmission(result, active.owner_key, captured);
      if (!current()) return;
      setNote(result); setBody(""); draft.current = null; setMessage("Note saved with its original source pin. Source authority and original availability have not been checked.");
      const saved = await discoverNotes(active.owner_key, signal); if (current()) setIndex(saved);
    }, "save");
  }
  function open(selector: NoteSelector, exporting = false) { const owner = session.current?.owner_key; if (!owner) return;
    void run(async (signal, current) => { const result = await privateRequest(notePath(selector, exporting), signal); validateNote(result, owner, selector);
      if (!current()) return;
      if (exporting) {
        if (download.current) URL.revokeObjectURL(download.current);
        download.current = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = download.current; link.download = "finlens-research-note.json";
        link.style.display = "none"; document.body.append(link); link.click(); link.remove();
      } else setNote(result);
    }); }
  function logout() { const active = session.current; if (!active) return;
    clearPrivate(); setLogoutPending(true); setMessage("Signing out of this private workspace.");
    void run(async (signal, current) => { await privateRequest("/logout", signal, active.csrf, {});
      if (current()) { session.current = null; setLogoutPending(false); setMessage("Signed out. Saved notes remain private on the server."); } }, "logout"); }
  return <section className="panel" aria-labelledby="private-workspace-title">
    <h1 id="private-workspace-title">Saved investigations</h1>
    <p role="status" aria-live="polite">{busy ? "Private research request in progress." : message}</p>
    {error && <p role="alert">{error}</p>}
    {logoutPending ? <button type="button" disabled={busy} onClick={logout}>Retry sign out</button> : identity ? <>
      <p>Private to your authenticated account. <button type="button" disabled={busy} onClick={logout}>Sign out</button></p>
      <form onSubmit={save}>
        <h2>Save a research note</h2><p>Your own notes are not verified financial results. Source references are unverified; original availability is not checked.</p>
        <label>Company<select value={cik} disabled={busy} onChange={event => chooseCompany(event.target.value)}>
          <option value="">Choose a company</option>{companies.map(company => <option value={company.cik} key={company.cik}>{company.name} ({company.ticker})</option>)}
        </select></label>
        <label>Stored filing reference<select value={accession} disabled={busy || !sources.length} onChange={event => { setAccession(event.target.value); draft.current = null; }}>
          <option value="">Choose a filing</option>{sources.map(source => <option key={source.record.accession} value={source.record.accession}>{source.record.accession} · stored version {source.record.publication_data_version}</option>)}
        </select></label>
        {cik && sourcesReady && !busy && !sources.length && <p>No stored filing references are available for this company.</p>}
        <label>Research note<textarea rows={4} maxLength={16384} value={body} disabled={busy} onChange={event => { setBody(event.target.value); draft.current = null; }} /></label>
        {new TextEncoder().encode(body).length > 16384 && <p role="alert">This note exceeds the supported text size.</p>}
        <button type="submit" className="primary-button" disabled={busy || !accession || !body.trim() || new TextEncoder().encode(body).length > 16384}>Save note</button>
      </form>
      <h2>Your saved notes</h2><button type="button" disabled={busy} onClick={() => refresh()}>Reload saved notes</button>
      {index?.items.length === 0 && <p>No saved notes yet.</p>}
      <ul>{index?.items.map(item => <li key={item.artifact_key}><p className="wrap-anywhere">{item.preview}</p>
        <p>CIK {item.source_cik} · {item.source_accession} · Unverified source reference</p>
        <button type="button" disabled={busy} onClick={() => open(item)}>Reopen note</button></li>)}</ul>
      {index?.next_cursor && <button type="button" disabled={busy} onClick={() => refresh(index.next_cursor!)}>More saved notes</button>}
      {note && <article aria-label="Opened research note"><h2>Research note</h2><p className="wrap-anywhere" style={{ whiteSpace: "pre-wrap" }}>{note.body}</p>
        <p>Unverified source reference. Original availability not checked. No source has been replaced or fetched.</p>
        <p className="wrap-anywhere">CIK {note.source.record.entity_key.id} · {note.source.record.accession} · Stored version {note.source.record.publication_data_version}</p>
        <details><summary>Exact source pin</summary><p className="mono wrap-anywhere">{note.source.record.manifest_sha256}</p>
          <p>Data version {note.source.record.data_version} · Evidence version {note.source.record.evidence_version}</p></details>
        <button type="button" disabled={busy} onClick={() => open(noteSelector(note), true)}>Export note as JSON</button>
      </article>}
    </> : <button type="button" disabled={busy} onClick={check}>Check sign-in</button>}
  </section>;
}
