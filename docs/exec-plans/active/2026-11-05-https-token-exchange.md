# Dormant HTTPS token exchange

Status: active; scratch implementation/validation complete, independent review pending.
Roadmap phase: bounded enabling step for the default-off private login seam.

## Objective

Provide one explicitly configured HTTPS Authorization Code/PKCE token transport
implementing the existing callable `TokenExchange -> TokenReply` contract. Prove
endpoint admission, response bounds, cancellation, closure and a synthetic signed
callback offline. No production composition is changed.

## Current architecture and context

Primary main is `eccaa0e13c60040392372417a9efacea267b6e23`. The ten reviewed
sign-in files and five protected exceptions are uncommitted and must remain exact.
`private_workspace_login.py` constructs the form body, consumes browser-bound
state, limits exchange to five seconds/32768 bytes, validates token response JSON,
verifies the existing RFC 9068 access-token profile, and checks invites before
account creation. The adapter must not duplicate or weaken those responsibilities.
HTTPX 0.28.1 is already installed and declared in backend requirements. Its
existing certifi dependency supplies the same bundled trust roots HTTPX uses.

## Constraints

All changes stay in this isolated scratch directory. No network, database,
Docker, providers, credentials, JWKS, cookies, routing, verifier changes, installs,
Git staging, commit, push or deployment. Synthetic RSA keys in the existing
offline test fixtures are memory-only test data, not actual credentials.
Exact primary and sign-in preservation hashes are in `preservation-before.json`.

## Non-goals

Provider selection/provisioning, client secrets, endpoint discovery, retries,
proxy configuration, real TLS/network acceptance, general OAuth/OIDC support,
production composition or live login.

## Implementation stages

1. Bind current source, instructions, typed contract and preservation snapshot.
2. Add an immutable, explicitly configured, otherwise dormant HTTPX adapter.
3. Exercise request/response failures, streaming limits, deadlines, cancellation,
   resource closure, redaction and one real signed synthetic callback.
4. Run focused offline and maintained login regressions; seal exact patch/hash
   artifacts and verify all unrelated files remain unchanged.

## Decisions

- Pin one canonical HTTPS URL by exact original-string comparison. Reject URL
  aliases or normalization instead of silently retargeting a request.
- Create one HTTPX client per exchange; no shared cookie jar or auth state.
- Use an explicit verified TLS client context with the existing certifi roots,
  Python's strict/partial-chain verification flags and no TLS key logging. Avoid
  `ssl.create_default_context` and ambient certificate paths; `trust_env=False`
  separately disables proxy and netrc lookup. Production transport retries are zero.
- Only an explicit MockTransport is injectable for offline tests. It establishes
  request behavior, not DNS, TLS certificate or network correctness.
- Read raw streaming bytes with identity encoding. Validate metadata and actual
  length without decoding, logging or parsing private token JSON. Token semantics
  remain the responsibility of the existing seam.
- Use an asyncio overall deadline in addition to HTTPX per-operation timeouts;
  async context managers own response/client closure on normal/error/cancel paths.

## Discovered issues

Self-review reproduced a cancellation/close-failure interaction: with a cancelled
body read and a failing client close, ordinary exception wrapping replaced
CancelledError with LOGIN_UNAVAILABLE. The pre-fix adapter SHA-256 was
`82c7797e56ec4d1b1e41beaa793ff10821ca5ec7ed3cb24786c04d4b25aa0011`.
The expanded 20-test run failed exactly that regression. The adapter now preserves
an outstanding caller cancellation even if cleanup raises. All 20 tests pass.
The existing crypto/ownership fixtures were reused without modification.

Final source review found that HTTPX `verify=True` calls Python's
`ssl.create_default_context`, whose SSLKEYLOGFILE handling is independent of
HTTPX trust_env. The first draft is retained unchanged at
`https-token-exchange-20261105` (handoff SHA-256
`7b12d2d2c337c86f82fba706911f843f4f3ba58766a0a8013a70de33cfb4c2a3`).
The V2 draft replaced that path with an explicit verified SSLContext and the same
existing certifi roots. No environment or SSL settings are modified; ambient
certificate paths, client certificates and key logging are not consulted. A
positive test checks loaded roots and verification/hostname flags while the
ambient TLS helpers and client-certificate loader are set to fail if invoked.

