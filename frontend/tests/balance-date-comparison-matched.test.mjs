import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { componentLoader } from "./component-loader.mjs";

const frontend = fileURLToPath(new URL("../", import.meta.url));
const load = componentLoader(frontend);
const { BALANCE_METRICS: metrics, balanceDates, balanceCell, checkBalanceSources, validBalanceDates, validateBalanceHistory } = load(frontend + "/lib/balance-date-comparison.ts");
const Comparison = load(frontend + "/components/balance-date-comparison.tsx").default;
const Freshness = load(frontend + "/components/research-freshness.tsx").default;
let dom, createRoot;
const previous = new Map();
before(async () => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://finlens.test", pretendToBeVisual: true });
  for (const name of ["window", "document", "HTMLElement", "Node", "Event", "MouseEvent"]) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] });
  }
  previous.set("IS_REACT_ACT_ENVIRONMENT", Object.getOwnPropertyDescriptor(globalThis, "IS_REACT_ACT_ENVIRONMENT"));
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import("react-dom/client"));
});
after(() => {
  dom?.window.close();
  for (const [name, descriptor] of previous) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else delete globalThis[name];
  }
});

// All issuers, values and SEC-shaped source metadata below are synthetic fixtures.
const company = { id: 1, ticker: "AAA", cik: "0000000001", name: "Synthetic balance issuer", exchange: "TEST", has_indexed_filing: false, indexed_filing_count: 0 };
const other = { ...company, id: 2, ticker: "BBB", cik: "0000000002", name: "Synthetic other issuer" };
const exact = "9007199254740993.1234567890123456789012345";
const dates = ["2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"];
function history(metric, ends = dates.slice(0, 2), issuer = company, value = exact) {
  const accession = issuer.cik + "-26-000001";
  return { ticker: issuer.ticker, company_cik: issuer.cik, metric, unit: "USD", requested_period: "instant",
    status: ends.length ? "available" : "unavailable", reason: ends.length ? null : "Synthetic_no_compatible_stored_observations.",
    comparability: null, history: ends.map((end, index) => ({
      metric, unit: "USD", status: "available", value, reason: null, formula: null, inputs: [], revenue_basis: null,
      period: { kind: "instant", start: null, end, fiscal_year: null, fiscal_period: null, fiscal_label_basis: "unknown" },
      provenance: [{ fact_id: metrics.indexOf(metric) * 100 + index + 1, canonical_metric: metric, company_cik: issuer.cik,
        original_concept: "Synthetic_" + metric, value, unit: "USD", period_start: null, period_end: end,
        form: "10-K", filed: "2026-02-01", accession_number: accession,
        sec_url: "https://www.sec.gov/Archives/edgar/data/" + Number(issuer.cik) + "/" + accession.replaceAll("-", "") + "/index.html",
        source_fiscal_year: 2025, source_fiscal_period: "FY" }], alternatives: [],
    })) };
}
function unavailable(body, index, status = "unavailable") {
  const point = body.history[index];
  Object.assign(point, { status, value: null, provenance: [], reason: "Synthetic_original_reason__v1 <em>literal</em>." });
  body.status = body.history.some(p => p.status === "available") ? "available"
    : body.history.every(p => p.status === "not_applicable") ? "not_applicable" : "unavailable";
  body.reason = body.status === "available" ? null : point.reason;
  return body;
}
const valid = (body, metric = metrics[0], issuer = company) => validateBalanceHistory(body, issuer, metric);
const goodSeries = (metric, ends) => ({ metric, data: valid(history(metric, ends), metric), error: null });
function freshness(issuer, pin) {
  const stream = { status: "unknown", last_checked_at: null, last_successful_sync_at: null, latest_source_filing_date: null,
    last_error: null, failure_stage: null, pending_targets: [], inventory_complete: false };
  return { ticker: issuer.ticker, data_version: pin, facts_version: pin, evidence_version: 0, status: "unknown",
    facts: stream, evidence: stream, latest_indexed_filing: null, migration_required: false, scope: "Synthetic stored-only fixture." };
}

