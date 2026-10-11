# Disabled AAPL Net Margin activation entry point

Status: disabled safety infrastructure prepared for independent Astra High review.
**Actual activation is not approved or enabled.** Baseline main / d6173d0. The separately
reviewed [dormant proposal](aapl-net-margin-proposal.md) and its immutable financial
records/pins remain unchanged. See [implementation](../backend/app/aapl_net_margin_activation.py).

## Operator boundary

`activate_aapl_net_margin(*, operator_authorized=False, reviewed_ref=None)` is an
internal process-local entry point. `_ACTIVATION_ENABLED` is literally **False**.
Disabled calls return False before proposal imports, store configuration, database
sessions or evidence I/O. Ordinary imports/startup/requests never register anything.
The explicit `python -m app.aapl_net_margin_launcher --profile <protected-profile>`
operator path fails closed with exit status 78 while the literal source gate is
false, before operator/store/database/evidence I/O. No CLI option or environment
variable enables the gate, and there is no persisted activation state.

Future activation requires separately approved source changes and commissioned
operator/deployment controls. The helper now also requires the owning launch
lifecycle with authenticated policy and a held maintenance lease. Its legacy
boolean/reference checks remain acknowledgments, not credentials. An existing
financial request context is also rejected. No enabled flag is added here.

**Deployment trust and maintenance exclusion remain unresolved and block activation.**
`aapl_operator_policy` reads TokenUser SID from the actual Windows process token;
it never reads claimed usernames/SIDs from arguments or environment variables.
The strict profile schema binds the reviewed permission/ref/version, approval and
evidence-policy digests, authorized SIDs, deployment ID, interpreter, import roots,
file pins and original-store path. Profiles reject duplicate/extra fields and
changed pins. These shape/hash checks are not proof of trusted ownership.

The production profile ACL verifier, complete deployment-integrity verifier and
maintenance-exclusion provider deliberately reject every real invocation. Tests
replace these private boundaries with reversible synthetic fixtures; production
has no skip-verification/synthetic flag. No operator profile, real SID allowlist,
ACL or original-store configuration is installed.

Commissioning requires independently verified Windows owners/DACLs on the profile,
all ancestor directories, launcher/backend code, interpreter/DLLs/stdlib/dependencies,
and the complete import closure. Untrusted writers, import hooks/search roots,
user-site injection, redirection or unverifiable ownership must reject. The protected
deployment mechanism must establish integrity before executing Python; self-hashing
already untrusted code cannot authenticate itself. Exact deployment and scope must
be approved through authenticated OS/deployment administration, not public IDs.

## Fresh validation before registration

The entry point only supports initial installation of this single reviewed pair.
It refuses existing selection/denominator/policy records and nonempty global Revenue
equivalences; it never clears or merges them. Existing withdrawal/supersession state
is checked by the reviewed evaluator against the exact proposed approval lineage.
Revoked/superseded approvals and withdrawn successors cannot be revived.

After those checks, the entry point uses the existing operator-configured
`FINLENS_SEC_ORIGINAL_STORE`, with no default or caller-supplied path. The root must
be absolute and unredirected. It creates a **new** application database session
internally; caller sessions, fact subsets, evidence objects and policies are not
accepted. `read_session` establishes PostgreSQL repeatable-read/read-only state,
which is explicitly checked before observations are loaded.

The existing financial dataset loader supplies all AAPL facts. All eligible raw
Revenue/Net Income candidates for the proposed end/kind, including changed starts,
enter the manifest. CIK/ticker, company version triple, complete publication inventory
and snapshot digest must exactly match the unchanged proposal. The legacy target
publication data version **0** is bound as 0, not replaced by company version 1 or
treated as equivalent to a later publication.

The existing adapter's `_verify_policy` performs complete local original inventory,
artifact/receipt byte hashing, official capture identity/provenance reconciliation,
DEI/context/unit/dimension parsing, exact statement/fact locators, original/raw
candidate closure, approval digest and evidence fingerprint validation. Missing,
changed, ambiguous or unsupported evidence fails closed. No pin is renewed, no
file/receipt is changed and no value is synthesized. Local hash integrity does not
independently establish SEC acquisition or accounting scope: the exact capture,
filed-date publication lineage and scope remain independent-review trust anchors.

No registry is assigned before the read-only session successfully closes. Lifecycle,
registry conflicts, gate and store configuration are then checked again. A private
lock serializes calls to this entry point. The evidence policy tuple is published
first; the denominator permission tuple is the final store in successful publication.
Both previous tuple references are saved before a narrow `try` around the stores.
The lifecycle changes from VALIDATING to PUBLISHING before either store. If either
store is interrupted, `except BaseException` first quarantines the lifecycle and restores the owned permission
first and then the owned policy, and re-raises the original exception. This includes
KeyboardInterrupt/SystemExit and ordinary exceptions; there is no success result or
silent partial registration on the tested recoverable failure paths. Recovery and
publication run under the same existing lock. Operator launches never retry in
the same interpreter, even when rollback succeeds.
Restoration uses identity checks: it only replaces the exact tuple published by this
attempt, preserving a different owner's tuple even if its contents compare equal.
No selection/withdrawal registry or global equivalence is modified or rolled back.

