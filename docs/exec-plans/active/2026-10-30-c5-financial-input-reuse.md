# C5 DB-only financial engine extraction

Status: active; implementation authorized, independent implementation review pending.
Roadmap phase: bounded shared-contract enabling increment; not U3/U4 completion.

## Objective

Extract the existing selection, fiscal reasoning, Decimal calculation and comparison
algorithm into one immediately used internal engine. Preserve the FinancialMetrics
DB facade, original rows, public schemas, authorization decisions, diagnostic
inventories, ordering, resource accounting and lifecycle protection.

## Current architecture and context

Immutable baseline: main / HEAD `6838af1d9164979daebb179144d67cd154da020e`.
Initial index empty. Initial worktree contains only the three protected exceptions:

| Path | SHA256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

All three hashes matched before writes; contents were not printed. Read AGENTS.md,
.agent/PLANS.md and relevant engineering/test guidance. Current roadmap records
existing-data metrics as delivered; external U3/U4 admission remains separate.
The independent design correction requires retaining full raw same-end/kind
authorization inventories even when starts differ, source-specific permission
operations, and Financial Insights' original `.facts`/projected `.base`/`.source`.

## Constraints

Exactly seven authorized paths: this plan; backend/app/financial_metric_engine.py
(new); backend/app/financial_metrics_service.py; backend/tests/test_financial_metrics.py;
backend/tests/test_financial_insights.py; backend/tests/test_pure_helper_isolation.py;
docs/shared-research-contracts.md. Stop on a need to broaden. No schema, registry,
evaluator, evidence adapter, ingestion or Financial Insights production edits.
Keep changes unstaged/uncommitted. Use process-local GIT_OPTIONAL_LOCKS=0.
No private environment reads/hashes, network, operational startup, real database
connections (including SQLite fixture connections), services, native acceptance,
installs, security changes or deployment. Guarded synthetic tests only; temporary
test artifacts must stay outside the repository. No bytecode/pytest cache writes.

## Non-goals

No session adapter/API, new financial semantics, generic authority capability,
verified dimensions/consolidation inferred from missing DB fields, acquisition,
source-policy approval, U3/U4 end-to-end completion, commit/push or self-approval.

## Implementation stages

1. Freeze discriminating serialized DB expectations against immutable 6838af1
   before extracting code; include independently specified values and ordering.
2. Introduce immutable internal observations/results and move the algorithm.
   Retain original-row maps and narrow authorization operations in the facade.
3. Project public DB results with full original metadata and budget accounting.
   Preserve lifecycle checks around conversion, delegated work and projection.
4. Replace only extraction-incompatible financial AST checks; test actual
   delegation, import isolation, mutation discrimination and consumer compatibility.
5. Run safely guarded scoped regressions, inspect diff/scope/hashes, document
   outcomes and stop for coordinator-directed independent review.

Recovery is local correction within these seven files, never resetting protected
work or modifying financial source policies to make parity pass.

## Decisions

- 2026-10-30: DB-only first increment follows the independent corrected design.
- Financial formulas retain Decimal local precision 28 and ambient rounding;
  no new quantization. Preserve exact dates, units, fiscal uncertainty, 53-week
  handling, denominator/basis/EPS rules and no synthetic Q4/YTD substitution.
- Refresh conflict admission, general selection ranking, revenue authorization
  conflict checks and Insights financial-support rejection remain different owners.
- Use existing guarded offline runner with network, dotenv, real PostgreSQL and
  SQLite connects blocked. Do not run legacy DB-backed fixtures merely to claim
  a larger regression count. Record precise unexecuted limits instead.

## Discovered issues

The existing Financial Insights moving-HEAD AST assertion and pure-helper
560dc30 whole-module financial assertion cannot describe intentional extraction.
Only their financial portions will change, with immutable parity and explicit
delegation/isolation replacements; unrelated structural assertions remain.

### Focused static-review corrections — 2026-10-30

Independent static implementation review returned REVISE with two P2 findings:

1. Projection rebuilt provenance from mutable original rows while the engine kept
   construction-time values/periods. Capture the complete scalar source projection
   with each immutable observation and project from that snapshot. Keep originals
   separately for existing authorization and diagnostic operations.
2. Helper conversion replaced submitted provenance by the observation under its
   fact ID. Preserve submitted source metadata through conversion and the original
   source-pair checks, including the pinned gross-margin guard; do not introduce
   a blanket mismatch rejection that changes legitimate helper behavior.

The seven candidate hashes and three protected hashes all matched the independent
review manifest before correction. HEAD/index/path scope also matched. This turn
may run only permitted pure offline correction regressions under normal execution.
No temp-fixture reruns, new basetemp, elevation or reuse of the old one-time approval.
Any permission prompt stops that command and requires a coordinator report.

