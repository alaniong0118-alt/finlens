# Development collation remediation: guarded operator runbook

Status: **verification implementation tested; independent focused review and all
maintenance authorization pending**. Supersedes the chat-only audit/runbook.
See [freshness rollout](data-freshness.md), [verification record](../backend/reports/collation_operator_verification.json)
and [read-only verifier](../backend/scripts/verify_collation.py).

## Target and boundaries

This runbook is specific to HEAD `2bbadf3` plus the reviewed operator safety files,
development revision `d7b834408ba8`, cluster `7692131504986030119`, database `finlens`
OID 16384. Runtime: PostgreSQL 16.15/pgvector 0.8.7, libc en_US.utf8, recorded/runtime
2.41/2.36. The exact previous image history is unproven. Keep the existing container,
image digest and volume; the verifier pins them and the local Docker endpoint.

The strategy remains ten targeted non-concurrent B-tree rebuilds in one transaction.
No database-wide rebuild or application change is needed. The verifier cannot execute
maintenance SQL. Its `--plan` option only writes guarded SQL text for inspection.
No database creation, restore, rebuild, version refresh, migration or bootstrap was
executed while developing it. `postgres`, `template1`, and `template0` are not repaired.

## Safety gates

- Explicit exceptions replace critical assertions; optimized Python is rejected
  before database configuration is imported. Never bypass a failed gate.
- TCP and Docker system_identifier/database name/OID/role must agree, and must
  match the captured baseline. Docker context/endpoint/container ID/image ID/
  persistent mount/port binding are checked before and after each audit.
- Exact qualified index definitions, ordered attributes/collations/opclasses,
  unique/primary flags, constraint links, expressions and valid/ready/live flags
  are checked. New persisted object scope requires another review.
- Both query plans are retained: intended public-table Seq Scan without indexed
  access, and intended schema/index Index Scan without a sort fallback. Complete
  ordered key groups and duplicate groups are checked, not just counts.
- Full-row fingerprints reuse the existing metrics verification helper; the
  embedding-only SHA256 is independently checked. Original rows must not change.
- Every audit requires at least 1 GiB free on host C: and D:, Docker data and /tmp.
  This is conservative for the fixed ~38 MiB dataset / ~3.71 MiB affected indexes.
  C:/D: cover this machine's host storage; re-review storage mapping if moved.
- Reports retain OIDs and pg_relation_filenode before/after. In-place rebuilding
  must change all ten filenodes and preserve logical OIDs. A saved verified
  pre-rebuild baseline is mandatory for post-rebuild/final gates.
- Quiescent audits reject any other database session, including idle sessions.
  Stopping the API alone is not proof that source writers have stopped.

## Authorization and future commands

**Do not run the following deployment steps until independently reviewed and
explicitly authorized.** Backup files, disposable database creation/restore and
rehearsal need authorization; development REINDEX and marker refresh need explicit
development-maintenance authorization. Migration/bootstrap remain a separate task.
The approved order is backup → isolated restore → rehearsal → stop API/writers →
targeted rebuild → verification → marker refresh → final verification.

Use one PowerShell session. Suspend all ingestion/refresh/demo/manual writers before
the backup and keep them suspended. No scheduling, SEC/OpenAI or frontend build.
Commands use the existing private database configuration; never echo its URL.

