# Dual-filing evidence comparison

Status: active; implementation candidate, independent review and browser acceptance pending.
Roadmap phase: bounded enabling slice of requirement 5b, not completion of multi-document synthesis.

## Objective
Select two distinct indexed filings for the current company, explicitly ask one question, and read original passages side by side with dates and official SEC sources. Exactly two filing-context requests per accepted submit, five passages per side maximum; no generated conclusions.

## Current architecture and context
Baseline main ad4afc9f017a2c060acd281ca745fd0e213352b1. FilingResearch owns a version-scoped indexed filing list. Existing getFilingContext supports required publication response headers via versionedController, including zero. Existing sec-risk validator checks bounded SOURCE serialization/metadata and canonical SEC URLs. Context route is already in READONLY_ROUTES and uses read_session, require_published and build_filing_context. No route/policy change needed. Canonical requirements: full-feature-requirements.md row 5b and shared-research-contracts.md; those broader target contracts remain drafts. No repository .agents/skills directory was found.

Starting changes preserved: frontend/next-env.d.ts; backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json; backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json; docs/exec-plans/active/2026-10-31-annual-comparison-markdown-export.md.

## Constraints
Frontend-only; no services, DB/provider/network/model calls, private env reads, installation, security settings, Git writes or deployment. Initial restricted-token sandbox construction failed before execution; supported require_escalated review subsequently granted inspection. Every shell operation uses supported review. No destructive filesystem operations; no drive/directory clearing. Browser prepared only, not launched before independent review.

## Non-goals
Synthesis, causal/change/amendment inference, financial calculations, acquisition, accounts, exports, persistence and backend changes. Synthetic checks do not establish real-source retrieval acceptance or encoder availability.

## Implementation stages
1. Confirm contracts and create plan.
2. Add bounded inventory/response validation and mounted comparison UI, reusing the existing context transport and source parser.
3. Add focused mounted/negative lifecycle tests and browser fixtures/spec/config, preserving shared helpers.
4. Run focused/regression tests, TypeScript, lint and whitespace; record hashes for review. Browser launch remains pending review.
Recovery: revert only the task-owned additions/edits if rejected; preserve pre-existing changes.

## Decisions
2026-11-01: Reuse separate filing-context calls, not company-wide ranking. Publication pin is enforced by existing request and response headers; filing context has no body pin field. Reuse validateRiskEvidence for source consistency, adding selected filing metadata/name checks. All source text remains original. Reference display identities include accession and citation ID.
Bounds: 100 indexed choices; reject invalid/duplicate/oversized inventory, never truncate it. Query 1-2000 UTF-16 units after trimming; selected metadata bounded. Each response uses existing 24,000-context / five-citation / 3,000-code-point passage limits; reject integrity failures rather than truncate. DOM at most ten passages and two filing columns.

## Discovered issues
Initial sandbox failed before execution; supported approval path now works. rg unavailable; PowerShell targeted file reads used. No backend or operational changes are authorized by this slice.

## Progress
- [x] Repository/contracts/route inspection.
- [x] Implementation.
- [x] Mounted/regression/static checks executed; existing baseline failures documented below.
- [x] Browser preparation and source self-review; execution deferred until independent review.
- [ ] Independent review and subsequent browser acceptance (outside current execution boundary).

## Test and validation strategy
Use local installed Node/TypeScript/JSDOM, synthetic fetch only. Cover pins zero/nonzero, same-tick repeated submit, empty/error isolation, source integrity negatives, edits/cancel/unmount/late delivery, publication changes, source disclosure request counts and bounded inventory. Run relevant existing filing/risk/QA tests, tsc --noEmit --incremental false, npm run lint, git diff --check. Prepare browser checks with shared lifecycle/focus helpers without launching servers/browser. Record actual commands/results below.

## Completion criteria
Review-ready frontend candidate with focused/regression/static checks passing; honest disabled/empty/error states; no unauthorized backend/operational mutation. Independent review and browser/real-data acceptance remain explicit pending gates.

## Final outcome
Pending.

