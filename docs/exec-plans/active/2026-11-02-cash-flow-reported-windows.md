# Cash flow over exact reported windows

Status: active — offline and six-case synthetic browser acceptance passed; final evidence review and delivery pending
Roadmap phase: bounded deterministic financial comparison from stored histories

## Objective and scope

Explicitly load operating cash flow, capital expenditures and free cash flow for
one company and one duration kind, then compare 2–4 exact start/end date pairs.
Offer half-year and nine-month reported windows separately. Preserve exact
values, USD, original reasons and source/operand lineage; distinguish a missing
window from an unavailable observation and a failed/unverified history.

Baseline: main `1e98a3a31713e4f2ecd84ecbcab951bd411f7980`, empty index and only
the five historical protected exceptions. Preserve balance-date, coverage and
annual-chart work. Scope is seven reviewed code/test paths plus this plan:
the API opt-in, new helper/component/mounted test, page integration and corrected
browser spec/fixture. No backend, financial formulas, dependencies or policy edits.

The immutable revised package is
`D:\Projects\finlens-cashflow-window-reviewfix-20261102-01\reviewfix-delivery`.
Product and browser-spec review passed after fixes for canonical source assignment,
malformed FCF input metadata and full outline clipping checks. Prior isolated
results are review evidence, not validation of this integrated checkout.

## Contracts, limits and decisions

- No automatic cash-flow requests. One explicit Load sends exactly three existing
  metric-history GETs for one selected duration, each with `limit=12`; at most 36
  validated windows form the union. Selection, source disclosure and Clear are
  local. Two to four distinct exact pairs are required; no date substitution.
- Half-year windows have 165–200 inclusive days; nine-month windows have 245–295.
  These are duration classes, not inferred fiscal-quarter identities. Retain
  overlaps and different intervals with unverified comparability disclosures.
- FCF is the existing server calculation `operating_cash_flow - capital_expenditures`;
  CapEx follows the existing positive-outflow convention. Validate the two complete
  operand/source references and immutable fact assignments across all responses.
  Do not recalculate, derive quarters, subtract annual/YTD values, convert FX or
  claim complete cash-flow statements or accounting comparability.
- The new consumer opts into required response publication headers through an
  optional `getMetricHistory` argument. Missing response headers refuse that
  history; returned mismatches invalidate the current publication. The default
  stays false for existing callers, including the delivered balance-date view;
  its inherited missing-header limitation remains unchanged.
- Company/CIK/publication/duration session identity and current-operation checks
  revoke cancelled work and ignored-abort late responses. A changed duration
  clears prior state and requires an explicit Load; no POST or model path exists.

## Constraints and stages

The initial integration authorized no staging, commit, push, Docker, native
browser, services, DB, network/provider, private configuration, model, auth
activation, downloads or security changes. Later separately reviewed isolated
acceptance attempts are recorded below. This evidence-only update authorizes
no new invocation or Git delivery. Preserve all drives, prior evidence and
protected files. Stop on conflicting live edits; do not merge semantics into
reviewed patches.

- [x] Verify package digests, baseline bytes and combined patch applicability.
- [x] Apply only reviewed patches, verifying reviewed Windows/LF representations.
- [x] Run guarded new/affected mounted and API regressions with finite bounds.
- [x] Run scoped lint, no-emit/non-incremental TypeScript and six-case list-only discovery.
- [x] Freeze exact scope/raw and expected Git-clean identities, status and source binding.
- [x] Independent integration/runner review and separately authorized browser acceptance.
- [ ] Final evidence review, scoped Git delivery and exact-commit CI.

## Validation strategy and actual results

Use installed dependencies and synthetic fetches only. Reuse the existing offline
I/O guard and bounded direct-child supervision. Run DOM suites separately, retain
command/exit/count/output evidence outside the repository, and distinguish selected
tests from entire suites. Cover response-header opt-in/legacy compatibility,
canonical operand assignment even when FCF fails, safe input rendering, exact
window selection, missing/error distinctions, publication zero, cancellation and
duration changes. Preserve existing balance/annual/quarter/coverage and financial-only
page behavior with relevant regressions. List only the new browser spec under
desktop-chromium and verify precisely six cases; do not execute a browser.

On 2026-11-02, from `D:\Projects\finlens-foundation\frontend`, executed:

```powershell
& '..\backend\.venv\Scripts\python.exe' -I -B 'D:\Projects\finlens-cashflow-integration-20261102\run-offline-checks.py'
```

The fixed external script and `offline-checks.json` in that directory retain all
11 exact commands, deadlines, exits, counts and bounded logs. Every check exited
0 with confirmed direct-child exit and `offline-guard blocked-attempts=0`.

