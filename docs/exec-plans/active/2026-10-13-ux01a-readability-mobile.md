# UX-01A — Bounded readability and mobile usability

Status: active — conditional closure ready for coordinator review; QA-01 29/29 PASS, mobile comparison visibility FAIL explicitly deferred
Roadmap phase: scoped UX-01A presentation milestone; UX-01B excluded

## Objective

Improve table/provenance readability, touch targets, 390px controls, table scrolling context, filing-readiness guidance and navigation. Preserve financial information and all existing research safeguards.

Current comparison decision: preserve the restored committed QA-01 non-sticky horizontal scrolling behavior. The sticky enhancement and focused-control overlays are withdrawn; keep the other approved UX-01A changes. The coordinator explicitly defers the confirmed 390px keyboard focus-clipping failure without classifying it as fixed or passing. Only a final unchanged QA-01 regression on the existing post-rollback immutable image is now authorized; no further CSS experiments or visual retries.

## Current architecture and context

Baseline main and local origin/main: `1b2468fc5aad0fe974e3bb70c2c4f6f033dbaf6b`. Existing React presentation uses semantic tables, native selectors/disclosures, CSS theme tokens and QA-01 isolated browser infrastructure. The completed UX-01 audit is the approved input; do not repeat it.

Initial unrelated Git changes (preserve byte-for-byte):

- `frontend/next-env.d.ts` — F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- `backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json` — A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- `backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json` — F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints

Presentation-only changes; no calculations, formatters, API contracts, validators, publication-version logic, fetching, cancellation or SEC eligibility changes. Preserve all 15 metrics, six primary cards, QA-01 assertions/evidence, SEC artifacts/receipts/backups and unrelated work. No dependency installation, service startup/restart, browser acceptance, database/provider operations, staging, commit or push.

## Non-goals

History transport retry, new data/features, custom company picker, redesign, automated retries, QA-02 and UX-01B. Browser acceptance is a later coordinator-authorized gate.

## Original implementation stages (historical)

1. Record baseline/protected hashes and an exact changed-file allowlist.
2. Adjust CSS typography, spacing, targets, mobile controls and sticky comparison context; add history scroll semantics and presentation copy/navigation.
3. Add focused offline DOM and presentation regressions without changing existing assertions.
4. Run existing Node tests, TypeScript, scoped ESLint and offline QA-01 regression checks.
5. Self-review allowlist, behavior logic preservation, whitespace, protected hashes and Git status; return to coordinator.

## Decisions

2026-10-13, conditional closure: 1440x900 Light comparison acceptance PASS; 390x844 Light full keyboard focus visibility FAIL and explicitly deferred as a known accessibility limitation. Baseline attribution UNKNOWN. Future accessibility remediation remains required in a separately authorized scope. Preserve financial/publication integrity, application/test sources and all historical evidence. Reuse image `sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612` with source manifest `8652044ed48aceab90fd5ea75425049b54abdcb7d83b45d9d3eae967fc06bd91`; independently verify its source bytes before running all 29 unchanged QA-01 Chromium tests once. No rebuild, pull, installation, staging, commit or push. This coordinator decision supersedes the earlier requirement to pass every visual check before regression, but does not turn failed/incomplete visual checks into PASS.

2026-10-13, minimal rollback: the final Chromium re-acceptance made the focused disclosure visible but entirely obscured AAA's Publication 0 heading. Financial metadata must remain readable. Restore `.comparison-scroll` and `.comparison-table` to their committed QA-01 declarations; remove the bounded vertical scrollport, sticky headings/metric labels, stacking layers and comparison-specific focus/scroll-padding workarounds. Change only CSS, affected UX static expectations and these two UX records. No TSX, financial, provenance, publication or QA-01 assertion changes; no new UI enhancement or UX-01B.

The earlier sticky decisions and correction below are historical and superseded by this rollback.

