# AAPL registry publication interruption recovery

Status: completed (blocking recovery correction only; activation still disabled)
Roadmap phase: single blocking correction to disabled activation preparation

## Objective and context
Restore the exact previous owned registry references if either publication
assignment is interrupted, propagate the exception, and permit a valid retry.
Verified main / 1a78b4078455f58e8c8ca15b607d8d6866c9d1be. Activation preparation
remains uncommitted. Preserve its existing files, frontend/next-env.d.ts and both
runtime reports. Follow [instructions](../../../AGENTS.md),
[activation contract](../../aapl-net-margin-activation.md) and existing lock ownership.

## Constraints and non-goals
No real activation or source-gate change, authenticated operator implementation,
new registry architecture, persistent config, database/evidence writes, acquisition,
services, infrastructure audit, commit or push. Operator authentication remains an
unresolved prerequisite for real activation. Financial/evidence contracts stay intact.

## Implementation stages
1. Inspect writers/readers and lock boundaries; snapshot the prior policy/permission
   tuples and publish under a narrow BaseException recovery block inside the lock.
2. Restore only references still owned by this publication; never overwrite another
   owner's tuples. Lock-cooperating writers serialize; unlocked mutation is unsupported.
3. Inject before/after permission-store interruptions and ordinary exceptions; test
   exact restoration, repeated failures, retry, conflicts and synchronized peers.
4. Run focused existing suites and whitespace/inactivity checks; document reader
   visibility limits and unresolved operator authentication; stop before activation.

## Decisions and discovered issues
The only runtime writer of these two registries is this disabled entry point;
registry declarations are empty constants. Ordinary financial readers do not take
its lock. Policy-first publication is fail closed for the policy-only interval,
but two module assignments and recovery do not offer atomic visibility to readers.
Recovery must revoke the owned permission before restoring the owned policy.

## Progress
- [x] Baseline, assignment sequence and ownership inspected.
- [x] Recovery and adversarial regressions implemented.
- [x] Focused tests, preservation checks and self-review completed.

## Test and validation strategy
Only reversible fixtures enable wiring and provide detached read-only session data.
Real original bytes/receipts are read only. Assert true production emptiness/disabled
gate before isolation and after cleanup. Fault injection targets actual module
assignments using a test-only module subclass. Include serialized competing calls
under the existing lock and foreign-reference ownership protection. No live enabled
registration or repeated live audit is required.

## Completion criteria and final outcome
Implemented a narrow BaseException handler around only the two publication stores,
after all database/evidence validation and post-validation boundary checks. Under
the existing activation lock it snapshots previous references, publishes policy
before permission, and restores the owned permission before the owned policy if
interrupted. Policy cleanup is attempted in finally even if permission cleanup
raises. Ownership is reference identity, not equality. Original exceptions propagate
when cleanup completes; no failed publication returns success. No new registry
architecture, financial constants or authenticated operator mechanism was added.

Changed this turn: activation source, activation tests, activation contract and this
plan. Existing uncommitted preparation files remain preserved. Approved proposal,
adapter/evaluator/metric/calculation files have no diff against HEAD. Source gate
remains False. Reader visibility is explicitly non-atomic; legitimate runtime
writers must cooperate with this lock. Unlocked writes and additional interruptions
inside recovery are not guaranteed atomic. Real operator authentication remains
unresolved and blocks actual activation; the caller boolean/public reference is
not authority. No real activation or operator-boundary approval occurred.

Executed from backend with only command/test-process environment variables:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:FINLENS_REVIEW_SEC_ORIGINAL_STORE='D:\FinLens-OperatorReports\sec-original-evidence'
.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_aapl_net_margin_activation.py -q --tb=short
.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_aapl_net_margin_activation.py tests/test_aapl_net_margin_proposal.py tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py -q --tb=short
```

Results: **61 activation tests passed**; final focused regression **312 passed**,
exit 0, no skips. The 11 added cases inject KeyboardInterrupt/SystemExit/RuntimeError
before and after the actual permission store, check exact restoration of all five
observed registry/equivalence references, repeat interruptions three times and then
retry successfully, observe policy-only reader abstention, preserve different-owner
tuples with equal contents, and prove a lock-cooperating concurrent retry cannot be
overwritten. Existing conflict tests now assert reference identity preservation too.
All enabled calls used reversible detached fixtures; no enabled live DB registration.
Existing fixtures verify production emptiness before isolation and after cleanup.

Separate fresh-process Python import assertions confirmed source gate False, all
four production registries empty and global Revenue equivalences empty. Search of
backend/app found no activation importer/caller outside the entry-point definition.
The existing suites passed financial permission isolation, Gross Margin safeguards,
exact reviewed identities/versions including publication 0, current Net Margin and
historical Revenue unavailable-state regressions. No live parity/infrastructure/full
audit was repeated in this correction; current preservation evidence is focused
regressions and unchanged financial/evidence implementation.

Self-review and whitespace checks passed; new untracked files were also checked
using git diff --no-index --check against NUL (exit 1 indicates file additions,
not whitespace failure). Final main HEAD remains 1a78b4078455f58e8c8ca15b607d8d6866c9d1be.
Existing frontend/next-env.d.ts modification and both runtime reports preserved.
No database/config/evidence writes, network/model calls, restart, commit or push.
Suggested commit: recover interrupted disabled AAPL registry publication.
