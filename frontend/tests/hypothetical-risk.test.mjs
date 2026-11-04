import test, {before} from "node:test";
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {readFileSync, mkdtempSync, unlinkSync, rmdirSync} from "node:fs";
import {tmpdir} from "node:os";
import {join, resolve} from "node:path";
import {fileURLToPath} from "node:url";
import React, {act} from "react";
import {createRoot} from "react-dom/client";
import {JSDOM} from "jsdom";
import {componentLoader} from "./component-loader.mjs";
const frontend = fileURLToPath(new URL("../", import.meta.url)), backend = resolve(frontend, "../backend");
const load = componentLoader(frontend), lib = load(join(frontend, "lib/hypothetical-risk.ts"));
const {HypotheticalRisk} = load(join(frontend, "components/hypothetical-risk.tsx"));
let receipts;
before(() => {
  const temp = mkdtempSync(join(tmpdir(), "finlens-risk-contract-")), output = join(temp, "contract.json");
  try {
    const python = join(backend, ".venv", ...(process.platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]));
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => ["systemroot", "windir", "path", "temp", "tmp", "tmpdir", "pathext", "comspec", "number_of_processors"].includes(key.toLowerCase())));
    const run = spawnSync(python, ["-I", "-S", "-B", "tests/run_financial_insights.py", "tests/test_hypothetical_risk.py"], {cwd: backend, env: {...env, FINLENS_RISK_CONTRACT_OUTPUT: output}, encoding: "utf8", timeout: 60000, windowsHide: true});
    assert.equal(run.status, 0, `${run.stdout}\n${run.stderr}`); process.stdout.write(run.stdout);
    receipts = JSON.parse(readFileSync(output, "utf8")); assert.equal(receipts.length, 11);
  } finally { try { unlinkSync(output); } finally { rmdirSync(temp); } }
});
const reply = receipt => new Response(JSON.stringify(receipt), {headers: {"Content-Type": "application/json"}});
test("fresh actual Python receipts validate across ties, sparse tails, overlap, signs and insufficient samples", () => {
  for (const receipt of receipts) assert.equal(lib.validateReceipt(receipt, receipt.inputs), receipt);
  assert.equal(receipts[0].result.es.exact.numerator, "7");
  assert.equal(receipts[1].result.es.exact.numerator, "8");
  assert.equal(receipts[2].result.es.reason, "insufficient_tail_mass");
});
test("malformed or contradictory receipts never pass", () => {
  const mutations = [r => {r.schema_id = "other";}, r => {r.result.var.exact.display = "NaN";}, r => {r.result.var.exact.numerator = "5";}, r => {r.result.panel.sessions[0].factors[0].gross_factor.numerator = "42";}, r => {r.result.scenarios[0].start_index = 10;}, r => {r.result.scenarios[0].tail_mass = {numerator: "-1", denominator: "1", display: "-1.000000000000000000"};}, r => {r.result.scenarios.pop();}, r => {r.result.scenarios[0].tail_mass = null;}, r => {r.result.es = {exact:null,reason:"insufficient_scenarios"};}, r => {r.result.data_authority = "market_history";}, r => {r.result.extra = true;}, r => {r.inputs.confidence = "0.9";}];
  for (const change of mutations) { const r = structuredClone(receipts[0]); change(r); assert.throws(() => lib.validateReceipt(r, receipts[0].inputs)); }
});
test("transport rejects malformed JSON, oversized bodies, wrong content type and server errors", async () => {
  const original = globalThis.fetch;
  try {
    for (const response of [new Response("{", {headers: {"Content-Type": "application/json"}}), new Response(" ".repeat(1048577), {headers: {"Content-Type": "application/json"}}), new Response("{}", {headers: {"Content-Type": "text/html"}}), new Response("{}", {status: 429})]) {
      globalThis.fetch = async () => response;
      await assert.rejects(lib.requestRisk(receipts[0].inputs, new AbortController().signal));
    }
  } finally {globalThis.fetch = original;}
});
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a; reject=b;}); return {promise,resolve,reject}; }
async function mounted(run) {
  const dom = new JSDOM("<!doctype html><div id='root'></div>", {url: "http://127.0.0.1/"});
  const names = ["window", "document", "navigator", "HTMLElement", "FormData", "IS_REACT_ACT_ENVIRONMENT", "fetch"];
  const originals = names.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]);
  for (const name of names.slice(0,5)) Object.defineProperty(globalThis, name, {configurable:true, writable:true, value:dom.window[name]});
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const root = createRoot(document.getElementById("root")), requests=[];
  globalThis.fetch = (url, options) => {const d=deferred(); requests.push({...d,url,options}); return d.promise;};
  try {
    await act(async () => root.render(React.createElement(HypotheticalRisk)));
    const form = document.querySelector("form"), input = receipts[0].inputs;
    const values = {currency:input.reporting_currency, date:input.exposure_date, confidence:input.confidence, horizon:String(input.horizon), value:input.portfolio_value, exposures:input.exposures.map(e=>`${e.asset_id} ${e.amount}`).join("\n"), sessions:input.sessions.map(s=>`${s.session_id} ${s.start} ${s.end} ${s.factors.long}`).join("\n")};
    for (const [name,value] of Object.entries(values)) form.elements.namedItem(name).value=value;
    const submit=async()=>act(async()=>form.dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true})));
    const change=async(name,value)=>act(async()=>{const e=form.elements.namedItem(name); e.value=value; const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),"value").set; setter.call(e,value); e.dispatchEvent(new dom.window.Event("input",{bubbles:true})); e.dispatchEvent(new dom.window.Event("change",{bubbles:true}));});
    await run({requests, submit, change, dom, form});
  } finally {
    await act(async()=>root.unmount()); dom.window.close();
    for(const [name,descriptor] of originals) if(descriptor) Object.defineProperty(globalThis,name,descriptor); else delete globalThis[name];
  }
}
test("mounted success presents exact audit and invalidates on input edits", async () => mounted(async({requests,submit,change})=>{
  await submit(); assert.equal(requests.length,1);
  await act(async()=>requests[0].resolve(reply(receipts[0])));
  assert.match(document.body.textContent,/Hypothetical sample results/);
  assert.equal(document.querySelectorAll("tbody tr").length,10);
  const disclosure=document.querySelector("summary"); disclosure.focus(); assert.equal(document.activeElement,disclosure);
  await change("confidence","0.85");
  assert.doesNotMatch(document.body.textContent,/Hypothetical sample results/);
}));
test("mounted restart, cancellation and ignored abort cannot publish stale responses", async () => mounted(async({requests,submit})=>{
  await submit(); await submit(); assert.equal(requests[0].options.signal.aborted,true);
  await act(async()=>requests[0].resolve(reply(receipts[0])));
  assert.doesNotMatch(document.body.textContent,/Hypothetical sample results/);
  const cancel=[...document.querySelectorAll("button")].find(b=>b.textContent==="Cancel calculation");
  await act(async()=>cancel.click()); assert.equal(requests[1].options.signal.aborted,true);
  await act(async()=>requests[1].resolve(reply(receipts[0])));
  assert.match(document.body.textContent,/Calculation cancelled/);
  assert.doesNotMatch(document.body.textContent,/Hypothetical sample results/);
}));
test("mounted malformed and error responses clear old results and allow explicit retry", async()=>mounted(async({requests,submit})=>{
  await submit(); await act(async()=>requests[0].resolve(reply(receipts[0])));
  await submit(); assert.doesNotMatch(document.body.textContent,/Hypothetical sample results/);
  await act(async()=>requests[1].resolve(reply({unexpected:true})));
  assert.match(document.querySelector('[role="alert"]').textContent,/could not be verified/);
  await submit(); await act(async()=>requests[2].reject(new Error("Synthetic transport failure")));
  assert.match(document.querySelector('[role="alert"]').textContent,/Synthetic transport failure/);
}));
test("mounted missing observations reject before a request", async()=>mounted(async({form,submit,requests})=>{
  form.elements.namedItem("sessions").value="s0 2026-01-01 2026-01-02";
  await submit(); assert.equal(requests.length,0);
  assert.match(document.querySelector('[role="alert"]').textContent,/Missing observations/);
}));

test("mounted timeout and unmount invalidate ignored-abort deliveries", async()=>{
  const schedule = globalThis.setTimeout; let deadline, last;
  globalThis.setTimeout = (callback, delay, ...args) => delay === 10000 ? (deadline=callback, schedule(()=>{}, 60000)) : schedule(callback,delay,...args);
  try { await mounted(async({submit,requests})=>{
    await submit(); last=requests[0];
    await act(async()=>deadline()); assert.equal(last.options.signal.aborted,true);
    assert.match(document.querySelector('[role="alert"]').textContent,/timed out/);
    await act(async()=>last.resolve(reply(receipts[0])));
    assert.doesNotMatch(document.body.textContent,/Hypothetical sample results/);
    await submit(); last=requests[1];
  }); assert.equal(last.options.signal.aborted,true); last.resolve(reply(receipts[0])); }
  finally {globalThis.setTimeout=schedule;}
});
