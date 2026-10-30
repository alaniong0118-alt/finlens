# UCR-OWNERSHIP-PG-01A — dormant PostgreSQL acceptance harness

Status: active; authoring authorized, operational execution NOT authorized.
Current disposition: independent Astra FAIL on the initial three-file candidate;
FIX1 corrections authorized. Git Step 1 and operational execution remain NO-GO.
Roadmap phase: bounded UCR/15a–15b ownership acceptance prerequisite.

## Objective

Author the coordinator-reviewed isolated PostgreSQL plan and privilege/resource
amendments in exactly the launcher, acceptance module and this ExecPlan. Establish
new offline guard evidence only. Real PostgreSQL acceptance remains unexecuted.

## Current architecture and context

Entry: main at c83449d4e87512c173680369916121a58227ac4d; empty index. Only the
three protected exceptions existed; their recorded SHA-256 values matched:

- frontend/next-env.d.ts: f4e8976c19fc926644d72610bf1058bd6bf52add97e46a02bc0b912a751625c0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: a783517d2875e39df4c831c410265d0126fbf6a9d3ddba1103f7bd61b057844c
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: f8df96c8890c0ece1e1701b25bc5c43b879c359eceb96acb451a2a0daa58bf7c

Read AGENTS.md, .agent/PLANS.md, roadmap and the relevant unchanged ownership,
authentication, ORM and migration sources. Reuse completed authentication,
ownership, C1 and C5 evidence without rerunning or reopening those groups.
The canonical 67-item inventory and recorded statuses remain unchanged; this is
not a product audit, UCR completion or release acceptance.

## Constraints

Only these paths may change:

1. backend/scripts/accept_research_ownership_postgres.py
2. backend/tests/acceptance_research_ownership_postgres.py
3. docs/exec-plans/active/2026-10-30-ucr-ownership-postgres-acceptance.md

No dependencies, Docker invocation, database connections/SQL, migrations, services,
provider/SEC requests, application integration or Git writes during authoring.
Never read/hash backend/.env. No changes to existing application, migrations,
configuration, workflows, requirements or completed evidence.

## Non-goals

Production identity/supervision, provider commissioning, HTTP/UI, financial
admission, source custody, Reader activation, actual transport lost-ack evidence,
native Windows containment acceptance or automatic next-phase execution.

## Implementation stages

1. Preserve baseline and author inert launcher with explicit future authorization.
2. Encode bounded run-owned target, restricted privileges and real acceptance cases.
3. Add positively guarded candidate-specific offline adapter/refusal checks.
4. Run only those new offline checks; syntax/scope/preservation self-review.
5. Stop for coordinator assessment and independent Astra review.

## Decisions

- 2026-10-30: Retain one fresh local Docker PostgreSQL 16/pgvector container;
  no environment comparison is reopened. No existing DSN/container/volume input.
- The future worker uses real service/verifier/repository and transactions. A
  temporary minimal Alembic environment uses committed revisions, not env.py or
  create_all. Empty legacy schemas/rows are preservation evidence only for this
  synthetic target, never populated production data.
- Effective grants include PUBLIC, membership, column ACLs and ownership checks.
  Service: CONNECT; public USAGE; ownership SELECT/INSERT; UPDATE only account
  cutoff/revision, session state/revision, artifact revision (row locking). No
  sequences, TEMP, CREATE, role memberships, ownership, DELETE or TRUNCATE.
- Resource controls and cleanup are candidate behavior until separately run.
  Unknown creation never means absent; cleanup requires positive ownership.

## Discovered issues

The initial new offline run executed 38 checks with two failures: the fake adapter
raised an assertion instead of modeling an inspect failure for a changed ID, and
a source assertion used the wrong local alias for the real OwnershipService.
Both fixture assertions were corrected without weakening operational guards.
The next 38-check run passed. Subsequent 40-check run also passed.

Source self-review additionally corrected buffered read(n) to read1(n) so small
progress events cannot be hidden until a buffer fills; privilege/constraint probes
reuse the bounded service pool rather than opening a third service connection;
target system ID/version/database/user are checked before migration writes;
cleanup ownership is separate from configuration acceptance so a failed bound
does not strand an otherwise positively identified owned container. Invalidation
events track closed physical connections and prohibit their reuse. Partial worker
events survive worker failure. Evidence-sink failure cannot authorize more work
or block already-owned cleanup; final reporting fails closed.

