# FD-01: Metric and Filing Discovery

Status: completed (approved implementation and offline validation; coordinator review pending)
Roadmap phase: bounded discovery improvement to existing Research Mode.

## Objective
Expose all 15 existing financial metrics in snapshots, history and guided value
questions. Make recorded filing metadata discoverable without implying searchable
evidence or complete stored text. Preserve financial and publication safety.

## Current architecture and context
Starting main/local origin/main: 1a07c4368aa1757b02adbf546987a50eff032277.
Read root AGENTS.md, ROADMAP.md and .agent/PLANS.md. Coordinator approved the FD-01
read-only proposal. Backend supports all 15 metrics; frontend displays 11 snapshot
metrics and nine history choices. Source discovery discards metadata-only records.
FR-01 including its obsolete-409 correction and CC-01 are completed foundations.
Existing working tree: modified frontend/next-env.d.ts and two untracked AAPL reports.
Protected starting SHA256:
- next-env: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- canary: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- discovery: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints
Only frontend/lib/research.ts, components/financial-research.tsx,
components/filing-research.tsx, lib/finlens-api.ts, app/globals.css,
tests/research.test.mjs, tests/research-interactions.test.mjs,
tests/finlens-api.test.mjs and this ExecPlan may change. No backend/API-contract,
formula, concept/authorization registry or CC-01 changes. No database writes,
network/provider/SEC access, service changes, production build, staging/commit/push.
Preserve original artifacts and protected files. Stop if scope expansion is needed.

## Non-goals
New metrics, arbitrary question builders, full filing readers, text availability
probes, prices, acquisition/refresh/schema changes, deployment and live acceptance.

## Implementation stages
1. Record baseline, protections and approved scope.
2. Shared presentation catalog, complete snapshot/history and accessible states.
3. Verify generated question wording with the actual offline backend resolver;
   expose only verified choices with explicit submission.
4. Retain complete source response; strict indexed/metadata/unknown separation,
   safe links, progressive disclosure and existing recovery.
5. Focused mounted/static/client regressions, existing FR-01/CC-01, type/lint/diff.
6. Self-review, protected SHA256 reconciliation, actual results and stop for review.

## Decisions
- Frontend catalog contains presentation vocabulary and period choices only, never
  financial formulas. Preserve existing labels used by comparison.
- Balance-sheet history uses instant dates; duration choices keep direct-quarter,
  annual and explicit YTD labels. Snapshot balance-sheet dates are shown as of.
- Guide offers latest/quarter/annual for duration and latest-only for instant.
  Preparing a question invokes existing edit cancellation, without submitting it.
- Only exact boolean true establishes indexed readiness. False is metadata-only;
  missing/malformed is unknown and never eligible for retrieval or AI.
- Preserve source request ownership, publication pins, valid indexed accession
  selection and independent direct answers. No per-filing requests for discovery.

## Discovered issues
- The actual source endpoint combines fact-accession records and published indexed
  filing metadata. It is not a complete inventory of every acquired SEC filing.
  FD-01 preserves its entire response; extending inventory would require a separately
  approved backend contract change. No text/chunk probing or full reader was added.
- Source min/max fact dates can include comparative observations and are not a
  verified filing reporting window. Discovery displays form, filed date and accession
  only, with existing HTTPS official SEC link validation.
- History now exposes additional metrics, so response ownership explicitly checks
  ticker, CIK, metric and requested period before display. Existing controlled-fetch
  fixtures were completed with the already-required CIK field; four negative cases
  prove mismatched identity/selection is rejected.
- Existing cash-flow tests selected the formerly single secondary section. They now
  select the cash-flow section while retaining every original financial, cache,
  pin, retry, race and fan-out assertion.

## Progress
- [x] Baseline/instructions/protected hashes rechecked (2026-10-12).
- [x] Shared catalog and snapshot/history presentation (2026-10-12).
- [x] All 39 questions passed the actual backend resolver before guide controls
  were introduced; controls use existing edit/cancellation and explicit submission.
- [x] Complete sources retained with strict readiness and progressive disclosure;
  24 FD-01 regressions added across the three approved test files.
- [x] Full frontend suite, type/lint/diff, self-review and preservation passed.
  Next safe action: coordinator/independent review; no next milestone started.

## Test and validation strategy
Use current Node/ReactDOM/JSDOM harness and controlled fetch, including ignored
abort/pre-commit 409 delivery. Test 15 IDs/groups, all period choices and statuses,
source/provenance integrity, 39 generated value questions against production
recognition/resolution in an isolated Python subprocess without live DB/network,
preparation without requests, readiness true/false/malformed, safe SEC links,
progressive disclosure, recovery, switching and existing FR-01/CC-01 regressions.
Run frontend tests, nonemitting TypeScript, selective ESLint and git diff --check.
Browser/HTTP acceptance is deferred; no services started/restarted or build run.

