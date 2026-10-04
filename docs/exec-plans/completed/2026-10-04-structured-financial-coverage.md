# Item 7 — Structured financial data coverage

Status: completed
Roadmap phase: Item 7, structured-data acquisition prerequisite for Research Mode

## Objective

Sync official Company Facts for the 35 stored issuers without replacing existing observations. Prove idempotency, recovery, source lineage and Item 6 compatibility; report genuine gaps.

## Current architecture and context

Follow [instructions](../../../AGENTS.md), [plan rules](../../../.agent/PLANS.md), [metrics](../../financial-metrics.md) and [data policy](../../data-sources.md). Starting Git tree clean at `74a2fb3`; Item 6 and its financial-semantics fixes are committed. Read both completed Item 6 records.

Actual read-only baseline: 35 companies, 3,251 facts across 10 issuers, 3,175 chunks and 3,175 vectors. PostgreSQL is healthy. Venv executable confirmed. [Baseline](../../../backend/reports/structured_financial_baseline.json) records full table hashes, every original fact ID/hash, AAPL and all issuer fact hashes/counts. Preserve this baseline on resume.

Importer audit: `import_metric` deletes all company/metric facts then reinserts a reduced list, commits separately per metric, and logs raw exceptions in the all-company loop. `build_metric_data` renames revenue concepts before `deduplicate_fact_data`, whose identity is metric/unit/start/end/type and whose form/recency preference discards different concepts, accessions, values and vintages. `setup_demo` filters its fixed accession first but also calls this collector. FinancialFact has sufficient source/value/date/unit/accession/form/frame/fy/fp fields; Numeric(24,4), no unique identity constraint. Legacy analysis expects stored revenue metric `Revenues`; Item 6 recovers original concept from source.

## Constraints

Preserve every old row and company identity. No chunks/vector changes, filing indexing, retrieval/RAG/frontend, dependency changes, OpenAI, commit or push. Keep current XOM CIK 0002115436. Only official Company Facts via existing paced SEC client/contact; never expose contact or exception bodies.

## Non-goals

New metric aliases, predecessor unification, model calls, frontend Research Mode, later milestones.

## Implementation stages

1. Record baseline/audit; implement exact source identity and insert-only merge, supported CLI and tests.
2. Representative missing-company dry-run; verify unchanged baseline.
3. JNJ/XOM/CAT/COST/F canaries one at a time with preservation, normalization and immediate no-op reruns.
4. Remaining catalog, diagnose/retry failures; full catalog no-op proof.
5. All-company metric coverage, real source/HTTP checks, regression/import/Alembic, docs and self-review.

## Decisions

- 2026-10-04: No migration needed. Exact identity uses company/source concept/unit/dates/value/accession/filed/form/frame/source fy/fp. Exclude derived stored metric/type and local ID/timestamp. Preserve original rows unchanged; retain distinct source observations. Require numeric values to fit Numeric(24,4) exactly rather than rounding silently.
- Use only Item 6's existing primary concepts/units, preserving legacy storage names. No speculative mappings. Observation selection remains in Item 6. PostgreSQL merge requires READ COMMITTED; a permanent test rejects repeatable-read snapshots that could predate a preceding lock holder's commit.
- Each company is atomic. PostgreSQL transaction advisory lock by CIK serializes supported merge writers before reading identity sets. SQLite fixtures are single-writer. No-op is database-derived; reports are not checkpoints. Interrupted committed companies remain durable; rerun fetches and compares sources again.
- Reports contain counts, sanitized error categories and normalized coverage, not SEC contact or raw exceptions. Write incremental JSON atomically under backend/reports.

## Discovered issues

Legacy report-verifier freezes the Item 6 baseline and must not be overwritten; Item 7 uses a separate preservation/coverage report. Discovery found supported observations for all five canaries: CAT 1,785; COST 2,462; F 1,559; JNJ 1,905; XOM 22. Current XOM CIK has limited successor history; no predecessor request or substitution.

