$dbPath = "C:\super_ai\.data\db"
if (-not (Test-Path $dbPath)) {
    New-Item -ItemType Directory -Path $dbPath -Force | Out-Null
}
$logPath = "C:\super_ai\.data\mongod.log"
$mongodExe = "C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe"

$existing = Get-Process -Name mongod -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "mongod is already running with PID: $($existing.Id)"
} else {
    Write-Host "Starting mongod with dbpath: $dbPath"
    Start-Process -FilePath $mongodExe -ArgumentList "--dbpath `"$dbPath`" --logpath `"$logPath`" --bind_ip 127.0.0.1 --port 27017" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

$conn = Get-NetTCPConnection -LocalPort 27017 -ErrorAction SilentlyContinue
if ($conn) {
    Write-Host "MongoDB Server is LISTENING on port 27017 (PID: $($conn.OwningProcess))"
} else {
    Write-Error "Failed to connect to MongoDB on port 27017"
    if (Test-Path $logPath) {
        Get-Content $logPath -Tail 20
    }
}
