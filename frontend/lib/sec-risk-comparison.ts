import { getCompanyContext, getFreshness, versionedController, type CompanyContext } from "./finlens-api";
import { riskTopic, validateRiskEvidence } from "./sec-risk";

export type ComparisonIssuer = Readonly<{ ticker: string; cik: string; name: string }>;
export type IssuerPair = readonly [ComparisonIssuer, ComparisonIssuer];
export type ComparisonPin = Readonly<{ dataVersion: number; factsVersion: number; evidenceVersion: number }>;
export type ComparisonColumn = Readonly<{
  issuer: ComparisonIssuer;
  status: "pending" | "evidence" | "insufficient" | "no_publications" | "error" | "timeout" | "cancelled";
  pin?: ComparisonPin;
  result?: CompanyContext;
  message?: string;
}>;
export type RiskComparisonSnapshot = Readonly<{
  generation: number; owner: string; topic: string; query: string; capturedAt: string;
  columns: readonly ComparisonColumn[];
}>;

const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && !Object.is(value, -0);
const validIssuer = (value: unknown): value is ComparisonIssuer => record(value)
  && typeof value.ticker === "string" && /^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(value.ticker)
  && typeof value.cik === "string" && /^[0-9]{10}$/.test(value.cik) && Number(value.cik) !== 0
  && typeof value.name === "string" && value.name.trim().length > 0;

export function comparisonIssuers(catalog: unknown, selection: readonly string[]): IssuerPair | null {
  if (!Array.isArray(catalog) || selection.length !== 2 || selection[0] === selection[1]) return null;
  const captured = selection.map(ticker => {
    const matches = catalog.filter(row => record(row) && row.ticker === ticker);
    const row: unknown = matches[0];
    return matches.length === 1 && validIssuer(row) ? Object.freeze({ ticker: row.ticker, cik: row.cik, name: row.name }) : null;
  });
  if (!captured[0] || !captured[1] || captured[0].cik === captured[1].cik) return null;
  return Object.freeze([captured[0], captured[1]]);
}

export function comparisonChoices(catalog: unknown): ComparisonIssuer[] {
  if (!Array.isArray(catalog)) return [];
  return catalog.filter(validIssuer).filter(row => catalog.filter(item => record(item) && item.ticker === row.ticker).length === 1)
    .map(row => ({ ticker: row.ticker, cik: row.cik, name: row.name }));
}

export function preferredRiskSelection(catalog: unknown): [string, string] {
  return comparisonIssuers(catalog, ["AAPL", "COST"]) ? ["AAPL", "COST"] : ["", ""];
}

export function comparisonFreshness(value: unknown, issuer: ComparisonIssuer): ComparisonPin {
  if (!validIssuer(issuer) || !record(value) || value.ticker !== issuer.ticker
      || !integer(value.data_version) || !integer(value.facts_version) || !integer(value.evidence_version)
      || value.facts_version > value.data_version || value.evidence_version > value.data_version) {
    throw new Error("Company data versions could not be verified.");
  }
  // No unchecked freshness fields are displayed or used as evidence readiness.
  return Object.freeze({ dataVersion: value.data_version, factsVersion: value.facts_version, evidenceVersion: value.evidence_version });
}

export function comparisonEvidence(value: unknown, issuer: ComparisonIssuer, pin: ComparisonPin, topicId: string): CompanyContext {
  const topic = riskTopic(topicId);
  if (!topic || !validIssuer(issuer) || !integer(pin.dataVersion) || !integer(pin.factsVersion) || !integer(pin.evidenceVersion)
      || pin.factsVersion > pin.dataVersion || pin.evidenceVersion > pin.dataVersion) throw new Error("Invalid comparison scope.");
  validateRiskEvidence(value, { ticker: issuer.ticker, cik: issuer.cik, scope: "company", accession: null,
    version: pin.dataVersion, query: topic.query });
  if (!("retrieval_scope" in value) || value.company_name !== issuer.name || value.company_cik !== issuer.cik
      || value.evidence_version !== pin.evidenceVersion) throw new Error("Company evidence versions or identity do not match.");
  return value;
}

export const COMPARISON_DEADLINE_MS = 30_000;
const unavailable = "Evidence unavailable or unverified.";
const timeoutMessage = "The 30-second comparison deadline expired. Submit again to retry.";
type Services = {
  freshness: typeof getFreshness; context: typeof getCompanyContext; pinned: typeof versionedController;
};
type Options = {
  currentOwner: () => string;
  publish: (snapshot: RiskComparisonSnapshot | null) => void;
  services?: Services;
  now?: () => number;
  schedule?: (callback: () => void, milliseconds: number) => ReturnType<typeof setTimeout>;
  unschedule?: (timer: ReturnType<typeof setTimeout>) => void;
};
type Run = {
  snapshot: RiskComparisonSnapshot; deadline: number; active: boolean;
  timer?: ReturnType<typeof setTimeout>; controllers: Map<number, AbortController>;
};

