# Scheduling is opt-in; this script never registers/enables a task.
param([switch]$EnableLiveRefresh, [string[]]$Ticker)
$ErrorActionPreference = 'Stop'

function Get-FinLensRefreshOptIn { return $env:FINLENS_REFRESH_ENABLED -eq '1' }

function Invoke-FinLensRefreshPython {
    param([string[]]$Selection)
    & ".\.venv\Scripts\python.exe" -B -m scripts.refresh_data @Selection --allow-network
    if ($LASTEXITCODE -ne 0) { throw 'Refresh failed or has pending work. Inspect the sanitized per-run report.' }
}

function Invoke-FinLensSelectedRefresh {
    param([bool]$Enabled, [string[]]$Tickers)
    if (-not $Tickers -or @($Tickers | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -or $Tickers.Count -gt 35) {
        throw 'Explicit -Ticker selections (1-35) are required. Full-catalog refresh/bootstrap is prohibited for the 36-company demo. No operation was started.'
    }
    if (-not $Enabled -or -not (Get-FinLensRefreshOptIn)) {
        throw 'Live refresh is disabled. Both explicit -EnableLiveRefresh and FINLENS_REFRESH_ENABLED=1 are required.'
    }
    $selection = @()
    foreach ($issuer in $Tickers) { $selection += @('--ticker', $issuer) }
    Push-Location -LiteralPath (Join-Path $PSScriptRoot 'backend')
    try { Invoke-FinLensRefreshPython $selection }
    finally { Pop-Location }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-FinLensSelectedRefresh ([bool]$EnableLiveRefresh) $Ticker
}
