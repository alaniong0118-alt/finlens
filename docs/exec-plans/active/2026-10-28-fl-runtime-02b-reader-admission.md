# FL-RUNTIME-02B.1 — Isolate ORM metadata from database bootstrap

Status: active; 02B.3B2b-FIX1 offline-verified; focused independent re-review pending
Roadmap phase: bounded runtime foundation; no reader data admission

## Objective

Import `app.orm_base` and `app.models` without database configuration, dotenv,
engine construction, connections or operational imports. Preserve one shared
SQLAlchemy Base, metadata registry and the existing model mappings.

## Current architecture and context

Read root AGENTS.md, ROADMAP.md and .agent/PLANS.md. Entry branch main;
HEAD and local origin/main both `0287e7687a9cdb87eefb1cbfe27afdf9e4475b65`;
index empty. Exactly the three original protected exceptions were present:

| Path | SHA-256 |
| --- | --- |
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

Before edits, hashed all 362 nonignored tracked/untracked files other than
environment files. All three proposed new paths were absent. `models.py` imports
Base from `database.py`, which loads configuration and constructs the operational
engine. Alembic imports the same public Base symbol; keep that export compatible.

## Constraints

Exactly five authorized paths: this plan, app/orm_base.py, app/database.py,
app/models.py and tests/test_orm_import_isolation.py (backend paths).
No other repository edits, staging, commits, push or merge. Never read private
dotenv. No real engine, SQL, connection, service, model, SEC/provider/network call.
Every executable probe installs guards before target imports; legacy bootstrap
compatibility uses a recording fake engine, never SQLAlchemy's real constructor.

## Non-goals

02B.2 and later; routes, reader DB access, publication admission/digests,
financial selectors/calculations/authorizations, schema/migration changes,
deployment, authentication, activation and frontend work.

## Implementation stages

1. Verify baseline, index, inventory and protected hashes; record this plan.
2. Add focused fresh-process tests; demonstrate the old import coupling fails.
3. Extract Base only, retain database re-export and update models' import.
4. Run isolated focused tests, relevant compatibility regressions and syntax.
5. Self-review source/metadata parity and exact scope; recheck preservation.

## Decisions

- 2026-10-28: Use one new inert module; no fallback, duplicate model definitions,
  metadata cloning or second application registry. Do not change operational
  database bootstrap. Fresh processes cover both model-first and database-first
  imports. Compare model definitions from the immutable baseline commit in an isolated reference namespace
  and PostgreSQL DDL in memory, without any database execution.
- Keep this authorized active plan path for coordinator handoff; no move to a
  completed path because the task authorizes exactly five paths.

## Discovered issues

None at preflight. Live database/Alembic execution is explicitly deferred.
The pre-extraction run failed as expected: 24 failing test/subtest cases across
8 methods (18.114s). Failures covered absent orm_base, the forbidden models-to-
database import, identity/import-order assertions and source ownership. Sentinel
negative controls, disabled reader and legacy bounds checks already passed.

## Progress

- [x] Baseline, empty index, protected hashes and absent new paths verified.
- [x] Relevant ORM/database/reader sources and test isolation mechanisms inspected.
- [x] Add tests and demonstrate pre-extraction failures.
- [x] Extract Base and run focused verification.
- [x] Complete source/metadata self-review; verify exact scope and preservation.
- [ ] Independent review/coordinator acceptance (no staging or later work).

## Test and validation strategy

Use installed Python with `-I -S -B`; no site startup, bytecode or pytest cache.
Fresh child processes inject site-packages explicitly after stdlib startup.
Guard imports, dotenv files/loaders, environment URL access, engine constructors,
physical drivers and sockets before target imports. Test sentinels themselves and
an in-memory reintroduction of the old models import. Use synthetic legacy
configuration and a recording fake engine for compatibility checks. Compare
source AST, full model metadata/DDL and mapper identities; no live SQL.
Record exact commands and results below after execution.

## Completion criteria

One Base exported by both modules; unchanged mapped class bodies and database
behavior apart from Base ownership; isolated imports independent of configuration;
focused negative/compatibility tests pass; reader still diagnostics-only; exact
five-file scope and original protected bytes/index/revisions preserved.

## Final outcome

The production delta is only the new six-line inert Base module, a Base import/
re-export replacing the old class in database.py, and the models.py import change.
No mapped class body, engine/session code, policy, route, migration or financial
calculation changed. Base.__module__ now identifies its new owning module;
database.Base remains the identical exported object. Tests compare against
baseline `0287e7687a9cdb87eefb1cbfe27afdf9e4475b65`, not moving HEAD.

### Focused evidence actually run

Working directory: `D:\Projects\finlens-foundation\backend`.

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/test_orm_import_isolation.py
# Before extraction: 8 methods, 24 failing test/subtest cases; 18.114s.
# After extraction: 8 passed; 18.171s. Final run after pinning immutable baseline:
# 8 passed; 18.747s.
```

The eight methods execute 38 fresh-process probes: ten inert imports across
missing/development/sec_readonly/sec_reader/unknown profiles; eleven raising
sentinel negative controls; one in-memory old-import regression; twelve import
orders (all six permutations in each legacy profile); two legacy bounds/missing-
URL checks; one diagnostic reader check; one metadata-reference comparison.
One method additionally compares the full model/database source AST in the
parent. The independent reference registry exists only inside the parity probe;
all six application mappers remain in exactly one application registry.

Metadata evidence: same Base object through orm_base/models/database and legacy
`from app.database import Base`; exact table object and mapper identity; expected
six mappings; full in-memory PostgreSQL table/index DDL, Python column defaults,
autoincrement, mapper attributes and primary-key parity with baseline definitions.
No DDL is executed. Guards reject application bootstrap imports, dotenv loaders/
files, DATABASE_URL resolution, engine construction, physical drivers and sockets.
The disabled reader still has only GET /healthz and GET /capabilities and false
research/AI capability fields. No service or ASGI lifespan was started.

Relevant existing regression, run with the same interpreter flags via stdin:

```python
import runpy
from types import SimpleNamespace
runpy.run_path('tests/run_sec_reader_offline.py', run_name='offline_probe')
import sqlalchemy
import sqlalchemy.engine.create
def forbidden(*args, **kwargs):
    raise AssertionError('Real engine construction forbidden in 02B.1 regressions')
calls = []
fake_engine = SimpleNamespace(connect=forbidden)
def recording_engine(*args, **kwargs):
    assert kwargs == {'pool_pre_ping': True}
    calls.append((args, kwargs))
    return fake_engine
