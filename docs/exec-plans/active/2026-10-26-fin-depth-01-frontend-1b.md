# FIN-DEPTH-01 Frontend Increment 1B

Status: active; corrected 1B.1 independently accepted per coordinator and committed;
1B.2A Astra FAIL retained; scoped import-deadline P2 correction verified offline,
pending focused independent re-review. Historical offline passes are scoped evidence.
Roadmap phase: bounded enabling slice of Research Mode depth. Only 1B.2A is authorized.

The original 1B.1 implementation and correction sections below retain historical
FAIL/pending-review wording and their original baselines/results. The 1B.2A section
and final handoff record describe the current task; no historical verdict is erased.

## Objective

Implement the accepted insights-only contract, bounded worker transport and owned
result lifetime. The coordinator supplied Astra PASS for all design amendments;
that verdict does not establish implementation, browser, database or pilot acceptance.

## Current architecture and context

Starting branch main, HEAD 21a94a74888cb184948e8388a223b005c62e23a5, empty index.
Preflight found only the three protected exceptions; their supplied SHA-256 hashes
matched. Reports were hashed only. Backend 1A serialization is authoritative.
Existing requestJson must remain unchanged. Next uses module-worker URL bundling.

## Constraints

Exactly six candidate paths: frontend/lib/financial-insights.ts,
frontend/lib/financial-insights.worker.ts, frontend/lib/finlens-api.ts,
frontend/tests/financial-insights.test.mjs,
frontend/e2e/fixtures/financial-insights.ts, and this plan.
No staging/commit/push, services, browser, DB, SEC/provider/model operations,
dependency installation, private .env access or protected-file changes.

## Non-goals

No component, styling, pilot, deployment or Backend 1A changes. Historical
FAIL/BLOCKED records and eight-file historical identity NOT VERIFIED remain intact.

## Implementation stages

1. Exact contract, bounded lexical preflight, graph/statement admission and decimals.
2. Worker input/output credits, complete display preflight and indexed pages.
3. Parent handle ownership, streaming limits, deadlines and disposal.
4. Guarded serialized fixtures, offline adversarial tests and safe static checks.
5. Scope/hash verification and coordinator handoff for Astra implementation review.

## Decisions

2026-10-26: Worker owns the full graph. Parent retains initial presentation plus
one committed and one staged page only. Busy different page requests are rejected;
identical requests coalesce. No page FIFO/cache. Oversized display records reject
before initial publication. Initial deadline is 30 seconds; later pages have 5 seconds.
Idle/absolute lifetimes are 5/15 minutes, heartbeat 15 seconds with 5-second allowance.

## Discovered issues

Extended guarded serialization exposed canonical D comparisons with null
percentage_reason when revenue bases conflict. The first extended combined run
was 243 passed / 1 failed; the validator was corrected only for the diagnostic
canonical shape. The nine-case focused compatibility rerun passed. Published
comparison percentage reasons remain strict. Initial 65-case development run passed.

Self-review added full raw/canonical source reconciliation, iterative queued-once
closures, UTF-8 fragment coalescing (not one retained string per network fragment),
post-suspension deadline checks, and bounded statement/edge page targets.

Browser bundling must not be inferred from TypeScript checks. A build in the working
repository could rewrite next-env.d.ts and create uncontrolled generated files.
Build and browser/runtime acceptance are therefore deferred, not bypassed.

## Progress

- [x] Read-only preflight and exact allowlist admission.
- [x] Implement contracts and lifecycle.
- [x] Final combined offline tests: 249 passed, 0 failed, 0 skipped/deselected.
- [x] TypeScript, scoped ESLint and candidate whitespace checks passed.
- [x] Exact six-path scope, baseline/index and protected fingerprints verified.
- [ ] Independent Astra implementation review (separate gate).

## Test and validation strategy

Use worker doubles and deterministic clocks. Backend synthetic serialization must
initialize the existing guarded runner preamble before any application import.
Run no-site/no-bytecode Python only. Test body, Unicode, JSON/graph limits, decimal
expansion, F/D separation, version zero, ACK ordering, lifetime and cancellation.
Run TypeScript without incremental output and scoped ESLint. No browser/services.

Actual contracts: HTTP-decoded input <=4 MiB; one exact-allocation 16 KiB input
slice awaiting ACK. Fatal UTF-8 and bounded lexical/duplicate-key preflight precede
native JSON.parse in the worker only. Graph/statement identities and complete
closures are checked against the committed wire shapes; finance arithmetic,
direction, prose and precision predicates remain server-owned. Decimal expansion
is lexically bounded before allocation. Publication zero and None:None are valid.

Output uses bounded structured-clone display objects (not cloned graphs), measured
before posting: <=32 KiB including protocol allowance, <=1,024 entries and <=25
records. This avoids a second native JSON.parse on the main thread. One output
credit is released by exact ACK; OP_COMPLETE gates publication. Parent retains an
initial model <=128 KiB plus one committed and one staged page <=32 KiB each;
the accepted 224 KiB logical ceiling is conservative. No worker page cache.
Collections are packed by both size and entry count. Every complete display record
is preflighted; oversized records reject the whole comparison before publication.

The exported panel must be disposed synchronously by the future UI on company,
year, version, cancellation and unmount changes. Handles expose disposal and a
bounded subscription; expired snapshots/pages become null. No UI was implemented.

## Completion criteria

Focused offline checks pass; six-path candidate only; protected hashes unchanged;
known deferred bundling/browser/runtime gates explicit; independent Astra review
remains pending until separately performed.

## Final outcome

Implemented only the six authorized paths. Five are new; finlens-api.ts adds an
opt-in wrapper and type import. A test compares the complete pre-existing
requestJson implementation with HEAD and proves it unchanged. Compare API calls
require matching discovery identity, supported years and publication tuple.
No financial formulas, source selection, direction or statement text are generated.

Final commands from frontend/:

```
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js lib/financial-insights.ts lib/financial-insights.worker.ts lib/finlens-api.ts e2e/fixtures/financial-insights.ts
```

Final combined tests: 249 passed, 0 failed, 0 cancelled, 0 skipped/deselected;
141.271 seconds. TypeScript and ESLint exit 0. Four golden fixtures match fresh
guarded Backend 1A serialization. Nine additional guarded cases cover loss/zero,
tiny values, ambiguous eleven-anchor windows, incompatible revenue bases and
NaN/sNaN/Infinity/-Infinity as the only CapEx candidate. All passed frontend
admission and complete display preflight without a database/provider operation.

Protocol evidence includes ignored fetch/read abort, actual 4 MiB / +1 byte,
misleading length, fragmented UTF-8, bounded ACK credit, missing initial/page ACK
and OP_COMPLETE, duplicate/obsolete messages, page coalescing/busy rejection,
post-30-second pages, initial/page/idle/absolute timeouts, heartbeat overlap and
silent termination, disposal and fixed retention. Aggregate JSON expansion and
graph/reference substitutions fail closed. Node's existing typeless-package
warning and the guarded Python import's existing Starlette/httpx deprecation
warning are not failures; dependencies were not changed.

