# Item 5 — Multi-company SEC filing indexing

Status: completed
Roadmap phase: 1, baseline filing coverage

## Objective

Give all 35 visible companies at least one real 10-Q (preferred) or 10-K with validated chunks, usable MiniLM embeddings, discoverable sources, and scoped search/context. Preserve every original company, financial fact, and AAPL chunk/vector.

## Current architecture and context

Starting Git state: clean, HEAD `dae258c`. Follow [architecture](../../architecture.md), [data policy](../../data-sources.md), [roadmap](../../../ROADMAP.md), and [plan rules](../../../.agent/PLANS.md). Existing ingestion requires a financial fact and deletes/replaces chunks. Sources are grouped only from facts. The new workflow must reuse parsing/persistence/embedding services while accepting official submissions metadata without importing facts.

## Constraints

No schema/dependency/frontend/retrieval changes, OpenAI calls, commits, or destructive operations. Use official SEC submissions and existing contact configuration; sequential requests with bounded retry/backoff. Never log credentials. Preserve current XOM CIK `0002115436`; accession prefixes are not necessarily registrant CIKs.

## Non-goals

Financial Metrics Layer, deeper coverage, AI acceptance, UI redesign, Company Facts import.

## Implementation stages

1. Record real database baseline and preservation hashes; inspect relevant code.
2. Add official discovery, additive ingestion, resumable CLI/report, and focused tests.
3. Dry-run representative discovery, then cross-industry canaries and read-only checks.
4. Index remaining incomplete companies; retry only failures.
5. Run default workflow again, verify preservation/API/lineage/regression/Alembic, document outcome.

Transactions: commit one filing's chunks independently, then backfill missing embeddings in scoped batches. Failure rolls back the current transaction, retaining committed chunks for resume. Existing chunks are validated and never automatically replaced. Recovery is rerunning the same command or a ticker subset; invalid persisted metadata requires inspection, not reset.

## Decisions

- 2026-10-04: Extend existing ingestion with optional metadata and reuse semantics; retain its legacy default behavior for existing callers.
- 2026-10-04: Sources must merge fact-backed and chunk-backed metadata using bounded queries, with no invented financial periods or metrics.

## Discovered issues

- SEC search confirms current XOM registrant has a 2026 10-Q under CIK 2115436 even though accession begins 34088. Verify against submissions and actual primary document before indexing.

## Progress

- [x] Read instructions, relevant architecture, source and tests; Docker healthy, venv available, API running.
- [x] Baseline: 35 companies, 3,251 facts, 37 chunks/vectors, 1 indexed company/accession. Full-row original hashes and IDs recorded in `backend/reports/catalog_indexing_verification.json`.
- [x] Implementation and focused tests: 43 passed (20 indexing checks, plus 23 existing catalog/availability/setup checks). SEC requests/encoder mocked in unit tests.
- [x] Discovery/canaries: dry-run AAPL/MSFT/JPM/JNJ/XOM/WMT succeeded. Five canaries added 542 chunks/vectors; all six representatives passed real HTTP sources/keyword/semantic/context, direct hybrid retrieval and citation lineage. Company listing remains one SELECT; all original hashes match.
- [x] Full batch: remaining 29 indexed, six skipped, zero failures; 35/35 Ready, 35 accessions, 3,175 chunks/vectors. No company retries needed.
- [x] Safe default rerun: 35 skipped, zero indexed/resumed/failed; full-table counts and hashes unchanged, no SEC/model calls.
- [x] Final validation/documentation: 23 indexing tests; full backend regression 87 tests and 44 subtests passed. Compile/FastAPI import passed; Alembic clean at `d7b834408ba8`. All six representative HTTP/search/context and actual SEC index HTTP 200 checks passed. Diff check passed; no frontend changes or paid calls.

## Test and validation strategy

SQLite/mocked SEC/encoder unit tests cover selection, skips, resumability, isolation, invalid/empty data, subset, report counts, and original data preservation. Real database baseline/full-row hashes cover companies/facts/original chunks. HTTP checks use database-selected accessions for AAPL, MSFT, JPM, JNJ, XOM, WMT. Assert source/context lineage and one SELECT for company listing. Full maintained backend suite including opt-in read-only AAPL regression; compile/import, Alembic check, and diff check. No real OpenAI client is used.

