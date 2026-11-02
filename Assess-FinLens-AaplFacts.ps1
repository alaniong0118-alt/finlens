#requires -Version 7.2
[CmdletBinding()]
param([switch]$AllowNetwork, [string]$ReceiptPath)

# Inert when dot-sourced for offline tests. Supported live entry requires separate
# approval for private configuration, local DB reads and SEC contact/acquisition.
function Invoke-AaplFactsWorker {
    param([string]$Executable, [string[]]$WorkerArguments, [string]$Directory,
        [ValidateRange(100,600000)][int]$DeadlineMs=600000,
        [ValidateRange(1024,16384)][int]$StreamLimit=16384)
    $process=[Diagnostics.Process]::new()
    $process.StartInfo=[Diagnostics.ProcessStartInfo]::new()
    $process.StartInfo.FileName=$Executable
    $process.StartInfo.WorkingDirectory=$Directory
    $process.StartInfo.UseShellExecute=$false
    $process.StartInfo.CreateNoWindow=$true
    $process.StartInfo.RedirectStandardOutput=$true
    $process.StartInfo.RedirectStandardError=$true
    foreach($argument in $WorkerArguments){$process.StartInfo.ArgumentList.Add($argument)}
    $streams=@();$started=$false;$code='WORKER_START_FAILED';$exitCode=$null
    $workerId=$null;$createdUtc=$null;$cleanup=$false;$protocol=$null
    $clock=[Diagnostics.Stopwatch]::StartNew()
    try {
        $started=$process.Start()
        if(-not $started){throw 'Start failed'}
        $workerId=$process.Id
        $createdUtc=$process.StartTime.ToUniversalTime().ToString('o')
        $code='WORKER_IO_FAILED'
        foreach($stream in @($process.StandardOutput.BaseStream,$process.StandardError.BaseStream)){
            $buffer=[byte[]]::new(1024)
            $streams+=@{Stream=$stream;Buffer=$buffer;Task=$stream.ReadAsync($buffer,0,$buffer.Length);
                Bytes=[IO.MemoryStream]::new();Count=0;Eof=$false}
        }
        while($true){
            if($clock.ElapsedMilliseconds -ge $DeadlineMs){$code='WORKER_DEADLINE';throw 'Deadline'}
            foreach($stream in $streams){
                if(-not $stream.Eof -and $stream.Task.IsCompleted){
                    $count=$stream.Task.GetAwaiter().GetResult()
                    if($count -eq 0){$stream.Eof=$true}else{
                        $stream.Count+=$count
                        if($stream.Count -gt $StreamLimit){$code='WORKER_OUTPUT_LIMIT';throw 'Output limit'}
                        $stream.Bytes.Write($stream.Buffer,0,$count)
                        $stream.Task=$stream.Stream.ReadAsync($stream.Buffer,0,$stream.Buffer.Length)
                    }
                }
            }
            if($process.HasExited -and @($streams|Where-Object{-not $_.Eof}).Count -eq 0){break}
            Start-Sleep -Milliseconds 10
        }
        $exitCode=$process.ExitCode
        if($streams[1].Count -ne 0){$code='WORKER_DIAGNOSTICS_REFUSED'}
        else{
            $code='WORKER_INVALID_RECEIPT'
            $text=[Text.UTF8Encoding]::new($false,$true).GetString($streams[0].Bytes.ToArray())
            $protocol=ConvertFrom-AaplWorkerProtocol -Text $text -ExitCode $exitCode
            $code=if($protocol.status -ceq 'ASSESSED'){'WORKER_COMPLETED'}else{'WORKER_REFUSED'}
        }
    } catch { $protocol=$null } # Never retain exception text or raw diagnostics.
    finally {
        if($started){
            try{
                # This original .NET process handle belongs to this attempt.
                # No PID/name/port lookup or arbitrary descendant termination.
                if(-not $process.HasExited){$process.Kill()}
                $cleanup=$process.WaitForExit(1000)
                if($cleanup){$exitCode=$process.ExitCode}
            }catch{$cleanup=$false}
        }else{$cleanup=$true}
        foreach($stream in $streams){$stream.Bytes.Dispose()}
        $process.Dispose()
    }
    if(-not $cleanup){$code='WORKER_CLEANUP_UNVERIFIED';$protocol=$null}
    [pscustomobject]@{Code=$code;ExitCode=$exitCode;WorkerId=$workerId;CreatedUtc=$createdUtc;
        CleanupVerified=$cleanup;ElapsedMs=$clock.ElapsedMilliseconds;Protocol=$protocol}
}

