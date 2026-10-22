# REL-DEMO-03C: bounded private evidence preservation implementation

Status: active; implementation prepared and synthetic checks passed; independent
safety review pending. Real execution remains NO-GO and is not authorized.
Roadmap phase: historical showcase evidence preservation, not runtime acceptance.

## Objective

Prepare a Windows-only seven-source/eight-output preservation tool and synthetic,
non-mutating tests for independent safety review. Preserve all historical outcomes.

## Current architecture and context

Baseline: main; HEAD and local origin/main are both
`cfa4521379bfde92331ba988b6b60a5887a39706`; index empty. The only initial
nonignored exceptions are frontend/next-env.d.ts and the two established AAPL
reports. Their SHA-256 values match the preceding assessments. Private backend/.env
is ignored; contents and hash are never read. All three authorized new paths were
absent. Root AGENTS.md, ROADMAP.md and .agent/PLANS.md were read.

The existing non-temporary Local AppData parent was assessed previously as private
to the operator, Administrators and SYSTEM. That historical assessment does not
replace approval-bound identity and ACL checks at future execution.

## Constraints

Only create/change:

- backend/scripts/preserve_showcase_evidence.py
- backend/tests/test_preserve_showcase_evidence.py
- this ExecPlan

No historical evidence writes, real destination creation, real receipt, ACL changes,
cleanup, bytecode/cache/temp artifacts, dependency installation, services, network,
database, browser, model or Git writes. Synthetic tests use memory-backed handles.
Never call tempfile.gettempdir(). Public files contain no personal absolute paths.

## Non-goals

Generic backup tooling, administrative-adversary containment, new acceptance,
public redistribution, automated approval, and clearing existing FAIL/MISSING gates.

## Implementation stages

1. Pin the committed manifest and fixed source/output identities.
2. Implement retained Windows directory/file handles and relative exclusive opens.
3. Implement copying, separate reread, embedded checks and private receipt semantics.
4. Exercise only memory-backed synthetic dependencies under filesystem-write guards.
5. Reconcile exact worktree scope and preservation, then hand off for safety review.

## Decisions

- Use ctypes and existing Windows APIs; no compiler, native build or new dependency.
- Anchor volume roots by approved volume GUID, descend one component at a time with
  NtCreateFile relative to retained directory handles, reject reparses, and deny
  write/delete sharing. Pathname-only preflight is insufficient.
- Require a separate private approval payload binding operator, reviewed tool hash,
  known-folder parent, source mapping, and every pre-existing ancestor/file identity
  and security descriptor. This is an operator/coordinator attestation, not a signature.
- Default invocation performs no filesystem mutation and does not load Windows APIs.
- Bytecode suppression is set before non-builtin imports. Real execution additionally
  requires isolated/no-site/no-bytecode interpreter flags. Git reads clear inherited
  Git environment overrides, disable tracing and lazy fetch, and pin the raw blob.
- The private receipt records completed evidence checks, not self-verification.
  Overall custody success is emitted only after independent receipt rereading.
  Failures retain partial artifacts and never delete, overwrite or retry.
- The native adapter pins the FOLDERID_LocalAppData GUID, uses DONT_VERIFY rather
  than CREATE, and requires the resolved result to match private approval. Volume
  roots are opened through approved volume-GUID names rather than drive-letter
  resolution. All descendants are single-component RootDirectory-relative opens.
- Existing handles require FILE_OPEN; all new handles require FILE_CREATE and the
  returned FILE_CREATED disposition. ShareAccess is FILE_SHARE_READ only. Directory
  handles request list/traverse/attributes/security-read/synchronization access;
  existing source handles request read access. Only new output handles request write.
- Every approved identity consists of volume serial, 128-bit file ID (native byte
  order, lowercase hex), normalized volume-GUID final path, SHA-256 of the queried
  owner/DACL security descriptor, and directory flag. New objects must resolve as
  immediate children of the retained parent on its volume, then retain their IDs.
