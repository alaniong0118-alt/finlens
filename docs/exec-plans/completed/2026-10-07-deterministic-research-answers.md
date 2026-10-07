# Deterministic Research Answers

Status: completed
Roadmap phase: scoped Research Mode milestone

## Objective

Clear latest financial value questions receive a direct, typed answer before supporting SEC evidence, using existing Financial Metrics selection, with exact provenance and honest unavailable states. No LLM is required.

## Current architecture and context

Research Mode has company snapshots/history and selected-filing context retrieval. FinancialMetrics owns dates, economic bases, Decimal calculations and provenance. The answer layer will consume it without changing selectors. Starting Git status is clean (Item 8 and mounted tests already in checkout); next-env.d.ts SHA256 is B6768A2C7FB9A45BEA5D463A4993FDD8590BD50E5FCAB0C6F84921EE981ACC82. Preserve it via disposable build copy. Prior scope is recorded in [Item 8](2026-10-05-research-mode.md).

## Constraints

No commit/push, SEC/OpenAI calls, database mutation, schema/dependency change or financial selector change. Read-only whole-row database fingerprint before/after. Selected company is authoritative; never switch it from question text.

## Non-goals

No general chatbot, causal/segment/historical-date questions, comparisons, multi-filing retrieval, portfolio/risk/market data, Partial Evidence or Query Router 2.0.

## Implementation stages

1. Audit relevant API/UI/tests and capture baseline.
2. Typed read-only backend intent/answer layer; reuse financial histories/summaries.
3. Independent answer/evidence UI requests with cancellation/version guards, progressive provenance.
4. Permanent backend and mounted frontend regressions; tests/lint/build.
5. Real HTTP/browser checks, preservation, docs and self-review; complete plan.

## Decisions

- Bounded explicit phrase recognition plus a closed residual vocabulary: reject unrecognized qualifiers, causal verbs, dates, multiple metrics and ambiguous periods.
- Explicit quarter/annual use summary semantics; latest available uses normalized metric histories by actual period, selecting latest observation including unavailable (never backfill an older available result). Equal end dates prefer shorter direct duration over YTD/annual and disclose actual kind. Instant latest is as-of; explicit reporting periods match summary-end balance sheet values.
- One answer request and one existing context request run independently per submitted question. Answer has no filing accession dependency; narrative evidence is explicitly selected-filing scope.

## Discovered issues

The standard backend at 8000 is non-reloading Item 8 and its PID 7744 executable/command line is not inspectable at current privileges; it was preserved. Acceptance used guarded backend 8021 and an identical disposable production frontend 3003. Initial test failures were fixture expectations (stored Numeric four-decimal precision and intentionally incompatible mixed revenue bases), corrected without changing financial semantics. The existing static TSX loader required .tsx import support for the new shared component; updated its loader. A combined shell launch was policy-rejected; separate source-copy and foreground-managed server commands succeeded. Cold local embedding initialization delayed evidence while the direct answer was already visible.

## Progress

- [x] 2026-10-07: Root instructions, user brief, roadmap, plan rules, completed Item 8 plan, financial service/contracts and mounted tests audited.
- [x] Database baseline and live UI audited: 35/58881/3175/3175, existing full-row hashes retained.
- [x] Backend/UI implemented; explicit summary/latest-history semantics, source metadata, independent state/failure branches and no-indexed-filing path.
- [x] Tests/lint/build, HTTP/browser acceptance completed: 161 backend tests +27 subtests, 34 frontend tests including 14 mounted, lint, production build/typecheck, import 21 routes, 13 real answer HTTP cases/source equality.
- [x] Preservation/docs/self-review complete; all-row DB and next-env hashes unchanged; docs/roadmap updated; source/financial boundaries reviewed.

## Test and validation strategy

Focused answer tests (fixtures forbid provider/SEC), financial metrics and Research Mode regressions; complete frontend mounted/helper/API suite, lint, production build in disposable copy. Real stored AAPL/JPM/COST/JNJ/XOM HTTP/browser workflows, unsupported negative, themes/desktop/mobile/switching. Read-only fingerprint includes embedding rows. git diff --check. Record actual commands/results below.

## Completion criteria

Direct value/unavailable/provenance render before evidence; conservative fallback; no provider dependency; independent error branches and stale-state guards; required tests/lint/build/browser pass; data and next-env unchanged; docs reflect bounded scope.

## Final outcome

Completed within the bounded latest financial-value milestone. See [24-part engineering report](../../../backend/reports/deterministic_answers_final_report.md) and [actual acceptance record](../../../backend/reports/deterministic_answers_verification.json).

Actual commands/results:

- Backend cwd: `.venv/Scripts/python.exe -m pytest tests/test_research_answers.py tests/test_financial_metrics.py tests/test_capabilities.py tests/test_rag.py -q -p no:cacheprovider` — 161 passed, 27 subtests; no real database/provider/SEC mutation. Existing dependency deprecations retained.
- Backend cwd: `.venv/Scripts/python.exe -B -c "from app.main import app; print(len(app.routes))"` — 21 routes/import passed.
- Frontend cwd: `npm test` — 34 passed (14 mounted); `npm run lint` —passed. Existing Node module-type warning retained.
- Identical disposable source copy `D:/Projects/finlens-answers-validation-20261007`: `FINLENS_API_BASE_URL=http://127.0.0.1:8021 npm run build` (PowerShell environment assignment) — production/typecheck passed; page 110 kB / first load 213 kB. Existing node_modules junction, no install/dependency change. Repository next-env SHA256 unchanged.
- Backend cwd: `.venv/Scripts/python.exe -B -m scripts.verify_research_answers --api-url http://127.0.0.1:8021` —13 real HTTP cases matched typed service output and exact stored source/operand values, before/after fingerprints equal. AAPL $109.42B June 27, JPM $57.35B net-interest, COST incompatible bases unavailable, JNJ $5.53B, XOM $116.02B quarter/annual unavailable; EPS warning, annual/latest, negatives/mismatch checked.
- CUA actual production browser 3003: AAPL exact source/form/accession, direct before 5 evidence; JPM/COST/JNJ/XOM results; main product evidence fallback, clinical trial insufficient, mismatch guidance, switching removed old answer. Light/Dark/System actual OS Light, 1440/390 viewports with no page horizontal overflow, keyboard Enter View provenance/focus passed. Final polished build reloaded/rechecked. Controlled local context 503 preserved direct answer/provenance; configured fixture explicit AI 502 preserved direct answer and 5 real passages. External transport/client forbidden, no live provider calls. Normal no-key backend restored afterward.
- Final read-only fingerprint equality: 35 companies, 58,881 facts, 3,175 chunks/embeddings, all whole-row SHA256s equal to pre-work. No schema/data acquisition/write or selector change.
- Repository `git diff --check` passed (ordinary LF/CRLF notices); final Git status only this milestone, uncommitted/unstaged. No commit/push or next milestone started.

Known boundaries: bounded latest-value recognition, existing coverage/period/basis gaps, selected-filing retrieval heuristics, manual representative accessibility checks, no live AI success claim. Original acceptance used 3003/8021 because the then-stale 8000 process could not be safely identified. Closure checks now confirm the product serves 3000/8000 with the new route; isolated acceptance servers are stopped.

Suggested commit: `Add deterministic Research Answers with financial provenance`.

## Resume closure — 2026-10-07

Completed artifacts were already present. No implementation, tests, dependency or data changes were needed. Current diff includes unrelated startup scripts and generated next-env churn added after original acceptance; preserve these and exclude them from this milestone commit. Historical test/build/browser/fingerprint results were retained without expensive reruns.

Lightweight closure verified implementation/tests present, Python syntax/import, 83 internal documentation targets/anchors, agreement of recorded before/after/final fingerprints, and equality of ten frontend source files to the accepted production copy. Current 3000/8000 local HTTP/OpenAPI and one frontend-proxy AAPL deterministic answer passed ($109.42B, June 27, 2026). This is current HTTP availability, not a repeated browser audit. No external SEC/OpenAI calls, financial/index writes, commit/push or next milestone. Final git diff --check outcome is in the verification record. Status remains completed.

## Focused P2 recognition fix — 2026-10-07

The independent review reproduced reporting-method questions incorrectly receiving numeric answers because the residual vocabulary allowed `how`, `is` and `reported` without a phrase-level intent check. The correction requires every `how` clause to use the amount phrase `how much`; method clauses and mixed amount/method questions return `not_matched`. Clear amount requests can normalize the active verb `is/are/was/were reporting` to the existing value vocabulary, while reporting noun phrases remain rejected. Company mismatch, metric/period recognition and the closed residual vocabulary remain in force; FinancialMetrics selection is unchanged.

Permanent isolated API regressions cover 18 rejected questions and 10 accepted reported-value questions, including the original reproductions, accounting/policy/noun variants, compound questions, and original unsupported categories. Before correction, the initial 26-case set had seven expected failures, demonstrating the defect and missing progressive-verb value support. After correction, all 28 focused cases passed. Full `tests/test_research_answers.py`: 91 passed. Relevant `test_financial_metrics.py`, `test_capabilities.py`, `test_rag.py`: 98 passed and 27 subtests passed. Commands used `.venv/Scripts/python.exe -B -m pytest ... -q -p no:cacheprovider` from backend, with isolated fixtures forbidding SEC/OpenAI; no development database was accessed or modified. Existing dependency deprecation warnings remain.

Only the recognizer, its regression tests and this record changed for the fix. Existing unrelated working-tree changes were preserved. No new plan was needed for this small correction under `.agent/PLANS.md`. No frontend/build/browser rerun, financial/index writes, external calls, commit/push or next-milestone work. Final `git diff --check` passed. The running backend must load the revised module on its next restart; no live-server acceptance was claimed for this follow-up.
