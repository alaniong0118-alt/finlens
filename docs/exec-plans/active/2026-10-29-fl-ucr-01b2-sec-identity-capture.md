# FL-UCR-01B2 bounded synthetic SEC capture

Status: completed local FL-UCR-01B2-P2 correction; focused Astra re-review pending.
Kept at the exact authorized active-plan path; not a roadmap acceptance claim.
Roadmap phase: scoped U1/U2 enabling kernel; no roadmap item accepted.

## Objective
Retain bounded immutable synthetic representation-body bytes, a canonical receipt,
and the existing UCR-01B1 source-bound issuer inventory, without external effects.

## Current architecture and context
Read root AGENTS.md, .agent/PLANS.md, ROADMAP.md, U1-U6, shared C1-C4/C7-C9,
data-sources.md and the requested Python contracts. Operational sec_client imports
configuration/environment and HTTP code; this module must never import it or
release_policy. Reuse research_contracts, universal_identity and sec_identity_source.
Starting main HEAD: f01e5e02eda7ba4e0a06014bea7bbf36eb428f55; index empty.
Only existing exceptions: frontend/next-env.d.ts (F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0),
canary-aapl_guarded_live_20261010_111844_3580610-publication.json
(A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C),
refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json
(F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C),
both report files under backend/reports/. Verified before edits.

## Constraints
Create only this plan, backend/app/sec_identity_capture.py and
backend/tests/test_sec_identity_capture.py. Preserve every existing file. Never
inspect/hash backend/.env. No network, DB, service, model, dependencies or Git writes.

## Non-goals
Real transport, authenticated owner/source custody, authority admission, durable
idempotency/quarantine, runtime termination guarantees and production integration.

## Implementation stages
1. Record the four mandatory P2 corrections and interfaces before code.
2. Implement immutable declarations, bounded validation, receipt and source sidecar.
3. Implement focused boundaries, negative cases, mutation and fresh-process isolation.
4. Run only the new suite, scoped syntax/whitespace and preservation checks.
Recovery: remove only these newly created files if requested; no existing rollback.

## Decisions
2026-10-29, mandatory Astra P2 corrections:
- P2-1: structural capture/binding validation is timeless. Explicit
  decide_synthetic_delivery(capture, context=...) consumes a fresh finite synthetic
  observation; cancellation/revocation/deadline deny after successful capture.
  Rebinding never checks or renews delivery. Observations are not authenticated grants.
- P2-2: retain only content-length, transfer-encoding, content-encoding, content-type,
  date, etag and last-modified; lowercase sorted JSON pair arrays. Validate all
  supplied headers, including forbidden location/content-range/trailer. Header
  representation is ASCII name + ': ' + value + CRLF, sum <=16,384, separately
  from canonical receipt UTF-8 bytes <=16,384. Closed fixed-order compact JSON
  includes capture_kind='synthetic'. No truncation or authenticated-hash inference.
- P2-3: PhaseCheckpoints has six required singleton fields, not phase-name lists.
  Body observations are an exact tuple, at most one per block, indexes contiguous.
  Check collection type/count before elements. Exact integer offsets from the
  single operation start: 30s successful-delivery maximum, 2s cleanup allowance.
  These are supplied logical times, not measured runtime or process guarantees.
- P2-4: ReplayIdentity includes canonical UUID, principal/session refs, canonical
  CIK through exact request, policy ref/revision, canonical original start and
  original relative deadline. Revalidate complete prior bytes/receipt; compare
  entire identity; fresh observations separately. prior requires exchange=None.
  Returned prior is historical capture, never fresh SEC verification. No persistent
  attempt discovery, network reconciliation, exactly-once guarantee or quarantine.

Chosen public interfaces: build_submissions_request(expected_cik),
capture_synthetic_submissions(request, *, context, exchange, prior=None),
bind_synthetic_capture(capture), decide_synthetic_delivery(capture, *, context).
CapturedIdentityInventory retains capture and SourceBoundIdentityInventory and
offers source_binding_for(candidate) returning the complete capture sidecar.

## Discovered issues
- Self-review tightened digest scalar types and added source identity/parser revision
  to the closed receipt, preventing silent receipt reuse across parser revisions.
- Self-review corrected a mutation probe that could have counted an unrelated
  rejection as a kill. Final controls require a dedicated IntendedBehaviorFailure;
  different rejection codes, exceptions and import failures fail the test instead.

## Progress
- [x] Baseline and protected hashes checked; requested contracts inspected.
- [x] Interfaces and all mandatory corrections recorded before implementation.
- [x] Implementation and self-review.
- [x] Focused tests, mutation controls, isolation, syntax and whitespace.
- [x] Final preservation checked; engineering handoff recorded below.