- Private parent and new-object ACLs must contain exactly three full-control allow
  ACEs: approved operator SID, SYSTEM and Administrators. Unexpected principals,
  masks, inheritance or owner fail closed; no permission repair is attempted.

## Discovered issues

Windows kernel semantics and real permissions cannot be accepted using synthetic
tests. Directory sharing exclusions may refuse an otherwise usable live machine;
failure must remain NO-GO rather than weakening them.

Existing source directories reportedly have additional write-capable principals,
including unresolved SIDs. The implementation does not declare those principals
trusted. Approved identities, relative traversal, write/delete sharing exclusions,
copied-byte hashes and final source rechecks remain required together. A trusted
operator/administrator and kernel are assumptions; administrative adversaries are
outside this bounded design. Existing writable memory mappings are not excluded by
sharing modes alone; expected hashes and final integrity checks remain necessary.

Receipt verification cannot be self-attested circularly in the same immutable file.
The receipt records evidence verification completed before its creation, preserves
historical states, and explicitly says custody completion is NOT SELF-ATTESTED.
Only successful independent receipt rereading, final source/identity rechecks and
handle closure permit the caller to receive overall PASS plus the receipt hash.
If those last steps fail, partial outputs/receipt remain and the operation is NO-GO.

## Progress

- [x] Baseline, protected hashes, ignored private metadata and three absent paths checked.
- [x] Scope and native containment design recorded before implementation.
- [x] Implementation prepared.
- [x] Non-mutating synthetic verification completed: 38 tests, zero failures/skips.
- [x] Preservation reconciliation and self-review completed; exact three-file scope.
- [ ] Independent safety review (separate coordinator-controlled gate).

## Test and validation strategy

Use the existing Python interpreter with `-I -S -B`, in-memory module loading and
stdlib unittest. Install an audit hook before test imports that rejects filesystem
mutation, subprocesses and ctypes DLL loading. No pytest cache or temporary files.
Tests must cover source/ancestor identity, reparse/ACL/namespace failures, exclusive
creation, byte/digest/embedded mismatches, partial writes, reread/receipt failure and
no retry. Native Windows execution remains NOT TESTED.

### Results actually obtained

The first guarded run passed 30 tests. Self-review then strengthened the core's
approval gate, native error-handle disposal, exact read bounds, known-folder return
validation and directory traverse access. Eight additional tests covered multi-chunk
copying, core authorization, weak private ACLs, corrupt rereading, an explicit rerun
after partial failure, final handle-close failure, Git trace/lazy-fetch suppression,
and interpreter isolation. Per-source historical revision/scope/classification are
also carried unchanged from the pinned manifest into the receipt. Intermediate
36/37-test runs followed corresponding changes. The final guarded run passed
**38 tests in 0.057 seconds**, zero failures/errors/skips, exit 0. Subtests and
repeated runs are not additional unique tests.

All guarded runs reported **zero forbidden filesystem/process/native-DLL attempts** and
**zero historical source handles opened**. Every storage handle used by tests is a
memory double. Python loaded the two new modules via compile/exec in memory; no
application package, pytest fixture, model, database or service was imported.
The pinned committed manifest was read separately with read-only Git, preserving
raw blob bytes; its SHA-256 and all seven selected locators/digests/sizes matched
the tool constants. Historical source files themselves were not opened or hashed.

### Reproducible guarded verification

Run the following from the repository root using existing dependencies only. The
payload and captured Git blob remain in memory. It deliberately blocks ctypes DLL
loading as well as mutation and subprocesses inside the test interpreter.

