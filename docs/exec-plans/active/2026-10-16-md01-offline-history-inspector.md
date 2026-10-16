# MD-01 bounded offline raw-close inspector

Status: active; implementation authorized, independent review pending
Roadmap phase: scoped offline market-data enabling increment

## Objective

Inspect explicitly supplied local original EOD bytes and metadata as chronological
Unadjusted close observations, with gaps, exact strings and separate provenance,
publication and return states. Acceptance uses fictional fixtures only.

## Current architecture and context

Baseline: main / 434f30ab40204343e55451e673f6053890d04405; empty index.
Existing modifications: frontend/next-env.d.ts and two untracked runtime reports.
The existing Tiingo normalizer owns parsing and blocked publication construction;
market contracts own structural validation. Neither authenticates provider truth.
Read AGENTS.md, ROADMAP.md and .agent/PLANS.md before implementation.

Protected SHA256:
- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints and non-goals

Only seven authorized new files: app/market_history.py, scripts/inspect_market_history.py,
their two tests, fixtures/market_history/synthetic-context.json (all under backend),
docs/market-data-history.md and this plan. No existing-file edits, staging or commit.
No network, credentials, DB, model, API, UI, persistence or production admission.
CC-02 and DEP-01A3 are excluded. No existing normalizer/return suite repetition.

## Implementation stages

1. Strict bounded metadata decoder and pure projection through existing normalizer.
2. Local regular-file reader and sanitized stdout table/JSON CLI.
3. Composition/CLI tests, syntax/import checks, examples and preservation audit.

## Decisions

- 2026-10-16: Coverage is inclusive, at most 366 calendar dates and 366 eligible
  sessions. Reject overbounds; never truncate or infer calendar entries.
- Original response <=4 MiB; context <=256 KiB. Context has strict keys/types,
  duplicate rejection and only synthetic/unverified_local labels. These labels
  are declarations, never authentication. No trusted label or completion switch.
- Initial publications only; predecessor bundles and trusted storage are outside
  this minimal inspector. Optional expected content/manifest hashes detect stale
  bindings but never confer custody. Original context bytes have a separate digest.
- Monetary outputs are exact Decimal strings. No return-engine import/calculation.
  Calendar/session/identity declarations retain their unverified status.

## Discovered issues

None requiring existing-code changes. Provider custody, instrument/calendar/currency
authority, entitlement and adjustment/action semantics remain external blockers.

## Progress

- [x] 2026-10-16 baseline, index, protected hashes and scoped sources inspected.
- [x] Implement projection, fixture and CLI.
- [x] Run focused validation and examples.
- [x] Complete self-review and preservation audit.

## Test and validation strategy

Only new tests: exact raw strings/provenance, blocked split/dividend states,
explicit gaps, invalid context/identity/fingerprints/adjustment bases, stale
bindings, unknown availability, bounded local CLI and sanitized errors. Guard
network/writes and forbidden application imports. Run Python with -B, pytest
without cache provider; compile sources in memory. Check whitespace and hashes.

## Completion criteria

Seven-file scope only; focused tests pass with exact counts; synthetic stdout
examples run; protected and tracked baseline bytes unchanged; index empty.
Keep this approved active path for Astra review; no move to another directory.

## Final outcome

Implementation complete; READY FOR ASTRA REVIEW. The active plan stays at this
authorized path pending coordinator/reviewer action. No production admission.
Exactly the seven allowed files are new; all 281 tracked starting files retain
their starting SHA256 bytes. Original next-env/report changes are preserved.

### Actual validation (2026-10-16)

From backend:
`.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/test_market_history.py tests/test_inspect_market_history.py -q --tb=short`
Final result: **56 passed, 0 failures, 0 errors, 0 skipped**, 0.33s. Initial run
reported 52 passed and 2 setup errors with unbounded auto-generated parameter IDs
for large/deep byte inputs. Explicit short test IDs resolved the setup errors;
assertions were retained. First corrected run: 53 passed; additional exact-boundary
and file-replacement coverage brought the final total to 56. Existing normalizer
and return-engine suites were not rerun; no shared boundary changed.

In-memory ast.parse/compile checks passed for four new Python files; both new
production modules imported successfully under -B without bytecode output.
Actual CLI ordinary-fixture table and JSON commands in docs/market-data-history.md
both exited 0. Their output separates raw observations, unverified provenance,
blocked normalization, unsupported publication and unavailable returns. Null
availability, all three content identifiers and context digest were retained.

Fresh-process acceptance installs an audit hook before inspector import, forbids
network and write operations and database/model/provider dependencies, then runs
the real CLI with the existing synthetic fixture/context. It passed with no
forbidden application modules loaded. Additional tests patch all Python file opens
and sockets during pure projection, verify exact input bounds and missing rows,
and reject changed files, ambiguous context and stale sidecar/manifest pins.

