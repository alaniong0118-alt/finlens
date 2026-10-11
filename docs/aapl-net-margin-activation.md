# Disabled AAPL Net Margin activation entry point

Status: implementation prepared for independent Astra High review. **Actual
activation is not approved or enabled.** Baseline main / 1a78b40. The separately
reviewed [dormant proposal](aapl-net-margin-proposal.md) and its immutable financial
records/pins remain unchanged. See [implementation](../backend/app/aapl_net_margin_activation.py).

## Operator boundary

`activate_aapl_net_margin(*, operator_authorized=False, reviewed_ref=None)` is an
internal process-local entry point. `_ACTIVATION_ENABLED` is literally **False**.
Disabled calls return False before proposal imports, store configuration, database
sessions or evidence I/O. Importing the module initializes only a lock and the
false gate. No application startup, financial request, HTTP route or CLI calls it.
No environment variable enables it, and there is no persisted activation state.

Future activation requires separately approved/reviewed source enabling the gate
and an explicit trusted operator call with `operator_authorized=True` and the exact
existing `ApprovalRef`. Truthy strings/integers and mismatched permission/version/ID
are rejected. The acknowledgement is an operator assertion, not an authentication
credential, SEC signature or proof of independent review. It must never become an
untrusted request parameter. An existing financial request context is also rejected.
This task adds neither an operator invocation nor an enabled flag.

**Authenticated operator authorization remains unresolved and blocks real activation.**
A caller-provided True value and the public approval reference are not authenticated
operator authority. They are not sufficient grounds to enable the source gate.
This publication-recovery correction supplies no access-control implementation and
does not constitute approval of the operator boundary or actual activation.

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
If either store is interrupted, `except BaseException` restores the owned permission
first and then the owned policy, and re-raises the original exception. This includes
KeyboardInterrupt/SystemExit and ordinary exceptions; there is no success result or
silent partial registration on the tested failure paths. Recovery and publication
run under the same existing lock, so a lock-cooperating retry starts after recovery.
Restoration uses identity checks: it only replaces the exact tuple published by this
attempt, preserving a different owner's tuple even if its contents compare equal.
No selection/withdrawal registry or global equivalence is modified or rolled back.

**Reader visibility is not atomic.** Ordinary financial readers do not acquire the
activation lock and the registries are separate module attributes. A reader can
observe the policy-only interval during publication/recovery, or a complete pair
briefly before a later interruption rolls it back. Policy-only readers abstain
without evidence I/O, but observations across separate reads are not a transactional
registry snapshot. No full atomicity is claimed. All legitimate runtime writers
must use this lock for their complete publication/recovery; arbitrary unlocked
mutation is unsupported. The identity guard avoids blindly deleting foreign tuples,
but is not a compare-and-swap guarantee against unlocked races. Abrupt termination
or an additional interruption inside recovery is not made atomic by a Python lock.

The entry point retains no proof cache. Every subsequent financial request still
uses the existing adapter to revalidate its own facts, versions and bytes. Changed
evidence after preflight therefore cannot authorize a later unverified response.
The lock does not protect external filesystem writes, database publications or
arbitrary mutation of trusted constants. Operator-owned immutable append-only
evidence and quiescent controlled registry installation remain deployment requirements;
no cross-filesystem/database atomicity is claimed.

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
permission installed.

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
   boolean/reference interface does not provide authentication. No automatic
   server-startup/request activation is supplied.

Specific Astra High review issues:

- What separately reviewed authenticated operator/invocation boundary will resolve
  the real-activation prerequisite? This correction does not address access control.
- Does fresh-session validation preserve legacy version 0, manifest completeness,
  independent provenance and the exact denominator-only permission?
- Are BaseException recovery, exact-reference ownership checks and lock-cooperating
  writer serialization sufficient under controlled, quiescent installation, given
  the explicitly non-atomic visibility to ordinary readers?
- Are the filesystem/database snapshot limits, immutable-store operation and
  subsequent per-request verification sufficiently fail closed?
