# Offline runner, no Pester/install dependency. All external interfaces are mocked.
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $repoRoot 'Start-FinLens.ps1')
$original = @{}
foreach ($name in @('Get-FinLensListeners', 'Get-FinLensProcessRecord', 'Get-FinLensHttp',
    'Get-FinLensJson', 'Test-FinLensOwnedListener', 'Wait-FinLensReady', 'Start-FinLensService', 'Invoke-FinLensProfileCheck')) {
    $original[$name] = (Get-Item "Function:$name").ScriptBlock
}
$passed = 0
$failed = 0

function Assert-That { param([bool]$Condition, [string]$Message) if (-not $Condition) { throw $Message } }
function Assert-Throws {
    param([scriptblock]$Action, [string]$Pattern)
    $caught = $null
    try { & $Action } catch { $caught = $_.Exception.Message }
    Assert-That ($null -ne $caught -and $caught -match $Pattern) "Expected failure matching $Pattern; got $caught"
}
function Reset-Fixture {
    foreach ($name in $original.Keys) { Set-Item "Function:script:$name" $original[$name] }
    $script:launches = @(); $script:requests = @(); $script:browsers = @()
    $script:mode = ''; $script:missing = $false; $script:occupied = 0; $script:profileDenied = $false
    $script:apiFixturePort=8000; $script:webFixturePort=3000
    $script:epoch = [DateTime]::Parse('2026-10-17T00:00:00Z').ToUniversalTime()
    function script:Test-Path { param($LiteralPath, $PathType) return (-not $script:missing) }
    function script:Get-Command { param($Name) if ($Name -ne 'node.exe') { throw 'Unexpected command discovery' }; [PSCustomObject]@{Source='C:\fixture\node.exe'} }
    function script:Invoke-FinLensProfileCheck { if ($script:profileDenied) { throw 'profile denied' } }
    function script:Get-NetTCPConnection {
        param($State)
        if ($script:occupied) { [PSCustomObject]@{LocalPort=$script:occupied; LocalAddress='127.0.0.1'; OwningProcess=999} }
        for ($i=0; $i -lt $script:launches.Count; $i++) {
            [PSCustomObject]@{LocalPort=@($script:apiFixturePort,$script:webFixturePort)[$i]; LocalAddress='127.0.0.1'; OwningProcess=101+100*$i}
        }
    }
    function script:Get-CimInstance {
        param($ClassName, $Filter)
        $processNumber = [int]($Filter -replace 'ProcessId=', '')
        $parent = if ($processNumber -in @(101,201)) { $processNumber-1 } else { 1 }
        [PSCustomObject]@{ProcessId=$processNumber; ParentProcessId=$parent; CreationDate=$script:epoch.AddSeconds([int]($processNumber % 100 -ne 0))}
    }
    function script:Start-Process {
        param($FilePath, $ArgumentList, [switch]$PassThru)
        if ($FilePath -like 'http:*') { $script:browsers += $FilePath; return }
        Assert-That ($FilePath -eq 'powershell.exe' -and $PassThru) 'Unexpected process launch'
        Assert-That ($ArgumentList -contains '-NoProfile' -and $ArgumentList -contains '-NoExit') 'Missing interactive/no-profile launch'
        $script:launches += [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($ArgumentList[-1]))
        [PSCustomObject]@{Id=100*$script:launches.Count; StartTime=$script:epoch; HasExited=$false}
    }
    function script:Invoke-WebRequest {
        param($Uri, [switch]$UseBasicParsing, $TimeoutSec, $MaximumRedirection)
        Assert-That ($UseBasicParsing -and $TimeoutSec -eq 2 -and $MaximumRedirection -eq 0) 'HTTP must be bounded and deny redirects'
        $script:requests += $Uri
        $destination = [uri]$Uri
        Assert-That ($destination.Scheme -eq 'http' -and $destination.Host -eq '127.0.0.1' -and
            $destination.Port -in @($script:apiFixturePort,$script:webFixturePort)) 'Unexpected destination'
        if ($script:mode -eq 'backend-down' -and $Uri -like '*:8000/*') { throw 'synthetic private error' }
        if ($script:mode -eq 'proxy-down' -and $Uri -like '*/api/finlens/*') { throw 'synthetic private error' }
        $content = switch -Regex ($Uri) {
            '/healthz$' { '{"status":"ok","service":"finlens-api"}'; break }
            '/capabilities$' { '{"research_mode":true,"ai_analysis_configured":false,"server_profile":"development"}'; break }
            '/dbz$' { '{"status":"ok","database":"postgresql"}'; break }
            default { '<html><title>FinLens | SEC Filing Research</title></html>' }
        }
        if ($script:mode -eq 'wrong-api' -and $Uri -like '*/healthz') { $content='{"status":"ok","service":"foreign"}' }
        if ($script:mode -eq 'wrong-proxy' -and $Uri -like '*/api/finlens/capabilities') { $content='{"research_mode":true,"ai_analysis_configured":false,"server_profile":"sec_readonly"}' }
        if ($script:mode -eq 'wrong-web' -and $Uri -eq 'http://127.0.0.1:3000') { $content='<title>Other app</title>' }
        if ($script:mode -eq 'invalid-json' -and $Uri -like '*/healthz') { $content='not-json' }
        if ($script:mode -eq 'wrong-db' -and $Uri -like '*/dbz') { $content='{"status":"ok","database":"other"}' }
        [PSCustomObject]@{StatusCode=200; Content=$content}
    }
    function script:Start-Sleep { throw 'Unexpected wait: failure cases use one-probe timeout zero' }
    function script:Stop-Process { throw 'Forbidden process termination' }
    function script:docker { throw 'Forbidden Docker operation' }
    function script:taskkill { throw 'Forbidden process-tree termination' }
}
function Test-Case {
    param([string]$Name, [scriptblock]$Body)
    Reset-Fixture
    try { & $Body; $script:passed++; Write-Output "PASS $Name" }
    catch { $script:failed++; Write-Output "FAIL $Name : $($_.Exception.Message)" }
}
function Invoke-Fixture { param([bool]$SkipBrowser=$true) Invoke-FinLensStartup $repoRoot 8000 3000 0 $SkipBrowser }