sqlalchemy.create_engine = recording_engine
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
import pytest
result = pytest.main([
    'tests/test_http_database_runtime.py::test_profile_limits_and_startup_options',
    'tests/test_http_database_runtime.py::test_hostile_url_rejected_without_engine_or_connect',
    'tests/test_http_database_runtime.py::test_hostile_environment_rejected_without_mutation',
    'tests/test_http_database_runtime.py::test_tls_preserved_hostname_single_address_and_canonical_options',
    '-q', '--tb=short', '-p', 'no:cacheprovider',
])
assert len(calls) == 1
raise SystemExit(result)
```

Result: 45 passed in 0.48s; one existing Starlette/httpx deprecation warning.
Exactly one recording fake bootstrap, zero real engines or connections. No
runtime/pool/SQL tests requiring real engines or databases were executed.

Four changed Python files were ast.parse/compile checked in memory under
`-I -S -B` without application imports or bytecode. Scoped tracked `git diff
--check` is clean; new files checked using `git diff --no-index --check -- NUL
<path>` (difference exit 1 for additions; no whitespace errors). Git's existing
LF-to-CRLF notices do not modify protected files.

### Preservation and review handoff

Final inventory/hash comparison verified exactly the five authorized paths
changed/added (365 files now versus 362 at entry); all original snapshotted files
other than the two authorized source edits are byte-identical. Verified main,
unchanged HEAD/local origin/main, empty index and all three original protected
hashes. Scoped whitespace checks found no errors in either tracked source or
the three added files.
No private dotenv, real engine, database/SQL, model, SEC/provider/network, service,
deployment or Git delivery operation was used. Live DB/Alembic and deployment
behavior remain unverified; unchanged source and synthetic parity are the scope
of this evidence. Independent acceptance is pending; 02B.2 is not started.

Recommendation: GO for independent review of 02B.1 only.
Suggested commit, only if separately authorized:
`refactor(runtime): isolate ORM metadata from database bootstrap`.

## FL-RUNTIME-02B.2 — Pure SEC URL and vector validation helpers

### Objective and current checkpoint

Extract the existing URL builders and float32 vector validator without behavioral
changes. This section supersedes the historical 02B.1 pending-review/next-work
statements above: the coordinator attests 02A/02B.1 are reviewed and delivered.
Verified main, HEAD/local origin/main
`560dc30c00e56cd3a8978feb87140f42a97359f8`, empty index and exactly the original
three protected exceptions with the SHA-256 values recorded above. All proposed
new paths were absent. Entry inventory has 365 nonignored files, hashed without
reading environment files. Root guidance and ExecPlan rules were reread.

### Scope and decisions

Authorized edits chosen: new app/sec_urls.py, app/embedding_validation.py and
tests/test_pure_helper_isolation.py; existing app/sec_client.py,
app/embedding_service.py, app/freshness_service.py,
app/financial_metrics_service.py, app/financial_insights_service.py; this plan.
All application/test paths are under backend. Nine paths total.

Reviewed direct callers and relevant maintained tests. Other read/operational
callers keep compatibility exports. filing_search_service.py still needs
embed_texts and receives the same validator through the export; no edit needed.
No additional production module or behavioral change is needed. Move the 384
constant with the validator and re-export both from embedding_service. Leave
all acquisition, encoder, policy, calculation, chunk conditions and digest logic
intact. Both pure modules require only Python stdlib; no dotenv or data imports.

### Constraints and non-goals

No private dotenv, real SQL/connections, services, SEC/provider/network calls,
model loading, package installation, schema changes, route/permission changes,
publication-admission redesign, activation, deployment or Git delivery.
No 02B.3 work. Protected bytes and every path outside the chosen scope must stay
unchanged. Pure import probes use independent fresh processes with raising
sentinels installed before target imports. Compatibility tests use synthetic
dotenv only; any legacy engine in maintained regressions is replaced by a
recording object before imports. No real engine is necessary.

### Stages, validation and completion criteria

1. Record verified checkpoint and bounded caller map.
2. Add independent negative/parity probes and demonstrate pre-extraction failures.
3. Move implementations verbatim; preserve compatibility imports; switch the
   three required read-side consumers to pure helpers.
4. Run focused tests and relevant synthetic passage/financial regressions.
5. Verify syntax, AST equivalence, scope/whitespace/index/revisions/protected bytes.

Use immutable baseline `560dc30c00e56cd3a8978feb87140f42a97359f8` for URL/vector
outcome and function/source comparisons, including exception types/messages and
causes. Exercise vector float32 boundaries and complete chunk validation damage
cases; compare digest bytes and unchanged chunk identities. Maintain existing
legacy profile guards and the reader's two disabled diagnostic routes. No test
result implies approval to release research text.

### Progress and discovered issues

- [x] Baseline, protected hashes, empty index and caller/test inspection.
- [x] Negative/parity tests and pre-extraction evidence.
- [x] Bounded extraction and focused regressions.
- [x] Final preservation/self-review and independent-review handoff.
- [ ] Independent coordinator/security acceptance; no Git delivery or later work.

### Actual verification

Working directory `D:\Projects\finlens-foundation\backend`:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/test_pure_helper_isolation.py
# Before extraction: 9 methods, 21 failing test/subtest cases and 1 error, 5.116s.
# Missing helper modules and existing operational imports were detected;
# negative controls and the disabled-reader probe already passed.
# After extraction: 9 passed, 4.349s; final run 9 passed, 4.333s.

.\.venv\Scripts\python.exe -I -S -B tests/test_orm_import_isolation.py
# Existing 02B.1 import/ORM regression: 8 passed, 18.144s.
```

The new suite uses 32 fresh processes. Ten pure-import probes cover missing,
development, sec_readonly, sec_reader and unknown profiles without importing any
third-party/application stack beyond the two helpers. Fifteen negative controls
prove raising imports and dotenv/URL/network initialization sentinels. Other
probes cover legacy exports/profiles, isolated read-side imports, chunk integrity,
disabled reader diagnostics and immutable baseline outcome parity. The source
test also verifies exact function AST equality for all three moved functions and
only the intended moves/import substitutions in all five edited production files.

Outcome comparisons include 240 URL cases and 38 vector factories: Unicode and
numeric CIK normalization, permissive existing accession handling, invalid types,
384 dimensions, float32 extrema/overflow/underflow/subnormals, NaN/infinities,
zero norm, alternate iterable types, exceptions/messages/causes and unchanged
inputs. Chunk tests preserve admitted identities and digest output, with twenty
damaged-chunk cases, empty input and unselected invalid vectors. They do not
admit publications or release research text. Function __module__ ownership moves
to the pure modules; legacy exports refer to the exact same function objects.

