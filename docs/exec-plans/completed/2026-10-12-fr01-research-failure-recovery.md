# FR-01: Research Failure Recovery

Status: completed within authorized FR-01 implementation and Astra P2 correction
offline scope; coordinator review and live acceptance pending.
Roadmap phase: bounded recovery correction to existing Research Mode.

## Objective
Recover catalog, initial publication checks, filing discovery and snapshots through
explicit accessible retries. Keep direct answers independent of filing discovery,
without weakening publication, company, query or evidence isolation.

## Current architecture and context
Baseline main and local origin/main: cab7737a84629afe5889ee01450f4dfed7671d49.
The coordinator approved the read-only FR-01 design. Read AGENTS.md and .agent/PLANS.md.
The catalog mounts once; freshness has only focus/visibility/five-minute recovery;
source discovery gates the form; accession keys remount direct answers; rejected
snapshot promises remain cached. Existing versioned controllers and mounted tests
provide the safety boundary. CC-01 retains separate per-company pins.

## Constraints
Only the seven approved frontend files and this ExecPlan may change. No backend,
shared API client, dependencies, formulas, permissions, database, source/provider
requests, service/build/configuration changes or Git staging/commit/push.
Preserve frontend/next-env.d.ts and both untracked AAPL runtime reports.
Starting SHA256: next-env F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0;
canary A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C;
discovery F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C.

## Non-goals
Global timeouts, automatic retry policies, broader inventory/financial audits,
new research features, live acceptance and deployment.

## Implementation stages
1. Confirm baseline and protected hashes; record approved scope.
2. Add bounded explicit catalog/freshness/source/snapshot recovery.
3. Isolate direct-answer state from accession-dependent evidence and AI state.
4. Add mounted regressions and run relevant frontend/API/CC-01 suites.
5. Type/lint/diff checks, self-review and preservation; stop for coordinator review.

## Decisions
- Unknown publication stays null; zero is valid. Use existing versioned controllers.
- Manual retries admit one active attempt and never replay generation or evidence.
- Version-change errors invoke existing freshness reconciliation, not an old-pin retry.
- Direct answers depend on company/query/publication; evidence additionally depends
  on filing and retrieval scope. Preserve valid direct results when sources recover.
- Cache rejection removes only the exact failed entry; successful/pending sharing stays.
- On DATA_VERSION_CHANGED, temporarily expose null and cancel any freshness check
  that predates the mismatch. Coalesce concurrent mismatches. Require a matching
  publication newer than the rejected pin before restoring versioned work; a stale
  freshness result must not cause an automatic rejected-pin request loop.
- An ordinary later freshness outage retains the previously verified pin and loaded
  research. A successful same-pin manual check does not refetch dependent research.
- Company-wide evidence also requires successful current-version source discovery
  with indexed filings. Failed/unknown discovery permits only pinned direct answers.
- P2 correction: the existing versionedController stores the callback supplied by
  each request scope. Bind that callback to the rendered, verified publication
  using useCallback dependencies. Compare that immutable originating version to
  latest.current only to determine obsolescence; never derive rejectedVersion from
  mutable latest state. Ignore obsolete/unmounted/unknown callbacks. A matching
  callback still rejects its own publication and uses the existing coalesced check.
  The callback remains stable for repeated freshness checks at the same publication.

## Discovered issues
Astra identified a pre-commit race: a publication-1 request can return 409 after
freshness synchronously verifies 2 but before React cancels the old request. The
stable mismatch callback reads latest.current and incorrectly rejects 2. Reopened
this plan to first reproduce 0->1 and 1->2 under normal React and StrictMode, then
bind callback invalidation to its originating publication without changing shared
API contracts. Only freshness, mounted tests and this plan may change in this turn.

The old freshness callback retained the rejected pin during reconciliation and could
accept a check started before the mismatch. This could permit old-pin submission
or repeated fan-out after a stale check. The null reconciliation state, cancellation
and rejected-version guard address this within the approved freshness module.
The accession/scope remount key erased independent direct answers. Replace it with
company ticker/CIK identity and separate direct/evidence request scopes; evidence
changes cancel only evidence and unmount its AI result. Query/company/publication
changes still invalidate both branches. No changes outside the approved scope needed.

