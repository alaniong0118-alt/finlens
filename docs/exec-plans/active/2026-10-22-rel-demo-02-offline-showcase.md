# REL-DEMO-02: offline university showcase evidence package

Status: active; bounded content preparation complete. Task acceptance FAIL for an
execution-scope deviation; content CONDITIONAL; independent Astra High review pending.
Roadmap phase: evidence packaging for the university showcase, not runtime acceptance.

## Objective

Prepare a truthful six-minute script and machine-readable evidence inventory. Preserve
historical, synthetic, implementation, static-ML and failed acceptance boundaries.
Package acceptance must remain separate from browser/runtime acceptance and from a
human timed rehearsal, which is not authorized or performed.

## Current architecture and context

2026-10-22 baseline: main; HEAD and local origin/main both
`3d3a245a1919a255ae510b4bfe51b5421a476eba`; no staged changes. No remote query.
The only initial worktree exceptions are the modified frontend/next-env.d.ts and
the two original untracked AAPL reports named below. Private backend/.env is ignored.
Root AGENTS.md, ROADMAP.md and .agent/PLANS.md were read before editing.

## Exact scope and constraints

Only these three files may be created or changed:

1. docs/exec-plans/active/2026-10-22-rel-demo-02-offline-showcase.md
2. docs/showcase/university-showcase.md
3. docs/showcase/evidence-manifest.json

No fourth file, evidence copies, generated screenshots, persisted verifier or
external writes. Preserve all source, tests, historical records and existing files.
Never read private environment contents. No database/SQL, Docker, service, browser,
model/inference, acquisition/provider/network, installation, deployment or Git writes.
No renewed DEP-01A3, REL-GAP-01A or QA-RISK investigation.

Protected public SHA-256 baseline:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Private backend/.env preservation uses metadata only; contents and hash are not
read. This is not a cryptographic private-file integrity assertion.

## Implementation stages

1. Verify immutable Git baseline, exact worktree and preservation inventory.
2. Inspect selected retained evidence; hash it without changing or copying it.
3. Write the script and manifest with logical external references and explicit gaps.
4. Run bounded in-memory offline checks, reconcile all original fingerprints and
   exact three-file scope, self-review, then hand off for independent Astra High.

## Decisions

- Treat the operator's REL-DEMO-02 instructions as coordinator attestation that
  independent Astra High review passed the three REL-LEX-01 P2 corrections.
  The old keyword plan's pending-review wording is stale. Do not invent a separate
  retained review report or claim this task independently repeated the review.
- Keep external temporary and untracked local evidence NON-PORTABLE. Do not put
  personal usernames or private absolute paths in these files.
- A required visual/acceptance chain relying only on non-portable evidence is
  BLOCKED for portable showcase use even when currently available on this machine.
- New live execution remains NO-GO. No package check clears operational gates.

## Discovered issues

1. Critical S4 synthetic browser visuals are embedded in ignored local reporter JSON.
   S5's original accepted browser captures/report/summary live in temporary storage.
   Their current readability is not portability. S4/S5 are BLOCKED for the portable
   evidence-backed visual presentation; their portable textual fallbacks do not
   replace original browser evidence. No durable copies were verified or created.
2. The separate original REL-LEX-01 independent Astra re-review report is MISSING
   from the selected evidence set. The operator's explicit coordinator attestation
   is authoritative for the P2 PASS status. The old plan remains untouched and its
   pending wording is identified as stale. No timestamp or report hash is invented.
3. Seven selected tracked text files have CRLF checkout bytes distinct from their
   canonical Git blobs. Both SHA-256 values are recorded, and Git filtered object
   equality plus CRLF-only comparisons passed. This is not a source change.
4. **Execution-scope FAIL:** the first in-memory verifier called Python
   `tempfile.gettempdir()`. Inspection of the installed `_get_default_tempdir`
   implementation confirmed that its successful lookup creates a randomized file,
   writes four bytes and unlinks it before returning. That transient external write
   was unauthorized. The filename was not captured; no probe artifact was retained.
   No waiver or retrospective authorization is inferred. The final verifier reads
   the existing TEMP environment value without probing and denies Python write,
   delete, mkdir and other filesystem mutation audit events. Its clean result does
   not erase the original scope failure. No broad temporary-directory scan or
   destructive cleanup was performed.

