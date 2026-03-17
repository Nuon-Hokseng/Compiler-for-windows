# start-launcher.ps1  — drop this in C:\IGAutomation\
# Called by start.vbs as: powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\IGAutomation\start-launcher.ps1"

$APP_DIR  = "C:\IGAutomation"
$BACKEND  = "$APP_DIR\backend"
$FRONTEND = "$APP_DIR\frontend"
$LOG      = "$APP_DIR\launcher-log.txt"

function Write-Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    try { Add-Content -Path $LOG -Value $line -ErrorAction SilentlyContinue } catch {}
    Write-Host $line
}

# Fresh log each launch
"" | Out-File -FilePath $LOG -Encoding utf8 -Force
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
    } catch { return $false }
}

# ── If both already up, just open browser ────────────
$backendUp  = Test-Port 8000
$frontendUp = Test-Port 3000
Write-Log "Initial port check: backendUp=$backendUp, frontendUp=$frontendUp"

if ($backendUp -and $frontendUp) {
    Write-Log "Both services running — opening browser."
    Start-Process "http://localhost:3000"
    exit 0
}

# ── Kill stale listeners ─────────────────────────────
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

# ── Find npm ─────────────────────────────────────────
function Find-Npm {
    # 1. Already on PATH?
    $npmOnPath = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmOnPath) { return $npmOnPath.Source }

    # 2. Common install locations
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

    # 3. Registry lookup
    try {
        $regPath = "HKLM:\SOFTWARE\Node.js"
        if (Test-Path $regPath) {
            $installDir = (Get-ItemProperty $regPath -ErrorAction SilentlyContinue).InstallPath
            $candidate  = Join-Path $installDir "npm.cmd"
            if (Test-Path $candidate) { return $candidate }
        }
    } catch {}

    return $null
}

$npmCmd = Find-Npm
if (-not $npmCmd) {
    $msg = "npm not found. Please install Node.js from https://nodejs.org and re-run setup."
    Write-Log "[ERROR] $msg"
    [System.Windows.Forms.MessageBox]::Show($msg, "IG Automation — Error", 0, 16) | Out-Null
    exit 1
}
Write-Log "npm found: $npmCmd"

# ── Start backend ────────────────────────────────────
Write-Log "Starting backend.exe..."
$backendProc = Start-Process `
    -FilePath "$BACKEND\backend.exe" `
    -WorkingDirectory $BACKEND `
    -WindowStyle Hidden `
    -PassThru `
    -ErrorAction SilentlyContinue
if ($backendProc) {
    Write-Log "  backend PID: $($backendProc.Id)"
} else {
    Write-Log "[WARN] backend.exe failed to start."
}

# ── Start frontend ───────────────────────────────────
Write-Log "Starting frontend via npm start..."

# Verify package.json has a start script before launching
$pkgJson = "$FRONTEND\package.json"
if (Test-Path $pkgJson) {
    try {
        $pkg = Get-Content $pkgJson -Raw | ConvertFrom-Json
        if (-not $pkg.scripts.start) {
            Write-Log "[ERROR] package.json has no 'start' script."
            [System.Windows.Forms.MessageBox]::Show(
                "Frontend package.json is missing a 'start' script. Please reinstall.",
                "IG Automation — Error", 0, 16) | Out-Null
            exit 1
        }
        Write-Log "  start script: $($pkg.scripts.start)"
    } catch {
        Write-Log "[WARN] Could not parse package.json: $($_.Exception.Message)"
    }
}

# Set Playwright browser path
$env:PLAYWRIGHT_BROWSERS_PATH = "C:\IGAutomation\browsers"

# Launch npm start — visible briefly to catch startup errors, then hide
# We use cmd /c so npm.cmd is resolved even if it's a .cmd wrapper
$frontendProc = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c `"$npmCmd`" start" `
    -WorkingDirectory $FRONTEND `
    -WindowStyle Hidden `
    -PassThru `
    -ErrorAction SilentlyContinue

if ($frontendProc) {
    Write-Log "  frontend PID: $($frontendProc.Id)"
} else {
    Write-Log "[ERROR] Failed to launch frontend process."
    [System.Windows.Forms.MessageBox]::Show(
        "Failed to start the frontend. Check $LOG for details.",
        "IG Automation — Error", 0, 16) | Out-Null
    exit 1
}

# ── Wait for backend (max 60 s) ───────────────────────
Write-Log "Waiting for backend on port 8000..."
$waited = 0
while (-not (Test-Port 8000) -and $waited -lt 60) {
    Start-Sleep -Seconds 2
    $waited += 2
}
if (Test-Port 8000) {
    Write-Log "  backend ready after ${waited}s"
} else {
    Write-Log "[WARN] backend not ready after 60s — continuing anyway"
}

# ── Wait for frontend (max 120 s) ─────────────────────
Write-Log "Waiting for frontend on port 3000..."
$waited = 0
while (-not (Test-Port 3000) -and $waited -lt 120) {
    # If the frontend process has already exited, it crashed — bail early
    if ($frontendProc.HasExited) {
        Write-Log "[ERROR] Frontend process exited early (code $($frontendProc.ExitCode))."
        Write-Log "  Check for missing node_modules or a broken .next build."
        [System.Windows.Forms.MessageBox]::Show(
            "The frontend crashed on startup (exit code $($frontendProc.ExitCode)).`n`nCheck: $LOG`n`nCommon fixes:`n• Re-run setup (run-setup.bat)`n• Delete frontend\.next and reinstall",
            "IG Automation — Frontend Error", 0, 16) | Out-Null
        exit 1
    }
    Start-Sleep -Seconds 2
    $waited += 2
}

if (Test-Port 3000) {
    Write-Log "  frontend ready after ${waited}s — opening browser"
    Start-Process "http://localhost:3000"
} else {
    Write-Log "[ERROR] Frontend did not respond on port 3000 after 120s."
    [System.Windows.Forms.MessageBox]::Show(
        "The frontend did not start within 2 minutes.`n`nCheck: $LOG`n`nTry re-running setup (run-setup.bat).",
        "IG Automation — Timeout", 0, 16) | Out-Null
    exit 1
}

Write-Log "================ Launcher done ================="
