# setup.ps1 — launcher for IGAutomation
# Place in C:\IGAutomation\ (or adjust APP_DIR)
# Called by start.vbs as:
# powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\IGAutomation\setup.ps1"

$APP_DIR      = "C:\IGAutomation"
$BACKEND      = "$APP_DIR\backend"
$FRONTEND     = "$APP_DIR\frontend"
$LOG          = "$APP_DIR\launcher-log.txt"
$FRONTEND_LOG = "$APP_DIR\frontend-log.txt"

# Ensure MessageBox type is available
try { Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue } catch {}

function Write-Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    try { Add-Content -Path $LOG -Value $line -ErrorAction SilentlyContinue } catch {}
    Write-Host $line
}

function Show-Error($message, $title = "IG Automation — Error") {
    try {
        [System.Windows.Forms.MessageBox]::Show($message, $title, 0, 16) | Out-Null
    } catch {
        Write-Log "[WARN] Could not show MessageBox: $($_.Exception.Message)"
    }
}

# Fresh logs each launch
"" | Out-File -FilePath $LOG -Encoding utf8 -Force
"" | Out-File -FilePath $FRONTEND_LOG -Encoding utf8 -Force

Write-Log "================ Launcher start ================"
Write-Log "BACKEND=$BACKEND"
Write-Log "FRONTEND=$FRONTEND"

# ── Port check helper ─────────────────────────────────
function Test-Port($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

# ── Find npm ─────────────────────────────────────────
function Find-Npm {
    # 1) On PATH
    $npmOnPath = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmOnPath) { return $npmOnPath.Source }

    # 2) Common install locations
    $candidates = @(
        "$env:PROGRAMFILES\nodejs\npm.cmd",
        "${env:ProgramFiles(x86)}\nodejs\npm.cmd",
        "$env:LOCALAPPDATA\Programs\nodejs\npm.cmd",
        "$env:APPDATA\npm\npm.cmd",
        "C:\Program Files\nodejs\npm.cmd"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }

    # 3) Registry
    try {
        $regPath = "HKLM:\SOFTWARE\Node.js"
        if (Test-Path $regPath) {
            $installDir = (Get-ItemProperty $regPath -ErrorAction SilentlyContinue).InstallPath
            if ($installDir) {
                $candidate = Join-Path $installDir "npm.cmd"
                if (Test-Path $candidate) { return $candidate }
            }
        }
    } catch {}

    return $null
}

# ── Initial health check ─────────────────────────────
$backendUp  = [bool](Test-Port 8000)
$frontendUp = [bool](Test-Port 3000)
Write-Log "Initial port check: backendUp=$backendUp, frontendUp=$frontendUp"

if ($backendUp -and $frontendUp) {
    Write-Log "Both services already running — opening browser and exiting."
    Start-Process "http://localhost:3000"
    exit 0
}

# ── Kill stale listeners only if stack not fully healthy ─────────
Write-Log "Killing stale listeners on 3000/8000 (if any)..."
@(3000, 8000) | ForEach-Object {
    $port = $_
    try {
        $pids = (netstat -ano | Select-String ":$port ") |
            Where-Object { $_ -match 'LISTENING' } |
            ForEach-Object { ($_ -split '\s+')[-1] } |
            Select-Object -Unique

        foreach ($p in $pids) {
            if ($p -match '^\d+$') {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                Write-Log "  Killed PID $p (port $port)"
            }
        }
    } catch {}
}
Start-Sleep -Seconds 1

# ── Validate paths ───────────────────────────────────
if (-not (Test-Path "$BACKEND\backend.exe")) {
    $msg = "Missing backend executable: $BACKEND\backend.exe"
    Write-Log "[ERROR] $msg"
    Show-Error $msg
    exit 1
}

if (-not (Test-Path $FRONTEND)) {
    $msg = "Missing frontend folder: $FRONTEND"
    Write-Log "[ERROR] $msg"
    Show-Error $msg
    exit 1
}

$npmCmd = Find-Npm
if (-not $npmCmd) {
    $msg = "npm not found. Please install Node.js from https://nodejs.org and re-run setup."
    Write-Log "[ERROR] $msg"
    Show-Error $msg
    exit 1
}
Write-Log "npm found: $npmCmd"

