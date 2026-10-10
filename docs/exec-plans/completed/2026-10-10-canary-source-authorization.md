# Canary source authorization gate

Status: completed — offline implementation/tests; independent review pending.
Roadmap phase: Data Freshness canary safety prerequisite.

## Objective and context

Add an opt-in, fail-closed AAPL publication scope to the existing refresh CLI.
The [live canary plan](../active/2026-10-09-sec-live-canary.md) remains active; this fix
does not execute it. HEAD starts at `61ebc90`. Preserve `frontend/next-env.d.ts`
and the untracked discovery report. The blocked execution performed zero refreshes,
SEC requests and writes; evidence is outside Git in
`D:\FinLens-OperatorReports\aapl_publication_scope_blocked_20261010_013551_3522599`.

## Constraints and non-goals

No live acquisition, development DB writes, model downloads, services, scheduling,
schema/dependency/frontend/financial-selector changes, staging, commit or push.
Use isolated SQLite fixtures and mocked sources; real DB checks are read-only.
Preserve separate stream commits, admission ownership and ledger reconciliation.
Resource limits remain soft. Do not implement a general acquisition framework.

## Implementation stages

1. Extend the request/CLI with a named, immutable-in-meaning AAPL scope.
2. Under admission, acquire/copy both sources; validate facts/conflicts and the
   entire selected inventory before recovery, attempts or other persistent writes.
3. Carry pinned sources to stream execution without source refetch; enforce zero
   fact insertion and exact filing selection; validate raw SEC submission identity.
4. Test rejection without even attempted DML, accepted separate stream commits,
   pinned-source behavior, failure recovery and ordinary-mode compatibility.
5. Update operator documentation, perform preservation checks and self-review.

## Decisions and discovered issues

- Existing `--max-filings` is a count cap, not an accession authorization.
- Existing facts publication precedes evidence discovery; progress callbacks run
  after stream completion. Neither historical dry-run nor monitoring can gate it.
- Scope is an explicit named profile for the authorized AAPL 10-K, not a general
  configurable allowlist. Source loaders remain the existing SEC client.
- Supported admission prevents competing supported writers. Unmanaged SQL remains
  outside admission; repeat checks must prevent unintended fact/filing publication.

## Progress

- [x] Root instructions, relevant code/contracts/tests and blocked evidence inspected.
- [x] Contracts, gate and pinned handoff implemented.
- [x] Offline negative/positive and compatibility tests passed.
- [x] Documentation, preservation and final review complete.

## Test/validation strategy and completion criteria

Permanent production service/CLI tests use in-memory ORM databases and forbidden
network sentinels. Reject new/conflicting facts, wrong identities, changed or
incomplete inventory, amendments, multiple targets, broken existing 10-Q and
already-published target with no persistent DML or table/version differences.
Accept the exact scope, load each metadata source once, validate raw header/document,
preserve rollback/partial-success behavior, and keep ordinary refresh tests passing.
Run focused plus relevant existing offline tests, syntax/import checks and
`git diff --check`; compare read-only original rows and metadata to the backup.

## Final outcome

`--publication-scope aapl-10k-2025` opts into the fixed authorization profile.
`refresh_scope.py` validates both sources before recovery/attempt/state writes,
retains detached source copies/digests, and checks the raw submission identity.
Guarded facts publication is dry-merge-only; evidence is rechecked before its
stream and transaction. Guarded failure stops further streams. Ordinary mode
keeps existing ingestion, stream transactions, ledger recovery and defaults.

Actual validation (backend working directory, `.venv/Scripts/python.exe -B`):

- `-m pytest tests/test_refresh_scope.py -q --tb=short`: **57 passed**.
- `-m pytest tests/test_refresh_scope.py tests/test_data_refresh.py tests/test_financial_sync.py tests/test_catalog_indexing.py -q --tb=short`: **163 passed**.
- Three in-memory mutations each caused the expected regression failure: removing
  the first zero-fact gate, refetching facts, and removing raw identity validation.
  These altered no source files. A temporary PowerShell redirection collision
  prevented the first mutation launcher from starting; corrected unique paths
  produced the retained successful detection results, not hidden test retries.
- Five changed Python files compiled to external evidence; FastAPI/CLI imports
  passed without startup or acquisition. No dependency updates were made for
  existing deprecation warnings.
- Read-only BOOTSTRAPPED and full original-row comparisons matched all 17 backup
  baseline categories: 35 companies, 58,881 facts, 3,175 chunks/vectors,
  35 publications/states, zero attempts; versions zero and freshness unknown.
  Alembic `f94c6f41e0cb`, finlens OID `16384`, cluster `7692131504986030119`,
  collation `2.36 / 2.36`. All four original fingerprints and per-company hashes
  matched, including exact metadata and schema/index/sequence identities.
- Scoped documentation references and `git diff --check` passed.

Evidence/handoff:
`D:\FinLens-OperatorReports\canary_source_gate_offline_20261010_104627_3156678`.
Only contracts/service/CLI, one scope module/test file, Data Freshness docs and
the two plans changed. Existing next-env churn and discovery report were preserved.
No staging, commit or push. Suggested commit: `Enforce pre-write AAPL canary source authorization`.

Residual limits: sequential SEC responses are not an atomic upstream snapshot;
unmanaged SQL is not controlled by admission. Later raw/staging failures can occur
after a no-change facts check commits metadata. Reconcile ledger outcomes rather
than rerun. Budgets and monitoring remain soft. SQLite tests do not claim a new
PostgreSQL fault-injection run; existing PostgreSQL lock/cleanup code is unchanged.
Independent Astra review and separately authorized live execution follow this
offline implementation; neither is claimed complete here.
