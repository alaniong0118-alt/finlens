# REL-PRODUCT-03 portable synthetic research walkthrough

Status: active; implementation/static verification only
Review state: Astra FAIL / NOT READY for Git Step 2 on the initial candidate;
two P2 evidence-integrity corrections are authorized within the same six paths.
Roadmap phase: bounded portfolio evidence preparation; no new product milestone

## Objective

Prepare one separately discoverable Linux Playwright capture journey and a default-off
CI path for exactly four labelled PNGs, the actual native clipboard Markdown bytes,
an offline viewer and a SHA-256 manifest. Browser/CI execution and Git publication
are NOT authorized. Independent Astra High review is the next delivery gate.

## Current architecture and context

Repository HEAD: `2e45d04b2adec942d90c3548c3a104a990c7f249` (verified).
The coordinator supplies accepted Ubuntu Chromium evidence of 78/78 PASS; this
task does not rerun or independently query that acceptance. Reuse the existing
frontend, e2e fixtures and Linux owned-process launcher. See
[existing browser guide](../../browser-e2e-testing.md) and
[portable showcase](../../showcase/minimum-portable-showcase.md).

Entry index empty. Only protected exceptions:

| Path | SHA-256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

## Constraints

Exactly six scoped paths: this plan, one showcase addendum, one capture-only .ts
scenario, one config, one .mjs packager, and the existing frontend E2E workflow.
No production, backend, fixture, acceptance-test, dependency or historical-evidence
changes. No browser/services, backend import, SQL/PostgreSQL/Docker, SEC/provider,
dependency installation, CI execution, staging/commit/push/cleanup or private .env
reads/hashes. Additional files or altered product behavior require coordinator approval.

## Non-goals

Reacceptance of QA-01, REL-ACCEPT-02C or SEC-LINK-01; live-data/SEC correctness;
native Windows execution; clearance of historical FAIL/BLOCKED/NO-GO boundaries.

## Implementation stages

1. Verify instructions, baseline, protected hashes and existing harness contracts.
2. Prepare capture config/scenario with unchanged synthetic AAA/BBB observations.
3. Prepare strict packaging and default-off, acceptance-dependent CI job.
4. Run source/static checks only; inspect scope, candidate bytes and preservation.
5. Stop for independent review. Future execution requires separate authorization.

## Decisions

- 2026-10-24: Name the scenario `research-walkthrough.capture.ts`, which is outside
  ordinary Playwright `.spec`/`.test` discovery. Dedicated config selects only it.
- Capture annotations label synthetic data inside each PNG; annotations never
  replace financial content or production components. The fourth full-page PNG
  retains both the real copy feedback and expanded freshness limits.
- Preserve clipboard UTF-8 bytes in an independent raw file. Viewer escapes text;
  it does not render Markdown links or request SEC-shaped synthetic destinations.
- Use a fresh, fixed ignored output subtree; reject existing package/raw outputs,
  symlinks, unexpected inputs and incomplete/failed run evidence. No cleanup tool.
- The manual boolean input defaults false. No capture/upload on ordinary push/PR.
- Source review of the installed Playwright runner showed graceful close resolves
  on process close without checking its exit code. The dedicated config therefore
  uses a small wrapper in the already authorized packager to run the unchanged
  launcher, forwarding shutdown to its owned child. A zero-exit cleanup receipt
  binds revision, launcher hash and capture interval; missing/failed receipt blocks
  packaging. No existing launcher or process-group implementation is changed.

## Discovered issues

Existing success screenshots are not generally retained, and routine CI uploads
failure diagnostics only. The new job must not change those existing contracts.
Synthetic freshness says current using fixed timestamps; captions must explain it
does not establish live currency. Historical manifests stay untouched.
Source review also corrected the period selector to its actual snapshot location,
and explicitly creates/checks the ignored parent directories rather than assuming
Playwright creates output directories before the scenario. These are static
corrections; no browser failure or runtime success is claimed.

## Progress