## Completion criteria
All approved functionality and focused regressions pass offline. Exactly existing
15 metrics; no substituted values/periods; metadata never authorizes indexed actions;
pins/cancellation/race safeguards preserved; protected hashes/out-of-scope unchanged;
actual results/self-review recorded, no staging/commit/push. Stop for coordinator.

## Final outcome
Implemented in exactly the eight approved frontend files, plus this ExecPlan:
- frontend/lib/research.ts: the single presentation catalog for the existing 15
  metrics, grouped labels, descriptions, display periods and tested question vocabulary.
- frontend/components/financial-research.tsx: unchanged primary six cards, nine
  additional metrics in three disclosures, inline reasons and individual period
  labels, all-15 grouped history selector and response-ownership checks.
- frontend/components/filing-research.tsx: metric/scope guide, editor preparation
  with cancellation/focus and no submission; raw source preservation, separate
  indexed/metadata/unverified states, official links, ten-at-a-time disclosure.
- frontend/lib/finlens-api.ts: exact-boolean readiness helper; no API contracts changed.
- frontend/app/globals.css: scoped layout, wrapping, responsive guide and source list.
- frontend/tests/research.test.mjs, research-interactions.test.mjs and
  finlens-api.test.mjs: catalog/resolver/static/mounted/client discovery regressions.

Actual commands, working directory D:/Projects/finlens-foundation/frontend:
1. Before introducing guided controls:
   `node --test --test-reporter=spec --test-name-pattern='FD-01' tests/research.test.mjs`
   passed 2/2, including all 39 generated question cases through the actual
   `answer_research_question`, recognition, metric selection and answer resolution.
2. Focused implementation validation:
   `node --test --test-reporter=spec --test-name-pattern='FD-01' tests/research.test.mjs tests/research-interactions.test.mjs tests/finlens-api.test.mjs`
   passed 22/22 before the final two preservation/recovery regression additions.
3. Final `node --test --test-reporter=spec tests/*.test.mjs`: 200/200 passed,
   0 failed/skipped, including 24 new FD-01 tests and all existing 176 tests.
   All 27 CC-01 cases passed. FR-01 recovery, rejected-snapshot eviction,
   unknown/0/1 pins, concurrent reconciliation, four obsolete-409 races and four
   current-pin fail-closed/coalescing cases passed, including StrictMode.
4. `node node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0.
5. `node node_modules/eslint/bin/eslint.js components/financial-research.tsx components/filing-research.tsx lib/research.ts lib/finlens-api.ts`: exit 0.
6. Repository root `git diff --check`: exit 0.

The isolated resolver subprocess uses detached transient ORM fixtures and its own
read-only scalars facade; Engine.connect and network socket connects are blocked.
Python uses -B/PYTHONDONTWRITEBYTECODE. Mounted UI uses controlled local fetch that
rejects external origins and deliberately ignores abort delivery. No database,
provider, SEC, service start/restart, production build or deployment operation ran.
Existing Node module-type and Git line-ending notices are non-failing; no dependency
or package configuration changes were introduced to suppress them.

Self-review: no formulas/registries/backend/publication enforcement, CC-01 component
or FR-01 freshness implementation changed. Instant values are explicitly as of a
date; duration requests remain quarter/annual/explicit YTD, and no new period/value
fallback exists. Original API values, units, reasons and provenance remain available.
Only exact true readiness permits selection; false and malformed/missing flags
cannot authorize filing or company evidence/AI. Preparation invalidates pending
direct/evidence/AI via existing paths and never fetches. No unrelated tracked files
changed beyond the preserved pre-existing next-env modification.

Protected SHA256 values rechecked after implementation exactly match all three
starting hashes above. Both reports remain untracked; next-env remains modified
with its original bytes. Original SEC artifacts, receipts and backups were not
touched. HEAD/local origin/main remain main@1a07c43; index has no staged changes.
The working tree intentionally contains eight FD-01 modified frontend files,
the new completed plan and the three pre-existing protected items. No add/commit/push.

Limitations/review: discovery covers the existing sources response only; guided
instant questions are latest-only and metric availability remains server-dependent.
No browser/HTTP/live-data acceptance or screen-reader certification was performed.
Pending acceptance should check narrow mobile/wide desktop layouts, light/dark
themes, keyboard select/disclosure/editor focus, long filing accessions and failure
states with controlled data. Offline validation needs no services. Live acceptance
would need the existing frontend/backend and a readable published database; service
changes and external retrieval remain subject to separate coordinator authorization.
No implementation blocker or out-of-scope dependency arose. A targeted independent
Astra review of period/readiness/publication presentation is recommended before
coordinator acceptance, without repeating the completed financial/backend audits.

Suggested commit after review (exclude protected items):
`feat(frontend): expose existing metric and filing discovery (FD-01)`.
Stopped after offline validation for coordinator review.
