# Financial-only native startup preparation

Status: active; code/offline tests only, no activation authority.

## Objective and context
Prepare a separate operator entry point for later approved local financial-only
real-data acceptance at main b4d1002d15d4c4fd92440d4b99b31da9ab88ddf9.
Reuse existing native listener/terminal ancestry/readiness helpers, not a new
service supervisor. Existing Start-FinLens.ps1 remains development-only; existing
Stop-FinLens.ps1 still refuses automatic shutdown. The full private-runtime
metadata diagnostic remains fixed BLOCKED and is never ignored or relabeled PASS.

## Constraints and non-goals
No real startup, private config read, DB/model/provider/tunnel/network access,
installation, permissions changes, drive/file cleanup or Git delivery in this task.
Preserve next-env.d.ts, two historical reports, the protected export plan and the
completed personal-site plan. Later configuration checking normally loads existing
private configuration without disclosing it; that operation needs separate approval.
The new check proves configuration/import readiness only, not DB privileges/data,
source rights, network containment, descendant cleanup or deployment acceptance.
Encoder/Qwen are outside this financial-only path; ordinary core imports must work.

## Implementation stages and decisions
1. Add a bounded checker requiring explicit process sec_readonly and financial-only
   opt-in before any app/config import. Verify immutable profile, encoder denial,
   local effective DB destination via canonical HTTP options, cold core import and
   disabled retrieval/generation capabilities; never query DB or warm an encoder.
2. Add dedicated startup script using legacy helpers without invoking their
   development-only startup/profile function. Child-only flags, ports8021/3003,
   occupied-port refusal, bounded hidden checker, exact health/capability/proxy checks,
   named interactive Ctrl+C terminals and no automatic termination of services/DB.
   Browser is opt-in after readiness; failures report known owned identities safely.
3. Synthetic Python and PowerShell tests, existing relevant guard regressions,
   whitespace/scope review; freeze for independent review. No real readiness claims.

## Validation strategy
Use the existing guarded Python runner with dotenv disabled and physical DB/socket
traps. Keep checker module import pure. PowerShell tests mock service/network/OS
interfaces; any checker timeout/output fixtures are isolated local child scripts,
never application services or private configuration. Verify bad profiles, poisoned
capabilities/proxy, ports, PID reuse, malformed checker output, timeout and output
bounds; retain legacy development/BLOCKED behavior. Tests must report actual counts.

## Progress and discovered issues
- [x] Inspected instructions, current source and five protected hashes; index empty.
- [x] Implement checker/entry point and focused synthetic tests.
- [x] Record offline outcomes and six-file scope; independent review pending.
- [ ] Later operator-approved configuration/DB/loopback/browser acceptance remains separate.

## Completion and final outcome
Pending reviewed code plus synthetic test evidence. This plan does not authorize
runtime activation, external access, real config/DB use or commit/push. A future
operator run must stop on every failed guard and leave PostgreSQL/unrelated
processes untouched; native observation cannot prove all descendants stopped.

## Implemented contract and safety limits
The new script reuses legacy helper declarations only, preserving explicitly
supplied dedicated options before dot-sourcing legacy defaults. It never invokes
the legacy development startup/profile routine. Default ports8021/3003, browser
opt-in only; foreign checkout roots, occupied listeners and failed checks refuse.
Backend child alone receives sec_readonly/financial-only/offline flags. Frontend
child alone receives the exact loopback backend URL and telemetry-off flag. Parent
and persistent environment settings are unchanged.

A hidden checker subprocess has a 10-second cooperative wall deadline and a4096
UTF-16-character bound per captured stream; native process creation/read completion
are not hard OS real-time guarantees. Only that newly created checker handle may
be killed/reaped on timeout/output failure, with a one-second reap allowance; never
service processes, unrelated listeners, DB or a process-name tree. Errors suppress
all raw child diagnostics. The canonical checker normally reads existing private
backend configuration only during a later explicitly approved run, verifies exact
process opt-ins before app imports, immutable restricted profile, encoder denial,
canonical bounded HTTP DB options with loopback effective hostaddr and actual core
import/capabilities. No DB session/query or model load occurs in the check. Ordinary
OpenAI SDK/psycopg imports are required, but an encoder/Qwen/model runtime is not.
Known encoder/model module imports are rejected instead of treated as readiness.

