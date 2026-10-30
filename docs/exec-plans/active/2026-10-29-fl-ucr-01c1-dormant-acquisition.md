# FL-UCR-01C1 — dormant single-CIK transport and Windows custody

Status: active — focused P2 corrections complete; narrow independent re-review pending.
Native and live acceptance remain unperformed and unauthorized.
Roadmap phase: scoped UCR enabling task; no later roadmap item authorized.

## Objective

Implement the coordinator-authorized dormant four-file slice. Accepted injected
representation bytes may be checked and published under a provisioned Windows
NTFS root. They remain offline, unverified as SEC evidence, and inadmissible as
financial or operator authority. The real acquisition entrypoint always raises.

## Current architecture and context

Starting HEAD: `9049f37f2500d3d287fa383a828d35135866aca1`; empty index.
The only initial exceptions are modified `frontend/next-env.d.ts` and two untracked
reports named below. All four implementation targets were absent. The existing
`sec_identity_source` parser and `sec_identity_capture` limits are reused without
changes. ROADMAP describes existing milestones; this task grants no activation.

Binding sources (read completely on 2026-10-30):
`D:/下载/FL-UCR-01C1_Sol_Corrected_Design.md` and
`D:/下载/FL-UCR-01C1_Astra_Final_Review.md`. These are design inputs; the user's
explicit implementation request supplies authorization. No design review repeated.

Protected SHA-256 values verified before implementation:

- `frontend/next-env.d.ts`: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- `backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json`: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- `backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json`: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints

Only this plan, `backend/app/sec_submissions_acquisition.py`,
`backend/app/sec_submissions_custody.py`, and
`backend/tests/test_sec_submissions_acquisition.py` may change. No .env inspection,
network, DB, services, native fixture execution, staging, commits, push or deploy.
No deletion, rollback rename, replacement or automatic recovery. Retain ambiguous
artifacts. One cooperative 30-second budget reserves two seconds for closure;
native pending I/O lifetimes take precedence over returning on time.

## Non-goals

Live commissioning, root provisioning, authority/admission, supervisor, scheduler,
routes, database integration, SEC authenticity, hard deadlines and crash durability.

## Implementation stages

1. Implement operation ownership, same-lock cancellation and receipt codec.
2. Implement strict raw HTTP gate and single-GET standard-library transport seam.
3. Implement typed handle-relative NTFS custody and status/pending protocol.
4. Exercise bounded offline fault/limit/race tests with DNS/sockets denied.
5. Self-review scope, invariants and protected files; leave all changes unstaged.

## Decisions

2026-10-30: Apply all final amendments: replace Event/already-open interfaces with
non-clearable same-lock cancellation and single-use inert descriptors; interpret
signed NTSTATUS with explicit pending retention; define exact canonical JSON and
require identical recovery re-encoding; zero-body guarantee covers bytes delivered
to the application before acceptance, allowing buffered transport read-ahead.
Canonical receipts use sorted keys, compact separators, ensure_ascii=True escaping,
UTF-8 without BOM/newline and allow_nan=False. Exact nested schema is documented
and enforced in the acquisition module. Injected callbacks are trusted test seams.

2026-10-30 implementation details: versions have exactly `acquisition`, `custody`,
`parser`, `policy`; timestamps and offsets have exactly `operation_start`,
`headers_complete`, `body_complete`, `receipt_created`. All JSON floating-point
tokens are rejected because the closed schema has no floating-point fields.
`Cancellation.cancel()` and logical handoff share one RLock, including reentrant
clock probes; final clock sampling precedes the cancellation test. An accepted
cancellation prevents handoff, and cancellation after handoff reports `too_late`.
Descriptors transfer on entry, before clock/CIK validation, and are single use.

2026-10-30 native ownership: handle tokens are separate from HTTP resources.
Unobservable pending native I/O retains its buffers, IOSB, API and operation ledger
in process memory, prohibits native-handle closure and prevents delivery. Unrelated
HTTP responses/connections still close. There is deliberately no automatic reaper,
rename retry, fallback, deletion, recovery or deadline reset. Supported private
ACLs have exactly operator, SYSTEM and Administrators full-control allow entries,
with supported inheritance flags; unsupported policies fail closed. Ancestors may
allow other principals read access, but not mutation/deletion rights.