## Actual verification and review handoff — 2026-11-01

All commands ran from frontend unless stated otherwise, with installed local dependencies and supported require_escalated approval. No user approval button remains pending. No browser/server, live DB, model, provider/network, installation, private configuration or Git write occurred. Python serializer regression uses its existing explicit DB/network/private-env denial guards; no production data acceptance follows.

- `node --test tests/dual-filing-evidence.test.mjs`: final **42 passed, zero failed**. Includes real mounted component/StrictMode, pins 0/7, exact pair and duplicate-submit reservation, literal Unicode/markup/source wording, namespaced identities, empty/error/timeout isolation, cancellation/unmount and ignored-abort late responses, same-tick question round trip, source metadata/serialization/bounds, sibling invalidation on header disagreement, actual FilingResearch inventory integration and browser fixture/request validation.
- `node --test --test-reporter=tap tests/dual-filing-evidence.test.mjs tests/evidence-presentation.test.mjs tests/sec-risk.test.mjs tests/sec-risk-comparison.test.mjs tests/finlens-api.test.mjs tests/qa01-harness.test.mjs tests/qa01-process-group.test.mjs`: **543 passed, zero failed, four skipped** (547 total; this run included 41 new tests before the final catalog-coercion guard/test). The four skips are pre-existing Linux-only process-tree integrations on Windows. Log: `%TEMP%/finlens-dual-passing-regression-20261101.log`. After the final guard, focused 42, TypeScript and lint all passed; no existing runtime behavior was changed by that guard.
- Broader combined run including unchanged research-interactions.test.mjs and research.test.mjs: **1,121 passed, 25 failed, four skipped** (1,150 at that checkpoint). Log: `%TEMP%/finlens-dual-final-regression-20261101.log`. This is an executed failing regression, not a green acceptance claim.
- Baseline comparison: read `git show HEAD:frontend/components/filing-research.tsx` into a task-owned temporary file. A temporary Node `--import` loader substitutes only that original source via readFileSync; it never changes repository source/tests. `node --import <temporary-loader> --test --test-reporter=tap tests/research-interactions.test.mjs`: **580 passed, 24 failed**. Normalized failure names match the candidate's 24 mounted failures exactly. Existing assertions expect old financial discovery/request sets (including 3 instead of the current 5 requests); other existing failures concern unavailable-state expectations and the bank gross_profit serializer case. Baseline `research.test.mjs` also fails before filing components load: `Cannot find module './research'` from existing snapshot-gaps/runtime relative-import handling in the test's loader. Baseline logs: `%TEMP%/finlens-dual-baseline-regression-20261101.log` and `%TEMP%/finlens-dual-baseline-static-render-20261101.log`; loader: `%TEMP%/finlens-dual-baseline-loader-20261101.mjs`. Shared tests were not edited or weakened. These baseline issues need separate coordinator disposition.
- `./node_modules/.bin/tsc.cmd --noEmit --incremental false`: exit 0 on final source.
- `npm run lint`: exit 0 on final source.
- `./node_modules/.bin/playwright.cmd test e2e/dual-filing-evidence.spec.ts --list --reporter=list`: lists **six cases**, three at 1440px and three at 390px. Discovery only: no browser or server launched. Shared full-page request lifecycle and strict focus-paint/contrast oracles remain unchanged. Prepared cases cover pair requests, original sources/disclosures/native keyboard, responsive containment, empty/error isolation, duplicate selection, and ignored-abort cancellation with a settled sibling.
- Root `git diff --check`: passed; task-owned source whitespace checked separately because new files are untracked.
- Static source-policy verification: existing READONLY_ROUTES admits exact GET filing-context route; route uses read_session, require_published and build_filing_context. No release-policy or route changes. sec_readonly synthetic capabilities are consistent with this existing admission; real encoder/qualified-filings availability remains untested.

## Candidate scope and remaining gates