2026-10-13: Keep semantic comparison tables with horizontal scrolling. Confine sticky headings/row labels to a labelled, focusable bounded scroll region with opaque theme backgrounds. Keep native disclosures and all financial details; compact the hero rather than hiding research information.

2026-10-13: Reuse existing eligibility booleans only to select empty-state copy. Do not add a readiness rule, request, effect or retry handler. Retain existing Ready/Not indexed wording within explicitly scoped filing-index labels for compatibility with existing regressions.

Changed-file allowlist:

- `frontend/app/globals.css`
- `frontend/app/page.tsx`
- `frontend/components/company-overview.tsx`
- `frontend/components/financial-research.tsx`
- `frontend/components/filing-research.tsx`
- `frontend/tests/research-interactions.test.mjs` (append focused tests only)
- `frontend/tests/ux01a-presentation.test.mjs`
- `docs/exec-plans/active/2026-10-13-ux01a-readability-mobile.md`
- `docs/ux01a-verification.md`

## Discovered issues

Post-rollback mobile focus limitation: the actual `.table-scroll.comparison-scroll` has clientWidth 322px, scrollWidth 640px, available horizontal range 318px and scrollLeft 0 after native Tab. AAA Revenue summary x206–422 (width 216px), y254.3125–317.1875, exceeds inner right edge x356 by 66px; the 3px outline plus 3px offset needs approximately 72px of horizontal reveal. Only 9/15 control hit points and 38/64 outline samples are visible. Position is static and z-index auto: this is ordinary horizontal clipping without sticky/focus overlays or covered Publication 0. The target plus outline fits within the scrollport; the observed mobile focus transition did not reveal it horizontally. Why the browser omitted reveal is not established by the retained trace, and no identical HEAD/mobile A/B run exists. The committed scroll design predates UX-01A, but inherited typography/target sizing changed; the issue's origin relative to QA-01 remains UNKNOWN. The coordinator explicitly defers it; remediation and full mobile keyboard accessibility acceptance remain outstanding.

Chromium acceptance found two sticky comparison defects: the original heading hid keyboard focus; raising the focused source made it visible but fully covered Publication 0. The coordinator withdrew sticky behavior. The minimal rollback restores the committed non-sticky CSS; rendered focus/outline clipping and mobile scrolling still require the small separately authorized acceptance plan in the verification record. Offline DOM/CSS checks cannot establish rendered visibility.

### Historical authorized sticky-focus correction — 2026-10-13 (superseded)

The retained real Chromium run passed all 29 unchanged QA-01 cases. Its visual pass found the focused AAA Revenue source summary at y244–288 entirely beneath a sticky company heading ending at y295.234375 (1440x900 Light). The overflow container is `.comparison-scroll`; its isolated stacking context contains header layers 2/3 and sticky metric labels at layer 1. Heading height is content-dependent, so neither a fixed pixel nor percentage top reserve guarantees clearance for long metadata, narrow screens or zoom.

Implement a CSS-only correction in `globals.css`: retain the existing horizontal metric-column reserve when body sources are not keyboard-focused, add block/end scroll clearance and source-control scroll margins for the 3px outline plus 3px offset and borders, and paint only keyboard-focused body summaries/links above sticky layers with an opaque theme background. While a body source is keyboard-focused, reduce the inline-start scroll reserve to edge clearance: at 390px the former 172px reserve leaves too little optimal viewing width for a source control, and the raised control can safely use the area above the metric overlay. Keep entire cells and unfocused controls in the existing table paint order. This uses the expressly authorized above-overlay visibility option without estimating header height; it does not change layout offsets, tab order, headings, financial content or TSX callbacks. Scroll padding/margin aid native reveal, but browser acceptance must establish actual clipping/visibility in both tab directions.

Correction allowlist: `frontend/app/globals.css`, `frontend/tests/ux01a-presentation.test.mjs`, this plan, and `docs/ux01a-verification.md`. No Docker/image/browser execution, dependency, backend/provider, history-retry or Git actions are authorized. All previous acceptance/failure evidence remains immutable.