All six candidates are regular UTF-8 text with no NUL or trailing whitespace.
Scoped git diff --check and new-file no-index whitespace checks passed. HEAD stays
21a94a74888cb184948e8388a223b005c62e23a5 on main; index empty. Only the six
candidates plus the original three exceptions are present. Protected SHA-256:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Reports were hashed only. No source outside the allowlist, private configuration,
backend policy, dependency or historical acceptance record was modified. No Git
publication or live/browser/model/provider operation occurred.

Independent Astra must review: exact F/D/canonical versus admitted shapes and
nullable diagnostic percentage reasons; field/Unicode/JSON/graph/work accounting;
lossless representation equality and expansion bounds; complete source lineage;
ACK identity/credit and payload bounds; operation settlement and ownership;
expiry, heartbeat overlap and disposal; guarded serialization safety. Review the
standard new Worker(new URL(..., import.meta.url), {type: 'module'}) integration
separately: actual Next bundling, browser Worker execution, mounted accessibility,
real PostgreSQL, issuer coverage, pilot and deployment remain NOT VERIFIED.
Parent retention bounds describe module-owned logical content, not exact JS heap
size or references independently retained by future UI consumers. Future 1B.2 must
subscribe to disposal and read only current handles; no rendered UX claim is made.

Stop for coordinator/Astra review. Suggested later commit message:
`feat: add bounded financial insights client contracts and worker transport`.

## Frontend 1B.2A authorization and implementation — 2026-10-26

Status: active candidate verification. Coordinator reports independent PASS for corrected
1B.1 and authorizes only bounded UI integration. The earlier FAIL, correction and
pending-review statements above are historical records, not current Git state.
Entry: main at d368bba9308864b1977e61040e1877ec4548ad57, index empty, exactly the
three original protected exceptions with all established hashes unchanged.

### Objective and exact scope

Add annual insights before the research grid inside ResearchFreshness, retaining
existing research access. Exactly five candidate paths: new
frontend/components/financial-insights.tsx and
frontend/tests/financial-insights-interactions.test.mjs; modify
frontend/app/page.tsx, frontend/app/globals.css and this plan. Committed 1B.1
contracts, existing tests, dependencies and private configuration stay untouched.

### Decisions and implementation stages

1. Use type-only insights imports until Worker support is checked, then defer the
   production module import. This preserves genuine unsupported-browser behavior
   and the existing CommonJS Home harness. Supported paths retain the original
   module Worker constructor. Guard import completion against current ownership.
2. One component-owned panel; current company/CIK/publication, year and attempt
   identities guard controllers, callbacks, disposal, pagination and focus. A
   30-second UI deadline includes deferred import time; the committed request,
   page, heartbeat, idle and absolute deadlines remain independently enforced.
   View publication also checks the attempt generation, including queued React
   updates after parsed-success/year-round-trip races.
   Subscription consumers retain handles, never copied comparison graphs/pages.
3. Render seven fixed metrics from F-admitted presentation values and server
   statements. Completeness concerns five headline comparisons only. Discovery
   years come only from the eleven-anchor endpoint. No financial recalculation.
4. Use one F/D page viewport, bounded pending navigation metadata and Worker
   targets/edges; disclose every flattened field, including hidden CapEx lineage.
5. Add offline mounted React tests with controlled fetch/Worker runtime doubles,
   then run targeted suites, existing Home regression, no-output TypeScript and
   scoped ESLint. Record exact outcomes and preservation checks below.

### Progress and validation strategy

- [x] Baseline/index/exception inventory and protected hashes verified before writes.
- [x] Implement the component, Home insertion and scoped responsive CSS.
- [x] Implement and run mounted interactions, relevant contract tests and Home regression.
- [x] TypeScript, scoped ESLint, diff/scope and protected-hash self-review.
- [ ] Independent Astra implementation review (separate coordinator gate).

No build, browser, Next/service, CI, Docker, database, SEC/provider/model, pilot or
deployment operation is authorized. No staging, commit or push. Next Worker
bundling, Playwright fixtures/configuration, real Chromium, screenshots,
320px/390px/zoom visual acceptance and manual NVDA/Chrome remain 1B.2B gates.
Final outcome and commands: recorded in the 1B.2A handoff below, after the
historical 1B.1 correction record.

## Astra two-P2 correction — 2026-10-26

Coordinator supplied independent Astra verdict: **FAIL — NO-GO for Git Step 1**.
Two P2s: admitted base observations were not bound to selected source values and
dates; relevant selected-identity conflict diagnostics could coexist with F support.
The accepted transport, worker protocol and lifetime are not being redesigned.

Pre-fix main/HEAD/index and exact six candidates plus three protected exceptions
were verified. Current entry SHA-256 (not historical design/P2 hashes):

| Candidate | Entry SHA-256 |
|---|---|
| frontend/lib/financial-insights.ts | EE7B47DD70976484158A3CD280AF38484B6B28FA44BEA5DF384F9F049787C76E |
| frontend/tests/financial-insights.test.mjs | 75F2FAB4EC7FA025B067AA6F56642581CA3E945E90D154C3A2FBBBEEA9D0EB5B |
| docs/exec-plans/active/2026-10-26-fin-depth-01-frontend-1b.md | AC4B0F4CCC3E523B7766A2BDDA5238B43147B7602294466FB9448798DA1BB7C6 |
| frontend/lib/financial-insights.worker.ts | EC3D2345A4D97D433B0520DF6B4B81852626ECA68BAA22C12A8E5A557694FA7B |
| frontend/e2e/fixtures/financial-insights.ts | 491733790CD78DC2A143295B196D41F2891AEB47F7293072C70CBB027D16B36A |
| frontend/lib/finlens-api.ts | EF78F72DD774722C3A79FF8378EE9F2E94030D4B67D7DB1073C9A35ECB26EA1A |

Only the validator, its tests and this plan may change in this correction. The
other three candidate hashes above must remain byte-identical.

Before correction, `node --test --test-name-pattern='P2 regression'
tests/financial-insights.test.mjs` ran 9 tests: 0 passed / 9 failed. All three
original Astra mutations were accepted instead of rejected: revenue 100 versus
source 999, FY2024 versus source dates in 2023, and selected CapEx conflict with
FCF still 15. Margin conflicts and duplicate-identity conflict variants were also
accepted. The production Worker/parent amount-substitution test fulfilled its
comparison request (READY) rather than rejecting. This failure evidence is retained.

Correction binds each admitted base value, canonical/source concept relationship,
fact ID, unit and exact start/end to its selected provenance/raw source and the
shared annual window. Filing-context fiscal annotations remain independent.
Derived observations still follow admitted operand/provenance chains; no finance
arithmetic, source reselection, direction or statement generation was added.
Conflict checks use the exact nine-field Backend 1A source_identity. Attached
selected-identity conflicting_value flags, or distinct finite values under that
identity even without the flag, reject the response as INVALID_RESPONSE. Genuine
unadmitted diagnostics, nonfinite alternatives and other vintages remain separate.