Self-review checked strict decoder keys/types, inclusive date bounds, exact string
serialization, no calendar inference or gap fill, no custody/completeness switches,
sanitized stderr, and source/normalized/manifest hash separation. Initial
publications only; no predecessor decoding is exposed in this minimal context.

`git diff --check` passed. All seven untracked additions were separately checked
with `git -c core.autocrlf=false diff --no-index --check -- /dev/null <path>`:
no whitespace output (exit 1 indicates the new-file diff, not a whitespace error).
All protected hashes match the initial values above; main/HEAD unchanged and
index empty. No existing file modifications, data writes, external requests,
credentials, installation, service operations, staging, commit or push.

Real-data custody, independent identity/calendar/currency authority, provider
retention/display/redistribution rights and adjustment/action semantics remain
unresolved. See docs/market-data-history.md for the unchanged admission boundary.

Suggested eventual commit: `feat: add bounded offline raw-close history inspector`.

## P2 filesystem correction (2026-10-16)

Status: active; coordinator approved four-file correction, re-review pending.
Baseline reverified: main/434f30ab40204343e55451e673f6053890d04405, empty index,
seven task files untracked and all protected hashes unchanged. Captured hashes of
all 290 starting tracked/nonignored untracked files outside the repository in
session memory; only CLI, CLI tests, this plan and market-data-history.md may change.

Finding confirmed: leaf-first lstat can traverse a rejected ancestor before its
check. A separate read-only security-boundary investigator confirmed both CLI
inputs share this boundary and the previous test does not assert lookup order.

Correction plan:
1. Lexically reject unsupported Windows spellings; never resolve paths.
2. Require a direct local fixed-volume DOS mapping before directory traversal.
3. Preflight both ancestor chains, root to parent, before either leaf lookup/open.
4. Recheck ancestry before each read; reject leaf reparses/nonregular files using
   lstat metadata, retain identity checks and bounded reads.
5. Add mocked ordering/root/path/race regression tests, run only the two MD-01
   modules, syntax/import and synthetic table/JSON acceptance; inspect preservation.

Supported path reader: Windows, trusted quiescent trees on classified fixed roots.
Other platforms, removable/CD/RAM, substituted/redirected or unknown mappings fail
closed. Portable bytes-only projection is unchanged. No claim of race-proof or
OS/network containment; handle-relative stronger protection is out of this patch.

- [x] Baseline, focused investigation and patch contract.
- [x] Implement and test correction.
- [x] Candidate review, final validation and preservation audit.

Correction outcome: fixed within the approved operating conditions;
READY FOR ASTRA P2 RE-REVIEW. No commit or production admission.

Current verification:
- Two edited Python sources compile in memory under -B; CLI import succeeds.
- Focused security trigger/root/path/order subset: 65 passed, 29 deselected,
  no failures or skips. These deselections were then included in the full run.
- Full two-module MD-01 command (same as above): 136 passed, 0 failures/errors/
  skips, 0.38s. No completed normalizer/return/financial suites were run.
- Original relative synthetic table and JSON commands both exit 0. Response,
  normalized-content and publication-manifest hashes exactly match the prior
  acceptance values above. Table renderer source is byte-equivalent after newline
  normalization; projection/test/fixture files were not modified.
- Native workspace root metadata: QueryDosDeviceW D: ->
  `\Device\HarddiskVolume4`; GetDriveTypeW D:\ -> 3; classifier accepts it.
- All 290 baseline paths still exist; only the four authorized hashes changed.
  Index empty and whitespace checks pass for tracked diff and each untracked edit.

Mocked regressions prove exact root-to-parent/leaf order, no descendant query after
ancestor symlink/junction/other reparse rejection, stopping on missing/inaccessible/
non-directory ancestors, lexical alias rejection without IO, fixed/remote/SUBST/
unknown root classification and unavailable-API rejection. Both inputs preflight
before either leaf access; a parent changed after initial preflight is rejected
by the repeated check. The existing mismatched opened-file identity test is retained.
No test creates real remote shares or filesystem junctions.

The deliberate supported-platform restriction is Windows-only for this CLI reader,
with direct fixed-volume mappings and trusted quiescent trees. Python checks do
not lock directory ancestry or drive mappings: replacement after the final check
may cause a lookup/open before rejection. Python socket audit tests do not contain
Windows filesystem redirector traffic. No race-proof/network-containment claim.

Final review: one fresh read-only bypass/regression reviewer found no concrete
surviving bypass or regression in the supported trusted/quiescent Windows trees.
Reviewer performed source review only; this is not Astra's independent re-review.
Parent reran final syntax/import/root checks and the two-module test command:
136 passed, 0 failures/errors/skips. Only the four authorized files changed among
the 290 captured paths; all tracked files, other three MD-01 files, historical
evidence and protected hashes are preserved. main/HEAD and empty index unchanged.
Final diff/whitespace checks cover tracked and untracked changes separately.

Suggested correction commit, only if later authorized:
`fix: validate offline inspector ancestors before target lookup`.
