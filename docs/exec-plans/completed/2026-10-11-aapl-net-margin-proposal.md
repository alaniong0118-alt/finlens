# Dormant AAPL Net Margin authorization proposal

Status: completed (review preparation only; activation remains unapproved)
Roadmap phase: scoped financial evidence review preparation; no activation

## Objective
Prepare immutable exact-pair denominator and evidence-policy records for independent
Astra High review. Production registries and financial outputs must remain unchanged.

## Current architecture and context
Baseline main / cca903b11d9242576ce41d32ca1b2859a0ab3e9a. Preserve the existing
frontend/next-env.d.ts modification and two untracked backend runtime reports.
The committed adapter validates original Inline XBRL, receipt provenance, publication
snapshot and complete raw candidates; its four production registries are empty.
Previous bounded read-only parity passed 25/25 against 7918c24. Follow
[AGENTS.md](../../../AGENTS.md) and [adapter contract](../../sec-evidence-adapter.md).

## Constraints
No real activation, configuration changes, database writes, SEC/model requests,
service restarts, evidence modifications, commit or push. External original-store
paths remain operator-controlled. Only tests may install process-local isolated
proposal records. No change to formulas, mappings, scope rules or Gross Margin.

## Non-goals
Historical Revenue authorization, other companies/periods/metrics, global Revenue
equivalences, activation endpoint, environment toggle or acquisition.

## Implementation stages
1. Reconcile contracts, exact local evidence and current read-only AAPL snapshot.
2. Add a dormant immutable proposal module and focused isolated tests/documentation.
3. Verify full evidence policy offline and against read-only publication/candidate
   data; run relevant regressions, inactive parity and preservation checks.
4. Self-review, record results and independent-review questions; stop before activation.
Rollback removes only this proposal's new files; no persistent data is changed.

## Decisions
- 2026-10-11: A side-effect-free proposal module is not imported by production
  loaders or registries. Activation requires a separate reviewed code patch;
  no runtime flag, HTTP switch or registration helper is added.
- Approval identifiers describe proposed version 1 records, not an already granted
  production permission. Original bases remain customer_contract / NetIncomeLoss.

## Discovered issues
- The initial temporary pin construction used the parser's exponential Decimal
  representation; the literal proposal uses fixed Decimal amounts. The adapter's
  policy/approval JSON binds that representation even though numerical identity is
  equal. Regenerated fingerprints from the final literal policy and independently
  parsed evidence; full validation then passed. No hash or financial contract changed.
- Initial test assertions incorrectly assumed loader proof order and omitted a
  detached fact's created_at. Corrected fixture/assertions; no production changes.
- Production original-store configuration remains unset intentionally. Capture
  receipt/path and publication filed-date lineage require independent acceptance;
  local completeness does not prove all SEC amendments have been acquired.

## Progress
- [x] Instructions, baseline and contracts inspected.
- [x] Exact proposal pins and records prepared.
- [x] Focused tests and read-only validation completed.
- [x] Self-review and final preservation checks completed.

## Test and validation strategy
Use real original bytes read-only with exact receipt/artifact pins; no copying or
mutation. Offline tests install proposal records only under pytest monkeypatch and
restore all registries/environment. Negative cases alter in-memory inputs or mocked
reads, never original evidence. Read-only PostgreSQL validation uses repeatable-read
snapshots and compares five summaries plus twenty histories with baseline 7918c24.
Run adapter/authorization regressions and git diff --check; record actual results.

## Completion criteria
Full policy verification succeeds for the exact pair and fails for adversarial
inputs. Import and normal application paths remain inactive, all registries and
Revenue equivalences empty, no unrelated changes or persistent side effects.

## Final outcome
Added one side-effect-free proposal module, its focused tests and an exact
[independent-review dossier](../../aapl-net-margin-proposal.md). No existing
production implementation, financial semantics or runtime configuration changed.
All four production registries and global Revenue equivalences remain empty.

Executed from backend (environment variables exist only in the command/test process):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:FINLENS_REVIEW_SEC_ORIGINAL_STORE='D:\FinLens-OperatorReports\sec-original-evidence'
.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_aapl_net_margin_proposal.py tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py -q --tb=short
```

Result: **251 passed**, including all **44 new proposal cases**, no skips. Cases
cover original policy/full loader, company/metric/period/accession/unit/source/value
boundaries, changed evidence, missing files/config/permission/policy, complete raw
manifest, versions/vintages, withdrawal/supersession, Gross Margin isolation,
historical gaps, immutability and inactive imports. Tests use detached facts and
publication fixtures, never database writes or persistent environment changes.
Original files/receipts are read only; failures alter mocked reads/in-memory inputs.

A PowerShell stdin invocation of `.venv/Scripts/python.exe -` used the application
database URL with connect_timeout=3 and `freshness_service.read_session`:
PostgreSQL reported repeatable read / read-only. Loaded AAPL via
`load_financial_metrics`; collected exactly two SELECTs and 2,343 existing facts.
`authorization_sources(('revenue','net_income'),'quarter',date(2026,6,27))` returned
exactly the two proposal identities; corresponding fact IDs were 1853/1976.
Read CompanyRefreshState and all two issuer FilingPublication records in the same
snapshot. Versions were 1/0/1 and `adapter.snapshot_digest` matched the literal
proposal snapshot `01b530f47b1d7b15bd7306af097d3bf972eeef17dabdc72467e195451a540dd9`.

Called `adapter._verify_policy(PROPOSED_EVIDENCE_POLICY,
PROPOSED_DENOMINATOR_AUTHORIZATION, raw, operator_root, snapshot, publications)`
without installing any registry records. Both real proof fingerprints matched the
literal bindings. `authorize_denominator` still rejected; supplying the proofs to
FinancialMetrics alone still left Net Margin unavailable. No live registry patch.

Loaded baseline FinancialMetrics in memory from
`git show 7918c24c9457ab4fe39759a06cb749087c9924a9:backend/app/financial_metrics_service.py`.
Compared model_dump(mode='json') for five summaries and revenue/revenue_growth_yoy/
net_margin/gross_margin histories across quarter/half_year/nine_months/annual/instant.
All **25/25** matched exactly. Gross Margin remained
0.5005620698794520047159033788; current Net Margin and FY2018 half-year Revenue /
FY2019 half-year Revenue YoY remained unavailable. This is in-process stored-data
verification, not restarted-service or browser acceptance.

Self-review: proposal has no registration/configuration/I/O functions and no
production importer. Existing adapter/evaluator/service/registry implementations
remain unchanged. New-file whitespace and git diff --check passed. Final Git is
main / cca903b, with the four scoped new files and preserved unrelated changes.
No commit/push, SEC/model request, writes, restart or evidence modification occurred.
Future activation requires separate user approval, independent Astra High review
of exact pins/provenance/scope and operator store configuration, with fresh snapshot
validation before installation. Suggested commit: prepare dormant AAPL Net Margin proposal.
