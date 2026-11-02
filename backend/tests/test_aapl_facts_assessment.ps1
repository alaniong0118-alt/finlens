# Offline: no app/config import, sockets, services, private files or DB. Tiny
# synthetic Python children exercise only process/pipe/deadline behavior.
# All created fixtures/receipts are retained; no filesystem cleanup.
#requires -Version 7.2
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $repoRoot 'Assess-FinLens-AaplFacts.ps1')
$python=Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$fixtureRoot=Join-Path (Split-Path -Parent $repoRoot) ('finlens-aapl-assessment-offline-'+[guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($fixtureRoot)
$passed=0;$failed=0
function Assert-That {param([bool]$Condition,[string]$Message) if(-not $Condition){throw $Message}}
function Assert-Throws {
    param([scriptblock]$Action)
    $caught=$false
    try{& $Action|Out-Null}catch{
        $caught=$true
        Assert-That ($_.Exception.Message -notmatch 'SYNTHETIC_SECRET') 'Private diagnostic escaped'
    }
    Assert-That $caught 'Expected refusal'
}
function Case {param([string]$Name,[scriptblock]$Body)
    try{& $Body;$script:passed++;Write-Output "PASS $Name"}
    catch{$script:failed++;Write-Output "FAIL $Name : $($_.Exception.Message)"}
}
function Run-Child {param([string]$Body,[int]$Deadline=2000)
    Invoke-AaplFactsWorker -Executable $python -Directory $fixtureRoot -DeadlineMs $Deadline `
        -WorkerArguments @('-I','-B','-c',$Body)
}
$valid=@{status='ASSESSED';scope='aapl-facts-dry-run';ticker='AAPL';company_cik='0000320193';
    dry_run=$true;outcome='no_change';would_insert=0;version_before=0;version_after=0;facts_inserted=0;filings_published=0}
Case 'byte drains and confirmed ordinary exit' {
    $r=Run-Child "print('fixture-ok')"
    Assert-That ($r.Code -ceq 'WORKER_COMPLETED' -and $r.Output.Trim() -ceq 'fixture-ok' -and
        $r.ExitCode -eq 0 -and $r.CleanupVerified -and $r.WorkerId -gt 0) 'Bad completion'
    Assert-That ($r.CreatedUtc.EndsWith('Z')) 'Creation identity must be UTC'
}
Case 'independent deadline terminates its sleeping worker' {
    $r=Run-Child 'import time; time.sleep(10)' 200
    Assert-That ($r.Code -ceq 'WORKER_DEADLINE' -and $r.CleanupVerified -and $r.ElapsedMs -lt 3000 -and
        $null -eq $r.Output -and $r.ExitCode -ne 0) 'Deadline or cleanup failed'
}
foreach($channel in @(1,2)){
    Case "incremental byte overflow stream $channel" {
        $r=Run-Child "import os,time; os.write($channel,b'x'*20000); time.sleep(10)"
        Assert-That ($r.Code -ceq 'WORKER_OUTPUT_LIMIT' -and $r.CleanupVerified -and $null -eq $r.Output) 'Output bound failed'
    }
}
Case 'stderr is never retained' {
    $r=Run-Child "import sys; print('SYNTHETIC_SECRET',file=sys.stderr)"
    Assert-That ($r.Code -ceq 'WORKER_DIAGNOSTICS_REFUSED' -and $null -eq $r.Output -and $r.CleanupVerified) 'stderr escaped'
}
Case 'nonzero exit is never accepted' {
    $r=Run-Child "import sys; print('SYNTHETIC_SECRET'); sys.exit(2)"
    Assert-That ($r.Code -ceq 'WORKER_REFUSED' -and $null -eq $r.Output -and $r.ExitCode -eq 2) 'Bad exit accepted'
}
Case 'invalid UTF8 is rejected without diagnostics' {
    $r=Run-Child "import os; os.write(1,b'\xff')"
    Assert-That ($r.Code -ceq 'WORKER_INVALID_RECEIPT' -and $null -eq $r.Output -and $r.CleanupVerified) 'Invalid encoding accepted'
}
Case 'missing executable is sanitized and never retried' {
    $r=Invoke-AaplFactsWorker -Executable (Join-Path $fixtureRoot 'absent.exe') -Directory $fixtureRoot -WorkerArguments @()
    Assert-That ($r.Code -ceq 'WORKER_START_FAILED' -and $null -eq $r.WorkerId -and $r.CleanupVerified) 'Bad start accounting'
}
Case 'strict successful version zero receipt' {
    $r=ConvertFrom-AaplAssessment ($valid|ConvertTo-Json -Compress)
    Assert-That ($r.version_before -eq 0 -and $r.version_after -eq 0) 'Zero lost'
}
foreach($mutation in @(
    @{ticker='BBB'},@{company_cik='0000000001'},@{dry_run='true'},@{facts_inserted=1},
    @{would_insert=$true},@{would_insert=-1},@{version_after=1},@{would_insert=1},@{extra='SYNTHETIC_SECRET'})){
    Case ('invalid receipt '+($mutation.Keys -join ',')) {
        $bad=$valid.Clone();foreach($key in $mutation.Keys){$bad[$key]=$mutation[$key]}
        Assert-Throws {ConvertFrom-AaplAssessment ($bad|ConvertTo-Json -Compress)}
    }
}
Case 'receipt is exclusive and never overwrites an existing file' {
    $path=Join-Path $fixtureRoot 'exclusive.json'
    $file=Open-AaplAssessmentReceipt $path
    try{$bytes=[Text.Encoding]::UTF8.GetBytes('preserved');$file.Write($bytes,0,$bytes.Length)}finally{$file.Dispose()}
    Assert-Throws {Open-AaplAssessmentReceipt $path}
    Assert-That ([IO.File]::ReadAllText($path) -ceq 'preserved') 'Original file changed'
}
Case 'receipt requires absolute JSON in an existing directory' {
    foreach($path in @('relative.json',(Join-Path $fixtureRoot 'wrong.txt'),(Join-Path $fixtureRoot 'absent\receipt.json'))){
        Assert-Throws {Open-AaplAssessmentReceipt $path}
    }
}

$realWorker=(Get-Item Function:Invoke-AaplFactsWorker).ScriptBlock
$originalProfile=$env:FINLENS_SERVER_PROFILE;$originalFlag=$env:FINLENS_FINANCIAL_ONLY
try{
    $script:invocations=0;$script:mode='valid'
    function Invoke-AaplFactsWorker {
        param($Executable,$WorkerArguments,$Directory)
        $script:invocations++
        Assert-That (($WorkerArguments[0..1] -join '|') -ceq '-I|-B' -and
            $WorkerArguments[2] -ceq (Join-Path $repoRoot 'backend\scripts\assess_aapl_facts.py') -and
            $WorkerArguments[3] -ceq '--allow-network') 'Wrong child binding'
        Assert-That ($Directory -ceq (Join-Path $repoRoot 'backend') -and $Executable -ceq $python) 'Wrong executable/cwd'
        $code=if($script:mode -eq 'cleanup'){'WORKER_CLEANUP_UNVERIFIED'}else{'WORKER_COMPLETED'}
        [pscustomobject]@{Code=$code;WorkerId=123;CreatedUtc='2026-11-02T00:00:00.0000000Z';ExitCode=0;
            ElapsedMs=1;CleanupVerified=($script:mode -ne 'cleanup');
            Output=if($script:mode -eq 'invalid'){'SYNTHETIC_SECRET'}else{($valid|ConvertTo-Json -Compress)}}
    }
    Case 'missing consent never creates a receipt or worker' {
        $path=Join-Path $fixtureRoot 'no-consent.json'
        Assert-Throws {Invoke-AaplFactsAssessment $false $path}
        Assert-That ($script:invocations -eq 0 -and -not [IO.File]::Exists($path)) 'Refusal came too late'
    }
    Case 'unsupported profile never changes environment or starts worker' {
        $env:FINLENS_SERVER_PROFILE='sec_readonly';$env:FINLENS_FINANCIAL_ONLY='1'
        Assert-Throws {Invoke-AaplFactsAssessment $true (Join-Path $fixtureRoot 'no-profile.json')}
        Assert-That ($script:invocations -eq 0 -and $env:FINLENS_SERVER_PROFILE -ceq 'sec_readonly' -and
            $env:FINLENS_FINANCIAL_ONLY -ceq '1') 'Profile bypassed'
    }
    $env:FINLENS_SERVER_PROFILE='development';$env:FINLENS_FINANCIAL_ONLY='0'
    Case 'parent records only strict bounded sanitized success' {
        $path=Join-Path $fixtureRoot 'success.json'
        $r=Invoke-AaplFactsAssessment $true $path
        Assert-That ($r.status -ceq 'ASSESSED' -and $script:invocations -eq 1 -and (Get-Item -LiteralPath $path).Length -le 65536) 'Receipt failed'
        Assert-That ((ConvertFrom-Json -InputObject ([IO.File]::ReadAllText($path))).result.version_after -eq 0) 'Receipt lost result'
    }
    foreach($kind in @('invalid','cleanup')){
        Case "failed $kind receipt is retained without raw output or retry" {
            $script:mode=$kind;$before=$script:invocations
            $path=Join-Path $fixtureRoot ($kind+'.json')
            Assert-Throws {Invoke-AaplFactsAssessment $true $path}
            $text=[IO.File]::ReadAllText($path)
            $r=ConvertFrom-Json -InputObject $text
            Assert-That ($r.status -ceq 'FAILED' -and $null -eq $r.result -and $text -notmatch 'SYNTHETIC_SECRET' -and
                $script:invocations -eq ($before+1)) 'Failure not retained safely'
        }
    }
}finally{
    Set-Item Function:Invoke-AaplFactsWorker $realWorker
    $env:FINLENS_SERVER_PROFILE=$originalProfile;$env:FINLENS_FINANCIAL_ONLY=$originalFlag
}
Write-Output "Results: $passed passed, $failed failed. Retained synthetic artifacts: $fixtureRoot"
if($failed -gt 0){exit 1}
