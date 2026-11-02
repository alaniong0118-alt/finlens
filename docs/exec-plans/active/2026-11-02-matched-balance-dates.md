# Matched-date balance measures

Status: active — offline and six-case synthetic browser acceptance passed; final evidence review and delivery pending
Roadmap phase: bounded deterministic financial comparison from existing data

## Objective

Explicitly load cash and equivalents, total assets and total liabilities, then
compare 2–4 distinct exact reported dates. Preserve original values, USD, dates,
reasons and source lineage. Missing dates, failed/unverified histories and server
unavailable/not-applicable observations must remain distinct. This is three
selected measures, not a complete statement or proof of accounting comparability.

## Baseline and scope

Start at `0bd57f2492f751f6079a6cbc334948d29b3d4280`, main, empty index and the
five protected exceptions. Preserve the delivered coverage filters, responsive
annual chart, their tests and prior acceptance evidence. Only three new product
files, the reviewed `app/page.tsx` import/navigation/provider hunk, two corrected
browser files and this plan are included. No conflicting live edits may be
overwritten. Balance product and corrected browser P2 reviews passed separately;
their earlier isolated test results are not new live-checkout validation.

The initial integration authorized no staging/commit/push, Docker, browser
execution, services, database, provider, private configuration, model,
installation, auth activation or security changes. Its separate runner remained
hard-disabled then. A later separately reviewed and authorized one-run isolated
acceptance completed as recorded below. This evidence-only update does not
authorize another invocation, activation or Git delivery. Preserve all drives,
existing files, the original freeze and the consumed one-run guard.

## Architecture, bounds and decisions

- One explicit Load action makes exactly three existing instant metric-history
  GETs, each bounded to 12 observations. At most 36 validated observed dates form
  the union. Selection/disclosure/clear do not fetch; dates are not substituted.
- Retain exact decimal strings and trusted server provenance. Invalid dates,
  duplicate date rows, unsafe SEC metadata or conflicting immutable fact IDs
  refuse the implicated series rather than ranking or silently deduplicating.
- Reuse the existing publication provider, transport, source disclosure/focus
  behavior and scoped table layout. Company/CIK/publication sessions and operation
  identity prevent cancelled or ignored-abort late fetch/body completions from
  replacing current work. No new financial calculation, endpoint or dependency.
- Missing-publication-header limitation is inherited and intentionally unchanged:
  requests carry the verified pin (including zero), and the existing transport
  rejects returned mismatched headers or DATA_VERSION_CHANGED errors. It does
  not require a returned header, and history bodies contain no publication
  version. Do not claim strict response-publication proof when that header is
  absent. This task neither tightens nor bypasses the shared API contract.
- Bounded loaded histories are not complete SEC coverage or a historical
  knowledge-cutoff view. Accounting scope/revisions may differ; no comparability,
  complete-financial-statements, real-data or full-beta acceptance is claimed.

## Implementation and validation stages

- [x] Verify reviewed patch digests, current baseline and clean initial index.
- [x] Apply only reviewed product/page and replacement browser patches; bind bytes.
- [x] Run guarded focused mounted/API and relevant page integration regressions.
- [x] Run scoped lint, no-emit/non-incremental TypeScript and six-case discovery.
- [x] Freeze exact candidate/source/status hashes with protected preservation.
- [x] Independent integration/runner review and separately authorized acceptance.
- [ ] Final review, scoped delivery and CI under a later coordinator instruction.

## Validation strategy and actual evidence

Use installed dependencies only, synthetic fetch responses and owned bounded
Node processes with the existing offline I/O guard. Keep DOM suites in separate
processes, retain logs/exit/guard counts, and report selected/skipped tests honestly.
Use installed Playwright CLI list-only for the single corrected balance spec and
desktop project: three behaviors at both 1440px and 390px (six cases). Discovery
does not start its browser, webServer or fixtures. The corrected P2 spec preserves
the complete API-start counter across Clear/retry so extra permitted GETs cannot
be hidden by resetting a baseline.

On 2026-11-02, from `D:\Projects\finlens-foundation\frontend`, executed:

```powershell
& '..\backend\.venv\Scripts\python.exe' -I -B 'D:\Projects\finlens-balance-date-integration-20261102\run-offline-checks.py'
```

The external fixed script records every underlying command, resource bound,
exit and log in `D:\Projects\finlens-balance-date-integration-20261102`.
`offline-checks.json` records all nine checks, each with exit 0, confirmed direct
child exit and `offline-guard blocked-attempts=0`. Test processes used installed
Node with `--test --test-isolation=none --test-timeout=15000 --test-reporter=tap`;
each file ran separately. No browser/service, database or provider ran.

