# FL-RUNTIME-02A — Disabled SEC reader foundation

Status: active; P2 correction implemented/offline-verified, independent re-review pending
Roadmap phase: scoped runtime foundation; no later increment authorized

## Objective

Introduce an explicit, inactive `sec_reader` profile with an isolated import path.
Admit only static health/capability diagnostics; deny all data and operations.
Preserve development, `sec_readonly`, route identity checks and financial semantics.

## Current architecture and context

Root AGENTS.md, ROADMAP.md, engineering standards and .agent/PLANS.md were read.
Verified branch `main`, HEAD/local origin/main
`4cd545f5e6d682423da55cac512abbcfa73a6a05`, empty index. The operator attests PR #1
was squash merged; no remote lookup is authorized or performed here.
Only pre-existing worktree exceptions:

| Protected path | SHA-256 |
| --- | --- |
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

`main.py` imports DB/research/provider modules before constructing its app.
`release_policy.py` already guards operational functions and route identities.
`embedding_service.py` currently falls through to development model loading for
any profile other than `sec_readonly`; this must become explicit admission.

## Constraints

No private dotenv reads, physical SQL, network/SEC/provider calls, service startup,
model downloads/installations, DB/frontend changes, activation, staging or delivery.
All authorization registries remain untouched and inactive. Tests use synthetic
transports and sentinels before application imports. No dependencies added.

## Non-goals

02B/02C/02D; financial/keyword routes or integrity contracts; authentication/JWT;
Cloudflare; Digest admission; DB roles, lifecycle changes or background workers.

## Implementation stages

1. Verify baseline and record a bounded plan.
2. Extend profile/policy and guard encoder entry before cache hits and imports.
3. Add isolated diagnostic reader entrypoint; reject incompatible entrypoints.
4. Add/run guarded synthetic tests and relevant existing-profile regressions.
5. Self-review exact scope, whitespace/index/HEAD and protected hashes; hand off.

## Decisions

- 2026-10-28: Keep existing missing-profile development default for compatibility.
  The reader entrypoint requires explicit `sec_reader`; missing/unknown/wrong
  profile and the legacy entrypoint/profile mismatch reject before initialization.
- 2026-10-28: Use a separate small reader module rather than moving the existing
  main module or changing DB lifecycle. Health means process diagnostic only;
  capabilities advertise research and AI as disabled regardless of credentials.

## Discovered issues

No FL-RUNTIME-01 design
artifact was found among runtime/release/reader document filenames; this increment
follows the explicit coordinator requirements and the current owning sources.

Initial combined tests: 316 passed, four failed (51.75s). All four failures were
legacy encoder assertions matching `local cache`, while the current error is the
typed `EncoderDependencyError` with a sanitized dependency message. Reproduced
the same four failures against all four unchanged HEAD production sources loaded
through an in-memory import finder (4 failed, 1 passed, 158 deselected; 0.66s).
Corrected only the two exception assertions in the maintained release tests to
assert the existing typed contract; encoder error behavior remains unchanged.

Additional regression findings (not financial implementation changes):

- Financial insights: 135 passed, one failed (6.18s). The failing
  `test_canonical_ast_changes_are_only_budget_instrumentation` strips budget
  instrumentation from the working tree but compares against already-merged HEAD
  without stripping it there. Both its test file and financial service are
  identical to HEAD (`git diff --exit-code` passed). Leave this stale baseline
  assertion unchanged and report it explicitly; no financial contract is modified.
- Combined runtime tests: 753 passed, nine failed (55.56s). Seven failures were
  the new runner's overly broad Engine.connect sentinel rejecting existing fake
  DBAPI fixtures; replace that sentinel with real PostgreSQL/SQLite driver guards.
  The remaining two cases use an unresolved `{chunk_id}`, malformed accession and
  missing pin for the existing tone route, yielding validation 422 before the
  expected synthetic busy response. These fixture defects are outside 02A scope.
