# QA-01 browser end-to-end testing

The suite exercises the real Next.js page, React effects, API client and financial/evidence validators. It uses test-only synthetic AAA/BBB issuers, not seeded or live financial data. Production components, calculations, API contracts and existing Node tests are unchanged.

## Running

Use supported Ubuntu 24.04 (or supported Linux in WSL), Node 24, and a Linux checkout/filesystem with its own Linux `node_modules`. Do not reuse Windows-installed modules from WSL. From `frontend/`:

```sh
npm ci
npm run test:qa01
npx playwright install --with-deps chromium
npm run test:e2e:isolation
npm run test:e2e
```

The prepared GitHub Actions workflow runs these commands on Ubuntu 24.04, with no backend/database services or secrets. It has not been committed, dispatched or pushed during implementation. Existing Node tests are a separate regression gate; their detached Python fixtures require the project's Python dependencies, so the browser-only CI job does not pretend to run them.

Safe local static checks, including on this Windows 10 machine:

```powershell
npm test
npm run test:qa01
npx tsc --noEmit --incremental false
npx eslint playwright.config.ts e2e/fixtures/data.ts e2e/fixtures/browser.ts e2e/fixtures/ignored-abort.ts e2e/research.spec.ts e2e/recovery.spec.ts e2e/comparison.spec.ts e2e/experience.spec.ts scripts/e2e-server.mjs scripts/e2e-process-group.mjs tests/qa01-harness.test.mjs tests/qa01-process-group.test.mjs
node --check scripts/e2e-server.mjs
npm run test:e2e:list
npm run test:e2e:isolation
```

Do not run a production build for this suite. Test discovery installs/starts nothing. `test:e2e:isolation` probes the two ports, copies only approved frontend source into its own temporary directory, creates/unlinks its dependency link, removes that owned directory and verifies the original next-env hash; it starts no services.