Independent review of V2 found a header-budget bypass: decoded Unicode character
counts were smaller than the raw HTTPX header bytes. V2's exact source SHA-256
`9c5f954409e5ce282b9df667fe08a51afabe9c8f9442661ae713ea9ddbea3c6a`
accepted a 9034-byte UTF-8 header set and a 9040-byte repeated-header set, despite
the unchanged 8192-byte limit. V3 adds two focused regression methods and changes
only `response.headers.multi_items()` to `response.headers.raw` in the adapter.
The sum counts raw name/value bytes for every field, including repeated fields;
it is a header-field byte budget, not a claim about protocol framing bytes.
The new regressions failed before correction (23 tests, three failing subcases,
no errors). All 23 pass after correction, including exact 8192-byte admission and
8193-byte refusal for ASCII, UTF-8 and repeated headers before body reads.
The V2 handoff `18383c2e46dbd2068dcedff579c81bdd7014a18a0a8bbee83fa2cbc7612dc7f0`
and all its artifacts remain unchanged at `https-token-exchange-20261105-v2`.

## Progress

- [x] Inspected repository instructions, contract and HTTPX dependency.
- [x] Captured primary main, empty index, 557 tracked files, ten sign-in hashes,
  five protected hashes and four Git metadata hashes.
- [x] Implement dormant adapter and 23 focused tests with MockTransport.
- [x] Reproduce and correct the self-review cancellation failure.
- [x] Reproduce independent-review raw-header finding and correct only byte admission.
- [x] Run maintained login (28), workspace (23), and verifier (16) regressions.
- [x] Record validation and explicit limitations; package three-file review scope.
- [ ] Independent review of exact artifacts; no primary integration in this task.

## Test and validation strategy

Use existing Windows Python in isolated `-I -S -B` mode. Construct the asyncio
wakeup loop before the existing strict offline audit guard. Deny real network,
private environment reads, database connections and subprocesses in tests.
MockTransport is the only request transport used. Verify exact form bytes,
endpoint and client security settings; assert bounded bodies, strict metadata,
one send/no redirects, sanitized exceptions, cancellation and resource closure.
Reuse the maintained signed login fixture for a start/callback/state/replay probe.
Commands actually run from
`C:\Users\IITSt\Documents\Codex\2026-11-04\task-3`:

```powershell
.\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\https-token-exchange-20261105-v3\backend\tests\test_private_workspace_token_exchange.py
.\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B D:\Projects\finlens-foundation\backend\tests\test_private_workspace_login.py
.\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B D:\Projects\finlens-foundation\backend\tests\test_private_workspace_http.py
.\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B D:\Projects\finlens-foundation\backend\tests\test_account_auth.py
```

Results: 23 + 28 + 23 + 16 = **90 passing tests**, no failures or errors in final
runs. The focused suite includes a real RS256 `at+jwt` synthetic callback using
the existing verifier, invite policy and fake ownership transactions, successful
state/research cookie issuance, and replay refusal without a second HTTP send.
No JSON-token semantics, invite, account, cookie or verifier code was changed.
Production client construction is inspected via spies that substitute only
MockTransport; actual TLS negotiation, DNS, proxy/network behavior is NOT_RUN.

Focused negative cases include exact endpoint aliases, malformed configuration
and typed limits, redirects/status errors without body reads, duplicate or
ambiguous headers, compression, declared/actual byte mismatches, early refusal of
an oversized stream (nine of 1000 chunks), no cookie carryover, transport/read/
close errors and secret-safe traceback/log output. An aggregate one-second
deadline interrupts both stalled headers and dribbling reads. Cancellation during
headers, body and response closure propagates while owned client/response cleanup
runs; a client-close error cannot replace external cancellation.

The asyncio deadline assumes the normal cooperative HTTPX/asyncio implementation
and a responsive event loop. It cannot forcibly terminate an arbitrary blocking
or cancellation-suppressing test transport. Cleanup-error tests establish a
sanitized refusal and cancellation propagation, not proof of remote socket
absence. There was no real socket or TLS operation to validate here.

## Completion criteria

Exact bounded scope, focused and maintained offline tests pass, primary/sign-in
preservation passes, no production activation, clear residual operational gates,
and artifacts ready for independent review.

## Final outcome

Prepared only in scratch: one new adapter, one focused test module and this plan.
`proposed.patch`, `validation.json` and `handoff.json` bind the exact files for
independent review. Primary main, all 557 tracked non-environment files, ten
sign-in files, five protected exceptions and Git metadata must remain unchanged
and the index empty at handoff. No provider or endpoint is installed or selected.
No network, database, Docker, credentials, staging, commit, push or deployment.

Residual gates: independent review, a separately authorized integration, explicit
trusted provider configuration, real HTTPS/TLS and endpoint acceptance, and the
already pending sign-in browser acceptance. Suggested future commit:
`Add dormant pinned HTTPS token exchange`.
