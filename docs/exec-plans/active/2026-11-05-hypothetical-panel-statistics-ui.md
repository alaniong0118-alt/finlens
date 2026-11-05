# Hypothetical panel statistics UI

Status: active; isolated candidate validated; independent review pending.
Roadmap: bounded presentation of the reviewed hypothetical Risk Lab statistics.

## Objective

Use the existing Risk Lab factor form to explicitly calculate and inspect
per-asset cumulative return, drawdown, sample volatility and covariance. Show
synthetic authority, return-ratio units, supplied-interval weighting, insufficient
data and exact audit. Preserve v1 risk receipts, replay and all primary files.

## Current architecture and context

Primary main is b05f59d706b4e840ebcbebf34c796628000fe0eb, index empty. Nine-file
backend statistics candidate and ten-file sign-in candidate remain unstaged.
Root AGENTS.md, ROADMAP.md, .agent/PLANS.md and engineering standards were read.
The reviewed backend provides a separate hypothetical-panel-statistics-v1 receipt
on a hidden default-off development route sharing risk/stress concurrency.
Risk Lab already has a default-off UI, exact factor inputs, abort/generation/
timeout ownership and local v1 receipt replay. Its shared client caps request
and response bytes. No new API proxy or public route is needed.

## Constraints and non-goals

Scratch only. No primary edits, publication retry, staging, commit, push, Docker,
network, real DB, providers, credentials, dependencies or deployment. Do not
change the backend, v1 response validators or replay formats. No statistics
download/import, portfolio wealth, annualization, probability or real-data claims.

## Implementation stages

1. Capture exact primary tracked/untracked/Git preservation and inspected contracts.
2. Add a strict statistics receipt client and accessible result view.
3. Add a second explicit form action sharing existing request lifecycle; keep
   risk/replay output separate and invalidate both on input/import/cancel/restart.
4. Generate source-bound actual Python receipts offline; test malformed contracts,
   states, races, cancellation, keyboard-focusable audit and narrow-safe structure.
5. Type/lint checks, self-review and seal exact patch, evidence and limitations.

## Decisions

- Reuse the existing form and a single request owner; never run an automatic
  secondary calculation. Enter/default submit remains original v1 risk behavior.
- The new view presents ratios directly (not percentages or monetary P&L), uses
  scoped covariance headers and a focusable horizontal scroll region, and retains
  exact normalized input/measure audit through a native disclosure.
- Receipt validation checks method/authority, full input echo and normalized panel,
  asset order, observations/duration units, availability, exact scalar display,
  covariance symmetry/diagonal and symbolic-root display bounds. It verifies
  transport/schema/display consistency, not independent statistical suitability.
- Keep fixed actual Python fixtures in tests, with generation/source hashes in
  review artifacts; no Node-to-Python test child launch or external service.

## Discovered issues

The previous mounted-suite Python child launch and Docker browser access remain
blocked. Neither denied operation will be retried. JSDOM and source/layout checks
are synthetic acceptance only; actual browser geometry and assistive technology
remain a separate gate.

Self-review found an initial test mistakenly called a non-exported replay parser,
so its assert.throws could pass on TypeError. It now exercises the actual async
readReplay with File bytes. An expanded import test initially failed because a
mutated confidence input contradicted its copied result; replace it with a second
actual Python risk receipt. A CSS test expected literal 0px while JSDOM serialized
the equivalent zero as 0; the assertion now checks numeric zero. Failed expanded
runs are retained as pre-review-tests and css-zero-assertion-failure evidence;
they are not counted as passes. No product logic changed to accommodate them.

## Progress

- [x] Inspect contracts, instructions and current state; capture preservation.
- [x] Implement the client, result view and shared explicit action.
- [x] Run focused offline checks, self-review and preserve exact artifacts.
- [ ] Independent review; any integration/publication requires separate authority.

## Test and validation strategy