- [x] CSS-only focused-control correction and one appended static regression; no TSX change.
- [x] Final Node suite: 230 passed, 4 Linux-only skips, 0 failures; five presentation tests pass. TypeScript (`--noEmit --incremental false`) and scoped ESLint pass. Allowlist/whitespace and protected/evidence checks complete; 844 retained evidence entries preserved.
- [ ] Coordinator review before new-image/browser acceptance; the former image/manifest are historical evidence only.

## Progress

- [x] Rollback preflight: main/endpoint refs at `1b2468f`, empty index, exact nine-file UX scope, three protected hashes, 963 prior browser/build evidence entries and 1,204 operator-report files verified and snapshotted externally.
- [x] Minimal non-sticky CSS rollback and affected static expectation update: exact committed scroll/table declarations restored; sticky/overlay/scroll-offset rules removed. All other CSS rules preserved.
- [x] Focused tests 12/12; full Node 230 passed, 4 Linux-only skips, 0 failures; TypeScript and scoped ESLint pass. Four-file rollback allowlist, diff/whitespace and preservation checks pass; 264 other repository files, three protected hashes, 963 prior evidence entries and 1,204 operator-report files unchanged.
- [ ] Coordinator review; smallest browser acceptance recorded separately, not executed in this pass.

Earlier implementation progress (historical; sticky enhancement withdrawn):

- [x] Baseline and protected hashes verified; repository guidance read.
- [x] Presentation implementation: readable table/source typography, 44px frequent targets, compact hero/navigation, single-column cards at <=480px, stacked history controls, sticky comparison context, labelled history region and capability-aware copy.
- [x] Focused regressions and existing offline checks: 11 new tests pass; full Node suite 229 passed, 4 Linux-only skips, 0 failures; TypeScript and scoped ESLint pass; unchanged 29 browser cases discovered only.
- [x] Final allowlist, whitespace, logic/QA preservation and protected hashes verified: nine scoped files plus the three original unrelated files; no staged changes.
- [ ] Coordinator review and separately authorized browser acceptance.

## Test and validation strategy

Use installed dependencies only. The rollback ran focused UX-01A Node tests and the full Node suite (including portable QA-01 checks), TypeScript with `--noEmit --incremental false`, and scoped ESLint for the changed presentation test. No Docker, build, browser run, discovery or copy-isolation command was executed. Preserve the first three CSS regressions and all mounted/QA-01 assertions; update only the two withdrawn sticky/focus-overlay expectations to non-sticky horizontal scrolling and the unchanged global focus outline. Static tests do not prove native rendered focus visibility.

## Completion criteria

Conditional closure requires the approved presentation/offline work, unchanged non-sticky application/test sources, all 29 unchanged QA-01 cases passing once with isolation/cleanup/source gates, protected hashes and baseline preservation, and explicit recording of the deferred mobile visibility FAIL, UNKNOWN baseline attribution and other NOT VERIFIED visual checks. This is incomplete accessibility acceptance, not full visual/keyboard PASS. Keep the existing plan in place for coordinator review; no UX-01B or Git action starts automatically.

## Original implementation outcome (historical)

Implementation and offline validation complete for coordinator review. Exact commands, results, changed files and pending acceptance are in [UX-01A verification](../../ux01a-verification.md). No service startup/restart, provider/database request, installation, build, browser acceptance, staging, commit or push occurred. All effect/event/request callbacks in touched TSX components match HEAD after newline normalization. Existing mounted tests are an unchanged prefix; new assertions are appended. QA-01 implementation/assertions/historical records and backend/shared safety modules match HEAD. The three protected hashes match the initial values above.

Keep this plan active pending coordinator review and separately authorized browser acceptance. Suggested eventual commit: `feat(ux01a): improve research readability and mobile usability`.

