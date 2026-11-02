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
$validProtocol=@{protocol=2;status='ASSESSED';scope='aapl-facts-dry-run';code=$null;
    last_confirmed_stage='assessment_completed';sec_http_attempts=$null;result=$valid;failure=$null;cleanup_failure=$null}
$blockedProtocol=@{protocol=2;status='BLOCKED';scope='aapl-facts-dry-run';code='PROXY_CONFIGURATION_UNSUPPORTED';
    last_confirmed_stage='development_verified';sec_http_attempts=$null;result=$null;
    failure=@{category='LOCAL_GUARD_REFUSAL';exception_type='AssessmentRejected';sqlstate=$null};cleanup_failure=$null}
Case 'byte drains and confirmed ordinary exit' {
    $json=$validProtocol|ConvertTo-Json -Depth 4 -Compress
    $r=Run-Child ("print('"+$json+"')")
    Assert-That ($r.Code -ceq 'WORKER_COMPLETED' -and $r.Protocol.status -ceq 'ASSESSED' -and
        $r.ExitCode -eq 0 -and $r.CleanupVerified -and $r.WorkerId -gt 0) 'Bad completion'
    Assert-That ($r.CreatedUtc.EndsWith('Z')) 'Creation identity must be UTC'
}
Case 'independent deadline terminates its sleeping worker' {
    $r=Run-Child 'import time; time.sleep(10)' 200
    Assert-That ($r.Code -ceq 'WORKER_DEADLINE' -and $r.CleanupVerified -and $r.ElapsedMs -lt 3000 -and
        $null -eq $r.Protocol -and $r.ExitCode -ne 0) 'Deadline or cleanup failed'
}
foreach($channel in @(1,2)){
    Case "incremental byte overflow stream $channel" {
        $r=Run-Child "import os,time; os.write($channel,b'x'*20000); time.sleep(10)"
        Assert-That ($r.Code -ceq 'WORKER_OUTPUT_LIMIT' -and $r.CleanupVerified -and $null -eq $r.Protocol) 'Output bound failed'
    }
}
Case 'stderr is never retained' {
    $r=Run-Child "import sys; print('SYNTHETIC_SECRET',file=sys.stderr)"
    Assert-That ($r.Code -ceq 'WORKER_DIAGNOSTICS_REFUSED' -and $null -eq $r.Protocol -and $r.CleanupVerified) 'stderr escaped'
}
Case 'nonzero exit is never accepted' {
    $r=Run-Child "import sys; print('SYNTHETIC_SECRET'); sys.exit(2)"
    Assert-That ($r.Code -ceq 'WORKER_INVALID_RECEIPT' -and $null -eq $r.Protocol -and $r.ExitCode -eq 2) 'Bad exit accepted'
}
Case 'invalid UTF8 is rejected without diagnostics' {
    $r=Run-Child "import os; os.write(1,b'\xff')"
    Assert-That ($r.Code -ceq 'WORKER_INVALID_RECEIPT' -and $null -eq $r.Protocol -and $r.CleanupVerified) 'Invalid encoding accepted'
}
Case 'nonzero worker retains only validated refusal protocol' {
    $json=$blockedProtocol|ConvertTo-Json -Depth 4 -Compress
    $r=Run-Child ("import sys; print('"+$json+"'); sys.exit(1)")
    Assert-That ($r.Code -ceq 'WORKER_REFUSED' -and $r.ExitCode -eq 1 -and $r.CleanupVerified -and
        $r.Protocol.code -ceq 'PROXY_CONFIGURATION_UNSUPPORTED' -and $null -eq $r.Protocol.sec_http_attempts) 'Safe refusal lost'
}
foreach($text in @('', '{broken', '{}')){
    Case ('missing or malformed protocol '+$text.Length) {
        $r=Run-Child ("import sys; print('"+$text+"'); sys.exit(1)")
        Assert-That ($r.Code -ceq 'WORKER_INVALID_RECEIPT' -and $null -eq $r.Protocol -and $r.CleanupVerified) 'Bad protocol accepted'
    }
}
Case 'oversized direct protocol rejects before parsing' {
    Assert-Throws {ConvertFrom-AaplWorkerProtocol (' '*16385) 1}
}
Case 'duplicate JSON properties rejected rather than normalized' {
    Assert-Throws {ConvertFrom-AaplWorkerProtocol '{"protocol":1,"protocol":1}' 1}
    $json=$validProtocol|ConvertTo-Json -Depth 4 -Compress
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($json.Replace('"would_insert":0','"would_insert":0,"would_insert":0')) 0}
}
$refusalStages=@{
    EXPLICIT_NETWORK_CONSENT_REQUIRED='not_started';EXPLICIT_DEVELOPMENT_REQUIRED='not_started'
    DEVELOPMENT_REQUIRED='network_admitted';LOCAL_DATABASE_REQUIRED='network_admitted'
    READ_ONLY_UNVERIFIED='database_configured';UNEXPECTED_DATABASE_OPERATION='schema_verified'
    CONNECTION_OPTIONS_CHANGED='database_configured';PROXY_CONFIGURATION_UNSUPPORTED='development_verified'
    PROXY_CONFIGURATION_UNVERIFIED='development_verified';AAPL_IDENTITY_MISMATCH='schema_verified'
    CANONICAL_ASSESSMENT_FAILED='source_admitted';INVALID_CANONICAL_RESULT='source_returned'
    ASSESSMENT_UNVERIFIED='not_started';OUTPUT_LIMIT='source_returned'
}
foreach($safeCode in $refusalStages.Keys){
    Case ('allowlisted refusal '+$safeCode) {
        $record=$blockedProtocol.Clone();$record.code=$safeCode;$record.last_confirmed_stage=$refusalStages[$safeCode]
        $parsed=ConvertFrom-AaplWorkerProtocol ($record|ConvertTo-Json -Depth 4 -Compress) 1
        Assert-That ($parsed.code -ceq $safeCode -and $null -eq $parsed.result -and $null -eq $parsed.sec_http_attempts) 'Refusal details lost'
    }
}
foreach($mutation in @(@{code='SYNTHETIC_SECRET'},@{code='proxy_configuration_unsupported'},
    @{last_confirmed_stage='assessment_completed'},@{last_confirmed_stage='source_returned'},
    @{result=$valid},@{sec_http_attempts=0},@{sec_http_attempts=1},@{sec_http_attempts=3},
    @{sec_http_attempts=-1},@{sec_http_attempts='unknown'},@{protocol=1},@{protocol=$true},@{extra='SYNTHETIC_SECRET'})){
    Case ('contradictory refusal '+($mutation.Keys -join ',')) {
        $bad=$blockedProtocol.Clone();foreach($key in $mutation.Keys){$bad[$key]=$mutation[$key]}
        Assert-Throws {ConvertFrom-AaplWorkerProtocol ($bad|ConvertTo-Json -Depth 4 -Compress) 1}
    }
}
Case 'exit code and stage must agree with status' {
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($blockedProtocol|ConvertTo-Json -Depth 4 -Compress) 0}
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($blockedProtocol|ConvertTo-Json -Depth 4 -Compress) 2}
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($validProtocol|ConvertTo-Json -Depth 4 -Compress) 1}
    $bad=$validProtocol.Clone();$bad.last_confirmed_stage='schema_verified'
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($bad|ConvertTo-Json -Depth 4 -Compress) 0}
}
foreach($badFailure in @(
    $null,'SYNTHETIC_SECRET',@{category='SYNTHETIC_SECRET';exception_type='other';sqlstate=$null},
    @{category='DATABASE_AUTH_REJECTED';exception_type='other';sqlstate='28P01'},
    @{category='DATABASE_AUTH_REJECTED';exception_type='PsycopgOperationalError';sqlstate='P0001'},
    @{category='DATABASE_PERMISSION';exception_type='PsycopgOperationalError';sqlstate='28P01'},
    @{category='UNCLASSIFIED';exception_type='SYNTHETIC_DYNAMIC_NAME';sqlstate=$null},
    @{category=@('UNCLASSIFIED');exception_type='other';sqlstate=$null},
    @{category='UNCLASSIFIED';exception_type='other';sqlstate=$null;private='SYNTHETIC_SECRET'})){
    Case 'malformed or inconsistent failure classification refused' {
        $bad=$blockedProtocol.Clone();$bad.code='ASSESSMENT_UNVERIFIED';$bad.last_confirmed_stage='database_configured';$bad.failure=$badFailure
        Assert-Throws {ConvertFrom-AaplWorkerProtocol ($bad|ConvertTo-Json -Depth 5 -Compress) 1}
    }
}
Case 'typed SQLSTATE cannot masquerade as an early refusal' {
    $bad=$blockedProtocol.Clone();$bad.code='ASSESSMENT_UNVERIFIED'
    $bad.failure=@{category='DATABASE_AUTH_REJECTED';exception_type='PsycopgOperationalError';sqlstate='28P01'}
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($bad|ConvertTo-Json -Depth 5 -Compress) 1}
}
Case 'success cannot carry primary or cleanup failure' {
    foreach($field in @('failure','cleanup_failure')){
        $bad=$validProtocol.Clone();$bad[$field]=$blockedProtocol.failure
        Assert-Throws {ConvertFrom-AaplWorkerProtocol ($bad|ConvertTo-Json -Depth 5 -Compress) 0}
    }
}
Case 'bad cleanup classification and duplicate failure fields rejected' {
    $bad=$blockedProtocol.Clone();$bad.cleanup_failure=@{category='UNCLASSIFIED';exception_type='SYNTHETIC_DYNAMIC_NAME';sqlstate=$null}
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($bad|ConvertTo-Json -Depth 5 -Compress) 1}
    $json=$blockedProtocol|ConvertTo-Json -Depth 5 -Compress
    Assert-Throws {ConvertFrom-AaplWorkerProtocol ($json.Replace('"category":"LOCAL_GUARD_REFUSAL"','"category":"LOCAL_GUARD_REFUSAL","category":"UNCLASSIFIED"')) 1}
}

