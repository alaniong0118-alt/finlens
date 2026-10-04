# Item 6 — Standardized financial metrics

Status: completed
Roadmap phase: 2

## Objective

Provide deterministic, typed company summaries and metric histories over existing FinancialFact rows, with compatible periods, explicit missing data and complete provenance. Audit all 35 companies without changing data.

## Current architecture and context

Follow [architecture](../../architecture.md), [engineering standards](../../engineering-standards.md) and [plan rules](../../../.agent/PLANS.md). Starting tree was clean at `0caa8cf` (Item 5 already committed by the user before this task). Legacy financial routes use financial_analysis.py; retain their contracts. FinancialFact has no separate original-concept column, but the importer preserves it in source. The replacing importer is not called.

Read-only baseline/audit: 35 companies, 3,251 facts, 3,175 chunks/vectors. Only 10 companies have facts; only Revenues (1,120), NetIncomeLoss (1,175), and EarningsPerShareDiluted (956) exist. Four revenue concepts are present. No cash/asset/liability/gross-profit/operating-income/cash-flow/CapEx observations exist. Full-row hashes are in [verification](../../../backend/reports/financial_metrics_verification.json). No real stored CapEx sign convention can be measured.

## Constraints

No database mutation, schema/dependency change, SEC indexing changes, retrieval changes, OpenAI calls, frontend work, commit or push. Preserve all existing uncommitted work.

## Non-goals

Fact ingestion expansion, Q4 subtraction, currency conversion, industry classification, dashboard/chart work, caching, later roadmap items.

## Implementation stages

1. Audit stored units/concepts/dates/context and record preservation baseline.
2. Add centralized registry, date-aware selectors, provenance schemas, Decimal derivations and two thin API routes.
3. Realistic fixtures and existing financial analysis regression; all-company coverage and representative stored-row/formula verification.
4. Full backend regression, import/Alembic/real HTTP/query counts, preservation, docs, self-review, completion.

## Decisions

- 2026-10-04: Service-only normalization; two additive /financials routes preserve existing legacy contracts.
- Audited revenue aliases retain original concepts; unsupported core concepts return unavailable. Additional standard primary concepts are conditional definitions tested with fixtures, not claimed real coverage; no speculative alias lists.
- Reclassify using dates, never trust stored period_type or filing fy/fp as period identity. Preserve source labels separately. Normalize fiscal labels only with reliable annual/YTD boundaries; leave ambiguous labels null.
- Select exact periods first, then deterministic restatement/concept/form tie breaks. Keep selected and alternative fact IDs/values visible; never average.
- Ratio outputs use ratio units (0.25 means 25%). Nonpositive revenue/prior-revenue denominators are unavailable; negative earnings remain valid. CapEx primary payment concept is a positive outflow; negative payment facts are rejected, never abs-converted. No real FCF coverage is claimed.

## Discovered issues

The legacy importer deduplicates before storage and conflates some filing-context fiscal labels with observation labels. Lost historical candidates cannot be reconstructed. All 25 newer catalog companies lack structured facts. Broader metric coverage requires a later explicitly authorized import, not invented observations.

Focused tests initially exposed an incorrect expected SEC index URL in the test itself; correcting its hyphenated accession assertion resolved four failures. Self-review corrected history availability to reflect its returned window rather than an older observation outside the requested limit. The existing backend process predates the new routes and port 8001 is occupied; real HTTP verification used an independently launched backend on 8016, leaving existing services intact.

## Progress

- [x] Instructions/code/data audit and preservation baseline.
- [x] Registry, service, schemas and two additive API routes.
- [x] 35 focused tests; five legacy read-only scripts and legacy fixture contract; full backend 137 tests and 44 subtests passed.
- [x] Real 35-company audit, representative source/formula checks, 20 real HTTP summary/history responses, unknown company/metric and health checks, two-SELECT summary, unchanged fingerprints; compile/import and Alembic clean.
- [x] Documentation, source/formula/period self-review, internal references and git diff --check; completed outcome recorded.

## Test and validation strategy

