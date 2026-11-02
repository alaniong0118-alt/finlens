import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { componentLoader } from "./component-loader.mjs";
const frontend = fileURLToPath(new URL("../", import.meta.url)), load = componentLoader(frontend);
const { CASH_FLOW_METRICS: metrics, validateCashFlowHistory: validate, cashFlowWindows, cashFlowCell, validCashFlowWindows, checkCashFlowSources } = load(frontend + "/lib/cash-flow-window-comparison.ts");
const Comparison = load(frontend + "/components/cash-flow-window-comparison.tsx").default;
const Freshness = load(frontend + "/components/research-freshness.tsx").default;
let dom, createRoot; const previous = new Map();
before(async () => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://finlens.test", pretendToBeVisual: true });
  for (const name of ["window", "document", "HTMLElement", "Node", "Event", "MouseEvent"]) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name)); Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] });
  }
  previous.set("IS_REACT_ACT_ENVIRONMENT", Object.getOwnPropertyDescriptor(globalThis, "IS_REACT_ACT_ENVIRONMENT")); globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import("react-dom/client"));
});
after(() => { dom?.window.close(); for (const [name, descriptor] of previous) descriptor ? Object.defineProperty(globalThis, name, descriptor) : delete globalThis[name]; });
// All values, issuers and SEC-shaped URLs are synthetic.
const company = { id: 1, ticker: "AAA", cik: "0000000001", name: "Synthetic issuer", exchange: "TEST", has_indexed_filing: false, indexed_filing_count: 0 };
const exact = "9007199254740993.1234567890123456789012345";
const windows = [2025, 2024, 2023, 2022, 2021].map(year => ({ start: `${year}-01-01`, end: `${year}-06-30` }));
function history(metric, selected = windows, kind = "half_year") {
  const accession = "0000000001-26-000001";
  const source = (name, w, index) => ({ fact_id: (name === metrics[0] ? 1 : 101) + index, canonical_metric: name, company_cik: company.cik,
    original_concept: `Synthetic_${name}`, value: name === metrics[0] ? exact : "10.0001", unit: "USD", period_start: w.start, period_end: w.end,
    form: "10-Q", filed: "2026-07-31", accession_number: accession, sec_url: `https://www.sec.gov/Archives/edgar/data/1/${accession.replaceAll("-", "")}/index.html`, source_fiscal_year: 2025, source_fiscal_period: "Q2" });
  return { ticker: company.ticker, company_cik: company.cik, metric, unit: "USD", requested_period: kind,
    status: selected.length ? "available" : "unavailable", reason: selected.length ? null : "No compatible stored SEC observations or inputs.",
    history: selected.map(w => {
      const index = windows.findIndex(x => x.start === w.start), p = { kind, ...w, fiscal_year: null, fiscal_period: null, fiscal_label_basis: "unknown" };
      const derived = metric === metrics[2], sources = derived ? [source(metrics[0], w, index), source(metrics[1], w, index)] : [source(metric, w, index)];
      return { metric, unit: "USD", status: "available", value: derived ? "9007199254740983.123356789012" : sources[0].value, reason: null,
        formula: derived ? "operating_cash_flow - capital_expenditures" : null, period: p, provenance: sources, alternatives: [],
        inputs: derived ? sources.map(s => ({ role: s.canonical_metric, metric: s.canonical_metric, value: s.value, unit: "USD", period: p, fact_ids: [s.fact_id] })) : [] };
    }) };
}
const valid = (metric, selected = windows, kind = "half_year") => validate(history(metric, selected, kind), company, metric, kind);
function freshness(pin) { const stream = { status: "unknown", last_checked_at: null, last_successful_sync_at: null, latest_source_filing_date: null, last_error: null, failure_stage: null, pending_targets: [], inventory_complete: false }; return { ticker: company.ticker, data_version: pin, facts_version: pin, evidence_version: 0, status: "unknown", facts: stream, evidence: stream, latest_indexed_filing: null, migration_required: false, scope: "Synthetic." }; }
async function mount(ctx) {
  const requests = [], unexpected = [];
  ctx.mock.method(globalThis, "fetch", (path, init) => {
    const url = new URL(String(path), "http://finlens.test");
    if (!/^\/api\/finlens\/companies\/AAA\/(freshness|financials\/metrics\/(operating_cash_flow|capital_expenditures|free_cash_flow))$/.test(url.pathname)) unexpected.push(String(path));
    let resolve; const promise = new Promise(yes => { resolve = yes; }); requests.push({ url, init, resolve, released: false }); return promise;
  });
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
  await act(async () => root.render(React.createElement(Freshness, { ticker: company.ticker, catalogChanged: async () => true }, React.createElement(Comparison, { company }))));
  ctx.after(async () => { await act(async () => root.unmount()); host.remove(); assert.deepEqual(unexpected, []); });
  const all = () => requests.filter(r => r.url.pathname.includes("/metrics/"));
  const pending = () => all().filter(r => !r.released && !r.init.signal.aborted);
  async function release(r, body, pin = 0, status = 200, header = true) { assert.ok(r && !r.released); r.released = true; await act(async () => r.resolve(new Response(JSON.stringify(body), { status, headers: header ? { "X-FinLens-Data-Version": String(pin) } : {} }))); }
  async function verify(pin = 0) { await release(requests.filter(r => r.url.pathname.endsWith("/freshness") && !r.released && !r.init.signal.aborted).at(-1), freshness(pin), pin); }
  async function click(name) { const b = [...host.querySelectorAll("button")].find(b => b.textContent === name); assert.ok(b && !b.disabled, name); await act(async () => b.click()); }
  async function choose(w) { const l = [...host.querySelectorAll("label")].find(l => l.querySelectorAll("time").length === 2 && l.querySelector("time").dateTime === w.start); assert.ok(l); const input = l.querySelector("input"); assert.equal(input.disabled, false); await act(async () => input.click()); return input; }
  async function settle(batch = pending(), pin = 0) { for (const r of batch) await release(r, history(r.url.pathname.split("/").at(-1)), pin); }
  return { host, requests, all, pending, release, verify, click, choose, settle };
}

