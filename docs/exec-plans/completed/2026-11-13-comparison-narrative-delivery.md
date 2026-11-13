# HEAD-based comparison narrative delivery

Status: completed subset preparation; independent complete-delta review pending
Roadmap phase: close existing Research Mode work; no feature expansion

## Objective

Produce a complete, isolated, reviewable comparison display/narrative subset
against HEAD `17be7b5ba856a6b881a79c2c778bb6bf85eca297`, rather than treating the
earlier five-line incremental review as approval of its entire dirty service.
Keep every existing repository file, including all eight A–C files, unchanged.

## Current architecture and context

Read AGENTS.md, ROADMAP.md, .agent/PLANS.md, engineering standards and the active
delivery-integration assessment. D is the smallest held public research path.
Its current service mixes comparison formatting/narrative with Chinese grammar
extensions and private publication projections. The latter are independent work.
E requires private storage/migrations; F/G require broader UI/export parents.
Entry HEAD is the SHA above; extensive pre-existing dirty work and zero staged
paths must remain preserved. A–C are accepted according to the coordinator.

## Constraints

Only this new ExecPlan and new external evidence may change. No staging, commit,
push, publication transport probes, alternate credentials/remotes, network or
security changes. No database provisioning/connections, installs, downloads,
servers or production operations. Never retry a denied operation by another
route. Preserve original receipts, working files, guards and assertions.

## Non-goals

No new grammar, private persistence, UI, arithmetic, ingestion, metric selection,
live database/browser/provider or release acceptance. This is a HEAD-specific
adaptation of existing work, requiring independent complete-delta review.

## Implementation stages

1. Capture dirty-file, A–C, Git metadata and prior-evidence identities.
2. Reconstruct HEAD sources/tests, overlay only the existing comparison resolver
   and display helper closure, the exact narrative tests, and five existing
   precision methods on the HEAD Chinese-comparison fixture.
3. Run unchanged installed offline guards with focused and relevant regressions;
   inspect actual failures, and fix only a demonstrated bounded defect if needed.
4. Freeze exact proposed manifest/patch, dependency closure, commands, results,
   preservation and remaining gates for independent review.

Recovery is deletion of these newly owned artifacts only; never reset or replace
the current dirty source/test files.

## Decisions

- 2026-11-13: Choose D with a new HEAD-specific candidate. Include its existing
  precision parent because the narrative tests demand literal tiny differences
  and distinguishable endpoints. Exclude unrelated language/private parents.
- Reconstruct in a new external directory; do not replace current source files.

## Discovered issues

- Baseline HEAD reproduces missing narrative/display behavior: 24 narrative
  failures and one refusal pass. The augmented original Chinese fixture runs
  18 methods and records 13 failing subtest/assertion records and three errors
  within its five precision methods; all thirteen original methods pass.
- The first relevant regression run has 197 passes and one blocked reference
  fixture: `git show 6838af1d9164979daebb179144d67cd154da020e:backend/app/financial_metrics_service.py`
  in the candidate snapshot is rejected by Git's dubious-ownership check.
  A direct diagnostic read confirms that reason. This is a local Git trust
  restriction, not an application assertion failure or an auto-review rejection.
  No trust/ACL/security setting changed, and the blocked snapshot read was not
  retried after diagnosis or replaced with another route. Its actual reference
  execution remains a hard gate. The later A–C compatibility run explicitly
  deselects this one test; no bypass or substitute C5 acceptance is claimed.
- The initial 35-case parity run passes assertions but its external import
  inventory rejects the intentionally loaded HEAD reference module. Retained
  wrapper v1 used an atexit callback, whose exception did not change exit 0.
  This receipt is incomplete metadata, not final parity acceptance. Wrapper v2
  explicitly permits only the named immutable HEAD file with its declared hash,
  and validates imports synchronously in finally so inventory failure is fatal.
  The final 35-case run passes with its complete import inventory. The product,
  tests and offline guard never changed for this harness correction.
- Static dependency traversal initially decoded a HEAD UTF-8 BOM as source text;
  retain the original script/failure, then use utf-8-sig matching Python source
  decoding. This external metadata correction passes; no product defect was
  manufactured or repaired in the current working tree.

## Progress

- [x] Read governing instructions and compare D–G dependency costs.
- [x] Preserve entry identities and reconstruct exact HEAD-specific closure.
- [x] Execute focused/regression/parity and negative controls.
- [x] Self-review, preservation, exact manifest and immutable review freeze.

## Test and validation strategy