Maintained synthetic regressions used the existing offline guards plus a fake
engine before collection. Reproduce with the same interpreter flags via stdin:

```python
import runpy
from types import SimpleNamespace
runpy.run_path('tests/run_sec_reader_offline.py', run_name='offline_probe')
import sqlalchemy
import sqlalchemy.engine.create
def forbidden(*args, **kwargs):
    raise AssertionError('Real engine forbidden in pure-helper regressions')
calls = []
fake_engine = SimpleNamespace(connect=forbidden)
def recording_engine(*args, **kwargs):
    assert kwargs == {'pool_pre_ping': True}
    calls.append((args, kwargs))
    return fake_engine
sqlalchemy.create_engine = recording_engine
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
import pytest
result = pytest.main([
    'tests/test_filing_tone_integration.py',
    'tests/test_financial_insights.py::test_discovery_and_seven_metric_composition_preserve_canonical_results',
    'tests/test_financial_insights.py::test_selected_source_conflicts_reject_dependent_claims',
    'tests/test_financial_insights.py::test_entire_loader_to_utf8_response_and_empty_evidence',
    '-q', '--tb=short', '-p', 'no:cacheprovider',
])
assert len(calls) == 1
raise SystemExit(result)
```

Result: 135 passed, 1.47s, one existing Starlette/httpx deprecation warning.
Exactly one recording fake bootstrap, zero real engines or connections. The
passage suite uses compiled SQL and in-memory Store responses, not SQL execution.
Its digest, pending/version, complete-publication, malformed identity/vector and
cleanup cases remain intact. Selected financial tests exercise canonical
comparisons, source-conflict abstention and complete UTF-8 evidence composition.
No full financial/DB/acquisition/model suite or live acceptance is claimed.

All eight changed Python files parsed/compiled in memory without application
imports or bytecode. Scoped tracked `git diff --check` passed with the existing
repository line-ending configuration. New-file `git diff --no-index --check --
NUL <path>` checks found no whitespace errors (exit 1 denotes additions).
An initial check disabling autocrlf on tracked files misclassified their existing
CRLF bytes; the correct configured check passed without normalization or edits.

### Final scope, limitations and handoff

Inventory/hash comparison verified exactly nine chosen paths: six existing
edits and three additions, 368 files versus 365 at entry. All original files
outside those six edits, including the three protected exceptions and prior
ORM/database/policy/reader sources, are byte-identical. Branch main and
HEAD/local origin/main remain `560dc30c00e56cd3a8978feb87140f42a97359f8`;
index empty. No private dotenv, real engine, SQL, connections, service, SEC/
provider/network call, model load, package installation, migration, deployment,
activation, staging, commit, push or merge occurred.

No scope blocker remains. URL builders retain their prior acceptance behavior;
they are not newly hardened URL validators. Strict publication admission remains
owned by existing readers and is unchanged. Native database/model/provider/
deployment acceptance is not tested. The reader remains diagnostics-only.
02B.3 is unstarted. GO for independent review of 02B.2 only.

Suggested commit, only after separate authorization:
`refactor(runtime): isolate SEC URL and vector validation helpers`.

## FL-RUNTIME-02B.3A — Pure deterministic keyword ranking extraction

### Objective and verified checkpoint

The coordinator authorizes only the pure ranking extraction after the read-only
02B.3 design recommended separate 3A/3B review. Coordinator attestation supersedes
the historical pending-review status above for 02B.2. Preserve legacy keyword
admission, normalization/validation/read order, outputs, exceptions and ORM identity.

Read root AGENTS.md, ExecPlan rules and relevant roadmap context. Verified main,
HEAD/local origin/main `002cb893ce312200416461f93cbbb22ab8458320`, empty index,
only the three protected exceptions and their original hashes above. Both new
paths are absent. Hashed 368 nonignored files before edits without environment
file reads. Actual keyword function, its main.py caller and maintained bounded
research/serialized keyword tests match design assumptions.

### Exact scope and constraints

Only backend/app/keyword_ranking.py (new), backend/app/filing_search_service.py,
backend/tests/test_keyword_ranking_isolation.py (new), and this plan may change.
No additional reads, changed SQL predicates, validation gates, result bounds,
byte/work/deadline/cancellation policy, publication checks, financial/tone changes,
semantic/hybrid changes, reader capabilities, schema/deployment or 02B.3B work.
No private dotenv, real engines/SQL/connections, service, SEC/provider/network,
model loading, installation or Git delivery. Preserve protected bytes/index.

### Implementation decisions and stages

- Move query term preparation into a stdlib-only helper called at the same point
  after legacy validate_research_input and before research_chunks. Keeping term
  preparation before the read preserves normalization/exception ordering and
  avoids redoing normalization in the kernel after a database read.
- Use frozen detached records (position, chunk_index, text); kernel returns
  original positions. The bridge indexes the original list, preserving ORM object
  identity and result types. No rank output attests complete-publication admission.
- Preserve lower/split/strip/count, repeated terms, positive filtering, sort keys,
  stable ties and slicing. No aliases, regex, casefold, weights or deduplication.

1. Record checkpoint and add independent immutable-baseline/negative tests.
2. Demonstrate pre-extraction failures, then implement only the approved bridge.
3. Run focused and maintained synthetic keyword/import/capability regressions.
4. Check syntax, source parity, exact four-path scope, whitespace and preservation.

### Validation and completion criteria

Independent fresh-process sentinels precede pure-module imports. Compare against
immutable `002cb893ce312200416461f93cbbb22ab8458320`, including duplicate terms,
ties, shuffled inputs, Unicode, substrings, empty queries, limits, exception/read
ordering and original return identities. In-memory mutation controls must detect
forbidden imports and altered duplicate/tie semantics. Use fake loaders and
compiled query predicates, never SQL execution. Maintained serialized keyword
tests must retain the intentionally malformed-digest legacy behavior. Full source
AST outside search_filing_chunks must match the baseline apart from one import.

### Progress and results

- [x] Baseline, protected hashes, index and caller/test inspection.
- [x] Add focused tests and pre-extraction evidence.
- [x] Implement and run relevant offline regressions.
- [x] Complete preservation/self-review and independent-review handoff.
- [ ] Independent review/coordinator acceptance; no delivery or later increment.

