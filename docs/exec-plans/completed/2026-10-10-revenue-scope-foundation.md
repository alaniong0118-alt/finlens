# Bounded revenue scope authorization foundation

Status: completed
Roadmap phase: scoped Financial Metrics Layer enabling work; no real activation

## Objective
Implement separate, immutable observation-selection and Net Margin denominator permissions, with empty production registries. Every existing production output must remain unchanged.

## Current architecture and context
Baseline: main / b1bb70a. Preserve modified frontend/next-env.d.ts and the two untracked runtime reports (canary-aapl_guarded_live_20261010_111844_3580610-publication.json and refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json).
The selector groups exact dates, resolves economic basis before ranking, and permits only one reviewed Gross Margin pair with a raw-observation ambiguity guard. FinancialFact lacks original XBRL contexts/dimensions and document identity; Company Facts frame/fiscal annotations do not establish these properties.

## Constraints
No SEC/model calls, data writes/migrations/refresh, restarts, full coverage audit, frontend changes, commit or push. Production permissions must stay empty. Evidence validation must not infer consolidated scope from numeric equality or tag names.

## Non-goals
Activation of AAPL Net Margin or historical revenue; global equivalences; arbitrary margin types; restatement reconciliation; approval service or schema migration.

## Implementation stages
1. Define immutable source/evidence/permission/lifecycle contracts and deterministic validators.
2. Add isolated, empty-registry integration to ambiguous component-revenue selection and denied Net Margin only.
3. Add synthetic in-memory observation tests (no database persistence), targeted existing-output regression and documentation.
4. Run focused tests, baseline comparison, diff check and self-review; complete plan.

## Decisions
- 2026-10-10: Independent evidence is an explicitly supplied immutable evaluation input; no production evidence adapter is fabricated. A future activation needs verified local document/XBRL context extraction.
- 2026-10-10: Exact reviewed candidate manifests detect new vintages/scopes, including same-value amendments. Differing-value vintages are distinguished from same-source conflicts and rejected; automated restatement reconciliation is outside this foundation.
- 2026-10-10: Preserve concept/basis and the existing Gross Margin path. Permissions apply only to their exact use and never bless comparisons globally.
- 2026-10-10: Approval lineage checks use the full permission registry and withdrawal history, including successors with different scopes. Version reuse with contradictory content is rejected.
- 2026-10-10: Limit first-release context authorization to explicitly verified undimensioned observations. SourceEvidence is a trusted internal input; no automatic evidence extraction/authentication is claimed.

## Discovered issues
Historical 2018/2019 primary-statement context is not established. FinancialFact rows cannot independently prove dimensions or consolidation; missing evidence must disable the new paths.
The first focused run found a rejection-reason dependency on row ranking for a conflicting denominator observation (47 passed, 1 failed). Moving raw manifest/conflict validation ahead of selected-operand identity checks fixed this; both insertion orders now produce the same conflict rejection.

## Progress
- [x] Read governing instructions, current Git state, relevant selector/contracts and Astra requirements.
- [x] 2026-10-10: Implement immutable contracts, empty registries and isolated integration, with preserved original concept/basis and traceable rejected raw alternatives.
- [x] 2026-10-10: Complete synthetic lifecycle/conflict/isolation tests: final run 76 passed in 0.53s, no database access/persistence.
- [x] 2026-10-10: Compare current AAPL outputs against b1bb70a over 2,343 existing facts: five summaries plus twenty selected metric histories serialize identically. Each comparison run used two SELECTs in a REPEATABLE READ, READ ONLY transaction; no data writes. Self-review confirms registry/formula/Gross Margin guard unchanged. Complete diff check recorded below.

## Test and validation strategy
Pure synthetic FinancialFact objects without sessions/writes: identity, evidence hash and context, permission isolation, duplicates and conflict order, raw candidate manifest changes, latest-vintage selection, lifecycle withdrawals/supersession and overlapping approvals, traceable alternatives, current/historical AAPL negative states and Gross Margin positive/conflict states. Read-only narrowly scoped AAPL baseline comparison if necessary; no all-company audit. No external calls. Run git diff --check.

## Completion criteria
Both permission paths testable; all registries empty; no current output changes; no production writes; focused tests pass; evidence/vintage limitations and follow-up review needs documented.

## Final outcome
Implemented the inactive foundation, additive optional authorization provenance, pure synthetic tests and contract documentation. All production selection/denominator/withdrawal registries remain empty; the production loader supplies no evidence. No real authorization was activated.

Focused command from backend: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_revenue_scope_authorizations.py -q` with `PYTHONDONTWRITEBYTECODE=1`: **76 passed**. Exact read-only AAPL baseline comparisons passed after final service edits. Gross Margin remains 0.5005620698794520047159033788; current Net Margin, FY2018 half-year Revenue and FY2019 half-year Revenue YoY remain unavailable. No full audit or live-server/restart validation occurred. Final `git diff --check` passed.

Follow-up Astra review before any activation: independent document/context evidence acquisition and trust boundary, complete raw manifest coverage (including legacy-ingestion limitations), conservative rejection of differing-value vintages, explicit approval lineage/withdrawal behavior, and any separately proposed real financial authorization. This task does not provide restatement reconciliation or historical primary-statement evidence.

Git: main / b1bb70a, task files uncommitted. Existing frontend/next-env.d.ts and the two runtime reports preserved; no commit or push. Suggested commit: `feat: add inactive bounded revenue scope authorization foundation`.
