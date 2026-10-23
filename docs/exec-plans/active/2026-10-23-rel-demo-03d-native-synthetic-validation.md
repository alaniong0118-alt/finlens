# REL-DEMO-03D — source-only native synthetic driver preparation

Status: active — source preparation only; native execution NOT AUTHORIZED.
Roadmap phase: bounded release-evidence enabling task; no milestone advancement.

## Objective

Prepare `backend/tests/native_showcase_evidence_acceptance.py` for coordinator and
independent review. This record is the preparation brief, written before the
driver. The initial design review returned PASS WITH CONDITIONS; subsequent
independent code review returned FAIL with three P2 findings. This revision
corrects those three findings for coordinator review and independent re-review.
Source readiness is not native acceptance or permission to execute. The current
task ends at the two-file review handoff, before Git Step 2.

## Review corrections incorporated before implementation

P2 sharing: hold a production read handle and perform separate FILE_WRITE_DATA
(0x00000002) and DELETE (0x00010000) competing opens. Each offers all three share
flags (0x7), uses FILE_OPEN (1), and has no creation, truncation, overwrite or
delete-on-close option. Only exact unsigned NTSTATUS STATUS_SHARING_VIOLATION
(0xC0000043) passes. Access denied and every other error fail. A compatible
FILE_GENERIC_READ (0x00120089, including READ_CONTROL and SYNCHRONIZE) open with
the same share flags must succeed and verify identity
and bytes. Register every returned handle before inspecting its status. An
unexpected success must be closed, then stop; the adapter's generic exception
cannot prove the native status.

### Three code-review P2 corrections (2026-10-23)

1. Compatible read control: use existing FILE_GENERIC_READ for the control and
   the raw_open permitted-access list, because observe queries the security
   descriptor and therefore needs READ_CONTROL. Keep SHARE_ALL, FILE_OPEN,
   separate minimal FILE_WRITE_DATA | SYNCHRONIZE and DELETE | SYNCHRONIZE probes,
   exact unsigned status comparison, registration, closure and terminal failure.
2. Exact adapter bytes and approval order: validate the ENTIRE approval first,
   using a driver-local pure path-chain validator with the production canonical
   DOS component rules. No adapter code is needed to validate approval. Only
   after load_approval returns, read adapter source once into immutable bytes
   `adapter_source`. Verify SHA256 of that buffer against the approved hash,
   which approval validation also binds to ADAPTER_SHA256. Compile that same
   buffer with dont_inherit=True and execute that code object in a fresh
   types.ModuleType namespace, registered under a private non-main name for
   dataclasses. There is no SourceFileLoader, exec_module, pathname reload, or
   bytecode-cache read/write. The compile filename is a diagnostic label only.
   WindowsAPI construction follows verified adapter execution. Default/help
   return before these steps; import only defines literals/functions/classes.
   This binds adapter bytes, not driver launch: hashing the driver's pathname
   after Python starts does NOT prove those are the driver bytes Python loaded.
   A trusted interpreter, standard library, driver launch and supervisor remain
   required and unresolved by this correction; approval is a trusted attestation.
3. Failure-specific IO_STATUS_BLOCK: do not read Information on failed native
   opens and remove the universal Information==0 assertion. Return its value
   only for STATUS_SUCCESS; successful FILE_OPEN controls still require the
   documented FILE_OPENED (1) disposition. Negative probes compare exact unsigned
   NTSTATUS only after rejecting/closing any returned handle. Sharing and
   exclusive FILE_CREATE collision probes retain their distinct exact statuses;
   access denied or any unexpected status cannot pass.

The ACL-negative functions, retained relative ancestor/identity checks, synthetic
fixture layout/bytes, closure accounting, no-cleanup behavior and historical/
production destination separation remain unchanged by this revision.

P3 ACL: only `source/unexpected-acl.bin` may receive one added ACE. Recheck its
approved in-run identity, non-reparse state, single link, bytes and original
private ACL immediately before mutation. Open an additional FILE_OPEN handle
with READ_CONTROL | WRITE_DAC | SYNCHRONIZE (no WRITE_OWNER, data-write, DELETE
or SACL rights). Use handle-based SetSecurityInfo with DACL_SECURITY_INFORMATION
only; owner/group/SACL arguments are null. Add SID S-1-5-32-545, access mask
FILE_GENERIC_READ (0x00120089), ACCESS_ALLOWED_ACE_TYPE, flags zero (no
inheritance). Reject a null DACL. Preserve original ACE bytes/order, owner,
group, ACL revision and security-descriptor control bits. Verify the exact
one-ACE delta and unchanged file identity/bytes before checking the exact
production `private_principals` rejection. API failure or another policy
failure is a failure, never the expected negative result. Do not restore ACLs.