# ── Validate frontend package.json start script ─────
$pkgJson = "$FRONTEND\package.json"
if (-not (Test-Path $pkgJson)) {
    $msg = "Missing package.json in frontend folder: $pkgJson"
    Write-Log "[ERROR] $msg"
    Show-Error $msg
    exit 1
}

try {
    $pkg = Get-Content $pkgJson -Raw | ConvertFrom-Json
    if (-not $pkg.scripts -or -not $pkg.scripts.start) {
        $msg = "Frontend package.json is missing a 'start' script. Please reinstall."
        Write-Log "[ERROR] $msg"
        Show-Error $msg
        exit 1
    }
    Write-Log "Frontend start script: $($pkg.scripts.start)"
} catch {
    $msg = "Could not parse package.json: $($_.Exception.Message)"
    Write-Log "[ERROR] $msg"
    Show-Error $msg
    exit 1
}

# Set Playwright browser path (if used by frontend)
$env:PLAYWRIGHT_BROWSERS_PATH = "$APP_DIR\browsers"

# ── Start backend ────────────────────────────────────
Write-Log "Starting backend.exe..."
$backendProc = Start-Process `
    -FilePath "$BACKEND\backend.exe" `
    -WorkingDirectory $BACKEND `
    -WindowStyle Hidden `
    -PassThru `
    -ErrorAction SilentlyContinue

if ($backendProc) {
    Write-Log "backend PID: $($backendProc.Id)"
} else {
    Write-Log "[ERROR] backend.exe failed to start."
    Show-Error "Failed to start backend.exe. Check launcher log: $LOG"
    exit 1
}

# ── Start frontend with output redirection ───────────
Write-Log "Starting frontend via npm start..."
$frontendProc = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c `"$npmCmd`" start >> `"$FRONTEND_LOG`" 2>&1" `
    -WorkingDirectory $FRONTEND `
    -WindowStyle Hidden `
    -PassThru `
    -ErrorAction SilentlyContinue

if ($frontendProc) {
    Write-Log "frontend PID: $($frontendProc.Id)"
    Write-Log "frontend log: $FRONTEND_LOG"
} else {
    Write-Log "[ERROR] Failed to launch frontend process."
    Show-Error "Failed to start frontend. Check logs:`n$LOG`n$FRONTEND_LOG"
    exit 1
}

# ── Wait for backend (max 60s) ───────────────────────
Write-Log "Waiting for backend on port 8000..."
$waited = 0
while (-not (Test-Port 8000) -and $waited -lt 60) {
    Start-Sleep -Seconds 2
    $waited += 2
}
if (Test-Port 8000) {
    Write-Log "backend ready after ${waited}s"
} else {
    Write-Log "[WARN] backend not ready after 60s — continuing anyway"
}

# ── Wait for frontend (max 120s) ─────────────────────
Write-Log "Waiting for frontend on port 3000..."
$waited = 0
while (-not (Test-Port 3000) -and $waited -lt 120) {
    if ($frontendProc.HasExited) {
        Write-Log "[ERROR] Frontend process exited early (code $($frontendProc.ExitCode))."
        Write-Log "Check frontend log: $FRONTEND_LOG"
        Show-Error "Frontend crashed on startup (exit code $($frontendProc.ExitCode)).`n`nCheck:`n$FRONTEND_LOG`n`nCommon fixes:`n• Re-run setup`n• Delete frontend\.next and reinstall node_modules" "IG Automation — Frontend Error"
        exit 1
    }
    Start-Sleep -Seconds 2
    $waited += 2
}

if (Test-Port 3000) {
    Write-Log "frontend ready after ${waited}s — opening browser"
    Start-Process "http://localhost:3000"
} else {
    Write-Log "[ERROR] Frontend did not respond on port 3000 after 120s."
    Write-Log "Check frontend log: $FRONTEND_LOG"
    Show-Error "Frontend did not start within 2 minutes.`n`nCheck:`n$FRONTEND_LOG`n`nTry re-running setup." "IG Automation — Timeout"
    exit 1
}

Write-Log "================ Launcher done ================="
exit 0