Use existing Python with `-I -S -B`, unchanged HEAD
`tests/run_sec_reader_offline.py`, installed dependencies only, and snapshot-local
source imports. Synthetic ORM records/fake query loaders retain real financial
engine/typed dispatch. Standalone Chinese fixture uses its original import/audit
guards. Record commands, failures, results and fixture changes separately.
Compare full structured payloads independently of answer_text/display fields.
Evidence root: `D:/Projects/finlens-delivery-D-head-20261113/`.
`run_case.py` records exact executable, argv, cwd, timestamps, actual child exit,
timeout and stdout/stderr. Its own process exits 0 after retaining an ordinary
test failure; the child exit in the command receipt is authoritative.

All commands start from `D:/Projects/finlens-foundation`:

    & backend/.venv/Scripts/python.exe -I -S -B D:/Projects/finlens-delivery-D-head-20261113/run_case.py <label> <group> <mode> <arguments>

The wrapper uses the same installed Python with -I -S -B, changes cwd to the
explicit frozen backend, and loads the unchanged HEAD offline runner in guard
mode, or the unchanged standalone fixture entry in standalone mode. Installed
site-packages are the only shared runtime; app imports stay in the snapshots.

| Label; group; mode | Arguments | Actual result |
| --- | --- | --- |
| baseline-narrative; baseline; guard | `tests/test_comparison_answer_narrative.py` | 24 failed, 1 passed; child exit 1. |
| baseline-precision; baseline; standalone | `tests/test_chinese_revenue_comparison.py` | 18 methods; 13 failure records, 3 error records; child exit 1. Subtest counts are not failed-method counts. |
| candidate-narrative; candidate; guard | `tests/test_comparison_answer_narrative.py` | 25 passed; exit 0. |
| candidate-precision; candidate; standalone | `tests/test_chinese_revenue_comparison.py` | 18 methods passed, no errors/failures/skips; exit 0. All six synthetic effect sentinels triggered once. |
| candidate-regression; candidate; guard | `tests/test_financial_insights.py tests/test_balance_sheet_ratios.py tests/test_quarter_window_comparison.py` | 197 passed, one blocked Git fixture failed; exit 1. |
| candidate-multi; candidate; standalone | `tests/test_multi_metric_fiscal.py` | 7 passed; exit 0. |
| head-payload-parity; candidate; guard | absolute external `test_payload_parity.py` | 35 assertions passed; exit 0 with failed atexit inventory; superseded metadata receipt retained. |
| head-payload-parity-final; candidate; guard | same external test path | 35 passed with complete import inventory; exit 0. |
| abc-integration; candidate-ABC; guard | `tests/test_comparison_answer_narrative.py tests/test_metric_accession_validation.py tests/test_financial_insights.py tests/test_balance_sheet_ratios.py tests/test_quarter_window_comparison.py tests/test_company_comparison.py tests/test_filing_chunk_offsets.py tests/test_rag.py::HybridTests tests/test_bounded_research.py -k 'not test_c5_insights_use_delegated_engine_and_keep_original_diagnostics'` | 516 passed, 1 deselected, 8 subtests passed; exit 0. |

The integration uses only D's candidate plus the five unchanged accepted A–C
source/test overlays. No A–C document or working file is changed. The initial
197 regression passes overlap this integration and are not added again.
Bounded-research Node subprocess fixtures use intercepted fetch, not a browser
or live HTTP. An existing Starlette/httpx deprecation warning remains.

Final parity independently requires expected matched/status/kind/read-count for
each of 35 scenarios before comparing payloads. It compares every field except
the four explicit presentation fields (`answer_text`, `formatted_value`,
`formatted_absolute_change`, `formatted_percentage_change`), recursively for
multi-metric children. Exact Decimal numbers, periods, formulas, selected and
alternative provenance, identifiers, URLs, availability and schemas are equal.
Ordinary noncomparison/refusal payloads are wholly equal; the declared tiny
direct amount changes from $0.00 to its literal $0.0001. The comparison cases
add complete change text. This targets HEAD, not the blocked older C5 reference.

Three single-source controls each copy the positive snapshot and mutate only
one declared line. Commands use the same run_case.py prefix:

| Label; group; mode | Arguments | Actual detection |
| --- | --- | --- |
| control-absolute; no-absolute; guard | `tests/test_comparison_answer_narrative.py::test_level_answer_states_absolute_change_and_percentage_policy` | 7 expected assertion failures; exit 1. |
| control-qualification; no-qualification; guard | `tests/test_comparison_answer_narrative.py::test_eps_answer_states_as_filed_difference_and_share_basis_qualification` | 1 expected qualification assertion failure; exit 1. |
| control-endpoints; no-distinct-endpoints; guard | `tests/test_comparison_answer_narrative.py::test_tiny_absolute_change_is_not_rounded_to_zero_in_text` | 1 expected literal endpoint assertion failure; exit 1. |