## Discovered issues

Native acceptance remains unperformed by authorization. Offline mocks cannot
establish actual NTFS rename, sharing, ACL, power-loss or process-kill behavior.

During implementation, fault tests found and resolved: the raw wrapper needed a
`flush()` delegate for HTTPResponse error-path closure; a reentrant cancellation
probe could deadlock the original Lock at handoff; verification state was initially
recorded after reader closure, misclassifying cancellation during closure. Final
verification now precedes cleanup classification. Self-review also added exact
comparison of reopened body/receipt with staged bytes (including otherwise-valid
changed receipts) and closure of HTTP resources during native quarantine.
Header prefix allocation was tightened to discover the bounded name before reading
the value; exact-cap tests caught and corrected prefix/terminator off-by-one cases.
The first hung offline test process was stopped by its verified test-process IDs;
no services, native fixture workers or unrelated processes were stopped.

## Progress

- [x] 2026-10-30: Read root rules, ExecPlan rules, relevant engineering/roadmap
  context and both complete binding sources. Reverified HEAD/index/protected hashes.
- [x] 2026-10-30: Implemented the three code/test files, all mandatory amendments,
  disabled boundary, strict HTTP gate, receipt codec and native custody seam.
- [x] 2026-10-30: Authorized offline tests and focused dependency regressions pass;
  completed self-review of ownership, publication, integrity and handoff invariants.
- [x] 2026-10-30: Recorded verification and remaining gates; final Git preservation
  checks are recorded with the engineering report. All work remains unstaged.

## Test and validation strategy

Run the standalone unittest file with isolated Python, no site packages and no
bytecode (`-I -S -B`). Install network denial before application imports. Use only
in-memory exchange/native seams by default; native cases require a separate explicit
disposable-fixture invocation and are skipped in this task. Verify parser boundaries,
ownership, every closure, cancellation/deadline checkpoints, rename outcomes,
canonical receipts, recovery and permanently disabled live entrypoint. Run existing
source/capture offline regressions if dependency reuse justifies them. Record actual
commands/results below; no planned validation counts as evidence.

Initial implementation verification, before the focused P2 corrections below,
from `D:/Projects/finlens-foundation` on 2026-10-30:

```powershell
backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_submissions_acquisition.py -q
```

Final result: 50 test methods, **49 passed, 0 failed, 1 skipped**, and **712 passing
subtests**. The skip is the authored opt-in native publish/reopen/recovery/collision
fixture. Socket/DNS monkeypatches and a socket-event audit hook are installed before
application imports. No native filesystem calls occur: native bindings are tested
through mock DLL functions, and protocol tests use in-memory structures/handles.
The runner explicitly uses verbose output, including when `-q` is supplied.

The two existing offline dependencies were run independently with the following
exact Python bootstrap, substituting `FILE` with each stated filename, piped through
`backend/.venv/Scripts/python.exe -I -S -B -` using a PowerShell literal here-string:

```python
import runpy, socket, sys

def deny(*args, **kwargs):
    raise AssertionError("offline_network_denied")
def audit(event, args):
    if event.startswith("socket."):
        deny()
socket.socket = socket.create_connection = socket.getaddrinfo = deny
sys.addaudithook(audit)
sys.argv = ["backend/tests/FILE"]
runpy.run_path(sys.argv[0], run_name="__main__")
```

- `test_sec_identity_source.py`: **44 passed, 0 failed**.
- `test_sec_identity_capture.py`: **30 passed, 0 failed**.

Total method outcomes: **123 passed, 0 failed, 1 native skip**. Subtests are
reported separately, not added to method counts. The reused source/capture files
were inspected for safe execution; their isolated subprocess probes additionally
deny network and other effects. No bytecode, pytest cache or repository report was
generated. No broader DB/provider/browser/service suite was run.

## Completion criteria

Four-file scope; disabled live boundary; mandatory amendments implemented; offline
suite passes; protected hashes/index/HEAD preserved; native evidence explicitly
pending; implementation ready for independent Astra High review, not activation.

