# Historical & Comparative Deterministic Research Answers

Status: completed (2026-10-08)
Roadmap phase: scoped Research Mode milestone

## Objective

Explicit fiscal years/quarters and bounded two-period comparisons use stored normalized financial observations, Decimal calculations and both-side provenance without an LLM. Preserve latest-value, evidence and optional-AI independence.

## Current architecture and context

FinancialMetrics owns exact-date classification, fiscal labels, scope-aware source/vintage selection and derived inputs. The existing research-answer service has closed-vocabulary latest-value recognition and two SELECTs. FilingSearch independently settles answer/evidence requests with scope guards. Reuse [metric contracts](../../financial-metrics.md), [latest-answer plan](../completed/2026-10-07-deterministic-research-answers.md) and [presentation plan](../completed/2026-10-07-answer-presentation-evidence-highlighting.md).

Starting Git state: eight modified and six untracked prior presentation artifacts; preserve all, especially unrelated generated next-env.d.ts churn. No changes to raw financial data, schema or dependencies are planned.

## Constraints

No SEC/OpenAI calls, financial/index writes, commit/push or future milestone. Fiscal meaning must follow existing normalized labels, never filing-context FY. Missing/ambiguous periods, incompatible revenue/input scope and uncertain EPS comparability must be explicit. Record read-only whole-row fingerprints before/after.

## Non-goals

General natural-language reasoning, arbitrary dates/time series, cross-company answers, Q4 synthesis, calendar conversion, restatement reconstruction, new retrieval or acquisition, Data Freshness/Risk/Portfolio/Market/ML work.

## Implementation stages

1. Audit services/contracts/tests and real representative histories; capture baseline.
2. Add normalized fiscal-period lookup and compatible comparison within Financial Metrics; extend bounded backend intent/typed answer.
3. Reuse answer card for historical/comparison display and both-side disclosures; keep independent request/state guards.
4. Permanent backend/API and mounted frontend regressions, focused related suites, lint/build/import.
5. Real HTTP/browser acceptance, fingerprints, documentation, self-review and plan closure.

## Decisions

- Preserve latest-value recognition and selection; historical parsing adds a separate bounded grammar after shared company checks.
- Explicit year defaults to annual fiscal-end-year convention. Quarter requires one unambiguous normalized fiscal-year/quarter match. Never infer from SEC filing-context labels.
- Comparison math and compatibility belong in Financial Metrics, not frontend. Show absolute change when safe; percentage requires a positive baseline. Ratio comparisons use percentage-point change. EPS remains explicitly as-filed/unverified.

## Discovered issues

Read-only audit: AAPL FY2024/FY2025 revenue is $391.035B/$416.161B; Q2 FY2025 is $95.359B. JPM annual revenue is already ambiguous across economic bases; same-quarter net-interest histories remain available. COST annual totals are compatible, but Q3 FY2026 uses customer-contract revenue versus Q3 FY2025 total revenue; that comparison must be unavailable. JNJ FY2025 net income is $26.804B. XOM has no annual series and unlabeled quarters, so explicit fiscal requests remain unavailable. Baseline fingerprints are in backend/reports/historical_answers_baseline.json.

## Progress

- [x] 2026-10-08: Read task, root instructions, roadmap, plan standard, completed plans and relevant services/contracts/tests.
- [x] Representative stored-history audit and baseline fingerprint (35/58,881/3,175/3,175, hashes match prior milestone).
- [x] Implementation/self-review: final 233 relevant backend tests and 55 frontend tests (26 mounted) passed, including fiscal-calendar alignment and all-metric routing.
- [x] Lint, TypeScript/no-emit, FastAPI import and production build passed. Build used an identical disposable source copy to preserve generated repository files.
- [x] 26 real HTTP/source audits; actual browser acceptance across five companies, four widths, themes and keyboard disclosures. Controlled mounted evidence/AI failure and scope-race tests passed.
- [x] Whole-row database fingerprints unchanged after HTTP/browser acceptance.
- [x] Documentation, reference validation, diff check and self-review completed.

## Test and validation strategy

