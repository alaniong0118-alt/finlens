// Local hypothetical receipt transport only; imported results are never restored.
import {formInputs, stable, validateReceipt, type RiskInputs, type RiskReceipt} from "./hypothetical-risk";
import {EXPOSURE_TYPE, stressFormInputs, validateStressReceipt, type StressInputs, type StressReceipt} from "./hypothetical-stress";

export type ReplayMethod = "risk" | "stress";
export type ReplayInputs = RiskInputs | StressInputs;
export type ReplayReceipt = RiskReceipt | StressReceipt;
export const MAX_REPLAY_BYTES = 1048576;
const fail = (): never => {throw new Error("Unsupported or invalid local receipt. Choose a complete receipt from this lab (UTF-8 JSON, at most 1 MiB). Your inputs have been preserved.");};
function requireValue(v: unknown): asserts v {if (!v) fail();}
function record(v: unknown, keys: string[]): asserts v is Record<string, unknown> {
  requireValue(v !== null && typeof v === "object" && !Array.isArray(v));
  const own = Object.keys(v); requireValue(own.length === keys.length && own.every(k => keys.includes(k)));
}
function list(v: unknown, min: number, max: number): asserts v is unknown[] {requireValue(Array.isArray(v) && v.length >= min && v.length <= max);}
function token(v: unknown): asserts v is string {requireValue(typeof v === "string" && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$(?![\s\S])/.test(v));}
function decimal(v: unknown): [bigint, bigint] {
  requireValue(typeof v === "string" && v.length <= 26 && /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?$(?![\s\S])/.test(v) && v.replace(/[^0-9]/g, "").length <= 24);
  const [whole, fraction = ""] = v.split("."); return [BigInt(whole + fraction), BigInt(10) ** BigInt(fraction.length)];
}
function day(v: unknown): asserts v is string {
  requireValue(typeof v === "string" && /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(v) && !v.startsWith("0000"));
  const date = new Date(`${v}T00:00:00.000Z`); requireValue(Number.isFinite(date.valueOf()) && date.toISOString().slice(0, 10) === v);
}
function shock(v: unknown): [bigint, bigint] {const [n,d] = decimal(v); requireValue(n >= -BigInt(100)*d && n <= BigInt(1000)*d); return [n,d];}
// Validate the full editable contract before any form mutation or receipt walk.
export function validateReplayInputs(method: ReplayMethod, v: unknown): ReplayInputs {
  record(v, method === "risk" ? ["reporting_currency","exposure_date","confidence","horizon","portfolio_value","exposures","sessions"] : ["reporting_currency","exposure_date","exposures","scenarios","common_shocks"]);
  requireValue(typeof v.reporting_currency === "string" && /^[A-Z]{3}$(?![\s\S])/.test(v.reporting_currency)); day(v.exposure_date);
  list(v.exposures,1,8); const assets: string[] = [];
  v.exposures.forEach(e => {
    record(e,method === "risk" ? ["asset_id","amount"] : ["asset_id","amount","currency","exposure_type"]);
    token(e.asset_id); decimal(e.amount); requireValue(!assets.includes(e.asset_id)); assets.push(e.asset_id);
    if (method === "stress") requireValue(e.currency === v.reporting_currency && e.exposure_type === EXPOSURE_TYPE);
  });
  const ids = new Set<string>();
  if (method === "risk") {
    requireValue(Number.isInteger(v.horizon) && (v.horizon as number) >= 1 && (v.horizon as number) <= 20);
    const [n,d] = decimal(v.confidence); requireValue(n > BigInt(0) && n < d);
    if (v.portfolio_value !== null) decimal(v.portfolio_value);
    list(v.sessions,0,120); let previous: string | undefined;
    v.sessions.forEach(s => {
      record(s,["session_id","start","end","factors"]); token(s.session_id); requireValue(!ids.has(s.session_id)); ids.add(s.session_id);
      day(s.start); day(s.end); requireValue(s.start < s.end && (previous === undefined || previous === s.start)); previous = s.end;
      record(s.factors,assets); Object.values(s.factors).forEach(f => requireValue(decimal(f)[0] > BigInt(0)));
    });
  } else {
    list(v.scenarios,1,12); v.scenarios.forEach(s => {
      record(s,["scenario_id","shocks"]); token(s.scenario_id); requireValue(!ids.has(s.scenario_id)); ids.add(s.scenario_id);
      record(s.shocks,assets); Object.values(s.shocks).forEach(shock);
    });
    list(v.common_shocks,1,21); const values: [bigint,bigint][] = [];
    v.common_shocks.forEach(s => {const [n,d] = shock(s); requireValue(!values.some(([a,b]) => a*d === n*b)); values.push([n,d]);});
  }
  requireValue(new TextEncoder().encode(JSON.stringify(v)).length <= 131072);
  return v as unknown as ReplayInputs;
}
// Scan before JSON.parse: reject duplicate/escaped duplicate keys and excessive nesting.
// JSON.parse alone silently accepts duplicate keys. No input is evaluated as code.
function parseUnique(text: string): unknown {
  let at = 0, nodes = 0;
  const space = () => {while (/[ \t\r\n]/.test(text[at] ?? "x")) at++;};
  const string = () => {
    const start = at++; let escaped = false;
    while (at < text.length) {const c = text[at++]; if (!escaped && c === '"') return JSON.parse(text.slice(start,at)) as string; if (!escaped && c === "\\") escaped = true; else escaped = false;}
    return fail();
  };
  const value = (depth: number): void => {
    requireValue(depth <= 16 && ++nodes <= 50000); space(); const c = text[at];
    if (c === "{" || c === "[") {
      at++; space(); const end = c === "{" ? "}" : "]", keys = new Set<string>();
      if (text[at] === end) {at++; return;}
      for (;;) {
        if (c === "{") {requireValue(text[at] === '"'); const key = string(); requireValue(!keys.has(key) && !key.includes("|")); keys.add(key); space(); requireValue(text[at++] === ":");}
        value(depth+1); space(); if (text[at] === end) {at++; return;} requireValue(text[at++] === ","); space();
      }
    }
    if (c === '"') {string(); return;}
    const start = at; while (at < text.length && !/[ \t\r\n,}\]]/.test(text[at])) at++;
    requireValue(at > start); JSON.parse(text.slice(start,at));
  };
  value(0); space(); requireValue(at === text.length); return JSON.parse(text);
}
function validateLocal(method: ReplayMethod, v: unknown): ReplayReceipt {
  record(v,["schema_id","inputs","result"]); const inputs = validateReplayInputs(method,v.inputs);
  return method === "risk" ? validateReceipt(v,inputs as RiskInputs) : validateStressReceipt(v,inputs as StressInputs);
}
export async function readReplay(method: ReplayMethod, file: File): Promise<ReplayInputs> {
  try {
    requireValue(file.size > 0 && file.size <= MAX_REPLAY_BYTES);
    const bytes = await file.arrayBuffer(); requireValue(bytes.byteLength === file.size && bytes.byteLength <= MAX_REPLAY_BYTES);
    // BOM is not part of the download format; malformed UTF-8 must never be repaired.
    requireValue(!(new Uint8Array(bytes)[0] === 239 && new Uint8Array(bytes)[1] === 187 && new Uint8Array(bytes)[2] === 191));
    const receipt = validateLocal(method,parseUnique(new TextDecoder("utf-8",{fatal:true}).decode(bytes)));
    return receipt.inputs;
  } catch {return fail();}
}
export function replayFields(method: ReplayMethod, inputs: ReplayInputs): Record<string,string> {
  const base = {currency:inputs.reporting_currency,date:inputs.exposure_date,exposures:inputs.exposures.map(e => `${e.asset_id} ${e.amount}`).join("\n")};
  if (method === "risk") {const v=inputs as RiskInputs; return {...base,confidence:v.confidence,horizon:String(v.horizon),value:v.portfolio_value ?? "",sessions:v.sessions.map(s => `${s.session_id} ${s.start} ${s.end} ${v.exposures.map(e => s.factors[e.asset_id]).join(" ")}`).join("\n")};}
  const v=inputs as StressInputs; return {...base,scenarios:v.scenarios.map(s => `${s.scenario_id} ${v.exposures.map(e => s.shocks[e.asset_id]).join(" ")}`).join("\n"),common:v.common_shocks.join(" ")};
}
export function restoreReplay(form: HTMLFormElement, method: ReplayMethod, inputs: ReplayInputs) {
  const fields = Object.entries(replayFields(method,inputs)).map(([name,value]) => {
    const element = form.elements.namedItem(name), view = form.ownerDocument.defaultView; requireValue(view && (element instanceof view.HTMLInputElement || element instanceof view.HTMLTextAreaElement)); return {element,value};
  });
  fields.forEach(({element,value}) => {element.value = value;});
}
export function receiptDownloadBytes(method: ReplayMethod, receipt: ReplayReceipt, form: HTMLFormElement): Uint8Array {
  const current = method === "risk" ? formInputs(form) : stressFormInputs(form);
  requireValue(stable(current) === stable(receipt.inputs)); validateLocal(method,receipt);
  const bytes = new TextEncoder().encode(JSON.stringify(receipt)+"\n"); requireValue(bytes.length <= MAX_REPLAY_BYTES); return bytes;
}
export function downloadReplay(bytes: Uint8Array, method: ReplayMethod): () => void {
  const url = URL.createObjectURL(new Blob([bytes as BlobPart],{type:"application/json;charset=utf-8"}));
  let revoked = false, timer: ReturnType<typeof setTimeout> | undefined;
  const dispose = () => {if (timer !== undefined) clearTimeout(timer); if (!revoked) {revoked=true; URL.revokeObjectURL(url);}};
  const anchor = document.createElement("a");
  try {anchor.href=url; anchor.download=`finlens-hypothetical-${method}-v1.json`; document.body.appendChild(anchor); anchor.click(); timer=setTimeout(dispose,0);}
  catch (error) {dispose(); throw error;} finally {anchor.remove();}
  return dispose;
}
