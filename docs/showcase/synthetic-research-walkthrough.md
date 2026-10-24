# Portable synthetic financial research walkthrough (REL-PRODUCT-03)

**SYNTHETIC TEST DATA — NOT REAL SEC FINANCIAL RESULTS**

Status: revised after two Astra P2 findings; independent re-review pending. Browser capture, CI,
artifact acceptance and human rehearsal are **NOT EXECUTED / NOT VERIFIED**.
This is an addendum to the [existing portable showcase](minimum-portable-showcase.md),
not a replacement script or acceptance manifest. Expected implementation baseline:
`2e45d04b2adec942d90c3548c3a104a990c7f249`. A future capture must bind the exact
reviewed descendant commit actually executed, never relabel it as a baseline run.

## Approximately four-minute presenter route

| Time | Existing user action and evidence | Explain |
|---|---|---|
| 0:00–0:40 | Select Synthetic Alpha (AAA); PNG 01 shows company and Revenue $1B. | Research Mode works without AI. These are intercepted test responses, not issuer observations. |
| 0:40–1:25 | Expand Revenue sources; PNG 02 retains Jan 1–Mar 31, 2025, exact 1000000000 USD, concept and supplied filing identity. | Period, unit and source identity remain explicit. The SEC-shaped synthetic.htm URL is illustrative, never fetched or presented as genuine filing evidence. |
| 1:25–2:20 | Select AAA/BBB in annual comparison; PNG 03 retains FY2025, $5B/$9B, Jan 1–Dec 31 dates and publications 0/1. | The annual window differs from the quarterly snapshot. Shared fiscal labels do not establish comparability. Do not infer ratios, differences, growth or investment merit. |
| 2:20–3:05 | Copy Revenue research note using native Chromium clipboard. | The viewer shows escaped text from the actual clipboard; its companion Markdown file preserves exact UTF-8 bytes. No generated replacement note. |
| 3:05–4:00 | PNG 04 is a full-page record of real copy feedback and expanded freshness scope. | Fixture current status and check/sync dates are synthetic. Version is not currency; coverage is not guaranteed. Show limits and the no-investment-advice footer. |

Timing is planned, not measured. PNG 04 is intentionally full-page, allowing both
widely separated product regions to remain in one uncomposited record. Scroll or
zoom it in the offline viewer; do not imply both appeared in one viewport.
The capture-only fixed banner is an annotation added by the scenario. No product
component, fixture value, API validator or financial calculation is modified.

## Reuse and evidence boundaries

The capture imports existing [browser interception](../../frontend/e2e/fixtures/browser.ts)
and [AAA/BBB fixtures](../../frontend/e2e/fixtures/data.ts), rendering the normal
frontend with the existing [Linux launcher](../../frontend/scripts/e2e-server.mjs).
The existing 78 acceptance cases, native clipboard/race checks and SEC-link tests
remain independent and unchanged. Capture is an evidence flow, not reacceptance
of QA-01, REL-ACCEPT-02C or SEC-LINK-01. No AI/retrieval action is used.

- Synthetic current-revision UI captures establish only frontend behavior under
  fixed intercepted responses. The deliberately missing/zero history observations
  and other metric fixtures are QA cases, not a coherent financial dataset.
- Historical prepared-data research records can accompany this module only with
  separate historical labels. Reuse existing artifact IDs and hashes from the
  [portable manifest](minimum-portable-showcase-manifest.json); do not modify it,
  infer unknown tested revisions or merge historical numbers with synthetic data.
- Current live database data remains **NOT VERIFIED**. Historical FAIL/BLOCKED,
  original full-showcase limitations, DEP-01A3 and native/live gates remain unchanged.

## Future execution gates — no execution authorized by this document

1. Independent Astra High review and coordinator approval of the six-file candidate.
2. Separate explicit authorization for Git actions and CI execution. Ordinary
   pushes/PRs can already trigger acceptance; permission to implement is not
   permission to publish or execute. No workflow has been dispatched here.
