# Dormant canonical AAPL facts assessment

Status: active — offline candidate frozen for independent review; live use not authorized
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
- [ ] Separate approval for configuration/DB/contact/SEC acquisition; not granted.

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

## Final outcome

Five new files are frozen for P2 closure review, with 62 Python focused checks
passing and 25 PowerShell checks for unchanged supervisor/test bytes. The broader
legacy regression failure and independent baseline evidence are preserved above.
Native PostgreSQL enforcement, actual SEC result, process termination under an OS
failure, user-interrupted supervisor recovery, and live data freshness remain
unverified. Killing the supervisor itself can leave the worker alive; the script
does not claim Job Object containment or arbitrary descendant cleanup. A timeout
does not cancel previously received SEC data remotely. No freshness/publication
metadata is updated by assessment, even if it finds new observations.

Suggested future commit:
`feat(ops): add dormant read-only AAPL facts assessment`.
