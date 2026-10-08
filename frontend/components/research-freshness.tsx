"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getFreshness, type CompanyFreshness } from "@/lib/finlens-api";

const VersionContext = createContext({ version: 0, changed: () => {} });
export const useResearchVersion = () => useContext(VersionContext);

export default function ResearchFreshness({ ticker, children, catalogChanged }: {
  ticker: string; children: ReactNode; catalogChanged: (signal: AbortSignal) => Promise<boolean>;
}) {
  const [data, setData] = useState<CompanyFreshness | null>(null);
  const [unavailable, setUnavailable] = useState(false);
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
    controller.current = new AbortController();
    const signal = controller.current.signal;
    getFreshness(ticker, signal).then(next => {
      if (signal.aborted || next.ticker !== ticker || next.data_version < (latest.current?.data_version ?? 0)) return;
      latest.current = next; setData(next); setUnavailable(false);
      reconcileCatalog(next.evidence_version);
    }).catch(() => { if (!signal.aborted) setUnavailable(true); })
      .finally(() => { if (controller.current?.signal === signal) pending.current = false; });
  }, [ticker, reconcileCatalog]);
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
  return <VersionContext.Provider value={{ version: data?.data_version ?? 0, changed: check }}>
    <section className="notice" aria-label="Data freshness" aria-live="polite">
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
      {unavailable && <p className="small">Freshness check unavailable. Previously stored research remains usable; currency is not verified.</p>}
      {catalogPending && <p className="small">Filing availability check pending. FinLens retries on the next freshness check.</p>}
      <p className="small muted">A recent check does not guarantee complete SEC coverage. No live data acquisition is triggered by this page.</p>
    </section>
    {children}
  </VersionContext.Provider>;
}
