# Annual comparison coverage-filter browser acceptance preparation

Status: active — preparation only; independent review and execution pending
Roadmap phase: bounded 4c/D9 UI acceptance; no new feature or export rights

## Objective

Prepare exactly two desktop Chromium cases and one 390×844 mobile-width case for
the reviewed current comparison coverage filter. Exercise counts, exclusions,
zero/reset, unverified responses, company-scope reset, keyboard/touch operation,
readability, copy eligibility and absence of additional API calls during filtering.
Prepare a separate frozen source snapshot and copy of the established bounded
runner. Do not execute browsers, containers or services in this task.

## Current architecture and context

Repository `D:/Projects/finlens-foundation`, main HEAD
`d6a9e42ce8571bec5450b06fed97d829d6b1272f`, empty index. Read root instructions,
[ExecPlan rules](../../../.agent/PLANS.md), [roadmap](../../../ROADMAP.md),
[browser harness](../../browser-e2e-testing.md), current component/filter tests,
shared QA fixtures and the established external acceptance runner/support.

The existing `Scenario` validates the request allowlist, independent publication
pins and explicit catalog before test overrides. Its teardown checks page errors,
external requests and deny-all upstream health. Use it unchanged. The new spec
path did not exist. The mobile project explicitly matches named files, so adding
the new spec to that list is necessary; other settings remain unchanged.

Baseline worktree: four reviewed pending QA files, two reviewed filter files,
modified `frontend/next-env.d.ts`, two untracked historical backend reports and
the blocked export ExecPlan. No pre-existing content may change. Protected hashes
are retained in the separate snapshot manifest; the export plan remains untouched.

Reviewed filter SHA-256:

- component: `4BF228BFB99DCAC347F9233D95C79B87874CCA457AA7348810A697D9984AC9C3`
- component tests: `DAEE3A8C301B5A4A52157D889D3F9401A0BB41BFE4B7BB002B4C565ED43F25D1`

Parent runner bundle:
`D:/Projects/finlens-annual-mobile-readability-614e75a2ce1a4c38aa5d8fdac76e6654`.
Reuse its final owned-telemetry join, phase freshness, process capture, host CLI
supervision and artifact/cleanup gates. Earlier desktop diagnostic proposals are
not the source for the new execution proposal. Old snapshots/evidence stay intact.

## Constraints

Only new `frontend/e2e/comparison-gap-filter.spec.ts`, necessary one-list mobile
registration in `frontend/playwright.config.ts`, this plan and a fresh external
snapshot/proposal. No edits to the four pending QA files or reviewed filter
component/tests. No backend/API/auth/rights/security/dependencies or Git writes.
Never inspect/hash `backend/.env`. No network, installs, services, containers,
browser execution, review dispatch or self-review. Report approval blocks promptly.

## Non-goals

Production data/eligibility claims, physical-device/assistive-technology acceptance,
full D9 completion, export activation, general test framework changes or Git delivery.

## Implementation stages

1. Verify baseline, allowed source inventory and exact established runner controls.
2. Add isolated spec and mobile registration using unchanged Scenario/catalog.
3. Run scoped offline lint/type/discovery and existing harmless support checks.
4. Freeze an explicit source inventory plus current overlays into a new owned root;
   pin hashes, preserve parent support and select only desktop2/mobile1.
5. Hand hashes, exact proposed command and limitations to coordinator. No runtime.

## Decisions

- 2026-10-31: Original fixture gate identified that annual constructors mark all
  four ratios unavailable. Coordinator explicitly authorized one all-available
  response constructor only inside the new spec. Reuse existing source/period/
  pin shapes and the existing synthetic zero-ratio observation. This response
  tests the UI/protocol; it does not assert financial formula or source eligibility.
- Overrides are exact annual endpoints for the participating AAA/BBB identities
  and supported years. Discovery remains constructor-derived. Invalid-source
  identity is deliberate and must fail the actual client validator. No shared
  fixtures change. Additional CCC comes only from the existing opt-in catalog.
- The small feature needed no plan; this multi-stage frozen execution preparation
  does, under `.agent/PLANS.md`.

## Discovered issues

The initial zero-gap fixture blocker is resolved by the explicit bounded
test-only constructor authorization above. Nothing changes export's C9 blocker.

## Progress

- [x] Required source/policy/baseline inspection; new spec path has no collision.
- [x] Located current bounded desktop/mobile runner including telemetry cleanup.
- [x] Spec and minimal configuration registration.
- [x] Scoped lint/type/discovery, constructor checks, QA52 and support111 passed.
- [x] Final frozen snapshot/proposal integrity and preservation validation.
- [ ] Coordinator-controlled focused independent review.
- [ ] One isolated runtime only after review PASS and separate approval if required.

## Test and validation strategy

