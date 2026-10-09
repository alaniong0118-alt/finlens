# Collation operator verification safety repairs

Status: completed (verification implementation only; execution remains pending)
Roadmap phase: scoped operational prerequisite; no migration rollout

## Objective

Replace the chat-only collation audit with a reviewable read-only verifier and
operator runbook resolving the three independently confirmed safety defects.

## Current architecture and context

HEAD `2bbadf3`; development revision `d7b834408ba8`. The existing ten-index
repair strategy remains approved. See [freshness operations](../../data-freshness.md).
Starting working tree: only generated `frontend/next-env.d.ts` modified; preserve
SHA256 `f4e8976c19fc926644d72610bf1058bd6bf52add97e46a02bc0b912a751625c0`.
Dataset: 35 companies, 58,881 facts, 3,175 chunks/vectors; libc en_US.utf8,
recorded/runtime 2.41/2.36. Prior operator scripts existed only in chat.

## Constraints

No REINDEX, ALTER DATABASE, database creation/restore, migration/bootstrap,
container/configuration/volume changes, SEC/OpenAI calls, scheduling or commits.
All live SQL must be read-only. Reports/files may be written. No dependencies added.

## Non-goals

Executing maintenance, changing the approved repair scope, application behavior,
financial semantics, or the next roadmap milestone.

## Implementation stages

1. Implement explicit safety validation, qualified index/plan checks and dual-path identity.
2. Add enforced space gates, physical index diagnostics, and conservative phase validation.
3. Add isolated injected-failure tests; document future authorized commands and recovery.
4. Run targeted tests/read-only live audit; verify preservation and complete this record.

## Decisions

- Keep the verifier incapable of executing SQL writes. Future write commands stay
  visible in the runbook, guarded by exact cluster/database identity in the SQL
  transaction and a freshly validated read-only report.
- Reject optimized Python before importing database configuration; use explicit
  exceptions for all safety gates regardless of optimization.
- Capture full semantic index definitions plus OIDs/filenodes; restoration may
  change physical identity, but an in-place rebuild must preserve logical identity.

## Discovered issues

Critical assertions disappeared with PYTHONOPTIMIZE; plan checks accepted another
index; TCP auditing and Docker SQL lacked a mandatory target match.

## Progress

- [x] Read instructions and independently inspect live index metadata.
- [x] Implement verifier, guarded SQL text generation and persistent runbook.
- [x] 61 pure/subprocess/injected regressions passed; no database fixtures/writes.
- [x] Live TCP/Docker identity and ten exact-index audits passed; fingerprints unchanged.
- [x] Live-baseline final-phase and actual non-quiescent plan generation rejected.
- [x] Windows PowerShell 5.1 parsed the full runbook; no deployment command executed.
- [x] Documentation references, generated-file preservation and git diff --check validated.

## Test and validation strategy

Pure/injected tests exercise production validators without database fixtures.
Subprocess optimization checks must fail before connection. Live audits compare
TCP/Docker identity, exact schema/index inventory, plans, duplicates, disk and
full-row/vector fingerprints. No database-write tests are authorized.

## Completion criteria

All requested negative cases fail closed; live before-phase succeeds; final-phase
rejects current mismatch; report/runbook are truthful; original fingerprints and
generated-file bytes preserved; git diff --check passes.

## Final outcome

All three P2 verification defects addressed. See the
[verification record](../../../backend/reports/collation_operator_verification.json)
and [future operator runbook](../../collation-remediation.md). The OID projection
explicitly casts to bigint so Docker JSON and SQLAlchemy return the same numeric
identity; the first live probe safely rejected the OID JSON string/integer mismatch
before this correction. Subsequent live audits passed with all original OIDs,
filenodes, source fingerprints and vector fingerprints unchanged.

Only operator scripts/tests/reports/docs changed. No backup, disposable writes,
maintenance, migration, container changes, source acquisition, scheduler, commit or
push occurred. Independent focused review and later execution authorization remain
required. Suggested commit: `Harden collation remediation operator verification`.