| Integrated check | Actual result |
| --- | --- |
| `cash-flow-window-comparison.test.mjs` | 15 passed |
| `finlens-api.test.mjs` | 165 passed |
| `balance-date-comparison-matched.test.mjs` | 20 passed |
| `annual-period-comparison.test.mjs` | 18 passed |
| `quarter-window-comparison.test.mjs` | 11 passed |
| `financial-coverage.test.mjs` | All 33 passed |
| `research-interactions.test.mjs`, pattern `^financial-only` | 28 selected, passed; other tests not run |
| `financial-insights-interactions.test.mjs`, pattern `^1B\.2A (Home\|supported Home)` | 2 selected, passed; other tests not run |
| ESLint on six changed TS/TSX paths | Passed |
| `tsc --noEmit --incremental false` | Passed |
| New spec `--list --project=desktop-chromium --reporter=list` | Exactly 6 cases; no browser launch |

Total: 292 tests passed, zero failures, cancellations or reported skips. Each DOM
file ran in a separate process with `--test --test-isolation=none
--test-timeout=15000 --test-reporter=tap`. Test heap limits were 384 MiB, lint and
discovery 512 MiB, TypeScript 768 MiB, with finite external deadlines/output caps.
These do not establish aggregate native-memory or OS egress containment. The
existing Node package-type warning in the API suite was retained without changing
package configuration.

Discovery covers three behaviors at 1440x1000 and 390x844. Both are selected under
desktop-chromium; the spec enables mobile/touch emulation at 390px. The initial
integration executed discovery only. Later isolated browser acceptance is
recorded below; physical touch, screen readers, zoom, forced colors, real data,
source rights, freshness and actual real-data runtime publication behavior remain
unverified. Acceptance binds its reviewed snapshot to the frozen source identities;
instrumentation stays outside the live production source.

## Separately authorized synthetic browser acceptance

The first attempt, `8ef9c9aa424a4caf969ad553a453ac76`, failed during the runner's
support-inventory ordering preflight: 0 passed, 0 failed browser cases and 6 not
run. The expected inventory had not been sorted like the actual inventory. Its
original FAILED result and consumed guard remain retained at
`D:\Projects\finlens-cash-flow-browser-artifacts-8ef9c9aa424a4caf969ad553a453ac76`.
Cleanup and preservation were verified. This is a harness preflight failure,
not a failed product/browser assertion or a successful acceptance.

The external runner correction sorted the expected inventory consistently with
the actual inventory. It received independent review; no source/spec, financial
semantics or browser oracle changed. The original failure was not overwritten.

The corrected attempt, `237cdd5e26d4440dafdc17070aefdc2d`, executed all six cases:
three at 1440x1000 and three at 390x844 with mobile/touch emulation. All six passed,
with zero failures, skips, not-run cases or within-attempt retries. Both phases
exited 0 with verified test evidence and cleanup. Cases covered exact half-year
selection and keyboard sources; missing, failed and missing-pin histories with
Clear/retry/publication mismatch; and nine-month/company switches rejecting late
stale responses. The acceptance owner inspected screenshots/geometry and
revalidated exact request associations/full-page ledgers. No acceptance-blocking
visual or request-accounting finding remained.

The owned container
`0406b68990b5b55a885730932deb0d0e4477471dbd6d86baa21c35b8b6adbda9`
was removed and exact absence verified. Final gates for test evidence, artifacts,
container absence, source preservation, proposal preservation and owned host CLI
exit were all true. The live source, five protected files, HEAD, status and empty
index were unchanged during acceptance. Only this plan changes for final evidence
closure; no tests were rerun to prepare this update.

Corrected evidence root:
`D:\Projects\finlens-cash-flow-browser-artifacts-237cdd5e26d4440dafdc17070aefdc2d`.
Primary SHA-256 pins:

- `overall-result.json`: `33DEF3FD870C8DE6D285821EB14ED53EA93C99EBCE9964678340B40F02FAB4AE`.
- `receipt.json`: `49C20862EB0056244072674B09CF5B0398AAF5064530032D1248E41964FC35F9`.
- `desktop/results.json`: `B2927DD2238D4E06735A895042B166179CC34ECE23FA026F4CF594DB6FE5562A`.
- `mobile/results.json`: `5B4A6CDB208E8574DF3271799B707A87947B5CF9835579CEC11BB1F4882E9086`.
- Corrected proposal manifest: `7B7719F2A444077C5CCBC40BB22161942B75B41A937A23248CA42A0A29614A3C`.

This remains synthetic browser-emulated acceptance. Six disclosed optional WASM
dependencies are still `UNVERIFIED_OPTIONAL_DEPENDENCIES`; passing these cases
does not establish their completeness. No physical-device/full accessibility,
real SEC data/rights/freshness, accounting comparability, complete financial
statement, deployment or external beta acceptance is claimed. Header opt-in is
verified for the new consumer in fixtures; legacy callers' optional-header
contract remains unchanged.

## Completion criteria and outcome

Reviewed content without semantic merge, passing focused offline/static checks,
exact six-case discovery, unchanged prior/protected files and empty index form
the integration gate. Source integration does not authorize activation, acquisition
or publication. The recorded synthetic browser gate has passed; final evidence
review and separately instructed Git delivery/CI remain pending.
Only the seven reviewed code/test paths and this plan are changed; five protected
exceptions remain byte-identical and the index is empty. Original freezes,
both attempt guards and all retained results are preserved.
