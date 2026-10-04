# Item 4 — Curated Company Catalog

Status: completed
Roadmap phase: Phase 1 catalog submilestone; Item 5 indexing remains pending

## Objective

Extend the existing seed to exactly the requested 35 issuers, verify every added ticker/name/CIK against official SEC metadata, and preserve all existing company rows and financial/evidence data.

## Current architecture and context

Read [repository instructions](../../../AGENTS.md), [roadmap](../../../ROADMAP.md), [engineering standards](../../engineering-standards.md), [source policy](../../data-sources.md), and [plan standard](../../../.agent/PLANS.md). The sole seed/catalog is `backend/seed_companies.py`; `scripts.setup_demo` reuses it. Company ticker and CIK already have unique schema constraints. `/companies` derives Ready/count from embedded chunks in one aggregate query.

Starting Git state: clean; HEAD `7c13968`. Current seed has 10 issuers. Baseline database counts/fingerprints will be recorded before any mutation in [catalog verification](../../../backend/reports/company_catalog_verification.json).

## Constraints

Only add the requested 25 company rows. Preserve legacy identities/names/IDs and all facts/chunks/vectors. No migrations, dependency/frontend/retrieval changes, SEC filings/facts ingestion, embedding/model/provider calls, commit, or push. Fetch SEC ticker metadata only.

## Non-goals

Item 5 filing indexing, new financial facts, universal readiness, and later Research Mode/AI milestones.

## Implementation stages

1. Verify added issuers from SEC metadata and record the real DB baseline.
2. Append verified records to the existing seed; retain insert-only behavior and safe reruns. Add focused catalog, preservation, and availability tests; update the setup test's catalog expectation.
3. Run relevant backend tests, then the supported seed on the real DB twice. Compare existing rows and table fingerprints, counts, and API metadata.
4. Update roadmap submilestone status; review scope, references, and whitespace; complete this plan.

## Decisions

- 2026-10-04: An ExecPlan is required because this is staged work with a real data change, under the repository plan/engineering rules.
- 2026-10-04: Use SEC `company_tickers_exchange.json` for all 25 records, including exchange. Preserve its names verbatim, pad CIK to 10 digits, uppercase exchange; leave the first 10 seed records untouched. Keep the verification snapshot as evidence, not a parallel catalog.
- 2026-10-04: Existing unique constraints are sufficient; no migration is needed. Seeding only touches Company and availability stays entirely database-derived.

## Discovered issues

- Current SEC metadata maps XOM to ExxonMobil Holdings Corp / CIK 0002115436. Use the verified current record rather than the older identity recalled from memory.
- `test_setup_demo.py` expects the former 10-row catalog; update that expectation while preserving its no-extra-ingestion assertions.

## Progress

- [x] 2026-10-04: Instructions, relevant seed/schema/tests and docs inspected; SEC metadata HTTP 200, all 25 tickers matched uniquely, selected CIKs unique.
- [x] 2026-10-04: Recorded live baseline: 10 companies, 3,251 facts, 37 chunks, 37 embeddings; original identities checked and full table fingerprints saved.
- [x] 2026-10-04: Extended the existing seed, batch-read existing identities, added preflight conflict checks, and retained insert-only behavior. Focused catalog/availability/setup tests passed (23 tests).
- [x] 2026-10-04: Real supported seed added 25 rows; rerun skipped all 35. Original 10 rows and complete facts/chunks/vectors hashes unchanged. Real HTTP 200 returned 35, AAPL true/1, additions false/0; real DB listing SELECT count was one.
- [x] 2026-10-04: Roadmap marks Item 4 complete and Item 5 pending; source policy updated. Internal references, diff scope, and whitespace checks passed. Completed plan archived; no next milestone started.

## Test and validation strategy

Use disposable SQLite tests for exact ticker set/count, ticker/CIK uniqueness, verified metadata, repeat seeding, existing rows/data preservation, identity conflicts, and readiness from only actual embedded chunks. Count listing SELECTs with SQLAlchemy events to guard against N+1 at 35 companies. Run catalog, availability, and setup tests from backend using `.venv/Scripts/python.exe`.

Before real seeding, record counts and full-row hashes of financial_facts/filing_chunks (including vectors), plus existing company records. Use read-only transactions for observations. Run `python seed_companies.py` twice, then assert 35 rows, unchanged original 10 records, unchanged fact/chunk/vector counts and fingerprints, and stable rerun state. The seed commits inserts in one transaction; failures must not update/delete existing data. Do not undo successful inserts as a routine cleanup.

Smoke the real `/companies` endpoint at 127.0.0.1:8000: 35 rows, AAPL true/1, new issuers false/0. Run `git diff --check`; review changed paths and internal references. No frontend build or real LLM evaluation is justified by this scope.

Actual validation: from backend, `.venv/Scripts/python.exe -m pytest tests/test_company_catalog.py tests/test_company_availability.py tests/test_setup_demo.py -q` passed 23 tests (existing datetime deprecation warnings only). `.venv/Scripts/python.exe seed_companies.py` ran twice successfully. Read-only PostgreSQL snapshots hashed ordered full `row_to_json` records, including embeddings; counts stayed 3,251/37/37. The actual HTTP response matched the direct DB-derived listing. Results are in the verification report linked above.

## Completion criteria

Exactly the requested 35 issuers in seed/live DB/API; all added identities SEC-verified; seed idempotent; legacy rows/facts/chunks/vectors unchanged; new issuers Not indexed and AAPL Ready; no listing N+1; focused tests and HTTP checks pass; only catalog-related changes; Item 5 stays pending.

## Final outcome

Exactly 35 companies now exist in the sole catalog, local database, and live API. Official SEC metadata verified all 25 additions, and seed names/CIKs/exchanges match that snapshot. Existing 10 company rows remain byte-for-byte equivalent in the recorded field comparison, including IDs and names. No migration or frontend/retrieval changes were needed.

The existing seed inserts missing rows only, reads identities once, and rejects ticker/CIK conflicts before inserts. A live rerun changed no company rows. Facts remained 3,251, chunks 37, and embeddings 37, with full ordered table hashes unchanged. AAPL stayed Ready with one indexed filing; all 25 additions stayed Not indexed. Real HTTP `/companies` returned 200/35; actual listing query count was one. Relevant tests passed 23/23. `git diff --check` passed, new-file whitespace checks passed, and 65 internal documentation links/anchors resolved.

Changed files: seed, focused catalog tests, setup test count, verification report, roadmap, source policy, and this plan. No SEC filings/facts were fetched, no model/vector/provider operation ran, and no data was deleted/replaced. No commit or push. Suggested commit: `Expand curated SEC company catalog to 35 issuers`.
