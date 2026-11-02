# Backend history to frontend consumer contract

Status: active — original Windows slice reviewed PASS; revision 2 focused validation passed, integration pending
Roadmap phase: requirement16c integration verification

## Objective

Close the maintained-test gap between real restricted-profile history HTTP
serialization and the balance-date/cash-flow-window consumers. Verify compatible
data, honest missing states, precision, lineage, publication pins and cleanup.

## Current architecture and context

Baseline is committed cash-flow change `cd86bf8ec44ada9f3beda00b4e5a91e682715d69`,
parent balance baseline `1e98a3a31713e4f2ecd84ecbcab951bd411f7980`.
Revision 2 is isolated at `D:\Projects\finlens-history-contract-review-r2-20261102`.
It uses the original fixed baseline archive and copies of the three reviewed
candidate files. The original package and evidence at
`D:\Projects\finlens-history-contract-20261102-1915-r16c` remain unchanged.
No live source, index or refs are written. Root AGENTS.md, .agent/PLANS.md and
engineering standards were read; no `.agents/skills` directory or nested
AGENTS.md/SKILL.md exists in the committed tree or inspected project ancestors.
The historical restricted-profile 403 gap is documented in
[the quarterly plan](2026-11-01-quarter-window-comparison.md); it is motivation,
not an assertion that this history route is broken.

## Constraints and non-goals

Two maintained test files plus this proportional plan only. No production,
dependency, validator, policy, schema or financial-formula changes. No DB,
provider, model, service, browser, Docker, download, credential or security-setting
access. Use existing guarded Python runner and frontend component loader.
Scratch junctions reference installed dependencies read-only during test runs.
Protect live next-env, historical reports and unrelated docs. No commit or push.
Revision 2 invokes no Git commands and performs no live-checkout/root writes.
The bridge explicitly requires Windows with installed dependencies at
`backend/.venv/Lib/site-packages`: the unchanged guarded runner hardcodes that
layout under `-I -S`. POSIX is unsupported and fails clearly before child startup;
no portable acceptance, environment provisioning or silent skip is claimed.

## Implementation stages

1. Capture fixed committed baseline; inspect governing instructions and test seams.
2. Drive the real FastAPI app, loader function's SQLAlchemy query construction
   and canonical metric engine with fake session responses under
   `ServerProfile("sec_readonly", True)`. Assert read-only setup SQL and cleanup
   orchestration; no physical SQL execution, ORM hydration or transactions occur.
3. Export current HTTP response text/headers from that same maintained backend
   test and replay through real getMetricHistory, versionedController, validators,
   source consistency checks and exact-date/window cell helpers.
4. Run targeted offline regressions, review tests-only diff, record hashes/results
   and deliver an unapplied patch for independent review.

## Decisions

- 2026-11-02: Nine metric/period slots: three instant balance measures plus
  OCF/CapEx/FCF for half-year and nine-month durations. Two dates per series.
  Full data at publications 0 and 7; sparse data at 7 and empty data at 0.
- All inputs are synthetic source facts. No handcrafted response snapshots or
  serializer replicas; capture actual response text and all response headers.
  Large Decimal values exceed JS safe integer precision but fit the deterministic
  backend Decimal calculation context. FCF is produced only by the real engine.
- The runner forbids the original-filing authorization adapter. Stub only its
  empty-evidence dependency and assert all relevant production registries empty;
  schema readiness is also stubbed true. Both dependencies are outside coverage.
  The loader's SQLAlchemy query construction, engine, response models, route and
  admission remain real; source rows are supplied as synthetic objects rather
  than hydrated by an ORM or physical database.
- Header removal is a labelled transport fault applied to captured success
  responses; backend stale pins and cleanup failures are actual HTTP outcomes.
- Node starts only the guarded in-process TestClient child, with a minimal
  environment allowlist, a 60-second timeout and no server socket/network.
- Revision 2 wraps owned capture artifacts in `try/finally`, cleaning them after
  success, startup exceptions/nonzero results, JSON parse errors and setup
  assertion failures. Caller-specified evidence paths retain ownership and are
  preserved even on failure. Five maintained controls cover startup, parsing,
  setup validation, caller ownership and unsupported POSIX configuration.

