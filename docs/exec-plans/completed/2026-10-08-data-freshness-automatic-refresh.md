# Data Freshness & Automatic Refresh

Status: completed — offline implementation acceptance (2026-10-08). Independent review and operational rollout remain pending; live acquisition/scheduling are not authorized.
Roadmap phase: scoped Research Mode correctness/operations milestone; no later roadmap item authorized.

## Objective

Keep stored financial answers, comparisons, charts and filing evidence current through controlled, incremental SEC refreshes. Publish only validated changes, preserve original observations/provenance, and make source age, check age and failures visible. Research Mode must remain useful without an LLM.

The architecture audit below records the pre-implementation baseline and proposal; it is retained as historical context. The implementation closure at the end and the [canonical refresh runbook](../../data-freshness.md) describe delivered behavior and approved scope. Follow [AGENTS](../../../AGENTS.md), [ExecPlan rules](../../../.agent/PLANS.md), [roadmap](../../../ROADMAP.md), [engineering standards](../../engineering-standards.md), [architecture](../../architecture.md), [product spec](../../product-spec.md), [data policy](../../data-sources.md) and [financial contracts](../../financial-metrics.md). Those documents remain authoritative for existing behavior.

## Current architecture and context

Audit date: 2026-10-08. Starting HEAD: `57eeed64a3d0cb12bc20fc75a7fca76d52f84fb1`. Answer Presentation and Historical Answers are already committed (`9b3dee4`, `57eeed6`). The only starting change is generated `frontend/next-env.d.ts`; preserve it byte-for-byte. Its starting SHA256 is `f4e8976c19fc926644d72610bf1058bd6bf52add97e46a02bc0b912a751625c0`.

The [recorded historical baseline](../../../backend/reports/historical_answers_baseline.json) contains 35 companies, 58,881 FinancialFacts, 3,175 FilingChunks and 3,175 embeddings. The [verification/report](../../../backend/reports/historical_answers_final_report.md) records matching whole-row/vector fingerprints after prior validation. These are recorded results, not a fresh database inspection in Phase 1. No database connection, service startup or source request is needed for this audit.

### Existing system audit

