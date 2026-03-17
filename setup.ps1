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
    try { Add-Content -Path $LOG -Value $line -ErrorAction SilentlyContinue } catch {}
}

function Write-Step($msg) {
    Write-Log ""
    Write-Log ">> $msg" "Cyan"
}

function Refresh-Path {
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
}

# Init log
try {
    "" | Out-File -FilePath $LOG -Encoding utf8 -Force
} catch {
    $LOG = "$env:TEMP\ig-automation-setup.log"
    "" | Out-File -FilePath $LOG -Encoding utf8 -Force
}

Write-Log "================================================" "Magenta"
Write-Log "  IG Automation - Setup" "Magenta"
Write-Log "================================================"
Write-Log "APP_DIR = $APP_DIR"
Write-Log "User    = $env:USERNAME"
Write-Log "OS      = $([System.Environment]::OSVersion.VersionString)"
Write-Log "Log     = $LOG"

try {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine -Force -ErrorAction SilentlyContinue
} catch {}

# ── VERIFY INSTALL ───────────────────────────────────
if (-not (Test-Path $APP_DIR)) {
    Write-Log "[ERROR] $APP_DIR not found. Please reinstall." "Red"
    Read-Host "Press Enter to exit"; exit 1
}
if (-not (Test-Path "$BACKEND\backend.exe")) {
    Write-Log "[ERROR] backend.exe missing. Please reinstall." "Red"
    Read-Host "Press Enter to exit"; exit 1
}
if (-not (Test-Path "$FRONTEND\.next")) {
    Write-Log "[ERROR] Frontend .next folder missing. Please reinstall." "Red"
    Read-Host "Press Enter to exit"; exit 1
}
Write-Log "[OK] Install verified." "Green"

