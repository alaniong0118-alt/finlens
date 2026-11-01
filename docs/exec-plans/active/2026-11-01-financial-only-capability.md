# Dormant financial-only capability restriction

Status: active; independently reviewed implementation and four-case synthetic browser acceptance passed; final Git delivery and runtime activation are not performed.

## Objective and scope

Add a default-off, process-only restriction within `sec_readonly`, preserving
stored financial research and deterministic questions while rejecting filing
text/retrieval and encoder use. This is not runtime, authentication, hosting or
external-access activation. Baseline: bb036a49953adc1bee1b43a612bc35141f47880c.

## Constraints

No new admitted routes, data/schema/formula changes, private configuration reads,
live DB/provider/model calls, installs, services or Git writes. Browser attempts
require a separately scoped approval and remain synthetic only.
Preserve the four historical exceptions and all C:/D:/E: files. The existing
BLOCKED private-runtime preflight and development-only launcher stay unchanged.
Capability restriction does not establish network isolation or source rights.

## Design and implementation stages

1. Freeze the process flag before dotenv loading; reject malformed values and
   incompatible profiles. Intersect exact route admission with financial routes
   and reject encoder calls before cache/imports.
2. Advertise `filing_research_enabled` with no-store. Gate UI retrieval mounts and
   keep the existing deterministic question path without evidence fan-out.
3. Add focused offline policy/config/API/mounted tests and explicit full-mode
   fixtures, then run applicable regression, lint and TypeScript checks.
4. Freeze candidate for independent review. Browser, runtime activation and Git
   delivery are separate gates.

## Retained source metadata

`/companies/{ticker}/sources` remains a stored metadata/provenance route, not a
financial-only dataset guarantee. It returns accession, form, filed date,
period_start/end, metrics, official sec_url and has_filing_chunks. It merges
financial-fact metadata with indexed-filing metadata, including filings without
financial facts; it does not return passage text. This retained metadata is stated
in the financial question panel. Filing text, chunks, search, context and tone
routes are excluded. Catalog indexing fields are retained without advertising
filing readiness when retrieval is disabled or unverified.

## Progress and validation

- Implemented: frozen process-only flag (`0`/`1`, absent = off), exact 16-route
  intersection, pre-cache encoder guard and uncached capability. No activation.
- UI: verified true is required to enable filing inventory effects and mount
  keyword/dual-filing/risk components. The shared financial editor stays mounted
  without inventory/context/AI fan-out when restricted. Legacy/missing/failed
  capabilities stay unverified, not assumed full.
- Backend: from `backend`, process-local `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`,
  `.venv/Scripts/python.exe -I -B tests/run_dep01a2_increment2_offline.py
  tests/test_financial_only_policy.py tests/test_quarter_window_policy.py
  tests/test_financial_coverage_policy.py`: 97 passed. After adding one actual
  restricted coverage route control, the financial-only test file alone passed
  45 tests. These runs overlap; they are not additive suite totals. Tests use
  guarded sockets/DB and mocked read-only sessions; no physical DB/model access.
- Frontend: from `frontend`, `E:/node.exe --test
  --test-name-pattern='financial-only|DEP-01A1|DEP-01A2 source timeout|mounted company switch keeps B|REL-LEX-01|mounted keyword fallback'
  tests/finlens-api.test.mjs tests/research-interactions.test.mjs`: 209 passed,
  zero failures/skips. Includes StrictMode, pins 0/7, unknown/malformed/pending
  capabilities, company/repin ignored-abort isolation and full-mode controls.
- Full `E:/node.exe --test tests/finlens-api.test.mjs`: 165 passed, zero skips.
- Final mounted selection (`financial-only|DEP-01A1|DEP-01A2 source timeout|mounted company switch keeps B`
  in `tests/research-interactions.test.mjs`): 19 passed, zero skips. This follows
  removing a redundant new page key and adding a full-mode company-change
  control. Its first run was 18 passed / 1 failed because the new control
  incorrectly expected editor retention; the existing company-keyed freshness
  subtree resets it. Corrected the control to assert that existing reset and
  continued retrieval, without changing production company-switch behavior.
- Additional `E:/node.exe --test tests/qa01-harness.test.mjs
  tests/financial-insights-interactions.test.mjs`: 153 passed / 2 failed. The
  Home fixtures lacked required capability fields and had obsolete expectations
  for immediate grid adjacency and the old empty-snapshot wording. HEAD already
  includes intervening comparison panels and the missing-metric unverified map.
  Corrected the fixtures and assertions to those actual contracts, without
  changing production layout or financial validation. First two-case recheck:
  1 passed / 1 failed (old snapshot text); final exact two-case recheck using
  `--test-name-pattern='^1B.2A (Home mounts|supported Home)'`: 2 passed, zero skips.
  The complete 155-case selection was not rerun after these test-only repairs;
  its initial failure evidence remains recorded here, not relabeled full PASS.
