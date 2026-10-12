# Company Research publication-version initialization

Status: completed (implementation and offline validation; coordinator live acceptance pending)
Roadmap phase: scoped correction to existing Research Mode

## Objective

Defer Company Research requests until freshness establishes the selected company's publication version. Preserve legitimate version zero, publication reconciliation, cancellation and CC-01's independent pins.

## Current architecture and context

Baseline verified: `main`, HEAD and local `origin/main` both `d01ed5a`. Existing uncommitted CC-01 changes span backend metrics/API, frontend page/styles/API, comparison component/contract/tests and two completed ExecPlans. All are preserved. The pre-existing modified `frontend/next-env.d.ts` and two untracked AAPL reports are protected; SHA256 fingerprints of all 15 pre-existing changed/untracked files were captured before implementation.

`ResearchFreshness` currently supplies `data?.data_version ?? 0`; summary/history/sources effects immediately pin that invented zero. User-submitted research and optional AI share this context. `requestJson` correctly rejects mismatched versions. Home already keys the provider by ticker and keeps CC-01 outside it.

## Constraints

Frontend-only correction with focused offline tests. No service restart, build, database writes, migrations, ingestion, SEC/provider requests, staging, commit or push. Do not repeat financial audits or change financial calculations, API contracts, protected files, freshness labels or server-side 36-hour stale semantics.

## Non-goals

CC-01 changes/review, financial coverage, backend changes and live acceptance. Stop after implementation and offline validation for coordinator review.

## Implementation stages

1. Establish the actual baseline and preserve fingerprints.
2. Add mounted regression coverage and adapt existing fixtures to establish a real initial publication version.
3. Represent unknown with null and guard every Company Research request entry point, retaining numeric pins once established.
4. Run relevant offline frontend tests, TypeScript and selective ESLint; inspect diffs and verify preservation fingerprints.

## Decisions

- 2026-10-12: Keep numeric version zero valid; use explicit `number | null` in the research context. Do not weaken or alter API version checks or CC-01 pinning.
- 2026-10-12: Keep existing coalesced freshness checks and stable callback dependencies, so unchanged freshness does not refetch research. A failed initial check leaves version unknown; later failures retain the last established pin.
- 2026-10-12: Reject malformed publication numbers locally before admitting a research pin. Keep existing ticker, monotonic-version, AbortSignal, snapshot identity and request-scope guards. The shared API client and comparison implementation remain byte-for-byte unchanged.

## Discovered issues

The confirmed initialization race is present in the current source. No unexpected baseline/preservation differences found.

## Progress

- [x] Baseline, root instructions, relevant code and existing mounted tests inspected.
- [x] Focused regressions and fixture adaptation: 13 new mounted cases; existing fixtures now explicitly establish version zero through freshness instead of depending on a fabricated pin.
- [x] Minimal frontend correction: explicit null context, guards for summary/history/cash-flow alternatives/sources/research submissions/optional AI and waiting labels.
- [x] Offline validation and self-review: 134 tests passed, TypeScript/ESLint/diff checks passed, all 15 pre-existing file fingerprints preserved.

## Test and validation strategy

Real ReactDOM + JSDOM mounted tests with controlled fetch, including actual initial versions 1 and 0, delayed/failed freshness, StrictMode, company switching, mid-request changes, cancellation, stale responses, unchanged freshness and reconciliation. Fetch fixtures intentionally deliver cancelled responses. Run existing Company Research/API and CC-01 offline tests. TypeScript uses `--noEmit --incremental false`; ESLint targets changed TSX. No production build or live acceptance.

## Completion criteria

No dependent request while version is unknown; zero remains usable; version/cancellation/identity guards retained; relevant offline checks pass; all pre-existing changed/untracked files match their captured fingerprints; final status/diff recorded.

## Final outcome

The initial context now exposes null until a valid selected-company freshness response arrives. No dependent request runs in that state. Numeric zero and nonzero versions both pass through the existing versioned controller and response checks. Failed initial checks remain unpinned; later failures retain the last established version. Known-version changes still abort pending requests, reject stale responses, clear incompatible products and reconcile the catalog; unchanged checks do not duplicate research requests. Freshness labels, five-minute visible checks and the backend's 36-hour stale classification are unchanged.