Final focused command from frontend/:

```
node --test --test-name-pattern='P2 regression|P2 positive' tests/financial-insights.test.mjs
```

Result: 12 passed / 0 failed / 0 cancelled / 0 skipped; 39.199 seconds.
The three original mutations now reject as INVALID_RESPONSE. The actual
production worker runtime and parent protocol emit FAIL INVALID_RESPONSE for the
amount substitution, with zero BATCH or OP_COMPLETE messages, no READY publication,
one worker termination, no retained worker graph and no remaining timers.

The positive guarded test independently compares the admission concept/basis
manifest with committed METRICS/REVENUE_CONCEPTS. Six freshly serialized cases
retain alternatives, equivalent duplicates, unrelated quarters, nonfinite rejected
candidates, arbitrary stored metric aliases and comparative-filing fiscal context.
Equivalent decimal spellings and signed zero equality pass without float amounts.
Legitimate derived margins/FCF and unavailable FCF with conflict diagnostics pass.
No selected input is reselected, amended or used for new financial arithmetic.

Full previously passing suites rerun with all new tests:

```
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js lib/financial-insights.ts
```

Combined result: 261 passed / 0 failed / 0 cancelled / 0 skipped/deselected;
181.811 seconds. TypeScript and scoped ESLint exit 0. The existing streaming,
Unicode, resource, worker/ACK/lifetime, zero-pin and None:None cases remain passing.
The earlier 249-pass result and Astra FAIL above remain historical evidence.

Only financial-insights.ts, financial-insights.test.mjs and this plan changed in
the correction. The worker, golden fixture and API hashes match their entry values
byte-for-byte. All three original protected hashes match. Branch remains main at
21a94a74888cb184948e8388a223b005c62e23a5; index remains empty; the candidate
inventory remains exactly six files plus the three protected exceptions.

No build, browser, service, Docker, database, SEC/provider/model operation or private
.env access occurred. Actual Next bundling/browser, issuer/runtime, pilot and
deployment acceptance remain NOT VERIFIED. No 1B.2 work began. No Git staging,
commit or push occurred. Ready for coordinator and focused Astra re-review only;
the historical Astra FAIL is not relabelled as an independent PASS.

## Frontend 1B.2A final offline handoff — 2026-10-26

Candidate complete for coordinator/independent Astra implementation review only.
This is not browser, Next Worker bundling, accessibility, live-data or deployment
acceptance. The coordinator supplied 1B.1 independent PASS and committed baseline;
no new independent PASS for 1B.2A is claimed.

### Implemented behavior and ownership

Home inserts annual insights immediately before its research grid under the same
selected-company ResearchFreshness provider and adds its navigation link. Snapshot,
history, filing research and both comparison sections retain their existing links.
The compact initial controls and collapsed seven-metric/evidence disclosures keep
other research discoverable. Scoped CSS stacks at tablet/mobile widths and wraps
long values, identifiers, fields and buttons; actual 320px/390px/200% zoom rendering
is not verified by JSDOM.

Discovery waits for a verified pin, including zero; years come only from the
eleven-anchor endpoint. Earlier/later selectors never silently swap. Compare and
retries are explicit. Seven fixed metric rows use only F-admitted formatted values;
classification follows presentation metadata with fixed metric definitions for
unavailable slots. Five-headline completeness, periods, publication identity and
all server statements/limitations/precision notices are displayed without frontend
financial recalculation. No admitted value is replaced by a D canonical value or zero.

One panel owns each component's session. Base company/CIK/publication identity,
selected-year invalidation, monotonically increasing attempt and controller
identity protect deferred imports, initiation, results, errors, 409 callbacks,
finalizers, subscriptions, pages and focus. Render publication checks the attempt
as well as base owner. Subscription functional updates recheck ownership when
React applies them. Company/pin changes detach subscriptions and dispose
synchronously; year/cancel/retry handlers do likewise before state changes;
layout cleanup covers unmount and StrictMode replay. A 30-second UI timer bounds
the complete initial action including import. Worker request/page/idle/absolute
and heartbeat policies are unchanged. Notifications reread nullable handles;
expiry/failure removes the financial result. Background renders do not interact.

Evidence uses separate F/D collection descriptions and one shared bounded page
viewport, Previous/Next controls and statement/edge targets. No React graph copy,
visited-page cache or unbounded navigation history exists. Identical navigation
coalesces, different busy navigation waits without a queue. Full flattened field
paths/values, raw source metadata, candidates/rejections and source/operand links
remain disclosed, including FCF's CapEx chain. SEC URLs pass the existing helper;
unsafe diagnostic URLs remain literal text. All backend text uses React text
rendering. Focus follows a completed matching page/current generation and does
not replace focus deliberately moved to another control.

### Checks actually run

Working directory: D:\Projects\finlens-foundation\frontend.

```
node --test tests/financial-insights-interactions.test.mjs tests/research-interactions.test.mjs
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js components/financial-insights.tsx app/page.tsx tests/financial-insights-interactions.test.mjs
```

Final combined mounted run: **619 passed, 0 failed/cancelled/skipped/todo**,
76.8765509 seconds: 49 new UI tests plus all 570 unchanged Home interaction tests.
The Home suite also passed alone earlier: 570/570, 23.804424 seconds.
Existing insights/API suites: **261 passed, 0 failed/cancelled/skipped/todo**,
182.3589354 seconds. Their guarded synthetic Python serialization cases ran
offline; no database, private configuration, SEC/provider/model operation ran.
TypeScript and scoped ESLint exit 0 with no diagnostics. No Next build ran.

The new harness uses real ReactDOM/act/JSDOM and the actual committed client and
exported Worker runtime behind controlled fetch/Worker and import-promise seams.
No real Worker process, browser or Next bundler was exercised. Both supported and
unsupported Home branches are mounted; supported insights and empty sibling
snapshot/history/filing outcomes settle independently. Tests cover zero/null pin,
exact/empty/single-year discovery, invalid pairs, seven metrics, server text,
partial conflict diagnostics, complete FCF/CapEx/source traversal across pages,
bounded retention, same-tick duplicate/busy/coalesced pages/submissions, cancel/
retry, A-B-A company/year races, parsed success before year edits, current and
obsolete/pre-commit 409, old finalizers/focus, deferred import expiry/cancellation,
idle/absolute/page expiry, Worker failure/pagehide, and StrictMode/unmount cleanup.
Unsafe diagnostic URLs and literal script markup are also covered.

Development failures were repaired, not hidden: the first harness attempted to
mock an absent global Worker property; it now declares/restores the test property.
After that setup fix, a complete new-suite run was 41/42 because the pre-commit freshness test
left JSDOM's document hidden; the visible-document setup now exercises that
callback. Focused reruns passed. Self-review added attempt-gated rendering,
ownership checks inside queued subscription updates and the import-inclusive UI
deadline; the final 619-test run includes these changes.

### Preservation and independent review focus