Planned focused evidence: compare selected, ranked-alternative and excluded-
alternative row mutations after construction against immutable 6838af1; compare
same-ID submitted provenance mutations (accession/concept/period/source value),
valid helper calls, legitimate metadata changes, changed metric values and duplicate
provenance against that baseline. Keep all nine frozen fingerprints unchanged.

## Progress

- [x] Baseline, empty index, authorized scope and protected hashes checked.
- [x] Bounded plan recorded before code changes.
- [x] Freeze pre-extraction fingerprints for nine discriminating datasets against
  immutable 6838af1: 145 serialized outputs per dataset (summary/history/fiscal/
  comparison/annual discovery/base). Independent selection/order/value assertions
  passed against the unmodified service. Guarded probe exited 0; no DB connection.
- [x] Implement and verify actual shared-engine delegation; two static P2 findings
  corrected in the focused follow-up, pending independent re-review.
- [x] Run authorized scoped offline regressions and mutation controls; keep
  historical evidence and current unexecuted gates distinct below.
- [x] Complete correction self-review and scoped preservation/whitespace checks;
  hand off for independent re-review, which remains pending. No self-approval or
  Git delivery follows.

## Test and validation strategy

Use `backend/.venv/Scripts/python.exe -I -S -B` and the inspected
`tests/run_sec_reader_offline.py` guard (before application imports), with explicit
synthetic test selections, `-p no:cacheprovider` and system temporary directories.
The guard blocks actual DB connections, DNS/network, model loads and .env opens.
No application server/lifespan or operational import check is authorized.

Planned evidence: fixed serialized fingerprints against 6838af1 plus pinned
baseline comparisons for summary/history/fiscal/comparison/annual discovery;
independent value/order assertions; deliberate decision mutations; actual engine
delegation; immutable records; conversion/projection work accounting; authority
loss during delegated work and on existing objects; full raw authorization
inventories, withdrawal and pinned gross-margin behavior; unchanged Insights
financial/diagnostic graph and pure-helper imports; empty-permission loader's
two statements and no evidence I/O. Existing synthetic authorization/evidence/
Insights/lifecycle/reader suites remain unchanged except authorized AST tests.

## Completion criteria

Only the seven paths changed, index/HEAD/protected exceptions preserved; targeted
offline checks and discriminating controls pass; limitations documented. This
stage ends with readiness for focused independent review, not approval/activation.

## Final outcome

Implementation candidate with two focused P2 source corrections; independent
re-review remains pending. Actual model/reasoning settings are not exposed in
session metadata; requested gpt-6.1-sol / High cannot be confirmed.

### Correction implementation

- Full FactProvenance scalar fields are captured as nested immutable tuples on
  internal observations. Engine values/dates and later source projections use the
  same capture. All public schema/registry/evaluator/source-policy files remain
  unchanged; original ORM rows are retained separately.
- `_unproject` captures the supplied provenance itself, including accession,
  concept, periods, source value and diagnostic metadata. It does not replace the
  source through a fact-ID lookup. Existing gross-margin source-pair/coverage and
  duplicate-source checks receive the submitted metadata. Historical calculate
  ignores previous input ancestry; conversion does not impose a new lookup of
  those IDs or require local rows for otherwise valid helper arithmetic.
- Raw authorization rejection inventories still project the original current
  rows at that operation. Missing local denominator operands retain the original
  unavailable path instead of raising a lookup error. No financial policy changed.
- Only engine, facade, metrics tests and the two authorized documents changed in
  this correction; the existing Insights/isolation test files retain their static
  review-manifest hashes. The total candidate scope remains exactly seven paths.

### Historical extraction evidence (previous turn, not a current rerun)

All commands ran from `D:\Projects\finlens-foundation\backend` using
`.venv/Scripts/python.exe -I -S -B`, with offline guards and no pytest cache.

1. Pre-extraction `tests/run_sec_reader_offline.py tests/test_financial_metrics.py
   -k c5`: 14 passed / 117 deselected after correcting two test assertions to use
   the requested original authorization window rather than the latest summary.
   Nine baseline fingerprints were frozen before production extraction and were
   not regenerated during the P2 correction.
2. `tests/run_sec_reader_offline.py tests/test_financial_metrics.py
   tests/test_financial_insights.py tests/test_financial_metric_explanations.py
   tests/test_revenue_scope_authorizations.py -k 'c5 or not test_financial_metrics'`:
   final extraction run 283 passed / 117 deselected. Includes five deliberate
   decision-mutation controls and conversion/projection/lifecycle checks.