The current host is Windows 10 build 19045, outside [Playwright's native Windows requirements](https://playwright.dev/docs/intro#system-requirements). Chromium was not installed or executed. The launcher also refuses native Windows browser execution: the installed Playwright runner force-kills Windows webServer trees rather than invoking graceful shutdown, which would skip temporary-directory cleanup. Linux/WSL is the supported execution path for this initial harness, including on Windows 11. Native Windows lifecycle support is a separate bounded follow-up.

## Isolation and request contracts

- Fresh browser context per test; no shared selections, storage, responses or cache. Service workers are blocked. Routes and WebSocket interception are installed before navigation.
- Browser HTTP allows the isolated origin `127.0.0.1:3107`, its page/assets, and an explicit API allowlist. Only the local Next HMR WebSocket is allowed. Unknown routes/methods/query parameters, unsupported metric names, unpinned financial requests and external destinations are blocked and fail the test. SEC links are inspected, never followed. AI-generation routes are excluded.
- API fixtures return complete typed bodies. Scenario publication state is independent of request headers. A known obsolete request gets 409 with `DATA_VERSION_CHANGED`, never a header echoed from the incoming request. Deliberately malformed responses test the actual client/component validators; interception validates request shape without repairing response bodies.
- The frontend runs from a `finlens-qa01-*` directory created beneath the OS temporary directory. The explicit source inventory excludes `.env`, backend, SEC artifacts, backups and generated output. Symlinked source trees are refused. Shared dependencies are linked, then explicitly unlinked before recursive cleanup. The original frontend directory never hosts a test build.
- Ports 3107 and 3108 must both be free; existing servers are never reused or killed. The isolated frontend proxy points exclusively to the owned deny-all upstream on 3108. Any financial/API upstream contact marks the run unhealthy and stops its owned processes. A runner-only `GET /__qa_status` reports harness health at teardown; browser access to 3108 is blocked. This diagnostic endpoint never forwards requests.
- The child inherits an environment allowlist for OS/runtime operation plus development mode, disabled Next telemetry and the deny-all proxy URL. Application/provider/database configuration is not inherited.

## Coverage and assertions

`research.spec.ts` checks six primary snapshot cards, all 15 metrics through native disclosure, zero/negative/unavailable/not-applicable values, exact provenance and safe SEC links. It checks quarter/annual/YTD/as-of history requests, rejected mismatched identity/period responses, EPS warnings, guide focus and explicit submission, indexed versus metadata/unverified filing readiness, and company-wide provenance refusal with the independent direct answer preserved.

`recovery.spec.ts` checks catalog/freshness/source/snapshot retries, rejected cache eviction, unchanged controls/editor/direct answer, actual versions 0 and 1, null/malformed pins, delayed freshness, missing/mismatched version headers, current-pin fail-closed rejection and same-pin guard, concurrent 409 coalescing, same-pin freshness outages, obsolete 0→1 and 1→2 responses and rapid company switches.

`comparison.spec.ts` checks distinct issuers, independent 0/1 pins, discovery and selected annual requests, year switching, invalid provenance isolated to one column, cancellation and explicit refresh. `experience.spec.ts` runs at both 1440×1000 and 390×844, checking light/dark persistence, viewport containment, keyboard skip link, native disclosures, sequential focus and editor focus.

Assertions use accessible names, explicit values/reasons, identity, source attributes and a request ledger. Screenshots are failure diagnostics only. Mobile means Chromium viewport/touch emulation, not a claim about real Android/iOS devices. Keyboard checks are bounded acceptance, not a complete accessibility certification.

Fixed test-only revenue observations differ by issuer, interval and annual year: AAA quarter/half-year/nine-month/annual 2025 = $1B/$2.4B/$3.7B/$5B; BBB = $2B/$4.2B/$6.5B/$9B. Annual 2024 = AAA $4B and BBB $7B. Comparison asserts exact values and dates for 2025→2024→2025, so stale-year reuse fails. Selected revenue/cash-flow/EPS/as-of histories contain a missing 2023 observation, available zero in 2024 and the current 2025 value. History acceptance checks all three rows' dates, zero/unavailable states and the selected period's exact value; snapshot interval values are also asserted. These are synthetic display inputs, never real financial information or new formulas.

## Race evidence and limits

Named ignored-abort tests normalize the selected company route to its full `/api/finlens/companies/...` pathname before navigation. Only same-origin exact matches lose the transport signal; other paths/origins retain cancellation. They retain the real production controller signal, requestJson logic, identity checks and lifecycle guards. A bounded delivery ledger records the exact path, query, originating publication pin, status and original signal's aborted state. All four browser delivery cases require the specific old response to arrive after cancellation: company switching and comparison cancellation (200), and obsolete 0→1 / 1→2 requests (409). An unrelated delivery cannot satisfy these assertions. No API client or response validation is replaced. Persistent offline regressions execute the serialized init callback with production-prefixed string/URL/Request inputs and the real API client, proving genuine active mismatches still invalidate while aborted ones do not.

These browser cases wait for the newer publication's committed UI before delivering an obsolete 409. They do **not** reproduce the exact pre-commit React ordering by themselves. The existing Node tests retain all four precise FR-01 races: 0→1 and 1→2, normal React and StrictMode, with `deliverBeforeCommit`. Next development renders under the existing StrictMode setting; this suite does not change that production configuration.

## Lifecycle and diagnostics

One worker, zero retries, 45-second tests, 5-second assertions, 10-second actions, 30-second navigation, 120-second startup and a 10-minute suite limit. Fresh contexts avoid test-to-test financial cache leakage. Held responses are released and pages closed before route removal so teardown cannot create an unmocked request. Deny-upstream health is checked before reporting success.

Linux SIGINT/SIGTERM cleanup tracks the owned detached Next process group independently of its leader's exit. Linux `/proc` membership, session identity and captured leader start time are checked before signalling; changed ownership is refused. After bounded SIGTERM/SIGKILL waits, absence of running members is verified again before unlinking dependencies and deleting only the verified temporary directory. Exited zombies hold no working-directory files and do not prevent cleanup. Verification failure retains the directory. The owned upstream is closed even if verification fails; original next-env SHA256 is checked after successful cleanup. Never run global Node/process kills or blanket temporary-directory cleanup. An OS crash/SIGKILL cannot execute JavaScript cleanup; ephemeral CI runner disposal is the final containment layer. Process-group verification requires Linux; other platforms retain static copy-isolation support only. Real Linux process-tree regressions and Next/browser lifecycle remain pending on this Windows host.

Failure traces and screenshots are retained; videos are disabled. Diagnostics cap API requests at 200 and failures/violations at roughly 100 each; exceeding the cap fails rather than hiding a loop. Failure artifacts include method/path/query/pin, with synthetic questions excluded from the ledger attachment. HTML reports never auto-open. Output directories are ignored. CI uploads failures only, for seven days. After an approved run, inspect with `npm run test:e2e:report`; nothing is published automatically.

## Initial implementation validation — 2026-10-13 (before remediation)

| Check actually executed | Result |
| --- | --- |
| `npm install --save-dev --save-exact --ignore-scripts @playwright/test@1.64.0` | Passed; three development packages added; no browser installation |
| `npm test` | 200 passed, 0 failed; includes FR-01/CC-01/FD-01 and all four pre-commit races |
| `npx tsc --noEmit --incremental false` | Passed |
| Selective ESLint command above | Passed |
| `node --check scripts/e2e-server.mjs` | Passed |
| `npm run test:e2e:list` | 29 project cases discovered across four files; discovery only |
| `npm run test:e2e:isolation` | Passed; owned source copy/link/cleanup and next-env preservation; no services |
| In-memory synthetic-contract probe through production modules | 132 positive structural/validator checks and 12 rejection checks passed |
| In-memory harness allowlist/independent-version probe | 8 allowed/default-response and 8 rejected request checks passed |
| Owned occupied-port probes for 3107 and 3108 | Launcher exited 1 as expected; both probe listeners retained and then closed by their owners |
| CI YAML parsing and `git diff --check` | Passed |
| Protected next-env and both report SHA256 checks | Unchanged |
| Chromium execution, Linux Next lifecycle, GitHub Actions | **NOT EXECUTED** |

The contract probe transpiled the test-only fixture module and production validator modules in memory. It checked six valid annual responses, eight invalid annual cases, four valid company-context responses at pins 0/1 and four invalid source identities, two evidence parsers, and 120 history identity/period shapes. It made no HTTP or provider requests. Harness probes exercised the exact allowlist and default reply code in memory. These are useful offline checks, not browser acceptance.

Persistent remediation regressions now replace the scratch contract/allowlist probe. Run `npm run test:qa01` on any supported Node 24 host. They execute the serialized init script and actual production API/annual/evidence validators entirely in memory; no browser or HTTP/provider/database requests. Eight portable cleanup regressions inject process membership and signals. Four additional tests create real owned Linux process trees and exercise normal shutdown, unexpected leader death, a SIGTERM-ignoring descendant and failure cleanup; these four explicitly skip on Windows. Ubuntu CI runs all of them before browser startup.

The npm installation reported 12 audit findings; no unrelated upgrade/audit-fix was attempted in QA-01. The dependency lock changed only the pinned Playwright dependency tree.

## Astra remediation validation — 2026-10-13

| Check actually executed after remediation | Result |
| --- | --- |
| `npm run test:qa01` | 18 passed, 0 failed; 4 real Linux process-tree tests explicitly skipped on Windows |
| `npm test` | 218 passed, 0 failed; same 4 Linux skips; all 200 existing tests preserved |
| `npx tsc --noEmit --incremental false` | Passed |
| Scoped ESLint and Node syntax checks | Passed |
| `npm run test:e2e:list` | All 29 project cases discovered in four specs; not browser execution |
| `npm run test:e2e:isolation` | Passed; no services started |
| Workflow parsing, tracked/new-file whitespace and protected hashes | Passed |
| Linux process-tree execution, Chromium cases and Next lifecycle, CI dispatch | **NOT EXECUTED**; no supported Linux/Chromium environment available |

The three findings are corrected and offline checks pass; ready for independent re-review. Keep the active ExecPlan open until supported Linux execution supplies process-tree and browser acceptance. Do not infer that browser assertions passed from discovery/static checks. No dependencies were installed or changed during remediation.

## Optional live smoke

Live smoke is not implemented or run by this milestone and is never a fallback for synthetic E2E. A future explicitly approved read-only smoke can inspect already-running frontend/API URLs with a separate GET allowlist for catalog/freshness/financial/source metadata. It must not share these fixtures or trigger evidence retrieval, embeddings, AI, refresh, ingestion, activation or database writes. No backend, database or provider service is required for this initial browser suite.
