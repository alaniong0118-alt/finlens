# Single-company annual period grid — bounded requirement 4b

Status: active — three historical browser attempts failed; test-local response/terminal recorder correction passes focused offline checks and awaits independent review; no new browser run.
Roadmap phase: scoped Research Mode comparison increment, requirement 4b.

## Objective

Using the existing selected company, let the user explicitly choose two to four
discovered annual fiscal end-years and view all eleven existing server-calculated
metrics side by side. Retain actual windows, exact values, units, economic bases,
missing/excluded reasons, operands and selected/alternative source observations.
This is a bounded annual grid, not completion of the entire requirement 4b.

## Current architecture and context

Read root AGENTS.md, .agent/PLANS.md, ROADMAP.md, engineering standards, data-source
policy, full-feature-requirements.md row 4b, and financial-metrics.md CC-02 contract.
The stored-only annual endpoint discovers fiscal end-years or returns an exact
annual eleven-metric result. FinancialMetrics remains the calculator. The existing
ResearchFreshness provider supplies the selected company's publication pin;
versionedController/getAnnualFinancials enforce the response version header.
Existing FinancialInsights handles a separate two-year insight workflow; existing
CompanyComparison compares issuers. Both stay intact.

Entry/resume HEAD: d6a9e42ce8571bec5450b06fed97d829d6b1272f. Index is empty;
index SHA256 E99C340A1DE7EB5F2EBFAD8F6C0B3D2C98B11DBEFD3C77F921680441F7A11ACC.
The preexisting eight modified and five untracked paths are preserved below.
No edits occurred in the interrupted initial inspection. Coordinator explicitly
abandoned the optional denied Win32_Process query and coordinates the single
writer through task status plus preserved hashes. Do not retry process inventory.

## Constraints

Only five paths: this plan, frontend/components/annual-period-comparison.tsx,
frontend/lib/annual-period-comparison.ts, frontend/tests/annual-period-comparison.test.mjs,
and frontend/app/page.tsx. No backend/contracts/dependencies, Git writes, acquisition,
services, database, Docker, browser launch, export, persistence, authentication or
source-policy exceptions. Never read or hash backend/.env. No self-review or
self-dispatched agents; coordinator owns focused independent review.

## Non-goals

No new financial formula, arithmetic, ranking, FX conversion, quarterly/YTD grid,
original/restated vintage selector or new permission. Existing metric eligibility
continues to decide unavailable and not-applicable states. Viewing stored admitted
API results grants no additional source, acquisition, export or redistribution right.

## Implementation stages

1. Reconfirm status and immutable paths; write this plan.
2. Add isolated response/presentation validation and annual-grid component; insert
   beside existing selected-company research inside ResearchFreshness.
3. Run inspected offline Node/React/JSDOM tests, targeted lint and no-emit type check
   without install, network, service, browser or database access.
4. Record actual checks, limits and hashes. Hand off for independent review.
Recovery: remove only the new candidate paths and reverse only the small page
integration, preserving every preexisting modification.

## Decisions

- 2026-10-31: Reuse the global company picker and its publication provider rather
  than add a second catalog/freshness workflow. Explicit annual checkboxes prevent
  invented periods and missing-year fallback. Every selection/request owns a new
  cancellation scope; a version mismatch hides the entire grid.
- 2026-10-31: Reuse CC-02 eleven-metric identity/window validation and existing
  MetricProvenance/SEC-link display policy. Additional local validation protects
  React's display fields and operand/source relationships; it changes no API.
- 2026-10-31: Native fieldsets, checkboxes, table headers, disclosure controls and
  horizontally scrollable existing styles provide the responsive/accessibility
  structure; actual browser/keyboard/layout acceptance remains a later gate.

## Discovered issues

The optional process query was access-denied and its escalation interrupted. No
repository operation ran through it. Coordinator directs abandoning it entirely.
No implementation blocker identified in the existing annual API.

## Progress

- [x] 2026-10-31: Instructions/contracts and narrow implementation inspected;
  resume status, HEAD, empty index and all thirteen preserved hashes match entry.
- [x] 2026-10-31: Isolated helper/component/page integration implemented.
- [x] 2026-10-31: Focused offline validation completed and recorded below.
- [x] 2026-10-31: Coordinator reported focused Astra review PASS WITH CONDITIONS,
  no blocking finding; added its requested positive shared-source YoY regression.
- [ ] Separately scoped and approved browser acceptance; stop for coordinator.

## Test and validation strategy

Use installed Node, TypeScript, ReactDOM and JSDOM only. Fetch is replaced by
in-memory responses. No child-process/backend fixture runner, network, services or
DB. Cover explicit 2–4 years; zero/null pins; malformed/mixed identity/window/unit/
sources; missing and excluded data; basis/duration warnings; partial failures;
rapid selections/company/version changes; stale continuations, cancellation,
refresh, unmount; actual provenance links and page integration. Targeted lint and
TypeScript no-emit checks must not regenerate next-env.d.ts or build artifacts.
Broader browser/API/data acceptance is intentionally deferred to coordinator.

### Actual validation (2026-10-31)

Working directory for commands below: D:/Projects/finlens-foundation/frontend.

- `node --test tests/annual-period-comparison.test.mjs`: initial sandbox invocation
  failed before tests started with Node test-worker `spawn EPERM`. Reported the
  exact approval action immediately and reran the same command with approved
  escalation. Actual result: **17 passed, zero failed/skipped/cancelled**, 1.21s.
  This runner loads installed TypeScript/React/ReactDOM/JSDOM in memory, uses the
  actual API transport and MetricProvenance, replaces only fetch and publication
  context, and has no backend/child-process fixture calls. The Node test worker
  is the only worker process; no browser/service/database/network was used.
