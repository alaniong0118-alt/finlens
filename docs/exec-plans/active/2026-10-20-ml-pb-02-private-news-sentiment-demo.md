# ML-PB-02: private local news sentiment demonstrator

Status: completed for implementation/synthetic/native verification; real acceptance deferred.
Roadmap phase: bounded private offline demonstration; no next milestone.

## Objective

Build an independent, explicitly started loopback demonstrator, one memory-only
model worker, strict private IPC, accessible owned page and verified shutdown.
First prove atomic Windows child ownership with harmless processes. Stop if the
native support gate cannot pass; never substitute post-spawn job assignment.

## Current architecture and context

Read root AGENTS.md, ROADMAP.md and .agent/PLANS.md. ML-PB-01 is committed at
main/HEAD 0a042f91232182fa13503066ece8c21f494a2158; index empty. Existing
frontend/next-env.d.ts modification and two untracked AAPL reports are protected.
316 tracked/nonignored files fingerprinted in memory. Private ignored/untracked
backend/.env fingerprint retained only in tool memory; no secret output/backups.

## Constraints and non-goals

Only seven authorized paths: backend/scripts/evaluate_news_sentiment.py,
backend/tests/test_news_sentiment_baseline.py, docs/news-sentiment-baseline.md,
backend/scripts/serve_news_sentiment_demo.py, backend/scripts/news_sentiment_demo.html,
backend/tests/test_news_sentiment_demo.py and this plan. Retain plan here.
No real ZIP read/training/reproduction, actual HTTP demo startup or browser
acceptance in this phase. No database, Docker, app/frontend services, external
network/provider, installation, persistent model/corpus/cache/report artifacts,
Git staging, commits, pushes or deployment. No weights redistribution clearance,
SEC/cybersecurity classifier, confidence, advice or returns/portfolio claims.

## Implementation stages

1. Preserve baseline; implement/test native atomic Job Object creation gate.
2. After gate passes, extract equivalent ML helpers and implement guarded worker,
   bounded framed IPC and parent-owned lifecycle/deadlines.
3. Implement standalone local HTTP API and accessible single-file UI.
4. Focused synthetic and harmless native tests; scoped syntax/quality checks.
5. Document exact evidence/deferred gates, self-review and final scope/integrity.

## Decisions

- Windows 10 build 19045 / CPython 3.14.7 x64 is the observed environment.
- Use STARTUPINFOEXW with PROC_THREAD_ATTRIBUTE_JOB_LIST and HANDLE_LIST in
  CreateProcessW, never Popen plus AssignProcessToJobObject. Job is unnamed,
  noninheritable; kill-on-close, job committed memory 1 GiB, active processes one,
  no breakaway. Retain process handle and verify termination.
- Parent deadlines: 60s before process creation through ready, 2s complete
  inference IPC, 5s cleanup. OS scheduling is not an exact real-time guarantee.
- Parent pipe writes use independently interruptible background I/O; reads use
  bounded nonblocking availability checks. No pickle, public IPC or model transfer.
- HTTP body 16 KiB / read 5s; sentence 2000 Unicode code points, single line.
- Preserve evaluation CLI/audit behavior; synthetic equivalence is not a real
  corpus reproduction. Fixed C=10 demonstration fits original train partition only.

## Discovered issues

Native gate resolved two development issues without weakening requirements:
Windows venv python.exe is a redirector that needs another process, incompatible
with the one-active-process job. Native children therefore use the exact base
interpreter with explicitly selected prepared venv packages. CompareObjectHandles
is available through the Windows handle API set, not this kernel32 export table.
An import-only native ML dependency probe hit the unchanged job memory limit
before BLAS thread limits were applied. The minimal child environment now pins
BLAS/OpenMP threads to one before imports; bounded dependency bootstrap passes.
No limit was increased and no corpus was read during that investigation.

## Progress

- [x] Repository guidance, expected baseline, scope and private fingerprints.
- [x] Native atomic ownership gate passed before full implementation: 7 passed
  in 0.41s on Windows build 19045, CPython 3.14.7 x64. JOB_LIST/HANDLE_LIST process
  creation, exact limits, live membership, noninheritance, abrupt parent death,
  memory/process denial, fail-closed creation and blocked-write interruption.