## Test and validation strategy
Use authored synthetic bytes only. Boundary validators may pass independently
while downstream parser/receipt constraints reject; never weaken UCR-01B1.
Run backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_sec_identity_capture.py
from repository root; compile sources in memory; scoped whitespace checks.
Mutations first verify original assertions, then require intended AssertionError
under in-memory source mutation, never count exceptions/import failures as kills.

## Completion criteria
Only three new files; exact focused suite passes; all P2 controls and isolation
have executed evidence; preserved HEAD/index/hashes; review readiness reported.

## Final outcome
Implemented only the two new Python files and this exact plan. No existing files
modified. No staging, commit, push, deployment, network/SEC, DB, service or model
activity. backend/.env was never inspected, hashed or modified.

### Public records and behavior
All ten public records are frozen slotted dataclasses: SubmissionsRequest,
ReplayIdentity, SyntheticObservation, SyntheticContext, PhaseCheckpoints,
BlockObservation, SyntheticExchange, SyntheticCapture, CapturedIdentityInventory,
and SyntheticDeliveryDecision. Nested inputs use exact immutable
types; collections are tuples. Public consumers reconstruct and validate their
inputs, including constructor-bypassed captures and sidecars. This is structural
defense, not protection against arbitrary hostile Python/native execution.

The four public operations above and three independent budget validators
(validate_body_blocks, validate_response_headers, validate_receipt_bytes) remain
pure. No executable callback or injected transport is accepted.
The receipt has fixed schema fl-ucr-01b2.synthetic.v1, stable insertion order,
compact UTF-8 JSON, lowercase sorted retained header pairs, source identity/parser
revision, immutable replay identity, artifact reference, body/block hashes and
lengths, phases, capture observation, framing/TLS declarations and all counters.
Full supplied header pairs remain in the capture; only allowlisted pairs enter
the receipt. Hash consistency never authenticates SEC origin or ownership.

bind_synthetic_capture returns both the capture and existing
SourceBoundIdentityInventory. Its source_binding_for(candidate) delegates to the
existing envelope and returns the complete captured sidecar. CIK, current-name,
former-name and contains-name candidates remain unverified issuers, with no
authority IDs, security/listing identities, publications or financial facts.

### Checks actually run (repository root, 2026-10-29)
- Focused command, final run:
  `.\backend\.venv\Scripts\python.exe -I -S -B backend/tests/test_sec_identity_capture.py`
  **25 tests passed, 0 failures, 0 errors, 0 skips**, 0.793s. Includes the eight
  mutation subcases below; not 25+8 independent unittest methods. Earlier focused
  runs also passed; no completed milestone or broad backend suites were run.
- Scoped in-memory compile of both Python sources passed, using the same isolated
  Python runtime with -I -S -B. No py_compile/bytecode output.
- Final `git -c core.autocrlf=false diff --no-index --check -- NUL <path>` for
  each new path produced no diagnostics; direct trailing-whitespace checks passed.
  An initial verification wrapper incorrectly required exit 0 for no-index diffs;
  it failed on the normal difference exit 1. Corrected wrapper accepts 0/1 only
  with empty stdout/stderr and passed. Earlier Git calls emitted LF/CRLF notices.
- Final main HEAD remains f01e5e02eda7ba4e0a06014bea7bbf36eb428f55, index empty.
  Git status contains exactly the three original exceptions plus these three new
  untracked files. All three original SHA256 values listed above match unchanged.
- Fresh child process: denied operational SEC/config/release/database/model/HTTP
  imports; denied environment access, network/socket creation, subprocesses and
  filesystem writes during import. Import machinery may read Python source/cache
  files. After import, open APIs are also denied. Capture, binding, three candidate
  lookups, replay and delivery/revocation executed under those guards and passed.
  AST independently restricts the module to dataclasses/hashlib/json/re and the
  existing pure research_contracts/sec_identity_source modules. This test harness
  is evidence of tested isolation, not an OS sandbox or universal effect proof.

### Mutation evidence actually executed
Each original probe passed first; each of eight in-memory mutants then produced
the intended dedicated assertion failure. Zero survivors or unrelated exceptions.

| Correction / mutant | Intended failed behavioral assertion |
|---|---|
| P2-1 expiry check removed | Final synthetic delivery must be denied after deadline. |
| P2-1 revocation check removed | Final synthetic delivery must be denied after revocation. |
| P2-2 receipt cap removed | 16,385 receipt bytes must reject with receipt_size. |
| P2-2 discriminator check removed | A bypassed live-tagged capture must reject with capture_kind. |
| P2-3 observation tuple guard removed | Mutable block-observation list must reject before traversal. |
| P2-3 exact-int check weakened | Boolean nanosecond offset must reject with observation_offset. |
| P2-4 complete replay comparison removed | Changed original start must reject with replay_identity. |
| P2-4 prior/exchange exclusion removed | Supplied prior plus exchange must reject with prior_with_exchange. |

