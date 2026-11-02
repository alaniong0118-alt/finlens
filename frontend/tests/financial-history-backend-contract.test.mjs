import test, { before } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync, rmSync, rmdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { componentLoader } from "./component-loader.mjs";

const frontend = fileURLToPath(new URL("../", import.meta.url));
const backend = resolve(frontend, "../backend"), load = componentLoader(frontend);
const api = load(join(frontend, "lib/finlens-api.ts"));
const balance = load(join(frontend, "lib/balance-date-comparison.ts"));
const flow = load(join(frontend, "lib/cash-flow-window-comparison.ts"));
let fixture;

function captureBackend({ run = spawnSync, platform = process.platform, output } = {}) {
  // Fresh capture on every run: never a hand-authored or checked-in JSON body.
  // This is an in-process TestClient child, not a listening backend/service.
  if (platform !== "win32") throw new Error("History backend/client contract requires Windows and installed backend/.venv/Lib/site-packages for the existing -I -S guarded runner. POSIX dependency bootstrap is unsupported.");
  let temporary;
  const target = output
    ?? join(temporary = mkdtempSync(join(tmpdir(), "finlens-history-contract-")), "responses.json");
  try {
    const python = process.env.FINLENS_CONTRACT_PYTHON ?? join(backend, ".venv", "Scripts/python.exe");
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
      ["systemroot", "windir", "path", "temp", "tmp", "pathext", "comspec", "number_of_processors"].includes(key.toLowerCase())));
    env.FINLENS_HISTORY_CONTRACT_OUTPUT = target;
    const result = run(python, ["-I", "-S", "-B", "tests/run_financial_insights.py",
      "tests/test_financial_history_client_contract.py", "-k", "test_export_current_backend_responses"],
      { cwd: backend, env, encoding: "utf8", timeout: 60_000, maxBuffer: 1024 * 1024, windowsHide: true });
    assert.equal(result.status, 0, `${result.error ?? ""}\n${result.stdout}\n${result.stderr}\nCapture: ${target}`);
    const captured = JSON.parse(readFileSync(target, "utf8"));
    assert.deepEqual(captured.capabilities, { research_mode: true, server_profile: "sec_readonly",
      ai_analysis_configured: false, ai_analysis_enabled: false, filing_research_enabled: false });
    assert.equal(captured.replies.length, 43);
    return captured;
  } finally {
    // Remove only this call's owned artifact/directory, including absent or
    // partially written output after startup, parse or validation failures.
    // Explicit caller-owned evidence paths are retained on every outcome.
    if (temporary) { try { rmSync(target, { force: true }); } finally { rmdirSync(temporary); } }
  }
}

before(() => { fixture = captureBackend({ output: process.env.FINLENS_HISTORY_CONTRACT_OUTPUT }); });

test("owned capture directories are removed after child startup exceptions and failed results", () => {
  for (const throws of [true, false]) {
    let directory;
    const startupError = new Error("Synthetic child startup failure");
    const run = (_python, _args, options) => {
      directory = dirname(options.env.FINLENS_HISTORY_CONTRACT_OUTPUT);
      assert.ok(existsSync(directory));
      if (throws) throw startupError;
      return { status: null, error: startupError, stdout: "", stderr: "" };
    };
    assert.throws(() => captureBackend({ run }), error => throws ? error === startupError : /Synthetic child startup failure/.test(error.message));
    assert.ok(directory); assert.equal(existsSync(directory), false);
  }
});

test("owned partial capture output is removed after JSON parse failure", () => {
  let target;
  const run = (_python, _args, options) => {
    target = options.env.FINLENS_HISTORY_CONTRACT_OUTPUT; writeFileSync(target, "{", "utf8");
    return { status: 0 };
  };
  assert.throws(() => captureBackend({ run }), SyntaxError);
  assert.equal(existsSync(target), false); assert.equal(existsSync(dirname(target)), false);
});

test("owned capture output is removed after setup validation failure", () => {
  let target;
  const run = (_python, _args, options) => {
    target = options.env.FINLENS_HISTORY_CONTRACT_OUTPUT;
    writeFileSync(target, JSON.stringify({ ...fixture, replies: [] }), "utf8");
    return { status: 0 };
  };
  assert.throws(() => captureBackend({ run }), { code: "ERR_ASSERTION" });
  assert.equal(existsSync(target), false); assert.equal(existsSync(dirname(target)), false);
});

test("caller-owned capture evidence survives parse failure", () => {
  const directory = mkdtempSync(join(tmpdir(), "finlens-history-contract-caller-")), output = join(directory, "responses.json");
  try {
    const run = () => { writeFileSync(output, "{", "utf8"); return { status: 0 }; };
    assert.throws(() => captureBackend({ run, output }), SyntaxError);
    assert.equal(readFileSync(output, "utf8"), "{");
  } finally { try { rmSync(output, { force: true }); } finally { rmdirSync(directory); } }
});

test("unsupported POSIX configuration fails clearly before child startup", () => {
  let calls = 0;
  assert.throws(() => captureBackend({ platform: "linux", run: () => { calls++; } }),
    /requires Windows.*backend\/\.venv\/Lib\/site-packages.*POSIX dependency bootstrap is unsupported/);
  assert.equal(calls, 0);
});

function response(snapshot, dropVersion = false) {
  const headers = new Headers(snapshot.headers);
  if (dropVersion) headers.delete("X-FinLens-Data-Version"); // Explicit proxy/header-loss fault only.
  return new Response(snapshot.body, { status: snapshot.status, headers });
}

