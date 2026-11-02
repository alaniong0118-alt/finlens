# Loaded coverage filters and selected annual chart

Status: active — offline checks and bounded synthetic browser acceptance PASS; final scope/delivery review pending
Roadmap phase: bounded presentation of existing deterministic research data

## Objective and scope

Show status totals and metric/status filters for the already loaded coverage map,
and an optional single-metric observation chart for already selected annual
comparison columns. Preserve exact table values, reporting dates, reasons and
source disclosures. These are partial user-facing improvements, not completion
of D9, historical coverage, chart accessibility, real-data acceptance or the beta.

## Baseline and constraints

Start at `979159efb87f008655edf053225b274dd6b0e91d`, main, empty index and five
known protected exceptions. Preserve the existing 33 coverage response/body
regressions unchanged. Other feature workers use isolated snapshots; balance-date
and all other features are excluded. The four independently reviewed coverage
and annual-chart source/browser patches and the separately reviewed corrections
below are integrated, without financial-semantic or browser-oracle changes.

No database, provider, network, private configuration, model, browser, service,
installation or security-setting work is part of this integration. Do not stage,
commit or push before the separately coordinated bounded browser acceptance.
Never delete/format drives or clean existing files/resources. Keep native browser
policy restrictions intact; no alternate control route is used.

## Architecture and decisions

- Coverage totals are a projection of validated loaded cells. Local filters retain
  original reasons/provenance and make no acquisition, completeness or extra-request
  claim. Scope changes, clear and new loads retain existing request ownership.
- Annual chart selection uses the existing eleven metrics and selected columns.
  Separate dots preserve missing observations; exact values and sources remain in
  the table. Unsafe numeric projection, incompatible units or conflicting revenue
  bases refuse a shared axis. No interpolation, new financial formula or request.
- Source patches and browser specs already passed independent review. Bind the
  integrated bytes to their exact patches and frozen snapshot files; stop on any
  semantic conflict instead of silently merging or changing expectations.

## Implementation stages and progress

- [x] Confirm baseline/index/protected state and the four approved patch digests.
- [x] Apply exact non-overlapping patches and verify each candidate byte stream.
- [x] Run focused mounted/helper regressions, including the unchanged 33 cases.
- [x] Run scoped lint, TypeScript and list-only discovery of exactly eight cases.
- [x] Freeze integrated hashes and evidence for coordinator review.
- [x] Separate pinned offline browser acceptance, screenshots/focus/request audit.
- [ ] Final scope review and subsequently authorized Git delivery.

## Validation strategy

Use only existing installed Node dependencies. Run focused test files in separate
owned Node processes with the established offline I/O guard; do not mix global
DOM harnesses in one process. Retain bounded logs, timeouts, exit and guard counts.
Lint only changed TypeScript files; typecheck with no emit/incremental writes.
Use installed Playwright CLI `--list` with an explicit reporter and exactly the
three selected spec files. Discovery must not launch the browser or web server.

Expected eight cases: two coverage summary/filter widths, four existing coverage
map/date-range cases, and two annual-chart widths. Bounded geometry, focus, visible
source and request-accounting assertions passed in the final run recorded below.
The acceptance worker used a separately reviewed isolated pinned snapshot;
this live-checkout integrator did not launch a duplicate workload.

## Discovered issues and actual results

Initial combined-checkout validation passed 60 tests in four separate guarded
Node processes: coverage presentation 4, annual chart 5, coverage regressions 33,
and existing annual comparison 18. Scoped lint, no-emit/non-incremental TypeScript
and list-only discovery passed; discovery found five desktop-project and three
mobile-project cases. Guard blocks were zero and all owned processes exited.
Evidence is retained in the external `finlens-dual-presentation-integration-20261102`
artifact directory. Browser execution was separately owned, not launched by this
integrator. Source and browser specs were unchanged after their reviewed patches.

## Completion criteria and current outcome

Exact reviewed bytes, no unexpected root changes, focused checks passing, eight
discovered cases, empty index and protected-file preservation are the offline
handoff gate. Bounded synthetic browser acceptance has passed; final scope review
and subsequently authorized Git delivery remain pending.
No full-feature or external-beta completion claim is made.

## First isolated browser attempt and responsive correction

The acceptance owner reported one passed 1440px annual-chart case, one failed
390px annual-chart case, and six remaining cases not run after the failure.
The narrow chart's label legibility assertion observed 6px. This is a failed
attempt, not an eight-case acceptance. Its retained artifact root is
`D:\Projects\finlens-annual-browser-artifacts-4d7327f75d584a4a83bb5dffd2565299`;
`overall-result.json` SHA-256 is
`1BC1FB1A19C8F1AC78560CDE8D3189BF75F2067B56181445D958136624BA851C`.
The receipt confirms owned container absence and preservation; original failed
artifacts are not overwritten or reclassified as passed.

Independent review passed a separate minimal responsive correction, patch
SHA-256 `BAAA6465887CB6AB7EB15B4A78E32EDD9355B85855A641FC5D0B1740920A47A0`.
Only `annual-comparison-chart.tsx` and its focused mounted test changed: use a
measured SVG width with fixed 220px height, and a 240px minimum inside a contained
horizontal-scroll region. Resize observation is cleaned up on unmount. The
financial projection, exact table contents, requests and eight-case browser
oracle are unchanged; no font/geometry assertion was relaxed.

