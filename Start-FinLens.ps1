param(
    [string]$ProjectRoot = "D:\Projects\finlens-foundation",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Get-ListenerInfo {
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

function Start-FinLensWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $escapedDirectory = $WorkingDirectory.Replace("'", "''")
    $windowCommand = @"
`$Host.UI.RawUI.WindowTitle = '$Title'
Set-Location '$escapedDirectory'
$Command
"@

    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $windowCommand
    ) | Out-Null
}

Write-Host "FinLens Environment Launcher" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"

if (-not (Test-Path $ProjectRoot)) {
    throw "Project root does not exist: $ProjectRoot"
}

$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $BackendDir)) {
    throw "Backend directory not found: $BackendDir"
}

if (-not (Test-Path $FrontendDir)) {
    throw "Frontend directory not found: $FrontendDir"
}

if (-not (Test-Path $PythonExe)) {
    throw "Backend virtual environment Python not found: $PythonExe"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Start Docker Desktop first."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found in PATH."
}

Write-Step "Starting PostgreSQL"
Push-Location $ProjectRoot
try {
    docker compose up -d postgres
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up -d postgres failed."
    }

    docker compose ps
}
finally {
    Pop-Location
}

Write-Step "Checking backend port $BackendPort"
$backendListener = Get-ListenerInfo -Port $BackendPort

if ($backendListener) {
    Write-Host "Port $BackendPort is already listening." -ForegroundColor Yellow
    Write-Host "PID: $($backendListener.PID)"
    Write-Host "Process: $($backendListener.ProcessName)"
    Write-Host "Command: $($backendListener.CommandLine)"
    Write-Host "Backend launch skipped to avoid killing or replacing an existing process." -ForegroundColor Yellow
}
else {
    Write-Host "Starting FinLens backend..."
    Start-FinLensWindow `
        -Title "FinLens Backend :$BackendPort" `
        -WorkingDirectory $BackendDir `
        -Command ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort"
}

Write-Step "Checking frontend port $FrontendPort"
$frontendListener = Get-ListenerInfo -Port $FrontendPort

if ($frontendListener) {
    Write-Host "Port $FrontendPort is already listening." -ForegroundColor Yellow
    Write-Host "PID: $($frontendListener.PID)"
    Write-Host "Process: $($frontendListener.ProcessName)"
    Write-Host "Command: $($frontendListener.CommandLine)"
    Write-Host "Frontend launch skipped to avoid killing or replacing an existing process." -ForegroundColor Yellow
}
else {
    Write-Host "Starting FinLens frontend..."
    Start-FinLensWindow `
        -Title "FinLens Frontend :$FrontendPort" `
        -WorkingDirectory $FrontendDir `
        -Command "npm run dev -- --hostname 127.0.0.1 --port $FrontendPort"
}

Write-Step "FinLens startup commands launched"

$HealthUrl = "http://127.0.0.1:$BackendPort/healthz"
$AppUrl = "http://127.0.0.1:$FrontendPort"

Write-Host "Backend health: $HealthUrl"
Write-Host "Frontend app:   $AppUrl"

if (-not $NoBrowser) {
    Write-Host "Opening FinLens in your browser in a few seconds..."
    Start-Sleep -Seconds 5
    Start-Process $AppUrl
}

Write-Host "`nYou can close this launcher window. Backend and frontend run in their own PowerShell windows." -ForegroundColor Green
