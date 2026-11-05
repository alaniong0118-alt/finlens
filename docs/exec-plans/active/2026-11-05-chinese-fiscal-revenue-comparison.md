# Closed Chinese fiscal revenue comparison and empty-name safety

Status: active; combined scratch validation complete, binding review pending.
Roadmap phase: bounded deterministic research-question recognition.

## Objective

Support one complete Traditional/Simplified Chinese question comparing revenue in
two explicit fiscal years, with existing typed English calculation/provenance.
Prevent an empty normalized catalog name from crashing English recognition.
Rejected utterances must load zero facts. Preserve all existing alias policy.

## Current architecture and context

Primary main is 4484a272dac3075a1d93d86cc5471eab3a9674c9. Its unchanged service
parent is 0e7671552292049d89d04370e72e8b6a1eef65227ea331f6d097bd9541d490dd.
Root AGENTS.md and .agent/PLANS.md were read. The separate comparison and alias
proposals passed independent review; their original artifacts remain immutable.
This candidate combines exactly those reviewed changes. Service SHA-256 is
23e9c94311ca2e08c754b4206813ce2f8dd6352407826e3e11e2633f349a456a.
The primary uncommitted ten-file sign-in candidate and five protected exceptions
are recorded in preservation-before.json and must remain untouched.

## Constraints and non-goals

Scratch only. No primary edits, sign-in changes, schema/model/formula/dependency
changes, database connections, network, Docker, provider, credentials, commit or
push. No general Chinese/company-name translation or localized answer claim.

## Implementation stages and decisions

1. Verify both reviewed proposals and supplied combined hash before preparation.
2. Copy both focused tests byte-for-byte and update this scoped combined plan.
3. Run each focused suite separately under its existing positive effect guards.
4. Run broader database-free backend regressions with the maintained offline
   runner, a sanitized test environment and explicit DB/network/write guards.
5. Inspect exact runtime changes, package four-file patch, verify preservation,
   and stop for independent binding review.

Both ASCII 1900-2099 years require explicit 財年/财年 labels. The whole utterance
uses optional 請/请, 比較/比较, optional labelled ticker, first fiscal year,
與/与/和, second fiscal year, optional 的, one existing revenue alias and one
optional question mark. Only ASCII/ideographic spaces are admitted. Unknown
clauses, negation, calendar ambiguity, growth wording, adjustments and conversion
reject. Distinct years sort exactly as English; nonadjacent intervals retain its
existing cumulative-period category without inferring YoY/CAGR.

The alias fix only guards name.split()[0] when normalization is empty. It retains
empty-alias filtering and multi-character ticker policy. It does not authorize
new aliases or broader Unicode semantics. Shared calculation and fact loading
remain unchanged.

## Discovered issues

The separate parent alias crash is resolved by the reviewed one-line fix. All
other existing aliases remain unchanged. No other scope expansion is planned.
The old comparison review helper intentionally expects the original parent's
crash; it is not reused as a combined acceptance oracle or modified in place.
The first broader-run attempt hit pytest's default log-handler file open and was
stopped by the write guard before tests ran. Disable the logging plugin rather
than relax that guard; final broader runs have zero guarded-effect attempts.

## Progress

- [x] Verify reviewed inputs, combined hash and protected source state.
- [x] Materialize exact combined service and both unchanged focused suites.
- [x] Run focused and broader database-free regressions.
- [x] Package and verify four-file patch and exact preservation/bindings.
- [ ] Independent binding review; no Git delivery or activation.

## Test and validation strategy

Use the existing interpreter/dependencies. Focused tests retain real operation,
answer, FinancialMetrics and provenance code with in-memory records/fake loaders;
no engine or database is executed. Positive guards reject network/process/SQLite,
environment-file, write and database-import effects. Broader selected explanation
and session-calculation suites use the maintained run_financial_insights.py plus
connection/audit guards; exclude the external original-report case. Disable pytest
cache/capture and plugin autoload. Shared contract tests are a separate existing
standard-library suite; their owned isolation subprocess does not use a database.
Do not run SQLite-backed API suites or mislabel deselected cases as passed.

## Completion criteria

Supplied combined hash and focused test bytes match; relevant tests pass within
allowed no-database scope; formulas/models/guards/loaders remain unchanged. Exact
patch scope is the service, both focused tests and this plan. Original proposals,
primary/sign-in/protected files and Git metadata remain unchanged. Independent
review is the next gate.

## Final outcome

Exact repository scope: backend/app/research_answer_service.py,
backend/tests/test_chinese_revenue_comparison.py,
backend/tests/test_company_alias_empty_name.py, and this plan. Both test files
remain byte-identical to their independently reviewed originals. The service is
exactly the reviewed comparison postimage with the reviewed first-name guard;
only company_aliases and recognize_operation differ among existing functions.
Financial formulas/models, source selection, typed handoff gates, Unicode safety,
loaders and all other existing functions remain unchanged.

Actual final results:

- Comparison focused suite: 13 passed, no failures/errors/skips.
- Empty-alias focused suite: 9 passed, no failures/errors/skips.
- Existing explanation/session-calculation suites: 82 passed; one explicitly
  excluded external-original-report case deselected. The actual imported service
  path and SHA-256 match this combined candidate. Database/network/process,
  environment-file and write attempt counters are all zero.
- Existing shared contract suite: 49 passed with 609 successful subtests; no
  failures. Its maintained, owned Python isolation subprocess remains in use.
- Joint interaction probes: 12 complete operation/answer/provenance parity pairs
  for Chinese, Japanese, punctuation-only and empty catalog names, plus four
  foreign-ticker denials with zero fact loading. All I/O attempt counters zero.
- Total: 153 tests passed, plus 609 contract subtests and the joint probes.
  Deselected/excluded cases are not counted as passed.
- Exact source/test hashes, LF blob identities, apply-check and preservation
  results are recorded in the scratch handoff; the patch has not been applied.

Reproduce from C:/Users/IITSt/Documents/Codex/2026-11-04/task-3:

```powershell
& .\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\combined-chinese-revenue-20261105\run-focused.py comparison
& .\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\combined-chinese-revenue-20261105\run-focused.py aliases
& .\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\combined-chinese-revenue-20261105\run-broader.py
& .\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\combined-chinese-revenue-20261105\check-combined.py
& .\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B D:\Projects\finlens-foundation\backend\tests\test_research_contracts.py
```

No database/SQLite connection, provider/network, Docker, commit or push occurred.
The primary sign-in candidate, protected files and both reviewed input bundles
remain unchanged. SQLite-backed HTTP/API suites and real sources/provider/browser
acceptance remain unrun. Output stays English; there is no general Chinese or
translated company-name recognition claim. Independent binding review remains
the next step before any integration or Git delivery.