| Integrated check | Actual result |
| --- | --- |
| `balance-date-comparison-matched.test.mjs` | 20 passed |
| `finlens-api.test.mjs` | 165 passed |
| `annual-period-comparison.test.mjs` | 18 passed |
| `financial-coverage.test.mjs` | All existing 33 passed |
| `research-interactions.test.mjs`, name pattern `^financial-only` | 28 selected, passed; other tests not run |
| `financial-insights-interactions.test.mjs`, name pattern `^1B\.2A (Home\|supported Home)` | 2 selected, passed; other tests not run |
| ESLint, page/component/helper/new spec/fixture only | Passed |
| `tsc --noEmit --incremental false` | Passed |
| Playwright single spec `--list --project=desktop-chromium --reporter=list` | Exactly 6 cases, no browser launch |

Total executed tests: 266 passed, zero failures, cancellations or reported skips.
The API suite retained the existing Node `MODULE_TYPELESS_PACKAGE_JSON` warning;
it did not change package configuration. Per-process Node heap limits were
384 MiB for tests, 512 MiB for lint/discovery and 768 MiB for TypeScript, with
finite external deadlines/output bounds and direct-process cleanup. These are
not an aggregate native-memory or OS egress-containment guarantee.

Discovery lists three behaviors at 1440x1000 and 390x844. Although selected under
the desktop project, the spec explicitly configures `isMobile` and `hasTouch` at
390px. The initial integration performed discovery only; the later isolated
acceptance below exercised both groups. Physical touch, screen readers, zoom,
forced colors and actual real-data publication/header behavior remain unverified.

## Separately authorized synthetic browser acceptance

On 2026-11-02 the acceptance owner executed one reviewed pinned-image invocation,
attempt `b8c02e471af449deb1792ae39a4e85fa`: six executed and passed, zero failures,
skips, not-run cases or retries. Both PowerShell and the container exited 0, with
no OOM reported. Three cases ran at each viewport: exact 2–4-date selection and
source keyboard access; gaps versus failed history with Clear/explicit retry;
publication zero and ignored-abort A-to-B-to-A ownership, including an old 409.
The workload host attach took 25,818 ms within its 600-second allowance; peak
resource statistics were not collected. No test was rerun for this doc update.

The acceptance owner inspected all 12 actual PNGs and associated geometry:
readable exact values/source text, native keyboard focus and contained horizontal
scrolling passed. Desktop table width/client width was 1324/1324 px; narrow was
640/322 px on a 390 px page with zero overflowing values. The narrow final source
summary's lower outline extent was 844.234375 px in an 844 px viewport, within
the unchanged 0.5 px tolerance; visual inspection reported no material clipping.
This is synthetic browser-emulated evidence, not physical-device or comprehensive
accessibility acceptance.

All 36 balance request occurrences matched exact company, metric, GET query,
pin, body absence and expected terminal response. Expected 503/409 stimuli were
retained. Full-page ledgers recorded 148 starts and 147 routed requests; the one
unbound request was a cancelled freshness replay admitted by the existing strict
pairing gate. Audit violations/binding errors were empty. Local selection and
Clear did not add requests; the explicit retry retained the full start counter.

The exact owned container
`5085c71cd4b3f172d6ce47f9ff890d22af2613c6e72e508efc4e8a0e2a19d8a7`
was removed and absence was independently read back. Phase/final cleanup and
all 10 owned host CLI exit checks passed. The consumed guard, original 33 raw
attempt files, indexed exports and inspection records remain retained. Source,
HEAD, index and five protected identities were unchanged during acceptance;
only this plan changes for final evidence closure.

Evidence directory: `D:\Projects\finlens-balance-native-inspection-20261102-b8c02e47`.
`native-report.md` and `native-delivery-manifest.json` describe the inspected
artifacts and preservation checks. Primary SHA-256 pins:

- `overall-result.json`: `93F3F3AC7AE9E35409C8678EBFC24DB10C94B2016E08142FCD9D28E465143591`.
- `balance-native-attempt-b8c02e47.zip`: `2E09580FC8F854C6A9511733A00A641707D7E15BDE4973D498D22E821EC142FD`.
- Acceptance snapshot manifest: `E5BEA8B9A98B4F43E72D78098F4CF8704E3C5C47B1C1B90E75A39C9538D5C768`.

Six disclosed optional WASM dependencies remain unverified; this successful run
does not establish their completeness. Existing circular-dependency webpack
warnings were retained. The inherited missing-publication-header limitation,
three-metric/bounded-history scope, unverified accounting comparability and lack
of real SEC data/freshness/rights acceptance remain unchanged. No full statement,
production readiness or external beta acceptance is claimed.

## Completion criteria and outcome

Exact reviewed source bytes, relevant offline checks, six passed synthetic browser
cases, unchanged prior features/protected files and an empty index satisfy the
current implementation/acceptance handoff. The final seven-file package binds
acceptance sources to the live checkout and records this plan's evidence-only
delta from the original freeze. Final evidence/doc review and separately
instructed Git delivery/CI remain pending. No staging, commit or push has occurred.
