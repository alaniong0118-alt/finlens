# FIN-DEPTH-01 Backend Increment 1A

Status: active; scoped NaN CapEx P2 correction verified; independent Astra P2 re-review pending
Roadmap phase: bounded deterministic Research Mode financial depth

## Objective

Implement only the approved Backend 1A annual financial insights contract: bounded
whole-company loading, unchanged canonical financial arithmetic, complete rejected
evidence, disjoint financial/diagnostic closures, closed statements and pinned API.

## Current architecture and context

Entry branch main, HEAD c7c3d31163bcd2fbc3b084e34666371c7b1b0c2c, empty index.
Only entry exceptions are frontend/next-env.d.ts and two untracked AAPL reports.
SHA-256 respectively: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0,
A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C,
F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C.
Reuse FinancialMetrics, annual_comparison's eleven-metric anchor union,
compare_fiscal, existing reader lifecycle and read-only repeatable-read sessions.
The approved conversation design and final focused contract addendum govern.

## Constraints

Only the three new financial_insights modules, optional normalizer checkpoints,
isolated database support, main route, release admission, focused synthetic tests
and this plan may change. No private .env access, live database, external calls,
models, services, browser, CI, dependencies, staging, commit or push. Preserve all
historical FAIL/BLOCKED records and protected exceptions. Stop on scope blockers.

## Non-goals

Frontend 1B, new finance formulas/mappings/policies, authorization activation,
schema/migration changes, acquisition, causal analysis and live acceptance.

## Implementation stages

1. Complete precheck; create this active record.
2. Implement typed contract/budgets and bounded full-company loading.
3. Add unchanged-normalization work checkpoints; build evidence and statements.
4. Integrate exact pinned GET route with publication/cleanup lifecycle.
5. Run isolated boundary/adversarial tests and smallest justified regressions.
6. Self-review exact unstaged scope and protected state; hand off for Astra.

## Decisions

- 2026-10-25: No selected-year input filtering or truncated-prefix calculation.
- 2026-10-25: Adapter use restricted to unchanged empty registries; no artifact I/O.
- 2026-10-25: Deadline/size/graph/query overflow rejects the entire response.
- 2026-10-25: Approved exact reference cardinalities and sign wording are fixed;
  diagnostic evidence never authenticates a value or change.

## Discovered issues

Existing loader eagerly materializes all facts. Existing rejected CapEx/margins can
omit operand provenance. Dedicated bounded loading and additive envelope required.

## Progress

- [x] 2026-10-25: Instructions, expected main/HEAD, empty index and protected hashes verified.
- [x] Bounded backend implementation.
- [x] Focused synthetic tests and regressions, with baseline failures retained below.
- [x] Scope/preservation verification and self-review; final checks recorded below.
- [ ] Independent Astra implementation acceptance (coordinator gate).

## Test and validation strategy

Use a guarded no-site/no-bytecode runner which blocks dotenv reads before app
imports and rejects live DB/network/model/artifact access. Synthetic objects and
mock read-only sessions only. Test every numerical ceiling, load completeness,
exact arithmetic/period/scope behavior, disjoint closures, statements, publication
zero/stale pins, registry changes, cleanup, cursor accounting and encoded bytes.
Record exact commands/results below; no unexecuted test is claimed passing.

## Completion criteria

Required contracts implemented without financial-semantic changes; focused tests
and relevant offline regressions pass; exact scope/index/protected state preserved.
Remain active pending independent implementation review. No frontend work starts.

## Implementation and resource ownership

New modules: backend/app/financial_insights_service.py,
backend/app/financial_insights_contract.py and backend/app/financial_insights_schemas.py.
Existing changes: backend/app/financial_metrics_service.py (optional work hooks),
backend/app/database.py (separate bounded pool/cursor), backend/app/main.py
(route, errors and publication), backend/app/release_policy.py (one exact GET),
backend/tests/test_http_database_runtime.py (valid selector for the added route).
New tests: backend/tests/test_financial_insights.py and its guarded runner
backend/tests/run_financial_insights.py. This is the only changed documentation.
All eleven authorized paths remain unstaged.

GET /companies/{ticker}/financials/insights requires exactly one canonical numeric
X-FinLens-Data-Version header, including verified zero. mode=discover accepts no
years and exposes the unchanged eleven-metric discovery union. mode=compare
(default) requires chronological earlier_fiscal_year/later_fiscal_year, 1900-2099.
Seven comparisons, full canonical operands, publication versions, typed evidence,
closed statements and completeness are returned. Expected-version mismatch uses
the existing 409 path before facts are loaded. All reads use the existing
repeatable-read/read-only context; cleanup must complete before response creation.