# Actual candidate Python producer -> actual supervisor parser. The synthetic
# worker uses the maintained guard, fake sessions and fixed error instances;
# it never calls an actual proxy discovery, native DB or source loader.
$fixture=Join-Path $fixtureRoot 'worker-protocol-cases.py'
$body=@'
import sys,pathlib,runpy,builtins,io
backend=pathlib.Path(sys.argv[1]);case=sys.argv[2]
runpy.run_path(str(backend/'tests/run_dep01a2_increment2_offline.py'),run_name='offline_guard')
for mod in (builtins,io):
    original=mod.open
    def guarded(p,*a,_original=original,**k):
        if isinstance(p,(str,pathlib.Path)) and pathlib.Path(p).name.startswith('.env'):raise AssertionError('Private file forbidden')
        return _original(p,*a,**k)
    mod.open=guarded
from unittest.mock import Mock
from types import SimpleNamespace
import psycopg
from sqlalchemy import exc as sa
from scripts import assess_aapl_facts as worker,setup_demo
errors={
    'auth':sa.OperationalError('SYNTHETIC_SQL',{},psycopg.errors.InvalidPassword('SYNTHETIC_SECRET')),
    'schema':setup_demo.DemoSetupError('SYNTHETIC_SECRET'),
    'timeout':sa.TimeoutError('SYNTHETIC_SECRET'),
    'unknown_state':sa.DBAPIError('SYNTHETIC_SQL',{},psycopg.errors.RaiseException('SYNTHETIC_SECRET')),
    'unknown_operational':sa.OperationalError('SYNTHETIC_SQL',{},psycopg.errors.SerializationFailure('SYNTHETIC_SECRET')),
    'cofailure':setup_demo.DemoSetupError('SYNTHETIC_SECRET'),
    'cofailure_guard':setup_demo.DemoSetupError('SYNTHETIC_SECRET'),
    'cleanup_only':None}
