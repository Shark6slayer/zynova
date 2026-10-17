<#
.SYNOPSIS
    Automated build, deploy, launch, and verification workflow for SUPER_AI on Android Studio emulator.

.DESCRIPTION
    1. Sets up JAVA_HOME (JDK 21) and ANDROID_HOME.
    2. Builds frontend (Vite).
    3. Syncs Capacitor with Android.
    4. Compiles debug APK via Gradle wrapper.
    5. Starts emulator if not running and waits for boot completion.
    6. Installs APK via ADB.
    7. Launches com.superai.app.
    8. Verifies running activity.
    9. Captures a timestamped screenshot to C:\super_ai\artifacts\android\.
    Optional: -LiveMode to configure Vite dev server loopback temporarily.

.PARAMETER LiveMode
    Opt-in live-reload mode pointing Capacitor to host machine Vite dev server (http://10.0.2.2:5173).
    Automatically restores capacitor.config.ts upon completion or error.

.PARAMETER SkipBuild
    Skip npm build and gradle assemble if APK is already current.

.PARAMETER TimeoutSeconds
    Timeout for waiting for emulator boot (default 180s).
#>

[CmdletBinding()]
param(
    [switch]$LiveMode,
    [switch]$SkipBuild,
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

# 1. Change to project root reliably
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location -LiteralPath $ProjectRoot
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " SUPER_AI Android Development & Emulator Auto-Run   " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "[1/9] Project root verified: $ProjectRoot" -ForegroundColor Green

# 2. Configure Environment Paths
$JdkPath = "C:\super_ai\.tools\jdk21\jdk-21.0.6+7"
$SdkPath = "C:\Users\karup\AppData\Local\Android\Sdk"
$AvdName = "Medium_Phone_API_37.0"
$PackageId = "com.superai.app"
$MainActivity = "com.superai.app.MainActivity"
$ArtifactDir = Join-Path $ProjectRoot "artifacts\android"

if (-not (Test-Path $JdkPath)) {
    Write-Error "JDK 21 not found at expected path: $JdkPath"
    exit 1
}
if (-not (Test-Path $SdkPath)) {
    Write-Error "Android SDK not found at expected path: $SdkPath"
    exit 1
}

$env:JAVA_HOME = $JdkPath
$env:ANDROID_HOME = $SdkPath
$env:ANDROID_SDK_ROOT = $SdkPath

$JavaBin = Join-Path $JdkPath "bin"
$PlatformTools = Join-Path $SdkPath "platform-tools"
$EmulatorDir = Join-Path $SdkPath "emulator"

$env:Path = "$JavaBin;$PlatformTools;$EmulatorDir;$env:Path"

# 3. Verify toolchains
Write-Host "[2/9] Verifying toolchains..." -ForegroundColor Yellow

$JavaExe = Join-Path $JavaBin "java.exe"
if (-not (Test-Path $JavaExe)) {
    Write-Error "Java executable not found at $JavaExe"
    exit 1
}

try {
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $javaVerOutput = & $JavaExe -version 2>&1 | Out-String
    $ErrorActionPreference = $oldEap
    Write-Host "  Java: $(($javaVerOutput -split "`r?`n")[0].Trim())" -ForegroundColor Gray
}
catch {
    Write-Error "Failed to execute Java: $_"
    exit 1
}

$AdbExe = Join-Path $PlatformTools "adb.exe"
$EmulatorExe = Join-Path $EmulatorDir "emulator.exe"
$GradlewBat = Join-Path $ProjectRoot "android\gradlew.bat"

if (-not (Test-Path $AdbExe)) {
    Write-Error "ADB not found at $AdbExe"
    exit 1
}
if (-not (Test-Path $EmulatorExe)) {
    Write-Error "Emulator executable not found at $EmulatorExe"
    exit 1
}
if (-not (Test-Path $GradlewBat)) {
    Write-Error "Gradle wrapper not found at $GradlewBat"
    exit 1
}

# 4. Optional Live Mode Configuration Management
$CapacitorConfigPath = Join-Path $ProjectRoot "capacitor.config.ts"
$ConfigBackupPath = Join-Path $ProjectRoot "capacitor.config.ts.bak"

function Restore-Config {
    if (Test-Path $ConfigBackupPath) {
        Write-Host "Restoring original capacitor.config.ts..." -ForegroundColor Yellow
        Copy-Item -LiteralPath $ConfigBackupPath -Destination $CapacitorConfigPath -Force
        Remove-Item -LiteralPath $ConfigBackupPath -Force
        Write-Host "Restored capacitor.config.ts successfully." -ForegroundColor Green
    }
}

if ($LiveMode) {
    Write-Host "[LiveMode] Enabling Opt-in Live Reload Mode..." -ForegroundColor Magenta
    Copy-Item -LiteralPath $CapacitorConfigPath -Destination $ConfigBackupPath -Force
    
    $configContent = Get-Content -LiteralPath $CapacitorConfigPath -Raw
    # Inject dev server url into server block
    if ($configContent -match "server:\s*\{") {
        $liveConfig = $configContent -replace "server:\s*\{", "server: {`n    url: 'http://10.0.2.2:5173',`n    cleartext: true,"
        Set-Content -LiteralPath $CapacitorConfigPath -Value $liveConfig -NoNewline
        Write-Host "Configured Capacitor server.url -> http://10.0.2.2:5173" -ForegroundColor Magenta
    }
}

# 5. Build Frontend & Sync Capacitor
$ApkPath = Join-Path $ProjectRoot "android\app\build\outputs\apk\debug\app-debug.apk"

try {
    if (-not $SkipBuild) {
        Write-Host "[3/9] Building Frontend (npm run build)..." -ForegroundColor Yellow
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "npm run build failed with exit code $LASTEXITCODE"
        }

        Write-Host "[4/9] Syncing Capacitor Android (npx cap sync android)..." -ForegroundColor Yellow
        & npx cap sync android
        if ($LASTEXITCODE -ne 0) {
            throw "npx cap sync android failed with exit code $LASTEXITCODE"
        }

        Write-Host "[5/9] Assembling Android Debug APK (gradlew.bat assembleDebug)..." -ForegroundColor Yellow
        Push-Location -LiteralPath (Join-Path $ProjectRoot "android")
        try {
            & .\gradlew.bat assembleDebug
            if ($LASTEXITCODE -ne 0) {
                throw "gradlew assembleDebug failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "[3-5/9] Skipping Build as requested (-SkipBuild)..." -ForegroundColor Cyan
    }

    # 6. Verify APK exists and is non-empty
    Write-Host "[6/9] Verifying APK artifact..." -ForegroundColor Yellow
    if (-not (Test-Path -LiteralPath $ApkPath)) {
        throw "Expected APK file does not exist at: $ApkPath"
    }
    $apkItem = Get-Item -LiteralPath $ApkPath
    if ($apkItem.Length -le 1000) {
        throw "APK file is suspiciously small or empty ($($apkItem.Length) bytes) at: $ApkPath"
    }
    Write-Host "  APK Verified: $ApkPath ($([math]::Round($apkItem.Length / 1MB, 2)) MB)" -ForegroundColor Green

    # 7. Emulator Lifecycle: Check or Start
    Write-Host "[7/9] Checking Android Emulator status..." -ForegroundColor Yellow
    
    # Check if any emulator is listed in adb devices
    function Get-ConnectedEmulator {
        $devLines = & $AdbExe devices | Where-Object { $_ -match "^\s*emulator-\d+\s+device\b" }
        if ($devLines) {
            return ($devLines[0] -split "\s+")[0].Trim()
        }
        return $null
    }

    $serial = Get-ConnectedEmulator

    if (-not $serial) {
        Write-Host "No booted emulator found. Starting AVD '$AvdName'..." -ForegroundColor Cyan
        
        # Start emulator in background
        Start-Process -FilePath $EmulatorExe -ArgumentList "-avd", $AvdName, "-no-snapshot-load", "-gpu", "auto" -WindowStyle Normal
        
        Write-Host "Waiting for emulator to connect to ADB (up to $TimeoutSeconds s)..." -ForegroundColor Yellow
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
            Start-Sleep -Seconds 3
            $serial = Get-ConnectedEmulator
            if ($serial) {
                Write-Host "Emulator connected with serial: $serial" -ForegroundColor Green
                break
            }
            # Check for unauthorized / offline
            $offlineLine = & $AdbExe devices | Where-Object { $_ -match "^\s*emulator-\d+\s+(offline|unauthorized)\b" }
            if ($offlineLine) {
                Write-Host "  Emulator detected in offline/boot state: $offlineLine" -ForegroundColor Gray
            }
        }

        if (-not $serial) {
            throw "Timed out waiting for emulator ($AvdName) to appear in ADB devices."
        }
    }
    else {
        Write-Host "Reusing running emulator: $serial" -ForegroundColor Green
    }

    # Wait for device to finish booting
    Write-Host "Waiting for Android system to complete boot (sys.boot_completed=1)..." -ForegroundColor Yellow
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $bootCompleted = $false
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $bootProp = (& $AdbExe -s $serial shell getprop sys.boot_completed 2>$null).Trim()
        if ($bootProp -eq "1") {
            $bootCompleted = $true
            break
        }
        Start-Sleep -Seconds 2
    }

    if (-not $bootCompleted) {
        throw "Emulator boot completed check timed out (sys.boot_completed was not '1' within $TimeoutSeconds s)."
    }
    Write-Host "Android system boot completed successfully." -ForegroundColor Green

    # Dismiss keyguard / wake screen
    & $AdbExe -s $serial shell input keyevent 82 2>$null
    & $AdbExe -s $serial shell input keyevent 224 2>$null

    # 8. Install & Launch App
    Write-Host "[8/9] Installing and launching application ($PackageId)..." -ForegroundColor Yellow
    $installOutput = & $AdbExe -s $serial install -r $ApkPath 2>&1 | Out-String
    Write-Host "  Install output: $($installOutput.Trim())" -ForegroundColor Gray
    if ($installOutput -notmatch "Success") {
        throw "Failed to install APK: $installOutput"
    }

    # Launch main activity
    Write-Host "Launching $MainActivity..." -ForegroundColor Yellow
    $launchOutput = & $AdbExe -s $serial shell am start -n "$PackageId/$MainActivity" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER 2>&1 | Out-String
    Write-Host "  Launch output: $($launchOutput.Trim())" -ForegroundColor Gray

    Start-Sleep -Seconds 4

    # Verify Activity is in foreground
    $focusedApp = & $AdbExe -s $serial shell dumpsys window | Select-String "mCurrentFocus|mFocusedApp" | Out-String
    Write-Host "  Current window focus: $($focusedApp.Trim())" -ForegroundColor Gray
    if ($focusedApp -notmatch $PackageId) {
        Write-Warning "App $PackageId not confirmed in immediate focus, trying to bring forward..."
        & $AdbExe -s $serial shell monkey -p $PackageId -c android.intent.category.LAUNCHER 1 2>$null
        Start-Sleep -Seconds 3
    }

    # 9. Screenshot Artifact Generation & Verification
    # Force stop previous instance for fresh clean launch
    & $AdbExe -s $serial shell am force-stop $PackageId 2>$null
    Start-Sleep -Seconds 1

    # Launch main activity
    Write-Host "Launching $MainActivity..." -ForegroundColor Yellow
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $launchOutput = & $AdbExe -s $serial shell am start -n "$PackageId/$MainActivity" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER 2>&1 | Out-String
    $ErrorActionPreference = $oldEap

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $screenshotName = "screen_$timestamp.png"
    $screenshotPath = Join-Path $ArtifactDir $screenshotName
    $deviceTempPath = "/sdcard/screen_temp.png"

    & $AdbExe -s $serial shell screencap -p $deviceTempPath
    & $AdbExe -s $serial pull $deviceTempPath $screenshotPath | Out-Null
    & $AdbExe -s $serial shell rm $deviceTempPath 2>$null

    if (-not (Test-Path -LiteralPath $screenshotPath)) {
        throw "Screenshot failed to save to $screenshotPath"
    }

    $ssItem = Get-Item -LiteralPath $screenshotPath
    if ($ssItem.Length -le 1000) {
        throw "Screenshot file is empty or corrupted ($($ssItem.Length) bytes)"
    }

    Write-Host ""
    Write-Host "====================================================" -ForegroundColor Green
    Write-Host " SUCCESS: SUPER_AI Running On Android Emulator      " -ForegroundColor Green
    Write-Host "====================================================" -ForegroundColor Green
    Write-Host "  Emulator Serial : $serial" -ForegroundColor White
    Write-Host "  Package ID      : $PackageId" -ForegroundColor White
    Write-Host "  APK Path        : $ApkPath" -ForegroundColor White
    Write-Host "  Screenshot Path : $screenshotPath ($([math]::Round($ssItem.Length / 1KB, 1)) KB)" -ForegroundColor White
    Write-Host "====================================================" -ForegroundColor Green

    exit 0

} catch {
    Write-Error "Android Dev Workflow failed: $_"
    exit 1
} finally {
    if ($LiveMode) {
        Restore-Config
    }
}

