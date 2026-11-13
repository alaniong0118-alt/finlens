# Canonical SEC accession eligibility for normalized metrics

Status: completed; bounded offline correction only
Roadmap phase: scoped correctness repair of delivered Phase 2/3 Research Mode.

## Objective

Reject non-ASCII SEC accession identities before normalized fact selection. Malformed
newer observations must not displace usable canonical sources or feed calculations.
Canonical ASCII observations retain their exact values and provenance.

## Current architecture and context

Read root AGENTS.md, ROADMAP.md, .agent/PLANS.md and engineering standards first.
`backend/app/financial_metrics_service.py:usable` admits detached/database facts to
the shared deterministic engine. Its accession regular expression uses Unicode
`\d`, which may admit identities outside EDGAR's ASCII accession format. The
existing URL builder interpolates this identity directly into source URLs.
Reproduce this issue with detached synthetic facts before changing eligibility.

HEAD at start: `17be7b5ba856a6b881a79c2c778bb6bf85eca297`. Exact initial dirty-path
hashes/status and initial service diff are recorded in
`D:/Projects/finlens-metric-accession-offline-20261113/`. The service is initially
clean. Numerous unrelated pending changes, including concurrent PG commissioning
and Home capability work, must be preserved. No nested AGENTS.md or .agents skills
directory was found under the relevant backend scope.

## Constraints

Only this plan, `backend/app/financial_metrics_service.py`, and a new dedicated
`backend/tests/test_metric_accession_validation.py` may change. No schema, source
rights/admission, custody, API/grammar or source acquisition changes. No network,
credentials, database/daemon/Docker access, installation, production data, security
settings, commit or push. Stop denied actions without escalation or rerouting.

## Non-goals

No general URL-builder rewrite, provenance authority expansion, new financial
definitions, live-data/browser acceptance, or full milestone/release completion.

## Implementation stages

1. Add detached synthetic regression cases; observe failure with current code.
2. Narrow accession digit eligibility to ASCII at the existing fact boundary.
3. Run dedicated and relevant offline financial regressions under the existing
   guarded runner with bytecode and pytest cache disabled.
4. Obtain independent fresh-context review, fix findings, inspect exact delta and
   preservation hashes, then record completed evidence and limitations.

Rollback is removal of this task's new files and its isolated service edit only.

## Decisions

- 2026-11-13: Keep existing source/authority policy and formula semantics; validate
  the already-required SEC accession format before ranking, rather than merely
  hiding a malformed source link after selection. Accession submitter CIK need
  not equal issuer CIK; do not add that restriction.

## Discovered issues

Reproduced: Python Unicode digit classes admit Arabic-Indic and fullwidth numerals
in every accession component, including mixed alphabets. A malformed newer
observation with value 999 displaced the valid canonical observation with value
100, and malformed operands produced available net-margin/free-cash-flow results.
The eligibility change refuses those observations before source capture/ranking.

The first post-fix run exposed an error in the new test itself: history uses the
`history` field, not `points`. Corrected the test to the actual schema; no history
production behavior changed.

A broad `-k 'accession or c5'` selector accidentally included five existing SQLite
fixtures. The offline guard refused all five connections; no database connection
occurred. Do not rerun those fixtures or remove the guard. The subsequent explicit
`-k c5` run selected only the intended detached cases.

The existing company-comparison route assertion at
`backend/tests/test_company_comparison.py:400` expects a summary without the
existing optional `balance_sheet_ratios` field, while the current route includes
it. It fails identically when only this task's regex change is restored to its
pre-task implementation in an isolated guarded Python process. This is an
existing working-tree mismatch, not a pristine-HEAD/full-suite acceptance claim.
Its owning test/route are outside this task and remain unchanged.

## Progress

- [x] Inspected governing guidance, roadmap, relevant active plans/code/tests and Git.
- [x] Reproduce malformed identity eligibility with failing focused tests.
- [x] Implement minimal repair and pass dedicated/core regression selections.
- [x] Attribute the separate existing route-assertion failure without changing it.
- [x] Independent review, preservation and scope checks.

## Test and validation strategy

