# EVIDENCE-LAT-01B: bounded company evidence phase timing

Status: active; implementation verified, narrow independent Astra High review pending.
Roadmap phase: scoped Research Mode diagnostic, no optimization or live acceptance.

## Objective

Implement the coordinator-authorized Astra-reviewed eight-file diagnostic. Observe
the existing company-wide SEC retrieval path without changing its results, SQL,
encoder cache/concurrency, admission, cleanup, or frontend deadline.

## Current architecture and context

Read [AGENTS](../../../AGENTS.md), [plan rules](../../../.agent/PLANS.md),
[roadmap](../../../ROADMAP.md) and [standards](../../engineering-standards.md).
Baseline main, HEAD 9d0416b1236995a25054c2a7c8b6df65159095a6, empty index.
An in-memory SHA256 inventory covers 325 tracked/nonignored paths plus the ignored
private environment entry included in that count. Preserve modified next-env.d.ts,
both pre-existing untracked AAPL reports and ignored backend/.env; no dotenv content
inspection. The two issuer chains run concurrently; model loading is lazy and its
LRU cache is not single-flight. No root cause or latency improvement is established.

## Constraints

Exactly eight files: app/main.py, freshness_service.py, embedding_service.py,
rag_context_service.py, filing_search_service.py; new app/evidence_latency.py,
tests/test_evidence_latency.py (all under backend/); this plan.
Only source edits and synthetic/offline tests are authorized. No real diagnostic
activation, listeners/services, PostgreSQL, model loading, network, installations,
manifest reconstruction, frontend/settings/dependency edits or Git writes.

## Non-goals

No warmup, performance optimization, construction lock, deadline extension,
evidence bypass, new endpoint, exporter, logger, writer or deployment. DEP-01A3
remains blocked. Original CC01C manifest availability remains unresolved; a new
baseline cannot establish historical continuity.

## Implementation stages

1. Verify baseline and protected bytes; define bounded ownership/admission.
2. Implement request-owned numeric spans and the existing-operation hooks.
3. Implement synthetic equivalence, concurrency, lifetime, privacy and failure tests.
4. Run focused adjacent offline regressions, syntax checks, diff and preservation.
5. Record results and stop for narrow independent Astra High implementation review.

## Decisions

- 2026-10-20: Place a pure ASGI observer inside the existing outer release-admission
  middleware; leave VersionedRoute error/header ordering intact. Observe final body
  send separately from application completion; neither denotes client receipt.
- Create the mutable holder before thread dispatch, share it through ContextVar
  copying, and reset tokens only where created. Span-parent context is copied too.
- Use fixed-capacity numeric buffers and closed phase/outcome enumerations. Record
  only bounded timestamps/IDs while a transaction is open. Aggregate after worker
  cleanup; seal cancelled/late-worker records as incomplete without aggregation.
- Activation needs two exact process settings, resolved development profile,
  explicit trusted local-run approval and verification of an actual already-bound
  listening socket. Never trust headers, parameters or ASGI server metadata alone.
  No activation is automatic. Tests inject synthetic gate state without listeners.
- Default-off collection has no collector allocation. No extraction channel is
  added: a future separately authorized operator can pause an owned process after
  cleanup and inspect the bounded private buffers with an existing debugger.

## Discovered issues

- The first expanded test run exposed a fake-session bug: its publication result
  did not honor the production pending-accession predicate. Corrected only the new
  fixture; production filtering was unchanged. That run had 581 pass / 5 fail.
- Two of those failures were harness assumptions: the old HTTP runtime tests expect
  an unconnected PostgreSQL QueuePool, while the first runner used a synthetic
  sqlite operational URL. The corrected guard uses an explicit fake PostgreSQL URL
  and rejects every psycopg/socket connection. No PostgreSQL connection was opened.
- The remaining two old HTTP runtime failures are stale tone-route inventory cases
  (development and sec_readonly): the test leaves {chunk_id} unresolved and supplies
  no required tone publication pin, producing 422 before the expected factory 503.
  Reproduced both against immutable HEAD source loaded IN MEMORY through an import
  finder, without checking out/editing any source. Baseline: 2 fail / 249 deselected.
  These out-of-scope tests remain unchanged. The corrected full four-file run had
  584 pass / 2 fail before the final nine diagnostic adversarial cases were added.