## Final outcome

The exact four new files implement the dormant scope. `acquire_submissions()`
always raises `live_acquisition_disabled` before inspecting inputs/configuration or
invoking factories. Injected acquisition and explicitly selected recovery retain
`offline_injected` origin and `unverified` evidence status. Recovery establishes
`RECOVERED_VERIFIED_LOCAL` only and cannot reconstruct delivery or authority.

The three P2 amendments are implemented in the same-lock cancellation/descriptor
interfaces, signed NTSTATUS/pending lifetime protocol, and exact canonical receipt
codec/re-encoding checks. The P3 correction is implemented by gating application
body methods while retaining the original buffered socket file; the read-ahead
fixture confirms buffered body bytes survive header validation. One GET is counted,
with no retry/redirect/fallback or physical-TCP-attempt/trailing-byte claim.

Native test **not executed**: the optional provisioned-disposable-root fixture for
actual rename/reopen, byte-preserving collision and recovery. Additional native
adversarial ACL/sharing/reparse/hard-link/identity and owned-worker-interruption
acceptance remains separately commissioned; mock tests do not satisfy these gates.
No production custody artifacts were created.

Remaining risks/gates: x64 local NTFS acceptance; trusted root and operator
provisioning; same-principal/admin/SYSTEM/kernel trust; no power-loss durability;
potential indefinite native pending wait or retained unknown-I/O resources; no hard
Windows deadline without a separately accepted supervisor. Current SEC policy,
contact/rights/retention, coordinated usage, TLS/egress, bootstrap admission,
independent implementation review and separate live-pilot authorization remain
required. No activation or further roadmap work is authorized by this patch.

Recommendation: ready for independent Astra High code review of the dormant patch.
No implementation blocker remains. Native execution and live commissioning require
separate coordinator approval. Keep this plan at its exact authorized active path.
Suggested future commit message: `feat(sec): add dormant single-CIK transport and NTFS custody`.

Final preservation checks on 2026-10-30: HEAD still
`9049f37f2500d3d287fa383a828d35135866aca1`; `git diff --cached --stat` is empty;
all three protected SHA-256 hashes still match the values above. Git status contains
only the original three exceptions and the four new authorized files. `.env` was
never inspected, hashed or modified. Tracked `git diff --check` and individual
new-file `git diff --no-index --check -- /dev/null FILE` checks found no whitespace
errors (no-index exit 1 denotes added-file differences, not failed tests).

## Focused P2 corrections — 2026-10-30

Coordinator authorized only the three confirmed P2 repairs and duplicate-header
assertion correction in these same four files. Astra's FAIL supersedes the earlier
readiness recommendation until these repairs are verified; no architectural review
or planning cycle is restarted. HEAD/index/protected hashes were reverified before
editing and still match. Native execution and all original exclusions remain.

- [x] P2-1: atomic cancellation/handoff decision, including same-thread reentry.
- [x] P2-2: retain staged body/receipt identities and compare reopened files.
- [x] P2-3: expose a sanitized capture recovery selector on failures after allocation.
- [x] Valid singleton duplicate-header assertions and deterministic negative probes.
- [x] Offline suites and focused self-review; final whitespace/hash verification
  and four-file fingerprints are supplied in the engineering report.

### Corrections and linearization

P2-1: Cancellation and handoff now compete through one builtin `dict.setdefault`
operation on an exact string key. The winning immutable decision is never replaced.
Cancellation inserts its unique request object (only the winner returns `accepted`);
handoff inserts a dedicated sentinel. A preexisting cancellation prevents handoff,
including reentry between the last cancellation check and commit. Once the sentinel
is inserted, same-thread reentry returns `too_late`, even before the logical-delivery
field is updated. The RLock and single-operation token ownership remain. Deadline
sampling now occurs immediately before the terminal lock, so injected clocks do
not execute inside that transition. This remains a cooperative, not hard deadline.
Deterministic trace probes exercise the original vulnerable gap, immediately before
commit, and immediately after commit. Existing cross-thread race tests also pass.

