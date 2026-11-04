// Local frontend only; API replies are fresh synthetic Python output. Every
// invocation retains a JSONL execution/request ledger, including failed runs.
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash, randomUUID} from "node:crypto";
import {existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, appendFileSync, unlinkSync, rmdirSync} from "node:fs";
import {tmpdir} from "node:os";
import {dirname, join, resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium, expect} from "@playwright/test";

const frontend=resolve(fileURLToPath(new URL("../",import.meta.url))), backend=resolve(frontend,"../backend");
const base=process.env.FINLENS_RISK_BROWSER_URL || "http://127.0.0.1:3139";
const disabled=process.env.FINLENS_RISK_DISABLED_URL || "http://127.0.0.1:3138";
const runId=randomUUID(), started=performance.now();
const ledger=resolve(process.env.FINLENS_RISK_LEDGER_PATH || join(frontend,"test-results",`risk-browser-${runId}.jsonl`));
mkdirSync(dirname(ledger),{recursive:true});
writeFileSync(ledger,"",{flag:"wx"}); // Never overwrite earlier run evidence.
let sequence=0, browser, requestId=0;
const hash=body=>createHash("sha256").update(body).digest("hex");
const errorInfo=error=>({name:error?.name || "Error",message:error?.message || String(error),stack:error?.stack});
function record(event, data={}) {
  appendFileSync(ledger,JSON.stringify({schema:"finlens-risk-browser-ledger-v1",runId,sequence:++sequence,
    at:new Date().toISOString(),elapsedMs:Math.round(performance.now()-started),event,...data})+"\n");
}
async function verify(width,name,action) {
  record("assertion_started",{width,name});
  try {const observed=await action(); record("assertion_passed",{width,name,observed}); return observed;}
  catch(error) {record("assertion_failed",{width,name,error:errorInfo(error)}); throw error;}
}
function trace(context,width,origin,violations,errors) {
  const ids=new WeakMap();
  context.on("request",request=>{
    const id=++requestId; ids.set(request,id);
    record("request",{width,id,method:request.method(),url:request.url(),resourceType:request.resourceType(),
      body:request.url().startsWith(`${origin}/api/finlens/`) ? request.postData() : null});
  });
  context.on("response",response=>record("response",{width,id:ids.get(response.request()),url:response.url(),status:response.status()}));
  context.on("requestfailed",request=>record("request_failed",{width,id:ids.get(request),url:request.url(),failure:request.failure()}));
  context.on("page",page=>page.on("pageerror",error=>{errors.push(error.message);record("page_error",{width,error:errorInfo(error)});}));
  return {
    id:request=>ids.get(request),
    deny:async(route,reason)=>{
      violations.push(reason); record("request_denied",{width,id:ids.get(route.request()),reason});
      await route.abort();
    },
  };
}