Expanded data reveals expected mapping/scope gaps: latest AXP revenue has incompatible customer-contract/net-interest candidates; CAT/F/MA latest net income lacks the existing primary concept; COST YoY crosses bases; Visa has no supported EPS. Preserve unavailable results. Nine negative CapEx observations remain stored but unavailable under the existing positive-payment rule. No Item 6 correction or new alias is justified by this milestone.

## Progress

- [x] Instructions/current implementation audit and real immutable baseline.
- [x] Safe merge/CLI and permanent isolated tests: 107 focused sync/metrics/demo tests passed.
- [x] Dry-run preserved the baseline. JNJ/XOM/CAT/COST/F each committed successfully, passed 72 real summary/history content checks and full original-row/chunk preservation, then immediately reran with zero inserts and identical whole-table hashes. Canary facts: 10,984 total, structured issuers 15/35. See [rollout](../../../backend/reports/structured_financial_rollout.json).
- [x] Remaining 30 companies updated (47,897 inserts), no failures. Total 55,630 inserted; 58,881 facts across 35/35 issuers. Full 35-company rerun: zero inserts, identical whole-table hashes. AAPL-only final guard check also returned no-op under verified READ COMMITTED.
- [x] Regression, source/HTTP audit, coverage, documentation and self-review completed; final reference/whitespace checks recorded below.

## Test and validation strategy

Synthetic SEC payloads and real SQLite ORM: insert/preserve/no-op, concept/vintage/restatement/frame distinctions, validation, dry-run/subset/unknown, failure rollback/global outage, interruption recovery, CLI/report, forbidden chunks/model paths. Existing Item 6 and maintained backend suite, offline/mocked providers. Real baseline fingerprints/subset preservation, exact new identity uniqueness, orphan checks, per-canary checks, cross-industry summary/history content and bounded SELECTs, compile/import/Alembic, documentation references and git diff --check.

## Completion criteria

Safe existing ingestion entry points; tested identity/atomic failure recovery; sequential staged official SEC acquisition; all available issuers covered with honest successor gaps; no-op full rerun; all original rows and chunks/vectors preserved; Item 6 compatibility, complete reports/docs and full backend regression.

## Actual validation

Backend venv commands, `PYTHONDONTWRITEBYTECODE=1`:

- `python -m pytest tests/test_financial_sync.py tests/test_financial_metrics.py tests/test_setup_demo.py -q -p no:cacheprovider`: initial 107 passed. Added stale-isolation guard regression after self-review; final maintained suite includes 27 sync tests, 66 metrics tests and demo compatibility.
- `FINLENS_RUN_DB_TESTS=1`, `HF_HUB_OFFLINE=1`, `python -m pytest tests -q -p no:cacheprovider`: final **195 passed + 44 subtests**. Provider mocked; network fixtures isolated and real embedding regression offline. Existing deprecation warnings only.
- `python -m scripts.sync_financial_facts --ticker ... --dry-run --report reports/financial_facts_discovery.json`: 5 official sources; no DB changes, exact baseline preserved by read-only audit.
- Canary subsets JNJ/XOM/CAT/COST/F, then remaining 30, then full default rerun with separate reports: [rollout](../../../backend/reports/structured_financial_rollout.json). Each canary: no-op rerun and 72 real HTTP content checks; no failures/retries needed. Final guard check AAPL: no-op.
- `python -m scripts.verify_financial_sync --api-url http://127.0.0.1:8020`: all-company quarter/annual summaries and all default metric histories checked against stored sources. Eight representatives have 16 real summary and 56 real history bodies (1,477 observations) matched against DB-validated service models; `/companies` 35/35 Ready with one accession each; `/healthz` 200. Summary two SELECTs. Separate uvicorn process on 8020, OpenAI key empty.
- Compile new/modified Python sources in memory and import FastAPI: 19 routes, passed. `python -m alembic current/check`: d7b834408ba8 head; no new upgrade operations. No migration or dependency change.
- Final audit: every original ID/full-row hash preserved, old fact-subset hash matches baseline; company/chunk/vector full hashes unchanged. Facts 3,251 -> 58,881, structured issuers 10 -> 35, chunks/vectors remain 3,175; identity duplicates and orphan facts zero.
- Source revenue/net-income observations 35/35, EPS 34/35. Quarterly normalized revenue 34, net income 32, EPS 34, YoY 33, approved net margins 21; annual FCF 21. All 15 definitions' quarter/annual coverage is recorded, including honest unavailable/not-applicable results.
- Final documentation references, whitespace checks and Git scope are recorded in the outcome below.