New component/validator/test and browser fixture/spec; two-line FilingResearch integration; responsive CSS; one mobile testMatch entry. No backend files changed. Initial four protected changes remain present and untouched by task writes. No acquisition, generation, finance calculator, persistence, account or export work. The source text is the existing bounded cleaned context, not guaranteed complete original filing text. The response bounds are logical application validation after the shared transport parses JSON; this slice adds no streaming byte limit.

Independent review, actual browser keyboard/responsive checks and baseline-test disposition remain pending. Real-source runtime acceptance additionally requires separately authorized qualified filings and encoder; no such acceptance is claimed. Keep this plan active. Suggested commit: `feat(research): compare two indexed filing evidence sources`. No staging, commit or push performed.

The following SHA-256 manifest excludes this living plan and protected unrelated files. Manifest digest is SHA-256 of the sorted `relative-path lowercase-sha256` lines, joined with LF and a final LF.

Initial candidate manifest (superseded by review fixes below) SHA-256: `d58d25b702e32cde07061fbffa6a0fee2d778d2b3a0a2595a1b5c206e299ae28`

```text
frontend/app/globals.css 62468642c537310debcb0fc156875a0c3a15fe4853bf614ff15e48e1e3d0c6ce
frontend/components/dual-filing-evidence.tsx 14667afee14c0d7fd11369cb7d5d2cfc22554002c0c4c916f9e2adeb33d8929b
frontend/components/filing-research.tsx 3d6c8edc55cda53568dacc93a782b63296d9c5805fd76cbaeb3979693ac0d1de
frontend/e2e/dual-filing-evidence.spec.ts 481da8c9448f62426d764f9cfd70f52967dbf236b19417c0f299726bb29b610b
frontend/e2e/fixtures/dual-filing-browser.ts db5ed9cce5355e95f9b02ed6cb4cad5936016633a8667070a61fed3886d41bcf
frontend/lib/dual-filing-evidence.ts fcc9c355bddf8501cec8b70a48557792e1253668051f8a440eb90c340beea751
frontend/playwright.config.ts ee23b5e78f62876f562e1c9f4ccd97e61edc48f2bfad1392ca9de224dbea883c
frontend/tests/dual-filing-evidence.test.mjs 48c80510e1800448660c2cb00cbfcc8325772a854ac7ab94ad58412b768df79d
```

## Independent-review fixes — 2026-11-01

Status: implementation fixes verified locally; independent re-review and browser execution pending. The review identified two P2 defects and a selector inventory pin gap. The initial manifest above is historical and superseded by the current manifest below.

- Source framing: the inherited validator permits CR/U+2028/U+2029 inside a source body, while the shared multiline renderer recognizes those as line boundaries. The dual-filing validator now rejects these noncanonical separators before exposing any result. Existing filing context serialization uses Python splitlines() followed by LF joins, so no backend change is needed. Counterexamples with a source-like END marker and an omitted qualification now fail closed; canonical LF source-like text retains its complete qualification in mounted rendering. This fix rejects malformed framing rather than rewriting or truncating source text.
- Inventory: every record now participates in accession uniqueness, canonical company URL, readiness boolean, form and date checks before indexed filtering. Contradictory indexed/metadata-only duplicates make the inventory invalid; render ownership changes immediately, hiding both sides and cancelling pending work. Restoring a valid inventory cannot resurrect a late response. Legitimate distinct metadata-only 8-K and unknown form/date records remain valid inventory members but cannot enter the selectable pair. Existing 100-indexed/10,000-total bounds remain.
- Publication binding: getFilingSources adds an opt-in requirePublishedVersion argument, default false to preserve other callers. FilingResearch opts in on its existing single versioned source request; no extra automatic request was introduced. Missing response headers now prevent its inventory from driving this comparison, including at publication zero. Explicit inventory retry followed by submit retains exactly two context requests.
- Existing backend contract verified by source inspection and a focused static regression: get_company_sources uses read_session; read_session captures scope["version"] and compares the expected pin; the registered VersionedRoute returns X-FinLens-Data-Version whenever that version is not None, including zero. No route, backend or release-policy changes were made. This is source-contract verification, not live HTTP/DB acceptance.

