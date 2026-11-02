# Dormant canonical AAPL facts assessment

Status: active — native read-only assessment complete; closeout documentation awaiting review
Roadmap phase: bounded freshness assessment preparation

## Objective

Provide an explicit operator-only AAPL Company Facts dry-run using the existing
refresh/conflict/merge path, supervised independently of its cooperative budgets.
It must not publish facts or freshness metadata. This is not filing discovery.

## Current architecture and context

Baseline: `acfb665c9473f0a90e46e2388214ebaeb0df61b8`, initially empty index.
Preserve the modified `frontend/next-env.d.ts`, two untracked historical backend
reports, annual Markdown export plan, and completed personal-site plan. Existing
refresh CLI, release policy, native launchers and BLOCKED runtime gate stay intact.
`refresh_service.refresh` already excludes recovery and publication in dry-run.
Its coordinator requires the actual sessionmaker's bound engine for its advisory
lock; replacing that factory with a generic context wrapper would lose the lock.

## Constraints and non-goals

Only five new files: dedicated PowerShell supervisor, Python worker, two focused
offline test files and this plan. No live SEC/DB/model/browser/services, private
configuration reads, installation, permission changes, Git writes or drive cleanup
during development. Future normal configuration loading and contact transmission
require separate approval. No formulas, admission path or shared refresh changes.

## Implementation stages

1. Add inert worker with explicit process development admission, fixed AAPL/CIK,
   dedicated loopback read-only engine and canonical dry-run delegation.
2. Add exclusive bounded receipt and incremental output/deadline supervision.
3. Exercise synthetic configuration, fake DB/service paths and harmless short
   local child processes; freeze bytes for independent review.

## Decisions

- Reuse `http_engine_options` validation without changing HTTP configuration.
  Add read-only startup options only to the dedicated engine, verify each
  transaction, and preserve the coordinator's actual bound factory.
- Keep explicit `development` provenance; never force a different profile.
- Supported entry is the supervisor. Its 600-second deadline is independent of
  cooperative refresh/HTTP limits; termination is of its own process handle only.
- No-DB Company Facts probing cannot identify differences from admitted DB facts,
  so it is not a second implementation or substitute for canonical diff.

## Resource and lifecycle guarantees

Implemented: connect 5 seconds, statement 30 seconds, lock 5 seconds; 300-second
cooperative stream budget inside a 600-second externally supervised worker.
SEC client's existing three-attempt/64 MiB decoded-response bound is unchanged.
Output drains are incremental and byte bounded, with a sanitized create-only
receipt of at most 64 KiB. No raw stdout/stderr or private diagnostics are retained.
Only the created worker handle may be terminated, with exit verification.

There is no OS egress sandbox, arbitrary-descendant containment, native peak-RAM
guarantee or aggregate DB result-byte cap. Cooperative limits are not hard wall
deadlines. PostgreSQL read-only mode permits session advisory locks and ending
their transactions, but persistent row DML is prohibited. Offline fakes cannot
certify native PostgreSQL enforcement. A future approved live check is separate.

## Discovered issues

The broader existing CLI/HTTP regression run stopped at one unrelated route-matrix
assertion after 252 passes: the filing-tone route returned 422 instead of the
expected simulated DB-busy 503. The matrix leaves `{chunk_id}` unresolved, supplies
`q=revenue` and no publication pin. The existing tone handler rejects missing pins
or any query before DB access (`main.py`, `get_filing_chunk_tone`). No shared file
was changed and this failed suite is not claimed green. The independent reviewer
later reproduced the failure with candidate imports forbidden, establishing it on
the baseline; a valid tone request reached the mocked DB and returned 503. Those
are reviewer results, not a rerun by this worker. Fixing that matrix is outside
this candidate.

Independent review also found a P2 in the candidate's env-only proxy check:
HTTPX can fall back to Windows/macOS platform proxies through public
`urllib.request.getproxies()`. The worker now checks that same public discovery
path before contact/source access, rejects HTTP(S)/ALL proxies conservatively
even when NO_PROXY could bypass them, and rejects malformed/failed discovery
without private diagnostics. It never clears proxy settings or forces a route.
All offline discovery is mocked: no actual registry/configuration lookup ran.
This is a point-in-time check repeated before the source call, not OS containment
or an atomic guarantee against concurrent platform configuration changes.

## Progress

- [x] Read repository standards and current source; baseline has only five known
  protected exceptions.
