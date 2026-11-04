# Default-off private workspace HTTP and UI

Status: active; FIX2 candidate ready for independent re-review. Independent
re-review closed the original three P2 defects; the subsequently reproduced
post-write outcome P2 remains pending independent re-review of this correction.
Roadmap phase: bounded 7c/15b connected development slice.

## Objective

Connect authenticated save, discovery, reload, reopen and JSON export to a browser
panel. Preserve exact source pins and explicit unverified-reference / original-
availability-not-checked labels. Do not claim configured login or real persistence.

## Current architecture and context

Starting main: 150bffc27c1464f14e4f24f61dbdf647ccd91433. Empty index; exactly
five original exceptions, protected by the SHA256 baseline in the task workspace.
The accepted ownership/note service has save/reopen/export but no discovery or
browser sessions. Next rewrites /api/finlens to FastAPI; no login adapter exists.
SEC read-only admission explicitly rejects unknown/private routes.

## Constraints

No provider activation, credentials/private env, live database, migrations,
permissions, deployment, dependencies, staging, commit or push. Default composition
must remain absent. Reuse the maintained ownership fake database and component
loader rather than build a parallel test framework. Preserve protected files.

## Non-goals

Real provider callback/login, persistent browser credentials/session store,
multi-worker hosting, PostgreSQL/role acceptance, verified source authority,
uploads, deletion, memory, cloud generation and completion of 7c/15b.

## Decisions

The coordinator authorized the recommended same-origin HttpOnly-session design as
a development choice. Implement an ASGI adapter with no environment/database or
provider imports. Register its unavailable default in the existing app; do not add
private routes to either read-only allowlist. Trusted server composition alone may
supply the ownership service and exact HTTPS browser origin.

An internal establishment method accepts an already obtained token, verifies it,
creates/resolves the existing private-notes investigation, and rotates a random
256-bit browser handle. It is not an HTTP login endpoint. Bearer tokens stay in
bounded process memory, never browser JSON/storage/URLs. Cookies are Secure,
HttpOnly, SameSite=Strict, Path=/ and use a __Host- name, without Domain. Each
establishment replaces prior handles for that owner; caller-chosen handles are
never accepted. Handle expiry uses token expiry plus a short monotonic lifetime.
The handle lifetime is capped at 300 seconds and the token's exact expiry, without
the verifier's clock-skew grace. The process holds at most 100 browser sessions.
The future trusted login callback must perform a full page navigation after
establishment/account switching. This slice supplies no background account-switch
or provider callback endpoint. UI discards state on pagehide, persisted pageshow,
logout, expiry, owner-mismatched responses and component unmount; late results are
discarded by generation/abort guards. Already delivered HTTP bytes cannot be recalled.

Every operation reauthorizes the underlying owned investigation. Writes require
the exact configured Origin and a random per-session CSRF header. Local logout
removes the server handle and expires the cookie; it does not revoke the provider
token or destroy saved investigations. Account token-cutoff/revocation remains
enforced by OwnershipService. No refresh, background retry or silent new session.

Discovery reads only live owner/session/artifact relationships with bounded
pagination. Public source choices come from stored publication/version metadata
under the authenticated transaction; their references remain unverified. Notes
never fetch or silently replace originals. UI uses no local storage for private
text, tokens, handles or CSRF, and clears private state when authorization fails.

## Implementation stages

1. Add bounded owner-filtered note/source discovery to the existing service.
2. Add default-off HTTP adapter, explicit session/CSRF lifecycle and app mount.
3. Add connected browser panel and safe transport; retain Research Mode behavior.
4. Focused offline ownership/HTTP/UI tests, lint/type/build and appropriate browser
   checks where feasible. Record actual checks and limitations separately.

## Discovered issues

No production browser session origin/provider/storage is configured. HTTPS and
trusted composition are future activation prerequisites, not settings changed by
this task. SEC read-only profiles continue to deny all private routes.