async function mount(ctx, { issuer = company, strict = false } = {}) {
  const requests = [], unexpected = [];
  ctx.mock.method(globalThis, "fetch", (path, init) => {
    const url = new URL(String(path), "http://finlens.test");
    if (!/^\/api\/finlens\/companies\/(AAA|BBB)\/(freshness|financials\/metrics\/(cash_and_equivalents|total_assets|total_liabilities))$/.test(url.pathname)) unexpected.push(String(path));
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    requests.push({ url, init, resolve, reject, released: false });
    return promise; // Deliberately ignore abort; the real transport must guard it.
  });
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host), catalogChanged = ctx.mock.fn(async () => true);
  async function render(next = issuer) {
    issuer = next;
    const content = React.createElement(Freshness, { key: issuer.ticker + issuer.cik, ticker: issuer.ticker, catalogChanged },
      React.createElement(Comparison, { company: issuer }));
    await act(async () => root.render(strict ? React.createElement(React.StrictMode, null, content) : content));
  }
  ctx.after(async () => { await act(async () => root.unmount()); host.remove(); assert.deepEqual(unexpected, []); });
  async function release(request, body, pin = 0, status = 200, header = true) {
    assert.ok(request && !request.released, "A distinct pending fetch is settled once"); request.released = true;
    await act(async () => request.resolve(new Response(JSON.stringify(body), { status,
      headers: header ? { "X-FinLens-Data-Version": String(pin) } : {} })));
  }
  function pendingHistory() { return requests.filter(r => r.url.pathname.includes("/metrics/") && !r.released && !r.init.signal.aborted); }
  const historyRequests = () => requests.filter(r => r.url.pathname.includes("/metrics/"));
  const freshnessRequests = () => requests.filter(r => r.url.pathname.endsWith("/freshness"));
  async function verify(pin = 0, selectedIssuer = issuer) {
    const request = freshnessRequests().filter(r => !r.released && !r.init.signal.aborted).at(-1);
    await release(request, freshness(selectedIssuer, pin), pin);
  }
  async function click(name) {
    const button = [...host.querySelectorAll("button")].find(b => b.textContent === name);
    assert.ok(button && !button.disabled, name); await act(async () => button.click()); return button;
  }
  async function choose(end) {
    const label = [...host.querySelectorAll("label")].find(label => label.querySelector("time")?.dateTime === end);
    assert.ok(label, "Date label " + end); const input = label.querySelector("input");
    assert.equal(input.disabled, false); await act(async () => input.click()); return input;
  }
  async function settle(batch = pendingHistory(), factory = (metric, target) => history(metric, dates, target), pin = 0) {
    for (const request of batch) {
      const target = request.url.pathname.includes("/BBB/") ? other : company;
      const metric = request.url.pathname.split("/").at(-1);
      await release(request, factory(metric, target), pin);
    }
  }
  async function focusCheck() { await act(async () => window.dispatchEvent(new Event("focus"))); }
  await render();
  return { host, requests, historyRequests, freshnessRequests, pendingHistory, verify, click, choose, settle, release, render, focusCheck };
}

test("bounded raw instant histories preserve the response, exact decimals and alternative filing evidence", () => {
  for (const metric of metrics) {
    const body = history(metric);
    const alternative = { ...body.history[0].provenance[0], fact_id: 999, value: "10.00000000000001", filed: "2025-12-31" };
    body.history[0].alternatives.push(alternative);
    const original = JSON.stringify(body);
    assert.equal(valid(body, metric), body);
    assert.equal(JSON.stringify(body), original);
    assert.equal(body.history[0].value, exact);
    assert.equal(body.history[0].alternatives[0], alternative);
  }
});

