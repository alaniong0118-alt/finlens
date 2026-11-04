# Default-off private-workspace login seam

Status: active; offline integration candidate, delivery-cleanup correction awaiting re-review.

## Objective and baseline

Start on `main` at `ea7910d13d03263167ee9b60fdb2a1a3a25c33e9`, empty index.
The five existing protected exceptions retain their recorded hashes. Read the
actual RFC 9068 verifier, ownership/account transaction, private ASGI adapter,
release admission, maintained crypto/fake-store tests and repository plan rules.

Connect a provider-neutral Authorization Code + PKCE S256 start/callback to the
existing `PrivateWorkspace.establish()` through trusted injected configuration and
fake transport only. No provider, issuer, keys, subjects or credentials are
configured in production; the main mount remains unavailable by default.

## Exact scope

- `backend/app/private_workspace_login.py` (new protocol/composition seam)
- `backend/app/private_workspace_http.py` (internal cancellation and handle discard)
- `backend/app/main.py` (unconfigured wrapper mount only)
- `backend/tests/test_private_workspace_login.py` (new, maintained crypto/store fakes)
- `backend/tests/test_private_workspace_http.py` (mount assertion only)
- `backend/tests/test_account_auth.py` (allow the new tested module in the existing guard)
- `backend/tests/test_financial_only_policy.py` (default-off/read-only route probes)
- this plan

The verifier, ownership SQL/schema, SEC allowlists, frontend and existing Strict
cookie policy must not change. No new test environment or harness.

## Development design and explicit boundaries

- Immutable required configuration pins the existing `IssuerPolicy`, exact HTTPS
  authorization/token endpoints, browser origin, API scopes and a separate exact
  issuer/subject invite allowlist. No discovery, environment reads, email inference,
  public signup, invitation URL, refresh flow or secret-bearing configuration.
- This seam is an OAuth public-client/PKCE profile, with token endpoint auth `none`.
  Provider compatibility/provisioning (including RFC 9068 and RFC 9207 support) must
  be reviewed separately before any real configuration. No ordinary ID token is
  accepted as an API token and no verifier rule is relaxed.
  `openid`/`offline_access`, ID-token and refresh-token responses are deliberately
  unsupported by this API-token-only profile, rather than silently ignored.
- Same-origin JSON `POST /private-research/login/start` returns an authorization URL
  for a future UI to navigate to. The URL contains only public parameters, a random
  state and S256 challenge. The verifier remains in bounded process memory.
- A separate Secure/HttpOnly/__Host correlation cookie uses SameSite=Lax for the
  top-level GET callback. The research cookie remains Secure/HttpOnly/Strict.
- GET callback requires exact `iss`, one-time browser-bound state, finite expiry,
  known response parameters and modern navigation Fetch Metadata. Code exchange is
  injected, bounded, non-redirecting and never retried. Only its `access_token` is
  verified with the existing real signature/profile verifier; invite membership is
  checked before `establish()` can create an account.
- Start rotates/revokes the initiating browser's prior handle and pending flow.
  Pending/in-flight callbacks are cancelled by `/login/cancel` and valid same-origin
  workspace logout responses. Completed-flow records briefly retain their new handle
  so a concurrently delivered logout cannot be followed by a usable stale cookie.
- Existing ownership cancellation is propagated into establishment. A cancellation
  or uncertain DB outcome may leave committed invited account/root metadata, but must
  not deliver a usable browser handle or claim rollback. No automatic exchange retry.
- Local logout/cancellation does not end provider SSO or revoke a provider token.
  The existing authenticated/CSRF-protected research logout remains authoritative.
- The application never logs/exposes exchange secrets in bodies, reprs or errors.
  Server/proxy access-log redaction of callback query parameters and actual browser
  cookie delivery require separate acceptance before real login; neither server
  logging nor HTTPS/proxy configuration is changed by this candidate.