Exactly five candidate paths, the two new and three modified paths enumerated
above, plus the three original protected exceptions. main and HEAD remain
d368bba9308864b1977e61040e1877ec4548ad57; Git index empty. Protected SHA-256 values
remain the established F4E8976C...1625C0 (next-env), A783517D...57844C (canary), and
F8DF96C8...58BF7C (discovery), with full values preserved in the historical record.
Reports were hashed only. Committed 1B.1 client/Worker/API, fixtures, existing tests,
package/dependency files and private configuration were not modified.
Tracked candidate git diff --check passed; all five candidates passed fatal UTF-8,
no-NUL, trailing-whitespace and final-newline checks. Git's normal LF/CRLF notices
do not indicate whitespace errors; no-index comparisons of new files return the
ordinary difference status and were supplemented by explicit text hygiene checks.

Independent Astra should examine: (1) deferred production import, supported/
unsupported branching and combined UI deadline; (2) synchronous owner invalidation,
attempt-gated React publication and stale 409/finalizer/subscription guards;
(3) F-only displayed values, five-headline labeling and server-authored wording;
(4) full F/D flattened disclosures and hidden CapEx lineage, single-page retention,
coalescing/busy navigation and safe source links; (5) completion/ownership/focus
ordering, expiry cleanup, StrictMode and the limitations of the offline harness.

No blocking committed-interface gap was found. All 1B.2B gates remain deferred:
Playwright config/routing, actual Next Worker bundling/browser execution, real
Chromium, desktop/mobile screenshots, 320px/390px/zoom layout and manual
NVDA/Chrome. Pilot, live/native and deployment remain unexecuted. No staging,
commit or push. Stop for coordinator review; do not start 1B.2B.
Suggested later commit: `feat: integrate bounded annual financial insights UI`.

## 1B.2A import-deadline P2 correction — 2026-10-26

Coordinator supplies independent Astra 6 High verdict: **FAIL — NO-GO for Git
Step 1**, exactly one P2. The reviewed UI relied on dispatch of its timeout
callback. Astra reproduced a 31,004 ms event-loop delay followed by import
completion before the overdue callback: one Worker and an HTTP request started
outside the 30-second UI initialization budget. Other bounded offline areas
passed; the preceding 619/261 test results remain historical and do not negate
this FAIL. No independent PASS for the correction is claimed.

Entry verified: main/d368bba9308864b1977e61040e1877ec4548ad57, empty index, exactly
the five existing UI candidates plus three protected exceptions; protected SHA-256
matches all established values. Only the component, its new interaction test and
this plan may change for this correction. Review-entry SHA-256 values:

- frontend/components/financial-insights.tsx: 4820B4AB78155F3E7AB0B887B132E5946D3FAD5E154334B02F2DFA510023E316
- frontend/tests/financial-insights-interactions.test.mjs: 4DCD8E9AE6DD3A046061AFBCD757B2EA7D9D269BC0EBD2C46168553E77265B6B
- this plan: C5E69418AB58E24ED554B835348DC4E69FD37A1B437FB0689CD5EA156C893D66
- frontend/app/page.tsx (must stay unchanged): ECB8884B99FB94A9DA5A763D0A1CD7CCD2068500E8A81C153D8114AB757CEBFD
- frontend/app/globals.css (must stay unchanged): F20DB044911F483ECFEBD315970946BED008CEF2E0296D70969951DD3BDD7439

Correction stages: first reproduce the ordering with tests against the reviewed
component, then capture operation-start monotonic and wall times and enforce
elapsed expiry independently of timer delivery. Preserve generation/controller
ownership, pass the time guard through the existing request.current seam, and
check import success/rejection, construction, initiation, async continuations and
initial READY publication. Keep successful comparisons' later Worker lifetime
unchanged. Rerun all bounded suites, no-output TypeScript, scoped ESLint and
preservation/whitespace checks. No other defect or milestone is authorized.

Entry progress: reproduction and correction pending. No browser/build/services, live
data/provider/model, dependencies, staging/commit/push or 1B.2B work is authorized.

### P2 reproduction, correction and offline evidence

The new regressions were added before changing the reviewed component. All six
selected import-ordering cases failed against that source (30,000 ms monotonic
boundary, 31,004 ms monotonic delay, wall fallback, backward wall clock, late import
rejection, and real delayed timer delivery). A second isolated real reproduction
captured the original ordering explicitly: **31,005.6224 ms elapsed, one Worker,
one insights HTTP request, timerFired=false**. Its expected-zero assertion failed.
The import continuation ran before the overdue timeout callback; the timeout
callback-only regression had not tested this condition.

The component now captures performance.now() and Date.now() at operation entry,
before invalidation/import/setup. Its initialization current guard first checks
the unchanged company/CIK/version/generation/controller ownership, then rejects
when monotonic elapsed time OR wall elapsed time reaches 30,000 ms. A frozen
monotonic clock cannot bypass the wall bound; a backward wall change cannot extend
the monotonic bound. Invalid/regressed monotonic readings fail closed.

This guard runs after import resolution or rejection, before/after panel setup,
through the existing request.current seam at asynchronous client continuations,
and before publishing initial data. Guarded wrappers around the existing public
environment.worker/fetch factories check directly before allocation/network work,
including time spent inside synchronous listener setup. Original factories are
retained once, so retries neither chain obsolete guards nor retain unbounded
attempt histories. No committed 1B.1 file or interface changed.

Successful promise settlement alone no longer ends the initialization budget.
The guard remains active until a matching READY layout commit rechecks time and
ownership, then clears the UI deadline and releases pending initialization. This
also rejects a commit delayed past the budget after a timely promise resolution.
After that commit, ordinary ownership remains active and the unchanged Worker
5-second page / 5-minute idle / 15-minute absolute lifetimes govern the result.

Elapsed expiry uses the same guarded invalidation/abort/disposal path as timer
expiry: detach subscriptions, abort the originating controller, clear pending
page/focus/init metadata and timers, dispose the owned session and remove result
publication. Only a current focused Cancel may restore focus to an explicit retry;
deliberately moved focus is preserved. Cleared or obsolete timeout callbacks cannot
expire a completed/replacement attempt. Import completion/rejection cannot revive
an expired attempt. Explicit retry captures fresh start clocks without extending
the old attempt or weakening publication binding.

Thirteen regressions were added; all 49 existing UI cases remain. New coverage
includes exact boundary/delayed monotonic time, stopped monotonic/wall fallback,
regressed clocks, late rejection, real event-loop stall, import + request combined
budget, delayed initial comparison completion, synchronous panel/listener setup,
delayed Worker STARTED before HTTP, and promise-settlement-to-React-commit delay.
They check zero resource/network creation for expired imports, no discovery READY
or financial UI, cleared timers/listeners/graph retention, controller aborts,
preserved focus, and a successful explicit fresh retry.

Final combined interaction/Home command from frontend/:

```
node --test tests/financial-insights-interactions.test.mjs tests/research-interactions.test.mjs
```

