# CC-02: bounded annual comparison expansion

Status: active — READY FOR GIT STEP 1 under coordinator control.
Final qualified synthetic browser acceptance and independent reviews have passed;
deployment is NOT approved.
Roadmap phase: Complete Research Mode, bounded company comparison increment.

Current decision (2026-10-16): Astra financial/cross-layer and final accessibility
reviews are PASS WITH CONDITIONS, with no blocking defect; the coordinator has
dispositioned both nonblocking P3 findings as recorded in the
[current final outcome](#current-final-outcome--coordinator-reconciliation-2026-10-16).
The stage records below preserve earlier failures and stop decisions as history;
they do not supersede that current decision. Keep this active path unchanged.

## Objective

Expand the existing read-only 2–4 company annual comparison from seven to eleven
metrics by appending Gross Profit, Operating Income, Net Income and Gross Margin.
Reuse established observations, financial calculations, units and source lineage.

## Current architecture and context

Starting branch: main. Verified HEAD: bde1a16c497db098cf78fe17dd89279958ccbcfc.
The Git index is empty. FinancialMetrics owns selection/calculation; annual_comparison
unions metric anchors and requires one exact annual window. The client validates
exact metric keys, units, company, dates and lineage. Existing requests retain one
independent publication pin per company, including verified zero.
See [roadmap](../../../ROADMAP.md), [plan rules](../../../.agent/PLANS.md), and
[financial contracts](../../financial-metrics.md).

Protected pre-existing files and verified starting SHA-256:

| File | SHA-256 |
|---|---|
| frontend/next-env.d.ts (modified) | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json (untracked) | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json (untracked) | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

## Constraints

Initial annual-expansion scope (later focus/browser authorizations are recorded
below): only the four approved metrics and directly related contracts, tests,
fixtures and documentation. Existing dependencies and synthetic fixtures only.
No database I/O,
SEC/provider calls, model loading, services/deployment, installations, staging,
commit or push. Preserve protected bytes. Stop if broader financial semantics are
needed. Keep this plan active for coordinator-controlled Git Step 1. This
documentation reconciliation authorizes no staging, commit, push or deployment.

## Non-goals

EPS, balance-sheet instants, quarterly/YTD comparison, new mappings/formulas or
authorizations, ranking, cross-company arithmetic, UI redesign and later milestones.
Do not rerun completed historical audits or treat the qualified synthetic browser
runs as live-provider, default development badge or production deployment acceptance.

## Implementation stages — historical initial annual expansion

1. Extend backend/client allowlists; classify Gross Margin as ratio. Keep existing
   seven-row ordering and append the four additions in approved order.
2. Add pure synthetic coverage for income anchors/ambiguity, exact annual windows,
   formula/provenance parity, scope rejection, banking states and version zero.
   Update mounted and browser fixtures; exercise real backend serialization in the
   real client validator, including available Gross Margin.
3. Document eleven-metric contract, exclusions and coordinated client/server delivery.
4. Run focused offline regressions, TypeScript without emit/incremental output,
   scoped ESLint, whitespace and preservation checks; self-review the exact diff.
5. Report READY FOR ASTRA REVIEW or BLOCKED and stop. Recovery is reverting only
   this increment's diff; no durable data or configuration changes are involved.

## Decisions

- 2026-10-16: Keep the existing endpoint and response types. Selected-year metrics
  expand to exactly eleven; discovery remains empty. Old strict clients reject the
  changed count, so coordinated frontend/backend delivery is required, not rolling
  mixed-version compatibility. No deployment is authorized here.
- 2026-10-16: Discovery includes annual anchors from all eleven metrics. New income
  anchors may reveal conflicts and make a previously selectable window ambiguous;
  all rows must then be unavailable. Never prefer revenue or choose per-row dates.
- 2026-10-16: Preserve annual end-year labels, 52/53-week YoY date checks, global
  reporting_periods(), signed income, exact Decimal values, input/alternative
  provenance, denominator permissions and same-accession Gross Margin checks.
- 2026-10-16: Side-by-side reported values do not establish equivalent issuer
  accounting scope. Preserve date/basis warnings and independent publication pins.

## Discovered issues

The mounted fixture has a separate ratio list and hard-coded seven-row/28-cell
counts; browser fixtures have another seven-metric list. Update these explicitly
and verify contract parity so an unavailable-only fixture cannot hide a unit defect.

The first backend run passed 88 tests but had four TestClient setup errors because
the new raw-socket guard intercepted Windows asyncio's internal signalling
socketpair. The guard now wraps application request execution after portal setup;
database, provider and model sentinels stay active throughout. The rerun passed
92 tests. No product-code change or weakened financial rule was required.

## Progress

- [x] 2026-10-16: Read root instructions and plan rules; verify expected main HEAD,
  empty index, exact three-file starting status and protected hashes before writing.
- [x] 2026-10-16: Implement approved allowlists and directly related tests/fixtures/docs.
- [x] 2026-10-16: Execute focused checks and self-review; protected hashes unchanged,
  expected HEAD retained and index empty.
- [x] 2026-10-16: Initial READY FOR ASTRA REVIEW handoff recorded before the
  independent reviews; its original stage outcome is retained below.
- [x] 2026-10-16: Astra financial/cross-layer review: PASS WITH CONDITIONS,
  no blocking defect (coordinator-reported independent result).
- [x] 2026-10-16: Qualified isolated Chromium desktop/mobile two/four-company
  acceptance complete; the final mobile two-company scratch override is recorded below.
- [x] 2026-10-16: Final Astra accessibility review: PASS WITH CONDITIONS,
  GO for coordinator-controlled Git Step 1 (coordinator-reported independent result).
- [x] 2026-10-16: Reconcile this plan only; record both coordinator P3 dispositions.
- [ ] Coordinator-controlled Git Step 1; no staging or commit performed in this task.

## Test and validation strategy — historical initial offline scope

This section records the initial annual-expansion stage. Subsequent authorized
focus/browser validation and the current qualified acceptance are recorded below.

Validation scope: backend comparison and financial
explanation tests with synthetic objects/mocked sessions; frontend comparison/API
tests and real backend-to-client serialization; TypeScript and scoped ESLint.
Cover exact eleven-key order, each income-only year, deduplication, newly exposed
ambiguity, wrong periods/units/company, zero/negative income, Gross Margin scope/
accession/denominator rejection and banking not_applicable. Retain existing YoY,
cash-flow and request lifecycle tests. Browser specs may be updated/typechecked
but no browser or running service acceptance is claimed. Avoid Next build because
it can overwrite protected next-env.d.ts.

Interim executed checks (2026-10-16):

- backend: `$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -B -m pytest
  -p no:cacheprovider tests/test_company_comparison.py
  tests/test_financial_metric_explanations.py -q`: 92 passed after the fixture
  correction above; existing Starlette/httpx deprecation warning only.
- frontend: `node --test --test-reporter=spec tests/company-comparison.test.mjs
  tests/finlens-api.test.mjs`: 104 passed, zero failures/skips. Includes real backend
  serialization with available Gross Margin, zero/one publication pins and rollover.
- frontend: `.\node_modules\.bin\tsc.cmd --noEmit --incremental false` and
  `.\node_modules\.bin\eslint.cmd lib/company-comparison.ts e2e/fixtures/data.ts
  e2e/comparison.spec.ts`: passed, no warnings/output.
- Additional week-calendar provenance assertions and direct browser-fixture/client
  validation were added after these runs; final reruns and preservation checks pending.

Final executed checks (2026-10-16, after all code/test changes):

- backend, same pytest command above: **92 passed**, no failures/skips, existing
  Starlette/httpx deprecation warning only. Comparison fixtures are synthetic and
  API sessions are mocks; no database was contacted or written.
- frontend: `node --test --test-reporter=tap tests/company-comparison.test.mjs
  tests/finlens-api.test.mjs`: **105 passed**, zero failures/cancellations/skips.
  This includes real backend serialization, available Gross Margin/input/source
  validation, signed income, independent zero/one pins, all four added metrics'
  malformed unit/window/company/source negatives, and browser-fixture validation
  for both test issuers and discovery/FY2024/FY2025. No browser was launched.
- frontend, same TypeScript/scoped ESLint commands above: **passed**.
- repository root, read-only Python AST comparison against HEAD: the entire
  financial service is identical except ANNUAL_COMPARISON_METRICS. All functions,
  including annual_comparison, calculate, observation and reporting_periods, retain
  identical ASTs. Only the allowlist and one explanatory comment changed.
- repository root, `git diff --exit-code HEAD --` over metric registry/schemas,
  revenue authorizations, SEC evidence adapter, freshness service, main routes,
  frontend transport/formatters and comparison component: **passed**, unchanged.
- repository root, `git diff --check`: **passed**. Protected-file SHA-256 values
  match all three starting values. HEAD and empty index reverified.
- Explicit read-only trailing-whitespace/single-EOF checks on all eight CC-02
  files, including this untracked plan: **passed**.

Self-review: production changes are confined to backend/client metric lists and
the client's Gross Margin ratio classification. No weakened validation, formula,
permission or period fallback. Annual-window ambiguity newly exposed by income
anchors fails closed as approved. Existing request counts and independent pins
are covered by mounted tests. Browser fixture changes are typechecked and passed
through the real client validator; this is not visual/mobile acceptance. No Next
build, live application/database/provider/model/deployment or historical audit ran.

## Completion criteria

Only approved metrics added; calculations/authorizations/version machinery unchanged;
focused tests and static checks pass; protected hashes unchanged and index empty;
actual commands/results and limitations recorded. Independent Astra financial/
cross-layer and final accessibility reviews are PASS WITH CONDITIONS, as reported
by the coordinator. Qualified synthetic Chromium acceptance covers all four cases.
Both P3 dispositions are recorded below. The current stop boundary is READY FOR
GIT STEP 1 under coordinator control; coordinated backend/frontend delivery and
rollback remain mandatory, and deployment is NOT approved.

## Final outcome — historical initial annual expansion, before focus correction

Historical handoff only; subsequent review and acceptance decisions are recorded
in the current final outcome. The initial results and restrictions follow unchanged.

**READY FOR ASTRA REVIEW** — approved seven-to-eleven annual expansion implemented
and focused offline checks passed. Keep this plan active pending independent Astra
review of the exact diff and coordinator disposition. Astra must independently
verify income-only/conflicting anchors, unchanged financial permissions/formulas,
serialized eleven-metric client acceptance, Gross Margin scope/accession gates,
publication zero/missing/stale behavior, protected bytes and coordinated delivery.

Changed files: backend/app/financial_metrics_service.py;
backend/tests/test_company_comparison.py; frontend/lib/company-comparison.ts;
frontend/tests/company-comparison.test.mjs; frontend/e2e/fixtures/data.ts;
frontend/e2e/comparison.spec.ts; docs/financial-metrics.md; this new active ExecPlan.
No schema, transport, rendering component, calculation or authorization file changed.

Git remains main at bde1a16c497db098cf78fe17dd89279958ccbcfc. Seven tracked CC-02
files modified and this ExecPlan untracked; index empty. The pre-existing modified
next-env.d.ts and both untracked runtime reports are byte-preserved. Nothing staged,
committed or pushed. No dependencies installed, data writes or deployment performed.
Suggested commit, only after later authorization:
`feat: expand annual company comparison to eleven metrics`.

## Historical stage: approved localized keyboard-focus correction — 2026-10-16

This is the horizontal-only stage record. Its failures and stop decision are
preserved; later vertical remediation and qualified acceptance supersede its blocker.

Coordinator approval covers exactly frontend/components/company-comparison.tsx,
frontend/tests/company-comparison.test.mjs and this active record. Starting main
HEAD remains bde1a16c497db098cf78fe17dd89279958ccbcfc; index empty. All three
protected SHA-256 values above were reverified before writing. Existing CC-02
changes and retained browser/investigation evidence are preserved separately by hash.

Read-only Chromium investigation reproduced the same defect in seven-metric HEAD
and eleven-metric CC-02: partially visible native summary focus is not fully
revealed. At 390px the 322px scroll interior clips 216px/176px controls plus their
3px outline and 3px offset. Both Tab and Shift+Tab reproduce it. No sticky columns
or headers exist; computed positions are static. No CSS or sticky-layout change
is needed or authorized.

Implementation: one comparison-local focus-capture handler, limited to keyboard-
visible provenance descendants (including nested summaries and source links).
After native focus scrolling, measure the scroll interior and complete indicator,
then apply the minimum clamped horizontal delta only when required. Preserve native
keys, active element, vertical scrolling, touch panning, selections and all request/
financial behavior. No timer, deferred callback, shared component or new dependency.

Planned validation: mounted geometry regressions for left/right/no-op/clamping,
pointer/touch exclusion and focus/selection/request/pin preservation; comparison
frontend tests, TypeScript, scoped ESLint and whitespace checks. Then current-source-
bound real Chromium, two/four companies at 390x844 touch and a short desktop smoke:
Tab/Shift+Tab, expanded available Gross Margin, nested details/source links, complete
control/outline visibility, native touch movement and no correction-induced vertical
jump. Reuse the existing isolated QA-01 image and strict helper/port/root cleanup.
Do not rerun financial or full browser suites. Stop if broader scope is needed.

- [x] Verify pre-write branch/HEAD/index/protected hashes and preserve prior evidence.
- [x] Implement localized handler and focused mounted tests: minimum horizontal
  reveal with computed outline gutter; no deferred work or focus/key interception.
- [x] Initial checks: 39 comparison frontend tests passed (10 new focus cases),
  TypeScript and component-scoped ESLint passed. Real Chromium remains pending.
- [x] Execute focused real Chromium checks and retain failures without relaxing
  visibility assertions. Horizontal reveal passes all 144 reached focus checks;
  all four full-visibility scenarios fail at vertical viewport edges.
- [x] Self-review and process/port/root cleanup completed; no broader correction
  attempted. Stop with DEFECT REMAINS, pending coordinator scope decision.

### Focus correction validation actually executed

- frontend: `node --test --test-reporter=spec tests/company-comparison.test.mjs`:
  **39 passed**, zero failures/skips. Ten new mounted cases cover right/left
  clipping, four-company geometry, no-op, both clamp boundaries, pointer/touch
  exclusion, nested disclosures/source links, repeated focus stability, active
  element, vertical scroll, selections, request counts and publication pins 0/1.
- frontend: `.\node_modules\.bin\tsc.cmd --noEmit --incremental false` and
  `.\node_modules\.bin\eslint.cmd components/company-comparison.tsx
  tests/company-comparison.test.mjs`: **passed**.
- Real Chromium **156.0.8078.4**, Playwright **1.64.0**, existing immutable image
  `sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`.
  Four focused cases ran once, one worker, zero retries: two/four companies at
  1440x1000 and 390x844 with mobile touch enabled. Current source copies (30 files)
  and the actual served application (18 source/config hashes plus Next cwd) were
  verified. No image pull/build/install or repository-hosted server was used.
- All **144 reached focus measurements** passed horizontal bounds and control
  occlusion checks. First mobile disclosures moved only the container's scrollLeft:
  two companies 0→73 (control x=133..349), four 0→33 (x=173..349), inside the
  scroller's x=34..356 interior with the full 6px outline extent visible.
- Eleven captured PNGs of reached first/nested/Gross Margin/source-link focus
  states each passed **64/64 exact outline-color samples**. A read-only stdlib
  PNG reader was used because Pillow is absent; nothing was installed.
- Complete focus/outline acceptance nevertheless **FAILED in all four cases**:
  native vertical scrolling can put a focused control flush against the viewport,
  independently of the now-correct horizontal bounds. Two-company desktop reverse
  traversal: control top=5.4375, outline top=-0.5625. Four-company desktop forward:
  control bottom=1000.359375 in a 1000px viewport. Two-company mobile after expanded
  Gross Margin/source links: next BBB summary top=-0.15625. Four-company mobile:
  DDD Gross Profit summary top=0.234375, outline top=-5.765625. Each control still
  had all 15 interior hit-test samples visible; these samples alone do not prove
  complete control/outline visibility. The stronger boundary assertion was retained.
- Available Gross Margin, its source links and nested Gross Profit alternatives
  were reached/verified in the two-company cases. Four-company cases stopped before
  Gross Margin. Reverse navigation progressed only in the desktop two-company case
  before the vertical-edge failure. Pointer/native-touch and final no-vertical-jump
  phases were not reached this round. Earlier pre-fix touch acceptance is historical
  evidence only, not proof for this modified component.
- No further browser rerun or product fix was attempted after identifying the scope
  boundary. Vertical-edge baseline attribution was not separately investigated.
  The handler contains no vertical-scroll call, CSS, deferred work or focus changes;
  a complete vertical visibility policy needs coordinator approval under the explicit
  scrollLeft-only/no-page-vertical-scroll constraints.
- Strict cleanup passed despite failed assertions: deny-all upstream healthy,
  no isolation violations, both ports closed, launcher/runtime/home roots absent,
  no live helpers after a bounded 250ms telemetry-shutdown wait. The owned container
  was removed. Browser console errors were empty in all four cases.

Evidence retained outside the repository:
`C:\Users\IITSt\AppData\Local\Temp\finlens-cc02-focus-fix-zrdn0w8e`.
This contains source/served binding, Docker isolation, complete browser JSON/traces,
uncropped failure frames, PNG outline samples and the exact incremental patch.

### Focus correction outcome — historical horizontal-only stop

The following was the decision at that stage, not the current acceptance status:

> **DEFECT REMAINS.** The localized horizontal fix and regression tests remain
> unstaged in exactly the three authorized files. Do not claim READY FOR ASTRA FOCUSED
> REVIEW or complete mobile acceptance. Stop for coordinator disposition of the
> newly exposed vertical-outline acceptance gap; do not expand CSS/shared components,
> request lifecycle or vertical scrolling without separate approval. Financial,
> API/provenance/publication behavior and all unrelated CC-02 files remain unchanged.

Current disposition: the later authorized vertical correction and scratch-harness
acceptance resolved this stage blocker; see the current final outcome. The original
failed runs remain failed historical evidence.

Final preservation checks: only the three authorized files differ from this round's
pre-write snapshot; all other recorded source hashes and 185 historical evidence
files are unchanged. main/expected HEAD and empty index retained; all three protected
hashes match the original table. Scoped whitespace/EOF checks and git diff --check
passed. Removing the new helper/import/focus prop reproduces the pre-write component
text exactly, independently confirming unchanged rendering/request logic. No stage,
commit or push. The exact incremental diff and preservation proof are retained in
the external evidence root above.

## Approved minimal vertical focus reveal — 2026-10-16

Implementation status: complete; final qualified acceptance and independent review
are recorded in the current final outcome. The plan remains active for Git Step 1.
The coordinator approved exactly this plan, the comparison component and its tests. Expected main HEAD, empty index and
three protected hashes verified before writing. Snapshot of all tracked/untracked
files and all retained CC-02 browser evidence is stored outside the repository.

The read-only investigation attributed vertical outline clipping to native
Chromium in HEAD, pre-horizontal CC-02 and current CC-02. Existing horizontal
correction remains intact. Extend the same synchronous keyboard-visible provenance
focus handler to reveal genuine vertical clipping against the visible viewport,
including outline and safety gutter, with outward-rounded and document-clamped
movement. Preserve page X, container scroll positions, focus, selection and requests.
No timers, key interception, CSS/shared/backend or financial changes.

Planned: focused top/bottom/fractional/clamp/no-op/nested/link/pointer/touch and
combined-axis regressions; comparison tests, TypeScript, scoped ESLint, whitespace;
then isolated current-source-bound Chromium desktop/mobile two/four-company checks
with native Tab/Shift+Tab, Gross Margin/nested source disclosures, complete painted
outline, minimal scrolling, native touch and unchanged request/pin state. Retain
strict complete cleanup and stop for focused Astra review without staging/commit.

- [x] Pre-write preservation gates.
- [x] Local implementation and focused tests: 55 passed, including 16 new vertical
  cases and extended nested/source cases; existing horizontal cases retained.
- [x] TypeScript, scoped ESLint and whitespace checks passed.
- [x] Complete qualified synthetic Chromium acceptance: all four cases pass.
  The final mobile two-company case uses the hash-recorded scratch-only indicator
  override; original badge/route failures remain preserved below.
- [x] Self-review, full process cleanup and external incremental diff captured.
- [x] QA obstacle disposition and final Astra accessibility review complete:
  PASS WITH CONDITIONS, GO for coordinator-controlled Git Step 1. Both nonblocking
  P3 dispositions are recorded in the current final outcome.

### Vertical correction implementation and actual validation

The existing local guard and horizontal math are preserved. Computed outline
extent is separated from the unchanged 1px safety gutter. After horizontal reveal,
measure again; use visualViewport offset/height with layout fallback. Only genuine
paint clipping triggers document Y movement. Round outward and clamp to
scrollHeight-clientHeight, preserving page X and both container positions except
independently required horizontal reveal. Fully visible paint is a no-op even
when the extra safety gutter would cross the edge. No timer, observer, focus call,
key interception, selection/request change or CSS/shared-component change.

Executed from frontend:
- `node --test --test-reporter=spec tests/company-comparison.test.mjs`: 55 passed,
  0 failures/skips (39 existing + 16 new vertical cases). Existing nested/source
  cases now verify both axes. Clamp/no-range, fractional geometry, effective
  viewport, pointer/touch exclusion, repeated-focus no-op, focus, selection,
  disclosure state, request counts and publication 0/1 preservation covered.
- `.\node_modules\.bin\tsc.cmd --noEmit --incremental false`: passed.
- `.\node_modules\.bin\eslint.cmd components/company-comparison.tsx
  tests/company-comparison.test.mjs`: passed, including final scoped rerun.
- `git diff --check`: passed. No full financial/historical suite was rerun.

Real Chromium 156.0.8078.4, existing Playwright 1.64.0/Linux QA-01 image reused.
Thirty input/runtime and eighteen actually served sources/configs plus Next cwd
verified against current source hashes. Existing dependencies; no image build,
pull, installation, backend/provider/model activity or database access.

Historical bounded acceptance-v2 (one worker, no retries; the blocked mobile
two-company entry was superseded only by the final qualified run recorded below):
- desktop 1440x1000, two companies: PASS, 19 whole-control/outline measurements;
  correction Y range -5..+7px, page X stable; 13 expected API requests.
- desktop 1440x1000, four companies: PASS, 19 measurements; Y -5..+8px;
  19 expected API requests.
- mobile 390x844 touch, four companies: PASS, 19 measurements; Y -5..+7px;
  native touch pan 0->301px; page Y stable during pan; 19 expected API requests.
- mobile 390x844 touch, two companies: BLOCKED at the bottom-edge Gross Margin
  summary. All 11 reached viewport/outline geometry checks pass, but only 14/15
  interior hit tests pass: unchanged Next.js development badge overlaps the
  control/outline at the bottom left. The focus box is x=41..257,
  y=773.96875..836.84375 and outline y=767.96875..842.84375. Do not count
  geometric fit as complete painted/occlusion acceptance.

Passing cases exercise native Tab/Shift+Tab and exit/re-entry, expanded available
Gross Margin operands/provenance, nested Gross Profit alternatives and source
links, already-visible no-op, pointer exclusion and unchanged values/warnings/
selections/pins/request count. Console/isolation errors are zero in acceptance-v2.

An initial observer attempt incorrectly sampled a microtask from document capture
as post-React state. Browser microtask checkpoints occur before React capture;
the scratch observer was corrected to sample document bubbling and compare with
RAF. Product code and complete visibility assertions were unchanged.

Only the blocked mobile two-company case was retried as acceptance-v3-mobile2.
The badge was dismissed through its native Preferences/Hide session UI, with its
exact local disable POST fulfilled synthetically rather than forwarded. All 19
focus geometry/occlusion checks then pass; native touch pan reaches 294px. This
retry is NOT acceptance: opening framework UI requests two development fonts
(/__nextjs_font/geist-latin.woff2 and geist-mono-latin.woff2), which unchanged
strict QA routing blocks. Two console errors/four isolation diagnostics result.
The request-count assertion also detects one extra AAA freshness GET. This run
is retained as failed; it does not establish request-lifecycle preservation.
No further harness allowlist, CSS/config, DOM hiding or application fix was made.

### Vertical correction outcome — historical harness blocker

The following was the pre-reconciliation decision, preserved as historical evidence:

> BLOCKED for complete focused acceptance. The localized implementation and focused
> tests remain unstaged within the three authorized files. Coordinator disposition
> is required for a separately bounded QA-only treatment of development chrome;
> do not weaken occlusion/network assertions or change Next config/global CSS in
> this scope. Do not claim READY FOR ASTRA FOCUSED REVIEW or production compatibility.
> The vertical correction resolves measured viewport clipping, but default development
> chrome still obstructs one checked state. No asynchronous correction was needed.

Current disposition: the separately authorized external scratch-harness correction
passed the remaining case without a product-code change. Final Astra review and
coordinator dispositions below supersede this historical blocker. Default-badge
and production deployment acceptance are still outside the qualification.

All three owned browser containers (observer attempt, acceptance-v2 and isolated
mobile retry) were removed. Each external checker verifies no remaining helpers,
listeners on 3107/3108, QA launcher roots, runtime roots or temporary HOME; telemetry
gets only bounded polling with no exemptions. Host inputs/artifacts are retained
as evidence. No live PostgreSQL access, staging, commit, push or deployment.

Evidence and exact incremental patch:
`C:\Users\IITSt\AppData\Local\Temp\finlens-cc02-vertical-fix-hlddrtv9`.
Final preservation: main/expected HEAD, empty index, unchanged status path set,
all three protected hashes and every non-authorized source/historical hash must
match the pre-write snapshot; final proof is retained in that evidence directory.

## Current final outcome — coordinator reconciliation, 2026-10-16

**READY FOR GIT STEP 1 — coordinator controlled.** The coordinator reports:

- Astra financial/cross-layer review: **PASS WITH CONDITIONS**, no blocking defect.
- Final independent Astra accessibility review: **PASS WITH CONDITIONS**,
  **GO for coordinator-controlled Git Step 1**.

These are the completed independent review results supplied by the coordinator;
this documentation-only task did not rerun either review or any test suite.

### Final qualified synthetic Chromium acceptance

| Case | Viewport | Final result | Evidence status |
|---|---|---|---|
| Desktop, two companies | 1440x1000 | PASS | Prior passing case retained; not rerun |
| Desktop, four companies | 1440x1000 | PASS | Prior passing case retained; not rerun |
| Mobile touch, four companies | 390x844 | PASS | Prior passing case retained; not rerun |
| Mobile touch, two companies | 390x844 | PASS | Final focused run with explicit scratch-only override |

Chromium 156.0.8078.4 / Playwright 1.64.0 used the existing isolated QA-01 Linux
image and synthetic fixtures. The final mobile two-company run passed all 19
focus checks, 15/15 control visibility samples at each stop, and eight PNG states
with 64/64 painted-outline samples each. Native Tab/Shift+Tab, exit/re-entry,
Gross Margin operands/provenance, nested disclosures/source links, pointer/touch
behavior and horizontal panning passed. Earlier initial failures remain failures;
they are not relabeled as passes by this final result.

The final mobile two-company run used framework-supported `devIndicators: false`
only in the served external scratch configuration. Repository configuration and
all product sources were unchanged. Binding checked 30 original input/runtime
files and 18 served files: 17 exact original-source matches plus the explicit,
hash-verified configuration override; no binding check was skipped.

- Original configuration SHA-256:
  `df0dc4826240eaf630223ddfe4e1086e201a718b9def66ad4f209529b934604f`.
- Served scratch configuration SHA-256:
  `f95fcf92dc101c6b6155fb5613de5d6eb1464c3a353c684883bcea7d8a6067ff`.

This qualifies **synthetic browser acceptance**. It does **not** establish
acceptance with the default development badge, which overlapped the original
mobile focus stop, or production deployment acceptance. No production/current-
source build, physical-device, other-browser-engine or live-backend acceptance
is implied. The final successful run had no console errors or isolation violations;
owned containers, helpers, listeners and temporary runtime roots were removed.

### Explained and bounded harness behavior

The rejected Geist font URLs were verified same-origin bundled framework assets.
Scratch-only routing permits exactly the two known local font GET URLs, with no
query/body and hash-verified `wOF2` bytes; other routes/external destinations retain
strict denial. The successful configuration-suppressed run requested neither font
and required no native Hide POST. The failed Preferences/Hide retry remains failed.

The extra unpinned `GET /companies/AAA/freshness` was traced to legitimate existing
whole-document window-focus behavior: native Tab left the document and Shift+Tab
re-entered it. A trusted window-focus event invoked `ResearchFreshness.check()`
0.3ms later, confirmed by the fetch stack. It was not caused by disclosure focus.
The final harness requires that exact event/callback/request association, rather
than increasing a blanket allowed count: 13 baseline requests plus one explained
metadata check, no fetches during in-table or subsequent pointer/touch actions,
unchanged financial requests and independent publication pins including zero.

Final evidence remains outside the repository:
`C:\Users\IITSt\AppData\Local\Temp\finlens-cc02-final-mobile-6tzyu2iu`:
`final-acceptance-report.md`, `scratch-harness-changes.patch`, and
`focused-v2/output/` contain the result, source/config binding, request/focus
attribution, geometry, screenshots and complete cleanup proof. Earlier evidence
roots referenced above remain preserved and distinguish the initial failures,
read-only investigations, horizontal/vertical remediation and failed retries.

### Coordinator disposition of both nonblocking P3 findings

1. **Horizontal safety gutter:** approximately 1px of near-edge horizontal movement
   can occur even when the painted outline is already visible. The coordinator
   accepts this harmless movement as **nonblocking and deferred**. Do not change
   product code or tests for this refinement in the current scope; the horizontal
   behavior should not be described as an unconditional already-visible no-op.
2. **Stale ExecPlan acceptance/outcome statements:** **resolved by this documentation
   reconciliation**. Current status/progress/outcome now reflect final qualified
   acceptance and both completed Astra reviews. Original failures and earlier stop
   decisions remain explicitly historical; no evidence was removed or rewritten
   into a successful result.

### Git, delivery and rollback boundary

Coordinated backend/frontend delivery **and rollback remain mandatory**. The strict
seven-metric client and expanded eleven-metric response are not mixed-version
compatible; deliver or roll back the compatible backend/frontend pair together.
**Deployment is NOT approved.** Git Step 1 remains coordinator controlled and is
not executed by this task. No staging, commit or push is authorized here.

The existing active path is retained. Only this document is edited in this round;
all prior CC-02 product/test changes, protected files and historical artifacts are
preserved. Run only documentation consistency, whitespace and preservation checks;
do not rerun financial/frontend/browser tests or Astra reviews for this reconciliation.
