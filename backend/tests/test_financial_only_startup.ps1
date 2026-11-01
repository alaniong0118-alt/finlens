# Offline only: all service, listener, HTTP and browser interfaces are mocked.
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $repoRoot 'Start-FinLens-FinancialOnly.ps1') -BackendPort 8123 -FrontendPort 3123 -OpenBrowser
$original=@{}
foreach($name in @('Invoke-FinancialOnlyCheckerProcess','Get-FinLensListeners','Get-FinLensHttp',
    'Get-FinLensJson','Test-FinLensOwnedListener','Wait-FinLensReady','Start-FinLensService')) {
    $original[$name]=(Get-Item "Function:$name").ScriptBlock
}
$passed=0;$failed=0
function Assert-That { param([bool]$Condition,[string]$Message) if(-not $Condition){throw $Message} }
function Assert-Throws {
    param([scriptblock]$Action,[string]$Pattern)
    $message=$null;try{& $Action|Out-Null}catch{$message=$_.Exception.Message}
    Assert-That ($null -ne $message -and $message -match $Pattern -and $message -notmatch 'SYNTHETIC_SECRET') 'Expected sanitized refusal'
}
function Reset-Fixture {
    foreach($name in $original.Keys){Set-Item "Function:script:$name" $original[$name]}
    $script:launches=@();$script:requests=@();$script:browsers=@();$script:occupied=0
    $script:mode='';$script:missing=$false;$script:checkerCalls=0
    $script:report=@{status='CONFIGURATION_READY';scope='financial-only-local';server_profile='sec_readonly';financial_only=$true;
        filing_research_enabled=$false;ai_analysis_enabled=$false;database_loopback=$true;encoder_imported=$false}
    function script:Test-Path {param($LiteralPath,$PathType) return (-not $script:missing)}
    function script:Get-Command {param($Name) Assert-That ($Name -eq 'node.exe') 'Unexpected executable';[pscustomobject]@{Source='C:\fixture\node.exe'}}
    function script:Invoke-FinancialOnlyCheckerProcess {
        $script:checkerCalls++
        if($script:mode -eq 'checker-failed'){throw 'SYNTHETIC_SECRET'}
        if($script:mode -eq 'checker-json'){return '{invalid SYNTHETIC_SECRET'}
        return ($script:report|ConvertTo-Json -Compress)
    }
    function script:Get-FinLensListeners {param($Port) if($Port -eq $script:occupied){[pscustomobject]@{LocalPort=$Port}}}
    function script:Start-FinLensService {
        param($Title,$Directory,$Executable,$ServiceArguments,$ChildEnvironment)
        $script:launches+=@{Title=$Title;Directory=$Directory;Executable=$Executable;Arguments=$ServiceArguments;Environment=$ChildEnvironment}
        [pscustomobject]@{Process=[pscustomobject]@{Id=100*$script:launches.Count};StartedAt=[datetime]'2026-11-01T00:00:00Z'}
    }
    function script:Test-FinLensOwnedListener {param($Port,$Owner) if($script:mode -eq 'foreign'){throw 'Unowned listener'};return $true}
    function script:Wait-FinLensReady {param($Stage,$Probe,$TimeoutSeconds) Assert-That ($TimeoutSeconds -eq 5) 'Unexpected deadline';if(-not (& $Probe)){throw 'Not ready'}}
    function script:Get-FinLensHttp {param($Url) $script:requests+=$Url;return '<title>FinLens | SEC Filing Research</title>'}
    function script:Get-FinLensJson {
        param($Url)
        $script:requests+=$Url
        $u=[uri]$Url
        Assert-That ($u.Host -eq '127.0.0.1' -and $u.Port -in @(8021,3003)) 'Unexpected HTTP target'
        if($Url -like '*/healthz'){return [pscustomobject]@{status='ok';service='finlens-api'}}
        if($Url -like '*/dbz'){return [pscustomobject]@{status='ok';database=if($script:mode -eq 'bad-db'){'wrong'}else{'postgresql'}}}
        if($Url -like '*/capabilities'){
            return [pscustomobject]@{research_mode=$true;server_profile=if($script:mode -eq 'development'){'development'}else{'sec_readonly'};
                ai_analysis_configured=$false;ai_analysis_enabled=$false;
                filing_research_enabled=if($script:mode -eq 'retrieval' -or ($script:mode -eq 'bad-proxy' -and $u.Port -eq 3003)){$true}else{$false}}
        }
        throw 'Unexpected probe'
    }
    function script:Start-Process {param($FilePath) Assert-That ($FilePath -eq 'http://127.0.0.1:3003') 'Unexpected process/browser';$script:browsers+=$FilePath}
}
function Invoke-Fixture {param([bool]$Browser=$false) Invoke-FinancialOnlyStartup -Root $repoRoot -ApiPort 8021 -WebPort 3003 -TimeoutSeconds 5 -OpenBrowser $Browser}
function Case {param($Name,[scriptblock]$Body) Reset-Fixture;try{& $Body;$script:passed++;Write-Output "PASS $Name"}catch{$script:failed++;Write-Output "FAIL $Name : $($_.Exception.Message)"}}