test("history contract rejects malformed identities, metric set, units, periods, values and aggregate states", () => {
  const mutations = [
    body => { body.ticker = "BBB"; }, body => { body.company_cik = other.cik; }, body => { body.metric = "revenue"; },
    body => { body.unit = "EUR"; }, body => { body.requested_period = "quarter"; }, body => { body.status = "unavailable"; },
    body => { body.history = null; }, body => { body.history = Array(13).fill(body.history[0]); },
    body => { body.history[0].metric = "total_assets"; }, body => { body.history[0].unit = "EUR"; },
    body => { body.history[0].value = 10; }, body => { body.history[0].value = "Infinity"; },
    body => { body.history[0].value = "1e9999"; }, body => { body.history[0].formula = "assets - liabilities"; },
    body => { body.history[0].inputs = [{}]; }, body => { body.history[0].provenance = []; },
    body => { body.history[0].alternatives = null; }, body => { body.history[0].period = null; },
    body => { body.history[0].period.start = "2025-01-01"; }, body => { body.history[0].period.kind = "annual"; },
    body => { body.history[0].period.end = "2025-02-30"; }, body => { body.history[0].period.end = "0000-01-01"; },
    body => { body.history[0].period.fiscal_year = "2025"; }, body => { body.history[0].period.fiscal_label_basis = null; },
    body => { body.history[0].provenance[0].value = "0"; }, body => { body.comparability = { value_basis: "restated", status: "verified" }; },
    body => { body.history[0].status = "not_applicable"; }, body => { body.history[0].reason = {}; },
  ];
  for (const mutate of mutations) { const body = history(metrics[0]); mutate(body); assert.throws(() => valid(body), { code: "INVALID_RESPONSE" }); }
  assert.throws(() => valid(history(metrics[0]), "revenue"), { code: "INVALID_RESPONSE" });
  assert.throws(() => valid(history(metrics[0]), metrics[0], { ...company, cik: "1" }), { code: "INVALID_RESPONSE" });
});

test("selected and alternative source lineage must bind to exact company, metric, unit and instant date", () => {
  for (const alternative of [false, true]) for (const mutate of [
    s => { s.fact_id = 0; }, s => { s.fact_id = 1.5; }, s => { s.company_cik = other.cik; },
    s => { s.canonical_metric = "total_assets"; }, s => { s.original_concept = ""; }, s => { s.unit = "EUR"; },
    s => { s.period_start = "2025-01-01"; }, s => { s.period_end = "2025-09-30"; },
    s => { s.filed = "2026-02-30"; }, s => { s.accession_number = "unknown"; }, s => { s.source_fiscal_period = 1; },
    s => { s.sec_url = "javascript:alert(1)"; }, s => { s.sec_url = "https://sec.gov.evil.test/filing"; },
    s => { s.sec_url = s.sec_url.replace("/data/1/", "/data/2/"); },
    s => { s.sec_url = s.sec_url.replace("000000000126000001", "000000000126000002"); },
    s => { s.sec_url = s.sec_url.replace("https://", "http://"); },
    s => { s.sec_url = s.sec_url.replace("https://", "https://user:secret@"); },
    s => { s.sec_url += "?redirect=https://example.test"; }, s => { s.sec_url += "#unknown"; },
  ]) {
    const body = history(metrics[0]), point = body.history[0];
    if (alternative) point.alternatives.push({ ...point.provenance[0], fact_id: 99 });
    mutate(alternative ? point.alternatives[0] : point.provenance[0]);
    assert.throws(() => valid(body), { code: "INVALID_RESPONSE" });
  }
});

test("duplicate same-date rows and conflicting fact identities reject the whole series", () => {
  for (const conflict of [false, true]) {
    const body = history(metrics[0]), duplicate = structuredClone(body.history[0]);
    if (conflict) { duplicate.value = "0"; duplicate.provenance[0].value = "0"; duplicate.provenance[0].fact_id = 500; }
    body.history.push(duplicate); assert.throws(() => valid(body), { code: "INVALID_RESPONSE" });
  }
  const body = history(metrics[0]); body.history[1].provenance[0].fact_id = body.history[0].provenance[0].fact_id;
  assert.throws(() => valid(body), { code: "INVALID_RESPONSE" });
});