| Area and exact files | Observed implementation | Refresh implication |
|---|---|---|
| [SEC client](../../../backend/app/sec_client.py): `_sec_get`, `get_company_facts`, `discover_filing`, `select_latest_filing` | Validated private contact User-Agent; 60-second timeout; sequential process-local 250 ms spacing; three attempts with 2/4-second backoff for selected HTTP/transport failures; redirects followed. Company Facts parses floats as Decimal and submissions checks CIK. Discovery prefers an exact 10-Q even over a newer 10-K, then falls back; archives consulted when needed. | Good acquisition base, but spacing is not shared across processes. No conditional-fetch metadata, response-size/job budgets or redirect-host enforcement. Baseline preference is not a freshness inventory. |
| [Parser](../../../backend/app/sec_parser.py): `normalize_fact_data`, `extract_primary_filing_document`, `clean_filing_html`, `chunk_filing_text` | Normalizes source metadata; extracts requested primary form; removes hidden/XBRL metadata; chunks cleaned text at 2,500 characters with 250 overlap. | Reuse unchanged. Document text and chunk offsets need a durable publication manifest; successful parsing is not proof of numerical interpretation. |
| [Importer](../../../backend/app/sec_importer.py): `validate_item`, `fact_identity`, `merge_company_facts` | Reviewed base concepts/units reused from registry. Validates finite Numeric(24,4), dates, accession and metadata. Retains every distinct source observation; no deletes. Identity includes CIK, concept, unit, dates, value, accession, filed, form, frame and source FY/FP. Transaction advisory lock per CIK, requiring READ COMMITTED, serializes supported writers. | Idempotency and original preservation already exist. A changed value is a distinct observation, not an update. No DB unique observation constraint; arbitrary writers bypass the lock. Need publication/version integration and conflict diagnostics, not a second importer. |
| [Fact sync service](../../../backend/app/financial_sync_service.py): `sync_catalog`; [CLI](../../../backend/scripts/sync_financial_facts.py) | Sequential fetch per selected issuer; fresh company session/atomic transaction; merge results published only after commit. Failures discard session and check DB health. Interruption preserves earlier commits. Dry-run and subset supported; sanitized atomic JSON checkpoints. | Reusable transaction/report semantics. `already_current` means no missing supported identities in that response, not durable freshness. No persisted last-check/version/run ledger. Full-catalog normalization report loads all stored facts; avoid doing that after each scheduled single-company job. |
| [Catalog indexer](../../../backend/app/catalog_indexing_service.py): `index_company`, `validate_filing`; [CLI](../../../backend/scripts/index_catalog.py) | Any complete valid stored accession satisfies baseline and skips discovery. Missing embeddings resume without SEC. Invalid siblings diagnosed and not replaced. Report counts are reread after failure. | Baseline coverage is intentionally not refresh. Discovery must run separately from the skip path and target explicit new accessions. Current validator accepts only exact 10-Q/10-K; amendments need explicit refresh-path validation/tests. |
| [Filing persistence](../../../backend/app/sec_filing_service.py): `ingest_filing_chunks`; [embeddings](../../../backend/app/embedding_service.py): `embed_filing_chunks` | Preservation flag avoids replacement; legacy default can delete an accession's chunks. Chunks commit before embeddings. Embeddings validate finite nonzero 384-dimensional vectors, fill only missing values and commit all batches; failure rolls back vector work. Model instance alone is LRU-cached. | Never use replacing default for refresh. Partial chunks are durable and resumable, but must not be advertised as published evidence. Existing helpers own commits, so a refresh publication path needs an explicit outer transaction rather than wrapping these committing helpers unchanged. |
| [Models](../../../backend/app/models.py), [database sessions](../../../backend/app/database.py), [migrations](../../../backend/migrations/versions/) | Three tables: companies, financial_facts, filing_chunks; unique ticker/CIK and unique accession/chunk_index; no refresh/version/publication tables. Fact provenance is rich; `created_at` is storage time. Migration chain ends at `d7b834408ba8` after companies/facts/chunks. | New additive operational tables are justified. Existing fact/chunk IDs and fields must remain intact; no migration-history rewrite or unique-key retrofit deleting duplicates. |
| [FinancialMetrics](../../../backend/app/financial_metrics_service.py): constructor, `fiscal_observation`, `compare_fiscal`; [registry](../../../backend/app/financial_metric_registry.py) | One company fact load, no persistent normalized-data cache. Resolves economic scope before latest filed/concept/form/amendment/accession/ID priority; preserves alternatives. Fiscal labels/boundaries and compatible units/derived operands are checked; Decimal arithmetic and EPS warnings retained. | Later valid filings can change earlier-period current answers. Freshness must track source vintages and dataset publication, not simply the newest reporting end. No new financial selector or arithmetic layer. |
| [Research Answers](../../../backend/app/research_answer_service.py): `answer_research_question`, `operation_agrees`; [API](../../../backend/app/main.py) | Immutable typed operation agreement before fact loading; supported answers use catalog + company-facts SELECTs; latest/historical/comparison endpoints reuse Metrics. Search/context are stored-data paths. `/companies` counts distinct accessions with any non-null vector; `/sources` treats any stored accession as searchable. Legacy `/text` and `/chunks` GET handlers call `get_filing_raw_text` and parse live SEC data. | Preserve operation/financial semantics. Add bounded version reads with a consistent DB snapshot. Gate publication at accession level without changing ranking. Legacy GET download behavior contradicts the target's no-interactive-SEC rule and needs a planned stored-only transition. |
| [Search](../../../backend/app/filing_search_service.py): `hybrid_search_filing_chunks`; [context](../../../backend/app/rag_context_service.py) | Company/accession-scoped DB retrieval; hybrid candidates may include chunks without embeddings for lexical relevance. | Do not globally remove lexical candidates or rerank. Require that the requested accession is published before invoking existing retrieval. |
| [Frontend API](../../../frontend/lib/finlens-api.ts), [Next config](../../../frontend/next.config.ts) | Fetch uses `cache: "no-store"`; same-origin rewrite proxies FastAPI. No dataset-version protocol or client data-cache library. | Browser cache bypass does not re-fetch mounted state after a background write. No new caching framework is needed. |
| [Page](../../../frontend/app/page.tsx), [financial workspace](../../../frontend/components/financial-research.tsx), [filing workspace](../../../frontend/components/filing-research.tsx), [request scopes](../../../frontend/lib/research.ts) | Catalog/capabilities load on mount; summary/history on selected controls; sources on company; answers/evidence on submit. Abort cleanup, scope guards and company/filing remount keys prevent user-scope races. Direct answer, evidence and optional AI settle independently. | Existing guards do not detect a data change for the same company. Add version to research scope and trigger bounded invalidation automatically. Preserve controls and independence. |
| [Compose](../../../docker-compose.yml), [Start](../../../Start-FinLens.ps1), [Stop](../../../Stop-FinLens.ps1), [demo setup](../../../backend/scripts/setup_demo.py) | Local PostgreSQL volume/healthcheck; development process lifecycle; explicit idempotent demo setup. No scheduler/queue/refresh worker found in app/scripts. | Reuse local CLI execution and OS scheduling; do not put acquisition in server startup or normal page requests. Existing operational writers must participate in publication accounting. |
| [Sync tests](../../../backend/tests/test_financial_sync.py), [index tests](../../../backend/tests/test_catalog_indexing.py), [metric tests](../../../backend/tests/test_financial_metrics.py), [historical tests](../../../backend/tests/test_historical_research_answers.py), [typed handoff tests](../../../backend/tests/test_research_operation_handoff.py), [mounted frontend tests](../../../frontend/tests/research-interactions.test.mjs) | Offline fixtures already cover merge identity, restatements, commit/flush failure, next issuer, interruption, missing vectors, invalid siblings, periods, compatibility, typed dispatch and UI races. | Extend production-path fixtures for version publication and background changes. SQLite cannot validate PostgreSQL advisory locks/isolation; require disposable PostgreSQL concurrency tests too. |
| [Fingerprint utility](../../../backend/scripts/verify_financial_metrics.py): `fingerprint`; [structured audit](../../../backend/reports/structured_financial_verification.json); [historical verification](../../../backend/reports/historical_answers_verification.json) | Whole-row ordered JSON hashes include chunk vectors; prior reports retain original-row preservation evidence. | Reuse read-only fingerprint function, not entire verifier entrypoints with broader behavior. During future append-only refresh compare original row subsets, not expect whole-table hashes to stay equal after intended inserts. |