Docker/image/Windows compatibility and real database behavior remain unverified.
This candidate requires observable Linux cgroup v2 bounds; unavailable settings
or incompatible read-only/runtime-file mounts are commissioning failures, with
no writable-root, volume, cgroup-v1 or larger-resource fallback. Reading effective
kernel limits in a later run is not a stress/OOM or Windows watchdog proof.

## Progress

- [x] Baseline, empty index and protected hashes verified.
- [x] Launcher and real acceptance path authored, 2026-10-30.
- [x] New offline guards/checks run; final results recorded below.
- [x] Final scope, syntax, preservation and self-review recorded, 2026-10-30.
- [ ] Independent review (not authorized by this task).
- [ ] Operational commissioning/authorization and PostgreSQL run (not authorized).

## Test and validation strategy

Use the existing Python interpreter with -I -S -B for a self-contained new offline
suite. Install positive guards before loading the candidate; real subprocesses,
sockets/database drivers, Docker and operational application imports must fail.
Fake operational adapters test construction and state decisions only. No existing
authentication/ownership/C1/C5/browser suite or broad regression runs.

### Implemented candidate behavior

Both modules import standard-library code only. Default/help refuse before
application imports or operational adapters. The acceptance file is not named
test_*.py and defines no discoverable TestCase outside its explicit --offline
function. No application startup, existing test, workflow or environment setting
registers this harness. The private worker is launcher-composed code, not an OS
boundary against privileged Python callers.

Future CLI requires --execute, --docker-context, --expected-context-endpoint
(local named pipe or Unix socket only), --image pgvector/pgvector@sha256:<digest>,
--expected-head c83449d4e87512c173680369916121a58227ac4d and --candidate-sha256.
--allow-pull defaults false. Candidate digest is SHA-256 over the ordered three
FILES entries: for each, unsigned 8-byte big-endian length plus UTF-8 relative
path, then unsigned 8-byte length plus exact file bytes. It includes this plan,
so obtain the final digest from the coordinator handoff, not a self-embedded hash.
Future execution uses the established Windows backend/.venv interpreter and
requires unchanged reviewed backend inputs, expected branch/HEAD, empty index,
only whitelisted/protected status entries and matching protected hashes.

The launcher creates its own uniquely named network/container, captures full
IDs and creation intents, compares labels/names/image/network identity and uses
only Docker's assigned 127.0.0.1 port with fresh in-memory credentials. It accepts
no existing DSN, database, container, volume or cleanup-target option. The external
TCP cluster system ID must match the freshly captured container's system ID
before any migration write. Unknown creation is not absence; no automatic retry.

| Resource | Encoded bound and evidence |
|---|---|
| Logging/root | Per-container log-driver none; read-only root; logging_collector off. Runtime mounts and a failed read-only root write probe required. |
| Writable storage | PGDATA tmpfs 256 MiB; /tmp and socket tmpfs 16 MiB each; /dev/shm and runtime /dev 64 MiB each. Read-only runtime hosts/hostname/resolver files; no named/anonymous volumes or unexpected writable storage. |
| CPU/memory/processes | 2 CPUs, 768 MiB memory, memory-plus-swap 768 MiB (zero swap), 128 PIDs, private IPC/cgroup namespace. Inspect settings plus memory.max, memory.swap.max, cpu.max and pids.max; unavailable observations fail. |
| Processes/output | Chunked concurrent capture: CLI 128 KiB combined; worker 512 KiB combined; progress line 8 KiB. No unbounded communicate/readline/spool. Whole sanitized evidence <=2 MiB with cleanup reserve. |
| Deadlines | Inspect 5s; create/start 10s; approved pull 60s; startup 60s; migration/provisioning 60s; scenarios 90s; worker <=660s within whole run 900s with 30s cleanup reserve. Stop <=10s, each remove <=5s within cleanup budget. |
| DB/workers/rows | Two operation workers; two service connections, one observer, at most one bootstrap connection; no overflow, checkout 1s, connect 2s. PostgreSQL max_connections 12. Retained rows <=64 accounts/256 sessions/512 artifacts. Service limits unchanged. |
| Host/cleanup | One new LOCALAPPDATA/FinLens/ownership-acceptance/<nonce> directory; receipt and exact temporary migration/env.py. Remove only positively identified owned container/network and matching generated migration file/directory; retain sanitized receipt. No prune, prefix sweep, volume removal, shared-image removal or global setting changes. |

