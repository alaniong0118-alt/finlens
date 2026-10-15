# DEP-01A3 Increment 1 - offline private-runtime preflight

Status: active - Option B implemented and tested; coordinator review pending
Roadmap phase: scoped private sec_readonly runtime enabling task, Increment 1 only

## Objective

2026-10-15 scope amendment: implement the already reviewed Option B. Check only
explicit process profile and Python/distribution requirement metadata. Do not
inspect model artifacts. Overall private-runtime status ALWAYS remains BLOCKED
with exit code 1, including when all preliminary metadata checks pass. This
supersedes the original manifest gate for this increment; the historical record
below remains preserved. Approved script name: preflight_private_runtime.py.

## Original stopped scope and inspection (historical)

Create an explicitly invoked, offline, metadata/filesystem-only diagnostic for a
future private sec_readonly runtime, with focused synthetic tests. The user
explicitly requires stopping if a trustworthy model artifact manifest contract
cannot be defined from existing repository evidence. That gate failed during
inspection; this plan records the blocker rather than inventing a contract.

## Current architecture and context

Read [repository instructions](../../../AGENTS.md),
[plan rules](../../../.agent/PLANS.md), [roadmap](../../../ROADMAP.md) and
[engineering standards](../../engineering-standards.md).

Verified starting branch main, HEAD and origin/main all at
`cf14ec552e40d199b79d421f3ee61651c9e1bff1`; index empty. Exactly the expected
protected worktree entries were present:

| Protected file | Initial and final SHA256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

Relevant current source evidence:

- `backend/requirements.txt` declares `sentence-transformers>=3.4,<6.0`.
- `backend/app/config.py` loads backend dotenv, then freezes the profile;
  an absent profile defaults to development. A future preflight must independently
  require explicit effective sec_readonly without changing development behavior.
- `backend/app/embedding_service.py` declares
  `sentence-transformers/all-MiniLM-L6-v2` and dimension 384. Its release loader
  calls `try_to_load_from_cache(MODEL_NAME, "modules.json")` without a pinned
  revision, then passes the resulting parent directory to the constructor with
  `local_files_only=True`.
- `backend/tests/test_release_profile.py` uses a synthetic modules.json and fake
  constructor to verify local-only behavior. It does not define an approved
  artifact inventory, revision, manifest schema or trusted digest.
- Relevant README/docs/ExecPlan searches and model/manifest filename discovery
  found no model artifact trust contract. SEC financial evidence manifests and
  browser source manifests concern different artifacts and cannot authorize a
  query encoder snapshot.

## Constraints

Only the requested script, focused test and this one plan are approved for edits.
Preserve protected files and original SEC evidence. No dependency changes,
application startup, database access, sockets/network, registry access, model
construction/downloads, configuration changes, migrations, ingestion,
publication, activation, deployment or Git staging/commit/push/reset/cleanup.
Do not auto-create, approve or repair a model manifest.

## Non-goals

No production startup/routes, existing operational commands, encoder, database,
dependency manifests or lockfiles may change. A passing future diagnostic would
not establish numerical model compatibility, database privilege safety, Next.js
proxy correctness, runtime performance/concurrency or deployment authorization.

## Implementation stages

1. Verify Git state and protected bytes; inspect relevant existing contracts.
2. Establish whether repository evidence supports a trustworthy model manifest.
   Stop and report if it does not. This is the current stopping point.
3. Only after that gate is resolved in a separately reviewed contract, implement
   explicit profile admission, supported requirement/distribution metadata checks,
   artifact validation and deterministic sanitized output.
4. Run focused offline synthetic tests with side-effect sentinels; self-review and
   verify preservation, then await coordinator and independent Astra High review.

Recovery: no runtime implementation exists to roll back. Preserve this blocked
plan for review; no cleanup/reset is authorized.

## Decisions