Isolated ORM fixtures: aliases, units, duration/instant, YTD/quarter/annual, restatements, non-calendar/53-week calendars, missing/zero/negative operands, margins/YoY/FCF, provenance, API errors and bounded SELECT counts. Real database is read-only: verify all 35 coverage, direct representative row/formula lineage, full-table hashes, HTTP. Full maintained backend suite includes provider-mocked opt-in DB tests; inspect legacy scripts before executing. Compile/import, Alembic check, documentation links and git diff --check.

### Actual commands and evidence

From backend using `.venv/Scripts/python.exe`:

- `-m pytest tests/test_financial_metrics.py -q`: 35 passed, including a maintained legacy financial-analysis contract fixture.
- With PowerShell `FINLENS_RUN_DB_TESTS=1` and `HF_HUB_OFFLINE=1`, `-m pytest tests -q`: 137 passed and 44 subtests passed; real provider client mocked in DB regressions.
- Five inspected legacy scripts (`test_core_financials.py`, `test_financial_db.py`, `test_financial_history.py`, `test_financial_snapshot.py`, `test_financial_summary.py`) executed via runpy under a patched SessionLocal bound to a read-only PostgreSQL transaction: all completed. These are script smoke checks, not extra assertion-based tests.
- `-m scripts.verify_financial_metrics --api-url http://127.0.0.1:8016`: all 35 summaries/histories audited, representative values and independent formulas compared with source rows, 20 real HTTP summary/history responses passed; unknown company/metric 404 and health 200. Summary uses two SELECTs. Temporary server: `-m uvicorn app.main:app --host 127.0.0.1 --port 8016`.
- `-m py_compile` for new registry/schemas/service/verifier/tests and main; FastAPI import: passed.
- `-m alembic current` / `check`: head `d7b834408ba8`, no upgrade operations.
- Final read-only full-row SHA-256/count check: baseline unchanged. Git root: `git diff --check`; internal documentation files/anchors and untracked whitespace checked.
- Continuation after interruption: preserved the completed implementation and prior validation; finalized the JSON report and moved this plan to completed. Report consistency, 64 internal links/anchors across seven changed documents, all eight untracked files' whitespace/conflict-marker checks and final `git diff --check` passed. No expensive regression, HTTP or database validation was repeated.

Real examples: AAPL FY2026 Q3 revenue 109,417,000,000; MSFT FY2026 Q3 revenue 82,886,000,000 (March quarter, June annual not synthesized); JPM FY2026 Q2 net-interest revenue 57,347,000,000; WMT FY2027 Q2 revenue 186,100,000,000. All match selected stored rows. GS/COST/JNJ/XOM/CAT/F have no stored facts, so validation confirms unavailable behavior rather than claiming numeric verification. These checks establish consistency with stored sources, not a new external SEC numerical audit. No real CapEx sign/FCF coverage exists; fixture-only convention is explicit.

## Completion criteria

Centralized canonical service, safe financial periods/formulas, typed snapshot/history API, provenance and unavailable results, realistic tests, real coverage report and independent stored-row checks, no database changes or provider dependency, clean regression and docs. Coverage gaps are limitations, not fabricated completion gates.

## Final outcome

Item 6 completed within existing-data scope: centralized 15-definition registry, typed summary/history API, deterministic selection/calculations, selected/alternative/input provenance, explicit missing data and preserved legacy interfaces. [Contracts](../../financial-metrics.md) document rules and limitations; [verification](../../../backend/reports/financial_metrics_verification.json) records audit, coverage, representative lineage and identical before/after hashes. Counts remain 35 companies / 3,251 facts / 3,175 chunks / 3,175 vectors. ROADMAP reflects completed backend layer and limited structured coverage. No schema/dependency/indexing/retrieval/frontend changes, OpenAI calls, commit or push; no next milestone started. No engineering blockers; broader metric/issuer coverage remains a documented acquisition limitation. Final task tree: 6 modified and 8 untracked files. Suggested commit: `Add standardized financial metrics with period-aware provenance`.

The independent review required conservative Dec/Jan inference, revenue economic scopes, EPS comparability metadata and deeper history verification. These follow-up corrections have a separate [review-fix record](2026-10-04-financial-semantics-fixes.md); the initial counts above are historical validation, not the updated test/metric coverage. Item 7 must address replacing ingestion and early deduplication before acquiring broader structured data; it remains unstarted.