3. `tests/test_pure_helper_isolation.py`: 10 passed.
4. Initial four-suite temp-fixture attempt: 283 passed / 6 deselected / 110 setup
   errors, all reported as WinError 5 accessing pytest's temporary directory.
   A later normal-sandbox attempt using a fresh temp root failed at fixture setup
   and temporary-directory cleanup. These attempts are failures, not passes.
5. The previously approved one-time elevated four-suite command had already
   started when the coordinator stopped retries. Its observed final result was
   **393 passed / 6 deselected**, exit 0, 13.68 seconds. Earlier approved execution
   also returned 393 passed / 6 deselected. Do not sum repeated/overlapping runs.
   Exact final command (historical record only; NOT permission to repeat):

```powershell
$env:GIT_OPTIONAL_LOCKS='0'
$c5TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('finlens-c5-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_sec_evidence_adapter.py tests/test_company_comparison.py tests/test_activation_lease_admission.py tests/test_reader_publication_admission.py --basetemp=$c5TempRoot --maxfail=1 --deselect=tests/test_sec_evidence_adapter.py::test_real_original_artifact_offline_without_permission_activation --deselect=tests/test_activation_lease_admission.py::test_operator_launch_post_ready_loss_reaches_no_successful_serving --deselect=tests/test_activation_lease_admission.py::test_post_ready_lease_loss_genuinely_terminates_process
```

Requested permission was `require_escalated` only for temporary-fixture access;
network, both real database drivers, private env reads and model loads stayed
blocked. There is no standing authorization for elevation or another temp run.

### Current focused correction evidence

Normal sandbox only; no new basetemp, temp-fixture group, elevation or operational
action. The existing guard was re-inspected before running application test imports.

- Before the production correction, the command below failed five selected cases,
  demonstrating snapshot/provenance drift and silent same-ID accession replacement:

```powershell
$env:GIT_OPTIONAL_LOCKS='0'
& .\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_financial_metrics.py -k '(c5_p2_snapshot and selected and value) or (c5_p2_helper and gross_profit and accession_number)'
```

- Initial focused post-correction `tests/run_sec_reader_offline.py
  tests/test_financial_metrics.py -k c5_p2`: 56 passed / 149 deselected, exit 0.
- Subsequent permitted group with timestamp and raw-authorization mutation cases:
  348 passed / 117 deselected, exit 0. Three missing-local-operand helper cases were
  then added; final result is recorded below after that last targeted run.
- `tests/test_pure_helper_isolation.py`: 10 passed, exit 0, 4.292 seconds, including
  fresh engine import/execution without ORM/configuration/provider dependencies.
- Final permitted regression command, from the same backend directory:

```powershell
$env:GIT_OPTIONAL_LOCKS='0'
& .\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_financial_metrics.py tests/test_financial_insights.py tests/test_financial_metric_explanations.py tests/test_revenue_scope_authorizations.py -k 'c5 or not test_financial_metrics'
```

Result: **351 passed / 117 deselected**, exit 0, 8.20 seconds. Includes all 68 new
P2 cases, the 32 prior C5 cases with unchanged frozen fingerprints, and the 251
Insights/explanation/authorization cases. The focused 56/348 earlier groups overlap
this result and are not additive. No permission prompt or elevation occurred.

The final P2 matrix contains 36 selected/ranked-alternative/excluded-alternative
post-construction mutations (including values, dates, concepts, accession, units,
fiscal annotations and timestamps); 24 same-ID supplied-source metadata mutations;
one legitimate FCF helper with no local rows and prior ancestry; four original-row
authorization diagnostic mutations; and three missing-local-denominator cases.
All compare against immutable 6838af1, with unchanged frozen goldens. Existing valid
calls, changed metric values, duplicate provenance, pinned coverage and decision
mutation controls remain in the scoped suite.

### Unverified limits

At the correction handoff, the four-suite groups had not been revalidated against
the corrected tree. That gap is addressed only by the separately authorized final
run below. The 117 excluded pre-existing metrics cases, DB-backed research/history/
sync regressions, external-original case and five launcher/process cases remain
unexecuted here. No real DB/API/browser, native custody, live source/provider,
allocation/RSS, session admission or runtime-delivery acceptance is claimed.
Conversion/projection logical work is counted; native resource guarantees are not.
The test runner reports the pre-existing Starlette/httpx deprecation warning; no
dependency or configuration change is authorized or made.

### Final correction scope and preservation

`main` / HEAD remains `6838af1d9164979daebb179144d67cd154da020e`; the index is empty.
Exactly the authorized seven candidate paths plus the three protected historical
exceptions remain. No stage/commit/push/branch/config operation occurred. All three
protected SHA256 values still match the table at the start of this plan; only their
hashes were read. Source-level self-review found no remaining issue in the two P2
corrections; this is not independent approval or a full acceptance PASS.

