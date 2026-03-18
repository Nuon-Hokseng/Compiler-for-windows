# Force execution policy for this session
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = "Continue"

$APP_DIR  = "C:\IGAutomation"
$BACKEND  = "$APP_DIR\backend"
$FRONTEND = "$APP_DIR\frontend"
$LOG      = "$APP_DIR\setup-log.txt"

function Write-Log($msg, $color = "White") {
    $ts   = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $LOG -Value $line -ErrorAction SilentlyContinue
}

function Write-Step($msg) {
    Write-Log ""
    Write-Log ">> $msg" "Cyan"
}

"" | Out-File -FilePath $LOG -Encoding utf8 -Force

Write-Log "================================================" "Magenta"
Write-Log "  IG Automation - Setup" "Magenta"
Write-Log "================================================"
Write-Log "APP_DIR  = $APP_DIR"
Write-Log "Log file = $LOG"

# ── VERIFY INSTALL ───────────────────────────────────
if (-not (Test-Path $APP_DIR)) {
    Write-Log "[ERROR] $APP_DIR not found. Please reinstall." "Red"
    exit 1
}
if (-not (Test-Path "$BACKEND\backend.exe")) {
    Write-Log "[ERROR] backend.exe missing. Please reinstall." "Red"
    exit 1
}
if (-not (Test-Path "$FRONTEND\.next")) {
    Write-Log "[ERROR] Frontend .next folder missing. Please reinstall." "Red"
    exit 1
}
Write-Log "[OK] Install verified." "Green"

# ── STEP 1: NODE.JS ──────────────────────────────────
Write-Step "[Step 1/3] Checking Node.js..."

$hasNode = $null
try { $hasNode = & node --version 2>&1 } catch {}

if (-not $hasNode -or $hasNode -notmatch "v\d") {
    foreach ($nodePath in @(
        "$env:PROGRAMFILES\nodejs\node.exe",
        "$env:ProgramFiles(x86)\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
    )) {
        if (Test-Path $nodePath) {
            $env:PATH = "$env:PATH;$(Split-Path $nodePath)"
            try { $hasNode = & node --version 2>&1 } catch {}
            if ($hasNode -match "v\d") { break }
        }
    }
}

if (-not $hasNode -or $hasNode -notmatch "v\d") {
    Write-Log "   Node.js not found. Downloading..." "Yellow"
    $nodeInstaller = "$env:TEMP\node-lts-x64.msi"
    $nodeUrl       = "https://nodejs.org/dist/v20.19.0/node-v20.19.0-x64.msi"

    & curl.exe -L --silent --show-error --output $nodeInstaller $nodeUrl
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $nodeInstaller) -or (Get-Item $nodeInstaller).Length -lt 1000000) {
        Write-Log "[ERROR] Failed to download Node.js." "Red"
        Write-Log "   Install manually from https://nodejs.org then re-run setup." "Red"
        exit 1
    }

    Write-Log "   Installing Node.js silently..." "Yellow"
    $proc = Start-Process "msiexec.exe" -ArgumentList "/i `"$nodeInstaller`" /quiet /norestart ADDLOCAL=ALL" -Wait -PassThru
    Remove-Item $nodeInstaller -ErrorAction SilentlyContinue

    if ($proc.ExitCode -notin @(0, 1641, 3010)) {
        Write-Log "[ERROR] Node.js install failed (exit $($proc.ExitCode))" "Red"
        exit 1
    }

    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    Start-Sleep -Seconds 3
}

try { $hasNode = & node --version 2>&1 } catch {}
if (-not $hasNode -or $hasNode -notmatch "v\d") {
    Write-Log "[ERROR] Node.js still not found. Restart and re-run setup." "Red"
    exit 1
}
Write-Log "[OK] Node: $hasNode" "Green"

# Ensure npm on PATH
foreach ($p in @(
    "$env:PROGRAMFILES\nodejs",
    "$env:APPDATA\npm",
    "$env:LOCALAPPDATA\Programs\nodejs"
)) {
    if ($p -and (Test-Path "$p\npm.cmd") -and $env:PATH -notlike "*$p*") {
        $env:PATH = "$env:PATH;$p"
    }
}
try { Write-Log "[OK] npm: $(& npm --version 2>&1)" "Green" } catch {}

# ── STEP 2: CONFIGURE FRONTEND ───────────────────────
Write-Step "[Step 2/3] Configuring frontend..."
Set-Location $FRONTEND

$utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

$loadEnvContent = @'
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');
const SECRET_KEY = '9cbfcce635d1160bf8fd4143a322ef1c1edebc84749ae1d34bcb167347754406';
const ENC_PATH   = path.join(__dirname, '.env.enc');
function loadEnv() {
    if (!fs.existsSync(ENC_PATH)) { console.error('[load-env] .env.enc not found'); process.exit(1); }
    const enc    = Buffer.from(fs.readFileSync(ENC_PATH).toString().trim(), 'base64');
    const keyBuf = crypto.createHash('sha256').update(SECRET_KEY).digest();
    const plain  = Buffer.alloc(enc.length);
    for (let i = 0; i < enc.length; i++) plain[i] = enc[i] ^ keyBuf[i % keyBuf.length];
    let loaded = 0;
    for (const line of plain.toString('utf8').split('\n')) {
        const t = line.trim();
        if (!t || t.startsWith('#') || !t.includes('=')) continue;
        const [k, ...rest] = t.split('=');
        const key = k.trim();
        const val = rest.join('=').trim().replace(/^["']|["']$/g, '');
        if (key && !(key in process.env)) { process.env[key] = val; loaded++; }
    }
    console.log('[load-env] ' + loaded + ' vars loaded');
}
loadEnv();
module.exports = {};
'@
[System.IO.File]::WriteAllText("$FRONTEND\load-env.js", $loadEnvContent, $utf8NoBOM)
Write-Log "   load-env.js written."

foreach ($cfgFile in @("$FRONTEND\next.config.js", "$FRONTEND\next.config.ts")) {
    if (Test-Path $cfgFile) {
        $cfgContent = Get-Content $cfgFile -Raw
        if ($cfgContent -notmatch "load-env") {
            [System.IO.File]::WriteAllText($cfgFile, "require('./load-env');`n" + $cfgContent, $utf8NoBOM)
            Write-Log "   Patched $(Split-Path $cfgFile -Leaf)"
        }
        break
    }
}