- [x] Worker and supervisor implemented; existing runtime code remains unchanged.
- [x] Focused offline validation completed; five protected hashes unchanged.
- [ ] Independent review and later delivery gate.
- [ ] Separate live approval was not granted at the initial dormant freeze; later
  exact approvals and the one failed native attempt are recorded below. Further
  execution is stopped during the current offline repair.

## Test and validation strategy

Use the guarded backend runner with dotenv disabled, synthetic DB configuration,
physical DB/socket traps and plugin autoload disabled. Test admission, destination
and timeout constraints, transaction/read-only event hooks, coordinator lock path,
canonical service delegation and error sanitization. PowerShell checks use only
synthetic short processes outside the repository for success, deadline, output,
stderr and cleanup behavior; no application startup. Record exact actual commands
and outcomes below after running. Preserve all fixtures/evidence; no bulk deletion.

Actual verification on 2026-11-02:

- Backend cwd `D:\Projects\finlens-foundation\backend`; process-only
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:
  `.\.venv\Scripts\python.exe -I -B tests/run_dep01a2_increment2_offline.py tests/test_aapl_facts_assessment.py --maxfail=1`
  — **49 passed**, four existing SQLAlchemy UTC-default deprecation warnings.
  The initial version also passed 49; the final run additionally trapped DNS and
  private dotenv reads and used specific rejection exception classes.
- Repository cwd; installed Codex PowerShell 7.6.5 executable:
  `C:\Users\IITSt\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe`
  with `-NoLogo -NoProfile -NonInteractive -File backend/tests/test_aapl_facts_assessment.ps1`
  — **25 passed, 0 failed**. Sleeping/oversized-output children were terminated
  through owned handles with verified exit. Cleanup-failure reporting was mocked;
  a real OS termination failure was not induced. Synthetic fixtures retained at
  `D:\Projects\finlens-aapl-assessment-offline-05bdef320e1c44a4b7912063b5cc1349`.
- Same guarded Python command selecting `tests/test_rel01a_cli.py tests/test_http_database_runtime.py --maxfail=1`
  — **252 passed, 1 failed**, remaining cases not run; see the precise route-matrix
  failure above. This was not a live HTTP/DB request; TestClient and fake sessions
  were used. No unrelated repair or further broad test rerun was undertaken.
- Proxy P2 repair: the focused guarded command with
  `tests/test_aapl_facts_assessment.py -k proxy --maxfail=1` passed **16 tests**
  (46 deselected). It mocks public platform discovery and the installed HTTPX
  proxy-map compatibility probe; no client transport or actual registry lookup.
  Direct/no-proxy controls, malformed results and discovery exceptions are covered.
  The full focused file then passed **62 tests**, four existing UTC-default
  deprecation warnings, using the same guarded command without `-k proxy`.
  The unchanged PowerShell suite was not rerun; its 25-pass result remains scoped
  to its unchanged bytes. Initial independent review also reproduced 49/25 passes.
- Existing tracked diff whitespace check passed. All five new files also passed
  `git -c core.autocrlf=false diff --no-index --check -- NUL <path>` with no
  diagnostics (exit 1 indicates the added-file diff, not a whitespace error).
  Ordinary `git diff --check` alone excludes untracked files. No staging or
  commit has occurred.

## Future operator contract (not executed or authorized here)

The supported entry is modern PowerShell executing
`Assess-FinLens-AaplFacts.ps1 -AllowNetwork -ReceiptPath <new-absolute-json-path>`.
The parent process must already explicitly have the approved development profile;
the script never sets that profile. The receipt parent directory must exist and
have no reparse-point ancestors; an existing receipt is never replaced. A refused,
timed-out or invalid worker retains a sanitized FAILED receipt. Failed preflight
before receipt reservation launches nothing. No automatic worker retry occurs.

Future approval must cover normal private configuration loading, existing local
PostgreSQL read-only access, transmission of the configured SEC contact, and the
single fixed `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json`
source (up to three existing client attempts). Nonempty proxy variables or
platform-discovered HTTP(S)/ALL proxies cause refusal; malformed/failed discovery
also refuses. This does not remove settings or select alternate routing. None of
these live actions ran here.
Receipt contents are counts, unchanged publication version, outcome and owned
worker identity/timing; source bodies and private exceptions are not retained.

## Completion criteria

Five-file scope, no shared runtime changes, focused checks pass, protected files
unchanged and independent review closes findings. Live acquisition remains dormant.

