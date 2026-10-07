param(
    [string]$ProjectRoot = "D:\Projects\finlens-foundation",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$StopDatabase
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Get-ListenerProcess {
    param([int]$Port)

    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $conn) {
        return $null
    }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue

    [PSCustomObject]@{
        Port        = $Port
        PID         = $conn.OwningProcess
        ProcessName = $proc.Name
        CommandLine = $proc.CommandLine
    }
}

function Stop-FinLensProcess {
    param(
        [int]$Port,
        [string]$ExpectedKind,
        [string]$ProjectRoot
    )

    $info = Get-ListenerProcess -Port $Port

    if (-not $info) {
        Write-Host "Nothing is listening on port $Port."
        return
    }

    $command = [string]$info.CommandLine
    $rootMatch = $command -like "*finlens-foundation*"

    $kindMatch = $false
    if ($ExpectedKind -eq "backend") {
        $kindMatch = ($command -match "uvicorn") -and ($command -match "app\.main:app")
    }
    elseif ($ExpectedKind -eq "frontend") {
        $kindMatch = ($command -match "next") -or ($command -match "npm")
    }

    Write-Host "Port $Port is owned by PID $($info.PID) ($($info.ProcessName))."
    Write-Host "Command: $command"

    if (-not ($rootMatch -and $kindMatch)) {
        Write-Host "Skipped: this process does not look like the expected FinLens $ExpectedKind process." -ForegroundColor Yellow
        return
    }

    Write-Host "Stopping FinLens $ExpectedKind process PID $($info.PID)..."
    Stop-Process -Id $info.PID -Force
    Write-Host "Stopped." -ForegroundColor Green
}

Write-Host "FinLens Environment Stopper" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"

if (-not (Test-Path $ProjectRoot)) {
    throw "Project root does not exist: $ProjectRoot"
}

Write-Step "Stopping backend"
Stop-FinLensProcess -Port $BackendPort -ExpectedKind "backend" -ProjectRoot $ProjectRoot

Write-Step "Stopping frontend"
Stop-FinLensProcess -Port $FrontendPort -ExpectedKind "frontend" -ProjectRoot $ProjectRoot

if ($StopDatabase) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker CLI not found; PostgreSQL was not stopped." -ForegroundColor Yellow
    }
    else {
        Write-Step "Stopping PostgreSQL"
        Push-Location $ProjectRoot
        try {
            docker compose stop postgres
            if ($LASTEXITCODE -ne 0) {
                throw "docker compose stop postgres failed."
            }
        }
        finally {
            Pop-Location
        }
    }
}
else {
    Write-Host "`nPostgreSQL was left running." -ForegroundColor Yellow
    Write-Host "Use -StopDatabase if you also want to stop the postgres container."
}

Write-Host "`nFinLens stop sequence complete." -ForegroundColor Green
