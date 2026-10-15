# DEP-01A2 Increment 2: bounded HTTP database runtime

Status: active; production Freshness P2 confirmed closed by Astra High; final two test-only assertion corrections complete; coordinator/Astra targeted review pending.
Roadmap phase: scoped deployment hardening, Increment 2 only.

## Objective

Give every HTTP database path a separate lazily connecting engine with the approved profile bounds and fixed, typed dependency errors. Retain verified publication pins, consistent read snapshots, operational workflows and release admission.

## Current architecture and context

Baseline inspected: branch main, HEAD and origin/main both `b4ec5b1d7b2d2c5ac0fea07b53b0c22a9d9db1a8`; index empty. HTTP routes use the operational SessionLocal, except /dbz uses its engine directly. VersionedRoute initializes version to zero even before validation. The encoder catches all constructor exceptions in release mode.

Protected initial SHA256 bytes:

- frontend/next-env.d.ts: `F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0`
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: `A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C`
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: `F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C`

## Constraints

Production changes confined to config.py, database.py, main.py, embedding_service.py and freshness_service.py (pin provenance/cleanup only). No real DB, writes, network/provider requests, model downloads, services, migrations, financial activation, frontend edits, Git staging/commit/push or private env changes.

## Non-goals

No Increment 3, aggregate HTTP wall-clock guarantee, QA-01, financial audits, DEP-01A1 acceptance rerun or Increment 1 tests. Synthetic evidence does not establish PostgreSQL timeout enforcement or concurrency safety.

## Implementation stages

1. Verify baseline and hashes; inspect relevant code and installed driver/pool behavior.
2. Implement profile bounds, isolated lazy HTTP factory, connection option validation and non-retrying checkout probe.
3. Implement route error boundary, verified pin retention and safe read-session cleanup; narrow encoder exceptions.
4. Run guarded synthetic tests and relevant offline regressions, debug, self-review diff and recheck hashes.
5. Stop for independent review. Recovery is reverting only this increment's named files after review; no automated Git reset/cleanup.

## Decisions

- 2026-10-14: SQLAlchemy's built-in pre-ping retries checkout reconnections. Use a checkout probe with built-in pre-ping disabled; invalidate and surface typed errors without requesting retry.
- 2026-10-14: HTTP supports synchronous postgresql+psycopg only, one explicit host and one IP address (numeric host or explicit hostaddr), retaining the hostname for TLS. Reject service/multi-host/option overrides before engine construction. Canonical libpq startup options apply before initialization and the checkout probe; never mutate PGOPTIONS.
- 2026-10-14: Route-local handling runs before ContextVar reset so verified zero/positive pins survive errors. Unverified state is None and has no version header.
- 2026-10-14: Missing metadata/schema cannot satisfy an explicitly supplied pin, including zero; return DATA_VERSION_CHANGED without inventing a version. Invalid metadata stays generic 500. Cleanup retains the acquired Connection because Session.close can detach its transaction before rollback raises.
- 2026-10-14: Existing HTTP test fixtures must target HttpSessionLocal. Ten existing test files receive only fixture substitutions; their operational factories, assertions and financial semantics are unchanged. Their broad suites are not rerun.
- 2026-10-14: Unknown SQLSTATE remains generic 500 even if a failed checkout probe discards its connection. Invalidation is a recovery action and does not establish the cause of unknown SQL/programming errors.

## Discovered issues

Installed psycopg expands DNS results into multiple connection attempts and prefer-standby into a second pass. SQLAlchemy built-in pool pre-ping can reconnect multiple times. Both must be constrained in the HTTP path; the operational engine remains unchanged.

The first test run found port zero incorrectly defaulting to 5432 and a test-fixture teardown referencing a monkeypatched cache function. Both were corrected. Real SQLAlchemy ORM/QueuePool tests over fake DBAPI objects additionally confirm that a detached transaction after rollback failure is discarded, primary programming errors survive cleanup, and checkout-probe failures do not retry within that request.

## Progress

- [x] Baseline, index, protected hashes and scope inspected.
- [x] Implementation.
- [x] Focused guarded tests and offline regressions.
- [x] Self-review, final inventory and protected hashes.
- [ ] Independent Astra High review (next action after implementation report).

## Test and validation strategy