## Subsequent approved run and offline diagnostic repair

The initial five-file dormant implementation was reviewed and delivered in
`f384d58bbf6d70576e30e29323e83505c9eb0c18`. This repair starts there, with the
same five protected exceptions and initially empty index; no shared refresh,
database, SEC client, admission policy or runtime launcher changes are included.

After separate explicit approval for local reads/SEC contact and a process-only
development context, one native attempt ran. Its worker exited 1 after 827 ms;
the supervisor exited 1 after 1,339 ms. The 354-byte receipt retained only
`WORKER_REFUSED`, with null result. It did not establish the refusal stage,
native read-only readiness, actual SEC HTTP attempts, would-insert or conflicts.
Do not infer historical HTTP count or refusal cause from elapsed time.

Evidence remains outside the repository at
`D:\Projects\finlens-aapl-facts-approved-dc32149bd9814afa901fb4423a075885`.
The receipt SHA-256 is
`99D33A6FB49615919B94C38537CCCB8FCABD3AD901443AF0553A6A78D4CF4207`.
Both owned PIDs were absent; the existing PG container and listener creation
identity matched. A false listener mismatch caused by JSON `System.DateTime`
versus formatted-string comparison remains in the original evidence, alongside
`cleanup-reconciliation.json` (SHA-256
`1ADCC15E26454BCACD94A3B24BDDD8856CF6ECE36B74DF1267784E51BC4160B7`).
Neither original record is overwritten by this repair. The process-only profile
did not persist, and no publication/freshness result is claimed.

Root cause: the worker already emitted an allowlisted BLOCKED JSON code, but
the supervisor discarded stdout for every nonzero exit before validating it.
The narrow repair adds protocol version 1: fixed scope, status, safe code,
last confirmed stage, null `sec_http_attempts`, and a validated result or null.
The worker tracks only completed boundaries, with a context reset per invocation;
the first local safe refusal survives canonical refresh's exception-to-result
conversion. A source admission is not proof of a sent HTTP request; source return
means parsed payload returned, not completed financial admission. No HTTP client
instrumentation was added, so all reported request counts remain unknown/null.

The supervisor incrementally bounds both pipes as before, validates even exit-1
stdout, and persists only the validated fields. Exit code/status/stage/code must
agree. Invalid UTF-8/JSON, unknown/duplicate fields, excess size/depth, contradictory
stages and any non-null uninstrumented HTTP count fail closed. Raw stderr and
exception/config/contact text are never copied. The 600-second worker deadline,
16 KiB per-pipe bound, 64 KiB exclusive receipt, SQL guards and cleanup semantics
are unchanged. Invalid/missing protocol leaves stage and request count unknown.
Worker and wrapper must be delivered together; an old/new protocol mismatch is
rejected rather than interpreted as a successful assessment.

Current offline checks (no native acquisition, config/registry reads or DB):

- Same guarded Python command documented above, selecting
  `tests/test_aapl_facts_assessment.py --maxfail=2`: **79 passed**, four existing
  UTC-default deprecation warnings. Coverage includes every safe refusal category,
  context reset, swallowed guard refusal, source-call failure, and unknown counts.
- Same installed PowerShell command for
  `backend/tests/test_aapl_facts_assessment.ps1`: **60 passed, 0 failed**. Only
  short synthetic local children and mocks ran; positive and negative protocol,
  nonzero exit, missing/oversized/malformed JSON, duplicate keys, stage/count
  contradictions, deadline/output and sanitized failed-receipt behavior passed.
  Fixtures retained at
  `D:\Projects\finlens-aapl-assessment-offline-35c821e399a94cedae99861206682781`.
- External future-cleanup helper/test only, at
  `D:\Projects\finlens-aapl-protocol-review-0aa92b10480b41819a6a3527ad1fd099`,
  normalizes explicit-offset strings, JSON DateTime and DateTimeOffset to UTC ticks.
  Unspecified timestamps and malformed/overflow dates are rejected. Running the
  same installed PowerShell with `-File <that directory>\test-owned-utc-identity.ps1`
  passed **13 synthetic checks**, without looking up any process or native state.

Next gate is independent review of this five-file repair and the two external
UTC helper/test files. No further assessment ran, no actual platform proxy lookup
was performed, and no source/Git delivery or activation is authorized by this
offline repair record. Existing historical refusals remain untouched.

## Final outcome