Run new-spec/config ESLint, scoped no-emit/nonincremental TypeScript and Playwright
discovery only; discovery must list exactly desktop2/mobile1. Run existing QA
harness offline tests and copied harmless runner support checks after inspecting
them. No test command may launch Playwright browsers, Docker or a server. Record
actual commands/results and any initial failures below. Final preservation checks
compare all prior hashes and HEAD/index/status. No browser result is implied.

## Completion criteria

Reviewed new spec, exact three-case discovery, offline checks, deterministic pinned
source/support/proposal manifest, prior byte preservation and coordinator handoff.
Execution acceptance remains a later gate with actual report/artifact/cleanup proof.

## Final outcome

Prepared three browser cases in the new spec. The only configuration delta is
adding `**/comparison-gap-filter.spec.ts` to the mobile project's `testMatch` list;
all other project/runner settings remain unchanged. No reviewed component/test
or shared fixture was edited.

Actual offline checks, from `D:/Projects/finlens-foundation/frontend`:

- `.\node_modules\.bin\eslint.cmd e2e/comparison-gap-filter.spec.ts playwright.config.ts`:
  exit 0, no diagnostics.
- Installed TypeScript compiler API with roots `e2e/comparison-gap-filter.spec.ts`
  and `playwright.config.ts`, tsconfig options plus `noEmit: true, incremental:
  false`: exit 0, zero diagnostics, no generated output.
- `node node_modules/@playwright/test/cli.js test e2e/comparison-gap-filter.spec.ts --list --reporter=list`:
  exit 0, exactly desktop2/mobile1. Discovery starts no server or browser.
- AST-extracted actual `syntheticAllAvailable` and `annualRequest` functions,
  real fixture constructors and real `validateAnnualResponse`: 11 checks passed
  covering AAA/BBB, 2024/2025, all 11 available statuses with supplied source
  shapes, original monetary values, rejected source-CIK mutation, exact endpoint,
  pin/method/year/query/identity refusal. No application or network calls.
- `node --test tests/qa01-harness.test.mjs`: ordinary run failed before test bodies
  with worker `spawn EPERM`. Required escalated retry was requested through the
  approval tool and completed exit 0: 52 passed, zero failures/skips/cancellations.
- Existing comparison component suite was not rerun: its code/test bytes remain
  the reviewed 272/272-passing candidate from the prior task. That historical
  result is not a browser result for this new spec.

New owned bundle:
`D:/Projects/finlens-comparison-gap-browser-3a9e4aa567934785a061e77441c1a437`.
Its 44 source files total 1,582,835 bytes. Source aggregate SHA-256:
`89BCA2427AFDA6E5C122340D131F7C4E947EAE83666E9081A6719BAB13E2932A`.
It contains the prior four QA files, both reviewed filter files, the new spec,
the minimally changed configuration and the parent's remaining frontend inputs.
The parent snapshot's HEAD-blob next-env and external diagnostic/telemetry helpers
are retained; repository next-env stays protected and is not copied as an overlay.

From repository root, ran the bundle's `proposal-offline-checks.ps1`: first run
passed 31 host and 22 capture checks, then a nested Node child failed with EPERM.
Required approval-tool escalation retry ran the same script unchanged: exit 0,
**111 passed** (31 host + 22 capture + 17 provenance + 41 join/phase sequencing).
Only harmless owned PowerShell/Node children and synthetic IO ran. Historical
receipt evidence used by one existing support test was read without mutation;
no historical PID was accessed and no Docker CLI was launched.

Generation correction: an initial PowerShell dictionary aggregation yielded a
missing total-byte pin. Corrected it by explicit integer summation before support
validation; no proposal execution occurred. PowerShell parsing of proposal and
support passed, and the inline Node program compiled with `vm.Script` without
execution. Tracked `git diff --check` emitted no whitespace diagnostics; untracked
spec/plan no-index checks likewise emitted no whitespace diagnostics (diff status
1 for the added files). Ordinary LF/CRLF warnings are preserved, not conversions.

The copied proposal changes only frozen source identity/count/byte/aggregate pins,
explicit frozen worktree-status inventory (including new untracked paths), selected
spec/title identities, desktop expected case count, scope label and offline
selection assertions. Image, no-egress, mounts, resources, all deadlines, host CLI
reaping, process/phase identity, telemetry join, artifact limits and owned cleanup
remain inherited. The six optional WASM-support dependencies remain explicitly
`UNVERIFIED_OPTIONAL_DEPENDENCIES`; no installation or new acceptance was inferred.

Review requirements: exact new spec and synthetic constructor scope, meaningful
rendered geometry/keyboard/touch assertions, current source/config deltas, explicit
44-file inventory and eight overlay hashes, protected hashes/status list, exact
desktop2/mobile1 selectors and unchanged bounded execution controls. No code
self-review or review dispatch was performed. Coordinator controls independent
review and later runtime. The final literal manifest-hash command is supplied in
the engineering handoff after final plan/hash preservation checks.