## Final outcome

Item 7 completed: 35/35 catalog issuers have official structured facts; all 35 updated without failures. Total 55,630 new observations, final 58,881 rows. All 3,251 original rows and their per-company fingerprints (including AAPL) are unchanged. All companies/chunks/vectors preserved, no identity duplicates/orphans. Full catalog rerun and each canary rerun were no-ops, proving recovery from stored identity rather than reports. No speculative mappings or Item 6 selector changes.

Supported command/options, provenance identity, transaction locking/isolation, failure/interruption behavior and successor limitations are documented in README, data sources, architecture and metric contracts. ROADMAP marks Item 7 complete while frontend Research Mode stays unstarted. [Final audit](../../../backend/reports/structured_financial_verification.json) contains source/metric coverage, 72 real HTTP contents, 1,477 history observations, original-issuer fingerprints and actual test/import/Alembic evidence; [rollout](../../../backend/reports/structured_financial_rollout.json) aggregates all 35 per-company outcomes and no-op proof. Item 6 historical reports remain intact.

Known bounded limitations: XOM current CIK only 22 supported observations; unmapped latest income/absent EPS, incompatible revenue scopes, uncertain fiscal labels and negative CapEx remain honestly unavailable. No unresolved implementation blocker; independent data-integrity review is required by the user before commit. No frontend, filing indexing, retrieval, embeddings, dependency/schema changes, OpenAI, commit or push. Temporary verification server was owned by this task and cleaned up after final HTTP checks.

Final checks passed: 81 internal documentation targets/anchors; whitespace/conflict-marker/JSON/size checks across 32 changed files; git diff --check (line-ending notices only). Final Git scope: 8 modified and 24 untracked files, none staged. Suggested commit: `Add non-destructive SEC financial facts sync across curated catalog`.

## Final review correction — 2026-10-05

Independent review found one P2 reporting defect: a successful merge/flush followed by commit failure rolled back the rows, but retained positive `inserted_by_metric` counts. The sync now keeps merge results local until the transaction context commits successfully; company reports initialize every committed per-metric count to zero. Failed source/flush/commit paths therefore cannot publish provisional inserts as committed. Successful dry-run `would_insert` diagnostics retain their existing behavior. No transaction, ingestion identity or Item 6 selection changes were needed.

Permanent isolated regression `test_commit_failure_reports_zero_inserts_and_next_company_continues` observes the flushed AAPL row inside its transaction, injects a commit failure, verifies complete rollback and zero total/per-metric inserts, processes MSFT successfully, and checks the completed atomic JSON report against the returned result. It failed against the original implementation and passed after correction. The existing flush-failure regression also now asserts zero per-metric committed counts. Other source/error/health-check paths were inspected; no equivalent stale-count path remains in the sync report.

Validation from `backend`, with `PYTHONDONTWRITEBYTECODE=1`:

- New regression alone: **1 passed**.
- `python -m pytest tests/test_financial_sync.py -q -p no:cacheprovider`: **28 passed**, including CLI/report, dry-run, rollback, continuation and recovery cases. Existing datetime deprecation warnings only.
- Read-only PostgreSQL full-row fingerprints before/after are identical for companies, facts and chunks (including vectors), and match the stored final verification report. Counts remain **35 companies, 58,881 facts, 3,175 chunks and 3,175 embeddings**.
- `git diff --check`: passed (line-ending notices only). No live SEC sync, OpenAI, healthy-data mutation, full backend regression, commit or push was performed for this reporting-only correction.

The final review finding is resolved. Historical rollout/verification results above remain unchanged; this section records only the scoped correction and checks actually rerun. No remaining blocker from this finding. Suggested commit for this correction: `Fix financial sync counts published before commit`.