- `node node_modules/eslint/bin/eslint.js components/annual-period-comparison.tsx
  lib/annual-period-comparison.ts app/page.tsx`: exit 0, no diagnostics.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false`:
  exit 0, no diagnostics. No Next build or generated file writes.
- At repository root, `git diff --check`: exit 0 (line-ending notices only).
- Compared all thirteen protected paths against this plan's baseline SHA256:
  **13/13 identical**, including finalized nine, blocked export plan, next-env.d.ts
  and both historical backend reports. Index SHA256 is unchanged and staged path
  list remains empty; HEAD is unchanged. No unexplained drift observed.

Coverage includes 2–4 explicit periods, zero/null pins, empty/single-year/discovery
failure, malformed issuer/year/window/unit/fields/source lineage, exact zero and
negative values, missing/excluded reasons, sources/alternatives, rejected off-origin
source links, unequal durations/bases, operand periods, partial failures, missing
headers, mixed pins, cross-period source-ID conflicts, selection/company A→B→A,
pin invalidation, unmount, cancellation, refresh, and page/provider integration.
Assertions of responsive/accessibility structure are DOM evidence only. Actual
layout, keyboard scrolling/focus, browser synthetic-runner compatibility, live API,
stored DB coverage and current deployment remain **unverified**. No self-review
or independent review was performed in this implementation chat.

### Focused review follow-up (2026-10-31)

Coordinator reports focused Astra review turn `01a190f3-b15f-7ee2-8db7-2c225ffe20b8`
as **PASS WITH CONDITIONS**, with no blocking finding. Its sole requested offline
addition is now implemented in the existing test path: adjacent FY2025/FY2024
Revenue YoY results share an unchanged FY2024 source fact, reused as later-year
prior operand and earlier-year current operand. Distinct current/prior roles,
annual windows, fact IDs, economic-basis fields, exact supplied ratios, displayed
percentages and SEC source links all survive rendering. The positive fixture uses
compatible `total_revenue` bases in both operands; it does not fabricate an
available calculation across incompatible bases. Existing conflicting-fact-ID
rejection assertions and production validation remain unchanged.

Ran exactly one targeted follow-up command from frontend:
`node --test --test-isolation=none tests/annual-period-comparison.test.mjs`.
Actual result: **18 passed, zero failed/skipped/cancelled**, 1.13s. Installed Node
advertises the supported isolation flag; this in-process invocation required no
approval, test-worker spawn, alternate runner, network, services or DB. No other
suite, lint, type check or browser acceptance was rerun for this test-only change.
Untracked test whitespace check produced no error diagnostics (only its LF/CRLF
notice; no-index returns 1 because the file is new). All thirteen protected hashes
and index SHA256 were rechecked unchanged; three production code hashes below
are unchanged. Only the candidate test and this existing plan changed.

Remaining browser conditions belong to coordinator: real Tab navigation,
disclosures, horizontal scrolling and focus clipping at desktop and 390px, actual
ResearchFreshness provider integration and a full-page request ledger. No browser,
Docker, Git writes or additional task was started. Stop here for coordinator.

### Candidate code SHA256

| Path | SHA256 |
| --- | --- |
| frontend/app/page.tsx | A8A5077060D512E2782DF8193E37C8770C194E77D079E885A27CE3F7AE920386 |
| frontend/components/annual-period-comparison.tsx | 98F471A8AEB1DC75049721EFCF8750109946FEFBE4BE358F195F9B5D145E15E4 |
| frontend/lib/annual-period-comparison.ts | 6F300BBE970220DC32D26052A7BFA6A38AECB3558F80941368D34AA13CBF75CD |
| frontend/tests/annual-period-comparison.test.mjs | 2191FD2F56EFC6959042E1E375A39E19298C4B1E96964650A7B13F8140FB91E9 |

## Completion criteria

Bounded UI behavior and safe focused tests pass; all protected hashes and index
remain unchanged; five-path candidate is handed off with limits and actual hashes.
Focused static review has a conditional pass as reported above. Actual browser
acceptance remains a separate pending gate.

## Preserved baseline SHA256

| Path | SHA256 |
| --- | --- |
| frontend/e2e/comparison.spec.ts | 3452DC7987B55668FA92497E5571A94562B30E0F9FC632F347EFC65E80C926A1 |
| frontend/e2e/fixtures/browser.ts | 248006C5AFA4F31978D5E1290FE56C74A1C298F4DE71D82C72F9756AFF840472 |
| frontend/e2e/fixtures/data.ts | BA6232C92E318395D9827788B665318645977D898248A37E862656CF01541485 |
| frontend/tests/qa01-harness.test.mjs | F7D505B0E098C20E5F2AE9EA60D554AC19CBECE391D7C14D9CFCF16B41D108D7 |
| frontend/components/company-comparison.tsx | 4BF228BFB99DCAC347F9233D95C79B87874CCA457AA7348810A697D9984AC9C3 |
| frontend/tests/company-comparison.test.mjs | DAEE3A8C301B5A4A52157D889D3F9401A0BB41BFE4B7BB002B4C565ED43F25D1 |
| frontend/e2e/comparison-gap-filter.spec.ts | 94CEA66DCCB72DB5A7F35A7FA4649A4ECC6B96A6E0396069E3EE76DEDAC132F3 |
| frontend/playwright.config.ts | 334E3749D69C858703F5DDBAF9B6EA58471F6931E7F383DBF17CC91E38B39216 |
| docs/exec-plans/active/2026-10-31-comparison-gap-filter-browser.md | 49CC6AB337B1388390F0A308023B8F49E017E4F773A2013F3586D129F0B864A8 |
| docs/exec-plans/active/2026-10-31-annual-comparison-markdown-export.md | 018323260C0FD778346DD397CD419E0F2376018DC2FBE3570BFAD37781B16051 |
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

## Final outcome

Five-path candidate received coordinator-reported focused independent Astra
PASS WITH CONDITIONS and its positive offline regression is implemented and
passing. All eleven metric values, formulas and source selection remain backend
owned. Existing API/publication admission and SEC link display policy are reused;
no source rights, acquisition, export or persistence permission is added.

Git status delta is exactly one modified tracked page plus four new untracked
candidate files; all preexisting eight modified and five untracked paths remain.
No stage, commit, push, shutdown, browser, Docker, database, service or source
acquisition action occurred. Keep this plan active pending the separately scoped
browser acceptance. Stop for coordinator. Suggested eventual commit:
`feat: compare selected company annual periods`.

## Authorized browser preparation — 2026-10-31

Coordinator authorizes two new repository test paths only:
frontend/e2e/annual-period-comparison.spec.ts and
frontend/e2e/fixtures/annual-period-browser.ts, plus factual updates to this plan.
Existing five-path candidate code, finalized nine, blocked export plan and all
other protected paths remain frozen. No browser/container run before focused
review PASS. Stop after the preparation report; no self-review or dispatch.

The existing mobile testMatch excludes the new spec. A separately pinned external
snapshot/frontend/playwright.annual-period.config.ts can import the frozen config
and add only this spec to the mobile project's testMatch. No repository config edit
is needed. The existing QA Scenario validates only 2024/2025 annual routes, so a
new local fixture layers exact annual-route interception on that same Scenario,
leaving its no-egress guards, other route fixtures and deny-all health checks intact.
It explicitly admits only the test-local four-year inventory and records every
request in Scenario's existing full-page ledger. Synthetic values are test data,
never acquired issuer data or production metric calculations.

Planned minimum: desktop two cases and one 390px touch case, actual freshness
provider/full page, 2→4 years, shared adjacent-year source lineage, missing period,
pin-zero request accounting, mismatched-version fail-closed behavior, cancellation,
company scope, real Tab/disclosures and full focus-outline containment, horizontal
touch scrolling. Reuse the prior pinned no-egress image/runner with a fresh owned
snapshot, artifact root and unchanged resource/deadline/cleanup boundaries.
Offline fixture/protocol checks and exact final selector discovery precede review.
Actual results and pins will be appended before handoff.

### Prepared browser candidate and actual offline results

Only the two new repository test paths and this plan changed in this stage. The
page/component/helper/unit-test candidate hashes above remain identical. New paths:

| Path | SHA256 |
| --- | --- |
| frontend/e2e/annual-period-comparison.spec.ts | 0090042AAF3B1C10AF152A48458A14C93E2B66D4E2E5F57719872A327847AAC9 |
| frontend/e2e/fixtures/annual-period-browser.ts | 45034C619F191C60DF950B924063C2911ADD161762B4FBA85A1F2CC7E3835686 |

Fresh external snapshot:
`D:/Projects/finlens-annual-period-browser-b238cd9875a442bcb6d538d688f4671a`.
Explicit source inventory: **50 files, 1,652,826 bytes**, aggregate SHA256
`DEA1E0E3BCA95F4A2A3130BA095CC773EC9DAD1E904A84B1A8EF4BE5CDC1FC40`.
It includes the prior 44 explicit frontend dependencies, the approved page overlay,
three new approved component/helper/unit-test inputs, the new spec/local fixture,
and the snapshot-only mobile config extension. The unchanged parent next-env and
image provenance/telemetry helpers are copied from the prior accepted snapshot;
working next-env remains preserved. No env, backend, reports, dependency tree,
generated output, directory link or repository metadata is mounted.

| External snapshot relative path | SHA256 |
| --- | --- |
| frontend/playwright.annual-period.config.ts | CEB5928135B6ACB5CE0223A26E24966FBFD19178BBB4470094D97913CBBCF7D5 |
| acceptance-proposal.ps1 | F87DEFCAABCF2703DCEB15A340BE70E694C89FCDC42FC5A121F03DA5CBA9DCC9 |
| annual-host-process.psm1 | FFB7348004420677A7337CE7918D09E81A365259903E30AD7098782B3D2B9843 |
| proposal-offline-checks.ps1 | C1F22320DB0F7B2A35D1A0C2B07AB7218F3988AF8C313F4DA8A76F44CE0B22ED |
| annual-period-offline-checks.cjs | D21A37B1A3F40BFCDFF4C2D45BAC0602F2B34B0ADC18F79F916F35888B8679A6 |

The external manifest is created once after this factual plan entry is finalized,
so its protected-working hash binds these exact plan bytes without circular pins.
The handoff supplies its final SHA256 and exact proposed execution command. Do not
edit or repin the reviewed snapshot after acceptance. Host-only preparation/state
sidecars and discovery reports are outside the mounted snapshot; no historical
bundle, manifest or run artifact was modified.

Actual offline checks, all exit 0 on the final candidate:

- From frontend: `node node_modules/eslint/bin/eslint.js
  e2e/annual-period-comparison.spec.ts e2e/fixtures/annual-period-browser.ts`.
- From frontend: `node node_modules/typescript/bin/tsc --noEmit --incremental false
  --pretty false`. No Next build or generated-file rewrite.
- `node D:/Projects/finlens-annual-period-browser-b238cd9875a442bcb6d538d688f4671a/annual-period-offline-checks.cjs`:
  **10 checks passed**. Both issuers/four years pass actual client validators;
  shared YoY source lineage and strict conflicting-ID rejection; exact annual
  route/method/query/pin validation; obsolete-pin 409; ledger signatures; actual
  adapted support selection assertion; exact config/title/project mapping; embedded
  Node parsing/resource pins; declared-substitution reversal recovers the complete
  parent proposal code after line-ending normalization. No proposal execution.
- PowerShell parser: runtime proposal and both inherited PS support files parse
  without errors; embedded Node program parsed without executing it.
- Exact final selectors below discovered **desktop 2 / mobile 1**. Both JSON
  reports have zero errors and zero execution results. Discovery is not a browser
  pass. Artifacts are outside the snapshot at
  `D:/Projects/finlens-annual-period-preflight-b238cd9875a442bcb6d538d688f4671a/{desktop,mobile}-discovery.json`.
- All **13/13 protected hashes**, approved production/unit-test hashes, HEAD and
  empty index match. Index SHA256 remains
  `E99C340A1DE7EB5F2EBFAD8F6C0B3D2C98B11DBEFD3C77F921680441F7A11ACC`.
  `git diff --check` passed with only existing LF/CRLF notices.

During preparation the new offline checker initially asserted a different textual
spelling of the parent's unchanged security flag and looked for the stdin budget
in the proposal instead of the inherited host module. These test expectations were
corrected, then the scoped checks passed. The draft proposal's new support-list
comparison was put in sorted order before finalization. No runtime boundary was
relaxed and no browser, container, service, network, installation or approval card
was used. Earlier broad QA/component/support suites were not rerun.

### Exact final phase selectors (discovery actually ran)

Working directory: external snapshot/frontend. Host-only module resolution used
`NODE_PATH=D:/Projects/finlens-foundation/frontend/node_modules`; JSON reporter
destinations were the separate preflight directory above. The actual installed
CLI was `D:/Projects/finlens-foundation/frontend/node_modules/@playwright/test/cli.js`.

```powershell
node <installed-cli> test --config=playwright.annual-period.config.ts e2e/annual-period-comparison.spec.ts --project=desktop-chromium --workers=1 --retries=0 --max-failures=1 --reporter=list,json --grep 'annual periods:' --list
node <installed-cli> test --config=playwright.annual-period.config.ts e2e/annual-period-comparison.spec.ts --project=mobile-width-chromium --workers=1 --retries=0 --max-failures=1 --reporter=list,json --grep 'annual periods:' --list
```

Discovered titles exactly match the runtime proposal:

1. Desktop: `annual periods: two/four years, shared sources and native keyboard @desktop-only`.
2. Desktop: `annual periods: cancel, company scope and actual publication invalidation @desktop-only`.
3. Mobile: `annual periods: 390px touch, four-year missing data and horizontal scroll @mobile-only`.

### Full-page API accounting and remaining runtime gates

Every case asserts the complete Scenario API ledger, not only new-grid requests.
The new local annual route appends to that same ledger. Signatures retain method,
exact issuer path, query, publication header and body. Existing guards still block
external/static-route violations and check the deny-all upstream. The complete
API ledger is attached on every case, including successful cases.

Automatic initial page inventory is eight requests: unpinned companies and
capabilities, plus AAA freshness (unpinned), and pinned-zero insights discovery,
annual discovery, quarter summary, quarter revenue history and stored sources.
No automatic selected-year annual request is permitted.

| Case | Explicit expected final API count; still unexecuted |
| --- | --- |
| Desktop grid/keyboard | 14 = initial 8 + two selected annual requests + four selected annual requests; checkboxes, navigation, source/operand disclosures and keyboard actions add none |
| Desktop cancel/scope/version | 33 = initial 8 + cancelled pair 2 + BBB0 publication scope 6 + BBB cancelled pair 2 + returning AAA0 scope 6 + old-pin pair 2 + AAA1 re-verification scope 6 + one evidence-catalog reconciliation |
| Mobile touch/scroll | 14 = initial 8 + selected pair 2 + selected four years 4; touch, disclosure and scrolling actions add none |

BBB0 deliberately retains the existing explicit insights-unavailable fixture;
AAA1 after mismatch does the same. No successful insights body is invented.
The real provider owns re-verification and publication-zero handling. Cases retain
exact supplied YoY ratios, unchanged shared source IDs, current/prior windows/bases,
actual dates, missing/excluded reasons and official source links. Desktop reaches
both YoY operand disclosures using actual Tab/Space; focus checks include outline
paint against viewport and horizontal scroller edges without a synthetic focus fix.
Mobile requires 390px touch emulation, a native CDP touch swipe that increases
scrollLeft, final-column containment and no document horizontal overflow.

Pinned runner boundaries are inherited: image
`sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`,
UID/GID 1001, no egress/published ports, read-only image, dropped capabilities,
no-new-privileges, 2 CPUs/4096 MiB RAM/zero additional swap/256 PIDs/512 MiB shm;
runtime/artifact/tmp tmpfs 2048/256/256 MiB. Workload 600s + 20s termination grace;
separate cleanup allowance 90s. Host CLI metadata/create/attach/stop/reap deadlines
15/30/650/23/3s. Artifact limits 128 files/64 MiB per file/256 MiB total; phase
capture 2 MiB per stream, host capture 1 MiB per stream, stdin 128 KiB, logs 4 MiB.
Fresh owned run/artifact nonce, exact container ID/name/image/owner verification,
creation-bound telemetry, image-code attestation and verified owned-only cleanup
remain mandatory. Ambiguous cleanup is never a pass. Six optional WASM support
packages retain UNVERIFIED_OPTIONAL_DEPENDENCIES and the explicit one-run risk
switch; nothing is installed.

Ready for coordinator-controlled focused Astra review of this preparation. No
browser/container execution, current runtime acceptance, full accessibility claim,
source-rights expansion, export permission, Git delivery, self-review or dispatch
occurred. Stop for coordinator; only after review PASS may the separately approved
single isolated run proceed, using the final manifest hash supplied at handoff.

## Focused browser-preparation P2 corrections — 2026-10-31

Coordinator supplied Astra review `01a19107-36bd-7850-909d-7c6a5ecad652` with two
P2s: the row helper's inner has-locator incorrectly included the ancestor grid,
and overflowing narrow-grid keyboard focus was not exercised. Only this plan and
the new annual-period browser spec may change; no product/fixture/config changes.

The inner rowheader locator is now page-rooted for Playwright's row-relative
has-filter evaluation, while the outer row lookup retains the annual-grid scope.
The existing 390px case now first proves horizontal overflow and that the FY2024
source summary begins beyond the scroller edge, then uses real Tab from the
existing submit control to reach that later-column summary, requires horizontal
movement and full focus-outline containment, and opens it with Space. The original
touch swipe/final-column checks and unchanged full-outline helper remain intact.
No target focus/scroll injection or product focus fix is added.

Preserve the prior frozen snapshot and its manifest
`C9BCF76BF68B5C6CCA003D115647CB5EEA5E46ABDD5C9D2A86C7FEE248ABAE2A`.
Prepare a fresh successor snapshot at
`D:/Projects/finlens-annual-period-browser-59fa3093b5b04068b291ac4c56aa505d`.
Source inventory remains fifty files. Only the spec overlay changes; source
identity pins and the scoped offline-check support will be updated. Image,
fixtures, selectors/case counts, no-egress, resources and owned cleanup stay fixed.
Focused locator regression, lint/type checks and exact discovery results follow.

### P2 correction results and successor pins

Only the annual-period spec and this plan changed in the repository. The fixture
remains SHA256 `45034C619F191C60DF950B924063C2911ADD161762B4FBA85A1F2CC7E3835686`;
all approved production/unit-test files, finalized nine and other protected files
are unchanged. The prior snapshot's sources, proposal, support and manifest remain
intact. This entry supersedes the prior preparation pins only for the new P2
candidate; earlier preparation/test records remain historical evidence.

Successor snapshot: fifty explicit source files, **1,653,896 bytes**; aggregate
SHA256 `2C27B80EDD4E7108F84BF36FBCCC0D917F5959094FFE7C78BD7E66D67AD1B329`.
Only one of the fifty source files differs from the previous snapshot: the spec.
The proposal changes only nonce and source byte/aggregate pins. Same image,
fixture, config, three case titles, desktop2/mobile1 selectors, full-page ledger
expectations, resource/deadline/egress/ownership/cleanup bounds remain in force.

| Current P2 candidate path | SHA256 |
| --- | --- |
| frontend/e2e/annual-period-comparison.spec.ts | 2E56A7A2300A9C2EEB68509EC843B4676E6A821FBCA83DD6D08152C0AA486F41 |
| external successor/acceptance-proposal.ps1 | 0D3039EB9CD0CE3745A9F555911CAAF56400C6748F3338005604D8B0A0057A03 |
| external successor/annual-period-offline-checks.cjs | 838E5AD720B0EE87672E8BD87D25AF5ED5FB96CBEFD088A7E1361CCEF1E924C7 |
| external successor/frontend/playwright.annual-period.config.ts | CEB5928135B6ACB5CE0223A26E24966FBFD19178BBB4470094D97913CBBCF7D5 |

Actual focused checks (2026-10-31), no approval required:

- `node D:/Projects/finlens-annual-period-browser-59fa3093b5b04068b291ac4c56aa505d/annual-period-offline-checks.cjs --p2-only`:
  **3 passed**. Executes the actual AST-extracted row helper against a small JSDOM
  model of relative `filter(has)` evaluation: Revenue and Revenue YoY match only
  their annual-grid rows; the unrelated grid is excluded, and restoring the former
  ancestor-prefixed inner selector matches zero rows. This is a discriminating
  offline scope regression, not actual Playwright execution. The second check
  verifies overflowing/offscreen-target/Tab/Space coverage, confirms the full
  outline helper and Tab helper are byte-identical, and confirms the entire
  original touch/final-column block is byte-identical. The third reverses only
  nonce/source-pin substitutions and recovers the prior proposal code, and parses
  the embedded Node program without executing it.
- From frontend: `node node_modules/eslint/bin/eslint.js e2e/annual-period-comparison.spec.ts`:
  exit 0. `node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false`:
  exit 0. No build or generated-file rewrite.
- Successor proposal PowerShell parsing: no errors, no execution.
- Exact final phase discovery, same two commands as above with successor snapshot
  as working directory and installed CLI path unchanged: desktop **2**, mobile
  **1**, both exit 0. The separate JSON files at
  `D:/Projects/finlens-annual-period-preflight-59fa3093b5b04068b291ac4c56aa505d/{desktop,mobile}-discovery.json`
  have zero errors and zero execution results. Case titles and grep/file/config/
  project/workers/retries/max-failures/reporter selectors are unchanged.
- Other working candidates/protected hashes, prior frozen bundle bytes, HEAD and
  empty index verified unchanged. Spec whitespace check has no error diagnostics
  (only LF/CRLF notice; no-index exit 1 reflects a new file).

Only these focused checks ran. The previous ten preparation checks, 18 component
tests and broader QA/support suites were not rerun. No browser, container, service,
network, install, Git write, .env access, self-review or dispatch occurred. Actual
390px focus/outline visibility is intentionally **unverified until execution**.

Finalize a new manifest once this factual entry is frozen; its exact SHA256 and
proposed command are supplied in the handoff. Stop for coordinator-controlled Astra
rereview. Browser execution remains gated on review PASS.

## Failed attempt and causal lifecycle correction — 2026-10-31

After Astra PASS turn `01a1910e-bdbf-7800-af12-164b1838164d`, exactly one authorized
attempt ran under manifest `5C7A471D81C26960FE4C12C4ED4C25D0DC45B50071B011FBC8F0B74788589D27`.
Run nonce: `9f23189b20854f4eb59dbf0b1afdbce3`; owned container:
`384b525b69259345975bb1736a75e9b88d42874800f9aeff7d3da50bce229f6d`.
It failed before interactions: desktop one failed/one not run, mobile not started.
The initial API ledger expected eight started requests but observed ten. No
geometry/keyboard/mobile failure was established. No retry or runtime fix occurred.

Evidence remains at
`D:/Projects/finlens-annual-browser-artifacts-9f23189b20854f4eb59dbf0b1afdbce3`.
The nine indexed payload files plus index (1,150,772 bytes) match their hashes.
Index SHA256: `2034ED5E4447C734281C226DFBC8E2CE42F466EB9CF1A2B46F5F5DB197787C37`;
receipt SHA256: `658473AAC0A877DD851D39DE27F39A9FFFF839BA0FA9F2B586120E49E58D959E`.
The runner's testEvidence/artifacts gates remained false. Phase/final quiescence
failed on PID/starttime `174/9748309`; telemetry ownership was unverified. The outer
runner subsequently verified exact owned-container removal and reaped all nine
host CLIs. This is not a successful inner cleanup or browser acceptance.

### Request cause proved before edits

The retained trace records the exact sequence below (UTC):

| Request | Start | Network result | Pin |
| --- | --- | --- | --- |
| AAA freshness generation 1 | 08:27:39.534 | status -1, ledger ERR_ABORTED | unpinned |
| AAA freshness generation 2 | 08:27:39.535 | HTTP 200, data_version 0 | unpinned |
| AAA annual discovery generation 1 | 08:27:39.601 | status -1, ledger ERR_ABORTED | 0 |
| AAA annual discovery generation 2 | 08:27:39.603 | HTTP 200, years 2025/2024/2023/2022 | 0 |

Generation numbers here label successive request identities, not invented API
fields. The API does not transmit a generation ID. ResearchFreshness owns its
controller/signal; AnnualSession owns a distinct operation object and tests
operation.current identity plus abort state before publication. Their effect
cleanups abort the old scope. The provider's check callback is stable for an
unchanged ticker/catalog callback, and the annual session effect is mount-only
under its company/CIK/pin/refresh key; the trace contains no scope change.

Actual installed Next `dist/build/define-env.js:126` enables App Router StrictMode
by default when no reactStrictMode override is supplied. `dist/client/app-index.js`
wraps the app in that mode. The snapshot launcher explicitly starts `next dev`;
actual ReactDOM development code disconnects/reconnects passive effects during
StrictMode replay. The current Next config does not override this setting.

A scoped offline reproduction uses the actual provider, grid, API transport and
ReactDOM/JSDOM, with only in-memory fetch replies. Without StrictMode: two started,
two completed, zero cancelled. Under development StrictMode: four started, two
completed, two cancelled, ordered as the trace above. Deliberately late cancelled
responses offering publication 9 and year 2099 cannot replace publication zero or
the discovered year list. Both differential cases passed. This proves the observed
cancelled bootstrap pair is development replay, not an unbounded request loop;
it is not a production-server acceptance claim.

Reproduction file:
`D:/Projects/finlens-annual-bootstrap-diagnosis-0aebcc300b594fc9a8187688d6f738ca.cjs`,
SHA256 `D15E29573AAE27A98440CD1EB1F3EAE5DEC9C94BB173D1CE963C60C83AF12897`.
Its first run exposed a test-loader path-normalization mismatch; normalizing module
cache paths fixed that harness issue before the successful differential run.

### Bounded correction and cleanup evidence

Only the new browser spec/local fixture and this plan change in the repository.
No product, finalized-nine, dependency, backend or repository launcher edit.
The local fixture now observes request/requestfinished/requestfailed identities,
asserts every started request has an exact completed/cancelled/pending disposition,
HTTP status and returned pin, and refuses unledgered requests. It verifies the old
replay request precedes its completed replacement. It does not ignore cancellations
or merely raise a total. Held user requests must transition pending→cancelled;
unexpected failures fail. A version-mismatch case explicitly completes one verified
old-pin column before delivering its peer's 409, then verifies the whole grid is
hidden and the real freshness provider establishes the new pin.

Expected full-case lifecycle totals, still pending browser execution:

| Case | Started | Completed | Cancelled |
| --- | --- | --- | --- |
| Desktop grid/keyboard | 16 | 14 | 2 bootstrap replay |
| Desktop cancel/scope/version | 40 | 29 | 6 mount-replay + 4 user-cancel + 1 new-pin annual replay |
| Mobile touch/keyboard/scroll | 16 | 14 | 2 bootstrap replay |

Cleanup diagnosis is separate. The receipt has zero birth records and explicit
MISSING_NEXT_ENTRY/MISSING_NEXT_CHILD_BIRTH. The existing observer starts only as
an `internal/preload` module; the frozen launcher never supplied --require or
NODE_OPTIONS, and sanitizes its child environment. Requiring that file merely to
read its exported attestation functions does not install it in Next. This explains
the missing proof. PID 174's recorded command is MainThread, with no attested role;
it **cannot be retrospectively identified as telemetry**. No such identity is
asserted and no historical record is changed.

The fresh snapshot alone adds an explicit run-owned NODE_OPTIONS --require for the
already-pinned observer to the existing isolated launcher. A Linux run-root guard
rejects other paths; inherited host NODE_OPTIONS is not forwarded. Actual Next's
child-launch source preserves parsed node options. The observer, identity policy,
image-code attestation, quiescence assertions, owned telemetry join, limits and
cleanup code remain unchanged. This activates the existing proof mechanism; no
new diagnostic framework or identity exemption is introduced. Actual Linux preload
and future cleanup success remain unverified until a separately approved run.

### Current prepared correction pins and checks

Fresh snapshot:
`D:/Projects/finlens-annual-period-browser-0aebcc300b594fc9a8187688d6f738ca`.
Fifty source files, 1,660,271 bytes; source aggregate SHA256
`A24ED31FE8A2D680DA9CFBA5FA4AD83E3D361066F69DEF450CBFB85FDC795C99`.
Exactly three source inputs differ from the failed snapshot: spec, local fixture,
and snapshot-only launcher. The repository launcher remains unchanged.

| Current correction path | SHA256 |
| --- | --- |
| frontend/e2e/annual-period-comparison.spec.ts | B050E90A917F9377A975FB96A47CB540B940105FD9D093BE14F5FAFC8E53E2AC |
| frontend/e2e/fixtures/annual-period-browser.ts | 441B65B11104FA2E187997FEC8B59722D635CCEFBAB33DE7C04A3B9545B00239 |
| external snapshot/frontend/scripts/e2e-server.mjs | 6E0561BBEE3A5C1EF932A3AEE15DE085043AF913527806FFEDF6C84B87449300 |
| external snapshot/acceptance-proposal.ps1 | FD7B91C706EB667738E1AE966D60FE26B938B4889A1ED4D30C16BBB08DB5E6A6 |
| external snapshot/annual-period-offline-checks.cjs | 569B24F39F2E2541D13BBB18040F14B3B10E6D84C277915710C578545EB1218A |

Actual checks, no approval or runtime escalation:

- The actual provider/grid StrictMode differential and stale-generation reproduction
  above passed (two cases); no browser or service.
- `node <fresh-snapshot>/annual-period-offline-checks.cjs --lifecycle-only`:
  four focused checks passed. The actual fixture callback and lifecycle assertions
  run against a bounded EventEmitter/Request double; missing cancellation, stale
  pin and unexpected failure mutants reject. Snapshot launcher code executes only
  with a stubbed spawn to verify the exact preload/options and unowned-path refusal.
  Reversing only nonce/source-pin substitutions recovers the complete prior runtime
  proposal, including unchanged cleanup. No process is spawned by these checks.
- From frontend: scoped spec/fixture ESLint and `tsc --noEmit --incremental false
  --pretty false` passed, exit 0. No build or generated-file writes.
- Exact selectors in the new snapshot discovered desktop two / mobile one, exit 0;
  separate JSON reports at
  `D:/Projects/finlens-annual-period-preflight-0aebcc300b594fc9a8187688d6f738ca/{desktop,mobile}-discovery.json`.
  These are discovery only, not browser test passes. Same three titles/projects,
  config, grep, workers/retries/max-failures/reporters as prior; --list appended.
- New proposal parses in PowerShell. Failed bundle/evidence and all other candidate/
  protected hashes remain unchanged; HEAD/index are unchanged. No broader suite,
  browser/container, network, database, install, Git write, security change, .env
  access, self-review or review dispatch occurred during this correction.

Finalize the new manifest after this factual record is frozen. Its final hash and
exact proposed command will be supplied for coordinator-controlled Astra review.
No browser retry is authorized or performed in this correction turn. Historical
PID identity and runtime preload/cleanup acceptance remain explicit open gates.

## Authorized minimal focus/readiness repair — 2026-10-31

After read-only diagnosis `01a19135-818e-7e33-a5fa-a16b902511db`, coordinator
authorizes only new browser spec/test-local support, this plan and a new external
runner copy. No product edits, browser run or historical overwrite. The prior
corrected attempt failed the outline-versus-own-fill proxy, and inner cleanup
rejected the still-incomplete authenticated helper before reaching its grace wait.
The retained screenshot shows a spaced visible outline; numeric computed colors
and rectangles were not retained, so the new test records them before assertions.

Focus repair samples the actual adjacent background under all four outline edges,
composites supported color layers, requires at least 3:1 contrast and retains exact
viewport/scroller containment, native Tab and a visible nonzero outline. Unknown
images/compositing/shadow paint fails closed; shadows are not substituted for the
required outline. No geometry tolerance or full-table-in-viewport requirement.

Readiness repair will remain within the original single absolute two-second join
budget, authenticate the sole pending helper against phase/parent/birth/code
identity before any reread wait, retain full completion verification before success,
and retain whole-container quiescence. No new grace, signals or process exemption.
Prepare fresh snapshot
`D:/Projects/finlens-annual-period-browser-fd097bc4e35541d2ac6b8b3d912ecf20`;
focused offline cases and final pins follow. Stop for independent review, no run.

### Actual minimal repair and offline results

The second historical run `1ae2d962ba4c4609a2abfc0ed5282d6e` remains FAILED:
bootstrap lifecycle passed (10 started, 8 completed, 2 cancelled, zero unledgered/
violations); the desktop focus-color predicate failed before Compare activation;
desktop second case and mobile did not run. Birth records authenticate helper
175/9909985, but its completion was missing and the join made zero polls before
OWNERSHIP_UNVERIFIED. Outer container removal was verified; inner cleanup was not.
Receipt/index and screenshots remain unchanged. Historical 174/9748309 remains
unidentified. No historical completion record or acceptance claim is synthesized.

Repository delta for this repair is only the new spec, its test-local fixture and
this plan. Production components/helpers/CSS, prior nine, blocked export plan,
repository launcher, backend, dependencies, HEAD and index are unchanged.

The actual serialized capture helper reads focus state, outline style/width/offset,
raw outline/fill colors, shadow/filter/opacity, rectangles, clipping bounds and four
outline-edge sample positions. It resolves adjacent background layers at those
positions and composites supported sRGB/alpha colors. A minimum 3:1 contrast is
required at all four edges. Unresolved images, compositing or target shadow/ring
paint fails closed; it is not accepted as an alternative focus indicator. Every
focus check attaches bounded JSON diagnostics (64 KiB maximum) before asserting,
including failure cases. Focus, nonzero outline, native Tab and strict original
viewport/scroller inequalities remain; no tolerance, style/focus/scroll injection,
or requirement to squeeze an entire wide table into the viewport was added.

The external join now accepts a fresh-read callback, starting its existing absolute
2000ms deadline before reading. The pending state is accepted for waiting only
after verifying nonce, immutable phase prefix, completed Next owner/server chain,
exact sole helper birth/entry, image code hash, PID/starttime/group/session and
parentage. `readinessVerified` never sets full `verified` or phase verification.
Missing/malformed/changed provenance fails immediately. Readiness rereads and live
helper inspection share the original deadline and combined 81-poll cap. Full
observer completion and the original ownedProofs checks remain mandatory before
success, followed by unchanged whole-container quiescence. No second grace,
signals, name matching or live-process exemption exists.

Fresh snapshot has **50 source files / 1,669,216 bytes**, aggregate SHA256
`8D07ACDD1178AF68150C0C3CD216B789F43DB9059900D0280B724DFAF877FA2D`.
Three source files differ from the immutable parent: spec, test-local fixture and
external-only settle-next-telemetry.cjs. Four explicitly pinned support files plus
proposal/manifest make 56 snapshot files. Existing preload, image, mobile config,
case titles/selectors, no-egress/resources/deadlines and outer owned cleanup remain.

| Current minimal-repair path | SHA256 |
| --- | --- |
| frontend/e2e/annual-period-comparison.spec.ts | D01BD608A5E0051CFFA05CFEAAF76358D9EE3459D28C24C15AEE1E97A8AFE5CC |
| frontend/e2e/fixtures/annual-period-browser.ts | 07A9935D57AFE458EA94943503DED47D91F743126CCF12BB5515B22186B22E88 |
| external snapshot/frontend/scripts/settle-next-telemetry.cjs | AA1B7F8181A3ED6B41BBC3A70A9DB1941A9778A34A2A7EBBF81E185CF494D3C5 |
| external snapshot/acceptance-proposal.ps1 | 13156313E992500FE34272B11AEBB429F45872773CF391ED984111A475474E19 |
| external snapshot/annual-focus-ready-checks.cjs | 74D7439A0BE449084DB946DB9AFBE5EB00E2BD8730D4DF25A02002E2CB0FACC7 |

Actual validation (2026-10-31), no approval required:

- `node D:/Projects/finlens-annual-period-browser-fd097bc4e35541d2ac6b8b3d912ecf20/annual-focus-ready-checks.cjs --focus-ready-only`:
  **23 focused checks passed** on final support bytes. Nine focus checks exercise
  the actual color/capture/assertion helpers with controlled DOM/style inputs:
  same-fill spaced outline, light/dark/alpha layers, invalid/low contrast,
  transparent/unresolved/image/mixed surfaces, retained diagnostics, no/zero
  outline, unknown shadow, every viewport edge and exact scroller edges (including
  0.01px violations). Native Tab and narrow touch/containment code are unchanged.
  Fourteen readiness/runner checks exercise actual provenance/phase/ownership/join
  helpers using in-memory file reads, actual retained birth rows, synthetic
  completion rows and fake clocks. They cover authenticated-but-not-complete
  refusal; delayed completion; 1999ms success; 2000ms/2001ms failure; missing
  completion; one shared readiness/live-inspection budget; bad code/birth/entry/
  owner/phase/attestation; missing helper entry; prefix mutation; PID reuse; and
  unchanged whole-container cleanup. Synthetic completion rows are never written
  into historical evidence. The entire prior runner is recovered by reversing
  only the declared source/nonce/support pins and fresh-read call-site change
  (line endings normalized). No actual process launch or /proc read occurs.
- From frontend: `node node_modules/eslint/bin/eslint.js
  e2e/annual-period-comparison.spec.ts e2e/fixtures/annual-period-browser.ts`: exit 0.
  `node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false`:
  exit 0. No build/generated-file writes.
- Exact final discovery under the new snapshot and unchanged external config:
  desktop **2**, mobile **1**, both exit 0. Installed CLI, file/project/config/grep,
  workers=1, retries=0, max-failures=1 and list,json reporter match the planned
  phases; only --list is appended. JSON files in
  `D:/Projects/finlens-annual-period-preflight-fd097bc4e35541d2ac6b8b3d912ecf20`
  are discovery evidence, not executed browser results.
- Proposal parses as PowerShell; its embedded Node program parses in the focused
  runner check. Parent snapshot, both indexed historical failed exports, protected
  working candidates, HEAD and empty index remain unchanged. `git diff --check`
  passes with existing line-ending notices only.

An initial 22-check pass preceded the additional exact scroller regression; final
23-check validation includes it and the full declared-runner-delta assertion.
No earlier broad/component/QA/support suite was rerun. No browser/container retry,
network, database, install, Git write, security change, .env access, self-review or
dispatch occurred. Actual paint/geometry, Linux completion timing, mobile behavior
and operational cleanup remain pending browser acceptance; offline checks do not
promote those gates.

Finalize the successor manifest once this plan is frozen and return its exact
hash/command for focused Astra review only. Suggested eventual commit:
`test: verify painted focus and bounded telemetry readiness`.

## Authorized response-header / terminal-state correction — 2026-10-31

Coordinator authorizes only the new annual spec, its local fixture/support, this
4b plan and a separately pinned external successor snapshot. No production code,
prior nine, blocked export plan, historical evidence, dependency, Git, .env,
network, database, security, browser or Docker action is authorized in this stage.

The third attempt `8066b1afbc1a45ad8e07c614d2451aad` remains FAILED: first desktop
grid/keyboard case and all nine focus checks passed; second desktop case failed
at BBB insights lifecycle accounting; mobile did not start. Inner cleanup, outer
container removal and preservation passed. Its retained trace contains one BBB
insights request (ledger ID 20): HTTP 503/version 0/code
QA01_INSIGHTS_PUBLICATION_UNAVAILABLE headers and terminal net::ERR_ABORTED.
BBB selection starts at trace time 11777.260ms, fulfillment at 11907.638ms,
and the explicit unavailable/retry UI assertion completes at 11918.308ms. No
switch back to AAA occurred. It is not a company-switch or replay cancellation.

Existing transport cancels a non-success body and aborts transport on disposal;
the old recorder saved headers only on requestfinished, losing headers on failed
requests. An actual-code in-memory probe during read-only diagnosis passed:
response 503 -> body cancelled -> internal transport aborted -> worker terminated;
caller signal remained un-aborted, owner current, exact error code/status retained
and zero timers remained. This is offline evidence, not a new browser run. The
trace does not distinguish which cleanup call triggered Chromium's terminal abort.

Implementation plan: observe response headers independently on the exact Request
object; preserve terminal pending/completed/cancelled/failed state independently.
Require exact 503/version 0/error code AND terminal net::ERR_ABORTED for BBB0,
and the corresponding known unsupported AAA1 insights publication after repin.
Keep true pre-header cancellation distinct, preserve full-page counts, ordered
replay generations, stale-column/version assertions and unavailable/retry UI.
Duplicate, unknown, out-of-order and misassociated events must fail closed.
Run deterministic actual-recorder regressions with in-memory event objects,
targeted lint/type checks and static selector/proposal checks only. Then freeze
the successor for independent Astra review; no self-dispatch or runtime retry.

### Actual recorder correction and focused results

Repository delta in this stage is exactly the new annual spec, its local fixture
and this existing plan. The recorder now captures the exact Request object's
`response` event into a separate status/version/code receipt. Only requestfinished
marks a body completed; requestfailed retains any earlier receipt and the exact
failure. Unknown, duplicate, late, conflicting, missing-header completion and
URL-misassociated events create violations instead of replacing earlier evidence.
Pre-header cancellations require no receipt. Header cancellations require the
exact expected receipt AND terminal `net::ERR_ABORTED`; neither a bare abort nor
a completed 503 is accepted. Error text matching is exact, not substring-based.
The explicit BBB unavailable/retry UI, whole-page ledger, replay generations,
cancelled selected-year requests and stale-column/publication guards remain.
The same known unsupported AAA1 fixture after repin is asserted as 503/version 1/
QA01_INSIGHTS_PUBLICATION_UNAVAILABLE plus terminal cancellation; this later
browser path remains unexecuted, and offline coverage is not runtime acceptance.

Fresh external root:
`D:/Projects/finlens-annual-period-browser-18f48e0e0f25435988b0b5bc551e33b0`.
Only the spec and local fixture differ among the 50 source entries from parent
fd097bc4e35541d2ac6b8b3d912ecf20. Source inventory: **50 files / 1,671,185 bytes**;
aggregate SHA256
`EF802B8418C2818E2ABE7FE4F81690B79522448F78A2F3ED4E1D437304EF325F`.
Four support files plus proposal/manifest remain 56 explicit snapshot files. The
existing focused support gains only a `--headers-only` branch; its earlier flags
are retained as historical support and were not rerun or claimed in this stage.

| Corrected path | SHA256 |
| --- | --- |
| frontend/e2e/annual-period-comparison.spec.ts | 9E69D383DE9C75529B6A14330D8F42A9DD842B2103EBEA23CA51C6B4C2C2EB30 |
| frontend/e2e/fixtures/annual-period-browser.ts | 2E1036352A1BC8E7AF85FF2D72B7D7C5EDCCC8797F125FBE43F7FDA5BA617769 |
| external snapshot/annual-focus-ready-checks.cjs | D850314078F4A0667A5E5A41827177B22FB6832B490023F12296BFD9033BA6CF |
| external snapshot/acceptance-proposal.ps1 | 44FFC795691F26444E766F7B31C161943C2F9A94340F4EE232437FCB606F8FAA |

Actual checks, no approval required:

- From frontend, `node D:/Projects/finlens-annual-period-browser-18f48e0e0f25435988b0b5bc551e33b0/annual-focus-ready-checks.cjs --headers-only`:
  **28 passed**, exit 0. Executes the actual fixture setup/listeners/assertions
  with an in-memory EventEmitter and request/response objects; no browser or
  network. Covers headers->abort without full-body completion, normal completion,
  pre-header cancellation, wrong/missing status/version/error code, completed 503
  rejection, arbitrary failure rejection, duplicate request/response/finish/failure,
  conflicting and late events, finish before headers, unknown exact identity,
  response URL mismatch, missing/duplicate ledger records, exact bootstrap
  10/8/2 counts and replay order, BBB0/AAA1 header cancellations and stale 409/pin
  rejection. Also proves actual request admission/interception/focus functions
  equal the immutable parent and recovers the entire parent runtime proposal by
  reversing only new nonce/source-aggregate/byte-count pins; embedded Node parses.
- `node node_modules/eslint/bin/eslint.js e2e/annual-period-comparison.spec.ts
  e2e/fixtures/annual-period-browser.ts`: exit 0, no diagnostics.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false`:
  exit 0, no diagnostics; no generated/build output.