### Resource and time acceptance boundaries
Independent exact/one-over tests cover one issuer/request/concurrency, zero
retries/redirects, 4,194,304 body bytes, 65,536 block bytes, 1,024 blocks, 64 header
pairs, 128-byte names, 2,048-byte values, 16,384 aggregate header bytes, 16,384
encoded receipt bytes, 256 ASCII User-Agent bytes, 5s connection/write/read
inactivity, 1s pool, 10s header phase, 30s operation, 2s cleanup and 1s minimum
request-start spacing (one-nanosecond violation). Full capture tests include exact
4MiB body and exact 16KiB canonical receipt; their immediate overflows reject.
An exact aggregate-header-budget valid exchange can fail receipt-size admission.
A valid 1,024-block transcript fails the independent receipt cap. No truncation.

All offsets use original_start at zero. Pool/connect/write/header intervals are
consecutive; header phase starts after write; read inactivity covers header-to-
first-block, inter-block and last-block-to-body-end gaps. Body ends by deadline.
Cleanup may structurally end by 32s, but a capture/final delivery at 32s is denied.
Start-spacing declarations additionally fit the finite 30s logical horizon;
operation deadlines are exact integers in [1ns,30s]. Final observations are
bounded to [0,32s]; larger/invalid observations reject structurally. These logical
budgets do not bound RSS, CPU, real elapsed time, blocked I/O or process exit.
Existing UCR-01B1 byte/parser limits remain unchanged and independently enforced.

### Replay, delivery and authority limitations
Structural rebinding can inspect historical bytes indefinitely, using their
original valid observation, but cannot renew origin/deadline or issue permission.
Replay requires the entire prior capture/receipt to validate, identical complete
replay identity, no exchange, and separately validated nondecreasing fresh
cancellation/revocation observations. Reuse returns the historical prior unchanged.
Delivery requires another matching-identity observation; decisions are historical
synthetic descriptions, not reusable authenticated grants or runtime enforcement.
Supplied observations can be fabricated. Self-consistent fabricated captures are
still synthetic. Stateless code cannot discover omitted prior attempts, establish
durable idempotency, reconcile uncertain dispatch, persist quarantine or prove
that a cancellation/revocation was honestly reported.

GO for independent Astra High implementation review; no independent review has
occurred in this task. NO-GO for real acquisition or official authority admission.
Outstanding separately authorized work: real authenticated owner/session and
policy resolution; reviewed SEC contact/fair-access rules; restricted HTTP/DNS/TLS
and redirect/framing/encoding enforcement; measured streaming/resource/deadline/
cancellation and cleanup guarantees; durable attempt/custody/idempotency and
uncertain-outcome quarantine/reconciliation; retention/rights/artifact access
controls; independent official issuer authority admission and runtime acceptance.

Suggested commit (not executed):
`feat(identity): add bounded synthetic SEC capture kernel`

## FL-UCR-01B2-P2 correction (2026-10-29)

### Review finding and bounded plan before implementation
The coordinator supplies Astra High's FAIL / NO-GO for Git Step 1: one P2,
no P0/P1. The delivery function and P2-2/P2-3/P2-4 passed that independent review.
The prior GO-for-review statement above is historical, not an acceptance verdict.
Current inspection confirms SyntheticDeliveryDecision checks allowed versus reason
but never compares reason with its observation, and carries no original deadline.
Thus direct construction/reconstruction can label revoked/cancelled/expired
observations allowed, and cannot validate operation-specific shorter deadlines.

Authorization is only to modify the same three existing untracked files. Starting
counts: implementation 506, tests 617, plan 210 (1,333 total). Main HEAD/index,
six-path worktree status and all three protected hashes rechecked unchanged.
No other files, accepted policies, receipts, parser or replay behavior may change.

Minimal design: require original_deadline_ns on SyntheticDeliveryDecision; add a
shared pure _delivery_reason(observation, original_deadline_ns), used by both
the record constructor and decide_synthetic_delivery. Preserve cancellation,
then revocation, then expiry precedence and inclusive deadline (offset <= deadline).
The helper revalidates exact observation types and the original [1ns,30s] deadline.
The factory passes the immutable capture-matching context's original deadline.
Constructors/replace reject contradictory reason/observation with sanitized
decision_lifecycle errors. This remains supplied synthetic metadata, not authority.
No existing public operation consumes decision records; capture/context type
boundaries must reject bypassed decisions passed in their place. No new API needed.

