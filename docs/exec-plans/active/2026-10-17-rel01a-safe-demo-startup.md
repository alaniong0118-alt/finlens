# REL-01A: safe prepared-demo startup and operational guards

Status: active; implementation and offline verification complete; coordinator and independent Astra review pending.
Roadmap phase: REL-01 local university demonstration preparation only.

## Objective

Start an existing prepared local development demo with bounded readiness and
process ownership checks. Reject full-catalog CLI operations before operational
work; keep separately authorized explicit-issuer workflows intact.

## Current architecture and context

Baseline: main, `5e296fc3e43d774368de31f59094b25e0746ece5`, empty index.
Only pre-existing changes are frontend/next-env.d.ts and two untracked reports.
Protected SHA256 values verified before implementation:

| File | SHA256 |
| --- | --- |
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

Health/capability endpoints and the frontend title provide existing application
markers. They are not authenticated instance identities. Refusing occupied app
ports, binding listeners to newly launched process ancestry, and setting the
frontend's backend URL only in its child process avoids accepting an unrelated
pre-existing listener without introducing a production identity protocol.

## Constraints and non-goals

Code/documentation and isolated offline tests only. No live services, DB access,
provider requests, installs, model loads, persistent environment changes or Git
mutations. Preserve financial, evidence, publication, UI and model implementations.
DEP-01A3 stays BLOCKED. No cryptographic attestation or deployment authorization.

## Implementation stages

1. Verify baseline; inspect existing scripts and safe application markers.
2. Improve prepared-data startup; refuse automatic process-name-based shutdown.
3. Reject CLI all/bootstrap/unselected admissions; preserve explicit selections.
4. Add runbook and correct directly relevant operational examples.
5. Run mocked PowerShell and guarded CLI tests, syntax and preservation checks.

## Decisions

- 2026-10-17: Reject all pre-existing application listeners, including plausible
  FinLens ones. Stop them from their original terminals before using the launcher.
- Use interactive service terminals as operator shutdown controls. No automatic
  process termination or database startup/stop; require PostgreSQL already ready.
  On failure leave started terminals visible and identify the stage; operator
  stops those terminals with Ctrl+C. No PID receipt or process-name kill heuristic.
- Block all refresh/bootstrap CLI selections globally rather than read the live
  catalog to rediscover the known 36-company boundary. Keep the 35-ticker limit.
- No rerun of completed financial audits, QA-01 or browser acceptance.

## Discovered issues

Existing Stop-FinLens.ps1 guesses ownership from a repository-name substring and
next/npm command names. Replace automated termination with actionable refusal.
The existing launcher starts Compose and does not check actual API/proxy health.

## Progress

- [x] Baseline and protected hashes verified.
- [x] Scripts and early CLI admission guards implemented.
- [x] Runbook and directly relevant documentation corrected.
- [x] Focused offline tests, syntax, self-review and preservation checks complete.
- [ ] Coordinator and independent Astra review.

## Test and validation strategy

PowerShell tests dot-source functions and replace external process/HTTP/port/Docker
interfaces. No real launcher run. Python uses the existing guarded offline runner,
fake sessions/services and explicit no-operational-import sentinels for denials.
Run only REL-01A and adjacent explicit-selection/release-admission tests. Validate
PowerShell parsing under Windows PowerShell 5.1 and current PowerShell. Do not
compile Python to disk. Recheck status/index/diff and protected hashes.

## Checks actually run

Repository-root commands (each runs only mocks, including browser/process calls):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File backend\tests\test_rel01a_startup.ps1
pwsh.exe -NoProfile -File backend\tests\test_rel01a_startup.ps1
```

Final result: **26 passed, 0 failed, 0 skipped on each runtime**. Covers ready and
transient states, custom ports, profile/JSON sanitization, foreign/recycled/wildcard
listeners, failed backend/DB/proxy/HTML identity, no premature browser, child-only
configuration, safe stop refusal and refresh wrapper selection/opt-ins. The first
fixture run was 15 passed/7 failed because Reset-Fixture cleared the foreach mode
variable; correcting that fixture collision exposed all intended negative cases.
An intermediate 24-case run passed before adding custom-port/profile-command checks.

Backend command, working directory backend:

```powershell
.\.venv\Scripts\python.exe -B tests/run_dep01a2_increment2_offline.py `
  tests/test_rel01a_cli.py `
  tests/test_refresh_scope.py::test_cli_passes_optin_to_real_coordinator `
  tests/test_refresh_scope.py::test_cli_cannot_silently_ignore_guard `
  tests/test_release_profile.py::test_development_launcher_validates_profile_before_infrastructure `
  tests/test_release_profile.py::test_operator_flags_cannot_bypass `
  tests/test_financial_sync.py::test_existing_other_report_cannot_be_overwritten `
  tests/test_financial_sync.py::test_cli_atomic_report_options_and_exit `
  tests/test_financial_sync.py::test_dry_run_and_subset `
  tests/test_company_catalog.py::test_36_company_all_selection_rejects_before_refresh_or_bootstrap `
  tests/test_catalog_indexing.py::test_skip_complete_without_network_or_encoder `
  tests/test_catalog_indexing.py::test_resume_missing_vectors_without_download
```

