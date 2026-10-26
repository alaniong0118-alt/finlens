# FIN-DEPTH-01 Frontend Increment 1B.1

Status: active; Astra implementation FAIL retained; scoped two-P2 correction verified offline, pending independent re-review.
Roadmap phase: bounded enabling slice of Research Mode depth. No 1B.2 UI work.

## Objective

Implement the accepted insights-only contract, bounded worker transport and owned
result lifetime. The coordinator supplied Astra PASS for all design amendments;
that verdict does not establish implementation, browser, database or pilot acceptance.

## Current architecture and context

Starting branch main, HEAD 21a94a74888cb184948e8388a223b005c62e23a5, empty index.
Preflight found only the three protected exceptions; their supplied SHA-256 hashes
matched. Reports were hashed only. Backend 1A serialization is authoritative.
Existing requestJson must remain unchanged. Next uses module-worker URL bundling.

## Constraints

Exactly six candidate paths: frontend/lib/financial-insights.ts,
frontend/lib/financial-insights.worker.ts, frontend/lib/finlens-api.ts,
frontend/tests/financial-insights.test.mjs,
frontend/e2e/fixtures/financial-insights.ts, and this plan.
No staging/commit/push, services, browser, DB, SEC/provider/model operations,
dependency installation, private .env access or protected-file changes.

## Non-goals

No component, styling, pilot, deployment or Backend 1A changes. Historical
FAIL/BLOCKED records and eight-file historical identity NOT VERIFIED remain intact.

## Implementation stages

1. Exact contract, bounded lexical preflight, graph/statement admission and decimals.
2. Worker input/output credits, complete display preflight and indexed pages.
3. Parent handle ownership, streaming limits, deadlines and disposal.
4. Guarded serialized fixtures, offline adversarial tests and safe static checks.
5. Scope/hash verification and coordinator handoff for Astra implementation review.

## Decisions

2026-10-26: Worker owns the full graph. Parent retains initial presentation plus
one committed and one staged page only. Busy different page requests are rejected;
identical requests coalesce. No page FIFO/cache. Oversized display records reject
before initial publication. Initial deadline is 30 seconds; later pages have 5 seconds.
Idle/absolute lifetimes are 5/15 minutes, heartbeat 15 seconds with 5-second allowance.

## Discovered issues

Extended guarded serialization exposed canonical D comparisons with null
percentage_reason when revenue bases conflict. The first extended combined run
was 243 passed / 1 failed; the validator was corrected only for the diagnostic
canonical shape. The nine-case focused compatibility rerun passed. Published
comparison percentage reasons remain strict. Initial 65-case development run passed.

Self-review added full raw/canonical source reconciliation, iterative queued-once
closures, UTF-8 fragment coalescing (not one retained string per network fragment),
post-suspension deadline checks, and bounded statement/edge page targets.

Browser bundling must not be inferred from TypeScript checks. A build in the working
repository could rewrite next-env.d.ts and create uncontrolled generated files.
Build and browser/runtime acceptance are therefore deferred, not bypassed.

## Progress

- [x] Read-only preflight and exact allowlist admission.
- [x] Implement contracts and lifecycle.
- [x] Final combined offline tests: 249 passed, 0 failed, 0 skipped/deselected.
- [x] TypeScript, scoped ESLint and candidate whitespace checks passed.
- [x] Exact six-path scope, baseline/index and protected fingerprints verified.
- [ ] Independent Astra implementation review (separate gate).

## Test and validation strategy

Use worker doubles and deterministic clocks. Backend synthetic serialization must
initialize the existing guarded runner preamble before any application import.
Run no-site/no-bytecode Python only. Test body, Unicode, JSON/graph limits, decimal
expansion, F/D separation, version zero, ACK ordering, lifetime and cancellation.
Run TypeScript without incremental output and scoped ESLint. No browser/services.

Actual contracts: HTTP-decoded input <=4 MiB; one exact-allocation 16 KiB input
slice awaiting ACK. Fatal UTF-8 and bounded lexical/duplicate-key preflight precede
native JSON.parse in the worker only. Graph/statement identities and complete
closures are checked against the committed wire shapes; finance arithmetic,
direction, prose and precision predicates remain server-owned. Decimal expansion
is lexically bounded before allocation. Publication zero and None:None are valid.