3. Identify the exact reviewed descendant SHA. The manual boolean
   `capture_walkthrough` defaults **false**, and `capture_revision` must equal the
   dispatch SHA. Capture additionally depends on a successful `chromium` job.
4. Use a disposable Ubuntu 24.04 checkout with Node 24, its own locked Linux
   dependencies and installed Playwright 1.64.0 Chromium. No .env, backend,
   PostgreSQL/Docker, provider credentials or SEC requests. Explicitly authorize
   dependency/browser downloads as part of future execution.
   Every copied render input must match that reviewed commit byte-for-byte,
   including `next-env.d.ts`. The protected modified local file has no exception:
   local source admission fails closed and local capture remains **NO-GO**.
5. Keep existing one-worker/no-retry/timeouts, fresh contexts, blocked service
   workers, route/WebSocket restrictions, deny-all upstream and owned-process
   verification/cleanup. Ports 3107/3108 must be free. Native Windows is unsupported.
6. Only a passing capture process, including fixture and webserver teardown, may
   proceed to packaging/upload. Independently inspect all four PNGs, note bytes,
   manifest and offline viewer; then conduct a timed rehearsal. No new live gate clears.

Future approved workflow order: unchanged acceptance job; then an opted-in capture
job performs `npm ci`, existing QA-01 process checks, Chromium installation,
existing isolation check, `npx playwright test --config=playwright.capture.config.ts`,
then `node scripts/package-research-walkthrough.mjs --package`. Both capture and
packaging require `FINLENS_CAPTURE_AUTHORIZED=true` and
`FINLENS_CAPTURE_REVISION=<actual reviewed SHA>`. These are deliberate switches,
not proof that human execution approval exists. No local dependency installation
or execution is authorized by these examples.

## Package contract

Fixed ignored root: `frontend/test-results/research-walkthrough/`. The capture
creates a fresh `raw/` directory with exactly four named PNGs, the native note and
capture metadata. Existing output causes refusal; no cleanup/overwrite command is
provided. A dedicated JSON runner report is read locally and never redistributed
because it may contain private absolute paths.

The capture config uses the packager's small `--serve` wrapper to run the unchanged
Linux launcher. Before launching it, a bounded admission enumerates its exact copy
roots: `app/`, `components/`, `lib/`, `public/`, `next.config.ts`, `next-env.d.ts`,
`package.json`, `tsconfig.json`, both supported PostCSS names and both Tailwind names.
Nested assets/styles and optional roots are included. Expected files/directories
come from the reviewed Git tree; live enumeration rejects changed, missing, extra,
symlinked or unsupported inputs. File identities, executable bits, byte counts and
exact SHA-256 values are recorded in internal `source-admission.json`. Empty
untracked directories also fail. The unchanged launcher and its copy-policy literal
are checked against the reviewed commit and pinned baseline. Private `.env` and
`.env.*` names/subtrees are excluded before opening or hashing, matching its filter.
Bounds: 4,096 entries, 512-byte paths, 10 MB per file and 64 MB total source bytes.

The wrapper forwards shutdown only to that owned child and writes an internal
`cleanup.json` receipt only after an actual zero exit following graceful shutdown.
Playwright's close-event wait alone does not establish a successful exit code.
It re-admits render inputs after execution before issuing the receipt. Capture
metadata binds the admission record and its file hash. Packaging separately
re-admits the live inputs against the reviewed Git tree, compares admission/capture/
execution/package digests and rejects inconsistent or missing inventory entries.
Packaging requires the cleanup receipt, its launcher hash and matching capture interval;
failed/forced cleanup cannot produce a publishable package. Existing launcher
process-group checks, temporary source custody and cleanup remain authoritative.

The packager accepts no user-supplied paths. It checks canonical path custody,
rejects symlinks/nonregular/oversized/unexpected files, verifies the single passing
zero-retry runner result, fully decoded PNGs, native-note digest, capture metadata,
and reviewed committed source bytes. It writes a fresh `package/` containing:

- Exactly four PNGs: company/Revenue, period/provenance, annual comparison, copy/freshness.
- `synthetic-research-note.md`, copied byte-for-byte from the native clipboard file.
- `index.html`, a self-contained labelled viewer with embedded PNGs, inert escaped
  note text, no scripts/external requests and a restrictive content security policy.
- `manifest.json`, written last, hashing the six other output files. An incomplete
  directory without a manifest is not a package. SHA-256 proves byte identity,
  not financial truth or independent acceptance. The manifest cannot hash itself.

PNG admission accepts noninterlaced 8-bit truecolor RGB/RGBA only. It validates all
chunk boundaries, ASCII names, ordering, CRCs, consecutive nonempty image data and
final IEND; only sRGB/gAMA/pHYs ancillary chunks with explicit layouts are supported.
Node's built-in zlib must successfully decompress exactly the declared rows, with
no trailing/concatenated compressed stream. All five PNG filters are reconstructed;
the manifest records a decoded-pixel SHA-256 as well as the original file hash.
Accepted PNG bytes are never rewritten. Unsupported palette, grayscale, bit depths,
interlace, ICC, transparency chunks and animation fail closed. Limits: 20 MB encoded,
4,096 chunks, width 1,440, height 1,000 (fourth image up to 30,000), and 128 MiB
decoded including row filters. The decoded ceiling can further restrict tall images.
Actual Chromium output format and visual legibility remain execution-review gates.

The manifest binds expected baseline and actual captured revision, fixture/harness/
configuration/tooling/lockfile hashes, actual Node/Next/Playwright/Chromium versions,
1440×1000 viewport, light theme, en-US locale, UTC timezone and scale 1. Captures
wait for asserted states and loaded fonts; screenshot animations are disabled.
The fourth PNG can be taller. Byte-identical PNGs across different runtimes are
not promised. Reproduce semantic states and pin the recorded runtime for comparison.

The CI opt-in compares `toJSON(inputs.capture_walkthrough)` with the literal string
`true`; only the Boolean value qualifies, not strings or numbers under GitHub's
loose equality. Manual dispatch, reviewed SHA equality and successful acceptance
are still required, with capture default OFF.

CI run/job/attempt and capture timestamps are populated only during actual approved
execution. For approved non-CI Linux execution, CI fields are null. No completed
manifest, screenshots, note or capture timestamps are supplied by this implementation.
The upload exists only in the opted-in job; ordinary push/PR capture uploads are
OFF. Existing failure diagnostics in the acceptance job retain their original policy.
The 30-day CI artifact is transport, not long-term university-showcase custody;
separately approve retention before expiry. No public release is implied.
Filesystem checks assume a quiescent owned runner. Prelaunch, execution-end and
package checks do not establish an atomic snapshot or protect against concurrent
replacement/change-and-restore during copying. Dependencies remain linked, not
copied; use the reviewed lockfile and fresh approved Linux installation. These
checks do not establish native containment or clear DEP-01A3.

## Static preparation checks

`node scripts/package-research-walkthrough.mjs --check` performs in-memory invariant
checks only: no filesystem writes, evidence generation, services or backend imports.
It includes clean/dirty/extra/missing/private-input admission probes and independent
complete PNG/decode rejection probes, including the former 45-byte no-IDAT input.
`node scripts/package-research-walkthrough.mjs --admit-check` inspects the current
reviewed tree and copied source files read-only, without starting the launcher.
It currently rejects protected `frontend/next-env.d.ts`; do not edit/restore that
file to make the check pass. Clean Ubuntu admission has not been executed here.
Non-emitting TypeScript, scoped ESLint, default/capture discovery listing, workflow
gate checks and Git/preservation checks are allowed by this task. Discovery is not
browser acceptance. Exact executed checks and outcome belong in the
[active ExecPlan](../exec-plans/active/2026-10-24-rel-product-03-portable-research-walkthrough.md).
