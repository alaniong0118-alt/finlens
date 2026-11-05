import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {createRequire} from "node:module";
import {join} from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";
const frontend = fileURLToPath(new URL("../", import.meta.url));
// Optional dependency root supports isolated source review; source under test
// always comes from this test's frontend directory, never the runtime checkout.
const runtime = process.env.FINLENS_FRONTEND_TEST_RUNTIME || frontend;
const require = createRequire(join(runtime, "package.json"));
const React = require("react"), {act} = React, {createRoot} = require("react-dom/client"), {JSDOM} = require("jsdom");
const {componentLoader} = await import(pathToFileURL(join(runtime,"tests/component-loader.mjs")));
const load = componentLoader(frontend);
const lib = load(join(frontend,"lib/hypothetical-panel-statistics.ts"));
const risk = load(join(frontend,"lib/hypothetical-risk.ts"));
const replay = load(join(frontend,"lib/hypothetical-replay.ts"));
const {HypotheticalRisk} = load(join(frontend,"components/hypothetical-risk.tsx"));
const raw = readFileSync(new URL("fixtures/hypothetical-panel-statistics.json", import.meta.url), "utf8").replaceAll("\r\n","\n");
assert.equal(createHash("sha256").update(raw).digest("hex"), "3e4ff354b27f979b143f9b339819e8589c59dc7e934314796ce2d01b3f232dbe");
const samples = JSON.parse(raw), receipt = samples.statistics[0].receipt;
const reply = r => new Response(JSON.stringify(r), {headers:{"Content-Type":"application/json"}});

