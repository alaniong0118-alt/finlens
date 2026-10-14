# DEP-01A2 Increment 1: research request deadline

Status: active; P2 validation-lifetime correction implemented, coordinator/Astra re-review pending
Roadmap phase: bounded release enabling task DEP-01A2 Increment 1

## Objective

Bound existing non-AI frontend research requests to 30 seconds across fetch,
body consumption and transport validation. Caller cancellation remains AbortError;
deadline expiry is FinLensApiError(0, REQUEST_TIMEOUT). Late completions must not
return data or invalidate publication ownership.

## Current architecture and context

`frontend/lib/finlens-api.ts` centralizes JSON transport and publication headers.
Mounted synthetic React tests already exercise manual retry, caches, independent
branches and version ownership. Starting HEAD, main and origin/main all equal
`be6228bb68506b3c12b2f66386ed4baaede745ad`.
Expected pre-existing changes: modified `frontend/next-env.d.ts`; untracked
`backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json`
and `backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json`.
Their SHA256 fingerprints were captured before edits for final preservation checks.

## Constraints and non-goals

Only Increment 1 is authorized. No backend, database, financial or security
admission changes; no services, providers, network requests, migrations, deployment,
QA-01 browser acceptance, staging, commits, pushes or cleanup. Preserve original
evidence/receipts and existing working-tree changes. Change components only if a
focused regression proves necessary. AI generation is outside the 30-second deadline.

## Implementation stages

1. Verify baseline, inspect transport and focused tests.
2. Add internal transport cancellation and an independently settling deadline.
3. Cover races, ignored abort, late completion, recovery and cleanup offline.
4. Run focused tests, self-review, verify preservation and stop for Astra review.
Rollback is a reviewable reversal of only this increment's diff; no data work occurs.

## Decisions

- 2026-10-14: Capture scope from the original caller signal, then create an internal
  controller. Race the entire transport against cancellation; keep the first cause
  and guard late continuations before metadata callbacks or data return.
- 2026-10-14: Preserve HTTP and malformed JSON classification; give broken body
  streams a distinct BODY_READ_ERROR instead of treating them as empty JSON.
- 2026-10-14: Check monotonic elapsed time at async/validation boundaries as well
  as racing a timer. A delayed timer cannot permit late data or metadata callbacks.
  Apply this check on rejection as well as successful return.
- 2026-10-14: Settled transports detach caller abort listeners. Updated the existing
  signal-identity assertions and nine mounted cases that previously expected a
  completed request's signal to abort when React later cancelled its caller.
  Pending sibling abort assertions, pre-commit race assertions, publication-pin
  ownership, coalescing and rejected-pin behavior checks remain exercised.

## Discovered issues

The existing transport swallows every body-read failure as null and relies on fetch
honoring caller abort. Both are addressed within this increment.
Initial runs exposed two API signal-identity assertions and nine mounted completed-
signal assertions tied to caller/transport identity. These were adapted to the new
controller boundary; no component correction was necessary.

## Progress

- [x] Baseline and expected working-tree changes verified; relevant instructions read.
- [x] Transport implementation and focused regression tests.
- [x] Offline validation, self-review and preservation checks.
- [ ] Independent Astra review (handoff after implementation; no self-acceptance).

## Test and validation strategy

Synthetic Node API tests and mounted React tests only, with mocked fetch and clocks.
Exercise stalled fetch/body, ignored abort, first terminal cause, late responses,
publication isolation, manual recovery, cache eviction, pending guards and cleanup.
Run the two primary test files, targeted lint and no-emit TypeScript if available.
Record actual commands/results below; do not run browser acceptance or build/start
services. Final `git diff --check` and original-file hashes must match expectations.

### Actual validation (2026-10-14)

From `D:\Projects\finlens-foundation\frontend`, Node v24.21.0:

- `node --test --test-reporter=tap tests/finlens-api.test.mjs tests/research-interactions.test.mjs`
  **206 passed, 0 failed, 0 skipped** (58 API tests and 148 mounted tests).
  New coverage includes 33 API cases and 11 mounted cases, all synthetic/offline.
- `node node_modules/eslint/bin/eslint.js lib/finlens-api.ts`: exit 0, no diagnostics.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0,
  no diagnostics and no emitted/incremental artifacts.

From repository root: `git diff --check` passed. Self-review confirmed changes are
limited to shared frontend transport, the two focused test files and this record.
No component, backend, admission policy, financial, dependency or evidence change.
No browser/API/live-network acceptance was run. The Node API suite emits its existing
MODULE_TYPELESS_PACKAGE_JSON warning; it does not affect the passing test result.

SHA256 preserved before/after:

- `frontend/next-env.d.ts`: `F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0`
- `backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json`:
  `A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C`
- `backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json`:
  `F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C`

## Completion criteria

Implementation and focused offline checks pass, no component changes without proof,
no out-of-scope changes, preserved files unchanged. Independent review remains a
separate gate and no later increment is started.

## Final outcome

Increment 1 implementation and focused offline validation are complete. Shared
transport now owns its controller/deadline and preserves the first terminal cause;
late continuations cannot return payloads or call publication changed callbacks.
Manual retry, failed cache eviction, pending guards, publication ownership and
independent branches pass their mounted regressions in the existing architecture.
AI generation has no new frontend deadline; profile/security admission is unchanged.