test("date union and exact cells preserve missing, unavailable, not-applicable and request errors", () => {
  const cash = goodSeries(metrics[0], [dates[0], dates[2]]);
  const assetsBody = unavailable(history(metrics[1], [dates[0], dates[1]]), 1);
  const assets = { metric: metrics[1], data: valid(assetsBody, metrics[1]), error: null };
  const liabilitiesBody = unavailable(history(metrics[2], [dates[0]]), 0, "not_applicable");
  const liabilities = { metric: metrics[2], data: valid(liabilitiesBody, metrics[2]), error: null };
  const failed = { metric: metrics[2], data: null, error: "Synthetic request failure" };
  assert.deepEqual(balanceDates([cash, assets, liabilities]), dates.slice(0, 3));
  assert.equal(balanceCell(cash, dates[1]).kind, "absent");
  assert.equal(balanceCell(assets, dates[1]).point.status, "unavailable");
  assert.equal(balanceCell(liabilities, dates[0]).point.status, "not_applicable");
  assert.equal(balanceCell(failed, dates[0]).kind, "error");
  assert.ok(validBalanceDates(dates.slice(0, 2), dates));
  assert.ok(validBalanceDates(dates.slice(0, 4), dates));
  for (const selected of [[], [dates[0]], [dates[0], dates[0]], dates, [dates[0], "2020-01-01"]]) assert.equal(validBalanceDates(selected, dates), false);
});

test("real publication provider waits for verification; explicit load uses exactly three GETs with zero pin", async ctx => {
  const h = await mount(ctx);
  assert.match(h.host.textContent, /Waiting for a verified/); assert.equal(h.historyRequests().length, 0);
  await h.verify(0); assert.equal(h.historyRequests().length, 0);
  await h.click("Load balance histories");
  assert.equal(h.pendingHistory().length, 3);
  assert.deepEqual(h.pendingHistory().map(r => r.url.pathname.split("/").at(-1)), metrics);
  for (const r of h.pendingHistory()) {
    assert.equal(r.url.search, "?period=instant&limit=12");
    assert.equal(r.init.method ?? "GET", "GET"); assert.equal(Object.hasOwn(r.init, "body"), false);
    assert.equal(r.init.cache, "no-store"); assert.equal(new Headers(r.init.headers).get("X-FinLens-Data-Version"), "0");
  }
  await h.settle(); assert.equal(h.host.querySelectorAll('input[type="checkbox"]').length, 5);
  assert.equal(h.host.querySelectorAll("table").length, 0);
  await h.choose(dates[0]); await h.choose(dates[1]);
  assert.equal(h.host.querySelectorAll("tbody tr").length, 3); assert.equal(h.host.querySelectorAll("tbody td").length, 6);
  assert.match(h.host.querySelector("table").textContent, new RegExp(exact.replaceAll(".", "\\.")));
  assert.equal(h.host.querySelector('[role="region"]').tabIndex, 0);
  assert.equal(h.host.querySelectorAll("th[scope=col]").length, 3);
  assert.equal(h.host.querySelectorAll("th[scope=row]").length, 3);
  assert.equal(h.host.querySelector('input[type="checkbox"]').closest("label").querySelector("time").dateTime, dates[0]);
  assert.match(h.host.textContent, /not a complete balance sheet/);
  assert.match(h.host.textContent, /not what was known historically/);
});

test("selection and native source disclosures stay local, preserve exact strings, and cap selection at four dates", async ctx => {
  const h = await mount(ctx); await h.verify(7); await h.click("Load balance histories"); await h.settle(undefined, undefined, 7);
  for (const r of h.historyRequests()) assert.equal(new Headers(r.init.headers).get("X-FinLens-Data-Version"), "7");
  const loadButton = [...h.host.querySelectorAll("button")].find(b => b.textContent === "Load balance histories");
  await h.choose(dates[0]); const focused = await h.choose(dates[1]); focused.focus();
  assert.equal(document.activeElement, focused);
  const detail = h.host.querySelector("td details"); detail.open = true;
  detail.querySelector("summary").focus(); assert.equal(document.activeElement, detail.querySelector("summary"));
  assert.ok(detail.textContent.includes(exact + " USD")); assert.match(detail.textContent, /Accession 0000000001-26-000001/);
  const source = detail.querySelector("a");
  assert.equal(source.getAttribute("href"), history(metrics[0]).history[0].provenance[0].sec_url);
  assert.equal(source.getAttribute("rel"), "noopener noreferrer");
  await h.choose(dates[2]); await h.choose(dates[3]);
  const last = [...h.host.querySelectorAll("label")].find(label => label.querySelector("time")?.dateTime === dates[4]).querySelector("input");
  assert.equal(last.disabled, true); assert.equal(h.host.querySelectorAll("thead th").length, 5);
  await h.choose(dates[3]); assert.equal(last.disabled, false);
  await h.choose(dates[2]); await h.choose(dates[1]); assert.equal(h.host.querySelector("table"), null);
  assert.equal(h.historyRequests().length, 3); assert.equal(h.freshnessRequests().length, 1);
  assert.equal([...h.host.querySelectorAll("button")].find(b => b.textContent === "Load balance histories"), loadButton);
});

