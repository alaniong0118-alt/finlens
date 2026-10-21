# REL-LEX-01 Increment A: selected-filing keyword search

Status: completed (three P2 corrections and offline verification; independent Astra re-review pending)
Roadmap phase: scoped Research Mode release enabling task; no later item authorized.

## Objective

Add an explicit third research purpose, preserving General research as default.
Each keyword submission sends one pinned selected-filing GET and renders only a
wholly validated stored response, with literal passages and honest provenance.

## Current architecture and context

Baseline: main, HEAD and local origin/main both
`666a5c8358cb9cb7dc5eb4c88ea08f0c4b5a1f09`; empty index. Existing changes are
only protected next-env.d.ts and two untracked protected reports. Their initial
Git blob hashes respectively are `830fb594ca2970a827555c28a253b097367e08d8`,
`ffc9d868ec186117c4fd9d902ba163bf6fff1a5f`, and
`e112739c2e93e11dae02a81139cd502f4a65a54b`. Private ignored backend/.env is
fingerprinted locally only; its contents must never be read or disclosed.
Existing requestJson provides a shared 30-second deadline and version transport.
The backend /search returns stored substrings, without semantic or model work.

## Constraints

Exactly six authorized paths: this plan; frontend/lib/finlens-api.ts;
frontend/components/filing-research.tsx; frontend/tests/finlens-api.test.mjs;
frontend/tests/research-interactions.test.mjs; backend/tests/test_bounded_research.py.
No staging, commit, push, services, browser, DB, model, dependency installation,
acquisition, activation or deployment. Preserve all protected/pre-existing state.

## Non-goals

No backend production or publication-policy changes, semantic fallback, AI,
financial claims, digest validation, or complete-filing coverage claim.

## Implementation stages

1. Capture baseline and inspect relevant contracts.
2. Add immutable keyword identity, whole-response and pinned-source validation.
3. Add separate accessible keyword lifecycle and literal renderer.
4. Exercise synthetic backend serialization through the real frontend validator,
   adversarial contracts, lifecycle races and relevant existing regressions.
5. Verify six-file scope, protected fingerprints and unstaged diff; self-review.
Rollback, if requested, must target only this task's edits, preserving prior work.

## Decisions

- 2026-10-21: Keyword mode performs a dedicated version-required source-list
  preflight on entry. Existing non-keyword source-list contracts stay unchanged.
  Submission itself sends only /search; preflight never automatically searches.
- Keep the plan at its explicitly authorized active path for review handoff.
- Immutable identity includes company name/CIK/ticker, selected accession,
  form/date/periods/metrics/indexed status/returned URL, transmitted query, limit
  and pin. A source-list mismatch disables submission; no metadata is repaired.
- Query edits invalidate search immediately; mode/scope edits additionally abort
  source preflight synchronously. Accession edits retain the query-independent
  pinned source inventory and invalidate the selected-filing search synchronously.
- Search retry retains the same native submit element and keyboard focus.
- Astra P2 correction: source eligibility is revoked at replacement verification
  start and synchronous scope invalidation, with a monotonic preflight generation.
  Search callbacks and render eligibility both require that successful generation.
  A batched same-identity scope round trip schedules a new verification epoch.
- Astra P2 correction: metadata-only form strings follow the /sources schema;
  indexed records alone require the 10-K/10-Q form allowlist. Issuer URLs,
  accessions, dates, exact Boolean eligibility and selected-source checks remain.
- Astra P2 correction: keep the source Retry element connected while pending,
  using aria-disabled plus a synchronous activation guard. Failure preserves
  keyboard focus; current success moves focus to an enabled submit/editor only
  if the user has not focused elsewhere. Scope cancellation/unmount clears intent.

## Discovered issues

2026-10-21 independent Astra High implementation review: FAIL / FIX REQUIRED.
Three reproduced P2 defects supersede the earlier offline self-review verdict:
1. Source ownership used a reusable identity string without a preflight generation;
   old inventory could admit and retain keyword results during replacement checks.
2. The indexed-form allowlist was applied to metadata-only sources, rejecting a
   valid mixed indexed 10-Q / metadata-only 8-K response.
3. The source Retry control unmounted while loading and focus restoration covered
   success only, leaving keyboard focus on BODY after another failure.

Correction baseline reverified: expected main/HEAD/local origin/main, empty index,
the original six-file worktree scope and all four protected fingerprints match.
Only these three defects and their regression coverage are authorized. Reuse the
existing offline commands; no services, real SQL/DB, providers, models or browsers.
The three corrections and focused/regression verification are now complete.
Independent Astra re-review remains pending; the earlier self-review PASS was
insufficient and does not override the independent FAIL verdict.