## Progress
- [x] Baseline/instructions and protected SHA256 verified (2026-10-12).
- [x] Implement scoped recovery and lifecycle isolation (2026-10-12).
- [x] Add 33 mounted recovery regressions and one rendering regression; existing
  tests retained and all frontend suites passed (2026-10-12).
- [x] Type/lint/diff/self-review and protected-file reconciliation (2026-10-12).
Next safe action: coordinator review of this uncommitted patch. No further work,
services, production build or live requests are authorized by this implementation task.

P2 follow-up progress (2026-10-12):
- [x] Recheck root instructions, callback ownership, baseline and protected hashes.
- [x] Add four deterministic pre-commit interleaving regressions and demonstrate failures.
- [x] Apply minimal originating-publication callback correction; retain rejection guard.
- [x] Negative tests, full relevant frontend tests, type/lint/diff and preservation.
- [x] Record final outcomes, close offline plan and stop for coordinator review.

## Test and validation strategy
Existing ReactDOM/JSDOM harness with controlled same-origin fetch and ignored-abort
delivery. Cover manual recovery, pins 0/1/null/malformed/wrong company, StrictMode,
delayed checks, double clicks, rapid switching, concurrent 409 reconciliation,
failed cache replacement, direct answers during source failure/recovery, evidence/AI
invalidation, focus and unchanged CC-01. Run relevant frontend suites, nonemitting
TypeScript, selective ESLint and git diff --check. No production build or live services.

Prior FR-01 final checks, 2026-10-12, working directory frontend:
- `node --test --test-reporter=spec tests/*.test.mjs`: 168 passed, zero failed,
  cancelled or skipped. Includes 97 mounted research tests (33 FR-01 additions),
  27 CC-01 comparison tests, 21 API-client tests, nine evidence-presentation tests,
  and 14 research rendering/helper tests. All requests are controlled test fixtures;
  the CC-01 serialization fixture uses an in-process backend serializer, not a service.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0.
- `node node_modules/eslint/bin/eslint.js app/page.tsx components/company-overview.tsx components/research-freshness.tsx components/filing-research.tsx components/financial-research.tsx`: exit 0.
- Root `git diff --check`: exit 0. Git reported only line-ending conversion notices.
- Earlier targeted mounted suite: 93 passed; final four additions raised it to 97.
  Initial FR-01-only run: 29 passed. No failing test run occurred.
- Node printed existing MODULE_TYPELESS_PACKAGE_JSON notices; no dependency/config
  changes made for them.

Self-review: reviewed all five implementation diffs, test harness changes and
regressions. Verified cancellation ownership, synchronous retry admission, strict
cache-entry identity, null-versus-zero guards and separate answer/evidence lifecycle.
Unchanged CC-01 and shared API-client tests passed. Protected SHA256 values match
their starting values exactly; index empty, HEAD/local origin/main still cab7737.
No backend/shared financial code, APIs, registries, provenance or formula edits.

P2 correction actual checks (2026-10-12, working directory frontend unless noted):
- First draft race run: four failed at a test DOM word-boundary assertion; corrected
  that assertion before evaluating the actual raced callback behavior.
- `node --test --test-reporter=spec --test-name-pattern='FR-01 P2 obsolete' tests/research-interactions.test.mjs`
  before implementation: zero passed, four failed at "Obsolete mismatch must not
  start reconciliation". Both 0->1 and 1->2 failed in normal React and StrictMode.
- `node --test --test-reporter=spec --test-name-pattern='FR-01 P2 current' tests/research-interactions.test.mjs`
  before implementation: four passed, zero failed. Controls preserve null/rejected-pin
  blocking and one reconciliation request when three current 409s arrive before commit.
