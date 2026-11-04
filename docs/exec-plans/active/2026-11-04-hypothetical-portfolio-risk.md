# Bounded hypothetical portfolio risk candidate

Status: active; development candidate implemented and verified; independent review and live-data acceptance pending
Roadmap phase: scoped development integration of requirement 10a

## Objective
Provide an opt-in synthetic-only signed-exposure workflow with exact kernel results and a complete loss/tail receipt, strict bounded HTTP input, and accessible responsive UI. Never claim market history, forecasts, advice or live-data acceptance.

## Current architecture and context
Starting main/HEAD c00c7468306f8aab74bad8da7f562e151da5edcd, empty index. Read root AGENTS.md, .agent/PLANS.md, ROADMAP.md, engineering standards, requirement 10a and the kernel plan. No repository SKILL.md files were found in tracked inventory. Reuse app/portfolio_risk.py unchanged. Existing protected changes: frontend/next-env.d.ts (F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0), two backend reports (A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C; F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C), active annual-comparison-markdown-export plan (018323260C0FD778346DD397CD419E0F2376018DC2FBE3570BFAD37781B16051), completed personal-site plan (2B416A00962794FF97CFDBDCAB1ACDEAB5AFF3623733AC8095359CBC3C84A704).

## Constraints
Default off, development only. Leave restricted admission lists unchanged. No persistence, uploads, external services/network, database access, credentials, installs, infrastructure, deployment, staging, commits or pushes. Do not read/hash backend/.env. Existing protected files must stay byte-identical. Backend testing uses the maintained offline guard runner.

## Non-goals
Market adapters, holdings custody, real-data rights/calendar/FX acceptance, statistical adequacy certification and roadmap completion.

## Implementation stages
1. Inspect contracts and baseline (done).
2. Add strict JSON adapter and opt-in route; preserve exact rational audit, bound transport before parsing and output before publication.
3. Add separately gated page and client component; cancel/invalidate on edits, supersession, timeout and unmount; validate responses before display.
4. Run kernel, adapter, fresh Python-to-TypeScript contract, mounted behavior, lint/type and responsive keyboard browser checks.
5. Review diff and hashes, record actual outcomes and gaps; leave unstaged.
Rollback: remove only new candidate files and the explicit main.py route registration; preserve all baseline edits.

## Decisions
2026-11-04: Keep this candidate separate from company research and release capabilities. Process flag FINLENS_HYPOTHETICAL_RISK=1 plus development admission enables backend; FINLENS_HYPOTHETICAL_RISK_UI=1 enables frontend page server-side. Neither grants release admission. Narrower adapter caps: 8 assets, 120 intervals, horizon 1..20, ordinary exact decimal strings up to 24 digits/12 decimal places, 128 KiB request and 1 MiB response. Existing kernel remains the only financial arithmetic.

## Discovered issues
- Fresh Python/client validation caught Python Decimal rendering exact zero as `0E-18`. The adapter now formats kernel-rounded values with fixed decimal notation; kernel arithmetic remains untouched.
- The first frontend type check rejected BigInt literals under the existing ES2017 target and insufficient reader narrowing. Replaced literals with BigInt constructors and asserted the reader; no tsconfig change.
- Initial test-harness issues included excessively long generated JSON-case IDs, JSDOM input-event dispatch, and a browser alert locator also matching Next route announcements. Added explicit bounded case IDs, immediate onInput invalidation and a main-scoped browser locator. Final checks pass.
- Node test/browser subprocess creation was blocked by the workspace sandbox (`spawn EPERM`); authorized elevated execution succeeded. No automatic approval rejection remains.
- An exploratory broad release-profile run through the strict financial runner produced **190 passed, 9 failed, 2 setup errors, 39 deselected**, plus 103 subtests. The runner deliberately replaces SEC/provider/model functions that those existing tests inspect, and the default pytest temp-root ACL also prevented two setups. This is not a passing full release suite. Re-ran only the compatible, relevant route/admission matrix: **43 passed, 122 deselected**. No production code was changed to bypass the guard.
- A C-drive temporary copy with D-drive dependency junction failed Next module resolution. Preserving symlinks then failed Next loader initialization across existing pages. A source-only copy under the ignored D-drive `build/` directory resolved this; final production build passed. Next emitted circular chunk dependency warnings; these remain warnings, not a clean warning-free build.
- Screenshots exposed weak unstyled buttons and split 18-place mobile values. Reused existing primary/secondary classes and widened result cards; the final build/browser checks and screenshot inspection pass.
- Independent review and real-data commissioning remain separate gates.