No browser/container/service/network/install/Git write or backend/.env inspection
occurred. Source-rights/export policy was not changed; the blocked export plan is
unchanged. Browser/mobile/real-data/runtime acceptance remains pending.

Final offline integrity validation passed: exactly 44 source / 48 total files,
1,582,835 source bytes, matching aggregate and per-file size/hash records, eight
current overlays, five protected-path hashes, unchanged HEAD/main/empty index and
exact expected worktree status. The host CLI module, provenance observer,
telemetry join and copied launcher match the parent bytes. Docker create/resource/
deadline block and resource manifest match the parent. All parent evidence stays
untouched. Only this slice's new spec, one configuration line and this plan were
added/changed in the repository; pre-existing candidates remain separate.

Suggested commit once independently accepted and requested:
`test: cover annual comparison coverage filter in browsers`.

## Astra P2 selector correction — 2026-10-31

Review turn `01a190d3-a043-7230-91b3-564a5afc9f8a` found that the proposal's
`--grep '^coverage gaps:'` cannot match Playwright full titles, which include
project/file prefixes. The earlier bare three-case discovery did not validate
those final phase selectors. No browser execution had occurred.

Removed only the leading caret from the two copied proposal grep literals and
the actual corresponding support assertion. Manifest phase selections, proposal/
support size/hash pins and correction/review metadata were updated. The 44 source
files, source aggregate, exact file/project selection, expected case titles/counts,
runtime bounds and cleanup controls are unchanged. This plan is the sole repository
file updated for this correction; all existing candidate/protected hashes remain.

Exact independent discovery commands actually run from
`D:/Projects/finlens-foundation/frontend`:

```powershell
node node_modules/@playwright/test/cli.js test e2e/comparison-gap-filter.spec.ts --project=desktop-chromium --workers=1 --retries=0 --max-failures=1 --reporter=list,json --grep 'coverage gaps:' --list
node node_modules/@playwright/test/cli.js test e2e/comparison-gap-filter.spec.ts --project=mobile-width-chromium --workers=1 --retries=0 --max-failures=1 --reporter=list,json --grep 'coverage gaps:' --list
```

Both exited 0. Desktop discovered exactly the two expected desktop titles; mobile
discovered exactly the expected 390px title. JSON reports contain zero errors and
empty execution results; their listed/skipped entries are discovery, not browser
test passes. No server or browser was started.

Scoped offline checks: extracted and executed the actual changed support test
callback, including selector/project/count/spec assertions; PASS. Reinstating only
the two runner carets reproduces prior runner SHA-256
`A21D85329159997FDBBD26608C12474C5B6ADC181E2B82537868372F0170929E`;
reinstating only the support assertion caret reproduces prior support SHA-256
`368DB9158FF2C3EDE7D85AA7928DE2691A31E2AEF8C97C26749E6BE9280A7C38`.
This proves the exact executable/support byte delta. PowerShell parsing and inline
Node compilation passed without proposal execution. No unchanged QA52/support111
suite rerun, escalation/approval request, browser/Docker/network/install/Git write
or .env inspection occurred. Prior full offline results above remain historical.

Ready for coordinator-controlled targeted P2 re-review after final manifest/plan
repinning and preservation checks; execution remains pending review PASS.

## Final accepted execution and delivery closure — 2026-10-31

This appended entry supersedes the earlier pending-review/execution statements
for this bounded filter slice. Earlier preparation/failure/discovery records are
retained as historical evidence. Coordinator confirmed Astra selector re-review
PASS in turn `01a190d7-59ac-79f1-8f1e-4d9999530fd7`, following earlier accepted
component/spec reviews. The separately authorized actual browser run is turn
`01a190d8-0140-7332-ab4e-3f37decdc395`.

Executed exactly once from `D:/Projects/finlens-foundation`:

```powershell
pwsh -NoLogo -NoProfile -NonInteractive -File 'D:\Projects\finlens-comparison-gap-browser-3a9e4aa567934785a061e77441c1a437\acceptance-proposal.ps1' -ExpectedManifestSha256 '2FA17256ABA0A6A0E7EB775E724587D919CB81B5185F5DB3D8845F6015DFC39A' -AcceptOptionalDependencyRisk
```

Preflight found no overlapping active local task and verified the reviewed
manifest/proposal/support, all 44 source files, eight overlays, five protected
paths, main/HEAD, empty index and exact worktree status. The approval-tool request
for Docker access was approved; only that attempt ran, with no alternate command
or retry. Actual terminal exit was 0 and final outcome **PASS**.