The same checker exposes a Uvicorn factory, rechecking inside the actual backend
process before socket binding and returning the unchanged app/router. This avoids
relying on another earlier process's configuration; database.py retains its parsed
URL after the check. No API/admission/schema/calculation code changed. A READY JSON
means configuration/import readiness only, never activation/privilege/data/right
acceptance and never a replacement PASS for the full BLOCKED private-runtime gate.

Readiness uses existing bounded HTTP probes and PID ancestry/creation-time checks:
health, strict disabled-retrieval/generation capabilities, read-only dbz and frontend
proxy/HTML. The per-stage budget can overrun by bounded pending two-second probes,
as documented for the reused helper. No listener is reused or stopped. Original
named interactive terminals are the graceful Ctrl+C controls; known terminal PID/
creation times are reported, including after readiness failure. A service identity
establishment failure can leave an untracked newly launched terminal: inspect the
expected FinancialOnly Backend/Frontend terminal titles manually, never infer
ownership or kill by name/port. No automatic service/DB shutdown is implemented;
all-descendant cleanup, hostile-local-process authentication and OS egress isolation
remain unproven. Offline flags only constrain normal model downloads.

## Actual offline validation
From backend, existing venv interpreter with process-local
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, guarded runner -I -B; no private dotenv/physical
DB/network calls. New test file runs alone so the real cold import cannot inherit
an already-loaded app/config from another test module:
- `.venv/Scripts/python.exe -I -B tests/run_dep01a2_increment2_offline.py tests/test_financial_only_startup.py --maxfail=1`:
  final26 passed, no warnings/skips. Tests trap private .env opens and physical
  sockets, verify CLI/factory rechecks, actual core imports with a synthetic URL,
  disabled encoder/model imports, process/frozen mismatch, remote/invalid DB
  targets and sanitized diagnostics. Earlier25 passed with seven warnings from
  a redundant empty pytest match expression; it was removed before final run.
- `test_private_runtime_preflight.py` alone:60 passed. `test_financial_only_policy.py`
  alone:45 passed (existing Starlette/httpx deprecation warning; no dependency edit).
  An initial combined run of these two files stopped with59 passed/1 failed because
  the policy module imports app at collection, contradicting the preflight test's
  explicit no-app-import process baseline;45 policy tests were unrun in that
  combined attempt. Separate cold processes preserve both existing assertions;
  the initial failure is retained, not labeled a combined pass.
- Read-only PowerShell parser: new startup and test scripts passed.
- Bound existing PowerShell7.6.5, `-NoLogo -NoProfile -NonInteractive -File backend/tests/test_financial_only_startup.ps1`:
  final25 passed, zero failed/skipped. Services, listeners, HTTP and browser are
  mocked; printed ready/PIDs100/200 are synthetic, not launched services. Four
  real short Python checker children use plain isolated fixture modules outside
  the repo, without app/config imports; success, stderr, overflow and timeout
  tested. Every created child is reaped by its own process handle. Two successive
  owned fixture directories remain retained (no filesystem deletion):
  `D:/Projects/finlens-financial-startup-offline-e602f7a6ed634688aee62104dd672a9e` and
  `D:/Projects/finlens-financial-startup-offline-40b3f912e3884d8f98ce8ddc70c83640`.
  Earlier24 passed before adding option-capture/factory assertions; counts overlap.
- Existing `backend/tests/test_rel01a_startup.ps1`:26 passed, zero failed/skipped,
  with synthetic interfaces, including legacy development rejection/ownership/PID
  reuse, unsafe Stop and refresh-guard controls. Existing startup/Stop/BLOCKED code
  bytes remain unchanged.

## Remaining gates
Freeze six files (new startup, checker, two tests, this plan, local-demo section)
for independent content review. No real service, browser, private config read,
DB query, inference, acquisition, tunnel, install, security change or Git mutation
has occurred. The isolated tests exercised the currently installed core import
path with synthetic configuration, not live startup or the real DB dataset.
After review, separately authorize normal config loading, existing local PG read-
only connectivity/data inspection, loopback service ports, optional local browser
and operator-controlled Ctrl+C shutdown. Stop on failed guards; don't alter the
legacy development/BLOCKED gates, start PostgreSQL, grant privileges or fetch data.
External beta/login persistence/source rights remain separate unresolved gates.