- Proposal parses as PowerShell. Exact prior installed Playwright CLI/config/
  file/project/grep/worker/retry/max-failure/reporter arguments with `--list`:
  desktop **2**, mobile **1**, both exit 0. Discovery JSON is in
  `D:/Projects/finlens-annual-period-preflight-18f48e0e0f25435988b0b5bc551e33b0`;
  it is discovery only, not executed browser results.
- `git diff --check`: exit 0, existing LF/CRLF notices only. Protected working
  candidates and parent source/support hashes were checked by the preparation
  script before copying. Final source/inventory, historical evidence and Git
  preservation verification accompanies manifest finalization.

All production code, original protected paths, external ownership/telemetry join,
observer preload, image, mobile config, runtime resources/deadlines and owned
cleanup remain unchanged. No browser/Docker/network/database/.env/install/security,
Git write, approval escalation, duplicate retry or review dispatch occurred.
Three prior failed attempts remain failed and immutable. Completion remains
blocked on independent review and separately authorized runtime acceptance.
Freeze this plan into the successor manifest and report the exact manifest hash
and invocation for focused independent Astra review only. Suggested eventual
commit: `test: distinguish response headers from terminal cancellation`.

## Final accepted execution and manual delivery closure — 2026-10-31

This factual append supersedes the earlier pending-review/execution statements
for this bounded synthetic annual-grid slice only. It does not complete all of
requirement 4b or alter historical outcomes. Coordinator confirmed independent
Astra recorder review PASS in turn `01a1916b-7567-7aa2-940b-6e89e5989acf`, after
the earlier product review `01a190f3-b15f-7ee2-8db7-2c225ffe20b8` and focused
acceptance corrections. Actual authorized execution is turn
`01a1916d-63f2-7b70-a437-b63770d32ebb`.

