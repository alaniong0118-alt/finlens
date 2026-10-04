# Item 5 review fixes

Status: completed
Scope: persistence and recovery corrections to completed Item 5

## Objective

Resolve the three review findings: reject invalid generated vectors before persistence, isolate diagnostic failures, and evaluate sibling accessions independently. Preserve the healthy 35-company dataset.

## Current architecture and context

Follow the [completed Item 5 plan](../completed/2026-10-04-multi-company-indexing.md) and [plan rules](../../../.agent/PLANS.md). Starting tree contains the existing uncommitted Item 5 code/docs/reports (9 modified, 10 untracked files). Real read-only baseline: 35 companies, 3,251 facts, 3,175 chunks/vectors, 35 indexed companies/accessions, 37 AAPL chunks. Full-table and AAPL hashes recorded in the [verification report](../../../backend/reports/item5_review_fixes_verification.json) before code edits.

## Constraints

No healthy-data mutation, SEC downloads, catalog embedding generation, frontend/schema/dependency changes, commits, or paid calls. Keep Item 5 complete and preserve previous work.

## Non-goals

Next roadmap item, retrieval redesign, refresh/deeper coverage, concurrency infrastructure.

## Implementation stages

1. Share vector validation at embedding persistence; rollback failed embedding transactions.
2. Make failed diagnostic reads return unknown counts; retain accumulated results if final database availability is unknown.
3. Validate accessions independently, preserve invalid siblings with explicit diagnostics.
4. Focused regressions, catalog suite, full backend suite, real read-only hashes/API/default-skip verification.

## Decisions

- Generated vectors must be validated before ORM assignment/flush, with the same helper reused for persisted-vector validation.
- Chunks remain committed independently; failed embedding work rolls back all new vectors in that filing, preserving previously committed vectors.
- Invalid siblings are never rewritten; valid complete coverage is skipped with accession diagnostics.
- Validate the float32 representation before persistence, including rejection of values that underflow into a stored zero vector. Demo and catalog validation reuse the same helper.
- Snapshot ticker/CIK scalar identities before processing; rollback/commit must not trigger company identity reloads outside the issuer failure boundary. A final readiness database failure preserves accumulated results with a controlled `catalog_error` and nonzero CLI exit.

## Discovered issues

The diagnostic handler's database read can raise after rollback. An ORM company identity may expire after rollback/commit; reporting must retain scalar identities independently.

The initial readiness-outage test fault injection matched a rendered SQL string incorrectly; replacing it with a direct Session.scalar failure exercised the intended boundary. The corrected focused run and subsequent full regression passed. No remaining code issue was discovered.

## Progress

- [x] Instructions/request inspected; preservation baseline recorded.
- [x] Code fixes and 15 focused regressions passed.
- [x] Catalog/demo/availability suite: 61 passed; full backend: 102 tests and 44 subtests passed.
- [x] Real read-only verification: identical hashes/counts, all 3,175 vectors valid, `/companies` HTTP 200 with 35 Ready, default skip 35 with no SEC/embedding work.
- [x] Documentation, self-review, diff check, completed outcome. Independent re-review remains the user's next review step.

## Test and validation strategy

Isolated SQLite fixtures and mocked SEC/encoder calls: zero/NaN/infinity/wrong dimensions; recovery without redownload; preservation of valid vectors; failure after a batch flush; diagnostic failure with a following successful issuer and CLI report; valid/invalid/incomplete sibling cases. Real database verification is read-only, comparing exact full-row hashes and counts. Run full maintained backend tests including provider-mocked AAPL tests, compile/import, Alembic check, real `/companies`, and diff check.

### Commands and actual results

From `backend`, using `.venv/Scripts/python.exe`:

- First, `-m pytest tests/test_catalog_indexing.py -q -k 'zero_vector or shared_embedding_boundary or after_batch_flush or diagnostic_failure or global_readiness or sibling or only_invalid_accessions or multiple_valid_accessions'`: corrected run 15 passed, 23 deselected.
- `-m pytest tests/test_catalog_indexing.py tests/test_company_catalog.py tests/test_company_availability.py tests/test_setup_demo.py -q`: 61 passed.
- PowerShell `$env:FINLENS_RUN_DB_TESTS='1'; $env:HF_HUB_OFFLINE='1'`, then `-m pytest tests -q`: 102 passed and 44 subtests passed, including provider-mocked database regression.
- `-m py_compile app/embedding_service.py app/catalog_indexing_service.py scripts/setup_demo.py scripts/index_catalog.py tests/test_catalog_indexing.py`: passed.
- `-c "from app.main import app; print('FastAPI import: OK')"`: passed.
- `-m alembic current` / `-m alembic check`: head `d7b834408ba8`, no new upgrade operations.

The read-only verification used `SET TRANSACTION READ ONLY` and SHA-256 over newline-joined `row_to_json(t)::text` rows ordered by ID for all three tables and the database-selected AAPL CIK. The exact baseline and final hashes/counts are in the verification report. It validated every stored vector using the shared helper, called `index_catalog(session)` with discovery/ingestion/embedding functions patched to reject unexpected work, and issued a real HTTP GET to `http://127.0.0.1:8000/companies`. All assertions passed. Git root: `git diff --check` passed; modified documentation links and new files were checked separately.

## Completion criteria

All three findings resolved, focused/catalog/full tests pass, exact healthy-data fingerprints unchanged, 35 Ready, no network/model work in default skip check, safe reporting and documentation current.

## Final outcome

All three findings fixed and permanent recovery/isolation/sibling regressions added. Healthy database fingerprints unchanged; AAPL remains 37/37 and Ready. Historical Item 5 reports are retained; the new review-fix report records before/after evidence. No blockers, next roadmap work, frontend/dependency/schema changes, SEC download, catalog reembedding, real provider call, commit, or push. Existing uncommitted Item 5 work is preserved; final tree has 11 modified and 12 untracked files. Suggested commit: `Harden catalog indexing validation and recovery`.