test("exact windows align without substitution and preserve decimals and FCF operand lineage", () => {
  const series = metrics.map(metric => ({ metric, data: valid(metric), error: null }));
  assert.deepEqual(cashFlowWindows(series), windows); assert.deepEqual(checkCashFlowSources(series), series);
  assert.equal(cashFlowCell(series[0], windows[0]).point.value, exact);
  assert.equal(cashFlowCell(series[0], { start: "2025-01-02", end: windows[0].end }).kind, "absent");
  assert.equal(cashFlowCell({ metric: metrics[0], data: null, error: "failed" }, windows[0]).kind, "error");
  assert.ok(validCashFlowWindows(windows.slice(0, 2), windows)); assert.ok(validCashFlowWindows(windows.slice(0, 4), windows));
  for (const selected of [[], windows.slice(0, 1), windows, [windows[0], windows[0]]]) assert.equal(validCashFlowWindows(selected, windows), false);
  assert.equal(series[2].data.history[0].inputs[0].value, exact);
});
test("invalid identities, periods, units, duplicates and FCF operand sources fail closed", () => {
  const mutations = [b => b.company_cik = "0000000002", b => b.unit = "EUR", b => b.requested_period = "quarter",
    b => b.history.push(structuredClone(b.history[0])), b => b.history[0].period.start = "2025-01-02",
    b => b.history[0].provenance[0].period_start = "2025-01-02", b => b.history[0].provenance[0].sec_url = "https://evil.test/x",
    b => b.history[0].inputs[0].value = "12", b => b.history[0].inputs[0].unit = "EUR", b => b.history[0].inputs[0].fact_ids = [500]];
  for (const mutate of mutations) { const b = history(metrics[2]); mutate(b); assert.throws(() => validate(b, company, metrics[2], "half_year"), { code: "INVALID_RESPONSE" }); }
  const series = metrics.map(metric => ({ metric, data: valid(metric), error: null }));
  series[1].data.history[0].provenance[0].value = "200";
  assert.ok(checkCashFlowSources(series).filter(s => !s.data).length >= 2);
});
test("explicit three bounded requests use pin zero; selection and source controls are local", async ctx => {
  const h = await mount(ctx); await h.verify(); assert.equal(h.all().length, 0); await h.click("Load cash flow histories");
  assert.equal(h.pending().length, 3); for (const r of h.pending()) { assert.equal(r.url.search, "?period=half_year&limit=12"); assert.equal(new Headers(r.init.headers).get("X-FinLens-Data-Version"), "0"); assert.equal(r.init.method ?? "GET", "GET"); }
  await h.settle(); await h.choose(windows[0]); await h.choose(windows[1]); assert.equal(h.host.querySelectorAll("tbody td").length, 6);
  assert.ok(h.host.querySelector("table").textContent.includes(exact)); const details = h.host.querySelector("td details"); details.open = true;
  assert.match(details.textContent, /Accession 0000000001-26-000001/); assert.equal(details.querySelector("a").getAttribute("rel"), "noopener noreferrer");
  await h.choose(windows[2]); await h.choose(windows[3]); const fifth = [...h.host.querySelectorAll("label")].find(l => l.querySelector("time")?.dateTime === windows[4].start).querySelector("input"); assert.equal(fifth.disabled, true);
  await h.choose(windows[3]); assert.equal(fifth.disabled, false); assert.equal(h.all().length, 3);
});
test("failed and absent histories remain distinct; retry is explicit", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load cash flow histories"); const batch = h.pending();
  await h.release(batch[0], history(metrics[0], windows.slice(0, 1))); await h.release(batch[1], history(metrics[1], windows.slice(0, 2))); await h.release(batch[2], { detail: "Failure" }, 0, 503);
  await h.choose(windows[0]); await h.choose(windows[1]); const rows = h.host.querySelectorAll("tbody tr");
  assert.match(rows[0].querySelectorAll("td")[1].textContent, /Not present in loaded history/); assert.match(rows[2].textContent, /History not verified/);
  assert.equal(h.all().length, 3); await h.click("Load cash flow histories"); assert.equal(h.all().length, 6); await h.settle();
});
test("missing response pin fails only its history, while a mismatch invalidates the publication", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load cash flow histories"); const batch = h.pending();
  await h.release(batch[0], history(metrics[0]), 0, 200, false); await h.release(batch[1], history(metrics[1])); await h.release(batch[2], history(metrics[2]));
  await h.choose(windows[0]); await h.choose(windows[1]); assert.match(h.host.querySelector("tbody tr").textContent, /History not verified/);
  await h.click("Load cash flow histories"); const retry = h.pending(); await h.release(retry[0], history(metrics[0]), 1);
  assert.ok(retry.every(r => r.init.signal.aborted)); assert.equal(h.host.querySelector("table"), null); assert.match(h.host.textContent, /Waiting for a verified/);
});
test("cancellation and changing duration discard stale responses and require an explicit load", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load cash flow histories"); const old = h.pending();
  await h.click("Cancel cash flow request"); assert.ok(old.every(r => r.init.signal.aborted)); await h.click("Load cash flow histories"); await h.settle();
  await h.choose(windows[0]); await h.choose(windows[1]); await h.settle(old, 9); assert.ok(h.host.querySelector("table").textContent.includes(exact));
  const select = h.host.querySelector("select"); await act(async () => { select.value = "nine_months"; select.dispatchEvent(new Event("change", { bubbles: true })); });
  assert.equal(h.host.querySelector("table"), null); assert.equal(h.all().length, 6); await h.click("Load cash flow histories");
  assert.equal(h.pending().length, 3); assert.ok(h.pending().every(r => r.url.search === "?period=nine_months&limit=12"));
});