Case 'legacy dot-source defaults cannot replace supplied dedicated options' {
    Assert-That ($financialOnlyOptions.ApiPort -eq 8123 -and $financialOnlyOptions.WebPort -eq 3123 -and $financialOnlyOptions.OpenBrowser) 'Dedicated options were overwritten'
}
Case 'success is child-only restricted and browser opt-in' {
    $profile=$env:FINLENS_SERVER_PROFILE;$flag=$env:FINLENS_FINANCIAL_ONLY
    Invoke-Fixture
    Assert-That ($launches.Count -eq 2 -and $browsers.Count -eq 0 -and $checkerCalls -eq 1) 'Unexpected launch count'
    Assert-That ($launches[0].Environment.FINLENS_SERVER_PROFILE -ceq 'sec_readonly' -and $launches[0].Environment.FINLENS_FINANCIAL_ONLY -ceq '1') 'Missing child-only restriction'
    Assert-That ($launches[0].Arguments -contains '127.0.0.1' -and $launches[0].Arguments -contains '8021') 'Wrong backend bind'
    Assert-That ($launches[0].Arguments -contains 'scripts.preflight_financial_only_startup:create_app' -and $launches[0].Arguments -contains '--factory') 'Actual server must recheck its own configuration'
    Assert-That ($launches[1].Environment.FINLENS_API_BASE_URL -ceq 'http://127.0.0.1:8021' -and $launches[1].Arguments -contains '3003') 'Wrong proxy pairing'
    Assert-That ($env:FINLENS_SERVER_PROFILE -ceq $profile -and $env:FINLENS_FINANCIAL_ONLY -ceq $flag) 'Parent environment changed'
}
Case 'browser opens only after explicit request and readiness' {Invoke-Fixture $true;Assert-That ($browsers.Count -eq 1) 'Expected one browser'}
foreach($port in @(8021,3003)) {Case "occupied $port refuses before config or HTTP" {$script:occupied=$port;Assert-Throws {Invoke-Fixture} 'already occupied';Assert-That ($launches.Count -eq 0 -and $requests.Count -eq 0 -and $checkerCalls -eq 0) 'Existing listener was touched'}}
Case 'missing prerequisites never provision' {$script:missing=$true;Assert-Throws {Invoke-Fixture} 'prerequisites missing';Assert-That ($launches.Count -eq 0) 'Unexpected launch'}
Case 'same ports reject' {Assert-Throws {Invoke-FinancialOnlyStartup $repoRoot 8021 8021 5} 'must differ'}
Case 'foreign checkout rejects' {Assert-Throws {Invoke-FinancialOnlyStartup (Split-Path -Parent $repoRoot) 8021 3003 5} 'reviewed startup script'}
foreach($caseMode in @('checker-failed','checker-json')) {Case $caseMode {$script:mode=$caseMode;Assert-Throws {Invoke-Fixture} 'configuration check did not pass';Assert-That ($launches.Count -eq 0) 'Checker refused too late'}}
foreach($field in @('financial_only','database_loopback','filing_research_enabled','ai_analysis_enabled','encoder_imported')) {
    Case "checker boolean $field strict" {$script:report[$field]='false';Assert-Throws {Invoke-Fixture} 'configuration check did not pass';Assert-That ($launches.Count -eq 0) 'Bad checker accepted'}
}
Case 'unknown checker fields refused' {$script:report.extra='SYNTHETIC_SECRET';Assert-Throws {Invoke-Fixture} 'configuration check did not pass'}
foreach($caseMode in @('development','retrieval','bad-db','foreign','bad-proxy')) {
    Case "readiness refuses $caseMode without browser" {
        $script:mode=$caseMode;Assert-Throws {Invoke-Fixture $true} 'startup failed at';Assert-That ($browsers.Count -eq 0) 'Browser after failure'
        Assert-That ($launches.Count -eq $(if($caseMode -eq 'bad-proxy'){2}else{1})) 'Frontend launched before valid backend'
    }
}

# Exercise only the hidden checker's deadline/output handling with tiny synthetic
# scripts outside the checkout. No application/config import or service starts.
$fixtureRoot=Join-Path 'D:\Projects' ('finlens-financial-startup-offline-'+[guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory((Join-Path $fixtureRoot 'scripts'))
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'scripts\__init__.py'),'',[Text.UTF8Encoding]::new($false))
$fixtureScript=Join-Path $fixtureRoot 'scripts\preflight_financial_only_startup.py'
$python=Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
foreach($kind in @('ready','stderr','overflow','timeout')) {
    Case "bounded checker child $kind" {
        $body=switch($kind){
            'ready' {"import os`nassert os.environ['FINLENS_SERVER_PROFILE']=='sec_readonly'`nassert os.environ['FINLENS_FINANCIAL_ONLY']=='1'`nprint('fixture-ok')"}
            'stderr' {"import sys`nprint('SYNTHETIC_SECRET',file=sys.stderr)"}
            'overflow' {"print('SYNTHETIC_SECRET'*1000)"}
            'timeout' {"import time`ntime.sleep(5)"}
        }
        [IO.File]::WriteAllText($fixtureScript,$body,[Text.UTF8Encoding]::new($false))
        if($kind -eq 'ready'){
            $output=& $original['Invoke-FinancialOnlyCheckerProcess'] $python $fixtureRoot 3000
            Assert-That ($output.Trim() -ceq 'fixture-ok') 'Wrong checker child output'
        }else{Assert-Throws {& $original['Invoke-FinancialOnlyCheckerProcess'] $python $fixtureRoot $(if($kind -eq 'timeout'){100}else{3000})} 'configuration check failed'}
    }
}
Write-Output "Synthetic child fixture retained: $fixtureRoot (no deletion performed)"
Write-Output "Financial-only startup PowerShell: $passed passed, $failed failed, 0 skipped"
if($failed){exit 1}