- `E:/node.exe node_modules/typescript/bin/tsc --noEmit --incremental false` and
  targeted ESLint on the four frontend product files plus the two changed TS
  fixture/spec files: exit 0. Production TS bytes unchanged since these checks.
- No browser, startup, native runtime, external access or real-data acceptance.
- Independent content review and any bounded browser acceptance remain pending.

## Independent review repair: stable financial ownership

The first review found a P2: capability verification replaced FinancialQuestions
with FullFilingResearch, remounting the editor and aborting/discarding a same-
company/pin financial answer. Two independent transition probes failed. Backend
restriction checks passed; this is not a backend admission defect.

Removed the mode-dependent component replacement. One FilingResearch and keyed
FilingSearch now own the editor and financial request across capability changes.
Only inventory effects and retrieval controls/children are enabled. Inventory
ownership includes capability state; changes synchronously invalidate evidence
ownership only, and disabled evidence cannot render. No financial POST replay,
backend policy change, runtime activation or company/publication reset removal.

Focused repair validation from `frontend`:

```text
E:/node.exe --test --test-name-pattern='financial-only|DEP-01A1 mounted|DEP-01A2 source timeout|mounted company switch keeps B' tests/research-interactions.test.mjs
35 passed; 0 failed/cancelled/skipped
E:/node.exe node_modules/typescript/bin/tsc --noEmit --incremental false
exit 0
E:/node.exe node_modules/eslint/bin/eslint.js components/filing-research.tsx
exit 0
```

Sixteen added transition cases cover pending/completed answers, pins 0/7 and
StrictMode, stable editor/form/answer DOM and focus, delayed valid capability,
restricted/legacy/invalid/failed capability, and reverse restriction cancelling
only evidence. The mock ignores abort and still delivers obsolete evidence;
tests reject its display and assert no automatic question replay. Existing
company/repin isolation and full-mode controls remain in the selection. Earlier
broader results above predate this narrow repair; no broad suites were repeated.
Independent re-review remains pending.

## First bounded synthetic browser attempt: failed, no retry

Independent targeted re-review subsequently closed the capability-transition P2
and accepted the fifteen-file candidate plus the new browser spec/config. One
authorized four-case attempt used the fixed local image
`sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`.
The six optional WASM dependencies remain unverified and explicitly accepted.
No production runtime/profile was activated.

- Snapshot: `D:/Projects/finlens-financial-only-browser-169291b5a5274410808293f3c1f1a759`.
  Manifest SHA256 `0C9D384F803E918A3ED978B6D3220ECFC0B0E4343F79E2D280527F5A4C28B4C4`;
  runner `BA6E7F617D94924DAD2E997FA5DC94F59B5E8E1E796B0BDE3FE13E1B94A18BD8`.
- External gate: `D:/Projects/finlens-financial-only-gate-169291b5a5274410808293f3c1f1a759`;
  launcher `814024BB02DE8DB30E63DDAAE00153B9320F57CC36068181B3DFEADB02AFD464`.
  Atomic attempt record retained. Source/status/hash preflight passed before run.
- Evidence root: `D:/Projects/finlens-annual-browser-artifacts-f9d7c04cd56b4783a2b5826f99b6e6de`.
  Desktop first case failed at spec line 147: AAA pin-0 aborted-delivery observer
  expected 1, observed 0. Desktop second case was skipped by fail-fast. Both
  mobile cases were unrun; no cases passed. Container exit 1, no OOM or timeout.
- This was a test failure propagated through the Docker CLI, not a denied Docker
  operation or failed staging. Both next-env copy boundaries passed with exact
  initial bytes and exclusive destination creation; no source permissions changed.
- Retained request-object ledger contains two exact AAA pin-0 financial POSTs,
  both completed 200, including the held old-company response. It records zero
  sources/context/filing requests, no binding errors, no rejected unbound requests
  and no fixture violations up to failure. This is partial evidence, not complete
  company/publication stale isolation or delayed-capability browser acceptance.