Output uses bounded structured-clone display objects (not cloned graphs), measured
before posting: <=32 KiB including protocol allowance, <=1,024 entries and <=25
records. This avoids a second native JSON.parse on the main thread. One output
credit is released by exact ACK; OP_COMPLETE gates publication. Parent retains an
initial model <=128 KiB plus one committed and one staged page <=32 KiB each;
the accepted 224 KiB logical ceiling is conservative. No worker page cache.
Collections are packed by both size and entry count. Every complete display record
is preflighted; oversized records reject the whole comparison before publication.

The exported panel must be disposed synchronously by the future UI on company,
year, version, cancellation and unmount changes. Handles expose disposal and a
bounded subscription; expired snapshots/pages become null. No UI was implemented.

## Completion criteria

Focused offline checks pass; six-path candidate only; protected hashes unchanged;
known deferred bundling/browser/runtime gates explicit; independent Astra review
remains pending until separately performed.

## Final outcome

Implemented only the six authorized paths. Five are new; finlens-api.ts adds an
opt-in wrapper and type import. A test compares the complete pre-existing
requestJson implementation with HEAD and proves it unchanged. Compare API calls
require matching discovery identity, supported years and publication tuple.
No financial formulas, source selection, direction or statement text are generated.

Final commands from frontend/:

```
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js lib/financial-insights.ts lib/financial-insights.worker.ts lib/finlens-api.ts e2e/fixtures/financial-insights.ts
```

Final combined tests: 249 passed, 0 failed, 0 cancelled, 0 skipped/deselected;
141.271 seconds. TypeScript and ESLint exit 0. Four golden fixtures match fresh
guarded Backend 1A serialization. Nine additional guarded cases cover loss/zero,
tiny values, ambiguous eleven-anchor windows, incompatible revenue bases and
NaN/sNaN/Infinity/-Infinity as the only CapEx candidate. All passed frontend
admission and complete display preflight without a database/provider operation.

Protocol evidence includes ignored fetch/read abort, actual 4 MiB / +1 byte,
misleading length, fragmented UTF-8, bounded ACK credit, missing initial/page ACK
and OP_COMPLETE, duplicate/obsolete messages, page coalescing/busy rejection,
post-30-second pages, initial/page/idle/absolute timeouts, heartbeat overlap and
silent termination, disposal and fixed retention. Aggregate JSON expansion and
graph/reference substitutions fail closed. Node's existing typeless-package
warning and the guarded Python import's existing Starlette/httpx deprecation
warning are not failures; dependencies were not changed.

All six candidates are regular UTF-8 text with no NUL or trailing whitespace.
Scoped git diff --check and new-file no-index whitespace checks passed. HEAD stays
21a94a74888cb184948e8388a223b005c62e23a5 on main; index empty. Only the six
candidates plus the original three exceptions are present. Protected SHA-256:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Reports were hashed only. No source outside the allowlist, private configuration,
backend policy, dependency or historical acceptance record was modified. No Git
publication or live/browser/model/provider operation occurred.

Independent Astra must review: exact F/D/canonical versus admitted shapes and
nullable diagnostic percentage reasons; field/Unicode/JSON/graph/work accounting;
lossless representation equality and expansion bounds; complete source lineage;
ACK identity/credit and payload bounds; operation settlement and ownership;
expiry, heartbeat overlap and disposal; guarded serialization safety. Review the
standard new Worker(new URL(..., import.meta.url), {type: 'module'}) integration
separately: actual Next bundling, browser Worker execution, mounted accessibility,
real PostgreSQL, issuer coverage, pilot and deployment remain NOT VERIFIED.
Parent retention bounds describe module-owned logical content, not exact JS heap
size or references independently retained by future UI consumers. Future 1B.2 must
subscribe to disposal and read only current handles; no rendered UX claim is made.

Stop for coordinator/Astra review. Suggested later commit message:
`feat: add bounded financial insights client contracts and worker transport`.

## Astra two-P2 correction — 2026-10-26

Coordinator supplied independent Astra verdict: **FAIL — NO-GO for Git Step 1**.
Two P2s: admitted base observations were not bound to selected source values and
dates; relevant selected-identity conflict diagnostics could coexist with F support.
The accepted transport, worker protocol and lifetime are not being redesigned.

Pre-fix main/HEAD/index and exact six candidates plus three protected exceptions
were verified. Current entry SHA-256 (not historical design/P2 hashes):