- Latency regression initially had one collection error from its explicitly pinned
  synthetic URL; runner now uses that existing fixture URL. Then 117 passed,
  three failed: legacy unknown-profile expectations assumed read-only fallthrough.
  Update that single expectation to deny unknown/invalid profiles and add
  `sec_reader` (which must not enter the legacy app).

## Progress

- [x] 2026-10-28: Baseline, empty index and all protected hashes verified.
- [x] Relevant configuration, release policy, imports and maintained tests read.
- [x] Implement minimal foundation; legacy main delta is five guard lines only.
- [x] Run focused offline tests, syntax and relevant regressions (baseline defects below).
- [x] Verify preservation and prepare independent Astra review handoff.

## Test and validation strategy

Guard dotenv, model imports, physical DB connections and external sockets before
app imports; allow only the stdlib-owned Windows asyncio wakeup socketpair.
Exercise pure ASGI in memory without lifespan/server startup. Fresh subprocesses
verify import isolation, profile selection and initialization order. Test forbidden
methods, aliases, route replacements, spoofed configuration, cached encoders,
injected clients and operational callbacks. Existing profile and financial tests
remain separately identified. Record actual commands/results below after running.

## Completion criteria

Only explicit minimal diagnostics admitted; data/operational/model paths blocked;
no imported DB/model/provider stack through the reader; focused and scoped regression
evidence recorded; all protected bytes and existing financial contracts preserved.
Independent Astra/coordinator review remains pending, with no staging or next work.

## Final outcome

Implemented 02A only; inactive and ready for independent review with explicit
baseline-test limitations. No application startup, real SQL/SEC/network/provider
calls, private dotenv access, model installation, activation or Git mutation.
ASGI requests ran in process without lifespan startup. Windows asyncio uses only
its own wakeup socketpair. PostgreSQL/SQLite driver calls, dotenv file reads,
model imports and provider constructors were guarded before app imports.

### Exact task scope

- `backend/app/config.py`: explicit third profile; no DB bounds for reader.
- `backend/app/release_policy.py`: separate two-route diagnostic policy, exact
  reader paths and original object identity, bound reader profile, invalid-profile
  denial, encoder admission before cache hits.
- `backend/app/embedding_service.py`: guard query/loader/cache entry, including
  empty inputs; preserve development and local-only sec_readonly behavior.
- `backend/app/main.py`: five-line early guard only; no route/handler refactor.
- `backend/app/sec_reader.py` (new): isolated static diagnostics, no data imports,
  no docs/schema, research and AI capabilities always false, no-store responses.
- `backend/tests/test_sec_reader.py` (new): fresh-process profile/import tests,
  forbidden methods/aliases, dependency/body sentinels, route replacements,
  spoofed configuration, warm encoder/provider caches and full maintained
  operational-entry inventory; authorization registries remain inactive.
- `backend/tests/run_sec_reader_offline.py` (new): pre-import isolation runner.
- `backend/tests/test_release_profile.py`: two stale error-message assertions
  changed to the existing typed encoder dependency exception.
- `backend/tests/test_evidence_latency.py`: deny invalid resolved profiles and
  reader requests through legacy app, retaining no-collection assertions.
- This ExecPlan (new).

### Final test evidence

Working directory `D:\Projects\finlens-foundation\backend`:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_sec_reader.py tests/test_release_profile.py tests/test_capabilities.py tests/test_http_database_runtime.py tests/test_bounded_research.py tests/test_evidence_latency.py -k "not (every_http_database_path_uses_bounded_factory and tone)"
# 881 passed, 2 deselected, one existing Starlette/httpx deprecation warning; 52.66s.