Isolated SQLite API fixtures forbid external clients. Test annual/quarter/YTD/Q4, fiscal ambiguity/vintages, revenue/input basis, EPS warnings, zero/negative/equal changes, conservative language/mismatch, latest regression and bounded SELECT count. Mounted actual components test success/unavailable, both-side provenance, independent evidence/AI failure and stale scopes. Full frontend suite/lint/build/typecheck; relevant answer/metrics backend suites/import. Guarded local backend and real browser cover AAPL/JPM/COST/JNJ/XOM, themes/mobile/fallback. Before/after whole-row fingerprints include vectors. git diff --check and internal documentation references.

## Completion criteria

Required explicit historical/comparison questions route deterministically; annual/quarter semantics and scope protections hold; calculations/provenance are auditable; causal/ambiguous questions fall back; async failures/switches preserve correct state; tests/lint/build/browser pass; raw/index data unchanged; accurate docs.

## Final outcome

Completed within bounded single-company, single-metric fiscal scope. Both comparison operands retain exact source provenance; positive-baseline percentage growth, ratio percentage-point changes and EPS warnings are explicit. Missing/incompatible periods remain unavailable. Fiscal-calendar boundary/duration alignment is checked before comparison. No SEC/OpenAI calls, database writes, dependencies, schema changes, commit or push.

See the [final engineering report](../../../backend/reports/historical_answers_final_report.md), [HTTP/source audit](../../../backend/reports/historical_answers_verification.json) and [browser record](../../../backend/reports/historical_answers_browser.json). Counts remain 35 companies, 58,881 financial facts, 3,175 chunks and 3,175 embeddings. Prior presentation work and unrelated generated next-env churn were preserved. Broader time-series/cross-company work remains outside this milestone.

## P2 recognition review fix — 2026-10-08

The independent review found explicit non-adjacent YoY wording was consumed by the revenue-growth alias and converted into cumulative growth. Capture the qualifier first. Accept an adjacent annual/same-quarter interval expressed as a range or from/to; conservatively reject compare/vs/between requests for independent YoY rates and non-adjacent explicit YoY. Label ordinary multi-year revenue changes cumulative. The existing single-period YoY metric and financial selection/calculation remain unchanged.

- [x] Added 27 isolated production-API regressions, including missing/basis-incompatible operands, company mismatch, quarter alignment, unsupported/causal wording and cumulative labels. Before the fix, the focused selection had 12 failures.
- [x] From backend: `.venv/Scripts/python.exe -B -m pytest tests/test_historical_research_answers.py -q -k 'yoy or multiyear' -p no:cacheprovider`: 28 passed (27 new cases plus one existing).
- [x] From backend: `.venv/Scripts/python.exe -B -m pytest tests/test_historical_research_answers.py tests/test_research_answers.py -q -p no:cacheprovider`: 190 passed (99 historical/comparative and 91 existing deterministic).
- [x] Six current-code service checks over read-only stored AAPL facts confirm rejected YoY questions, adjacent +6.43% and cumulative FY2022–FY2025 +5.54%. Whole-row hashes/counts match the original baseline before/after; recorded under `yoy_recognition_review_fix` in the machine report.
- [x] Documentation and `git diff --check` completed. No frontend/build or broader suite rerun: only recognition/backend display wording changed. No live-server restart/HTTP reacceptance is claimed for this follow-up.

No database writes, SEC/OpenAI calls, dependencies, registry/selector changes, commit or push. Existing mixed presentation changes and generated next-env churn remain preserved. Suggested fix commit message: `Preserve explicit YoY intent in historical research answers`.


## Three P2 recognition-safety fixes — 2026-10-08

Completed bounded follow-up; no next milestone started.

- Growth aliases previously consumed the grammatical target before comparison conversion. Reject change/increase/decrease/grow verbs targeting revenue growth itself; do not compare revenue levels in place of two growth rates. Explicit rate vocabulary remains unsupported through the closed grammar.
- Include normalized year-to-year wording in the existing explicit YoY qualifier, preserving adjacent-year/same-quarter compatibility checks and rejecting non-adjacent or independent-rate comparisons.
- A shared notation guard protects both latest and historical routing. Inspect original mathematical notation: slash-year/yr (including fiscal/calendar-year) qualifiers are unsupported annualization. Relative percent changes in margins are unsupported; never substitute percentage points. Revenue percent-change and ordinary margin comparisons remain supported.