Executed exactly once from `D:/Projects/finlens-foundation`:

```powershell
pwsh -NoLogo -NoProfile -NonInteractive -File 'D:\Projects\finlens-annual-period-browser-18f48e0e0f25435988b0b5bc551e33b0\acceptance-proposal.ps1' -ExpectedManifestSha256 'EFC658DB4264D046A4942B40D3FFAD67D9D2D25727570C78664EA5ACE1CC9AAE' -AcceptOptionalDependencyRisk
```

Preflight verified exact manifest/source/support/proposal bytes, all previous-nine
and protected working hashes, HEAD/main, unchanged empty index, exact 20-path
worktree status and desktop2/mobile1 discovery. Supported chat status showed no
other active local FinLens writer. Docker elevation was explicitly requested and
approved for this exact command. Terminal exit was 0; final outcome **PASS**.
There was one create and one foreground attach, with no workload retry or fix.

| Actual case | Result | Completed / cancelled / unledgered |
| --- | --- | --- |
| Desktop two/four years, shared sources and native keyboard | passed, retry 0 | 14 / 2 / 0 |
| Desktop cancel, company scope and actual publication invalidation | passed, retry 0 | 27 / 13 / 0 |
| 390px touch, four-year missing data and horizontal scroll | passed, retry 0 | 14 / 2 / 0 |