## Progress

- [x] Verify baseline/index and capture in-memory preservation inventory.
- [x] Read applicable instructions and relevant source/test contracts.
- [x] Implement the bounded observer and eight-file hooks.
- [x] Synthetic tests and focused regression verification.
- [x] Observational AST equivalence and syntax validation; self-review.
- [x] Final fingerprint comparison: exact eight-file scope and protected integrity pass.

## Test and validation strategy

Use installed Python with -B, dotenv disabled, a synthetic sqlite URL, pytest cache
and plugin autoload disabled, and an in-process network/real-model/real-DB guard.
New tests use fake sessions/encoders and direct ASGI execution without listeners.
Compare enabled/disabled response bytes/headers, source order/scores, operation
ledgers, cache attempts, BaseException and cancellation behavior. Exercise every
declared diagnostic bound and failure mode. Adjacent tests cover HTTP/release
admission, read-session cleanup, complete publications and hybrid retrieval.
Record exact commands/counts below; no existing historical totals are new evidence.

## Completion criteria

Exactly eight authorized paths changed; protected/unrelated bytes unchanged;
targeted synthetic checks and relevant regressions pass; no unauthorized effects;
honest coverage and lifecycle limitations documented. Stop for independent review.

## Final outcome

Implemented exactly the eight authorized files. No live execution or activation is
authorized. Future measurement needs
original CC01C manifest provenance, exact publications/pending state/version and
chunk/vector fingerprints, approved local model/offline provenance, verified
process ownership and resource monitoring; do not recover these in this task.

### Activation and observation contracts

No existing startup path calls the private approval function. Exact process
settings FINLENS_EVIDENCE_LATENCY=bounded-local-v1 and
FINLENS_EVIDENCE_LATENCY_LOCAL_RUN=approved-local-v1 are necessary but insufficient.
Resolved profile must be development, and any explicit process profile must agree.
Unexpected diagnostic-prefix settings fail closed. A separately authorized trusted
bootstrap must explicitly approve a local run and supply its COMPLETE actual bound
listener set: exactly one TCP listening socket, 127.0.0.1 or ::1, valid port. The
observer rechecks the real socket, process PID, approval lifetime and server binding
at admission. A request header/parameter/server tuple alone never grants approval.
No real approval was exercised; tests inject private synthetic admission state.
These binding checks do not establish dataset/model trust or deployment readiness.

Only GET /companies/{AAPL|COST}/{context|freshness} is observed. The collector retains
numeric route/issuer slots, not paths/tickers from requests: route 1=context,
2=freshness; issuer 1=AAPL, 2=COST. Admission denial changes no response or retrieval.
The observer is inside ReleaseAdmissionMiddleware and outside CORSMiddleware.
VersionedRoute keeps its original error, pin-header and no-store ordering.

All spans use perf_counter_ns; raw relative timestamps have generated 16-hex-digit
request IDs and numeric parent/span/phase/edge/outcome fields. Only request-owned
timestamps/IDs are appended while a transaction is active. No diagnostic callback,
logging, formatting, await, SQL or aggregation is added inside that transaction.

Hierarchy: HTTP -> route pipeline -> worker -> factory / connection acquisition /
transaction setup / pin read / publication reads and eligibility / encoder / Python
similarity / hybrid ranking / context / cleanup. Publication reads include result
consumption. Eligibility contains validation and digest spans. Encoder contains LRU
lookup -> loader body -> dependency imports / constructor call / dimension admission,
then encode and output conversion. Cache lookup is INCLUSIVE of a miss's loader,
not a pure hash-lookup benchmark. The constructor span counts attempts at the actual
constructor call site, including failures. No LRU decorator, model arguments,
construction lock, encoding/ranking formula or model concurrency behavior changed.