Use backend/.venv/Scripts/python.exe with dotenv disabled, synthetic PostgreSQL URL, socket and DBAPI connection bombs installed before imports. Mock engines/sessions/psycopg errors, compile PostgreSQL SQL, and use in-process ASGI requests. Cover both profiles, hostile connection options/environment, lazy operational separation, every HTTP DB route, lifecycle failures/recovery, pins, safe taxonomy, encoder conditions and admission. Record exact commands and pass/fail/skip counts below.

## Completion criteria

Approved bounds and all HTTP paths implemented; no operational fallback or automatic retry; fixed sanitized errors and verified pins preserved; focused offline tests pass; protected hashes unchanged; no out-of-scope changes. Independent review and real deployment acceptance remain pending.

## Final outcome

Implementation and scoped offline verification complete; STOP for independent Astra High review. No review approval, deployment readiness or real PostgreSQL timeout/concurrency enforcement is claimed. No commits or staging.

### Exact task-file inventory and diff

Five production files modified:

- `backend/app/config.py`: immutable development/sec_readonly HTTP bounds.
- `backend/app/database.py`: separate lazy HTTP engine/factory, synchronous psycopg single-destination validation, startup SQL limits, non-retrying checkout probe and typed database classification. Existing engine/SessionLocal configuration preserved.
- `backend/app/main.py`: all 18 database routes use HttpSessionLocal; route-local sanitized failures retain verified pins and fixed cache headers; no default version zero.
- `backend/app/embedding_service.py`: explicit EncoderDependencyError; missing imports/cache, unreadable artifacts and malformed JSON/model dimension conditions are typed; unexpected programming errors propagate.
- `backend/app/freshness_service.py`: verified pin/null handling, explicit expected-pin rejection when unverifiable, retained connection and safe cleanup. Existing REPEATABLE READ, READ ONLY first transaction SQL preserved.

Ten existing test files modified only to redirect HTTP fixtures to HttpSessionLocal (release fixture still bombs the operational engine):

- `backend/tests/test_capabilities.py`
- `backend/tests/test_catalog_indexing.py`
- `backend/tests/test_company_availability.py`
- `backend/tests/test_company_catalog.py`
- `backend/tests/test_company_comparison.py`
- `backend/tests/test_company_evidence_search.py`
- `backend/tests/test_data_refresh.py`
- `backend/tests/test_financial_metrics.py`
- `backend/tests/test_refresh_postgres.py`
- `backend/tests/test_release_profile.py`

Three new files:

- `backend/tests/run_dep01a2_increment2_offline.py`: dotenv-disabled synthetic URL, physical psycopg/socket bombs, no pytest cache/bytecode.
- `backend/tests/test_http_database_runtime.py`: configuration, typed errors, lifecycle/pin, route coverage, encoder, development compatibility and fake DBAPI ORM/pool tests.
- `docs/exec-plans/active/2026-10-14-dep-01a2-http-database-runtime.md`: this implementation/review handoff.

Tracked task diff at final inspection: 307 insertions, 52 deletions across 15 files. The three new files are untracked and are additional to that diff. The protected frontend modification is excluded from the task diff.

Exact tracked unified diff command (repository root):

```powershell
git diff -- backend/app/config.py backend/app/database.py backend/app/embedding_service.py backend/app/freshness_service.py backend/app/main.py backend/tests
```

New files can be reviewed directly; they are intentionally not staged. `git diff --check` passed; only existing Git LF/CRLF conversion notices were emitted.

### Bounds and HTTP path coverage

| Bound | development | sec_readonly |
|---|---:|---:|
| connect_timeout | 5 seconds | 3 seconds |
| pool_timeout | 5 seconds | 2 seconds |
| statement_timeout | 30000 ms | 10000 ms |
| lock_timeout | 5000 ms | 2000 ms |
| pool_size | 5 | 5 |
| max_overflow | 5 | 0 |

Canonical options are `-c statement_timeout=30000 -c lock_timeout=5000` or `-c statement_timeout=10000 -c lock_timeout=2000`. They are passed to the physical connection before dialect initialization SQL and checkout probes. HTTP supports only `postgresql+psycopg`, an explicit host/database and one IP (numeric host or hostaddr); TLS query configuration is retained. Conflicting URL/environment options, services, multi-host/address lists and alternate/async drivers fail before connection. Process-wide PGOPTIONS and operational configuration are not modified.