test("nine-month durations preserve exact dates and unavailable points", async ctx => {
  const h = await mount(ctx); await h.verify(0); const select = h.host.querySelector("select");
  await act(async () => { select.value = "nine_months"; select.dispatchEvent(new Event("change", { bubbles: true })); });
  await h.click("Load cash flow histories");
  const nine = windows.map(w => ({ start: w.start, end: w.end.replace("06-30", "09-30") }));
  for (const r of h.pending()) {
    const metric = r.url.pathname.split("/").at(-1), body = history(metric, nine, "nine_months");
    if (metric === metrics[2]) { const p = body.history[1]; Object.assign(p, { status: "unavailable", value: null, reason: "Missing compatible inputs.", provenance: [], inputs: [] }); }
    await h.release(r, body);
  }
  await h.choose(nine[0]); await h.choose(nine[1]); assert.match(h.host.querySelector("caption").textContent, /Nine-month/);
  assert.match(h.host.querySelectorAll("tbody tr")[2].querySelectorAll("td")[1].textContent, /Missing compatible inputs/);
  assert.equal(h.all().length, 3);
});
test("cross-response period metadata and FCF operand disagreement reject implicated histories", () => {
  const series = metrics.map(metric => ({ metric, data: valid(metric), error: null }));
  series[1].data.history[0].period.fiscal_year = 2025;
  assert.ok(checkCashFlowSources(series).every(item => item.data === null));
  const differing = metrics.map(metric => ({ metric, data: valid(metric), error: null }));
  differing[1].data.history[0].value = "99"; differing[1].data.history[0].provenance[0].value = "99";
  assert.ok(checkCashFlowSources(differing).filter(item => !item.data).length >= 2);
});
test("history response bound and duration kind are enforced", () => {
  const b = history(metrics[0]); b.history = Array(13).fill(b.history[0]); assert.throws(() => validate(b, company, metrics[0], "half_year"));
  assert.throws(() => validate(history(metrics[0]), company, metrics[0], "nine_months"));
});