| Resource | Limit | Owning enforcement |
|---|---|---|
| Whole-company facts/input | 10,000 / 8 MiB | service.preflight_query, bounded_load, row_stats; inner LIMIT 10,001 and full-load count/byte verification |
| Eligible/group candidates | 10,000 / 256 | service.admit_input before FinancialMetrics |
| Envelope sources/candidates/slot | 2,048 / 4,096 / 256 | Composition.raw_source, observation, candidates_for and Graph.put |
| Annual windows/per selected year | 256 / 16 | admit_input, existing eleven metric anchor union |
| Observations/operands/rejections | 64 / 32 / 256 | Graph.put and collector allocation checks |
| Nodes/edges/depth | 8,192 / 16,384 / 6 | Graph.put, closure, validate; category and role edge grammar |
| Statements/per-statement refs/all refs | 35 / 8,192 / 32,768 | validate_statement_limits and exact expected statement equality |
| Raw fields | date/time 64, ordinary 128, metric/source 400 UTF-8 bytes | preflight_query and row_stats |
| Other strings | identities 192, company name 800, explanations 1,024, statements 2,048 | schema/checked_text/validate_fields |
| Work/output | 2,000,000 visits / 4 MiB actual UTF-8 | Budget, normalizer _walk/_tick/_contains, bounded_json |
| Research SELECTs/all cursor calls | 5 / 20 | InsightsCursor.execute, including raw initialization/probe calls |
| Connection/pool/statement/lock | 2 s / 1 s / 1,500 ms / 250 ms | isolated insights_session_factory; existing engines unchanged |
| Publication deadline | 20 s | Budget reserves blocking time, loop checkpoints, post-cleanup and ASGI send checks |

Field ceilings are inclusive; exact structural role/cardinality constraints can
reject before generic resource ceilings. Reference closures are computed from a
collector-owned graph, with independent copies at the response boundary. Financial
refs exclude rejected operands and alternatives. Diagnostic refs retain negative
CapEx, rejected margins, competing windows and conflicting source identities.
Admitted canonical comparisons and Decimal formulas are reused without recomputation.

## Additional implementation decisions and corrected test discoveries

- All full-company facts are projected through a client-side cursor; fetchmany(128)
  is not SQLAlchemy yield_per. Named/server cursors are rejected. Tests exercise
  real SQLAlchemy CursorResult fetchmany over a fake DBAPI and account SQL at the
  native cursor entrypoint, not just SQLAlchemy events.
- Installed SQLAlchemy uses an empty-query ';' checkout ping; it is counted.
- Native HSTORE initialization explicitly creates psycopg.Cursor and bypasses
  cursor_factory. This unused initialization feature is disabled only on the new
  pool (use_native_hstore=False). Financial projections contain no HSTORE. No
  operational/ordinary HTTP engine or financial policy is changed.
- The four module-owned authorization/policy registries must stay empty. The
  production evidence adapter is not called; its approved empty-registry result
  is exactly (). No artifact, model, provider or SEC acquisition occurs.
- A guard-runner cache_clear compatibility error was corrected without permitting
  model loading. Twenty unrelated encoder/model tests remain deliberately excluded.
- Empty-evidence testing exposed repeated concatenation of diagnostic reasons;
  complete reasons now remain in separate side/operand records. Parent reasons
  use the approved 1,024-byte explanation ceiling, not a smaller ordinary field cap.
- An AST equivalence test strips only optional budget instrumentation and compares
  FinancialMetrics to HEAD. All original selection and arithmetic AST is retained.
- Final precision self-review added explicit coverage for negative display-zero
  boundaries and nonzero percentages rounding to zero on large baselines. Those
  percentages use exact presentation, with the accepted precision notice; no
  unqualified positive/negative zero change is published for a nonzero result.

## Verification actually executed

From D:\Projects\finlens-foundation\backend:

```
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_insights.py tests/test_company_comparison.py tests/test_http_database_runtime.py -k "not encoder and not missing_cache and not incompatible_model and not tone" --maxfail=3 --tb=short
```

Final scoped run: **406 passed, 22 deselected**, one existing Starlette/httpx
deprecation warning. Includes 114 new insights cases, 61 annual comparison cases
and 231 relevant HTTP database/runtime cases. This is synthetic/mocked evidence;
no real database, API listener or browser was exercised. The runner installs
dotenv/private-file, database, provider, model and external-network guards before
application imports. Windows stdlib asyncio wakeup socket pairs are confined IPC.

The broader run including tone cases produced **2 failures, 385 passes, 20
deselected** before the last additional cases. Both failures are the pre-existing
generic route fixture supplying an invalid filing-tone selector: actual 422,
expected 503. Reproduced both using git-show HEAD:backend/app/main.py compiled
into an in-memory module under the same guards, selecting only the two tone cases:
**2 failed, 38 deselected**. The tone assertions/product behavior were not changed.
This remains FAIL evidence, not a passed broader suite.