Actual fix validation (frontend working directory):

- `node --test tests/dual-filing-evidence.test.mjs tests/finlens-api.test.mjs`: **221 passed, zero failed/skipped**. Includes 57 dual-filing tests (15 added review regressions), existing API regressions, ordinary optional-header source behavior, required inventory headers at pins 0/7, malformed separator negatives, full qualification retention, contradictory inventory invalidation and positive distinct metadata-only cases.
- `./node_modules/.bin/tsc.cmd --noEmit --incremental false`: exit 0.
- `npm run lint`: exit 0.
- Root `git diff --check` and explicit task-owned/new-file trailing whitespace scan: passed.
- As instructed, broad suites were not repeated. The independently accepted attribution of the existing 25 broader failures is unchanged. Existing shared tests/helpers were not weakened or edited.
- No browser, server, live DB/provider/model/network, Git write, destructive action or protected-file write occurred. Next step: independent re-review of the current manifest; browser execution remains deferred.

Current reviewed-fix candidate manifest uses the same LF hashing algorithm documented above and includes the small finlens-api.ts opt-in change. This living plan is excluded from the manifest.

Current candidate manifest SHA-256: `151ab782a40e4247ab9a7eadc2b00b4819159c28812c243bb5d2300c8bf4cdca`

```text
frontend/app/globals.css 62468642c537310debcb0fc156875a0c3a15fe4853bf614ff15e48e1e3d0c6ce
frontend/components/dual-filing-evidence.tsx 14667afee14c0d7fd11369cb7d5d2cfc22554002c0c4c916f9e2adeb33d8929b
frontend/components/filing-research.tsx 92b7dc21191070c7c7bf4f48e3051d921f365963c07bb2856592e17b4f8ed227
frontend/e2e/dual-filing-evidence.spec.ts 481da8c9448f62426d764f9cfd70f52967dbf236b19417c0f299726bb29b610b
frontend/e2e/fixtures/dual-filing-browser.ts db5ed9cce5355e95f9b02ed6cb4cad5936016633a8667070a61fed3886d41bcf
frontend/lib/dual-filing-evidence.ts 3f54089710f01f4bc5c4420e6bacb898997481a68a81edea3d9e662b53bdd24f
frontend/lib/finlens-api.ts bc04ecd9e4a91e5f66151dc9451ec0933be6d6c8dc53a03eef0dd44964569567
frontend/playwright.config.ts ee23b5e78f62876f562e1c9f4ccd97e61edc48f2bfad1392ca9de224dbea883c
frontend/tests/dual-filing-evidence.test.mjs 6b27407a2953a64e368221bfeaceeefe67f28b7343d0cb8b970b59b5e1d60a9c
```


## Authorized bounded browser acceptance — 2026-11-01

Independent Astra re-review: scoped PASS for both P2 fixes and the inventory-header gap; parent reported 221 focused/API tests plus 14 additional mounted probes passing. That independent report is distinct from the checks run here. The nine-file candidate remained `151ab782a40e4247ab9a7eadc2b00b4819159c28812c243bb5d2300c8bf4cdca` throughout this browser run.

One supported, explicitly reviewed workload launch ran under the supplied PowerShell 7 executable. No user action is pending. No broad-suite rerun, stage, commit, push, download, settings change, real DB/provider/model/SEC access or production mutation occurred.

Preparation and exact identities:

- Prior proven donor: `D:/Projects/finlens-coverage-browser-c80d617c9ab4495a84ae8625ae650e02`; donor runner SHA-256 `F3E2073E5D2DE6D79E5C70689D526DCE08D2ADFB6CD73D0B8C8D532144BDDB30`. Existing staging/provenance/telemetry overlays were copied without modification; application files came from the reviewed current repository. Only snapshot bindings, exact case selection and case-specific evidence checks were adapted in the new runner; resource/isolation/staging/cleanup safeguards were retained.
- New retained immutable snapshot: `D:/Projects/finlens-dual-filing-browser-757a70cbc3434178b79353dd39d6771a`; 62 whitelisted frontend files, 1,626,032 bytes. Source aggregate SHA-256 `935314C283D7F15023954D4BA654425598053B528F5B1D44B56FB97026722510`. Snapshot manifest SHA-256 `EF9AC56A9D58E52C9AD44C57E31FBB4D13DFF0C448DA9CA5EDCCBDDA6129B5A6`; adapted runner SHA-256 `45B83EFD6354D70423256B644B630309F936974DD6184D7B40206F160FBB9814`.
- Separate retained gate: `D:/Projects/finlens-dual-filing-gate-757a70cbc3434178b79353dd39d6771a`. Launcher SHA-256 `7D6D91D675BC4D69310B37A1AAAB231081076A5AF8BA7F964A6E725E1FE94F6D`. Read-only preflight returned `PASS_EXACT_RUNNER_READONLY_PREFLIGHT` before workload approval. Exact launch: `C:/Users/IITSt/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe -NoProfile -File D:/Projects/finlens-dual-filing-gate-757a70cbc3434178b79353dd39d6771a/launch-once.ps1`.
- Docker `desktop-linux` endpoint `npipe:////./pipe/dockerDesktopLinuxEngine`; existing local image `sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`, no image volumes. Seven image code references matched and Node was v24.21.0. Standing acceptance of the six existing optional WASM-support dependency risks was used; those optionals remain unverified, not installed.
- Restrictions: pull never, network none, no published ports, UID/GID 1001, read-only root, all capabilities dropped, no-new-privileges, 2 CPUs, 4 GiB RAM/no extra swap, 256 PIDs, 512 MiB private shared memory, bounded private tmpfs/artifacts, 600-second Linux workload deadline and independent bounded Windows supervision. Source mount read-only; fresh artifact mount only.

Actual browser outcome: **six passed, zero failed/skipped/flaky/retried**, exactly three desktop Chromium cases at 1440x1000 and the same three at 390x844. Each project ran:

1. Original source presentation, exact pair accounting, native keyboard/source disclosures and responsive containment.
2. Independent empty/error side, explicit retry and duplicate-selection disabling.
3. Cancellation with an already settled sibling and deliberately delivered ignored-abort response; neither result reappeared.

The full-page ledger assertions passed without helper changes. Across the six cases there were 16 context requests for eight explicit submissions, always the two distinct selected accessions with `limit=5`, same query and publication header zero. Source disclosure and question edits added no context request. All six fixture violation lists and binding-error lists were empty. One raw teardown attachment (desktop cancellation case, row 3) flags an unbound startup freshness replay because that attachment calls lifecycle with no declared-cancellation list. It is a cancelled/headerless/bodyless local GET with ERR_ABORTED and exactly one same-generation routed/completed 200 companion (row 4); it meets the existing strict replayCancellations exception used by the passing expectFullLedger checks. No new exception or weakened accounting was introduced.

Preserved evidence and visual inspection:

- Original artifacts: `D:/Projects/finlens-annual-browser-artifacts-a31acf8615b448eaaef14b3003c37c04`. Hashed export: 30 files including artifact-index.json, 1,248,261 bytes; original index entries rechecked after inspection. Eight PNGs, eight focus JSONs and six ledgers were decoded without alteration from inline report attachments into the new gate's `evidence-view/`; original reports were not changed.
- All eight actual screenshots and focus geometries were inspected. Native focused compare/disclosure/source/cancel controls have visible solid 3px outlines with 6px total extent, completely contained in the measured viewport; four-point adjacent-surface contrast ratios are at least 4.6876:1. Desktop shows separate source columns; 390px stacks them and wraps source metadata/literal script-like text. Automated layout checks found no page horizontal overflow. Empty/error states were asserted by the browser cases; they have no separate saved screenshots.
- Visual caveat: the existing floating development Next.js N badge is visible at the lower left. At 390px it overlaps nonfocused content near the bottom edge, including part of the Filing B heading in the source-link screenshot and the pending publication/status line in the cancel screenshot. None of the eight checked focused controls is occluded. No indicator hiding, CSS workaround, assertion relaxation, extra scroll/focus mutation or retry was used. This is a disclosed development-overlay limitation, not blanket visual/accessibility acceptance.
- Scope caveat: the six immutable reviewed browser cases exercise publication zero. Pins zero/nonzero, publication changes, malformed header/inventory/source boundaries and additional stale-owner scenarios passed the focused mounted tests, but nonzero/publication-switch browser execution was not added. Real qualified-filings/encoder/retrieval acceptance, native zoom and assistive technology remain unverified. Requirement 5b synthesis is still incomplete/out of scope.