Desktop report: 2 passed, zero failed/skipped/flaky, 12,351.166 ms. Mobile report:
1 passed, zero failed/skipped/flaky, 8,676.847 ms. All ledgers had zero violations.
BBB0 request 20 retained exact HTTP 503/version 0 and
QA01_INSIGHTS_PUBLICATION_UNAVAILABLE headers followed by net::ERR_ABORTED.
Repinned AAA1 request 40 retained the same exact status/code with version 1 and
terminal net::ERR_ABORTED. Neither is represented as completed body delivery.
The cancellation/scope/stale-column assertions passed through the full second
case. Nine desktop and two mobile focus diagnostics passed all 44 edge samples;
minimum recorded contrast was 4.922782915430799:1, with strict containment intact.

Run nonce: `a8e3e7aa73d14844bf9e3417efd0c1fd`.
Owned container: `4ca288d44e0cd1a477465d193febb1a844d34f3a10610ba31d9da4181147cac2`.
Artifact root:
`D:/Projects/finlens-annual-browser-artifacts-a8e3e7aa73d14844bf9e3417efd0c1fd`.
All six final gates passed: testEvidence, artifacts, containerAbsent, preservation,
proposalPreserved and hostClisReaped. Both phase cleanups and final cleanup were
verified: ports 3107/3108 closed, zero extra live processes and QA temporary copies,
stage dependency link and owned runtime root removed. Both authenticated helpers
were observed absent without signals; joins took about 52.608 ms and 51.946 ms.
All ten host CLIs were reaped. Final exact-container-ID/name listings were empty.