function ConvertFrom-AaplWorkerProtocol {
    param([string]$Text,[int]$ExitCode)
    if([Text.Encoding]::UTF8.GetByteCount($Text) -gt 16384){throw 'Worker protocol size limit'}
    $options=[Text.Json.JsonDocumentOptions]::new();$options.MaxDepth=8
    $document=[Text.Json.JsonDocument]::Parse($Text,$options)
    try{
        $root=$document.RootElement
        if($root.ValueKind -ne [Text.Json.JsonValueKind]::Object){throw 'Worker protocol must be object'}
        $nodes=@($root)
        foreach($field in @('result','failure','cleanup_failure')){
            $valueNode=[Text.Json.JsonElement]::new()
            if($root.TryGetProperty($field,[ref]$valueNode) -and $valueNode.ValueKind -eq [Text.Json.JsonValueKind]::Object){$nodes+=@($valueNode)}
        }
        foreach($node in $nodes){
            $names=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            foreach($property in $node.EnumerateObject()){
                if(-not $names.Add($property.Name)){throw 'Duplicate worker property'}
            }
        }
        $record=ConvertFrom-Json -InputObject $Text -AsHashtable -Depth 8 -ErrorAction Stop
    }finally{$document.Dispose()}
    $keys=@('protocol','scope','status','code','last_confirmed_stage','sec_http_attempts','result','failure','cleanup_failure')
    $stages=@('not_started','process_admitted','development_verified','network_admitted',
        'database_configured','schema_verified','source_admitted','source_returned','assessment_completed')
    if((($record.Keys|Sort-Object)-join '|') -cne (($keys|Sort-Object)-join '|') -or
        $record.scope -isnot [string] -or $record.status -isnot [string] -or $record.last_confirmed_stage -isnot [string] -or
        ($record.protocol -isnot [int] -and $record.protocol -isnot [long]) -or $record.protocol -ne 2 -or $record.scope -cne 'aapl-facts-dry-run' -or
        $record.last_confirmed_stage -cnotin $stages -or $null -ne $record.sec_http_attempts){throw 'Invalid protocol identity or uninstrumented count'}
    if($record.status -ceq 'ASSESSED'){
        if($ExitCode -ne 0 -or $null -ne $record.code -or $record.last_confirmed_stage -cne 'assessment_completed' -or
            $null -ne $record.failure -or $null -ne $record.cleanup_failure){
            throw 'Contradictory worker success'
        }
        $record.result=ConvertFrom-AaplAssessment ($record.result|ConvertTo-Json -Depth 3 -Compress)
    }elseif($record.status -ceq 'BLOCKED'){
        $databaseStages=@('database_configured','schema_verified','source_admitted','source_returned')
        $allowed=@{
            EXPLICIT_NETWORK_CONSENT_REQUIRED=@('not_started')
            EXPLICIT_DEVELOPMENT_REQUIRED=@('not_started','schema_verified')
            DEVELOPMENT_REQUIRED=@('network_admitted')
            LOCAL_DATABASE_REQUIRED=@('network_admitted')
            READ_ONLY_UNVERIFIED=$databaseStages
            UNEXPECTED_DATABASE_OPERATION=$databaseStages
            CONNECTION_OPTIONS_CHANGED=$databaseStages
            PROXY_CONFIGURATION_UNSUPPORTED=@('development_verified','schema_verified')
            PROXY_CONFIGURATION_UNVERIFIED=@('development_verified','schema_verified')
            AAPL_IDENTITY_MISMATCH=@('schema_verified')
            CANONICAL_ASSESSMENT_FAILED=@('schema_verified','source_admitted','source_returned')
            INVALID_CANONICAL_RESULT=@('source_returned')
            ASSESSMENT_UNVERIFIED=@($stages|Where-Object{$_ -cne 'assessment_completed'})
            OUTPUT_LIMIT=$stages
        }
        if($ExitCode -ne 1 -or $null -ne $record.result -or $record.code -isnot [string] -or
            $record.code -cnotin @($allowed.Keys) -or $record.last_confirmed_stage -cnotin $allowed[$record.code]){
            throw 'Contradictory or unknown worker refusal'
        }
        foreach($field in @('failure','cleanup_failure')){
            if($null -ne $record[$field]){Assert-AaplFailureClassification $record[$field] $record.last_confirmed_stage}
        }
        if($null -eq $record.failure){
            if($record.code -cne 'EXPLICIT_NETWORK_CONSENT_REQUIRED' -or $null -ne $record.cleanup_failure){throw 'Missing failure classification'}
        }elseif($record.code -cnotin @('ASSESSMENT_UNVERIFIED','CANONICAL_ASSESSMENT_FAILED') -and
            $record.failure.category -cne 'LOCAL_GUARD_REFUSAL'){throw 'Guard code conflicts with failure classification'}
    }else{throw 'Unknown worker protocol status'}
    return $record
}