P3 identity and closure: approval contains the complete existing DOS path chain
from volume root through LocalAppData, with independently reviewed native
identities. Open the approved volume GUID root; reopen every next component
relative to its retained predecessor. Register each acquired handle before
observation. Immediately before EACH fixture creation, re-observe EVERY approved
existing identity and every retained synthetic identity; recheck the private
parent and fixture directories. Prior observations never authorize mutation.
The driver retains ancestors until completion. Its handle ledger attempts every
owned close despite a close failure, with no retries, preserving the original
failure and reporting additional close failures. The unchanged adapter continues
to own its internal token/query handles; the ledger owns handles it returns and
all raw-probe handles.

Supervision: any future run must be one foreground process under an external
supervisor, maximum 120 seconds total and 30 seconds for an individual native
call or approval-input wait. The Python monotonic deadline is supplementary and
cannot interrupt blocking FFI. On timeout, unexpected access, status, identity,
ACL delta, or supervision loss, mark FAIL/ABORTED and stop. Request one interrupt;
if it does not settle within 5 seconds, terminate only the independently recorded
foreground PID after verifying its start time and ownership. Never kill unrelated
processes. Forced termination cannot establish successful handle closure. Retain
all fixture objects and partial state for review. No retry, relocation, automatic
deletion, ACL restoration, or PASS after timeout.

## Current architecture and baseline

Repository: `D:\Projects\finlens-foundation`; branch `main`. HEAD and local
`origin/main` are `46f61d683c7fca1bbf2d5a0f4d974afbf96d3de2`. Index is empty.
At original preparation both authorized paths were absent. At correction-task
entry both remain untracked: driver SHA256
`07392e86a71d49a26c0e5ff3703871ead72363706a0ded4719bb255e16fc48fb`,
plan SHA256 `42c39d0a501238c7e23454d51a18e44fd1a9daec5d808574e9d5b5a6b707a874`.
All other worktree exceptions are still ONLY:

- Modified `frontend/next-env.d.ts`, SHA256
  `f4e8976c19fc926644d72610bf1058bd6bf52add97e46a02bc0b912a751625c0`.
- Untracked `backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json`,
  SHA256 `a783517d2875e39df4c831c410265d0126fbf6a9d3ddba1103f7bd61b057844c`.
- Untracked `backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json`,
  SHA256 `f8df96c8890c0ece1e1701b25bc5c43b879c359eceb96acb451a2a0daa58bf7c`.

The unchanged adapter is `backend/scripts/preserve_showcase_evidence.py`, SHA256
`ce215717bebd1ad2b74d820293d927e7e0fe2ae2dd0e03b32fc0b30fd9718e34`.
Use its WindowsAPI, Spec, identity, check_observation, check_private, read_checked,
copy_exact and compare_streams. Never call its preservation orchestration,
committed manifest loader, or CLI. The test-only raw NtCreateFile probes and
DACL helper are outside production; production is neither patched nor wrapped.

## Constraints and non-goals

Only this plan and the named test driver may change. No native execution,
preflight, import/run of the driver, fixture creation, ACL modification, copying,
services, databases, SEC/provider/network calls or historical evidence access
is authorized now. Do not read or modify `backend/.env`. Preserve the protected
files above. No new framework, dependency, production edits, stage, commit or
push. No filesystem cleanup, retries or relocation. No new browser, financial,
model, release, deployment or historical-custody acceptance claim.

## Prospective fixture and approval contract

The only future root is the operator's native LocalAppData plus
`FinLens-NativeValidation-REL-DEMO-03D-v1`. Its exclusive creation must fail if
anything already occupies that name. Exactly four directories (root, source,
destination, decoy) and four files are permitted, under 512 KiB total:

- source/payload.bin: 131089 bytes, byte i = i modulo 251.
- destination/payload.bin: copy of the source through production copy_exact.
- decoy/payload.bin: ASCII `not-source\n` (11 bytes).
- source/unexpected-acl.bin: ASCII `synthetic ACL probe\n` (20 bytes).

No output receipt, log, extracted asset or historical input is created. Output
is a bounded console summary; private approval paths/identities are not echoed.
There is no discovery/preflight mode in the driver. Future independently
authorized inspection must provide approval via bounded stdin JSON with exact
keys: task, operator_sid, operator_name, local_app_data, bindings,
reviewed_driver_sha256, reviewed_adapter_sha256, independent_review_sha256,
supervision. Bindings must be the exact complete production path_chain, all
directories, with exact identity fields volume_serial, file_id, final_path,
security_sha256, directory. Supervision is the literal
`foreground:120s-total:30s-call:5s-interrupt:retain-on-abort`.
The native operator and known folder must match this independently approved
input. The driver is default-off and inert on import; its future explicit flag
also requires isolated/no-site/no-bytecode Python, source hash bindings and a
Windows platform. These gates do not confer authorization. No run command is
authorized or exercised by this task.