### Actual verification and outcome

Working directory `D:\Projects\finlens-foundation\backend`:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/test_keyword_ranking_isolation.py
# Before production edits: 8 methods, 10 failing test/subtest cases and 2 errors;
# 3.386s. Missing ranker module and absent delegation were detected.
# After extraction: 8 passed; 3.715s.
```

The eight methods use 23 independent fresh processes: five pure imports across
missing/development/sec_readonly/sec_reader/unknown profiles; twelve negative
import/bootstrap controls, including an injected forbidden import; one immutable
ranking matrix; one duplicate/tie mutation probe; two legacy profile parity
probes; one normalization/detachment probe; one disabled-reader probe. The source
AST/signature comparison runs in the parent. Pure-module import needs no config,
database, SQLAlchemy, encoder/provider or SEC client. Sentinel attempts raise and
are recorded even if application code tries to swallow them.

Ranking parity uses the entire original function extracted from immutable
`002cb893ce312200416461f93cbbb22ab8458320`. The pure matrix compares 432 cases:
nine empty/permuted/duplicate-index/52-row/character-boundary datasets, sixteen
query forms and three limits. Query forms include actual tabs/newlines/Unicode
whitespace, combining marks, lower-vs-casefold differences, punctuation, repeated
terms, zero matches and overlapping substrings. Empty-query arithmetic is tested
with oracle boundary validation bypassed; separate bridge probes retain the real
validator and verify empty/whitespace-only queries fail before reads.

In-memory mutants deduplicate query terms or add position as a tie-breaker. Each
fails the same immutable-oracle comparator that accepts the real kernel. Another
probe injects app.database before the pure source and must fail its import guard.
No mutant is written to disk. Bridge tests use actual mapped FilingChunk objects,
compare identity/result types/exceptions, compile unchanged predicates, and verify
one read for valid input and none for validation failures. A traced string proves
validation and normalization precede the read. Kernel inputs contain only frozen
position/index/text records. SQL is never executed.

Relevant maintained regressions ran through a guarded stdin launcher under the
same interpreter flags. The exact launcher is:

```python
import os
import runpy
from types import SimpleNamespace
from urllib.parse import quote
runpy.run_path('tests/run_sec_reader_offline.py', run_name='offline_probe')
import sqlalchemy
import sqlalchemy.engine.create
def forbidden(*args, **kwargs):
    raise AssertionError('Real engine forbidden in keyword extraction regressions')
calls = []
fake_engine = SimpleNamespace(connect=forbidden)
def recording_engine(*args, **kwargs):
    assert kwargs == {'pool_pre_ping': True}
    calls.append((args, kwargs))
    return fake_engine
sqlalchemy.create_engine = recording_engine
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
node_guard = '''
import net from 'node:net';
import tls from 'node:tls';
import http from 'node:http';
import https from 'node:https';
import dns from 'node:dns';
const forbidden = () => { throw new Error('Forbidden live Node network'); };
net.Socket.prototype.connect = forbidden;
net.connect = net.createConnection = tls.connect = forbidden;
http.request = http.get = https.request = https.get = forbidden;
dns.lookup = forbidden;
globalThis.fetch = forbidden;
'''
os.environ['NODE_OPTIONS'] = '--import=data:text/javascript,' + quote(node_guard, safe='')
os.environ['NODE_DISABLE_COMPILE_CACHE'] = '1'
import pytest
result = pytest.main([
    'tests/test_bounded_research.py',
    'tests/test_sec_reader.py::test_reader_route_inventory_and_capabilities_fail_closed',
    'tests/test_sec_reader.py::test_reader_import_and_requests_are_independent_of_data_and_provider_stack',
    '-q', '--tb=short', '-p', 'no:cacheprovider',
])
assert len(calls) == 1
raise SystemExit(result)
```

Result: 190 passed, 4.98s; one existing Starlette/httpx deprecation warning.
Exactly one recording fake bootstrap and zero real engines/connections. Python
network/drivers/providers/models/dotenv files are guarded before application
imports; Node networking is guarded before its module imports, then maintained
tests install their own synthetic fetch. The Windows stdlib-owned asyncio wakeup
socketpair is the existing runner's sole socket exception, not a service/probe.

This covers the entire bounded research suite, including the actual ASGI-to-TS
keyword serialization contract with an intentionally incorrect manifest digest,
validation before reads, query/result/chunk limits, body/inventory integrity and
existing synthetic semantic/hybrid behavior. Reader import/capability checks
still pass with only diagnostics and false research/AI fields. No live API,
database performance, provider/model or deployment acceptance is claimed.

All three changed Python files parsed/compiled in memory without application
imports or bytecode. Scoped tracked git diff --check passed; new-file no-index
checks found no whitespace errors (exit 1 denotes file additions). Source AST
outside search_filing_chunks is identical to baseline after removing the single
new helper import, including all semantic/hybrid functions. Service signature
and return annotation are unchanged. No bound or lifecycle policy was added.

### Preservation, risks and review handoff

Verified exactly four authorized paths: two edits, two additions, 370 nonignored
files versus 368 at entry. Every original snapshotted file outside the two edits
is byte-identical, including all three protected exceptions and financial/tone/
policy/database sources. main, HEAD/local origin/main remain
`002cb893ce312200416461f93cbbb22ab8458320`; index empty. No staging, commit, push
or merge. No private dotenv, real SQL/connection/engine, live service, SEC/provider
call, model load, installation, reader activation or deployment occurred.

The new helper owns no authority, ORM/session, clocks, request cancellation or
resource-policy decisions. Existing filing_search_service still imports the
encoder module for its unchanged semantic/hybrid functions; only the new kernel
is independently isolated. No observable legacy behavior difference was found
within tested valid ORM/read contracts. Complete-publication admission remains
unimplemented; a keyword result does not prove manifest integrity. 02B.3B is
unstarted. GO for independent review of 02B.3A only.

Suggested commit, only after separate authorization:
`refactor(runtime): isolate deterministic keyword ranking`.

## FL-RUNTIME-02B.3B1 — Shared complete publication integrity core

### Objective, checkpoint and constraints

Extract Tone's complete-publication admission into a reusable module returning
frozen detached scalar records, preserving observable Tone behavior and its
caller-owned read snapshot. Coordinator attests previous increments accepted.
Verified main, HEAD/local origin/main
`a488b7b28c7da2775f73f530fcc49f21015782b8`, empty index, exactly the three
protected exceptions and their SHA-256 values recorded above. Both new paths
are absent. Read root instructions, roadmap, ExecPlan rules, resolver, freshness
primitives, strict-extra lifecycle schema, maintained Tone tests and main's
read_session caller. Gate passed before edits. No private dotenv inspected.

Authorized maximum six paths; chosen five: new backend/app/publication_admission.py,
new backend/tests/test_publication_admission.py, backend/app/filing_tone_service.py,
backend/tests/test_filing_tone_integration.py, and this plan. Leave freshness
primitives and read_session unchanged. No Reader adapter/routes, strict policy,
ranking/financial/provenance changes, new limits, SQL/physical connections,
network/models/providers, services, deployment or Git delivery.

### Decisions and implementation stages

Keep existing freshness primitives as dependencies of the new core, avoiding
cycles and duplicate digest algorithms. Move the admission gates in their exact
order. The core accepts a validated integer version and independently rejects
invalid selector/version types before reads. Tone retains its own pre-DB decoded
pin/selector validation and constructs the unchanged public schemas only after
the entire core succeeds. Core output omits embeddings after validation and
contains only frozen dataclasses, tuples and scalar metadata/text. No selectable
partial result, session owner, lifecycle manager or digest bypass is added.
Narrowly update the maintained schema_ready monkeypatch to its new owning module;
retain the publication-field compatibility export used by the synthetic Store.

1. Record checkpoint; add guarded immutable-baseline tests and negative controls.
2. Extract gates, detach all admitted chunks, retain Tone selection/response adapter.
3. Run focused core tests and complete maintained synthetic Tone regressions.
4. Self-review AST/SQL/failure parity, boundaries, exact scope and preservation.

### Progress and validation strategy

- [x] Pre-edit gate and relevant caller/primitive/test inspection.
- [x] Shared core and Tone adapter.
- [x] Guarded offline oracle, negative, boundary and maintained regression tests.
- [x] Final preservation/self-review; independent review handoff.
- [ ] Independent coordinator acceptance; no Git delivery or later increment.

Use immutable `a488b7b28c7da2775f73f530fcc49f21015782b8` as the Tone oracle,
synthetic sessions and compiled (never executed) SQL. Compare success bytes,
errors/status/headers and read/failure ordering; test complete inventory/digest,
unselected damage, exact established 4000-chunk/3000-character bounds, detached
output, cancellation/cleanup propagation, forbidden dependency controls and
disabled Reader routes. Launch with -I -S -B and guards before app imports;
no pytest cache/plugins. Record actual commands/results and limitations below.

### Completion criteria and outcome

The five chosen paths are implemented and verified offline. Dependency structure:
Tone adapter -> publication_admission -> existing freshness primitives/models/
refresh contracts; chunk validation -> pure SEC URL/vector helpers. There is no
reverse import or dependency on config/database bootstrap/acquisition/encoder.
Freshness primitives (including existing schema capability caching, digest,
resource bounds and read_session) are byte-identical. No new evidence cache.

All gates from company lookup through full digest comparison have identical AST
and order to the immutable resolver. Returned CompletePublication contains a
frozen PublicationManifest and tuple of frozen PublicationChunk scalar records;
no embeddings, ORM rows, session or partially verified chunks escape. Tone's
schema definitions, request validator and scorer have identical AST to baseline.
Its adapter selects only after successful admission; missing passage remains 404
after full integrity validation. Existing error classifications, headers and
cleanup/scoring order are preserved in the synthetic comparisons.

### Actual verification, discoveries and negative controls

Working directory: `D:\Projects\finlens-foundation\backend`.

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/test_publication_admission.py
# Final: 9 methods passed, 12.578s; 26 fresh guarded child processes.
```

