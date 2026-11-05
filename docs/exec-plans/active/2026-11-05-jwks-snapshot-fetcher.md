# Dormant bounded JWKS snapshot fetcher

Status: active; isolated implementation and offline checks complete; independent review pending.
Roadmap phase: bounded private-login enabling step, no provider activation.

## Objective

Fetch only an explicitly trusted IssuerPolicy.jwks_uri through verified HTTPS and
return a candidate KeySnapshot with explicit revision and bounded lifetime.
Existing SingleIssuerVerifier.install_snapshot owns all JSON/key validation,
revision ordering and activation. No token or unknown kid can trigger a fetch.

## Current architecture and context

Root AGENTS.md, .agent/PLANS.md, engineering standards and relevant ROADMAP text
were read. Starting main is eccaa0e13c60040392372417a9efacea267b6e23 with empty
index and the existing ten-file sign-in candidate/five protected exceptions.
The three reviewed token-exchange files are also present untracked in primary;
their bytes and the separate V3 review bundle are preserved independently.
During final packaging, main advanced to b95f4c0d87f273276a284c52333c86f4ba470db1,
whose parent is that entry head and whose only changes commit those same three
token-exchange files. Their working bytes and all entry source bytes match.
The entry snapshot remains immutable; baseline-transition.json binds the observed
new head and metadata separately. This task performed no Git mutation.
account_auth.py already defines IssuerPolicy, KeySnapshot, MAX_JWKS=65536,
MAX_KEYS=16, MAX_SNAPSHOT_AGE=3600 and strict install/verification boundaries.
The pending token-exchange V3 and sign-in candidates must remain unchanged.

## Constraints and non-goals

Scratch only, no primary/pending-candidate edits, network, database, Docker,
credentials, installs, provider configuration, commits, push or deployment.
No discovery, scheduler, retry, cache, shared client, automatic key refresh,
installation or verifier changes. No actual TLS/DNS/provider acceptance claim.

## Implementation stages

1. Capture exact primary and pending-candidate preservation hashes.
2. Add one dormant fetcher and guarded HTTPX MockTransport tests.
3. Exercise bounded transport, deadlines, cancellation, closure and key handoff.
4. Run maintained verifier/login regressions, inspect scope and package hashes.
5. Verify preservation and leave all artifacts for independent review.

## Decisions

- Keep this proposal independent of the unpublished token-exchange module.
  Reuse its reviewed HTTPX security configuration pattern without modifying it
  or introducing a general transport framework or cross-candidate dependency.
- Accept only a canonical exact configured ASCII HTTPS URI. No caller URL,
  discovery, redirects, environment proxy/auth/netrc/CA/keylog settings or client
  credentials. Trust remains explicit server configuration; no public-IP-only
  policy or DNS-address pinning is claimed.
- One client/response per GET, HTTP/1.1, verified certifi roots, zero retries,
  one connection, no keepalive. Raw header field names+values <=8192 bytes;
  raw response <= existing MAX_JWKS, identity encoding and strict metadata.
- Overall five-second asyncio deadline plus HTTPX operation timeouts. Async
  context managers own cleanup. Cooperative HTTPX/asyncio and a responsive loop
  are required; no force-termination guarantee for malicious injected code.
- Explicit revision and lifetime are trusted control-plane arguments. Snapshot
  fetched_at is conservatively floored request-start wall time. Clock/elapsed
  checks refuse a result already expired at return; lifetime never exceeds 3600s.
- Candidate bytes can be malformed JWKS. Fetching grants no trust: the unchanged
  verifier must validate/install explicitly, and failed installation must retain
  the previously installed keys. Unknown-key tokens never cause network activity.

## Discovered issues

No implementation failure observed. The first focused run passed all 21 methods.
A 1024-bit public-key regression was then added to an existing table-driven method;
the final focused and maintained regression runs also passed. No earlier failure
is represented as passing evidence. Synthetic clock injection is trusted test
support, not a clock supplied by an HTTP request. Transport bytes are not promoted
to validated key material merely because a fetch succeeded.
After the first seal, self-review strengthened the redaction assertion to format
the active exception traceback before unittest clears traceback frames. The
focused suite was rerun; the previous complete seal and evidence remain preserved
under initial-seal/. This changes test evidence only, not production behavior.

The first sealing attempt stopped before producing a patch or handoff because the
entry index hash changed. Read-only checks established the exact external
three-file commit above, with identical source/test bytes, empty index and the
remaining sign-in/protected work intact. Packaging is rebound to that new head;
no reset, stash, rebase, checkout or metadata overwrite was used. Tests execute the
same working bytes before and after that commit and remain applicable.