session=Mock()
session.close.side_effect=sa.TimeoutError('SYNTHETIC_CLOSE_SECRET') if case in {'cofailure','cleanup_only'} else None
if case=='cofailure_guard':
    def fail_close():raise worker.AssessmentRejected('READ_ONLY_UNVERIFIED')
    session.close.side_effect=fail_close
engine=SimpleNamespace(dispose=Mock(side_effect=TypeError('SYNTHETIC_DISPOSE_SECRET') if case=='cofailure' else None))
factory=Mock(return_value=session);factory.kw={'bind':engine}
worker._network_admission=lambda:None
worker._make_factory=lambda *a:factory
setup_demo.check_schema=Mock(side_effect=errors[case])
raise SystemExit(worker.main(['--allow-network']))
'@
$bytes=[Text.UTF8Encoding]::new($false).GetBytes($body)
$file=[IO.File]::Open($fixture,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$file.Write($bytes,0,$bytes.Length)}finally{$file.Dispose()}
$expectedCategories=@{auth='DATABASE_AUTH_REJECTED';schema='SCHEMA_REQUIREMENT_UNSATISFIED';timeout='POOL_TIMEOUT';
    unknown_state='DATABASE_ERROR_UNCLASSIFIED';cofailure='SCHEMA_REQUIREMENT_UNSATISFIED';
    unknown_operational='DATABASE_ERROR_UNCLASSIFIED';
    cofailure_guard='SCHEMA_REQUIREMENT_UNSATISFIED';cleanup_only='POOL_TIMEOUT'}