## Implementation stages and decisions

1. Verify baseline and protected files; stop on unexpected state.
2. Record all independent review corrections in this brief BEFORE driver edits.
3. Prepare inert test-only driver, binding to the unchanged adapter and synthetic
   constants; implement sharing, ACL, identity, collision and byte checks.
4. Inspect source without executing it; compare allowed-file scope, source
   hashes, protected hashes, index and whitespace; hand off for review.

2026-10-23: Use a private handle ledger rather than production orchestration.
Independent approval supplies existing identities; runtime observations cannot
self-authorize them. Each new synthetic identity is captured only after an
exclusive create and containment/private-policy checks. Minimal DACL mutation
is confined to the last case, after all positive private-policy checks. No
post-mutation private-policy check is expected to pass for that file.

## Discovered issues and limitations

No native facts have been measured. ACL inheritance/ordering, privilege and
share semantics, known-folder behavior, close behavior and platform ABI remain
unverified. The unchanged adapter uses generic Stop errors for many native
failures; the sharing test therefore samples raw native status directly.
Reparse creation, stale-handle use, hostile administrator races and historical
preservation are outside this protocol. Exact security-descriptor hashes may
fail closed on legitimate OS descriptor normalization; do not weaken checks or
retry in response. In-process deadlines cannot replace external supervision.

## Progress

- [x] 2026-10-23: Baseline, protected hashes, empty index and absent targets checked.
- [x] 2026-10-23: P2/P3 corrections incorporated into the preparation brief.
- [x] 2026-10-23: Prepared driver and performed non-executing static self-review.
- [x] 2026-10-23: Recorded static verification and protected-file/Git checks below.
- [x] 2026-10-23: Rechecked correction-task baseline, empty index and protected hashes.
- [x] 2026-10-23: Corrected the three independent code-review P2 findings in source.
- [x] 2026-10-23: Recorded correction-specific static regression checks and source hash.
- [ ] Coordinator and independent review (next authorization boundary).
- [ ] Separately authorize native inspection and, later, one supervised run.

## Test and validation strategy

NOW: text/AST inspection only. Parse source as data; do not import, execute,
invoke help/default mode, instantiate WindowsAPI, or run pytest/compileall.
Check top-level inertness, fixed native constants, all acquisition/closure paths,
exact error comparisons, restricted SetSecurityInfo arguments, allowed scope,
protected hashes, empty index and `git diff --check`. Static checks establish
syntax/source properties only, never runtime behavior.

FUTURE, NOT RUN: native SDK/operator and chain observations; exclusive fixture
creation; source/decoy identity and byte separation; production chunked copy,
hash and reopened-byte verification; exact native sharing probes plus read
control; exclusive collisions with exact STATUS_OBJECT_NAME_COLLISION; exact
DACL delta followed by private_principals rejection; closure accounting.
Native execution attempts under this authorization must remain ZERO.

## Original preparation verification (superseded source snapshot)

2026-10-23, working directory `D:\Projects\finlens-foundation`:

- PASS: a standalone stdin inspector run as `python -I -S -B -` read the driver
  as text and used `ast.parse`; it did NOT import or execute the driver or adapter.
  Assertions checked literal/definition-only module initialization; guarded main;
  production attribute allowlist; absence of preservation, process/network and
  filesystem-cleanup calls; exact sharing/ACL constants; separate write/delete
  probes and compatible read control; DACL-only SetSecurityInfo arguments;
  exact ACL delta/private_principals comparison; guard-before-create ordering;
  raw-probe handle registration before return; and trailing whitespace.
- The initial inspector's generic forbidden `remove` assertion also matched
  in-memory list removal. Its check was narrowed to allow only `self.owned` and
  `synthetic` list removal. Both subsequent AST inspections passed. No driver
  execution was used to investigate this inspector false positive.
- PASS: manual source review of all acquisition paths, retained relative chain,
  source/destination byte helpers, minimal DACL rights, raw ACE preservation,
  null-DACL rejection, owner/group/control comparison, and best-effort closure
  preserving the primary exception. Allocation-release failures also cannot
  replace an already active failure. With no earlier error, the first owned
  handle-close exception is the terminal failure.
- Driver: 489 lines, SHA256
  `07392e86a71d49a26c0e5ff3703871ead72363706a0ded4719bb255e16fc48fb`.
  Review anchors: Handles line 31; raw_open 63; sharing_checks 104;
  security_snapshot 133; add_users_read_ace 169; acl_negative 212;
  approved_run 247 (guard/create and retained chain); approval gates 379;
  default-off main 436.
