# DEP-01A2 Increment 3: bounded research reads

Status: active; implementation and offline verification complete; coordinator and independent Astra High implementation review pending.
Roadmap phase: scoped deployment hardening, Increment 3 only.

## Objective

Reject invalid inputs and oversized complete research scopes before text body reads, embeddings or ranking. Preserve exact admitted text, provenance, ranking, publication snapshots and freshness contracts.

## Current architecture and context

Starting branch main; HEAD and origin/main both cc8c4c41871c3b7ee3dfad402f7e76ad6dd73e32; index empty. Only existing changes: frontend/next-env.d.ts and two untracked backend runtime reports. Root AGENTS.md, ROADMAP.md and .agent/PLANS.md read. The legacy /companies branch scans all chunks; legacy /sources scans company chunks. Migrated discovery uses publication metadata. Historical catalog report contains 35 companies / 3,175 chunks, with largest company 336 chunks, below the proposed aggregate 4,000 ceiling; this is offline baseline evidence, not a current DB measurement.

Protected SHA256:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints

Production edits only main.py, freshness_service.py, filing_search_service.py and rag_context_service.py. Focused synthetic tests and this plan allowed. No real PostgreSQL connections, network/provider calls, downloads, service startup, ingestion, migrations, writes, publication, financial authorization, frontend changes or Git staging/commits/push/reset/cleanup. Preserve operational stored_chunks and source pinning.

## Non-goals

Later increments, performance guarantees without PostgreSQL, browser acceptance, AI provider acceptance and deployment.

## Implementation stages

1. Verify Git/protected files and offline discovery compatibility before production changes.
2. Add shared validation and bounded inventory/body readers; apply to selected/company/legacy reads and text.
3. Bound fully formatted selected and company context blocks; preserve ranked prefixes.
4. Add focused fake-session/compiled PostgreSQL/HTTP tests and minimal compatibility assertions; run guarded offline verification, debug, self-review and rehash.

## Decisions

- 2026-10-15: Apply aggregate discovery admission only to legacy chunk-reading branches; migrated metadata discovery does not materialize chunk text. Reject entire oversized requested legacy scope, without per-filing query loops or partial discovery.
- Use Python len and SQL length, deterministic inventory ordered by company/accession/index/ID, limit 4001; bodies must match complete admitted metadata and lengths.
- Retain PostgreSQL cosine distance and ascending distance ordering. Semantic search now verifies the entire admitted body set before excluding absent embeddings and applying the requested top-k; hybrid still considers missing embeddings with zero semantic similarity. This increases admitted semantic body reads to at most 4,000, rather than fetching only top-k, to avoid partial success.
- HTTP result counts reject decimal/exponent strings; JSON answer counts are strict integers. Answer questions are checked at their decoded length before trimming and retain their original query identity. No filing text or offsets are normalized.
- Atomic body-admission inconsistencies return 409 EVIDENCE_PENDING. Existing company publication eligibility exclusions (bad digest/metadata/vector/count) remain intact; an oversized chunk instead rejects the whole eligible requested scope with SEARCH_SCOPE_TOO_LARGE.

## Discovered issues

Existing company-wide reader excludes oversized publications, selected search reads unbounded text, freshness latest-publication lookup loads full ORM, and selected context has no formatted size ceiling. These are within approved scope.

Existing company search assertions expected EVIDENCE_PENDING for a supplied pin with missing metadata, and 404 for a supplied zero pin on an unknown company. Increment 2 already returns DATA_VERSION_CHANGED at snapshot verification; assertions now preserve that precedence. Unknown-company behavior without a supplied pin is still 404. The guarded runner disables dotenv; the existing temporary synthetic dotenv test now explicitly enables only its local temporary fixture while private dotenv remains disabled during imports.

## Progress

- [x] Baseline and protected hashes checked; source discovery branches inspected.
- [x] Shared readers and validation implemented in the four allowed production files.
- [x] Context and HTTP integration complete, including legacy aggregate rejection and exact text preflight.
- [x] Offline acceptance and self-review complete; protected hashes verified unchanged.
- [ ] Coordinator and independent Astra High implementation review. No next increment, staging or commit authorized.

## Test and validation strategy