Task files:

- `frontend/components/research-freshness.tsx`
- `frontend/components/financial-research.tsx`
- `frontend/components/filing-research.tsx`
- `frontend/tests/research-interactions.test.mjs`
- This completed ExecPlan.

Validation actually run on 2026-10-12, from `D:\Projects\finlens-foundation\frontend`:

| Command | Result |
| --- | --- |
| `node --test --test-name-pattern='mounted initialization\|mounted failed initial\|mounted rapid company\|mounted invalid initial' tests/research-interactions.test.mjs` before correction | 10 expected failures reproduced premature dependent requests; StrictMode doubled initial fan-out. |
| `node --test tests/research-interactions.test.mjs` during correction | 61/62 passed; invalid negative publication handling then corrected before final checks. |
| `npm test` | 134/134 passed, zero failed/skipped. Includes 64 mounted Company Research tests and all 27 existing CC-01 tests. CC-01's existing cross-language fixture runs isolated in-memory backend code; no live service/database/provider use. |
| `node node_modules/typescript/bin/tsc --noEmit --incremental false` | Exit 0. |
| `node node_modules/eslint/bin/eslint.js components/research-freshness.tsx components/financial-research.tsx components/filing-research.tsx` | Exit 0, no diagnostics. |

From repository root, `git diff --check` passed. Self-review inspected the production and test diffs, all `useResearchVersion`/`versionedController` call sites, cancellation/identity/monotonic guards, callback dependencies and scope boundaries. SHA256 reconciliation found zero mismatches across all 15 pre-existing changed/untracked files, including CC-01 API/component/contracts/tests/plans, protected `next-env.d.ts` and both protected reports. Existing Node module-type warnings were non-failing; no dependency/configuration changes were made.

No build, restart, live browser/HTTP check, provider/SEC request, ingestion, migration or PostgreSQL write was performed. Live full-reload acceptance with AAPL version 1 and a version-0 company remains for the coordinator, including observing request pins and ensuring no premature 409s. No known offline blocker remains. No stage/commit/push performed.

Git status at handoff (`main`, HEAD/local `origin/main` `d01ed5a`; index unchanged):

```text
 M backend/app/financial_metric_schemas.py
 M backend/app/financial_metrics_service.py
 M backend/app/main.py
 M frontend/app/globals.css
 M frontend/app/page.tsx
 M frontend/components/filing-research.tsx
 M frontend/components/financial-research.tsx
 M frontend/components/research-freshness.tsx
 M frontend/lib/finlens-api.ts
 M frontend/next-env.d.ts
 M frontend/tests/research-interactions.test.mjs
?? backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json
?? backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json
?? backend/tests/test_company_comparison.py
?? docs/exec-plans/completed/2026-10-12-cc01-review-corrections.md
?? docs/exec-plans/completed/2026-10-12-company-comparison-cc01.md
?? docs/exec-plans/completed/2026-10-12-publication-version-initialization.md
?? frontend/components/company-comparison.tsx
?? frontend/lib/company-comparison.ts
?? frontend/tests/company-comparison.test.mjs
```

Full tracked `git diff --stat` (includes preserved earlier work; excludes untracked files):

```text
 backend/app/financial_metric_schemas.py       |  30 +++++-
 backend/app/financial_metrics_service.py      |  38 +++++++
 backend/app/main.py                           |  14 ++-
 frontend/app/globals.css                      |  18 ++++
 frontend/app/page.tsx                         |   4 +-
 frontend/components/filing-research.tsx       |  11 +-
 frontend/components/financial-research.tsx    |  18 ++--
 frontend/components/research-freshness.tsx    |   9 +-
 frontend/lib/finlens-api.ts                   |  12 ++-
 frontend/next-env.d.ts                        |   2 +-
 frontend/tests/research-interactions.test.mjs | 144 +++++++++++++++++++++++---
 11 files changed, 265 insertions(+), 35 deletions(-)
```

Task-only tracked diff: **4 files changed, 152 insertions(+), 30 deletions(-)**, plus this untracked plan. Suggested commit: `fix(frontend): wait for the initial research publication version`.
