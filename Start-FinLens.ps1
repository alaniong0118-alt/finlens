param(
    [string]$ProjectRoot = "D:\Projects\finlens-foundation",
    [ValidateRange(1, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1, 65535)][int]$FrontendPort = 3000,
    [ValidateRange(5, 180)][int]$ReadinessTimeoutSeconds = 60,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

function Get-FinLensListeners {
    param([int]$Port)
    # No matching port is normal; enumeration failure must propagate.
    @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalPort -eq $Port })
}

function Get-FinLensProcessRecord {
    param([int]$ProcessId)
    Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
}

function Test-FinLensOwnedListener {
    param([int]$Port, $Owner)
    if ($Owner.Process.HasExited) { throw 'A launched service terminal exited. Inspect its output; no process was terminated.' }
    $listeners = @(Get-FinLensListeners $Port)
    if (-not $listeners.Count) { return $false }
    foreach ($listener in $listeners) {
        if ($listener.LocalAddress -ne '127.0.0.1') { throw "Port $Port is not exclusively bound to IPv4 loopback." }
        $currentId = [int]$listener.OwningProcess
        $childStarted = [DateTime]::MaxValue
        $owned = $false
        for ($depth = 0; $depth -lt 16 -and $currentId -gt 0; $depth++) {
            $record = Get-FinLensProcessRecord $currentId
            if (-not $record -or -not $record.CreationDate) { break }
            $started = ([DateTime]$record.CreationDate).ToUniversalTime()
            if ($started -gt $childStarted -or $started -lt $Owner.StartedAt) { break }
            if ($currentId -eq $Owner.Process.Id) {
                $owned = $started -eq $Owner.StartedAt
                break
            }
            $childStarted = $started
            $currentId = [int]$record.ParentProcessId
        }
        if (-not $owned) { throw "Port $Port is not owned by the terminal launched here. No process was terminated." }
    }
    return $true
}

function Get-FinLensHttp {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -MaximumRedirection 0 -ErrorAction Stop
        if ($response.StatusCode -eq 200) { return [string]$response.Content }
    } catch { return $null } # Never log raw errors, response bodies or credentials.
    return $null
}

function Get-FinLensJson {
    param([string]$Url)
    $body = Get-FinLensHttp $Url
    if ($null -eq $body) { return $null }
    try { return ConvertFrom-Json -InputObject $body -ErrorAction Stop }
    catch { throw 'A readiness endpoint returned invalid JSON. Verify the service in its terminal.' }
}

function Assert-FinLensApiIdentity {
    param($Health, $Capabilities)
    if ($Health.status -cne 'ok' -or $Health.service -cne 'finlens-api' -or
        $Capabilities.research_mode -isnot [bool] -or -not $Capabilities.research_mode -or
        $Capabilities.server_profile -cne 'development' -or
        $Capabilities.ai_analysis_configured -isnot [bool]) {
        throw 'API identity/profile did not match FinLens development. No service was stopped.'
    }
}

function Wait-FinLensReady {
    param([string]$Stage, [scriptblock]$Probe, [int]$TimeoutSeconds)
    $clock = [Diagnostics.Stopwatch]::StartNew()
    do {
        if (& $Probe) { return }
        if ($clock.Elapsed.TotalSeconds -ge $TimeoutSeconds) { break }
        Start-Sleep -Milliseconds 250
    } while ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    throw "$Stage readiness timed out. Inspect service terminals, PostgreSQL and proxy ports. Stop only your demo terminals with Ctrl+C; no provisioning or downloads were attempted."
}

function Invoke-FinLensProfileCheck {
    param([string]$PythonExe, [string]$BackendDir)
    Push-Location -LiteralPath $BackendDir
    try {
        # Config/profile only, no database, model or provider initialization.
        & $PythonExe -B -c 'from app.release_policy import require_development; require_development()' *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Profile check returned a failure.' }
    } catch {
        throw 'Development profile preflight failed. Check private backend configuration without printing credentials; this launcher rejects sec_readonly.'
    } finally { Pop-Location }
}

function Start-FinLensService {
    param([string]$Title, [string]$Directory, [string]$Executable, [string[]]$ServiceArguments, [hashtable]$ChildEnvironment)
    $quote = { param($value) "'" + ([string]$value).Replace("'", "''") + "'" }
    $lines = @('$ErrorActionPreference = ''Stop''', ('$Host.UI.RawUI.WindowTitle = ' + (& $quote $Title)),
        ("Set-Location -LiteralPath " + (& $quote $Directory)))
    foreach ($name in $ChildEnvironment.Keys) {
        $lines += "Set-Item -LiteralPath 'Env:$name' -Value $(& $quote $ChildEnvironment[$name])"
    }
    $argumentsText = ($ServiceArguments | ForEach-Object { & $quote $_ }) -join ' '
    $lines += "& $(& $quote $Executable) $argumentsText"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes(($lines -join [Environment]::NewLine)))
    # Interactive terminals are intentional operator controls: stop with Ctrl+C.
    # On failure leave them visible; never guess ownership to terminate a tree.
    $process = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-NoExit', '-EncodedCommand', $encoded) -PassThru
    $record = Get-FinLensProcessRecord $process.Id
    if (-not $record -or $process.HasExited -or
        [Math]::Abs((([DateTime]$record.CreationDate).ToUniversalTime() - $process.StartTime.ToUniversalTime()).TotalMilliseconds) -gt 10) {
        throw 'Cannot establish launched terminal identity. Inspect the new terminal; no automatic cleanup attempted.'
    }
    [PSCustomObject]@{ Process = $process; StartedAt = ([DateTime]$record.CreationDate).ToUniversalTime() }
}