## Progress
- [x] Baseline, contracts and protected exceptions inspected.
- [x] Adapter and HTTP tests.
- [x] UI, cross-language and lifecycle tests.
- [x] Browser, targeted regression and final preservation verification; candidate remains unstaged.

## Test and validation strategy
Record exact commands and outcomes below. Test coercion/malformed/duplicate JSON, caps, ties/fractional/sparse tails, signs, complete/missing observations, horizons and overlapping windows; compare adapter to actual kernel. Fresh Python output must pass client validator. Mounted tests exercise ignored aborts and malformed responses, cancellation, edits, failure and keyboard-accessible controls. Browser checks at 1440 and 390 widths with keyboard. No service access except local frontend for browser checks.

## Completion criteria
Bounded default-off synthetic behavior, precise full audit, no broadened admission, appropriate tests and checks, preserved baseline, empty index and independent-review-ready evidence. Product/live-data acceptance remains pending.

## Actual validation and final outcome

Implementation is complete within the development candidate scope. See
[workflow and API contract](../../hypothetical-portfolio-risk.md) for process flags,
exact schema, resource budgets, assumptions, rollback and reproduction. New code
uses existing FastAPI/React/Next dependencies only. The Python adapter invokes the
unchanged exact kernel; the client validates the receipt without implementing a
second financial estimator.

Actual final commands/results (backend commands run from `backend`, frontend
commands from `frontend`, Git commands from repository root):

1. `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_risk.py tests/test_portfolio_risk.py`: **77 passed, 103 subtests passed**, 1.82s; one installed Starlette TestClient deprecation warning. Guard forbids environment-file reads, live sockets, DB connections, model imports and provider acquisition. No live database was touched.
2. `.venv/Scripts/python.exe -I -S -B tests/test_portfolio_risk.py`: **25 tests passed**, 1.164s, including six references, independent oracle and five actual-source numerical mutants. This is the unchanged kernel's standalone standard-library suite.
3. `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_release_profile.py -k 'real_backend_denies or forbidden_routes_execute or every_reviewed_route_identity or actual_route_inventory or added_alias or structurally_equal_replacement or websocket_is_denied or proxy_rewrite'`: **43 passed, 122 deselected**, 0.56s. Existing route inventories and identity admission checks passed; the candidate is absent from all restricted allowlists. The candidate tests also prove disabled/absent flag rejection before malformed body parsing and both restricted profiles reject.
4. `node --test tests/hypothetical-risk.test.mjs`: **8 tests passed**, 2.876s; captures **11 fresh actual Python responses** and runs all **52 adapter tests** under the offline guard before consumption. Covers exact signs/ties/overlap, malformed/contradictory responses, bounded transport, mounted success/errors, edits, restart, cancellation, timeout, unmount and ignored-abort delivery. No hand-authored response fixture replaces Python output.
5. `node node_modules/typescript/bin/tsc --noEmit --incremental false`: PASS. `node node_modules/eslint/bin/eslint.js . --ext .ts,.tsx`: PASS, including final source. `node --check scripts/verify-hypothetical-risk.mjs`: PASS.
6. `NEXT_TELEMETRY_DISABLED=1 node node_modules/next/dist/bin/next build` in the explicit same-drive temporary source-only copy: **PASS**, including framework lint/types/prerendering. Final candidate is dynamic, 6.11 kB route / 109 kB First Load JS. Existing circular chunk warnings remain. Protected repository next-env.d.ts was never used as a build output.
7. Started only owned loopback Next production instances at 3139 (UI flag 1) and 3138 (UI flag 0) in that copy. `FINLENS_RISK_BROWSER_CHANNEL=chrome FINLENS_RISK_SCREENSHOT_DIR=<task workspace> node scripts/verify-hypothetical-risk.mjs`: **PASS** on installed Chrome **156.0.8078.80**, widths **1440x900 and 390x900**. Default-off route 404; exact tie/fractional/sparse-tail results; short exposure; h=2 overlap; keyboard Enter on both disclosures; no page overflow with full receipt; malformed/server errors; ignored-abort cancel/edit; explicit retry and missing observations. **Zero external requests and zero page errors** were recorded. These are real browser checks against intercepted synthetic Python output, not real backend/data acceptance. Desktop/mobile screenshots were retained in the task workspace and visually inspected.
8. Both owned servers stopped. A listener check found no listeners on 3138/3139. Removed only both verified owned temporary source copies, unlinking their node_modules junctions before recursive cleanup. Shared dependencies remain intact.
9. Final Git/hash/whitespace checks: main at the original full HEAD, empty index, all five protected SHA256 baselines preserved. Kernel and release policy unchanged by Git content checks. Only candidate paths and original exceptions remain. `git diff --check` passes; untracked candidate UTF-8/EOF/whitespace checks are recorded in the final review manifest.

