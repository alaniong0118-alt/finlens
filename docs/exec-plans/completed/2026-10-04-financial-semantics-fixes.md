# Item 6 financial-semantics review fixes

Status: completed
Roadmap phase: 2, Item 6 review corrections

## Objective

Resolve conservative fiscal-year inference, revenue economic scope, EPS history comparability and history verification findings without redesigning the accepted metrics architecture.

## Current architecture and context

Read [instructions](../../../AGENTS.md), [plan standard](../../../.agent/PLANS.md), [roadmap](../../../ROADMAP.md), [metric contracts](../../financial-metrics.md) and the [Item 6 implementation record](../completed/2026-10-04-financial-metrics.md). Starting tree: six modified and eight untracked Item 6 files; preserve all completed work. Registry/service/schemas normalize stored FinancialFact rows through two additive routes.

Pre-change read-only verification matched the [report](../../../backend/reports/financial_metrics_verification.json): 35 companies, 3,251 facts, 3,175 chunks and 3,175 embeddings. Full-row SHA-256: companies `ace9bd807d59983386906c3e3612bc2b05c262344731ba4421bbf2c6586084f0`; facts `8be8dfd4d532d5cc79b6a66f03b1db06197bbfbb6dd515f03f8b55c265e46581`; chunks including vectors `ca6ce451d4060723b3c3dcc73c58a623a5dfac37a8246b435f69d8bb4bdf3c12`.

## Constraints

No fact mutation, SEC acquisition/indexing, retrieval/frontend/schema/dependency changes, OpenAI calls, Item 7 implementation, commit or push. Taxonomy documentation may be consulted to establish concept meaning; no new company observations acquired.

## Non-goals

Importer repair, broader fact coverage, split-adjustment heuristics, dashboard work, architectural rewrite.

## Implementation stages

1. Verify taxonomy meanings and choose minimal explicit revenue basis/comparability rules.
2. Correct fiscal-year inference and add typed revenue/EPS metadata with permanent regressions.
3. Verify full representative histories and HTTP contents; run focused and full backend regressions, import/Alembic and preservation checks.
4. Update contracts/report and Item 7 ingestion prerequisite; self-review and move this record to completed.

## Decisions

- Preserve deterministic restatement ordering only within economically compatible revenue candidates; uncertainty must remain visible with candidate provenance.
- EPS remains exactly reported; share-basis comparability is unverified, never heuristically adjusted.
- Fiscal quarter and fiscal year evidence are independent; a supported quarter may retain a null year.
- FASB documentation confirms four separate bases: total earning activities, customer contracts, normal-course net sales and earning activities net of interest expense. No production cross-family equivalences are approved. Single component observations remain source-faithful and labelled, but do not establish consolidated margin denominators. Exact same-concept restatements remain deterministic.
- Project fiscal end year across 364–371 days only after a full previous year; require a unique year. Two consecutive full calendar years with identical month/day boundaries separately support calendar-year projection. Refinement from null to an observed annual end year is allowed; confident Dec/Jan guesses are eliminated.
- Use a Pydantic wrap serializer to omit absent additive metadata, retaining the documented 2.10 minimum without dependency changes.

## Discovered issues

Current importer replaces rows and deduplicates concepts before storage. This is an Item 7 prerequisite, not part of these fixes. Single retained revenue concepts cannot prove equivalence to discarded alternatives.

The conservative week-calendar range alone left JPM's Jan–Dec current-year label null. Repeated stored full-calendar boundaries provide independent evidence, so a separately tested calendar-pattern rule preserves FY2026 Q2. Seven latest-quarter net margins were previously computed from customer-contract revenue without total-scope evidence; they now return unavailable. GOOGL/NVDA/JPM retain approved margins (3/35), while reported revenue/net income/compatible latest YoY remain 10/35. This is an intentional correctness reduction, not a data loss.

## Progress

- [x] Read instructions/request/current state; record unchanged database baseline.
- [x] Implement scoped fixes and regression fixtures.
- [x] Focused/full tests, representative read-only histories/HTTP, import/Alembic and fingerprints.
- [x] Documentation, report, self-review and completed outcome.

## Test and validation strategy

Permanent Dec/Jan 52/53-week and non-calendar fiscal fixtures; total/subset/bank conflicts and compatible/incompatible alias transitions; source-faithful EPS vintage fixtures. Verification helpers must reject wrong history ordering, types, values and source lineage, and compare HTTP bodies. Use SQLite fixtures and PostgreSQL read-only transactions. Full backend opt-in DB suite uses mocked provider and offline embedding cache. Record actual commands/results separately from planned checks.

## Completion criteria

All four findings addressed; canonical scope and uncertainty visible; representative outputs either correct or explicitly unavailable; real history lineage and HTTP content checked; relevant/full tests and Alembic clean; exact table counts/hashes preserved; documentation complete and next milestone unstarted.

### Actual validation

From `backend/` using `.venv/Scripts/python.exe`:

- `-m pytest tests/test_financial_metrics.py -q -p no:cacheprovider`: 66 passed (31 new cases plus maintained tests), including existing financial-analysis compatibility. Dec/Jan 52/53-week refinement, non-calendar, explicit/absent scope equivalence, bank conflicts, margin denominator, EPS vintage and verifier corruption cases passed.
- `FINLENS_RUN_DB_TESTS=1`, `HF_HUB_OFFLINE=1`, `-m pytest tests -q -p no:cacheprovider`: 168 passed plus 44 subtests; provider mocked, SQLite mutation fixtures isolated, real database regressions read-only. Existing deprecation warnings only.
- `-m scripts.verify_financial_metrics --api-url http://127.0.0.1:8017`: all 35 summary/history datasets verified against source rows. Ten real HTTP summaries and 26 histories (716 observations) checked, including annual revenue, EPS comparability and derived inputs; unknown company/metric 404, health 200. Two SELECTs remain.
- `-m py_compile` on registry/schemas/service/verifier/tests/main; explicit FastAPI import: 19 routes, passed.
- `-m alembic current` / `check`: `d7b834408ba8 (head)`, no new upgrade operations.
- Pre/post full-row fingerprints match. No OpenAI call or SEC company-data acquisition; only FASB taxonomy definitions consulted.

Representative latest values/periods remain: AAPL FY2026 Q3 revenue 109417000000; MSFT FY2026 Q3 82886000000; JPM FY2026 Q2 57347000000; WMT FY2027 Q2 186100000000. Original income/EPS and compatible YoY inputs remain source-faithful. JPM net margin remains 0.3688946239559174847856034317; AAPL/MSFT/WMT margins are unavailable with scope reasons. All no-fact issuers remain unavailable. Independent re-review is still the user's next gate.

## Final outcome

All four findings resolved within the accepted registry/service/schema architecture. Scoped changes: five backend implementation/test/verifier files, report, README/architecture/product/metric contracts, original Item 6 record, this record and the ROADMAP Item 7 risk note. The original Item 6 route/data-source changes remain preserved. No schema, dependency, ingestion, retrieval, frontend or database mutation; no provider calls, next milestone, commit or push.

Final checks: documentation references/anchors and untracked whitespace/conflict markers passed; `git diff --check` passed with line-ending notices only. The verification report preserves pre/post hashes, records 66 focused / 168 full tests plus 44 subtests, 36 real summary/history content checks and deliberate margin-coverage changes. Final Git scope: six modified and nine untracked files, none staged. Suggested commit: `Fix financial metric scope, fiscal inference and history verification`. Independent re-review remains pending; no unresolved implementation blockers. Broader acquisition still requires Item 7 ingestion-safety work.