Static checks: ten scoped Python files compile without imports/bytecode; scoped
tracked git diff --check and all scoped Python trailing-whitespace checks pass.
Git warns about normal future LF/CRLF conversion; protected next-env is unchanged.
Pre/post HEAD/index and all three protected SHA-256 values match the entry state.
Only the eleven authorized paths plus the three protected exceptions are present.

## Final outcome

Backend 1A implementation is ready for independent Astra implementation review.
Plan remains active; independent acceptance is pending. No claim of live PostgreSQL,
native connection, issuer coverage, browser, CI, provider, deployment or release
acceptance is made. Baseline tone failures and historical FAIL/BLOCKED records are
preserved. No Frontend 1B, staging, commit or push occurred.
Suggested eventual commit: feat(research): add bounded annual financial insights backend.

## Astra P2 correction — 2026-10-25

Independent Astra 6 High verdict: **FAIL — REQUIRE SCOPED SOL FIXES**. Exactly one
P2: diagnostic CapEx sign classification orders Decimal NaN without testing
finiteness, producing InvalidOperation and an incorrect endpoint 500 even when a
valid selected CapEx/FCF exists. Canonical usable() already rejects nonfinite facts.
This verdict supersedes the earlier implementation-review readiness statement;
historical test outcomes and unrelated filing-tone FAIL evidence remain intact.

Authorized correction paths only: financial_insights_service.py,
test_financial_insights.py and this active plan. Entry main/HEAD, empty index,
exact eleven-file candidate scope and all three protected hashes match. Candidate
byte fingerprints were captured to prove all other candidate files stay unchanged.

- [x] Scoped precheck and relevant source/test inspection.
- [x] Before-fix endpoint reproduction and focused regression cases.
- [x] Finiteness-first diagnostic correction, including accurate rejection tags.
- [x] Focused/full guarded regression and three-path preservation verification.
- [ ] Coordinator/Astra P2 re-review (not performed by this task).

### Root cause and scoped correction

The collector compared fact.value < 0 without an is_finite() guard. It also could
label a nonfinite same-identity candidate an equivalent duplicate because its
finite-only identity-value set contained the usable winner alone. Both are the
same diagnostic-classification path, not financial-selector defects.

The classifier now establishes Decimal finiteness before duplicate/sign
classification. Nonfinite candidates receive the stable nonfinite_value
disposition; they are not classified as finite negative payments or equivalent
duplicates. The existing text_value/raw_source representation is unchanged:
diagnostic values remain strings (NaN, sNaN, Infinity, -Infinity), never nonfinite
JSON numbers. Canonical usable(), ranking, formulas, input admission, source scope,
version pins, resource caps, reader lifecycle and route admission are unchanged.

### Before/after verification actually executed

Focused command from backend (same guarded runner and isolation as above):

```
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_insights.py -k "nonfinite_capex_endpoint_diagnostics or finite_capex_endpoint_classification_unchanged" --tb=short
```

Before the service correction: **16 failed, 6 passed, 114 deselected**. Two
explicit NaN endpoint reproductions (valid selected later-year CapEx, and only
earlier-year CapEx) independently returned HTTP 500 instead of the asserted 200.
The pre-request canonical checks retained selected CapEx 5 and FCF 15 in the
later-year fixture, confirming that the failure was diagnostic-only. Infinity
variants also failed the required accurate rejection-classification assertions.

After correction: **22 passed, 114 deselected**. The 16 nonfinite cases cover
both years, with/without a usable selected candidate, across NaN, signaling NaN,
positive infinity and negative infinity. Six finite cases cover negative, zero
and ordinary positive CapEx in both years. Every case exercises the actual
Insights route, bounded loader, composer and serializer over a mocked read-only
session. Tests verify unchanged valid comparisons/selected fact IDs, unavailable
FCF when required CapEx is absent, diagnostic identity/reason retention, strict
JSON parsing, and exclusion of rejected values from F support closures.

The unchanged established Backend 1A regression command recorded above now gives
**428 passed, 22 deselected**, with the existing Starlette/httpx deprecation
warning. No additional deselections or assertion relaxations. The original 406
passing cases remain; 22 scoped regression cases were added. Historical filing-
tone baseline failures are neither edited nor relabeled.

Post-checks: expected main/HEAD, empty index and original eleven-file candidate
scope retained. Byte fingerprints prove that only the two authorized source/test
paths and this plan changed during the correction; the other eight candidate
files and all three protected exceptions remain byte-identical to P2 entry.
Scoped syntax/whitespace checks pass. No real DB, external network, provider,
model, private .env, service, browser, CI or Frontend 1B work occurred.

Outcome: **READY FOR ASTRA P2 RE-REVIEW**. Independent closure is pending; the
historical Astra FAIL above remains recorded. All changes remain unstaged.
