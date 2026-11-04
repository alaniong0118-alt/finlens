import test,{before} from "node:test";
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {readFileSync,mkdtempSync,unlinkSync,rmdirSync} from "node:fs";
import {tmpdir} from "node:os";
import {join,resolve} from "node:path";
import {fileURLToPath} from "node:url";
import React,{act} from "react";
import {createRoot} from "react-dom/client";
import {JSDOM} from "jsdom";
import {componentLoader} from "./component-loader.mjs";
const frontend=fileURLToPath(new URL("../",import.meta.url)),backend=resolve(frontend,"../backend");
const load=componentLoader(frontend),lib=load(join(frontend,"lib/hypothetical-stress.ts"));
const {HypotheticalStress}=load(join(frontend,"components/hypothetical-stress.tsx"));
let receipts;
before(()=>{
  const temp=mkdtempSync(join(tmpdir(),"finlens-stress-contract-")),output=join(temp,"receipts.json");
  try {
    const python=join(backend,".venv",...(process.platform==="win32"?["Scripts","python.exe"]:["bin","python"]));
    const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>["systemroot","windir","path","temp","tmp","tmpdir","pathext","comspec","number_of_processors"].includes(key.toLowerCase())));
    const result=spawnSync(python,["-I","-S","-B","tests/run_financial_insights.py","tests/test_hypothetical_stress.py"],{cwd:backend,env:{...env,FINLENS_STRESS_CONTRACT_OUTPUT:output},encoding:"utf8",timeout:60000,windowsHide:true});
    assert.equal(result.status,0,`${result.stdout}\n${result.stderr}`);process.stdout.write(result.stdout);
    receipts=JSON.parse(readFileSync(output,"utf8"));assert.equal(receipts.length,9);
  } finally {try{unlinkSync(output);}finally{rmdirSync(temp);}}
});
const reply=receipt=>new Response(JSON.stringify(receipt),{headers:{"Content-Type":"application/json"}});
test("actual Python stress receipts validate across signed, zero, decimal and boundary cases",()=>{
  for(const receipt of receipts) assert.equal(lib.validateStressReceipt(receipt,receipt.inputs),receipt);
  assert.equal(receipts[0].result.scenarios[0].total_pnl.display,"-12.500000000000000000");
  assert.equal(receipts[0].result.scenarios[0].total_loss.display,"12.500000000000000000");
  assert.equal(receipts[0].result.common_shock_pnl_per_percentage_point.display,"0.500000000000000000");
});
test("malformed and arithmetically contradictory receipts reject",()=>{
  const exact=value=>({numerator:String(value),denominator:"1",display:`${value}.000000000000000000`});
  const changes=[r=>{r.result.data_authority="observed_market_data";},r=>{r.result.method_id="forecast";},r=>{r.result.exposures[0].currency="EUR";},r=>{r.result.exposures[0].exposure_type="option";},r=>{r.result.gross_exposure=exact(0);},r=>{r.result.scenarios[0].contributions.pop();},r=>{r.result.scenarios[0].contributions[0].asset_id="unknown";},r=>{r.result.scenarios[0].contributions[0].pnl=exact(1);r.result.scenarios[0].contributions[0].loss=exact(-1);},r=>{r.result.scenarios[0].total_pnl=exact(0);r.result.scenarios[0].total_loss=exact(0);},r=>{r.result.common_shock_pnl_per_percentage_point=exact(0);},r=>{r.result.common_shock_sensitivity.reverse();},r=>{r.result.scenarios[0].extra=true;},r=>{r.inputs.common_shocks=[];}];
  for(const change of changes){const receipt=structuredClone(receipts[0]);change(receipt);assert.throws(()=>lib.validateStressReceipt(receipt,receipts[0].inputs));}
});
test("stress transport shares bounded JSON/content/error validation",async()=>{
  const original=globalThis.fetch;
  try {
    for(const response of [new Response("{",{headers:{"Content-Type":"application/json"}}),new Response(" ".repeat(1048577),{headers:{"Content-Type":"application/json"}}),new Response("{}",{headers:{"Content-Type":"text/html"}}),new Response("{}",{status:422})]){
      globalThis.fetch=async()=>response;await assert.rejects(lib.requestStress(receipts[0].inputs,new AbortController().signal));
    }
  }finally{globalThis.fetch=original;}
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
    await act(async () => root.render(React.createElement(HypotheticalStress)));
    const form = document.querySelector("form"), input = receipts[0].inputs;
    const values={currency:input.reporting_currency,date:input.exposure_date,exposures:input.exposures.map(e=>`${e.asset_id} ${e.amount}`).join("\n"),scenarios:input.scenarios.map(s=>`${s.scenario_id} ${input.exposures.map(e=>s.shocks[e.asset_id]).join(" ")}`).join("\n"),common:input.common_shocks.join(" ")};
    for (const [name,value] of Object.entries(values)) form.elements.namedItem(name).value=value;
    const submit=async()=>act(async()=>form.dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true})));
    const change=async(name,value)=>act(async()=>{const e=form.elements.namedItem(name); e.value=value; const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(e),"value").set; setter.call(e,value); e.dispatchEvent(new dom.window.Event("input",{bubbles:true})); e.dispatchEvent(new dom.window.Event("change",{bubbles:true}));});
    await run({requests, submit, change, dom, form});
  } finally {
    await act(async()=>root.unmount()); dom.window.close();
    for(const [name,descriptor] of originals) if(descriptor) Object.defineProperty(globalThis,name,descriptor); else delete globalThis[name];
  }
}