Astra P1: selected-filing publication-manifest presence does not revalidate
chunk content against the publication digest. Version/header and source identity
checks establish response consistency only. Stored keyword matches must not be
presented as digest-revalidated evidence or verified financial claims. Backend
policy changes and live acceptance require a separate scope.

The initial new backend bridge tests exposed fake-Store deficiencies (publication
projection rows were namespaces rather than SQLAlchemy-style tuples; SET statements
have no column_descriptions) and a fixture's incorrect tie-order expectation.
These were fixed only in the new test's local adapter/assertions. All 16 final
bridge cases pass. No backend production changes were needed.

## Progress

- [x] Baseline, root instructions, roadmap and relevant source contracts inspected.
- [x] API validation and keyword UI implemented.
- [x] Focused offline validation and self-review complete.
- [x] Protected files, index and exact scope reverified.
- [x] Record independent Astra FAIL and three P2 root causes.
- [x] Correct source generation/eligibility, mixed metadata inventory and retry focus.
- [x] Add 85 focused P2 cases; rerun relevant frontend/backend regressions and checks.
- [x] Self-review corrected boundaries and prepare independent Astra re-review handoff.

## Test and validation strategy

Only local installed runtimes and offline synthetic data. Use Node test runner
with existing React/jsdom harness; backend pytest fake Store/TestClient, with
session/model/provider bombs; transfer actual serialized search JSON in memory
to a Node validator. Run relevant research/risk regressions and installed lint /
non-incremental TypeScript checks. No Next build (may touch protected next-env).
Record exact commands and actual results below, separately from this strategy.

## Completion criteria

Atomic pinned contracts; one GET per explicit submission; synchronous duplicate
reservation; owner/generation guards; stale success/error/finalizer/409 rejection;
accessible literal rendering; regression checks; protected-state preservation.

## Initial implementation validation (2026-10-21, historical)

From `D:\Projects\finlens-foundation\frontend`:

```powershell
node --test tests/finlens-api.test.mjs tests/research-interactions.test.mjs tests/research.test.mjs tests/sec-risk.test.mjs tests/sec-risk-comparison.test.mjs
```

PASS: 799 tests, zero failures/skips, including research, risk, comparison and
mounted tone regressions. After the final source-preflight mode-cancellation
refinement, the complete keyword subset was rerun:

```powershell
node --test --test-reporter=dot --test-name-pattern=REL-LEX-01 tests/finlens-api.test.mjs tests/research-interactions.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/eslint/bin/eslint.js lib/finlens-api.ts components/filing-research.tsx
```

PASS: 101 keyword tests (53 API, 48 mounted), TypeScript exit 0, ESLint exit 0
with no warnings. The final two mounted cases prove synchronous source-preflight
mode cancellation before a late 409. Earlier focused runs also passed; totals
above identify the final runs rather than accumulating repeated executions.

From `D:\Projects\finlens-foundation\backend`:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_bounded_research.py
```

PASS: 188 tests (172 existing plus 16 new bridge cases), zero failures, one
installed Starlette/httpx deprecation warning. The bridge uses actual FastAPI
TestClient serialization, fake sessions, compiled read-only SQL and Node stdin;
it creates no fixture files and makes no real HTTP/provider/model/DB calls.
Cases cover pins 0/2, substring/case matching, zero matches, Unicode astral and
combining text, CRLF, stored trimming and backend rank order. Encoder/model,
SEC, semantic/context, financial answer, tone and AI/provider bombs remain unused.
The deliberately substituted manifest digest still permits stored keyword
matches, proving why the P1 qualification must remain visible.

The installed Node runtime emits its existing module-type advisory; no package
or runtime changes were made. Git emits its existing LF-to-CRLF advisories for
test files; `git diff --check` reports no whitespace errors.

## P2 correction validation (2026-10-21, current)

The initial replacement-inventory reproduction failed before the production
correction. All three independent Astra root causes were checked against current
source, and focused regressions now cover each. One added batched-scope test
initially counted the required replacement /sources request as unexpected traffic;
the assertion was corrected to prohibit keyword submissions while allowing that
verification request. Production safeguards were not weakened to satisfy it.

Frontend working directory and installed runtimes are unchanged. Commands run:

```powershell
node --test --test-name-pattern='REL-LEX-01 P2' tests/finlens-api.test.mjs tests/research-interactions.test.mjs
node --test --test-reporter=spec tests/finlens-api.test.mjs tests/research-interactions.test.mjs tests/research.test.mjs tests/sec-risk.test.mjs tests/sec-risk-comparison.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/eslint/bin/eslint.js lib/finlens-api.ts components/filing-research.tsx
```

PASS: 85 new focused P2 tests (9 API, 76 mounted). PASS: 886 total frontend
regressions, including all 186 keyword tests. Zero failures/skips. TypeScript and
scoped ESLint exit 0; final lint has no warnings. Existing module-type advisories
remain unchanged. Focus assertions use jsdom focused keyboard events plus an
explicit click for Enter's native default action; this is not browser acceptance.

Backend command (with PYTHONDONTWRITEBYTECODE=1) is unchanged:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_bounded_research.py
```