test("changing duration cancels pending histories and ignores late responses", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load cash flow histories"); const old = h.pending();
  const select = h.host.querySelector("select"); await act(async () => { select.value = "nine_months"; select.dispatchEvent(new Event("change", { bubbles: true })); });
  assert.ok(old.every(r => r.init.signal.aborted)); assert.equal(h.all().length, 3);
  await h.settle(old, 99); assert.equal(h.host.querySelector("table"), null); assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/freshness")).length, 1);
  await h.click("Load cash flow histories"); assert.equal(h.pending().length, 3); assert.ok(h.pending().every(r => r.url.search.includes("nine_months")));
});
test("legacy metric history callers still accept a response without a publication header", async ctx => {
  const api = load(frontend + "/lib/finlens-api.ts");
  ctx.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify(history(metrics[0])), { status: 200 }));
  const signal = api.versionedController(0, () => assert.fail("missing legacy header should not refresh")).signal;
  const result = await api.getMetricHistory(company.ticker, metrics[0], "half_year", signal);
  assert.equal(result.history[0].value, exact);
  await assert.rejects(api.getMetricHistory(company.ticker, metrics[0], "half_year", signal, true), { code: "INVALID_RESPONSE" });
});

test("canonical fact assignment cannot change between raw histories when FCF fails", () => {
  const operating = valid(metrics[0]), capex = history(metrics[1]);
  const source = structuredClone(operating.history[0].provenance[0]);
  source.canonical_metric = metrics[1]; capex.history[0].provenance[0] = source; capex.history[0].value = source.value;
  validate(capex, company, metrics[1], "half_year");
  const series = [{ metric: metrics[0], data: operating, error: null }, { metric: metrics[1], data: capex, error: null },
    { metric: metrics[2], data: null, error: "Synthetic FCF request failed." }];
  for (const order of [series, [...series].reverse()]) {
    const checked = checkCashFlowSources(order);
    assert.ok(checked.every(item => item.data === null));
    assert.match(checked.find(item => item.metric === metrics[0]).error, /Conflicting source identities/);
    assert.match(checked.find(item => item.metric === metrics[1]).error, /Conflicting source identities/);
  }
  const legitimate = metrics.map(metric => ({ metric, data: valid(metric), error: null }));
  assert.equal(legitimate[0].data.history[0].provenance[0].fact_id, legitimate[2].data.history[0].provenance[0].fact_id);
  assert.ok(checkCashFlowSources(legitimate).every(item => item.data));
});

test("FCF input revenue basis accepts schema values and rejects non-renderable or unknown metadata", () => {
  for (const basis of [undefined, null, "total_revenue", "customer_contract", "net_sales", "net_interest"]) {
    const body = history(metrics[2]);
    for (const input of body.history[0].inputs) {
      if (basis === undefined) delete input.revenue_basis; else input.revenue_basis = basis;
    }
    assert.equal(validate(body, company, metrics[2], "half_year"), body);
  }
  for (const basis of [{ unexpected: true }, ["total_revenue"], 1, true, "unknown"]) {
    for (const index of [0, 1]) {
      const body = history(metrics[2]); body.history[0].inputs[index].revenue_basis = basis;
      assert.throws(() => validate(body, company, metrics[2], "half_year"), { code: "INVALID_RESPONSE" });
    }
  }
});

test("malformed FCF input metadata fails closed in the mounted view rather than crashing its sources", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load cash flow histories");
  for (const r of h.pending()) {
    const metric = r.url.pathname.split("/").at(-1), body = history(metric);
    if (metric === metrics[2]) body.history[0].inputs[0].revenue_basis = { unexpected: true };
    await h.release(r, body);
  }
  await h.choose(windows[0]); await h.choose(windows[1]);
  const rows = h.host.querySelectorAll("tbody tr"); assert.equal(rows.length, 3);
  assert.match(rows[2].textContent, /History not verified/); assert.equal(rows[2].querySelector("details"), null);
  assert.ok(rows[0].textContent.includes(exact));
  await h.click("Load cash flow histories");
  for (const r of h.pending()) {
    const metric = r.url.pathname.split("/").at(-1), body = history(metric);
    if (metric === metrics[2]) { body.history[0].inputs[0].revenue_basis = null; body.history[0].inputs[1].revenue_basis = "net_sales"; }
    await h.release(r, body);
  }
  await h.choose(windows[0]); await h.choose(windows[1]);
  const fcf = h.host.querySelectorAll("tbody tr")[2]; assert.doesNotMatch(fcf.textContent, /History not verified/);
  assert.match(fcf.textContent, /net sales/); assert.equal(h.all().length, 6);
});

test("mounted reassigned fact IDs reject both histories when FCF independently fails", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load cash flow histories");
  const batch = h.pending(), operating = history(metrics[0]), capex = history(metrics[1]);
  capex.history[0].provenance[0] = { ...operating.history[0].provenance[0], canonical_metric: metrics[1] };
  capex.history[0].value = operating.history[0].value;
  await h.release(batch[0], operating); await h.release(batch[1], capex); await h.release(batch[2], { detail: "Synthetic FCF failure" }, 0, 503);
  assert.match(h.host.textContent, /No cash flow histories could be verified/);
  assert.match(h.host.textContent, /Conflicting source identities/); assert.equal(h.host.querySelector("table"), null);
});