**Publication consists of separate assignments; reader exclusion supplies safety.**
The one-shot process-local lifecycle refuses bootstrap while a maintained financial
reader is active. During VALIDATING only the owning bootstrap thread's private
validation context can read; during PUBLISHING no financial reader is admitted.
FinancialMetrics construction/calculation/summaries/history/fiscal comparisons,
the dataset/evidence/authorization entry points, legacy financial loaders,
research answers and sync coverage/admission are guarded. Ordinary inactive
processes retain concurrent reads and no added evidence/database I/O.

The outer ASGI wrapper denies HTTP (503) and WebSocket (1013) outside READY.
After exact registry verification the publication is sealed; READY is reached
only on successful ASGI startup completion, with a held maintenance lease and a
second exact registry check. Shutdown closes admission before application cleanup.
Failure/shutdown cannot return to READY; initialization/publication cannot repeat.
Arbitrary Python calls to unguarded pure helpers, object attributes, `__wrapped__`,
or unlocked registry mutation are outside this boundary. Trusted deployment code
must not introduce a new consumer/writer that bypasses it. HTTP wrapping alone
is not asserted to constrain arbitrary internal execution.

The dedicated launcher uses Uvicorn Config/Server with the application object in
the same interpreter: workers=1, reload=False, factory=False, lifespan="on", no
FD/UDS/inherited sockets. Ambient UVICORN_* variables, WEB_CONCURRENCY and socket
activation variables reject. External CLI preflight cannot mutate another backend.
Ordinary `app.main:app` remains inactive and has no auto-registration hook.

Any validation/publication/final verification/import/server failure quarantines
the lifecycle and propagates. The operator CLI hard-exits nonzero (78), without
logging exception text or running potentially failing cleanup/atexit handlers.
ASGI lifecycle failures, including failures after startup completion, hard-exit
directly: raising in a background lifespan task alone need not stop Uvicorn.
Termination runs in finally even if quarantine marking itself fails. Secondary
rollback faults may strand tuples, but that process cannot serve or retry. No
cleanup atomicity under arbitrary repeated interruptions is claimed. Supervisors
must use authenticated, operator-controlled fresh-process retries, never fallback
to ordinary serving in an uncertain interpreter.

The entry point retains no proof cache. Every subsequent financial request still
uses the existing adapter to revalidate its own facts, versions and bytes. Changed
evidence after preflight therefore cannot authorize a later unverified response.
The lock does not protect external filesystem writes, database publications or
arbitrary mutation of trusted constants. No cross-filesystem/database atomicity
is claimed. Repeatable-read is a consistent snapshot, not a fence against commits.

The uncommissioned maintenance provider must acquire concrete protected resources
and yield a lease with ownership/loss checks, covering all relevant Company,
FinancialFact, CompanyRefreshState and FilingPublication writers, plus original
markup/receipt/store mutation. Existing refresh coordinator advisory locks do not
exclude raw importer/bootstrap/direct-SQL or filesystem writers. A future protected
deployment must fence every writer entry point/identity and store custodian through
an independently verified maintenance controller; an environment flag or assertion
that jobs are stopped is insufficient. Absent that complete fence, this provider
always rejects. Lease ownership is rechecked after validation and before READY.
For this minimal implementation the lease is conservatively retained through
server shutdown; relaxing its lifetime requires separate review.

### Continuing lease admission (Astra G/H/I correction)

Retaining the lease context is not sufficient. A commissioned provider must expose:

- `assert_held() -> None`: a fresh authoritative ownership/scope/expiry/renewal check.
  Lost, revoked, expired, failed-renewal, unreachable or unverifiable ownership raises;
  cached successes and boolean/string claims are not accepted. Checks must have a
  bounded timeout and report inability to monitor as loss, not stale validity.
- `subscribe_loss(callback) -> None`: atomically install monitoring, reporting an
  already lost lease as well. Publish invalidity before notifying `callback(error)`;
  invoke outside provider ownership locks to avoid lifecycle/provider lock inversion.
  Notify promptly on revocation, expiry, renewal/monitor failure even while HTTP or
  WebSocket consumers are idle. The context owns monitoring until normal shutdown
  and intentional release; a lost lease can never be renewed back into authority.

The controller subscribes before checking initial validity. READY admissions check
current ownership for every HTTP/WebSocket dispatch, ASGI receive and send (both
before and after awaits), and maintained direct financial entry/exit. Checks include
authorization-dependent internal operations through their existing decorators.
Completed calculations are checked before returning, including error exits. Ownership
is also checked at READY and shutdown transitions. Ordinary inactive processes have
no controller/lease requirement and retain existing no-evidence financial semantics.

Any detected ownership failure or notification latches irreversible failure,
records the first lease exception, sets FAILED and drives exit 78. The independent
poison latch and FAILED state precede the fallible `fail()` hook. A marking exception
is retained separately; termination still runs in finally. If a broken/test terminator
returns, the original lease exception is raised, never successful continuation.
Repeated notifications/renewal attempts cannot restore READY or permit reinitialization.