Result: **632 passed, 0 failed/cancelled/skipped/todo**, 115.0727946 seconds:
62 UI tests (49 retained + 13 new) and all 570 unchanged Home interactions.
The actual delayed-event-loop regression now observed **31,004.2958 ms elapsed,
zero Workers, zero insights HTTP requests, timerFired=false**, then verified a
fresh retry starts exactly one Worker and one insights HTTP request. No expired
import constructed even an InsightsPanel. HTTP counts exclude the independently
mocked prerequisite freshness check; no external HTTP operation ran.

Additional final commands from frontend/:

```
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js components/financial-insights.tsx tests/financial-insights-interactions.test.mjs
```

Existing contract/API result: **261 passed, 0 failed/cancelled/skipped/todo**,
183.1395473 seconds. Total final relevant coverage: **893 passed** across the two
full commands; no deselection in either. Guarded offline serialization in the
existing suites used no services/database/private configuration/provider calls.
TypeScript and scoped ESLint exit 0 with no diagnostics. The final exact-inventory
and SHA-256 assertion passed; candidate tracked git diff --check and fatal UTF-8,
no-NUL, trailing-whitespace/final-newline checks on all five paths passed.

Final inventory is exactly the existing five candidates: new component/test,
modified Home/CSS/ExecPlan, plus the original three protected exceptions. Only the
component/test/ExecPlan changed during this P2 correction. Home/CSS match their
review-entry SHA-256 values above byte-for-byte. Branch remains main at
d368bba9308864b1977e61040e1877ec4548ad57; index empty. Final protected SHA-256:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Self-review: financial presentation/F-D boundaries and pagination code unchanged;
ownership checks precede elapsed-time checks, timeout cleanup is idempotent, the
same operation-start budget follows import/request/commit without reset, and
completed comparisons retain their separately enforced Worker lifetime. No new
defect or committed-interface gap found. No source/test outside the three-path
correction scope changed; existing Home/CSS and committed contracts are preserved.

Progress: scoped correction and offline verification complete; **stop for
coordinator and focused Astra re-review**. Prior Astra FAIL remains historical
independent evidence; these self-run checks do not establish Astra PASS or Git
Step 1 authorization. Review the timer-independent clock guard, existing environment
resource wrappers, initialization-to-commit ordering, cancellation/focus cleanup,
and before/after real event-loop reproduction. Actual browser/module-Worker/Next
bundling and all 1B.2B/native/pilot/deployment gates remain NOT VERIFIED. No build,
browser, services, Docker/PostgreSQL, SEC/provider/model, dependency installation,
private .env access, staging, commit or push occurred.
Suggested later correction commit: `fix: enforce elapsed annual insights initialization deadline`.

## Frontend 1B.2B test-only authorization — 2026-10-26

Coordinator accepted the read-only preflight and authorized implementation only.
The coordinator supplies 1B.2A independent approval; current main and local
origin/main are 28d14d29c34a5aee95778237659d70ab86eaaff6. Historical verdicts above
remain unchanged. Real Chromium/Next Worker acceptance is NOT VERIFIED.

Exactly five authorized candidate paths:

- frontend/e2e/fixtures/financial-insights-browser.ts (new)
- frontend/e2e/financial-insights.spec.ts (new; exactly one desktop case)
- frontend/e2e/fixtures/browser.ts
- frontend/tests/qa01-harness.test.mjs
- this ExecPlan

Step 0 passed before writes: main/exact HEAD, empty index, exactly the original
three protected exceptions, and all three protected SHA-256 values match the
preceding record. Committed component/client/Worker/fixture hashes match preflight;
the original fixture remains 491733790CD78DC2A143295B196D41F2891AEB47F7293072C70CBB027D16B36A.
No private configuration or report contents were read.

Implementation stages: clone/rebase the complete fixture identity; admit only the
two exact insights query forms; correct disabled-AI capabilities; synchronize
automatic discovery without requiring comparison or changing existing assertions;
author the native-Worker case; run targeted offline regressions/type/lint/listing;
verify scope, preservation and self-review. No browser/service/build/container,
installation, data/provider operation, staging, commit or push is authorized.

Decision: successful insights fixtures support only AAA/0000900001 at 0 and
BBB/0000900002 at 1, with FY2024/FY2025. Existing generic recovery scenarios move
AAA to versions 1/2. Those versions must retain generic behavior and independent
obsolete-pin 409 handling, but receive a bounded current-pin insights 503 rather
than inventing an unauthorized successful publication. Shared readiness must
permit this explicit terminal failure and never wait for comparison or unrelated
held requests. The new browser case requires successful baseline discovery.

Progress: preservation complete; implementation and offline validation pending.
The overall plan stays active. Supported Linux runtime verification and separate
execution authorization remain prerequisites; mobile/zoom/accessibility, native,
pilot and deployment acceptance remain deferred.

## Frontend 1B.2B implementation and resumed verification — 2026-10-27

Resumed in the same conversation after a usage interruption; no implementation
restart. Before additional writes, all five candidates existed, main/HEAD remained
28d14d29c34a5aee95778237659d70ab86eaaff6, index was empty, and inventory was exactly
five candidates plus the three original protected exceptions. All protected hashes
matched. The prior log establishes an initial 26/26 harness pass, followed by an
expanded QA-01 run with 38 passes and four Linux-only skips, successful noEmit and
scoped lint, and listing of 79 project cases across six files (one new desktop
case). The interrupted financial/API run had no recoverable final completion
result; its session was unavailable, so it was restarted as an offline regression.
No browser or service ran before or after interruption.

### Implemented behavior and identity decisions

The new browser adapter clones the unchanged committed fixture and rewrites only
identity fields. AAA/0000900001 publication/facts/evidence 0 and BBB/0000900002
publication/facts/evidence 1 are the only successful synthetic publications. Years
remain FY2024/FY2025. Scope rebasing covers the root, every node, edge, and statement
reference; source rebasing covers raw sources and nested canonical provenance and
alternatives. Reserved accessions ending 100001 avoid conflicting with generic
QA-01 filing metadata. Canonical SEC index URLs match each adapted CIK/accession.
Fact IDs, graph keys/relationships, F/D categories, amounts, formulas, changes,
percentages, statuses, and server-authored statement text are retained. This is an
insights-only dataset, not a reconciliation with generic snapshot amounts.

Interception admits only exact GET insights discovery or comparison 2024 -> 2025
for known issuers, null/absent HTTP bodies, canonical safe-integer publication pins,
and no duplicate/extra query parameters. Parameter order may vary; the production
request spelling is asserted exactly in the browser case. Unknown modes/years/
routes, malformed/future pins, unknown issuers, and non-GET methods fail closed.
Even a literal JSON null or empty HTTP body is rejected. Existing obsolete-pin
409 determination still precedes fixture generation. Existing external/HMR rules,
limits, deny-all upstream and teardown remain intact. Capabilities now supply the
complete disabled-AI sec_readonly contract without changing the API client.