```powershell
$rel03cInfo=[Diagnostics.ProcessStartInfo]::new('git')
$rel03cInfo.WorkingDirectory=(Get-Location).Path
$rel03cInfo.UseShellExecute=$false
$rel03cInfo.RedirectStandardOutput=$true
foreach($arg in @('--no-optional-locks','--no-replace-objects','-c','core.fsmonitor=false','show','cfa4521379bfde92331ba988b6b60a5887a39706:docs/showcase/evidence-manifest.json')){$rel03cInfo.ArgumentList.Add($arg)}
$rel03cProcess=[Diagnostics.Process]::Start($rel03cInfo)
$rel03cMemory=[IO.MemoryStream]::new()
$rel03cProcess.StandardOutput.BaseStream.CopyTo($rel03cMemory)
$rel03cProcess.WaitForExit()
if($rel03cProcess.ExitCode -ne 0){throw 'Committed manifest read failed'}
$rel03cManifest=[Convert]::ToBase64String($rel03cMemory.ToArray())
$rel03cMemory.Dispose()
$rel03cProcess.Dispose()
$rel03cHarness=@'
import os, sys
sys.dont_write_bytecode = True
violations = []
mutations = {'os.mkdir','os.remove','os.rename','os.rmdir','os.chmod','os.chown','os.link','os.symlink','os.utime','os.truncate','os.ftruncate','shutil.copyfile','shutil.copymode','shutil.copystat','subprocess.Popen','os.system','os.startfile','ctypes.dlopen','winreg.CreateKey','winreg.SetValue','winreg.DeleteKey','winreg.DeleteValue'}
def audit(event, args):
    forbidden = event in mutations
    if event == 'open':
        mode, flags = args[1], args[2]
        forbidden = (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
    if forbidden:
        violations.append(event)
        raise RuntimeError('Forbidden test side effect: ' + event)
sys.addaudithook(audit)
import base64, pathlib, types, unittest
root = pathlib.Path.cwd()
script_path = root / 'backend/scripts/preserve_showcase_evidence.py'
test_path = root / 'backend/tests/test_preserve_showcase_evidence.py'
implementation = types.ModuleType('preserve_showcase_evidence')
implementation.__file__ = str(script_path)
sys.modules[implementation.__name__] = implementation
exec(compile(script_path.read_bytes(), str(script_path), 'exec'), implementation.__dict__)
tests = types.ModuleType('test_preserve_showcase_evidence')
tests.__file__ = str(test_path)
tests.PINNED_MANIFEST = base64.b64decode('__REL03C_MANIFEST__')
sys.modules[tests.__name__] = tests
exec(compile(test_path.read_bytes(), str(test_path), 'exec'), tests.__dict__)
suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
print('GUARD: mutation/process/native-DLL attempts=' + str(len(violations)))
print('NATIVE WINDOWS COPY: NOT TESTED; HISTORICAL SOURCES OPENED: 0')
raise SystemExit(0 if result.wasSuccessful() and not violations else 1)
'@
$rel03cHarness=$rel03cHarness.Replace('__REL03C_MANIFEST__',$rel03cManifest)
$rel03cHarness | & '.\backend\.venv\Scripts\python.exe' -I -S -B -
```

### Future private approval contract (not supplied or generated here)

The explicit --execute-approved entry point reads at most 65,536 bytes of UTF-8
JSON from stdin. Duplicate keys, unknown top-level fields, missing component
bindings and extra component bindings are rejected. Required fields:

- schema_version: integer 1; execution_authorized: boolean true.
- approved_revision: the pinned revision above.
- reviewed_tool_sha256: exact reviewed tool bytes; independently checked by the CLI.
- independent_review_sha256: separately retained safety-review record digest.
- operator_sid and operator_name: expected Windows token SID and GetUserNameW name.
- local_app_data: privately approved Known Folder path; raw environment expansion
  is never used to choose the destination.
- operator_temp: privately approved original source mapping, not newly discovered
  temporary storage.
- bindings: exactly every existing component of all seven source paths and the
  private parent, including roots, with the five identity fields described above.

