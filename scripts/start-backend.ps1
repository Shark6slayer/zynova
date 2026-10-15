<#
.SYNOPSIS
    Starts MongoDB (if not running) and the SUPER_AI FastAPI backend server.

.DESCRIPTION
    1. Sets directory to C:\super_ai\backend.
    2. Verifies Python virtual environment at C:\super_ai\backend\venv.
    3. Checks and launches MongoDB on 127.0.0.1:27017 using local .data\db store.
    4. Verifies database connectivity.
    5. Checks if backend is already running on port 8000.
    6. Starts FastAPI backend with uvicorn app.main:app on 127.0.0.1:8000.
    7. Verifies health endpoint at http://127.0.0.1:8000/api/v1/health.

.PARAMETER Port
    Port to bind FastAPI (default 8000).

.PARAMETER Host
    Host address to bind FastAPI (default 127.0.0.1).
#>

[CmdletBinding()]
param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvPython = Join-Path $BackendDir "venv\Scripts\python.exe"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " SUPER_AI Backend & Database Startup Service        " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Verify Virtual Environment
if (-not (Test-Path $VenvPython)) {
    Write-Error "Python virtual environment not found at $VenvPython"
    exit 1
}
Write-Host "[1/5] Python venv verified: $VenvPython" -ForegroundColor Green

# 2. Check / Start MongoDB Server
Write-Host "[2/5] Checking MongoDB database server..." -ForegroundColor Yellow
$mongoPort = 27017
$mongoConn = Get-NetTCPConnection -LocalPort $mongoPort -ErrorAction SilentlyContinue

if (-not $mongoConn) {
    Write-Host "  MongoDB not listening on port $mongoPort. Launching MongoDB server..." -ForegroundColor Yellow
    $dbPath = Join-Path $ProjectRoot ".data\db"
    $logPath = Join-Path $ProjectRoot ".data\mongod.log"
    if (-not (Test-Path $dbPath)) {
        New-Item -ItemType Directory -Path $dbPath -Force | Out-Null
    }
    
    $mongodExe = "C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe"
    if (-not (Test-Path $mongodExe)) {
        Write-Error "mongod.exe not found at $mongodExe"
        exit 1
    }

    Start-Process -FilePath $mongodExe -ArgumentList "--dbpath `"$dbPath`" --bind_ip 127.0.0.1 --port $mongoPort --logpath `"$logPath`"" -WindowStyle Hidden
    
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $mongoReady = $false
    while ($sw.Elapsed.TotalSeconds -lt 15) {
        Start-Sleep -Seconds 1
        $mongoConn = Get-NetTCPConnection -LocalPort $mongoPort -ErrorAction SilentlyContinue
        if ($mongoConn) {
            $mongoReady = $true
            break
        }
    }

    if (-not $mongoReady) {
        Write-Error "Timed out waiting for MongoDB to start on port $mongoPort."
        exit 1
    }
    Write-Host "  MongoDB Server started on 127.0.0.1:$mongoPort (PID: $($mongoConn.OwningProcess))" -ForegroundColor Green
} else {
    Write-Host "  MongoDB Server is already RUNNING on 127.0.0.1:$mongoPort (PID: $($mongoConn.OwningProcess))" -ForegroundColor Green
}

# 3. Check if backend port is already in use
Write-Host "[3/5] Checking backend port $Port..." -ForegroundColor Yellow
$backendConn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($backendConn) {
    Write-Host "  Port $Port is already in use by PID $($backendConn.OwningProcess)." -ForegroundColor Yellow
    try {
        $health = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/api/v1/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($health.status -eq "healthy") {
            Write-Host "  SUPER_AI Backend is already healthy and listening at http://${HostAddress}:${Port}/" -ForegroundColor Green
            Write-Host "  API Prefix : http://${HostAddress}:${Port}/api/v1" -ForegroundColor White
            Write-Host "  Docs       : http://${HostAddress}:${Port}/docs" -ForegroundColor White
            exit 0
        }
    } catch {
        Write-Warning "  Existing process on port $Port is not responding to health check."
    }
}

# 4. Start FastAPI backend with uvicorn
Write-Host "[4/5] Starting FastAPI backend on http://${HostAddress}:${Port}..." -ForegroundColor Yellow
Set-Location -LiteralPath $BackendDir

$backendProcess = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", "$Port", "--reload" `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -WindowStyle Normal

# 5. Verify Health Endpoint
Write-Host "[5/5] Waiting for backend to become healthy..." -ForegroundColor Yellow
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$isHealthy = $false

while ($sw.Elapsed.TotalSeconds -lt 20) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/api/v1/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($health -and $health.status -eq "healthy") {
            $isHealthy = $true
            break
        }
    } catch {
        # Waiting for server boot
    }
}

if (-not $isHealthy) {
    Write-Error "Backend failed to report healthy status within 20 seconds."
    exit 1
}

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host " SUPER_AI Backend is OPERATIONAL                    " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host "  Process ID  : $($backendProcess.Id)" -ForegroundColor White
Write-Host "  Local URL   : http://${HostAddress}:${Port}/" -ForegroundColor White
Write-Host "  API Prefix  : http://${HostAddress}:${Port}/api/v1" -ForegroundColor White
Write-Host "  Health URL  : http://${HostAddress}:${Port}/api/v1/health" -ForegroundColor White
Write-Host "  Ready URL   : http://${HostAddress}:${Port}/api/v1/ready" -ForegroundColor White
Write-Host "  Swagger UI  : http://${HostAddress}:${Port}/docs" -ForegroundColor White
Write-Host "  MongoDB     : mongodb://127.0.0.1:27017 (super_ai_db)" -ForegroundColor White
Write-Host "  Android Emu : http://10.0.2.2:${Port}/api/v1" -ForegroundColor White
Write-Host "====================================================" -ForegroundColor Green

exit 0
