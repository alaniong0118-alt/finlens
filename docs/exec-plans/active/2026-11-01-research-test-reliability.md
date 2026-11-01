# Research regression test reliability

## Objective and bounds

At baseline `62913ead3e66ed82bc512288d547912ae8b3c138`, repair only the demonstrated test harness/expectation defects. No production source, routes, release policy, services, browsers, network, live database, credentials, Git writes or cleanup. Preserve the four existing protected exceptions and all source evidence. This is a follow-up reliability slice, not new product behavior.

## Original evidence and decisions

Retained `%TEMP%/finlens-dual-baseline-regression-20261101.log` recorded 604 mounted tests, 580 passes and 24 failures; the retained static-render log recorded one loader failure. The broader prior cohort reported 1121 passes, 25 failures and 4 skips. These 25 failures predate dual-filing implementation; this does not make them acceptable or prove later assertions pass.

Read-only current-HEAD probes confirmed: 22 request expectations omit annual and/or quarter discovery; one unavailable fixture fabricates a null-valued provenance fact; one corpus assertion incorrectly suppresses diagnostic tables for not-applicable rows; one static loader resolves relative TS dependencies from the test directory. All 306 guarded real backend histories passed the current validator. Bank gross-profit history renders three null not-applicable rows and its backend reason, with no chart. No production defect was demonstrated by these initial failures.

## Implementation and acceptance

- [x] Add identity-bound mounted request recording and explicit five-endpoint scope assertions, admitting only two verified discovery replays when requested. Bind original company/path/query/method/body/pin/signal and per-request notifications without assuming global notification order.
- [x] Repair affected expectations, unavailable provenance and diagnostic-row/chart assertions; preserve exact values, nulls and reasons.
- [x] Use a real TS/TSX component loader with importer-relative resolution, frontend aliases and early export caching. No rendering stubs.
- [x] Add dedicated negative ledger counterexamples and explicit null-valued-source rejection. Add private-configuration/network audit guards to the newly reachable pure static backend fixture.
- [x] Run focused repairs and dedicated negatives first; retain their exact outcome.
- [x] Run one complete relevant mounted/static cohort including all 306 real backend serializations. Preserve newly exposed failures separately from the original 25; do not claim full pass prematurely.
- [x] Review exact diff, whitespace, hashes and protected files; hand off for independent review before Git.

## Validation record

Dedicated support tests initially passed 33/33, exit 0 (`support.log`). First focused repaired cohort passed 29/30, exit 1 (`focused-1.log`). The remaining failure was newly reachable at the concurrent-409 assertion: `old[0]` is now annual discovery, whose own mismatch aborts its operation. The test now explicitly delivers the verified snapshot request first, then the other recorded identities; it retains settled-snapshot/live-transport and canceled-sibling assertions without assuming endpoint creation determines notification order. No product change was needed. Added raw-URL/row binding counterexamples before final validation.

Logs are retained outside source at `D:/Projects/finlens-test-reliability-gate-c5422015dc3c487baf52ff899a68cb0b`. The initial read-only probes changed no files and made no external calls. Implementation is test-only; no browser or production-source edits are authorized in this slice.

Second dedicated run: 34/34 passes, zero failures/skips, exit 0 (`support-2.log`). Second focused repaired cohort: 30/30 passes, zero failures/skips, exit 0 (`focused-2.log`), including the 306-serialization mounted corpus. These followed the recorded targeted changes; unchanged broad suites were not repeated.

Final cohort ran exactly once after focused acceptance: `node --test --test-reporter=tap tests/research-interactions.test.mjs tests/research.test.mjs tests/research-test-support.test.mjs tests/history-request-accounting.test.mjs`, frontend cwd. Result: **660 passed, 0 failed, 0 skipped/cancelled/todo**, exit 0, 27.365 seconds (`complete-cohort.log`, structured `complete-cohort.json`). This includes all 306 mounted real backend serializations and the formerly blocked pure backend guided-question check. No unrelated full-suite run, browsers, live services, model or external network occurred.

The original 25 failures are resolved in this relevant cohort. One additional formerly blocked creation-order assumption was encountered and preserved in focused-1 evidence; it was corrected by explicit snapshot identity rather than weakening cancellation assertions. No remaining defect is exposed by this cohort; no claim is made about unrelated suites or real-data/encoder acceptance.

Final scope is six files: the two existing test files, two small test helpers, dedicated counterexamples, and this plan. Production sources and shared existing browser accounting tests are unchanged. Whitespace checks passed; HEAD remains `62913ead3e66ed82bc512288d547912ae8b3c138`, index is empty, and all four protected exceptions retain their recorded raw hashes. No Git mutation or cleanup was performed. Candidate is ready for independent review; commit/push remain outside this handoff. Exact final raw hashes, scoped statistics and log identities are recorded in the external gate's `final-manifest.json`.