test("mounted cells distinguish absent date, unavailable, not-applicable and failed series without substitution", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories");
  const batch = h.pendingHistory();
  await h.release(batch[0], history(metrics[0], [dates[0]]));
  await h.release(batch[1], unavailable(unavailable(history(metrics[1], dates.slice(0, 2)), 0), 1, "not_applicable"));
  await h.release(batch[2], { detail: "Synthetic upstream failure" }, 0, 503);
  await h.choose(dates[0]); await h.choose(dates[1]);
  const rows = h.host.querySelectorAll("tbody tr");
  assert.match(rows[0].querySelectorAll("td")[1].textContent, /Not present in loaded history/);
  assert.ok(!rows[0].querySelectorAll("td")[1].textContent.includes(exact));
  assert.match(rows[1].querySelectorAll("td")[0].textContent, /Unavailable/);
  assert.match(rows[1].querySelectorAll("td")[1].textContent, /Not applicable/);
  assert.match(rows[1].textContent, /Synthetic_original_reason__v1 <em>literal<\/em>/);
  assert.equal(rows[1].querySelector("em"), null);
  assert.match(rows[2].textContent, /History not verified/);
  assert.equal(rows[2].querySelector("a"), null);
  assert.equal(h.historyRequests().length, 3);
});

test("empty and undated histories show original availability/reasons without inventing selectable dates", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories");
  await h.settle(undefined, metric => {
    const body = history(metric, []);
    if (metric === metrics[0]) {
      body.status = "not_applicable"; body.reason = "Synthetic_not_applicable_reason.";
    } else if (metric === metrics[1]) {
      const point = unavailable(history(metric, [dates[0]]), 0).history[0]; point.period = null;
      body.history = [point];
    }
    return body;
  });
  assert.match(h.host.textContent, /0 distinct reported dates/); assert.match(h.host.textContent, /Fewer than two dates/);
  assert.match(h.host.textContent, /Not applicable/); assert.match(h.host.textContent, /Synthetic_not_applicable_reason/);
  assert.match(h.host.textContent, /Undated observation/);
  assert.equal(h.host.querySelector("input[type=checkbox]"), null); assert.equal(h.host.querySelector("table"), null);
});

test("all request failures remain errors and require another explicit three-request load", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories");
  for (const request of h.pendingHistory()) await h.release(request, { detail: "Synthetic failure" }, 0, 503);
  assert.match(h.host.textContent, /No balance histories could be verified/);
  assert.equal(h.host.querySelector("table"), null); assert.equal(h.historyRequests().length, 3);
  await h.click("Load balance histories"); assert.equal(h.historyRequests().length, 6); await h.settle();
});

test("unsafe provenance rejects its whole mounted series and contributes no dates or links", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories");
  await h.settle(undefined, metric => {
    const body = history(metric, metric === metrics[0] ? ["2020-01-01"] : dates.slice(0, 2));
    if (metric === metrics[0]) body.history[0].provenance[0].sec_url = "https://evil.test/filing";
    return body;
  });
  assert.ok(!h.host.textContent.includes("2020-01-01")); await h.choose(dates[0]); await h.choose(dates[1]);
  assert.match(h.host.querySelector("tbody tr").textContent, /History not verified/);
  assert.equal(h.host.querySelector('a[href*="evil"]'), null);
});

