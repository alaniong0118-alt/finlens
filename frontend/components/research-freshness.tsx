"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getFreshness, type CompanyFreshness } from "@/lib/finlens-api";

// Zero is a valid publication. Only null means freshness has not established a pin.
const VersionContext = createContext<{ version: number | null; changed: () => void }>({ version: null, changed: () => {} });
export const useResearchVersion = () => useContext(VersionContext);

export default function ResearchFreshness({ ticker, children, catalogChanged }: {
  ticker: string; children: ReactNode; catalogChanged: (signal: AbortSignal) => Promise<boolean>;
}) {
  const [data, setData] = useState<CompanyFreshness | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [checking, setChecking] = useState(false);
  const [publicationChanged, setPublicationChanged] = useState(false);
  const publicationInvalidated = useRef(false);
  const rejectedVersion = useRef<number | null>(null);
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const latest = useRef<CompanyFreshness | null>(null);
  const mounted = useRef(true);
  const reconciledEvidenceVersion = useRef(0);
  const catalogController = useRef<AbortController | null>(null);
  const [catalogPending, setCatalogPending] = useState(false);
  const reconcileCatalog = useCallback((version: number) => {
    if (version <= reconciledEvidenceVersion.current || catalogController.current) return;
    const request = new AbortController(); catalogController.current = request;
    setCatalogPending(true);
    catalogChanged(request.signal).then(applied => {
      if (!applied || request.signal.aborted || !mounted.current) return;
      reconciledEvidenceVersion.current = Math.max(reconciledEvidenceVersion.current, version);
      setCatalogPending(reconciledEvidenceVersion.current < (latest.current?.evidence_version ?? 0));
    }).catch(() => { /* Keep reconciliation pending for the next bounded check. */ })
      .finally(() => { if (catalogController.current === request) catalogController.current = null; });
  }, [catalogChanged]);
  const check = useCallback(() => {
    if (pending.current || !mounted.current) return;
    pending.current = true;
    setChecking(true);
    controller.current = new AbortController();
    const signal = controller.current.signal;
    getFreshness(ticker, signal).then(next => {
      if (signal.aborted) return;
      if (next.ticker !== ticker) throw new Error("Publication company does not match");
      if (!Number.isSafeInteger(next.data_version) || next.data_version < 0) throw new Error("Invalid publication version");
      if (next.data_version < (latest.current?.data_version ?? 0)) throw new Error("Publication version regressed");
      if (rejectedVersion.current !== null && next.data_version <= rejectedVersion.current) throw new Error("Rejected publication has not reconciled");
      latest.current = next; setData(next); setUnavailable(false);
      publicationInvalidated.current = false;
      rejectedVersion.current = null;
      setPublicationChanged(false);
      reconcileCatalog(next.evidence_version);
    }).catch(() => { if (!signal.aborted) setUnavailable(true); })
      .finally(() => {
        if (controller.current?.signal !== signal) return;
        pending.current = false;
        if (!signal.aborted) setChecking(false);
      });
  }, [ticker, reconcileCatalog]);
  const publicationVersion = data?.data_version ?? null;
  const changed = useCallback(() => {
    // versionedController retains this callback for its originating publication.
    // Freshness can verify a newer pin before React commits cancellation: an old
    // rejection must not invalidate that independently verified publication.
    if (!mounted.current || publicationVersion === null || publicationVersion !== latest.current?.data_version) return;
    // A rejected pin cannot authorize manual research while reconciliation waits.
    if (!publicationInvalidated.current) {
      publicationInvalidated.current = true;
      rejectedVersion.current = publicationVersion;
      // A check started before the mismatch may itself describe the old version.
      controller.current?.abort(); controller.current = null; pending.current = false;
    }
    setPublicationChanged(true);
    check();
  }, [check, publicationVersion]);
  useEffect(() => {
    mounted.current = true; check();
    const visible = () => { if (!document.hidden) check(); };
    const timer = window.setInterval(visible, 300000);
    window.addEventListener("focus", visible); document.addEventListener("visibilitychange", visible);
    return () => {
      mounted.current = false; controller.current?.abort(); controller.current = null; pending.current = false;
      catalogController.current?.abort(); catalogController.current = null;
      window.clearInterval(timer);
      window.removeEventListener("focus", visible); document.removeEventListener("visibilitychange", visible);
    };
  }, [check]);
  return <VersionContext.Provider value={{ version: publicationChanged ? null : data?.data_version ?? null, changed }}>
    <section className="notice" aria-label="Data freshness" aria-live="polite" aria-busy={checking}>
      <strong>Stored data · {unavailable ? "check unavailable" : data?.status ?? "unknown"}</strong>
      {data && <> · version {data.data_version}<p className="small">Financial facts: {data.facts.status} · Evidence: {data.evidence.status}.
        {data.facts.last_checked_at && <> FinLens checked facts {new Date(data.facts.last_checked_at).toLocaleString()}.</>}
        {data.facts.latest_source_filing_date && <> SEC source filed {data.facts.latest_source_filing_date}.</>}
        {data.latest_indexed_filing && <> Latest published evidence: {data.latest_indexed_filing.form}, filed {data.latest_indexed_filing.filed}.</>}
      </p><details><summary>Freshness scope and synchronization</summary><p className="small">{data.scope}</p>
        <p className="small">Last successful facts sync: {data.facts.last_successful_sync_at ?? "Not verified"}. Last evidence check: {data.evidence.last_checked_at ?? "Not verified"}.
          {data.evidence.pending_targets.length > 0 && <> {data.evidence.pending_targets.length} filing targets pending.</>}</p>
        {data.migration_required && <p className="small">Refresh metadata is not installed. Existing stored research remains available; source currency is unknown.</p>}
      </details></>}
      {unavailable && <><p className="small">{data && !publicationChanged
        ? "Freshness check unavailable. Already loaded research remains available; currency is not verified."
        : "Freshness check unavailable. Could not verify this company’s data version. Retry to load research."}</p>
        <button type="button" className="secondary-button" disabled={checking} onClick={check}>Retry data check</button></>}
      {checking && <p className="small">Checking the company’s published data…</p>}
      {publicationChanged && <p className="small">Published data changed. Research waits until its publication version is verified again.</p>}
      {catalogPending && <p className="small">Filing availability check pending. FinLens retries on the next freshness check.</p>}
      <p className="small muted">A recent check does not guarantee complete SEC coverage. No live data acquisition is triggered by this page.</p>
    </section>
    {children}
  </VersionContext.Provider>;
}