No real approval payload, destination, receipt or evidence copy was created. The
payload is not a signature and cannot defend against a malicious authorized operator.
Approval values must come from separate review; this tool does not auto-enroll them.
Trusted launch of the independently reviewed tool bytes is a prerequisite. The
self-hash check is not authentication of already-running code or a hostile Python
installation. Launch review must retain the isolated/no-site/no-bytecode flags.

Destination child: FinLens-ShowcaseEvidence-REL-DEMO-03-v1. Its seven basenames are
risk-browser-report.json, ml-static-report.md, ml-static-summary.json,
ml-desktop-capture.png, ml-mobile-capture.png, qa-risk-original-fail.json and
qa-risk-teardown-fail.json; custody-receipt.json is the only additional output.
Total historical bytes: 1,341,222. Both embedded PNGs remain inside the risk JSON.

## Completion criteria

Exactly three authorized new files; fixed seven-source/eight-output contract;
reviewable native handle-relative containment; fail-closed synthetic cases; no real
operation; original protected state preserved; explicit independent-review handoff.

## Final outcome

Implementation candidate is CONDITIONAL for independent review, not accepted for
execution. Real Windows ABI calls, volume/handle queries, sharing contention,
permission inheritance, reparse races, actual NTFS creation and durability are
NOT TESTED. No real destination handle or source handle was opened by the tool.

Final read-only reconciliation verified main/HEAD/local origin unchanged, empty
index, exactly the three authorized new files plus the three original exceptions,
all three protected hashes unchanged, and private environment metadata unchanged.
In-memory AST, trailing-whitespace, newline, personal-path and plan checks passed.
Per-file Git no-index whitespace checks emitted no diagnostics; exit 1 records
the new-file differences rather than a passing test exit. No other files changed.

Independent safety review must examine the exact three new files, native API
signatures/flags, approval binding, ancestor retention, relative exclusive opens,
ACL admission, independent rereading, receipt limitations and failure retention.
Do not infer authorization from synthetic tests or this plan. Any future native
validation or actual operation needs explicit separate coordinator authorization.
No stage, commit, push, evidence operation or next milestone is authorized.

Suggested later commit, after review and separate Git authorization:
`feat(showcase): prepare bounded private evidence preservation`.

## Focused P3 cleanup correction

Independent review subsequently returned PASS WITH CONDITIONS for the inactive
implementation, with no confirmed P0-P2 findings and one confirmed P3 finding:
Known Folder HRESULT validation preceded try/finally, leaking an allocated output
buffer on failure. This later review supersedes the earlier pending-review wording
for the original snapshot; the correction itself awaits focused re-review.

The native call and result validation now occur inside the existing try/finally.
CoTaskMemFree is called exactly once when the output pointer is non-null, including
failure paths. Null output fails closed without a free call. Successful path
validation and all other native, identity, ACL, containment and copying logic are
unchanged. No generic allocation framework was introduced.

Six new memory-only tests invoke the actual method on an uninitialized adapter
with controlled Python fakes, never ctypes or real native APIs. Before the source
correction: six tests ran, four passed and two failed, reproducing the allocated
failed-HRESULT leak and an exception-after-allocation leak. After the correction:
all six passed, zero errors/skips. Tests also cover successful allocation, failed
null output, successful HRESULT with null output, path-validation failure,
failure propagation and exactly-once cleanup. Both runs used the existing
isolated/no-site/no-bytecode harness and audit guard, with zero forbidden
mutation/process/native-DLL attempts and zero historical source handles opened.

For focused reproduction, use the guarded harness above, omit its manifest Git
capture, set tests.PINNED_MANIFEST to None, and load only
unittest.defaultTestLoader.loadTestsFromTestCase(tests.KnownFolderCleanupTests).
The original synthetic tests were preserved and were not broadly rerun. The
seven-source/eight-output allowlist and all historical classifications are unchanged.

Native Windows behavior remains NOT TESTED. Real copying remains NO-GO pending
focused independent re-review and separate coordinator authorization. No real
destination, receipt, historical evidence access, ACL change or Git write occurred.