From `backend`, use `.venv/Scripts/python.exe -I -S -B
tests/run_sec_reader_offline.py` with explicit paths and `-p no:cacheprovider`.
The runner blocks .env reads, network/DNS, real PostgreSQL and SQLite connections,
models and OpenAI. All fixtures are detached synthetic records, never live SEC or
database acceptance. Cover Unicode/mixed digits in every accession component,
malformed-only refusal, valid fallback ranking, and derived-input refusal, plus
canonical positive controls and surrounding existing pure financial regressions.

## Completion criteria

Reproduced failure precedes repair; dedicated tests and relevant regressions pass;
independent review resolved; only the three task paths change relative to start;
unrelated initial dirty bytes remain intact except identified concurrent work.

## Final outcome

Completed one-line eligibility repair plus 21 dedicated regression cases and this
plan. Exact new delta:

- `backend/app/financial_metrics_service.py`: one line replaced; the ten/two/six
  accession components accept ASCII digits only.
- `backend/tests/test_metric_accession_validation.py`: new detached synthetic tests.
- `docs/exec-plans/completed/2026-11-13-metric-accession-validation.md`: this record.

All commands below ran from `D:/Projects/finlens-foundation/backend`, using
`.venv/Scripts/python.exe -I -S -B` and the guarded runner. No package downloads,
model/provider/SEC calls, daemon startup, credentials or real DB operations.

| Actual invocation after Python flags | Actual result |
|---|---|
| `tests/run_sec_reader_offline.py tests/test_metric_accession_validation.py --maxfail=2` before fix | 2 failed at original eligibility assertions; stopped as requested by flag. |
| `tests/run_sec_reader_offline.py tests/test_metric_accession_validation.py -k 'malformed_newer or malformed_operand'` before fix | 11 failed, 10 deselected; wrong-value ranking and derived availability reproduced. |
| Dedicated test file, initial post-fix invocation | 14 passed, 7 failed due to new test's incorrect history field; corrected to actual schema. |
| `tests/run_sec_reader_offline.py tests/test_metric_accession_validation.py tests/test_financial_metrics.py -k 'accession or c5'` | 121 passed, 113 deselected, 5 setup errors from guard-blocked SQLite fixtures; affected actions stopped. |
| `tests/run_sec_reader_offline.py tests/test_financial_insights.py tests/test_company_comparison.py tests/test_balance_sheet_ratios.py tests/test_quarter_window_comparison.py` | 258 passed, 1 existing summary assertion failure described above. |
| `tests/run_sec_reader_offline.py tests/test_metric_accession_validation.py tests/test_financial_insights.py tests/test_balance_sheet_ratios.py tests/test_quarter_window_comparison.py` | 219 passed, no skips/failures. |
| `tests/run_sec_reader_offline.py tests/test_financial_metrics.py -k c5` | 100 passed, 118 deselected, no skips/failures. |
| `D:/Projects/finlens-metric-accession-offline-20261113/baseline_regression_probe.py` | The same single comparison assertion fails under the restored pre-task regex; the isolated process makes no checkout edits. |
| Independent fresh-context review: guarded dedicated file | 21 passed; no actionable code/test findings, no reviewer edits. |

The final two green parent invocations total 319 distinct passing cases; the
earlier broader invocation also observed 60 distinct passing company-comparison
cases and its one retained failure. Counts across repeated runs are not additive.
Existing Starlette/httpx deprecation warnings remain. The baseline probe and
final focused/core stdout receipts are retained under the external receipt path;
earlier failure output is recorded in this chat and summarized here.

Self-review and independent review confirm no new source rights, custody or
authority; existing canonical source policy and Decimal/formula behavior remain.
`git diff --check -- backend/app/financial_metrics_service.py` passed. At the final
preservation check all 165 original dirty-path SHA256 values matched, including
concurrent PG/Home files; HEAD stayed `17be7b5ba856a6b881a79c2c778bb6bf85eca297`.
Only the three task paths are added to initial status. Nothing staged, committed
or pushed. Final worktree: 57 modified, 111 untracked, zero staged.

Not run: live SEC/rights/custody validation, DB/PG/Docker, browser/HTTP servers,
frontend build, external network, provider and full repository acceptance. Prior
Home worker EPERM and Docker named-pipe denial were not retried or bypassed.
No current production exposure or affected real rows is claimed. Runtime metadata
does not expose an actual model/version, so none is asserted.

Suggested commit: `fix(financials): reject non-ASCII SEC accession identities`.