After integration, the responsive chart's six tests and the existing eighteen
annual-comparison tests passed in separate guarded processes (24 total, no skips
or guard blocks). Scoped component lint and no-emit/non-incremental TypeScript
also passed; all owned processes exited. This is targeted new evidence, not a
claim that the earlier full 60-test batch was rerun. Other candidate files,
the existing 33-case coverage regression file and five protected exceptions
remained byte-identical. New receipts are under the external
`finlens-annual-responsive-integration-20261102` artifact directory.

At this stage the rerun was **PENDING**; its actual outcome is recorded in the
second-attempt section below. The acceptance owner bound a separate fresh one-run
proposal. This integrator did not launch another browser, commit/push, or
integrate the separate balance feature.

## Second isolated browser attempt and local focus spacing

The acceptance owner reported five desktop-project passes and one mobile-project
pass, followed by one mobile failure and one remaining mobile case not run
(six passed, one failed, one not run overall). Annual-chart labels measured 16px
at both 1440px and 390px; the 390px chart case is a narrow desktop context, not
separate touch acceptance. The remaining failure was the mobile Status control's
outline extending 6.23px below the viewport. The eight-case suite did not pass.

Retained evidence is at
`D:\Projects\finlens-annual-browser-artifacts-cba245de38be473cb4eba9a800144ce2`;
`overall-result.json` SHA-256 is
`273B8CD8C7EE2C6C357130A1A96D785C3EABFD3E48072E664EEF3E352CF38A8F`.
Its owned-container absence, preservation and host-CLI cleanup checks passed.
Both failed attempt directories and their original statuses remain preserved.

Independent review passed the minimal focus-spacing patch, SHA-256
`8D8B5EC5427FDD002255B7848F93C1F3972EEFF5C9E6773648A992D3E2C3A584`.
Only the coverage Metric and Status selects receive a local 8px scroll margin,
plus a focused mounted regression. Existing outline width/offset, browser
viewport, geometry tolerances, eight-case oracles and all annual source remain
unchanged. No scripted browser scrolling, new request or financial logic was added.

Integrated validation passed one new focus regression, four coverage-presentation
tests and the existing thirty-three coverage regressions (38 total, no skips or
I/O guard blocks). Scoped coverage-component lint and no-emit/non-incremental
TypeScript also passed; owned Node processes exited. The unchanged annual tests
were not rerun or added to these counts. Receipts remain in the external
`finlens-coverage-focus-integration-20261102` artifact directory.

At this stage the next native check was **PENDING** under a fresh separately
bound one-run proposal; its accepted outcome is recorded below. This integrator
launched no browser, kept the index empty, made no commit/push and did not
integrate the balance feature.

## Final bounded synthetic browser acceptance (2026-11-02)

After the two reviewed product corrections, one fresh final attempt passed all
eight selected cases: desktop project 5 and mobile project 3, with no skipped
cases, flaky results or test retries. This does not reclassify the two earlier
failed attempts; all three attempt directories and original outcomes remain.

Final artifacts are retained at
`D:\Projects\finlens-annual-browser-artifacts-c76e0b6fa33f4d40a102c95c145c3457`.
The accepted snapshot manifest SHA-256 is
`D9E6CD483A22C9BB3354C516122A9026613EB9A5CDB4FEDCC1EE8EA2E798C1A5`;
the terminal `overall-result.json` SHA-256 is
`491235467718183D38D7D1CF043581AF0548B7082B5EC4C0073387BA6C5798F9`.
Desktop and mobile report SHA-256 values are respectively
`A606C312187CE46FA930AE8FAD354189ED24F44394D23BE78927AEAA193E6C6C` and
`17E8AF12ED98A50EB0ECED5D44F1AB5E2AE567DA2E851720377D8EB8B872B65A`.

The acceptance owner inspected screenshots and geometry: the mobile Status
outline bottom was 842.23px within the 844px viewport, and annual-chart labels
were 16px at both 1440px and 390px. Request audits reported no violations; recorded
request failures were aborts. The 390px annual-chart case used a narrow desktop
context, not mobile emulation. No full screen-reader, zoom, forced-colors or
touch acceptance is claimed. Six optional WASM dependency risks remain unverified
(`UNVERIFIED_OPTIONAL_DEPENDENCIES`); this is not full dependency verification.

All terminal ownership/preservation gates passed, including exact owned-container
absence and host-CLI cleanup. The integrator rehashed all 29 final indexed
artifacts and the prior 19 plus 32 indexed artifacts without mutation. Runtime
sources/browser specs match the accepted snapshot after explicit CRLF-to-LF
normalization, except the accepted isolated `next-env.d.ts` typing-path adjustment;
the original protected file was not changed. Acceptance-only launch/provenance
helpers were not copied into production. All live source/tests and five protected
exceptions remained unchanged; only this plan was updated after acceptance.

Final review is **PENDING**. The index remains empty; no commit/push, balance
integration or additional native operation is part of this documentation handoff.
These synthetic fixtures do not prove real-data completeness, full D9, broad
accessibility acceptance or external-beta readiness.