## Completion criteria

35 Ready companies, complete embeddings for each selected filing, source/search/context usable, original data unchanged, repeat run skips without mutations, tests and database/API checks pass, documented SEC policy and resumability. Otherwise keep plan active with explicit blockers.

## Final outcome

Item 5 completed with no unresolved blockers. All original company/fact/chunk hashes match; AAPL remains one indexed filing with its original 37/37 rows/vectors. XOM used official current-registrant metadata without substitution. Reports: [batch](../../../backend/reports/catalog_indexing_batch.json), [default rerun](../../../backend/reports/catalog_indexing.json), [preservation/API](../../../backend/reports/catalog_indexing_verification.json). README, roadmap, architecture, product sources contract, and source policy updated. Financial Metrics Layer not started. Starting tree was clean; only scoped code/tests/docs/reports changed. No commit or push. Suggested commit: `Index baseline SEC filings across the curated company catalog`.

## Verification commands executed so far

From `backend`, using `.venv/Scripts/python.exe`: `-m pytest tests/test_catalog_indexing.py tests/test_company_availability.py tests/test_setup_demo.py tests/test_company_catalog.py -q`; `-m scripts.index_catalog` with repeated representative `--ticker` arguments and `--dry-run`; canary subset without dry-run; `-m scripts.verify_catalog_indexing --stage canaries`. Reports are in `backend/reports/catalog_indexing_{discovery,canaries,verification}.json`.

XOM discovery and raw primary document succeeded under current registrant CIK 2115436, accession `0000034088-26-000093`, filed 2026-08-03; no predecessor handling needed. Offset validation accepts trimmed chunk edges because existing parser offsets span the untrimmed cleaned-text slice. Opt-in regression now scopes its fixed 37/37 assertion to AAPL while retaining a whole-database read-only fingerprint.

Final commands from backend: `.venv/Scripts/python.exe -m scripts.index_catalog --report reports/catalog_indexing.json` (batch), `.venv/Scripts/python.exe -m scripts.index_catalog` (default rerun), `-m scripts.verify_catalog_indexing --require-all --stage final`; `FINLENS_RUN_DB_TESTS=1 HF_HUB_OFFLINE=1` with `-m pytest tests -q`; `-m py_compile` for touched Python files; FastAPI import; `-m alembic check` / `current`. Full-row rerun fingerprints were recorded before and after the command. Git root: `git diff --check`. Self-review added explicit persistence-conflict and CLI report/exit-code tests, confirmed no secret/raw exception bodies are reported, and validated documentation references. Existing dependency deprecation warnings remain; no dependencies were changed.

## Post-review corrections — 2026-10-04

All three independent review findings are resolved without reopening roadmap work. Shared embedding persistence validates 384 finite float32 values and positive norm before assignment/flush; any embedding failure rolls back all uncommitted batches. Catalog diagnostics are best effort with nullable counts, stable company identities, and a controlled final-readiness outage result. Each stored accession is validated independently; complete valid coverage skips while invalid/incomplete siblings are reported and preserved. API indexed-filing count semantics remain unchanged.

Permanent regressions cover zero/NaN/infinity/dimension/float32-underflow rejection, recovery without SEC downloads, failure after a real batch flush (including interruption), diagnostic failure with subsequent issuer success and JSON report generation, final readiness outage, and valid/invalid/incomplete sibling coverage. New focused tests: 15 passed; catalog/demo/availability suite: 61 passed; full backend with opt-in database tests: 102 tests and 44 subtests passed. Compile/import and Alembic checks passed; only existing dependency deprecation warnings remain.

Real read-only verification preserved all full-table/AAPL SHA-256 fingerprints: 35 companies, 3,251 facts, 3,175 chunks/valid vectors, 35 indexed companies/accessions, and AAPL's original 37 chunks/vectors. `/companies` returned HTTP 200 with 35 Ready and one indexed filing each. A read-only default catalog service run skipped all 35, with discovery/ingestion/embedding calls blocked and zero provider calls. No healthy-data mutation, catalog redownload/reembedding, frontend work, or real OpenAI call occurred. See the [scoped fix plan](2026-10-04-item5-review-fixes.md) and [before/after verification](../../../backend/reports/item5_review_fixes_verification.json).
