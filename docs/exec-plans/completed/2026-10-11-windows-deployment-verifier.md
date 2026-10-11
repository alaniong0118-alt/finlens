# Bounded Windows deployment verifier

Status: completed
Roadmap phase: disabled activation security prerequisite only

## Objective and current context

Baseline main `6aa273c1cfd7c96ab65dece969df1dffe75de396`. Preserve the
frontend/next-env.d.ts modification and two untracked runtime reports. Refine
the operator-profile/integrity stubs with actual read-only Windows descriptor
checks and isolated adversarial tests. Production activation remains prohibited.

## Constraints and non-goals

No real profile, identities, ACL changes, store configuration, maintenance fence,
network, database, artifacts, service operations or commit/push. No financial,
evidence, version, lifecycle or writer-coordination changes.

## Implementation and decisions

1. Read Windows owner/DACL using native APIs and evaluate ordinary allow ACEs
   conservatively, including inherited/group grants and parent replacement.
2. Trust only the Windows SYSTEM/Administrators custody boundary in this initial
   subset; no caller-selected custodian may bootstrap profile trust. Define a
   versioned profile with explicit code/runtime roots and custody rights.
3. Inspect protected roots, interpreter/config pins and import paths/hooks. Keep
   the external bootstrap/import-closure anchor explicitly uncommissioned and
   rejecting. Self-hashing in an already untrusted interpreter cannot prove trust.
4. Run offline profile/descriptor tests and existing safety regressions, actual
   read-only development rejection, syntax/whitespace and empty-registry checks.

## Progress and validation

- [x] Read request, AGENTS and plan rules; confirm baseline and relevant contracts.
- [x] Implement bounded checks and adversarial tests.
- [x] Validate, self-review, record exact results and external trust blockers.

## Checks actually run

From `backend`, without external evidence-store opt-in:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_windows_deployment_verifier.py tests/test_aapl_activation_safety.py tests/test_activation_lease_admission.py tests/test_aapl_net_margin_activation.py tests/test_aapl_net_margin_proposal.py -q
```

Final result: **253 passed, 90 skipped**, one existing Starlette deprecation warning,
5.60 seconds. Includes 102 new verifier cases. Skips require the explicit external
original-store test configuration; no prior SEC/database/financial audit was repeated.
Synthetic profiles/descriptors exist only in isolated temporary fixtures. No ACL or
real operator identity was installed; no gate or registry is patched in the new tests.

Native read-only probes successfully read owner/DACL and actual-token AccessCheck
results on the volume, policy source and virtual-environment executable. The volume
and interpreter rejected broad modification grants; the policy source rejected its
owner. Full development custody rejected `protected_profile_acl_unauthorized_modification`.
Native API adversarial tests include null descriptors, validation and token/AccessCheck
failures. Initial native debugging established that AccessCheck requires owner AND
group information in the returned security descriptor; the API now requests both.

Fresh-process checks confirmed false activation gate, four empty registries, empty
Revenue equivalences, no original-store configuration, rejecting maintenance provider
and always-rejecting external bootstrap anchor. AST syntax and trailing-whitespace/
final-newline checks passed for all three Python changes; `git diff --check` passed.
Explicit whitespace checks also cover new tests and this untracked plan.

## Self-review and remaining boundaries

Supported descriptor subset is deliberately conservative: ordinary allow ACEs only,
trusted SYSTEM/Administrators ownership/custody, all inherited/group mutation grants
and every ancestor inspected. Deny/object/conditional ACLs and delegated custodians
reject. Actual AccessCheck establishes current-token DACL rights, not all host token
privileges or an administrator/backup/restore audit. Native API allocations/duplicate
token handles are released; no running-thread impersonation, ACL or token adjustment.

Profile schema v2 binds roots, configuration and custody plus existing exact financial
approval pins. Import structural checks reject unsafe startup/search paths/hooks and
active .pth lines. No transitive Python/native DLL closure or atomic handle-based
path proof is claimed. `_verify_external_bootstrap` ALWAYS rejects: an independently
protected OS/deployment launch mechanism must prove integrity before Python executes.
No profile claim, boolean or environment flag satisfies that missing trust anchor.
Review this external boundary, conservative ACL subset, native API ABI/cleanup,
privilege assumptions and ancestor/path race limitations with Astra High.

Launcher, lifecycle, financial/evidence/version and database coordination code are
unchanged. The source gate is false and the maintenance provider remains rejecting.

Synthetic passing checks are not production deployment attestation. Unsupported
ACE types/descriptors must reject rather than attempting incomplete effective-access
reasoning. An independent protected launcher/runtime must establish bootstrap
integrity before executing Python; implementing that anchor is outside this task.

## Completion criteria

Focused tests pass; real writable deployment rejects; source gate remains false,
maintenance provider rejects, four registries/equivalences empty; no prohibited
operations or unrelated changes. Document unsupported ACL/import cases clearly.

## Final outcome

Completed the bounded checks, tests and documented fail-closed boundary. Five task
files: operator policy, existing safety-fixture schema, new verifier tests, activation
security contract and this plan. HEAD remains main
`6aa273c1cfd7c96ab65dece969df1dffe75de396`. Frontend modification and both runtime
reports preserved. No real configuration, database, network, services, artifacts,
activation, commit or push. Real deployment trust remains NOT READY.
Suggested commit after review: `feat: add bounded Windows deployment custody checks`.