The receipt-bound export contains **27 files / 387,680 bytes**. Every indexed
size/hash and export accounting was verified after execution. Key raw SHA-256:

| Artifact | SHA-256 |
| --- | --- |
| overall-result.json | 1F6558954916EB3F681108C6E5BF0CCC19E6F86D13B35C933A15FEAEECACF963 |
| artifact-index.json | 4703A05B937A9A90690B20ED3C51AD797BA9DA7B63F7B07BAEA3D2D296D64A5A |
| receipt.json | 60426F25B4D2DE474FC556E9F73717EB17CE3B5C70EB48268888B20C41C2D0E3 |

Historical attempts `9f23189b20854f4eb59dbf0b1afdbce3`,
`1ae2d962ba4c4609a2abfc0ed5282d6e` and
`8066b1afbc1a45ad8e07c614d2451aad` remain **FAILED**. Their indexed exports and
outcomes were checked and retained; the later PASS does not rewrite any failure,
prove a past unidentified PID's ownership or synthesize missing historical records.

Acceptance is synthetic Linux Chromium against intercepted fixture responses,
including a 390px touch-emulated viewport. It is not current real-DB/API/SEC/provider
acceptance, native Windows Chromium, a physical-device/full accessibility audit,
full 4b/D6 completion or deployment acceptance. The product grid is connected in
Home under the existing selected-company ResearchFreshness provider and uses the
existing annual API; no new backend financial engine or dormant contract is being
claimed as an end-to-end feature. The six optional WASM dependencies remain
UNVERIFIED_OPTIONAL_DEPENDENCIES; the explicit risk switch applied to this one
attempt only, with no package installation or general dependency acceptance.

