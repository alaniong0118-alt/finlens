# Guided historical and comparison questions

Status: active; product review and limited synthetic functional acceptance passed; overall native wrapper failed after export. Final ten-file review and CI remain pending.
Roadmap phase: bounded presentation slice for requirements 1b, 4b and 16a.

## Objective

Prepare explicit fiscal-period and same-period comparison questions in the existing financial editor. Controls prepare a preview; Use question fills and focuses the editor; only explicit submission requests an answer. Preserve all 39 latest-value templates.

## Current architecture and context

Starting HEAD: `54c9e90998534e0e56d261d35aeb5e7d94f56ee6`, empty index. Five pre-existing exceptions remain excluded: `frontend/next-env.d.ts`, two historical backend reports, the annual markdown export plan and the completed personal-site plan. The backend already recognizes fiscal labels and comparisons in `research_answer_service.py`; the frontend currently exposes latest-value guides only. No backend changes are planned.

## Constraints and non-goals

Ten-file scope: the research helper, financial question component, their two existing test files, scoped guide input CSS, a focused style test, this plan, one browser spec, canonical synthetic JSON and one mobile-project registration. No discovery, automatic submission, new endpoint, calculation, policy change, production data access, model or installation. Fiscal years are requests in the grammar's 1900–2099 range, never availability claims. Quarter requests require direct observations; no annual/YTD substitution. Comparisons use the eleven existing duration metrics, one shared quarter or annual period, and increasing years. Growth-rate comparisons, mixed quarters, CAGR and instant-date comparisons remain excluded.

## Implementation stages

1. Add finite fiscal question vocabulary and validation while retaining the latest-value helper.
2. Add preparation modes around the stable existing editor and request ownership.
3. Extend guarded backend template contracts and mounted lifecycle checks; run scoped lint and TypeScript.
4. Freeze exact source and evidence for independent review. Browser acceptance and delivery remain separate gates.

## Decisions and discoveries

- Backend `PERIOD_PATTERN` accepts four-digit 19xx/20xx years and `Q1 FY2024` through `Q4 FY2024`.
- `Compare FY2024 and FY2025 operating margin` binds percentage-point difference; EPS comparisons retain the backend's as-filed/no-percentage constraints.
- One shared period selector prevents mixed-quarter comparisons by construction; invalid years still disable preparation at the helper boundary.

## Validation and progress

Implemented: Latest value remains the default. Specific fiscal period offers fifteen fiscal-year metrics and twelve direct-quarter metrics; Compare periods offers eleven metrics with one shared annual/Q1–Q4 selector. Empty, malformed, out-of-range, same and reversed years cannot prepare a comparison. Preparation does not edit or cancel current work; Use question retains the existing cancellation and focus behavior.

Checks actually run on 2026-11-03, from `frontend/`, using existing Node 24 and the existing backend virtual environment:

- `node --test --test-isolation=none --test-timeout=30000 --test-reporter=tap tests/research.test.mjs`: **22 passed**, zero skips. The extended guarded Python bridge checks 39 unchanged latest templates, all 63 historical and 55 comparison metric/period branches, six extra boundary/missing/multi-year controls, and six unsupported manual questions. It binds actual backend metric, operation and requested periods, then checks actual canonical answers, sources, percentage points and EPS as-filed/no-percentage semantics. The bridge uses synthetic detached facts and rejects private configuration, real DB and network access.
- `node --test --test-isolation=none --test-timeout=15000 --test-reporter=tap --test-name-pattern='guided fiscal|FD-01 guided|FD-01 preparation|FD-01 Use question|financial-only|mounted historical|mounted comparison|mounted unavailable comparison|mounted evidence failure preserves a completed comparison' tests/research-interactions.test.mjs`: **49 passed**, zero skips. Includes twelve new cases for preparation, unavailable comparison, focus/editor identity, pending/completed capability transitions, company/publication invalidation, ignored abort and pins 0/7; relevant existing controls remain passing. Financial-only cases assert no filing inventory, retrieval or AI requests.
- `node node_modules/eslint/bin/eslint.js lib/research.ts components/filing-research.tsx`: passed.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`: passed.

The exact bounded invocations and retained stdout/stderr/receipts are outside the checkout at `D:/Projects/finlens-guided-historical-20261103/`. `check.py` uses the existing direct-child supervisor with a 120-second deadline and 256 KiB output cap, Node heap limits of 384/512/768 MiB, and the existing network/private-environment preload. All completed checks reported zero blocked external I/O attempts and confirmed direct-child exit. These are process/test guards, not OS egress or aggregate descendant-memory containment.

Three initial unit runs failed while constructing the extended contract: synthetic operands first used incompatible filing accessions; a new assertion assumed instant observations retained fiscal annotations; another expected EPS percentage status `unavailable` rather than the actual `not_applicable`. Only synthetic fixture/expectation corrections followed source inspection; no backend behavior or existing assertion was loosened. All failed logs remain retained. The passing final unit run is `unit-4`; mounted/lint/TypeScript receipts are `mounted-1`, `lint-1` and `tsc-1`. Node's existing typeless-package warning remains.

## Acceptance contract

The reviewed bounded proposal uses desktop 1440/publication 0 and emulated 390/publication 7. Each case prepares annual revenue, unavailable direct-quarter revenue, operating-margin comparison and same-quarter EPS comparison, with four explicit financial POSTs, zero preparation/retrieval requests, invalid-year controls, source disclosure, keyboard/pixel focus and verified reading frames. Capability transitions and company/publication ownership remain covered by the independently passing mounted suite. JSDOM cannot establish rendered geometry or real-data availability.

## Acceptance history and narrow style correction

- The first native attempt (`a7fe85d780794ff4a3da2be5d654e2db`) stopped with **0 passed, 1 desktop failed, 1 narrow case not run**, before any financial POST. The Use question hit-test perimeter verdict rejected a transparent sibling paragraph. Independent screenshot inspection established continuous teal outline pixels; no product occlusion was demonstrated. Original trace, screenshots, request audits, consumed guard and cleanup evidence are preserved under `D:/Projects/finlens-annual-browser-artifacts-a7fe85d780794ff4a3da2be5d654e2db/`. Exact owned container absence, source/protected preservation and empty index were verified. No retry was performed in that turn.
- Earlier packaging failures and source snapshots remain preserved. List-only discovery now uses `--reporter=list` before source binding, preventing generated HTML reports from entering or mutating the immutable source inventory.
- The guided spec's corrected oracle retains ancestry as diagnostic and verifies continuous screenshot outline bands using PNG bundled in pinned Playwright 1.64.0, with no dependency addition. All prior keyboard/center/size/contrast/viewport/ancestor-clipping assertions remain. **37 focused pixel/geometry tests plus 21 reading-viewport tests pass**; this has not yet established a successful replacement native run.
- Independent review then identified missing styles on new year inputs and an incorrect new preview threshold. The product correction only adds `.question-guide input[type="text"]` to three existing control font/appearance/hover selector lists: full width, 14px text and minimum 44px height. Other input types/scopes and financial logic are unchanged. The browser layout check separately retains the existing 13px preview rule while requiring input/select text at least 14px.
- `node --test --test-isolation=none --test-timeout=10000 --test-reporter=tap tests/guided-fiscal-presentation.test.mjs`: **2 passed**, zero skips, checking exact control-style reuse, desktop/narrow declarations and selector scope. The **58 oracle/reading tests**, strict browser TypeScript, scoped browser lint and two-case list-only discovery also passed after the correction. All preload guards reported zero blocked external I/O. Current scoped evidence is in `D:/Projects/finlens-guided-style-fix-20261103/`; no additional native run or service launch occurred.
- A broader existing UX file reported its historical `No comparison-specific focus layers` failure on the already committed quarter-comparison selectors. One isolated control using the exact HEAD test and HEAD stylesheet reproduced that same failure. The existing UX file is unchanged in Git; no old assertion was weakened. New checks live in the separate focused file above. This historical suite is not claimed green, and the already verified 22/49 research suites were not redundantly rerun because their four source/test files remain byte-identical.

## Completion criteria and remaining gates

Product, style, focus-clearance, reading-oracle and startup-ledger corrections received independent scoped review. The following history supplements the earlier stages above; earlier statements that a native replacement was pending describe those stages, not the final two-case result.

## Subsequent native attempts and retained evidence

All attempts below were separately commissioned, used the same fixed offline image with no external network or published ports, and retained their consumed guards, original results and identity-cleanup evidence. No failed result was rewritten. The known six optional WASM dependencies remain unverified.

- `e1212e3c57d94f05a933c5aba77c9be7`: **0 passed / 1 desktop failed / 1 narrow not run**. Native Tab navigation placed Shared fiscal period at top -0.234375px, clipping its 6px outer outline. The reviewed product correction adds only `scroll-margin-block:8px` to guided text inputs, selects and buttons; no test scrolling, focus override or relaxed threshold. The focused style suite now has three cases.
- `49cac3eab3c243bc929bcc3a85251fae`: **0 passed / 1 desktop failed / 1 narrow not run**. All five control focus captures passed and all four financial POSTs completed, but EPS explanation exposure failed. The screenshot showed the explanation; that helper asserted before attaching its geometry, so its exact failing sample remains unavailable. A rounded-corner hit-test issue was plausible, not proved from that attempt. The independently reviewed scratch correction uses bounded actual text interiors (two height bands by five horizontal positions per fragment), records each hit/ownership and attaches labeled geometry/PNG before final assertions. Complete-target containment, paint, font and clipping remain required. **75 offline controls passed** after a missing mock identifier was repaired; this was synthetic oracle evidence, not another native run.
- `43e740adb45e4c4a85b12a9418992dee`: **1 desktop passed / 1 narrow failed**, no not-run or retry. The 390px case failed at initial exact request accounting, before preparation or a financial POST: two successful `GET /companies` requests were observed instead of one. Source inspection and the existing mounted regression establish that the first nonzero `evidence_version` triggers one catalog reconciliation; facts-only changes do not. The reviewed spec now requires exactly one extra successful, unpinned, queryless/bodyless catalog GET only for nonzero evidence publication. **20 focused controls passed**, including missing reconciliation, a third GET, facts-only nonzero/evidence zero, strict identity/status negatives and both retained startup records. Preparation-time zero-request checks and all other spec functions remain unchanged.
- `7d1089b7500049a290339cde4d503511`: **2 test cases passed / 0 failed / 0 skipped / 0 not run / 0 retries**, desktop 1440/publication 0 and emulated 390/publication 7. Four exact financial POSTs completed in each case; catalog GET counts were one and two respectively. Both cases passed invalid-year, source disclosure, focus/pixel, reading and layout assertions. Ten focus and six reading geometry records and all eighteen PNG dimensions/hashes were independently checked. Page width equaled viewport width, controls were 14px and preview 13px. Representative screenshots were visually inspected. Docker attach took 21.484 seconds; the container exited 0 without timeout or OOM.

The last attempt's **overall wrapper result remains FAILED (outer exit 1)**. After export, PowerShell StrictMode read absent optional `exportError` at runner line 633; JavaScript supplies that field only on export failure. The final stdout receipt in `ownership-intent.json` reports `PRELIMINARY_TEST_EVIDENCE`, both phase evidence flags, a matching artifact-index digest, 30 exported files and 3,424,349 bytes. Its stored `receipt.json` predates the added export metadata. All 29 indexed files were independently hash/size verified, but the original outer `testEvidence`/`artifacts` gates remain false. No runner repair or native rerun was performed to relabel that result. Independent review permits limited functional acceptance and CI integration, not full native gate PASS.

Evidence roots follow `D:/Projects/finlens-annual-browser-artifacts-<attempt>/`. Final inspection: `D:/Projects/finlens-guided-native-inspection-7d1089b7500049a290339cde4d503511/inspection-receipt.json`, SHA-256 `B6B66ED1A05DE407CDEE2DCFB856A1322B791C3BEC4D66F6308BAAD20976F90B`. Original final result SHA-256 `C372AB0A65094AD53FFD88E97354CDC6B171FD0BE5136E7124D08BC449E901E9`; artifact-index SHA-256 `B34CE7416C23385B921718B772B476FC8CCBC6B7CDAAA07B5EE33505E07CF1E4`. Earlier packaging/source-binding refusals, including generated HTML report drift before a lock or workload, remain retained separately; they were not browser case failures.

Exact owned containers were independently confirmed absent after every attempt; original source, five protected exceptions and empty index were preserved. Final cleanup recorded internal ports 3107/3108 closed, zero extra live processes, owned runtime removal and host CLIs reaped. The Next development N badge visibly overlaps some lower guide help text in the 390px Shared fiscal period frame. It does not overlap measured focused controls or measured EPS/unavailable targets; no blanket no-occlusion claim is made.

## Final integration checks

The three reviewed browser files are integrated without semantic changes. Git's existing `core.autocrlf=true` produced CRLF in the new spec/JSON; normalized LF bytes match the accepted snapshot exactly, while the config matches raw bytes. The existing wrapper/support scripts remain external and are not part of this ten-file candidate.

Final checks actually run against the integrated checkout on 2026-11-03:

- Existing guarded `research.test.mjs` plus `guided-fiscal-presentation.test.mjs`: **25 passed**, zero skips (22 utility/backend-contract cases plus three style cases).
- The same bounded mounted selection documented above: **49 passed**, zero skips.
- Scoped ESLint on the two product TypeScript files, browser spec and Playwright config: passed. Project `tsc --noEmit --incremental false`: passed.
- `playwright test e2e/guided-fiscal-questions.spec.ts --grep 'guided fiscal questions:' --list --reporter=list`: exactly **two cases discovered**; no browser or service launched.
- The single legacy `UX-01A comparison uses the shared focus outline without source overlay workarounds` case: **one failure on current CSS and the same one failure on exact HEAD CSS/test**, both `No comparison-specific focus layers` on the already committed quarter-comparison selectors. The legacy test is byte-identical to HEAD. No baseline failure was fixed, hidden or counted as a pass.

Exact commands, bounded receipts and logs are retained in `D:/Projects/finlens-guided-final-integration-20261103/` (`check.py`, `unit-final`, `mounted-final`, `lint-final`, `tsc-final`, `discovery-final`, `legacy-candidate`, `legacy-baseline`). This reuses the earlier 120-second direct-child supervision, 256 KiB output cap and 384/512/768 MiB Node heap bounds. Every direct child exited; all guards reported zero blocked external I/O. The existing typeless-package warning remains. No repeated browser workload, wrapper modification, configuration/private-data access or Git write occurred during this integration.

This slice does not establish financial coverage, real-data availability, accounting comparability, physical touch, native Windows browser, screen-reader, zoom or forced-colors acceptance. Final source/evidence review, a separately authorized commit/push and exact-commit CI remain outstanding. No new native run is required merely to repair the external wrapper issue.