## Progress

- [x] Inspect repository instructions and verifier contracts.
- [x] Capture preservation and implement in isolated scratch.
- [x] Run focused and maintained offline validation.
- [x] Package exact artifacts and verify preservation.
- [ ] Independent review and any separately authorized integration.

## Test and validation strategy

Reuse maintained real synthetic RSA/JWT fixtures and their fake/no-network/no-DB
guards. Use only HTTPX MockTransport, never a real request. Test canonical endpoint
and typed arguments, verified TLS factory/no ambient credentials, response media,
duplicate/UTF-8/repeated/exact-boundary headers, exact body bounds, redirects,
status/error redaction, deadlines, cancellation and cleanup. Explicitly install
fetched candidates in independent synthetic verifier instances to test valid
signed tokens, malformed/private/weak/duplicate keys, revision ordering, expired
snapshots/tokens, rotation, and unknown kid with unchanged fetch counts.
Record actual commands/results separately from plans, including failed runs.

## Completion criteria

Three-file proposed repository scope with exact hashes and synthetic tests;
existing verifier/installation boundary unchanged; primary and pending artifacts
preserved. Independent review and real transport acceptance remain outstanding.

## Final outcome

The proposed repository scope is exactly three new files:

- backend/app/private_workspace_jwks_fetch.py
- backend/tests/test_private_workspace_jwks_fetch.py
- docs/exec-plans/active/2026-11-05-jwks-snapshot-fetcher.md

From the isolated scratch root, using the existing canonical interpreter:

```powershell
& D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe -I -S -B .\backend\tests\test_private_workspace_jwks_fetch.py
& D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe -I -S -B D:\Projects\finlens-foundation\backend\tests\test_account_auth.py
& D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe -I -S -B D:\Projects\finlens-foundation\backend\tests\test_private_workspace_login.py
```

Final results: 21 focused fetcher + 16 maintained verifier + 28 maintained login
methods = **65 passing tests**, no failures/errors/skips. test-execution.json and
its stdout/stderr captures retain actual commands, timestamps, exits and hashes.
The focused suite runs two real five-second deadlines, actual explicit SSLContext
verification/root-store checks and a spied production factory which substitutes
only MockTransport. No socket/DNS/TLS handshake/provider request was performed.

Header admission counts raw field names/values, including repeats: exact 8192-byte
sets pass and 8193-byte sets plus the old UTF-8 bypass examples refuse before body
reads. The body budget is the verifier's 65536 bytes; an unbounded synthetic stream
stops after 17 chunks. Media/encoding/framing ambiguity, redirects/304/status and
transport/close failures refuse without response body logging. Cancellation during
headers/body/response close propagates; a close exception cannot replace caller
cancellation. Context-manager assertions are synthetic cleanup evidence, not a
proof of real remote socket absence. TLS/CA setup and trusted clock callbacks are
synchronous; the asyncio deadline assumes these return and the loop is responsive.

Explicit installation exercises real synthetic RS256 signatures, source/revision
binding, rotation and unknown-kid/expired-token/expired-snapshot refusal. Thirteen
malformed/unsafe key cases, including an actually parsed 1024-bit RSA public key,
fail installation while the previous snapshot still verifies its signed token.
Concurrent calls own independent clients and never carry response cookies or
cache directives into later fetches. No HTTP or token path invokes the fetcher.

Preservation binds 557 entry tracked non-environment primary files, ten sign-in files,
five protected files, three primary pending token files, seven V3 bundle files,
three sign-in manifests and entry Git metadata. The observed baseline transition
binds 560 current tracked files and current metadata at main
b95f4c0d87f273276a284c52333c86f4ba470db1. Status differs from entry only because
the three token files are now tracked; the index is empty. No product files,
verifier, install boundary,
pending candidate, route, dependency, provider setting or deployment was changed.

proposed.patch, validation.json and handoff.json bind the independent review
candidate. No integration or activation is authorized by this plan. Outstanding:
independent source/security review, separately authorized integration, trusted
endpoint/revision/lifetime/concurrency policy, actual HTTPS/TLS/DNS/provider
acceptance, and the existing pending browser acceptance. No generic SSRF address
filter, forceful cancellation of malicious code, scheduler or disk cache is claimed.

Suggested future commit: Add dormant bounded JWKS snapshot fetcher.