Effective service role is LOGIN, connection limit 2, NOINHERIT, NOSUPERUSER,
NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS, with no memberships or object
ownership. PUBLIC database privileges (including TEMPORARY) and public-schema
privileges are revoked only in the newly generated database. Service gets only
CONNECT and schema USAGE. Run-local HBA allows that login only to the generated
database; maintenance/template ACLs are untouched. Newly migrated column ACLs
must initially be absent; unexpected grants fail closed rather than being trusted.

| Tables | Effective privileges |
|---|---|
| research_accounts | SELECT, INSERT; UPDATE(token_cutoff, revision) |
| research_sessions | SELECT, INSERT; UPDATE(state, revision) |
| research_artifacts | SELECT, INSERT; UPDATE(revision), needed for SELECT FOR UPDATE |
| Legacy application/Alembic tables and sequences | None; no ownership, grant options or memberships supply indirect authority |

No service DELETE/TRUNCATE/REFERENCES/TRIGGER, schema/database CREATE or TEMP.
The real worker checks effective catalog privileges, column ACL behavior, PUBLIC,
membership and ownership; rollback-contained negative probes require 42501.
CREATE DATABASE is intentionally not probed inside a transaction (25001 would
not prove denial); NOCREATEDB/NOSUPERUSER are checked. Other-database HBA probes
require 28000. Safe legacy DML probes affect zero rows even if an unexpected grant
exists. Bootstrap/observer authority is never passed into service composition.

### Future PostgreSQL scenarios — all NOT RUN

The exact parent/worker protocol requires all 28 named scenarios and individual
pass events before a complete event can be accepted. Final run success additionally
requires actual owned-resource cleanup and durable bounded evidence.

1. Real Alembic base -> e4dda2eedbb0 -> 36134e0d3560 -> 77068e51af12 ->
   d7b834408ba8 -> f94c6f41e0cb -> a7c730103001; vector prerequisite; temporary
   minimal env consumes supplied connection only. Additive schema/defaults/
   collations/constraints, explicit repeated upgrade and empty legacy schema/
   sequence preservation. Never create_all, normal env.py, dynamic head or downgrade.
2. Effective privileges and rollback-contained probes; valid/bad/unconfigured
   actual token verification before database checkout.
3. Concurrent first account/session creation with distinct and identical requests;
   last session and artifact slots; concurrent artifact replay/conflicting reuse.
4. Two-owner service denial; actual unique/composite-FK/lifecycle SQLSTATE checks;
   exact case identity and revision checks.
5. Reservation-before-revocation, revocation-before-reservation, read-before-
   revocation and revocation-before-read; both invalidation orderings; cutoff
   equality/less-than denial, genuinely fresh token after bounded real-clock wait,
   nondecreasing repeated cutoff.
6. Pre-dispatch cancellation and absence before retry; confirmed persistence with
   withheld delivery after cancellation or key-snapshot change.
7. Injected before/after-real-commit failures; independent durable ground truth and
   authorized same-key reconciliation; later revocation/invalidation denial.
8. Genuine captured-backend termination before commit and at dispatch; injected
   rollback/close failures; physical invalidation, closed drivers, no checked-out
   connection, idle transaction or lingering blocker; final service disconnects.

Concurrency requires distinct real backend PIDs and pg_blocking_pids/Lock witness
while the first worker holds its account insert/row lock. Evidence includes XIDs,
backend start identities and wait details. Missing witness fails, with release
inside the unchanged 1-second service lock budget. No start-barrier-only pass.
JWTs are signed using ephemeral in-memory RSA keys through SingleIssuerVerifier;
the real OwnershipService/repository and SQLAlchemy/psycopg transactions run under
the restricted login. No fake principals/repositories in the PostgreSQL path.

Injected after-commit exceptions simulate lost acknowledgement; real backend
termination exercises a genuine driver/server failure. Actual committed-but-lost
transport acknowledgement remains NOT_TESTED, never inferred from either case.
Legacy financial/source/publication tables stay empty; no production records,
backup, report, SEC store, provider or financial authorization is involved.

### Observed new offline evidence

Working directory for the sole new suite command: D:/Projects/finlens-foundation.

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/acceptance_research_ownership_postgres.py --offline

Runs: initial 38 checks / 2 failed fixture assertions; corrected 38 checks /
0 failures/errors/skips; expanded 40 checks / 0 failures/errors/skips; expanded
44 checks / 0 failures/errors/skips. The last 44-check run was repeated only
after a further source change to encode quota-boundary replay and retained
artifact quota after parent revocation; closure result is 44 passing checks,
zero failures/errors/skips. No completed group was rerun.
The suite uses only standard-library fake processes/Docker adapters and synthetic
SQL construction; it executes no SQL and imports no database/application packages.
Positive guards reject subprocess/Docker boundaries, sockets, database/application
imports, environment-file reads and filesystem writes. Sentinel audit events do
not actually read .env or create processes/sockets/files. Default/help, fresh
guarded imports, digest/CLI refusals, mount/cgroup settings, exact grants/probes,
bounded stream/deadline handling, creation uncertainty, ownership and cleanup
decisions have new offline evidence only.