| Candidate | Entry SHA-256 |
|---|---|
| frontend/lib/financial-insights.ts | EE7B47DD70976484158A3CD280AF38484B6B28FA44BEA5DF384F9F049787C76E |
| frontend/tests/financial-insights.test.mjs | 75F2FAB4EC7FA025B067AA6F56642581CA3E945E90D154C3A2FBBBEEA9D0EB5B |
| docs/exec-plans/active/2026-10-26-fin-depth-01-frontend-1b.md | AC4B0F4CCC3E523B7766A2BDDA5238B43147B7602294466FB9448798DA1BB7C6 |
| frontend/lib/financial-insights.worker.ts | EC3D2345A4D97D433B0520DF6B4B81852626ECA68BAA22C12A8E5A557694FA7B |
| frontend/e2e/fixtures/financial-insights.ts | 491733790CD78DC2A143295B196D41F2891AEB47F7293072C70CBB027D16B36A |
| frontend/lib/finlens-api.ts | EF78F72DD774722C3A79FF8378EE9F2E94030D4B67D7DB1073C9A35ECB26EA1A |

Only the validator, its tests and this plan may change in this correction. The
other three candidate hashes above must remain byte-identical.

Before correction, `node --test --test-name-pattern='P2 regression'
tests/financial-insights.test.mjs` ran 9 tests: 0 passed / 9 failed. All three
original Astra mutations were accepted instead of rejected: revenue 100 versus
source 999, FY2024 versus source dates in 2023, and selected CapEx conflict with
FCF still 15. Margin conflicts and duplicate-identity conflict variants were also
accepted. The production Worker/parent amount-substitution test fulfilled its
comparison request (READY) rather than rejecting. This failure evidence is retained.

Correction binds each admitted base value, canonical/source concept relationship,
fact ID, unit and exact start/end to its selected provenance/raw source and the
shared annual window. Filing-context fiscal annotations remain independent.
Derived observations still follow admitted operand/provenance chains; no finance
arithmetic, source reselection, direction or statement generation was added.
Conflict checks use the exact nine-field Backend 1A source_identity. Attached
selected-identity conflicting_value flags, or distinct finite values under that
identity even without the flag, reject the response as INVALID_RESPONSE. Genuine
unadmitted diagnostics, nonfinite alternatives and other vintages remain separate.

Final focused command from frontend/:

```
node --test --test-name-pattern='P2 regression|P2 positive' tests/financial-insights.test.mjs
```

Result: 12 passed / 0 failed / 0 cancelled / 0 skipped; 39.199 seconds.
The three original mutations now reject as INVALID_RESPONSE. The actual
production worker runtime and parent protocol emit FAIL INVALID_RESPONSE for the
amount substitution, with zero BATCH or OP_COMPLETE messages, no READY publication,
one worker termination, no retained worker graph and no remaining timers.

The positive guarded test independently compares the admission concept/basis
manifest with committed METRICS/REVENUE_CONCEPTS. Six freshly serialized cases
retain alternatives, equivalent duplicates, unrelated quarters, nonfinite rejected
candidates, arbitrary stored metric aliases and comparative-filing fiscal context.
Equivalent decimal spellings and signed zero equality pass without float amounts.
Legitimate derived margins/FCF and unavailable FCF with conflict diagnostics pass.
No selected input is reselected, amended or used for new financial arithmetic.

Full previously passing suites rerun with all new tests:

```
node --test tests/financial-insights.test.mjs tests/finlens-api.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false --pretty false
node node_modules/eslint/bin/eslint.js lib/financial-insights.ts
```

Combined result: 261 passed / 0 failed / 0 cancelled / 0 skipped/deselected;
181.811 seconds. TypeScript and scoped ESLint exit 0. The existing streaming,
Unicode, resource, worker/ACK/lifetime, zero-pin and None:None cases remain passing.
The earlier 249-pass result and Astra FAIL above remain historical evidence.

Only financial-insights.ts, financial-insights.test.mjs and this plan changed in
the correction. The worker, golden fixture and API hashes match their entry values
byte-for-byte. All three original protected hashes match. Branch remains main at
21a94a74888cb184948e8388a223b005c62e23a5; index remains empty; the candidate
inventory remains exactly six files plus the three protected exceptions.

No build, browser, service, Docker, database, SEC/provider/model operation or private
.env access occurred. Actual Next bundling/browser, issuer/runtime, pilot and
deployment acceptance remain NOT VERIFIED. No 1B.2 work began. No Git staging,
commit or push occurred. Ready for coordinator and focused Astra re-review only;
the historical Astra FAIL is not relabelled as an independent PASS.