- Diagnosis: the new spec installs the existing single-path ignored-abort seam
  three times. Each installation creates its own array and overwrites the shared
  `window.qaDeliveries` slot, so one global observer cannot reliably report all
  three paths. The successful HTTP completion does not recover the original
  AbortSignal observation from the hidden arrays. No product defect is established
  by this failed probe. Proposed repair is one test-local bounded multi-path
  observer retaining exact path/method/pin/body accounting and the strict count
  assertion; no shared helper or production change has been made, no retry.
- One actual focus PNG/geometry pair was captured before failure: desktop submit
  target 44.796875px, DPR 1, solid 3px outline / 3px offset, full viewport
  containment, center/perimeter exposure, contrast 4.9228:1 and no page overflow.
  Pixel inspection shows a continuous unobscured submit ring. A floating N badge
  partially overlaps unrelated lower-left page content; not all UI is unobscured.
  No mobile or delayed-capability focus images exist for this attempt.
- Retained index SHA256 `C8D0DDB9BC1DA2088664F91F412EE1D7FAEFF955C2E36491DD3B8257A11F800A`.
  Read-only post-run verification matched all 19 indexed entries plus the index
  itself: 20 exports, 3,019,387 bytes. Original host artifact/test gates remain
  false because the CLI failed; independent hash checks do not relabel the run.
- Identity-owned cleanup passed: exact full container ID/name/image/nonce verified
  before removal, container absence confirmed, all owned host CLIs reaped, no
  uncertain starts. Inner ports 3107/3108 closed, zero extra live processes,
  zero owned QA copies; owned runtime removed. Source/protected preservation
  passed. Existing files, snapshots, receipts and failed evidence are retained.
- Only this factual append follows execution. Browser spec, production/test source
  and protected exceptions are unchanged. Independent repair review and a new
  bounded execution gate are required before any successor attempt.
- Post-run scoped hashes confirm all sixteen code/test inputs and four protected
  exceptions unchanged. Global status additionally contains an untracked
  `docs/exec-plans/active/2026-11-01-finlens-personal-site.md`, not created, read,
  modified or included by this workstream; any future snapshot must reconcile
  that separate status entry. Index remains empty and HEAD unchanged.

## Test-local observer repair (not yet browser-validated)

Confirmed from the unchanged shared initializer that every single-path install
allocates a new array and assigns the same `window.qaDeliveries` slot. The first
case installed it three times; the second case used the same observer API once.
Both new cases now use one test-local installation per document with an independent
`qaFinancialOnlyDeliveries` store. Only AAA/BBB research POSTs and BBB summary GET
are selectable, with monotonic request IDs and exact method/path/query/pin/raw-body
capture. Duplicate installs reject before changing fetch/store; an unrelated
legacy install cannot erase existing or in-flight observations. The original
signals are preserved for application guards while the chosen synthetic transport
ignores abort. Wrong methods/body streams reject; unrelated calls retain their
native signals and remain subject to the existing fixture network guards.

The strict late-return expectations remain 1 for each exact old financial request
and 0 for preserved capability-transition requests. The latter also requires one
actual observation per document; a missing store cannot masquerade as zero.
Records explicitly say `headers_returned`, not body completion. The unchanged
request-object ledger still independently requires full HTTP completion. Observer
records are included in the bounded audit, so a future failure retains this
measurement instead of losing private per-wrapper arrays.

Focused validation: `E:/node.exe --test tests/financial-only-observer.test.mjs`
passed 11/11 with no skips. Tests extract the actual initializers and counter from
source and exercise all three routes, out-of-order returns, later legacy and
duplicate installation, immutable identities, wrong query/pin/body/status, raw JSON
null, non-aborted responses, native unrelated signals, unsupported shapes/routes
and missing-store rejection. Final TypeScript and targeted spec ESLint exit 0.
An intermediate TS2352 on a test-only Window cast was corrected to optional-field
access with an exact count assertion. Playwright list remains four cases; no
browser or broad suite was rerun. Original failed receipts/logs are unchanged.

The separate active personal-site plan is now absent, and Git status instead
contains `docs/exec-plans/completed/2026-11-01-finlens-personal-site.md`. This task
did not move it or read its contents. Preserve it as a fifth exception, SHA256
`2B416A00962794FF97CFDBDCAB1ACDEAB5AFF3623733AC8095359CBC3C84A704`.
No other concurrent status change was observed. Independent review of this
test-local delta is required before a successor run; no new attempt is authorized
or implied by this record.

## Second synthetic attempt and focused product layout repair

