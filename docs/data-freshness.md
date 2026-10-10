# Data freshness and controlled refresh

Status (2026-10-09): **development deployment completed and independently accepted (Astra PASS)**. Live SEC refresh is not yet validated; automatic scheduling is disabled. Offline implementation history remains in [verification](../backend/reports/data_freshness_verification.json), [implementation report](../backend/reports/data_freshness_implementation.md) and the [completed implementation plan](exec-plans/completed/2026-10-08-data-freshness-automatic-refresh.md).

## Accepted development deployment

These are accepted execution results, not checks repeated during documentation closure:

- Database `finlens`, OID `16384`, cluster `7692131504986030119`; Alembic `f94c6f41e0cb`; libc collation recorded/runtime `2.36 / 2.36`.
- Offline bootstrap committed 35 `filing_publications`, 35 `company_refresh_state`, zero `refresh_attempts`. Initial data/stream versions are zero and freshness is **unknown**: publication of legacy stored evidence does not prove a live SEC check.
- Fresh backup: `D:\Backups\FinLens\freshness_20261009_185544_4121139\finlens.dump` (9,649,856 bytes), SHA256 `de34c8aaccddee686fb9a81f130d8bde734e7921eb3ce80b1025eba2a18cd077`. Archive inventory and complete decode passed; this deployment did not include a fresh isolated restore or a cluster-global/PITR backup.
- Independent acceptance: `D:\FinLens-OperatorReports\freshness_independent_acceptance_20261009_233932_0408181`. Original execution and final recovery evidence are retained outside Git. Thirty independent HTTP checks accepted backend, frontend proxy, freshness, financial Research and stored evidence.
- All four original row/vector fingerprints matched: 35 companies, 58,881 facts, 3,175 chunks and 3,175 embeddings. Scheduler remains disabled; no live SEC refresh or OpenAI acquisition was accepted.

Remaining rollout: the [one-company offline canary plan](exec-plans/active/2026-10-09-sec-live-canary.md), independent live acceptance/resource measurement, separately authorized wider coverage, then separately authorized scheduling. Do not rerun backup/migration/bootstrap merely to close documentation.

### Historical Research incident

**Historical intermittent HTTP 500; currently not reproducible.** The user observed AAPL `revenue growth` displaying a plausible 16.36% deterministic answer alongside HTTP 500, then independently retried without the error. This is not a verified financial-value audit or a completed bug fix. Scoped existing deployment/recovery log inspection supplied no concrete Research-error cause. The supplemental reporting `KeyError: 'table'` was a separate read-only reporting incident after successful deployment; it is not evidence of the Research error's cause. If the HTTP error recurs, capture the request/route, timestamp and sanitized backend traceback before diagnosing it.

## Publication architecture

`refresh_data` delegates to the coordinator in `refresh_service.py`, reusing SEC acquisition, Company Facts merge, filing parser/chunker and local MiniLM encoder. FinancialMetrics, its registry, typed operation dispatch, Decimal calculations and financial interpretation are unchanged. No new dependency, queue, HTTP write endpoint or startup job is introduced.

A process lock and a PostgreSQL session advisory lock admit one supported SEC job across processes. Per-CIK transaction advisory locks and row locks serialize publication. Refresh stream publication and operational updates use the physical PostgreSQL connection holding admission; losing that connection aborts its uncommitted transaction rather than letting a displaced worker publish through another connection. Nested admission probes never commit an active publication. Supported legacy sync/index/demo/embedding commands share admission and publication hooks. Unmanaged SQL writers are outside this protocol and must not run concurrently.

The admission connection is dedicated to one job and is physically invalidated
and closed on every exit, including healthy completion. Cleanup issues no SQL
unlock or commit: closing the PostgreSQL session aborts residual work and releases
its session advisory locks. This deliberately retires one connection per job;
other pooled connections remain reusable. Publication DBAPI exceptions invalidate
the owner immediately, before independent ledger reconciliation. This includes
rollback failures before I/O and failures after rollback reached PostgreSQL;
SQLAlchemy's inactive transaction flag alone cannot prove rollback completed.
Tests match production `pool_pre_ping=True`, `autoflush=False` and `autocommit=False`.
Reconciliation needs a separate available pool connection; the current default
pool supports this without configuration changes.

