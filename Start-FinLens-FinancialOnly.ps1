param(
    [string]$ProjectRoot = $PSScriptRoot,
    [ValidateRange(1,65535)][int]$BackendPort = 8021,
    [ValidateRange(1,65535)][int]$FrontendPort = 3003,
    [ValidateRange(5,180)][int]$ReadinessTimeoutSeconds = 60,
    [switch]$OpenBrowser
)

# Dot-source declarations only, never the development-only startup function.
# Preserve supplied options before the legacy script binds its own defaults.
$financialOnlyOptions = @{ Root=$ProjectRoot; ApiPort=$BackendPort; WebPort=$FrontendPort;
    TimeoutSeconds=$ReadinessTimeoutSeconds; OpenBrowser=[bool]$OpenBrowser }
. (Join-Path $PSScriptRoot 'Start-FinLens.ps1')

function Invoke-FinancialOnlyCheckerProcess {
    param([string]$PythonExe, [string]$BackendDir,
        [ValidateRange(100,10000)][int]$TimeoutMs = 10000)
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = [Diagnostics.ProcessStartInfo]::new()
    $process.StartInfo.FileName = $PythonExe
    $process.StartInfo.Arguments = '-B -m scripts.preflight_financial_only_startup --check-configuration'
    $process.StartInfo.WorkingDirectory = $BackendDir
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    foreach ($entry in @{FINLENS_SERVER_PROFILE='sec_readonly';FINLENS_FINANCIAL_ONLY='1';
        HF_HUB_OFFLINE='1';TRANSFORMERS_OFFLINE='1'}.GetEnumerator()) {
        $process.StartInfo.EnvironmentVariables[$entry.Key] = $entry.Value
    }
    $started=$false; $streams=@(); $failure=$null; $output=$null
    try {
        $clock=[Diagnostics.Stopwatch]::StartNew()
        $started=$process.Start()
        if (-not $started) { throw 'Checker did not start.' }
        foreach ($reader in @($process.StandardOutput,$process.StandardError)) {
            $buffer=[char[]]::new(1024)
            $streams+=@{Reader=$reader;Buffer=$buffer;Task=$reader.ReadAsync($buffer,0,$buffer.Length);
                Text=[Text.StringBuilder]::new();Count=0;Eof=$false}
        }
        while ($true) {
            foreach ($stream in $streams) {
                if (-not $stream.Eof -and $stream.Task.IsCompleted) {
                    $count=$stream.Task.GetAwaiter().GetResult()
                    if ($count -eq 0) { $stream.Eof=$true }
                    else {
                        $stream.Count+=$count
                        if ($stream.Count -gt 4096) { throw 'Checker output bound exceeded.' }
                        $null=$stream.Text.Append($stream.Buffer,0,$count)
                        $stream.Task=$stream.Reader.ReadAsync($stream.Buffer,0,$stream.Buffer.Length)
                    }
                }
            }
            if ($process.HasExited -and @($streams|Where-Object{-not $_.Eof}).Count -eq 0) { break }
            if ($clock.ElapsedMilliseconds -ge $TimeoutMs) { throw 'Checker deadline exceeded.' }
            Start-Sleep -Milliseconds 10
        }
        if ($process.ExitCode -ne 0 -or $streams[1].Count -ne 0) { throw 'Checker refused configuration.' }
        $output=$streams[0].Text.ToString()
    } catch { $failure='Financial-only configuration check failed; private diagnostics suppressed.' }
    finally {
        if ($started) {
            try {
                # This handle belongs only to the checker created above, never a
                # service or a PID found by name/port. No child-tree termination.
                if (-not $process.HasExited) { $process.Kill() }
                if (-not $process.WaitForExit(1000)) { throw 'Checker remains unverified.' }
            } catch { $failure='Financial-only checker cleanup is unverified; no services were launched.' }
        }
        $process.Dispose()
    }
    if ($failure) { throw $failure }
    return $output
}

function Invoke-FinancialOnlyConfigurationCheck {
    param([string]$PythonExe, [string]$BackendDir)
    try {
        $json=Invoke-FinancialOnlyCheckerProcess $PythonExe $BackendDir
        $record=ConvertFrom-Json -InputObject $json -ErrorAction Stop
        $names=@('status','scope','server_profile','financial_only','filing_research_enabled',
            'ai_analysis_enabled','database_loopback','encoder_imported')
        if ((($record.PSObject.Properties.Name|Sort-Object)-join '|') -cne (($names|Sort-Object)-join '|') -or
            $record.status -cne 'CONFIGURATION_READY' -or $record.scope -cne 'financial-only-local' -or
            $record.server_profile -cne 'sec_readonly') { throw 'Invalid checker identity.' }
        foreach ($name in @('financial_only','database_loopback')) {
            if ($record.$name -isnot [bool] -or -not $record.$name) { throw 'Invalid checker restriction.' }
        }
        foreach ($name in @('filing_research_enabled','ai_analysis_enabled','encoder_imported')) {
            if ($record.$name -isnot [bool] -or $record.$name) { throw 'Invalid checker restriction.' }
        }
    } catch { throw 'Financial-only configuration check did not pass. No service was launched; private diagnostics suppressed.' }
}

function Assert-FinancialOnlyApiIdentity {
    param($Health, $Capabilities)
    if ($Health.status -cne 'ok' -or $Health.service -cne 'finlens-api' -or
        $Capabilities.server_profile -cne 'sec_readonly' -or
        $Capabilities.research_mode -isnot [bool] -or -not $Capabilities.research_mode) {
        throw 'Financial-only API identity/profile mismatch.'
    }
    foreach ($name in @('ai_analysis_configured','ai_analysis_enabled','filing_research_enabled')) {
        if ($Capabilities.$name -isnot [bool] -or $Capabilities.$name) {
            throw 'Financial-only API capability mismatch.'
        }
    }
}