- `node --test --test-reporter=spec --test-name-pattern='FR-01 P2' tests/research-interactions.test.mjs`
  after correction: eight passed, zero failed. Then strengthened the four obsolete
  regressions to also reject the newly committed publication through its own callback.
- `node --test --test-reporter=spec tests/*.test.mjs`: 176 passed, zero failed,
  cancelled or skipped. Includes 105 mounted research tests, all original 33 FR-01
  mounted regressions, eight P2 additions, 27 CC-01, 21 API-client, nine evidence
  presentation and 14 rendering/helper tests. No live service needed or contacted.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0.
- `node node_modules/eslint/bin/eslint.js components/research-freshness.tsx`: exit 0.
- Root `git diff --check`: exit 0. Existing line-ending/module-type notices only.

The race harness resolves already-parsed response fixtures within one outer act;
microtask draining does not yield to a timer or flush a separate response act.
Catalog reconciliation proves the newer freshness callback already assigned latest;
old DOM publication and non-aborted old signals prove React has not committed yet.
Late 409 then leaves the newer pin usable without another check or duplicate fan-out.
Ignored-abort old replies after commit remain isolated. A mismatch from a request
using the newly committed pin still fails closed, ruling out a permanently stale
callback. Negative controls also cover current pins 0/1 and manual same-pin rejection.

P2 self-review: callback identity is captured with its originating publication;
mutable latest is read solely for equality, before any invalidation mutation. Unknown
uses an explicit null check and zero remains valid. Matching simultaneous callbacks
retain the existing invalidation/pending guards; stale callbacks do nothing. The
shared client's 409 rejection, error throw and abort checks are unchanged. Existing
company-switch, delayed-response, source/direct/evidence and snapshot tests passed.
SHA256 rechecked against this turn's starting values for both reports, next-env and
the five other approved FR-01 files: all unchanged. No scope expansion needed.

## Completion criteria
Offline checks pass; no invented/unpinned research; stale responses cannot publish;
retry is bounded; direct answers survive unrelated source recovery; protected hashes
and out-of-scope files unchanged; actual validation recorded; no staging/commit/push.

## Final outcome
Implemented retries for catalog, freshness, sources and selected snapshots. Initial
freshness copy accurately reports unavailable publication identity. Source failures
remain distinct from successful empty results, while verified pinned direct research
stays usable and survives source recovery. Failed cache entries are evicted without
automatic requests, and older rejections cannot evict replacements. All offline gates
passed, with no implementation blocker or scope expansion.

Modified: frontend/app/page.tsx; frontend/components/company-overview.tsx;
frontend/components/research-freshness.tsx; frontend/components/filing-research.tsx;
frontend/components/financial-research.tsx; frontend/tests/research-interactions.test.mjs;
frontend/tests/research.test.mjs. Created only this completed FR-01 record.
Current cumulative frontend diff: seven files, 611 insertions and 55 deletions. This untracked plan
is additional and not included by git diff --stat. Existing modified next-env.d.ts
and two untracked AAPL reports retain their exact original bytes/status. Nothing
staged, committed or pushed; no services started/restarted, DB writes or provider,
SEC, refresh, activation or production-configuration operations performed.

Limitations: no production build or real browser/HTTP acceptance. Native retry
button semantics/focusability and live-region feedback were tested in JSDOM; real
keyboard/focus continuity, visual states and end-to-end failure simulation remain
live acceptance needs after coordinator review. Existing/served frontend and API
would be needed then; offline tests required neither service. Request timeouts remain
a separately bounded follow-up. Astra's confirmed P2 is corrected; independent
re-review of this correction and real browser acceptance remain pending.
Suggested commit: `fix(frontend): make research load failures recoverable`.

P2 turn outcome: modified only frontend/components/research-freshness.tsx,
frontend/tests/research-interactions.test.mjs and this FR-01 ExecPlan. The correction
adds publication ownership to mismatch callbacks without changing the shared API
contract, rejected-version guard or other FR-01 behavior. Eight new deterministic
regressions pass and all 176 frontend tests pass. No known offline blocker remains.
Next action belongs to coordinator review; no further changes or live operations.