## Constraints and non-goals

- Phase 1 was documentation only. The subsequent implementation request authorizes source changes, isolated migrations and offline tests, but forbids development database writes, SEC/OpenAI contact, live scheduling, staging, commit or push.
- Preserve current metric registry/selection, fiscal quarter versus YTD/annual separation, no synthesized Q4, economic-basis safeguards, Decimal arithmetic, EPS comparability, typed recognition, evidence policy and citation boundaries.
- No arbitrary company/predecessor substitution, new metric mappings, market prices, Portfolio, Risk, ML, cross-company analysis, paid AI audit or historical filing backfill project.
- Implementation is now authorized with those limits. Destructive rollback/volume deletion never becomes an automatic recovery step.

## Gap analysis and proposed architecture

Missing: durable per-stream checks/status, discovery of newer filings for Ready companies, atomic evidence publication, version events, frontend invalidation, controlled scheduling and recovery ledger. Existing manual sync is reusable; a parallel catalog, importer, financial selector, retrieval engine or job framework is unnecessary.

Proposed flow: **scheduled/manual CLI → stored-company selection → serialized discovery → bounded validation/staging → stream publication transaction → versioned DB reads → client invalidation**. Facts and evidence are separate streams; successful facts may publish while indexing fails. Aggregate freshness must expose that partial failure, never claim the entire company is current. Network and embedding work occur outside short publication transactions.

### Schema/migration requirements (proposed, not applied)

Add three small operational tables in a new Alembic revision after the current head:

1. **CompanyRefreshState**: unique company CIK/FK, monotonic BIGINT `data_version` (initial 0), per-stream version and explicit facts/evidence check/success/attempt timestamps, source filing dates, status/error codes and next-due time. Derive the aggregate response from these fields; do not store an independently drifting aggregate status.
2. **RefreshAttempt**: UUID attempt/run identity, company/stream, start/finish/status, policy/parser/model versions, source digest/identity, discovered/validated/committed counts, before/after versions, safe error and pending targets. A committed change has a unique company/version event; no-change/failed/dry-run rows cannot impersonate change events. Version and successful event are committed with the actual data. Group attempts by run ID; no fourth run table needed initially.
3. **FilingPublication**: unique company/accession, form/filed/filename, validated expected chunk/vector counts, cleaned-document digest, parser/chunk/model configuration, publication timestamp/version and published state. Retain full cleaned text for new filings so stored-only `/text` is exact; citation offsets keep their existing meaning. Partially staged work is never published.

All timestamps use timezone-aware UTC; dates remain SEC dates. Constrain enums, nonnegative versions/counts, identities and event uniqueness. No normalized financial table, destructive backfill or modification to original facts/chunks/vectors. Validate legacy filings before registering baseline publication at version 0; unknown check/sync times stay null. A baseline manifest proves stored completeness, not SEC currency. Legacy full text may be reconstructed only when offsets/overlaps prove exact contiguous coverage; otherwise return an explicit stored-text-unavailable state, never silently download or claim exact text.

Migration tests must preserve baseline row IDs and original column/vector fingerprints. Whole-row hashes of old tables must remain equal when no old-table columns change. Keep old evidence unpublished if validation fails; report it rather than delete or repair silently.

### Discovery and incremental publication

- Facts: reuse full Company Facts payload and reviewed mappings; compare exact supported identities. Do not skip checks merely because the newest filing date is unchanged: SEC can revise a response. Record a canonical supported-observation digest and distinguish source changes from actionable supported inserts.
- Filings: inventory latest eligible **10-Q and 10-K separately**, plus relevant 10-Q/A and 10-K/A in the bounded discovery window. Compare accessions against publication manifests; preserve every old accession. New discovery must not reuse baseline `index_company`'s early skip as a currency check. No arbitrary historical backfill; report backlog/discovery bounds. A capped/incomplete inventory is pending, not current.
- Default proposal: sequential companies, at most two new full filings per issuer per run, explicit archive-page/response-byte/elapsed-time limits; a reached limit checkpoints pending work. Final limits should be set from offline load fixtures and canary measurements before enabling scheduling. Do not claim complete amendments coverage beyond the checked window.
- Facts publication: validate all candidates and conflict diagnostics before inserting; reuse `merge_company_facts` under READ COMMITTED and its advisory lock. Short transaction inserts missing rows, increments the company/stream version and commits the successful event. Expose provisional counts only as `would_insert`; expose committed counts only after commit. A rollback advances neither data version nor committed totals.
- Evidence publication: reuse parser, chunker and encoder/validation; stage a bounded cleaned document/chunks/vectors in memory or ignored private cache keyed by CIK/accession/content/config digest. Extract transaction-neutral persistence primitives with existing helper wrappers retained for compatibility; do not call internally committing helpers inside a purported atomic outer transaction. Insert a complete new accession, publication manifest and version event atomically. For pre-existing incomplete accessions, validate identity/text and fill only missing vectors in that same publication boundary; preserve non-null vectors.
- Gate catalog availability, `/sources`, text/chunks, keyword/semantic/context/answer entrypoints on a valid published accession. Keep existing lexical/semantic ranking and thresholds unchanged inside that scope. A previously published accession stays usable if a newer target fails. Avoid an API where directly requesting an unpublished accession bypasses the gate.

### Restatements and provenance preservation