All 18 DB route templates tested at the real in-process route/factory boundary in both profiles:

```text
GET /dbz
GET /companies
POST /companies/{ticker}/research-answer
GET /companies/{ticker}/financials/summary
GET /companies/{ticker}/financials/annual
GET /companies/{ticker}/financials/metrics/{metric}
GET /companies/{ticker}/financial-summary
GET /companies/{ticker}/financial-snapshot
GET /companies/{ticker}/financial-history
GET /companies/{ticker}/sources
GET /companies/{ticker}/freshness
GET /companies/{ticker}/context
GET /companies/{ticker}/filings/{accession_number}/text
GET /companies/{ticker}/filings/{accession_number}/chunks
GET /companies/{ticker}/filings/{accession_number}/search
GET /companies/{ticker}/filings/{accession_number}/semantic-search
GET /companies/{ticker}/filings/{accession_number}/context
POST /companies/{ticker}/filings/{accession_number}/answer
```

The last route is development-only and was confirmed rejected before the factory/encoder in sec_readonly. Health/capabilities remain configuration-only. No new HTTP database/operational path was admitted.

### Error taxonomy and provenance

| Typed condition | Public status/code |
|---|---|
| SQLAlchemy pool TimeoutError; psycopg SQLSTATE 55P03 / 53300 | 503 DATABASE_BUSY |
| psycopg SQLSTATE 57014 | 504 DATABASE_TIMEOUT |
| SQLSTATE class 08 / 57P01-57P03; typed connection-establishment OperationalError; invalidated connection without an unknown SQLSTATE | 503 DATABASE_UNAVAILABLE |
| Explicit EncoderDependencyError | 503 RETRIEVAL_UNAVAILABLE |
| Unknown SQLSTATE / programming errors | sanitized generic 500 |

The classifier uses SQLAlchemy exception types and typed psycopg `.orig.sqlstate`; no diagnostic-message matching. Codes 57014 and 55P03 do not prove timeout/cancellation/NOWAIT mechanisms. Recognized dependency messages are fixed, with X-FinLens-Error-Code and Cache-Control: no-store. No SQL, parameters, URL/host/password diagnostics or model paths are returned. Meaningful research 400/404/409/422 details/codes are retained.

Publication zero and positive integers are verified only after the scalar metadata query completes; None is unverified. Early connect/checkout/probe/transaction/schema/pin failures have no version header. Verified pins survive query and cleanup failures. Mismatched or unverifiable supplied pins get DATA_VERSION_CHANGED; no retry, repin or partial response is introduced. Each request owns one read session/snapshot; subsequent recovery uses a fresh session.

### Actual validation commands and results

Working directory for Python commands: `D:\Projects\finlens-foundation\backend`. Every invocation set `$env:PYTHONDONTWRITEBYTECODE='1'` and used `-B`; the runner disables dotenv, uses only dummy credentials, bombs physical psycopg connections and external sockets, and disables pytest cache. No service is started.

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py
```

Final result: **236 passed, 0 failed, 0 errors, 0 skipped**, one pre-existing Starlette/httpx deprecation warning, 1.66 seconds. Coverage includes both profiles, URL/env/TLS validation, construction isolation, registered connect event, compiled PostgreSQL pin/transaction SQL, every DB route, failure stages and recovery, unknown/zero/positive/mismatched pins, schema failures, unknown SQL errors, cleanup/invalidation, local-only encoder and programming failures. The actual ORM/pool tests use fake DBAPI, not PostgreSQL or SQLite.

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_company_comparison.py -k api
```