PASS: 188 tests; also 16/16 targeted rel_lex bridge cases passed separately.
The existing 16 serialization cases now emit a real FastAPI /sources response
with a newer metadata-only 8-K before the indexed 10-Q. The real frontend client
accepts this response, rejects using that 8-K (including forged indexed status),
rejects substituted selected URLs, and searches only the eligible 10-Q. Exact
headers at versions zero/two and encoder/provider/model bombs remain intact.
No real SQL execution, connections, provider calls, model loads or services occur.
The installed Starlette/httpx deprecation warning remains unchanged.

Coverage includes pending/completed search results, both settlement orders,
empty/rejected/malformed/missing-header replacement checks, scope A-B-A including
batched events, stale preflight success/failure before and after a newer success,
and restoration only after the current generation verifies. Keyboard cases cover
three repeated failures then recovery, focus intentionally moved to the editor,
stale retries after scope changes and unmount, duplicate retry activation and no
unintended keyword submission. The renderer/provenance/URL/deadline contracts and
non-keyword research/risk regressions pass unchanged.

## Self-review and Astra implementation re-review handoff

- P1: bounded and explicitly disclosed, not repaired. Manifest presence and
  publication-version agreement do not establish digest validation. No digest,
  citations, semantic scores, sufficiency or financial claims are fabricated.
- Response/provenance conditions: whole-response rejection, exact company/name/
  accession/query, exact pin including zero, real dates/allowed forms, canonical
  returned SEC index URL, consistent safe filenames, unique canonical chunk IDs,
  count/limit and Unicode offset checks are implemented and adversarially tested.
- Lifecycle conditions: separate state; synchronous duplicate reservation and
  event invalidation; immutable request plus owner/generation checks; render-time
  gating; layout unmount cancellation; stale success/error/finalizer/409 rejection;
  shared 30-second deadline and explicit retry only. A-B-A, same-tick edits,
  StrictMode, ignored abort, pre-commit races and unmount are covered offline.
- P2 source-generation correction: invalidate prior inventory and search ownership
  synchronously, gate rendering on current verified generation and selected-source
  eligibility, and guard every preflight/search completion against obsolete owners.
- P2 mixed inventory correction: metadata-only non-indexed forms are valid schema
  records; the indexed allowlist and canonical source admission remain strict.
- P2 focus correction: the Retry element stays mounted and focusable while pending,
  activation is guarded, and success-only focus handoff cannot run for stale owners
  or overwrite intentionally moved focus.
- Independent Astra High returned FAIL / FIX REQUIRED for the initial change.
  Review next: the exact corrected six-file unstaged change, the three P2 fixes
  and new cases above. No independent re-review or browser/live acceptance was
  performed here. No next milestone or Git action is authorized by this handoff.

## Final outcome

PASS for the three scoped corrections and offline verification; independent
Astra re-review is pending. Browser/live product acceptance
remains NOT TESTED because browser/services/DB/model operations are unauthorized.
No dependencies installed, services started, network acquisition, model execution,
DB access, Git staging/commit/push, activation or deployment occurred.

Final branch is main; HEAD and local origin/main remain
`666a5c8358cb9cb7dc5eb4c88ea08f0c4b5a1f09`; index remains empty.
The three protected public files match their initial Git blob hashes; private
backend/.env matches its initial SHA-256 and remains ignored, with contents not
inspected. No unexpected worktree paths were introduced.

Current cumulative unstaged implementation diff against HEAD: backend test
+88/-0; filing-research.tsx +171/-10; finlens-api.ts +112/-0; API tests +150/-0;
interactions +377/-0. This is five tracked files, +898/-10, plus this new plan.
These totals include the original implementation and the three P2 corrections.
The pre-existing protected
next-env.d.ts change (+1/-1) and two untracked reports remain outside this task.
The plan is the exact sixth authorized path; no completed-path move is authorized.

Suggested commit (not performed):
`feat(research): add bounded selected-filing keyword search`