- [x] Shared helpers, worker, IPC, HTTP and UI.
- [x] Focused synthetic/native tests and scoped checks: 140 passed, no failures/skips.
- [x] Documentation and self-review; final preservation reconciliation below.

## Test and validation strategy

Use installed interpreter with -I -B. Disable pytest cache and third-party plugin
autoload. Only baseline/new focused test modules. In-memory synthetic corpus and
controlled workers; native tests use harmless owned Python children, bounded
deadlines and cleanup. Cover abrupt owner death, atomic membership, inheritance,
spawn/attachment failure, limits, blocked IPC, stale/partial responses, HTTP
security, cancellation ownership, sanitized errors and no persistent exports.
No live listener or original ZIP. Compile sources in memory; git diff --check.

## Completion criteria

Native gate passes; focused evidence supports implementation contracts; only
seven allowed files changed; baseline/private/protected files unchanged; index
empty/HEAD unchanged. State deferred real ZIP and browser gates explicitly.

## Final outcome

PASS WITH CONDITIONS for the bounded implementation phase. Ready for targeted
Astra High review and a separate real-ZIP/demo/browser acceptance checkpoint.
No real corpus, actual demo listener or live browser acceptance was exercised.
Only seven authorized paths changed; no Git staging/commit/push/deployment.
Suggested later commit: `feat(ml): add private local news sentiment demonstrator`.

## Actual verification evidence

Only the two focused modules ran, with installed dependencies and no caches:

```powershell
# cwd D:\Projects\finlens-foundation\backend
& '.\.venv\Scripts\python.exe' -I -B -c "import os,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.path.insert(0,os.getcwd()); import pytest; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','tests/test_news_sentiment_baseline.py','tests/test_news_sentiment_demo.py','--durations=3']))"
```

Final source run: **140 passed in 7.78s**, zero failures/skips: 59 baseline/helper
tests and 81 demo cases. Includes 11 real Windows native lifecycle/protocol cases.
A focused native-only run also passed **11 cases in 2.46s**. Earlier development
failures were diagnosed and fixed; these totals describe the final source run.
No production source/UI changed afterward; final edits only record documentation.

Native evidence on Windows 10 build 19045, CPython 3.14.7 x64:

- Initial seven native gate cases passed before implementing helpers/service/UI.
  JOB_LIST/HANDLE_LIST attributes succeeded in CreateProcessW; kernel query
  confirmed live child membership, flags 0x2208, active-process limit one and
  job committed-memory limit 1073741824 bytes. No post-spawn assignment API exists.
- Job handle is non-inheritable. A deliberately inheritable unrelated event was
  excluded; kernel object comparison guards against numeric handle reuse.
- Abrupt controller death during child startup and simulated inference caused
  owned child exit, verified on retained/opened process handles. Harness stdout
  reads and cleanup are independently bounded. Probe children have finite
  lifetimes; controllers are explicitly cleaned up.
- Invalid executable/atomic job attributes fail without an unowned child.
  Over-limit VirtualAlloc and child process creation are denied. A blocked pipe
  writer unblocks after owned termination; a separate harmless process survives.
- A real atomic-job worker exchanges framed JSON with a fake model, rejects
  unsupported features and exits on shutdown. Native warmup/inference timeout
  cases terminate and verify the owned child. An import-only bootstrap exercises
  installed ML dependencies under the real limits/audit policy, without fitting.

Synthetic evidence covers training-only features, fixed C=10 preparation with
controlled source/split metadata, no holdout predictions, zero-feature rejection,
readiness/failure, frame bounds before allocation, schemas/IDs/labels, duplicate,
stale/partial/disconnected messages, single ownership across cancellation, both
IPC directions completing before slot release, idempotent shutdown and explicit
unverified cleanup states. Parent I/O never waits synchronously for child work on
the HTTP loop. Warmup/inference deadlines are monotonic and do not auto-retry.

HTTP ASGI tests use no listener. They cover peer/Host/Origin/token/duplicate-header
admission, strict JSON/body/input bounds, body-read timeout, disabled routes and
WebSockets, security headers and sanitized validation/HTTP/general exceptions.
No input/token/path/child stderr is logged or echoed. The separate parent audit
bootstrap passes without serving HTTP; outbound connections/writes/app/provider
imports are denied by scoped Python guards, not claimed as OS sandboxing.