## Minimal rollback outcome

The rollback and requested offline work are complete. Only `globals.css`, the affected UX presentation test and the two existing UX records changed in this pass. Production CSS delta against the approved pre-rollback working tree: two replacement lines and eleven deleted lines (2 additions / 13 deletions in the diff). Every other CSS declaration/media rule and every TSX file remain unchanged; semantic comparison markup, Publication 0 representation, provenance, all 15 metrics, six primary cards, pins and callbacks are preserved. Existing nine-file UX Git scope plus three unrelated protected files remains unstaged, and main/local origin/main remain `1b2468f`.

Commands/results and the smallest proposed browser plan are in [UX-01A verification](../../ux01a-verification.md). External logs, before snapshot, rollback diff and preservation proof are retained at `C:\Users\IITSt\AppData\Local\Temp\finlens-ux01a-rollback-868a9c33156c46b686a1ea0bf69a54db`. No Docker, Chromium, dependencies, services, providers/database, history retry, new polish, UX-01B or Git action. Stop for coordinator review; do not claim rendered closure yet or move this plan to completed. Suggested eventual commit remains `feat(ux01a): improve research readability and mobile usability`.

## Conditional closure and final regression — current authorization

- [x] Nine-file unstaged UX-01A scope and empty index confirmed at main/local origin `1b2468f`; all 268 starting repository files, three protected hashes, 1,112 retained evidence entries and 1,204 operator-report files verified before work.
- [x] Existing immutable image verified independently in an isolated non-root, read-only, network-none static container: all 33 approved runtime/QA source hashes match current host files; app/components/lib/e2e inventories match exactly; pinned package versions, lockfile, Chromium and SWC binary hashes match retained proof. No rebuild, pull, install or browser execution in this gate. Offline-only UX Node tests/docs outside the 33-file image context remain separately protected.
- [x] Documentation-only deferral recorded; CSS, TSX, tests, fixtures, QA assertions, pins and financial content remain unchanged.
- [x] Final QA-01 Chromium regression executed exactly once on the existing verified image: 27/27 desktop + 2/2 mobile, 29/29 total, one worker, zero retries/failures/skips/flaky, 36.1s. Existing test identities, assertions, fixtures and timeouts preserved.
- [x] Graceful SIGTERM and launcher/Next exit 0; 29 browser contexts opened/closed, no live owned processes/listeners/temp roots. Source manifest matched before/after execution; 536 observed requests (338 synthetic API), zero external destinations/page errors. Final preservation and coordinator handoff recorded in the verification document; no staging, commit or push.

Other post-rollback visual checks not completed by the stopped run remain NOT VERIFIED, including 390px Dark, the later mobile provenance/source-navigation/cards/history/target/overflow checks, broader viewport/zoom cases and nested alternatives/additional issuers. Historical pre-rollback visual evidence is retained and is not a substitute for these checks. Financial/publication/source integrity is unchanged; future mobile accessibility remediation remains required.

Conditional handoff: the nine-file UX-01A change is ready for a coordinator-approved staged commit with incomplete accessibility acceptance explicitly documented. Keep the three unrelated protected files excluded from any future stage. The plan remains at its existing path for coordinator review; no move, commit, push, new milestone or remediation is performed automatically. The known 390px comparison keyboard visibility result remains FAIL and baseline attribution UNKNOWN despite the passing general QA suite.

Final evidence: `C:\Users\IITSt\AppData\Local\Temp\finlens-ux01a-final-regression-79054a32caf24e82b4171f475841b9d6`. Only this plan and `docs/ux01a-verification.md` changed in this pass; all 266 other starting repository files, three protected hashes, 1,112 previous evidence entries and 1,204 operator-report files are preserved. Source/image gate used the actual existing image filesystem; no rebuild, pull or installation. External runner preparation encountered two local setup errors before the successful single source probe and QA run; those original scripts/errors are retained, with no safety-gate or browser retry.