Actual report results: desktop **2/2 passed**, mobile **1/1 passed**, zero failures,
skips or retries. Desktop duration 11,213.204 ms; mobile duration 8,006.145 ms.
Coverage includes gaps/counts, exclusions/raw reasons, zero/reset, unknown-source
refusal, copy eligibility, company-scope reset, keyboard, rendered containment and
390px touch emulation. No live-data, physical-device, full accessibility, complete
D9, source-rights or export acceptance is inferred.

Run nonce: `3a58f6d5d48e4b1fa61eb2a81b1cabca`.
Owned container: `ecb75c637e6f867bba94edc40a949da5799ca05be06197c17a020b6dc9580189`.
Artifact root:
`D:/Projects/finlens-annual-browser-artifacts-3a58f6d5d48e4b1fa61eb2a81b1cabca`.

All six final gates passed: testEvidence, artifacts, containerAbsent, preservation,
proposalPreserved and hostClisReaped. Both phase cleanups and final cleanup were
verified: ports 3107/3108 closed, zero extra live processes, zero QA temporary
copies, dependency link and owned runtime root removed. Exactly one foreground
attach and ten successful reaped host CLIs were recorded. Owned removal was
followed by empty exact-container-ID and exact-name listings. Both creation-bound
telemetry helpers were observed gone without signals. Image-code attestation
matched all seven references under Node v24.21.0.

The exported payload contains **23 files / 63,428 bytes**; all indexed sizes and
SHA-256 values were verified against the receipt-bound index. Key evidence:

| Artifact | SHA-256 |
| --- | --- |
| overall-result.json | C9BB2C1E302697E84CFC31B9252BDE3C9B1A01400BA4FE4BBE7EBF11B1AE6E12 |
| artifact-index.json | 8BBF989BD2DB58FD5ABB8F39E060132FD23197172916554C47958C0906A6D68A |
| receipt.json | 6BA57DFAB212E02D5047E900E09D4F2645DE9E608EDA3BAD3C86373BB28179C4 |
| ownership-intent.json | 14A56B32160CEB536B96394D17CDB565E54EA77AA3F9128A47E5CC0B9875E8F2 |
| desktop/results.json | 885896F9D2019C0B8EB6DA58A2DB31914D7BAE9CC2F872C05D06044F84DDFE7D |
| mobile/results.json | 6EDC02936DD6DF68180E3F3B7DD396295290AA560C74DEECEE0AA253FB7F59E6 |

Preserved runtime limits: pinned image
`sha256:381859e085dbc2652dedc773a14dadbad4f291bb7dda578d71079335862ce612`,
UID/GID 1001, no egress or published ports, read-only image, dropped capabilities
and no-new-privileges; 2 CPUs, 4,096 MiB RAM, zero additional swap, 256 PIDs,
512 MiB shared memory; tmpfs 2,048 MiB runtime / 256 MiB artifacts / 256 MiB tmp.
Workload 600s plus 20s termination grace and separate 90s cleanup allowance.
Host CLI deadlines metadata/create/attach/stop/reap are 15/30/650/23/3s.
Artifact limits remain 128 files, 64 MiB/file and 256 MiB total; per-phase capture
2 MiB per stream, host capture 1 MiB per stream, stdin 128 KiB and local logs 4 MiB.
The six optional WASM support packages remain `UNVERIFIED_OPTIONAL_DEPENDENCIES`;
the explicit risk switch applied to this attempt only. Nothing was installed.

Validation chronology remains precise: component suite **272/272**, QA harness
**52/52**, and copied/adapted support **111/111** passed before the final two-anchor
selector correction. After that correction, both exact phase-selector discoveries
and the changed actual support assertion passed; the full support suite was not
rerun. This closure performs no test, discovery, browser or support rerun.

Post-execution checks preserved all repository candidates/protected hashes and
the reviewed snapshot, main at `d6a9e42ce8571bec5450b06fed97d829d6b1272f`, empty
index and exact worktree status. No repository file changed during execution.
The current separately authorized closure appends only this plan. Its pre-closure
SHA-256 was `27AFC52C74868C0A01E40AEF481073C1BA06B7248094A1C7C4D4DA0F05031941`.
The reviewed external manifest and run artifacts remain unchanged and bind the
pre-closure plan bytes; they are not repinned or rewritten after acceptance.

Manual delivery remains two separate batches. First: the four prior QA files
`frontend/e2e/comparison.spec.ts`, `frontend/e2e/fixtures/browser.ts`,
`frontend/e2e/fixtures/data.ts`, `frontend/tests/qa01-harness.test.mjs`.
Second: filter component/tests, the new gap-filter spec, Playwright mobile
registration and this plan. The second batch's browser spec depends on the first
batch's opt-in catalog/Scenario constructors. Exclude `frontend/next-env.d.ts`, the
two historical backend reports, blocked export plan and all external bundles.
No staging, commit or push was performed. Suggested manual commits:
`test: strengthen annual comparison browser coverage`, then
`feat: add annual comparison coverage filter`.