/** One explicit submission, two independent chains. No work starts on setup/render. */
export function createRiskComparison(options: Options) {
  const services = options.services ?? { freshness: getFreshness, context: getCompanyContext, pinned: versionedController };
  const now = options.now ?? (() => performance.now());
  const schedule = options.schedule ?? ((callback, milliseconds) => setTimeout(callback, milliseconds));
  const unschedule = options.unschedule ?? (timer => clearTimeout(timer));
  let mounted = false;
  let generation = 0;
  let current: Run | null = null;

  const owns = (run: Run) => mounted && current === run && options.currentOwner() === run.snapshot.owner;
  const clearTimer = (run: Run) => { if (run.timer !== undefined) { unschedule(run.timer); run.timer = undefined; } };
  function stop(run: Run) {
    run.active = false; clearTimer(run);
    run.controllers.forEach(controller => controller.abort()); run.controllers.clear();
  }
  function emit(run: Run) { if (owns(run)) options.publish(run.snapshot); }
  function expire(run: Run) {
    if (!owns(run) || !run.active) return;
    run.snapshot = { ...run.snapshot, columns: run.snapshot.columns.map(column => column.status === "pending"
      ? { issuer: column.issuer, status: "timeout", message: timeoutMessage } : column) };
    stop(run); emit(run);
  }
  function allowed(run: Run, index: number): boolean {
    if (!owns(run) || !run.active || run.snapshot.columns[index].status !== "pending") return false;
    if (now() >= run.deadline) { expire(run); return false; }
    return true;
  }
  function finish(run: Run, index: number, column: ComparisonColumn) {
    if (!allowed(run, index)) return;
    run.snapshot = { ...run.snapshot, columns: run.snapshot.columns.map((previous, slot) => slot === index ? column : previous) };
    run.controllers.get(index)?.abort(); run.controllers.delete(index);
    if (run.snapshot.columns.every(item => item.status !== "pending")) stop(run);
    emit(run);
  }
  async function chain(run: Run, index: number) {
    const issuer = run.snapshot.columns[index].issuer;
    try {
      if (!allowed(run, index)) return;
      const freshnessController = new AbortController(); run.controllers.set(index, freshnessController);
      const raw = await services.freshness(issuer.ticker, freshnessController.signal);
      if (!allowed(run, index) || run.controllers.get(index) !== freshnessController) return;
      const pin = comparisonFreshness(raw, issuer);
      if (!allowed(run, index)) return;
      // The next request replaces, rather than overlaps, this issuer's freshness GET.
      const controller = services.pinned(pin.dataVersion, () => {
        // requestJson invokes changed before rejecting. A superseded callback cannot
        // invalidate a new generation, another issuer, or even its own settled column.
        if (run.controllers.get(index) !== controller || !allowed(run, index)) return;
        finish(run, index, { issuer, status: "error", message: `${unavailable} Published data changed. Submit again to verify this issuer.` });
      });
      run.controllers.set(index, controller);
      if (!allowed(run, index)) return;
      const response = await services.context(issuer.ticker, issuer.cik, run.snapshot.query, controller.signal);
      if (!allowed(run, index) || run.controllers.get(index) !== controller) return;
      const result = comparisonEvidence(response, issuer, pin, run.snapshot.topic);
      // Validation and result commitment share the ORIGINAL monotonic deadline.
      if (!allowed(run, index)) return;
      finish(run, index, { issuer, pin, result, status: result.searched_accessions.length === 0 ? "no_publications"
        : result.citations.length === 0 ? "insufficient" : "evidence" });
    } catch {
      finish(run, index, { issuer, status: "error", message: unavailable });
    }
  }
  return {
    activate() { mounted = true; },
    deactivate() { mounted = false; if (current) stop(current); current = null; },
    invalidate() { if (current) stop(current); current = null; if (mounted) options.publish(null); },
    reconcile() { if (current && options.currentOwner() !== current.snapshot.owner) this.invalidate(); },
    cancel() {
      const run = current;
      if (!run || !owns(run) || !run.active) return;
      if (now() >= run.deadline) { expire(run); return; }
      run.snapshot = { ...run.snapshot, columns: run.snapshot.columns.map(column => column.status === "pending"
        ? { issuer: column.issuer, status: "cancelled", message: "Comparison cancelled. Submit again to retry." } : column) };
      stop(run); emit(run);
    },
    submit(issuers: IssuerPair, topicId: string, owner: string): boolean {
      if (!mounted || current?.active || options.currentOwner() !== owner || !riskTopic(topicId)
          || !Array.isArray(issuers) || issuers.length !== 2 || !issuers.every(validIssuer)
          || issuers[0].ticker === issuers[1].ticker || issuers[0].cik === issuers[1].cik) return false;
      // Reserve synchronously, before publish/React updates or any request can run.
      const captured = issuers.map(issuer => Object.freeze({ ...issuer }));
      const run: Run = { snapshot: { generation: ++generation, owner, topic: topicId, query: riskTopic(topicId)!.query,
        capturedAt: new Date().toISOString(), columns: captured.map(issuer => ({ issuer, status: "pending" })) },
      deadline: now() + COMPARISON_DEADLINE_MS, active: true, controllers: new Map() };
      current = run;
      run.timer = schedule(() => {
        // Browser timers are approximate. Never terminate early if one fires early.
        const tick = () => { if (!owns(run) || !run.active) return; if (now() >= run.deadline) expire(run);
          else run.timer = schedule(tick, run.deadline - now()); };
        tick();
      }, COMPARISON_DEADLINE_MS);
      emit(run); void chain(run, 0); void chain(run, 1);
      return true;
    },
  };
}