Shared ready() retains its original three assertions and adds only a terminal
automatic-discovery wait before request-count baselines. Successful baseline
publications must show the exact choose-compare status. Unprovided current AAA
versions 1/2 must show the exact existing generic insights error status. Readiness
does not request/wait for comparison, release held requests, call refresh, or
change scenario versions. Four offline Locator-protocol tests exercise the real
readiness method and installed assertion library, including a deliberately held
unrelated gate. These are protocol stubs, not DOM or browser acceptance.

### Recovery and 503 self-review

Inspected every ready() call and relevant hold/count assertion in recovery.spec.ts,
research.spec.ts, comparison.spec.ts, experience.spec.ts and sec-nlp-01b.spec.ts.
Existing malformed/unverified pins remain request-free; held freshness is released
before ready(); source retry and same-pin checks keep their existing assertions;
obsolete 0 -> 1 / 1 -> 2 snapshot deliveries retain cancellation and freshness-count
checks. No existing spec/assertion was edited.

The unprovided-publication response is a pinned 503 with
QA01_INSIGHTS_PUBLICATION_UNAVAILABLE, not DATA_VERSION_CHANGED. Two new offline
regressions send that actual Scenario response through getFinancialInsights,
InsightsPanel, and the committed Worker protocol runtime at AAA versions 1 and 2.
Each rejects with the exact 503 code, makes exactly one insights fetch, terminates
the session, leaves zero Worker listeners/retained nodes, triggers zero publication
reconciliation callbacks, and permits the real pinned summary client both before
and after failure. Old-pin 409s are independently checked before this branch.
This establishes bounded transport isolation; actual React/Chromium transition
ordering and original browser-suite counts remain unverified until authorized.

### Authored desktop acceptance case

Exactly one case has the authorized title and a 90-second runner timeout. It
captures native page Worker events before navigation, verifies same-origin Next
asset URLs and a live DedicatedWorkerGlobalScope, and requires discovery completion
and an explicit comparison request with pin zero. Neither global Worker nor
Worker JavaScript is replaced. All seven metric expectations are independent
literals; five-headline completeness, reporting periods and F/D separation are
asserted. Statement navigation follows later FCF -> CapEx operand -> CapEx
observation -> source 10, checking focus, full reference/scope, exact flattened
fields and safe SEC link attributes without external navigation. F pages are
replaced on Next/Previous, D replaces F, each page has at most 25 records, the
comparison Worker stays owned/live, and page operations add no insights HTTP fetch.
A persistent offline test verifies these fixed amounts, target-page lookups and
lineage fields against production admission/presentation; it does not claim UI
focus or native Worker acceptance.

### Offline verification actually completed

Working directory for the following commands: D:\Projects\finlens-foundation\frontend.

```
node --test tests/qa01-*.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js e2e/fixtures/financial-insights-browser.ts e2e/fixtures/browser.ts e2e/financial-insights.spec.ts tests/qa01-harness.test.mjs
node node_modules/@playwright/test/cli.js test --list --reporter=list
```

Final QA-01 result: **41 passed, 0 failed/cancelled/todo, 4 Linux-only skips**
(45 total), 10.0686149 seconds. This contains all 18 prior portable cases and 23
new cases; four genuine Linux process-tree cases remain explicitly skipped here.
Both positive issuer/mode pairs pass actual lexical preflight, whole-response
admission and presentation. Negative cases reject nested source CIK/URL, graph and
statement scope corruption, publication mismatch, invalid request selectors and
pins. In-memory installed-route tests retain external/API/3108 blocking and HMR-only
WebSocket behavior. Original fixture byte hash and complete graph relationships
are checked persistently. No real HTTP/network request occurs in these tests.

TypeScript noEmit and scoped ESLint: exit 0, no diagnostics. Listing: exit 0,
79 project cases in six files; exactly one new insights case in desktop-chromium,
none in mobile-width-chromium. Listing does not launch the configured webServer.
Tracked candidate git diff --check and fatal UTF-8/no-NUL/trailing-whitespace/
final-newline checks across all five candidate files passed. The first draft's
23-pass/3-fail result was corrected before interruption: two tests had wrongly
expected absent rather than zero-page F/D discovery collections, and an undefined
pin test had accidentally used its helper's default pin. These were test-expectation
errors; final results above supersede that draft without changing production code.

Additional offline regression completed:

```
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
```

Result: **261 passed, 0 failed/cancelled/skipped/todo**, 186.779079 seconds, exit 0.
The guarded synthetic Backend 1A serialization ran through the existing test
runner, not a backend service or database. Existing worker transport/lifetime,
current/obsolete version guards, exact publication-tuple comparison binding and
shared API regressions all passed. Node emitted the pre-existing typeless-package
module warning; no package/dependency change was made. Combined final executed
coverage: **302 passed, 0 failed, 4 explicit Linux-only skips** across the two
commands. The earlier interrupted run is not counted.

### Deferred gates and independent review

Supported Linux runtime/checkout, Node 24 with Linux dependencies, installed pinned
Chromium/system libraries, /proc ownership verification, temporary-directory access
and free 3107/3108 ports must be independently established. No WSL/container,
dependency or browser installation/startup was attempted. A separately authorized
run must prove actual Next module-Worker emission/execution, all new browser
assertions/focus, existing QA-01 browser regression and Linux lifecycle cleanup.
390px/320px, actual browser zoom, manual keyboard/accessibility/NVDA, native/pilot
and deployment acceptance remain deferred. No production build acceptance claimed.

Astra High should review exact identity-only rebasing/source chronology, fixed
publication limits and independent stale-pin handling, canonical request/body/query
admission, shared terminal readiness under held/current/obsolete publications,
503 cleanup/no-reconciliation evidence, and native-Worker/pagination/focus assertions.
No file outside the five-path allowlist is needed or modified. No outstanding
implementation defect was found in this self-review; runtime compatibility is an
unresolved acceptance gate. No staging, commit, push or deployment is authorized.

### Final preservation and handoff

The only candidate source hashes (SHA-256) are:

- frontend/e2e/fixtures/financial-insights-browser.ts: 39C7A7B10D789BBC521D2AAC8F817C4916D1B88EBA03C6B8918438868C59CC04
- frontend/e2e/financial-insights.spec.ts: 4C05953A0F07464D280A4FB870D5911BB16AFB936ABBE3AEE3DC0092EC7DC9BD
- frontend/e2e/fixtures/browser.ts: 7904258AA71C7462EE2A98C02E7D5E076210BCE0E3E1E795FBAB7E99178581D0
- frontend/tests/qa01-harness.test.mjs: 8BB35AD8ACEBE27674E42443B1CBDA48942E5981E5434322BEBA084A6088AC5E

The fifth candidate is this appended ExecPlan; its final byte hash belongs in the
handoff report rather than a self-referential value here. The three protected
fingerprints remain:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Committed component/client/Worker, original fixture, generic data, existing browser
specs, Playwright config, launcher/process-group scripts, dependencies, workflow and
runbook remain unchanged. Candidate inventory is exactly the five paths listed in
the authorization; branch main/exact baseline and empty index retained. Protected
reports were hashed only. Nothing was staged, committed or pushed.