# ── STEP 1: NODE.JS ──────────────────────────────────
Write-Step "[Step 1/3] Checking Node.js..."
Refresh-Path

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

    $downloaded = $false
    try {
        & curl.exe -L --silent --show-error --output $nodeInstaller $nodeUrl
        if ($LASTEXITCODE -eq 0 -and (Test-Path $nodeInstaller) -and (Get-Item $nodeInstaller).Length -gt 1000000) {
            $downloaded = $true
        }
    } catch {}

    if (-not $downloaded) {
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            (New-Object Net.WebClient).DownloadFile($nodeUrl, $nodeInstaller)
            if ((Test-Path $nodeInstaller) -and (Get-Item $nodeInstaller).Length -gt 1000000) {
                $downloaded = $true
            }
        } catch { Write-Log "   WebClient failed: $($_.Exception.Message)" "Yellow" }
    }

    if (-not $downloaded) {
        Write-Log "[ERROR] Could not download Node.js." "Red"
        Write-Log "   Install from https://nodejs.org then re-run: $APP_DIR\run-setup.bat" "Red"
        Read-Host "Press Enter to exit"; exit 1
    }

    Write-Log "   Installing Node.js silently..." "Yellow"
    $proc = Start-Process "msiexec.exe" -ArgumentList "/i `"$nodeInstaller`" /quiet /norestart ADDLOCAL=ALL" -Wait -PassThru
    Remove-Item $nodeInstaller -ErrorAction SilentlyContinue

    if ($proc.ExitCode -notin @(0, 1641, 3010)) {
        Write-Log "[ERROR] Node.js install failed (exit $($proc.ExitCode))" "Red"
        Read-Host "Press Enter to exit"; exit 1
    }

    Refresh-Path
    Start-Sleep -Seconds 3

    foreach ($nodePath in @(
        "$env:PROGRAMFILES\nodejs\node.exe",
        "$env:ProgramFiles(x86)\nodejs\node.exe"
    )) {
        if (Test-Path $nodePath) { $env:PATH = "$env:PATH;$(Split-Path $nodePath)" }
    }
    try { $hasNode = & node --version 2>&1 } catch {}
}

if (-not $hasNode -or $hasNode -notmatch "v\d") {
    Write-Log "[ERROR] Node.js still not found after install." "Red"
    Write-Log "   Restart your computer and re-run: $APP_DIR\run-setup.bat" "Red"
    Read-Host "Press Enter to exit"; exit 1
}
Write-Log "[OK] Node: $hasNode" "Green"

$npmPaths = @(
    (Join-Path $env:PROGRAMFILES "nodejs"),
    (Join-Path $env:APPDATA "npm"),
    (Join-Path $env:LOCALAPPDATA "Programs\nodejs")
)
foreach ($p in $npmPaths) {
    if ($p -and (Test-Path (Join-Path $p "npm.cmd"))) {
        if ($env:PATH -notlike "*$p*") { $env:PATH = "$env:PATH;$p" }
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
        "$env:PROGRAMFILES\Python312\python.exe","C:\Python312\python.exe")) {
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

# Bake npm path at setup time
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
$startBat = @"
@echo off
set PLAYWRIGHT_BROWSERS_PATH=C:\IGAutomation\browsers
set LOG=C:\IGAutomation\launcher-log.txt

echo [%TIME%] ===== start-services.bat ===== >> "%LOG%"

:: ── Find npm ──────────────────────────────────────
set NPM_CMD=
if exist "$npmBaked" (
    set "NPM_CMD=$npmBaked"
    goto npm_ok
)
if exist "%ProgramFiles%\nodejs\npm.cmd" (
    set "NPM_CMD=%ProgramFiles%\nodejs\npm.cmd"
    goto npm_ok
)
if exist "%ProgramFiles(x86)%\nodejs\npm.cmd" (
    set "NPM_CMD=%ProgramFiles(x86)%\nodejs\npm.cmd"
    goto npm_ok
)
if exist "%LOCALAPPDATA%\Programs\nodejs\npm.cmd" (
    set "NPM_CMD=%LOCALAPPDATA%\Programs\nodejs\npm.cmd"
    goto npm_ok
)
if exist "%APPDATA%\npm\npm.cmd" (
    set "NPM_CMD=%APPDATA%\npm\npm.cmd"
    goto npm_ok
)
where npm >nul 2>&1
if %errorlevel%==0 ( set NPM_CMD=npm & goto npm_ok )
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Node.js" /v InstallPath 2^>nul') do (
    if exist "%%b\npm.cmd" ( set "NPM_CMD=%%b\npm.cmd" & goto npm_ok )
)
echo [%TIME%] [ERROR] npm not found >> "%LOG%"
exit /b 1

:npm_ok
echo [%TIME%] npm=%NPM_CMD% >> "%LOG%"

:: ── Kill stale on 8000 / 3000 ─────────────────────
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING" 2^>nul') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul

:: ── Write backend bat with fully resolved path ─────
(
    echo @echo off
    echo cd /d "C:\IGAutomation\backend"
    echo set PLAYWRIGHT_BROWSERS_PATH=C:\IGAutomation\browsers
    echo backend.exe ^>^> "C:\IGAutomation\launcher-log.txt" 2^>^&1
) > "%TEMP%\ig-backend.bat"

:: ── Write frontend bat with fully resolved npm path ─
(
    echo @echo off
    echo cd /d "C:\IGAutomation\frontend"
    echo "%NPM_CMD%" run start ^>^> "C:\IGAutomation\launcher-log.txt" 2^>^&1
) > "%TEMP%\ig-frontend.bat"

:: ── Log what was written for debugging ─────────────
echo [%TIME%] ig-frontend.bat contents: >> "%LOG%"
type "%TEMP%\ig-frontend.bat" >> "%LOG%"

:: ── Start backend ──────────────────────────────────
echo [%TIME%] Starting backend >> "%LOG%"
start "" /B cmd /c ""%TEMP%\ig-backend.bat""

:: ── Start frontend ─────────────────────────────────
echo [%TIME%] Starting frontend >> "%LOG%"
start "" /B cmd /c ""%TEMP%\ig-frontend.bat""

echo [%TIME%] Both services launched >> "%LOG%"
"@
[System.IO.File]::WriteAllText("$APP_DIR\start-services.bat", $startBat, $utf8NoBOM)
Write-Log "   start-services.bat written." "Green"

# ── open-app.bat ─────────────────────────────────────
$openBat = @"
@echo off
set LOG=C:\IGAutomation\launcher-log.txt
echo [%TIME%] ===== open-app.bat ===== >> "%LOG%"

:: ── Fast path: both already up, open immediately ──
netstat -an | findstr ":3000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    netstat -an | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
    if %errorlevel%==0 (
        echo [%TIME%] Both ports up - opening browser >> "%LOG%"
        start "" "http://localhost:3000"
        exit /b 0
    )
)

:: ── Start services ─────────────────────────────────
echo [%TIME%] Starting services >> "%LOG%"
call "C:\IGAutomation\start-services.bat"

:: ── Wait for port 3000 via curl ────────────────────
echo [%TIME%] Waiting for port 3000 >> "%LOG%"
:waitloop
curl -s --max-time 1 http://localhost:3000 >nul 2>&1
if %errorlevel%==0 (
    echo [%TIME%] Port 3000 ready - opening browser >> "%LOG%"
    start "" "http://localhost:3000"
    exit /b 0
)
timeout /t 1 /nobreak >nul
goto waitloop
"@
[System.IO.File]::WriteAllText("$APP_DIR\open-app.bat", $openBat, $utf8NoBOM)
Write-Log "   open-app.bat written." "Green"

# ── start.vbs (thin silent wrapper only) ─────────────
$launchVbs = @"
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd /c C:\IGAutomation\open-app.bat", 0, False
"@
[System.IO.File]::WriteAllText("$APP_DIR\start.vbs", $launchVbs, $utf8NoBOM)
Write-Log "   start.vbs written." "Green"

# ── Scheduled task: start services at logon ──────────
$currentUser = "$env:USERDOMAIN\$env:USERNAME"
Write-Log "   Registering scheduled task for: $currentUser" "Yellow"

Unregister-ScheduledTask -TaskName "IGAutomation-Startup" -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"C:\IGAutomation\start-services.bat`"" `
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
    Write-Log "[OK] Scheduled task registered - services auto-start at logon." "Green"
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
Write-Log "  Services will auto-start on next logon." "Magenta"
Write-Log "  Double-click 'IG Automation' on your Desktop" "Magenta"
Write-Log "================================================"
Write-Log "Log: $LOG"