## Progress

- [x] 2026-10-22: Git, protected public hashes and private metadata match baseline.
- [x] Root instructions, roadmap and ExecPlan requirements inspected.
- [x] Selected evidence inspected and manifest written.
- [x] Six-minute script and truthful fallbacks written.
- [x] Offline content verification, preservation and self-review completed.
- [x] Unauthorized transient temp probe recorded as FAIL, with non-probing final verifier.
- [ ] Independent Astra High review, separately controlled by coordinator.

## Test and validation strategy

Use installed PowerShell and Python standard library in isolated no-bytecode mode.
All verifier code is supplied in memory; do not create test scripts or reports.
Check hashes/existence, Git source bindings, JSON references, original outcomes,
ML matrix arithmetic, six planned segment intervals, fallbacks, privacy and scope.
Do not run application tests, imports, browser automation or a real timed rehearsal.
Actual commands, counts, gaps and results are recorded below.

### Commands and results actually executed

Working directory: repository root. All verifier payloads were supplied in memory;
no script, evidence copy or fourth repository file was saved. The inventory and
verifier outputs were returned to the conversation rather than written to disk.

Baseline/final Git commands:

```powershell
git --no-optional-locks status --porcelain=v1 --untracked-files=all
git branch --show-current
git rev-parse HEAD refs/remotes/origin/main
git diff --cached --name-status
git check-ignore backend/.env
```

Initial status was also inspected with ordinary `git status --short --branch`.
Observed main and expected HEAD/local origin/main; no staged changes; private file
ignored. No remote command was executed. Per selected tracked artifact, the
in-memory verifier invoked these read-only Git forms, substituting its relative path:

```text
git show HEAD:<repository-relative-path>
git rev-parse HEAD:<repository-relative-path>
git hash-object --path=<repository-relative-path> <repository-relative-path>
git show 0a042f91232182fa13503066ece8c21f494a2158:docs/news-sentiment-baseline.md
```

PowerShell `Get-FileHash -Algorithm SHA256 -LiteralPath <selected-path>` hashed the
25 selected physical evidence files and all 326 original inventoried non-env files.
Private backend/.env was inspected with `Get-Item -Force` metadata only, never
Get-Content/Get-FileHash. The exact shell invocation for the initial verifier was:

```powershell
$code | & '.\backend\.venv\Scripts\python.exe' -I -B -
```

The here-string `$code` was the in-memory standard-library artifact/JSON/claim/ML
verifier. It returned exit 0, **350 content checks PASS**, but its tempfile lookup
breached the execution scope. The subsequent diagnostic was source inspection only:

```python
import inspect, tempfile
print(inspect.getsource(tempfile._get_default_tempdir))
```

That diagnostic did not call gettempdir. Its returned implementation confirms the
four-byte write and unlink on the successful resolution path. No random filename
or event log was captured, so the report does not invent one.

Final corrected invocation:

```powershell
$code | & '.\backend\.venv\Scripts\python.exe' -I -S -B -
```

Final `$code` SHA-256, UTF-8 payload without a trailing newline:
`d9808bdca06d3f674f45640c0723b65f8dc64585caaba0ea54b14e94b53675cd`.
The payload was not persisted under the no-test-script restriction. It reads
`os.environ['TEMP']` for logical external locators, disables optional Git locks in
its child environment, and installs a write-denying audit hook before imports and
verification. Output: exit 0, **352 content checks PASS**, **zero final-verifier
Python filesystem mutation attempts**. This is a repeat of content checks after
correcting the verifier and failure disclosures, not 702 unique tests or a passing
task-scope result.

The actual checks covered:

- 28 unique artifact IDs: 25 physical files, two decoded-in-memory PNG attachments,
  one MISSING original independent-review report with coordinator attestation.