Result: **4 passed, 26 deselected, 0 failed/skipped**, one warning. Only synthetic API/contract tests selected; no financial audit or database fixture execution.

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_rag.py::HybridTests tests/test_capabilities.py
```

Result: **13 passed plus 8 subtests passed, 0 failed/skipped**, one warning. Nine mocked hybrid/context retrieval tests plus four configuration-only capability tests.

Final intended test coverage: **253 test cases passed plus 8 subtests**, no remaining failures/errors/skips. Other suites were not rerun, including DEP-01A1 acceptance, QA-01, Increment 1, live Postgres and financial audits.

Intermediate history is retained, not overwritten: first core run **210 passed, 1 failed, 36 teardown errors** (port-zero handling and fixture cache-clear), followed after corrections/additions by **212**, **215**, **228**, **232**, and final **236** passing core cases. One intermediate invocation used a broader negative selector than intended and passed **250 cases, 12 deselected**, all synthetic fixtures/compiled SQL with the same guards:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_http_database_runtime.py tests/test_company_comparison.py -k 'not test_latest_common and not test_explicit and not test_period and not test_ambiguous and not test_annual and not test_predecessor and not test_52 and not test_53 and not test_missing and not test_sparse and not test_revenue and not test_production_permissions'
```

This intermediate selection is not treated as a financial audit or production acceptance; the final dedicated core invocation selected every new core test without filtering.

### Development compatibility and remaining acceptance

Synthetic checks confirm original operational engine pool pre-ping/default pool policy and SessionLocal binding/autoflush/autocommit, original development encoder constructor and query encode arguments, deterministic API pins/contracts, retrieval ranking/context and capabilities. No operational maintenance, ingestion or refresh workflow was executed. Ten fixture-adapter files were updated for future independent testing; their complete suites were not run here. Financial selectors, calculations, authorization registries and frontend cancellation code were untouched.

Pending: independent Astra High review; separately authorized real PostgreSQL connection/startup/statement/lock enforcement, concurrency/pool/load/TLS and deployment acceptance. DNS-only/service/multi-host/alternate-driver HTTP configurations are intentionally unsupported and require explicit compatible deployment configuration. Network-stall/driver cancellation/rollback time and initialization cost can exceed the individual configured limits; these are not an aggregate HTTP wall-clock deadline. Frontend timeout does not terminate backend work. Existing explicit on-request schema capability checks are preserved; no factory/startup probe was added.

### Final Git state and preservation

Branch main and both HEAD/origin/main remain `b4ec5b1d7b2d2c5ac0fea07b53b0c22a9d9db1a8`. Index empty. Fifteen task files modified, three task files new/untracked; the original modified frontend file and two original untracked reports remain present. No Git add/commit/push/reset/cleanup.

Final protected SHA256 hashes exactly match the initial hashes listed above. Rechecked using Get-FileHash after tests and implementation. No private .env, original evidence, reports or frontend bytes were changed.

Suggested commit message (not executed): `Bound HTTP research database runtime and sanitize dependency failures`.

## Targeted P2 correction — 2026-10-14

Astra High found that the production freshness BODY still defaulted to version zero when its metadata row or schema was missing. Omitting the version header did not stop the frontend from consuming the numeric body pin. The original boundary-test substitution also converted None to zero and masked this behavior.

Baseline rechecked before edits: main, HEAD/origin/main at the expected `b4ec5b1d7b2d2c5ac0fea07b53b0c22a9d9db1a8`; index empty, the same 21 existing modified/untracked paths from Increment 2. All three protected hashes match the original values above. Captured hashes for all 21 paths to detect any changes outside the three authorized correction files.

Scope: freshness_service.py, test_http_database_runtime.py and this existing ExecPlan only. The existing VersionedRoute HTTPException boundary already provides safe body/code/cache headers and retained verified pin handling; main.py does not require editing. Introduce fixed HTTP 503 FRESHNESS_UNAVAILABLE specifically for absent schema/row. Do not reclassify unknown programming errors, fabricate pins, modify transaction cleanup or broaden production scope.

### Before-fix reproduction

Added two failing tests using the actual route and production freshness function, synthetic ORM metadata/session and compiled PostgreSQL statements. No main.freshness substitution; only the DB session and schema-capability result are synthetic.