test("cancelled requests cannot render or invalidate a replacement even when fetch ignores abort", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories"); const old = h.pendingHistory();
  await h.click("Cancel balance request"); assert.ok(old.every(r => r.init.signal.aborted));
  assert.match(h.host.textContent, /cancelled/); assert.equal(h.historyRequests().length, 3);
  await h.click("Load balance histories"); const replacement = h.pendingHistory();
  await h.settle(replacement, (metric, issuer) => history(metric, dates, issuer, "123.0000000000001"));
  await h.choose(dates[0]); await h.choose(dates[1]);
  await h.settle(old, (metric, issuer) => history(metric, dates, issuer, "999"), 999);
  assert.match(h.host.querySelector("table").textContent, /123\.0000000000001 USD/);
  assert.ok(!h.host.querySelector("table").textContent.includes("999 USD"));
  assert.equal(h.freshnessRequests().length, 1); assert.equal(h.historyRequests().length, 6);
});

test("ignored-abort A to B to A responses cannot cross company/session ownership", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories"); const firstA = h.pendingHistory();
  await h.render(other); assert.ok(firstA.every(r => r.init.signal.aborted)); await h.verify(0, other);
  await h.click("Load balance histories"); const firstB = h.pendingHistory();
  await h.render(company); assert.ok(firstB.every(r => r.init.signal.aborted)); await h.verify();
  await h.click("Load balance histories"); const secondA = h.pendingHistory(); await h.settle(secondA);
  await h.choose(dates[0]); await h.choose(dates[1]);
  await h.settle(firstA, (metric, issuer) => history(metric, ["2020-01-01", "2019-01-01"], issuer, "1"), 5);
  await h.settle(firstB, (metric, issuer) => history(metric, ["2021-01-01", "2020-01-01"], issuer, "2"), 5);
  assert.match(h.host.querySelector("caption").textContent, /AAA/); assert.ok(h.host.querySelector("table").textContent.includes(exact));
  assert.ok(!h.host.textContent.includes("2019-01-01")); assert.ok(!h.host.textContent.includes("2021-01-01"));
  assert.equal(h.historyRequests().length, 9); assert.equal(h.freshnessRequests().length, 3);
});

test("verified publication refresh clears dates, cancels pending work and pins the next explicit load", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories"); const old = h.pendingHistory();
  await h.focusCheck(); await h.verify(2);
  assert.ok(old.every(r => r.init.signal.aborted)); assert.equal(h.host.querySelector("table"), null);
  assert.equal(h.host.querySelector("input[type=checkbox]"), null); assert.equal(h.historyRequests().length, 3);
  await h.click("Load balance histories"); const next = h.pendingHistory();
  assert.ok(next.every(r => new Headers(r.init.headers).get("X-FinLens-Data-Version") === "2"));
  await h.settle(next, (metric, issuer) => history(metric, dates, issuer, "2.0000000000002"), 2);
  await h.choose(dates[0]); await h.choose(dates[1]); await h.settle(old, undefined, 9);
  assert.match(h.host.querySelector("caption").textContent, /Publication version 2/);
  assert.match(h.host.querySelector("table").textContent, /2\.0000000000002 USD/);
  assert.equal(h.freshnessRequests().length, 2);
});

test("active publication mismatch aborts siblings and waits for independently verified newer publication", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories"); const old = h.pendingHistory();
  await h.release(old[0], history(metrics[0], dates), 1);
  assert.ok(old.every(r => r.init.signal.aborted)); assert.match(h.host.textContent, /Waiting for a verified/);
  assert.equal(h.host.querySelector("table"), null); assert.equal(h.freshnessRequests().length, 2);
  await h.verify(0); assert.match(h.host.textContent, /Could not verify/);
  assert.equal([...h.host.querySelectorAll("button")].find(b => b.textContent === "Load balance histories").disabled, true);
  await h.click("Retry data check"); await h.verify(1); await h.click("Load balance histories");
  assert.ok(h.pendingHistory().every(r => new Headers(r.init.headers).get("X-FinLens-Data-Version") === "1"));
  await h.settle(undefined, undefined, 1); await h.choose(dates[0]); await h.choose(dates[1]);
  for (const request of old.slice(1)) await h.release(request, history(request.url.pathname.split("/").at(-1)), 99);
  assert.match(h.host.querySelector("caption").textContent, /Publication version 1/); assert.equal(h.freshnessRequests().length, 3);
});

