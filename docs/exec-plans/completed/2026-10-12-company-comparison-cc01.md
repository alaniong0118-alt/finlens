# CC-01: annual company comparison

Status: completed (implementation and offline verification; coordinator Git review pending)
Roadmap phase: Complete Research Mode; bounded cross-company comparison slice.

## Objective
Compare seven existing annual metrics for 2–4 catalog companies, with explicit
fiscal end-year labels, actual dates, source lineage and honest unavailable states.

## Current architecture and context
Baseline main and origin/main: d01ed5a46791274c93ebfdb132a2be0617c15591.
FinancialMetrics owns deterministic observations and economic-scope safeguards.
VersionedRoute and read_session pin each company publication in a read-only
transaction. The frontend already has the catalog, formatters and source disclosures.
See ../../../ROADMAP.md and ../../../.agent/PLANS.md.
Pre-existing changes: frontend/next-env.d.ts and the two untracked backend runtime
reports (canary-aapl_guarded_live_20261010_111844_3580610-publication.json and
refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json). Preserve their
bytes; initial SHA-256 fingerprints recorded in the execution output.

## Constraints
No services, live network/provider requests, persistent database changes, activation,
configuration changes or Git staging/commit/push. Original SEC evidence is untouched.
Reuse formulas, units, authorization and provenance without weakening them.
Tests use synthetic objects and mocked read sessions; existing disposable offline
test facilities are permitted, but no application database is contacted.

## Non-goals
Market data, valuations, rankings, inferred cross-company economic equivalence,
quarter/YTD substitution, activation infrastructure and later roadmap features.

## Implementation stages
1. Add an additive annual response contract, exact-window service selector and GET.
2. Add strict client scope validation and an accessible comparison section.
3. Add focused offline regressions, run relevant suites, type/lint/whitespace checks.
4. Self-review and verify preservation, record results and stop for coordinator review.
Recovery is reverting only CC-01 changes; no durable data or configuration changes.

## Decisions
- 2026-10-12: Annual choices use the existing reporting anchors and normalized fiscal
  end-year semantics, not source filing fiscal annotations. A unique window is required;
  missing/ambiguous years return unavailable metrics and no guessed dates.
- 2026-10-12: Every company has its own publication version. Pin discovery and
  selected-year requests to that version; never claim an atomic cross-company snapshot.
- 2026-10-12: Warn for any differing reporting dates, display economic bases without
  claiming equivalence, and perform no client financial calculations.

## Discovered issues
- Exact reporting anchors can exist even when revenue scope is rejected; keep the
  annual window and preserve the unavailable value and rejected-source alternatives.
- Adding an empty company slot must immediately hide the previous comparison.
  Scope-key rendering and cancellation guard this independently of network aborts.
- Failed coverage discovery is distinct from verified absence of annual periods.
- No issue requires expanded scope. Live visual/API acceptance remains unverified.

## Progress
- [x] Verify baseline, relevant contracts and preservation fingerprints.
- [x] Implement additive backend endpoint and offline tests.
- [x] Implement frontend and mounted interactions.
- [x] Run checks, self-review and preservation verification.

## Test and validation strategy
Exact/missing/ambiguous years; 52/53-week calendars; company/FY/version isolation;
scope rejection, missing/negative cash flow, provenance and legacy endpoint parity.
Mounted controls, limits/duplicates, date warnings, stale response/cancellation and
error recovery. Use existing Node/ReactDOM/jsdom facilities. Run tsc without emitting
or incremental files, selective lint, Python syntax checks and git diff --check.
Do not run Next build because it can overwrite the protected next-env.d.ts.
Actual commands/results will be recorded after execution.

Interim validation (2026-10-12): backend CC-01 + authorization regression: 98 passed;
frontend CC-01/API/research/mounted suites: 109 passed; TypeScript and selective ESLint
passed. One frontend assertion initially expected a generic HTTP message although
the existing API preserves the supplied error detail; corrected the assertion.
Additional numerator/input isolation tests were included in final verification below.