- PASS: adapter and all three protected hashes match the baseline above.
  `git rev-parse HEAD` and `git rev-parse origin/main` match the expected commit;
  `git diff --cached --name-status` is empty. `git diff --numstat` contains only
  the pre-existing 1-addition/1-deletion next-env change; untracked additions do
  not appear in that command.
- PASS: `git diff --check` exits 0. Both authorized untracked sources were also
  examined with `git diff --no-index --check -- /dev/null <authorized-path>`:
  no whitespace errors; exit 1 represents the expected added-file difference.
  Git emitted only its LF-to-CRLF advisory. No Git configuration was modified.
- Final status: the original next-env modification and two original untracked
  reports, plus exactly the two authorized new files. No staging/commit/push.
- Native driver execution attempts: **0**. Native API execution/preflight,
  fixture creation, ACL modification, copying, services/database/provider/network
  activity, and historical evidence access: **0**. No .env access. No runtime
  test, pytest invocation, default/help invocation, or native acceptance claim.

## Three-P2 correction verification (current source snapshot)

2026-10-23, working directory `D:\Projects\finlens-foundation`. Baseline branch,
HEAD/local origin, empty index, original protected hashes and unchanged adapter
were verified BEFORE edits. Both preparation files had the entry hashes recorded
above; no unexpected baseline differences were found.

PASS, static inspection only: a standalone `python -I -S -B -` stdin inspector
parsed the old/current driver text with ast.parse. No driver or adapter was
imported, executed, or compiled into runnable code by the inspector. It asserted:

- Literal/definition-only module initialization and default/help early exits.
- FILE_GENERIC_READ includes READ_CONTROL and SYNCHRONIZE; permitted access and
  compatible read use that mask. SHARE_ALL/FILE_OPEN and the separate minimal
  write/delete status checks remain present.
- Unsigned native status normalization, no Information inspection for failures,
  exact negative status comparison, and terminal closure of returned handles.
  Success-only FILE_OPEN controls still require Information==FILE_OPENED (1).
- Exactly one adapter.read_bytes call and one assignment to adapter_source.
  Full load_approval returns first, with no adapter parameter/reference; its
  local path validator enforces the same canonical DOS/component restrictions.
  The exact source variable feeds SHA256 and compile; exec receives only that
  compile result and the fresh module's globals. The approved adapter hash is
  bound to the pinned production hash. SourceFileLoader/importlib/exec_module
  are absent. Order: full approval line 485, source read 486, hash 487-488,
  fresh namespace 489-492, compile 493-494, exec 495, WindowsAPI 496.
- All constants are AST-identical to the entry snapshot. Changed definitions
  are exactly raw_open, expect_native_failure, sharing_checks, load_approval
  and main; the only added definition is approval_path_chain. Every other
  function/class is AST-identical, including ACL-negative behavior, retained
  ancestor/identity guards, fixture layout and byte budget, exclusive collision
  verification, byte helpers, closure accounting and failure preservation.
- No preservation/manifest invocation, production destination access, filesystem
  cleanup, process invocation or network acquisition was introduced. Text has
  no trailing whitespace. No new dependency or production change was made.

Current driver: 514 lines, SHA256
`d01261936b5c28f567214f9d46bce366c2bdd9d4059c98d7c7e64fea85615290`.
Review anchors: permitted access line 70, status/Information 87-91;
negative-probe closure/status 94-103; compatible read 106-116; local path
validation 381-397; full approval 400-454; opt-in and source binding 457-496.
The previous source snapshot's PASS statements were limited static checks;
they did not resolve these findings or establish native acceptance. Independent
code review remains FAIL until coordinator review and independent re-review.

Final read-only checks PASS: `git status --short`, HEAD/local origin, empty
`git diff --cached --name-status`, tracked `git diff --check` (exit 0), protected hashes,
and whitespace checks for each untracked source using
`git -c core.autocrlf=false diff --no-index --check -- /dev/null <path>`.
For the latter, exit 1 is the expected added-file difference; whitespace errors
would be reported separately. The per-command option does not modify Git config.
Final status remains the original next-env modification and two original
untracked reports plus these two untracked preparation files. No staging,
commit, push, filesystem cleanup or .env access. Native execution attempts
remain **0**, including default/help modes and preflight. All native behavior
and the driver/adapter runtime path remain **NOT TESTED**.

## Completion criteria and final outcome

Preparation is ready only when exactly the two authorized sources are present,
static checks are recorded, original protected state and index are preserved,
and no native driver/API was executed. Correction-specific static checks pass;
native acceptance remains NOT TESTED. This plan stays active at the coordinator
and independent-review boundary. No preflight or run is authorized by this
handoff, and existing synthetic/offline results cannot supply native acceptance.
Suggested commit message after separate Git authorization:
`test: prepare bounded native synthetic evidence driver`.
