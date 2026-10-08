# Data Freshness & Automatic Refresh — implementation acceptance

Date: 2026-10-08. **Offline implementation and review repairs validated; operational rollout and focused Astra re-review pending.** No live currency claim is made. Canonical design/commands/rollout live in the [runbook](../../docs/data-freshness.md); exact checks/hashes are in [verification JSON](data_freshness_verification.json).

## Delivered phases and changed files

- Contracts/schema: `app/refresh_contracts.py`, operational ORM models and additive `f94c6f41e0cb` migration. Existing migrations and financial/chunk/vector schema remain unchanged.
- Coordination/publication/recovery: new `app/refresh_service.py`, `app/freshness_service.py`, `scripts/refresh_data.py`, opt-in root `Refresh-FinLens.ps1`.
- Supported writer integration: `sec_importer.py`, `financial_sync_service.py`, `sec_client.py`, `sec_filing_service.py`, `embedding_service.py`, `catalog_indexing_service.py`, `scripts/setup_demo.py`.
- Stored-only/versioned API: `app/main.py`. Financial response bodies retain existing contracts; source/readiness now requires complete evidence publication.
- UI: `research-freshness.tsx`, `financial-research.tsx`, `filing-research.tsx`, page provider and typed API/version headers. No redesign/dependency change.
- New backend refresh/PostgreSQL tests; existing writer/API fixtures updated for manifest readiness, migration head and bounded version SELECT. Frontend API/mounted tests add version invalidation and StrictMode coverage.
- Canonical README/roadmap/product/architecture/data/metric docs, completed ExecPlan, baseline/verification/report and real unknown-state screenshots.

`frontend/next-env.d.ts` is a pre-existing generated change and is excluded from this milestone. Its SHA256 remains unchanged. No Git index change, commit or push was made.

## Key guarantees

Facts append under the existing exact identity/precision rules. Same-vintage conflicting amounts (including fiscal/frame variants) fail before selection can depend on insertion order; later filing restatements preserve old source rows. Financial Metrics/registry/FinancialOperation recognition/calculations are unchanged.

Financial and evidence streams publish independently. New facts/complete filing rows, manifest, company version and durable event commit atomically. No-op does not advance versions. Confirmed rollbacks return zero committed total/per-metric/publication counts; unknown commits return indeterminate/null fields, and durable successful commits retain actual counts. Provisional `would_insert` is labelled separately. Failure metadata requires retained admission; connection loss or indeterminate outcomes stop the job, while ordinary isolated failures can allow subsequent issuers. Evidence targets leave pending diagnostics only after commit; a failed publication retains all uncommitted targets. Abandoned attempts recover under exclusive admission; missing reports reconstruct from the database ledger.

Evidence completeness is a manifest boundary; partial chunks/vectors cannot become Ready or bypass direct-accession gates. New filings stage in memory, while existing partial filings resume without replacing text or valid vectors. Latest Q and K are discovered independently, with recent amendments, bounded targets and honest pending inventories.

Read-only consistent snapshots + expected-version headers prevent mixed-version financial/provenance responses. Selected-company freshness checks coalesce, reject stale responses and invalidate selected panels/results on publication changes. Question/controls/manual filing selection remain; no AI replay. StrictMode cleanup/re-setup and late-finally races have a permanent mounted regression. First observed evidence publication also reconciles potentially stale catalog readiness exactly once.

## Validation actually run