Working directory: `D:\Projects\finlens-foundation\backend`, PYTHONDONTWRITEBYTECODE=1:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_http_database_runtime.py::test_production_freshness_unverified_is_unavailable
```

Observed **2 failed, 0 passed**: both returned HTTP 200 with body data_version=0; absent schema additionally returned migration_required=true. Neither state was a verified publication. Production code was unchanged during this reproduction.

### Correction progress

- [x] Recheck baseline/index/worktree and protected hashes.
- [x] Reproduce both failures through the actual production freshness function.
- [x] Apply minimal missing-metadata guard and remove the test substitution's null-to-zero fallback.
- [x] Test real-function unverified, verified zero/positive, stale pins, cleanup, recovery and programming failures; run Increment 2 regressions.
- [x] Final preservation check and self-review; STOP for coordinator/Astra review.

### Correction and after-fix results

Only three files changed relative to the P2 turn's starting worktree:

- `backend/app/freshness_service.py`: missing schema or CompanyRefreshState row now raises a fixed HTTPException 503 with X-FinLens-Error-Code=FRESHNESS_UNAVAILABLE. A present row supplies the Freshness versions explicitly. The read_session/pin/cleanup logic is unchanged by this targeted fix.
- `backend/tests/test_http_database_runtime.py`: synthetic ProductionFreshnessSession supplies real ORM metadata and compiles PostgreSQL statements; availability/version tests exercise the actual production function. Removed the boundary stub's `session.version or 0` fallback. Added missing row/schema, subsequent recovery to verified zero/positive, stale pin, cleanup and programming-error regressions.
- This existing ExecPlan: finding, reproduction, correction and actual results.

The existing main.py boundary required no change: it preserves fixed HTTPException detail/code, adds Cache-Control=no-store, and attaches only already verified publication headers. No unknown exceptions are caught/reclassified in the corrected freshness function.

For an unpinned freshness request, missing row or schema returns exactly:

```json
{"detail":"Publication freshness is unavailable. Try again later."}
```

HTTP 503, X-FinLens-Error-Code=FRESHNESS_UNAVAILABLE, Cache-Control=no-store, no X-FinLens-Data-Version header and no usable data_version body. A supplied pin when metadata is unverifiable continues to return the existing DATA_VERSION_CHANGED 409 without a fabricated version header. Genuine metadata version zero and positive versions still return 200 with matching body/header pins. A verified stale pin returns 409 carrying the verified current version, before the freshness body query. Unknown TypeError/AttributeError/assertion failures in real freshness queries remain fixed generic 500 responses, with verified pin provenance retained and no exception disclosure.

All Python commands below ran in `D:\Projects\finlens-foundation\backend`, with PYTHONDONTWRITEBYTECODE=1, the existing guarded runner and `-B`. No real PostgreSQL, network, model download or service startup occurred.

1. Re-ran the exact two-case reproduction command above after the production fix: **2 passed, 0 failed**, 1.16 seconds (before: 2 failed, both 200/zero).
2. Targeted production-function regression command:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_http_database_runtime.py -k 'production_freshness or zero_positive_missing_metadata or unmigrated_scope'
```

Result: **17 passed, 232 deselected, 0 failed/errors/skipped**, 1.25 seconds.

3. Complete Increment 2 offline regressions:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py
```

Result: **249 passed, 0 failed/errors/skipped**, 1.71 seconds. This includes all 18 bounded HTTP DB route tests, profile/option/SQLSTATE classifications, release admission and existing fake DBAPI/session/pool cleanup tests.

4. Existing relevant API regression:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_company_comparison.py -k api
```

Result: **4 passed, 26 deselected, 0 failed/errors/skipped**, 1.17 seconds.

