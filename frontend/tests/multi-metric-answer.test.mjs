import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL, fileURLToPath } from "node:url";
const primary = process.env.FINLENS_TEST_FRONTEND ?? fileURLToPath(new URL("..", import.meta.url));
const require = createRequire(`${primary}/package.json`);
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { componentLoader } = await import(pathToFileURL(`${primary}/tests/component-loader.mjs`));
const render = componentLoader(primary)(fileURLToPath(new URL("../components/research-answer.tsx", import.meta.url))).default;
const accession="0000000001-25-000001";
const source=(metric,period) => ({ fact_id:1, canonical_metric:metric, original_concept:metric, value:"100", unit:"USD", period_start:period.start,period_end:period.end,form:"10-K",filed:"2026-02-01",accession_number:accession,sec_url:`https://www.sec.gov/Archives/edgar/data/1/000000000125000001/${accession}-index.html`,company_cik:"0000000001",source_fiscal_year:2026,source_fiscal_period:"FY" });
const point = (metric, present) => {const period=present ? {kind:"annual",start:"2024-01-01",end:"2024-12-31",fiscal_year:2024,fiscal_period:"FY"} : null;return { metric, status: present ? "available" : "unavailable", value: present ? "100" : null, unit:"USD", period, reason:present ? null : "No matching fact", inputs:[], provenance:present ? [source(metric,period)] : [], alternatives:[], formula:null, revenue_basis:null };};
const question="revenue and net income for FY2024";
const item = (metric, label, present) => ({ metric, metric_label:label, question, matched:true, ticker:"TEST", answer_kind:"historical_metric", status:present ? "available" : "unavailable", formatted_value:present ? "$100.00" : null, answer_text:present ? "Synthetic available" : "No matching fact", requested_period:{fiscal_year:2024,quarter:null}, observation:point(metric,present),comparability:null });
const multi = { matched:true, ticker:"TEST", question, company_cik:"0000000001", requested_period:{fiscal_year:2024,quarter:null}, window_status:"unverified", answer_kind:"multi_metric", metrics:[item("revenue","Revenue",true),item("net_income","Net income",false)] };
test("renders separate fiscal values, unavailable explanation and provenance controls", () => {
  const html=renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer:multi}));
  assert.match(html,/Revenue/); assert.match(html,/Net income/); assert.match(html,/100 USD/); assert.match(html,/Unavailable/);
  assert.match(html,/No matching fact/); assert.match(html,/Revenue sources and details/); assert.match(html,/Net income sources and details/);
  assert.ok((html.match(/FY2024/g) || []).length >= 2);
});
test("replacement renders only new company data and malformed multi fails closed", () => {
  const replacement={...multi,metrics:[item("gross_profit","Gross profit",false),item("total_assets","Total assets",false)]};
  const html=renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer:replacement}));
  assert.match(html,/Gross profit/);assert.doesNotMatch(html,/Revenue|Net income|\$100/);
  assert.equal(renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer:{...multi,metrics:[]}})),"");
});


test("discloses actual dates, revenue basis, incompatibility and rejects bad binding", () => {
 const revenue=item("revenue","Revenue",true); revenue.observation.period={kind:"annual",start:"2023-07-01",end:"2024-06-30",fiscal_year:2024,fiscal_period:"FY"}; revenue.observation.revenue_basis="customer_contract"; revenue.observation.provenance=[source("revenue",revenue.observation.period)];
 const income=item("net_income","Net income",true); income.observation.period={kind:"annual",start:"2024-01-01",end:"2024-12-31",fiscal_year:2024,fiscal_period:"FY"}; income.observation.provenance=[source("net_income",income.observation.period)];
 const answer={...multi,window_status:"incompatible",metrics:[revenue,income]}; const html=renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer}));
 assert.match(html,/Reporting windows differ/);assert.match(html,/customer contract/);assert.match(html,/2023/);assert.match(html,/2024/);
 assert.equal(renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer:{...answer,metrics:[revenue,{...income,ticker:"OTHER"}]}})),"");
});

test("malformed metrics and foreign provenance fail closed; comparative filing year is allowed", () => {
 const revenue=item("revenue","Revenue",true), income=item("net_income","Net income",false);
 const src=source("revenue",revenue.observation.period);
 revenue.observation.provenance=[src];
 const show=answer=>renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer}));
 assert.match(show({...multi,metrics:[revenue,income]}),/Revenue sources/);
 for (const metrics of [null,{},[null,income],[revenue,null],[{...revenue,observation:{...revenue.observation,period:{...revenue.observation.period,fiscal_year:2023}}},income],[{...revenue,observation:{...revenue.observation,provenance:[{...src,company_cik:"0000000002"}]}},income],[{...revenue,observation:{...revenue.observation,alternatives:[{...src,company_cik:"0000000002"}]}},income],[{...revenue,observation:{...revenue.observation,period:{...revenue.observation.period,end:"2023-12-31"}}},income],[{...revenue,observation:{...revenue.observation,provenance:null}},income]]) {
  assert.equal(show({...multi,metrics}),"");
 }
});

test("selected company must match the response CIK", () => {
 assert.equal(renderToStaticMarkup(React.createElement(render,{companyCik:"0000000002",answer:multi})),"");
});

test("instant observations with an unlabeled year remain supported", () => {
 const instant=item("total_assets","Total assets",true); instant.observation.period={kind:"instant",start:null,end:"2024-12-31",fiscal_year:null,fiscal_period:null}; instant.observation.provenance=[source("total_assets",instant.observation.period)];
 assert.match(renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer:{...multi,metrics:[instant,item("revenue","Revenue",true)]}})),/Total assets/);
});

test("rejects mismatched selected source and nested objects", () => {
 const revenue=item("revenue","Revenue",true), income=item("net_income","Net income",false), src=revenue.observation.provenance[0];
 const show=answer=>renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer}));
 for (const change of [{canonical_metric:"net_income"},{value:"101"},{period_end:"2023-12-31"},{period_start:"2023-01-01"},{sec_url:"https://www.sec.gov/Archives/edgar/data/2/000000000125000001/0000000001-25-000001-index.html"},{form:{}},{fact_id:{} }]) {
  assert.equal(show({...multi,metrics:[{...revenue,observation:{...revenue.observation,provenance:[{...src,...change}]}},income]}),"");
 }
 for (const change of [{value:{}},{unit:{}},{formula:{} }]) assert.equal(show({...multi,metrics:[{...revenue,observation:{...revenue.observation,...change}},income]}),"");
 assert.equal(show({...multi,metrics:[{...revenue,question:"different"},income]}),"");
});

test("unbound display text cannot override exact observation", () => {
 const revenue={...item("revenue","Revenue",true),formatted_value:"$999",answer_text:"fabricated"};
 const html=renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer:{...multi,metrics:[revenue,item("net_income","Net income",false)]}}));
 assert.match(html,/100 USD/); assert.doesNotMatch(html,/999|fabricated/);
});

test("rejects malformed nullable fiscal labels before shared formatting", () => {
 const income=item("net_income","Net income",false);
 const show=answer=>renderToStaticMarkup(React.createElement(render,{companyCik:"0000000001",answer}));
 for (const fiscal_period of [{},[],42,true]) { const revenue=item("revenue","Revenue",true);revenue.observation.period.fiscal_period=fiscal_period;assert.equal(show({...multi,metrics:[revenue,income]}),""); }
 const valid=item("revenue","Revenue",true);valid.observation.period.fiscal_period=null;assert.match(show({...multi,metrics:[valid,income]}),/Revenue/);
});
