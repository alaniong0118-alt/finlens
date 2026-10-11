# Disabled AAPL activation safety infrastructure

Status: completed (disabled infrastructure only; real activation remains blocked)
Roadmap phase: bounded safety prerequisite; no activation or later milestone

## Objective

Implement an inactive same-interpreter operator bootstrap, terminal lifecycle,
financial-reader exclusion and ASGI admission checks. Keep the literal activation
gate false and all production registries empty. Actual deployment trust and
maintenance exclusion must fail closed if they cannot be established here.

## Current architecture and context

Baseline main `d6173d0dd962360b5b2b4f13b2827f2383becbe6`. The activation helper
validates before two registry assignments and restores owned references on
BaseException, but has no authenticated operator, admission or fatal-recovery
boundary. Ordinary startup does not call it. Preserve modified
`frontend/next-env.d.ts` and the two untracked backend canary/discovery reports.

## Constraints and non-goals

No production registration, gate enabling, persistent configuration, original
evidence changes, network, live DB access/writes, services, commit or push. No
financial formulas/mappings or reviewed pins change. Enabled tests use detached
synthetic data and reversible module substitutions only.

## Implementation stages

1. Add private one-shot lifecycle and direct-reader admission boundaries.
2. Add Windows process-token identity and strict protected-policy interface.
   Unproven deployment ACL/integrity and maintenance exclusion remain rejecting
   production boundaries, never caller assertions.
3. Add same-process bootstrap and ASGI readiness/lifespan wrapper. Require exact
   registry verification before readiness; failed launches terminate nonzero.
4. Add offline adversarial tests, run focused regressions and whitespace checks.
5. Self-review and document precise deployment blockers; complete this plan.

## Decisions

- 2026-10-11: no general registry service or live activation. Bootstrap precedes
  the server, freezes publication afterward, and blocks financial consumers.
- Production ACL/dependency integrity and all-writer/store maintenance controls
  are not established by the current architecture. Implement explicit rejecting
  boundaries and document what a later independent review must prove.

## Discovered issues

Research answers and sync coverage construct FinancialMetrics directly; guarding
only HTTP routes or the dataset loader is insufficient. Existing recovery tests
permit isolated retries; production bootstrap will instead be terminal on fault.

## Progress

- [x] Read instructions and relevant source; confirm baseline and preserved files.
- [x] Implement bounded infrastructure and isolated tests.
- [x] Run focused regression and self-review; confirm disabled controls and scope.
- [x] Run tracked and new-file whitespace checks and fresh-process invariants.

## Test and validation strategy

Fake server runner and synthetic detached SEC/database fixtures only. Cover
identity/profile rejection, server configuration, exact publication, lifecycle,
direct readers, HTTP/WebSocket/lifespan, secondary faults and process termination.
Run activation/proposal/adapter/authorization/financial/consumer regressions as
justified by guarded entry points. Tests must assert original empty registries
before monkeypatch isolation. Record actual commands and results here.

## Completion criteria

Literal false gate and production emptiness preserved; no serving on fault;
one-shot lifecycle; exact final permission boundary; synthetic tests pass;
remaining ACL/integrity and maintenance controls clearly block real activation.

## Final outcome

Implemented Windows TokenUser SID retrieval, strict profile/pin validation with
rejecting ACL/deployment-integrity boundaries, an uncommissioned maintenance
lease provider, one-shot lifecycle/direct-reader guards, same-interpreter launcher,
exact post-publication checks and HTTP/WebSocket/lifespan admission. Secondary
recovery faults never start a server; the operator CLI and background ASGI failure
paths hard-exit nonzero. No source gate, proposal/pin or registry declaration changes.

Validation from `backend/`, process-local PYTHONDONTWRITEBYTECODE=1 and without
FINLENS_REVIEW_SEC_ORIGINAL_STORE (never persistent configuration):

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_aapl_activation_safety.py tests/test_aapl_net_margin_activation.py tests/test_aapl_net_margin_proposal.py tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py tests/test_financial_metrics.py tests/test_research_answers.py tests/test_historical_research_answers.py tests/test_research_operation_handoff.py tests/test_financial_sync.py -q
```

Result: 968 passed, 90 skipped, 12.36 seconds. The new safety module contributes
98 passing cases. Opt-in original-artifact cases skipped deliberately; all enabled
launcher paths used synthetic originals/identities, fake sessions/servers and
reversible substitutions. Actual Windows SID retrieval was checked without printing
the SID, granting authority or installing a policy. Two disposable CLI subprocesses
exited 78 without listener startup, output or real registration. Relevant existing
sync tests used disposable in-memory SQLite; no live application DB access occurred.
Existing FastAPI/httpx and SQLAlchemy datetime deprecation warnings remain.

Self-review corrected background-lifespan failure termination (raising alone may
leave Uvicorn running), checked termination even when quarantine marking faults,
added actual concurrent readers after both registry stores, and rechecked exact
registries immediately before ASGI startup completion. Tracked diff and new-file
whitespace checks passed; fresh imports verified the false gate, four empty
registries and empty global Revenue equivalences. No database/artifact/network audit
was repeated. No service/configuration/SEC/model operation, commit or push occurred.

Outstanding real-activation gates: authenticated protected deployment commissioning,
reviewed complete owner/DACL/interpreter/import-closure verification, concrete
all-writer and original-store fencing with monitored ownership, operator-controlled
outside-Git original store configuration, separate source enabling/user approval and
Astra High implementation/deployment review. The maintenance lease is deliberately
retained for the server lifetime in this initial disabled implementation. These
uncommissioned controls always reject; setting a profile or acknowledgment cannot
make them pass.

Final Git remains main/d6173d0 with 14 task files (9 modified, 5 new) plus the
preserved frontend modification and two untracked runtime reports. Suggested commit:
`feat: add disabled operator launch and financial admission safety boundaries`.