### Independent review and execution gates

Next step is coordinator assessment and independent Astra review of this exact
three-file candidate. Focus on transaction/probe semantics under the exact column
grants, migration composition, actual overlap witnesses, conservative commit
classification, bounded streaming/timeouts, creation reconciliation and cleanup
ownership/evidence failure paths. No independent PASS is asserted here.

Execution stays NO-GO without separate authorization naming reviewed candidate
digest, exact local Docker context/endpoint and image digest/download decision,
new container/network/database/role/extension/migration/host resources, synthetic
writes/backend termination and exact bounds/owned cleanup. No Docker availability,
installed image, cgroup enforcement, mount compatibility, Windows process kill,
hard watchdog or actual PostgreSQL success has been checked. First-run acceptance
is conditional on observed evidence and final confirmed cleanup.

Provider/HTTP integration also needs real provider/key delivery/rotation/logout,
runtime role/deployment composition, HTTP delivery/cancellation/ownership tests
and its own authorization. Financial admission/source custody/SEC/Reader/native
browser gates remain separate. No next phase starts automatically.

## Completion criteria

Exactly three authored files; new offline checks and syntax/scope checks pass;
protected files/HEAD/index preserved. All real scenarios are encoded without
placeholder passes/skips, and clearly marked NOT RUN. Execution needs separate
authorization of exact candidate, local context/endpoint, image/download,
synthetic writes/backend termination, bounds and owned-resource cleanup.

## Initial candidate outcome (historical)

Candidate authored within the three-path whitelist. Final offline/syntax/scope/
preservation checks pass. New guarded suite: 44 tests, no failures/errors/skips.
Positive guard controls: 7 blocked operational imports, 2 process boundary
events, 1 socket event, 1 environment-file event and 1 filesystem-write event.
These are intentional synthetic sentinel controls, not actual I/O attempts.

Static verification uses existing Python -I -S -B with ast.parse and compile in
memory for the two Python sources, and UTF-8/trailing-whitespace/single-final-
newline checks for all three files. Scoped git diff --check passes; because the
candidate paths are untracked, the explicit byte/whitespace checks cover their
content. Final git status is exactly the three candidate additions plus the
three original protected exceptions; HEAD/branch/index and protected hashes are
unchanged. No Git line-ending configuration was changed. Final per-file hashes,
length-framed combined candidate digest and addition-only statistics are returned
in the handoff; no self-referential plan digest is embedded here.

No Docker executable, DB driver/application import, SQL, migration, external
service, provider or SEC request ran. No .env file was opened/hashed; no package
installed. All 28 future real PostgreSQL scenarios remain NOT RUN. Independent
review and operational execution remain pending, with no implementation scope
deviation, production-framework expansion or next-phase activation. Review
readiness is not operational readiness; no PostgreSQL/native PASS is claimed.

Suggested eventual commit, only if separately authorized:
test(research): add opt-in isolated PostgreSQL ownership acceptance harness

## FIX1 — independent review corrections (2026-10-30)

Astra independently returned FAIL for aggregate
47c42444e7e58d76b8f637fc5b0d55ff743947a1049c698c6d07dc79d2bb1ee3
(initial +2304/-0 candidate). The historical 44-check PASS above is offline
launcher evidence, not independent acceptance. Three guarded probes reproduced:

1. P1: authentication refusals were asserted as OwnershipFailure even though
   the committed verifier raises AuthFailure before the transaction handler.
2. P1: commit-dispatch termination received a SQLAlchemy connection proxy;
   its dictionary .info caused AttributeError before any termination query.
   Conservative indeterminate state and zero rows could then falsely pass.
3. P2: reader-thread exceptions did not reach process supervision; zero exit
   could be returned as successful output despite incomplete capture.

Pre-fix three candidate digests, aggregate, main/HEAD, empty index, exact six
status entries and protected hashes matched the coordinator baseline. Original
candidate sources are retained in tool memory only for fix-only diff statistics;
no backup files are created.

### Bounded corrections

- Authentication has a separate auth_denied helper catching only the exact
  AuthFailure contract/reason and checking unchanged checkout count for each
  refusal. Ownership/transaction failure assertions remain separate. Unrelated
  exceptions, wrong reasons, checkout or missing refusal fail the check.