Source scope: backend main.py (five-line registration), new hypothetical adapter
and route, adapter tests; new frontend gated page, component, validator/transport,
mounted contract tests and browser verification script; workflow contract doc and
this active plan. No dependencies, schema, migrations, restricted allowlists,
capabilities, roadmap acceptance statuses or existing financial arithmetic changed.

Remaining acceptance: independent engineering/financial review; real-market
source rights/custody/identity/vintage, exact admitted operands, calendar/action/FX
completeness, statistical adequacy, authenticated ownership, provider/PostgreSQL
commissioning, real-data/API acceptance and release/deployment. Application byte
limits do not configure a proxy ingress cap; per-process admission is not global
rate limiting; client cancellation does not forcibly kill Python work. No public
hosting is authorized by this candidate. Cross-browser/device/screen-reader
acceptance beyond installed Chromium at the tested widths was not performed.

Disposition: ready for independent review of this bounded default-off candidate.
No staging, commit, push, external requests, live DB/provider commissioning,
credentials access, installation or deployment. Plan stays active pending review
and broader acceptance; this does not claim completion of requirement 10a.

Suggested commit after separate review/authorization:
`feat(quant): add bounded hypothetical portfolio risk development workflow`.


## Independent review correction — cancellation ownership (FIX1)

Status: active. Independent review found P2: acquiring the process slot before
AnyIO capacity wait leaked it if cancellation prevented worker entry. The original
implementation results above are historical, not proof against this defect.
On re-entry, main/HEAD/index and all 11 candidate / five protected hashes matched
the original manifest; no unrelated changes appeared.

Plan: use a locked per-dispatch ownership handoff. Request cleanup may release
only while queued; a worker atomically takes ownership before arithmetic and alone
releases after it exits. Cleanup-first races revoke a late worker's permission to
compute, preventing reused-slot overlap or double release. Test real AnyIO capacity
queuing and worker dispatch, cancellation in each phase/repeated cancellation,
late callback entry, actual dispatch-start failure, worker exception and valid
retry. No arithmetic, source labels, resource bounds or admission changes.

Also persist a machine-readable browser execution/request ledger on each future
browser verification run, including individual observed assertions, API bodies,
intercepted reply identity, abort deliveries, source/fixture hashes and outcome.
Previous screenshots and console summaries alone are insufficient independent
proof of the full browser matrix. Preserve prior evidence and exact hashes.

- [x] Safe queued/running ownership and deterministic actual-dispatch tests.
- [x] Durable browser ledger and verification of that harness.
- [x] Focused regression, unchanged-state hashes and re-review handoff.

### FIX1 implementation and actual verification

The route now captures the acquired semaphore in `_SlotOwner`. One threading
lock orders queued cleanup versus actual worker entry. The request's synchronous
finally releases only a queued owner; actual entry changes it to running and the
worker releases in its own finally. Cleanup-first revokes a delayed callback,
which returns without calculation or release. Thus dispatch cancellation/failure
before entry frees admission; cancellation/failure after entry cannot free a
running calculation's slot. Repeated cleanup and post-completion cancellation are
idempotent. No asynchronous cleanup/checkpoint can itself be cancelled. A skipped
worker result cannot be published as an empty success.

