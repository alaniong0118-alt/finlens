# Standalone two-filing mounted-suite lifecycle

Status: active; implementation validated and frozen for independent review
Roadmap phase: close existing integration; no feature expansion

## Objective

Deliver G's two-filing test lifecycle correction as a complete HEAD-relative
candidate, without inheriting held report/passage features. Preserve the accepted
A-D/F candidates, original G preimages/receipts and all existing dirty files.
Demonstrate real mounted-suite ownership/restoration with regression controls.

## Current architecture and context

Read AGENTS.md, ROADMAP.md, .agent/PLANS.md, engineering standards, the active
delivery assessment and the completed frontend combined-validation plan.
Recorded HEAD is `17be7b5ba856a6b881a79c2c778bb6bf85eca297`. No Git operation is
used: raw HEAD/ref/index hashes and the accepted F HEAD archive supply inspection
evidence. Fresh Git status/index interpretation is unavailable under the inherited
restriction. Existing mixed two-filing test contains F/G plus held product work.
It must remain unchanged; deliver only the external reconstructed candidate.

## Constraints

No staging/commit/push, Git/ownership workaround, settings/credentials/ACL changes,
network/download/install/provisioning, database operation or new infrastructure.
Do not retry the previously denied build route. C5 remains unexecuted. Use the
installed Node no-isolation runner and dependencies. Synthetic/JSDOM checks are
not native-browser, visual, live database or provider evidence.

## Non-goals

E's private persistence stack; G's held report/passage parents; new product scope;
full repository test/release acceptance; browser/build acceptance through a new
execution route. Do not substitute full working files for partial candidates.

## Implementation stages

1. Hash current source, prior evidence and raw Git metadata; verify immutable HEAD.
2. Reconstruct only G suite hooks/descriptor restoration/mount guard over HEAD;
   add a focused regression with absent and non-default incoming descriptors.
3. Run full candidate suite, regression profiles, failure controls, adjacent pure
   suites, types/lint and exact F-overlay compatibility using retained snapshots.
4. Freeze exact full/partial manifest, patch, receipts, preservation and limits.

## Decisions

2026-11-13: Select the smallest coherent G slice. Report and passage test files
are absent at HEAD and need their own product parents; they are not required for
two-filing DOM lifetime ownership. Preserve HEAD's existing test callbacks and
its serializer-spelling assertion. In F compatibility only, use F's independently
accepted removal of that assertion. No production expression changes belong to G.

## Discovered issues

The previously accepted G lifecycle fix is incremental over dirty feature
preimages. Current full files cannot be delivered under that review. A fresh
HEAD-specific candidate and actual full-candidate tests are required.

The initial new regression imported ReactDOM before installing a document. React
cached its no-DOM event path, producing 86 product-case failures. Removing that
early import fixes the harness without changing the candidate or assertions.
The original HEAD control's descriptor failure made TAP inspect a closed JSDOM
window and crash (exit 7). Primitive presence/flag/identity assertions retain
the same check and report readable failures. Initial snapshots/receipts remain.
The final regression additionally checks an accessor descriptor.

Initial broader cohorts each had one missing-sqlalchemy fixture failure because
the snapshot lacked the installed backend environment and the legacy guided
question regression selected system Python. Link the existing backend .venv into
the two final snapshots, as in F's accepted reproduction. The unchanged guarded
regression then passes. No installation, test skip or assertion change occurred.

## Progress

- [x] Read governing/current assessment and select coherent scope.
- [x] Preserve baseline and reconstruct candidate.
- [x] Execute positive/negative and compatibility checks.
- [x] Self-review, freeze and report residual gates.
- [ ] Separate independent review of the complete reconstructed G candidate.

## Test and validation strategy

All commands use `backend/.venv/Scripts/python.exe -I -S -B` to invoke external
`run_case.py <label> <snapshot> <mode> <arguments>`. Child executable, exact argv,
snapshot cwd, UTC timestamps, exits, timeout state and raw output digests are
stored in each `*-command.json`. Tests use installed `E:/node.exe --test
--test-isolation=none --test-reporter=tap`. No timeout occurred.

Actual final checks (overlapping counts must not be added):