From `backend/`, with explicit disposable test DSN only:

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_data_refresh.py tests/test_refresh_postgres.py -q -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --tb=short
```

- **43 focused refresh tests passed**, including four real PostgreSQL tests on a separate loopback container. Each PostgreSQL case owns a UUID database: concurrent merge idempotency; independent-connection advisory admission; REPEATABLE READ answer/version coherence while a writer publishes between reads; old-head migration + Alembic check with original fixture rows preserved.
- **733 backend tests + 27 subtests passed; 13 skipped.** After the pending-target reporting adjustment, **107 refresh/sync/index tests passed**, including the strengthened PostgreSQL migration/bootstrap preservation fixture with original text and vectors. Self-review restored both original catalog CLI regressions removed during fixture editing; final full regression includes them, plus compatible per-chunk ticker/name metadata assertions. Skips are the existing opt-in database RAG suite; it was not pointed at healthy development data. Existing fiscal/basis/EPS/typed recognition regressions passed. Existing Starlette/httpx and naive datetime deprecation warnings remain.
- Source clients/encoders/providers are injected fixtures. MockTransport verifies trusted host rejection, redirects disabled, decoded-byte caps, bounded 429 Retry-After and retries. No real SEC/OpenAI call occurred.
- From `frontend/`: **64 tests passed (34 mounted)**, `npm run lint` and `npx tsc --noEmit --incremental false` passed. A new StrictMode regression first failed, then passed after admission cleanup was corrected. Existing presentation/historical/fallback protections remain.
- `npm run build` passed in a disposable frontend snapshot with the same installed dependencies. Build was repeated after the lifecycle fix. The repository's generated `next-env.d.ts` was never rewritten.
- Real read-only HTTP: health/database/catalog, AAPL/JPM/COST/JNJ/XOM freshness/summary/sources, AAPL latest revenue and historical growth passed. Catalog stays 35/35 Ready. AAPL returns exact `109417000000.0000` USD and +6.43% FY2024→FY2025 growth. Development freshness honestly reports unknown/version 0/migration required.
- Browser: actual stored AAPL data and unknown/migration disclosure inspected at 1440 and 390 widths (mobile client/scroll width both 375). Screenshots are linked in the runbook. No evidence/AI submission, live refresh or full repeated browser acceptance was performed. Version transitions are mounted fixture coverage, not real development publication.
- Syntax/import, disabled CLI/wrapper, local documentation references, whitespace and final generated-file/data preservation checks are recorded in verification JSON.

## Preservation

| Healthy development data | Before | After |
|---|---:|---:|
| Companies | 35 | 35 |
| Financial facts | 58,881 | 58,881 |
| Filing chunks | 3,175 | 3,175 |
| Embeddings | 3,175 | 3,175 |

Whole-row SHA256 fingerprints of companies/facts/chunks (including vectors) match exactly. Development revision remains `d7b834408ba8`; the new migration was applied only to disposable databases. No development metadata, financial or indexing writes occurred.

## Deferred operational acceptance / risks

1. Independent Astra review remains pending. No self-review is presented as independent approval.
2. Explicitly authorize development/target migration and metadata bootstrap cutover; keep API stopped between migration and bootstrap, then restart schema-capability cache. Migration alone would leave publication manifests empty.
3. Explicitly authorize live SEC canaries, current source-access policy review, encoder/resource measurements, subset rollout and preservation audit. No OpenAI is needed.
4. Separately authorize scheduler installation/activation. Wrapper is opt-in; no scheduled task/service was created or enabled.
5. Discovery is bounded recent-window coverage, not complete filing history. Sparse registrants stay pending. Synchronous HTTP/parser/encoder calls can overrun soft time budgets; checks prevent publication once the deadline is exceeded, but cannot forcibly interrupt a call. Peak memory still needs canary measurement.
6. Bootstrap/legacy manifests may lack exact cleaned full text; stored chunks remain readable and `/text` honestly returns unavailable. Arbitrary/manual SQL writes bypass supported versioning. Already published data has no generic rollback/exclusion facility; corrective recovery requires reviewed forward publication.

Suggested commit: `Add transactional SEC refresh and version-aware Research Mode`.

## Independent review repairs — 2026-10-08

The initial independent review found four P2 defects. This section records the
bounded repair separately from the original acceptance above; it does not claim
independent approval of the repaired implementation.

| Finding / root cause | Repair and permanent regression |
|---|---|
| Ownership probe and publication used different connections. | Refresh publication and operational writes use the admission connection. PostgreSQL tests terminate that backend after the probe and after flush/before commit, acquire admission elsewhere, verify zero publication/version advance, then recover/publish once and rerun as a no-op. Nested probes cannot commit an outer transaction. |
| Every publication exception was treated as rollback. | A fresh connection waits on the per-CIK transaction lock and reads the atomic ledger. Both facts and evidence tests inject before-commit and after-commit exceptions, check exact committed counters/versions, separate backend PIDs, ledger preservation and idempotent retry. Unreachable reconciliation returns explicit indeterminate/null fields and stops later streams. |
| Fatal error was checked after the entire stream loop. | A control-flow barrier stops before evidence or the next company. The facts-checkpoint failure test asserts no inventory/download/encoder/publication, retained committed facts, unprocessed evidence, and safe retry. |
| Observed evidence version was treated as catalog acknowledgment. | Separate successfully reconciled version and in-flight state; acknowledge only after fetch/state application. Mounted tests cover failure then same-version success, bounded/coalesced checks, question/company preservation and discarded catalog responses after company switching. |

Changed in this repair: `app/refresh_service.py`, `app/refresh_contracts.py`,
`scripts/refresh_data.py`, the two refresh test modules, frontend page/freshness/
filing components and mounted tests, this report/verification JSON, runbook,
roadmap and the implementation/repair ExecPlans. No migration or financial
selection/arithmetic changes were required. The question is held by the company
panel so first-publication filing remounts retain text while invalidating results.

Validation actually run:

- Backend: `python -B -m pytest -q -p no:cacheprovider tests/test_refresh_postgres.py tests/test_data_refresh.py`: **52 passed**, using only the opt-in disposable PostgreSQL instance and isolated SQLite fixtures.
- `python -B -m pytest -q -p no:cacheprovider tests/test_financial_sync.py tests/test_catalog_indexing.py tests/test_setup_demo.py tests/test_research_answers.py tests/test_historical_research_answers.py`: **465 passed**. A full 733-test repeat was not needed.
- After the final nested-probe guard, the three shared sync/index/setup modules were rerun: **81 passed** (a subset of the 465, not additional unique tests).
- Frontend `npm test`: **66 passed (36 mounted)**; `npm run lint`, `npx tsc --noEmit --incremental false` and `npm run build` passed. Build used a disposable frontend snapshot with the same installed dependencies, preserving repository next-env bytes.
- In-memory mutations: separate publication connection **2 failures**; disabled commit reconciliation **2 failures**; removed fatal barrier **1 failure**; acknowledgment despite failed catalog fetch **1 failure**. Expected mutation failures are evidence that real invariants are protected; source files were never temporarily weakened.
- An initial parallel mutation run exposed a test PID lookup that lacked database scoping. It was corrected to select the owning test database only and given a bounded lock timeout; final clean mutation runs and the 52-test suite passed as described.
- Five changed Python production/test files compile in memory; FastAPI imports normally. Final whitespace/reference and preservation checks are recorded in verification JSON. Existing non-failing deprecation/module-format warnings remain.

Development still contains 35 companies, 58,881 facts, 3,175 chunks and 3,175
embeddings; original full-row fingerprints and revision `d7b834408ba8` match.
No SEC/OpenAI calls, development writes/migration, dependency changes, scheduler
activation, browser rerun, staging, commit or push occurred. The private-data
source and financial rules were not changed. Focused Astra re-review is the next
acceptance step; migration/bootstrap, authorized canaries and scheduling remain
separate pending gates. See the [repair plan](../../docs/exec-plans/completed/2026-10-08-refresh-review-fixes.md).

## Transaction-cleanup integrity repair — 2026-10-08

The focused independent review found residual publication could commit in cleanup
after a before-commit error and a rollback failure before I/O. With production
autoflush disabled, a fact persisted at version zero with only a running attempt.
This was not covered by the earlier passing suites above.

The dedicated admission connection now always terminates through SQLAlchemy
invalidation/close at coordinator exit. There is no cleanup SQL or commit.
Publication DBAPI errors immediately invalidate the owner before fresh-connection
ledger reconciliation. A failed rollback cannot leave reusable pooled state;
PostgreSQL session termination releases advisory locks and aborts residual work.
Other pool connections remain reusable, with no dependency/pool-setting change.

Changed for this repair: `app/refresh_service.py`, `tests/test_refresh_postgres.py`,
this report/verification JSON, the runbook and bounded ExecPlan records. Fixtures
now match production `pool_pre_ping=True`, `autoflush=False`, `autocommit=False`.
Seven new real PostgreSQL cases cover both streams/both rollback failure phases,
coordinator cleanup with an externally failed session, and driver commit followed
by lost acknowledgment. Assertions include flushed rows, zero aborted publication,
physical closure/non-reuse, recovered ownership, exact ledger/version counts and
one successful retry followed by no-op. Existing unknown-outcome tests retain null
counters, preserve successful ledgers and stop subsequent evidence acquisition.

Validation actually run:

- Seven focused new PostgreSQL cases passed.
- Refresh/PostgreSQL, financial sync, catalog indexing, demo setup, deterministic
  latest and historical answer suites passed together: **524 tests**, comprising
  **59 refresh/PostgreSQL** and **465 financial/compatibility** cases.
- In-memory restoration of unlock-and-commit cleanup caused **one expected failure**:
  actual persisted fact count 1 versus required 0. Repository source was not weakened.
- Both changed Python files compiled in memory; FastAPI import passed.
- Read-only development fingerprints match the baseline: 35 companies, 58,881
  facts, 3,175 chunks/embeddings; revision remains `d7b834408ba8`.

No frontend changes/tests/build, development writes/migration, SEC/OpenAI calls,
dependencies, scheduling, staging, commit or push. The generated next-env file
remains byte-identical. This closes the Builder repair only; final independent
Astra re-review and all operational rollout gates remain pending. See the
[cleanup plan](../../docs/exec-plans/completed/2026-10-08-refresh-transaction-cleanup.md).