New tests invoke the real ASGI route, Starlette `run_in_threadpool`, AnyIO limiter
and actual worker threads. Thread events and limiter queue statistics establish
phase deterministically; no fixed timing sleeps select the race. The ten cases
cover queued and running cancellation with one/three cancellation requests, a
real dispatched callback paused before ownership claim and resumed after slot
reuse, actual `WorkerThread.start` failure, failure after actual worker entry,
completion before cancellation, and both expected/unexpected worker exceptions.
Actual BoundedSemaphore release counts detect leaks/doubles, and each case proves
subsequent valid HTTP retry (the delayed-entry case reuses before old callback exit).

Actual correction commands/results:

- Backend cwd: `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_risk.py -k actual_dispatch`: **10 passed, 52 deselected**, 0.25s.
- Backend cwd: `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_risk.py tests/test_portfolio_risk.py`: **87 passed, 103 subtests passed**, 1.86s. The same single installed TestClient deprecation warning remains.
- Backend cwd: the exact focused release-profile command recorded in item 3 above: **43 passed, 122 deselected**, 0.57s. Restricted admission and source/authority contracts are unchanged.
- Frontend cwd: `node --test tests/hypothetical-risk.test.mjs`: **8 passed**, 3.030s, freshly capturing 11 Python receipts after all **62 adapter/route tests** pass. No financial wire contract changed.
- Frontend cwd: existing `tsc --noEmit --incremental false`, full `.ts/.tsx` ESLint and `node --check scripts/verify-hypothetical-risk.mjs`: PASS. No frontend product source changed during FIX1.
- Rebuilt an owned source-only copy under the ignored same-drive build directory using existing dependencies: production build PASS (same circular-chunk warnings). Started only its loopback frontend instances, no backend, DB or providers.
- Browser harness negative control: set `FINLENS_RISK_BROWSER_URL=https://example.invalid` and an explicit new ledger path. Expected exit 1 (`Loopback origins only`) before Python/browser/network execution. Retained exactly run_started/run_failed/run_finished events. SHA256 `fb95b6f97d387597b53eff55111a26d96bbb99bc64594f198369e87259caf118`.
- First ledger-enabled browser run passed and is retained as historical correction evidence (`risk-fix1-browser-ledger.jsonl`). Then tightened both keyboard disclosure open/visibility assertions and retained a separate final run; no earlier ledger was overwritten.
- Final browser command: `FINLENS_RISK_BROWSER_CHANNEL=chrome FINLENS_RISK_LEDGER_PATH=<task workspace>/risk-fix1-browser-ledger-final.jsonl node scripts/verify-hypothetical-risk.mjs`: PASS at 1440x900 and 390x900 on Chrome 156.0.8078.80. Ledger has **173 sequenced records, 29 passed assertion groups, 40 requests, 40 responses, 20 intercepted synthetic API replies, four confirmed aborted-signal deliveries**, no denied requests, request failures or page errors. Assertions record actual displays, replay JSON, both disclosure open states and visible contents, focus, geometry, errors, cancellation/edit outcomes and retry. Full API request/reply bodies bind to freshly captured Python receipts. This remains intercepted synthetic browser acceptance, not a real-data/API claim.
- Independently parsed the final JSONL: contiguous sequence, one run ID, final PASS/finish, exact expected counts, 14 assertion groups per width plus default-off 404, source SHA256 matches, reconstructed Python-receipt digest matches, every non-malformed API reply matches its Python receipt and exact request echo, all requests loopback, all four late deliveries have aborted signals and zero result count. PASS. Final ledger SHA256: `d710567ae58e3e4b40213196889ae3baa4a51eaffd4e15894faceaa4a9ee76b1`.
- Both owned frontend processes stopped; no listeners on 3138/3139. Removed only the verified FIX1 temporary copy after unlinking its shared dependency junction. Existing dependencies remain intact.

FIX1 changes exactly five existing candidate paths: route, backend test file,
browser verification script, workflow doc and this plan. All other candidate
bytes, all five protected exceptions, HEAD/main and the empty index are preserved.
The final correction manifest outside the repository binds all 11 candidate files,
these five before/after hashes and the retained browser ledgers. No staging,
commit, deployment, installation, external network, live DB/provider or credential
operation occurred. Existing bounds, labels, kernel and admission remain intact.

Disposition: P2 correction implemented and tested; ready for focused independent
re-review. Independent acceptance and all broader gates documented above remain
pending. Prior screenshot-only assertions are historical; use the final JSONL
ledger for independently inspectable browser execution evidence.