```powershell
$ErrorActionPreference = 'Stop'
$repo = 'D:\Projects\finlens-foundation'
Set-Location "$repo\backend"
$python = "$repo\backend\.venv\Scripts\python.exe"
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "D:\Backups\FinLens\collation_$stamp"
$scratch = "finlens_collationcheck_$stamp"
$archive = "/tmp/finlens_collation_$stamp.dump"
New-Item -ItemType Directory -Path $backup | Out-Null

function Check-Native([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed; stop." }
}
function Invoke-ReviewedPlan([string]$ReportFile, [string]$SqlFile) {
    $snapshot = Get-Content -LiteralPath $ReportFile -Raw | ConvertFrom-Json
    # Recheck pinned runtime immediately before SQL. This probe is read-only.
    $now = & $python -B -c 'import json; from scripts.verify_collation import check_optimization,runtime_identity; check_optimization(); print(json.dumps(runtime_identity()))'
    Check-Native 'Immediate runtime identity'
    $current = $now | ConvertFrom-Json
    if (($current | ConvertTo-Json -Depth 12 -Compress) -ne
        ($snapshot.runtime | ConvertTo-Json -Depth 12 -Compress)) {
        throw 'Runtime changed after verification.'
    }
    # Generated SQL checks cluster/name/OID in this very write transaction,
    # locks the four tables, and checks all ten index OIDs/filenodes again.
    Get-Content -LiteralPath $SqlFile -Raw |
        docker --context $current.context exec -i $current.container psql `
            -X -U finlens -d $snapshot.identity.database -v ON_ERROR_STOP=1 -f -
    if ($LASTEXITCODE -ne 0) {
        throw 'Maintenance outcome may be uncertain. Keep API down; never refresh based on assumption.'
    }
}

# 1. Fresh backup. This snapshot is not maintenance authorization.
& $python -B -m scripts.verify_collation --output "$backup\before.json" | Out-Null
Check-Native 'Before audit'
$before = Get-Content "$backup\before.json" -Raw | ConvertFrom-Json
$ctx = $before.runtime.context
$cid = $before.runtime.container
docker --context $ctx exec $cid pg_dump -U finlens -d finlens `
    --format=custom "--file=$archive"
Check-Native 'Backup'
docker --context $ctx cp "${cid}:$archive" "$backup\finlens.dump"
Check-Native 'Archive copy'
$hash = (Get-FileHash "$backup\finlens.dump" -Algorithm SHA256).Hash.ToLowerInvariant()
$remoteHash = docker --context $ctx exec $cid sha256sum $archive
Check-Native 'Archive checksum'
if (($remoteHash -split '\s+')[0] -ne $hash) { throw 'Backup hash mismatch.' }
$hash | Set-Content "$backup\archive.sha256" -Encoding ASCII
docker --context $ctx exec $cid pg_restore --list $archive |
    Set-Content "$backup\archive-list.txt" -Encoding UTF8
Check-Native 'Archive inventory'
docker --context $ctx exec $cid pg_restore --file=/dev/null $archive
Check-Native 'Archive decode'

# 2. Isolated restore: template0 is copied, never altered.
& $python -B -m scripts.verify_collation --baseline "$backup\before.json" | Out-Null
Check-Native 'Target before disposable creation'
docker --context $ctx exec $cid createdb -U finlens --maintenance-db=finlens `
    -T template0 --encoding=UTF8 --locale-provider=libc `
    --lc-collate=en_US.utf8 --lc-ctype=en_US.utf8 $scratch
Check-Native 'Disposable database creation'
docker --context $ctx exec $cid pg_restore -U finlens "--dbname=$scratch" `
    --exit-on-error --no-owner --no-privileges $archive
Check-Native 'Disposable restore'
& $python -B -m scripts.verify_collation --database $scratch --phase restored `
    --baseline "$backup\before.json" --quiescent --output "$backup\restored.json" | Out-Null
Check-Native 'Restored data and index verification'

# 3. Rehearse, using fresh target guards before each write.
& $python -B -m scripts.verify_collation --database $scratch --phase restored `
    --baseline "$backup\before.json" --quiescent --output "$backup\rehearsal-start.json" `
    --plan rebuild --sql-output "$backup\rehearsal-rebuild.sql" | Out-Null
Check-Native 'Generate rehearsal rebuild plan'
$rehearsalAcknowledged = $false
Invoke-ReviewedPlan "$backup\rehearsal-start.json" "$backup\rehearsal-rebuild.sql"
$rehearsalAcknowledged = $true
& $python -B -m scripts.verify_collation --database $scratch --phase rebuilt `
    --baseline "$backup\restored.json" --quiescent --output "$backup\rehearsal-rebuilt.json" `
    --plan refresh --sql-output "$backup\rehearsal-refresh.sql" | Out-Null
Check-Native 'Verify rehearsal rebuild / generate refresh plan'
if (-not $rehearsalAcknowledged) { throw 'Rebuild was not acknowledged.' }
Invoke-ReviewedPlan "$backup\rehearsal-rebuilt.json" "$backup\rehearsal-refresh.sql"
& $python -B -m scripts.verify_collation --database $scratch --phase final `
    --baseline "$backup\restored.json" --quiescent --output "$backup\rehearsal-final.json" | Out-Null
