// Offline browser evidence: actual local downloads/imports, synthetic API interception.
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash,randomUUID} from "node:crypto";
import {mkdirSync,mkdtempSync,readFileSync,writeFileSync,appendFileSync,existsSync,unlinkSync,rmdirSync} from "node:fs";
import {tmpdir} from "node:os";
import {dirname,join,resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium,expect} from "@playwright/test";
const frontend=fileURLToPath(new URL("../",import.meta.url)),backend=resolve(frontend,"../backend"),runId=randomUUID();
const base=process.env.FINLENS_REPLAY_BROWSER_URL||"http://127.0.0.1:3139",disabled=process.env.FINLENS_REPLAY_DISABLED_URL||"http://127.0.0.1:3138";
const ledger=resolve(process.env.FINLENS_REPLAY_LEDGER_PATH||join(frontend,"test-results",`replay-browser-${runId}.jsonl`));
mkdirSync(dirname(ledger),{recursive:true});writeFileSync(ledger,"",{flag:"wx"});let sequence=0,browser,requestId=0;
const hash=value=>createHash("sha256").update(value).digest("hex");
const record=(event,data={})=>appendFileSync(ledger,JSON.stringify({schema:"finlens-replay-browser-ledger-v1",runId,sequence:++sequence,at:new Date().toISOString(),event,...data})+"\n");
const canonical=v=>Array.isArray(v)?`[${v.map(canonical).join(",")}]`:v&&typeof v==="object"?`{${Object.entries(v).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,x])=>`${JSON.stringify(k)}:${canonical(x)}`).join(",")}}`:JSON.stringify(v);
async function verify(scope,name,action){record("assertion_started",{scope,name});try{record("assertion_passed",{scope,name,observed:await action()});}catch(error){record("assertion_failed",{scope,name,error:{message:error.message,stack:error.stack}});throw error;}}
const fields=(method,v)=>({currency:v.reporting_currency,date:v.exposure_date,exposures:v.exposures.map(e=>`${e.asset_id} ${e.amount}`).join("\n"),...(method==="risk"?{confidence:v.confidence,horizon:String(v.horizon),value:v.portfolio_value??"",sessions:v.sessions.map(s=>`${s.session_id} ${s.start} ${s.end} ${v.exposures.map(e=>s.factors[e.asset_id]).join(" ")}`).join("\n")}:{scenarios:v.scenarios.map(s=>`${s.scenario_id} ${v.exposures.map(e=>s.shocks[e.asset_id]).join(" ")}`).join("\n"),common:v.common_shocks.join(" ")})});
try{
  record("run_started",{base,disabled,ledger,channel:process.env.FINLENS_REPLAY_BROWSER_CHANNEL||"bundled-chromium"});
  for(const url of [base,disabled])assert.match(url,/^http:\/\/127\.0\.0\.1:[0-9]+$/);
  const sources=["frontend/lib/hypothetical-replay.ts","frontend/components/hypothetical-replay.tsx","frontend/components/hypothetical-risk.tsx","frontend/components/hypothetical-stress.tsx","frontend/scripts/verify-hypothetical-replay.mjs","backend/app/hypothetical_risk.py","backend/app/hypothetical_stress.py"];
  record("source_hashes",{sha256:Object.fromEntries(sources.map(p=>[p,hash(readFileSync(resolve(frontend,"..",p)))]))});
  const temp=mkdtempSync(join(tmpdir(),"finlens-replay-browser-")),paths={risk:join(temp,"risk.json"),stress:join(temp,"stress.json")};let receipts;
  try{
    const python=join(backend,".venv",...(process.platform==="win32"?["Scripts","python.exe"]:["bin","python"]));
    const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>["systemroot","windir","path","temp","tmp","tmpdir","pathext","comspec","number_of_processors"].includes(key.toLowerCase())));
    const args=["-I","-S","-B","tests/run_financial_insights.py","tests/test_hypothetical_risk.py","tests/test_hypothetical_stress.py"];
    const run=spawnSync(python,args,{cwd:backend,env:{...env,FINLENS_RISK_CONTRACT_OUTPUT:paths.risk,FINLENS_STRESS_CONTRACT_OUTPUT:paths.stress},encoding:"utf8",timeout:60000,windowsHide:true});
    record("python_capture",{python,args,status:run.status,stdout:run.stdout,stderr:run.stderr});assert.equal(run.status,0);
    receipts=Object.fromEntries(Object.entries(paths).map(([method,path])=>{const bytes=readFileSync(path),values=JSON.parse(bytes);record("python_receipts",{method,count:values.length,sha256:hash(bytes),receipts:values});return [method,values];}));
  }finally{for(const path of Object.values(paths))if(existsSync(path))unlinkSync(path);rmdirSync(temp);}
  browser=await chromium.launch({headless:true,...(process.env.FINLENS_REPLAY_BROWSER_CHANNEL?{channel:process.env.FINLENS_REPLAY_BROWSER_CHANNEL}:{})});record("browser_started",{version:browser.version()});
  async function trace(context,scope,origin){
    const violations=[],errors=[],ids=new WeakMap();
    context.on("request",req=>{const id=++requestId;ids.set(req,id);record("request",{scope,id,url:req.url(),method:req.method(),resourceType:req.resourceType(),body:req.postData()});});
    context.on("response",res=>record("response",{scope,id:ids.get(res.request()),url:res.url(),status:res.status()}));
    context.on("requestfailed",req=>record("request_failed",{scope,id:ids.get(req),url:req.url(),failure:req.failure()}));
    context.on("page",page=>page.on("pageerror",e=>{errors.push(e.message);record("page_error",{scope,message:e.message});}));
    const deny=async(route,reason)=>{violations.push(reason);record("request_denied",{scope,id:ids.get(route.request()),reason});await route.abort();};
    return {violations,errors,deny,ids};
  }
  const off=await browser.newContext({serviceWorkers:"block"}),offTrace=await trace(off,"disabled",disabled);
  await off.route("**/*",route=>new URL(route.request().url()).origin===disabled?route.continue():offTrace.deny(route,"Nonlocal request"));const offPage=await off.newPage();
  for(const path of ["/hypothetical-risk","/hypothetical-risk/stress"])await verify("disabled",path,async()=>{const response=await offPage.goto(disabled+path);assert.equal(response.status(),404);return {status:response.status()};});
  assert.deepEqual(offTrace.violations,[]);assert.deepEqual(offTrace.errors,[]);await off.close();
  for(const width of [1440,390])for(const method of ["risk","stress"]){
    const scope={width,method},context=await browser.newContext({viewport:{width,height:900},serviceWorkers:"block",acceptDownloads:true}),tr=await trace(context,scope,base);
    let apiCount=0,hold=false,release;const apiInputs=[];
    await context.addInitScript(()=>{
      window.replayEvidence={urls:[],revoked:[],deliveries:[],writes:[],held:[],heldReadsStarted:0,completedReads:0,readCompletions:[]};
      const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);
      URL.createObjectURL=blob=>{const url=create(blob);window.replayEvidence.urls.push({url,size:blob.size,type:blob.type});return url;};
      URL.revokeObjectURL=url=>{window.replayEvidence.revoked.push(url);revoke(url);};
      const native=window.fetch.bind(window);window.fetch=async(input,init)=>{if(typeof input!=="string"||!input.startsWith("/api/finlens/hypothetical-"))return native(input,init);const response=await native(input,{...init,signal:null});window.replayEvidence.deliveries.push({aborted:init.signal.aborted,body:init.body});return response;};
      const read=File.prototype.arrayBuffer;File.prototype.arrayBuffer=function(){
        if(!window.pauseReplayRead)return read.call(this);
        const id=++window.replayEvidence.heldReadsStarted,name=this.name,size=this.size;
        return new Promise((resolve,reject)=>window.replayEvidence.held.push(async()=>{
          let outcome="fulfilled";
          try{resolve(await read.call(this));}catch(error){outcome="rejected";reject(error);}
          finally{
            // Resolve the native read and let its consumer promise jobs finish first.
            await new Promise(done=>setTimeout(done,0));
            window.replayEvidence.completedReads++;window.replayEvidence.readCompletions.push({id,name,size,outcome});
          }
        }));
      };
      const write=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){window.replayEvidence.writes.push({key:k,value:v});return write.call(this,k,v);};
    });
    await context.route("**/*",async route=>{
      const req=route.request(),url=new URL(req.url());if(url.origin!==base)return tr.deny(route,"Nonlocal request");
      if(!url.pathname.startsWith("/api/finlens/"))return route.continue();
      if(url.pathname!==`/api/finlens/hypothetical-${method}`||req.method()!=="POST")return tr.deny(route,"Unexpected API request");
      apiCount++;const inputs=req.postDataJSON();apiInputs.push(inputs);const index=receipts[method].findIndex(r=>canonical(r.inputs)===canonical(inputs));assert.ok(index>=0,"Only actual captured inputs may calculate");
      if(hold){record("api_held",{scope,id:tr.ids.get(req),inputs});await new Promise(resolve=>{release=resolve;});}
      const body=JSON.stringify(receipts[method][index]);record("api_reply",{scope,id:tr.ids.get(req),fixtureIndex:index,status:200,sha256:hash(body),body:receipts[method][index]});await route.fulfill({status:200,contentType:"application/json",body});
    });
    const page=await context.newPage(),path=method==="risk"?"/hypothetical-risk":"/hypothetical-risk/stress";await page.goto(base+path);
    const result=page.locator(method==="risk"?'[aria-labelledby="risk-result"]':'[aria-labelledby="stress-results"]');
    const download=page.getByRole("button",{name:"Download current receipt (JSON)",exact:true}),input=page.locator('input[type="file"]');
    const snapshot=()=>page.locator("form").evaluate(form=>Object.fromEntries(new FormData(form)));
    const fill=async r=>{for(const [name,value] of Object.entries(fields(method,r.inputs)))await page.locator(`[name="${name}"]`).fill(value);};
    const calculate=()=>page.getByRole("button",{name:method==="risk"?"Calculate hypothetical risk":"Calculate hypothetical stress",exact:true}).click();
    const choose=async bytes=>input.setInputFiles({name:"local-receipt.json",mimeType:"application/json",buffer:bytes});
    const releaseReads=async()=>{
      const barrier=await page.evaluate(async()=>{
        window.pauseReplayRead=false;const batch=window.replayEvidence.held.splice(0),before=window.replayEvidence.completedReads;
        await Promise.all(batch.map(run=>run()));
        // Native reads and consumer jobs have settled; allow React's commit/effects too.
        await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
        return {released:batch.length,before,after:window.replayEvidence.completedReads,queued:window.replayEvidence.held.length,completions:window.replayEvidence.readCompletions.slice(before)};
      });
      record("file_read_barrier",{scope,...barrier});
      assert.equal(barrier.released,1);assert.equal(barrier.after,barrier.before+barrier.released);assert.equal(barrier.queued,0);
      assert.equal(barrier.completions.length,barrier.released);assert.ok(barrier.completions.every(read=>read.outcome==="fulfilled"));return barrier;
    };
    const downloaded=async keyboard=>{const wait=page.waitForEvent("download");if(keyboard){await download.focus();await page.keyboard.press("Enter");}else await download.click();const d=await wait,stream=await d.createReadStream(),chunks=[];for await(const chunk of stream)chunks.push(chunk);assert.equal(await d.failure(),null);return {bytes:Buffer.concat(chunks),filename:d.suggestedFilename()};};
    let bytes;
    await verify(scope,"explicit-byte-exact-keyboard-download",async()=>{
      await expect(download).toBeDisabled();await fill(receipts[method][0]);await calculate();await expect(result).toBeVisible();const d=await downloaded(true);bytes=d.bytes;
      assert.deepEqual(bytes,Buffer.from(JSON.stringify(receipts[method][0])+"\n"));assert.equal(d.filename,`finlens-hypothetical-${method}-v1.json`);
      await expect.poll(()=>page.evaluate(()=>window.replayEvidence.revoked.length)).toBe(1);
      return {size:bytes.length,sha256:hash(bytes),filename:d.filename,urlEvidence:await page.evaluate(()=>({urls:window.replayEvidence.urls,revoked:window.replayEvidence.revoked}))};
    });
    await verify(scope,"wrong-method-malicious-and-oversized-files-preserve-current-draft",async()=>{
      const before=await snapshot(),count=apiCount;
      for(const bad of [Buffer.from(JSON.stringify(receipts[method==="risk"?"stress":"risk"][0])),Buffer.from('{"__proto__":{"polluted":true}}'),Buffer.alloc(1048577)]){await choose(bad);await expect(page.locator("main").getByRole("alert")).toContainText("draft is unchanged");assert.deepEqual(await snapshot(),before);await expect(result).toBeVisible();}
      assert.equal(apiCount,count);return {inputs:before,apiCount,filesRejected:3};
    });
    await verify(scope,"keyboard-local-import-restores-only-assumptions-without-request",async()=>{
      const count=apiCount;const chooser=page.waitForEvent("filechooser");await input.focus();await page.keyboard.press("Enter");await(await chooser).setFiles({name:"downloaded.json",mimeType:"application/json",buffer:bytes});
      await expect(result).toHaveCount(0);await expect(download).toBeDisabled();await expect(page.locator('main > p[role="status"]')).toContainText("Imported hypothetical assumptions");assert.equal(apiCount,count);assert.deepEqual(await snapshot(),fields(method,receipts[method][0].inputs));
      return {inputs:await snapshot(),apiCount,resultCount:await result.count(),downloadDisabled:await download.isDisabled()};
    });
    await verify(scope,"fresh-calculation-is-explicit-and-reproduces-download",async()=>{
      const before=apiCount;await calculate();await expect(result).toBeVisible();assert.equal(apiCount,before+1);const d=await downloaded(false);assert.deepEqual(d.bytes,bytes);return {apiCount,inputs:apiInputs.at(-1),sha256:hash(d.bytes)};
    });
    await verify(scope,"decimal-precision-input-order-round-trip",async()=>{
      const precision=receipts[method].find(r=>JSON.stringify(r.inputs).includes("000000000001"))||receipts[method].find(r=>r.inputs.exposures.some(e=>e.amount.includes(".")))||receipts[method][1];const count=apiCount;
      await choose(Buffer.from(JSON.stringify(precision)));await expect(result).toHaveCount(0);assert.deepEqual(await snapshot(),fields(method,precision.inputs));assert.equal(apiCount,count);await calculate();await expect(result).toBeVisible();const d=await downloaded(false);assert.deepEqual(d.bytes,Buffer.from(JSON.stringify(precision)+"\n"));return {inputs:precision.inputs,sha256:hash(d.bytes)};
    });
    await verify(scope,"import-invalidates-pending-calculation-and-ignored-abort-delivery",async()=>{
      await fill(receipts[method][0]);hold=true;const before=apiCount;await calculate();await expect.poll(()=>apiCount).toBe(before+1);await expect.poll(()=>typeof release).toBe("function");
      await choose(bytes);await expect(result).toHaveCount(0);const deliveries=await page.evaluate(()=>window.replayEvidence.deliveries.length);hold=false;release();await expect.poll(()=>page.evaluate(()=>window.replayEvidence.deliveries.length)).toBe(deliveries+1);
      assert.equal(await page.evaluate(()=>window.replayEvidence.deliveries.at(-1).aborted),true);await expect(result).toHaveCount(0);assert.deepEqual(await snapshot(),fields(method,receipts[method][0].inputs));return {apiCount,delivery:await page.evaluate(()=>window.replayEvidence.deliveries.at(-1)),resultCount:await result.count()};
    });
    await verify(scope,"late-file-read-cannot-overwrite-edits",async()=>{
      await page.evaluate(()=>{window.pauseReplayRead=true;});await choose(Buffer.from(JSON.stringify(receipts[method][1])));await expect(page.getByRole("button",{name:"Cancel local import"})).toBeVisible();
      await page.locator('[name="currency"]').fill("EUR");const barrier=await releaseReads();
      await expect(page.locator('[name="currency"]')).toHaveValue("EUR");await expect(page.getByRole("button",{name:"Cancel local import"})).toHaveCount(0);await expect(result).toHaveCount(0);return {inputs:await snapshot(),apiCount,barrier};
    });
    await verify(scope,"repeated-edit-clears-superseded-read-status-immediately",async()=>{
      await page.evaluate(()=>{window.pauseReplayRead=true;});await choose(bytes);await expect(page.getByRole("button",{name:"Cancel local import"})).toBeVisible();
      await page.locator('[name="currency"]').fill("GBP");await expect(page.getByRole("button",{name:"Cancel local import"})).toHaveCount(0);
      await expect(page.getByRole("region",{name:"Local receipt replay",exact:true}).getByRole("status")).toHaveText("");
      const barrier=await releaseReads();await expect(page.locator('[name="currency"]')).toHaveValue("GBP");await expect(result).toHaveCount(0);return {inputs:await snapshot(),apiCount,barrier};
    });
    await verify(scope,"keyboard-cancel-discards-local-read",async()=>{
      const before=await snapshot(),count=apiCount;await page.evaluate(()=>{window.pauseReplayRead=true;});await choose(bytes);const cancel=page.getByRole("button",{name:"Cancel local import",exact:true});await cancel.focus();await page.keyboard.press("Enter");
      const barrier=await releaseReads();await expect(page.getByRole("region",{name:"Local receipt replay",exact:true}).getByRole("status")).toContainText("Local import cancelled");assert.deepEqual(await snapshot(),before);assert.equal(apiCount,count);return {inputs:before,apiCount,barrier};
    });
    await verify(scope,"narrow-controls-no-page-overflow-no-storage-or-external-requests",async()=>{
      await input.scrollIntoViewIfNeeded();const geometry=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('input[type="file"],#risk-replay,#stress-replay')].map(e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right})),writes:window.replayEvidence.writes}));
      assert.ok(geometry.scrollWidth<=width+1);for(const c of geometry.controls)assert.ok(c.left>=0&&c.right<=width+1);assert.deepEqual(geometry.writes,[]);assert.deepEqual(tr.violations,[]);assert.deepEqual(tr.errors,[]);
      if(process.env.FINLENS_REPLAY_SCREENSHOT_DIR){mkdirSync(process.env.FINLENS_REPLAY_SCREENSHOT_DIR,{recursive:true});const path=join(process.env.FINLENS_REPLAY_SCREENSHOT_DIR,`${method}-${width}.png`);await page.screenshot({path,fullPage:true});record("screenshot",{scope,path,sha256:hash(readFileSync(path))});}
      return {...geometry,apiCount,violations:tr.violations,errors:tr.errors};
    });
    record("viewport_complete",{scope,apiCount,evidence:await page.evaluate(()=>({urls:window.replayEvidence.urls,revoked:window.replayEvidence.revoked,deliveries:window.replayEvidence.deliveries,heldReadsStarted:window.replayEvidence.heldReadsStarted,completedReads:window.replayEvidence.completedReads,readCompletions:window.replayEvidence.readCompletions}))});await context.close();
  }
  record("run_complete",{outcome:"passed"});console.log(`Replay browser verification passed. Ledger: ${ledger}`);
}catch(error){record("run_complete",{outcome:"failed",error:{message:error.message,stack:error.stack}});throw error;}
finally{if(browser)await browser.close();}