The additive revision `f94c6f41e0cb` (parent `d7b834408ba8`) adds:

| Table | Responsibility |
|---|---|
| `company_refresh_state` | Company-wide monotonic data version, facts/evidence versions, validated JSON state per stream. |
| `refresh_attempts` | Durable run/attempt identity, status, timestamps, sanitized result, source digest and unique committed company/version event. |
| `filing_publications` | Complete company/accession manifest: source identity, chunk count/digest, parser/model configuration, publication time/version and optional exact cleaned full text. |

There is no change to existing financial/chunk/vector columns. Facts remain insert-only. Each stream stages source work outside the short publication transaction; validated rows, manifest, version and successful attempt finalize together. Reports publish committed counts only after commit or durable-ledger reconciliation. Confirmed rollback removes the whole publication and records safe failure metadata while admission is still owned. Displaced workers leave recovery to the next admitted worker. Prior publications remain readable. Facts may advance while evidence fails; their versions/statuses remain distinct. There is no cross-stream atomicity.

Publication exceptions are reconciled on a fresh database connection. A bounded five-second lock/statement wait on the per-CIK transaction lock ensures the old publication has ended before its durable attempt is interpreted. A successful ledger entry supplies the committed result without being overwritten. A still-running/failed/interrupted attempt after that barrier confirms no successful publication. If reconciliation cannot establish truth, the report uses `status=indeterminate`, `commit_outcome=indeterminate`, null committed counts/per-metric counts/version-after, and `commit_outcome_unknown`; later streams stop. `would_insert` remains a clearly provisional diagnostic. Other outcomes distinguish `not_attempted`, `committed`, and `rolled_back`.

Evidence readers and readiness count **published complete accessions**, not any embedded row. Validation requires contiguous identities, consistent source metadata/offsets and finite nonzero 384-dimensional vectors. New evidence is staged in memory, then published atomically. Stored incomplete filings resume without downloading or replacing text/valid vectors. An interrupted uncommitted stage may need to reacquire a new filing; existing partial stored chunks remain reusable. Compatibility ingestion can persist unpublished chunks, but cannot expose them as complete research.

Refresh discovers the latest exact 10-Q and 10-K independently, plus amendments in the bounded recent submissions window (maximum 2,000 metadata entries). It does not crawl archived history. Missing either base form, an incomplete inventory or capped backlog remains pending. `current` certifies only this declared scope, never unlimited EDGAR coverage. Sparse/current-registrant XOM is not merged with a predecessor.

## Financial revisions

Existing exact source identities, precision validation and fiscal/economic-basis selection are reused. Later-filed/accession comparative observations append with original provenance preserved. Conflicting amounts in the same company/concept/unit/dates/accession/filed/form context fail the company before publication, including frame/FY/FP variants that would otherwise rely on insertion order. This is a rejection diagnostic (`ambiguous_source_revision`), not an automatic correction or a new persisted quarantine store. The prior dataset/version survives; an operator must investigate. Disappeared source observations are not deleted.

## Freshness and read consistency

`GET /companies/{ticker}/freshness` exposes `data_version`, `facts_version`, `evidence_version`, stream status, attempt/check/success times, source filed date, pending targets, safe failure stage and latest published filing. UTC check times are distinct from SEC filed dates. Aggregate status preserves the worst stream state: failed, pending, stale, unknown, current. A successful check older than 36 hours becomes stale; bootstrap and compatibility writers cannot claim a source check and remain unknown. No-op checks update operational timestamps without changing versions.