- 2026-10-15: Apply the user's explicit requirement 4 stop condition. Model name,
  dimension and local-only cache loading do not specify which immutable snapshot
  and complete artifact set have been separately reviewed. Inventing a schema
  accepting caller-provided hashes or a self-asserted reviewed flag would not
  supply the missing trust evidence.
- 2026-10-15: Do not create a partial preflight/test suite or invent error codes
  while the mandatory manifest gate is unresolved. Only this approved plan is
  added. No production behavior or command changes.

## Discovered issues

Missing trust requirements for coordinator review:

1. Reviewed immutable model revision and complete required artifact inventory,
   including model/module configuration, tokenizer, pooling and weights, with
   approved relative identities, sizes/hash policy and expected digests.
2. Manifest schema/version and trusted approval anchor supplied independently of
   the artifacts being checked; clear ownership and review provenance.
3. Rules for local snapshot roots, paths, cache symlinks and containment, plus a
   binding between the verified snapshot and the runtime's actual cache selection.

No numerical compatibility evidence for a replacement sentence-transformers
version was established. Existing local-only loader tests are not such evidence.

## Progress

- [x] 2026-10-15: Verify exact baseline, index, worktree and protected hashes.
- [x] Read relevant repository instructions, roadmap, config, encoder, dependency
  declarations, local-only tests and documentation.
- [x] Confirm installed sentence-transformers 6.1.0 fails the declared range using
  distribution metadata and supported requirement parsing only.
- [x] Record missing manifest trust contract and stop before implementation.
- [x] Verify final Git state, scope, whitespace and protected-file preservation.
- [ ] Coordinator resolves missing trust contract; independent Astra High review
  remains pending. No deployment authorization is inferred.
- [ ] Implement script and focused tests after the trust gate is resolved.

## Test and validation strategy

Planned, not run: synthetic explicit/missing/wrong profile; missing, malformed,
incomplete and incompatible metadata; absent/incomplete manifest; hash mismatch;
valid synthetic artifacts; filesystem failures; fixed sanitized diagnostics;
sentinels for database/socket/model/download/subprocess/filesystem mutations.
No pytest or browser/API/runtime acceptance was run because implementation was
stopped at the mandatory trust gate.

### Checks actually run

Working directory: `D:\Projects\finlens-foundation`.

Git checks: `git status --short`, `git branch --show-current`, `git rev-parse HEAD`,
`git rev-parse origin/main`, `git diff --cached --name-status`, protected-file
`Get-FileHash -Algorithm SHA256`, and inspection of the existing next-env diff.

Metadata-only check (no app, encoder or model library import; bytecode disabled):

```powershell
& .\backend\.venv\Scripts\python.exe -B -c "from importlib.metadata import version; from packaging.requirements import Requirement; r=Requirement('sentence-transformers>=3.4,<6.0'); v=version(r.name); print('sentence-transformers metadata version: '+v if v=='6.1.0' else 'sentence-transformers metadata version differs from reported baseline'); print('Declared-range check: FAIL' if not r.specifier.contains(v, prereleases=False) else 'Declared-range check: PASS')"
```

Observed: `sentence-transformers metadata version: 6.1.0`,
`Declared-range check: FAIL`. Command exit 0 means the inspection executed, not
that the dependency satisfied its requirement. This is a direct metadata/range
check, not an implemented preflight result or full dependency validation.

Final verification: `git diff --check` and the new plan whitespace check passed;
branch/HEAD/origin/main and empty index unchanged. Final protected hashes equal
the baseline above. Final status contains only the three protected entries and
this new plan. No original SEC artifact was modified or loaded.

## Completion criteria

Trust contract resolved; all requested runtime checks and synthetic negative/
positive tests implemented and passed; no side effects; protected bytes preserved;
coordinator and independent Astra High implementation review completed. These
criteria are not satisfied; the task remains blocked.

## Final outcome

Stopped under the user's explicit manifest trust requirement. Added only this
blocked ExecPlan; script and test files do not exist. No preflight contract or
error codes were introduced. Confirmed the reported installed 6.1.0 metadata is
out of the existing declared range; no replacement was selected or validated.
All three protected files remain unchanged and unstaged; no commit/push occurred.

