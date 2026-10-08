# Scheduling is opt-in. This script does not register or enable a scheduled task.
param([switch]$EnableLiveRefresh)
$ErrorActionPreference = "Stop"
if (-not $EnableLiveRefresh -or $env:FINLENS_REFRESH_ENABLED -ne "1") {
    throw "Live refresh is disabled. Both explicit -EnableLiveRefresh and FINLENS_REFRESH_ENABLED=1 are required."
}
$repositoryPath = $PSScriptRoot
Push-Location (Join-Path $repositoryPath "backend")
try {
    & ".\.venv\Scripts\python.exe" -m scripts.refresh_data --all --allow-network
    if ($LASTEXITCODE -ne 0) { throw "Refresh failed or has pending work. Inspect the sanitized per-run report." }
} finally {
    Pop-Location
}