Company-scoped API responses carry `X-FinLens-Data-Version` and `Cache-Control: no-store`. An optional expected-version request header rejects a changed dataset with safe HTTP 409 / `DATA_VERSION_CHANGED` before loading facts. Dedicated PostgreSQL reads use REPEATABLE READ + READ ONLY; writers remain READ COMMITTED. Related frontend requests reject version disagreement and trigger one coalesced freshness check, rather than combine incompatible responses.

Warm migrated query counts: financial summary/history/matched answer **3 SELECTs** (version plus existing catalog/company and fact loads); rejected recognition **2**; sources **4**; freshness **4**; company catalog **1 aggregate SELECT**. FinancialMetrics service still uses two SELECTs and no per-metric fan-out. Initial schema-capability inspection adds bounded catalog queries once per engine; restart API after migration. Unmigrated catalog fallback uses **2 bulk SELECTs**, validates complete stored accessions in memory and never writes metadata. It is transitional and more expensive than the migrated manifest query.

Research Mode checks freshness once for the selected company, on focus/visibility return and every five minutes while visible. Requests coalesce and abort on cleanup; StrictMode re-setup is covered. Catalog reconciliation tracks successfully applied evidence versions separately from observed metadata. A failed catalog request stays pending and retries on a later freshness check at the same version, with one request in flight and no immediate retry loop. Company switches abort reconciliation and discard old responses. A data-version change refetches summary/selected history/sources and invalidates answer/evidence/AI products. Company, period/metric controls, question and a still-published manual filing selection remain; question state also survives the first filing becoming available. AI is never replayed automatically. Metadata failures preserve usable research and disclose that currency is not verified.

All normal read routes use stored data. `/chunks` returns stored published chunks. `/text` returns exact stored cleaned text, or 409 / `STORED_TEXT_UNAVAILABLE` for older bootstrap manifests; it never reconstructs text from overlap or fetches SEC. Keyword/semantic/context/optional answer routes centrally require a published accession. Retrieval ranking and Evidence Policy are unchanged.

## Operator commands and safe rollout

The development collation repair and migration/bootstrap cutover are accepted;
their historical procedures remain in the [collation runbook](collation-remediation.md)
and external revision-4 deployment evidence. For other installations, diagnose
collation and obtain target-specific authorization before maintenance.

Run backend commands from `backend/` using `.venv/Scripts/python.exe`. **Steps 1–4 are completed on development; retain them as cutover guidance for other authorized targets. Do not repeat them on the accepted database. Steps 5–6 still require separate live-canary authorization and the linked plan's gates.** Keep private database/contact settings in ignored env files. No OpenAI key is required.

