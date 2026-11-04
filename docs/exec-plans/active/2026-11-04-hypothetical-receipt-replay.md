# Local hypothetical receipt download and replay

Status: active; implementation and local validation complete; independent review pending
Roadmap phase: scoped enabling workflow for hypothetical risk/stress, without source-export acceptance

## Objective
Download only current validated Risk Lab / Stress Lab receipts as local JSON. Read an explicitly selected bounded receipt as untrusted data, restore editable assumptions only, clear results, and require explicit fresh calculation. Preserve exact input strings and original input ordering.

## Current architecture and context
Starting main e03a1b16ff07a32b942e3c84e92528b781abb051; index empty. Existing exact receipt validators and abort/generation lifecycle remain the foundation. Root AGENTS.md and .agent/PLANS.md apply. ROADMAP status is unchanged. Existing protected changes: frontend/next-env.d.ts, two backend/reports JSON files, the annual-comparison export active plan, and the personal-site completed plan. Their exact hashes and all tracked non-secret source hashes are retained in replay-entry-manifest.json outside the repository.

## Constraints
Frontend and documentation only; default-off flags and restricted route admission unchanged. No backend, services, database, providers, credentials, dependencies, product-managed persistence, browser storage, cloud, deployment, staging or commits. Local file choice never sends a file. Imports never display supplied results as verified or submit automatically. Financial labels remain explicitly hypothetical.

## Non-goals
Observed-source exports, live acceptance, forecasts, recommendations, conversion between methods, browser storage, source certification, backend arithmetic changes.

## Implementation stages
1. Snapshot protected bytes and inspect current contracts.
2. Add bounded UTF-8 JSON/shape/method/input validation and deterministic receipt download; share local transfer UI across labs.
3. Integrate file/read generation ownership with edits, calculation, cancellation and unmount; restore form fields atomically after validation only.
4. Test actual Python receipts, exact download bytes and round trip, hostile inputs, precision, late operations, and browser keyboard/narrow behavior with retained machine-readable request ledger.
5. Document limits, run regression/type/lint/build checks, verify untouched backend/protected bytes and empty index, leave candidate unstaged.
Recovery: revert only the candidate allowlist after independent review; never reset/stash or touch protected changes.

## Decisions
2026-11-04: reuse existing receipt envelopes and validators; imported outputs are inspected for supported shape/contract but discarded. No new envelope or method conversion. Canonical download is compact JSON plus one LF, within the existing 1 MiB receipt cap; this avoids pretty-print expansion beyond import bounds. File reads are versioned against parent input lifecycle; edits/submits/cancellation invalidate pending reads, while invalid import preserves drafts.

## Discovered issues
- The optional frontend/public directory does not exist. Initial source-copy preparation stopped on that absent directory; the helper now skips it. Both owned source copies, including the partial first copy, were subsequently removed safely.
- New transfer status/alerts exposed ambiguous browser harness selectors. New replay checks scope application alerts and calculation/transfer statuses separately. Existing Risk/Stress verifiers now scope calculation status to the main direct paragraph. The two initial replay failures and two initial regression-selector failures remain in separate retained JSONL ledgers; they did not demonstrate input/result corruption.
- A targeted repeated-edit check found that unchanged parent status could let React skip a render, leaving obsolete local-read loading UI visible. Each parent now publishes its monotonic request revision through explicit React state; the synchronous ref still rejects late read/request callbacks. Both mounted regression cases and all four real-browser method/width cases pass after the fix.
- The build retains existing webpack circular chunk warnings. Guarded Python capture reports the existing Starlette/httpx deprecation warning. No dependencies were installed or changed.

## Progress
- [x] Verified main, empty index, root instructions, current contracts, and preserved entry hashes.
- [x] Implement local workflow.
- [x] Complete validation and self-review, with exact candidate/protected byte checks and owned-resource cleanup.
- [ ] Independent review. Next safe action: review the unstaged 12-file candidate against the outside-repository replay-review-manifest.json. Do not stage or commit under this task.

## Test and validation strategy
Planned: existing guarded Python receipt captures without live services; mounted React and pure contract tests; exact UTF-8 Blob bytes and URL cleanup; malicious/oversized/wrong-method files, complete input bounds, signed/zero/decimal precision, stale file/request delivery; TypeScript and ESLint; isolated source-only Next production build; installed Chrome desktop/narrow/keyboard run with local-only interception and retained JSONL execution/request evidence. No real backend commissioning.

## Validation actually run

2026-11-04, from frontend:

