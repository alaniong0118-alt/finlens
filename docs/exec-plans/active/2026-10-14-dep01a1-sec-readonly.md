# DEP-01A1 SEC-only release admission

Status: active — implementation and targeted P2 correction verified; coordinator/Astra High re-review pending
Roadmap phase: bounded portfolio release enabling task DEP-01A1

## Objective
Implement the approved immutable `development | sec_readonly` server profile,
default-deny HTTP admission, effective AI capabilities, and early operational
guards. Research reads and deterministic answers remain available.

## Current architecture and context
Read [repository instructions](../../../AGENTS.md), [plan rules](../../../.agent/PLANS.md)
and [roadmap](../../../ROADMAP.md). Baseline: main = origin/main = HEAD =
`1cad18545071ba9a199094577b1efd384e37fc29`. Existing changes to preserve:
`frontend/next-env.d.ts` and the two untracked AAPL reports dated 20261010.
FastAPI routes use publication-bound read sessions; operational services also
expose directly callable writers and injected sources.

## Constraints
Implementation and focused offline synthetic tests only. No real database,
SEC/provider/network/model-download calls, service startup, configuration changes,
migrations, activation, publication, Git staging/commit/push/reset/cleanup.
Preserve financial calculations, evidence, freshness and read-session contracts.

## Non-goals
DEP-01A2/A3, hosting, timeout/readiness implementation, OS/database sandboxing,
QA-01/browser reruns, completed financial/parser regression suites.

## Implementation stages
1. Validate and resolve the server profile immediately after dotenv loading.
2. Freeze exact admitted route identities and reject before CORS/dependencies.
3. Guard generation/acquisition and operational entry points before callbacks/I/O.
4. Restrict query encoder to cached local artifacts; consume effective capabilities.
5. Run isolated focused tests, inspect diff and preservation, record outcome.
Recovery: review/revert only this task's edits manually; no reset or cleanup.

## Decisions
- 2026-10-14: Preserve unset development compatibility; explicit blank/unknown
  profile values fail startup without echoing configuration values.
- 2026-10-14: HTTP policy includes exact method, path template and registered route
  object; new routes/aliases and unsupported methods require separate admission.
- 2026-10-14: `FINLENS_SERVER_PROFILE` is resolved once after dotenv. Release must
  explicitly select `sec_readonly`; later environment edits and HTTP headers
  cannot change it. `ai_analysis_configured` and new `ai_analysis_enabled` are
  effective capabilities; both are false in release even with dummy credentials.
- 2026-10-14: Minimal guard-only boundary extensions were necessary in
  `backend/app/sec_filing_service.py` and `backend/app/financial_sync_service.py`:
  direct ingestion and sync touch sessions before their lower-level importer or
  coordinator guard. Guard both outer and internal entry points, before the
  existing financial-reader decorator. No service body/calculation changes.
- 2026-10-14: Supported scripts include verification commands that read live
  databases/APIs or write reports; their operational entry points are also
  development-only. Pure financial/parser/evidence helpers remain unchanged.
- 2026-10-14: Freeze admission after route registration and install before CORS.
  GET health/db probes, exact research reads and deterministic POST are allowed;
  generation, docs/OpenAPI, unknown/alias routes, trailing-slash redirects,
  HEAD/OPTIONS and other unsupported methods are denied with HTTP 403 and
  `X-FinLens-Error-Code: RELEASE_MODE_BLOCKED`. WebSockets close with code 1008.
- 2026-10-14: Use `try_to_load_from_cache` and a local model snapshot path with
  `local_files_only=True`; never use a remote model identifier in release.
  Missing/incomplete cache fails with a controlled RuntimeError; development
  retains its existing constructor. Local installed library source confirms
  local-only propagation to model/config/tokenizer/module loaders.

## Discovered issues
- Initial offline harness blocked Windows asyncio's internal loopback socketpair,
  preventing ASGI test loops. Final runner allows only the stdlib socketpair's
  exact callsite and loopback address; general external, localhost/database,
  `connect_ex` and `create_connection` calls remain forbidden. No servers started.
- Synthetic fact needed an explicit created timestamp to satisfy existing source
  provenance validation. Added it only to the test fixture.
- Self-review found `functools.wraps` does not preserve lru_cache control methods.
  Forward cache_clear/cache_info/cache_parameters while keeping admission outside
  cache hits. Focused test proves cached clients cannot bypass release admission.
- Final self-review replaced tuple membership with explicit object identity (`is`)
  for admitted routes: framework route equality can be structural. A focused test
  verifies even a replacement with the original endpoint/template is denied.
- 2026-10-14 independent Astra High review reported one blocking P2:
  `refresh_scope.pin_sources()` remained directly callable without release
  admission, including via its `refresh_service` imported alias. The function
  can open a supplied factory, read scalar values, then invoke injected facts,
  observations and inventory callbacks before a lower-level guard. Targeted
  correction authorized only in refresh_scope.py, test_release_profile.py and
  this plan: add the existing definition-level `@development_only`, prove zero
  callbacks in release and preserved development contracts, then stop for review.