- [x] Preserve baseline and reconcile interrupted implementation/tests.
- [x] Complete test-only adapter, exact routing/capabilities and shared readiness.
- [x] Author one desktop case and persistent admission/recovery regressions.
- [x] Finish authorized offline regression, noEmit, scoped lint, listing and text checks.
- [x] Self-review and record exact scope, fingerprints and limitations.
- [ ] Independent Astra High review and coordinator decision.
- [ ] Independently verify supported Linux prerequisites and separately authorize execution.
- [ ] Real Chromium/Next module-Worker and Linux cleanup acceptance; existing browser regression.
- [ ] Separately scoped mobile/zoom/accessibility/native/pilot/deployment gates.

Proposed later invocation, NOT RUN, from the approved Linux frontend directory:

```
npm run test:e2e -- e2e/financial-insights.spec.ts --project=desktop-chromium --grep '^FIN-DEPTH-01 real Worker annual discovery comparison and evidence navigation$'
```

Use the existing QA-01 runbook's isolation precheck and runner-owned teardown;
neither cleanup nor network rules are changed by this patch. Stop here for
coordinator/Astra review. Suggested later commit message:
`test: add isolated annual financial insights browser acceptance`.

## QA-01 cross-platform fixture checksum correction — 2026-10-27

Coordinator authorized exactly two candidate files: frontend/tests/qa01-harness.test.mjs
and this appended ExecPlan. Before writes: main/HEAD ed718c2fcc781213d49812c1d746b0105df7244d,
empty index, only the original three protected exceptions, and all protected
SHA-256 fingerprints matched. The fixture's Windows checkout bytes remain
491733790cd78dc2a143295b196d41f2891aeb47f7293072c70cbb027d16b36a.
Ignored private backend/.env remains untouched and unread.

Incident: push-triggered Frontend browser E2E run 40431066500, attempt 1,
job 121948564760, SHA ed718c2fcc781213d49812c1d746b0105df7244d:
https://github.com/alaniong0118-alt/finlens/actions/runs/40431066500
Hosted Ubuntu 24.04.5/Node 24.21.0 completed npm ci, then QA-01 reported
44 passed, 1 failed, 0 skipped. The sole failure was the raw-checkout fixture hash.
Chromium installation, isolated launcher precheck and browser tests/teardown were
skipped. Four Linux process-tree integration tests passed; synthetic capture was
skipped. This is historical CI evidence, not a new run or browser acceptance.

Root cause: the test pinned Windows CRLF SHA-256
491733790cd78dc2a143295b196d41f2891aeb47f7293072c70cbb027d16b36a,
while the committed Git/Linux LF SHA-256 is
afad566f1ee89ba285f51559bc60ce439d50d2580327ffe1776e2a02ef35b27b.
Read-only comparison showed exactly four CRLF-to-LF substitutions and otherwise
identical bytes. The Windows digest remains historical preservation evidence;
the independent canonical Git digest is the portable content expectation.

Correction plan: verify every CR is followed by LF, remove only those CR bytes
into a separate in-memory buffer, and require the fixed canonical LF checksum.
No decoding/re-encoding or other content normalization is needed. Preserve all
existing graph/reference/identity/admission assertions. Add bounded simulated
LF/CRLF positives, a non-newline byte mutation negative, and malformed CR negatives.
Do not edit the original fixture, production/browser/isolation code, Git settings,
workflow or dependencies. Run only the specifically authorized offline commands;
results and final preservation checks pending below. No browser/services/CI rerun,
installation, staging, commit, push or external data request is authorized.

Implemented in qa01-harness.test.mjs:193-237: a byte-oriented checksum helper
asserts each CR byte is followed by LF, removes only that CR in a separate buffer,
and compares SHA-256 against the fixed independently verified LF digest above.
The original input buffer is never modified. Existing graph/reference/identity/
admission assertions follow the helper call unchanged. No text trimming, UTF-8
replacement, financial recomposition, dynamic expected hash, or fixture write is
part of checksum verification.

Four bounded regressions use memory buffers only: canonical LF acceptance,
equivalent CRLF acceptance with input immutability, a single non-newline byte
mutation rejected by the fixed digest, and malformed carriage returns rejected
before hashing. The latter covers leading/trailing lone CR, CRCRLF, and LFCR.

Actual commands from D:\Projects\finlens-foundation\frontend:

```
node --test tests/qa01-*.test.mjs
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js tests/qa01-harness.test.mjs
```

QA-01: **45 passed, 0 failed/cancelled/todo, 4 explicit Linux-only skips**
(49 total), 10.1080905 seconds, exit 0. The four new checksum cases and existing
graph/admission/isolation/readiness/recovery checks all passed. Simulated LF/CRLF
coverage is not a claim that Linux was launched. TypeScript noEmit/nonincremental
and scoped ESLint: exit 0, no diagnostics. Existing financial/API regression:
**261 passed, 0 failed/cancelled/skipped/todo**, 180.0927417 seconds, exit 0.
Combined executed coverage: **306 passed, 0 failed, 4 explicit Linux-only skips**.
No test deselection or browser execution occurred.

Self-review: the checksum normalizes only valid CRLF representation, preserves all
other bytes, and rejects every other content change against a literal Git digest.
The test diff retains all previous graph checks. The plan diff is append-only;
no historical finding, correction or approval is rewritten. No change outside the
two-file scope is needed. git diff --check and exact two-candidate/three-exception
inventory checks passed. Fixture, production/browser/configuration/dependency/
workflow/Git-setting paths remain unchanged. Browser/Next module-Worker acceptance
is still NOT VERIFIED; no CI rerun or browser/services were attempted.

Final preservation: main remains ed718c2fcc781213d49812c1d746b0105df7244d, index
empty, exactly the two authorized candidates plus the original three protected
exceptions. The fixture's raw Windows SHA-256 and all three protected fingerprints
match the established baselines above. Ignored backend/.env was not read or edited.
Fatal UTF-8/no-NUL/trailing-whitespace/final-newline and final exact-scope/whitespace
checks passed. No production/browser/Worker/isolation/config/workflow/dependency or
Git line-ending setting changed. No remaining correction defect found offline.

Ready for focused independent Astra review of byte-only normalization, rejection
before hashing, fixed canonical digest, positive/negative regressions, preserved
graph assertions and exact scope. Stop for coordinator review; no staging, commit,
push or rerun. Suggested later commit:
`test: make insights fixture checksum portable`.

## Native evidence focus ownership P2 repair — 2026-10-27

Coordinator authorizes exactly four candidates: components/financial-insights.tsx,
tests/financial-insights-interactions.test.mjs, e2e/financial-insights.spec.ts (all
under frontend/), and this appended ExecPlan. Before writes: main/HEAD
ec20b628d861994813105bed1eff764e1b1a40d1, empty index, only the original three
protected exceptions; their hashes and the original fixture's Windows byte hash
491733790CD78DC2A143295B196D41F2891AEB47F7293072C70CBB027D16B36A match.
No private configuration was read. No browser, services, build, CI, dependencies,
database/provider operation, staging, commit, push or deployment is authorized.

