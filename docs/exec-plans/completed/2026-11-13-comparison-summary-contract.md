# Company comparison summary contract regression

Status: completed; bounded offline correction independently reviewed
Roadmap phase: scoped correctness maintenance of delivered Research Mode comparison

## Objective

Resolve the reproduced comparison-route regression without changing financial
semantics. Verify the complete public summary payload, additive balance-sheet
ratios, unchanged annual comparison payloads, and existing publication safeguards.

## Current architecture and context

Read root AGENTS.md first, ROADMAP.md, .agent/PLANS.md, engineering standards,
financial contracts, the CC-02 annual expansion and balance-sheet ratio plans.
The [ratio contract](../active/2026-11-04-balance-sheet-ratios.md) explicitly opts the public
summary route into ratios while keeping default internal summaries and the annual
facade unchanged. The route, serializer and dedicated ratio tests implement that
contract. The older comparison test expects an internal summary without opt-in.

HEAD: `17be7b5ba856a6b881a79c2c778bb6bf85eca297`; 57 modified, 111 untracked,
empty index at entry. Dirty-path SHA-256
manifest, raw status and pre-existing accession-service diff retained outside Git
at `D:/Projects/finlens-comparison-summary-offline-20261113/`. Preserve all existing
work, including the reviewed ASCII accession filter and its dedicated tests.

## Constraints

Only backend/tests/test_company_comparison.py and this task's plan may change.
Existing Python and guarded synthetic tests only. No DB operations (including
SQLite), Docker, network, models/providers, credentials, installations, services,
security/settings changes, staging, commit or push. Do not retry or bypass prior
Docker named-pipe or Home spawn denials. Do not modify PG/Home runners, tests,
plans or frontend files.

## Non-goals

No production formula, selector, route, schema, source policy or API changes;
no new comparison features or broader milestone acceptance.

## Implementation stages

1. Reproduce the exact assertion safely and identify the owning product contract.
2. Correct the full-response expectation and cover ratios with/without eligible
   instant operands while retaining all existing endpoint/version assertions.
3. Run focused and relevant guarded financial regressions, inspect the exact
   delta and preservation manifest, and stop for separate Astra review.

Recovery: remove only this task's test delta and new plan; no product/data rollback.

## Decisions

- 2026-11-13: Correct a stale test expectation. The public route deliberately
  passes include_balance_ratios=True; removing that opt-in would regress the
  established additive product contract. Keep full response equality rather
  than discarding the additional field or relaxing comparison to a subset.
- Add a positive instant-input variant with a newer date than annual revenue:
  ratios use their independent as-of date, not the annual reporting interval.
  Check literal values and source IDs as well as complete service serialization.

## Discovered issues

The exact original test fails at line 400: seven common summary fields match,
but the public response additionally contains balance_sheet_ratios. No product
defect was found in this mismatch. The dedicated ratio tests and owning plan
explicitly require this field on the public summary and omit it by default.

## Progress

- [x] Read guidance, inspect current status/code/contracts and preserve baseline.
- [x] Reproduce the original assertion failure under the existing offline guard.
- [x] Correct and strengthen the focused route regression.
- [x] Run focused/regression checks and self-review/preservation verification.
- [x] Freeze for separate Astra review; no new work after this slice.
- [x] 2026-11-13: Record independent Astra review and complete documentation-only
  closure; preserve frozen test/product bytes and concurrent work.

## Test and validation strategy

All test commands run from D:/Projects/finlens-foundation/backend with
`.venv/Scripts/python.exe -I -S -B tests/run_sec_reader_offline.py`.
The unchanged runner blocks env-file reads, real DB connections (including
SQLite), external network/DNS, models and provider clients, and disables pytest
cache. TestClient exercises ASGI in process with fake read-only sessions;
Windows asyncio wakeup sockets are the runner's existing narrow exception.

Actual pre-change command suffix:
`tests/test_company_comparison.py::test_api_exact_year_choices_version_pin_and_existing_endpoints`:
**1 failed**, at the full summary assertion, with the existing Starlette/httpx
deprecation warning. No DB/network connection was attempted or denied.

