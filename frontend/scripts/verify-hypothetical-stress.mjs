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
const base=process.env.FINLENS_STRESS_BROWSER_URL || "http://127.0.0.1:3139";
const disabled=process.env.FINLENS_STRESS_DISABLED_URL || "http://127.0.0.1:3138";
const runId=randomUUID(), started=performance.now();
const ledger=resolve(process.env.FINLENS_STRESS_LEDGER_PATH || join(frontend,"test-results",`stress-browser-${runId}.jsonl`));
mkdirSync(dirname(ledger),{recursive:true});
writeFileSync(ledger,"",{flag:"wx"}); // Never overwrite earlier run evidence.
let sequence=0, browser, requestId=0;
const hash=body=>createHash("sha256").update(body).digest("hex");
const errorInfo=error=>({name:error?.name || "Error",message:error?.message || String(error),stack:error?.stack});
function record(event, data={}) {
  appendFileSync(ledger,JSON.stringify({schema:"finlens-stress-browser-ledger-v1",runId,sequence:++sequence,
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
  record("run_started",{base,disabled,channel:process.env.FINLENS_STRESS_BROWSER_CHANNEL || "bundled-chromium",ledger});
  for (const url of [base,disabled]) assert.ok(/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(url),"Loopback origins only");
  const sourcePaths=["backend/app/hypothetical_stress.py","backend/app/hypothetical_risk_route.py","backend/tests/test_hypothetical_stress.py","frontend/app/hypothetical-risk/page.tsx","frontend/app/hypothetical-risk/stress/page.tsx","frontend/components/hypothetical-stress.tsx","frontend/lib/hypothetical-stress.ts","frontend/lib/hypothetical-risk.ts","frontend/scripts/verify-hypothetical-stress.mjs"];
  record("source_hashes",{sha256:Object.fromEntries(sourcePaths.map(path=>[path,hash(readFileSync(resolve(frontend,"..",path)))]))});
  const temp=mkdtempSync(join(tmpdir(),"finlens-stress-browser-")), output=join(temp,"responses.json");
  let receipts;
  try {
    const python=join(backend,".venv",...(process.platform === "win32" ? ["Scripts","python.exe"] : ["bin","python"]));
    const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>["systemroot","windir","path","temp","tmp","tmpdir","pathext","comspec","number_of_processors"].includes(key.toLowerCase())));
    const args=["-I","-S","-B","tests/run_financial_insights.py","tests/test_hypothetical_stress.py"];
    const run=spawnSync(python,args,{cwd:backend,env:{...env,FINLENS_STRESS_CONTRACT_OUTPUT:output},encoding:"utf8",timeout:60000,windowsHide:true});
    record("python_capture",{python,args,status:run.status,stdout:run.stdout,stderr:run.stderr,error:run.error ? errorInfo(run.error) : null});
    assert.equal(run.status,0,`${run.stdout}\n${run.stderr}`);
    const body=readFileSync(output); receipts=JSON.parse(body.toString("utf8"));
    record("python_receipts",{sha256:hash(body),count:receipts.length,receipts});
  } finally {if(existsSync(output)) unlinkSync(output); rmdirSync(temp);}
  browser=await chromium.launch({headless:true,...(process.env.FINLENS_STRESS_BROWSER_CHANNEL ? {channel:process.env.FINLENS_STRESS_BROWSER_CHANNEL} : {})});
  record("browser_started",{version:await browser.version()});
  const off=await browser.newContext({serviceWorkers:"block"}), offViolations=[], offErrors=[];
  const offTrace=trace(off,null,disabled,offViolations,offErrors), offPage=await off.newPage();
  await off.route("**/*",route=>new URL(route.request().url()).origin===disabled ? route.continue() : offTrace.deny(route,"Unexpected disabled-page origin"));
  await verify(null,"disabled-page",async()=>{
    const status=(await offPage.goto(`${disabled}/hypothetical-risk/stress`)).status(); assert.equal(status,404);
    assert.deepEqual(offViolations,[]); assert.deepEqual(offErrors,[]); return {status,violations:offViolations,errors:offErrors};
  });
  await off.close();
  const canonical=value=>Array.isArray(value)?`[${value.map(canonical).join(",")}]`:value&&typeof value==="object"?`{${Object.entries(value).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([key,v])=>`${JSON.stringify(key)}:${canonical(v)}`).join(",")}}`:JSON.stringify(value);
  for(const width of [1440,390]) {
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:"block"});
    const violations=[],errors=[],observed=trace(context,width,base,violations,errors),page=await context.newPage();
    let mode="normal",pending,apiCount=0;
    record("viewport_started",{width,height:900});
    await context.addInitScript(()=>{
      const native=window.fetch.bind(window);window.stressDeliveries=[];let id=0;
      window.fetch=async(input,init)=>{
        if(typeof input!=="string"||!input.endsWith("/hypothetical-stress"))return native(input,init);
        const deliveryId=++id,response=await native(input,{...init,signal:null});
        window.stressDeliveries.push({id:deliveryId,aborted:init.signal.aborted,inputs:JSON.parse(init.body),status:response.status});return response;
      };
    });
    await context.route("**/*",async route=>{
      const url=new URL(route.request().url());
      if(url.origin!==base)return observed.deny(route,`Unexpected origin: ${url.origin}`);
      if(!url.pathname.startsWith("/api/finlens/"))return route.continue();
      if(url.pathname!=="/api/finlens/hypothetical-stress")return observed.deny(route,`Unexpected API: ${url.pathname}`);
      apiCount++;
      const inputs=route.request().postDataJSON(),selected=mode,fixtureIndex=receipts.findIndex(r=>canonical(r.inputs)===canonical(inputs));
      if(selected==="hold"){record("api_held",{width,id:observed.id(route.request()),inputs});await new Promise(resolve=>{pending=resolve;});}
      if(!["failure","busy","malformed"].includes(selected))assert.ok(fixtureIndex>=0,"Unknown synthetic browser inputs");
      const status=selected==="failure"?422:selected==="busy"?429:200;
      const body=selected==="malformed"?{schema_id:"wrong"}:selected==="failure"?{detail:"unsupported_shock_percent"}:selected==="busy"?{detail:"candidate_busy_retry_explicitly"}:receipts[fixtureIndex];
      record("api_reply",{width,id:observed.id(route.request()),mode:selected,fixtureIndex,status,body,syntheticError:["failure","busy"].includes(selected)});
      await route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
    });
    await verify(width,"keyboard-workflow-navigation",async()=>{
      await page.goto(`${base}/hypothetical-risk`);
      const link=page.getByRole("link",{name:"Hypothetical linear price stress",exact:true});await link.focus();await page.keyboard.press("Enter");
      await expect(page).toHaveURL(`${base}/hypothetical-risk/stress`);await expect(page.getByRole("heading",{name:"Hypothetical linear price stress",exact:true})).toBeVisible();
      return {url:page.url(),backLink:await page.getByRole("link",{name:"Historical hypothetical risk",exact:true}).getAttribute("href")};
    });
    const field=name=>page.getByLabel(name,{exact:true}),results=page.getByRole("region",{name:"Conditional stress results",exact:true});
    const calculate=()=>page.getByRole("button",{name:"Calculate hypothetical stress",exact:true}).click();
    const fill=async(receipt=receipts[0])=>{
      const input=receipt.inputs;
      await field("Reporting currency").fill(input.reporting_currency);await field("Exposure date").fill(input.exposure_date);
      await field("Signed exposures").fill(input.exposures.map(e=>`${e.asset_id} ${e.amount}`).join("\n"));
      await field("Named scenario shocks (%)").fill(input.scenarios.map(s=>`${s.scenario_id} ${input.exposures.map(e=>s.shocks[e.asset_id]).join(" ")}`).join("\n"));
      await field("Common shock sensitivity (%)").fill(input.common_shocks.join(" "));
    };
    const audit=()=>page.getByRole("region",{name:"Contribution audit decline",exact:true});
    await fill();
    await verify(width,"exact-signed-contributions-and-explicit-zero",async()=>{
      await calculate();await expect(results).toBeVisible();await expect(audit().locator("tfoot td").nth(0)).toHaveText("-12.500000000000000000");
      await expect(audit().locator("tfoot td").nth(1)).toHaveText("12.500000000000000000");await expect(audit().locator("tbody tr")).toHaveCount(3);
      return {rows:await audit().locator("tbody tr").allTextContents(),totals:await audit().locator("tfoot td").allTextContents(),zero:await audit().locator("tbody tr").nth(2).textContent()};
    });
    if(process.env.FINLENS_STRESS_SCREENSHOT_DIR){const path=join(process.env.FINLENS_STRESS_SCREENSHOT_DIR,`stress-${width}.png`);await page.screenshot({path,fullPage:true});record("screenshot",{width,path,sha256:hash(readFileSync(path))});}
    await verify(width,"common-shock-sensitivity-and-keyboard-table-scroll",async()=>{
      const table=page.getByRole("region",{name:"Common shock totals",exact:true});await expect(table.locator("tbody tr")).toHaveCount(3);
      await expect(table.locator("tbody tr").nth(0).locator("td").nth(0)).toHaveText("-50.000000000000000000");
      await expect(results).toContainText("Each +1 percentage point common shock changes P&L by 0.500000000000000000 USD");
      const geometry=await table.evaluate(e=>({width:e.clientWidth,scrollWidth:e.scrollWidth}));await table.focus();
      if(width===390){assert.ok(geometry.scrollWidth>geometry.width);await page.keyboard.press("ArrowRight");await expect.poll(()=>table.evaluate(e=>e.scrollLeft)).toBeGreaterThan(0);}
      return {rows:await table.locator("tbody tr").allTextContents(),geometry,scrollLeft:await table.evaluate(e=>e.scrollLeft),focused:await table.evaluate(e=>document.activeElement===e)};
    });
    await verify(width,"keyboard-full-audits-and-replay",async()=>{
      const common=page.getByText("Common-shock contribution audits",{exact:true});await common.focus();await page.keyboard.press("Enter");await expect(common.locator("..")).toHaveAttribute("open","");
      const receipt=page.getByText("Exact stress replay receipt",{exact:true});await receipt.focus();await page.keyboard.press("Enter");await expect(receipt.locator("..")).toHaveAttribute("open","");
      const pre=page.getByLabel("Exact stress receipt",{exact:true});await expect(pre).toBeVisible();
      const body=JSON.parse(await pre.textContent());assert.deepEqual(body,receipts[0]);
      return {commonOpen:await common.locator("..").evaluate(e=>e.open),replayOpen:await receipt.locator("..").evaluate(e=>e.open),visible:await pre.isVisible(),receipt:body};
    });
    await verify(width,"no-page-horizontal-overflow",async()=>{
      const size=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,innerWidth:window.innerWidth}));assert.ok(size.scrollWidth<=size.innerWidth+1);return size;
    });
    for(const index of [1,2,3,5,6,8])await verify(width,`signed-zero-decimal-boundary-${index}`,async()=>{
      await fill(receipts[index]);await expect(results).toHaveCount(0);await calculate();
      const expected=receipts[index].result.scenarios[0].total_pnl.display;await expect(audit().locator("tfoot td").nth(0)).toHaveText(expected);
      return {inputs:receipts[index].inputs,expected,totals:await audit().locator("tfoot td").allTextContents()};
    });
    await verify(width,"below-minus-100-rejected",async()=>{
      await fill();await field("Named scenario shocks (%)").fill("decline -101 5 0\nunchanged 0 0 0");mode="failure";await calculate();
      await expect(page.locator("main").getByRole("alert")).toContainText("-100 to 1000 percent");await expect(results).toHaveCount(0);
      return {alert:await page.locator("main").getByRole("alert").textContent(),resultCount:await results.count()};
    });
    await verify(width,"malformed-response-clears-results",async()=>{
      await fill();mode="malformed";await calculate();await expect(page.locator("main").getByRole("alert")).toContainText("could not be verified");await expect(results).toHaveCount(0);
      return {alert:await page.locator("main").getByRole("alert").textContent(),resultCount:await results.count()};
    });
    await verify(width,"busy-state-is-explicit",async()=>{
      mode="busy";await calculate();await expect(page.locator("main").getByRole("alert")).toContainText("already running");return {alert:await page.locator("main").getByRole("alert").textContent()};
    });
    for(const kind of ["cancel","edit"])await verify(width,`ignored-abort-${kind}`,async()=>{
      mode="hold";const before=await page.evaluate(()=>window.stressDeliveries.length);await calculate();await expect.poll(()=>Boolean(pending)).toBe(true);
      if(kind==="cancel")await page.getByRole("button",{name:"Cancel calculation",exact:true}).click();else await field("Signed exposures").fill("long -100\nshort -50\nzero 0");
      pending();pending=undefined;await expect.poll(()=>page.evaluate(()=>window.stressDeliveries.length)).toBe(before+1);
      const delivery=await page.evaluate(()=>window.stressDeliveries.at(-1));assert.equal(delivery.aborted,true);await expect(results).toHaveCount(0);
      await expect(page.getByRole("status")).toContainText(kind==="cancel"?"cancelled":"Inputs changed");return {delivery,resultCount:await results.count(),status:await page.getByRole("status").textContent()};
    });
    await verify(width,"explicit-retry-new-signed-result",async()=>{
      mode="normal";await calculate();await expect(audit().locator("tfoot td").nth(0)).toHaveText(receipts[1].result.scenarios[0].total_pnl.display);
      return {totals:await audit().locator("tfoot td").allTextContents()};
    });
    await verify(width,"missing-shock-never-becomes-zero",async()=>{
      const before=apiCount;await field("Named scenario shocks (%)").fill("missing -10 5");await calculate();await expect(page.locator("main").getByRole("alert")).toContainText("Missing shocks are not zero");assert.equal(apiCount,before);await expect(results).toHaveCount(0);
      return {requestsBefore:before,requestsAfter:apiCount,alert:await page.locator("main").getByRole("alert").textContent()};
    });
    await verify(width,"network-and-page-integrity",async()=>{assert.deepEqual(violations,[]);assert.deepEqual(errors,[]);return {violations,errors};});
    await context.close();record("viewport_completed",{width});
  }
  record("run_passed",{defaultOffPage:404,syntheticPythonReceipts:receipts.length,browser:await browser.version(),widths:[1440,390]});
  console.log(JSON.stringify({status:"PASS",ledger,runId},null,2));
}catch(error){record("run_failed",{error:errorInfo(error)});console.error(`Browser execution ledger: ${ledger}`);throw error;}
finally{try{await browser?.close();}finally{record("run_finished");}}