Exit and cleanup: one invocation, no retry; runner/container exit 0, no signal/OOM. Container ID `646e2e3eaa4f2501e5550c2aebfe1116eb96ce50cdd3792ebd928f6505351150`, owner nonce `a31acf8615b448eaaef14b3003c37c04`. Both phase cleanup checks passed. Four process observations (baseline, desktop, mobile, final) were known; owned telemetry joins passed with no signals. All ten bounded host Docker CLIs exited 0 and were reaped. Internal ports 3107/3108 closed, zero extra live processes and QA copies, owned runtime root removed. Exact ID/name/image/nonce was verified before container removal; absence verified afterward. Snapshot, gate, original artifacts and all prior gates were retained. No bulk filesystem deletion or drive changes occurred. All source and four protected-file hashes matched the frozen manifest before the documentation append.

Final runner result SHA-256 `3b0e5cda8b27a599d249b8a421a8e36423de84b7d3196f878dde83f32a1d7593`; artifact index SHA-256 `c53f454b83ce631445c3a8586e63ff30022baba9fb56ea47c671ce9e2f5fa858`; receipt SHA-256 `a3c600b45fb0d3b27346456d39a988fcba5bff3fa6162f02fc14005a95570d8b`.

The accepted attribution of the 25 earlier broader baseline failures remains unchanged; those suites were not rerun here. Current outcome: source re-review PASS and six-case offline browser PASS with the disclosed overlay and coverage limitations. Coordinator disposition of those limitations and baseline failures remains separate. No Git operation is authorized by this outcome; suggested commit remains `feat(research): compare two indexed filing evidence sources`.


## Terra P3 selector identity presentation fix — 2026-11-01

Terra identified that native select text can truncate accessions at desktop/narrow widths, making same-form/same-date filings indistinguishable before submit. Authorized fix scope: component, CSS, focused tests and this ExecPlan only. No browser, broad suite, Git write or unrelated polish was run.

Each native selector now has an adjacent visible full-accession description, associated through aria-describedby. Descriptions stay outside the wrapping label so existing accessible names Filing A/Filing B are retained. Text uses the existing anywhere-wrap utility, and the new grid wrapper has min-width zero. Only validated current selections from the current verified inventory receive an accession label; incomplete/invalid inventories or an unverified publication show a neutral placeholder. No selection, request, cancellation or source-validation logic changed. There is no additional fetch.

Actual validation from frontend:

- `node --test tests/dual-filing-evidence.test.mjs`: **61 passed, zero failed/skipped**. Four added mounted tests cover same-form/same-date distinct-accession fixtures, full visible text and accessible description identity, label updates without requests, contradictory/incomplete inventory clearing, missing-pin clearing, and parent publication refresh hiding old labels until the existing pinned inventory response arrives. Existing exact two-context-request tests still pass.
- `./node_modules/.bin/tsc.cmd --noEmit --incremental false`: exit 0.
- `npm run lint`: exit 0.
- Root `git diff --check` and new/task-owned trailing-whitespace scan: passed.

The previous six-case browser evidence and all original artifacts remain unchanged and retained for candidate 151ab782a40e4247ab9a7eadc2b00b4819159c28812c243bb5d2300c8bf4cdca. It does not constitute a browser rerun of this presentation fix. Actual 390px wrapping/focus geometry after this change remains pending permitted browser reacceptance. The development N badge overlap caveat, nonzero/publication-switch mounted-only evidence, and independently attributed 25 broader baseline failures remain explicit and unchanged. No deployment, stage, commit or push occurred; four protected files retain their recorded hashes.

