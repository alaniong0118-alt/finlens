# Start an existing prepared local demo

This is a development-only, existing-data procedure. REL-01A tests scripts offline;
real startup, DB reads, encoder use and browser acceptance require separate operator
authorization. Public/private deployment is not approved. DEP-01A3 is **BLOCKED**.

## Prerequisites and startup

Use the intended checkout, prepared backend venv/frontend node_modules, installed
Node.js, private backend configuration and existing dataset. PostgreSQL/pgvector
must already be running and reachable through DATABASE_URL. Do not print private
settings. OpenAI is optional. First-time provisioning is the separately authorized
README Quick Start: installation, migration, seed, acquisition and model preparation
are not routine startup or repairs for this database.

After authorization, from the repository root in Windows PowerShell:

```powershell
.\Start-FinLens.ps1 -NoBrowser
```

No Docker operation, installation, migration, seed, refresh, index, provider request
or encoder warmup is invoked. Occupied application ports are refused, even for
plausible FinLens servers. Stop your previous demo from its original terminals;
never kill an unknown listener to free a port.

Defaults: frontend `http://127.0.0.1:3000`, backend `http://127.0.0.1:8000`.
For unused alternate ports pass `-BackendPort 8021 -FrontendPort 3003`. The frontend
receives the exact backend URL only in its child process, overriding its normal
file setting without editing it. Backend child HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE
flags prevent normal Hub downloads; frontend child telemetry is disabled. Parent
and persistent environment settings stay intact.

Development profile is required. Each service starts in its own interactive
terminal, retained as a Ctrl+C shutdown control. Backend readiness precedes
frontend startup. Default budget: 60 seconds per stage; -ReadinessTimeoutSeconds
accepts 5-180. A stage may overrun by the remaining bounded probe calls, each with
a two-second HTTP timeout. No redirects, unbounded retries or raw diagnostics.

## Readiness and identity

Success requires:

- Requested-port listeners bound to `127.0.0.1`, with PID ancestry and creation
  times tracing to the newly launched terminals.
- Direct `/healthz`: `status: ok`, `service: finlens-api`; `/capabilities`: Research
  Mode and development profile; `/dbz`: PostgreSQL connectivity.
- Frontend HTML with the existing FinLens title, and the same safe checks through
  `/api/finlens` on the requested frontend port.

`/dbz` performs a read-only query in a later authorized startup. These existing
markers are operational checks, not cryptographic authentication, source/build
attestation or hostile-local-process isolation. Refusing pre-existing listeners,
checking launched ancestry and fixing the child proxy target establishes ordinary
local pairing without a new production protocol. This is not deployment proof.

The ready message does not certify financial coverage, publication availability,
first-search latency, encoder usability or end-to-end acceptance. Accept the chosen
demonstration scenarios separately.

## Failure and shutdown

On configuration, ownership, identity or readiness failure, startup fails and does
not open the browser. Inspect named terminals privately. No process is automatically
terminated, including terminals started before failure. Press Ctrl+C in each
original FinLens service terminal, then close it. PostgreSQL is left untouched.

`Stop-FinLens.ps1` deliberately refuses automated termination, including its legacy
-StopDatabase switch. Port/command-name guessing was insufficient ownership proof.
To stop PostgreSQL, obtain authorization and run `docker compose stop postgres`
from the intended project. Preserve volumes; never reset data as a startup repair.

For occupied ports, inspect ownership without printing command lines/secrets; stop
only a service you control or choose unused ports. For DB failure, check the intended
service and private configuration without migrations/bootstrap. For proxy failure,
check terminal output and requested ports; do not substitute an unverified backend.

If evidence search/encoder is unavailable, retain supported snapshots, histories
and direct answers. Explain the limitation; do not invent passages, install/download
models or weaken evidence eligibility. Offline flags are not DEP-01A3 model-trust
or containment acceptance. Cache diagnosis requires separate authorization;
startup neither inspects model artifacts nor loads an encoder.

## Operational commands and AMD

The 36-company demo prohibits `refresh_data --all`, any CLI bootstrap, unselected
`index_catalog` and unselected `sync_financial_facts`, including dry runs. CLI
guards reject these unconditionally before operational work without reading the
catalog. No implicit batching, truncation or raised budget; RefreshRequest still
permits at most 35 tickers. Internal service contracts remain unchanged; CLI guards
are not a sandbox against trusted Python callers. Do not evade operator restrictions.

Explicit issuer selections still require separate acquisition/write approval.
Example wrapper syntax for a separately approved operation:

```powershell
# Only after separate authorization and the existing process opt-in:
.\Refresh-FinLens.ps1 -Ticker AAPL -EnableLiveRefresh
```

The wrapper also requires FINLENS_REFRESH_ENABLED=1 in that process. It never sets
the variable, offers bootstrap or enables scheduling. Old unselected shortcuts now
fail. Do not enable scheduling or include AMD without separate approval.

AMD is catalog-only: no facts, evidence, publication or verified freshness. Its pin
stays null; research may wait for verification. Do not present it as zero-valued,
Ready or a supported demo scenario. Use financially supported companies and retain
their unavailable metrics and actual periods.