## Progress
- [x] Read approved request/instructions, verify baseline and preserved files.
- [x] Implement server and frontend policy.
- [x] Focused synthetic verification and self-review.
- [x] Record final outcome.
- [x] Independent Astra High implementation review received: one blocking P2 in pin_sources.
- [x] Targeted P2 guard correction, offline reproduction/regression and preservation checks.
- [ ] Coordinator/Astra High re-review (next safe action; no deployment).

## Test and validation strategy
Offline ASGI clients, bomb sessions/providers/callbacks and blocked external sockets.
No real application startup. Validate invalid startup configuration before engine
creation, allowed deterministic requests, forbidden dependency count zero,
proxy forwarding, operational argument bypass, model local-only behavior,
capability failure/strict booleans and development compatibility. Commands/results
will be recorded below. Preserve original file SHA256s recorded before editing.

### Checks actually run (2026-10-14)

From `D:\Projects\finlens-foundation\backend`:

```powershell
& .\.venv\Scripts\python.exe -B tests/run_dep01a1_offline.py
```

Initial implementation result: **152 passed**, one existing Starlette TestClient deprecation warning,
9.75 seconds. Runner supplies synthetic `DATABASE_URL=sqlite://`, disables private
dotenv loading, defaults to development, blocks network before imports, and runs
only `test_release_profile.py` and `test_capabilities.py`. No database connection
is used: reads use fake sessions/ORM-shaped objects, operational inputs are bombs,
and model/provider/SEC constructors/transports are fakes. Startup rejection checks
use isolated subprocesses. There are no real provider calls or downloaded models.
Coverage: invalid profile before initialization, frozen profile/dotenv ordering,
all 19 reviewed method/template pairs, unknown methods/routes/dependencies,
direct and forwarded denials, dummy credentials, deterministic available/null
results with provenance, operational services/scripts/flags/callbacks, cached
encoder miss/incomplete cache/local-only constructor, and development routes,
cached client controls, fake generation, fake SEC transport, seed/import sessions.

From `D:\Projects\finlens-foundation\frontend`:

```powershell
node --test --test-name-pattern='DEP-01A1|mounted AI failure retains|mounted no-key success' tests/finlens-api.test.mjs tests/research-interactions.test.mjs
node node_modules/eslint/bin/eslint.js app/page.tsx components/filing-research.tsx lib/finlens-api.ts
node node_modules/typescript/bin/tsc --noEmit --incremental false
```

Final result: **10 passed**, no failed/cancelled tests; lint and TypeScript passed.
Frontend requests are entirely intercepted synthetic fetches; mounted React/jsdom
checks verify malformed/missing/inconsistent/failed capabilities keep generation
disabled while direct answers and evidence remain usable. Development optional AI
failure and no-key behavior retain existing research. Existing Node module-type
warning remains. No browser, production build, or QA-01 suite run.

From repository root: `git diff --check` passed; PowerShell Parser.ParseFile
reported no launcher syntax errors. `git diff --exit-code` confirmed unchanged
database.py, freshness_service.py, financial_analysis.py,
financial_metrics_service.py, financial_metric_registry.py,
research_answer_service.py, revenue_scope_authorizations.py,
sec_evidence_adapter.py and tracked backend reports. HEAD/main/origin/main remain
at the approved baseline. No staging, commit, push, reset or cleanup occurred.

Preserved SHA256 before/after:

| Existing file | SHA256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

### P2 targeted correction — 2026-10-14

Rechecked HEAD `1cad18545071ba9a199094577b1efd384e37fc29` and starting
status (33 modified tracked files, 6 untracked). Hashed all 39 existing modified
and untracked files to verify preservation across this correction. The starting
DEP-01A1 implementation was retained.

The exact production change in `backend/app/refresh_scope.py` is two added lines:

```diff
+from app.release_policy import development_only
 ...
+@development_only
 def pin_sources(factory, catalog, facts_loader, inventory_loader, observations, reject_conflicts):
```

All existing imports remain, and AST comparison with HEAD confirms the original
arguments and entire function body are unchanged. The definition-level wrapper
is shared by `refresh_scope.pin_sources` and `refresh_service.pin_sources`; no
refresh_service, HTTP, frontend or financial changes were needed.

Tests added only in `backend/tests/test_release_profile.py`:

- Both aliases added to the existing operational-entry registry; generic bomb
  arguments verify rejection precedes catalog access.
- Six negative cases (two aliases by factory/scalar/loader bomb stage) require
  `ReleaseModeBlocked` with code `RELEASE_MODE_BLOCKED`; factory, scalar,
  facts_loader, inventory_loader, observations and reject_conflicts each have
  zero calls. Catalog is valid, so existing catalog validation cannot mask the
  missing release boundary.