Validation from `backend/`:

- `.venv/Scripts/python.exe -B -m pytest tests/test_historical_research_answers.py -q -k math_intent -p no:cacheprovider`: 45 focused API cases passed after final changes.
- `.venv/Scripts/python.exe -B -m pytest tests/test_historical_research_answers.py tests/test_research_answers.py -q -p no:cacheprovider`: 235 passed (144 historical/comparative, 91 existing deterministic).
- Synthetic FY2023/2024/2025 revenue 50/100/110 proves rates 100%/10% fall despite levels rising. Rate-change questions fall back; legitimate revenue comparisons return +10%. Margins 20%/25% retain +5 percentage points for ordinary comparisons, but relative `% change` questions fall back. Ordinary FY2022/2025 revenue 40/110 returns +175% explicitly cumulative.
- Four in-memory mutation checks, without editing production files, were detected: removing growth-target guard caused 6 failures; slash-year guard 6; relative-margin guard 4; year-to-year qualifier 7. Original functions/regex restored; focused tests rerun normally.
- Syntax compilation in memory and FastAPI import passed. `git diff --check` passed (existing LF/CRLF notices only).
- Isolated SQLite fixtures forbid SEC/OpenAI clients. No development data writes or frontend/dependency/registry/selector modifications. Current PostgreSQL connection failed even with a bounded timeout; current fingerprints were **not reverified**. Historical baseline remains 35 companies / 58,881 facts / 3,175 chunks / 3,175 embeddings; do not treat that prior observation as a live check.

Limits: rate differences, relative margin growth, annualization/CAGR and arbitrary time-series analysis remain unsupported. No browser/build or broad financial-metrics regression rerun was warranted by this recognition-only change. Existing 15 modified/15 untracked mixed milestone files remain preserved; generated `frontend/next-env.d.ts` is unrelated and unchanged by this follow-up. Do not stage prior presentation files or generated churn with this fix. No commit or push.

Suggested scoped fix commit: `Guard unsupported financial growth and percentage intents`.


## Mathematical-intent follow-up — 2026-10-08

Status: completed (bounded review correction; original milestone history retained).

The final review found that alias-dependent growth guards missed possessive/reordered targets, margin guards omitted grow/grew, and raw slash regexes missed punctuation within per-year denominators. Replace these scattered checks with a small structured preflight over original-question tokens that retain `%` and `/`. Classify the operation independently of aliases before the closed grammar consumes wording. Unsupported operations must fall back, with company mismatch taking precedence.

Validation completed below: permanent API equivalence/metamorphic cases using 50/100/110 revenue and 20%/25% margins; focused and full historical/deterministic tests; three in-memory mutation checks; syntax/import; read-only baseline fingerprints if available; final diff/status review. No financial selector, registry, calculation, provenance, frontend, dependency or data changes are authorized. Preserve the existing mixed working tree and generated next-env file.


## Structured mathematical-intent correction — 2026-10-08

The focused independent review found equivalent wording still bypassed the earlier guards. Those earlier pass counts remain historical validation of listed cases, not proof of complete recognition. This follow-up replaces the scattered alias-dependent growth/notation guards with `MathematicalIntent` and `classify_math_intent` in the answer service.

Original-question tokens retain `%` and `/` before destructive word normalization or aliases. A finite operation/target classification separates value/level change, growth-rate change, point difference, relative percentage, annualized and unsupported operations. Growth plus a change verb rejects regardless of possessive/reordered syntax; compound targets conservatively abstain. Relative margin operations reject for all existing comparison verbs, including grow/grew. Slash/per-year operands survive parentheses, spacing and fiscal-year hyphens; unknown slash expressions also abstain. Company mismatch still wins over unsupported intent. The closed grammar and existing YoY adjacency rules remain a second gate; classification never selects facts or performs arithmetic.

Validation actually run from `backend/`:

- 149 new permanent FastAPI/service-path cases: 36 growth-target variants, 36 relative-margin variants, 44 annualization variants, 24 legitimate level/YoY variants, four ordinary margin comparisons and five ambiguous/unsupported cases. The typography matrix covers plain, uppercase, doubled whitespace and curly apostrophe/en-dash/parenthesized-growth forms.
- `.venv/Scripts/python.exe -B -m pytest tests/test_historical_research_answers.py -q -k preflight -p no:cacheprovider`: 149 passed.
- `.venv/Scripts/python.exe -B -m pytest tests/test_historical_research_answers.py tests/test_research_answers.py -q -p no:cacheprovider`: 384 passed (293 historical/comparative plus 91 existing deterministic).
- Synthetic revenue 50/100/110 keeps YoY rates 100%/10%; rate-change requests reject while level changes return +10%. Margins 20%/25% reject relative percent requests and retain +5 percentage points for ordinary comparisons. Ordinary multi-year growth stays explicitly cumulative; compatible adjacent YoY remains available.
- Three in-memory operation mutations were caught by the new API tests: misclassifying growth-target operations caused 28 failures; relative-margin operations 28; annualization 20. No production file was mutated by these checks.
- Syntax/FastAPI import and final `git diff --check` passed. Existing dependency deprecation and LF/CRLF notices are not test failures.
- Read-only current PostgreSQL fingerprints match the original baseline: 35 companies, 58,881 financial facts, 3,175 chunks and 3,175 embeddings. All company/fact/chunk-with-vector SHA256 values match. No data writes, financial selection/registry/calculation/provenance changes, SEC/OpenAI calls, frontend/dependency changes or next milestone work.

Supported wording is deliberately bounded; growth-rate differences, relative margin growth, annualization/CAGR, arbitrary division and arbitrary time-series analysis remain unsupported. Explicit percentage-point vocabulary may fall back when outside the closed grammar; ordinary margin comparisons already return correctly labelled points. No browser/build rerun was needed. Existing mixed milestone changes remain preserved (15 modified/15 untracked); generated next-env churn is excluded from the intended commit, and shared frontend/documentation files still require hunk-level separation. No staging, commit or push.

Suggested scoped commit message: `Classify financial operations before research-answer normalization`.

## Recognition-handoff redesign — 2026-10-08

Status: completed (bounded correctness follow-up).

Objective: retain operation, canonical metric, fiscal operands and support status through dispatch. Reject independently labelled growth observations and preserve Unicode mathematical operators before normalization. Financial selection/calculation, API schema, frontend, dependencies and development data are out of scope.

Stages: implement typed recognition/dispatch boundary; add isolated API equivalence and contract regressions; run focused/full deterministic suites and three in-memory mutations; verify syntax/import, read-only fingerprints and protected files; update reports and complete this plan.

Completion criteria: both reproductions reject, supported value/interval/margin requests remain correct, no operation substitution through dispatch, mutations fail meaningfully, data preserved and diff clean. Existing mixed working tree remains intact. No commit/push or external calls.


### Handoff follow-up outcome

- [x] Typed operation contract and mandatory dispatch agreement implemented; requested growth metric is retained until an explicit revenue interval operation dispatches.
- [x] Independently labelled growth observations, Unicode operators and unknown notation protected; no new financial calculations.
- [x] 119 new API regressions and 503 combined historical/deterministic tests passed. All FinancialMetrics selection/economic-basis/Decimal/provenance code preserved.
- [x] In-memory mutations caught operand (12 failures), Unicode (8) and operation-agreement (6) removal; originals restored.
- [x] Syntax/FastAPI import passed. Actual before/after read-only database fingerprints equal the baseline: 35 companies, 58,881 facts, 3,175 chunks/embeddings.
- [x] Updated financial contracts, verification JSON and final report. No frontend/dependency/schema/data writes, SEC/OpenAI calls, staging, commit or push.

Commands and bounded limitations are in the final report's recognition-handoff section and machine record. All completion criteria satisfied; final `git diff --check` passed (existing LF/CRLF notices only). Working tree: 15 modified, 16 untracked; nothing staged. Existing mixed milestone work and generated next-env churn remain untouched. Suggested scoped commit: `Enforce typed financial operations through research-answer dispatch`.