```powershell
E:/node.exe --test tests/hypothetical-replay.test.mjs tests/hypothetical-risk.test.mjs tests/hypothetical-stress.test.mjs
E:/node.exe node_modules/typescript/bin/tsc --noEmit --incremental false
E:/node.exe node_modules/eslint/bin/eslint.js . --ext .ts,.tsx
```

Final result: **40 frontend tests passed** (21 replay + 8 Risk + 11 Stress), types and lint passed. Replay before-hook uses the fixed backend .venv interpreter with `-I -S -B tests/run_financial_insights.py tests/test_hypothetical_risk.py tests/test_hypothetical_stress.py`: **127 guarded Python tests passed**, capturing **11 Risk and 9 Stress actual receipts**. Existing separate client suites also captured their own fresh receipts (62 Risk / 65 Stress backend tests). No live sockets, DB/provider/model acquisition or real .env loading is admitted by the maintained guard. Exact UTF-8 download bytes, every captured receipt input round trip, hostile JSON/duplicates/depth/UTF-8/size/method/version/shape/input constraints, short/zero/decimal/order cases, draft preservation, ignored aborts, late reads/errors, explicit replay submit, repeated edits and deterministic unmount-before-URL-timer cleanup passed.

An owned source-only copy at `build/hypothetical-replay-e23112fd-d813-4646-a9a4-8d92befe512c` linked existing node_modules on the same drive. `NEXT_TELEMETRY_DISABLED=1 E:/node.exe node_modules/next/dist/bin/next build` passed after the final UI fix; the primary next-env.d.ts was never rewritten. Build warnings are noted above. UI-enabled and disabled production copies were started using `next start --hostname 127.0.0.1 --port 3139` / `3138`, with process UI flag 1 / 0, without backend services.

Final installed Chrome runs from frontend (channel env value `chrome`, each with a unique absolute ledger path):

```powershell
E:/node.exe scripts/verify-hypothetical-replay.mjs
E:/node.exe scripts/verify-hypothetical-risk.mjs
E:/node.exe scripts/verify-hypothetical-stress.mjs
```

- Pre-review replay ledger `replay-browser-ledger-final.jsonl` (late-read evidence superseded by the completion-barrier rerun below): **42 assertion groups**, 67 requests / 67 responses, 16 intercepted API replies, both methods at 1440x900 and 390x900 plus disabled 404 gates. SHA256 `d6d35209f5c9eded0dda4e37d702970269049f2fcea6dc9c8b4b21f168b29a26`.
- Risk final candidate regression ledger `replay-risk-regression-ledger-final-candidate.jsonl`: **29 assertion groups**, 45 requests, 20 intercepted API replies. SHA256 `044f1df29915e98a372676f9ff5cbe91dbbd4c807fccbe96254d2d9acb2aef3b`.
- Stress final candidate regression ledger `replay-stress-regression-ledger-final-candidate.jsonl`: **39 assertion groups**, 56 requests, 26 intercepted API replies. SHA256 `4b95b8088f5db75583f6919eb59514c6708d7aa552573ca38bf9f15888037e29`.

Artifacts live outside Git at `C:/Users/IITSt/Documents/Codex/2026-11-05/task/`. Four final screenshots live in replay-browser-screenshots-final. Ledgers retain fresh Python receipts/hashes, all network activity and observed DOM/download/input/URL/keyboard/geometry evidence. Replay browser imports made no API calls, no storage writes and no external requests; actual local downloads matched exact backend receipt serialization. API responses were synthetic interception, including deliberate ignored-abort deliveries. No live API or source acceptance is claimed. Earlier failed/superseded runs are retained, not overwritten.

Both owned loopback frontends were stopped. Ports 3138/3139 have no listeners. The verified dependency junction was unlinked, then both exact owned source copies removed. Browser contexts/download contexts were closed. No user-selected input file or pre-existing resource was deleted.

Self-review: current-result download compares current form inputs to the validated receipt again. Strict UTF-8/duplicate/depth/size scanning precedes receipt validation; supported shape/output invariants are a format gate only. Full input bounds precede restoration. Imported outputs never enter parent receipt state. Fields are checked before atomic restoration. Generation/ref ownership protects pending calculations, file reads, edits, submits, cancellation, timeout, replacement imports and unmount. URLs revoke after click, on click failure, before replacement, and on unmount. No storage/network/upload dependency was introduced.

## Independent-review evidence follow-up