Initial dormant delivery passed independent P2 closure with 62 Python and 25
PowerShell checks. The current diagnostic repair has 79 Python, 60 PowerShell
and 13 external synthetic UTC checks passing; its independent review is pending.
The broader legacy regression failure and independent baseline evidence remain
preserved above. This task does not recover the missing historical refusal code.
Native PostgreSQL enforcement, actual SEC result, process termination under an OS
failure, user-interrupted supervisor recovery, and live data freshness remain
unverified. Killing the supervisor itself can leave the worker alive; the script
does not claim Job Object containment or arbitrary descendant cleanup. A timeout
does not cancel previously received SEC data remotely. No freshness/publication
metadata is updated by assessment, even if it finds new observations.

Suggested future commit:
`feat(ops): add dormant read-only AAPL facts assessment`.

## Protocol 2 connection/schema classifier (offline, pending review)

The reviewed protocol-1 candidate was tried once under subsequent exact phase
approval. Evidence is preserved at
`D:\Projects\finlens-aapl-protocol-native-702a34975c7e4f9da504368e28891aa0`.
Its worker returned `ASSESSMENT_UNVERIFIED`, last confirmed `database_configured`,
exit 1, 848 ms; supervisor exit 1, 1,360 ms. Schema/native read-only readiness was
not confirmed, coordinator/source acquisition were not reached, and instrumented
HTTP count remained null. Both owned processes exited; original PG identities,
candidate/protected hashes and parent environment were preserved. The final receipt
SHA-256 is `DCB5583E24A9C6A7B9A7A874D6D1020DC355B38B47109F6962D7A94F7EDD7EFB`.
This does not identify the earlier or current underlying native exception.

Read-only offline probes found no connect-argument/API incompatibility: installed
SQLAlchemy 2.1.2, psycopg 3.3.6 and libpq 18.4 accepted synthetic options; actual
SQLAlchemy `do_connect` dispatch reached the intercepted connector. Real
SQLAlchemy begin/session/coordinator with fake DBAPI passed three read-only begin
checks, and psycopg adapted empty immutabledict/named parameters. Real schema
checker controls accepted valid synthetic inventory and rejected missing table,
column, migration head and vector with DemoSetupError. Mock authentication and
mock missing schema both reproduced the same generic code/stage. Therefore neither
is claimed as the real cause; no admission/schema requirement was changed.

The scoped repair now emits protocol **2**, adding fixed-shaped `failure` and
`cleanup_failure` fields (category, static exception type label, allowlisted
SQLSTATE or null). Only a verified psycopg exception may supply SQLSTATE; unknown
states are suppressed. Classifiers never inspect exception strings, SQL, DSNs,
parameters or dynamic class names. Unrecognized errors remain UNCLASSIFIED/other.
Classification itself cannot replace an original exception if it fails.

The first primary diagnostic is saved before session close. Session-close failure
attempts invalidation; its first safe cleanup category is separate. Engine-dispose
failure cannot override the primary. A cleanup-only failure still refuses the
assessment. A scoped cleanup context prevents a local guard raised during cleanup
from stealing the original refusal code. This does not prove native cleanup under
OS failure. Deadline, read-only options, complete schema gate, coordinator binding,
canonical dry-run semantics, source scope and request-count unknowns are unchanged.
Worker/wrapper must be updated together; protocol-1/malformed/inconsistent fields
are rejected, and any failure or cleanup diagnostic forbids success.

Actual offline verification, using the same guarded commands documented above:

- `tests/test_aapl_facts_assessment.py --maxfail=2`: **99 passed**, four existing
  UTC-default warnings. First classifier iteration passed 97; an additional cleanup
  guard co-failure regression brought it to 98; unknown operational SQLSTATE
  classification is covered in the final 99-case file. A non-allowlisted server
  SQLSTATE is unclassified, never mislabeled as a connection failure.
- `backend/tests/test_aapl_facts_assessment.ps1`: **80 passed, 0 failed**. The first
  iteration passed 78; cleanup-guard co-failure brought it to 79, and the final run
  adds unknown operational SQLSTATE. Eight actual
  candidate-producer -> supervisor-parser synthetic fixtures cover authentication,
  schema, pool timeout, two unknown SQLSTATE types, primary plus multiple cleanup failures,
  cleanup guard and cleanup-only failure. These children use the maintained offline
  guard, fake sessions and no-op source admission, not live configuration/DB/SEC.
  Fixtures remain at
  `D:\Projects\finlens-aapl-assessment-offline-2350f88a665640d4a785c2d6a9f5a3a2`.
