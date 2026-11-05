# Hypothetical factor-panel statistics

Status: active; reviewed candidate integrated unstaged; portable parity correction awaiting independent re-review.
Roadmap phase: bounded additive mathematical continuation of Risk Lab.

## Objective

Use the existing complete, chronological, user-entered hypothetical factor panel
to calculate per-asset cumulative return, maximum drawdown, sample volatility and
covariance per supplied interval. Preserve v1 Risk/Stress receipts, VaR/ES and
receipt replay exactly. Add no source authority, forecasting or investment advice.

## Current architecture and context

Entry main is b05f59d706b4e840ebcbebf34c796628000fe0eb; index empty, ten-file
uncommitted sign-in candidate and five protected exceptions. Root AGENTS.md,
ROADMAP.md, .agent/PLANS.md, existing kernel/adapter/route, frontend receipt and
replay contracts and relevant risk documentation were inspected. portfolio_risk.py
owns exact rational validation, bounds and HALF_EVEN display. The API accepts up
to 8 assets and 120 supplied intervals. Its development-only, default-off route
lifecycle owns the shared concurrency slot and cancellation handoff. The v1 client
and replay reader reject extra fields; those responses cannot be extended in place.

## Constraints and non-goals

Scratch only. No primary or sign-in changes, Docker, database, network, credentials,
dependencies, staging, commit, push or deployment. No portfolio wealth, rebalancing,
cash financing, missing-value filling, annualization or real-market claims. UI is
deferred: this candidate provides a separate bounded backend diagnostic receipt
without broadening the strict v1 browser/download/import contract.

## Implementation stages

1. Capture primary/sign-in/protected preservation and baseline hashes.
2. Add a pure panel-statistics kernel using existing validation/rational bounds.
3. Extract shared request decoding without changing v1 output; add separate
   statistics receipt and default-off development route using existing lifecycle.
4. Test exact references, numerical/resource edges, invalid panels, HTTP admission,
   shared concurrency/cancellation, v1 byte parity and maintained replay regression.
5. Self-review scope, seal patch/hash/test evidence and verify preservation.

## Decisions

- Each supplied interval is one equally weighted observation of r=factor-1.
  Sample covariance is sum((r_i-mean_i)*(r_j-mean_j))/(N-1), N>=2.
  No calendar duration, frequency, independence or annualization is inferred.
- Cumulative return is product(factors)-1, N>=1. Maximum drawdown is the largest
  decline from an earlier normalized asset-factor peak, with initial index 1
  included. This is per-asset normalization, never an invented portfolio balance.
  Boundary 0 precedes interval 0; ties keep the earliest peak/trough witness.
- Signed exposures, declared portfolio value, confidence and horizon do not alter
  these asset statistics. Existing input validation still applies to the shared
  Risk Lab form. No short-position wealth or financing interpretation is added.
- All moments, cumulative returns and drawdowns are exact Fractions. A volatility
  value retains the exact nonnegative variance radicand, with an integer-isqrt
  rounded 18-place HALF_EVEN display; irrational roots are never called rational.
  Tiny nonzero values may display zero; exact operands remain authoritative.
- No observations makes path statistics unavailable. Fewer than two makes sample
  variance/volatility/covariance unavailable. Missing/nonpositive factors, gaps,
  duplicate assets and incompatible currency remain rejected, never dropped.
- Individual arithmetic-bound failures produce explicit unavailable measures;
  covariance uses a common complete panel and symmetric results. Structural and
  aggregate input/operation/output bounds reject the request without partial output.
- Reuse the existing one-slot route lifecycle and release restrictions. Separate
  schema/method IDs leave existing Risk/Stress receipts and replay unchanged.

## Discovered issues

The first full backend run passed 194 tests and 111 subtests. Self-review then
added a third-asset covariance reference and export fixture. The first expanded
pure-kernel run failed one test because its expected cross terms were transcribed
incorrectly. An independent raw cross-product reference yielded 7/600, 1/150 and
-1/120, matching the kernel. Only the test reference changed; that expanded
backend run passed 196 tests and 111 subtests. An explicit main-app registration
control then brought the final run to 197 passed and 111 subtests. This failed test is not counted as
passing evidence. The installed Starlette TestClient emits an existing HTTPX
deprecation warning; no dependencies were installed or changed.

