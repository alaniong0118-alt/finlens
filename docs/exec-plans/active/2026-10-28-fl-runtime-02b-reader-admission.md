# FL-RUNTIME-02B.1 — Isolate ORM metadata from database bootstrap

Status: active; 02B.1/02B.2 accepted per coordinator, 02B.3A offline-verified/review pending
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
