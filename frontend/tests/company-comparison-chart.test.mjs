import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
const primary = process.env.FINLENS_TEST_FRONTEND ?? fileURLToPath(new URL("..", import.meta.url));
const require = createRequire(`${primary}/package.json`), React = require("react"), { JSDOM } = require("jsdom");
const { componentLoader } = await import(pathToFileURL(`${primary}/tests/component-loader.mjs`));
const loaded=componentLoader(primary)(fileURLToPath(new URL("../components/company-comparison-chart.tsx",import.meta.url)));
const {companyChartProjection:project, default:Chart}=loaded;
const point=(value, options={})=>({metric:"revenue",status:value===null?"unavailable":"available",value,unit:options.unit??"USD",reason:value===null?"Synthetic missing":null,period:{kind:"annual",start:options.start??"2024-01-01",end:"2024-12-31",fiscal_year:2024,fiscal_period:"FY"},inputs:[],revenue_basis:options.basis===undefined?"total_revenue":options.basis});
const col=(ticker,value,options={})=>({company:{ticker,cik:ticker},result:{period:point(value,options).period,metrics:{revenue:point(value,options)}}});
const absent=ticker=>({company:{ticker,cik:ticker},error:"Synthetic unavailable"});
test("negative, zero and unavailable observations retain selection order",()=>{
 const p=project("revenue",[col("BBB","-10"),col("AAA","0"),col("CCC","20")]);
 assert.equal(p.reason,null);assert.deepEqual(p.rows.map(r=>r.column.company.ticker),["BBB","AAA","CCC"]);assert.deepEqual(p.rows.map(r=>r.value),[-10,0,20]);
 const q=project("revenue",[col("BBB","-10"),col("AAA",null)]);assert.equal(q.rows[1].value,null);assert.equal(q.diagnostics.excluded,1);
});
test("different dates, units, bases and unknown basis never share an axis",()=>{
 assert.match(project("revenue",[col("A","1"),col("B","2",{start:"2023-12-31"})]).reason,/windows differ/);
 assert.match(project("revenue",[col("A","1"),col("B","2",{unit:"EUR"})]).reason,/Units differ/);
 assert.match(project("revenue",[col("A","1"),col("B","2",{basis:"net_sales"})]).reason,/bases differ/);
 assert.match(project("revenue",[col("A","1"),col("B","2",{basis:null})]).reason,/basis is unknown/);
 assert.match(project("revenue",[col("A","1"),absent("B")]).reason,/basis is unknown/);
});
test("unsafe floating conversion and empty data are explicit",()=>{
 for(const value of ["9007199254740993","1e-400","1e400"]) assert.match(project("revenue",[col("A",value),col("B","1")]).reason,/cannot be plotted safely/);
 assert.match(project("revenue",[col("A",null),col("B",null)]).reason,/No available/);
 assert.equal(project("revenue",[col("A","0.10"),col("B","1e3")]).reason,null);
});
test("optional, labelled chart works in a narrow scrolling region without fetching",async()=>{
 const dom=new JSDOM("<!doctype html><html><body></body></html>",{url:"http://finlens.test"});
 const old={};for(const key of ["window","document","HTMLElement","Node","Event"]){old[key]=Object.getOwnPropertyDescriptor(globalThis,key);Object.defineProperty(globalThis,key,{configurable:true,value:dom.window[key]});}
 const previousFetch=globalThis.fetch;globalThis.fetch=()=>{throw Error("network forbidden")};globalThis.IS_REACT_ACT_ENVIRONMENT=true;
 let restores=0; const {createRoot}=require("react-dom/client");const host=document.createElement("div");host.style.width="240px";document.body.append(host);const root=createRoot(host);
 try {await React.act(async()=>root.render(React.createElement(Chart,{key:"request-A",onShowAll:()=>{restores++},columns:[col("B","-10"),col("A","0"),col("C","20")]})));
 assert.equal(host.querySelector("details").open,false);assert.equal(host.querySelector("svg"),null);
 const restore=[...host.querySelectorAll("button")].find(button=>button.textContent==="Show all metric rows and sources");assert.ok(restore);await React.act(async()=>restore.click());assert.equal(restores,1);
 const select=host.querySelector("select");assert.ok(host.querySelector(`label[for="${select.id}"]`));
 await React.act(async()=>{select.value="revenue";select.dispatchEvent(new dom.window.Event("change",{bubbles:true}));});
 const region=host.querySelector('[role="region"]'),svg=region.querySelector("svg");assert.equal(region.style.overflowX,"auto");assert.equal(svg.style.minWidth,"440px");assert.equal(svg.getAttribute("role"),"img");
 assert.deepEqual([...svg.querySelectorAll("text")].map(x=>x.textContent),["B","A","C"]);assert.equal(svg.querySelectorAll("circle").length,3);
 assert.match(host.textContent,/no zero baseline/);assert.match(host.textContent,/2024/);
 await React.act(async()=>root.render(React.createElement(Chart,{key:"request-B",columns:[col("A","1"),col("D","2")]})));
 assert.equal(host.querySelector("select").value,"");assert.equal(host.querySelector("svg"),null);assert.equal(host.querySelector("details").open,false);
 }finally{await React.act(async()=>root.unmount());dom.window.close();globalThis.fetch=previousFetch;for(const key in old){if(old[key])Object.defineProperty(globalThis,key,old[key]);else delete globalThis[key];}}
});

test("close large values fail closed, while identical and well-separated values remain usable",()=>{
 const p=project("revenue",[col("A","1000000000000000000"),col("B","1000000000000000100"),col("C","1000000000000000300")]);
 assert.match(p.reason,/too small to plot reliably/);
 assert.equal(project("revenue",[col("A","1000000000000000000"),col("B","1000000000000000000")]).reason,null);
 assert.equal(project("revenue",[col("A","-100"),col("B","0"),col("C","100")]).reason,null);
});