Limitations: abort remains best effort for transports/body readers that ignore it;
their late results are blocked and late rejection is handled. JavaScript cannot
preempt a blocked event loop; elapsed-time checks reject when execution resumes.
No live/browser/QA-01 acceptance or later increment is claimed.

Final Git: on main at the original baseline, no staged changes. This increment
modifies `frontend/lib/finlens-api.ts`, `frontend/tests/finlens-api.test.mjs`, and
`frontend/tests/research-interactions.test.mjs`, and adds this untracked active plan.
The original modified next-env file and both untracked backend reports retain their
initial hashes. No staging, commit, push, cleanup, service or data operation occurred.

Suggested commit after independent review:
`fix: bound frontend research requests to 30 seconds (DEP-01A2 Increment 1)`.

STOP: independent Astra review pending. Keep this record active for that review;
do not begin DEP-01A2 Increment 2 or 3.

## P2 targeted correction (2026-10-14)

Astra independently found that capabilities and company-evidence validation ran
after requestJson had cleared its deadline and caller listener. The earlier 206
passing tests did not cover clock expiry during these endpoint validators; the
implementation outcome above is historical and subject to this blocking finding.

HEAD/main/origin/main remain at `be6228bb68506b3c12b2f66386ed4baaede745ad`.
The working tree matches the prior handoff exactly, and all three preservation
hashes above were rechecked and match. No unexpected changes were found.

Authorized correction: pass the two existing synchronous validators into requestJson
and invoke them before its final success checkpoint and cleanup. The existing catch
checkpoint must cover validator exceptions too. Keep the same controller, deadline,
terminal cause, metadata guards and cleanup finally; no transport redesign or scope
expansion is needed. Endpoint predicates and error messages must remain unchanged.

- [x] Add/run focused endpoint-validation deadline regressions, including the three
  reported reproductions, before changing implementation.
- [x] Move endpoint validation inside the existing lifetime and rerun focused tests.
- [x] Run affected existing frontend regressions, lint/types and preservation checks.
- [ ] Stop for coordinator and Astra review; no later increment.

### P2 implementation and decisions

`requestJson` accepts an optional synchronous validator and invokes it in its existing
try/catch/finally, after transport completion but before final success delivery.
It checks cancellation/deadline before and after validation; the existing catch
checkpoint checks validator exceptions before error delivery. The timer and caller
abort listener therefore remain active throughout validation, with a single cleanup
finally for all paths. No new controller, deadline, timer or transport layer was added.

`getCapabilities` and `getCompanyContext` now return that request promise directly
and supply their unchanged validation predicates/messages through the callback.
Company scope still comes from the original caller signal. No endpoint-specific
validation remains in a continuation outside the request lifetime. AI's deadline
opt-out, release capability rules, transport error classifications and publication
metadata callbacks are unchanged.

This correction edits only `frontend/lib/finlens-api.ts`,
`frontend/tests/finlens-api.test.mjs` and this existing ExecPlan.
`frontend/tests/research-interactions.test.mjs` retains its prior Increment 1 edits
without new P2 edits. No scope expansion or component changes were necessary.

### P2 validation actually run

All test commands ran from `D:\Projects\finlens-foundation\frontend`, offline with
synthetic fetch, monotonic clock and timers:

1. Before implementation,
   `node --test --test-name-pattern='DEP-01A2 P2' tests/finlens-api.test.mjs`:
   **18 failed / 0 passed**, including all three Astra reproductions. Valid responses
   incorrectly succeeded; invalid evidence returned EVIDENCE_SCOPE_MISMATCH.
2. After implementation, the same focused command:
   **18 passed / 0 failed / 0 skipped**. Tests cover both validators crossing the
   deadline on success/failure, retained validation errors before deadline, active
   timer/listener during validation, version zero, both first-cause orderings,
   exactly-once cleanup and suppressed late sibling 409 publication callbacks.
3. Only after the focused suite passed,
   `node --test --test-reporter=tap tests/finlens-api.test.mjs tests/research-interactions.test.mjs`:
   **224 passed / 0 failed / 0 skipped** (76 API tests and 148 mounted tests).
   Existing tests retain null/unverified gates, manual recovery, pending guards,
   publication ownership, independent research branches, AI policy and DEP-01A1
   capability admission coverage.
4. `node node_modules/eslint/bin/eslint.js lib/finlens-api.ts`: exit 0, no diagnostics.
5. `node node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0,
   no diagnostics or generated artifacts.
6. Repository-root `git diff --check`: exit 0. Self-review confirmed the validators'
   predicates and error messages are unchanged and the existing finally remains
   the sole timer/listener cleanup path. Rechecked all three preservation hashes;
   each matches the original values recorded above.

No QA-01/browser acceptance, services, network/provider/SEC requests, backend/database
operations, staging, commits, pushes, resets or cleanup occurred. HEAD/main/origin/main
remain the expected baseline. Final status is the same seven paths as the prior
handoff: four modified frontend files (including preserved next-env), two original
untracked backend reports and this untracked active ExecPlan; nothing is staged.

P2 implementation and offline validation are complete. Event-loop blocking still
cannot be preempted; elapsed-time checks now cover endpoint validation when execution
resumes. Independent coordinator/Astra acceptance is pending, and no later increment
has started. Suggested commit after review remains the Increment 1 message above.

STOP for coordinator and Astra review.