The lifecycle lock serializes its own validity checks, transitions and reader
admission bookkeeping; it does not serialize external revocation or async transport
submission. Provider checks and callbacks must obey the bounded/no-lock-inversion
contract above. No lifecycle lock is retained across an ASGI await. Once failure is
latched, subsequent guarded admission/delivery boundaries reject. The process also
terminates on idle loss notifications, without waiting for another request.

Results not yet passed to a transport are withheld when a boundary detects loss;
bytes already accepted/delivered cannot be retracted. A send already in progress
can accept bytes before the post-send check/notification terminates the process.
Likewise, there is a check-to-send/check-to-return interval in which external lease
state can change. This patch does not promise instantaneous external revocation or
atomic lease-check-and-byte-commit. A future production provider must independently
prove authoritative freshness, detection/notification latency and renewal expiry
semantics. Stronger transport-level guarantees require a reviewed delivery reservation
or cancellation/commit capability; a Python readiness snapshot is insufficient.
The real provider remains rejecting, so none of these prerequisites are assumed met.

Focused synthetic tests cover loss before admission/direct reads, during calculation,
after calculation, between response sends, inside an awaited send, during WebSocket
activity, polling/idle notifications, expiry/renewal/probe errors, concurrent READY
or shutdown transitions, quarantine-marking faults and genuine subprocess fail-stop.
No production activation, evidence retrieval or deployment fencing is exercised.

FINLENS_SEC_ORIGINAL_STORE must be operator-controlled, absolute, outside Git,
unredirected and identical to the protected deployment policy. Ancestor/store
custody must prevent untrusted replacement; the backend needs read-only access.
Original artifacts/receipts remain immutable, with independently accepted capture,
publication and accounting-scope lineage. Hashes are not SEC signatures. Changed
pins, versions or manifests require a new reviewed proposal, never automatic repinning.

## Tests and actual activation gates

Tests assert empty real registries and a false gate before isolation. Only reversible
monkeypatch fixtures enable the gate, supply a detached session factory and permit
test-local registration. Original bytes/receipts are read only. No enabled invocation
uses the live PostgreSQL application. Negative fixtures mutate detached records or
mocked reads, not stored evidence. Existing proposal/adapter/authorization tests
continue to cover historical unavailable states and Gross Margin safeguards.
Fault injection targets the actual permission attribute store before and after its
assignment, covering BaseException and ordinary exceptions, exact reference
restoration, repeated interruption, a successful fresh retry, preserved foreign
ownership and serialized concurrent retries. No fault test leaves a real production
permission installed. The new safety tests use only synthetic issuers/documents,
fake sessions/servers and reversible trust substitutions. They cover actual Windows
token identity without printing/allowlisting it, profiles, effective server settings,
concurrent reader exclusion even after both stores, secondary cleanup faults,
lost maintenance ownership, terminal lifecycle and HTTP/WebSocket admission.
Disposable CLI processes test nonzero termination without listeners or real records.
Original-evidence acceptance tests are not repeated for this task.

Before actual activation:

1. Obtain separate user approval and Astra High approval of this entry point and
   the actual deployment/invocation; approval of the dormant proposal alone is insufficient.
2. Configure the trusted operator-owned original store separately, preserving its
   pinned receipt capture path and append-only protections. Do not change it in this patch.
3. Revalidate original receipts, exact raw manifest, complete publication snapshot,
   approval lineage and every fingerprint immediately before the explicit call.
   Changed pins require a new reviewed proposal/version, never automatic repinning.
4. Establish and independently review authenticated operator authorization, the
   trusted in-process invocation and registry lifecycle ownership. The current
   boolean/reference interface does not provide authentication. Commission the
   rejecting ACL/integrity and maintenance providers through separate review.
   This disabled infrastructure does not authorize source-gate enabling.

Specific Astra High review issues:

- What separately reviewed authenticated operator/invocation boundary will resolve
  the real-activation prerequisite? This correction does not address access control.
- Does fresh-session validation preserve legacy version 0, manifest completeness,
  independent provenance and the exact denominator-only permission?
- Are one-shot lifecycle ownership, maintained direct-consumer guards, exact final
  registry checks and pre-server publication sufficient to exclude partial reads?
- Do background-lifespan fail-stop and secondary-cleanup termination prevent all
  uncertain-state serving, including repeated faults?
- For G/H/I, are live ownership checks, monotonic loss notification/latching,
  calculation-exit and receive/send checks sufficient within the stated boundary
  guarantee? Review actual check-to-send/return races, provider bounded-time freshness
  and notification requirements; no atomic byte delivery or instant revocation is claimed.
- What concrete protected deployment and complete database/store writer fence can
  safely commission the deliberately rejecting providers? Is retaining maintenance
  ownership through server shutdown acceptable for the initial narrow scope?
- Are the filesystem/database snapshot limits, immutable-store operation and
  subsequent per-request verification sufficiently fail closed?