Test-Case 'ready services, child-only pairing, offline flags, no acquisition' {
    $before = [Environment]::GetEnvironmentVariables('Process')
    Invoke-Fixture
    Assert-That ($launches.Count -eq 2 -and $browsers.Count -eq 0) 'Expected exactly two service terminals'
    Assert-That ($launches[0] -match "'uvicorn' 'app.main:app'" -and $launches[0] -match 'HF_HUB_OFFLINE' -and $launches[0] -match 'TRANSFORMERS_OFFLINE') 'Backend command contract'
    Assert-That ($launches[1] -match 'FINLENS_API_BASE_URL.*http://127.0.0.1:8000' -and $launches[1] -match "'dev'.*'127.0.0.1'.*'3000'") 'Frontend command pairing'
    Assert-That (($launches -join '') -notmatch 'alembic|setup_demo|seed_companies|refresh_data|index_catalog|sync_financial_facts|pip install|npm ci|npx') 'Forbidden provisioning command'
    Assert-That ($requests.Count -eq 7 -and $requests -contains 'http://127.0.0.1:3000/api/finlens/dbz') 'Direct/proxied readiness required'
    $after = [Environment]::GetEnvironmentVariables('Process')
    Assert-That ($before.Count -eq $after.Count) 'Parent environment changed'
    foreach ($key in $before.Keys) { Assert-That ($before[$key] -ceq $after[$key]) 'Parent environment value changed' }
}
Test-Case 'browser opens only after successful readiness' { Invoke-Fixture $false; Assert-That ($browsers.Count -eq 1) 'Expected one browser' }
Test-Case 'alternate ports pair only the requested backend and frontend' {
    $script:apiFixturePort=8021; $script:webFixturePort=3003
    Invoke-FinLensStartup $repoRoot 8021 3003 0 $true
    Assert-That ($launches[1] -match 'FINLENS_API_BASE_URL.*http://127.0.0.1:8021' -and
        $requests -contains 'http://127.0.0.1:3003/api/finlens/dbz') 'Custom port pairing not verified'
}
Test-Case 'profile command uses no operational imports and sanitizes errors' {
    Set-Item Function:Invoke-FinLensProfileCheck $original['Invoke-FinLensProfileCheck']
    function Invoke-FixturePython {
        param([switch]$B, [string]$c)
        $script:profileArgumentsValid = $B -and $c -ceq 'from app.release_policy import require_development; require_development()'
        throw 'private-fixture-diagnostic'
    }
    $beforeLocation=$PWD.Path
    $message=$null
    $script:profileArgumentsValid=$false
    try { Invoke-FinLensProfileCheck 'Invoke-FixturePython' $repoRoot } catch { $message=$_.Exception.Message }
    Assert-That ($profileArgumentsValid -and $message -match '^Development profile preflight failed' -and $message -notmatch 'private-fixture' -and $PWD.Path -ceq $beforeLocation) 'Profile diagnostics/location not safe'
}
foreach ($port in @(8000,3000)) {
    Test-Case "occupied port $port refused before any launch or HTTP" {
        $script:occupied=$port
        Assert-Throws { Invoke-Fixture } 'already occupied'
        Assert-That ($launches.Count -eq 0 -and $requests.Count -eq 0) 'Occupied listener must never be probed/reused'
    }
}
Test-Case 'missing preparation does not provision' { $script:missing=$true; Assert-Throws { Invoke-Fixture } 'prerequisites missing'; Assert-That ($launches.Count -eq 0) 'No launch expected' }
Test-Case 'release-profile denial precedes service launch' { $script:profileDenied=$true; Assert-Throws { Invoke-Fixture } 'profile denied'; Assert-That ($launches.Count -eq 0) 'Profile gate too late' }
Test-Case 'same app ports rejected' { Assert-Throws { Invoke-FinLensStartup $repoRoot 8000 8000 0 $true } 'must differ' }
foreach ($caseMode in @('wrong-api','wrong-proxy','wrong-web','invalid-json','wrong-db','backend-down','proxy-down')) {
    Test-Case "safe readiness failure $caseMode" {
        $script:mode=$caseMode
        Assert-Throws { Invoke-Fixture $false } 'identity|invalid JSON|readiness timed out|database readiness'
        Assert-That ($browsers.Count -eq 0) 'Browser opened after failed readiness'
        if ($caseMode -in @('wrong-api','invalid-json','wrong-db','backend-down')) { Assert-That ($launches.Count -eq 1) 'Frontend must wait for backend' }
    }
}
Test-Case 'foreign process claiming a launched port rejected' {
    $script:launches=@('fixture')
    function script:Get-FinLensProcessRecord { param($ProcessId) [PSCustomObject]@{ParentProcessId=0; CreationDate=$script:epoch} }
    Assert-Throws { Test-FinLensOwnedListener 8000 ([PSCustomObject]@{Process=[PSCustomObject]@{Id=100; HasExited=$false}; StartedAt=$epoch}) } 'not owned'
}
Test-Case 'recycled terminal identity rejected' {
    $script:launches=@('fixture')
    function script:Get-FinLensProcessRecord { param($ProcessId) [PSCustomObject]@{ParentProcessId=100; CreationDate=$script:epoch.AddSeconds(1)} }
    Assert-Throws { Test-FinLensOwnedListener 8000 ([PSCustomObject]@{Process=[PSCustomObject]@{Id=100; HasExited=$false}; StartedAt=$epoch}) } 'not owned'
}
Test-Case 'wildcard listener rejected' {
    function script:Get-FinLensListeners { [PSCustomObject]@{LocalAddress='0.0.0.0'; OwningProcess=100} }
    Assert-Throws { Test-FinLensOwnedListener 8000 ([PSCustomObject]@{Process=[PSCustomObject]@{Id=100; HasExited=$false}; StartedAt=$epoch}) } 'loopback'
}
Test-Case 'dead terminal rejected' { Assert-Throws { Test-FinLensOwnedListener 8000 ([PSCustomObject]@{Process=[PSCustomObject]@{Id=100; HasExited=$true}}) } 'terminal exited' }
Test-Case 'transient not-ready state is retried to readiness' {
    $script:probeCount=0
    function script:Start-Sleep { param($Milliseconds) Assert-That ($Milliseconds -eq 250) 'Wrong polling delay' }
    Wait-FinLensReady 'fixture' { $script:probeCount++; return ($script:probeCount -eq 2) } 1
    Assert-That ($probeCount -eq 2) 'Expected exactly two probes'
}
Test-Case 'unsafe shutdown shortcut never terminates processes or Docker' {
    Assert-Throws { & (Join-Path $repoRoot 'Stop-FinLens.ps1') -StopDatabase } 'Automatic shutdown is disabled'
}
Test-Case 'refresh wrapper refuses missing/blank/oversize selections before Python' {
    foreach ($selection in @(@(), @(' '), @(1..36 | ForEach-Object { "T$_" }))) {
        Assert-Throws { & (Join-Path $repoRoot 'Refresh-FinLens.ps1') -Ticker $selection -EnableLiveRefresh } 'Explicit -Ticker selections'
    }
}
Test-Case 'refresh wrapper preserves both explicit opt-ins' {
    Assert-Throws { & (Join-Path $repoRoot 'Refresh-FinLens.ps1') -Ticker AAPL } 'Live refresh is disabled'
}
Test-Case 'refresh wrapper forwards explicit issuers and never falls back to all' {
    . (Join-Path $repoRoot 'Refresh-FinLens.ps1')
    function Get-FinLensRefreshOptIn { return $true }
    function Invoke-FinLensRefreshPython {
        param([string[]]$Selection)
        Assert-That (($Selection -join '|') -ceq '--ticker|AAPL|--ticker|COST') 'Explicit selection changed or expanded'
        $script:forwarded=$true
    }
    $script:forwarded=$false
    $beforeLocation=$PWD.Path
    Invoke-FinLensSelectedRefresh $true @('AAPL','COST')
    Assert-That ($forwarded -and $PWD.Path -ceq $beforeLocation) 'Dispatch/location not preserved'
}
Test-Case 'refresh wrapper opt-in variable is still required' {
    . (Join-Path $repoRoot 'Refresh-FinLens.ps1')
    function Get-FinLensRefreshOptIn { return $false }
    function Invoke-FinLensRefreshPython { throw 'Python must not run without both opt-ins' }
    Assert-Throws { Invoke-FinLensSelectedRefresh $true @('AAPL') } 'Live refresh is disabled'
}

Write-Output "REL-01A PowerShell: $passed passed, $failed failed, 0 skipped"
if ($failed) { exit 1 }