if (Test-Path "$FRONTEND\node_modules") {
    Write-Log "[OK] node_modules pre-bundled - no install needed." "Green"
} else {
    Write-Log "   node_modules missing - running npm install..." "Yellow"
    & npm install --silent 2>&1 | Out-Null
    Write-Log "[OK] npm install complete." "Green"
}

# ── PLAYWRIGHT ───────────────────────────────────────
$PW_BROWSERS = "C:\IGAutomation\browsers"
[System.Environment]::SetEnvironmentVariable("PLAYWRIGHT_BROWSERS_PATH", $PW_BROWSERS, "Machine")
$env:PLAYWRIGHT_BROWSERS_PATH = $PW_BROWSERS

$chromiumDirs = Get-ChildItem -Path $PW_BROWSERS -Filter "chromium-*" -Directory -ErrorAction SilentlyContinue
if ($chromiumDirs) {
    Write-Log "[OK] Chromium pre-bundled: $($chromiumDirs[0].Name)" "Green"
} else {
    Write-Log "[WARN] Chromium not found in bundle. Downloading..." "Yellow"
    if (-not (Test-Path $PW_BROWSERS)) { New-Item -ItemType Directory -Path $PW_BROWSERS -Force | Out-Null }

    $pyExe = $null
    foreach ($p in @("python","python3",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:PROGRAMFILES\Python312\python.exe",
        "C:\Python312\python.exe"
    )) {
        try { $v = & $p --version 2>&1; if ($v -match "3\.(11|12|13)") { $pyExe = $p; break } } catch {}
    }

    $chromiumOk = $false
    if ($pyExe) {
        & $pyExe -m pip install playwright --quiet 2>&1 | Out-Null
        & $pyExe -m playwright install chromium
        if ($LASTEXITCODE -eq 0) { $chromiumOk = $true; Write-Log "[OK] Chromium installed via Python." "Green" }
    }

    if (-not $chromiumOk) {
        & npm install playwright --no-save 2>&1 | Out-Null
        $pwCmd = "$FRONTEND\node_modules\.bin\playwright.cmd"
        if (Test-Path $pwCmd) {
            & $pwCmd install chromium
            if ($LASTEXITCODE -eq 0) { $chromiumOk = $true; Write-Log "[OK] Chromium installed via npm." "Green" }
        }
    }

    if (-not $chromiumOk) { Write-Log "[WARN] Chromium not installed - will attempt on first use." "Yellow" }
}

# ── STEP 3: CREATE LAUNCHERS ─────────────────────────
Write-Step "[Step 3/3] Creating launchers, scheduled task and Desktop shortcut..."