The suite covers imports in five profiles, fifteen raising guard/mutant controls,
recursive frozen/scalar detachment and post-admission ORM mutation independence,
80 direct immutable-oracle cases with exact serialized success/error and compiled
SQL/parameters/options/read-order parity, whole-publication/unselected corruption,
missing selection after corruption, no partial detachment, reordered-body rejection,
21 cancellation/runtime propagation injections and cleanup failure propagation.
Source assertions prove unchanged public schema/validator/scorer AST and the
verbatim admission gate sequence. No SQL is executed.

Boundary probes admit 4000 chunks each of 3000 Unicode code points (24 million
UTF-8 bytes) and a lifecycle last_error of 65537 characters; no unapproved output
or lifecycle cap was introduced. Existing one-over manifest/inventory/text bounds
reject before body reads. Import controls reject operational database/config,
SEC/encoder/provider stacks, models, Reader/bootstrap; initialization controls
reject engine creation, DATABASE_URL access, dotenv-file reads and networking.
An in-memory forbidden-import mutant trips the same guard. An in-memory digest-
bypass mutant must fail the unselected same-length corruption assertion; neither
mutant is written to the repository. Scoring-work and deadline policies remain
absent, as confirmed by the unchanged gate/primitives source.

Initial verification exposed two harness defects: the immutable module's Pydantic
objects must use its own scorer, and the first generated matrix had 77 cases
rather than its asserted 80. Corrected the scorer selection and added three
state-version corruption cases. Production admission needed no correction.

Maintained regression launcher, run via stdin with the same interpreter flags:

```python
import runpy
from types import SimpleNamespace
runpy.run_path('tests/run_sec_reader_offline.py', run_name='offline_probe')
import sqlalchemy
import sqlalchemy.engine.create

def forbidden(*args, **kwargs):
    raise AssertionError('Real engine forbidden in publication admission regressions')
calls = []
fake_engine = SimpleNamespace(connect=forbidden)
def recording_engine(*args, **kwargs):
    assert kwargs == {'pool_pre_ping': True}
    calls.append((args, kwargs))
    return fake_engine
sqlalchemy.create_engine = recording_engine
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
import pytest
result = pytest.main([
    'tests/test_filing_tone_integration.py',
    'tests/test_sec_reader.py::test_reader_route_inventory_and_capabilities_fail_closed',
    'tests/test_sec_reader.py::test_reader_import_and_requests_are_independent_of_data_and_provider_stack',
    '-q', '--tb=short', '-p', 'no:cacheprovider',
])
assert len(calls) == 1, calls
raise SystemExit(result)
```