- All 25 physical files and both PNGs available; actual lengths and SHA-256 match.
- 18 portable tracked artifacts; nine available non-portable artifacts plus the
  missing original review report. Every segment's IDs resolve internally.
- Selected tracked Git identity, canonical blob hashes and seven CRLF-only working
  differences. Historical tested revisions remain UNKNOWN where not established.
- Six contiguous intervals exactly 0-30-120-195-255-330-360 seconds; script,
  output, proof limits, prohibited claims and fallback for every segment. These are
  planned allocations only, not measured speaking times.
- All Markdown file links resolve; all three new files contain no personal Windows
  username/private absolute path or credential-like assignment.
- Retained risk reporter: six expected cases, zero unexpected/flaky/skipped.
  Original QA-RISK-01 and single-cycle teardown conclusion retain FAIL.
- REL-SHOW-01D summary: PASS only for static historical analysis, zero retries;
  current HTML exactly matches accepted source SHA-256.
- Current historical aggregate block equals the frozen Git block. Matrix rows
  actual/columns predicted are [[53,17,14],[6,400,23],[8,31,139]]; total 691,
  diagonal 592, errors 99, supports 84/429/178; FP 14/48/37, FN 31/29/39.
  Recomputed accuracy 85.67293777134587%, macro-F1 0.7998327245268925;
  class metrics, displayed rounding, neutral baseline 62.0839%, negative recall
  63.0952% and the non-doubled error explanation agree. No corpus/model read.
- Content CONDITIONAL, portable showcase BLOCKED, live execution NO-GO, timed human
  rehearsal NOT TESTED, independent package review PENDING and execution scope FAIL
  remain separate classifications.

Preservation reconciliation after writing the package: all **326 original
inventoried file SHA-256 values unchanged**, private metadata unchanged and exactly
the three authorized new repository paths. Selected original evidence hashes also
passed rechecking. No test suite, app import, browser, service, container, database,
model, corpus, network/provider or deployment operation was executed.

Final document self-review also parsed JSON, checked the separate FAIL/CONDITIONAL/
BLOCKED gates, scanned all three authorized files for private absolute locations,
and checked LF termination/no trailing whitespace with a write-denying Python hook:
PASS. Per-file `git diff --no-index --check -- /dev/null <authorized-file>` emitted
only the existing LF-to-CRLF advisories, exit 1 for the new-file differences, and no
whitespace-error diagnostics. Those exit codes are not presented as passing tests.
Final full file hashes and exact unstaged new-file numstats are returned in the
engineering handoff; no self-referential file hash is embedded in this plan.

## Completion criteria

Exactly the authorized three files; valid manifest and resolvable logical IDs;
truthful claim boundaries/fallbacks; unavailable/non-portable evidence marked;
original PASS/FAIL/NOT TESTED states retained; historical ML arithmetic agrees;
all original fingerprints and private metadata preserved. Preparation may finish
CONDITIONAL with portable segments BLOCKED. Astra review remains a separate gate.

## Final outcome

Exactly the three authorized repository documents/artifacts are prepared. No
application behavior changed. Content-package verdict **CONDITIONAL**; portable
full-showcase verdict **BLOCKED**; overall task execution acceptance **FAIL** because
of the unauthorized transient temp probe. The corrected final verifier does not
supersede that failure. No staging, commit or push occurred.

Remaining December 15 risks: loss of temporary/ignored browser artifacts; missing
original keyword re-review record; absent current keyword browser acceptance;
unaccepted current repaired-risk/real-data runtime; unresolved database identity,
trusted encoder admission and immediate teardown failures; independent package
review and real human timing not completed. Do not reopen those runtime
investigations or infer a live path from this documentation task.

Coordinator handoff: request independent Astra High read-only review of these exact
three unstaged files, actual artifact/source binding, script claim boundaries,
portability BLOCKED decisions, historical FAIL preservation and the recorded
execution-scope deviation. Astra review does not grant a waiver, authorize copying,
or permit runtime or Git actions. Operator decides how to disposition the scope
failure; no further file or evidence movement is proposed or performed here.

After separate review/authorization only, suggested commit title:
`docs(showcase): bind university walkthrough to retained evidence`.
