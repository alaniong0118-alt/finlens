# Disabled AAPL Net Margin activation preparation

Status: completed (disabled implementation only; no activation approval)
Roadmap phase: scoped activation implementation for independent review; no activation

## Objective
Prepare an internal operator-only activation entry point reusing the exact reviewed
dormant proposal. Keep its code gate false and every production registry empty.

## Current architecture and context
Verified main / 1a78b4078455f58e8c8ca15b607d8d6866c9d1be. Preserve the existing
frontend/next-env.d.ts modification and two untracked backend runtime reports.
The proposal binds the exact AAPL quarter pair, original/receipt fingerprints,
complete raw manifest and 1/0/1 company versions including legacy publication 0.
Follow [AGENTS.md](../../../AGENTS.md), [ExecPlan rules](../../../.agent/PLANS.md),
[proposal](../../aapl-net-margin-proposal.md) and [adapter](../../sec-evidence-adapter.md).

## Constraints and non-goals
No real registration, persistent configuration, SEC/model requests, writes to DB,
ingestion, migrations, refreshes, service restart, original evidence modification,
financial semantics change, commit or push. No HTTP/CLI/environment activation
switch or automatic startup/request wiring. No other permissions or scope expansion.

## Implementation stages
1. Inspect contracts and define a source-controlled false gate plus explicit trusted
   operator acknowledgement of the exact approval reference.
2. Add minimal internal entry point: fresh repeatable-read/read-only session,
   existing manifest/policy verifier, lifecycle/conflict checks, then publish policy
   before permission. Do not call its enabled path outside isolated tests.
3. Add focused reversible test wiring using the original artifact read-only and
   detached existing proposal fixtures. Run adapter/authorization/proposal regressions.
4. Check inactive read-only parity, preservation and self-review; complete report.
Rollback removes the scoped preparation files and documentation changes only.

## Decisions
- Code gate remains false; changing it requires separately approved/reviewed source.
  Even an enabled gate requires an explicit operator call and exact reference.
- Reuse the current evaluator and original evidence adapter. No new approval type,
  policy builder, financial constants, repinning or alternate evidence interface.
- Registration is process-local and initial-single-pair-only. Policy publishes first;
  the permission tuple is the final visibility step. A private lock serializes this
  entry point; it does not claim to lock files or external registry mutations.
- Fresh sessions are created internally, preventing caller-supplied stale sessions
  or incomplete fact subsets. Each subsequent financial request still revalidates
  evidence under the existing adapter; the preflight does not cache proofs.

## Discovered issues
No blocking validation failure. The first full-suite command exceeded its output
wait window; no completed result was claimed. After adding three meaningful
post-preflight invalidation cases, reran with a longer wait and captured exit 0.
Separate Astra approval of actual activation and operator store configuration remain
absent by design. The operator assertion is not authentication; independent SEC
provenance and immutable store operation remain deployment/review responsibilities.

## Progress
- [x] Instructions, baseline and reviewed contracts inspected.
- [x] Disabled implementation and focused tests prepared.
- [x] Focused regression and inactive parity completed.
- [x] Self-review and final preservation checks completed.

## Test and validation strategy
Assert actual empty registries and false gate before test patches. Only an isolated
monkeypatch context enables wiring, supplies a detached read-only session factory
and restores all registries/configuration. Never register against live PostgreSQL.
Use original files read-only; fault injection changes in-memory facts/metadata or
mocked reads. Check no partial registration and no dormant I/O, full validation,
identity/approval/version boundaries, unsafe configuration and withdrawal/supersession.
Run focused suites with cache/bytecode output disabled and git diff --check.

## Completion criteria
Source gate false, no normal importer/caller, every production registry empty,
valid isolated registration only after full fresh verification, rejection leaves
registries unchanged, original financial responses unchanged, no unrelated changes.

## Final outcome
Added the disabled internal entry point, focused tests and operator/review contract;
updated the existing proposal documentation to link to the disabled preparation.
The approved proposal constants, policy/fingerprints, evaluator, adapter, calculation
service and metric registry remain unchanged. No production application importer or
caller of the activation module exists. No environment activation toggle or persistent
state was added. Source gate remains literally False, all four production registries
and global Revenue equivalences empty, production store configuration unset.

Executed from backend with only command/test-process environment variables:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:FINLENS_REVIEW_SEC_ORIGINAL_STORE='D:\FinLens-OperatorReports\sec-original-evidence'
.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_aapl_net_margin_activation.py tests/test_aapl_net_margin_proposal.py tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py -q --tb=short
```

Final result: **301 passed**, including **50 new activation cases**, no skips,
exit 0. Initial activation suite passed 47/47 before three extra per-request
invalidation cases. Successful enabled wiring was exercised ONLY with an isolated,
reversible fake session factory; the real original/receipt files were read without
copying/modification. No enabled call used the PostgreSQL database. Fixtures checked
actual inactivity before patches and restored all registries, gate and environment
after every test. Negative cases prove no partial registration for unsafe roots,
changed bytes/receipts, wrong approval/reference/metric/source/company/period,
changed raw manifests/versions including legacy publication 0, unsafe transactions,
conflicts, withdrawals/supersessions and late boundary changes. Per-request tests
prove the preflight retains no usable proof cache after evidence/version/withdrawal
changes. Existing suites also cover historical Revenue gaps and Gross Margin guards.

A separate PowerShell stdin `.venv/Scripts/python.exe -` verification imported the
disabled module, checked the false gate and empty registries, and used application
database URL with connect_timeout=3 and `freshness_service.read_session` only.
PostgreSQL reported repeatable read / read-only. `load_financial_metrics` executed
exactly two SELECTs. Loaded baseline FinancialMetrics in memory from
`git show 7918c24c9457ab4fe39759a06cb749087c9924a9:backend/app/financial_metrics_service.py`;
five summaries and revenue/revenue_growth_yoy/net_margin/gross_margin histories for
quarter/half_year/nine_months/annual/instant matched **25/25** by model_dump(mode='json').
No call to the enabled activation entry point occurred in this live verification.

Current AAPL snapshot matches the unchanged reviewed proposal (versions 1/0/1;
snapshot SHA-256 01b530f47b1d7b15bd7306af097d3bf972eeef17dabdc72467e195451a540dd9).
The raw manifest remains the two exact proposal identities; target publication
version remains 0. Gross Margin remains 0.5005620698794520047159033788, current
Net Margin unavailable, and FY2018 half-year Revenue / FY2019 half-year Revenue YoY
remain unavailable. This is in-process stored-data parity, not restarted-service or
browser acceptance.

Self-review confirmed source-only gate/operator acknowledgement, fresh internal
sessions, reuse of unchanged exact proposal and full adapter verification, lifecycle
rechecks, no stored proofs, initial-empty registry restriction and policy-before-
permission publication. Filesystem/database atomicity and direct mutation of trusted
constants are not claimed; quiescent controlled operator installation and append-only
evidence remain required. Whitespace checks and final git status verified separately.
No database/config/evidence modification, acquisition, model call, restart, commit
or push occurred. Existing frontend modification and both runtime reports preserved.
Final Git: main / 1a78b40, four scoped new files and one scoped documentation edit.

Remaining gates and specific Astra issues are in
[activation contract](../../aapl-net-margin-activation.md). Actual activation needs
separate user/Astra approval, explicit source-gate change, trusted operator invocation,
store configuration and fresh exact pin validation. Suggested commit:
`Prepare disabled AAPL Net Margin activation boundary`.
