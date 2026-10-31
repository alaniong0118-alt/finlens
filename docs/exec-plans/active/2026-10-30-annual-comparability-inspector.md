# Annual Comparability Inspector — bounded 4c/D6 increment

Status: active — approved focused runtime verification passed; independent re-review pending.
Roadmap phase: Complete Research Mode; bounded consumer of the CC-02 annual contract.

## Objective

Add an accessible disclosure for each of the existing eleven annual metrics that
puts the selected companies' observed periods, reported revenue bases, operand
periods/bases and missing/excluded reasons together. Differences and unknowns must
remain visible; matching metadata never establishes financial equivalence.
This increment does not complete requirements 4c or D6.

## Current architecture and context

Read [root guidance](../../../AGENTS.md), [plan rules](../../../.agent/PLANS.md),
[engineering standards](../../engineering-standards.md), [roadmap](../../../ROADMAP.md),
[requirements 4c/D6](../../full-feature-requirements.md),
[financial contracts](../../financial-metrics.md#annual-company-comparison-cc-02),
the [CC-02 plan](2026-10-16-cc02-annual-metric-expansion.md), client types,
comparison implementation, existing mounted tests and guarded serialization fixtures.
No nested AGENTS.md or .agents/skills exists in the relevant repository paths.

Starting main HEAD: `b66c73e7ee5e091561a881f4fa7bdfa6f2e30e52`; index empty.
Only the three supplied protected exceptions exist; their SHA-256 values match:

| Protected path | SHA-256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

The plan path was absent before creation. Existing comparison owns validation,
independent publication pins, aggregate notices, raw reasons, source disclosures,
copy-note eligibility and synchronous focus reveal within horizontal scrolling.
Derived metric revenue bases belong to explicit revenue operands; do not borrow
another metric's basis or infer basis from concept, issuer or equal amounts.

## Constraints

Exactly four writable paths: this plan, frontend/lib/company-comparison.ts,
frontend/components/company-comparison.tsx, frontend/tests/company-comparison.test.mjs.
Keep all changes unstaged. No backend/.env access (including implicit test loading),
protected-file contents, frozen PostgreSQL files, unrelated temporary discovery
files, database/network/model operations, services, browsers, installations,
dependencies, build output, security changes, Git delivery or extra agents.
Stop on denial or an unexplained starting-state difference; do not broaden scope.

## Non-goals

No formulas, ranking, metric expansion, currency conversion, eligibility inference,
new requests, schemas, identity/source metadata, API/backend changes, runtime or
native accessibility acceptance. No reopening completed CC-02/C5 reviews.

## Implementation stages

1. Verify starting state and inspect relevant guidance/contracts/test execution.
2. Add pure observed-metadata diagnostics and per-row native details disclosures.
3. Add focused fixtures covering differing/missing dates and bases, exclusions,
   exact raw reasons, ownership changes, source/copy behavior and no extra requests.
4. Run affected test file, scoped lint and no-output TypeScript checks; self-review
   diff and verify HEAD/index/scope/protected hashes. Return candidate for separate
   independent review. Recovery is limited to this increment's diff; no data changes.

## Decisions

- 2026-10-31: Use native details/summary with existing provenance styles in each
  metric row header, preserving table structure, horizontal scroll and focus reveal.
  Group verified companies plus explicit unverified errors in the same disclosure.
- 2026-10-31: Compare only observed dates and exact nonempty revenue-basis labels
  on the metric and revenue operands. Explain unknown basis for revenue-dependent
  rows; absent metadata on other rows is not evidence of financial equivalence.
  Preserve all reasons/labels as text, with no interpretation of free-form codes.
- 2026-10-31: Coordinator-directed static-review correction: reject non-string
  operand metric labels before a response can reach the inspector. Unknown strings
  remain accepted verbatim, with no allowlist or financial-policy change.

## Discovered issues

Existing test subprocesses import backend configuration. Installed python-dotenv
supports PYTHON_DOTENV_DISABLED=1; use it before running the affected test file so
backend/.env is never loaded. Supply only synthetic process-local database config;
the inspected serializers construct synthetic FinancialMetrics objects, guard live
dependencies and do not invoke application startup. CommonMark subprocesses read
stdin and render locally. No test subprocess additions are planned.

The ordinary Node suite failed before test-body execution: test worker creation
returned `spawn EPERM`. The required escalation retry waited for approval and
terminated with `CreateProcess ... Rejected("rejected by user")`. No test worker
or synthetic Python fixture was run, and no pass evidence exists. No further
escalation or retry was attempted after rejection. No ACL/config/isolation changes.

The coordinator supplied an independent static REVISE finding: input.metric was
newly rendered without runtime string validation, so a malformed object could crash
React even in a collapsed disclosure. After the pending request was definitively
rejected, all four source hashes matched the review binding before editing. Added
the string guard and two mounted regressions for malformed-column containment and
unknown string preservation. These regressions have not executed. The component
bytes remain unchanged from that static review.

Final static self-review also found existing new test expectations with title-case
labels that disagree with research.ts sentence-case labels: the earlier exclusion
test uses `Gross Margin`, and the four-company inspector test expects title case
for nine labels. These would need correction before a green suite can be claimed.
They remained unchanged in the previous handoff because the coordinator lifted the source freeze only for
the concrete operand-metric P2 and its regressions. The new P2 regression uses the
actual `Free cash flow` label. Report these static test issues for coordinator
disposition; do not treat unexecuted tests as passing.

## Progress

- [x] 2026-10-31: Starting state, protected hashes, plan absence, scope and relevant
  documentation/fixtures inspected.
- [x] Implement diagnostics and eleven native per-row disclosures.
- [x] Add eight inspector regressions and two P2 regressions; retain existing
  assertions and explicitly target original cell controls in provenance focus tests.
- [x] Correct coordinator-reported P2 after approval request reached terminal rejection.
- [x] Scoped ESLint and TypeScript checks passed on the corrected candidate;
  read-only diff/self-review completed. Preservation checked before correction;
  final scope/hash evidence accompanies the handoff.
- [x] 2026-10-31 closeout: correct the two reported test-expectation defects using
  established research.ts labels; preserve production labels and P2 implementation.
- [x] 2026-10-31: Receive fresh explicit approval and execute the exact corrected-
  candidate focused command once: 260 passed, zero failed/skipped, exit 0.
- [ ] Targeted independent Astra correction review remains outstanding. No Git GO.

## Test and validation strategy

Actual commands/results (2026-10-31), cwd `D:\Projects\finlens-foundation\frontend`:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:DATABASE_URL='postgresql+psycopg://fixture:private@127.0.0.1/fixture'
$env:FINLENS_SERVER_PROFILE='development'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
node --test tests/company-comparison.test.mjs
```

Ordinary execution: exit 1; one file-level failure at worker spawn, zero passes,
zero test bodies executed. Escalated request for this exact command/cwd: rejected
by user before process creation. Requested permission was require_escalated;
justification: "Allow the inspected offline comparison test file to spawn its Node
test worker and existing guarded synthetic Python fixtures? The sandbox blocked
worker creation with EPERM; dotenv loading is disabled and no server, database,
network or model work is requested." No further retry. Suite: **NOT VERIFIED**.

```powershell
.\node_modules\.bin\eslint.cmd lib/company-comparison.ts components/company-comparison.tsx
```

Passed, exit 0, no diagnostics, before and after the P2 correction (second run
justified by the new validator change).

```powershell
node -e 'const ts = require("typescript"); const config = ts.readConfigFile("tsconfig.json", ts.sys.readFile); if (config.error) { process.stderr.write(ts.flattenDiagnosticMessageText(config.error.messageText, "\n")); process.exit(1); } const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, process.cwd(), { noEmit: true, incremental: false }); const program = ts.createProgram(["lib/company-comparison.ts", "components/company-comparison.tsx"], parsed.options); const diagnostics = [...parsed.errors, ...ts.getPreEmitDiagnostics(program)]; if (diagnostics.length) process.stderr.write(ts.formatDiagnosticsWithColorAndContext(diagnostics, { getCurrentDirectory: ts.sys.getCurrentDirectory, getCanonicalFileName: p => p, getNewLine: () => "\n" })); else process.stdout.write("Scoped TypeScript: 0 diagnostics (2 roots; no emit or incremental output).\n"); process.exit(diagnostics.length ? 1 : 0);'
```

Passed before and after P2: exit 0, zero diagnostics, two roots with imported
dependencies, no emit/incremental output. This is static checking only.

From repository root with process-local GIT_OPTIONAL_LOCKS=0: git diff --check
passed (Git emits LF/CRLF advisory warnings); exact scoped diff and numstat reviewed.
`node --check tests/company-comparison.test.mjs` passed, exit 0; syntax only,
no test bodies executed. Final read-only status confirms exactly four candidate
paths plus the three protected exceptions, unchanged main/HEAD and empty index.
All three protected SHA-256 values still match the starting table; their contents
were never read. The new plan has no trailing whitespace.
No build, browser, zoom, assistive-technology, real-data/API or complete D6 acceptance.

## Completion criteria

Observed metadata and unknowns are inspectable for all eleven rows; missing,
excluded and unverified participants remain explicit; no inferred financial
equivalence or eligibility; reasons preserved exactly as inert text. Existing
validation, pins, formatting, lineage, copy behavior and focus reveal preserved.
Focused checks pass or limitations are explicit. Exactly four-path candidate,
unchanged HEAD/empty index/protected hashes, and separate review still pending.

## Final outcome

Four-path candidate prepared with the coordinator's concrete P2 correction and the
subsequently authorized test-label corrections. After fresh explicit approval, the
focused dynamic suite executed once and passed all 260 tests, exit 0; no failures
or skips. Prior static checks passed and were not rerun during runtime verification.
Targeted independent correction review remains pending. No complete D6 acceptance
or Git GO. The approval and exact result follow in the chronological record below.
Plan stays at this authorized active path. HEAD remains
`b66c73e7ee5e091561a881f4fa7bdfa6f2e30e52` on main, index empty; no Git delivery.
Only the four candidate paths plus three protected exceptions are in status.
All protected hashes matched at entry, before correction and in final verification;
raw candidate SHA-256 evidence is supplied with the handoff. No backend/.env access,
operational work, frozen-file access or unrelated cleanup.

Suggested eventual commit: `feat: inspect annual metric comparability limits`.

## P2 closeout and corrected-candidate verification — 2026-10-31

The follow-up request explicitly authorizes correction of both previously reported
label-expectation defects, scoped static checks and preparation of a fresh runtime
approval request. The prior rejection remains effective for runtime execution.

Preflight: main/HEAD and empty index match the earlier handoff. All four raw
candidate hashes match that handoff; only the expected seven paths are in status.
All protected hashes match their recorded baselines. App task state reports the
prior turn completed and current turn active without approval flags; the earlier
test request is terminal/rejected. Agent inventory contains only the current root
writer. No overlapping old test or writer was identified.

The existing `typeof input.metric !== "string"` rejection already precedes response
publication. It requires no further production change. Existing mounted P2 tests
cover malformed-object containment, valid peer visibility, disabled copy, and exact
unknown string rendering as inert text. No duplicate regression was added.

Corrected two test expectations against METRIC_CATALOG / METRIC_LABELS in
frontend/lib/research.ts: `Gross Margin` becomes `Gross margin` for the existing
copy eligibility assertion; the four-company summary assertion uses established
sentence-case metric labels. Exact equality, four-participant counts, closed
disclosure states and all other assertions remain intact. Production labels,
financial values, reasons, period/basis semantics and requests are unchanged.

Actual closeout checks, using exactly the earlier recorded commands:

| Check | Working directory | Outcome |
|---|---|---|
| Local ESLint on lib/company-comparison.ts and components/company-comparison.tsx | frontend | Exit 0; no diagnostics |
| Recorded TypeScript compiler-API command with the same two roots, noEmit=true, incremental=false | frontend | Exit 0; zero diagnostics; no emit/incremental output |
| git diff --check | repository root, GIT_OPTIONAL_LOCKS=0 | Exit 0; only existing LF/CRLF advisory warnings |

Final self-review confirms only the two authorized expectation lines changed in
the test during this closeout. The production library/component raw hashes remain
identical to the previous handoff. Current source scope, main/HEAD, empty index and
protected hashes are rechecked at handoff. No runtime test body has executed during
this closeout; test/pass/fail/skip counts for this corrected candidate are unknown.
Historical worker-spawn failure counts above are not runtime acceptance counts.

Fresh approval outcome: pending. The current tool environment has no interactive
elevation approval facility; no sandbox_permissions parameter or equivalent
workaround will be used. The final handoff requests explicit user approval in chat
for one execution of the exact earlier Node command, from the same frontend cwd,
with the exact process-local offline/dotenv-disabled synthetic settings recorded
above. Requested scope is spawning the Node test worker and existing inspected
synthetic Python fixtures only. The changed environment is not approval and the
previous rejection is preserved. No runtime attempt, alternate runner, isolation
change, permission modification, build, browser, live API or PG work occurred.

The candidate remains BLOCKED pending that fresh approval and focused test-body
execution. P2 and label corrections are prepared for targeted independent Astra
re-review, with runtime evidence explicitly outstanding; no full acceptance or
Git progression is authorized. Stop after the necessary approval request.

## Freshly approved single runtime verification — 2026-10-31

The user explicitly approved ONE corrected-candidate run of the exact command and
all six environment assignments recorded above, from
`D:\Projects\finlens-foundation\frontend`. Approval covers only the Node worker
and existing inspected synthetic Python fixture subprocesses. Environment settings
are confined to the task shell and its children; no persistent configuration.
This approval does not retroactively authorize the historical rejected request
and grants no standing permission for another run, Git delivery or operations.

Immediately before execution, read-only checks confirmed main at
`b66c73e7ee5e091561a881f4fa7bdfa6f2e30e52`, empty index and the expected seven-path
worktree scope. Both production hashes, the test hash and the plan hash matched
the immediately preceding handoff; all three protected hashes matched their
recorded baselines. No source or test edits were made during this verification.

Executed exactly once from frontend:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:DATABASE_URL='postgresql+psycopg://fixture:private@127.0.0.1/fixture'
$env:FINLENS_SERVER_PROFILE='development'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
node --test tests/company-comparison.test.mjs
```

Actual result: **exit 0; 260 tests, 260 passed, 0 failed, 0 skipped, 0 cancelled,
0 todo, 0 suites; duration 26811.3061 ms**. Test-body execution occurred, including
both the malformed operand containment regression and the unknown-string inert
text regression. All ten new inspector/P2 regressions passed alongside the
existing comparison, provenance, publication, copy and focus regressions.
No assertion failure or process-creation failure occurred in this approved run.
Only the same running command was awaited; no rerun, alternate runner, isolation
change, broader permission request or repeated static check was performed.

Only this ExecPlan is updated during verification. Final read-only diff statistics,
candidate raw hashes, index/HEAD/status and protected hashes accompany the handoff.
Historical EPERM and rejection evidence above remains unchanged. The corrected
candidate is ready for targeted independent Astra re-review; the implementation
does not self-approve that review or authorize staging, commit or push. Native
browser/mobile/zoom/assistive-technology, real-data/API, PostgreSQL and complete D6
acceptance remain outside this evidence. Stop after the result report.
