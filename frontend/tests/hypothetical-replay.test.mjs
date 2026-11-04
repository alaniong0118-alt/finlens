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
const frontend=fileURLToPath(new URL("../",import.meta.url)),backend=resolve(frontend,"../backend"),load=componentLoader(frontend);
const lib=load(join(frontend,"lib/hypothetical-replay.ts"));
const forms={risk:load(join(frontend,"lib/hypothetical-risk.ts")).formInputs,stress:load(join(frontend,"lib/hypothetical-stress.ts")).stressFormInputs};
const components={risk:load(join(frontend,"components/hypothetical-risk.tsx")).HypotheticalRisk,stress:load(join(frontend,"components/hypothetical-stress.tsx")).HypotheticalStress};
let receipts;
before(()=>{
  const temp=mkdtempSync(join(tmpdir(),"finlens-replay-contract-")),risk=join(temp,"risk.json"),stress=join(temp,"stress.json");
  try {
    const python=join(backend,".venv",...(process.platform==="win32"?["Scripts","python.exe"]:["bin","python"]));
    const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>["systemroot","windir","path","temp","tmp","tmpdir","pathext","comspec","number_of_processors"].includes(key.toLowerCase())));
    const result=spawnSync(python,["-I","-S","-B","tests/run_financial_insights.py","tests/test_hypothetical_risk.py","tests/test_hypothetical_stress.py"],{cwd:backend,env:{...env,FINLENS_RISK_CONTRACT_OUTPUT:risk,FINLENS_STRESS_CONTRACT_OUTPUT:stress},encoding:"utf8",timeout:60000,windowsHide:true});
    assert.equal(result.status,0,`${result.stdout}\n${result.stderr}`);process.stdout.write(result.stdout);
    receipts={risk:JSON.parse(readFileSync(risk,"utf8")),stress:JSON.parse(readFileSync(stress,"utf8"))};assert.equal(receipts.risk.length,11);assert.equal(receipts.stress.length,9);
  } finally {for(const file of [risk,stress]){try{unlinkSync(file);}catch(error){if(error.code!=="ENOENT")throw error;}}rmdirSync(temp);}
});
const file=(value)=>new File([typeof value==="string"?value:JSON.stringify(value)],"receipt.json",{type:"application/json"});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const reply=r=>new Response(JSON.stringify(r),{headers:{"Content-Type":"application/json"}});
function fill(form,method,inputs){for(const [name,value] of Object.entries(lib.replayFields(method,inputs)))form.elements.namedItem(name).value=value;}
function result(){return document.querySelector('[aria-labelledby="risk-result"], [aria-labelledby="stress-results"]');}
async function mounted(method,run) {
  const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://127.0.0.1/"});
  const names=["window","document","navigator","HTMLElement","FormData","IS_REACT_ACT_ENVIRONMENT","fetch"];
  const originals=names.map(n=>[n,Object.getOwnPropertyDescriptor(globalThis,n)]);
  for(const name of names.slice(0,5))Object.defineProperty(globalThis,name,{configurable:true,writable:true,value:dom.window[name]});globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const root=createRoot(document.getElementById("root")),requests=[],blobs=[],revoked=[],clicks=[];
  const oldCreate=URL.createObjectURL,oldRevoke=URL.revokeObjectURL,oldClick=dom.window.HTMLAnchorElement.prototype.click;
  URL.createObjectURL=blob=>{blobs.push(blob);return `blob:local-${blobs.length}`;};URL.revokeObjectURL=url=>revoked.push(url);
  dom.window.HTMLAnchorElement.prototype.click=function(){clicks.push({href:this.href,download:this.download});};
  globalThis.fetch=(url,options)=>{const d=deferred();requests.push({...d,url,options});return d.promise;};
  try {
    await act(async()=>root.render(React.createElement(components[method])));
    const form=document.querySelector("form");fill(form,method,receipts[method][0].inputs);
    const submit=async()=>act(async()=>form.dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true})));
    const select=async selected=>act(async()=>{const input=document.querySelector('[type="file"]');Object.defineProperty(input,"files",{configurable:true,value:[selected]});input.dispatchEvent(new dom.window.Event("change",{bubbles:true}));});
    const click=async text=>act(async()=>[...document.querySelectorAll("button")].find(b=>b.textContent===text).click());
    const edit=async()=>act(async()=>form.elements.namedItem("exposures").dispatchEvent(new dom.window.Event("input",{bubbles:true})));
    await run({form,dom,requests,submit,select,click,edit,blobs,revoked,clicks});
  }finally{
    await act(async()=>root.unmount());dom.window.close();
    URL.createObjectURL=oldCreate;URL.revokeObjectURL=oldRevoke;dom.window.HTMLAnchorElement.prototype.click=oldClick;
    for(const [name,d] of originals)if(d)Object.defineProperty(globalThis,name,d);else delete globalThis[name];
  }
}
for(const method of ["risk","stress"]){
  test(`${method}: all actual Python receipts round trip with exact download bytes and editable input order`,async()=>mounted(method,async({form})=>{
    for(const receipt of receipts[method]){
      fill(form,method,receipt.inputs);
      const bytes=lib.receiptDownloadBytes(method,receipt,form);
      assert.deepEqual(Buffer.from(bytes),Buffer.from(JSON.stringify(receipt)+"\n","utf8"));
      const imported=await lib.readReplay(method,new File([bytes],"receipt.json"));assert.deepEqual(imported,receipt.inputs);
      lib.restoreReplay(form,method,imported);assert.deepEqual(forms[method](form),receipt.inputs);
    }
  }));
  test(`${method}: invalid envelopes, method/version, malicious JSON and size reject before restore`,async()=>{
    const original=receipts[method][0],other=receipts[method==="risk"?"stress":"risk"][0];
    for(const value of [other,{},[],null,{...original,schema_id:"future-v2"},{...original,extra:true},{...original,result:{...original.result,method_id:"forecast"}},{...original,result:{...original.result,precision_id:"float"}},{...original,result:{...original.result,data_authority:"real_market_data"}}])await assert.rejects(lib.readReplay(method,file(value)));
    const text=JSON.stringify(original);
    for(const raw of [text.replace('{','{"schema_id":"other",'),text.replace('{','{"\\u0073chema_id":"other",'),'{"__proto__":{"polluted":true}}',text+"evil()",'['.repeat(20)+'0'+']'.repeat(20),'',"\ufeff"+text,'{"result":NaN}',text.replace('"inputs":','"inputs|result":')])await assert.rejects(lib.readReplay(method,file(raw)));
    assert.equal({}.polluted,undefined);
    let read=false;await assert.rejects(lib.readReplay(method,{size:1048577,arrayBuffer:()=>{read=true;throw Error("read");}}));assert.equal(read,false);
    await assert.rejects(lib.readReplay(method,{size:1,arrayBuffer:async()=>new Uint8Array([0xc0]).buffer}));
    await assert.rejects(lib.readReplay(method,{size:1,arrayBuffer:async()=>new Uint8Array([1,2]).buffer}));
    await assert.rejects(lib.readReplay(method,{size:1,arrayBuffer:async()=>{throw Error("unreadable");}}));
  });
  test(`${method}: exact input bounds reject numbers, injection, ambiguous currency, invalid calendar and incomplete maps`,()=>{
    const changes=[v=>{v.extra=1;},v=>{v.reporting_currency="$";},v=>{v.reporting_currency="USD\n";},v=>{v.exposure_date="2025-02-30";},v=>{v.exposure_date="0000-01-01";},v=>{v.exposures=[];},v=>{v.exposures=Array(9).fill(v.exposures[0]);},v=>{v.exposures[0].asset_id="x\n";},v=>{v.exposures[0].asset_id="<script>";},v=>{v.exposures.push(v.exposures[0]);}];
    for(const amount of [1,true,null,"1e2","+1","01","NaN","1\n","0.0000000000001","1234567890123456789012345"," "] )changes.push(v=>{v.exposures[0].amount=amount;});
    if(method==="risk")changes.push(v=>{v.confidence="0";},v=>{v.confidence="1";},v=>{v.horizon=true;},v=>{v.horizon=21;},v=>{v.sessions[0].factors={};},v=>{v.sessions[0].factors[v.exposures[0].asset_id]="0";},v=>{v.sessions[0].start=v.sessions[0].end;},v=>{v.sessions[1].start="2025-01-01";},v=>{v.sessions[1].session_id=v.sessions[0].session_id;},v=>{v.sessions=Array(121).fill(v.sessions[0]);});
    else changes.push(v=>{v.exposures[0].currency="EUR";},v=>{v.exposures[0].exposure_type="option";},v=>{v.scenarios[0].shocks={};},v=>{v.scenarios[0].shocks[v.exposures[0].asset_id]="-100.000000000001";},v=>{v.common_shocks=["1000.000000000001"];},v=>{v.common_shocks=["0","-0.0"];},v=>{v.scenarios.push(v.scenarios[0]);},v=>{v.common_shocks=[];},v=>{v.common_shocks=Array(22).fill("0");});
    for(const change of changes){const inputs=structuredClone(receipts[method][0].inputs);change(inputs);assert.throws(()=>lib.validateReplayInputs(method,inputs));}
  });
  test(`${method}: download is explicit, current and byte exact; valid import discards outputs and needs explicit fresh submit`,async()=>mounted(method,async({form,requests,submit,select,click,blobs,revoked,clicks})=>{
    const download=()=>[...document.querySelectorAll("button")].find(b=>b.textContent==="Download current receipt (JSON)");
    assert.equal(download().disabled,true);await submit();assert.equal(download().disabled,true);
    await act(async()=>requests[0].resolve(reply(receipts[method][0])));assert.ok(result());
    await click("Download current receipt (JSON)");assert.equal(blobs.length,1);assert.equal(blobs[0].type,"application/json;charset=utf-8");
    assert.deepEqual(Buffer.from(await blobs[0].arrayBuffer()),Buffer.from(JSON.stringify(receipts[method][0])+"\n"));assert.equal(clicks[0].download,`finlens-hypothetical-${method}-v1.json`);
    await new Promise(resolve=>setTimeout(resolve,10));assert.deepEqual(revoked,["blob:local-1"]);assert.equal(document.querySelector('a[download]'),null);
    await select(new File([await blobs[0].arrayBuffer()],"receipt.json"));assert.equal(result(),null);assert.equal(download().disabled,true);assert.equal(requests.length,1);
    assert.deepEqual(forms[method](form),receipts[method][0].inputs);assert.match(document.body.textContent,/Imported hypothetical assumptions/);
    await submit();assert.deepEqual(JSON.parse(requests[1].options.body),receipts[method][0].inputs);
    await act(async()=>requests[1].resolve(reply(receipts[method][0])));assert.ok(result());
    // Programmatic changes without input events cannot export a mismatched receipt.
    form.elements.namedItem("currency").value="EUR";await click("Download current receipt (JSON)");assert.equal(blobs.length,1);assert.match(document.body.textContent,/current validated result is required/);
  }));
  test(`${method}: invalid import preserves drafts and current receipt without requests`,async()=>mounted(method,async({form,requests,submit,select})=>{
    await submit();await act(async()=>requests[0].resolve(reply(receipts[method][0])));const before=forms[method](form);assert.ok(result());
    for(const value of [file("invalid"),file(receipts[method==="risk"?"stress":"risk"][0]),new File([new Uint8Array(1048577)],"large.json")]){
      await select(value);assert.deepEqual(forms[method](form),before);assert.ok(result());assert.equal(requests.length,1);assert.match(document.body.textContent,/draft is unchanged/);
    }
  }));
  test(`${method}: valid import aborts pending calculation, ignores late result, and never auto-submits`,async()=>mounted(method,async({form,requests,submit,select})=>{
    await submit();await select(file(receipts[method][1]));assert.equal(requests[0].options.signal.aborted,true);
    assert.deepEqual(forms[method](form),receipts[method][1].inputs);assert.equal(requests.length,1);
    await act(async()=>requests[0].resolve(reply(receipts[method][0])));assert.equal(result(),null);
    await submit();assert.deepEqual(JSON.parse(requests[1].options.body),receipts[method][1].inputs);
  }));
  test(`${method}: pending file reads cannot overwrite edits, calculation, cancellation, or newer imports`,async()=>mounted(method,async({form,requests,select,edit,submit,click})=>{
    const bytes=await file(receipts[method][1]).arrayBuffer();
    for(const action of [async()=>edit(),async()=>submit(),async()=>click("Cancel local import"),async()=>select(file(receipts[method][0]))]){
      fill(form,method,receipts[method][0].inputs);const pending=deferred();await select({size:bytes.byteLength,arrayBuffer:()=>pending.promise});assert.match(document.body.textContent,/Reading local receipt/);
      await action();await act(async()=>pending.resolve(bytes));assert.deepEqual(forms[method](form),receipts[method][0].inputs);assert.equal(result(),null);
    }
    assert.equal(requests.length,1);
  }));
  test(`${method}: repeated edits immediately cancel pending local-read UI even when parent status is unchanged`,async()=>mounted(method,async({select,edit})=>{
    await edit();const bytes=await file(receipts[method][1]).arrayBuffer(),pending=deferred();
    await select({size:bytes.byteLength,arrayBuffer:()=>pending.promise});await edit();
    assert.doesNotMatch(document.body.textContent,/Reading local receipt/);assert.equal([...document.querySelectorAll("button")].some(b=>b.textContent==="Cancel local import"),false);
    await act(async()=>pending.resolve(bytes));assert.equal(result(),null);
  }));
  test(`${method}: obsolete file failures cannot erase a newer successful import`,async()=>mounted(method,async({form,select})=>{
    const pending=deferred(),bytes=await file(receipts[method][1]).arrayBuffer();
    await select({size:bytes.byteLength,arrayBuffer:()=>pending.promise});
    await select(file(receipts[method][1]));assert.deepEqual(forms[method](form),receipts[method][1].inputs);
    await act(async()=>pending.reject(Error("Late device failure")));
    assert.equal(document.querySelector('[role="alert"]'),null);assert.match(document.body.textContent,/Imported hypothetical assumptions/);assert.equal(result(),null);
  }));
  test(`${method}: unmount revokes URLs and invalidates an outstanding local read`,async()=>{
    let pending,bytes,revoked; const schedule=globalThis.setTimeout;
    globalThis.setTimeout=(callback,delay,...args)=>delay===0?schedule(()=>{},60000):schedule(callback,delay,...args);
    try {await mounted(method,async({select,submit,requests,click,revoked:urls})=>{
      revoked=urls;
      await submit();await act(async()=>requests[0].resolve(reply(receipts[method][0])));await click("Download current receipt (JSON)");assert.deepEqual(revoked,[]);
      bytes=await file(receipts[method][1]).arrayBuffer();pending=deferred();await select({size:bytes.byteLength,arrayBuffer:()=>pending.promise});
    });assert.deepEqual(revoked,["blob:local-1"]);await act(async()=>pending.resolve(bytes));}
    finally{globalThis.setTimeout=schedule;}
  });
}
test("download cleanup revokes object URL if native click throws",()=>{
  const dom=new JSDOM("<!doctype html><body></body>"),oldDocument=globalThis.document,oldCreate=URL.createObjectURL,oldRevoke=URL.revokeObjectURL;
  const urls=[];try{globalThis.document=dom.window.document;URL.createObjectURL=()=>"blob:failure";URL.revokeObjectURL=url=>urls.push(url);dom.window.HTMLAnchorElement.prototype.click=()=>{throw Error("blocked");};
    assert.throws(()=>lib.downloadReplay(new Uint8Array([1]),"risk"),/blocked/);assert.deepEqual(urls,["blob:failure"]);assert.equal(document.querySelector("a"),null);
  }finally{globalThis.document=oldDocument;URL.createObjectURL=oldCreate;URL.revokeObjectURL=oldRevoke;dom.window.close();}
});
