# One-company SEC Live Canary

Status: active — scoped publication blocked; source-gate fix awaits independent review.
Roadmap phase: Data Freshness rollout, not a new feature milestone.

## Objective

Validate one bounded real refresh using existing contracts, without making a
catalog-wide freshness claim. Establish source identity, publication safety,
no-op behavior, resource measurements and independent acceptance before wider
rollout. Planning does not authorize network acquisition, writes or scheduling.

## Current architecture and context

Follow [Data Freshness](../../data-freshness.md) and [SEC source policy](../../data-sources.md).
Implementation: `backend/scripts/refresh_data.py`, `backend/app/refresh_service.py`,
`refresh_contracts.py`, `sec_client.py`, financial merge and filing staging services.
The accepted development baseline is Alembic `f94c6f41e0cb`, 35 companies,
58,881 facts, 3,175 chunks/vectors, 35 publications/states, zero attempts,
version zero and unknown freshness. Use the external independent acceptance
directory linked in Data Freshness for exact identities and four hashes.
Starting HEAD: `4f799a4`; existing `frontend/next-env.d.ts` churn is unrelated.
These are historical accepted results; execution must obtain fresh baselines.

## Constraints and non-goals

- Exactly one catalog issuer, AAPL, through existing supported CLI; no manual
  inserts, financial-selector changes, re-embedding of valid existing evidence,
  OpenAI calls, service restarts, Docker changes or scheduler activation.
- Confirm current AAPL catalog CIK, stored accessions, manifests and financial
  provenance read-only before use. Choose AAPL because its dense, independently
  checked stored data supports preservation and Research audits. Stop for an
  identity discrepancy; do not substitute another issuer automatically.
- Separate authorization must cover SEC discovery/Company Facts, a fresh backup
  and bounded live publication, resource budgets and an explicit no-op follow-up.
  No disposable restore or destructive recovery is implied.
- Keep API available for consistency checks; prevent unmanaged writers and other
  supported acquisition jobs. Coordinator admission serializes supported jobs;
  it is not protection against arbitrary SQL. Scheduler stays disabled.
- Reject unresolved running/indeterminate attempts before starting. Recovery can
  mark abandoned attempts interrupted; do not allow an unnoticed unrelated run
  to expand this canary's scope.

## Implementation stages and execution gates

### 1. Fresh preflight and backup (not executed)

Verify Git/worktree, approved executable and Docker/cluster/database identities,
collation, revision/schema, valid indexes, disk gates and scheduler state using
the accepted operator checks. Capture row-ID inventories and full original-row
and vector fingerprints, current API versions and metadata for all 35 companies.
Validate the private `SEC_CONTACT_EMAIL` without printing it. Review current SEC
fair-access policy only in the separately authorized network phase; this plan
did not contact SEC to revalidate policy.

The encoder lazily loads `all-MiniLM-L6-v2`; first use can otherwise download a
model. Require an already verified local cache and successful offline load in
the execution environment, with `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`. Stop if the cache is incomplete; downloading a model
requires separately agreed scope. Existing vectors are 384 dimensional.

Take a fresh operator-managed verified dump before publication, record its
SHA256/inventory/decode acknowledgment outside Git, and enforce existing host
and Docker disk-space gates. The accepted pre-migration dump is retained for
inspection but is not a substitute for this current metadata-aware backup.

### 2. Authorized discovery-only run

Use a new timestamped external evidence directory and unique report filenames.
The existing CLI permits JSON reports only inside `backend/reports`; retain its
original checkpoint there and copy it to external evidence after inspection.
Never commit live operator reports or overwrite another run's checkpoint.
The following are proposed commands, not commands executed by this plan:

```powershell
Set-Location D:\Projects\finlens-foundation\backend
# Set $canaryEvidence to the newly created, authorized external evidence directory.
$canaryPython = 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe'
$canaryStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$canaryDiscovery = Join-Path $PWD "reports/canary-$canaryStamp-discovery.json"
$canaryPublication = Join-Path $PWD "reports/canary-$canaryStamp-publication.json"
& $canaryPython -m scripts.refresh_data --ticker AAPL --stream both --dry-run --allow-network --max-filings 1 --max-seconds 300 --max-run-seconds 600 --report $canaryDiscovery
if ($LASTEXITCODE -ne 0) { throw 'Discovery failed; stop before publication.' }
Copy-Item -LiteralPath $canaryDiscovery -Destination $canaryEvidence -ErrorAction Stop
```

Dry-run still fetches full Company Facts and recent submissions, but writes no
operational/data rows and performs no raw-filing/embedding staging. Review
would-insert counts, candidate filing identities and discovery completeness;
`no_change` in dry-run does not certify freshness or complete inventory.
Stop if source identity, economic/fiscal provenance or resource scope is unclear.

SEC client uses validated identification, sequential >=250 ms request spacing,
60-second HTTP timeout, at most three attempts and bounded backoff/Retry-After.
It restricts HTTPS SEC hosts/path families and disables redirects. Each decoded
response is capped at 64 MiB; this is neither an aggregate nor peak-memory cap.
Recent submissions choose latest 10-Q, latest 10-K and recent amendments; there
is no unlimited historical archive crawl in this refresh path.

### 3. Authorized bounded publication