Actual post-change command suffixes and results (same executable/flags/guard):

| Invocation suffix | Result |
|---|---|
| `tests/test_company_comparison.py::test_api_exact_year_choices_version_pin_and_existing_endpoints` | 2 passed; both new parameter variants. |
| `tests/test_company_comparison.py tests/test_balance_sheet_ratios.py tests/test_metric_accession_validation.py tests/test_financial_insights.py tests/test_quarter_window_comparison.py` | 281 passed, zero failures/skips. |
| `tests/test_financial_metrics.py -k c5` | 100 passed, 118 deselected, zero failures/skips. |

The two regression invocations cover 381 distinct passing cases. Focused results
are repeated within that count, not additive. The only warning is the existing
Starlette/httpx TestClient deprecation. Final regression stdout/stderr are retained
as regression.stdout.txt / regression.stderr.txt and c5.stdout.txt / c5.stderr.txt
under the external evidence directory. No guard denial occurred in these runs.

Not run: the 118 deselected financial-metrics cases (including SQLite fixtures),
full repository suites, live HTTP server/browser/frontend checks, actual DB/PG,
Docker, SEC/provider/source-authority or deployment/production acceptance.

## Completion criteria

Focused contract and relevant guarded regressions pass; no assertions weakened,
product behavior unchanged, exact two-file delta reviewed and unrelated bytes
preserved. Independent Astra review has no actionable findings. These bounded
criteria are satisfied; broader product acceptance and Git delivery remain separate.

## Final outcome

The mismatch is a stale test expectation, not a demonstrated product bug.
Exactly two task paths changed: backend/tests/test_company_comparison.py and this
new plan. The test still compares the entire response, now using the documented
summary opt-in. Both variants retain the existing discovery/selected-year/history
and stale-publication assertions. New checks require no ratios on annual facade
responses or default internal summaries; require explanatory unavailable ratios
without operands; and verify exact 0.25/zero-cash values, selected fact IDs and
independent 2026-03-31 ratio dates against 2025-12-31 annual revenue.

No application module, formula, eligibility rule or prior test was removed or
weakened. The ASCII accession change and its dedicated tests remain intact.
Self-review inspected the complete diff against the owning ratio/annual contracts;
scoped git diff --check passed. All 168 original dirty paths matched their initial
SHA-256 values at preservation verification, including PG/Home files. HEAD stays
17be7b5ba856a6b881a79c2c778bb6bf85eca297, with zero staged paths and no commit/push.
The implementation-stage final worktree had 58 modified and 112 untracked paths.

## Independent review and closure — 2026-11-13

The coordinator's closure instruction reports independent Astra review in chat
`01a1d254-40dd-7ff3-9152-03423c667bbb`: no actionable findings, 92 guarded tests
independently passed, and all 170 then-dirty file hashes remained unchanged. The
review did not repeat the full 381-case implementation run. These are distinct
review and implementation results, not additive test counts. The coordinator
provided the review result; this closure did not rerun or reconstruct its commands.

The delivery subset assessment identified this plan's missing closure as the
remaining documentation gap. This follow-up changes and moves only this plan to
completed, fixes its relative ratio-contract link, and records the review. It
does not edit the frozen comparison test, product files or concurrent work.
No tests were rerun for this documentation-only closure; the implementation and
review evidence above retain their original scope and limitations. No broader
integration, live-service, database, browser or production acceptance is implied.

Closure checks: `git diff --no-index --check -- /dev/null
docs/exec-plans/completed/2026-11-13-comparison-summary-contract.md` passed from
the repository root; the corrected ratio-contract target exists and the former
active plan is absent. All 183 other dirty-file SHA-256 values match the closure
entry snapshot, including the frozen comparison test and product files. HEAD is
unchanged; current status is 62 modified, 122 untracked files, zero staged paths.
Nothing was staged, committed or pushed. The coordinator-owned delivery assessment
still references the old active path; updating that incoming link is outside this
plan-only authorization and is handed back with the new completed path.

Suggested commit: `test(comparison): align summary regression with balance-sheet ratio contract`.