The final baseline-relative tracked diff is +198/-363 facade, +392/-1 metrics tests,
+98/-32 Insights tests, +35/-0 isolation tests, +53/-2 shared-contract documentation.
The new engine is 488 lines; this new plan's final line count/hash are included in
the final handoff manifest. Both new files remain untracked, not add-N staged.

`git diff --check --` with all seven explicit paths passed. A separate read-only
seven-file scan also checks trailing whitespace, missing final newlines and extra
blank EOF lines, including the two untracked files. It found one extra engine EOF
blank line, removed without changing code semantics. The final read-only scan passed
after the documentation update. No Git line-ending configuration was changed.

Six non-self-referential file hashes at handoff (the final plan SHA256 is supplied
in the report so this file need not contain its own hash):

| Candidate path | SHA256 |
|---|---|
| backend/app/financial_metric_engine.py | 8F725B440316F080DC89B2F7607A3F4E38074E29789DD6A5FB9BD1789EE7EC87 |
| backend/app/financial_metrics_service.py | 2977CA23C92BB6F3709E33D7A2F0FAB48CF27D1F32CA9678B28B936216C14D0D |
| backend/tests/test_financial_metrics.py | A427FDDE3E99064E32AFCB4D999B3F00CC342710C294ED310CDDEE0A79B7CB81 |
| backend/tests/test_financial_insights.py | D3B9261B9E1B3F8C07629FAFC8B69EE2C561D201C3D88D81BB9610ADEB4103E3 |
| backend/tests/test_pure_helper_isolation.py | 7506619A1551A9C6942B9FE37BF7B2DB845FFF33BE2D9CDF824F769FFF676AE5 |
| docs/shared-research-contracts.md | C88E87AA6A3D8B516827A440A13BC6777131DABAD88964A1F8EAA162C886FEBF |

Suggested eventual commit, only after separate review/Git authorization:
`refactor(financials): extract shared engine with DB parity`.

### Final corrected-tree four-suite regression — 2026-10-30

Separately authorized bounded validation after the coordinator reported Astra's
focused P2 re-review and independent 351-test / 10-test reproduction. Those suites
and that review were not repeated in this turn. Before execution, all seven files
matched the final reviewed manifest, including this plan's pre-run SHA256
`140AC09E1ED8B039510AF219D7B68F23A24FF8726578C7B8DECFC69CA5C1385A`.
`main` / HEAD was `6838af1d9164979daebb179144d67cd154da020e`, the index was empty,
and status contained exactly the seven candidate paths and three protected
historical exceptions. All protected hashes matched the opening table.

Working directory: `D:\Projects\finlens-foundation\backend`. Exact command:

```powershell
$env:GIT_OPTIONAL_LOCKS='0'
$c5TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('finlens-c5-' + [guid]::NewGuid().ToString('N'))
& './.venv/Scripts/python.exe' -I -S -B tests/run_sec_reader_offline.py tests/test_sec_evidence_adapter.py tests/test_company_comparison.py tests/test_activation_lease_admission.py tests/test_reader_publication_admission.py --basetemp=$c5TempRoot --maxfail=1 --deselect=tests/test_sec_evidence_adapter.py::test_real_original_artifact_offline_without_permission_activation --deselect=tests/test_activation_lease_admission.py::test_operator_launch_post_ready_loss_reaches_no_successful_serving --deselect=tests/test_activation_lease_admission.py::test_post_ready_lease_loss_genuinely_terminates_process
```

Result: **exit 0; 393 passed, 6 deselected, 1 warning; 14.18 seconds**. This is a
new execution against the corrected tree, distinct from every historical run and
temporary-directory failure above. One normal-execution attempt, no elevation,
permission request, guard weakening, extra exclusion or retry. The current host
has filesystem sandboxing disabled; this run did not reuse the prior single-use
outside-sandbox approval. Existing network/DB/model/private-env guards stayed on.

The six exclusions are one external-original-artifact case, one operator-launch
case and four parametrized process-termination cases. They remain unverified here.
No native/live, real DB/API/browser, allocation/RSS, session-admission or deployment
acceptance follows. The warning is the existing Starlette/httpx deprecation.

Only this ExecPlan was updated after the successful run. Final read-only checks
verify unchanged HEAD/empty index/status path set, the six other candidate hashes,
all protected hashes and scoped whitespace including untracked files. The final
ExecPlan hash/diff are supplied in the validation report to avoid a self-hash.
No implementation/test change, staging, commit or push is authorized by this run.