The existing mounted frontend command failed its shared Python fixture hook:
spawnSync returned null status with undefined stdout/stderr. The old hook does
not print result.error, so the precise cause is unverified. All 40 tests were
blocked by that prerequisite; they are not reported as product assertion passes.
No retry, permission change or alternate child-process launch was attempted.
The available room history supplied no new specific permission for that launch.

A separate, source-bound client-format check uses retained actual Python receipts
and explicitly forbids all Node child-process and fetch attempts. It directly
exercises unchanged v1 validators, byte download and JSDOM form restoration:
20 receipts and eight invalid/new-schema rejections passed, with zero forbidden
attempts. This is not a replacement claim for mounted lifecycle/browser acceptance.

## Progress

- [x] Inspect current contracts and instructions; choose independent receipt.
- [x] Capture preservation; implement pure kernel and bounded adapter/route.
- [x] Run numerical/API regression and independent client-format checks; record mounted-suite blocker.
- [x] Self-review and prepare exact artifacts for independent review.
- [ ] Independent review and separately authorized integration.

## Test and validation strategy

Use existing interpreter/dependencies with the maintained offline runner and
in-memory module overlay. No real server, database or upstream request. Verify
hand-calculated products, drawdown witnesses including initial loss/recovery/ties,
sample N-1 variance/covariance, symmetry/PSD, symbolic sqrt exact rounding ties,
zero/one observations, negative/zero exposures, extreme exact numbers and hostile
Decimal context. Verify all panel/transport bounds and retained route admission,
actual-dispatch cancellation/resource behavior. Compare complete original v1
receipt bytes against the unchanged primary adapter and run existing frontend
replay tests with actual backend receipts. UI/browser acceptance is not claimed.

## Completion criteria

Bounded independently reviewable patch, reproducible exact statistics, explicit
unavailable states, unchanged v1 bytes/semantics and release/lifecycle controls,
preserved primary/sign-in state and exact artifact hashes. No live-data acceptance.

## Final outcome

Eight-file proposed repository scope:

- backend/app/factor_panel_statistics.py: new pure, bounded exact statistics.
- backend/app/hypothetical_panel_statistics.py: separate versioned receipt.
- backend/app/hypothetical_risk.py: extract shared decoding; old output unchanged.
- backend/app/hypothetical_risk_route.py: one additive hidden development route.
- backend/tests/test_factor_panel_statistics.py: exact numerical/property tests.
- backend/tests/test_hypothetical_panel_statistics.py: adapter/API/lifecycle/parity.
- docs/hypothetical-panel-statistics.md: definitions, units, limits and API contract.
- this ExecPlan.

From the scratch root, using existing runtime/dependencies and no services:

```powershell
& D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe -I -S -B .\run-offline.py
& E:\node.exe .\check-v1-client.mjs
```

The backend command overlays exactly four candidate app modules onto the maintained
offline runner. The retained execution receipt records sanitized environment names,
commands, times, exits, output hashes and actual imported candidate hashes.
Final result: **197 tests and 111 subtests passed**, no failures/skips; one existing
deprecation warning. It includes unchanged risk/stress adapters and the original
portfolio-risk kernel regression. Numerical controls include 729 exact two-asset
PSD cases and 125 three-asset quadratic forms, hand-calculated drawdowns/moments,
N-1 denominator and negative covariance, symbolic roots and exact rounding ties,
hostile Decimal context, tiny nonzero roots, empty/singleton panels, unequal
durations and independent arithmetic unavailable states. The 8-asset/120-interval
API maximum remains within the response cap. Real AnyIO dispatch tests cover
queued/running repeated cancellation, retained ownership, dispatch/worker failures
and valid retry across the shared slot.

All 45 varied v1 risk requests and all 11 original replay-export fixture variants
produce byte-identical output to the unchanged primary adapter. The separate
zero-child-process client-format check passes 20 actual risk/stress receipts with
exact JSON download bytes and editable-input-only restoration; both existing
replay readers reject the new statistics schema. Actual Python receipt files and
statistics-example.json are retained as synthetic test evidence. The original
mounted frontend command remains blocked as described above. No real browser ran.

Self-review binds the decoder extraction structurally and verifies all prior route
functions/classes, the release policy, main registration and exact VaR/ES kernel
remain unchanged. No frontend files, replay formats or request allowlists change.
Preservation covers 563 tracked non-environment primary files, ten sign-in files,
five protected exceptions and three Git metadata files, unchanged main/status and
empty index. No primary write, Docker, DB, real network, credentials, install,
staging, commit, push or deployment occurred.