Result: **35 passed, 0 failed, 0 skipped**, 11 existing Starlette/httpx and
SQLAlchemy datetime deprecation warnings. Earlier narrower selection: 25 passed.
Physical sockets/psycopg are blocked by the existing runner; dotenv is disabled,
DB URL is dummy, sessions are fake or disposable in-memory SQLite. Provider and
encoder work in adjacent tests uses injected fixtures. Test reports use pytest
temporary directories, not historical reports. No broad regression or QA-01 run.

PowerShell Parser.ParseFile succeeded on the three operational scripts and new
test. Python ast.parse succeeded on all seven changed/new Python files, without
imports or bytecode output. Final PowerShell execution also parses the final sources.
git diff --check passed. Only the intended scope plus the three pre-existing
protected paths is present; protected hashes match the baseline and index is empty.

## Exact file inventory and rationale

- Start-FinLens.ps1: prepared prerequisites, profile/ownership checks, bounded
  direct/proxy readiness, child-only pairing/offline flags and manual shutdown.
- Stop-FinLens.ps1: remove unsafe substring-based termination; fail with manual steps.
- Refresh-FinLens.ps1: explicit selection and preserved dual opt-in; mockable dispatch.
- backend/scripts/index_catalog.py and backend/scripts/sync_financial_facts.py:
  reject missing/blank issuer selections before operational imports/work.
- backend/scripts/refresh_data.py: reject all/bootstrap before DB/schema access.
- backend/tests/test_rel01a_startup.ps1 (new): mocked PowerShell boundary tests.
- backend/tests/test_rel01a_cli.py (new): denial, release restriction, limits and
  explicit-selection tests with fake services/sessions.
- backend/tests/test_company_catalog.py: strengthen the existing all-selection
  regression to require denial before any DB/schema/request work; no identity audit.
- backend/tests/test_financial_sync.py: supply explicit issuer selection so existing
  report-protection assertions still exercise their intended boundary.
- backend/tests/test_release_profile.py: update the launcher ordering assertion for
  service startup after profile admission, with no Docker invocation.
- README.md, docs/data-sources.md, docs/data-freshness.md: separate provisioning,
  remove unsafe executable examples and require explicit issuer selection.
- docs/ai-cov01-amd-catalog.md: append dated superseding CLI behavior only; preserve
  historical identity/financial evidence and make no new AMD admission claim.
- docs/local-demo.md (new): prerequisites, startup/readiness, failure/shutdown,
  forbidden commands, AMD and encoder/deployment limitations.
- This active ExecPlan (new): scope, decisions, actual verification and handoff.

## Completion criteria and final outcome

Implementation/offline gates passed. The 35-ticker limit, backend/app financial,
evidence, publication/model logic and all frontend production sources are unchanged.
No Git mutation or live service/database/provider/environment operation occurred;
only test-process environment/mocks and disposable test data were used. No persistent
environment file was changed. Protected bytes and historical reports are preserved.

Known boundaries: PostgreSQL must already run; occupied app ports are never reused.
Started service terminals remain open on failure, for operator Ctrl+C shutdown.
Existing health/title markers plus process lineage are ordinary local identity
checks, not authenticated source/build attestation or adversarial race containment.
Polling uses a stage budget and bounded individual HTTP calls, not hard process
cancellation. Cached encoder/search/real DB/actual browser readiness remains untested.
DEP-01A3 remains BLOCKED; no deployment or later milestone is approved.

Leave active for coordinator and independent Astra review. No staging/commit/push.
Suggested later commit: `feat(rel01a): guard prepared demo startup and explicit issuer operations`.
