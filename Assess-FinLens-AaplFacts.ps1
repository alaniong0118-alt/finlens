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
    $workerId=$null;$createdUtc=$null;$cleanup=$false;$stdout=$null
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
        if($exitCode -ne 0){$code='WORKER_REFUSED'}
        elseif($streams[1].Count -ne 0){$code='WORKER_DIAGNOSTICS_REFUSED'}
        else{
            $code='WORKER_INVALID_RECEIPT'
            $stdout=[Text.UTF8Encoding]::new($false,$true).GetString($streams[0].Bytes.ToArray())
            $code='WORKER_COMPLETED'
        }
    } catch { $stdout=$null } # Never retain exception text or raw diagnostics.
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
    if(-not $cleanup){$code='WORKER_CLEANUP_UNVERIFIED';$stdout=$null}
    [pscustomobject]@{Code=$code;ExitCode=$exitCode;WorkerId=$workerId;CreatedUtc=$createdUtc;
        CleanupVerified=$cleanup;ElapsedMs=$clock.ElapsedMilliseconds;Output=$stdout}
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
        cleanup_verified=$false;result=$null}
    try{
        try{
            $run=Invoke-AaplFactsWorker -Executable $python -Directory $backend -WorkerArguments @('-I','-B',$worker,'--allow-network')
            $report.code=$run.Code;$report.worker_id=$run.WorkerId;$report.worker_created_utc=$run.CreatedUtc
            $report.exit_code=$run.ExitCode;$report.elapsed_ms=$run.ElapsedMs;$report.cleanup_verified=$run.CleanupVerified
            if($run.Code -ceq 'WORKER_COMPLETED'){
                try{
                    $report.result=ConvertFrom-AaplAssessment $run.Output
                    $report.status='ASSESSED'
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