## Discovered issues

Default Windows sandbox cannot initialize this writable-root configuration.
Supported per-command approval works; no settings changed. `rg` is unavailable,
so bounded PowerShell searches were used. No product mismatch emerged in this
bounded matrix.

An overbroad existing backend regression selection initially returned 397 passed
and 27 failed (including the 44 new tests). Repeating the same selection without
the new module returned 353 passed and the identical 27 failures. Twenty encoder
cases conflict with this runner's intentionally forbidden `_get_model`; six old
all-route cases omit required selectors/pins and receive 422 instead of their
expected DB-busy 503; one existing financial-only coverage wrapper calls a
parameterized helper without its required `pin`. These are baseline validation
limitations, not history product findings. Full unchanged-test failure evidence
is retained at scratch `backend/evidence/baseline-existing-regression.log`.
No existing tests, runner guards or product behavior were altered to hide them.

The first delivery check applied cleanly but the existing global
`core.autocrlf=true` converted all three added files to CRLF. Confirmed all three
differences were line endings only. Final byte-identity verification uses
`git -c core.autocrlf=false apply --check --whitespace=error-all`, then the same
one-command formatting setting for scratch application. No persistent Git or
security setting changed. The first scratch package is retained; use only
the original `delivery-final/delivery-manifest.json` for the reviewed first
version. Revision 2 packages a new addition-only patch and verifies reconstruction
and whitespace with Python's standard library, without invoking Git.

Independent review passed the original documented Windows slice and confirmed
the exact 27 baseline failures. Review fault injections verified FCF arithmetic,
Decimal serialization and required-header assertions. The requested revision
only fixes harness cleanup, makes Windows support explicit and corrects coverage
language. Those original fault injections and broad baseline failures need not
be rerun for this revision.

## Progress

- [x] 2026-11-02: Fixed archive baseline and inspected conventions.
- [x] 2026-11-02: Added backend capture/contract and frontend bridge tests.
- [x] 2026-11-02: New backend matrix 44/44 and bridge 7/7 passed.
- [x] 2026-11-02: Final focused backend regression 149/149 and frontend 207/207 passed.
- [x] Original tests-only scope reviewed PASS for documented Windows coverage.
- [x] Revision 2 cleanup and platform prerequisite controls implemented.
- [x] Revision 2: backend 44/44, standalone bridge 12/12 and frontend regression 212/212 passed.
- [x] Revision 2 patch/hash evidence prepared; integrator review/application pending.

## Test and validation strategy