The observer-corrected one-attempt run retained artifact root
`D:/Projects/finlens-annual-browser-artifacts-57d3907e99e64564a27492c3c96feba6`.
It executed one passing and one failing desktop case; both mobile cases were
unrun after desktop fail-fast. The explicit financial request/company/repin case
passed: the observer retained both aborted old deliveries, all current results,
and zero hidden filing retrieval calls. The delayed-capability case retained
editor/form DOM identity, query and focus but failed the unchanged visibility
oracle before pending-answer release or completed-answer navigation. The editor
moved to y=996.40625..1087.578125 in a 1000px viewport; its outward ring extended
93.578125px below the viewport. The saved PNG confirms this is layout displacement,
not subpixel rounding or the floating development badge. No mobile or complete
transition acceptance is claimed.

The runner exited 1 after 13.777 seconds, without timeout. Identity-bound cleanup
passed: the exact owned container was absent, host CLI processes were reaped,
inner ports 3107/3108 closed, zero extra live processes/copies remained. All 19
indexed entries passed length/SHA256 verification (20 files including the index).
Index SHA256: `6514B9F064C61E9BD6A7E1E9CDFC5731F669785FB858E39F7DB6793C45B681F4`.
All 18 candidate and five protected-file hashes matched their reviewed inputs;
the index was empty and HEAD unchanged. Both failed attempts remain preserved.

The scoped product repair keeps a common financial heading/intro and the stable
financial form/answer before capability-dependent filing controls, selected
filing metadata and research-purpose control. Full-mode filing controls remain
usable; keyword/risk/general mode selection is retained. This is document-order
layout behavior, with no capability-triggered focus or scrolling effect, no
request/ownership changes and no POST replay. The restricted notice stays explicit
below the financial form; full-mode retrieval configuration follows it. Mounted
checks lock the editor's preceding DOM identities and text across both capability
directions and inventory completion, including pending/completed answers,
StrictMode and pins 0/7. JSDOM checks structure, not real pixel visibility.

Validation from `frontend` with the existing `E:/node.exe`:
- `--test --test-name-pattern='^financial-only ' tests/research-interactions.test.mjs`:
  final recheck: 28 passed, zero failures/skips, including explicit per-node
  identity checks for the stable editor prefix (the earlier 28-case run also passed).
- `--test --test-name-pattern='^RISK-SEC-01 |^REL-LEX-01 |^mounted keyword fallback'
  tests/research-interactions.test.mjs`: 182 passed, zero failures/skips.