Three frontend files changed from the prior reviewed/browser candidate: app/globals.css, components/dual-filing-evidence.tsx and tests/dual-filing-evidence.test.mjs. The other six frontend hashes are unchanged. This append preserves the complete prior ExecPlan prefix (SHA-256 bc179d7f2244cc7d36f19728825ccc8850729150dce4e51f91ef3ada54da941c). The current nine-file manifest below supersedes the previous manifest for further review, while the prior acceptance evidence remains historical and intact.

Current P3-fix candidate manifest SHA-256: `a6ee57f2841338e9f59828212eb84b7ab5675b05ce42c56ddb98197ae9702edd`

```text
frontend/app/globals.css 95c72d7c573ee268e00725a59a245365e42e0757bf2edb8444706a4517e883db
frontend/components/dual-filing-evidence.tsx 66ff156c8f8a2431a8206ab204524fed30e67868c4cf4c69284be3f466724738
frontend/components/filing-research.tsx 92b7dc21191070c7c7bf4f48e3051d921f365963c07bb2856592e17b4f8ed227
frontend/e2e/dual-filing-evidence.spec.ts 481da8c9448f62426d764f9cfd70f52967dbf236b19417c0f299726bb29b610b
frontend/e2e/fixtures/dual-filing-browser.ts db5ed9cce5355e95f9b02ed6cb4cad5936016633a8667070a61fed3886d41bcf
frontend/lib/dual-filing-evidence.ts 3f54089710f01f4bc5c4420e6bacb898997481a68a81edea3d9e662b53bdd24f
frontend/lib/finlens-api.ts bc04ecd9e4a91e5f66151dc9451ec0933be6d6c8dc53a03eef0dd44964569567
frontend/playwright.config.ts ee23b5e78f62876f562e1c9f4ccd97e61edc48f2bfad1392ca9de224dbea883c
frontend/tests/dual-filing-evidence.test.mjs 4759ad4ab0ac363e0adeae9e96404a9fcbd6fcfb42a934c6124a82ea7a5f2f4d
```


## P3 focused visual verification — 2026-11-01

Terra's narrow source/test review approved focused visual verification. One justified presentation-change batch ran exactly two existing primary cases: `dual filing: original sources, strict pair accounting, native keyboard and responsive layout`, once in desktop Chromium 1440x1000 and once at 390x844. No source/config/test modifications were made for capture; no broad suite or blind retry occurred. The nine-file P3 candidate remained `a6ee57f2841338e9f59828212eb84b7ab5675b05ce42c56ddb98197ae9702edd` throughout.

Retained identities and invocation:

- Fresh snapshot `D:/Projects/finlens-dual-filing-p3-browser-082ce8030af24e129afde6de3bc308a8`: 62 files, 1,626,243 bytes, source aggregate SHA-256 `E0E19315B9ECA048E9A3BBDE6A691FB7B1AE8D3FDA0176D3795C2984838C4A61`. Manifest SHA-256 `0D7C3F478F959B7E73AE4079BA8EC586F265ADE40F66A4E2F34FAB95B375EF57`; runner SHA-256 `1FC00F4F2731D58DDB0D06BBB01E56BC0A3BC1365446675AD80CB9888E53D972`.
- Fresh gate `D:/Projects/finlens-dual-filing-p3-gate-082ce8030af24e129afde6de3bc308a8`; launcher SHA-256 `B4E1AC8795DCEDA120BF6D29B1894D5C91DF2D4549597D60CBD01B44EA5195FF`. Supported read-only preflight passed before tool-approved execution. Exact command: `C:/Users/IITSt/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe -NoProfile -File D:/Projects/finlens-dual-filing-p3-gate-082ce8030af24e129afde6de3bc308a8/launch-once.ps1`.
- Same pinned local Linux image `sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`, desktop-linux named pipe; existing seven image code references MATCH. Prior reviewed network-none/no-ports/pull-never/nonroot/read-only/cap-drop/no-new-privileges/resource/staging/identity-cleanup restrictions and accepted six optional WASM dependency risks retained. No install/download/credential/real-data/provider/model/settings access or Git write.