Check-Native 'Rehearsal final audit'

# 4. Stop the verified API owner and all database clients/writers.
# Prefer Ctrl+C in its owning terminal. Do not stop Docker/PostgreSQL.
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'API still listening; stop its verified owner before continuing.'
}

# 5. Separately authorized development rebuild. Inspect generated SQL before invocation.
& $python -B -m scripts.verify_collation --baseline "$backup\before.json" `
    --quiescent --output "$backup\development-start.json" `
    --plan rebuild --sql-output "$backup\development-rebuild.sql" | Out-Null
Check-Native 'Development pre-write gate'
$developmentAcknowledged = $false
Invoke-ReviewedPlan "$backup\development-start.json" "$backup\development-rebuild.sql"
$developmentAcknowledged = $true

# 6. Only after acknowledged rebuild AND successful verification may refresh proceed.
& $python -B -m scripts.verify_collation --phase rebuilt --baseline "$backup\before.json" `
    --quiescent --output "$backup\development-rebuilt.json" `
    --plan refresh --sql-output "$backup\development-refresh.sql" | Out-Null
Check-Native 'Development rebuilt gate'
if (-not $developmentAcknowledged) { throw 'No acknowledged rebuild; marker refresh prohibited.' }
Invoke-ReviewedPlan "$backup\development-rebuilt.json" "$backup\development-refresh.sql"
& $python -B -m scripts.verify_collation --phase final --baseline "$backup\before.json" `
    --quiescent --output "$backup\development-final.json" | Out-Null
Check-Native 'Development final gate'
```

The logical restore builds indexes under libc 2.36. It proves backup completeness,
current-runtime compatibility and rehearsal execution, not repair of the original
physical files. No-owner/no-privileges restore intentionally does not verify role/ACL
recovery. Retain private configuration and the original database separately.

## Stop conditions and uncertain outcomes

Any failed check stops the procedure; leave API/writers down during development
maintenance. Never edit a report, weaken expected fingerprints or use another
index's plan to manufacture PASS. A different valid planner choice is an explicit
coverage failure requiring query/review adjustment, not automatic acceptance.

Do not infer rollback or commit solely from process exit, index validity or row
counts. On lost rebuild acknowledgment, preserve the original baseline, SQL,
reports and logs. Read-only `rebuilt` inspection can diagnose changed filenodes but
does not substitute for an acknowledged command. After controlled investigation,
generate a new rebuild plan from a fresh `rebuilt` snapshot and repeat all ten
rebuilds under renewed operator control; use new filenames. Require an acknowledged
successful transaction plus successful verification before generating/executing
refresh. If the initial rebuild rolled back, repeat from `before` instead.

If refresh acknowledgment is lost, inspect the actual recorded version with
read-only SQL before choosing `rebuilt` (2.41) or `final` (2.36) verification.
Never downgrade, overwrite the database, change runtime, drop constraints, delete
original rows/vectors, or delete volumes for recovery. Restore/cutover to a new
database and disposable cleanup require separate reviewed authorization.

## Subsequent rollout

The final gate still requires revision d7b834408ba8. Do not run Alembic upgrade or
bootstrap here. After repair, repeat the [freshness deployment preflight](data-freshness.md#operator-commands-and-safe-rollout)
and obtain separate authorization. Keep scheduling disabled. Pin the verified
image digest before any future recreation/pull through a reviewed configuration
change; do not replace this running container to perform the repair.
