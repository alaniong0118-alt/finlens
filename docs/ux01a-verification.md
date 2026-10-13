# UX-01A implementation and offline verification

Date: 2026-10-13 (Asia/Macau)
Baseline: main and local origin/main `1b2468fc5aad0fe974e3bb70c2c4f6f033dbaf6b`
Status: conditional closure ready for coordinator review; final QA-01 29/29 PASS, mobile comparison visibility FAIL deferred and attribution UNKNOWN

## Implemented changes

- Financial tables, provenance and supporting metadata use 13px text; source identifiers inherit the provenance text size. Increased source paragraph/cell spacing and tabular numeric alignment. Amounts, dates, units, economic bases, unavailable reasons, exact values and source disclosures remain present.
- Native summaries, source links, topic chips, comparison Remove controls and section navigation target at least 44px through CSS. Selectors and primary actions retain their existing 44px baseline. No native interaction or focus handler was replaced.
- History selectors stack below 768px. Snapshot cards use one column below 481px to avoid cramped financial/date text at 390px; six primary cards and all 15 metrics remain unchanged. The existing expanded-provenance behavior remains intact.
- Comparison remains a semantic table in the existing labelled, focusable horizontal scroll region. The minimal rollback restores committed QA-01 non-sticky headings/metric labels and normal document-height layout. Company/CIK/period/publication metadata and per-cell financial/provenance information remain represented; no comparison component or contract changed.
- Historical observations have a labelled, focusable scroll region, linked visible keyboard/scroll instructions and the original semantic caption/headings/rows. Native source disclosures remain operable.
- Company badges explicitly say Ready/Not indexed for filing research and explain that indexing does not establish financial completeness or freshness. The original database-derived condition and counts remain unchanged.
- Initial research guidance uses the existing selected-filing/company-evidence eligibility inputs to distinguish filing exploration from supported financial questions. It does not authorize evidence or alter submission/request logic.
- Added Historical trends access to existing section navigation. Reduced hero heading size/margins and mobile panel padding; kept all capability messaging and financial information visible.

## Changed-file allowlist and scope

| File | Change |
| --- | --- |
| `frontend/app/globals.css` | Typography, spacing, targets, mobile grids and restored non-sticky comparison scrolling |
| `frontend/app/page.tsx` | One navigation anchor |
| `frontend/components/company-overview.tsx` | Filing-index badge/supporting copy |
| `frontend/components/financial-research.tsx` | History-region attributes and instructions |
| `frontend/components/filing-research.tsx` | Initial empty-state copy branches only |
| `frontend/tests/research-interactions.test.mjs` | Seven appended mounted UX-01A tests; existing tests unchanged |
| `frontend/tests/ux01a-presentation.test.mjs` | Five static presentation-contract tests using existing PostCSS; two affected expectations updated for rollback |
| `docs/exec-plans/active/2026-10-13-ux01a-readability-mobile.md` | Approved scope, preservation and progress |
| `docs/ux01a-verification.md` | This offline acceptance/handoff record |

The production diff consists of CSS, JSX attributes, one anchor and presentation text. No financial formatter, metric/catalog definitions, API client/contract, validator, publication version, fetch/cancel lifecycle, SEC eligibility, backend, dependency, QA-01 assertion or historical evidence changed. No financial information was hidden or replaced.

## Original implementation checks (historical)

Commands run in `D:\Projects\finlens-foundation\frontend` using installed dependencies:

| Check | Result |
| --- | --- |
| `node --test --test-name-pattern=UX-01A tests/research-interactions.test.mjs tests/ux01a-presentation.test.mjs` | 11 passed, 0 failed |
| `npm test` | 233 total: 229 passed, 4 Linux-only process-tree tests skipped, 0 failed; all existing 218 portable tests plus 11 new tests pass |
| `.\node_modules\.bin\tsc.cmd --noEmit --incremental false` | Passed; no generated type/build output |
| `.\node_modules\.bin\eslint.cmd app/page.tsx components/company-overview.tsx components/financial-research.tsx components/filing-research.tsx tests/research-interactions.test.mjs tests/ux01a-presentation.test.mjs` | Passed |
| `.\node_modules\.bin\playwright.cmd test --list --reporter=list` | All unchanged 29 QA-01 cases discovered in four files; no browser/server execution |