Use existing Node/Python dependencies. Generate actual backend receipts with
verified source hashes and no config/service imports. Validate empty, singleton,
constant, short/negative exposure, negative covariance, exact/tiny decimals and
arithmetic-bound unavailable results. Mutate response shape, method, authority,
input/panel, counts, units, symmetry, witness, root/rational displays and reasons.
Exercise shared risk/statistics lifecycle, stale replies, edits, import/replay,
timeout, cancellation and unmount. Verify native button/disclosure focus, scoped
table headers and narrow-safe wrapping/overflow in JSDOM/source, explicitly not
a browser-layout pass. Type-check and lint only affected source without emits.

## Completion criteria

Small additive source-bound candidate; passing focused tests and static checks;
unchanged primary bytes/Git state and v1 replay behavior; exact artifacts for
independent review. No real-market or live browser acceptance claim.

## Final outcome

Seven-file proposed repository scope:

- frontend/components/hypothetical-risk.tsx: second explicit submit action and
  statistics state using the existing request owner; shared busy announcement.
- frontend/lib/hypothetical-risk.ts: admit only the one additional fixed endpoint
  in the existing bounded transport; original v1 validator/form parser unchanged.
- frontend/components/hypothetical-panel-statistics.tsx: synthetic asset summary,
  ratio units, availability, drawdown boundaries, covariance and exact receipt.
- frontend/lib/hypothetical-panel-statistics.ts: strict separate receipt validation.
- frontend/tests/hypothetical-panel-statistics.test.mjs: focused contract/lifecycle.
- frontend/tests/fixtures/hypothetical-panel-statistics.json: eight actual synthetic
  Python statistics cases and two actual v1 risk receipts; no external source data.
- this ExecPlan.

Actual verification in the isolated scratch root, using only existing runtimes:

```powershell
& D:/Projects/finlens-foundation/backend/.venv/Scripts/python.exe -I -S -B ./export-receipts.py
& D:/Projects/finlens-foundation/backend/.venv/Scripts/python.exe -I -S -B ./run-offline.py
& D:/Projects/finlens-foundation/backend/.venv/Scripts/python.exe -I -S -B ./run-offline.py --static
```

Final focused result: 63 passed, zero failures/skips. There are 40 malformed
statistics mutations, real empty/singleton/constant/short/negative-covariance/
exact-decimal/arithmetic-limit/eight-asset fixtures, same-origin transport caps
and errors, shared risk/statistics restart and ignored-abort races, cancellation,
edit/stream/timeout/unmount invalidation, v1 exact download/round trip, valid
import cancellation and a held valid file read with an explicit completion
counter. Invalid statistics imports preserve the current draft/result. The
offline guard recorded zero forbidden network or child-process attempts.

TypeScript strict checking of the four affected TS/TSX files and their real
dependencies passed with zero diagnostics, no emits. ESLint passed with zero
errors/warnings. The static compiler host maps only candidate sources over the
read-only primary dependency root; it does not modify or build primary output.
Existing release gates, page, route/proxy configuration, backend, stress and
v1 replay implementations are unchanged. All primary tracked/untracked bytes,
pending sign-in/backend candidate/protected exceptions and Git metadata/status
remain unchanged from preservation-before.json. No stage/commit/push or denied
publication retry occurred.

The tests configure widths 1440 and 390 and verify focusable native controls,
scoped covariance headers, native audit disclosure, wrapping, adaptive grid and
bounded scroll structure. JSDOM does not measure layout, generate browser pixels
or exercise native keyboard/assistive-technology interaction. No actual browser,
full Next production build or whole mounted frontend suite was run. These remain
acceptance gaps; no Docker/access-denial retry, installation or network is used
to overcome them. The new action depends on the separately reviewed unpublished
backend; it does not activate it, and a disabled/missing server returns an explicit
error. No UI integration or publication is authorized by this scratch task.

Review handoff.json, proposed.patch and their exact file hashes before integration.
The two edited existing scratch files are normalized to LF only; retained
normalization-proof.json binds the pre/post raw bytes. The source review patch
uses LF preimages and passes git apply --check --whitespace=error-all against
exact scratch copies of the current primary files, without applying changes.
execution-source.json records actual candidate source/fixture hashes at the final
test launch; primary code is used only for unchanged dependencies and test tools.
Suggested future commit: Add hypothetical asset statistics to Risk Lab.