Standards consulted: [PKCE RFC 7636](https://www.rfc-editor.org/rfc/rfc7636.html),
[issuer response RFC 9207](https://www.rfc-editor.org/rfc/rfc9207.html),
[OAuth security BCP RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html), and
[cookie navigation semantics](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie).
These are protocol design references; no provider endpoint was contacted.

## Validation and progress

- [x] Inspect architecture and verify starting state/protected files.
- [x] Implement bounded immutable configuration, invite gate and ASGI route wrapper.
- [x] Reuse real in-memory RSA/JWT fixtures, fake ownership transactions and the
  existing strict network/DB/dotenv guard. Exercise PKCE, state/cookie mismatch,
  expiry, replay, duplicate/unknown fields, provider errors/timeouts, ID tokens,
  invite denial before account access, cancellation, switching/logout races and
  sanitized responses/reprs. Keep existing private save/isolation coverage.
- [x] Run verifier, ownership, private HTTP and new login unit suites, plus focused
  real-main default-off/read-only admission checks with the existing offline runner.
- [x] Inspect exact patch, hashes and preservation; leave everything unstaged.

No provider provisioning, real JWKS retrieval, credential creation, live database,
migration, HTTPS/proxy setup, deployment or actual browser/provider login acceptance.
No current user decision is needed to build this unconfigured profile; selecting a
compatible provider, real invite subjects and production client authentication is
an explicitly separate decision. Process memory is not a durable multi-worker store.

## Actual validation and final outcome

2026-11-04, fixed existing virtualenv, `-I -S -B`, no installs or live services:

- Initial standalone invocation stopped before collection because isolated mode
  omitted the test path. Added the same explicit test-path bootstrap as the existing
  maintained tests. Initial 13 login tests then passed; later boundary additions
  increased the final login suite to **20 passing tests**.
- From the repository root, `backend/.venv/Scripts/python.exe -I -S -B` with each
  explicit file: `backend/tests/test_account_auth.py`: **16 passed**;
  `test_research_ownership.py`: **57 passed**; `test_private_workspace_http.py`:
  **23 passed**; `test_private_workspace_login.py`: **20 passed**. Reused the existing
  RSA/fake-store/ASGI loop and strict audit/socket/DB/dotenv guard. The only guard
  edit admits the new application module, with no external-effect exception.
- From `backend`: `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py
  tests/test_financial_only_policy.py -k "private_workspace or login_mount" --tb=short`:
  **14 passed, 46 deselected**. Actual default mount stays 503 without configuration;
  both SEC read-only variants deny start/callback/cancel before invoking the adapter.
- **130 focused checks passed**. Tests cover browser-bound state, PKCE challenge,
  one-time/concurrent replay, pre-/mid-exchange expiry, exact issuer and invite subject,
  unchanged ID-token/audience/client/jti/lifetime rejection, endpoint bounds/errors,
  empty invite policy, cancellation, account switching, logout before/after callback,
  failed cookie publication and confirmed/indeterminate fake commits with no handle.
- Static source comparison verifies unchanged verifier, ownership and SEC admission
  modules, and unchanged Strict-cookie, cookie-parser, authorization and private
  dispatch methods. No ownership migration/schema change or database acceptance.
- Private-workspace logs: `private-login-first.txt` (bootstrap failure),
  `private-login-second.txt` (13-pass intermediate), `private-login-final.txt` (20),
  `private-login-verifier-checks.txt` (16), `private-login-ownership-checks.txt` (57),
  `private-login-workspace-checks.txt` (23), `private-login-admission-checks.txt` (14).
  No raw test receipts are added to the product repository.
- Final whitespace/scope/preservation checks pass: exactly eight candidate files
  unstaged, index empty, unchanged baseline and five protected exception hashes.

Independent review remains pending. No UI sign-in activation, actual HTTPS/cookie or
provider acceptance, real JWKS fetch or PostgreSQL validation was performed. The
future transport must actually honor the injected deadline, response-size and
no-redirect contract; this candidate supplies fake transport only. No production
policy/grants or persistent credentials were created. Rollback is the scoped source
patch; no data/configuration changes. No staging, commit or push.

## Independent-review contention correction

The first independent review found an event-loop availability defect: callback
state consumption and exception cleanup acquired the flow RLock synchronously,
while start could hold that lock across a workspace discard waiting behind DB
work. This correction changes only the login module, its tests and this plan;
the other five candidate files retain the original reviewed raw hashes.

- Flow consumption/reservation remains an atomic one-use transition, performed on
  a worker. Detach records while holding the flow lock; cancel ownership work and
  discard workspace handles only after releasing it. No workspace operation or
  cancellation-lock acquisition occurs while holding the flow lock.
- A request-local cancellation event closes the race between request cancellation
  and worker acquisition. Cleanup tasks are tracked, run off-loop and survive the
  initiating request's cancellation. Workers recheck cancellation before account
  establishment and handle publication; late handles are discarded. Exceptions
  retain sanitized responses. Unconsumed or replayed callbacks do not clear a
  legitimate correlation cookie or discard an already successful session.
- Two targeted regressions reproduced the original defect: one heartbeat timeout
  and one cancellation failure, recorded in `private-login-contention-before.txt`.
  The tests use identity-owned threads with bounded watchdogs, release/join them in
  `finally`, and drain tracked cleanup. They create no network or DB environment.
- Three deterministic contention tests now prove that a 20 ms async heartbeat,
  invented callback and request cancellation complete before the deliberately held
  lock is released, with a 200 ms assertion bound. They cover start waiting on the
  workspace lock, callback state consumption waiting on the flow lock, and exception
  cleanup waiting on the flow lock. A fourth regression preserves a valid session
  and correlation cookie after an invented or replayed callback.
- Final focused rerun: **24 login + 16 verifier + 57 ownership + 23 private HTTP +
  14 main admission = 134 passing checks**; main admission also deselects 46 cases.
  Existing default-off and SEC read-only behavior remains covered. The admission
  run reports the existing Starlette/httpx deprecation warning only.
- Preserved private receipts: `private-login-contention-first-fix.txt` (22 login
  tests), and `private-login-contention-final-{login,verifier,ownership,workspace,
  admission}.txt` (the final 134 checks). These supersede the original 130-check
  candidate for re-review without replacing its receipts or manifest.

The candidate still requires independent re-review. The provider, transport,
PostgreSQL, HTTPS/proxy/log-redaction and actual browser acceptance exclusions
above remain in force. Background cleanup is process-local, not durable across
process termination. No live services, credentials, migration or deployment.

## Independent-review response-delivery correction

Focused independent review closed the contention defect and found a separate
cleanup race: failed delivery of an unconsumed invalid/replayed callback response
called cookie-wide cancellation, which could revoke a legitimate concurrent
callback's completed session. Only the login module, its tests and this plan change
again; the original eight-file candidate scope and other five raw hashes remain.

- The ASGI request retains its own attempt object across callback processing and
  response delivery. Delivery-failure cleanup abandons only the exact flow that
  request reserved or consumed. Invalid, malformed or replayed requests with no
  consumed flow do not acquire cleanup authority through a shared browser cookie.
  Start response cleanup uses the same exact reserved-flow identity. Explicit
  browser cancellation/logout retain their intentional browser-wide semantics.
- Successful callback delivery failure still discards its own handle, including
  failure after headers or during body delivery and request cancellation. Tracked
  cleanup still runs off-loop; no flow-lock or cancellation behavior is relaxed.
- Before the fix, two new deterministic concurrency tests reproduced **eight
  failures** (`private-login-delivery-before.txt`): pause an invalid 400, complete a
  legitimate callback, then fail/cancel that 400; or pause a legitimate 303 while a
  replay's 400 delivery fails/cancels. Both header and body phases are covered.
  The legitimate session incorrectly changed from 200 to 401 in every case.
- Final coverage includes those eight cases, four successful-callback delivery
  failures that must revoke only their own handle while preserving another owner,
  and four start-delivery failures that must remove only their own reserved flow.
  Event/task resources are released and awaited in `finally`; cleanup is drained.
- An intermediate 26-test login run passed. An expanded test initially asserted
  preservation of another handle for the same owner, contradicting existing
  deliberate same-owner rotation; changed the fixture to the other admitted owner.
  Preserve that failed test receipt as `private-login-delivery-final-login.txt`.
  The corrected final receipt is `private-login-delivery-final-login-corrected.txt`.
- Final focused checks: **27 login + 16 verifier + 57 ownership + 23 private HTTP +
  14 main admission = 137 passed**. Other final receipts use the prefix
  `private-login-delivery-final-`; admission deselects 46 cases and reports the
  existing Starlette/httpx deprecation warning. Earlier contention tests all pass.

The correction remains unstaged for re-review. Provider/JWKS, real PostgreSQL,
HTTPS/proxy/log-redaction and browser acceptance remain unverified and excluded.
No credentials, live database, migration, provider activation or deployment.