function Assert-AaplFailureClassification {
    param($Failure,[string]$Stage)
    $keys=@('category','exception_type','sqlstate')
    if($Failure -isnot [Collections.IDictionary] -or
        (($Failure.Keys|Sort-Object)-join '|') -cne (($keys|Sort-Object)-join '|') -or
        $Failure.category -isnot [string] -or $Failure.exception_type -isnot [string]){throw 'Invalid failure fields'}
    $states=@{
        '28P01'='DATABASE_AUTH_REJECTED';'28000'='DATABASE_AUTH_REJECTED';'3D000'='DATABASE_TARGET_MISSING'
        '08000'='DATABASE_CONNECTION_FAILED';'08001'='DATABASE_CONNECTION_FAILED';'08003'='DATABASE_CONNECTION_FAILED'
        '08004'='DATABASE_CONNECTION_FAILED';'08006'='DATABASE_CONNECTION_FAILED';'08007'='DATABASE_CONNECTION_FAILED'
        '08P01'='DATABASE_CONNECTION_FAILED';'53300'='DATABASE_CAPACITY';'25006'='READ_ONLY_REJECTED_OPERATION'
        '42501'='DATABASE_PERMISSION';'42P01'='SCHEMA_OBJECT_MISSING';'42703'='SCHEMA_OBJECT_MISSING'
        '3F000'='SCHEMA_OBJECT_MISSING';'57014'='QUERY_CANCELED_OR_TIMEOUT';'55P03'='LOCK_NOT_AVAILABLE'
    }
    if($null -ne $Failure.sqlstate){
        if($Failure.sqlstate -isnot [string] -or $Failure.sqlstate -cnotin @($states.Keys) -or
            $Failure.category -cne $states[$Failure.sqlstate] -or
            $Failure.exception_type -cnotin @('PsycopgError','PsycopgOperationalError') -or
            $Stage -cnotin @('database_configured','schema_verified','source_admitted','source_returned')){throw 'Invalid typed SQLSTATE classification'}
        return
    }
    $pairs=@{
        LOCAL_GUARD_REFUSAL=@('AssessmentRejected');SCHEMA_REQUIREMENT_UNSATISFIED=@('DemoSetupError')
        POOL_TIMEOUT=@('SQLAlchemyTimeoutError');CONFIGURATION_INVALID=@('SQLAlchemyArgumentError')
        API_STATE_ERROR=@('SQLAlchemyInvalidRequestError');DEPENDENCY_UNAVAILABLE=@('ImportError')
        PROGRAMMING_ERROR=@('TypeError');VALUE_ERROR=@('ValueError');UNCLASSIFIED=@('other')
        DATABASE_CONNECTION_UNVERIFIED=@('PsycopgOperationalError')
        DATABASE_ERROR_UNCLASSIFIED=@('PsycopgError','PsycopgOperationalError','SQLAlchemyDBAPIError')
    }
    if($Failure.category -isnot [string] -or $Failure.category -cnotin @($pairs.Keys) -or
        $Failure.exception_type -cnotin $pairs[$Failure.category]){throw 'Unknown or inconsistent failure classification'}
    if($Failure.category -ceq 'SCHEMA_REQUIREMENT_UNSATISFIED' -and $Stage -cne 'database_configured'){
        throw 'Schema classification outside readiness boundary'
    }
}

function ConvertFrom-AaplAssessment {
    param([string]$Text)
    $record=ConvertFrom-Json -InputObject $Text -AsHashtable -ErrorAction Stop
    $keys=@('status','scope','ticker','company_cik','dry_run','outcome','would_insert',
        'version_before','version_after','facts_inserted','filings_published')
    if($record -isnot [Collections.IDictionary] -or
        (($record.Keys|Sort-Object)-join '|') -cne (($keys|Sort-Object)-join '|') -or
        $record.status -cne 'ASSESSED' -or $record.scope -cne 'aapl-facts-dry-run' -or
        $record.ticker -cne 'AAPL' -or $record.company_cik -cne '0000320193' -or
        $record.dry_run -isnot [bool] -or -not $record.dry_run -or
        $record.outcome -cnotin @('no_change','would_update')){throw 'Invalid worker identity'}
    foreach($key in @('would_insert','version_before','version_after','facts_inserted','filings_published')){
        if(($record[$key] -isnot [int] -and $record[$key] -isnot [long]) -or $record[$key] -lt 0){throw 'Invalid counter'}
    }
    if($record.version_before -ne $record.version_after -or $record.facts_inserted -ne 0 -or
        $record.filings_published -ne 0 -or
        (($record.outcome -ceq 'would_update') -ne ($record.would_insert -gt 0))){throw 'Invalid dry-run result'}
    return $record
}