Independent review reported no blocking product defect and requested two evidence corrections. Product implementation and all other candidate files are byte-identical to the reviewed manifest `f9ae64707af3cf6c727f5383312b6104de1e45c8423fdf23380695ac68509364`; only this plan and `frontend/scripts/verify-hypothetical-replay.mjs` change in this follow-up.

The old verifier released native file reads without awaiting their returned promises. Its late-read observations could therefore precede native completion. The verifier now awaits every released native `File.arrayBuffer()` promise, resolves/rejects its consumer, drains consumer promise jobs through a task barrier, increments an explicit completion counter with per-read outcome metadata, then waits two animation frames for React commits/effects before asserting restored/draft/result state. Each affected assertion records its observed completion barrier, and each viewport records started/completed read counts. No product code or behavior changed.

Focused rerun from frontend: `E:/node.exe --check scripts/verify-hypothetical-replay.mjs` passed; `E:/node.exe --test tests/hypothetical-replay.test.mjs` passed **21 tests**, with **127 maintained-guard Python tests** and fresh 11 Risk / 9 Stress receipts. A new owned source-only production build passed using existing dependencies; the existing circular-chunk warnings remain. No dependency or backend changes occurred.

`FINLENS_REPLAY_BROWSER_CHANNEL=chrome E:/node.exe scripts/verify-hypothetical-replay.mjs` passed **42 assertion groups**, covering both labs at 1440 and 390 widths plus disabled gates. Corrected ledger `replay-browser-ledger-barrier.jsonl` has **265 records**, **67 requests / 67 responses**, **16 intercepted API replies**, and **12 file_read_barrier records**. Each barrier released exactly one fulfilled native read and advanced completion by one; each viewport ended with three started and three completed held reads. SHA256 `04fe0eddeff069102b745240b54898faf59113057539663bb6ce0aecce2346d7`. Four new screenshots are retained in `replay-browser-screenshots-barrier`. This new ledger supersedes the old late-read assertions; all prior ledgers remain unchanged.

Request-failure qualification: the retained Stress regression ledger `replay-stress-regression-ledger-final-candidate.jsonl` contains **one** `request_failed` event (request ID 17, width 1440): a **non-API navigation GET** to `/hypothetical-risk/stress?_rsc=FCbzIIjvug7x6Crw` received **HTTP 200 headers**, then reported **net::ERR_ABORTED**. Its request, response and failure events remain intact in that ledger and are copied into the revised review manifest as a joined observation. It was not an API calculation/upload failure. There is no aggregate zero-request-failure claim.

Manifest count correction: the original entry map includes both tracked files and protected exceptions. The correct preservation labels are **255 tracked non-environment backend files plus two protected untracked backend reports**, for **257 backend entries total**. The revised manifest computes the tracked count from `git ls-files`, distinguishes the reports explicitly, and retains all five protected hashes. Original manifest remains as `replay-review-manifest-initial.json`; the revised manifest includes its immutable hash. HEAD/index/scope preservation is rechecked after this documentation update. The new owned loopback servers were stopped, its verified dependency junction unlinked and source copy removed, with ports 3138/3139 clear. No DB, provider, external service or deployment was used.

## Completion criteria
Both methods download only current validated results. Valid import restores exact editable assumptions without rendering/importing results or making a request. Invalid files preserve drafts; all superseded reads/requests are ignored. URLs are revoked. Tests pass with exact candidate scope and immutable backend/protected files. Candidate remains unstaged pending independent review.

## Final outcome
Implemented 12-file frontend/documentation candidate: shared replay helper and component, both lab form integrations, focused contract/mounted suite, a ledger-producing real-browser verifier, calculation-status selector updates in both existing browser verifiers, shared replay documentation, both method documentation links, and this plan. HEAD remains e03a1b16ff07a32b942e3c84e92528b781abb051 on main with an empty index. All 255 tracked non-environment backend files, two protected untracked backend reports, and all five protected exceptions match the entry snapshot; all remaining existing non-secret tracked files are unchanged outside the six declared modifications. The six new candidate files and six modifications remain unstaged for independent review; no commit/push/deployment occurred.

Acceptance limits: synthetic fixtures and intercepted browser API only; no live backend, PostgreSQL/provider commissioning, authorized real sources/holdings/history, export source rights/custody acceptance, financial/statistical suitability, other browser engines/physical devices/screen readers, release or deployment acceptance. Local device files are an explicit user-controlled export, not product-managed persistence. Candidate review, not further integration, is the next step. Suggested eventual commit: `feat: add local hypothetical receipt replay`.