Reuse [current selection policy](../../financial-metrics.md#period-and-selection-policy). Original IDs, exact values, units, concepts, dates, source fiscal metadata, accession and stored timestamps remain immutable. A later filing's compatible observation is appended and may supersede an older source for the same exact reporting period by the existing ranking; both remain accessible as selected/alternative provenance. This is latest-known data, not an as-of filing reconstruction.

Before publication, detect changed values sharing the same source context identity excluding value, and same-priority conflicting candidates. A source correction within the same accession/context lacks reliable revision chronology; do not let insertion ID decide a financial revision. Conservatively quarantine the candidate facts batch (controlled failed/review-required outcome, unchanged prior published facts/version) and retain digest/diagnostics for review. Do not change selector priority or delete the older observation to resolve it. Later-accession restatements with clear existing priority can append normally; incompatible scopes still produce unavailable results. Quarantine diagnostics must not claim provisional candidates are persisted facts.

Recompute affected histories and derived metrics through FinancialMetrics on the next versioned read. New annual boundaries may change quarter labelling/availability for existing observations; this is a dataset change even when the newly filed period is old. Preserve JPM bank basis, COST incompatibility, XOM current registrant and reported-as-filed EPS warnings. Record selected-source/availability changes separately from inserted row counts.

### Refresh CLI and scheduler design

Proposed command from `backend/`: `.venv/Scripts/python.exe -m scripts.refresh_data --ticker AAPL --stream both --dry-run` (not implemented). Repeated stored tickers or explicit `--all`; stream facts/evidence/both; bounded limits; run ID; controlled report path. Manual invocation and scheduling share one coordinator. Validate selection/schema/contact/report permissions before source calls; never accept caller-supplied fetch URLs. A CLI without explicit selection should show help rather than silently refresh the catalog.

Dry-run may fetch when live execution is later authorized, but performs no durable DB writes, version increments, publication, timestamp updates or model generation. It reports would-insert/would-index and unknown validation where embeddings were not produced. Offline fixture mode injects acquisition/encoder functions; it must forbid real SEC/OpenAI clients. Exit codes distinguish success/no-change, partial failure/pending and invalid configuration/global outage. JSON reports use atomic replacement, sanitized errors and unique run paths; DB state is the authority if file writing fails after commit.

Use Windows Task Scheduler to invoke the existing venv CLI once daily, proposed at 06:00 UTC, with missed-run catch-up and non-overlap. Document an equivalent cron command for other hosts; do not add Celery/Redis/APScheduler or a FastAPI startup timer. Scheduler installation/enabling is a separate rollout action after tests/review and authorized live canaries. Machine sleep/offline states make data stale honestly; they do not fabricate successful checks.

One coordinator session holds a global PostgreSQL session advisory lock across the run to serialize SEC traffic across supported processes, with nonblocking acquisition and safe release/connection-loss cancellation. Per-company fact transaction locks remain unchanged. All SEC-writing CLIs, demo/import compatibility entrypoints and indexing must use the coordinator admission/publication protocol or be clearly disabled during scheduled operation; an alternative unversioned writer is not acceptable. Do not hold the fact transaction lock across network/embedding work. Before publication verify the coordinator lock/connection is still owned; discard staged results after lock loss and revalidate on retry. No durable lease system is needed for this single-host design.

### Data version, cache and read consistency

- `data_version` increases once per successful changed stream publication, not per row/check/request; facts/evidence versions indicate which stream changed. One successful stream can advance the version while the other fails. No-change checks update check/success metadata without increasing data versions. Baseline is version 0, unknown currency.
- Version row, changed data/publication and event share a transaction. Row locks serialize increments; event uniqueness prevents duplicated publication. Reports include committed version and stream, not speculative counters. Current reads cannot observe a version describing uncommitted rows.
- FinancialMetrics is already rebuilt per request; there is no financial result cache to purge. Keep it that way initially. Model/client caches are independent of source-data freshness. Any later result cache key must include company version, metric/period/query and policy version.
- Read endpoints use a consistent read-only snapshot covering version and facts/evidence (e.g. REPEATABLE READ on dedicated API read transactions). Keep fact **writer** sessions at READ COMMITTED as required by `merge_company_facts`. Do not globally change database isolation. Batch version loading with company lookup/catalog where practical; no per-metric SELECTs. Measure the new bounded query count rather than repeat the old two-SELECT claim untested.
- Multiple frontend endpoint calls may straddle publication despite individual consistency. Client accepts a response only for its requested company/scope version; a mismatch triggers one coordinated metadata refresh/retry, never an unbounded retry loop or a mixture presented as one current dataset. Source links remain valid for the older snapshot while it is explicitly labelled.

### Proposed API contracts and frontend freshness UX

Add read-only `GET /companies/{ticker}/freshness` and additive version metadata on object financial/history/research/context responses; keep `/companies` and `/sources` arrays compatible using additive company fields and a response version header for sources. Proposed metadata: company `data_version`, `facts_version`, `evidence_version`, stream statuses, check/success timestamps, latest source filing dates, latest **published** indexed filing (accession/form/filed), pending count and safe error code. No credentials, contact email, raw exception bodies, absolute paths or arbitrary source URLs.

Define status, separately per stream and as an aggregate:

- `unknown`: no verified check/bootstrap only; null is not success.
- `pending`: active/backlogged discovery or an eligible known target is not fully published.
- `failed`: last attempt failed; previous published data remains readable and labelled.
- `stale`: previously successful checks exceed configured check SLA (proposal: 36 hours for daily jobs).
- `current`: checked within SLA, supported inventory complete within declared policy, all required known targets published and no unresolved stream failure. Does not promise all SEC concepts or unlimited filing history are supported.

Aggregate failed/pending/stale/unknown must not be hidden by one current stream. Display details rather than reducing readiness, financial coverage and freshness to one badge. `last_checked_at` means completed source discovery/validation, `last_successful_sync_at` means successful stream reconciliation including no-change, and `latest_source_filing_date` means SEC filed date for that stream's eligible source; failures have a separate last-attempt timestamp. Never substitute stored `created_at` for these dates. `latest_indexed_filing` is the newest successfully published eligible filing, not merely the last job target.

Client: one selected-company freshness request on selection, focus/visibility return and a bounded visible-tab interval (proposal: five minutes); no per-card polling or SEC refresh triggered by requests. Stop timers on unmount/hidden tabs; coalesce in-flight checks. Catalog readiness reloads once when evidence publication changes. Version change invalidates requests/state keyed by company/version, refetches only the selected summary/history/sources, and clears stale answer/evidence/AI products together. Preserve company, controls and explicit filing selection when still published; never force a manually selected old filing to the newest one.

Keep the question text, show “Data updated; research this question again,” and do not auto-call AI or silently rerun a historical query against another scope. Existing data may stay visible as a clearly labelled prior version during replacement; never place an old value under new provenance/version. Freshness failure alone does not erase valid financial data. Use accessible text/status announcements, focus stability and explicit SEC source dates versus FinLens check times. No UI redesign or fake zeros.

Legacy `/text` and `/chunks` become stored-only reads with compatible success payloads where stored material exists and an explicit unavailable/pending response otherwise. Preserve official raw links as navigation links. They must not enqueue a refresh or fetch from SEC on a cache miss. Add regression coverage for every public research/read route with SEC network forbidden. No unauthenticated HTTP refresh/write endpoint is proposed.

### Security, failure recovery and observability

Allow only validated CIK/accession/document identities and server-constructed SEC HTTPS hosts/paths. Validate each redirect target or disable redirects; bound bytes, archive pages, retries and overall deadlines. Reuse contact validation, but never log its value. Process-local pacing alone is insufficient; coordinator serializes supported jobs. Honor throttling/Retry-After with a bounded wait, stop on exhausted rate/access denial and checkpoint the backlog. Review current SEC published requirements during a later explicitly authorized acquisition phase, not in this no-contact audit.

Persist attempts before work and finalize them after publication. A crash can leave an attempt running; the next exclusive coordinator marks abandoned attempts interrupted after verifying no active lock, then resumes from actual DB identities/manifests. A crash after commit but before report output must regenerate the committed result from ledger state, not insert again. A second job returns busy safely. Global DB outage stops the run; per-company errors isolate sessions and preserve previous publications. Staging files are ignored, bounded, validated on reuse and never trusted as committed truth.

Failure after flush/at commit rolls back rows, manifests, version and successful event; a separate safe failure record may then be written in a fresh session. Total and per-metric committed insert counts remain zero. Index failure must not publish partial evidence. Report facts/evidence outcomes separately, with source/config digests, IDs, counts, no-change/new/revised diagnostics, versions, timings, limits reached, next action and sanitized HTTP category. Missing/unavailable metrics remain a valid financial result, not necessarily a sync failure.

Pre-publication rollback is transactional. Post-publication recovery is forward-only: stop scheduling, diagnose, append a corrective observation or publish a reviewed exclusion/new version with explicit provenance if necessary. Do not decrement/reuse versions, delete facts or silently revert to old truths. Arbitrary historical rollback/quarantine of already-published rows is not available in this proposal and requires a separately reviewed design/authorization if needed. Roll back deployment by disabling jobs and freshness UI, leaving operational tables/data intact; do not run destructive downgrades on the healthy dataset.

## Decisions

- 2026-10-08: Reuse merge/parser/encoder/FinancialMetrics and existing CLI patterns. Introduce explicit publication transactions and operational metadata only where the audit shows missing guarantees.
- 2026-10-08: Separate facts/evidence publication and status. Cross-stream global atomicity would hold large transactions or require a second data store; honest partial state is simpler.
- 2026-10-08: Keep current latest-compatible-vintage selection, reject unresolved same-context corrections before publication, and retain older provenance. No financial-semantics rewrite is authorized.
- 2026-10-08: Single-host OS scheduler + PostgreSQL advisory admission; no new queue dependency. Proposed cadence, limits and table/contract names remain implementation decisions to verify before rollout.
- 2026-10-08: Preserve canonical documentation now; update it with implemented behavior in a later phase. Do not label roadmap work complete merely because its plan exists.

## Discovered issues / risk register

| Risk (observed unless stated) | Impact | Planned mitigation / gate |
|---|---|---|
| Baseline skip and 10-Q preference | Ready can remain old; a new annual filing can be missed. | Separate latest-per-form discovery and bounded backlog fixtures. |
| Chunks committed before vectors; any-vector readiness | Partially indexed accession can appear searchable/current. | Publication manifest and central accession gate, preserving ranking. |
| Same-context correction lacks revision timestamp; selector tie includes ID | Newly inserted conflicting value may silently win. | Pre-publication conflict diagnostics/quarantine; later accession restatements keep existing policy. |
| New annual boundaries / revised older facts | Quarter labels, derived values and old histories can change. | Full company version invalidation and fiscal/availability fixtures; no period substitution. |
| Version read separate from data / endpoint fan-out | New version could label old data or mix panel snapshots. | Consistent read transaction + client version agreement and bounded retries. |
| Manual writer bypass / concurrent process pacing | Unversioned writes, duplicate jobs or rate bursts. | Integrate every supported writer; one SEC coordinator; DB transaction locks/events. |
| Network during legacy reads | Interactive requests violate source isolation. | Stored-only route transition; forbidden-network API tests. |
| Cache replay / crash after commit before report | Double publication, corrupt versions or misleading counters. | Revalidate digests; unique committed events; ledger-authoritative recovery. |
| Sparse issuer / unsupported metric / economic-basis shift | Fresh source could be misrepresented as universally usable financial data. | Separate coverage from freshness; retain unavailable/basis/EPS reasons. |
| Historical reports contain pre-commit working-tree notes | Old reports can be mistaken for current Git state. | Starting HEAD/status recorded above; historical reports remain dated evidence. |
| Proposed bounded discovery may leave backlog | Cannot claim full currency after capped work. | Pending state, explicit policy window and resume targets. |
| SEC response/model/parse resource cost | Jobs can exceed desktop budgets. | Size/deadline caps, sequential work, local cached encoder, canary measurements. |

## Implementation stages / migration and rollout sequence

1. **Contract and fixtures:** agree status/version/publication invariants; add offline examples and migration-preservation fixtures. Pin cadence/discovery scope as configuration; no source contact required.
2. **Additive schema and coordinator:** new operational tables/constraints; baseline manifest validation; advisory admission, event transactions and safe report recovery. Validate on disposable PostgreSQL before any development migration.
3. **Facts refresh:** integrate all supported fact writers, reused merge, conflict gate, commit-bound counts/version; no-change and revision tests. Keep selectors/registry untouched.
4. **Evidence refresh:** new-accession inventory, amendments, transaction-neutral staging/persistence, published-accession gates, stored-only text/chunks and all indexing/demo writer integration. Keep old usable evidence accessible.
5. **Versioned read/UI:** additive contracts, consistent snapshots, selected-company metadata checks and mounted invalidation/fallback tests; update source/date labels without redesign.
6. **Operations and canaries:** dry-run/restart/concurrency tests, documentation, independently reviewed preservation results. Only after subsequent authorization: controlled SEC canaries, inspect budget/contact, migrate healthy DB with preservation checks, then explicitly enable scheduler. No OpenAI requirement.
7. **Acceptance and closure:** representative AAPL/JPM/COST/JNJ/XOM behavior, query-count measurements, fresh-clone migration/setup, security/accessibility review, update roadmap/product/architecture/data/runbook with delivered scope, complete plan only when gates pass. Do not start another milestone.

Estimated complexity: **medium-high**, approximately 8–12 focused engineering days plus independent review/rollout observation; schema/locking/publication and client version races dominate. This is a planning estimate, not a delivery promise. Stages 2–4 are the critical path; scheduler wiring is small only after transaction guarantees exist.

## Test and validation strategy (Phase 1 proposal; actual results below)

Use existing pytest API/service fixtures and Node/jsdom mounted tests; inject fixture acquisition/encoder outputs and fail on real SEC/OpenAI clients. Disposable PostgreSQL with pgvector and test-only credentials is mandatory for locking/isolation/migrations; never point mutation fixtures at the development DSN.

| Scenario | Required production-path assertion |
|---|---|
| No change | Zero committed inserts, identical version/data/provenance, updated successful-check metadata; repeat run equivalent. |
| New quarter / new annual | Append only; published version advances atomically; explicit quarter never selects YTD/annual/Q4 synthesis; new annual boundaries invalidate affected views. |
| Later restatement / same-context conflict | Later compatible filing can supersede with both provenance rows retained; ambiguous same-context correction is quarantined without changing prior facts/version. |
| Duplicates / concurrent refresh | Exact duplicates add nothing; second coordinator busy; supported concurrent merges cannot duplicate; only one version event per publication. |
| Incomplete Company Facts | Malformed supported observation fails issuer atomically; genuinely missing/unsupported metric remains unavailable, never zero or fabricated source. |
| New filing / index failure / amendment | Validate metadata/document/counts/vectors; failed batches never become published/current; old accession stays usable; resume does not replace old text/vectors. |
| Flush/commit/interruption/report failure | Zero rolled-back committed counts/version; next issuer healthy; committed job with missing report reconstructs from ledger; stale running attempt recovers without duplicate rows. |
| Source limits/host/redirect/throttling | Unknown URLs denied; caps checkpoint pending; retry bounded; logs contain no secrets/contact/raw errors. |
| Stale frontend / cache invalidation | Mounted summary/history/source/answer/evidence/AI requests cannot cross versions; focus/timer discovers updates without reload; same-version checks do not fan out; client retry bounded. |
| Unavailable / basis / EPS | COST and bank revenue rules, sparse XOM, EPS warnings, zero/negative denominators and existing typed-operation grammar unchanged. |
| Old provenance / read routes | Original row subset hashes and official accession URLs intact; legacy reads are stored-only; direct unpublished-accession requests cannot bypass publication. |
| Migration/bootstrap/fresh clone | Existing tables/IDs/vectors unchanged, check times unknown, complete baseline registered only after validation; new clone migrates/setup works without AI credentials or scheduler. |

During implementation run relevant existing financial-sync/indexing/metrics/historical/typed-answer suites plus new refresh tests. Run full backend regression when shared persistence/read paths change; frontend tests/lint/type/build/browser checks only for frontend stages. Measure bounded query counts (including version metadata), no per-metric fan-out, representative response/job cost and no acquisition during normal HTTP. After intentional inserts, verify all original rows by ID/subset fingerprints and separately audit newly appended observations/manifests/events.

## Progress and actual Phase 1 validation

Implementation continuation 2026-10-08: read-only baseline matched the recorded counts and all three table fingerprints; stored at `backend/reports/data_freshness_baseline.json`. Development migrations and acquisition remain forbidden. A separate disposable PostgreSQL instance will validate migrations, concurrency and atomic publication. Preserve the starting generated-file hash. Proposed state fields use typed, validated JSON per stream plus constrained version/event columns, keeping the three-table design without an expanding set of duplicated stream columns.

- [x] 2026-10-08: Read requirements, root instructions, roadmap, ExecPlan standard and relevant canonical docs.
- [x] 2026-10-08: Inspect acquisition, importer/sync, indexing/parser/encoder, models/migrations, selection/dispatch, API/frontend state, operations, tests and preservation artifacts.
- [x] 2026-10-08: Document implemented guarantees versus gaps and proposed schema/publication/version/scheduler/recovery design.
- [x] 2026-10-08: Check documentation targets, scope, generated-file preservation and `git diff --check` (see Phase 1 closure record below).
- [x] Implement contracts, schema/coordinator, insert-only facts, complete evidence publication, read/UI versioning and disabled operational support.
- [x] Run offline production-path, PostgreSQL migration/concurrency/isolation, mounted UI, full relevant regression and read-only preservation checks.
- [x] Finish runbook/reports/canonical docs and implementation self-review.
- [ ] Independent Astra review (separate review, not claimed here).
- [x] Authorized development migration/bootstrap and API recovery independently accepted on 2026-10-09 (see deployment addendum).
- [ ] Live canaries/resource measurement and scheduler activation (separately authorized operational acceptance).

Phase 1 commands run from repository root: scoped `Get-Content`/`rg` source/doc/test reads; `git status --short`, `git diff --stat`, `git diff -- frontend/next-env.d.ts`, `git rev-parse HEAD`; SHA256 of the pre-existing generated file. Final checks: local relative Markdown targets/anchors in this plan, source function references, documentation scope, `git diff --check`, and new-file whitespace check. No application tests/build, browser/live HTTP, DB connection, SEC/OpenAI request, migration, scheduler or data write was performed. Existing test counts and baseline fingerprints above are explicitly historical evidence.

Phase 1 closure record: all local Markdown link targets in this plan resolve; the referenced selection-policy anchor resolves; code symbols named in the audit were checked against source. `git diff --check` and new-plan whitespace check pass. Generated `next-env.d.ts` SHA256 matches the starting value. Git status contains only that pre-existing generated change and this new active plan. No roadmap completion status changed.

## Implementation decisions and discovered issues — 2026-10-08

- Per-stream typed JSON stores check/success/source/status details alongside constrained company version/event columns; the three-table design is retained without redundant column sets.
- Discovery intentionally checks only the capped recent submissions window, latest exact Q/K independently plus amendments. No archive crawl is added; sparse/incomplete inventory stays pending. This is the documented bounded implementation of the proposed inventory, not full EDGAR coverage.
- Dedicated API reads use REPEATABLE READ + READ ONLY; existing writers keep READ COMMITTED. Version consistency adds one bounded SELECT; old two-SELECT API claims were updated while the financial service remains unchanged.
- No staging-file cache is added: new evidence stages in memory before publication; existing persisted partial accessions resume without replacement. Crash before publication can require reacquisition of a new filing; there is no misleading durable staging claim.
- Bootstrap is explicit offline version-zero manifest registration; it cannot add unversioned publications after a company's version has advanced. Development bootstrap/migration remain forbidden this round. Unmigrated read-only fallback validates complete legacy evidence and reports unknown freshness.
- Old tests encoded any-vector readiness and the prior schema head; fixtures now model committed manifests/current head and count the version SELECT. A new explicit-quarter fixture needed a real annual boundary, preserving the existing fiscal selector instead of weakening it.
- Self-review found a StrictMode admission-cleanup defect. The new mounted test first reproduced failure, then passed after cleanup clears its own admission and stale finally callbacks cannot unlock newer requests.
- Final self-review retained every uncommitted evidence target on rollback, rather than clearing pending diagnostics before commit; 107 targeted refresh/sync/index tests passed afterward. PostgreSQL migration/bootstrap now checks an original stored chunk/vector as well as facts. Initial observed evidence versions also reconcile potentially stale catalog readiness once, with a mounted regression.
- Run/stream deadlines are soft between synchronous stages/batches; total budget is propagated into stream/encoder staging, and over-budget source work cannot publish. Resource/time canaries remain a live rollout gate.

## Implementation acceptance criteria

The implementation request explicitly forbids development writes/live SEC/OpenAI/scheduling and permits closure after offline acceptance with rollout deferred. The original entire-milestone operational gates are therefore separated from this completed implementation plan, not claimed as satisfied.

- [x] Supported writers atomically publish validated changes/version/events; no-op, rollback, counter and retry invariants pass.
- [x] Original observations/text/vectors/provenance retained; same-vintage unclear corrections rejected before insertion-order selection.
- [x] Separate stream freshness/source/check dates; partial inventories/failures remain honest.
- [x] Interactive reads stored-only, unpublished accessions gated, no automatic SEC/AI execution.
- [x] Version-aware mounted views reject stale responses, preserve controls/query, retain usable research on check failure and support cleanup/re-setup.
- [x] Offline API/PostgreSQL migration/concurrency/isolation, existing financial regression, frontend tests/lint/type/build and read-only HTTP/browser preservation checks pass.
- [x] Migration/bootstrap/rollback/operator instructions and explicit rollout limitations documented; self-review and whitespace/reference checks pass.

## Actual validation and commands

See [implementation report](../../../backend/reports/data_freshness_implementation.md) for exact commands, changed modules and warnings; [verification JSON](../../../backend/reports/data_freshness_verification.json) retains counts/hashes and real HTTP results.

- Backend focused refresh: 43 passed, including 4 isolated real PostgreSQL tests. Full backend: 733 passed + 27 subtests, 13 existing opt-in DB RAG tests skipped. No development mutation tests.
- Frontend: 64 passed (34 mounted); lint and no-emit TypeScript passed; disposable production build passed after final lifecycle fix. Same dependencies, no generated repository-file edits.
- Real read-only HTTP: healthy catalog 35/35 Ready; AAPL/JPM/COST/JNJ/XOM summary/sources/freshness; AAPL exact quarterly revenue 109,417,000,000 USD and FY2024→FY2025 +6.43%. Development version stays 0/unknown, migration required.
- Browser inspected real unmigrated unknown/freshness disclosure and financial values at 1440/390; mobile no horizontal overflow. Version changes are offline mounted acceptance. No AI/evidence request or source acquisition was triggered.
- Whole-row fingerprint equality: 35 companies, 58,881 facts, 3,175 chunks/vectors; development revision unchanged at d7b834408ba8. Generated next-env SHA256 unchanged.
- Syntax/import, CLI/wrapper disabled behavior, documentation references and git diff --check validated at closure; results recorded in machine verification.

## Deferred operational acceptance — original 2026-10-08 snapshot

Independent Astra review, explicitly authorized target migration/validated bootstrap/API restart, current SEC policy/contact check, live subset canaries/no-op/recovery/preservation, encoder/memory/time measurements and explicit scheduler activation remain pending. These are not implementation blockers under the requested offline scope. The milestone is not operationally complete. No later roadmap work is authorized.

## Final outcome

Completed the bounded offline implementation and self-review; moved this plan to completed only for that scope. No SEC/OpenAI calls, development schema/data writes, dependency changes, scheduling, staging, commits or pushes. The pre-existing next-env generated diff remains byte-identical and must be excluded from a future milestone commit. Rollout uses the [runbook](../../data-freshness.md); do not downgrade metadata or delete volumes for recovery. Suggested commit: `Add transactional SEC refresh and version-aware Research Mode`.

## Independent review repair closure — 2026-10-08

The independent review found four P2 failures after the original implementation
acceptance. The [bounded repair plan](2026-10-08-refresh-review-fixes.md) records
their implementation and validation; original acceptance above remains historical.
Refresh publication now shares the admission connection, uncertain commits are
reconciled against the durable ledger through a fresh connection, fatal errors
stop before later streams, and catalog reconciliation retries unchanged evidence
versions until fetch/state application succeeds. Indeterminate outcomes explicitly
use null committed counters rather than fabricated zero counts. Question text
survives first-filing remounts, while results still invalidate.

Repair validation: 52 refresh/PostgreSQL tests, 465 selected deterministic and
compatibility regressions, 66 frontend tests (36 mounted), lint/type/disposable
production build, syntax/import and four detected in-memory mutations. Read-only
development fingerprints, old revision and next-env bytes remain unchanged.
No migration or financial-selector/arithmetic changes, dependencies, acquisition,
provider calls, live jobs, staging or commits. See the updated [implementation
report](../../../backend/reports/data_freshness_implementation.md) and [verification
JSON](../../../backend/reports/data_freshness_verification.json). Focused independent
re-review and all operational rollout gates remain pending.

## Development deployment closure — 2026-10-09

Independent Astra acceptance is **PASS** for fresh backup, development migration
to `f94c6f41e0cb`, offline bootstrap and API recovery. Thirty independent HTTP
checks passed. Bootstrap committed 35 publications/35 refresh states/zero attempts,
with initial versions zero and unknown freshness; original financial/vector
fingerprints matched. This supersedes migration/review-pending statements in the
historical sections above, without changing their recorded offline test results.

Canonical backup path/SHA256, external acceptance evidence and the historical
intermittent Research HTTP 500 are recorded in [deployment status](../../data-freshness.md#accepted-development-deployment).
No new acceptance tests or database operations were performed during this closure.
Live SEC refresh remains unvalidated and scheduling disabled. Continue only after
separate authorization through the [planned one-company canary](../active/2026-10-09-sec-live-canary.md).