Connection acquisition includes possible pool wait, physical setup and SQLAlchemy
work. Pin-read timing includes the existing schema capability check when needed.
Freshness-read timing is the entire freshness helper, including validation and its
reads. Route-entry-to-worker-entry is framework validation/dispatch/scheduling;
worker-end-to-route-end includes serialization, scheduling and header/bookkeeping.
The HTTP root also includes the final send/application-return interval. Final body
send is measured separately, and NEVER means client receipt. No cross-request sum
is called comparison wall time. Exclusive durations subtract the clipped UNION of
direct-child intervals, including overlap once; fixed scratch storage is preallocated.

Factory, connection and SET TRANSACTION retain their original order and count.
Close/invalidation spans surround existing operations only. A failed factory has no
cleanup-success event. A cleanup envelope's completion does not imply successful
close: close/invalidation have separate outcomes. Primary exceptions keep precedence.

The holder is created before dispatch and copied by reference with ContextVar;
worker code never rebinds that holder to communicate with its parent. Parent-span
tokens reset only in their originating contexts. Per-record locks never serialize
different issuers' constructors. HTTP finalization seals records; late workers
cannot mutate them. If the worker has not finished, aggregation is skipped and
aggregated=false: durations/count summaries are unavailable, not zero-cost claims.

### Bounded storage and private inspection

Hard limits: eight admitted records for the process, two actively collecting
requests, 128 START/END events per record, five minutes from approval and at most
35 seconds of recording per request. These deadlines stop DIAGNOSTICS, not business
work; the unchanged frontend still has its 30-second comparison deadline. Overflow,
expiry or internal failure cannot cancel or modify retrieval. There is no renewal,
background task, persistent writer, console logger, exporter or response change.

Per-record fixed buffers: 2,048 raw bytes + 4,096 summary bytes + 2,048 interval
scratch bytes, all allocated before aggregation. A conservative 15,360-byte object
reservation per slotted record plus 8,192 control bytes caps diagnostic-owned
retained state at 131,072 bytes. Admission validates this interpreter's record
object/buffer overhead before retention, with 40-byte allowances for bounded numeric
fields. Buffers never grow; no summary list/dictionary/JSON is built. Eight-record
object-footprint tests stay below reservation. This is a retained diagnostic-state
bound, not a Python/process/model RSS or business-request memory bound. Collector
code/constants and ordinary interpreter execution are not request-data storage.

Every record has explicit aggregated/truncated/expired/internal-failure/worker-done/
body-sent flags and a required-phase missing mask. coverage_complete means required
phases successfully observed for that route, not every instruction classified, all
publications eligible, client receipt, or a performance guarantee. Warm encoder
reuse does not require constructor spans; observed loader attempts do. Empty scope,
pre-dispatch failure, cancellation, missing hooks and truncation cannot silently
claim full context-path coverage. Sealed buffers remain bounded until process exit;
the collection window does not silently erase the evidence.

Future inspection requires separate authorization and an existing in-process
debugger on the verified owned process after transactions/workers have settled.
Inspect private _collector.records, flags and fixed numeric buffers using the
documented Struct layouts in evidence_latency.py. No new live extraction function,
endpoint, logging or export channel was implemented or exercised. For unaggregated
records, raw boundaries may be incomplete and summary fields are unavailable.

### Verification actually run

All Python invocations used the installed backend venv and -B. Dotenv was disabled
BEFORE app import; no private .env contents were read. Plugin autoload and pytest
cache were disabled. Real TCP connects/connection helpers and psycopg connects were
blocked; real sentence_transformers/torch/transformers imports were blocked. Only
Python's internal Windows event-loop socketpair fallback was allowed (no application
listener/server). Existing company-evidence tests use disposable in-memory SQLite;
new tests use fake sessions/encoders and in-process ASGITransport, without lifespan
startup. No package installation or original SEC/model artifact access.

Reproduction guard, cwd backend (the URL below is an intentionally fake fixture):

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:DATABASE_URL='postgresql+psycopg://fixture:private@127.0.0.1/fixture'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:FINLENS_SERVER_PROFILE='development'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$runner = @'
import sys, socket, importlib.abc
def bomb(*a, **k):
    raise AssertionError('Offline guard blocked external operation')
