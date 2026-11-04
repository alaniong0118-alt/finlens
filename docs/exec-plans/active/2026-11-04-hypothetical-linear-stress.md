# Hypothetical linear price stress and common-shock sensitivity

Status: active; bounded implementation and validation complete, independent review pending
Roadmap phase: bounded enabling slice of requirement 11b, not general stress or live-data acceptance

## Objective
Add named explicit per-exposure shocks and an independent common-shock sensitivity table alongside Risk Lab. Show exact contributions, total P&L/loss, normalized inputs and replay receipt. Clear every stale result on edit/restart/cancel/timeout/unmount. Keep both routes development-only and default-off.

## Current architecture and context
Starting main/HEAD 75852db47cd7f7a864f74792ac9e708d58b8b85a; empty index. Only five existing protected exceptions: frontend/next-env.d.ts, two named backend reports, annual-comparison-markdown-export active plan and personal-site completed plan. Their SHA256 values match the earlier Risk Lab preservation baselines. Recorded an entry manifest outside the repository. Read root AGENTS.md, ROADMAP.md, .agent/PLANS.md, engineering standards, requirement 11b and existing risk adapter/route/client/tests. Tracked inventory contains no repository SKILL.md. No stress implementation exists. Existing exact historical kernel and release allowlists remain immutable.

## Constraints
No external network/services, providers, live DB, credentials/environment-file access, persistence, uploads/downloads, installs, new dependencies, infrastructure, staging, commits, pushes or deployment. Only existing local dependencies and owned loopback frontend instances for browser testing. Preserve unrelated work. Browser verification must retain a machine-readable assertion/request ledger on success and failure.

## Non-goals
Historical market scenarios, source admission, probabilities, forecasts, recommendations, advice, nonlinear instruments, options/derivatives, duration/credit mappings, FX, rebalancing, fees/financing and full requirement 11b completion.

## Implementation stages
1. Verify baseline and contracts (done).
2. Add exact linear mathematical adapter; share existing admission/body bounds and reviewed queued/running worker-slot ownership across both endpoints.
3. Add gated stress page, explicit inputs and audit/sensitivity tables; reuse exact-value/transport validation and existing lifecycle patterns.
4. Test arithmetic, bounds, missing/unsupported inputs, actual dispatch cancellation/concurrency, Python/client receipts and mounted lifecycle. Verify desktop/narrow keyboard behavior with a durable ledger; run relevant historical regressions, types/lint/build.
5. Self-review scope, source labels and hashes; leave unstaged for independent review.
Rollback: remove only new stress files and reverse the scoped route/client/page changes. Do not restore protected or unrelated files.

## Decisions
- 2026-11-04: Method `hypothetical-linear-price-stress-v1`; only explicit `linear_price_notional` exposures. For signed reporting-currency notional E and user shock s in percentage points, P&L=E*s/100 and loss=-P&L. Positive loss means loss, negative loss remains gain. Exact Fraction arithmetic; reuse existing encode/display18 boundary (18 places, HALF_EVEN), without changing the historical kernel.
- Require one declared three-uppercase-letter currency and the identical explicit currency on every exposure; symbols, missing/mixed currency and every other exposure type reject. Syntax is a user assertion, not registry/FX certification. Dates are user assertions, not market pins.
- Bounds: 1..8 distinct assets, 1..12 named scenarios, 1..21 distinct common shock values. Every named scenario must include exactly one explicit shock for every asset, even zero exposures. Ordinary decimal strings retain existing 24-digit/12-fractional-place/26-character bounds. Shocks must be -100..1000 percent inclusive; the upper limit is an application bound, not a suggested scenario. A missing shock never becomes zero.
- Common shocks apply the same explicit percentage to all positions, independently of named scenarios (never added to their shocks). Sort common-shock rows by exact percentage; retain named scenario order. Slope per +1 percentage point is net exposure/100. Offsetting a common shock does not imply no risk. No time horizon, probabilities or VaR/ES interpretation.
- Reuse the existing process-wide slot across both routes, preserving queued cancellation revocation and running-worker ownership. Shared process flags FINLENS_HYPOTHETICAL_RISK=1 and FINLENS_HYPOTHETICAL_RISK_UI=1; no restricted-route additions.
- Proposed 12-file scope: new backend stress adapter/test; existing risk route; existing client risk library with shared exact/transport exports; new stress library/component/page/test/browser script; existing Risk Lab page navigation; new contract doc and this plan. No main.py, historical kernel, release policy or dependency changes.