Repository checks:

- `git diff --check` passed. New record/test files checked for trailing whitespace.
- Changed-file allowlist checked against Git status, separately accounting for the initial three unrelated files.
- QA-01 E2E/config/harness/tests/docs and shared financial/API/freshness/backend/dependency files have no diff from HEAD.
- In-memory TypeScript AST inspection confirms all arrow/function-expression callbacks in touched TSX files match HEAD after CRLF/LF normalization. The first raw-text comparison detected newline differences; the normalized comparison passed. Manual diff review confirms presentation-only changes.
- Existing `research-interactions.test.mjs` content remains an exact unchanged prefix after newline normalization; all prior assertions are retained.
- Protected SHA256 checks match the before values in the [active plan](exec-plans/active/2026-10-13-ux01a-readability-mobile.md). HEAD/local origin/main remain the baseline. SEC artifacts, receipts and backups were not modified by this work.

New regressions check history-region focus/semantics and exact zero/negative/missing values/dates/sources, disclosure without requests, navigation without fetching, qualified readiness, and guidance/request behavior for eligible versus metadata-only/malformed evidence in both scopes. Current CSS tests preserve typography/targets/mobile expectations and check non-sticky scrolling without source overlays; they are not rendered-layout tests.

## Historical proposed browser acceptance after rollback (partially executed; mobile failure deferred)

No Docker, image build, Chromium execution, real API smoke or service start/restart is authorized or performed in the rollback pass. Retained Chromium evidence describes the two prior sticky failures and pre-rollback code; it cannot establish rendered acceptance of this rollback. Use a future separately authorized current-source immutable image and existing isolated two-issuer fixtures only.

1. Reproduce the former AAA Revenue case at 1440x900 Light with AAA/BBB, expanded provenance and native Tab/Shift+Tab. The comparison now follows ordinary document scrolling, so do not require the removed inner 75vh vertical scrollport or sticky context. Verify the complete control/3px outline with rendered measurements, multiple-point occlusion checks and a screenshot. Return to the heading and verify Publication 0/1, company/CIK and annual dates remain readable; no focused source may paint over header metadata or financial values.
2. At 390x844 Light/Dark, exercise horizontal table scrolling, both issuer columns and first/last rows with expanded/collapsed disclosures and official source links. Verify Tab/Shift+Tab and Enter/Space, full focus visibility at horizontal edges, normal vertical document scrolling and no unintended document-width overflow. Headers/metric labels scroll with the table; they are no longer promised to stay visible. Spot-check exact values/dates/units/unavailable reasons, six primary cards/all 15 metrics, stacked history controls, 44px controls and labelled historical keyboard scrolling. Use existing sources only; nested alternatives and additional issuers remain unsupported by these fixtures.
3. If those checks pass, run the unchanged 29 QA-01 Chromium cases (27 desktop, 2 mobile), one worker and zero retries, with their existing assertions/fixtures/timeouts and isolation/cleanup verification. Stop on a blocking defect; no automatic CSS fix or retry.

Broader viewport/zoom/screen-reader acceptance remains unverified where the stopped previous runs did not exercise it. This plan does not authorize additional polish or UX-01B and does not claim browser closure from static tests.

## Deferred to UX-01B / separate scope

History transport retry remains unimplemented. Further guided-answer layout refinements, full screen-reader/contrast/device accessibility acceptance and additional populated-mobile browser coverage remain later scoped work. No new financial/data/retrieval features or UX-01B implementation started.

## Git and handoff

Nine scoped files changed/added, all unstaged. The original modified `frontend/next-env.d.ts` and two untracked backend runtime reports remain byte-identical. No staging, commit, push, installation, migration, database write, ingestion or deployment occurred.

Suggested eventual commit: `feat(ux01a): improve research readability and mobile usability`.

Return to coordinator before browser acceptance or Git actions. A bounded independent review of this diff and subsequent browser evidence is recommended before closure; the active plan remains open.

## Historical sticky comparison focus correction — 2026-10-13 (superseded by rollback)