original_connect = socket.socket.connect
socketpair_code = getattr(getattr(socket, '_fallback_socketpair', None), '__code__', None)
def guarded_connect(self, address):
    if socketpair_code is not None and sys._getframe(1).f_code is socketpair_code and isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1'}:
        return original_connect(self, address)
    bomb()
socket.socket.connect = guarded_connect
guarded_connect._finlens_offline_guard = True
socket.socket.connect_ex = bomb
socket.create_connection = bomb
class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'sentence_transformers', 'torch', 'transformers'}:
            bomb()
sys.meta_path.insert(0, NoModels())
import psycopg
psycopg.connect = bomb
psycopg.Connection.connect = bomb
import pytest
args = ['-q', '-p', 'no:cacheprovider', 'tests/test_evidence_latency.py',
        'tests/test_http_database_runtime.py', 'tests/test_bounded_research.py',
        'tests/test_company_evidence_search.py']
for profile in ['development', 'sec_readonly']:
    args.append('--deselect=tests/test_http_database_runtime.py::test_every_http_database_path_uses_bounded_factory[' + profile + '-GET-/companies/{ticker}/filings/{accession_number}/chunks/{chunk_id}/tone]')
raise SystemExit(pytest.main(args))
'@
& .\.venv\Scripts\python.exe -B -c $runner
```

Final result: **593 passed, 2 deselected**, 15.13s; no failures/skips. Includes all
120 new diagnostic cases and 473 existing adjacent cases. Warnings: existing
Starlette/httpx deprecation and datetime.utcnow fixture deprecations (155 total).
The two explicitly deselected baseline failures are documented above, not repaired.
The initial standalone diagnostic suite before adversarial additions passed 85/85.

Same guard, replace pytest args with:

```python
['-q', '-p', 'no:cacheprovider', 'tests/test_release_profile.py', '-k',
 'invalid_profile_rejects or profile_is_resolved or real_backend_denies or forbidden_routes or every_reviewed_route or actual_route_inventory or added_alias or structurally_equal or websocket or proxy_rewrite']
```

Result: **73 passed, 89 deselected**, 10.70s, one existing deprecation warning.
This selection covers early denial, exact route identity, aliases/replacements,
websockets, proxy forwarding and frozen profile admission; no unrelated writer/AI
or stale encoder-message tests were selected.

Self-review static check: parse current and git-show-HEAD versions of the five
modified production files with ast; remove ONLY latency imports/decorators/spans
and the new observer registration, and normalize the split _get_model local in
embed_texts back to its original call expression. All five ASTs match baseline.
compile(source, path, 'exec') passed all seven Python files without imports or
bytecode output. No separate backend linter/type-check configuration was found.
git diff --check passes; only existing autocrlf notices on two touched files.

New tests cover response status/headers/bytes, citations/order/CIK/versions,
embedding inputs/outputs/arguments, numeric ranking/context, lazy result consumption,
DB ledger/order/count, failure and cleanup precedence, two concurrent fake cold
constructors then warm reuse, context propagation/reset, missing coverage,
late post-finalization work, union-exclusive durations, field/schema/privacy
canaries, every declared cap, denied profiles/configuration/listeners, no HTTP
activation and collector-internal failures.

Outcome: **PASS WITH CONDITIONS**, ready for narrow independent Astra High review.
Conditions: the two proven pre-existing tone inventory test failures remain outside
scope; no real admission/listener/latency/cancellation/model/data/deployment evidence
is claimed. No stage/commit/push. Suggested eventual commit:
`chore: add bounded SEC evidence latency diagnostics`.

Final preservation: inventory 325 -> 328 files, exactly five authorized pre-existing
Python files changed and three authorized files added, zero removals or unrelated
byte changes. SHA256 matches for next-env.d.ts, both pre-existing untracked backend
reports and ignored/untracked backend/.env. main/HEAD remain exactly the starting
baseline; index empty. git diff --check passes (autocrlf notices only). Worktree
contains these eight task entries plus the three preserved original status entries.
No real diagnostic approval, model initialization, PostgreSQL connection, service
startup, provider call, environment-file edit, stage, commit, push or deployment.
Keep this plan active for the requested independent review; do not start measurement.