## Discovered issues
- The existing reviewed Risk Lab files are CRLF Git blobs. Plain `git diff --check` flags new CRLF lines as trailing whitespace. Preserved their existing endings and used a command-local CRLF-aware whitespace configuration plus strict UTF-8/EOF/per-line space checks; no normalization or protected-file edit.
- Isolated Next builds passed with the same circular chunk dependency warnings seen in historical Risk Lab. No unrelated bundling change was attempted.
- Self-review added explicit receipt binding to each original currency/type declaration and a permuted exposure-order case, so shocks cannot accidentally follow sorted row position. No additional product scope or financial model was introduced.
- Browser validation remains synthetic HTTP interception with actual Python positive receipts and controlled malformed/error replies, not live-data or live-backend commissioning.

## Progress
- [x] Baseline and contract inspection.
- [x] Backend and shared lifecycle tests.
- [x] Client/UI and fresh Python contract.
- [x] Browser ledger, regressions and final preservation.

## Test and validation strategy
Use the maintained -I -S -B offline guard runner. Check independent exact long/short/zero examples, -100/1000 boundaries, extreme/context-sensitive decimal controls, unknown/duplicate/missing fields and mixed currency/type rejection. Test cross-route slot exclusion, actual queued/running cancellation and retries; rerun all historical kernel/route ownership tests. Capture actual Python receipts for strict client validation and mounted tests covering ignored abort, errors, restart, timeout and unmount. Browser at 1440 and 390 widths, keyboard disclosures and table scroll, with all API replies synthetic and all external requests denied. Retain ledger/source/fixture hashes. Run types, full lint, isolated production build, source scope/UTF-8/whitespace and protected hashes. Record actual commands/results below; no real DB/provider acceptance implied.

## Completion criteria
Exact bounded typed arithmetic and complete audit; explicit synthetic assumptions; fail-closed inputs and malformed responses; shared reviewed lifecycle/admission preserved; tested responsive keyboard UI; all preservation checks pass; independent-review-ready unstaged candidate. Broader product/live-data acceptance remains pending.

## Actual verification and final outcome

The bounded candidate is implemented in exactly the proposed 12 paths: three
tracked edits (shared route, shared client helper, Risk Lab page navigation) and
nine additions (stress adapter/test, library/component/page/client test/browser
verifier, [method/API contract](../../hypothetical-linear-stress.md), this plan).
Historical math, main.py, release allowlists, authentication/security policy,
providers, database/schema, dependencies and roadmap acceptance statuses are
unchanged. All changes are unstaged, with no commit/push or deployment.

Actual final commands/results:

1. Backend cwd: `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_stress.py tests/test_hypothetical_risk.py tests/test_portfolio_risk.py`: **152 passed, 103 subtests passed**, 1.96s. This includes **65 stress tests**, all 62 historical adapter/actual-dispatch regressions and the 25-test exact kernel suite with independent oracles/mutants. One installed Starlette TestClient deprecation warning remains. The maintained guard blocks environment-file reads, live sockets, DB connections, provider acquisition and model imports.
2. Backend cwd: `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_release_profile.py -k 'real_backend_denies or forbidden_routes_execute or every_reviewed_route_identity or actual_route_inventory or added_alias or structurally_equal_replacement or websocket_is_denied or proxy_rewrite'`: **43 passed, 122 deselected**, 0.56s. The new stress route is not in any restricted allowlist. New stress tests verify absent/default-off flags, both restricted profiles, HTTP boundary rejection, shared cross-route busy states, actual queued/running cancellation, and successful stress/historical retries with different method IDs.
3. Frontend cwd: `node --test tests/hypothetical-stress.test.mjs tests/hypothetical-risk.test.mjs`: **19 passed**, 2.951s. The stress suite freshly runs all 65 guarded Python tests and consumes **nine actual adapter receipts**; the historical suite separately captures eleven receipts after 62 tests. Long/short/zero, precise decimals, lower/upper bounds, malformed and mathematically contradictory receipts, unsupported declaration normalization, exposure order, input edits, restart, ignored-abort success/error, cancellation, timeout, unmount and explicit retries pass.
4. Frontend cwd: `node node_modules/typescript/bin/tsc --noEmit --incremental false`, full `node node_modules/eslint/bin/eslint.js . --ext .ts,.tsx`, and `node --check scripts/verify-hypothetical-stress.mjs`: PASS on final code.
5. Production build in the owned same-drive source-only temporary copy, `NEXT_TELEMETRY_DISABLED=1 node node_modules/next/dist/bin/next build`: PASS, including framework lint/type checks and page generation. Final dynamic stress route **7.57 kB / 114 kB First Load JS**, historical route 6.26 kB / 112 kB. Existing circular chunk warnings remain. Repository next-env.d.ts was never a build output.
6. Owned loopback production frontend instances only: UI flag 1 at 3139 and flag 0 at 3138. Final stress command from frontend: `FINLENS_STRESS_BROWSER_CHANNEL=chrome FINLENS_STRESS_LEDGER_PATH=<task workspace>/stress-browser-ledger-final.jsonl FINLENS_STRESS_SCREENSHOT_DIR=<task workspace> node scripts/verify-hypothetical-stress.mjs`: **PASS**, installed Chrome **156.0.8078.80**, **1440x900 and 390x900**. Real default-off 404, keyboard workflow navigation, signed/zero/decimal/boundary/permuted inputs, all contributions, independent common sensitivity, keyboard horizontal table scrolling, both audit disclosures open/visible, exact receipt, no page overflow, lower-bound rejection/error fixture, malformed/busy states, cancelled and edited ignored-abort deliveries, explicit signed retry, missing shocks rejected before transport. Screenshots were retained and visually inspected; tables are intentionally scrollable on narrow screens with visible keyboard guidance.
7. The unchanged historical browser verifier also ran against this final shared implementation: `FINLENS_RISK_BROWSER_CHANNEL=chrome FINLENS_RISK_LEDGER_PATH=<task workspace>/stress-historical-regression-ledger.jsonl node scripts/verify-hypothetical-risk.mjs`: **PASS**, both widths, all 29 historical assertion groups. No browser package was installed or downloaded.
8. Independently parsed both final JSONL ledgers: contiguous event sequences and one run ID, final PASS/finish, source SHA256 matches, reconstructed fresh Python receipt digest matches, every positive intercepted reply equals its captured Python receipt and exact request echo, every request is loopback, zero request failures/denials/page errors, all four ignored-abort deliveries per suite carry aborted signals and no stale result. Stress: **229 records, 39 assertion groups, 54 requests/responses, 26 API replies**, nine fresh receipts; six of those replies are explicitly controlled malformed/error fixtures. Historical: **179 records, 29 assertion groups, 43 requests/responses, 20 API replies**, eleven fresh receipts. These are intercepted synthetic browser tests, not live API acceptance.
9. Stress final ledger SHA256: `455f042f3f2df984018fce895873d09ef4be198d1df8c21da1b58b732d0347c4`. Historical regression ledger SHA256: `a43aed5171cef1ae7963de2728564eecee06c6960c76479abeaea83e4378f0f1`. The earlier stress ledger is retained as historical evidence; no ledger was overwritten.
10. Stopped both owned loopback servers; verified no listeners on 3138/3139. Removed only the validated owned temporary source/build copy after unlinking the node_modules junction. Shared dependencies remain intact.
11. Final preservation checks: exact starting HEAD/main and empty index; all five protected SHA256 values unchanged; historical kernel, main.py, release policy and all other tracked bytes outside the three planned edits unchanged. All twelve candidate UTF-8/EOF/trailing-space checks and CRLF-aware Git diff checks pass. Exact hashes and both ledger receipts are recorded in the review manifest outside the repository. No environment files were read or hashed.

Self-review: the calculation has one explicit bounded economic model; every
exposure/percentage is retained, no silent zero-fill or row join occurs, and no
rounded value feeds arithmetic. The adapter validates the full panel first.
Client checks bind assumptions and verify the linear contribution/totals before
rendering backend values. The existing locked slot ownership is reused without
changing state transitions; the calculator is injected only at worker execution,
with original historical behavior retained. Navigation and gates remain separate
from private workspace/provider/data admission.

Remaining acceptance: independent financial/engineering review; real economic
instrument suitability and source/data/ownership/custody/calendar/action/FX
admission; actual backend/live DB/provider commissioning; broader browser/device/
screen-reader checks; release/deployment. This implementation does not complete
requirement 11b or establish statistical adequacy. Byte caps do not configure
proxy ingress, the slot is per process, and cancellation does not kill workers.
No external network, real data, live DB/provider, credential, install/download,
Git staging/commit/push or deployment operation occurred in this increment.

Disposition: ready for independent review of the bounded default-off candidate.
Suggested eventual commit, only after separate review/authorization:
`feat(quant): add hypothetical linear price stress and sensitivity`.