# Bake npm path at setup time so it works on any machine
$npmBaked = "npm"
foreach ($candidate in @(
    "$env:PROGRAMFILES\nodejs\npm.cmd",
    "$env:ProgramFiles(x86)\nodejs\npm.cmd",
    "$env:LOCALAPPDATA\Programs\nodejs\npm.cmd",
    "$env:APPDATA\npm\npm.cmd"
)) {
    if (Test-Path $candidate) { $npmBaked = $candidate; break }
}
Write-Log "   npm baked path: $npmBaked" "Green"

# ── start-services.bat ───────────────────────────────
# Inspired by the original working approach - straightforward, no temp files
# Uses PowerShell Start-Process for hidden windows instead of cmd /k
$startBat = @"
@echo off
set LOG=C:\IGAutomation\launcher-log.txt
set PLAYWRIGHT_BROWSERS_PATH=C:\IGAutomation\browsers

echo [%TIME%] ===== start-services.bat ===== >> "%LOG%"

:: ── Find npm ──────────────────────────────────────
set NPM_CMD=
if exist "$npmBaked" ( set "NPM_CMD=$npmBaked" & goto npm_ok )
if exist "%ProgramFiles%\nodejs\npm.cmd" ( set "NPM_CMD=%ProgramFiles%\nodejs\npm.cmd" & goto npm_ok )
if exist "%ProgramFiles(x86)%\nodejs\npm.cmd" ( set "NPM_CMD=%ProgramFiles(x86)%\nodejs\npm.cmd" & goto npm_ok )
if exist "%LOCALAPPDATA%\Programs\nodejs\npm.cmd" ( set "NPM_CMD=%LOCALAPPDATA%\Programs\nodejs\npm.cmd" & goto npm_ok )
if exist "%APPDATA%\npm\npm.cmd" ( set "NPM_CMD=%APPDATA%\npm\npm.cmd" & goto npm_ok )
where npm >nul 2>&1
if %errorlevel%==0 ( set NPM_CMD=npm & goto npm_ok )
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Node.js" /v InstallPath 2^>nul') do (
    if exist "%%b\npm.cmd" ( set "NPM_CMD=%%b\npm.cmd" & goto npm_ok )
)
echo [%TIME%] [ERROR] npm not found >> "%LOG%"
exit /b 1

:npm_ok
echo [%TIME%] npm=%NPM_CMD% >> "%LOG%"

:: ── Kill stale processes on 8000 and 3000 ─────────
echo [%TIME%] Killing stale processes... >> "%LOG%"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul

:: ── Start backend hidden via PowerShell ───────────
echo [%TIME%] Starting backend... >> "%LOG%"
powershell -NoProfile -WindowStyle Hidden -Command ^
  "Start-Process -FilePath 'C:\IGAutomation\backend\backend.exe' ^
   -WorkingDirectory 'C:\IGAutomation\backend' ^
   -WindowStyle Hidden ^
   -RedirectStandardOutput 'C:\IGAutomation\backend-out.txt' ^
   -RedirectStandardError 'C:\IGAutomation\backend-err.txt'"
echo [%TIME%] Backend process started >> "%LOG%"

:: ── Start frontend hidden via PowerShell ──────────
echo [%TIME%] Starting frontend... >> "%LOG%"
powershell -NoProfile -WindowStyle Hidden -Command ^
  "Start-Process -FilePath '%NPM_CMD%' ^
   -ArgumentList 'run','start' ^
   -WorkingDirectory 'C:\IGAutomation\frontend' ^
   -WindowStyle Hidden ^
   -RedirectStandardOutput 'C:\IGAutomation\frontend-out.txt' ^
   -RedirectStandardError 'C:\IGAutomation\frontend-err.txt'"
echo [%TIME%] Frontend process started >> "%LOG%"

echo [%TIME%] Both services launched >> "%LOG%"
"@
[System.IO.File]::WriteAllText("$APP_DIR\start-services.bat", $startBat, $utf8NoBOM)
Write-Log "   start-services.bat written." "Green"

# ── open-app.bat ─────────────────────────────────────
# Inspired by original: simple netstat loop, open browser when ready
$openBat = @"
@echo off
set LOG=C:\IGAutomation\launcher-log.txt
echo [%TIME%] ===== open-app.bat ===== >> "%LOG%"

:: ── Fast path: both already up ────────────────────
netstat -an | findstr ":3000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    netstat -an | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
    if %errorlevel%==0 (
        echo [%TIME%] Both ports up - opening browser >> "%LOG%"
        start "" "http://localhost:3000"
        exit /b 0
    )
)

:: ── Services not running - start them ─────────────
echo [%TIME%] Starting services >> "%LOG%"
call "C:\IGAutomation\start-services.bat"