proposed.patch, validation.json and handoff.json bind exact raw/LF file identities,
test evidence and remaining gaps. Independent numerical/security/API review is
the next gate; no integration is authorized here. UI/keyboard/narrow/browser,
mounted frontend regression, real-source/custody/calendar/actions/FX, statistical
suitability and live-data acceptance remain outstanding. No roadmap completion
or portfolio-wealth claim is made.

Suggested future commit: Add bounded hypothetical factor-panel statistics.


## Post-integration parity correction (2026-11-05)

Independent review of the integrated candidate identified a test-only defect:
the two v1 parity tests loaded an absolute current-primary adapter path. After
integration that compares the candidate to itself; it also is not portable.
The earlier primary integration run explicitly rebound that oracle to preserved
parent bytes and remains valid evidence, but that harness workaround must not
be required by checked-in tests.

The correction replaces dynamic source loading with a checked-in 56-case golden
fixture generated only from Git commit b05f59d706b4e840ebcbebf34c796628000fe0eb.
Generation verifies exact raw SHA-256 of the original adapter and kernel before
executing those frozen modules in memory. Every case retains its complete input,
expected full response byte length and SHA-256. Test-side fixture provenance,
case counts and SHA-256 are pinned; only fixture CRLF/LF spelling is normalized.
No local primary path, current source fallback or Git installation is needed by
the committed tests. A monkeypatched candidate calculation changes VaR by one
without changing response length; the frozen comparison must reject its digest.

The two modified application files are normalized from mixed CRLF/LF to LF.
Their ASTs and previously reviewed LF Git blob identities are unchanged. No
application logic, numerical or admission behavior changes in this correction.
The portable fixture is the ninth file in the full panel-statistics scope.

The original scratch artifacts remain immutable. Primary integration and this
correction are separately authorized; ten pending sign-in files, five protected
exceptions, all unrelated tracked files and Git index/refs must remain unchanged.
Publication remains forbidden pending independent re-review. Offline verification
results for this correction are recorded below; browser/UI and real-source
acceptance remain outstanding, and the mounted frontend hook blocker above is
not retried or counted as a passing test.


Correction validation: the actual primary modules run through the maintained
offline runner with no oracle-rebinding plugin. The final five-file backend suite
passes 199 tests and 111 subtests, including all 56 frozen byte comparisons, the
same-length changed-VaR rejection, and an in-memory CRLF fixture that loads normally
but rejects a one-field mutation. There is one existing Starlette/HTTPX
deprecation warning. The independent client-format check passes 20 byte-exact
downloads/input-only round trips and eight invalid/new-schema rejections, with
zero child-process or fetch attempts. No mounted frontend or browser run is
claimed. Plain git diff --check now succeeds; Git still reports its existing
autocrlf warnings, and no Git configuration was modified.

Reproduce from the primary backend with the existing interpreter and maintained
guarded runner (the fixture requires no absolute path or Git process):

```powershell
& .venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_panel_statistics.py tests/test_factor_panel_statistics.py tests/test_hypothetical_risk.py tests/test_hypothetical_stress.py tests/test_portfolio_risk.py -s -p no:logging -p no:faulthandler --confcutdir tests -o addopts=
```

The retained correction run-primary-offline.py adds explicit database prohibition
and actual imported-path/hash witnesses, without substituting any module or test
oracle. The nine-file candidate remains unstaged on b05f59d706b4e840ebcbebf34c796628000fe0eb;
the correction changes only the API test, golden fixture, this plan and EOL
spelling of the two already-reviewed app files. Kernel, separate statistics
adapter, numerical tests and contract documentation remain byte-identical to
their independently reviewed candidate. Review exact candidate-manifest.json,
correction.patch and full-candidate.patch before any publication; commit/push
are not authorized by this correction task.

An optional filesystem-relocation test initially stopped during pytest tmp_path
setup: WinError 5 on both the shared temporary root and a dedicated task-local
root. Both failed executions are retained and are not counted as passes.
No permission changes, escalation or retry of those paths occurred. The final
test uses an in-memory read_bytes fixture to test CRLF portability and drift
without filesystem temporary-directory behavior. The repository fixture remains
resolved only relative to __file__; source inspection confirms no absolute path
or import of another adapter. The inaccessible pytest-owned-temp directory is
left untouched as failed-run evidence; no cleanup success is claimed for it.