Result: 146 passed in 2.83s; one existing Starlette/httpx deprecation warning.
Exactly one recording fake bootstrap, zero real engines/connections. These are
in-process synthetic ASGI requests, not live HTTP/service acceptance. The 19 new
HTTP comparisons use the exact immutable resolver with unchanged schema classes
and compare response bytes, all headers/status, SQL/read events and scoring calls.
Cases include valid/old/Unicode/unscorable/unsupported text, pin failures,
manifest/pending/digest/unselected damage, resource/metadata failures, missing
selection and failed cleanup. Reader remains diagnostics-only with research/AI
capabilities false. The sole socket exception is the existing guarded stdlib
Windows asyncio wakeup socketpair, not an external service or network probe.

### Preservation, remaining boundaries and review handoff

Pre-edit inventory hashed 370 nonignored tracked/untracked files, excluding env
files. Final comparison has 372 files, no deletions, and exactly the five chosen
changed/added paths. Every original file outside the three chosen existing edits
is byte-identical, including freshness, main, search, ranking, sec_reader and the
three protected exceptions. All four changed Python files parse/compile in memory
under -I -S -B without application imports or bytecode. Configured git diff
--check and both new-file no-index checks find no whitespace errors (exit 1 for
new-file differences). Existing LF-to-CRLF notices are informational.

main, HEAD/local origin/main remain
`a488b7b28c7da2775f73f530fcc49f21015782b8`; index empty. No private dotenv,
real SQL/connection, model loading, SEC/provider request, live service, deployment,
staging, commit, push or merge occurred. No source outside the five chosen paths
was edited. Protected SHA-256 values remain exactly those recorded above.

No blocker to independent review of this compatibility extraction. A future
strict Reader entry point still needs separately approved finite lifecycle,
scoring-work, deadline and output controls, caller-owned Reader DB/HTTP lifecycle
and route/authorization review. None is implemented or activated here. This
digest checks stored consistency; it cannot authenticate privileged DB writers or
replace financial authorization. No live DB/performance/deployment acceptance
is claimed. Broader 02B.3B/02B.4 remain unstarted.

GO for independent review of 02B.3B1 only. Suggested commit, only after separate
authorization: `refactor(runtime): share complete publication admission core`.
<!-- Latest scoped increment is recorded below; historical evidence stays scoped. -->


## FL-RUNTIME-02B.3B2b — Strict Reader publication helper

### Objective, checkpoint and scope

Implement only the approved fixed strict Reader admission helper through the
mandatory shared integrity pipeline; preserve immutable Tone compatibility.
Pre-edit: main at `14c8341009fbb978be96828cbd44123b055afb7b`, empty index,
exactly the three historical protected exceptions and matching SHA-256 values
recorded at the top of this plan. Both new paths absent. Root AGENTS, roadmap,
ExecPlan rules and relevant source/tests read. Private dotenv never inspected.
A non-environment inventory snapshot is held outside the repository for final
preservation comparison.

Exactly five authorized paths: app/publication_admission.py, new
app/reader_resource_policy.py, new tests/test_reader_publication_admission.py,
tests/test_publication_admission.py (all backend), and this plan. No sixth path,
Git delivery, physical database, network, model/provider, service or activation.

### Decisions and stages

1. Verify baseline/protected bytes and inspect only direct integrity dependencies.
2. Add fixed policy and private shared pipeline branches; no public override.
3. Add actual-entry resource, integrity, projection, parser and mutation tests.
4. Run offline focused/Tone tests, self-review and final preservation checks.

Use PostgreSQL `octet_length(convert_to(CAST(evidence AS TEXT), 'UTF8'))` in
both size and CASE guard. Existing JSON column preserves whitespace/escapes;
no JSONB cast or normalized Python reserialization is size authority. Strict
projections exclude facts/cleaned_text and ORM entities. Returned identity,
versions, byte size and complete text are rechecked. CASE bounds transfer,
not server CPU/RSS/time. No real PostgreSQL execution is authorized.

Correction to prior design/calibration benchmark wording: deep-JSON synthetic
benchmark evidence demonstrated early detection, **not parser avoidance**. No
such benchmark is recorded in the preceding committed plan sections; it must
not be promoted to an implementation claim. New tests must sentinel the parser
through the actual strict entry for excessive bytes and nesting.

Resource policy: lifecycle <=131072 UTF-8 bytes, container depth <=2, pending
array occurrences <=4096; chunks <=4000 (4001 sentinel), each text <=3000 code
points, aggregate <=12000000 code points / <=48000000 UTF-8 bytes; vectors
exactly 384 dimensions, aggregate <=1536000 components; detached non-text
<=2000000 logical bytes, total <=50000000 logical bytes. Logical accounting
counts every scalar occurrence: UTF-8 strings, decimal ASCII integers and ISO
dates, excluding container/object overhead and discarded vectors. Scalar types
and schema widths are checked before encoding/accounting/detachment.

Lifecycle: scan bounded original text before parsing, ignoring quoted/escaped
delimiters; reject duplicate decoded keys, unknown fields before Pydantic, count
pending targets without deduplication, then retain full StreamState validation.
Invalid selectors -> 422 before reads; stale pin -> DATA_VERSION_CHANGED before
lifecycle processing; resource excess -> SEARCH_SCOPE_TOO_LARGE before unsafe
processing; otherwise malformed -> EVIDENCE_PENDING. Tone retains its policy
and read/error order. Mixed-case precedence and scanner semantics tested below.

### Progress and validation

- [x] Baseline and protected gate.
- [x] Fixed policy and shared pipeline implementation.
- [x] Focused tests, mutation controls and immutable Tone compatibility.
- [x] Self-review, final scope/hash/index verification and handoff.

Deferred: Reader adapter/session ownership, DB/HTTP lifecycle, real database SQL
execution/encoding and performance acceptance, elapsed/RSS/selected-response
limits, ranking and its proposed 256000000 work budget, routes/capability wiring,
service startup, acquisition, models/providers and deployment. Reader remains
diagnostics-only. No next increment is authorized. Independent Astra High review
and coordinator Git Step 1 remain subsequent gates.

### Actual verification and self-review outcome