- Two development positive controls use synthetic sessions and fake validation/
  dry-run merge callbacks; preserve loader arguments, `PinnedCanarySources`,
  digest/evidence contracts and detached source copies.
- Two development negative controls preserve `canary_catalog_cik_mismatch`
  without factory/callback execution.
- One alias/signature assertion verifies both exports are the same callable and
  retain all six original argument names; development positive calls use keywords.

Commands run from `D:\Projects\finlens-foundation\backend`:

```powershell
& .\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('tests/run_dep01a1_offline.py', run_name='dep01a1_offline_config'); import pytest; raise SystemExit(pytest.main(['-q','--tb=short','-p','no:cacheprovider','tests/test_release_profile.py','-k','pin_sources']))"
& .\.venv\Scripts\python.exe -B tests/run_dep01a1_offline.py
```

Before the source fix, the targeted reproduction produced **6 failed / 5 passed /
148 deselected**: bombs proved both aliases reached factory, scalar and facts
loader. No actual database or network was involved. After the source fix and
registry additions: **13 passed / 0 failed / 0 skipped / 148 deselected** (1.15s).
The complete bounded DEP-01A1 acceptance runner: **165 passed / 0 failed / 0 skipped**
(9.49s), with the existing TestClient deprecation warning only. The unchanged
runner disables private dotenv, blocks external sockets and uses synthetic inputs;
no services, models, real database or providers were invoked.

Verification order: inspected exact source diff and AST/signature/body equivalence;
reran the security triggers, alternate bomb stages and legitimate controls;
ran the bounded owning acceptance suite. A fresh read-only skill investigation
and a fresh source-only candidate review found the shared definition boundary
sufficient and no concrete surviving bypass/regression within the authorized
scope. These internal checks do not substitute for coordinator/Astra re-review.

Final `git diff --check` passed. SHA256 comparisons confirm every starting
modified/untracked file except the authorized test/plan additions is byte-identical,
including `frontend/next-env.d.ts`, both original untracked reports and the rest
of the existing DEP-01A1 implementation. The only new modified tracked path is
refresh_scope.py. Exactly the three authorized repository files changed during
this correction; no other file was necessary. HEAD remains unchanged. No staging,
commit, push, reset, cleanup, real DB/network access, service startup, model
downloads, SEC/provider calls, financial/parser or QA-01 audits occurred.

## Completion criteria
All approved policy requirements implemented; focused checks pass; no out-of-scope
effects; financial/evidence/read-session files preserved; diff self-reviewed.
Independent review remains a separate user/coordinator step.

## Final outcome
Implementation and the targeted pin_sources P2 correction are verified within
DEP-01A1; stop here for coordinator/Astra High re-review.
Profile admission is application enforcement, not an OS/database/Python sandbox.
No live deployment, real database acceptance, real cached-model loading or actual
Next server proxy acceptance is claimed. Proxy verification reproduces the
unchanged inspected catch-all rewrite with an in-process forwarding transport.
Release query retrieval requires a complete standard Hugging Face local cache;
absent/incomplete cache causes a controlled failure without acquisition. Default
development remains intentional; operators must explicitly select the release
profile. New routes require policy admission. No DEP-01A2/A3 work was performed.

### Changed-file ledger

- Backend app: `config.py`, new `release_policy.py`, `main.py`, `answer_service.py`,
  `sec_client.py`, `embedding_service.py`, `refresh_service.py`, `sec_importer.py`,
  `catalog_indexing_service.py`, `sec_filing_service.py`, `financial_sync_service.py`,
  `aapl_net_margin_activation.py`, `aapl_net_margin_launcher.py`, `refresh_scope.py`.
- Backend operations: `seed_companies.py`, `.env.example`, and scripts
  `setup_demo.py`, `index_catalog.py`, `sync_financial_facts.py`, `refresh_data.py`,
  `evaluate_rag.py`, `verify_catalog_indexing.py`, `verify_collation.py`,
  `verify_financial_metrics.py`, `verify_financial_sync.py`,
  `verify_historical_answers.py`, `verify_research_answers.py`.
- Frontend: `lib/finlens-api.ts`, `app/page.tsx`, `components/filing-research.tsx`.
- Focused tests: backend `tests/test_capabilities.py`, new
  `tests/test_release_profile.py`, new `tests/run_dep01a1_offline.py`; frontend
  `tests/finlens-api.test.mjs`, `tests/research-interactions.test.mjs`.
- Development launcher: `Start-FinLens.ps1`; this ExecPlan.

Final verified Git state: **33 task-modified tracked files + 4 new task files**,
plus the pre-existing modified `frontend/next-env.d.ts` and two untracked reports.
Total: **34 modified tracked files, 6 untracked files**, all unstaged.
All changes remain unstaged; no commits created. Suggested commit after review:
`feat: enforce SEC-only read-only release profile (DEP-01A1)`.