Use existing backend/.venv with guarded runner: private dotenv disabled, dummy DB URL, physical DB/socket/encoder sentinels, fake sessions, PostgreSQL SQL compilation and synthetic fixtures only. Exercise input/chunk/inventory/text/context boundaries, failed admission before work, body mismatch, all affected HTTP/service entry points, legacy catalog and company source compatibility, freshness and release admission. Exact commands/results will be recorded below. Do not repeat full financial/QA/A1/A2 acceptance suites.

## Completion criteria

All approved bounds implemented and focused tests passed; only allowed files changed; protected hashes unchanged; no physical DB/network/provider work; coordinator and independent Astra implementation review remain pending.

## Final outcome

Implemented only Increment 3. Suggested commit: `Bound research inventories, document reads and source contexts`. No staging, commit, push, PostgreSQL connection, external requests, ingestion, migration, service startup, model download, publication or financial authorization was performed.

### Exact changed-file inventory

Production:

- backend/app/main.py
- backend/app/freshness_service.py
- backend/app/filing_search_service.py
- backend/app/rag_context_service.py

Tests:

- backend/tests/test_bounded_research.py (new)
- backend/tests/test_company_evidence_search.py (atomic oversize and Increment 2 pin expectations)
- backend/tests/test_rag.py (admission fixture and isolated temporary dotenv fixture)
- backend/tests/test_http_database_runtime.py (metadata-only latest-publication fake projection)

Plan: docs/exec-plans/active/2026-10-15-dep01a2-increment3-bounded-research.md (new).

### Bounds and covered paths

Decoded query/question: 1–2,000 characters with non-whitespace content. Result count: integer 1–50, default 5. Complete selected/eligible company/legacy discovery inventory: at most 4,000 chunks, each at most 3,000 characters. Context: at most 24,000 fully formatted characters, including indent/framing/separators, with complete sources and citations only; stop at the first qualifying block that does not fit. Full stored text: at most 12,000,000 characters, with SQL length projection before body materialization. Python len and PostgreSQL length(text), not byte counts.

- GET /companies (legacy aggregate chunk discovery; migrated metadata discovery preserved).
- GET /companies/{ticker}/sources (legacy company-scoped chunk discovery; migrated metadata discovery preserved).
- GET /companies/{ticker}/filings/{accession_number}/search.
- GET /companies/{ticker}/filings/{accession_number}/semantic-search.
- GET /companies/{ticker}/filings/{accession_number}/context.
- GET /companies/{ticker}/context.
- GET /companies/{ticker}/filings/{accession_number}/chunks.
- GET /companies/{ticker}/filings/{accession_number}/text.
- POST /companies/{ticker}/filings/{accession_number}/answer (development only; mocked generation acceptance).
- GET /companies/{ticker}/freshness (latest filing is now a metadata projection; missing/zero/positive/stale contracts unchanged).
- Direct services: search_filing_chunks, search_filing_chunks_semantic, hybrid_search_filing_chunks, hybrid_search_company_chunks, rank_hybrid_chunks, build_filing_context, build_company_context, _build_context; bounded shared reader also covers unmigrated require_published and stored_filing.

Invalid selected semantic/context limits intentionally change 400 to 422; all changed input entry points reject before session creation (HTTP) or normalization/embedding/retrieval (service). Oversized requested scopes reject atomically with 409 SEARCH_SCOPE_TOO_LARGE. Missing full text remains 409 STORED_TEXT_UNAVAILABLE. Empty stored-filing inventories and admission/body mismatches return 409 EVIDENCE_PENDING instead of indexing empty lists or returning partial success. Existing read_session transaction/pin logic is unchanged, as are SEC-only route admission, development generation boundaries, evidence thresholds, ranking/deduplication, citation IDs, stored source identities and financial authorization.

### Actual production PostgreSQL compilation evidence

Compiled statements captured from calls to the actual production functions using fake sessions and sqlalchemy.dialects.postgresql.dialect(), without connecting:

1. require_published selects only filing_publications.accession_number with company/accession predicates; no publication ORM or cleaned_text.
2. Inventory selects ID, company/accession, index/chunk ID, form/filed/filename, offsets/SEC URL, length(filing_chunks.text) AS text_length, ordered by company/accession/index/ID, LIMIT parameter 4001. Neither bare text nor embedding is projected; there is no embedding filter or top-k restriction.
3. Body reads retain company/accession predicates, admitted IDs via IN, length(filing_chunks.text) <= 3000 and LIMIT 4001. Every ID, identity field, text length and count must match admission. Distance variants keep PostgreSQL <=> and ORDER BY distance; all bodies are verified before semantic vector filtering/top-k.
4. Full text first selects length(filing_publications.cleaned_text); body SELECT retains company/accession predicates plus length(cleaned_text) <= 12000000.
5. Latest freshness filing selects accession_number, form and filed, ordered by filed/accession DESC, LIMIT 1. Missing latest filing is still None.
6. Company-wide publication query still uses load_only for metadata and LIMIT 21; no cleaned_text column. Operational stored_chunks AST was compared with HEAD and is identical.

### Commands and results

Working directory: D:\Projects\finlens-foundation\backend. Existing guarded runner sets a dummy database URL, disables private dotenv and rejects physical psycopg/socket connections. New focused tests additionally bomb unmocked HTTP session creation, model loading and SEC/provider work. Existing ORM compatibility tests use disposable in-memory SQLite fixtures only; no application database is connected or written.

Final combined command:

```powershell
.\.venv\Scripts\python.exe tests/run_dep01a2_increment2_offline.py `
  tests/test_bounded_research.py tests/test_rag.py `
  tests/test_company_evidence_search.py tests/test_company_availability.py `
  tests/test_http_database_runtime.py::test_production_freshness_unverified_is_unavailable `
  tests/test_http_database_runtime.py::test_production_freshness_recovers_on_later_independent_request `
  tests/test_http_database_runtime.py::test_production_freshness_stale_pin_is_409_before_body_reads `
  tests/test_http_database_runtime.py::test_production_freshness_unverified_cleanup_failure_preserves_unavailable `
  tests/test_http_database_runtime.py::test_production_freshness_programming_failure_remains_sanitized_generic
```

Result: **267 passed, 27 subtests passed**, 14.04s. Warnings: existing Starlette TestClient and SQLAlchemy datetime.utcnow deprecations. New fake-session suite separately passed 172 tests. Initial test runs exposed fixture/response-shape issues and old Increment 2 assertions; these were corrected before the successful final run. An earlier wider compatibility selection passed 362 and failed the three stale assertions above; no full financial/QA/A1/A2 acceptance suite was run.

After the combined run, strengthened the two context-prefix cases with a later short block that could fit if an implementation skipped the first non-fitting block. Ran `.\.venv\Scripts\python.exe tests/run_dep01a2_increment2_offline.py tests/test_bounded_research.py::test_context_full_formatted_boundary_prefix_duplicates_and_identity`: **2 passed**. No production edits followed the combined run.

Additional manual check: executed the production read helpers against synthetic Store sessions and printed PostgreSQL-compiled projection SQL (no literal private parameters or live connections). All statements were SELECTs. Source AST comparison confirms operational stored_chunks is unchanged. git diff --check passes. Final protected SHA256 values equal all three baseline hashes recorded above; tracked SEC artifacts/receipts are outside the diff.

### Navigation risk and remaining uncertainty

The saved 35-company/3,175-chunk catalog was replayed as complete synthetic legacy company/source discovery: all 35 remain indexed, each accession counts once, and each scope uses one inventory/body pair without per-filing query loops. Largest saved company: 336 chunks. Thus the proposed count limit does not demonstrably break this expected baseline. This is historical catalog metadata plus synthetic stored text, not a fresh observation of live chunk lengths or catalog growth. Legacy scopes growing past 4,000 chunks or containing a chunk over 3,000 characters intentionally return atomic 409; migrated metadata-only discovery remains unaffected.

PostgreSQL query planning, sorting/length evaluation cost, actual pgvector execution, TOAST/decompression cost, physical timeout enforcement, concurrency and latency remain unmeasured. Bounded materialization and compiled SQL do not prove PostgreSQL performance or an aggregate request wall-clock guarantee. No live API/browser/database acceptance or real provider acceptance is claimed.

### Final Git and preservation

Branch main at cc8c4c41871c3b7ee3dfad402f7e76ad6dd73e32, index empty. Seven tracked backend files modified; one focused test and this plan untracked. Original modified frontend/next-env.d.ts and both untracked runtime reports remain byte-identical to their initial hashes. No original SEC artifact or receipt changed. Implementation is ready for coordinator/Astra review; the plan remains active for that review gate.