P2-2: Publication retains immutable identity tuples (volume serial, file ID,
security digest and directory type) for each staged file after writer verification
and before writer closure. Reopened body and receipt identities must each match
their own staged tuple. Directory identity, exact bytes, digests, ACLs, reparse and
link checks remain enforced. Independent identical-byte body-ID and receipt-ID
replacement probes now fail with `integrity_failure` and withheld delivery.
Explicit recovery still verifies current local integrity without inventing historic
file-ID continuity; a separate regression proves that distinction for both files.

P2-3: `Operation.capture_id` starts as None and is set immediately after internal
UUID allocation and canonical validation. `CaptureFailure.capture_id` carries that
selector through early I/O failures, collision/failure/indeterminate publication,
post-rename cancellation and cleanup failures. Failures before allocation retain
None, and the old two-argument exception construction remains valid. Explicit
recovery records its already-validated selector too. No selector is added to error
messages or treated as evidence of publication, source authenticity, authorization
or delivery. The acceptance test uses an actual unpatched generated UUID, obtains
it exclusively from the post-rename cancellation exception and explicitly recovers
that exact bundle without refetch, discovery or authority promotion.

Duplicate-header quality: every permitted critical singleton first succeeds with a
valid value, including `application/json` for Content-Type and the actual body length
for Content-Length. Adding its equal case-insensitive duplicate must specifically
fail with `duplicate_critical_header` before body consumption. Forbidden headers
have no valid accepted singleton and remain covered by existing forbidden-header
tests; unrelated HTTP parser cases were not rewritten.

### Actual focused verification

Before production edits, the new five-test focused selection reproduced the defects:
1 passed, 3 failed, 1 errored (missing failure selector), with 6 passing duplicate
header subtests. The identical selection after the repairs passed all 5 tests and
6 subtests. Exact focused command, from repository root:

```powershell
backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_submissions_acquisition.py OfflineTests.test_reentrant_cancel_after_final_check_prevents_handoff OfflineTests.test_replaced_body_id_with_identical_bytes_is_rejected OfflineTests.test_replaced_receipt_id_with_identical_bytes_is_rejected OfflineTests.test_failed_capture_selector_selects_explicit_recovery OfflineTests.test_duplicate_critical_headers_even_equal
```

Final full corrected suite command:

```powershell
backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_submissions_acquisition.py -q
```

Result: **59 methods, 58 passed, 0 failed, 1 native skip; 710 passing subtests**.
Subtest count changes from 712 because the duplicate-specific loop now covers six
accepted critical singletons instead of ten mixed/forbidden critical names (-4),
and explicit integrity-only recovery adds two independent file cases (+2).
All three Astra failure-probe equivalents are covered, with additional before/after
commit, pre-allocation compatibility, unchanged recovery semantics and callback-lock
assertions. The original cross-thread and exhaustive fault/checkpoint tests pass.

The existing source and synthetic-capture regressions were rerun independently
through the exact isolated, network-denying bootstrap recorded above, using their
respective filenames: **44 passed** and **30 passed**, both with zero failures.
Final method totals: **132 passed, 0 failed, 1 native skip**. Focused selection and
subtests are not added again to those totals. No caches or new repository files were
created by execution. No native fixture, network, DB, service or provider was used.

### Narrow re-review recommendation and preserved gates

All three targeted corrections and the duplicate-header assertion correction are
complete, with no expansion beyond the same four previously untracked files.
Recommend narrow Astra High re-review of these fixes, not a general design restart
or Git Step 1. The live entrypoint remains unconditionally disabled. Native NTFS
publication/sharing/ACL/adversarial/worker-interruption acceptance, trusted-root
provisioning, hard-deadline supervision and live operational admission remain
unperformed separate gates. No native behavior, power-loss durability or SEC
authenticity is established by offline mocks or recovery.

HEAD and the empty index are preserved; all three protected SHA-256 hashes match.
`backend/.env` remains uninspected, unhashed and unmodified. Leave all four files
unstaged and uncommitted. Suggested eventual commit message:
`fix(sec): close dormant capture cancellation, identity and recovery gaps`.