:: ── Wait for backend on port 8000 ─────────────────
echo [%TIME%] Waiting for backend on port 8000... >> "%LOG%"
:wait_backend
timeout /t 2 /nobreak >nul
netstat -an | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto wait_backend
echo [%TIME%] Backend ready >> "%LOG%"

:: ── Wait for frontend on port 3000 ────────────────
echo [%TIME%] Waiting for frontend on port 3000... >> "%LOG%"
:wait_frontend
timeout /t 2 /nobreak >nul
netstat -an | findstr ":3000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto wait_frontend
echo [%TIME%] Frontend ready - opening browser >> "%LOG%"

start "" "http://localhost:3000"
"@
[System.IO.File]::WriteAllText("$APP_DIR\open-app.bat", $openBat, $utf8NoBOM)
Write-Log "   open-app.bat written." "Green"

# ── start.vbs (silent wrapper for shortcut) ──────────
$launchVbs = @"
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd /c C:\IGAutomation\open-app.bat", 0, False
"@
[System.IO.File]::WriteAllText("$APP_DIR\start.vbs", $launchVbs, $utf8NoBOM)
Write-Log "   start.vbs written." "Green"

# ── silent-start.vbs (for scheduled task) ────────────
$silentVbs = @"
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd /c C:\IGAutomation\start-services.bat", 0, False
"@
[System.IO.File]::WriteAllText("$APP_DIR\silent-start.vbs", $silentVbs, $utf8NoBOM)
Write-Log "   silent-start.vbs written." "Green"

# ── Scheduled task: auto-start services at logon ─────
$currentUser = "$env:USERDOMAIN\$env:USERNAME"
Write-Log "   Registering scheduled task for: $currentUser" "Yellow"

Unregister-ScheduledTask -TaskName "IGAutomation-Startup" -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "`"C:\IGAutomation\silent-start.vbs`"" `
    -WorkingDirectory $APP_DIR

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Highest

try {
    Register-ScheduledTask `
        -TaskName "IGAutomation-Startup" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null
    Write-Log "[OK] Scheduled task registered - services auto-start silently at logon." "Green"
} catch {
    Write-Log "[WARN] Could not register scheduled task: $($_.Exception.Message)" "Yellow"
    Write-Log "       Shortcut will still start services on demand." "Yellow"
}

# ── DESKTOP SHORTCUT ─────────────────────────────────
$loggedInUser = $null
try { $loggedInUser = (Get-WmiObject -Class Win32_ComputerSystem).UserName -replace '.*\\','' } catch {}

$desktopPaths = @()
if ($loggedInUser) { $desktopPaths += "C:\Users\$loggedInUser\Desktop" }
$desktopPaths += @("$env:USERPROFILE\Desktop", "$env:PUBLIC\Desktop", "C:\Users\Public\Desktop")

foreach ($dp in ($desktopPaths | Select-Object -Unique)) {
    $existing = "$dp\IG Automation.lnk"
    if (Test-Path $existing) { Remove-Item $existing -Force -ErrorAction SilentlyContinue }
}

$iconRefreshCode = @"
using System;
using System.Runtime.InteropServices;
public class IconRefresh {
    [DllImport("Shell32.dll")]
    public static extern void SHChangeNotify(int eventId, int flags, IntPtr item1, IntPtr item2);
}
"@
Add-Type -TypeDefinition $iconRefreshCode -ErrorAction SilentlyContinue

$shortcutCreated = $false
foreach ($dp in ($desktopPaths | Select-Object -Unique)) {
    if ((Test-Path $dp) -and (-not $shortcutCreated)) {
        try {
            $shell    = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut("$dp\IG Automation.lnk")
            $shortcut.TargetPath       = "C:\Windows\System32\wscript.exe"
            $shortcut.Arguments        = "`"$APP_DIR\start.vbs`""
            $shortcut.WorkingDirectory = $APP_DIR
            $shortcut.WindowStyle      = 7
            $shortcut.Description      = "IG Automation"
            $shortcut.IconLocation     = "$APP_DIR\AppIcon.ico,0"
            $shortcut.Save()
            [IconRefresh]::SHChangeNotify(0x8000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
            Write-Log "[OK] Shortcut created: $dp\IG Automation.lnk" "Green"
            $shortcutCreated = $true
        } catch {
            Write-Log "   Shortcut failed at $($dp): $($_.Exception.Message)" "Yellow"
        }
    }
}

Write-Log ""
Write-Log "================================================" "Magenta"
Write-Log "  ALL DONE!" "Magenta"
Write-Log "  Services will auto-start silently at logon." "Magenta"
Write-Log "  Double-click 'IG Automation' on your Desktop" "Magenta"
Write-Log "================================================"
Write-Log "Log: $LOG"