Self-review narrowed source discovery to five scalar metadata columns instead of
materializing full FilingPublication text or refresh-stream JSON. Up to 50 stored
publications per selected CIK are supported; larger inventories reject as a whole.
Note discovery uses 20-item pages with an artifact-key cursor and live owner /
session / artifact revision predicates. Every page is a current read, not a
cross-page database snapshot. No catalogue or evidence data is modified.

Initial HTTP test development had two fixture failures (commit failure injected
before source preparation, and Python 3.14 AST dump omitting empty lists); corrected
without weakening guards. The first UI command hit sandbox EPERM while Node tried
to spawn its test subprocess. Node's supported --test-isolation=none mode runs the
same tests in-process. A JSDOM cleanup typo and an initial lint failure were fixed;
those earlier commands are not counted as final passing evidence.

The maintained frontend/scripts/e2e-server.mjs explicitly refuses native Windows
browser execution and requires Linux/WSL process-group verification. No alternative
launcher was built, no existing live server was used, and no browser acceptance or
production Next build is claimed. No security setting or permission was changed.

## Progress

- [x] Inspect source, requirements and protected baseline; resolve design boundary.
- [x] Implement bounded discovery and HTTP lifecycle.
- [x] Implement connected UI and focused verification.
- [x] Review exact diff and preservation; leave unstaged.

## Test and validation strategy

Reuse real ephemeral JWT signatures and the existing ownership fake transaction
store for HTTP tests. Cover missing/forged/cross-user/expired/revoked sessions,
CSRF/origin denial, fixation/rotation/logout, repeat save, reload discovery,
exact export, bounded bodies/output and error handling. Use the existing React
component loader for UI interactions and late response/cancellation guards.
These checks do not establish real database or provider/browser-login acceptance.

## Completion criteria

Default unavailable; no read-only permission expansion; focused tests pass;
private state and token confidentiality hold; five protected exceptions unchanged;
candidate unstaged and exact evidence/remaining integration gates recorded.

## Final outcome

Candidate scope is exactly twelve files:

- backend/app/research_ownership.py — bounded owner-filtered note discovery and
  scalar stored-publication reference choices, plus FIX1 atomic save_new_note;
  existing save/reopen/export and
  transaction/COMMIT/cleanup methods unchanged.
- backend/app/private_workspace_http.py — default-off ASGI adapter and transient
  server-managed session lifecycle. GET state/notes/sources/note/export; POST
  notes/logout. No login route, environment flag, provider client, database engine
  factory or credential loader. No CORS grants or read-only allowlist changes.
- backend/app/main.py — only an unconfigured private-research mount and import.
- backend/tests/test_research_ownership.py — extends the maintained fake repository
  for discovery, pagination and query-shape checks.
- backend/tests/test_private_workspace_http.py — reuses that fake store and actual
  ephemeral signed JWT verifier; direct ASGI tests with no listening HTTP server.
- backend/tests/test_financial_only_policy.py — focused real FastAPI mount and
  existing release-middleware admission regression.
- frontend/app/page.tsx — link to saved investigations only; no new home API calls.
- frontend/app/investigations/page.tsx — new route wrapper and public-research link.
- frontend/components/private-workspace.tsx — connected availability, source-choice,
  save, discovery/pagination, reload, reopen, JSON export and local logout UI.
- frontend/lib/private-workspace.ts — bounded same-origin transport and owner /
  selector/source/response checks. CSRF stays in memory; no browser token input.
- frontend/tests/private-workspace.test.mjs — mounted React tests using the existing
  component loader and synthetic protocol responses.
- This ExecPlan.

Actual offline verification (no production/provider/database acceptance):

From repository root, established backend interpreter, -I -S -B:

    backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_research_ownership.py
    backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_private_workspace_http.py

Original candidate results: 50 ownership/SQL-shape tests and 13 ASGI/session tests passed, zero
failures/errors/skips. Includes real ephemeral RS256 verification, cookie flags,
rotation/fixation rejection, exact Origin/CSRF, forged/duplicate cookies, bearer
override denial, expiry, revocation/cutoff, two-owner discovery and guessed-ID
denial, repeat save, reload/reopen/export, size/shape caps and sanitized failures.
The maintained fake store proves neither PostgreSQL constraints nor locking races.

