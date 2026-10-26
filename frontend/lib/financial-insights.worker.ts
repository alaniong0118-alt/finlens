import { InsightBudget, InsightsError, demand, encodedSize, isRecord, preflightInsightsJson, prepareInsights, structuralEntries, validateInsights,
  type InsightIdentity, type PreparedInsights } from "./financial-insights";

export type InsightsPort = { postMessage: (message: unknown, transfer?: Transferable[]) => void };
type PendingAck = { operation: number; sequence: number; resolve: () => void; reject: (e: unknown) => void };
/** Exported seam runs the actual worker protocol in deterministic offline doubles. */
export function createInsightsWorkerRuntime(port: InsightsPort, now = () => performance.now()) {
  let generation = "", identity: InsightIdentity, deadline = Infinity, disposed = false, busy = false, inputSequence = 0;
  let chunks: string[] = [], tail = "", bytes = 0, decoder: TextDecoder | null = null, prepared: PreparedInsights | null = null;
  let ack: PendingAck | null = null, currentOperation = 0, state = "NEW";
  const check = () => { if (disposed) throw new DOMException("Cancelled", "AbortError"); if (now() >= deadline) throw new InsightsError("REQUEST_TIMEOUT", "Financial insights took too long.", 0); };
  function control(type: string, fields: Record<string, unknown> = {}) { const message = { type, generation, ...fields }; demand(encodedSize(message) <= 512 && structuralEntries(message) <= 32, "INSIGHTS_CLIENT_LIMIT"); port.postMessage(message); }
  function fail(error: unknown) {
    if (disposed) return; const e = error instanceof InsightsError ? error : new InsightsError();
    control("FAIL", { operation: currentOperation, code: e.code }); disposed = true; ack?.reject(e); ack = null; chunks = []; tail = ""; prepared = null; decoder = null;
  }
  function append(text: string) {
    tail += text;
    while (tail.length >= 16384) { chunks.push(tail.slice(0, 16384)); tail = tail.slice(16384); }
    demand(chunks.length <= 256 && tail.length < 16384, "INSIGHTS_CLIENT_LIMIT");
  }
  async function batch(value: unknown, operation: number, sequence: number) {
    check(); demand(ack === null);
    const meta = { type: "BATCH", generation, operation, sequence, bytes: encodedSize(value), entries: structuralEntries(value) };
    demand(meta.bytes + encodedSize(meta) + 16 <= 32768 && meta.entries + 8 <= 1024, "INSIGHTS_CLIENT_LIMIT");
    const wait = new Promise<void>((resolve, reject) => { ack = { operation, sequence, resolve, reject }; });
    // Only this bounded display object is cloned. Body JSON parsing stays worker-only.
    port.postMessage({ ...meta, payload: value }); await wait; check();
  }
  async function deliverInitial() {
    const budget = new InsightBudget(check, now); const text = chunks.join("") + tail; chunks = []; tail = "";
    await preflightInsightsJson(text, new InsightBudget(check, now)); check();
    const parsed: unknown = JSON.parse(text); check();
    const response = await validateInsights(parsed, identity, budget); prepared = await prepareInsights(response, budget);
    state = "INITIAL_DELIVERY";
    // Initial chunks are scalar header, one metric or one statement. Assemble by typed parts.
    const { statements, metrics, ...header } = prepared.initial;
    const items: unknown[] = [{ kind: "header", value: header }, ...metrics.map(value => ({ kind: "metric", value })), ...statements.map(value => ({ kind: "statement", value }))];
    let sequence = 0, page: unknown[] = [], size = 2, entries = 0;
    for (const item of items) { await budget.tick(); const n = encodedSize(item) + 1, e = structuralEntries(item) + 1; demand(n <= 32256 && e <= 1000, "INSIGHTS_CLIENT_LIMIT");
      if (page.length && (size + n > 32256 || entries + e > 1000)) { demand(sequence < 4, "INSIGHTS_CLIENT_LIMIT"); await batch({ kind: "initial", items: page }, 0, sequence++); page = []; size = 2; entries = 0; }
      page.push(item); size += n; entries += e;
    }
    if (page.length) { demand(sequence < 4, "INSIGHTS_CLIENT_LIMIT"); await batch({ kind: "initial", items: page }, 0, sequence++); }
    control("OP_COMPLETE", { operation: 0, batches: sequence });
    if (identity.selection.mode === "discover") { prepared = null; state = "DONE"; } else { state = "READY"; deadline = Infinity; }
  }
  async function handle(input: unknown) {
    if (disposed) return;
    try {
      demand(isRecord(input) && typeof input.type === "string");
      if (input.type === "INIT") {
        demand(state === "NEW" && typeof input.generation === "string" && input.generation.length <= 128 && isRecord(input.identity) && typeof input.remaining === "number" && input.remaining > 0 && input.remaining <= 30000);
        generation = input.generation; identity = input.identity as unknown as InsightIdentity; deadline = now() + input.remaining; decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }); state = "READING"; control("STARTED"); return;
      }
      demand(input.generation === generation);
      if (input.type === "ACK") { demand(ack && input.operation === ack.operation && input.sequence === ack.sequence); const accepted = ack; ack = null; accepted.resolve(); return; }
      if (input.type === "PING") { demand(state === "READY" || state === "PAGING"); control("PONG", { nonce: input.nonce }); return; }
      demand(!busy); check();
      if (input.type === "CHUNK") {
        demand(state === "READING" && input.sequence === inputSequence && input.buffer instanceof ArrayBuffer && input.buffer.byteLength <= 16384);
        bytes += input.buffer.byteLength; demand(bytes <= 4194304, "INSIGHTS_CLIENT_LIMIT");
        append(decoder!.decode(input.buffer, { stream: true })); control("INPUT_ACK", { sequence: inputSequence++ }); return;
      }
      if (input.type === "END") { demand(state === "READING" && input.sequence === inputSequence); append(decoder!.decode()); decoder = null; state = "VALIDATING"; busy = true; await deliverInitial(); busy = false; return; }
      demand(input.type === "PAGE" && state === "READY" && prepared && Number.isSafeInteger(input.operation) && (input.operation as number) > currentOperation && typeof input.collection === "string" && Number.isSafeInteger(input.page) && (input.page as number) >= 0 && typeof input.remaining === "number" && input.remaining > 0 && input.remaining <= 5000);
      const collection = prepared.pages.get(input.collection); demand(collection && (input.page as number) < collection.length);
      currentOperation = input.operation as number; deadline = now() + input.remaining; state = "PAGING"; busy = true;
      const records = []; const budget = new InsightBudget(check, now);
      for (const index of collection[input.page as number]) { await budget.tick(); records.push(prepared.record(index)); }
      demand(records.length <= 25); await batch({ kind: "page", collection: input.collection, page: input.page, records }, currentOperation, 0);
      control("OP_COMPLETE", { operation: currentOperation, batches: 1 }); state = "READY"; deadline = Infinity; busy = false;
    } catch (error) { fail(error); }
  }
  return { handle, dispose() { disposed = true; ack?.reject(new DOMException("Cancelled", "AbortError")); ack = null; chunks = []; tail = ""; prepared = null; decoder = null; },
    inspect: () => ({ state, bytes, inputSequence, textChunks: chunks.length, tailUnits: tail.length, outgoing: ack ? 1 : 0, pageCache: 0, nodes: prepared?.nodes.length ?? 0 }) };
}

// Importing this file in Node tests installs no global listener.
const workerGlobal = globalThis as unknown as InsightsPort & { importScripts?: unknown; document?: unknown; addEventListener?: (type: string, listener: (e: MessageEvent) => void) => void };
if (typeof workerGlobal.importScripts === "function" && typeof workerGlobal.document === "undefined") {
  const runtime = createInsightsWorkerRuntime(workerGlobal);
  workerGlobal.addEventListener!("message", event => { void runtime.handle(event.data); });
}
