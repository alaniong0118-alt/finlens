# Post-READY maintenance lease admission correction

Status: completed
Roadmap phase: targeted correction to disabled activation safety only

## Objective and baseline

Preserve main `d6173d0dd962360b5b2b4f13b2827f2383becbe6` and the existing
uncommitted 14-file infrastructure patch. Correct Astra G/H/I: READY must require
live maintenance ownership at admission and result delivery, with terminal
quarantine and fail-stop even when marking failure throws. Preserve unrelated
frontend/runtime reports, all reviewed evidence/formulas and the false gate.

## Constraints

Offline synthetic tests only. No real registrations, operator/store configuration,
deployment fencing, services, database writes, network, artifacts, commit or push.
Production maintenance provider remains rejecting. No redesign of approved A-F.

## Implementation stages and decisions

1. Define fresh authoritative `assert_held` and loss subscription contract. Latch
   loss independently of fallible quarantine marking; terminate on detection.
2. Check financial entry/exit, HTTP/WebSocket admission/receive/send, and lifecycle
   transitions. Inactive processes do not acquire activation lease requirements.
3. Test revocation/expiry/renewal/ownership failures, in-flight operations, races,
   repeated faults and actual disposable-process termination.
4. Update the contract with exact timing/transport limitations; run focused
   regression, syntax, whitespace and registry checks; self-review and report.

The lifecycle lock serializes its own transitions/checks, not external lease
revocation or async transport writes. Future providers must publish invalidity
before notifying, deliver notifications promptly outside their ownership locks,
and never return cached validity. No claim of instantaneous/retractable delivery.

## Progress and validation

- [x] Read request/instructions; confirm Git and relevant READY defect.
- [x] Implement and test bounded correction: live entry/exit and transport checks,
  loss subscription, irreversible poison latch and finally-based termination.
- [x] Record focused results, final invariants and limitations; self-review.

## Checks actually run

From `backend`, with `PYTHONDONTWRITEBYTECODE=1`, Python `-B` and
`-p no:cacheprovider`; the process-only review-store variable was absent:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_activation_lease_admission.py tests/test_aapl_activation_safety.py -q
```

136 passed (38 new lease cases and 98 existing safety cases), one existing
Starlette deprecation warning.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_activation_lease_admission.py tests/test_aapl_activation_safety.py tests/test_aapl_net_margin_activation.py tests/test_aapl_net_margin_proposal.py tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py tests/test_financial_metrics.py tests/test_research_answers.py tests/test_historical_research_answers.py -q
```

859 passed, 90 skipped in 11.83 seconds. Skips are opt-in external original-store
cases; no original retrieval or live parity was repeated. Existing Starlette and
SQLAlchemy deprecation warnings remain. Synthetic regression fixtures use
disposable test data; no production database was accessed or changed.

Four disposable child interpreters (polling/notification, with/without quarantine
marking fault) genuinely terminated with code 78, no stdout/stderr and no server
or production registrations. Fresh-interpreter checks confirmed literal false
gate, four empty registries, empty global equivalences and no lifecycle claim.
AST syntax checks passed for the five correction Python files. `git diff --check`
passed; explicit newline/trailing-whitespace checks include untracked source files.

## Self-review and remaining limitations

No formula, mapping, evidence pin, registry ownership or financial source changes
were made in this correction. Existing direct guards are reused. A-F operator,
deployment, publication and startup behavior remain intact. Inactive requests
retain no lease requirement and no additional evidence I/O.

Authoritative checks are synchronous under the lifecycle lock; a future provider
must bound their duration and invoke loss callbacks outside provider locks. The
lock cannot synchronize external revocation with asynchronous transport commit.
Check-to-return/send windows and already accepted bytes remain explicit limits.
Real provider implementation and its freshness/monitor latency guarantees remain
blocked pending independent review. Astra G/H/I should review live boundary
checks, monotonic notification/failure, repeated quarantine faults and these limits.

## Completion criteria

Synthetic post-READY loss denies financial results and irreversibly quarantines;
direct operations check before returning; ASGI boundaries recheck ownership;
callbacks fail-stop even if quarantine fails; default inactive outputs unchanged;
empty real registries and false source gate; no prohibited operations.

## Final outcome

Completed bounded correction without activation. Seven correction files: lifecycle,
ASGI launcher, provider contract comments, existing synthetic safety fixtures, new
lease regressions, activation contract documentation and this plan. HEAD remains
`d6173d0dd962360b5b2b4f13b2827f2383becbe6` on main. The prior uncommitted patch,
frontend/next-env.d.ts and both runtime reports are preserved. No persistent
configuration, live database/network/service, artifact, commit or push operations.
Suggested commit after review: `fix: enforce live maintenance ownership for financial admission`.