- [x] 2026-10-24: Instructions, HEAD, empty index and three protected hashes verified.
- [x] 2026-10-24: Capture/config/packager/workflow/addendum prepared within six-file scope.
- [x] 2026-10-24: Static verification and self-review recorded below.
- [ ] Independent Astra High review.
- [ ] Separately authorized Ubuntu capture, artifact inspection and human rehearsal.
- [x] Correct P2-1: admit and recheck every copied render input against reviewed Git bytes.
- [x] Correct P2-2: bounded complete PNG chunk/CRC/inflate/pixel validation and adversarial probes.
- [x] Harden Boolean CI opt-in; revised hashes reported at handoff for independent re-review.

## Test and validation strategy

Allowed: Node syntax, in-memory packaging invariants, non-emitting TypeScript,
scoped ESLint, config/discovery listing without browsers/services, workflow gate
inspection, Git diff/whitespace and SHA-256 checks. Never run the launcher,
isolation command, production build or browser test in this task.

### Checks actually executed (2026-10-24)

Working directory `frontend/`, using installed tools only; no dependency install:

- `node --check scripts/package-research-walkthrough.mjs`: PASS.
- `node scripts/package-research-walkthrough.mjs --check`: PASS. In-memory path
  rejection, schema/result mutation rejection, cleanup receipt rejection, SHA-256
  known vector, UTF-8 preservation/rejection, HTML escaping/CSP, four-image output
  completeness and null CI identity. Probe objects are never written as evidence.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`: PASS.
- `node node_modules/eslint/bin/eslint.js playwright.capture.config.ts
  e2e/research-walkthrough.capture.ts scripts/package-research-walkthrough.mjs`: PASS.
- `node node_modules/playwright/cli.js test --list --reporter=list`: 78 tests in
  five original spec files; capture absent. Discovery only, no test/browser run.
- Capture config `--list --reporter=list` with the capture switch unset: expected
  exit 1 with default-OFF refusal. With the switch true in that listing process
  only: one capture test in one file. No scenario body/launcher/service executed;
  the switch for listing does not constitute execution approval.
- In-memory `js-yaml`/Node inspection: original acceptance job, push/PR triggers,
  permissions and concurrency deep-equal HEAD. Eight conditional-gate cases PASS:
  push/PR, opt-out, blank/wrong SHA, failed/skipped acceptance refuse capture;
  matching manually opted-in successful acceptance admits the future job.
- Git source comparison: production app/components/lib, existing fixture/spec/test,
  package/lockfile, base config, launcher/process-group and historical showcase
  paths have zero diff. No `test-results/research-walkthrough` subtree exists.
- Read-only inspection of installed Playwright implementation confirmed JSON
  report/result fields, deferred report write, deferred output-directory creation
  and the graceful-close exit-code limitation. No installed source was modified.

Root Git whitespace, exact combined candidate diff/stat/hash, empty index and final
protected hashes are verified at handoff. The candidate SHA-256 is reported in the
engineering handoff rather than embedded here (which would make it self-referential).
It binds the concatenated Git-format diffs for these six relative paths in ordinal
order, using `core.autocrlf=false`: tracked HEAD diff for the workflow, no-index
`/dev/null` diffs for the five additions. The patch is composed and hashed in memory;
no patch artifact, index update or extra repository file is created.

The first candidate-hash inspector incorrectly applied `core.autocrlf=false`
whitespace checking to the entire worktree, treating the protected pre-existing
CRLF next-env file as added whitespace. It stopped before hashing. The corrected
inspector uses ordinary full-worktree `git diff --check` and raw-byte checks only
for candidate paths. The protected file was neither normalized nor modified.

## Completion criteria

### Astra P2 correction record — 2026-10-24

Initial candidate patch SHA-256:
`daa02208e2e9dca308d9171a85a1c1a449c7ec6af06c33c5e61054d63d6eb230`.
Coordinator supplied Astra FAIL / NOT READY for Git Step 2. That classification
remains the initial candidate's historical result; this correction is not an
independent acceptance or Git authorization.

P2-1: Enumerate every copied file/directory using the unchanged launcher's exact
12-root inventory and reviewed Git tree. Reject extras (including untracked optional
config/assets), missing/changed bytes, types, executable bits and symlinks. Bind
relative identities, byte counts and SHA-256 into a revision-bound inventory and
admission-file hash; compare before launcher spawn, after verified launcher exit,
and independently during packaging. Admission checks the actual launcher against
reviewed bytes and pins its copy policy to the unchanged baseline. Exclude private
environment names/subtrees before stat/read/hash. No next-env exception exists.
Limits: 4,096 entries, 512-byte paths, 10 MB/file, 64 MB source content. Inventory
does not cover linked dependency bytes or prove an atomic temporary-copy snapshot;
trusted fresh Linux dependencies and a quiescent source tree remain prerequisites.
Concurrent replacement/change-and-restore is not claimed to be prevented.

P2-2: Strict bounded PNG chunk/order/CRC validation; required consecutive IDAT;
Node zlib exact-length decompression with compressed-input consumption check; full
filter reconstruction for 8-bit RGB/RGBA; decoded pixel hash in manifest. Unsupported
features fail closed, original bytes remain untouched. Caps: 20 MB encoded, 4,096
chunks, fixed 1,440 width, bounded height and 128 MiB decoded. Package preparation
and success publication are separate; rejection cannot call the manifest writer.

CI: `toJSON` of the opt-in must equal the string `true`, excluding numeric/string
truthy values under loose GitHub equality. All other guards/defaults stay intact.

Correction checks actually executed, using installed tools only:

- Node syntax, non-emitting TypeScript and scoped ESLint: PASS.
- `--check`: PASS. Clean source admission binds the intended revision; modified,
  extra, missing/changed inventory, wrong revision and protected modified next-env
  fail. Instrumented in-memory private env entries are never opened or hashed.
- Four independent complete RGB/RGBA PNG positives: PASS; all filters, Paeth
  diagonal selection, split IDAT, known decoded hashes and unchanged original bytes.
- Twenty-five malformed PNG/decode/resource negatives: rejected, including exactly
  45-byte IHDR/IEND without IDAT, bad CRC, compressed truncation/corruption, trailing/
  concatenated streams, wrong row geometry/filter, unsupported formats, malformed
  chunks/order/types/dimensions and decoded-size limit. In-memory publication
  gates show invalid inventory/PNG never invoke success-manifest writing.
- `--admit-check`: expected exit 1, specifically `Render input differs from reviewed
  commit: frontend/next-env.d.ts`. This is local NO-GO, not clean Ubuntu acceptance.
  The protected file was neither edited, normalized, restored nor excepted.
- Workflow structural checks and 351 Boolean-type/event/SHA/result combinations:
  PASS. Original acceptance job, push/PR triggers, permissions and concurrency
  deep-equal HEAD; capture remains default OFF. No capture output subtree exists.
- No Playwright discovery or browser runtime executed in this correction task.
  Original fixtures/tests remain unchanged; the prior 78-case discovery record
  is historical, not a new browser result.

Final whitespace, six-path candidate hashes/diff statistics, expected HEAD, empty
index, original protected hashes and unchanged out-of-scope source are checked at
handoff. No new repository file, dependency or launcher modification is introduced.

Six-file scope; no production or accepted test changes; default suite still 78
cases and capture separately one case; restrictive packaging; honest provenance;
static checks pass; protected hashes/index preserved; explicit review handoff.
Execution acceptance remains pending even when source is ready for review.

## Final outcome

Revised implementation and static verification: READY FOR INDEPENDENT ASTRA RE-REVIEW.
Independent acceptance remains PENDING; stop before Git Step 2. Local capture
remains NO-GO because protected next-env is not reviewed HEAD content.
Plan remains active: independent review, browser/CI execution, image legibility,
native clipboard capture, real Linux wrapper/receipt lifecycle, package generation
and timed rehearsal remain NOT EXECUTED / NOT VERIFIED. Static discovery is not
runtime acceptance. No screenshots, exported note, execution manifest or timestamps
were generated. No production/fixture/acceptance-test/historical-evidence changes.

HEAD unchanged; index empty; exactly six candidate files plus the three original
protected exceptions. Protected hashes match entry values. No private .env access,
services, backend, database/Docker/SEC/provider, installation, workflow execution,
Git staging/commit/push or cleanup. Stop for coordinator review; no later milestone.

Suggested future commit (not authorized now):
`test(showcase): prepare gated synthetic research walkthrough capture`.