From backend, reused tests/run_dep01a1_offline.py setup through runpy with a
non-__main__ run name, then pytest -q --tb=short -p no:cacheprovider for only:

    tests/test_financial_only_policy.py::test_private_workspace_is_denied_before_adapter_in_readonly_profiles
    tests/test_financial_only_policy.py::test_private_workspace_mount_is_unavailable_in_development_without_configuration

Exact PowerShell invocation from backend:

```powershell
@'
import sys, runpy
from pathlib import Path
sys.path.insert(0, str(Path('.venv/Lib/site-packages').resolve()))
runpy.run_path('tests/run_dep01a1_offline.py', run_name='offline_setup')
import pytest
raise SystemExit(pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider', 'tests/test_financial_only_policy.py::test_private_workspace_is_denied_before_adapter_in_readonly_profiles', 'tests/test_financial_only_policy.py::test_private_workspace_mount_is_unavailable_in_development_without_configuration']))
'@ | & '.\.venv\Scripts\python.exe' -I -S -B -
```

Five tests passed, zero failures/skips; one existing TestClient deprecation warning.
The setup supplies an inert sqlite:// engine URL, disables dotenv and blocks
external socket access. No SQLite/PostgreSQL connection or SQL was executed by
these tests. Both sec_readonly variants deny before the adapter; development's
actual main mount returns private/no-store 503 with no configured session service.

From frontend, established E:/node.exe:

    node --test --test-isolation=none tests/private-workspace.test.mjs
    node node_modules/typescript/bin/tsc --noEmit --incremental false
    node node_modules/eslint/bin/eslint.js app/page.tsx app/investigations/page.tsx components/private-workspace.tsx lib/private-workspace.ts

Original mounted UI result: 12 passed, zero failures/skips, including default-off and
read-only states, error vs empty source inventory, idempotent explicit retry,
fresh mounted-page discovery, exact export, denied and wrong-owner clearing,
logout failure/retry, expiry, page history and late-response isolation. TypeScript
and scoped ESLint exit 0. Original focused evidence: 80 tests passed; it did not
cover the three subsequently reproduced P2 defects below. No real login,
database restart, native browser layout/download, production build or CI is claimed.

Private exports are reauthorized JSON responses with no-store/nosniff headers and
fixed filenames. Source authority remains unverified and original availability is
not checked on save, reopen or export. Only metadata pins and user-authored text
are retained; source text is never fetched or silently replaced. Download object
URLs are bounded to one and revoked on replacement, private-state clearing or exit.

Remaining activation gates: an approved provider callback and token profile/key
lifecycle; trusted HTTPS browser origin/TLS and same-origin proxy acceptance;
real PostgreSQL note migration/constraints and dedicated-role acceptance, including
SELECT on the required stored publication/version metadata; a reviewed production
session store or explicit single-worker lifecycle, revocation/clock/concurrency
acceptance; browser/accessibility/download checks and independent review. Do not
add grants, configure these dependencies or activate private writes as this task.
Logout revokes the local handle only, not provider tokens; account cutoff remains
enforced on every operation. Process restart requires reauthentication and retains
no browser-session credentials. No memory zeroization or cross-worker revocation
guarantee is claimed.

All twelve candidate paths remain unstaged for review. Final preservation checks
pass: local and remote main remain 150bffc27c1464f14e4f24f61dbdf647ccd91433,
index empty, exactly twelve candidate paths plus the five original exceptions,
and all five protected SHA256 hashes unchanged. All pre-existing ownership class
methods are AST-identical, including _run and existing save/reopen/export. Python
syntax, all candidate final-newline/trailing-whitespace checks and git diff --check
pass. Exact file hashes are recorded in the task workspace's
private-workspace-review-manifest.json for independent review.
No migration, credential, provider, live database, permissions, deployment or Git
delivery action was taken.

Suggested eventual commit: feat(research): connect default-off private investigations

## FIX1 — independent NO-GO corrections, 2026-11-04