Final verification (2026-10-12):
- Working directory backend: `.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider
  tests/test_company_comparison.py tests/test_revenue_scope_authorizations.py -q`:
  **101 passed** (22 CC-01, 79 authorization regressions). No live database or external
  clients; CC-01 uses synthetic objects and SELECT-only mocked sessions. Existing
  Starlette TestClient/httpx deprecation warning remains.
- Working directory frontend: `node --test tests/company-comparison.test.mjs
  tests/finlens-api.test.mjs tests/research.test.mjs tests/research-interactions.test.mjs`:
  **111 passed**, zero failures/skips (26 CC-01 tests). Includes four-company bounded
  retrieval, keyboard controls/disclosures, stale response/cancellation, provenance
  isolation and the existing mounted Home/research interactions. Existing Node module
  type warnings remain. Narrow layout is checked structurally/CSS, not by a real browser.
- Working directory frontend: `.\node_modules\.bin\tsc.cmd --noEmit --incremental false`
  and `.\node_modules\.bin\eslint.cmd app/page.tsx lib/finlens-api.ts
  lib/company-comparison.ts components/company-comparison.tsx`: passed.
- Working directory repository root: `git diff --check`: passed. Read-only Python
  trailing-whitespace/EOF checks on all five new files and AST parsing on the four
  touched Python files: passed. Git no-index check returns a difference exit status
  for new files; independent explicit whitespace validation avoids confusing that
  status with a whitespace error.
- SHA-256 of protected next-env.d.ts and both runtime reports matches the initial
  values. Production selection/denominator/withdrawal/evidence-policy registries and
  global Revenue equivalences remain empty (asserted by the offline tests).
- Self-review confirms the diff only adds selection/validation/presentation; no
  existing observation formulas, mappings, authorization contents or endpoint fields
  changed. Per-company publication versions are independent, not an atomic universe
  snapshot. No inference of cross-company equivalence or numeric rankings.

## Completion criteria
Focused checks pass; no financial-engine changes; production permissions stay empty;
protected fingerprints match; no staging/push; scope and live limitations documented.

## Final outcome
Implemented one additive GET endpoint and an annual 2–4 company comparison section.
Discovery returns observed end-year labels without financial values. A requested
year resolves one unique existing reporting window and seven existing observations;
missing/ambiguous windows remain unavailable. Date and basis differences are visible,
with source disclosures and SEC links. No source amounts are inferred or recalculated
in the client. Latest shared observed label is preferred; the union remains selectable
with explicit missing coverage. Company selection and refresh pin discovery and
selected-year results to each company's version; cancellation and request keys prevent
stale publication. Financial unavailable states remain distinct from transport failure.

Changed files: backend/app/main.py, backend/app/financial_metrics_service.py,
backend/app/financial_metric_schemas.py, backend/tests/test_company_comparison.py;
frontend/app/page.tsx, frontend/app/globals.css, frontend/lib/finlens-api.ts,
frontend/lib/company-comparison.ts, frontend/components/company-comparison.tsx,
frontend/tests/company-comparison.test.mjs, and this completed plan.

Git: main remains d01ed5a46791274c93ebfdb132a2be0617c15591, matching local origin/main;
six tracked CC-01 files modified and five CC-01 files new; index empty. The pre-existing
next-env.d.ts change and two runtime reports remain untouched. No staging/commit/push.
Tracked CC-01 diff: 109 insertions, four deletions; new files are reported separately
because unstaged untracked files are not included by git diff --stat.

No live application, database or actual browser acceptance was run; no services were
started/restarted. Next build was intentionally omitted to preserve next-env.d.ts.
Live acceptance needs a running database/backend with the new route loaded (reload or
restart as appropriate) and a frontend serving the updated code. Production frontend
acceptance additionally requires its normal build/restart, separately authorized.
No migration, configuration or activation dependency exists for CC-01.
Stop at coordinator review before any Git staging.
Suggested commit: feat: add annual company comparison with evidence lineage.