Suggested commit message for this documentation-only result, if later requested:
`docs: record DEP-01A3 model manifest trust blocker`.

## Approved Option B implementation - 2026-10-15

The user reports Astra High already reviewed Option B and explicitly authorizes
implementation without repeating design investigation. The original manifest
implementation/test stages above are superseded for this increment. This
diagnostic MUST NOT inspect model artifacts and MUST ALWAYS return BLOCKED.
No model approval or deployment decision is inferred from the scope amendment.

### Current context and scope

Reverified main/HEAD/origin/main at the expected
`cf14ec552e40d199b79d421f3ee61651c9e1bff1`, empty index, the same three protected
entries and this existing untracked plan. The plan's pre-update SHA256 was
`639B8328CCB6D84CA61494E7DAFD3F45CFE931E3F4763017A822DF2D53AC25D2`.
Its original inspection/history is preserved above. The only task edits are:

- `backend/scripts/preflight_private_runtime.py` (new)
- `backend/tests/test_private_runtime_preflight.py` (new)
- This existing untracked ExecPlan (updated).

No changes to application/startup/operational modules, dependency declarations,
lockfiles, private env files, the venv or SEC evidence artifacts. Temporary
synthetic fixtures are the only files created by the focused tests. The preflight
itself performs read-only operations.

### Implementation contracts and decisions

- Explicit invocation: from backend, use the intended interpreter and process
  environment `FINLENS_SERVER_PROFILE=sec_readonly`, then
  `python -B -m scripts.preflight_private_runtime`. No dotenv read, fallback,
  environment mutation, app/encoder import, registry access or model-file access.
  Bytecode writes are disabled before packaging imports as well.
- Output is deterministic JSON with `status: BLOCKED` and `exit_code: 1` on EVERY
  result, including two preliminary PASS checks. main returns 1; script raises
  SystemExit(1). These are diagnostics, never admission/activation commands.
- `explicit_profile` accepts only the exact process value sec_readonly; absence,
  blank, whitespace, unknown and development values fail.
- `python_dependency_metadata` checks backend/requirements.txt with supported
  packaging Requirement, Metadata, Version and marker/specifier APIs and stdlib
  importlib.metadata. No installed package code is imported. Parser absence or
  breakage fails closed without installation.
- Requirements are nonempty, UTF-8, one PEP 508 requirement per noncomment line.
  Pip directives/includes and direct URLs are unsupported and fail closed.
  Root markers use the current interpreter/platform with no active extra.
- Traverse all active transitive Requires-Dist declarations; union extras per
  canonical distribution identity and re-expand when new extras become active.
  Evaluate markers for base plus active extra contexts. Validate requested extras
  against Provides-Extra. Recheck every incoming version constraint even for
  already-expanded nodes; cycles terminate once extra sets stabilize.
- Discover installed identities using metadata only; duplicate canonical names
  for an active dependency are ambiguous. Validate core METADATA using packaging,
  including required fields, duplicates, version, markers and requirement syntax.
  Name disagreement across discovery/core metadata fails closed.
- Python is checked against each active distribution's Requires-Python.
  Missing/empty Requires-Python is indeterminate and rejected, even though that
  field is optional in the metadata standard. No new repository Python version
  bound is invented. Prereleases require explicit specifier admission.
- All diagnostics use fixed codes/messages; no raw metadata identities/versions,
  paths, profile values, credentials, URLs or exception text are emitted.
  Codes are deduplicated/sorted. The known sentence-transformers constraint
  violation has its own fixed code. No replacement version is selected/validated.
- Fixed limitations always state model/numerical, DB privilege, Next.js proxy,
  performance/concurrency and private deployment boundaries. No model manifest
  is read or generated. The historical trust/numerical gaps remain unresolved.

### Diagnostic code inventory

Exact fixed messages live in the script's MESSAGES mapping:

| Code | Trigger |
|---|---|
| PROFILE_REQUIRED | Process profile is not exactly sec_readonly. |
| PARSER_UNAVAILABLE | Supported parsing cannot be imported. |
| REQUIREMENTS_INVALID | Declared requirement file cannot be read/parsed, is empty or unsupported. |
| METADATA_INVALID | Missing, inconsistent, malformed or indeterminate core/dependency metadata; unsupported active URL/extra. |
| METADATA_AMBIGUOUS | Multiple installed distributions declare an active canonical identity. |
| DEPENDENCY_MISSING | Active dependency has no installed distribution. |
| DEPENDENCY_INCOMPATIBLE | Installed version violates an active requirement. |
| SENTENCE_TRANSFORMERS_INCOMPATIBLE | Installed sentence-transformers violates its active declared range. |
| PYTHON_INCOMPATIBLE | Current interpreter violates an active Requires-Python declaration. |
| INSPECTION_FAILED | Unexpected metadata/filesystem/environment inspection failure. |
| ARGUMENTS_UNSUPPORTED | Command-line arguments supplied; arguments are never echoed. |

Overall BLOCKED is permanent even with an empty diagnostic list. It does not
depend on a synthetic missing-model failure or on the current dependency defect.

### Validation and progress

- [x] Reverify Git baseline, existing untracked plan and protected hashes.
- [x] Implement the scoped Option B script and focused synthetic tests.
- [x] Test profile, Python/dependency metadata, markers/extras, graph constraints,
  duplicate identities, malformed/incomplete metadata, sanitized failures and
  permanent BLOCKED/nonzero output.
- [x] Check forbidden imports, sockets/DNS, subprocess startup, filesystem writes
  and nonmetadata/model-artifact reads using bomb sentinels. Exercise the real
  marker-environment helper under the external-operation guards as well.
- [x] Self-review and final preservation/whitespace/scope verification.
- [ ] Coordinator review. Stop here; no additional milestone or deployment work.

Actual focused command, cwd `D:\Projects\finlens-foundation\backend`:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_private_runtime_preflight.py
```

Final result: **60 passed in 0.29s**, no skips/failures. The first run found a
prerelease policy discrepancy (51 passed, 1 failed); explicitly using the
specifier's prerelease admission policy fixed it. Added an explicit-prerelease
positive control. Subsequent additions cover real marker collection, diagnostic
ordering and retention of the known incompatibility alongside invalid metadata.
No broader regression is justified: all production behavior is untouched.

Actual metadata-only CLI check, same cwd, using the unchanged current venv:

```powershell
$env:FINLENS_SERVER_PROFILE='sec_readonly'
& .\.venv\Scripts\python.exe -B -m scripts.preflight_private_runtime
```

Observed exit **1**, overall **BLOCKED**, explicit_profile **PASS**,
python_dependency_metadata **FAIL**, with fixed codes **METADATA_INVALID** and
**SENTENCE_TRANSFORMERS_INCOMPATIBLE**. Prior direct metadata inspection confirmed
the reported 6.1.0 installation; this actual preflight deterministically detects
its violation of the unchanged >=3.4,<6.0 declaration. Generic metadata failure
is reported without dumping affected local metadata or raw diagnostics.

### Option B completion criteria and outcome

Scoped implementation and synthetic tests are complete; coordinator review is
pending, so the plan stays active. Overall private runtime remains BLOCKED.
No numerical compatibility, database/proxy safety, performance or deployment
acceptance was attempted or established. No DB/network/model/download/service
operations, dependency changes, venv changes or Git writes occurred.

Final Git state: main/HEAD/origin/main unchanged; index empty. Six uncommitted
entries comprise the three protected originals, two new Python files and this
updated untracked plan. All protected hashes remain exactly equal to the table
above. Whitespace, local plan links and approved-file inventory were checked.

Suggested commit message, only if separately requested:
`feat: add blocked offline private runtime metadata preflight`.