foreach($kind in $expectedCategories.Keys){
    Case ('end-to-end synthetic worker '+$kind) {
        $r=Invoke-AaplFactsWorker -Executable $python -Directory $fixtureRoot -DeadlineMs 8000 `
            -WorkerArguments @('-I','-B',$fixture,(Join-Path $repoRoot 'backend'),$kind)
        Assert-That ($r.Code -ceq 'WORKER_REFUSED' -and $r.ExitCode -eq 1 -and $r.CleanupVerified) 'Worker protocol failed'
        Assert-That ($r.Protocol.failure.category -ceq $expectedCategories[$kind] -and
            $r.Protocol.last_confirmed_stage -ceq 'database_configured' -and $null -eq $r.Protocol.sec_http_attempts) 'Classification lost'
        if($kind -eq 'auth'){Assert-That ($r.Protocol.failure.sqlstate -ceq '28P01') 'Auth state lost'}
        if($kind -in @('unknown_state','unknown_operational')){Assert-That ($null -eq $r.Protocol.failure.sqlstate) 'Unknown SQLSTATE leaked'}
        if($kind -in @('cofailure','cleanup_only')){
            Assert-That ($r.Protocol.cleanup_failure.category -ceq 'POOL_TIMEOUT') 'First cleanup error lost'
        }elseif($kind -eq 'cofailure_guard'){
            Assert-That ($r.Protocol.code -ceq 'ASSESSMENT_UNVERIFIED' -and
                $r.Protocol.cleanup_failure.category -ceq 'LOCAL_GUARD_REFUSAL') 'Cleanup guard replaced primary code'
        }else{Assert-That ($null -eq $r.Protocol.cleanup_failure) 'Unexpected cleanup failure'}
        Assert-That (($r.Protocol|ConvertTo-Json -Depth 5 -Compress) -notmatch 'SYNTHETIC') 'Private text escaped'
    }
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
        $code=if($script:mode -eq 'cleanup'){'WORKER_CLEANUP_UNVERIFIED'}elseif($script:mode -eq 'blocked'){'WORKER_REFUSED'}else{'WORKER_COMPLETED'}
        [pscustomobject]@{Code=$code;WorkerId=123;CreatedUtc='2026-11-02T00:00:00.0000000Z';ExitCode=if($script:mode -eq 'blocked'){1}else{0};
            ElapsedMs=1;CleanupVerified=($script:mode -ne 'cleanup');
            Protocol=if($script:mode -eq 'invalid'){'SYNTHETIC_SECRET'}elseif($script:mode -eq 'blocked'){$blockedProtocol}else{$validProtocol}}
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
    foreach($kind in @('invalid','cleanup','blocked')){
        Case "failed $kind receipt is retained without raw output or retry" {
            $script:mode=$kind;$before=$script:invocations
            $path=Join-Path $fixtureRoot ($kind+'.json')
            Assert-Throws {Invoke-AaplFactsAssessment $true $path}
            $text=[IO.File]::ReadAllText($path)
            $r=ConvertFrom-Json -InputObject $text
            Assert-That ($r.status -ceq 'FAILED' -and $null -eq $r.result -and $text -notmatch 'SYNTHETIC_SECRET' -and
                $script:invocations -eq ($before+1)) 'Failure not retained safely'
            if($kind -eq 'blocked'){
                Assert-That ($r.worker_refusal_code -ceq 'PROXY_CONFIGURATION_UNSUPPORTED' -and
                    $r.last_confirmed_stage -ceq 'development_verified' -and $null -eq $r.sec_http_attempts) 'Receipt lost safe refusal'
            }else{Assert-That ($null -eq $r.worker_refusal_code -and $null -eq $r.last_confirmed_stage) 'Unverified details persisted'}
        }
    }
}finally{
    Set-Item Function:Invoke-AaplFactsWorker $realWorker
    $env:FINLENS_SERVER_PROFILE=$originalProfile;$env:FINLENS_FINANCIAL_ONLY=$originalFlag
}
Write-Output "Results: $passed passed, $failed failed. Retained synthetic artifacts: $fixtureRoot"
if($failed -gt 0){exit 1}