These are sensitivity checks, not additional product journeys. No guard, existing
assertion or admission policy was weakened. The full positive product cohorts
are 516 integration cases plus 18 standalone Chinese methods and 7 multi-metric
methods, with 35 separate parity scenarios; repeated focused runs are not added.

## Exact proposed manifest and dependency closure

Only the following four HEAD-relative paths are proposed. The first and third
are partial-file reconstructions: never stage their current whole working files.
`delivery.patch` and `candidate/` retain exact review bytes.

1. `backend/app/research_answer_service.py`: HEAD plus the exact current
   resolve_historical_answer, display constants and four formatting helpers.
2. `backend/tests/test_comparison_answer_narrative.py`: exact current 25-case file.
3. `backend/tests/test_chinese_revenue_comparison.py`: exact HEAD file plus five
   exact current test_precision_* methods. Original guard and all original
   assertions remain unchanged.
4. `docs/exec-plans/completed/2026-11-13-comparison-narrative-delivery.md`: this
   complete-delta delivery record, separate from the historical incremental plan.

The precision helper parent is required by tiny-change narrative assertions;
its direct-value behavior is tested explicitly. The normalized registry,
schemas, FinancialMetrics engine, Company/FinancialFact models and release
decorator are exact HEAD bytes. No uncommitted production parent is necessary.
Static recursive local imports account for 58 modules (including conditional
imports); runtime inventories bind actual imports to snapshot hashes. Source
AST verification proves every other HEAD top-level statement unchanged; all
changed/added function and constant ASTs equal the named current input spans.
The Chinese test AST equals HEAD after removing only those five methods, each
identical to its current-source counterpart. All six snapshot inventories match
their declared HEAD files/overlays. No dirty import is permitted; the parity
reference is the sole explicit hash-checked external app module.

Excluded: Chinese net-income/quarter/multi-metric grammar, private pinned-answer
projection helpers, ownership/models/HTTP/login/session modules, migrations,
frontend/UI/export, shared README/ROADMAP/product-spec and all other dirty paths.
A–C are separate independent scopes; their compatibility overlay is not a D
prerequisite. E–G and excluded D parent features remain held.

## Preservation and review evidence

Entry records 184 pre-existing dirty files plus this newly created active plan.
Final preservation requires all 184 original file hashes, all eight A–C paths,
all 1,340 preceding assessment artifacts, HEAD, refs and raw index unchanged;
zero staged paths. This task changes only its new plan in the repository and
adds its external evidence. Original narrative evidence and prior assessment
freezes are not overwritten. `reconstruction.json`, `structure-verification.json`,
`preservation.json`, the complete proposed manifest and `review-freeze.json`
bind the HEAD blobs, raw candidate/source bytes, test resources, scripts and all
execution receipts. Hash validation, not filesystem permission changes, provides
the immutable review binding. `verify_freeze.py` checks those hashes; reproduction
uses a new sibling directory and never overwrites retained receipts.

## Completion criteria

Exact HEAD-relative source/test subset; genuine parent dependencies accounted;
focused, relevant regressions and meaningful negative controls recorded; original
working files/A–C/Git metadata/prior evidence preserved; independent review entry
point and all remaining hard gates explicit. Complete subset preparation does
not imply independent review acceptance or permission to stage/publish.

## Final outcome

The D narrative/display subset is reconstructed and source-scope verified over
immutable HEAD, with focused, relevant regression, parity and sensitivity checks.
It is ready for independent complete-delta review; the earlier incremental review
is not inherited as approval of this adaptation. Current application/test files
and A–C remain untouched. No new product defect required a working-tree fix.

Remaining hard gates: independent full-delta reviewer acceptance; one blocked
legacy fixed-SHA Git reference execution; subsequent exact candidate/index/HEAD
delivery preflight and authorized staging/commit; Git publication remains blocked
by the coordinator-reported github.com:443 transport restriction. No publication
attempt, alternate identity/remote/proxy/security route or trust-setting change
was made. Original connection metadata remains historical. Real PostgreSQL/SQL,
migrations, live services/SEC/provider/model, frontend/browser/accessibility,
durability/physical cleanup and release acceptance did not run and are not closed.

No stage, commit or push. Suggested eventual subject:
`fix(research): preserve precise self-contained comparison answers`.