- Existing external UTC helper/test bytes remain unchanged; their prior 13-check
  result is not claimed as a new execution. No native workload, proxy discovery,
  private configuration, real DB/SEC, model, browser, Git delivery or settings
  change occurred in this classifier implementation task.

Freeze the same five repository files for one focused closure review. Preserve
all earlier manifests, patches and failed native evidence; historical cause/counts
remain unknown. No further native run precedes that review.

## Verified native closeout (2026-11-02)

This section supersedes the earlier pending-review/native-readiness statuses;
their failed receipts and historical unknowns remain unchanged. Protocol 2 was
independently reviewed and delivered at
`2a866d704ceb64d8281d3cfcfaad5ec20408f7e9`. The following operations had separate
user approval; none authorizes a non-dry-run refresh or account activation.

### Bounded logical backup

The exact archive `finlens-463d36230db2474c91560276473a0cd4.dump` is 9,966,019
bytes, SHA-256
`6394255352AA8E857E9A903B5FA89FC79763EADEAD61C527B05495C424ED3C34`.
Retained native evidence established seven table count/length/hash equalities,
including vector and publication data, plus extensions, revision and sequence
names. Strict schema text initially differed; the original FAILED receipt was
not rewritten. Subsequent bounded schema-only diagnostics and independent
semantic review established equivalence of exactly three CHECK array-cast versus
element-cast expressions. No global comparator or normalizer was weakened.
The append-only supplemental logical-restore receipt is SHA-256
`897C46F431279438410C457B693BD8F8D15F467DC9247226B028F154DA96CF48`.
Sequence values/is_called, owners/ACLs/global roles, PITR and full writable
recovery remain unverified. This is qualified logical evidence for this archive,
not complete recovery acceptance.

### One additive migration

After independent review and fresh prerequisites, one bounded native transaction
upgraded `f94c6f41e0cb` to `a7c730103001` in 8.632 seconds, with acknowledged
commit. The three dormant ownership tables were empty; 18 columns, 13 constraints,
7 indexes and 10 C-collated identifier columns passed checks. Six existing data
tables retained equal counts/serialized lengths/hashes; existing schema and
extensions were unchanged. Source container/volume identity, archive, historical
evidence and five protected files were preserved; owned cleanup was confirmed.
No account rows, authentication activation or permission changes were performed.
The migration result receipt is SHA-256
`465D7F2B85A61491C22F520BBEBB532FEAC5E845FDB9BD8B7799463EC3E9D87B`.

### Canonical AAPL read-only assessment

An external preflight refused before launching any assessment; its exact failing
identity field remains unknown. A DateTime/string comparison defect was
subsequently reproduced offline and repaired. The original failed receipt remains
preserved. The external
repair reused the previously reviewed UTC helper unchanged; 13 existing plus
45 identity checks passed offline and independent review. Fresh five-field
container/image/running/start/volume checks then passed before and after the run.

The committed supervisor and worker ran once, under the approved child-only
development context and existing local PostgreSQL read-only safeguards. Protocol
2 reported `WORKER_COMPLETED`, last confirmed stage `assessment_completed`, exit
0, no failure/cleanup classification and verified worker exit after 2,350 ms.
For AAPL/CIK `0000320193`, the canonical facts dry-run returned `no_change`,
`would_insert=0`, publication version `1 -> 1`, `facts_inserted=0` and
`filings_published=0`. Actual `sec_http_attempts` remains null/uninstrumented;
neither request count nor historical failure causes are inferred from timing.
Assessment receipt SHA-256:
`98DC5241BC436E149B4EF5BBF721A34827EEF0F5D75F4D2F2C99D0AF8C8D86A9`.
Post-verification receipt SHA-256:
`54A8C83BFD1C68BFFF328E2322079F57A6B737E7DF890991DAB7A7E86127C5EE`.
These sanitized receipts remain outside the repository; no contact value or raw
source/configuration body is copied here. The original PostgreSQL identity,
Git baseline, empty index and five protected exceptions were unchanged.

This closes the assessment diagnostic loop. No formal refresh, publication or
freshness-metadata update occurred. It does not establish latest filing coverage,
current freshness, full recovery, auth activation, full DEP acceptance or an
externally accessible beta. No further native operation was performed afterward.