async function consume(ctx, snapshot, { dropVersion = false } = {}) {
  let changes = 0, requests = 0;
  const controller = api.versionedController(snapshot.request_pin, () => { changes++; });
  ctx.mock.method(globalThis, "fetch", async (path, init) => {
    requests++;
    assert.equal(path, "/api/finlens" + snapshot.path);
    assert.equal(init.method ?? "GET", "GET");
    assert.equal(init.cache, "no-store");
    assert.equal(Object.hasOwn(init, "body"), false);
    assert.equal(new Headers(init.headers).get("X-FinLens-Data-Version"), String(snapshot.request_pin));
    return response(snapshot, dropVersion);
  });
  const promise = api.getMetricHistory(fixture.company.ticker, snapshot.metric, snapshot.kind,
    controller.signal, snapshot.kind !== "instant").then(body => snapshot.kind === "instant"
    ? balance.validateBalanceHistory(body, fixture.company, snapshot.metric)
    : flow.validateCashFlowHistory(body, fixture.company, snapshot.metric, snapshot.kind));
  return { promise, changes: () => changes, requests: () => requests };
}

for (const [scenario, publication] of [["full", 0], ["full", 7], ["sparse", 7], ["empty", 0]]) {
  test(`real financial-only history bodies and headers reach all consumers: ${scenario}, publication ${publication}`, async ctx => {
    const snapshots = fixture.replies.filter(r => r.scenario === scenario && r.publication === publication && r.status === 200);
    assert.equal(snapshots.length, 9);
    const accepted = [];
    for (const snapshot of snapshots) {
      const request = await consume(ctx, snapshot), body = await request.promise;
      assert.deepEqual(body, JSON.parse(snapshot.body), "Transport/validators must preserve the actual backend payload");
      assert.equal(request.changes(), 0); assert.equal(request.requests(), 1);
      for (const point of body.history) {
        const original = JSON.parse(snapshot.body).history.find(p => p.period.end === point.period.end);
        assert.deepEqual(point.period, original.period);
        if (point.status === "available") assert.equal(point.value, fixture.values[snapshot.metric]);
        for (const source of point.provenance) {
          assert.equal(typeof source.value, "string");
          assert.equal(source.period_start, point.period.start); assert.equal(source.period_end, point.period.end);
        }
      }
      accepted.push({ metric: snapshot.metric, kind: snapshot.kind, data: body, error: null });
    }
    const balances = balance.checkBalanceSources(accepted.filter(s => s.kind === "instant"));
    assert.ok(balances.every(s => s.data));
    assert.equal(balance.balanceDates(balances).length, scenario === "empty" ? 0 : 2);
    if (scenario === "sparse") {
      assert.equal(balances[0].data.status, "unavailable");
      assert.equal(balance.balanceCell(balances[2], "2025-12-31").kind, "absent");
    }
    for (const kind of ["half_year", "nine_months"]) {
      const series = flow.checkCashFlowSources(accepted.filter(s => s.kind === kind));
      assert.ok(series.every(s => s.data), "Raw histories must agree with FCF's actual operand/source identities");
      const windows = flow.cashFlowWindows(series);
      assert.equal(windows.length, scenario === "empty" ? 0 : 2);
      const fcf = series.find(s => s.metric === "free_cash_flow");
      if (scenario === "sparse") {
        const latest = windows[0];
        assert.equal(flow.cashFlowCell(series[1], latest).kind, "absent");
        const cell = flow.cashFlowCell(fcf, latest);
        assert.equal(cell.kind, "observation"); assert.equal(cell.point.status, "unavailable");
        assert.ok(cell.point.reason); assert.equal(cell.point.value, null);
      }
      for (const point of fcf.data.history.filter(p => p.status === "available")) {
        assert.equal(point.value, fixture.values.free_cash_flow);
        assert.equal(point.inputs.length, 2);
        for (const input of point.inputs) {
          const raw = series.find(s => s.metric === input.metric).data.history.find(p =>
            p.period.start === point.period.start && p.period.end === point.period.end);
          assert.equal(input.value, raw.value);
          assert.deepEqual(input.fact_ids, raw.provenance.map(s => s.fact_id));
          assert.deepEqual(point.provenance.find(s => s.canonical_metric === input.metric), raw.provenance[0]);
        }
      }
    }
  });
}

test("actual stale-pin 409 responses invalidate every consumer family at zero and nonzero publications", async ctx => {
  const snapshots = fixture.replies.filter(r => r.status === 409);
  assert.equal(snapshots.length, 6);
  for (const snapshot of snapshots) {
    const request = await consume(ctx, snapshot);
    await assert.rejects(request.promise, { status: 409, code: "DATA_VERSION_CHANGED" });
    assert.equal(request.changes(), 1); assert.equal(request.requests(), 1);
  }
});

test("header-loss fault preserves balance's optional header and cash-flow's required header", async ctx => {
  const snapshots = fixture.replies.filter(r => r.status === 200 && r.scenario === "full" && r.publication === 0);
  for (const snapshot of snapshots) {
    const request = await consume(ctx, snapshot, { dropVersion: true });
    if (snapshot.kind === "instant") assert.deepEqual(await request.promise, JSON.parse(snapshot.body));
    else await assert.rejects(request.promise, { status: 502, code: "INVALID_RESPONSE" });
    assert.equal(request.changes(), 0); assert.equal(request.requests(), 1);
  }
});

test("actual cleanup failure remains an HTTP error rather than a valid cash-flow history", async ctx => {
  const snapshot = fixture.replies.find(r => r.status === 500);
  assert.ok(snapshot);
  const request = await consume(ctx, snapshot);
  await assert.rejects(request.promise, { status: 500 });
  assert.equal(request.changes(), 0); assert.equal(request.requests(), 1);
});