- `node_modules/eslint/bin/eslint.js components/filing-research.tsx` and
  `node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0.

Focused independent layout review and one separately gated four-case rerun remain
pending. The browser spec, observer, geometry/tolerance, keyboard actions and
viewport sizes are unchanged by this repair. No runtime activation or Git writes.

## Proposed next acceptance (not executed)

Reuse the pinned isolated synthetic browser harness for the existing four cases:
restricted and delayed pending/completed transitions at desktop and 390px in
`financial-only-capability.spec.ts`. Explicitly model the
restricted capability and reject all filing/content requests; retain exact
financial endpoint/query/pin accounting including zero, one direct question per
submit, company and publication changes, keyboard/source-link access and native
focus visibility. No new generic request recorder, runtime or startup mechanism.

## Completion criteria and limitations

Exact route/config and UI request tests pass; existing financial pins, read-only
transactions, budgets and registry checks remain. Missing/failed capability
verification must not enable retrieval. Legacy servers retain financial UI but
cannot verify the new retrieval capability. Old clients may still attempt denied
requests; zero-background-retrieval assurance requires the matching new frontend.

## Final bounded synthetic acceptance (supersedes earlier pending checkpoints)

The independent Astra layout re-review reported scoped PASS with 15 independently
passing focused tests. The 18-file candidate and five protected exceptions matched
its reviewed pins. No further product, observer or browser-spec edits followed.
Earlier review/acceptance-pending statements above record their original stages;
they do not describe the final result below.

A separate packaging attempt stopped before any browser case: artifact root
`D:/Projects/finlens-annual-browser-artifacts-659d49cbea4547f98b0915d9d484d25c`.
The container's embedded JavaScript still required totalBytes 1657555 while the
manifest correctly described 1657686. It exited 1 in 486ms, without OOM/timeout;
zero browser cases, screenshots or geometry were produced. Host identity-owned
container/CLI cleanup and all candidate/protected preservation checks passed.
This packaging failure is not a product failure and remains retained unchanged.

Only that byte-count binding and fresh successor identities were corrected in
external proposal artifacts, with no repository changes. The prevention lesson
is to validate both the outer PowerShell and the actual embedded JavaScript
source checks before launch, including count, total bytes, every source/support
hash, aggregate and exact inventory. The new no-launch check executes those
actual inner read-only checks and rejects five malformed identity controls,
including the stale previous byte total. It initially needed the native Buffer
global supplied explicitly to the isolated evaluation context; the final check
passed without launching a workload. Linux runtime/user identity and artifact
ownership checks remain enforced by the unchanged actual runner, not simulated
by this Windows check. Outer preflight also passed: 64 source files, 1657686 bytes,
18 reviewed candidate inputs and five protected exceptions.

Final single-attempt command used bound PowerShell 7.6.5 / .NET 10.0.11:
`C:/Users/IITSt/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe -NoLogo -NoProfile -NonInteractive -File D:/Projects/finlens-financial-only-gate-f23ad47ec57849eab87f871a53a8d1fb/launch-once.ps1`.
Launcher SHA256: `55D56CD036202D021866A30BED60F9148F0A153276E6A37423FAE1FB392B10E7`.
Manifest SHA256: `139D2B3DA15DAC3BBB22FCC745E0649E5D0A9E4C3657429811B32DE5EDE96257`.
Runner SHA256: `E52D3C9FDB7EFAC316790A276A2C517F8F0EE3402645E6B8254E8608D467718C`.
No attempt marker was rearmed or reused; all prior failed attempts remain intact.

Final artifact root:
`D:/Projects/finlens-annual-browser-artifacts-5351358969bb4deab2f2e86fcd04e987`.
Actual result: desktop1440 two passed; narrow390 two passed; zero failed, skipped
or retries. The restricted explicit-question/company/publication-isolation case
and delayed-capability pending/completed-ownership case passed at each width.
Runner/container exit 0 in 24040ms, without OOM or timeout. The image remained
`sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`.
Nonroot execution, no network/published ports/downloads, read-only root and the
existing resource/deadline/export limits were retained. Six previously disclosed
optional WASM dependency gaps remain UNVERIFIED_OPTIONAL_DEPENDENCIES, not certified.

All eight PNG/geometry pairs were decoded and visually inspected. Tested editor
and submit focus rings were continuous and unoccluded at both widths; measured
DPR1, 3px outline with 3px offset, contrast about 4.923, no clipping ancestors or
page overflow. Button height 44.796875px, editor height 91.171875px. Pending and
completed retained editors both measured y475.28125..566.453125 desktop and
y397.90625..489.078125 narrow, fully inside the unchanged viewports. No test or
capability-triggered programmatic scrolling was added. The floating N indicator
still overlaps some lower-left narrow notice/loading/answer content; it does not
overlap the tested focused controls. This is not a claim that all screen content
is unobscured, real-touch-device acceptance or broad accessibility certification.

Request audits and complete lifecycle ledgers were checked: each restricted case
observed 36 requests (27 completed, nine explicitly accounted cancellations), five
financial POSTs for five explicit submissions, zero filing inventory/context/search
requests, and two deliberately ignored-abort old financial deliveries rejected by
render ownership. Each delayed case observed 26 requests over two navigations
(20 completed, six declared startup cancellations), two financial POSTs (one per
navigation), two metadata inventory requests only after verified capability, and
zero context/search fan-out or answer replay. Last-navigation observer records
retain one non-aborted financial delivery. All four ledgers had zero binding
errors, rejected-unbound records or unexplained violations; recorded cancellation
is not globally ignored. Company and pins 0/1/2 stale-result checks passed; the
mounted tests separately exercise pins 0/7 and reverse capability transitions.

All 29 indexed artifact entries passed byte-length/SHA256 verification (30 files
including the index), 1787599 indexed bytes. Index SHA256:
`024B9B6DEC7C2E3353007DAA65663CD926B055508FEE5263186117E7FF7C4D4B`.
The exact owned container
`18cf788f15ada2a2ed320e313beb6091145fd13ad9ab7698e087fe21fba7f9bd`
was absent after cleanup, host CLI processes were reaped, inner ports3107/3108
closed, zero extra live processes or QA copies remained, and only owned runtime
staging/dependency links were removed. Source/proposal/preservation gates all
passed. No existing files/drives were deleted, formatted or cleaned.

Only this ExecPlan's status and factual final evidence were updated after the
successful run. All 17 code/test candidate files and all five protected exceptions
remain at reviewed hashes. This is dormant software plus synthetic acceptance;
no actual application activation, real-data/encoder acceptance, external beta,
source-rights approval, deployment, installation or Git write occurred. Git
staging/commit/push remain a separate final delivery gate. Suggested commit:
`feat(research): add dormant financial-only capability restriction`.