Independent review reported three reproduced P2 defects. Before editing, all
twelve candidate hashes matched the original review manifest; the five protected
exceptions, HEAD and empty index also matched. A pre-fix copy is retained in the
task workspace as private-workspace-pre-fix-manifest.json. All fixes remain inside
the same twelve-file candidate; eight of those files changed for FIX1.

### Reproduction before fixes

Using the established commands/interpreters above:

    python -I -S -B backend/tests/test_private_workspace_http.py HttpTests.test_rejected_note_payloads_never_consume_artifact_quota
    node --test --test-isolation=none --test-name-pattern='malformed JSON|same-owner save' tests/private-workspace.test.mjs

The first command failed all six subcases: empty/whitespace/non-string/control/
surrogate text and a structurally valid non-publication C1 reference returned 400
but left committed artifact reservations. The second command failed four tests:
malformed 401 and 403 JSON left the opened note/index/draft visible; same-owner
responses with different text or source digest acknowledged success and erased
the submitted draft. These reproduced failures are retained as historical evidence.

### Corrections

1. privateRequest handles 401/403 immediately after receiving status, before any
   content-type, stream, UTF-8 or JSON checks. It cancels the body without awaiting
   it and preserves the HTTP authentication status even for absent, malformed,
   non-JSON, oversized or unreadable bodies. The existing auth-clearing UI path
   now runs independently of body decoding. Read-only error headers stay intact.
2. The HTTP save route now calls OwnershipService.save_new_note. It validates the
   exact body, complete closed publication reference, request and session selectors
   before allocation; reservation and note insertion share one existing _run
   transaction and one COMMIT. A new artifact is flushed only inside that transaction
   to establish FK insertion order; no intermediate COMMIT occurs. Any later
   validation/serialization/cancellation/database failure before COMMIT rolls back
   the reservation as well. Existing account FOR UPDATE then session/artifact/note
   locking serializes quota allocation and same-owner request replay. Existing
   save_note/reserve_artifact contracts and _run commit/cleanup logic are unchanged.
   Identical request/body/pin replay reconciles the same row; conflicting payloads
   reject without allocating another artifact. An uncertain COMMIT concerns both
   rows. No automatic retry, orphan cleanup, live schema change or quota reset.
3. Save acknowledgement checks the response owner and then exact submitted text
   plus the complete source envelope, including nullable/version/time/rights fields.
   JSON object-key order does not affect equality; no text normalization occurs.
   Same-owner mismatches use a distinct SAVE_RESPONSE_MISMATCH error: no success
   acknowledgement, draft clearing, index refresh or replacement note rendering.
   The draft and request key remain available for explicit identical retry. Owner
   mismatches and authentication failures still clear private client state.

### FIX1 verification actually run

The four reproduced UI regressions and all six rejected-payload subcases now pass.
Final full focused commands are the same as the original commands above:

- test_research_ownership.py: 57 passed, zero failures/errors/skips. Seven new
  atomic-save tests cover 101 rejected requests without allocation, full reference
  type rejection, lock ordering/single write COMMIT, conflicting replay, rollback
  after artifact flush, output rejection, cancellation before and after COMMIT,
  both uncertain-COMMIT outcomes, explicit reconciliation and the last quota slot.
- test_private_workspace_http.py: 15 passed, zero failures/errors/skips. Includes
  all rejected payload cases plus HTTP write-COMMIT failure before/after persistence
  and identical retry recovery with matching note/reservation identities.
- The two focused real-mount/read-only policy functions above: 5 passed, zero
  failures/skips; the same existing TestClient deprecation warning.
- private-workspace.test.mjs: 18 passed, zero failures/skips. Six new tests cover
  malformed 401/403 clearing, mismatched text/pin retention and stable retry identity,
  other unreadable auth bodies, full-envelope binding and key-order equivalence.
- TypeScript --noEmit --incremental false, scoped ESLint and git diff --check pass.

Final FIX1 focused evidence: 95 tests passed. Fake-store ordering and SQL-shape
checks are not PostgreSQL concurrency/locking acceptance; that gate remains pending.
No new harness, dependencies, provider/session activation, credentials, real DB,
migration, permissions, deployment or Git delivery action was introduced. Browser,
production build, provider, source-authority and operational acceptance limitations
remain unchanged. The exact twelve final SHA256 hashes are delivered in the updated
private-workspace-review-manifest.json for independent re-review.