try {
  record("run_started",{base,disabled,channel:process.env.FINLENS_RISK_BROWSER_CHANNEL || "bundled-chromium",ledger});
  for (const url of [base,disabled]) assert.ok(/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(url),"Loopback origins only");
  const sourcePaths=["backend/app/hypothetical_risk.py","backend/app/hypothetical_risk_route.py","backend/tests/test_hypothetical_risk.py",
    "frontend/app/hypothetical-risk/page.tsx","frontend/components/hypothetical-risk.tsx","frontend/lib/hypothetical-risk.ts",
    "frontend/scripts/verify-hypothetical-risk.mjs"];
  record("source_hashes",{sha256:Object.fromEntries(sourcePaths.map(path=>[path,hash(readFileSync(resolve(frontend,"..",path)))]))});
  const temp=mkdtempSync(join(tmpdir(),"finlens-risk-browser-")), output=join(temp,"responses.json");
  let receipts;
  try {
    const python=join(backend,".venv",...(process.platform === "win32" ? ["Scripts","python.exe"] : ["bin","python"]));
    const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>["systemroot","windir","path","temp","tmp","tmpdir","pathext","comspec","number_of_processors"].includes(key.toLowerCase())));
    const args=["-I","-S","-B","tests/run_financial_insights.py","tests/test_hypothetical_risk.py"];
    const run=spawnSync(python,args,{cwd:backend,env:{...env,FINLENS_RISK_CONTRACT_OUTPUT:output},encoding:"utf8",timeout:60000,windowsHide:true});
    record("python_capture",{python,args,status:run.status,stdout:run.stdout,stderr:run.stderr,error:run.error ? errorInfo(run.error) : null});
    assert.equal(run.status,0,`${run.stdout}\n${run.stderr}`);
    const body=readFileSync(output); receipts=JSON.parse(body.toString("utf8"));
    record("python_receipts",{sha256:hash(body),count:receipts.length,receipts});
  } finally {if(existsSync(output)) unlinkSync(output); rmdirSync(temp);}
  browser=await chromium.launch({headless:true,...(process.env.FINLENS_RISK_BROWSER_CHANNEL ? {channel:process.env.FINLENS_RISK_BROWSER_CHANNEL} : {})});
  record("browser_started",{version:await browser.version()});
  const off=await browser.newContext({serviceWorkers:"block"}), offViolations=[], offErrors=[];
  const offTrace=trace(off,null,disabled,offViolations,offErrors), offPage=await off.newPage();
  await off.route("**/*",route=>new URL(route.request().url()).origin===disabled ? route.continue() : offTrace.deny(route,"Unexpected disabled-page origin"));
  await verify(null,"disabled-page",async()=>{
    const status=(await offPage.goto(`${disabled}/hypothetical-risk`)).status(); assert.equal(status,404);
    assert.deepEqual(offViolations,[]); assert.deepEqual(offErrors,[]); return {status,violations:offViolations,errors:offErrors};
  });
  await off.close();
  for (const width of [1440,390]) {
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:"block"});
    const violations=[],errors=[],observed=trace(context,width,base,violations,errors),page=await context.newPage();
    let mode="normal",pending;
    record("viewport_started",{width,height:900});
    await context.addInitScript(()=>{
      const native=window.fetch.bind(window); window.riskDeliveries=[]; let id=0;
      window.fetch=async(input,init)=>{
        if(typeof input!=="string" || !input.endsWith("/hypothetical-risk")) return native(input,init);
        const deliveryId=++id;
        const response=await native(input,{...init,signal:null});
        window.riskDeliveries.push({id:deliveryId,aborted:init.signal.aborted,inputs:JSON.parse(init.body),status:response.status}); return response;
      };
    });
    await context.route("**/*",async route=>{
      const url=new URL(route.request().url());
      if(url.origin!==base) return observed.deny(route,`Unexpected origin: ${url.origin}`);
      if(!url.pathname.startsWith("/api/finlens/")) return route.continue();
      if(url.pathname!=="/api/finlens/hypothetical-risk") return observed.deny(route,`Unexpected API: ${url.pathname}`);
      const inputs=route.request().postDataJSON();
      const fixtureIndex=receipts.findIndex(r=>r.inputs.confidence===inputs.confidence && r.inputs.horizon===inputs.horizon && r.inputs.exposures[0].amount===inputs.exposures[0].amount && r.inputs.sessions.length===inputs.sessions.length && r.inputs.portfolio_value===inputs.portfolio_value);
      assert.ok(fixtureIndex>=0,"Unknown synthetic browser request");
      const selected=mode;
      if(selected==="hold") {record("api_held",{width,id:observed.id(route.request()),inputs}); await new Promise(resolve=>{pending=resolve;});}
      const status=selected==="failure" ? 422 : 200, body=selected==="malformed" ? {schema_id:"wrong"} : receipts[fixtureIndex];
      record("api_reply",{width,id:observed.id(route.request()),mode:selected,fixtureIndex,status,body});
      await route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
    });
    await page.goto(`${base}/hypothetical-risk`);
    const input=receipts[0].inputs, results=page.getByRole("region",{name:"Hypothetical sample results",exact:true});
    const field=name=>page.getByLabel(name,{exact:true});
    const calculate=()=>page.getByRole("button",{name:"Calculate hypothetical risk",exact:true}).click();
    const fill=async()=>{
      await field("Exposure date").fill(input.exposure_date); await field("Horizon (supplied intervals)").fill("1");
      await field("Confidence (0 < α < 1)").fill(input.confidence); await field("Signed exposures").fill("long 100");
      await field("Declared portfolio value (optional)").fill("100");
      await field("Exact gross-return factors").fill(input.sessions.map(s=>`${s.session_id} ${s.start} ${s.end} ${s.factors.long}`).join("\n"));
    };
    const displays=()=>results.locator("dd").allTextContents();
    await fill();
    await verify(width,"exact-threshold-ties",async()=>{
      await calculate(); await expect(results).toBeVisible();
      await expect(results.locator("dd").nth(0)).toHaveText("4.000000000000000000");
      await expect(results.locator("dd").nth(1)).toHaveText("7.000000000000000000"); return {display:await displays()};
    });
    if(process.env.FINLENS_RISK_SCREENSHOT_DIR) {
      const path=join(process.env.FINLENS_RISK_SCREENSHOT_DIR,`risk-${width}.png`);
      await page.screenshot({path,fullPage:true}); record("screenshot",{width,path,sha256:hash(readFileSync(path))});
    }
    await verify(width,"keyboard-audit-and-replay",async()=>{
      const summary=page.getByText("Complete loss and tail audit",{exact:true});
      await summary.focus(); await page.keyboard.press("Enter"); await expect(page.locator("tbody tr")).toHaveCount(10);
      await expect(summary.locator("..")).toHaveAttribute("open","");
      await expect(page.getByRole("region",{name:"Scenario loss audit",exact:true})).toBeVisible();
      const full=page.getByText("Full replay receipt and normalized inputs",{exact:true});
      await full.focus(); await page.keyboard.press("Enter");
      await expect(full.locator("..")).toHaveAttribute("open","");
      await expect(page.getByLabel("Exact replay receipt")).toBeVisible();
      await expect(page.getByLabel("Exact replay receipt")).toContainText('"unverified_synthetic_inputs"');
      return {auditOpen:await summary.locator("..").evaluate(e=>e.open),replayOpen:await full.locator("..").evaluate(e=>e.open),replayVisible:await page.getByLabel("Exact replay receipt").isVisible(),rows:await page.locator("tbody tr").allTextContents(),replay:JSON.parse(await page.getByLabel("Exact replay receipt").textContent()),focused:await full.evaluate(e=>document.activeElement===e)};
    });
    await verify(width,"no-horizontal-overflow",async()=>{
      const geometry=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,innerWidth:window.innerWidth}));
      assert.ok(geometry.scrollWidth<=geometry.innerWidth+1); return geometry;
    });
    await verify(width,"edit-invalidates-and-fractional-tail",async()=>{
      await field("Confidence (0 < α < 1)").fill("0.85"); await expect(results).toHaveCount(0);
      await calculate(); await expect(results.locator("dd").nth(1)).toHaveText("8.000000000000000000"); return {display:await displays()};
    });
    await verify(width,"sparse-tail-unavailable",async()=>{
      await field("Confidence (0 < α < 1)").fill("0.95"); await calculate();
      await expect(results.locator("dd").nth(1)).toHaveText("Unavailable: less than one observation of tail mass"); return {display:await displays()};
    });
    await verify(width,"signed-short-exposure",async()=>{
      await fill(); await field("Signed exposures").fill("long -100"); await calculate();
      await expect(results.locator("dd").nth(0)).toHaveText(receipts[10].result.var.exact.display); return {expected:receipts[10].result.var.exact.display,display:await displays()};
    });
    await verify(width,"overlapping-horizon",async()=>{
      await fill(); await field("Horizon (supplied intervals)").fill("2"); await field("Confidence (0 < α < 1)").fill("0.5"); await calculate();
      await expect(results).toContainText("Overlapping windows share 1 intervals"); await expect(results.locator("dd").nth(0)).toHaveText(receipts[3].result.var.exact.display);
      return {expected:receipts[3].result.var.exact.display,display:await displays(),overlap:await results.locator("p").nth(1).textContent()};
    });
    await verify(width,"malformed-response-rejected",async()=>{
      await fill(); mode="malformed"; await calculate(); await expect(page.locator("main").getByRole("alert")).toContainText("could not be verified"); await expect(results).toHaveCount(0);
      return {alert:await page.locator("main").getByRole("alert").textContent(),resultCount:await results.count()};
    });
    await verify(width,"server-error",async()=>{
      mode="failure"; await calculate(); await expect(page.locator("main").getByRole("alert")).toContainText("Calculation rejected");
      return {alert:await page.locator("main").getByRole("alert").textContent()};
    });
    for(const kind of ["cancel","edit"]) await verify(width,`ignored-abort-${kind}`,async()=>{
      mode="hold"; const before=await page.evaluate(()=>window.riskDeliveries.length);
      await calculate(); await expect.poll(()=>Boolean(pending)).toBe(true);
      if(kind==="cancel") await page.getByRole("button",{name:"Cancel calculation",exact:true}).click();
      else await field("Confidence (0 < α < 1)").fill("0.85");
      pending(); pending=undefined;
      await expect.poll(()=>page.evaluate(()=>window.riskDeliveries.length)).toBe(before+1);
      const delivery=await page.evaluate(()=>window.riskDeliveries.at(-1)); assert.equal(delivery.aborted,true);
      await expect(results).toHaveCount(0); await expect(page.locator('main > p[role="status"]')).toContainText(kind==="cancel" ? "cancelled" : "Inputs changed");
      return {delivery,resultCount:await results.count(),status:await page.locator('main > p[role="status"]').textContent()};
    });
    await verify(width,"explicit-retry",async()=>{
      mode="normal"; await calculate(); await expect(results.locator("dd").nth(1)).toHaveText("8.000000000000000000"); return {display:await displays()};
    });
    await verify(width,"missing-observation-rejected-before-request",async()=>{
      const before=await page.evaluate(()=>window.riskDeliveries.length);
      await field("Exact gross-return factors").fill("s0 2026-01-01 2026-01-02"); await calculate();
      await expect(page.locator("main").getByRole("alert")).toContainText("Missing observations");
      const after=await page.evaluate(()=>window.riskDeliveries.length); assert.equal(after,before);
      return {alert:await page.locator("main").getByRole("alert").textContent(),deliveriesBefore:before,deliveriesAfter:after};
    });
    await verify(width,"network-and-page-integrity",async()=>{assert.deepEqual(violations,[]); assert.deepEqual(errors,[]);return {violations,errors};});
    await context.close(); record("viewport_completed",{width});
  }
  record("run_passed",{defaultOffPage:404,syntheticPythonReceipts:receipts.length,browser:await browser.version(),widths:[1440,390]});
  console.log(JSON.stringify({status:"PASS",ledger,runId},null,2));
} catch(error) {
  record("run_failed",{error:errorInfo(error)}); console.error(`Browser execution ledger: ${ledger}`); throw error;
} finally {
  try {await browser?.close();} finally {record("run_finished");}
}