function Invoke-FinancialOnlyStartup {
    param([string]$Root, [ValidateRange(1,65535)][int]$ApiPort=8021,
        [ValidateRange(1,65535)][int]$WebPort=3003,
        [ValidateRange(5,180)][int]$TimeoutSeconds=60, [bool]$OpenBrowser=$false)
    if ($ApiPort -eq $WebPort) { throw 'Backend and frontend ports must differ.' }
    $rootPath=(Resolve-Path -LiteralPath $Root -ErrorAction Stop).Path
    if (-not $rootPath.Equals($PSScriptRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Use the checkout containing this reviewed startup script.'
    }
    $backend=Join-Path $rootPath 'backend'; $frontend=Join-Path $rootPath 'frontend'
    $python=Join-Path $backend '.venv\Scripts\python.exe'
    $next=Join-Path $frontend 'node_modules\next\dist\bin\next'
    foreach ($path in @($python,$next,(Join-Path $backend 'scripts\preflight_financial_only_startup.py'))) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Prepared financial-only prerequisites missing; no provisioning attempted.' }
    }
    $node=(Get-Command node.exe -ErrorAction Stop).Source
    foreach ($port in @($ApiPort,$WebPort)) {
        if (@(Get-FinLensListeners $port).Count) { throw "Port $port is already occupied; no listener was reused or stopped." }
    }
    Invoke-FinancialOnlyConfigurationCheck $python $backend
    $apiUrl="http://127.0.0.1:$ApiPort"; $webUrl="http://127.0.0.1:$WebPort"
    $owners=@(); $stage='backend'
    try {
        $apiOwner=Start-FinLensService 'FinLens FinancialOnly Backend - Ctrl+C to stop' $backend $python @('-B','-m','uvicorn','scripts.preflight_financial_only_startup:create_app','--factory','--host','127.0.0.1','--port',"$ApiPort") @{
            FINLENS_SERVER_PROFILE='sec_readonly'; FINLENS_FINANCIAL_ONLY='1'; HF_HUB_OFFLINE='1'; TRANSFORMERS_OFFLINE='1'
        }
        $owners+=@{Role='Backend';Owner=$apiOwner}
        Wait-FinLensReady 'Financial-only backend/database' {
            if (-not (Test-FinLensOwnedListener $ApiPort $apiOwner)) { return $false }
            $health=Get-FinLensJson "$apiUrl/healthz"; $caps=Get-FinLensJson "$apiUrl/capabilities"
            if ($null -eq $health -or $null -eq $caps) { return $false }
            Assert-FinancialOnlyApiIdentity $health $caps
            $db=Get-FinLensJson "$apiUrl/dbz"
            if ($null -eq $db) { return $false }
            if ($db.status -cne 'ok' -or $db.database -cne 'postgresql') { throw 'Database readiness mismatch.' }
            return $true
        } $TimeoutSeconds
        $stage='frontend'
        $webOwner=Start-FinLensService 'FinLens FinancialOnly Frontend - Ctrl+C to stop' $frontend $node @($next,'dev','--hostname','127.0.0.1','--port',"$WebPort") @{
            FINLENS_API_BASE_URL=$apiUrl; NEXT_TELEMETRY_DISABLED='1'
        }
        $owners+=@{Role='Frontend';Owner=$webOwner}
        Wait-FinLensReady 'Financial-only frontend/proxy' {
            if (-not (Test-FinLensOwnedListener $ApiPort $apiOwner) -or -not (Test-FinLensOwnedListener $WebPort $webOwner)) { return $false }
            $html=Get-FinLensHttp $webUrl
            if ($null -eq $html) { return $false }
            if ($html -cnotmatch '<title>FinLens \| SEC Filing Research</title>') { throw 'Frontend identity mismatch.' }
            $health=Get-FinLensJson "$webUrl/api/finlens/healthz"; $caps=Get-FinLensJson "$webUrl/api/finlens/capabilities"
            $db=Get-FinLensJson "$webUrl/api/finlens/dbz"
            if ($null -eq $health -or $null -eq $caps -or $null -eq $db) { return $false }
            Assert-FinancialOnlyApiIdentity $health $caps
            if ($db.status -cne 'ok' -or $db.database -cne 'postgresql') { throw 'Proxy database readiness mismatch.' }
            return $true
        } $TimeoutSeconds
        $stage='browser'
        if ($OpenBrowser) { Start-Process $webUrl | Out-Null }
        Write-Host "Financial-only local startup ready: $webUrl; no encoder, real-data coverage, external access or full private-runtime acceptance is certified."
    } catch {
        throw "Financial-only startup failed at $stage. Inspect only the named terminals; no service or PostgreSQL was stopped."
    } finally {
        foreach ($item in $owners) {
            Write-Host ("FinLens FinancialOnly {0} - Ctrl+C to stop; terminal PID {1}, started {2:o}" -f $item.Role,$item.Owner.Process.Id,$item.Owner.StartedAt)
        }
        if ($owners.Count) { Write-Host 'Stop original terminals with Ctrl+C, then verify their identities/listeners. Descendant cleanup and OS egress containment are not proven.' }
    }
}

if ($MyInvocation.InvocationName -ne '.') { Invoke-FinancialOnlyStartup @financialOnlyOptions }