test("source-bound Python contracts cover sparse, short/zero, exact decimals and arithmetic unavailable", () => {
  assert.equal(samples.statistics.length,8);
  for (const {receipt:r} of samples.statistics) assert.equal(lib.validateStatistics(r,r.inputs),r);
  assert.equal(samples.statistics.find(c=>c.name==="negative_covariance").receipt.result.covariance[0][1].exact.display,"-0.020000000000000000");
  assert.equal(samples.statistics.find(c=>c.name==="constant_zero").receipt.result.assets[0].sample_volatility.display,"0.000000000000000000");
  assert.equal(samples.statistics.find(c=>c.name==="exact_decimal").receipt.inputs.exposures[0].amount,"-123456789012.123456789012");
  assert.equal(samples.statistics.find(c=>c.name==="arithmetic_limit").receipt.result.assets[0].cumulative_return.reason,"arithmetic_resource_limit");
});
const mutations = {
  schema:r=>r.schema_id="hypothetical-risk-v1", method:r=>r.result.method_id="other", precision:r=>r.result.precision_id="float",
  authority:r=>r.result.data_authority="observed_market_history", basis:r=>r.result.observation_basis="annualized",
  unit:r=>r.result.return_unit="percent", covariance_unit:r=>r.result.covariance_unit="USD", notices:r=>r.result.notices.pop(),
  input:r=>r.inputs.confidence="0.8", extra:r=>r.result.forecast=true, count:r=>r.result.sample_count=3,
  denominator:r=>r.result.sample_denominator=2, days:r=>r.result.interval_days[1]=1, equal_lengths:r=>r.result.equal_interval_lengths=true,
  order:r=>r.result.asset_ids.reverse(), assets:r=>r.result.assets.reverse(), panel:r=>r.result.panel.panel_id="market",
  missing_factor:r=>r.result.panel.sessions[0].factors.pop(), factor:r=>r.result.panel.sessions[0].factors[0].gross_factor={numerator:"1",denominator:"1",display:"1.000000000000000000"},
  date:r=>r.result.panel.sessions[0].start="2026-01-02", missing_asset:r=>r.result.assets.pop(),
  unknown_asset:r=>r.result.assets[0].asset_id="other", witness:r=>r.result.assets[0].trough_boundary=3,
  null_witness:r=>r.result.assets[0].peak_boundary=null, witness_order:r=>r.result.assets[0].peak_boundary=2,
  false_unavailable:r=>r.result.assets[0].sample_variance={exact:null,reason:"insufficient_observations"},
  negative_variance:r=>r.result.assets[0].sample_variance.exact={numerator:"-1",denominator:"50",display:"-0.020000000000000000"},
  root:r=>r.result.assets[0].sample_volatility.display="0.141421356237309504", root_leading_zero:r=>r.result.assets[0].sample_volatility.display="00.141421356237309505",
  radicand:r=>r.result.assets[0].sample_volatility.radicand=r.result.assets[1].sample_variance.exact,
  root_null:r=>r.result.assets[0].sample_volatility.radicand=null, root_reason:r=>r.result.assets[0].sample_volatility.reason="arithmetic_resource_limit",
  rational_display:r=>r.result.assets[0].cumulative_return.exact.display="-0.020000000000000000",
  rational_bound:r=>r.result.assets[0].cumulative_return.exact.numerator="1".repeat(2501),
  covariance_shape:r=>r.result.covariance[0].pop(), covariance_row:r=>r.result.covariance[1]=null,
  symmetry:r=>r.result.covariance[1][0]=r.result.assets[1].sample_variance,
  diagonal:r=>r.result.covariance[0][0]=r.result.assets[1].sample_variance,
  complete:r=>r.result.covariance_complete=false, mean_failure:r=>r.result.assets[0].sample_mean_return={exact:null,reason:"arithmetic_resource_limit"},
};
for (const [name,change] of Object.entries(mutations)) test(`reject contradictory statistics: ${name}`,()=>{
  const r=structuredClone(receipt);change(r);assert.throws(()=>lib.validateStatistics(r,receipt.inputs));
});
test("insufficient observations cannot be silently represented as exact zero",()=>{
  const empty=structuredClone(samples.statistics.find(c=>c.name==="empty").receipt);
  empty.result.assets[0].cumulative_return={exact:{numerator:"0",denominator:"1",display:"0.000000000000000000"},reason:null};
  assert.throws(()=>lib.validateStatistics(empty,empty.inputs));
});
test("statistics never enter v1 replay and the original risk receipt still validates", async()=>{
  risk.validateReceipt(samples.risk,samples.risk.inputs);
  for(const method of ["risk","stress"])await assert.rejects(replay.readReplay(method,new File([JSON.stringify(receipt)],"statistics.json")),/./);
});
test("statistics use the bounded same-origin transport with exact inputs and cancellation signal",async()=>{
  const original=globalThis.fetch,signal=new AbortController().signal;
  try {
    globalThis.fetch=async(url,options)=>{assert.equal(url,"/api/finlens/hypothetical-panel-statistics");assert.equal(options.method,"POST");assert.equal(options.cache,"no-store");assert.equal(options.signal,signal);assert.deepEqual(JSON.parse(options.body),receipt.inputs);return reply(receipt);};
    assert.deepEqual(await lib.requestStatistics(receipt.inputs,signal),receipt);
  }finally{globalThis.fetch=original;}
});
test("transport rejects malformed, oversized, disabled, busy and invalid endpoint responses",async()=>{
  const original=globalThis.fetch;
  try {
    for(const response of [new Response("{",{headers:{"Content-Type":"application/json"}}),new Response(" ".repeat(1048577),{headers:{"Content-Type":"application/json"}}),new Response("{}",{headers:{"Content-Type":"text/html"}}),new Response(new Uint8Array([255]),{headers:{"Content-Type":"application/json"}}),...[404,429,422,500].map(status=>new Response("{}",{status}))]){
      globalThis.fetch=async()=>response;await assert.rejects(lib.requestStatistics(receipt.inputs,new AbortController().signal));
    }
    globalThis.fetch=()=>{throw new Error("must not fetch");};
    await assert.rejects(lib.requestStatistics({...receipt.inputs,portfolio_value:"9".repeat(131073)},new AbortController().signal),/request limit/);
    await assert.rejects(risk.requestHypothetical("https://untrusted.invalid",receipt.inputs,new AbortController().signal,lib.validateStatistics),/could not be verified/);
  }finally{globalThis.fetch=original;}
});
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function mounted(run,{sample=receipt,width=390}={}){
  const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://127.0.0.1/"});
  Object.defineProperty(dom.window,"innerWidth",{value:width});
  const names=["window","document","navigator","HTMLElement","FormData","IS_REACT_ACT_ENVIRONMENT","fetch"], originals=names.map(n=>[n,Object.getOwnPropertyDescriptor(globalThis,n)]);
  for(const name of names.slice(0,5))Object.defineProperty(globalThis,name,{configurable:true,writable:true,value:dom.window[name]});
  globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const root=createRoot(document.getElementById("root")),requests=[];
  globalThis.fetch=(url,options)=>{const d=deferred();requests.push({...d,url,options});return d.promise;};
  try{
    await act(async()=>root.render(React.createElement(HypotheticalRisk)));
    const form=document.querySelector("form"),i=sample.inputs;
    const values={currency:i.reporting_currency,date:i.exposure_date,confidence:i.confidence,horizon:String(i.horizon),value:i.portfolio_value??"",exposures:i.exposures.map(e=>`${e.asset_id} ${e.amount}`).join("\n"),sessions:i.sessions.map(s=>`${s.session_id} ${s.start} ${s.end} ${i.exposures.map(e=>s.factors[e.asset_id]).join(" ")}`).join("\n")};
    for(const [name,value] of Object.entries(values))form.elements.namedItem(name).value=value;
    const button=()=>document.querySelector('button[value="statistics"]');
    const submit=async()=>act(async()=>button().click());
    const riskSubmit=async()=>act(async()=>form.dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true})));
    const change=async(name,value)=>act(async()=>{const element=form.elements.namedItem(name);Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element),"value").set.call(element,value);element.dispatchEvent(new dom.window.Event("input",{bubbles:true}));element.dispatchEvent(new dom.window.Event("change",{bubbles:true}));});
    await run({dom,form,requests,submit,riskSubmit,change,button});
  }finally{
    await act(async()=>root.unmount());dom.window.close();
    for(const [name,descriptor] of originals)if(descriptor)Object.defineProperty(globalThis,name,descriptor);else delete globalThis[name];
  }
}
test("mounted explicit statistics action renders units, synthetic warnings, exact audit and scoped covariance",async()=>mounted(async({requests,submit,button})=>{
  assert.equal(requests.length,0);button().focus();assert.equal(document.activeElement,button());
  await submit();assert.match(document.body.textContent,/Calculating hypothetical asset statistics/);assert.equal(requests.length,1);
  await act(async()=>requests[0].resolve(reply(receipt)));
  const section=document.querySelector('[aria-labelledby="asset-statistics-result"]');assert.ok(section);
  assert.match(section.textContent,/Synthetic user-entered factors only/);assert.match(section.textContent,/Unequal supplied interval lengths: 1, 6/);
  assert.match(section.textContent,/return ratios, not percentages/);assert.match(section.textContent,/N−1 = 1/);
  assert.equal(section.querySelectorAll('th[scope="row"]').length,2);assert.equal(section.querySelectorAll('th[scope="col"]').length,3);
  const region=section.querySelector('[role="region"]');region.focus();assert.equal(document.activeElement,region);assert.equal(region.style.overflowX,"auto");
  const summary=section.querySelector("summary");summary.focus();assert.equal(document.activeElement,summary);
  const audit=section.querySelector("pre");audit.focus();assert.equal(document.activeElement,audit);assert.deepEqual(JSON.parse(audit.textContent),receipt);
  assert.equal(audit.style.overflowWrap,"anywhere");assert.ok(section.querySelector('h3').style.overflowWrap);
  assert.equal(document.querySelectorAll('[aria-labelledby="risk-result"]').length,0);
  assert.equal([...document.querySelectorAll("button")].find(b=>b.textContent.startsWith("Download current")).disabled,true);
}));
for(const name of ["empty","singleton","constant_zero","arithmetic_limit","eight_assets"])test(`mounted explicit availability: ${name}`,async()=>{
  const sample=samples.statistics.find(c=>c.name===name).receipt;
  await mounted(async({requests,submit})=>{
    await submit();await act(async()=>requests[0].resolve(reply(sample)));
    const section=document.querySelector('[aria-labelledby="asset-statistics-result"]');assert.ok(section);
    if(name==="empty"||name==="singleton")assert.match(section.textContent,/Unavailable: insufficient supplied intervals/);
    if(name==="constant_zero")assert.doesNotMatch(section.textContent,/Unavailable/);
    if(name==="arithmetic_limit")assert.match(section.textContent,/Unavailable: exact arithmetic limit reached/);
    if(name==="eight_assets")assert.equal(section.querySelectorAll('th[scope="col"]').length,9);
  },{sample});
});
test("mounted edit clears results and late response from ignored abort never appears",async()=>mounted(async({requests,submit,change})=>{
  await submit();await change("confidence","0.8");assert.equal(requests[0].options.signal.aborted,true);
  await act(async()=>requests[0].resolve(reply(receipt)));assert.equal(document.getElementById("asset-statistics-result"),null);
  await change("confidence","0.5");await submit();await act(async()=>requests[1].resolve(reply(receipt)));assert.ok(document.getElementById("asset-statistics-result"));
  await change("value","0");assert.equal(document.getElementById("asset-statistics-result"),null);
}));
test("risk/statistics restart share one owner and only latest method can publish",async()=>mounted(async({requests,submit,riskSubmit,form})=>{
  await submit();await riskSubmit();assert.equal(requests[0].options.signal.aborted,true);assert.equal(requests[1].url,"/api/finlens/hypothetical-risk");
  await act(async()=>requests[0].resolve(reply(receipt)));assert.equal(document.getElementById("asset-statistics-result"),null);
  await act(async()=>requests[1].resolve(reply(samples.risk)));assert.ok(document.getElementById("risk-result"));
  assert.equal([...document.querySelectorAll("button")].find(b=>b.textContent.startsWith("Download current")).disabled,false);
  const bytes=replay.receiptDownloadBytes("risk",samples.risk,form);
  assert.equal(new TextDecoder().decode(bytes),JSON.stringify(samples.risk)+"\n");
  assert.deepEqual(await replay.readReplay("risk",new File([bytes],"risk.json")),samples.risk.inputs);
  await submit();assert.equal(document.getElementById("risk-result"),null);await act(async()=>requests[2].resolve(reply(receipt)));assert.ok(document.getElementById("asset-statistics-result"));
}));
test("repeated cancel retains draft and rejects late statistics, then allows explicit retry",async()=>mounted(async({requests,submit,form})=>{
  const draft=form.elements.namedItem("sessions").value;await submit();
  const cancel=[...document.querySelectorAll("button")].find(b=>b.textContent==="Cancel calculation");await act(async()=>{cancel.click();cancel.click();});
  assert.equal(requests[0].options.signal.aborted,true);await act(async()=>requests[0].resolve(reply(receipt)));
  assert.match(document.body.textContent,/Calculation cancelled/);assert.equal(document.getElementById("asset-statistics-result"),null);assert.equal(form.elements.namedItem("sessions").value,draft);
  await submit();await act(async()=>requests[1].resolve(reply(receipt)));assert.ok(document.getElementById("asset-statistics-result"));
}));
test("malformed and rejected statistics clear old output and preserve editable inputs",async()=>mounted(async({requests,submit,form})=>{
  await submit();await act(async()=>requests[0].resolve(reply(receipt)));await submit();assert.equal(document.getElementById("asset-statistics-result"),null);
  await act(async()=>requests[1].resolve(reply({schema_id:"unknown"})));assert.match(document.querySelector('[role="alert"]').textContent,/could not be verified/);
  await submit();await act(async()=>requests[2].resolve(new Response("{}",{status:429})));assert.match(document.querySelector('[role="alert"]').textContent,/already running/);
  assert.equal(form.elements.namedItem("confidence").value,"0.5");
}));
test("missing observations reject locally without auto-calculation",async()=>mounted(async({requests,submit,form})=>{
  form.elements.namedItem("sessions").value="s0 2026-01-01 2026-01-02 1.2";await submit();assert.equal(requests.length,0);assert.match(document.querySelector('[role="alert"]').textContent,/Missing observations/);
}));
test("timeout and unmount discard even ignored-abort statistics deliveries",async()=>{
  const schedule=globalThis.setTimeout;let timeout,last;
  globalThis.setTimeout=(callback,delay,...args)=>delay===10000?(timeout=callback,schedule(()=>{},60000)):schedule(callback,delay,...args);
  try{await mounted(async({requests,submit})=>{
    await submit();last=requests[0];await act(async()=>timeout());assert.equal(last.options.signal.aborted,true);assert.match(document.querySelector('[role="alert"]').textContent,/timed out/);
    await act(async()=>last.resolve(reply(receipt)));assert.equal(document.getElementById("asset-statistics-result"),null);await submit();last=requests[1];
  });assert.equal(last.options.signal.aborted,true);await act(async()=>last.resolve(reply(receipt)));}finally{globalThis.setTimeout=schedule;}
});
test("late streamed body cannot restore a result after inputs change",async()=>mounted(async({requests,submit,change})=>{
  await submit();let stream;const bytes=new TextEncoder().encode(JSON.stringify(receipt));
  const response=new Response(new ReadableStream({start(c){stream=c;c.enqueue(bytes.slice(0,100));}}),{headers:{"Content-Type":"application/json"}});
  await act(async()=>requests[0].resolve(response));await change("confidence","0.8");
  await act(async()=>{stream.enqueue(bytes.slice(100));stream.close();});assert.equal(document.getElementById("asset-statistics-result"),null);assert.equal(requests[0].options.signal.aborted,true);
}));
test("a valid v1 import cancels pending statistics and requires an explicit fresh calculation",async()=>mounted(async({requests,submit,form,dom})=>{
  await submit();const input=document.querySelector('input[type="file"]');
  const imported=samples.risk_import;
  Object.defineProperty(input,"files",{configurable:true,value:[new File([JSON.stringify(imported)],"risk.json")]});
  await act(async()=>input.dispatchEvent(new dom.window.Event("change",{bubbles:true})));
  assert.equal(requests[0].options.signal.aborted,true);assert.equal(form.elements.namedItem("confidence").value,"0.8");assert.equal(requests.length,1);
  await act(async()=>requests[0].resolve(reply(receipt)));assert.equal(document.getElementById("asset-statistics-result"),null);
  assert.match(document.body.textContent,/calculate explicitly for a fresh result/);
}));
test("a held v1 read released after statistics start cannot overwrite the draft or submit",async()=>mounted(async({requests,submit,form,dom})=>{
  const held=deferred();let completed=0;const input=document.querySelector('input[type="file"]');
  const imported=samples.risk_import;
  const bytes=new TextEncoder().encode(JSON.stringify(imported));
  Object.defineProperty(input,"files",{configurable:true,value:[{size:bytes.byteLength,arrayBuffer:()=>held.promise.then(value=>{completed++;return value;})}]});
  await act(async()=>input.dispatchEvent(new dom.window.Event("change",{bubbles:true})));await submit();
  await act(async()=>held.resolve(bytes.buffer));assert.equal(completed,1);
  assert.equal(form.elements.namedItem("confidence").value,"0.5");assert.equal(requests.length,1);assert.equal(requests[0].options.signal.aborted,false);
  await act(async()=>requests[0].resolve(reply(receipt)));assert.ok(document.getElementById("asset-statistics-result"));
}));
for(const width of [1440,390])test(`semantic focus and bounded layout structure at configured width ${width} (not browser geometry)`,async()=>mounted(async({requests,submit,button})=>{
  assert.equal(window.innerWidth,width);assert.equal(button().getAttribute("type"),"submit");assert.ok(document.getElementById(button().getAttribute("aria-describedby")));
  await submit();assert.equal(document.querySelector("form").getAttribute("aria-busy"),"true");await act(async()=>requests[0].resolve(reply(receipt)));
  assert.equal(document.querySelector("form").getAttribute("aria-busy"),"false");
  const section=document.querySelector('[aria-labelledby="asset-statistics-result"]');assert.equal(Number.parseFloat(section.style.minWidth),0);
  assert.ok([...section.querySelectorAll("div")].find(d=>d.style.gridTemplateColumns.includes("min(100%, 290px)")));
  const region=section.querySelector('[role="region"]');assert.equal(region.tabIndex,0);assert.equal(region.style.maxWidth,"100%");region.focus();assert.equal(document.activeElement,region);
  assert.ok(section.querySelector("table caption"));assert.equal(section.querySelector("summary").parentElement.tagName,"DETAILS");
},{width}));
test("invalid statistics import keeps the draft and current result without automatic requests",async()=>mounted(async({requests,submit,form,dom})=>{
  await submit();await act(async()=>requests[0].resolve(reply(receipt)));const draft=form.elements.namedItem("sessions").value,input=document.querySelector('input[type="file"]');
  Object.defineProperty(input,"files",{configurable:true,value:[new File([JSON.stringify(receipt)],"statistics.json")]});
  await act(async()=>input.dispatchEvent(new dom.window.Event("change",{bubbles:true})));
  assert.match(document.querySelector('[role="alert"]').textContent,/Invalid local receipt/);assert.equal(form.elements.namedItem("sessions").value,draft);assert.ok(document.getElementById("asset-statistics-result"));assert.equal(requests.length,1);
}));