The fixed local image/no-egress/no-pull/no-published-port policy, resource caps,
deadlines and identity-owned cleanup were unchanged. No database, .env, provider,
source acquisition, install, security-policy or Git write occurred. No repository
file changed during execution; all candidate/protected hashes, HEAD/main at
`d6a9e42ce8571bec5450b06fed97d829d6b1272f`, empty index and exact status were preserved.

This separately authorized closure appends only this existing plan. Its accepted
pre-closure raw SHA-256 was
`1497F8B357A748A200F2562352D6676187D668FA18BADCBFDF7017C00ADC5922`.
The immutable reviewed manifest and run evidence continue to bind those earlier
plan bytes; they are not repinned or rewritten after acceptance. Closure performs
no tests, discovery, browser, services or support reruns. Manual delivery remains
three batches in order: four prior QA files; five coverage-filter files; seven
annual-grid files including this plan. Exclude the three protected exceptions,
separate blocked Markdown-export plan and all external snapshots/run artifacts.
No staging, commit or push was performed. Suggested third-batch commit:
`feat: compare selected company annual periods`.

## Native existing-data acceptance and doc-only closure — 2026-10-31

This separately authorized factual append records actual native execution turn
`01a191c2-c232-7192-9d77-36ad89265ecb`. It extends the accepted synthetic boundary
above with one bounded existing-data Windows/Chrome journey. Earlier pending
native-runtime statements are superseded only for the cases recorded here;
requirement 4b and D6 are not declared complete. No earlier text is rewritten.