- Dispatch explicitly unwraps the SQLAlchemy proxy's driver_connection while
  preserving the original proxy argument to the dialect commit. The pre-commit
  session path also obtains that driver explicitly. terminate validates actual
  psycopg driver/PID and the database, service role, application and backend-start
  identity. Its exact-selector pg_terminate_backend(pid,500) must return true;
  the same PID/start must then be absent. A witness is returned only afterward.
- Both termination scenarios require that positive witness, the matching driver's
  observed psycopg OperationalError (57P01/connection-class SQLSTATE or no state),
  invalidation/closed connection, unchanged conservative service outcome and
  durable-zero-row/reconciliation checks. Commit errors are observed around the
  real dialect call; pre-commit query errors are observed at do_execute with the
  cursor's exact driver identity. Missing witness or unrelated Python/driver
  failures cannot pass solely because the service reports indeterminate.
- Readers signal failures to supervision with one fixed-size Event; each stream
  has its own verified EOF Event. Both the running-child loop and post-join path
  reject reader failure, including zero-exit children; incomplete EOF also fails.
  Raw reader diagnostics are not retained. Existing caps, deadlines, bounded
  kill/join behavior and uncertain CommandFailure propagation are preserved.
  Creation stays pending until positively reconciled; cleanup capture failure
  remains unverified and never triggers retries or wider cleanup.

### New offline regression coverage

Fourteen new tests (45–58) extend the existing 44 without running completed groups:

- Both authentication refusals, exact type/reason, no checkout, unrelated/ownership
  exceptions, success-without-refusal and checkout-before-refusal negatives. The
  exception classes are compiled directly from their committed class AST nodes;
  no application/JWT import or old authentication module/test runs. Synthetic
  verifier/service inputs exercise this acceptance logic, not signature validity.
- Realistic proxy.info dictionary / driver.info.backend_pid shapes exercise both
  termination callers. Synthetic observation adapters cover completed witness,
  pre-query AttributeError, missing/false/empty termination evidence, backend still
  present, wrong target, wrong driver error/state, wrong witness and missing closed
  invalidation. No adapter executes SQL or connects to a database.
- Stdout/stderr read OSError before/after partial bytes, running and zero-exit
  children, verified EOF control and non-EOF invalid read. Creation capture failure
  goes through BoundedProcess -> Run.create -> reconciliation/owned cleanup; empty
  lookup cannot establish absence. Removal capture failure stays unverified and
  blocks network teardown without retry.
- Three focused bad-behavior controls remain in memory only: ownership-only auth
  refusal handling, proxy-as-driver plus the former missing-witness acceptance,
  and ignored reader/EOF failure. The new checks reject their respective bad
  behavior. There are no mutant/backup files or general mutation framework.

### Actual checks and remaining gates

Working directory: D:/Projects/finlens-foundation. Command actually run:

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/acceptance_research_ownership_postgres.py --offline

First FIX1 run: 58 tests passed, zero failures/errors/skips (0.200 seconds).
After adding partial-byte capture variants, the same suite passed at closure:
58 tests, zero failures/errors/skips (0.207 seconds). No FIX1 run failed.
Positive guards remain enabled for processes, sockets, operational imports,
environment-file reads and filesystem writes. Prior 44-pass and fixture-failure
history above is preserved; the independent FAIL has not been superseded.

Closure in-memory AST/compile, UTF-8/whitespace/EOF and scoped diff checks passed.
An oversized static-statistics command was rejected before process creation by
Windows error 206; the same read-only check uses bounded Python stdin instead
of putting the in-memory baseline archive on the command line. No backup file
or operational command is needed for that handoff.
Final preservation/scope checks confirm main at the original expected HEAD,
empty index, exactly the three candidate files plus the three protected entries,
and matching protected hashes. Final counts/statistics/digests
are returned without embedding a self-referential plan digest.

All 28 PostgreSQL scenarios remain NOT RUN. Actual committed-but-lost transport
acknowledgement, Windows watchdog/enforcement, Docker/image compatibility, SQL
and real termination are untested. No Docker executable, DB/app package import,
connection, SQL, service, provider request, installation or Git write occurred.
No .env was opened/hashed. Only the three whitelisted candidate files changed.

Local correction completion means readiness for focused independent re-review,
not acceptance: Git Step 1 and operational execution remain NO-GO. Stop for the
coordinator and Astra; no next phase starts automatically.