Planned validation: direct/reconstruction lifecycle matrices, shorter deadlines,
combined flags/precedence, strict scalar types, constructor bypasses, historical
binding, after-capture denial and original replay lifetime; new targeted constructor
and reconstruction mutation probes. Run only the focused suite and scoped syntax/
whitespace/preservation checks; retain existing fresh-process isolation evidence by
actually rerunning its test in that suite. Outcomes pending.

### P2 correction outcome and executed evidence
- Before edits to Python, reproduced four contradictory direct constructions:
  revoked, cancelled, combined flags and 30,000,000,001ns, all allowed=True.
  Their four unchanged dataclasses.replace reconstructions were also accepted.
- Added required original_deadline_ns after observation in the public decision
  record. All four public operation signatures remain unchanged. Manual record
  constructors must supply the original deadline; there is no global fallback.
- Shared _delivery_reason revalidates observation and deadline and implements
  the existing cancelled > revoked > expired > synthetic_only precedence.
  The factory supplies the original deadline from its capture-matching identity;
  the constructor rejects any reason inconsistent with the lifecycle observation.
  Existing allowed/reason shape checks remain. Rejections use payload-free
  decision_lifecycle, deadline, observation_type/offset/flags codes as applicable.
- Frozen/slotted record semantics remain. Construction and replace revalidate
  forged nested observations/deadlines and contradictions. No existing public
  operation consumes a delivery decision as permission; tests verify that valid
  and bypassed decision objects cannot masquerade as captures, prior captures or
  contexts at those boundaries. Arbitrary object.__setattr__ or native execution
  is not a sandboxed threat model, and reading an unchecked bypassed attribute
  directly cannot establish a valid decision.
- Direct and reconstruction regressions cover revoked/cancelled/combined flags,
  global and shorter expiry, exact inclusive deadlines at 1ns/10ns/30s, correct
  denied reasons/precedence, contradictory reasons, invalid exact types and
  lifecycle metadata altered through constructor bypass. Shortening a carried
  deadline below an allowed observation rejects on construction/reconstruction.
- Factory regressions cover a 10ns original deadline, success at 10ns, expiry at
  11ns, cancellation/revocation after capture, combined flags after expiry and
  cleanup-horizon observations at 32s. Historical binding still succeeds after
  denied delivery. Replay at 10ns retains the original start and deadline;
  replay at 11ns denies expiry; changed original start/deadline reject.
- Final requested command from repository root:
  `.\backend\.venv\Scripts\python.exe -I -S -B backend/tests/test_sec_identity_capture.py`
  **30 tests passed, 0 failures, 0 errors, 0 skips**, 0.828s. Only this focused
  suite was run. Its fresh-process import/execution isolation and AST checks pass;
  the child additionally executes direct/reconstruction lifecycle rejection under
  the existing effect-denial guards. Import-only Python source/cache reads remain
  allowed; no authenticated or OS-sandbox guarantee is asserted.
- New mutation control: two in-memory mutants, 12 baseline probes pass followed
  by 12 intended dedicated assertion failures. Constructor guard removal is
  detected by five invalid lifecycle scenarios in direct and reconstruction paths
  (10 probes). Replacing the shorter deadline with the global maximum is detected
  in both paths (2 probes). Different errors/import failures do not count as kills.
  Existing eight mutation controls also pass: 10 mutants killed in total, with
  20 intended failing behavioral probes across both mutation tests, no survivors.
- Self-review confirms only the delivery record/helper/factory changed in the
  implementation. Accepted header/receipt, checkpoints, exact bytes, source binding,
  replay and resource policies are unchanged. Syntax is compiled in memory and
  whitespace checked only for the three authorized paths; no generated files.
- Final preservation: main at f01e5e02eda7ba4e0a06014bea7bbf36eb428f55, index
  empty, only the same six worktree paths, protected hashes unchanged as above.
  No .env inspection/hash, network/SEC/provider, DB, service, Docker, model,
  dependencies, production integration, stage/commit/push or deployment.

GO for focused Astra High P2 re-review, not Git Step 1 acceptance. The supplied
independent FAIL remains the review disposition until superseded by re-review.
All previous synthetic trust limitations remain: a consistent standalone declared
deadline/decision is not authenticated authorization or custody; no measured
elapsed-time/termination, real transport/TLS, durable idempotency/quarantine,
production custody or official authority admission is implemented.
Suggested commit (not executed):
`fix(identity): enforce synthetic delivery decision lifecycle invariants`