Actual outcome: **two passed, zero failed/skipped/flaky/retried**, one workload invocation. Desktop report 9,179.901 ms (case 1,433 ms); mobile report 7,400.382 ms (case 2,239 ms). Each final ledger contains exactly two filing-context requests, same question, limit five, publication zero, both completed 200. Both violation/binding-error/raw rejected-unbound lists are empty. Existing assertions also verify disclosure/question edits add no request, source URL identity, no interpreted script element, source columns at desktop/stacking at 390px, and no horizontal page overflow.

Original artifacts: `D:/Projects/finlens-annual-browser-artifacts-700d42067cbd40d0b8c7df7a1e899493`; 30 hashed exported files including index, 865,840 bytes. Derived unchanged attachment bytes and inspection summary are under the new gate's `evidence-view/`. All six actual PNGs and six focus geometries were inspected. Exact primary P3 evidence:

- `evidence-view/desktop-compare-viewport.png`: both complete adjacent accession labels visible before submit, while native select display text may truncate. Cancel control visible in idle state.
- `evidence-view/mobile-compare-viewport.png`: both complete adjacent accessions visible at 390px, with neither clipping nor N-badge overlap. Native selectors retained.
- `evidence-view/desktop-source-details-viewport.png` and `evidence-view/mobile-source-details-viewport.png`: original excerpts and focused source disclosure.
- `evidence-view/desktop-sec-link-viewport.png` and `evidence-view/mobile-sec-link-viewport.png`: expanded source metadata and focused official SEC source link.

Focus remains visible/contained for compare, disclosure and source link in each viewport: solid 3px outlines, 6px extent, minimum measured contrast 4.6876:1; none of these six targets is occluded. Existing development N badge remains visible; at 390px it still overlaps off-focus lower-left content near the Filing B heading in the source-link screenshot. No badge hiding, source alteration, extra capture scrolling, weakened assertion or retry was used. Same-form/same-date fixture proof remains the passed mounted P3 regression; these unchanged browser fixtures use different forms/dates.

Exactly the requested two primary cases were run. Pending-cancel focus/ignored-abort delivery with a settled sibling, empty/error-side isolation, explicit retry and duplicate-selection browser assertions were not repeated: their unchanged lifecycle behavior remains supported by the preserved prior six-case run on candidate 151ab782a40e4247ab9a7eadc2b00b4819159c28812c243bb5d2300c8bf4cdca, plus the current 61-test mounted suite. Current captures show the cancel button idle, not a fresh pending/post-cancel screenshot. Prior run artifacts/snapshot/gate remain untouched. Nonzero/publication-switch browser coverage remains mounted-only; the 25 independently attributed baseline failures were not rerun. No real qualified-filings/encoder or full requirement-5b synthesis acceptance is claimed.

Exit/cleanup: container ID `f1846630d6457b72bc477c6d7b32e15f46e0fc94ce198e3a144550c18a2dd650`, owner nonce `700d42067cbd40d0b8c7df7a1e899493`; exit 0, OOM false, no signals. Both phase cleanup checks and all final gates passed. All ten bounded host Docker CLIs reaped with exit 0; ports 3107/3108 closed, no extra live process/QA copy, owned runtime root removed, exact owned container removed and absence verified. Snapshot and all evidence retained; source/protected hashes matched before this documentation-only appendix. No bulk filesystem or drive cleanup occurred.

Current outcome: P3 primary browser verification PASS with actual readable full-accession pixels at both viewports; independent Terra visual closure remains for the parent. This appendix preserves the prior ExecPlan prefix (SHA-256 d1593bef865aff5d775dce07f5332e54a14271672809aab4d51812d153b0dc23). No staging, commit or push was performed.
