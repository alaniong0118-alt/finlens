# Refresh transaction cleanup repair

Status: completed (bounded repair; independent re-review pending)
Roadmap phase: bounded Data Freshness integrity repair

## Objective
Prevent coordinator cleanup from committing residual publication work after an
unconfirmed rollback, with real PostgreSQL failure and recovery regressions.

## Current architecture and context
Follow the [runbook](../../data-freshness.md) and previous
[repair record](../completed/2026-10-08-refresh-review-fixes.md).
Refresh publication shares the admission connection. SQLAlchemy can mark a
transaction inactive even when rollback failed before reaching PostgreSQL;
cleanup currently unlocks and commits that connection. Starting tree: 30 modified
tracked files, 17 untracked files, nothing staged. Preserve all existing changes.

## Constraints
Offline isolated PostgreSQL only; no development writes/migration, SEC/OpenAI,
dependencies, frontend changes, scheduling, staging, commits or pushes.

## Non-goals
Financial selection/arithmetic changes, architecture expansion, live rollout.

## Implementation stages
1. Retire the dedicated admission connection without cleanup SQL or commits;
   discard publication connections immediately after DBAPI exceptions.
2. Exercise before/after-I/O rollback faults, ordinary rollback, lost commit
   acknowledgment, unknown outcomes, pool non-reuse and idempotent recovery.
3. Run focused refresh/shared-writer/financial regressions, an in-memory mutation,
   syntax/import, read-only fingerprints, documentation and whitespace checks.

## Decisions
The admission connection is dedicated to a whole refresh job. Physically retire
it at exit, including healthy exits, so advisory-lock release never requires
trusting transaction bookkeeping or returning a suspect session to the pool.
Other pooled connections remain reusable; no pool configuration change is needed.

## Discovered issues
The review reproduced one persisted fact with version zero and a running attempt
after before-commit plus before-I/O rollback failures with autoflush=False.

## Progress
- [x] Read brief, instructions, current implementation, tests and Git state.
- [x] Implement correction and permanent regressions.
- [x] Verify, document, self-review and close this bounded plan.

## Test and validation strategy
Use the opt-in disposable PostgreSQL instance and UUID test databases. Match
production pool_pre_ping=True and autoflush=False; assert actual rows, versions,
ledger events, backend PIDs, physical invalidation and ownership recovery.
Keep mutations in memory. Compare development full-row fingerprints read-only.

## Completion criteria
Cleanup cannot commit publication work; failed rollback connections cannot return
to the pool; commits/rollbacks/unknown outcomes stay truthful; facts and evidence
recover once; focused checks pass and original development data is unchanged.

## Final outcome
Coordinator cleanup performs no SQL/commit and physically retires the dedicated
owner on every exit. Publication DBAPI errors invalidate before fresh-connection
ledger reconciliation. Unknown outcomes retain null counters; a lost owner cannot
publish failure metadata or process later streams. Running attempts recover under
the next admitted coordinator; successful ledger entries remain authoritative.

Seven new PostgreSQL regressions passed. From `backend/`, using the dedicated test
DSN, `python -B -m pytest -q -p no:cacheprovider tests/test_refresh_postgres.py
tests/test_data_refresh.py tests/test_financial_sync.py tests/test_catalog_indexing.py
tests/test_setup_demo.py tests/test_research_answers.py
tests/test_historical_research_answers.py` passed 524 tests (59 refresh/PostgreSQL,
465 financial/compatibility). Existing ordinary rollback, after-commit reconciliation,
unknown outcome, nested admission, concurrent merge, snapshot and migration tests
passed under production fixture settings. An in-memory mutation restoring unsafe
cleanup made the new direct regression fail with one persisted fact instead of zero.

Both changed Python files compile in memory and FastAPI imports. Read-only
development fingerprints retain 35 companies, 58,881 facts and 3,175 chunks/vectors;
revision is still d7b834408ba8. Next-env bytes are unchanged. Exact checks and final
Git/whitespace status are recorded in the
[verification JSON](../../../backend/reports/data_freshness_verification.json).
No frontend, financial semantics, dependencies, development writes/migration,
SEC/OpenAI, scheduling, staging, commit or push. Operational rollout remains
unauthorized; final independent Astra re-review is the next acceptance gate.

Suggested commit after review: `Fix refresh transaction cleanup after rollback failure`.