Two jsdom cases stub every fetch and load no remote resources. They verify
preparation/ready controls, label rendering, Clear, stale responses after Clear
and failure, immediate Stop clearing, explicit stopped confirmation and Ctrl+C
fallback when cleanup cannot be confirmed. This is DOM evidence, not actual
browser/mobile/accessibility acceptance. The owned JS was syntax-parsed using
installed TypeScript tools; no builds or emitted artifacts.

ML-PB-01 equivalence: in-memory execution of the committed baseline and modified
runner over identical authored synthetic rows produced equal split fingerprints
and full aggregate evaluation output. Aggregate comparison SHA256:
ECE7C768163B1A3517C15F631230810C814892E85F6F8E0A528790197E5F2164.
Parser/group/split/pin/audit/CLI-orchestration ASTs are identical to the committed
baseline. Constructor/helper coefficient and prediction equality also passes.
No real corpus reproduction is claimed for this phase.

Four Python files passed in-memory compile/AST checks. Scoped inspection found no
main-app/database/provider imports, Popen calls, extraction or model/corpus export
calls in the demo. Uvicorn configuration keywords match the installed API.
`git diff --check` passed; ordinary existing Windows autocrlf notices are not
whitespace failures and no Git/environment configuration was altered.

Tested source SHA256, retained for interrupted-task provenance:

- evaluate_news_sentiment.py: 4930BAF0E0A99C928071ACE7E5E94ACC988723039506A912D3EF6C9D886ED6F5
- serve_news_sentiment_demo.py: B34F79956904EB434CE55F7F949258BD87BDE27260A5E52560C20F5559624AA1
- test_news_sentiment_baseline.py: C1ECD5481D3683AC6F1D640BDD712EAAE62204369825DEA023438888274F938E
- test_news_sentiment_demo.py: 39D4BF8D5A2703ADF806156EDC331A767699ABA1CB0FCBFFA0DB071319397B7C
- news_sentiment_demo.html: 7EAA18429D0DC50039DEFA64DC5FC42A1CDBC16BF4C384E9371F71A42C572DA5

## Remaining acceptance and limitations

Separate coordinator approval is required before any original-ZIP read, real
evaluation reproduction, actual corpus warmup, private HTTP demo startup or live
browser acceptance. Measure real cold readiness, peak memory and repeated
inference latency under unchanged limits. Reject/fix discrepancies; do not raise
limits or alter labels/splits to force acceptance. Existing 85.67% accuracy/0.7998
macro-F1 are historical ML-PB-01 results displayed as such, not newly measured.

Private nonprofit academic use only; CC BY-NC-SA 3.0 citation/attribution retained.
No corpus/weights redistribution clearance, probabilities, SEC filing validation,
cybersecurity classifier, trading/portfolio/return predictions or production
claim. Python hooks and Job Objects are not complete filesystem/network isolation;
trusted operator/libraries/host required. OS scheduling is not hard real-time,
job committed memory is not exact RSS, and reference release is not secure erasure.

## Final integrity reconciliation

HEAD/main remains 0a042f91232182fa13503066ece8c21f494a2158; index empty.
Exactly three authorized existing files changed and four authorized files were
added. All other 313 initial tracked/nonignored paths remain byte-identical;
none was removed. No app, frontend, release, startup or dependency file changed.
The existing modified next-env file/two untracked reports remain pre-existing
status only, with unchanged SHA256:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- canary publication report: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- refresh discovery report: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

backend/.env remains ignored/untracked and matches its initial private in-memory
fingerprint. No values or private hashes are printed or persisted. The original
ZIP was not opened or hashed in this phase. A metadata scan of 410 workspace
files (excluding Git/dependency/Next-build trees) found no unexpected recent
files or new model/corpus/cache/temp/report/dump artifacts. All owned sources
match the final tested fingerprints above. Local doc links and whitespace checks
pass, including the seven untracked/modified task files and git diff --check.

No original-ZIP read/training/reproduction, corpus-backed worker launch, actual
demo listener, live browser, external provider/network service, database, Docker,
main backend/frontend, dependency installation or persistent configuration change
occurred. Native processes were synthetic, owned and bounded; ASGI/jsdom tests
used no HTTP listener. No staging, commit, push or deployment. Coordinator review
and separate real-ZIP/local-browser acceptance are the next authorization gates.