5. Existing retrieval/capability regression:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_rag.py::HybridTests tests/test_capabilities.py
```

Result: **13 passed plus 8 subtests passed, 0 failed/errors/skipped**, 1.15 seconds. Each Python run emitted the same pre-existing Starlette/httpx deprecation warning.

Final unique suite total: **266 test cases plus 8 subtests passed**; targeted reproduction/17-case runs are subsets, not extra cases. No QA-01, DEP-01A1 acceptance, Increment 1, live PostgreSQL, financial audit or broad refresh suite ran. The historical unmigrated acceptance test in test_data_refresh.py still expects the superseded HTTP 200/migration_required freshness body; that unrelated file was preserved and its broad suite was not run under this narrow authorization. This correction intentionally replaces that unverified-success contract with explicit unavailable behavior.

Self-review and `git diff --check` passed. Rehashed all 21 pre-existing modified/untracked paths: exactly these three correction files changed; the other 18 retained their initial bytes. No paths were added/removed. The protected frontend/report hashes match the initial hashes above exactly. main.py, database.py, config.py and embedding_service.py were byte-preserved, retaining the HTTP/operational split, profile bounds, typed classifications and local-only encoder/release policy.

Final Git status still has the same path inventory: 16 modified tracked files (15 prior Increment 2 task files plus protected frontend/next-env.d.ts) and five untracked files (three prior task files plus the two protected reports). Index empty; branch main and HEAD/origin/main remain the expected baseline. No staging, commit, push or cleanup. Original evidence/private .env files were not edited.

Correction complete; STOP for coordinator and Astra review. Real PostgreSQL enforcement/concurrency and deployment acceptance limitations remain as documented above. Suggested later commit message: `Reject unverified freshness publication pins`.

## Final test-only correction — 2026-10-14

The coordinator reports Astra High confirmed the production Freshness P2 closed and approved the missing-metadata 503 / verified-zero-or-positive 200 / stale-pin 409 contracts. The two remaining obsolete assertions in test_data_refresh.py were separately authorized for assertion-only correction.

Baseline before editing: branch main, HEAD and origin/main both `b4ec5b1d7b2d2c5ac0fea07b53b0c22a9d9db1a8`, index empty, same 21 worktree paths. Protected-file hashes match the initial values above. Captured all existing modified/untracked paths plus every backend/app Python source file (53 unique files) to verify production and unrelated work preservation.

Only two files changed relative to this turn's starting worktree:

- `backend/tests/test_data_refresh.py`: replaced only freshness-response assertions in `test_unmigrated_read_only_api_keeps_valid_evidence_and_unknown_freshness` and `test_no_interactive_network_and_unpublished_accession_gate`.
- This existing Increment 2 ExecPlan: current review status and final test evidence.

Each named test now asserts HTTP 503, X-FinLens-Error-Code=FRESHNESS_UNAVAILABLE, exact fixed JSON `{"detail": "Publication freshness is unavailable. Try again later."}`, Cache-Control=no-store, no X-FinLens-Data-Version header and no data_version body field. The obsolete successful-body status/migration_required/facts expectations were removed only from these freshness assertion blocks.

All other fixture code and assertions are unchanged: evidence remains accessible without metadata, SEC/provider/network sentinels remain active, request-time write observation remains intact, and unpublished accession text/chunks/search/semantic/context/answer requests still require 409. No skip or relaxed assertion was added. A source comparison against the turn-start test file confirmed that exactly the two named freshness blocks changed.

### Exact validation

Working directory: `D:\Projects\finlens-foundation\backend`, PYTHONDONTWRITEBYTECODE=1:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py tests/test_data_refresh.py::test_unmigrated_read_only_api_keeps_valid_evidence_and_unknown_freshness tests/test_data_refresh.py::test_no_interactive_network_and_unpublished_accession_gate
```

Result: **2 passed, 0 failed, 0 errors, 0 skipped**, 1.21 seconds. Three existing deprecation warnings: one Starlette/httpx and two datetime.utcnow warnings. No additional regression suite was necessary or run; the complete 249-test suite, DEP-01A1, financial audits and QA-01 were not repeated.

The existing guarded runner disables private dotenv, uses a synthetic URL, blocks physical psycopg connections and external sockets, and avoids pytest cache/bytecode. The existing tests use transient in-memory SQLite and injected synthetic SEC/evidence/encoder fixture inputs. Their fixture schema/setup/publication simulation is confined to that isolated memory database; no operational database, SEC/provider request, model download, service startup, migration, ingestion, publication or activation was performed against real application state.

`git diff --check` and self-review passed. Final preservation check: exactly the two authorized files changed among the 53 captured files; all backend/app production sources, frontend/next-env.d.ts, both protected reports and other pre-existing work retained their starting bytes. Protected SHA256 hashes remain:

- frontend/next-env.d.ts: `F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0`
- canary-aapl_guarded_live_20261010_111844_3580610-publication.json: `A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C`
- refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: `F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C`

Final Git path inventory is unchanged: 16 modified tracked files and five untracked files, all inherited paths from Increment 2 and protected work. Index empty; main/HEAD/origin/main unchanged at the expected baseline. No Git staging, commit, push, reset or cleanup. No SEC evidence or real .env files were edited.

Final assertion-only correction complete; STOP for coordinator and Astra targeted review. Production acceptance limitations remain unchanged. Suggested later test-only commit message: `Align freshness regression assertions with unavailable metadata contract`.