test("strict-mode effect replay creates no automatic history requests or duplicate explicit loads", async ctx => {
  const h = await mount(ctx, { strict: true });
  assert.equal(h.historyRequests().length, 0); await h.verify(0);
  await h.click("Load balance histories"); assert.equal(h.historyRequests().length, 3);
  await h.settle(); await h.choose(dates[0]); await h.choose(dates[1]);
  await h.click("Clear balance comparison"); assert.equal(h.host.querySelector("table"), null);
  assert.equal(h.historyRequests().length, 3);
});

test("bounded date union contains at most the 36 explicitly loaded observations", () => {
  const series = metrics.map((metric, index) => goodSeries(metric,
    Array.from({ length: 12 }, (_, year) => String(1980 + index * 12 + year) + "-12-31")));
  assert.equal(balanceDates(series).length, 36);
  assert.deepEqual(checkBalanceSources(series), series);
});

test("conflicting fact identities across responses reject every involved series regardless of order", () => {
  for (const reverse of [false, true]) {
    const series = metrics.map(metric => goodSeries(metric, dates.slice(0, 2)));
    series[1].data.history[0].alternatives.push({ ...series[1].data.history[0].provenance[0],
      fact_id: series[0].data.history[0].provenance[0].fact_id });
    const checked = checkBalanceSources(reverse ? series.toReversed() : series);
    for (const item of checked) assert.equal(!!item.data, item.metric === metrics[2]);
    assert.ok(series.every(item => !!item.data), "Inputs are preserved");
    series[2].data.history[0].provenance[0].fact_id = series[0].data.history[0].provenance[0].fact_id;
    assert.ok(checkBalanceSources(series).every(item => item.data === null));
  }
});

test("mounted cross-response source conflict stays explicit and cannot contribute selectable dates", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories");
  await h.settle(undefined, metric => {
    const body = history(metric, metric === metrics[2] ? dates.slice(0, 2) : ["2020-01-01"]);
    if (metric === metrics[1]) body.history[0].provenance[0].fact_id = 1;
    return body;
  });
  assert.ok(![...h.host.querySelectorAll("label time")].some(time => time.dateTime === "2020-01-01"));
  await h.choose(dates[0]); await h.choose(dates[1]);
  assert.match(h.host.querySelectorAll("tbody tr")[0].textContent, /Conflicting source identities/);
  assert.match(h.host.querySelectorAll("tbody tr")[1].textContent, /Conflicting source identities/);
  assert.ok(h.host.querySelectorAll("tbody tr")[2].textContent.includes(exact));
});

test("stalled response body ignores abort but cannot affect explicit retry or publication ownership", async ctx => {
  const h = await mount(ctx); await h.verify(); await h.click("Load balance histories");
  const old = h.pendingHistory(); let finishBody;
  old[0].released = true;
  await act(async () => old[0].resolve({ ok: true, status: 200,
    headers: new Headers({ "X-FinLens-Data-Version": "999" }), json: () => new Promise(resolve => { finishBody = resolve; }) }));
  assert.equal(typeof finishBody, "function");
  await h.click("Cancel balance request");
  await h.click("Load balance histories"); await h.settle(); await h.choose(dates[0]); await h.choose(dates[1]);
  await act(async () => finishBody(history(metrics[0], ["2010-01-01", "2009-01-01"])));
  await h.settle(old.slice(1), undefined, 999);
  assert.ok(h.host.querySelector("table").textContent.includes(exact));
  assert.ok(!h.host.textContent.includes("2010-01-01"));
  assert.equal(h.freshnessRequests().length, 1);
});