The subsequent retained Chromium acceptance passed all 29 unchanged QA-01 cases (27 desktop, 2 mobile). Two UX visual cases passed; comparison keyboard focus failed, and remaining cases were stopped. The immutable historical external result has SHA256 `cbfea273367b3eaec02d86bb4283b9e3b8e3f21e06d150c23b4d808b7e9c02c0`; its final evidence index has SHA256 `851cc6542a79e09f4b289794a90fcd113b38adc2408ac15f3a98e01425808c6d`. Both are retained beneath `finlens-ux01a-recovery-fde2b013ae1846449a7f8cffa20aa178` in the host temporary directory; no historical evidence is edited.

### Root cause and exact correction

The `.comparison-scroll` overflow region has an isolated stacking context and a 75vh maximum height. Sticky company headings at layers 2/3 painted over the focused body disclosure: its y244–288 rectangle and 3px outline were entirely under a heading ending at y295.234375. Existing `scroll-padding-left:172px` helped with the 160px metric column but provided no vertical or focus-halo clearance. Heading height depends on names, periods, reasons, wrapping and zoom; a fixed or percentage header-height guess cannot cover all cases.

Only `globals.css` changes production presentation:

- Add 8px block and right scroll padding and 8px scroll margins to comparison body summaries/links. This covers the existing 3px outline, 3px outline offset and 1px region border without changing layout padding or row heights. The [CSS scrolling specification](https://www.w3.org/TR/css-scroll-snap-1/#scroll-padding) defines these as viewing-region/scroll-into-view adjustments; native Tab/Shift+Tab behavior remains a browser acceptance gate.
- Paint only a body summary/link matching `:focus-visible` as `position:relative; z-index:4; background:var(--card)`. It stays in normal layout with no offsets/transform/size changes, uses an opaque Light/Dark token and retains the global focus outline. Whole cells are never raised. Unfocused source content, sticky headings/metric labels and corner ordering remain unchanged.
- While a body source is keyboard-focused, a scoped `:has(...:focus-visible)` rule reduces left scroll padding to 8px. The raised source can use the full scrollport above the metric overlay: a permanent 172px reserve otherwise leaves insufficient viewing width on narrow/zoomed layouts. The original metric-column reserve returns when body sources are not keyboard-focused.

No TSX, table structure, financial/provenance content, formatting, publication pins, API/eligibility rules, fetch/cancel callbacks, dependencies or QA-01 assertions changed. History transport retry remains excluded.

### Offline checks and limits

One appended static CSS regression checks focus layering above the corner, opaque theme tokens, halo/border clearance, the active horizontal reserve, absence of offsets/size changes and unchanged unfocused-cell order at 1440/390/320 widths. It does not prove rendered occlusion, clipping or browser native focus scrolling.

Final checks actually run from `frontend/`: `npm test` — 234 total, 230 passed, 4 Linux-only process-tree skips, 0 failures; all five presentation tests pass. Installed `tsc --noEmit --incremental false` and scoped `eslint tests/ux01a-presentation.test.mjs` pass. The production CSS diff against the retained accepted-source staging copy is limited to one scroll-container declaration and eight added lines (comments and scoped source-control rules). This does not constitute browser focus-visibility acceptance.

The correction allowlist, `git diff --check` and new-line whitespace checks pass. All 264 repository files outside the four-file correction allowlist, all three protected SHA256 hashes, Git index/status and 844 retained evidence entries match the before snapshot. No Docker command, image build, Chromium execution, service startup, provider/database operation, staging, commit or push occurred in this correction pass.

### Required browser rerun and risks

Reproduce the retained 1440x900 Light failure first, then test 1280x900 and 390x844 Light/Dark. Tab and Shift+Tab through every disclosure, nested alternative-source disclosure and official source link after horizontal and vertical scrolling; expand/collapse with Enter/Space. Inspect the full focused rectangle and outline against headers, metric labels, borders and scrollport clipping (including first/last rows, both issuers and rightmost columns). Keep exact values/dates/sources, 160px metric labels, opaque headings and column alignment checks.

Exercise long/wrapped company/period metadata, 480/481 and 767/768 boundaries, 320 CSS-pixel reflow and actual verifiable 200% browser zoom. Verify that focus-triggered `:has` styling is resolved before native scrolling in both tab directions, and that unfocused sticky context returns on blur. A focused source may temporarily cover part of company/metric metadata; it must remain visually tied to its company/row, and normal sticky context must restore when focus moves. This tradeoff uses the expressly authorized above-overlay option; browser review must assess it, not just center-point hit testing. Three/four-company fixtures remain unsupported unless separately approved. Re-run all 29 unchanged QA-01 cases on a newly built current-source image only after coordinator authorization; prior image/manifest evidence cannot validate this patch.

Correction files: `frontend/app/globals.css`, `frontend/tests/ux01a-presentation.test.mjs`, the existing UX-01A active plan and this record. Return to coordinator before browser execution or Git actions.

## Minimal safe comparison rollback — 2026-10-13

The final immutable-image re-acceptance made the AAA Revenue source control and complete 3px outline visible at 1440x900 Light (15 control hit points and 64 outline samples), but its opaque z-index 4 layer fully covered Publication 0. The mandatory metadata check failed; all subsequent UX checks and the full QA suite stopped. Retained result SHA256: `993f2b4f59f5685b3a716143012038a41931f3097f89baaaee1f53bd30acfb60`; evidence-index SHA256: `3965cafc9e0f98615104c462ce58ccdb81041a775aac277c503e7b0d86c06b92`. Evidence is unchanged beneath `C:\Users\IITSt\AppData\Local\Temp\finlens-ux01a-final-1fce2f27b9e449bf804fdaecf24e8a40`.

Coordinator decision: withdraw the sticky enhancement and prioritize functional completeness, financial correctness and stability. Inspected `git show HEAD:frontend/app/globals.css`; restored exactly:

```css
.comparison-scroll { margin-top:12px; border:1px solid var(--border); border-radius:10px; }
.comparison-table { min-width:640px; }
```

Removed three sticky header/metric/corner rules, the summary/link scroll-margin and focused z-index/background rule, the focus-dependent `:has` scroll-padding rule and their explanatory comments. The restored rules no longer set max-height, overflow, isolation or scroll-padding, or override table border-collapse/border-spacing. Existing `.table-scroll` horizontal scrolling and global collapsed table borders/shared focus outline apply. This restores the committed behavior without new offsets, handlers or UI improvements.

Rollback allowlist: `frontend/app/globals.css`, `frontend/tests/ux01a-presentation.test.mjs`, the existing UX active plan and this verification record. Only the two affected UX static expectations change; the first three CSS regressions and every QA-01 assertion remain unchanged. All TSX, metrics, amounts/dates/units/unavailable reasons, exact source disclosures, publication pins and callbacks are preserved. The larger text, 44px targets, mobile improvements, history accessibility, readiness/empty-state wording, Historical Trends navigation and compact hero remain intact.

Current checks actually executed from `D:\Projects\finlens-foundation\frontend`, using installed dependencies only:

| Check | Current rollback result |
| --- | --- |
| `node --test --test-name-pattern=UX-01A tests/research-interactions.test.mjs tests/ux01a-presentation.test.mjs` | 12 passed, 0 failures, 0 skips |
| `npm.cmd --offline --ignore-scripts test` | 234 total: 230 passed, 4 Linux-only process-tree skips on Windows, 0 failures |
| `.\node_modules\.bin\tsc.cmd --noEmit --incremental false` | Passed, no generated build/type output |
| `.\node_modules\.bin\eslint.cmd tests/ux01a-presentation.test.mjs` | Passed |
| `git diff --check` plus whitespace checks on all four rollback files | Passed |

Self-review/preservation: the two restored declarations exactly match `git show HEAD:frontend/app/globals.css`; every CSS declaration/media rule outside the withdrawn enhancement is unchanged from the before snapshot. The first three presentation tests are unchanged; only the two sticky/overlay expectations were revised. All 264 repository files outside the four-file rollback allowlist, every TSX file and QA-01 source/assertion, all three protected SHA256 hashes, 963 previous browser/build evidence entries and 1,204 operator-report files remain byte-identical. Git status filenames and index match the preflight; the index is empty and main/HEAD/local origin/main remain `1b2468f`.

External before snapshot, exact rollback diff, test logs and preservation proof: `C:\Users\IITSt\AppData\Local\Temp\finlens-ux01a-rollback-868a9c33156c46b686a1ea0bf69a54db`. Production CSS diff in this pass is 2 additions / 13 deletions. Only `globals.css`, the affected UX presentation test and the two existing UX records changed. Publication metadata (including version 0) and all provenance remain represented in unchanged semantic markup; rendered visibility has not been retested.

Stop for coordinator review. Rendered focus/metadata acceptance remains pending the small plan above and separate authorization. No Docker or Chromium execution, dependency/service change, backend/provider/database operation, history retry, new UI improvement, UX-01B, staging, commit or push occurred in this pass.

## Conditional closure: explicit accessibility limitation and final regression

The coordinator accepts conditional UX-01A closure with a known mobile comparison accessibility limitation and directs that further CSS experiments stop. **The failure is deferred, not fixed or passing. Baseline attribution remains UNKNOWN.** Only these two existing UX documents may change in this final pass; application CSS/TSX, tests, fixtures, assertions, financial content, publication pins and callbacks are preserved.

### Actual post-rollback browser results

| Check | Retained result |
| --- | --- |
| 1440x900 Light populated AAA/BBB comparison | PASS: complete controls/3px outlines, Tab/Shift+Tab and source links, company/CIK/period/Publication 0/1 metadata, metric labels and stable non-sticky scrolling |
| 390x844 Light complete keyboard visibility | FAIL: first native Tab to expanded AAA Revenue leaves the disclosure/outline partially clipped horizontally |
| 390px company/publication metadata brought into view | PASS before the failure; no raised focus layer covers Publication 0/1 |
| 390x844 Dark and subsequent mobile visual checks | NOT VERIFIED: stopped before execution |
| Other incomplete post-rollback visual checks | NOT VERIFIED: later mobile source traversal, history/cards/targets/provenance/overflow; broader responsive/zoom, nested alternative sources and three/four-issuer visual coverage |

Preserved failure evidence: `C:\Users\IITSt\AppData\Local\Temp\finlens-ux01a-closure-a54fa6460a3b48d2b3aacc1a1a19940e`. Its result SHA256 is `697a154ffb738fc5ee63408840aa8568d968dd03e41ed60975577c70d31524f9`, and evidence-index SHA256 is `a1133f9e963edba610203e6a3633c9a699bae09377bd96d7decd3b7d562c03e1`. No failure screenshot, trace, report or historical result is rewritten.

### Confirmed clipping mechanics and attribution limits

The scroll container is `.table-scroll.comparison-scroll`: clientWidth **322px**, scrollWidth **640px**, available range **318px**, scrollLeft **0** after Tab. AAA Revenue disclosure occupies **x206–422**, **y254.3125–317.1875**, width **216px**, height **62.875px**. The scrollport interior ends at **x356**, clipping **66px** of the control. Its **3px outline / 3px offset** extends to x428, requiring approximately **72px** of reveal in this state. Actual visibility: **9/15 control points**, **38/64 outline samples**; full outline containment FAIL. The control plus outline can fit within the scrollport and sufficient scroll range exists. The failure is the observed absence of adequate horizontal reveal during focus, not an unavoidable oversized target or sticky overlay. Position remains static, z-index auto, and no focused control covers company metadata.

The retained trace shows programmatic region focus and a scroll reset followed by native Tab in Chromium mobile emulation. It does not establish the browser's internal scrolling decision or behavior under every normal entry/timing condition. `git show HEAD:frontend/app/globals.css` confirms the same baseline horizontal overflow, 640px table minimum, 160px metric column, comparison cell widths/padding and shared outline. The comparison component and provenance function match HEAD. Inherited summary/table typography and target sizing changed in UX-01A, and no identical baseline/current mobile A/B execution exists. QA-01's two mobile tests exercise `experience.spec.ts`, not comparison focus visibility. Therefore neither a pre-existing defect nor a UX-01A-introduced defect is established: **UNKNOWN**.

Financial/publication integrity remains unchanged: all 15 metrics, six primary cards, amounts/dates/units/unavailable explanations, source provenance, exact values and publication 0/1 pins remain represented; no financial/API/data-fetching/eligibility/callback change is made. This is a known accessibility limitation, not evidence of changed financial data. **Future accessibility remediation and rendered keyboard verification are required in a separately approved scope.** No speculative scroll-margin, sticky, overlay or JavaScript scroll workaround is proposed or implemented.

### Final regression authorization and identity

Reuse exactly image `sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612` with approved 33-file manifest SHA256 `8652044ed48aceab90fd5ea75425049b54abdcb7d83b45d9d3eae967fc06bd91`. Independent static image-filesystem verification passed before QA: all 33 source hashes and application/E2E inventories match current host sources; pinned packages, lockfile and Chromium/SWC binaries match preserved evidence. Offline-only UX Node tests and documents outside this image allowlist are separately protected; no additional image source or dependency installation is inferred.

Run the unchanged full QA-01 suite once using existing isolated infrastructure, one worker and zero retries, preserving assertions/fixtures/timeouts. A passing 27 desktop + 2 mobile regression would establish existing QA behavior only; it cannot override the known mobile comparison visibility FAIL or NOT VERIFIED visual checks. No image rebuild/pull/install, production service change, provider/database operation, source/test change, staging, commit or push is authorized.

### Final QA-01 results and preservation

The unchanged QA suite actually ran **once** on the verified existing image using `npm --offline --ignore-scripts run test:e2e -- --reporter=list,html,json --output=/artifacts/test-results --max-failures=1` in `/work/frontend`:

| Result | Executed count |
| --- | --- |
| Desktop Chromium | 27/27 PASS |
| Mobile-width Chromium | 2/2 PASS |
| Total | 29/29 PASS in 36.1s |
| Failed / skipped / flaky / retries | 0 / 0 / 0 / 0 |
| Workers | 1 |

All expected test identities matched the preserved QA-01 suite; each had exactly one passed result with retry 0. Existing 45s test timeouts, 600s global timeout, fixtures, assertion source and configuration are unchanged. Mobile QA passes cover the two existing experience cases; they do not exercise or fix the known comparison focus-clipping defect. **1440px comparison PASS / 390px comparison keyboard visibility FAIL / baseline attribution UNKNOWN remain unchanged.** All other incomplete populated-comparison mobile and broader visual checks remain NOT VERIFIED.

Runtime safety and cleanup passed: pwuser uid 1001, Docker `--network=none`, `--read-only`, `--pull=never`, no published ports, one artifact-only bind and no production credentials/database/socket mounts. The passive observer recorded **536 requests, including 338 synthetic API requests**, **zero external destinations**, **zero page errors**, and **29/29 browser contexts opened/closed**. Browser open/close counts matched. The owned Next/launcher received graceful SIGTERM and exited 0, with no live owned processes, test listeners or temporary source directories. The test container and stopped image-verification container were removed; the acceptance image and every historical artifact were retained. No real SEC, AI, Tiingo, backend or PostgreSQL request occurred.

Source integrity matched all 33 approved hashes before and after the regression. Final preservation checks cover all **266 repository files outside the two-document allowlist**, including application CSS/TSX, tests, fixtures, assertions, dependency files and all three protected SHA256 values; **1,112 previous evidence entries** and **1,204 operator-report files** remain unchanged. Git status filenames and index are preserved; index empty, main HEAD and local origin/main remain `1b2468fc5aad0fe974e3bb70c2c4f6f033dbaf6b`. Documentation allowlist/diff/whitespace checks pass. No staging, commit or push.

New external evidence: `C:\Users\IITSt\AppData\Local\Temp\finlens-ux01a-final-regression-79054a32caf24e82b4171f475841b9d6`, including independent image-source proof, invocation/runtime records, full test log, JSON/HTML reports, request observations, cleanup and final preservation proof. A SHA256 index covers the final external artifacts. Two external setup errors (pre-existing probe directory and a missing variable in informational console output) occurred before the successful single source probe/QA run; their scripts and diagnostic note are retained. No mandatory safety gate or QA test failed, and no gate/browser attempt was retried.

**Ready for a coordinator-approved staged Git commit with documented incomplete accessibility acceptance.** Stage only the existing nine UX-01A files after separate authorization; exclude `frontend/next-env.d.ts` and both unrelated backend runtime reports. Suggested eventual commit: `feat(ux01a): improve research readability and mobile usability`. Future accessibility remediation remains required in separate scope; no CSS experiment, history transport retry, UX-01B or advanced visual work starts here. Stop for coordinator review.