## FIX2 — preserve note-write outcome through final authorization failures

The independent re-review closed FIX1's three defects but reproduced a related P2:
after the atomic note write committed, the final authorization read could fail
with its own commit_state=not_issued. The HTTP adapter exposed that read state as
the note-write outcome, despite both note and artifact persisting.

Before editing, the twelve FIX1 candidate hashes and five protected hashes matched;
the index was empty. The prior manifest is retained in the task workspace as
private-workspace-pre-fix2-manifest.json. Only three files change relative to FIX1:
backend/app/private_workspace_http.py, backend/tests/test_private_workspace_http.py
and this ExecPlan. All other candidate files remain byte-identical to FIX1.

### Reproduction and correction

Before the code correction, this exact repository-root command failed as reported:

    backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_private_workspace_http.py HttpTests.test_final_authorization_read_failure_reports_confirmed_note_write_without_content

The test injects failure at the third account_lock during a valid POST, after
preflight authorization and the atomic write. It observed HTTP 503 with
commit_state=not_issued while one note and one artifact persisted; it expected
confirmed. The corrected test now passes and explicitly reconciles by replaying
the same request without another allocation.

The adapter now owns a request-local _NoteWriteOutcome, passed into the worker.
Its state means the note mutation's outcome, not the COMMIT state of independent
authorization/discovery reads. It starts not_issued and is never reused across
requests. Before invoking save_new_note it becomes conservatively indeterminate;
the ownership service's explicit lifecycle failure can refine it to not_issued,
indeterminate or confirmed. A raw verifier rejection at write entry is known to
precede the ownership transaction and remains not_issued. Unexpected service
failures with no lifecycle evidence remain indeterminate, whether or not a fake
store happens to show persisted rows.

A successful save_new_note return marks confirmed before receipt encoding and
final authorization. Neither a later read's state nor a response/cleanup failure
can downgrade it. Post-write serialization faults are sanitized server errors,
not represented as client input errors. Error responses retain only code and the
note-write commit_state; failed authorization still withholds all note content
and expires/revokes the local handle where the existing auth policy requires it.
This is not a promise of successful response delivery or rollback of a confirmed
or indeterminate write. No automatic retry or provider action is introduced.

An indeterminate authorization-read COMMIT before save_new_note is entered now
correctly reports the note write as not_issued. The existing read-failure test was
updated to that explicit contract and verifies subsequent identical reconciliation.

### FIX2 validation actually run

Using the established commands/interpreter and the guarded mount-test invocation
recorded above:

- test_private_workspace_http.py: 23 tests passed, zero failures/errors/skips.
  The eight added tests cover the exact third-lock reproducer, post-write auth
  denial and cookie expiration without content disclosure, confirmed cleanup and
  receipt-encoding failures, unknown service failures before/after persistence,
  validation and pre-commit rollback, raw verifier rejection, per-request state
  isolation, and explicit retry/reconciliation without duplicate notes/artifacts.
  The prior tests retain both uncertain write-COMMIT outcomes and all FIX1 checks.
- The two focused real-mount/read-only policy functions: 5 passed, zero failures/
  skips; the same existing TestClient deprecation warning. Default-off development
  and both SEC read-only restrictions remain unchanged.
- Candidate Python syntax, whitespace/final-newline checks and git diff --check
  pass. Unchanged ownership/frontend source and tests retain the recorded FIX1
  evidence; those unrelated suites/type/lint checks were not repeated for FIX2.

Fresh FIX2 evidence is 28 focused tests passed. Existing fake transactions and
injected faults do not establish PostgreSQL lock/concurrency or production/browser
acceptance. All activation, provider, source-verification, database/role, browser,
build and deployment limitations remain unchanged. No new harness, schema changes,
credentials, live database, permissions, staging, commit or deployment action.
The final twelve exact hashes are in private-workspace-review-manifest.json.