Historical evidence: run 40435559542 / job 121963274546 at this SHA reported
49 QA-01 passes and Chromium 78 passes / 1 failure; capture skipped. Artifact
12703662394 and its trace confirm DedicatedWorkerGlobalScope, comparison and seven
metrics passed. Later FCF appeared on F page 5 of 8 by click completion, but the
article remained inactive for five seconds. Neither the transient activeElement
nor disabled interval was captured. Native loss of focused-trigger ownership when
paging disables it remains the supported explanation, not a proven body-focus log.
The old guard rejects any connected trigger after it loses focus and consumes the
pending request before returning. Historical reviews and incidents remain intact.

Repair plan: capture a per-navigation focus ticket before request/pending UI work;
retain it through Worker completion and React commit. A ticket begins owned only
when its trigger owns focus at activation. Capture-phase focusin/pointerdown/keydown
listeners revoke on later intent elsewhere, including a move away then back to
body. Capture phase avoids consuming the original activation's bubbling event.
Completion can recover application-caused body focus loss only with the original,
unrevoked ticket and all existing generation/owner/handle/target checks. Duplicate
and busy navigation must not replace tickets. Clear listeners/tickets on completion,
failure, invalidation, expiry, cancellation, replacement and StrictMode cleanup.

Add explicit offline disabled-blur simulation, pointer/keyboard activation,
lineage/page focus, genuine intent/body return and lifecycle/stale/listener tests.
Keep native-browser assertions; add bounded failure diagnostics without focusing
targets or changing Worker/network/deadline behavior. Planned gates: complete
interaction, contract/API and QA-01 offline suites, noEmit, scoped lint and exact
scope/hash/whitespace review. Implementation and actual results pending below.

Implementation completed in the four-file scope. PageFocus now holds activation
ownership, completion state and an idempotent listener release function. Capture
listeners revoke ownership on later outside pointerdown, focusin or keyboard
navigation; revocation survives a subsequent return to body. The layout effect
consumes only a completed ticket with the original generation, owner, handle,
collection, page and exact record validation. An owned ticket can recover focus
from body after the trigger is disabled or removed. Merely observing body never
grants ownership. Existing coalesced/busy guards run before ticket creation.
All completion/error/lifecycle paths release listeners, including synchronous
request failure, disposal, expiry, generation changes and StrictMode unmount.

Regressions explicitly model JSDOM's missing native disabled-control blur by
momentarily enabling the disabled trigger, blurring it, then restoring disabled
before held Worker completion. They never focus the expected destination. This
is simulation of the native gap, not proof of repaired Chromium behavior.
Coverage includes pointer/Enter/Space activation, connected and naturally removed
triggers, FCF-to-CapEx-to-source lineage, Previous/Next viewport focus, deliberately
moved focus, return to body, outside pointer intent, Tab/other keyboard intent,
unowned body activation, duplicate/coalesced/busy calls, and strict/non-strict
year/company/publication/cancel/expiry/page-timeout/Worker-failure/unmount cleanup
with stale delivery. Each mount also checks zero remaining document navigation
listeners alongside existing Worker, timer and retained-byte cleanup assertions.

The Chromium spec retains the original toBeFocused assertions and five-second
focus wait. Passive diagnostics use a 64-event ring and one disabled-attribute
observer; failure attachments record active/trigger/target identity, bounded
control labels, connected/disabled/rendered state, viewport/page/busy status and
observed activation/intent/publication ownership. Internal generation/handle are
explicitly not exposed. Listeners and observer are released in finally. No editor
values/typed keys, new requests, fake Workers, manual destination focus, retries
or extended deadlines were introduced.

Offline execution from frontend/: initial full interaction suite passed 94/94,
zero failures/skips, 199750.9193 ms. The financial/API command
`node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs` passed
261/261, zero failures/skips, 183568.8499 ms. The QA-01 command
`node --test tests/qa01-*.test.mjs` passed 45/49 with four explicit Linux-only
process-tree integration skips, zero failures, 9862.3299 ms. No test deselection
was used. TypeScript `node node_modules/typescript/bin/tsc --noEmit --incremental
false --pretty false` and scoped ESLint over the component, interaction test and
browser spec both exited 0 without diagnostics, including after final diagnostic
label and regression refinements. The final interaction rerun additionally
covers Tab dispatched at the original trigger and the component's rejected busy
navigation, rather than only the underlying handle's busy rejection; result and
final preservation checks follow below.

Final interaction command `node --test tests/financial-insights-interactions.test.mjs`
passed **95/95**, zero failed/cancelled/skipped/todo, 189175.9597 ms, exit 0.
All 62 original cases remain; 33 focused cases were added. Final distinct suite
coverage is **401 passed, 0 failed, 4 Linux-only skips** (405 total cases).
TypeScript and scoped ESLint both passed again after the final source/test edits.
Git whitespace, fatal UTF-8/no-NUL/newline hygiene, exact four-candidate plus
three-exception inventory, original focus-assertion count and append-only plan
history checks passed. Main/HEAD remain ec20b628d861994813105bed1eff764e1b1a40d1;
index is empty. All three protected SHA-256 baselines and fixture raw Windows
digest 491733790CD78DC2A143295B196D41F2891AEB47F7293072C70CBB027D16B36A
remain unchanged. Ignored backend/.env exists and was never read or written.

Final source candidate SHA-256 fingerprints:

- frontend/components/financial-insights.tsx:
  C44C7E6CBA952030C6FF028B91FCD1E3DD4A7D6835C6510C2FC2628B97462420
- frontend/tests/financial-insights-interactions.test.mjs:
  82E9E8E9E00D51698BE9BBCFE5E06EA36113B4B423CBB0BE4FA7F4E3EE2ACDCC
- frontend/e2e/financial-insights.spec.ts:
  8E8CDF221CC8B486D885661EC9FF19B6528D332B1EE11186D2DF4775724874E4

Self-review found no outstanding offline correction defect. The historical
connected-trigger rejection is corrected; the native disabled-trigger cause
remains an evidence-supported hypothesis because the failed trace omitted the
transient active element. No repaired Chromium or Linux process cleanup result
is claimed. Browser diagnostics are type/lint checked but have not run in a
browser. Worker construction, financial/provenance contracts, QA-01 network rules,
configuration, dependencies and workflows are untouched. No browser/build/services,
CI rerun, staging, commit or push occurred.

Ready for independent Astra review of activation ownership/event ordering,
irreversible user-intent revocation (including body return), completed-ticket
generation/handle checks, synchronous/asynchronous cleanup, busy/coalesced calls,
StrictMode listener ownership, simulation limitations and passive diagnostics.
Stop for coordinator review. A subsequent authorized Linux Chromium run remains
necessary for native acceptance. Suggested later commit:
`fix: preserve evidence navigation focus ownership`.