Working directory `D:\Projects\finlens-foundation\backend`:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/test_reader_publication_admission.py
# Final: 9 methods passed, 10.281s; 12 fresh guarded child processes.
.\.venv\Scripts\python.exe -I -S -B tests/test_publication_admission.py
# Final: 9 methods passed, 13.560s; 26 fresh guarded child processes.
```

The Reader suite tests the actual strict entry, scalar detached/frozen results,
public bypass rejection, pin zero/older intact publications, exact lifecycle byte
boundary and one-over, exact pending/depth boundaries, escaped delimiters,
malformed roots, duplicate decoded keys (including escaped key spellings),
unknown members before Pydantic, dense/mixed-invalid pending arrays and numeric
tokens with 10000 digits without numeric conversion. Numeric tokens produce a
private marker; complete structural/resource validation precedes rejection of
invalid scalar types. Stored representation whitespace and multibyte characters
are accounted without reserialization. Stale pins precede parser invocation.

The 4000-row successful strict fixture simultaneously reaches 3000 code points
per chunk, 12000000 aggregate code points, 48000000 UTF-8 text bytes and 1536000
vector components. Over-count, 4001 sentinel, per-text one-over and 383/385-vector
dimensions reject; inventory/body reorder, missing/truncated/duplicate data,
late unselected corruption, final invalid/nonfinite/zero/overflow vectors,
canonical identity and wrong digest all reject without any partial detachment.
Actual pgvector-style NumPy float32 arrays pass; zero-dimensional arrays reject
as malformed evidence before len/conversion. All vector validation remains in
the mandatory shared pipeline; no vector is returned.

Independent aggregate arithmetic tests check exact limits and one-over. Some
aggregate excesses are already implied by count*per-row limits; 50000000 total
is exactly 48000000 text + 2000000 metadata, so its one-over cannot independently
be reached while both constituent limits pass. A separate actual-entry fixture
reaches exactly 2000000 non-text logical bytes and proceeds to an integrity
sentinel; one additional byte fails before that sentinel. This uses deliberately
noncanonical but scalar-width-valid metadata and is **not** a successful
publication fixture. Repeated scalar occurrences are compared against the exact
expected sum, not deduplicated by value/object identity.

Five in-memory negative mutations each fail for their intended reason:

1. Digest comparison bypass -> `strict corruption accepted`.
2. Strict entry switched to legacy -> `strict corruption accepted`, using a
   dual-mode synthetic session and valid lifecycle JSON exceeding 131072 bytes.
3. SQL CASE changed to return raw text on excess -> `oversized payload transferred`;
   the synthetic executor materializes/records the actual returned raw payload
   based on compiled CASE semantics, even though Python later rejects it.
4. Depth check removed -> `deep JSON reached parser` from the raising parser
   sentinel through the actual strict entry.
5. Canonical-source check bypass -> `strict corruption accepted`; inventory is
   updated to the same damaged URL so no earlier identity mismatch masks it.

The transfer control is compiled-SQL plus synthetic executor evidence, not real
PostgreSQL execution. ReaderStore rejects ORM projections and legacy session
methods, checks explicit UTF8 conversion in both SQL expressions, excludes
facts/cleaned_text and verifies chunk sentinel/body length predicates. Actual
entry tests use parser sentinels for both byte excess and depth excess. Twenty-
five query-stage injections cover driver ProgrammingError/OperationalError,
RuntimeError, CancelledError and KeyboardInterrupt; six validation/digest-stage
injections also propagate unchanged. Session lifecycle ownership is absent.

Immutable Tone oracle remains pinned to
`a488b7b28c7da2775f73f530fcc49f21015782b8`. All 80 direct oracle cases still
compare successful JSON bytes, errors/status/headers, SQL/parameters/options and
read order. The AST test only erases fixed Reader branches and maps the local
evidence alias back to state.evidence; it still compares the entire legacy gate
sequence and the unchanged public schema/scorer. The legacy wrapper is asserted
to fix reader=False. Pin zero, intact older publications and publication version
<= evidence version <= current data version remain covered.

Maintained Tone plus disabled-Reader regression: **146 passed in 2.94s**, one
existing Starlette/httpx deprecation warning. Reproduction: use the full guarded
stdin launcher recorded in the preceding 02B.3B1 Actual Verification section
with the same interpreter flags, three selected test targets and fake engine;
only the forbidden-engine diagnostic text changed. Exactly one recording fake
bootstrap, no physical engines/connections. The 19 immutable ASGI comparisons
retain exact bytes, all headers/status, SQL/read ordering and scoring calls.
Reader still has only healthz/capabilities and false research/AI capabilities.
These are in-process synthetic requests; no live HTTP/service was run.

All four Python files parse/compile in memory with no application imports or
bytecode. Scoped tracked/new-file whitespace checks pass (new-file no-index
exit 1 only denotes additions). No unrelated broad audit was rerun.

Final inventory comparison verifies exactly the five authorized changed/added
paths against the pre-edit snapshot; every other original non-environment file
is byte-identical, with no deletions. main and HEAD remain
`14c8341009fbb978be96828cbd44123b055afb7b`; index remains empty. The three
protected hashes remain:

- next-env: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- canary report: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- discovery report: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Final Git status is the three protected exceptions plus the three scoped tracked
edits and two scoped new files. No staging, commit or push. No private dotenv
read/hash, real SQL/database, network/acquisition, provider/model, service,
activation, deployment or HTTP/DB lifecycle work occurred. The policy adds no
ranking machinery or 256000000 work budget. Elapsed time, RSS, selected-response
limits and the separately approved future adapter/real DB/HTTP/runtime gates
remain deferred; projection is not a PostgreSQL CPU/RSS/time guarantee.

GO for independent implementation review of 02B.3B2b only. No known offline
implementation blocker; independent Astra High acceptance and coordinator Git
Step 1 are pending. Suggested commit after separate authorization:
`feat(runtime): add strict reader publication admission helper`.


## FL-RUNTIME-02B.3B2b-FIX1 — Reader-only no_autoflush correction

### Objective, checkpoint and constraints

Coordinator reports Astra High FAIL/NO-GO for one P2: strict Reader SELECTs can
implicitly flush pending caller ORM state. Earlier UTF-8, depth, structural,
integrity and Tone compatibility areas passed independent review and are not
being redesigned. This finding supersedes the earlier no-known-blocker handoff.

Verified main at `14c8341009fbb978be96828cbd44123b055afb7b`, empty index,
the existing five-path implementation and three original protected exceptions.
All three historical SHA-256 values match. Read root AGENTS, ExecPlan rules and
the existing plan. Snapshot all non-environment repository files outside the
repository; never inspect/hash private dotenv.

Exactly three correction paths: backend/app/publication_admission.py,
backend/tests/test_reader_publication_admission.py, and this plan. Preserve
all other bytes, including prior implementation changes. No Git delivery,
lifecycle ownership, explicit flush/commit/rollback, real engine/SQL/network,
services, model/acquisition, activation or next Runtime increment.

### Decision, stages and verification strategy

Wrap the whole strict entry's private shared admission call in the supplied
Session's actual no_autoflush context. Leave the Tone entry and shared pipeline
unchanged. SQLAlchemy restores its prior configuration via finally, including
False, exceptions and BaseException. No permanent session setting is added.

Add a real unbound Session fixture with pending mapped Company state and a
raising flush sentinel. Keep real Session.execute and ORM autoflush machinery;
intercept only bind resolution after the real autoflush gate to replay the
existing synthetic projected rows, without engine/connection/SQL. Check success,
ordinary failure and cancellation at every SELECT, initial True/False state,
pending-state preservation, no cleanup, and unchanged Tone autoflush behavior.
One in-memory removal mutant must hit the raising flush sentinel before the
post-autoflush fixture interception.

- [x] Baseline/protected gate and bounded dependency inspection.
- [x] Add regression and demonstrate pre-fix autoflush failure.
- [x] Add Reader-only context and verify focused restoration/mutation probes.
- [x] Relevant Reader/Tone/disabled-Reader regressions; syntax/whitespace.
- [x] Final three-path preservation and focused Astra re-review handoff.

### Actual FIX1 evidence and outcome

Production correction is only `with session.no_autoflush:` around the strict
entry's complete `_admit_publication(..., reader=True)` call (+2/-1 lines).
Error translation occurs after context exit. No Tone entry, shared integrity
pipeline, SQL projection/order, resource ceiling, lifecycle or other production
AST changed; an in-memory pre-correction/current AST comparison verified this.
No session ownership, permanent autoflush assignment or explicit flush/commit/
rollback/cleanup was added. Synthetic ReaderStore only gains a null context
interface; it is not the implicit-autoflush regression authority.

The regression uses a real unbound `sqlalchemy.orm.Session`, real mapped pending
Company state, the actual Session.no_autoflush property, and real Session.execute
-> ORM pre-session execution -> Session._autoflush machinery. A raising flush
sentinel replaces only Session.flush. A dedicated get_bind exception intercepts
execution AFTER the actual autoflush gate; a wrapper replays the existing scalar
projection fixtures from that interception. Session.connection is synthetic for
the existing schema-capability probe; _connection_for_bind and all cleanup/
transaction methods raise if used. No engine, physical connection or database SQL
is involved. No do_orm_execute early-result hook masks autoflush.

Before the production correction, the new actual-entry regression failed with
`AutoflushAttempt: implicit Reader autoflush reached flush sentinel` at the first
company SELECT, through SQLAlchemy context.py -> Session._autoflush -> flush.
Result: 1 test, 1 expected failure, 0.786s. This reproduced the review finding
before applying the fix.

After correction, the real-Session matrix verifies initial autoflush True/False:
2 successful full Reader admissions; 30 failures (RuntimeError, CancelledError,
KeyboardInterrupt at each of the five SELECT stages for both initial settings);
4 mapped malformed/resource HTTP failures; one caller-owned nested no_autoflush
admission. All 37 Reader invocations preserve pending ORM state, unbound status,
zero flush calls and the exact prior autoflush setting. Every intercepted Reader
SELECT observes False. The nested context restores False internally and True
only on the caller's outer exit. A separate actual Tone entry with initial True
still triggers its original autoflush sentinel, proving the correction is
Reader-only.

One targeted in-memory mutant removes precisely the new context. It raises the
same AutoflushAttempt at the first real ORM gate, with exactly one flush call,
zero post-autoflush read interceptions, unchanged pending state, bind=None and
autoflush=True. The control checks these facts before reraising, so unsupported
fake-session interfaces or unrelated fixture failures cannot satisfy it. No
mutation was written to the repository.

Commands actually run from `D:\Projects\finlens-foundation\backend`:

```powershell
# Pre-fix: 1 expected failure; post-fix targeted pair: 2 passed, 1.625s.
.\.venv\Scripts\python.exe -I -S -B tests/test_reader_publication_admission.py ReaderPublicationAdmissionTests.test_real_unbound_session_no_autoflush_and_restoration
.\.venv\Scripts\python.exe -I -S -B tests/test_reader_publication_admission.py
# 11 passed, 12.486s.
.\.venv\Scripts\python.exe -I -S -B tests/test_publication_admission.py PublicationAdmissionTests.test_tone_matches_immutable_oracle_for_integrity_matrix PublicationAdmissionTests.test_source_gate_order_and_unmodified_public_schema PublicationAdmissionTests.test_detached_complete_output_and_pin_validation
# 3 passed, 1.836s; all 80 immutable direct Tone cases retain exact SQL/read/output/error parity.
.\.venv\Scripts\python.exe -I -S -B tests/test_reader_publication_admission.py ReaderPublicationAdmissionTests.test_no_autoflush_removal_hits_real_flush_sentinel
# Final strengthened negative probe: 1 passed, 0.809s.
```

Narrowed immutable ASGI/disabled-Reader regression: **21 passed in 2.28s**, one
existing Starlette/httpx deprecation warning. Use the guarded stdin launcher
recorded above with the same interpreter flags and recording fake engine, but
replace the complete Tone test-file target with:
`tests/test_filing_tone_integration.py::test_http_bytes_headers_and_failure_order_match_immutable_head`;
retain the two recorded disabled-Reader targets. Exactly one recording fake
bootstrap; zero real engines/connections. This checks all 19 immutable HTTP
bytes/status/headers/SQL/read-order cases and two diagnostics-only route/import
checks. No broad QA/audit rerun, live service or PostgreSQL occurred.

Both correction Python files parse/compile in memory without imports/bytecode.
Correction-scoped whitespace checks pass. Final non-environment inventory
comparison against the FIX1 entry snapshot verifies exactly the three authorized
correction paths, no additions/deletions and every other file byte-identical,
including reader_resource_policy.py and test_publication_admission.py.

Final main/HEAD remain `14c8341009fbb978be96828cbd44123b055afb7b`, index empty.
Git status still consists of the existing five-path implementation (three tracked
edits and two new files) plus the same three protected exceptions. All three
protected SHA-256 values remain exactly the historical values above. No private
dotenv read/hash, staging, commit or push.

No known remaining FIX1 blocker: **GO for focused Astra High re-review**.
Independent acceptance and coordinator Git Step 1 remain pending. Reader remains
diagnostics-only; all previously deferred DB/HTTP/runtime, ranking, activation
and deployment gates remain deferred. Stop here; no next increment is started.
Suggested commit only after separate authorization:
`fix(runtime): suppress strict reader admission autoflush`.