function Invoke-FinLensStartup {
    param([string]$Root, [int]$ApiPort, [int]$WebPort, [int]$TimeoutSeconds, [bool]$SkipBrowser)
    if ($ApiPort -eq $WebPort) { throw 'Backend and frontend ports must differ.' }
    $rootPath = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).Path
    $backend = Join-Path $rootPath 'backend'
    $frontend = Join-Path $rootPath 'frontend'
    $python = Join-Path $backend '.venv\Scripts\python.exe'
    $next = Join-Path $frontend 'node_modules\next\dist\bin\next'
    foreach ($required in @($python, $next, (Join-Path $backend '.env'), (Join-Path $rootPath 'docker-compose.yml'))) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw 'Prepared demo prerequisites missing. Follow docs/local-demo.md; this launcher does not provision or install.'
        }
    }
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    # Even plausible FinLens listeners are refused: markers alone cannot attest origin.
    foreach ($port in @($ApiPort, $WebPort)) {
        if (@(Get-FinLensListeners $port).Count) {
            throw "Port $port is already occupied. Stop the intended demo from its original terminal or select unused ports; no listener is reused or terminated."
        }
    }
    Invoke-FinLensProfileCheck $python $backend
    $apiUrl = "http://127.0.0.1:$ApiPort"
    $webUrl = "http://127.0.0.1:$WebPort"
    Write-Host 'Prepared-data startup: PostgreSQL must already be running. No Docker, provisioning, acquisition or encoder warmup is invoked.'
    $apiOwner = Start-FinLensService 'FinLens Backend - Ctrl+C to stop' $backend $python @('-B', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") @{
        HF_HUB_OFFLINE = '1'; TRANSFORMERS_OFFLINE = '1'
    }
    Wait-FinLensReady 'Backend/database' {
        if (-not (Test-FinLensOwnedListener $ApiPort $apiOwner)) { return $false }
        $health = Get-FinLensJson "$apiUrl/healthz"
        $caps = Get-FinLensJson "$apiUrl/capabilities"
        if ($null -eq $health -or $null -eq $caps) { return $false }
        Assert-FinLensApiIdentity $health $caps
        $db = Get-FinLensJson "$apiUrl/dbz"
        if ($null -eq $db) { return $false }
        if ($db.status -cne 'ok' -or $db.database -cne 'postgresql') { throw 'Unexpected database readiness response.' }
        return $true
    } $TimeoutSeconds
    $webOwner = Start-FinLensService 'FinLens Frontend - Ctrl+C to stop' $frontend $node @($next, 'dev', '--hostname', '127.0.0.1', '--port', "$WebPort") @{
        FINLENS_API_BASE_URL = $apiUrl; NEXT_TELEMETRY_DISABLED = '1'
    }
    Wait-FinLensReady 'Frontend/proxy' {
        if (-not (Test-FinLensOwnedListener $ApiPort $apiOwner) -or -not (Test-FinLensOwnedListener $WebPort $webOwner)) { return $false }
        $html = Get-FinLensHttp $webUrl
        if ($null -eq $html) { return $false }
        if ($html -cnotmatch '<title>FinLens \| SEC Filing Research</title>') { throw 'Unexpected frontend application identity.' }
        $health = Get-FinLensJson "$webUrl/api/finlens/healthz"
        $caps = Get-FinLensJson "$webUrl/api/finlens/capabilities"
        $db = Get-FinLensJson "$webUrl/api/finlens/dbz"
        if ($null -eq $health -or $null -eq $caps -or $null -eq $db) { return $false }
        Assert-FinLensApiIdentity $health $caps
        if ($db.status -cne 'ok' -or $db.database -cne 'postgresql') { throw 'Unexpected proxy database readiness response.' }
        return $true
    } $TimeoutSeconds
    Write-Host "FinLens development demo ready: $webUrl (backend $apiUrl). Search/encoder, dataset coverage and release acceptance are not verified by startup."
    Write-Host 'Stop with Ctrl+C in each named service terminal, then close those terminals. No automatic process or database cleanup is performed.'
    if (-not $SkipBrowser) { Start-Process $webUrl | Out-Null }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-FinLensStartup $ProjectRoot $BackendPort $FrontendPort $ReadinessTimeoutSeconds ([bool]$NoBrowser)
}