test("mounted stress success presents complete contributions and sensitivity",async()=>mounted(async({requests,submit,form})=>{
  await submit();assert.equal(requests[0].url,"/api/finlens/hypothetical-stress");
  assert.deepEqual(JSON.parse(requests[0].options.body),receipts[0].inputs);
  await act(async()=>requests[0].resolve(reply(receipts[0])));
  assert.match(document.body.textContent,/Conditional stress results/);
  assert.match(document.body.textContent,/-12.500000000000000000/);
  assert.equal(document.querySelectorAll('[aria-label="Contribution audit decline"] tbody tr').length,3);
  const scroll=document.querySelector('[aria-label="Common shock totals"]');scroll.focus();assert.equal(document.activeElement,scroll);
  const before=form.elements.namedItem("scenarios").value;assert.match(before,/unchanged 0 0 0/);
}));
test("mounted edit and explicit zero versus missing shock behavior",async()=>mounted(async({requests,submit,change,form})=>{
  await submit();await act(async()=>requests[0].resolve(reply(receipts[0])));
  await change("scenarios","missing -10 5");assert.doesNotMatch(document.body.textContent,/Conditional stress results/);
  await submit();assert.equal(requests.length,1);assert.match(document.querySelector('[role="alert"]').textContent,/Missing shocks are not zero/);
  form.elements.namedItem("scenarios").value="explicit 0 0 0";
  assert.deepEqual(lib.stressFormInputs(form).scenarios[0].shocks,{long:"0",short:"0",zero:"0"});
}));
test("mounted supersession and cancellation reject ignored-abort success",async()=>mounted(async({requests,submit})=>{
  await submit();await submit();assert.equal(requests[0].options.signal.aborted,true);
  await act(async()=>requests[0].resolve(reply(receipts[0])));assert.doesNotMatch(document.body.textContent,/Conditional stress results/);
  await act(async()=>[...document.querySelectorAll("button")].find(b=>b.textContent==="Cancel calculation").click());
  await act(async()=>requests[1].resolve(reply(receipts[0])));assert.equal(requests[1].options.signal.aborted,true);
  assert.match(document.body.textContent,/Calculation cancelled/);assert.doesNotMatch(document.body.textContent,/Conditional stress results/);
}));
test("mounted stale errors after edit cannot erase a newer signed receipt",async()=>mounted(async({requests,submit,change})=>{
  await submit();await change("exposures","long -100\nshort -50\nzero 0");await submit();
  await act(async()=>requests[1].resolve(reply(receipts[1])));assert.match(document.body.textContent,/Conditional stress results/);
  await act(async()=>requests[0].reject(new Error("Stale failure")));assert.equal(document.querySelector('[role="alert"]'),null);
  assert.match(document.body.textContent,/Conditional stress results/);
}));
test("mounted malformed response clears old results and permits explicit retry",async()=>mounted(async({requests,submit})=>{
  await submit();await act(async()=>requests[0].resolve(reply(receipts[0])));
  await submit();assert.doesNotMatch(document.body.textContent,/Conditional stress results/);
  await act(async()=>requests[1].resolve(reply({schema_id:"wrong"})));assert.match(document.querySelector('[role="alert"]').textContent,/could not be verified/);
  await submit();await act(async()=>requests[2].resolve(reply(receipts[0])));assert.match(document.body.textContent,/Conditional stress results/);
}));
test("mounted stress timeout and unmount invalidate late deliveries",async()=>{
  const schedule=globalThis.setTimeout;let deadline,last;
  globalThis.setTimeout=(callback,delay,...args)=>delay===10000?(deadline=callback,schedule(()=>{},60000)):schedule(callback,delay,...args);
  try {await mounted(async({submit,requests})=>{
    await submit();last=requests[0];await act(async()=>deadline());assert.equal(last.options.signal.aborted,true);
    await act(async()=>last.resolve(reply(receipts[0])));assert.match(document.querySelector('[role="alert"]').textContent,/timed out/);
    assert.doesNotMatch(document.body.textContent,/Conditional stress results/);await submit();last=requests[1];
  });assert.equal(last.options.signal.aborted,true);last.resolve(reply(receipts[0]));}
  finally{globalThis.setTimeout=schedule;}
});

test("receipt validation cannot silently normalize a mixed currency or unsupported type",()=>{
  for(const [field,value] of [["currency","EUR"],["exposure_type","option_delta"]]){
    const inputs=structuredClone(receipts[0].inputs);inputs.exposures[0][field]=value;
    const receipt=structuredClone(receipts[0]);receipt.inputs=structuredClone(inputs);
    assert.throws(()=>lib.validateStressReceipt(receipt,inputs));
  }
});

test("form shocks follow exposure input order rather than sorted receipt order",async()=>mounted(async({form})=>{
  form.elements.namedItem("exposures").value="zero 0\nshort -50\nlong 100";
  form.elements.namedItem("scenarios").value="decline 0 5 -10\nunchanged 0 0 0";
  const inputs=lib.stressFormInputs(form);
  assert.deepEqual(inputs.exposures.map(e=>e.asset_id),["zero","short","long"]);
  assert.deepEqual(inputs.scenarios[0].shocks,{zero:"0",short:"5",long:"-10"});
}));