Original actual commands, from the first scratch `backend/` (PowerShell; Python 3.14.7):

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_history_client_contract.py
```

44 passed, existing Starlette/httpx deprecation warning. The export case always
exercises its real HTTP matrix, and writes captured output only when requested.
The final focused command used the same runner with these exact node IDs:

```text
tests/test_financial_history_client_contract.py
tests/test_financial_coverage_policy.py
tests/test_quarter_window_policy.py
tests/test_release_profile.py::test_actual_route_inventory_matches_explicit_policy
tests/test_release_profile.py::test_every_reviewed_route_identity_is_admitted
tests/test_financial_only_policy.py::test_explicit_subset_and_truthful_uncached_capabilities
tests/test_financial_only_policy.py::test_all_financial_pairs_keep_exact_route_identity_and_reader_denial
tests/test_financial_only_policy.py::test_restricted_real_quarter_route_keeps_pins_and_readonly_cleanup
tests/test_financial_only_policy.py::test_restricted_quarter_stale_pin_closes_without_computation
tests/test_financial_only_policy.py::test_restricted_quarter_still_requires_a_pin_before_session
tests/test_http_database_runtime.py::test_failure_stages_snapshot_cleanup_and_later_request_recovery
tests/test_http_database_runtime.py::test_zero_positive_missing_metadata_and_409_headers
tests/test_http_database_runtime.py::test_cleanup_failure_preserves_primary_programming_error_and_discards_connection
tests/test_http_database_runtime.py::test_actual_orm_close_rollback_failure_discards_detached_connection
tests/test_http_database_runtime.py::test_actual_orm_cleanup_failure_preserves_primary_and_never_reuses_bad_connection
tests/test_http_database_runtime.py::test_actual_pool_checkout_timeout_has_no_retry_and_later_request_recovers
```

149 passed, no skips/deselections. Log: scratch `backend/evidence/final-backend-targeted.log`.
The preexisting-only failure reproduction selected the financial-only, coverage,
quarter and HTTP-runtime modules plus the same two release-profile node IDs,
with `--tb=short`: 353 passed / 27 failed. Initial working-directory interpreter
typo failed before launching Python, then was corrected.

From scratch `frontend/` (Node 24.21.0):

```powershell
node --test tests/financial-history-backend-contract.test.mjs
node --test tests/financial-history-backend-contract.test.mjs tests/balance-date-comparison-matched.test.mjs tests/cash-flow-window-comparison.test.mjs tests/finlens-api.test.mjs
```

7/7 and 207/207 passed, no skips. Existing Node typeless-package warning in the
combined run. The final run supplied scratch
`backend/evidence/history-responses.json` via `FINLENS_HISTORY_CONTRACT_OUTPUT` to
retain 43 actual responses and actual financial-only capabilities; the default
test invocation at that checkpoint removed its owned temporary artifact only
after success; revision 2 corrects cleanup on failed setup as described above.
Log: scratch `backend/evidence/final-frontend-targeted.log`.

No live DB/data coverage, reverse proxy, browser, provider/model evaluation or
live-service HTTP claim is implied. No production changes require a build/lint
run; existing mounted components run in the frontend regression selection.
The fake session verifies loader query construction and read-session control
flow, not physical ORM hydration, transaction isolation or database cleanup.
Schema readiness and original-filing authorization evidence remain stubbed and
outside this contract's acceptance coverage.

Revision 2 actual commands, from its `backend/` and `frontend/` respectively:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_history_client_contract.py
node --test tests/financial-history-backend-contract.test.mjs
node --test tests/financial-history-backend-contract.test.mjs tests/balance-date-comparison-matched.test.mjs tests/cash-flow-window-comparison.test.mjs tests/finlens-api.test.mjs
```

Results: 44/44 backend, 12/12 standalone bridge, 212/212 combined frontend; zero
skips or failures. The combined frontend run used the default owned temporary
capture path; the standalone run supplied
`FINLENS_HISTORY_CONTRACT_OUTPUT=D:\Projects\finlens-history-contract-review-r2-20261102\backend\evidence\revision2-history-responses.json`
to retain fresh responses on a caller-owned path. Logs are
`backend/evidence/revision2-new-backend.log`, `revision2-bridge.log` and
`revision2-frontend-targeted.log`. Five new harness controls include both thrown
startup errors and failed child results, partial JSON output, setup assertion
failure, caller ownership and the POSIX prerequisite error before startup.
Existing Starlette/httpx and Node typeless-package warnings remain.

Broad baseline regression and reviewer-verified product fault injections were
not repeated. Revised scope and hashes are in `delivery-r2/delivery-manifest.json`.
All original patch/candidate/log hashes and all 499 archived baseline files are
rechecked. The addition-only unified patch is generated with stdlib `difflib`;
header/hunk reconstruction, exact bytes and whitespace are checked without Git.
The explicit no-Git restriction leaves revised Git application checking to the
integrator; original Git application evidence remains historical and preserved.

## Completion criteria

All nine slots traverse real restricted HTTP serialization and client validation;
precision, dates, source/operand identity, available/empty/sparse results,
publications 0/7, stale rejection and fake read-session cleanup orchestration pass. Optional balance
and required cash-flow headers retain their distinct documented behavior.
No production changes. Reviewable patch with fixed baseline and exact hashes.

## Final outcome

The original bounded matrix passed without production changes and received an
independent Windows-scope PASS. Revision 2 passes the focused Windows checks,
including cleanup faults and explicit unsupported-platform rejection.
Each delivery is a preserved three-file patch against the same fixed baseline,
with exact SHA-256 hashes and scope in its manifest. Application remains pending;
nothing is committed or pushed. Suggested commit:
`test(research): join history HTTP responses to frontend contracts`.