Independent Astra diagnostic-successor review PASS is recorded in turn
`01a191bf-c3a8-7332-8c18-a13977b25d26`, following the original operator-assisted
composition review `01a19193-3f91-71c0-bd81-b54ac2c41bb3`. Those were preparation
reviews, not executions. The separately authorized successor launch ran exactly
once from `D:/Projects/finlens-foundation`, returned exit 0, and reached
`ready-for-separately-controlled-browser`; no launch retry or product repair ran:

```powershell
pwsh -NoLogo -NoProfile -File 'D:\Projects\finlens-native-annual-a979060ed7104eeea8c1ddc8ccf0fc17\compose.ps1' -Mode Launch -OperatorPresent -ExpectedManifestSha256 '21CC81C9AC80C37DCE35350A1E0632B153BF3BD1E5A3C525BF35FA8A04E103BC'
```

Actual outcome: **PASS_BOUNDED_EXISTING_DATA_ANNUAL_JOURNEY**. Eight direct loopback
stored-only freshness/discovery/annual requests verified AAPL publication pin 1
and JPM pin 0, including matching returned version headers. Zero remains a valid
pin. Both issuers currently discovered FY2024/FY2025 in that observation. Six raw
financial responses (two discoveries and four exact-year results) are retained.
Native Chrome then exercised AAPL FY2024/FY2025, JPM FY2024/FY2025 and return to AAPL.

- All eleven rows per issuer were inspected: **44 cells** matched exact available
  API values in DOM details or exact unavailable/not-applicable reasons. Rounded
  display, actual dates, units and economic-basis labels were observed separately.
- **24 source fact-ID checks** matched UI lineage; the stored-response inspection
  verified 24 source identity/canonical-link tuples and **8 operand/source tuples**.
  These are lineage checks, not independent SEC authenticity or completeness proof.
- AAPL retained its customer-contract revenue basis and unavailable margin reasons.
  JPM retained incompatible revenue scopes, gross-profit/margin not-applicable
  states, missing cash-flow inputs and negative operating cash flow. No missing
  metric was replaced by a different period or fabricated value.
- Native keyboard Enter opened AAPL FY2025 revenue and JPM FY2025 operating-cash-flow
  sources. Space opened AAPL FY2025 revenue-YoY operand periods/bases and JPM FY2024
  operating-cash-flow sources at the temporary 390x844 viewport. Focus/open state
  and source fact/period context were observed.
- At 390px, document width was 375px; the focused table region had client width
  307px and scroll width 640px. ArrowRight changed scrollLeft from 0 to 120px.
  On return to AAPL, pin 1 was visible with zero selected years and no old table.
  The viewport override was reset (1281px observed) and the created Chrome tab closed.

The original terminals were `FinLens Native Annual a97906 BACKEND` (PID 41268,
creation `2026-10-31T11:41:19.7556010Z`) and `a97906 FRONTEND` (PID 18844,
creation `2026-10-31T11:41:23.4288820Z`). After the user confirmed Ctrl+C and closure
of both original terminals, this reviewed read-only command ran once:

```powershell
pwsh -NoLogo -NoProfile -File 'D:\Projects\finlens-native-annual-a979060ed7104eeea8c1ddc8ccf0fc17\compose.ps1' -Mode CheckStopped -ExpectedManifestSha256 '21CC81C9AC80C37DCE35350A1E0632B153BF3BD1E5A3C525BF35FA8A04E103BC'
```

Its observation from `2026-10-31T11:47:33.7722938Z` through
`11:47:36.1422355Z` (19:47 Asia/Macau) found no listeners on 8021/3003 and neither
original terminal identity present, with creationUncertain false.
**completeDescendantCleanupVerified remains false.** No forced termination,
database stop or filesystem deletion was performed. These are past, non-atomic
listener/original-terminal observations, not present liveness or process-tree proof.

Evidence root:
`D:/Projects/finlens-native-annual-results-a979060ed7104eeea8c1ddc8ccf0fc17`.
The [result](../../../../finlens-native-annual-results-a979060ed7104eeea8c1ddc8ccf0fc17/acceptance-result.json),
[index](../../../../finlens-native-annual-results-a979060ed7104eeea8c1ddc8ccf0fc17/artifact-index.json)
and [cleanup observation](../../../../finlens-native-annual-results-a979060ed7104eeea8c1ddc8ccf0fc17/cleanup-observation.json)
retain **12 indexed payload files / 75,461 bytes**, plus the self-excluded index
(13 files total). All indexed sizes/hashes were verified during execution closure
and reread for this documentation append. Two JPEG screenshots were displayed in
the native browser tool output; they were not exported as local evidence files,
and no full DOM snapshot was retained. Do not invent screenshot-file hashes.

| Artifact | Raw SHA-256 |
| --- | --- |
| acceptance-result.json | 47131110F95E899622D7B3E704BDC1B9C5BD3A9DF8CE1BDDD0FAA63F03C62198 |
| artifact-index.json | 6858DFD44D5494D9CCD7D82A0CF7A600A628AD8BA04C8081512DD09C23BC7124 |
| cleanup-observation.json | CD1597DFE2F27678AEC15C0DC1F36AD8FFA6720BFB0206BB6DDBF4478EBE457D |

The first extra offline operand inspection rejected valid stored tuples because
its PowerShell local used the automatic variable `input` inside Where-Object.
Renaming that local to `operand` and rechecking the same stored responses passed;
this correction and the earlier pending-cleanup snapshot remain disclosed in
preservation-and-provenance.json. No service, HTTP or browser case was repeated.

The original native bundle
`D:/Projects/finlens-native-annual-384105c0177e435c90fd3b973fbb0365` remains **FAILED**
(original execution turn `01a19196-97e4-78a1-9e2e-df17e1475587`). Its exact failed
frontend probe/cause was not recoverable; the later success establishes no
NODE_PATH root cause. Parent prepared files and failed session were preserved.
The three historical failed synthetic attempts named above remain **FAILED**;
the later synthetic/native passes neither rewrite nor retroactively repair them.

This acceptance used existing stored data, read-only application endpoints and
normal private backend configuration without inspecting/copying/hashing/printing
it. It made no acquisition/provider/SEC request, database provisioning/migration
or installation. No external source link was navigated. It does not establish
fresh SEC data, complete coverage, physical touch, full accessibility, deployment,
full 4b/D6, OS-enforced no-egress/resource limits or complete descendant cleanup.
Native operating bounds remain different from the isolated synthetic container.

This doc-only closure performs no tests, discovery, runtime checks, new review
cycle, browser/service/DB work or Git writes. Before append, all 47 public repository
pins, empty index, HEAD and exact 20-path status matched. The accepted native
manifest continues to bind this plan's pre-append bytes, SHA-256
`4B0DB0B014375F9FF87CAB76DE7DF29F9392443A8213B8E0AE893A77A6FCA0CC`.
The older synthetic manifest still binds its earlier plan bytes as recorded above.
Neither immutable manifest nor any evidence file is repinned or rewritten here.
The final appended-plan hash belongs in the manual handoff, not in either manifest.

Manual delivery remains three batches in dependency order: (1) four prior QA files,
(2) five coverage-filter files, (3) seven annual-grid files including this appended
plan. Preserve the exact path groups recorded above; batch 2 depends on batch 1's
opt-in fixture constructors. Exclude the three protected exceptions, blocked
Markdown-export plan and all external snapshots/results. Read-only Step 1 checks
HEAD/main, empty unchanged index, exact status, current per-file hashes/diffstat
and this append's preserved byte prefix. It stages, commits and pushes nothing.
Suggested later manual commit subjects remain `test: strengthen annual comparison
browser coverage`, `feat: add annual comparison coverage filter`, then
`feat: compare selected company annual periods`.

One next proposed canonical product milestone is a bounded **4c/D6 Comparability
Inspector**, under Research Mode/Phase 3: let users inspect two selected annual
columns' actual windows, currency/economic basis, unavailable/excluded reasons and
source/operand context together. [Requirement 4c and D6](../../full-feature-requirements.md)
still require an integrated inspector beyond current warnings. The present AAPL/JPM
journey supplies bounded available/incompatible/not-applicable examples; it does
not cover the full industry/EPS/quarterly/as-of matrix or complete those rows.
Define that scope and its negative-case acceptance before implementation; do not
invent formula, source-rights/export, acquisition or vintage permissions. This is
only a handoff recommendation: no next-milestone work is started by this closure.