.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_insights.py -k "not canonical_ast_changes_are_only_budget_instrumentation"
# 135 passed, 1 deselected, same existing warning; 3.55s.
```

The two tone failures were independently reproduced using unchanged HEAD versions
of config/release_policy/embedding_service/main loaded by an in-memory import finder
before pytest collection: `tests/test_http_database_runtime.py -k
"every_http_database_path_uses_bounded_factory and tone" -q --tb=short -p
no:cacheprovider` => 2 failed, 251 deselected (0.79s). No source checkout or edit
was used. The financial AST test is self-contained on two unchanged tracked files;
its full unfiltered run failed as recorded above. These three cases are explicitly
excluded from final passing counts, not treated as accepted or repaired.

Syntax verification used `.venv\Scripts\python.exe -I -S -B -` with a stdin script
calling `ast.parse(source, filename=path)` and `compile(source, path, 'exec')` on
all nine changed Python files: PASS, without imports or generated bytecode.
AST self-review compared main to `git show HEAD:backend/app/main.py` after removing
only the early reader guard: identical. Existing READONLY_ROUTES AST: identical.

### Preservation and security review

Verified exact ten task paths plus the three original protected exceptions, empty
index, unchanged main/HEAD/origin/main and all protected SHA-256 hashes matching
the starting table. Tracked diff and all four new files checked for whitespace.
All financial services/schemas/contracts, database lifecycle, financial
authorization/activation sources, existing financial-insights and HTTP-runtime
test files match HEAD. No financial or keyword route is admitted for the reader.

Compatibility detail: missing global profile still selects development for the
existing app; missing/unknown/inconsistent configuration cannot select the reader.
`app.sec_reader` requires explicit `sec_reader`; `app.main` rejects that profile
before DB/research initialization. The reader's middleware also rejects a later
in-process mismatch rather than inheriting development or sec_readonly admission.
Health is a static process diagnostic, not readiness/data/DB/provider acceptance.
This is application admission, not a sandbox against trusted Python/OS/DB access.
Direct trusted imports of operational modules outside the reader remain outside
the import-isolated entrypoint; their maintained function guards reject operations.

### Independent Astra/coordinator handoff

Review the exact ten-file candidate against baseline
`4cd545f5e6d682423da55cac512abbcfa73a6a05`, especially entrypoint/profile pairing,
default-deny routing before dependencies, diagnostic capability truthfulness,
encoder cache guards, and unchanged financial/authorization boundaries. Review the
three documented baseline test defects separately; no broad suite PASS is claimed.
No independent Astra review has run in this chat. Coordinator review is required
before staging or any further implementation; 02B/02C/02D remain unstarted.

Suggested commit (only after separately authorized review/staging):
`feat(runtime): add disabled SEC reader foundation`.

## P2 correction — dotenv admission boundary

The coordinator supplied Astra's independent FAIL / NO-GO: the reader imported
`app.config` before checking the process profile, and that module called dotenv
before admission. The earlier runner's no-op masked this boundary defect. Prior
readiness wording and broad passing counts above are historical, not acceptance
of this boundary. No private file was read during review or this correction.

Rechecked `main`, HEAD/origin/main `4cd545f5e6d682423da55cac512abbcfa73a6a05`,
empty index and all three protected hashes. Existing candidate scope is exactly
the same ten files. Captured all nonignored tracked/untracked file hashes and
copies of the five authorized correction files outside the repository at
`C:\Users\IITSt\AppData\Local\Temp\finlens-02a-p2-vunms2ek`.

Only config.py, sec_reader.py, test_sec_reader.py, run_sec_reader_offline.py and
this plan may change relative to that snapshot. No changes to the other five
candidate files or existing historical failing tests are authorized.

- [x] Added sentinel/injection probes before changing production code.
- [x] Reproduced original defect: 19 failed, 161 deselected (19.14s), using
  `.\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_sec_reader.py -k "independent_fresh_process or explicit_reader_never_loads or dotenv_cannot_inject or shared_config_rejects_reader"`
  from `backend`. Missing/invalid entrypoint profiles reached the loader, injected
  reader values were accepted, explicit reader/config imports called dotenv, and
  the independent stdlib-only fresh-process sentinel failed before rejection.
- [x] Add pre-config process gate and shared-loader reader restrictions.
- [x] Run only targeted reader/security and existing-profile regressions.
- [x] Check exact correction delta, preservation, syntax/whitespace and index;
  return candidate to independent Astra/coordinator review without staging.

### Correction and secured boundaries

- `backend/app/sec_reader.py:6-15`: check the exact process value before importing
  `app.config`; missing/blank/invalid/legacy values reject without importing shared
  config or invoking any dotenv loader. Retain the resolved-profile check to reject
  conflicts with an already-imported shared configuration. No fallback is added.
- `backend/app/config.py:11-25`: capture the process profile before any dotenv call.
  Direct shared-config imports with explicit `sec_reader` skip initial dotenv.
  Every subsequent `load_backend_env` invocation explicitly raises ValueError
  before path handling or loader invocation if the original process profile, the
  current process profile, or the frozen resolved profile is `sec_reader`. Removing
  or changing the environment after reader admission cannot reopen the loader.
- `backend/app/config.py:64-69`: reject a reader profile injected solely by dotenv,
  including a synthetic loader that violates `override=False`. Development and
  sec_readonly retain the same initial/default/custom-path calls, override=False,
  process precedence, dotenv-supplied legacy selection and frozen resolution.
- `backend/tests/run_sec_reader_offline.py:75-88`: replace the anonymous no-op with
  a recording legacy sentinel that fails for reader process values. Reader child
  probes install an unconditional raising sentinel before application imports;
  injection tests install explicit adversarial synthetic loaders and assert no
  invocation. Legacy tests opt into controlled recording loaders only.
- `backend/tests/test_sec_reader.py:26-89,157-292`: process-aware fixture, explicit
  import barrier, genuine loader sentinels, default/custom-path reload attempts,
  conflicting frozen/process state, dotenv injection, and six legacy precedence
  cases. Three fresh-process negative probes use only stdlib plus a synthetic
  dotenv module, independently of the runner, and failed on the original code.

Exact unified correction diffs for the five files are retained outside the repo
at `C:\Users\IITSt\AppData\Local\Temp\finlens-02a-p2-vunms2ek\p2-correction.patch`.
The other five original candidate files are byte-identical to the pre-correction
snapshot: main.py, release_policy.py, embedding_service.py, test_release_profile.py
and test_evidence_latency.py. Route objects, allowlists, capability bodies, encoder
guards, financial semantics and inactive authorization registries are unchanged.

### Focused verification actually run

All commands below used `D:\Projects\finlens-foundation\backend`:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_sec_reader.py -k "independent_fresh_process or explicit_reader_never_loads or dotenv_cannot_inject or shared_config_rejects_reader"
# Before correction: 19 failed, 161 deselected (19.14s).
# After correction: 19 passed, 161 deselected (18.56s).

.\.venv\Scripts\python.exe -I -S -B tests/run_sec_reader_offline.py tests/test_sec_reader.py tests/test_release_profile.py::test_profile_is_resolved_once_and_frozen tests/test_release_profile.py::test_profile_resolves_after_dotenv_and_does_not_revalidate_on_reload tests/test_http_database_runtime.py::test_encoder_local_only_and_development_constructor_compatibility tests/test_http_database_runtime.py::test_profile_limits_and_startup_options tests/test_capabilities.py
# 192 passed (63.39s). One existing Starlette/httpx deprecation warning.
```

No broad 881/135 suite rerun; the two malformed tone fixtures and stale financial
AST comparison remain untouched historical failures. No full-suite PASS claimed.
Four corrected Python files parse/compile without imports/bytecode. Diff checks
cover tracked changes and new files. Final all-file hash/inventory comparison
confirms only the five authorized correction paths changed; the final candidate
remains exactly the same ten files plus the three protected exceptions. Protected
SHA-256 values match the original table; branch/HEAD/origin/main and empty index
are unchanged. No new dependency, private dotenv read, physical SQL/network/SEC/
provider call, model download, service/lifespan startup or Git staging occurred.

### Re-review handoff

Local correction and focused verification are complete; the supplied Astra
FAIL / NO-GO verdict is not superseded by local test results. Independent Astra
re-review must assess pre-config admission, direct config import, late loader
denial and the original missing-profile injection case before coordinator Git
Step 1. This remains application admission, not a Python/OS sandbox. No review
agent was invoked in this correction; no staging or later increment is authorized.