| Label | Arguments / result |
| --- | --- |
| standalone | `tests/dual-filing-evidence.test.mjs`: 61 passed, exit 0 |
| full-candidate-fixture-complete | `tests/dual-filing-evidence.test.mjs tests/dual-filing-lifecycle.test.mjs tests/research.test.mjs tests/sec-risk.test.mjs tests/sec-risk-comparison.test.mjs`: 469 passed, zero failed/cancelled/skipped/todo, exit 0 |
| F-compatibility-fixture-complete | Same cohort plus `tests/context-text-fidelity.test.mjs`, exact accepted F overlay with G hooks applied to F's partial two-filing test: 504 passed, zero failed/cancelled/skipped/todo, exit 0 |
| baseline-final | Unmodified HEAD two-filing test plus final new regression: 61 passed, 1 descriptor-presence failure, 63 cancelled after the expected read-only act-flag before-hook failure; exit 1 |
| no-restoration-control | Only remove descriptor restoration: all 122 repeated product cases pass, three lifecycle checks fail, no cancelled/skipped cases; exit 1 |
| root-hook-control | Only remove the enclosing suite: all 122 repeated product cases pass, three lifecycle checks fail, no cancelled/skipped cases; exit 1 |
| types | `node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0 |
| lint | `node_modules/eslint/bin/eslint.js tests/dual-filing-evidence.test.mjs tests/dual-filing-lifecycle.test.mjs`: exit 0 |
| assertion-preservation | Espree verifies all 28 syntactic test registrations, complete callback bodies, arguments and order equal HEAD; F/G equals F's same 28 registrations. Loops expand to the unchanged 61 product cases; exit 0 |

The new regression runs the complete mounted suite twice: absent incoming globals,
then a live neighboring document with read-only data and accessor descriptors. It
checks exact descriptor presence, flags and identities and mounts/clicks a real
React button in the restored neighbor realm. The broader research suite includes
its unchanged guarded Python subprocess using synthetic financial facts and fake
session persistence. SQL/network/.env are denied by that test's existing guards.
This is not backend/live database/HTTP/provider acceptance. Existing Node module
type warnings remain; package/lock/config are unchanged.

The initial failing/new-harness and fixture-incomplete receipts remain separate.
`candidate-initial.json`, v2 and final-regression successor records distinguish
all iterations. Only final snapshot/regression bytes are deliverable.

## Completion criteria

Complete HEAD-relative closure, no dirty production dependency, unchanged test
callbacks, observed defect controls, passing full candidate and F compatibility,
exact candidate identities/partial-file boundary and preservation checks. A
separate independent review remains a later gate; this author cannot claim it.

## Final outcome

Implemented one standalone G lifecycle slice; independent review remains pending,
so this plan stays active. Evidence root:
`D:/Projects/finlens-G-lifecycle-20261113`. `delivery-manifest.json` and
`delivery-final.patch` bind exactly three proposed paths. Two are full new files
(this plan and `frontend/tests/dual-filing-lifecycle.test.mjs`); the existing
`frontend/tests/dual-filing-evidence.test.mjs` is a PARTIAL reconstruction. Never
substitute its mixed working-tree file. `candidate-final/` holds exact proposed
bytes. `review-freeze.json`, `verify_freeze.py` and `reproduce.py` are review entry
points; original evidence and failed attempts remain immutable.

No production source changed. All existing repository paths except the two newly
owned files, all captured A-D/F/G and E evidence and all raw Git metadata are
checked against entry. Source closure is HEAD plus the two test files only;
no package/config change or dirty runtime dependency is included. F compatibility
is distinct from a prerequisite and preserves F's accepted partial boundaries.
The compatibility two-filing result is a composed successor, not a replacement
for either immutable accepted F bytes or the original G dirty-preimage receipt.

Remaining: independent review, future exact HEAD/index/scope preflight and explicit
delivery authorization. E and G report/passage feature parents remain held. C5 is
UNEXECUTED; no Git/ownership fixture was selected/retried/rerouted. Full frontend
suite, production build, native browser/responsive/accessibility, live SQL/storage,
source/model/provider, printing, release and publication are not accepted. The
prior denied build route was not retried through any route. Native browser checks
would not validate a Node test-global lifecycle and no product UI changed here.
No staging/commit/push/settings/credentials/ACL/database action occurred. Fresh Git
status remains unavailable; raw metadata equality does not claim current remote
or staged-scope acceptance. Suggested eventual commit after delivery authorization:
`test(frontend): isolate two-filing mounted suite lifetime`.