function Open-AaplAssessmentReceipt {
    param([string]$Path)
    if(-not [IO.Path]::IsPathFullyQualified($Path) -or [IO.Path]::GetExtension($Path) -cne '.json'){
        throw 'Use a new absolute .json receipt path in an existing directory.'
    }
    $parent=[IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Path)))
    if(-not $parent.Exists){throw 'Receipt directory must already exist.'}
    while($null -ne $parent){
        if(($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Receipt directory aliases are unsupported.'}
        $parent=$parent.Parent
    }
    # CreateNew atomically refuses all existing files; no replacement or deletion.
    return [IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
}

function Invoke-AaplFactsAssessment {
    param([bool]$NetworkConsent,[string]$Destination)
    if(-not $NetworkConsent){throw 'SEC acquisition requires separate explicit approval and -AllowNetwork.'}
    if($env:FINLENS_SERVER_PROFILE -cne 'development' -or
        ($null -ne $env:FINLENS_FINANCIAL_ONLY -and $env:FINLENS_FINANCIAL_ONLY -cne '0')){
        throw 'An explicitly configured development operator process is required; no profile was changed.'
    }
    $backend=Join-Path $PSScriptRoot 'backend'
    $python=Join-Path $backend '.venv\Scripts\python.exe'
    $worker=Join-Path $backend 'scripts\assess_aapl_facts.py'
    if(-not (Test-Path -LiteralPath $python -PathType Leaf) -or
        -not (Test-Path -LiteralPath $worker -PathType Leaf)){throw 'Existing assessment prerequisites are missing; nothing was installed.'}
    $receipt=Open-AaplAssessmentReceipt $Destination
    $report=[ordered]@{scope='aapl-facts-dry-run';attempt_id=[guid]::NewGuid().ToString();
        started_utc=[datetime]::UtcNow.ToString('o');status='FAILED';code='SUPERVISOR_FAILED';
        worker_id=$null;worker_created_utc=$null;exit_code=$null;elapsed_ms=0;
        cleanup_verified=$false;worker_refusal_code=$null;last_confirmed_stage=$null;
        sec_http_attempts=$null;failure=$null;cleanup_failure=$null;result=$null}
    try{
        try{
            $run=Invoke-AaplFactsWorker -Executable $python -Directory $backend -WorkerArguments @('-I','-B',$worker,'--allow-network')
            $report.code=$run.Code;$report.worker_id=$run.WorkerId;$report.worker_created_utc=$run.CreatedUtc
            $report.exit_code=$run.ExitCode;$report.elapsed_ms=$run.ElapsedMs;$report.cleanup_verified=$run.CleanupVerified
            if($run.Code -cin @('WORKER_COMPLETED','WORKER_REFUSED')){
                try{
                    # Revalidate at the persistence boundary; never write opaque
                    # worker text, stderr or arbitrary injected dictionaries.
                    $protocol=ConvertFrom-AaplWorkerProtocol ($run.Protocol|ConvertTo-Json -Depth 5 -Compress) $run.ExitCode
                    $expectedCode=if($protocol.status -ceq 'ASSESSED'){'WORKER_COMPLETED'}else{'WORKER_REFUSED'}
                    if($run.Code -cne $expectedCode -or $run.CleanupVerified -isnot [bool] -or -not $run.CleanupVerified){throw 'Contradictory worker lifecycle'}
                    $report.worker_refusal_code=$protocol.code
                    $report.last_confirmed_stage=$protocol.last_confirmed_stage
                    $report.sec_http_attempts=$protocol.sec_http_attempts
                    $report.failure=$protocol.failure
                    $report.cleanup_failure=$protocol.cleanup_failure
                    if($protocol.status -ceq 'ASSESSED'){
                        $report.result=$protocol.result;$report.status='ASSESSED'
                    }
                }catch{$report.code='WORKER_INVALID_RECEIPT'}
            }
        }catch{} # Constant sanitized receipt even for supervisor failures.
        $report.finished_utc=[datetime]::UtcNow.ToString('o')
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($report|ConvertTo-Json -Depth 5 -Compress))
        if($bytes.Length -gt 65536){throw 'Sanitized receipt limit exceeded; no raw output retained.'}
        $receipt.Write($bytes,0,$bytes.Length);$receipt.Flush($true)
    }finally{$receipt.Dispose()}
    if($report.status -cne 'ASSESSED'){
        throw ('Assessment failed: '+$report.code+'. Receipt retained; do not retry without diagnosis.')
    }
    return [pscustomobject]$report
}

if($MyInvocation.InvocationName -ne '.'){
    $ErrorActionPreference='Stop'
    try{Invoke-AaplFactsAssessment -NetworkConsent $AllowNetwork.IsPresent -Destination $ReceiptPath}
    catch{Write-Error 'AAPL assessment refused or failed. Preserve any created receipt; private diagnostics suppressed.';exit 1}
}