Recheck identities, backup, disk/resource gates, admission and baseline before
write. Inspect discovery scope: a one-filing cap does not bound full Company
Facts merge size. The narrow AAPL authorization requires the
[opt-in source gate](../../data-freshness.md#exact-aapl-publication-scope): both
fresh metadata sources must be validated before the first persistent write,
with zero new facts and only the exact authorized 10-K missing. The command
must retain that same validated source snapshot; an earlier dry-run is insufficient.
The offline fix requires independent Astra review before live execution.

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
& $canaryPython -B -m scripts.refresh_data --ticker AAPL --stream both --publication-scope aapl-10k-2025 --allow-network --max-filings 1 --max-seconds 300 --max-run-seconds 600 --report $canaryPublication
if ($LASTEXITCODE -ne 0) { throw 'Refresh non-success/pending: inspect report and durable ledger; do not retry.' }
Copy-Item -LiteralPath $canaryPublication -Destination $canaryEvidence -ErrorAction Stop
```

Capture stdout/stderr, native exit code, run UUID, committed ledger and report
checkpoints. A pending backlog legitimately exits nonzero; inspect it, do not
mislabel it failure-free/current or automatically drain remaining filings.

Facts deduplicate exact company/concept/unit/period/accession/filed/form source
identities and append revisions; conflicting observations fail before publication.
Evidence deduplicates company/accession manifests; existing complete stored data
may be reused. Missing raw filings are parsed, cleaned, chunked and locally
embedded; publication validates a complete chunk/vector set before exposing it.
One evidence transaction publishes the bounded staged set, not half a filing.

Facts and evidence are separate transactions, not one atomic company refresh.
A changed stream increments company data version once and records that stream's
publication version. Both streams changing can increment twice. Successful no-op
checks change timestamps/attempt metadata, not data versions. Missing scope or
capped backlog remains pending; no new SEC filing alone is not sufficient for
no-op if facts changed or a missing latest 10-K/amendment remains to publish.

### 4. Preservation, consistency and independent acceptance

Compare frozen original row IDs and their exact row/vector hashes, not whole-table
hash equality after authorized append. Original rows must remain byte-equivalent;
all 34 untargeted issuers' data and versions must remain unchanged. Record new
whole-table counts/hashes separately, reconcile every added fact/chunk/vector and
manifest with the committed ledger, and audit exact accession/official SEC links.

Read local freshness/catalog/financial summary/history/Research and stored evidence
endpoints. Audit AAPL financial values, periods, revenue basis and provenance
against selected source rows; a newly selected legitimate revision may change a
Research answer without altering an original row. Validate version headers,
expected-version HTTP 409, API repeatable-read consistency and frontend version
invalidation without automatic AI. Confirm no unpublished/partial filing appears.

If authorized and the discovery scope is complete, perform one separately
budgeted follow-up refresh with a new report filename to prove no-op: zero inserted
facts/chunks/vectors, unchanged versions, updated check metadata, no duplicates.
If scope remains pending, record incomplete canary and seek a bounded follow-up;
do not claim no-op acceptance from a capped partial run.

Measure total/stream elapsed time, process peak working set/CPU, encoder duration,
disk/WAL growth and acquisition volume where existing evidence exposes it. Reports
do not promise complete HTTP byte/request or peak-memory instrumentation; record
measurement gaps honestly. The 300/600-second budgets are cooperative: synchronous
HTTP/parser/encoder calls may overrun, with checks before publication. Operator
resource ceilings and stop/recovery handling must be agreed before execution;
these flags are not hard termination guarantees. OpenAI request count must be zero.

Independent review must accept identities, committed outcomes, preservation,
source provenance, no-op/pending semantics, measured costs and usable API/UI.

## Failure, recovery and rollback limits

Stop on failed gates, lock loss, checkpoint failure or uncertain commit. Earlier
facts may remain committed when evidence fails; ordinary stream failure does not
imply the entire run rolled back. Do not blindly repeat either stream.
Use a fresh read-only connection and `--show-run <run-uuid>` to inspect durable
attempts. Indeterminate committed counts are null, never asserted zero. The failed
admission owner is discarded; do not bypass it with another writer/session.
Confirmed pre-publication rollback preserves prior published data. After commit,
recovery is forward-only and requires reviewed corrective publication. No decrement
of versions, deletion of originals, downgrade or restore is authorized here.
Logical backup is not PITR or cluster-role recovery; any restore has explicit
authorization, target-identity and downtime requirements.

## Decisions and discovered issues

- 2026-10-09: AAPL first; both streams, at most one newly staged filing. Broader
  catalog acquisition and automatic backlog draining are excluded.
- Unknown legacy freshness is correct; deployment acceptance is not live freshness.
- Historical AAPL Research HTTP 500 is currently not reproducible. No causal
  attribution or code fix is warranted; see the recorded incident in Data Freshness.
- 2026-10-10: Publication stopped before launch (zero refresh/SEC/write operations):
  the unrestricted CLI could merge facts before evidence discovery, and count caps
  could not pin the target. The [bounded offline gate fix](../completed/2026-10-10-canary-source-authorization.md)
  adds a named source authorization profile. No live publication or no-op follow-up
  is claimed; accepted backup/monitoring evidence remains outside Git.

## Progress, validation and completion criteria

- [x] Offline code/contracts and accepted deployment evidence inspected; plan drafted.
- [ ] Separate acquisition/backup/publication/resource/no-op authorization obtained.
- [ ] Fresh preflight/cache/contact/disk gates and verified backup pass.
- [ ] Discovery scope reviewed; bounded publication outcome independently reconciled.
- [ ] Original-row preservation, versions, source audits and API/UI checks pass.
- [ ] No-op or honest pending boundary demonstrated; resource gaps resolved.
- [ ] Independent acceptance recorded; plan moved to completed only for this scope.

Actual checks this planning round: documentation references and whitespace only;
no live tests, acquisition, model loading or database writes. Existing offline
failure regressions remain evidence, not live failure-injection acceptance.

## Scheduler prerequisites and final outcome

Pending execution. A successful one-company canary alone cannot authorize all
35 companies. First approve and accept bounded wider rollout/coverage, resource
budgets and recovery behavior; then separately authorize the task account,
credentials, cadence, no-overlap policy and monitoring. The existing opt-in wrapper
defaults to catalog-wide scope and requires both its enable flag and environment
opt-in. Do not invoke/register/enable it during this canary. Keep scheduling disabled.
