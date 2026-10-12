# CC-01: two Astra P2 corrections

Status: completed (offline correction; coordinator review pending)
Roadmap phase: bounded CC-01 correction; no additional functionality.

## Objective
Accept date-compatible 52/53-week Revenue YoY operands across calendar end-year
rollovers, and expose cash-flow-only annual years without relaxing window ambiguity.

## Current architecture and context
HEAD main d01ed5a46791274c93ebfdb132a2be0617c15591; CC-01 remains unstaged.
Preserve its existing changes, frontend/next-env.d.ts and both runtime reports.
The backend observation() already uses start/end gaps of 357–378 days and duration
difference at most nine days for Revenue YoY. The client incorrectly assumes adjacent
calendar end-year labels. CC-01 discovery incorrectly uses revenue-first reporting_periods.
See ../../../.agent/PLANS.md and the prior completed CC-01 plan.

## Constraints and non-goals
No formulas, mappings, global reporting_periods behavior, authorization or production
registry changes. No database/network/provider I/O, services, build, configuration,
SEC evidence modifications, staging, commit or push. No unrelated refactoring.

## Implementation stages
1. Add reproductions for rollover validation and cash-flow-only year selection.
2. Correct only client prior-period validation and CC-01 annual anchor discovery.
3. Run focused prior/new offline suites, type/lint/whitespace, preservation checks.
4. Self-review, record results and stop for coordinator review.

## Decisions
- Reuse metric_periods across all seven CC-01 metrics and deduplicate exact windows;
  do not modify revenue-first anchors used by existing endpoints.
- Match the existing backend YoY date tolerances, retaining the prior operand's own
  end-year label and exact source/input identities. Never compute financial values.
- Exercise a fresh serialized synthetic backend response through the client validator.

## Discovered issues
Only the two reproduced P2 findings are in scope.

## Progress
- [x] Inspect actual Git state, affected contracts and existing tests.
- [x] Add regressions and confirm the defects before correction.
- [x] Correct both defects and run focused validation.
- [x] Verify preservation and complete self-review (final whitespace/hash checks below).

## Test and validation strategy
Positive: 2022-12-31 → 2024-01-06 annual Revenue YoY = 0.25; FY2024 OCF 9,
CapEx 3, FCF 6 despite FY2025-only revenue. Negative: out-of-range start/end gaps,
duration mismatch, nonannual/mislabeled inputs, incompatible cash-flow windows.
Use pure synthetic FinancialMetrics fixtures and existing Node/React test harness.
Run CC-01 + authorization backend suites, relevant frontend suites, nonemitting
TypeScript, selective ESLint, syntax and whitespace checks. No live DB or API.

## Completion criteria
Both reproductions pass after fixes; negative and previous CC-01 tests pass; protected
hashes and production registries unchanged; no unrelated modifications or staging.

## Final outcome
Both defects reproduced before correction: five new backend cases failed because
revenue-first discovery hid annual cash-flow windows; the serialized backend rollover
response had YoY 0.25 and was rejected by the frontend. After correction, all pass.

Code changes are limited to backend/app/financial_metrics_service.py and
frontend/lib/company-comparison.ts. Tests extended only in
backend/tests/test_company_comparison.py and frontend/tests/company-comparison.test.mjs.
No global reporting_periods, observation(), formulas, mappings or permissions changed.

The frontend validates prior operands using their own correct fiscal end-year and
the existing backend start/end-gap range (357–378 days inclusive) and duration
difference (at most nine days). Exact input/source/company/unit/version checks remain.
The backend unions existing metric_periods across seven CC-01 metrics; exact windows
are deduplicated by existing selection logic and multiple windows remain ambiguous.

Validation on 2026-10-12:
- backend working directory: `.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider
  tests/test_company_comparison.py tests/test_revenue_scope_authorizations.py -q`:
  **109 passed** (30 CC-01, 79 authorization), existing TestClient/httpx warning only.
- frontend working directory: `node --test tests/company-comparison.test.mjs
  tests/finlens-api.test.mjs tests/research.test.mjs tests/research-interactions.test.mjs`:
  **112 passed**, no failures/skips. Existing Node module-type warnings only.
  The new cross-layer test invokes the backend test Python environment once, serializes
  a fresh synthetic response and passes it through the real frontend validator.
  It also rejects start/end gaps below/above bounds, ten-day duration mismatch and
  incorrect prior fiscal labels, with source/input dates kept consistently bound.
- frontend working directory: `.\node_modules\.bin\tsc.cmd --noEmit --incremental false`
  and `.\node_modules\.bin\eslint.cmd lib/company-comparison.ts`: passed.
- repository root: `git diff --check`, read-only Python syntax/whitespace checks and
  final protected-file SHA-256 comparison: passed. Exact results in execution output.

Self-review: seven-metric union does not merge competing dates or hide a conflicting
cash-flow window behind revenue. Existing latest summary and reporting_periods
semantics stay unchanged. Negative and prior CC-01 isolation/version tests pass;
all four production permission registries and Revenue equivalences remain empty.

No live database/API/browser acceptance or Next build performed, and no services
started. No SEC/provider/model I/O, database writes, migrations, refreshes or activation.
Protected next-env.d.ts and both runtime reports retain their original SHA-256.
Original evidence, receipts and activation/Tiingo infrastructure untouched.

Git remains main d01ed5a46791274c93ebfdb132a2be0617c15591. Prior CC-01 changes
remain uncommitted and unstaged; this correction adds only this plan to its file list.
No known remaining blocker for these two corrections; coordinator review and live
acceptance are still pending. Stop without staging, commit or push.
Suggested commit after review: fix: preserve annual comparison coverage and week-calendar YoY.
