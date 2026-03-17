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

# Set execution policy machine-wide silently
try {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine -Force -ErrorAction SilentlyContinue
} catch {}

# VERIFY INSTALL
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
Write-Step "[Step 1/2] Checking Node.js..."
Refresh-Path

$hasNode = $null
try { $hasNode = & node --version 2>&1 } catch {}

# Check common paths
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

# Ensure npm on PATH
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
Write-Step "[Step 2/2] Configuring frontend..."
Set-Location $FRONTEND

$utf8NoBOM = [System.Text.UTF8Encoding]::new($false)

# Write load-env.js for runtime env decryption
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

# node_modules is pre-bundled — no npm install needed
if (Test-Path "$FRONTEND\node_modules") {
    Write-Log "[OK] node_modules pre-bundled - no install needed." "Green"
} else {
    Write-Log "   node_modules missing - running npm install..." "Yellow"
    & npm install --silent 2>&1 | Out-Null
    Write-Log "[OK] npm install complete." "Green"
}

# Set PLAYWRIGHT_BROWSERS_PATH permanently
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

# ── CREATE SILENT VBS LAUNCHER ───────────────────────
Write-Step "Creating launcher and Desktop shortcut..."

$launchVbs = @"
Dim sh
Set sh = CreateObject("WScript.Shell")

Dim APP_DIR, BACKEND, FRONTEND, logFile
APP_DIR  = "C:\IGAutomation"
BACKEND  = APP_DIR & "\backend"
FRONTEND = APP_DIR & "\frontend"
logFile  = APP_DIR & "\launcher-log.txt"

' ── Logging helper (append-mode, no Flush) ──────────
Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")

' Wipe log on fresh launch
fso.OpenTextFile(logFile, 2, True).Close

Sub Log(msg)
    Dim ts, f
    ts = Now()
    Set f = fso.OpenTextFile(logFile, 8, True)  ' 8=ForAppending
    f.WriteLine "[" & Right("0" & Hour(ts), 2) & ":" & Right("0" & Minute(ts), 2) & ":" & Right("0" & Second(ts), 2) & "] " & msg
    f.Close
End Sub

' ── Port check helper ───────────────────────────────
Function PortListening(port)
    PortListening = (sh.Run("cmd /c netstat -an | findstr "":" & port & " "" | findstr ""LISTENING"" >nul 2>&1", 0, True) = 0)
End Function

Log "================ Launcher start ================"
Log "BACKEND="  & BACKEND
Log "FRONTEND=" & FRONTEND

' ── If both already up just open browser ────────────
If PortListening(8000) And PortListening(3000) Then
    Log "Both services already running - opening browser"
    sh.Run "http://localhost:3000"
    WScript.Quit
End If

' ── Kill stale listeners ────────────────────────────
Log "Killing stale listeners on 3000/8000..."
sh.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":3000 "" ^| findstr ""LISTENING""') do taskkill /F /PID %a >nul 2>&1", 0, True
sh.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":8000 "" ^| findstr ""LISTENING""') do taskkill /F /PID %a >nul 2>&1", 0, True
WScript.Sleep 1000

' ── Verify .env.enc exists ──────────────────────────
If Not fso.FileExists(FRONTEND & "\.env.enc") Then
    Log "[ERROR] .env.enc not found"
    MsgBox ".env.enc is missing from:" & vbCrLf & FRONTEND & vbCrLf & "Please reinstall.", 16, "IG Automation - Error"
    WScript.Quit
End If
Log ".env.enc found OK"

' ── Find npm ────────────────────────────────────────
Dim npmCmd
npmCmd = ""

Dim npmFull
npmFull = sh.ExpandEnvironmentStrings("%PROGRAMFILES%\nodejs\npm.cmd")
If fso.FileExists(npmFull) Then npmCmd = npmFull

If npmCmd = "" Then
    Dim npmx86
    npmx86 = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%\nodejs\npm.cmd")
    If fso.FileExists(npmx86) Then npmCmd = npmx86
End If

If npmCmd = "" Then
    Dim npmLocal
    npmLocal = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\nodejs\npm.cmd")
    If fso.FileExists(npmLocal) Then npmCmd = npmLocal
End If

If npmCmd = "" Then
    If sh.Run("cmd /c npm --version >nul 2>&1", 0, True) = 0 Then
        npmCmd = "npm"
    End If
End If

If npmCmd = "" Then
    Log "[ERROR] npm not found anywhere"
    MsgBox "npm (Node.js) was not found." & vbCrLf & "Please install Node.js from https://nodejs.org then re-run setup.", 16, "IG Automation - Error"
    WScript.Quit
End If
Log "npm found: " & npmCmd

' ── Start backend ────────────────────────────────────
Log "Starting backend.exe..."
sh.Run "cmd /c cd /d """ & BACKEND & """ && set PLAYWRIGHT_BROWSERS_PATH=C:\IGAutomation\browsers && backend.exe >> """ & logFile & """ 2>&1", 0, False

' ── Start frontend ───────────────────────────────────
Log "Starting frontend..."
sh.Run "cmd /c cd /d """ & FRONTEND & """ && """ & npmCmd & """ run start >> """ & logFile & """ 2>&1", 0, False

' ── Wait for backend (max 60s) ───────────────────────
Log "Waiting for backend on port 8000..."
Dim i
For i = 1 To 30
    WScript.Sleep 2000
    If PortListening(8000) Then
        Log "Backend ready after " & (i * 2) & "s"
        Exit For
    End If
Next
If Not PortListening(8000) Then Log "[WARN] Backend not ready after 60s"

' ── Wait for frontend (max 120s) ─────────────────────
Log "Waiting for frontend on port 3000..."
Dim frontendReady
frontendReady = False
For i = 1 To 60
    WScript.Sleep 2000
    If PortListening(3000) Then
        Log "Frontend ready after " & (i * 2) & "s - opening browser"
        sh.Run "http://localhost:3000"
        frontendReady = True
        Exit For
    End If
Next

If Not frontendReady Then
    Log "[ERROR] Frontend did not start within 120s - check log above for npm/next errors"
    MsgBox "The frontend did not start within 2 minutes." & vbCrLf & vbCrLf & "Check the log for errors:" & vbCrLf & logFile, 16, "IG Automation - Error"
End If
"@

[System.IO.File]::WriteAllText("$APP_DIR\start.vbs", $launchVbs, [System.Text.UTF8Encoding]::new($false))
Write-Log "   start.vbs written."

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
Write-Log "  Double-click 'IG Automation' on your Desktop" "Magenta"
Write-Log "================================================"
Write-Log "Log: $LOG"