1. Stop source-writing jobs; record read-only counts/full-row fingerprints and take an operator-managed backup. Confirm isolated tests and independent review first.
2. Stop API for the migration/bootstrap cutover. On an existing dataset, migration alone creates empty manifests; do not serve the migrated catalog before validated bootstrap.
3. Apply the additive revision and offline bootstrap:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
.venv/Scripts/python.exe -m scripts.refresh_data --all --bootstrap
```

Bootstrap validates the complete stored inventory, retains rows/vectors and records version-zero manifests without fabricated check dates. It is idempotent, only intended before versioned publication, and must be resolved before restart if invalid accessions are reported. Fresh clones instead migrate then run the existing `scripts.setup_demo`; no legacy bootstrap is needed.

4. Restart API (schema capability is cached); verify readiness, sources, unknown freshness and unchanged original fingerprints. Keep scheduler disabled.
5. After separate live acquisition authorization, validate private SEC contact and cached encoder; perform one-company discovery-only dry-run followed by a small canary. The narrowly authorized AAPL publication must use the opt-in gate below rather than the unrestricted example:

```powershell
.venv/Scripts/python.exe -m scripts.refresh_data --ticker AAPL --dry-run --allow-network --report reports/canary-discovery.json
.venv/Scripts/python.exe -m scripts.refresh_data --ticker AAPL --allow-network --max-filings 1 --max-seconds 300 --max-run-seconds 600 --report reports/canary-publication.json
```

`--dry-run` still acquires source metadata/Company Facts and requires network authorization. It performs no database/operational writes and no embedding work. `would_insert` means observations for facts, filings for evidence; committed counters stay zero. Successful dry-run status is `would_update`/`no_change`, not a freshness certification.

6. Audit appended identities, original-row fingerprints, revisions, source lineage, independent stream statuses and UI version invalidation. Repeat no-op/recovery, then explicitly approve broader rollout. Use repeated `--ticker`, `--all`, `--stream facts|evidence|both`, bounded `--max-filings`, stream `--max-seconds` and total `--max-run-seconds`. No selection/no `--allow-network` means no acquisition.

Reports use new filenames and atomic replacement of that run's checkpoints. To reconstruct a committed run after report loss:

```powershell
.venv/Scripts/python.exe -m scripts.refresh_data --show-run <run-uuid>
```

The durable ledger is authoritative, including abandoned/interrupted attempts. Failed company streams can be retried; a global database outage or lost coordinator lock stops the job. Fatal checkpoint/database errors stop before the next stream, including evidence after facts. Earlier committed facts remain committed and are reported honestly. A retry discovers those identities and does not insert them twice.

For an indeterminate commit, stop automatic retries, restore database connectivity and inspect `--show-run` using the recorded run UUID. A durable successful attempt is the committed truth even when its original acknowledgment was lost. An abandoned running attempt is recovered under exclusive admission by the next controlled run; the idempotent source merge prevents duplicate publication. Never interpret null committed counts as zero, rewrite a successful ledger entry, or decrement versions to match a failed report.

After a publication DBAPI error the original owner is discarded even when fresh
reconciliation confirms the outcome. A committed ledger returns its exact counts
and version; confirmed absence of successful publication returns `rolled_back`
and zero committed counts. If the fresh read is unavailable, the outcome remains
`indeterminate` with null counts/version. An invalidated owner cannot record failure
metadata or start another stream; `refresh_busy_or_lock_lost` can accompany a
confirmed rollback. Its original running attempt is retained for the next
controlled coordinator to mark interrupted, rather than being rewritten without
ownership. Use the run UUID and ledger before deciding which streams to retry.

## Exact AAPL publication scope

Offline implementation: [scope gate plan](exec-plans/completed/2026-10-10-canary-source-authorization.md).
Independent code review and live acceptance remain required. Proposed command
for separately authorized execution, **not executed by this fix**:

```powershell
Set-Location D:\Projects\finlens-foundation\backend
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$canaryStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$canaryReport = "reports/canary-$canaryStamp-publication.json"
& .\.venv\Scripts\python.exe -B -m scripts.refresh_data --ticker AAPL --stream both --publication-scope aapl-10k-2025 --allow-network --max-filings 1 --max-seconds 300 --max-run-seconds 600 --report $canaryReport
if ($LASTEXITCODE -ne 0) { throw 'Stop; reconcile report and ledger. Do not retry.' }
```

Use the accepted pinned Core/Docker/Python procedure and fresh monitoring session.
The named profile requires AAPL/CIK `0000320193`, both streams, one filing and
300/600-second maximum budgets. Under admission it acquires/copies both metadata
sources once, validates conflicts and **zero** new supported facts, and requires
the complete selected inventory to be exactly the authorized 10-K
`0000320193-25-000079` (2025-10-31, `aapl-20250927.htm`) plus the already published,
complete 10-Q `0000320193-26-000020` (2026-07-31, `aapl-20260627.htm`). Amendments,
competing/incomplete/changed scope, already published/partially stored targets,
and unsettled running attempts fail before any persistent write.

Reports retain validated source digests; execution reuses the captured sources
without metadata refetch. Raw envelope/header and primary document identities
must match the pin before embedding. Guarded facts publication uses only a dry
merge and cannot insert facts; evidence scope is rechecked at stream entry and
publication. A guarded stream failure stops subsequent streams. Once the initial
gate passes, ordinary separate stream commits still apply: a facts no-change check
may commit before raw/evidence failure. Such later failures may record metadata;
an initial scope rejection does not. Reconcile uncertain outcomes; do not retry.

The two SEC responses are sequential, not an atomic upstream snapshot. Supported
writers share admission; unmanaged SQL must remain excluded operationally.
Soft resource limits and cooperative deadlines are unchanged (preflight consumes
the facts-stream budget). Without this opt-in, ordinary refresh defaults, scope
and recovery are unchanged. A separate dry-run neither pins nor authorizes the
sources acquired by a later invocation.

## Scheduling: disabled

`Refresh-FinLens.ps1` is an opt-in wrapper, not a registered task. It requires **both** `-EnableLiveRefresh` and `FINLENS_REFRESH_ENABLED=1` in that process. No setting is enabled by this implementation.

After live canary/review and explicit scheduler authorization, a Windows Task Scheduler action can invoke:

```powershell
powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -File D:\Projects\finlens-foundation\Refresh-FinLens.ps1 -EnableLiveRefresh
```

Configure the task's account/environment intentionally (including the opt-in variable), working directory, private backend env access and local cached model. Use a disabled task initially; choose one daily trigger at 06:00 UTC (14:00 Asia/Macau), no overlapping instances, run only on the intended host and log the sanitized exit code/run UUID. Enable only after the operator authorizes it. Stop scheduling by disabling the task and removing the opt-in variable. This repository does not install a service or task or claim scheduler activation was tested.

## Security, budgets and recovery limits

SEC code restricts HTTPS hosts/path families, disables redirects, uses private validated identification, sequential 250 ms pacing, 60-second HTTP timeout, at most three attempts, bounded backoff/Retry-After (30 seconds) and a 64 MiB decoded-response cap. Global cooperative admission serializes supported SEC jobs across processes. Error output excludes contact details, credentials, source bodies and raw exception text. URL safety/redirect/size/retry tests use offline MockTransport, never SEC. Existing source-policy links were not revalidated through live SEC contact this round; current fair-access policy must be reviewed before rollout.

Defaults are two filing targets per company-stream, 300-second stream and 1,800-second run budgets; bounded overrides are validated. Deadlines are checked between acquisition/index batches and before publication. A running HTTP/parser/encoder call cannot be forcibly interrupted by this synchronous worker, so elapsed time can exceed a budget; over-budget staged work is not published. A byte cap is not a peak-memory guarantee. Live canaries must measure memory, encoder latency and scope coverage before scheduling.

Pre-commit recovery is rollback and retry. Post-publication recovery is forward-only: stop jobs, investigate and design a reviewed corrective publication. Do not decrement versions, delete original facts, replace valid vectors, run destructive downgrades or remove database volumes. Unknown/manual SQL writes bypass versioning and must be prohibited operationally. No general historical rollback/exclusion system is added.

## Validation boundary

Offline API/service, real disposable PostgreSQL migration/locking/isolation and mounted UI regressions passed; original full financial regression and read-only HTTP/browser acceptance remain recorded in [verification](../backend/reports/data_freshness_verification.json). The repair record separately records 52 refresh/PostgreSQL tests, 465 deterministic/compatibility tests, 66 frontend tests, lint/type/build and four detected mutations. Screenshots show the historical **unmigrated/unknown** deployment at [desktop](screenshots/data-freshness/desktop-unknown.jpg) and [mobile](screenshots/data-freshness/mobile-unknown.jpg). Version-change/retry UI acceptance is fixture-based. Browser acceptance was not repeated for those repairs. The accepted deployment above supersedes their old migration-pending status: original financial/vector data were preserved through the additive migration. Live SEC canaries, resource measurements and scheduler activation remain pending.

The subsequent [transaction-cleanup repair](exec-plans/completed/2026-10-08-refresh-transaction-cleanup.md)
adds seven PostgreSQL cases and production fixture settings: 59 refresh/PostgreSQL
plus 465 financial/compatibility tests passed together (524 total). Restoring unsafe
cleanup in memory caused the regression to persist a fact incorrectly. Frontend
tests/build were not repeated because this correction changes no frontend files.
